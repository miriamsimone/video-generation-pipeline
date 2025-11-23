#!/usr/bin/env python3
"""
generate_all_sequences.py

Generate tween sequences for all base_paths and poses using recursive
midpoint refinement (binary subdivision) up to max_depth.

- Discovers endpoints like: frames/endpoints/<expr_id>__<pose>.png
- Uses expressions.json["base_paths"] to find (start_expr, end_expr) pairs
- For each (base_path, pose) where both endpoints exist:
    - Creates: <sequences_dir>/<base_path_id>__<pose>/
    - Copies endpoints as 000.png (t=0.0) and 100.png (t=1.0)
    - For depth = 1..max_depth:
        - For each adjacent pair of frames, generate a midpoint frame.
- Writes manifest.json in each sequence directory.

With max_depth=2, the default, you get tweens at 0.25, 0.5, 0.75.

Example:

    export OPENAI_API_KEY=sk-...
    python generate_all_sequences.py \
        --config expressions.json \
        --endpoints-dir frames/endpoints \
        --sequences-dir frames/sequences \
        --max-depth 2 \
        --max-workers 6
"""

import argparse
import base64
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List, Tuple, Optional

from openai import OpenAI
from PIL import Image

# ---- Shared description tables (same spirit as other scripts) ----

MOUTH_DESCRIPTIONS: Dict[str, str] = {
    "neutral": "mouth relaxed and closed in a neutral position",
    "smile_soft": "mouth in a gentle soft smile, lips slightly curved upward",
    "smile_big": "mouth in a big smile, teeth slightly visible and lips widely curved upward",
    "ah": "mouth open vertically in an 'ah' vowel shape, jaw dropped",
    "ee": "mouth stretched horizontally in an 'EE' sound, lips pulled wide",
    "uw": "mouth rounded forward in an 'OO' or 'UW' shape, lips pursed",
    "frown": "mouth in a small frown, the corners slightly downturned",
}

EYE_DESCRIPTIONS: Dict[str, str] = {
    "neutral": "eyes open in a relaxed neutral way",
    "wide": "eyes opened wide in surprise or excitement",
    "squint": "eyes slightly squinting, cheeks raised",
    "blink_closed": "eyes fully closed in a blink",
}

BROW_DESCRIPTIONS: Dict[str, str] = {
    "neutral": "eyebrows in a neutral relaxed position",
    "raise": "eyebrows raised",
    "furrow": "eyebrows drawn together in a small furrow",
}

POSE_DESCRIPTIONS: Dict[str, str] = {
    "center": (
        "head upright, facing the viewer directly"
    ),
    "tilt_left_small": (
        "head tilted slightly toward the boy's left shoulder "
        "(which appears on the right side of the image to the viewer)"
    ),
    "tilt_right_small": (
        "head tilted slightly toward the boy's right shoulder "
        "(which appears on the left side of the image to the viewer)"
    ),
    "nod_down_small": (
        "head tilted slightly downward as if nodding, with the chin moving "
        "closer to the chest"
    ),
    "nod_up_small": (
        "head tilted slightly upward, as if looking a bit above eye level"
    ),
}


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def describe_expression(expr_id: str, cfg: dict) -> str:
    expr = cfg["expressions"][expr_id]
    mouth = expr["mouth"]
    eyes = expr["eyes"]
    brows = expr["brows"]

    return (
        f"{MOUTH_DESCRIPTIONS.get(mouth, mouth)}, "
        f"{EYE_DESCRIPTIONS.get(eyes, eyes)}, "
        f"{BROW_DESCRIPTIONS.get(brows, brows)}"
    )


@dataclass
class Frame:
    t: float
    file: str  # relative filename in the sequence dir, e.g. "025.png"


@dataclass
class SequenceState:
    path_id: str          # base_path_id__pose
    expr_start: str
    expr_end: str
    pose_id: str
    dir: str              # sequence directory
    frames: List[Frame]   # frames with t in [0,1]


@dataclass
class TweenJob:
    path_id: str
    expr_start: str
    expr_end: str
    pose_id: str
    left_t: float
    right_t: float
    mid_t: float
    left_file: str   # relative filenames like "000.png"
    right_file: str
    out_file: str    # relative filename like "050.png"
    size: str


