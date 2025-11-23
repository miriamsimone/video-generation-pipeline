#!/usr/bin/env python3
"""
generate_neutral_pose_sequences.py

Generate pose-transition sequences from neutral at a source pose
(e.g. 'center') to neutral at every other pose (tilt_left_small, nod_down_small, etc.)
using recursive midpoint refinement.

Outputs (for each target pose):
  frames/sequences/neutral_<source_pose>_to_neutral_<target_pose>/
    000.png  # neutral__<source_pose>.png
    050.png  # etc (depending on max_depth)
    100.png  # neutral__<target_pose>.png
    manifest.json

Example:

    export OPENAI_API_KEY=sk-...
    python generate_neutral_pose_sequences.py \
      --config expressions.json \
      --endpoints-dir frames/endpoints \
      --sequences-dir frames/sequences \
      --source-pose center \
      --max-depth 2 \
      --max-workers 8
"""

import argparse
import base64
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List, Optional, Tuple

from openai import OpenAI
from PIL import Image

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


def discover_endpoints(endpoints_dir: str) -> Dict[Tuple[str, str], str]:
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


@dataclass
class Frame:
    t: float
    file: str


@dataclass
class PoseSeq:
    path_id: str
    pose_start: str
    pose_end: str
    expr_id: str
    dir: str
    frames: List[Frame]


@dataclass
class TweenJob:
    path_id: str
    expr_id: str
    pose_start: str
    pose_end: str
    left_t: float
    right_t: float
    mid_t: float
    left_file: str
    right_file: str
    out_file: str
    size: str


