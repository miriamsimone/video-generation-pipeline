#!/usr/bin/env python3
"""
generate_head_tilts.py

Take existing extreme expressions (and neutral) at a source pose (e.g. 'center')
and generate all other head tilts for each expression, using OpenAI gpt-image-1.

Inputs:
  - expressions.json (defines expressions + poses)
  - frames/endpoints/<expr_id>__<source_pose>.png  (extreme expression endpoints)
  - optional base neutral image for neutral__<source_pose>.png if missing

Outputs:
  - frames/endpoints/<expr_id>__<pose>.png for every pose in config["poses"]

Example:

    export OPENAI_API_KEY=sk-...

    python generate_head_tilts.py \
        --config expressions.json \
        --endpoints-dir frames/endpoints \
        --base-neutral watercolor_boy_greenscreen.png \
        --source-pose center \
        --max-workers 6
"""

import argparse
import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List, Tuple, Optional

from openai import OpenAI
from PIL import Image

# --- description tables -------------------------------------------------------

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
    """
    Turn an expression id like 'speaking_ah' into a natural-language
    description based on its component mouth/eyes/brows in expressions.json.
    """
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


@dataclass
class TiltJob:
    expr_id: str
    pose_id: str
    source_pose: str
    src_img_path: str  # expression at source_pose
    out_path: str      # expression at pose_id
    size: str


def generate_head_tilt(job: TiltJob, cfg: dict) -> None:
    """
    Use gpt-image-1 to change only the head pose, keeping expression identical.
    """
    client = OpenAI()
    
    expr_desc = describe_expression(job.expr_id, cfg)
    pose_desc = POSE_DESCRIPTIONS.get(job.pose_id, job.pose_id.replace("_", " "))

    prompt = f"""
    Watercolor portrait of the same young boy on a transparent background.
    Use the reference image for his identity, hairstyle, clothing, earrings,
    framing, and facial expression.

    Important: In this description, "left" and "right" refer to the boy's own
    left/right, not the viewer's. When both are mentioned, assume the boy's
    left/right is the source of truth.

    Head pose:
      - Change the head pose to: {pose_desc}.

    Facial expression:
      - Keep the facial expression identical to the reference image.
      - The expression should match this description:
        {expr_desc}

    Only adjust the head's orientation/tilt. Do NOT change the mouth, eyes,
    eyebrows shape (other than small perspective adjustments), hairstyle,
    clothing, earrings, or background.
    """

    with open(job.src_img_path, "rb") as f:
        result = client.images.edit(
            model="gpt-image-1",
            image=[f],
            prompt=prompt,
            size=job.size,
            n=1,
            quality="high",
        )

    b64 = result.data[0].b64_json
    img_bytes = base64.b64decode(b64)
    img = Image.open(BytesIO(img_bytes)).convert("RGBA")
    os.makedirs(os.path.dirname(job.out_path), exist_ok=True)
    img.save(job.out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to expressions.json")
    parser.add_argument(
        "--endpoints-dir",
        default="frames/endpoints",
        help="Directory containing <expr_id>__<pose>.png endpoints",
    )
    parser.add_argument(
        "--base-neutral",
        help=(
            "Path to neutral base image for the boy. "
            "If neutral__<source-pose>.png is missing, this will be used for it."
        ),
    )
    parser.add_argument(
        "--source-pose",
        default="center",
        help="Pose id that existing endpoints are in (default: center)",
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
        help="If set, overwrite existing tilt files instead of skipping.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    endpoints_dir = args.endpoints_dir
    os.makedirs(endpoints_dir, exist_ok=True)

    endpoints_map = discover_endpoints(endpoints_dir)

    # Ensure neutral at source pose exists, using --base-neutral if provided.
    if ("neutral" in cfg.get("expressions", {})) and (
        ("neutral", args.source_pose) not in endpoints_map
    ):
        if not args.base_neutral:
            print(
                "[!] neutral__{sp}.png missing and --base-neutral not provided; "
                "neutral won't be included in head tilts.".format(sp=args.source_pose)
            )
        else:
            neutral_target = os.path.join(
                endpoints_dir, f"neutral__{args.source_pose}.png"
            )
            if not os.path.exists(neutral_target) or args.overwrite:
                print(
                    f"[i] Creating neutral__{args.source_pose}.png from base-neutral."
                )
                img = Image.open(args.base_neutral).convert("RGBA")
                img.save(neutral_target)
                endpoints_map[("neutral", args.source_pose)] = neutral_target

    # Expressions list (use all in config, including 'neutral' if present)
    expr_ids: List[str] = list(cfg["expressions"].keys())

    # Poses we want to cover
    poses: List[str] = cfg.get("poses", [])
    if not poses:
        raise SystemExit("No 'poses' array found in expressions.json")

    if args.source_pose not in poses:
        print(
            f"[!] source-pose '{args.source_pose}' not in config poses; "
            f"poses in config: {poses}"
        )

    # Build jobs: for each expression and each pose, generate from source-pose.
    jobs: List[TiltJob] = []

    for expr_id in expr_ids:
        # Where is this expression at the source pose?
        key_src = (expr_id, args.source_pose)
        src_path: Optional[str] = endpoints_map.get(key_src)

        if src_path is None:
            print(
                f"[i] Missing source pose for expr '{expr_id}' at '{args.source_pose}', skipping."
            )
            continue

        for pose in poses:
            if pose == args.source_pose:
                # Already have this; that's the reference.
                continue

            out_fname = f"{expr_id}__{pose}.png"
            out_path = os.path.join(endpoints_dir, out_fname)

            if os.path.exists(out_path) and not args.overwrite:
                print(f"[i] Exists, skipping tilt: {out_fname}")
                continue

            jobs.append(
                TiltJob(
                    expr_id=expr_id,
                    pose_id=pose,
                    source_pose=args.source_pose,
                    src_img_path=src_path,
                    out_path=out_path,
                    size=args.size,
                )
            )

    if not jobs:
        print("[i] No head-tilt jobs to run (everything exists or nothing to do).")
        return

    print(
        f"[i] Generating {len(jobs)} head-tilted endpoints "
        f"with {args.max_workers} workers..."
    )

    def worker(job: TiltJob):
        try:
            generate_head_tilt(job, cfg)
            return job, None
        except Exception as e:
            return job, e

    results: List[Tuple[TiltJob, Optional[Exception]]] = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_to_job = {executor.submit(worker, j): j for j in jobs}
        for fut in as_completed(future_to_job):
            job = future_to_job[fut]
            job_res, err = fut.result()
            if err is None:
                print(
                    f"[✓] {job_res.expr_id} @ {job_res.pose_id} "
                    f"-> {os.path.basename(job_res.out_path)}"
                )
            else:
                print(
                    f"[!] Failed {job_res.expr_id} @ {job_res.pose_id}: {err}"
                )
            results.append((job_res, err))

    ok = sum(1 for _, e in results if e is None)
    fail = len(results) - ok
    print(f"[i] Done. Success: {ok}, Failed: {fail}")


if __name__ == "__main__":
    main()

