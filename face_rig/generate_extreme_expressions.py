#!/usr/bin/env python3
"""
generate_extreme_expressions.py

Given a base neutral portrait image (the watercolor boy on greenscreen) and
an expressions.json config, generate one "extreme" keyframe for each named
expression (happy_big, speaking_ah, speaking_ee, speaking_uw, etc).

Outputs are saved as:

    <outdir>/<expression_id>__<pose_id>.png

Run:

    export OPENAI_API_KEY=sk-...
    python generate_extreme_expressions.py \
        --config expressions.json \
        --base-image watercolor_boy_greenscreen.png \
        --pose center \
        --outdir frames/endpoints \
        --max-workers 4
"""

import argparse
import base64
import json
import os
from io import BytesIO
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI
from PIL import Image

# ---- Expression description tables (same idea as in generate_sequence.py) ----

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
    Turn an expression id like "speaking_ah" into a natural language description
    based on its mouth/eyes/brows components in expressions.json.
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


def generate_extreme_for_expression(
    base_image_path: str,
    expr_id: str,
    cfg: dict,
    pose_id: str,
    out_path: str,
    size: str = "1024x1536",
) -> None:
    """
    Use gpt-image-1 to edit the base image into the target extreme expression.
    """
    client = OpenAI()  # Initialize client here, not at module level
    
    expr_desc = describe_expression(expr_id, cfg)
    pose_desc = POSE_DESCRIPTIONS.get(pose_id, pose_id.replace("_", " "))

    prompt = f"""
    Watercolor portrait of the same young boy on a transparent background.
    Use the given reference image for his identity, hairstyle, clothing, and
    framing.

    Important: In this description, "left" and "right" refer to the boy's own
    left/right, not the viewer's. When both are mentioned, assume the boy's
    left/right is the source of truth.

    Head pose: {pose_desc}.

    Adjust only the facial expression:

    - Target expression: {expr_desc}

    Make this an extreme, distinct version of this expression while keeping
    the style, character identity, and head pose identical to the reference.
    Only change the mouth, eyes, and eyebrows; do not change hairstyle,
    clothing, earrings, or background.
    """

    with open(base_image_path, "rb") as f:
        result = client.images.edit(
            model="gpt-image-1",
            image=[f],
            prompt=prompt,
            size=size,
            n=1,
            quality="high",
        )

    b64 = result.data[0].b64_json
    img_bytes = base64.b64decode(b64)
    img = Image.open(BytesIO(img_bytes)).convert("RGBA")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to expressions.json")
    parser.add_argument(
        "--base-image", required=True, help="Path to neutral base PNG of the boy"
    )
    parser.add_argument(
        "--pose",
        default="center",
        help="Pose id (must exist in expressions.json poses); default: center",
    )
    parser.add_argument(
        "--outdir",
        required=True,
        help="Directory to write endpoint keyframes, e.g. frames/endpoints",
    )
    parser.add_argument(
        "--size",
        default="1024x1536",
        help='Image size, e.g. "1024x1536" or "1024x1024"',
    )
    parser.add_argument(
        "--include-neutral",
        action="store_true",
        help="If set, also generate a 'neutral' image (otherwise base-image is used for neutral).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="If set, overwrite existing files instead of skipping.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max number of parallel OpenAI calls (default: 4).",
    )

    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.pose not in cfg.get("poses", []):
        print(
            f"[!] Pose '{args.pose}' not found in config poses. "
            f"Available poses: {', '.join(cfg.get('poses', []))}"
        )

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    expressions: List[str] = list(cfg["expressions"].keys())

    # Build list of work items
    jobs: List[Tuple[str, str]] = []  # (expr_id, out_path)

    for expr_id in expressions:
        if expr_id == "neutral" and not args.include_neutral:
            print("[i] Skipping 'neutral' (base image is neutral).")
            continue

        out_name = f"{expr_id}__{args.pose}.png"
        out_path = os.path.join(outdir, out_name)

        if os.path.exists(out_path) and not args.overwrite:
            print(f"[i] Exists, skipping: {out_path}")
            continue

        jobs.append((expr_id, out_path))

    if not jobs:
        print("[i] Nothing to do; all endpoints already exist (or were skipped).")
        return

    print(f"[i] Generating {len(jobs)} expressions with {args.max_workers} workers...")

    def worker(expr_id: str, out_path: str):
        try:
            generate_extreme_for_expression(
                base_image_path=args.base_image,
                expr_id=expr_id,
                cfg=cfg,
                pose_id=args.pose,
                out_path=out_path,
                size=args.size,
            )
            return expr_id, out_path, None
        except Exception as e:
            return expr_id, out_path, e

    # Parallel execution
    results: List[Tuple[str, str, Optional[Exception]]] = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_to_job = {
            executor.submit(worker, expr_id, out_path): (expr_id, out_path)
            for expr_id, out_path in jobs
        }

        for future in as_completed(future_to_job):
            expr_id, out_path = future_to_job[future]
            expr_id_res, out_path_res, err = future.result()
            if err is None:
                print(f"[✓] {expr_id_res} -> {out_path_res}")
            else:
                print(f"[!] Failed {expr_id_res}: {err}")
            results.append((expr_id_res, out_path_res, err))

    ok = sum(1 for _, _, e in results if e is None)
    fail = len(results) - ok
    print(f"[i] Done. Success: {ok}, Failed: {fail}")


if __name__ == "__main__":
    main()