def generate_midframe(job: TweenJob, seq_dir: str, cfg: dict) -> None:
    client = OpenAI()
    
    expr_desc = describe_expression(job.expr_id, cfg)
    pose_start_desc = POSE_DESCRIPTIONS.get(
        job.pose_start, job.pose_start.replace("_", " ")
    )
    pose_end_desc = POSE_DESCRIPTIONS.get(
        job.pose_end, job.pose_end.replace("_", " ")
    )

    prompt = f"""
    Watercolor portrait of the same young boy on a transparent background,
    matching the style, identity, hairstyle, clothing, and framing of the
    reference images.

    Important: All references to "left" and "right" are from the boy's
    perspective (his own left/right). If the viewer's left/right is mentioned,
    treat it as secondary clarification.

    Facial expression:
      - Keep the expression identical to the neutral reference:
        {expr_desc}

    Head pose:
      - This frame is an in-between at relative t = {job.mid_t:.2f}
        between these head poses:
          * Start: {pose_start_desc}
          * End:   {pose_end_desc}

      - Only adjust the head orientation/tilt smoothly between these two
        poses. Do NOT change the mouth, eyes, eyebrows shape (beyond minor
        perspective effects), hairstyle, clothing, earrings, or background.
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
        help="Directory root where pose sequences will be written",
    )
    parser.add_argument(
        "--source-pose",
        default="center",
        help="Pose we transition from (default: center)",
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
        "--max-depth",
        type=int,
        default=2,
        help="Recursive midpoint depth; 2 gives t=0.25,0.5,0.75 (default: 2)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing midframes; endpoints are always copied.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    endpoints_map = discover_endpoints(args.endpoints_dir)
    if not endpoints_map:
        raise SystemExit(f"No endpoints found in {args.endpoints_dir}")

    poses = cfg.get("poses", [])
    if not poses:
        raise SystemExit("No 'poses' array found in expressions.json")

    if args.source_pose not in poses:
        print(
            f"[!] source-pose '{args.source_pose}' not in poses; poses: {poses}"
        )

    # Ensure we have neutral expression defined
    if "neutral" not in cfg.get("expressions", {}):
        raise SystemExit("Expression 'neutral' not found in expressions.json")

    expr_id = "neutral"

    neutral_source_key = (expr_id, args.source_pose)
    if neutral_source_key not in endpoints_map:
        raise SystemExit(
            f"Missing endpoint image for neutral at source pose: "
            f"{expr_id}__{args.source_pose}.png"
        )

    os.makedirs(args.sequences_dir, exist_ok=True)

    # Build pose sequences neutral(source) -> neutral(target_pose)
    sequences: Dict[str, PoseSeq] = {}
    for pose in poses:
        if pose == args.source_pose:
            continue

        key_target = (expr_id, pose)
        if key_target not in endpoints_map:
            print(
                f"[i] Skipping pose '{pose}' (no neutral__{pose}.png in endpoints)."
            )
            continue

        src_img = endpoints_map[neutral_source_key]
        tgt_img = endpoints_map[key_target]

        path_id = f"neutral_{args.source_pose}_to_neutral_{pose}"
        seq_dir = os.path.join(args.sequences_dir, path_id)
        os.makedirs(seq_dir, exist_ok=True)

        # endpoints
        f_start = os.path.join(seq_dir, "000.png")
        f_end = os.path.join(seq_dir, "100.png")
        shutil.copy2(src_img, f_start)
        shutil.copy2(tgt_img, f_end)

        frames = [Frame(t=0.0, file="000.png"), Frame(t=1.0, file="100.png")]
        sequences[path_id] = PoseSeq(
            path_id=path_id,
            pose_start=args.source_pose,
            pose_end=pose,
            expr_id=expr_id,
            dir=seq_dir,
            frames=frames,
        )

    if not sequences:
        print("[i] No pose sequences to build (maybe missing neutral tilts).")
        return

    print(f"[i] Initialized {len(sequences)} neutral pose sequences.")

    # Recursive midpoint refinement
    for depth in range(1, args.max_depth + 1):
        print(f"\n=== Pose refinement depth {depth} ===")
        jobs: List[Tuple[TweenJob, PoseSeq]] = []

        for seq in sequences.values():
            seq.frames.sort(key=lambda f: f.t)
            existing_ts = [f.t for f in seq.frames]

            for i in range(len(seq.frames) - 1):
                left = seq.frames[i]
                right = seq.frames[i + 1]
                mid_t = 0.5 * (left.t + right.t)

                if mid_t <= left.t or mid_t >= right.t:
                    continue
                if any(abs(mid_t - t) < 1e-6 for t in existing_ts):
                    continue

                idx = int(round(mid_t * 100))
                out_file = f"{idx:03d}.png"
                out_path = os.path.join(seq.dir, out_file)
                if os.path.exists(out_path) and not args.overwrite:
                    seq.frames.append(Frame(t=mid_t, file=out_file))
                    existing_ts.append(mid_t)
                    continue

                job = TweenJob(
                    path_id=seq.path_id,
                    expr_id=seq.expr_id,
                    pose_start=seq.pose_start,
                    pose_end=seq.pose_end,
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

        print(f"[i] Depth {depth}: {len(jobs)} pose tween frames to generate.")

        def worker(job: TweenJob, seq_dir: str):
            try:
                generate_midframe(job, seq_dir, cfg)
                return job, None
            except Exception as e:
                return job, e

        results: List[Tuple[TweenJob, Optional[Exception]]] = []
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

        for job_res, err in results:
            if err is not None:
                continue
            seq = sequences[job_res.path_id]
            if not any(abs(f.t - job_res.mid_t) < 1e-6 for f in seq.frames):
                seq.frames.append(Frame(t=job_res.mid_t, file=job_res.out_file))

        ok = sum(1 for _, e in results if e is None)
        fail = len(results) - ok
        print(f"[i] Depth {depth} done. Success: {ok}, Failed: {fail}")

    # Write manifests
    for seq in sequences.values():
        seq.frames.sort(key=lambda f: f.t)
        frames_list = [{"t": f.t, "file": f.file} for f in seq.frames]
        manifest = {
            "path_id": seq.path_id,
            "expr_start": seq.expr_id,
            "expr_end": seq.expr_id,
            "pose": f"{seq.pose_start}_to_{seq.pose_end}",
            "frames": frames_list,
        }
        manifest_path = os.path.join(seq.dir, "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"[i] Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()