def discover_endpoints(endpoints_dir: str) -> Dict[Tuple[str, str], str]:
    """
    Scan endpoints_dir for files named <expr_id>__<pose>.png
    Returns a map (expr_id, pose) -> filepath.
    """
    mapping: Dict[Tuple[str, str], str] = {}
    for fname in os.listdir(endpoints_dir):
        if not fname.lower().endswith(".png"):
            continue
        stem = fname[:-4]
        if "__" not in stem:
            continue
        expr_id, pose = stem.split("__", 1)
        full_path = os.path.join(endpoints_dir, fname)
        mapping[(expr_id, pose)] = full_path
    return mapping


def generate_midframe(job: TweenJob, seq_dir: str, cfg: dict) -> None:
    client = OpenAI()  # Initialize per-thread
    
    expr_start_desc = describe_expression(job.expr_start, cfg)
    expr_end_desc = describe_expression(job.expr_end, cfg)
    pose_desc = POSE_DESCRIPTIONS.get(job.pose_id, job.pose_id.replace("_", " "))

    prompt = f"""
    Watercolor portrait of the same young boy on a transparent background,
    matching the style, identity, hairstyle, clothing, and framing of the
    reference images.

    Important: All references to "left" and "right" are from the boy's
    perspective (his own left/right). If the viewer's left/right is mentioned,
    treat it as secondary clarification.

    Head pose: {pose_desc}.

    Generate a single in-between frame at relative position t = {job.mid_t:.2f}
    between these two facial expressions:

      - Start: {expr_start_desc}
      - End:   {expr_end_desc}

    Only adjust the mouth, eyes, and eyebrows smoothly between the two
    reference expressions. Do NOT change hairstyle, clothing, earrings,
    or background. Keep proportions and framing identical.
    """

    left_path = os.path.join(seq_dir, job.left_file)
    right_path = os.path.join(seq_dir, job.right_file)

    with open(left_path, "rb") as fa, open(right_path, "rb") as fb:
        result = client.images.edit(
            model="gpt-image-1",
            image=[fa, fb],
            prompt=prompt,
            size=job.size,
            n=1,
            quality="high",
        )

    b64 = result.data[0].b64_json
    img_bytes = base64.b64decode(b64)
    img = Image.open(BytesIO(img_bytes)).convert("RGBA")
    out_path = os.path.join(seq_dir, job.out_file)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to expressions.json")
    parser.add_argument(
        "--endpoints-dir",
        default="frames/endpoints",
        help="Directory containing <expr_id>__<pose>.png endpoints",
    )
    parser.add_argument(
        "--sequences-dir",
        default="frames/sequences",
        help="Directory root where sequences will be written",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Recursive midpoint depth; 2 gives t=0.25,0.5,0.75 (default: 2)",
    )
    parser.add_argument(
        "--size",
        default="1024x1536",
        help='Image size, e.g. "1024x1536" or "1024x1024"',
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max number of parallel OpenAI calls (default: 4)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="If set, overwrite existing tween frames (endpoints are always copied).",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    endpoints_map = discover_endpoints(args.endpoints_dir)
    if not endpoints_map:
        raise SystemExit(f"No endpoints found in {args.endpoints_dir}")

    poses = sorted({pose for (_, pose) in endpoints_map.keys()})
    print(f"[i] Found poses in endpoints: {poses}")

    base_paths = cfg["base_paths"]  # list of {id, start, end}
    os.makedirs(args.sequences_dir, exist_ok=True)

    # Build initial sequence states (just endpoints 0 and 1)
    sequences: Dict[str, SequenceState] = {}

    for pose_id in poses:
        for bp in base_paths:
            expr_start = bp["start"]
            expr_end = bp["end"]
            path_base_id = bp["id"]
            path_id = f"{path_base_id}__{pose_id}"

            key_start = (expr_start, pose_id)
            key_end = (expr_end, pose_id)

            if key_start not in endpoints_map or key_end not in endpoints_map:
                # missing endpoints for this pose, skip
                continue

            start_img = endpoints_map[key_start]
            end_img = endpoints_map[key_end]

            seq_dir = os.path.join(args.sequences_dir, path_id)
            os.makedirs(seq_dir, exist_ok=True)

            # Copy endpoints into sequence dir as 000.png and 100.png
            f_start = os.path.join(seq_dir, "000.png")
            f_end = os.path.join(seq_dir, "100.png")

            shutil.copy2(start_img, f_start)
            shutil.copy2(end_img, f_end)

            frames = [
                Frame(t=0.0, file="000.png"),
                Frame(t=1.0, file="100.png"),
            ]

            sequences[path_id] = SequenceState(
                path_id=path_id,
                expr_start=expr_start,
                expr_end=expr_end,
                pose_id=pose_id,
                dir=seq_dir,
                frames=frames,
            )

    if not sequences:
        print("[i] No sequences to generate (no matching endpoint pairs).")
        return

    print(f"[i] Initialized {len(sequences)} sequences with endpoints.")

    # Recursive refinement by depth
    for depth in range(1, args.max_depth + 1):
        print(f"\n=== Refinement depth {depth} ===")
        jobs: List[Tuple[TweenJob, SequenceState]] = []

        # Build jobs for this depth across all sequences
        for seq in sequences.values():
            # sort frames by t
            seq.frames.sort(key=lambda f: f.t)

            # for each adjacent pair, schedule a midpoint if it doesn't exist yet
            existing_ts = [f.t for f in seq.frames]
            for i in range(len(seq.frames) - 1):
                left = seq.frames[i]
                right = seq.frames[i + 1]
                mid_t = 0.5 * (left.t + right.t)

                # Only care about midpoints strictly between endpoints
                if mid_t <= left.t or mid_t >= right.t:
                    continue

                # Skip if a frame near mid_t already exists
                if any(abs(mid_t - t) < 1e-6 for t in existing_ts):
                    continue

                idx = int(round(mid_t * 100))
                out_file = f"{idx:03d}.png"
                out_path = os.path.join(seq.dir, out_file)

                if os.path.exists(out_path) and not args.overwrite:
                    # if it exists and we're not overwriting, just register it
                    seq.frames.append(Frame(t=mid_t, file=out_file))
                    existing_ts.append(mid_t)
                    continue

                job = TweenJob(
                    path_id=seq.path_id,
                    expr_start=seq.expr_start,
                    expr_end=seq.expr_end,
                    pose_id=seq.pose_id,
                    left_t=left.t,
                    right_t=right.t,
                    mid_t=mid_t,
                    left_file=left.file,
                    right_file=right.file,
                    out_file=out_file,
                    size=args.size,
                )
                jobs.append((job, seq))

        if not jobs:
            print("[i] No new midpoints to generate at this depth.")
            continue

        print(f"[i] Depth {depth}: {len(jobs)} tween frames to generate.")

        # Parallel execution at this depth
        results: List[Tuple[TweenJob, Optional[Exception]]] = []

        def worker(job: TweenJob, seq_dir: str) -> Tuple[TweenJob, Optional[Exception]]:
            try:
                generate_midframe(job, seq_dir, cfg)
                return job, None
            except Exception as e:
                return job, e

        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_to_job = {
                executor.submit(worker, job, seq.dir): job for (job, seq) in jobs
            }
            for fut in as_completed(future_to_job):
                job = future_to_job[fut]
                job_res, err = fut.result()
                if err is None:
                    print(
                        f"[✓] {job_res.path_id} t={job_res.mid_t:.3f} "
                        f"-> {job_res.out_file}"
                    )
                else:
                    print(
                        f"[!] Failed {job_res.path_id} t={job_res.mid_t:.3f}: {err}"
                    )
                results.append((job_res, err))

        # Register successful frames in our sequence states
        for job_res, err in results:
            if err is not None:
                continue
            seq = sequences[job_res.path_id]
            # avoid duplicates
            if not any(abs(f.t - job_res.mid_t) < 1e-6 for f in seq.frames):
                seq.frames.append(Frame(t=job_res.mid_t, file=job_res.out_file))

        ok = sum(1 for _, e in results if e is None)
        fail = len(results) - ok
        print(f"[i] Depth {depth} done. Success: {ok}, Failed: {fail}")

    # Write manifest.json for each sequence
    for seq in sequences.values():
        seq.frames.sort(key=lambda f: f.t)
        frames_list = [{"t": f.t, "file": f.file} for f in seq.frames]
        manifest = {
            "path_id": seq.path_id,
            "expr_start": seq.expr_start,
            "expr_end": seq.expr_end,
            "pose": seq.pose_id,
            "frames": frames_list,
        }
        manifest_path = os.path.join(seq.dir, "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"[i] Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()

