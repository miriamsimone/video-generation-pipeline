#!/usr/bin/env python3
"""
generate_sequence.py

Tween between two facial expressions for a given head pose using OpenAI gpt-image-1.

Usage example:

    export OPENAI_API_KEY=sk-...
    python generate_sequence.py \
        --config expressions.json \
        --base-path neutral_to_speaking_ah \
        --pose center \
        --start-image frames/endpoints/neutral_center.png \
        --end-image   frames/endpoints/speaking_ah_center.png \
        --outdir      frames/neutral_to_speaking_ah__center \
        --max-depth 3 \
        --distance-threshold 6.0
"""

import argparse
import base64
import json
import math
import os
from dataclasses import dataclass
from io import BytesIO
from typing import List

from openai import OpenAI
from PIL import Image, ImageChops

client = OpenAI()


# ---------- tiny image distance metric ----------

def rms_distance(path_a: str, path_b: str, size=(64, 64)) -> float:
    """Root-mean-square pixel distance between two images (downscaled)."""
    a = Image.open(path_a).convert("RGBA").resize(size, Image.LANCZOS)
    b = Image.open(path_b).convert("RGBA").resize(size, Image.LANCZOS)
    diff = ImageChops.difference(a, b)
    h = diff.histogram()

    # RMS per PIL docs
    sq = (value * (idx ** 2) for idx, value in enumerate(h))
    sum_of_squares = float(sum(sq))
    num_pixels = float(a.size[0] * a.size[1] * 4)  # RGBA
    return math.sqrt(sum_of_squares / max(num_pixels, 1.0))


# ---------- config helpers ----------

def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


MOUTH_DESCRIPTIONS = {
    "neutral": "mouth relaxed and closed in a neutral position",
    "smile_soft": "mouth in a gentle soft smile, lips slightly curved upward",
    "smile_big": "mouth in a big smile, teeth slightly visible and lips widely curved upward",
    "ah": "mouth open vertically in an 'ah' vowel shape, jaw dropped",
    "ee": "mouth stretched horizontally in an 'EE' sound, lips pulled wide",
    "uw": "mouth rounded forward in an 'OO' or 'UW' shape, lips pursed",
    "frown": "mouth in a small frown, the corners slightly downturned"
}

EYE_DESCRIPTIONS = {
    "neutral": "eyes open in a relaxed neutral way",
    "wide": "eyes opened wide in surprise or excitement",
    "squint": "eyes slightly squinting, cheeks raised",
    "blink_closed": "eyes fully closed in a blink"
}

BROW_DESCRIPTIONS = {
    "neutral": "eyebrows in a neutral relaxed position",
    "raise": "eyebrows raised",
    "furrow": "eyebrows drawn together in a small furrow"
}

POSE_DESCRIPTIONS = {
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


# ---------- OpenAI calls ----------

def generate_midframe_from_endpoints(
    left_image_path: str,
    right_image_path: str,
    out_path: str,
    expr_start: str,
    expr_end: str,
    pose_id: str,
    u: float,  # normalized position between left & right, 0..1
    cfg: dict,
    size: str = "1024x1536",
) -> None:
    """
    Generate a frame between two anchor endpoints using both as references.
    u=0 means closer to left, u=1 means closer to right.
    """
    expr_start_desc = describe_expression(expr_start, cfg)
    expr_end_desc = describe_expression(expr_end, cfg)
    pose_desc = POSE_DESCRIPTIONS.get(pose_id, pose_id.replace("_", " "))

    prompt = f"""
    Watercolor portrait of the same young boy on a transparent background,
    matching the style and identity of the reference images.

    Important: All references to "left" and "right" are from the boy's
    perspective (his own left/right). If the viewer's left/right is mentioned,
    treat it as secondary clarification.

    Head pose: {pose_desc}.

    This frame should sit at relative position u = {u:.2f} between these two
    expressions:

      - Start: {expr_start_desc}
      - End:   {expr_end_desc}

    Only the mouth, eyes, and eyebrows should change smoothly between the
    two references. Keep hairstyle, clothing, proportions, and framing
    identical to the references.
    """

    with open(left_image_path, "rb") as fa, open(right_image_path, "rb") as fb:
        # NOTE: `image` must be a list; no `response_format` param
        result = client.images.edit(
            model="gpt-image-1",
            image=[fa, fb],
            prompt=prompt,
            size=size,
            n=1,
            quality="high",
        )

    # Default response is b64_json, so just decode it
    b64 = result.data[0].b64_json
    img_bytes = base64.b64decode(b64)
    img = Image.open(BytesIO(img_bytes))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)


def generate_midframe_openai(
    base_image_path: str,
    out_path: str,
    expr_start: str,
    expr_end: str,
    pose_id: str,
    t_mid: float,
    cfg: dict,
    size: str = "1024x1536",
) -> None:
    """
    Use gpt-image-1 to produce a midframe starting from base_image_path.
    """
    expr_start_desc = describe_expression(expr_start, cfg)
    expr_end_desc = describe_expression(expr_end, cfg)
    pose_desc = POSE_DESCRIPTIONS.get(pose_id, pose_id.replace("_", " "))

    prompt = f"""
    Watercolor portrait of the same young boy on a transparent background,
    in a consistent style with the reference image.

    Important: All references to "left" and "right" are from the boy's
    perspective (his own left/right). If the viewer's left/right is mentioned,
    treat it as secondary clarification.

    Head pose: {pose_desc}.

    His facial expression should be halfway between these two descriptions:

    - Start: {expr_start_desc}
    - End: {expr_end_desc}

    Render a single in-between frame appropriate for time t = {t_mid:.2f}
    between the start and end expressions. Only adjust the mouth, eyes,
    and eyebrows. Keep hairstyle, clothing, proportions, and framing
    identical to the reference.
    """

    with open(base_image_path, "rb") as f:
        # NOTE: `image` must be a list; no `response_format` param
        result = client.images.edit(
            model="gpt-image-1",
            image=[f],
            prompt=prompt,
            size=size,
            n=1,
            quality="high",
        )

    # Default response is b64_json, so just decode it
    b64 = result.data[0].b64_json
    img_bytes = base64.b64decode(b64)
    img = Image.open(BytesIO(img_bytes))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)


# ---------- core refinement ----------

@dataclass
class Frame:
    t: float          # position along path [0,1]
    expr_id: str      # e.g. "neutral" or "speaking_ah"
    pose_id: str      # e.g. "center"
    filename: str     # path to PNG on disk


def refine_once(
    frames: List[Frame],
    path_id: str,
    expr_start: str,
    expr_end: str,
    pose_id: str,
    cfg: dict,
    outdir: str,
    distance_threshold: float,
    max_depth: int,
    current_depth: int,
    size: str
) -> bool:
    """
    One pass over the list, trying to insert midframes where frames are "far".
    Returns True if any new frame was added.
    """
    if current_depth >= max_depth:
        return False

    changed = False
    i = 0
    while i < len(frames) - 1:
        a = frames[i]
        b = frames[i + 1]

        d = rms_distance(a.filename, b.filename)
        print(f"[{path_id}] depth={current_depth} segment {i}-{i+1} d={d:.2f}")

        if d < distance_threshold:
            i += 1
            continue

        t_mid = 0.5 * (a.t + b.t)
        frame_index = int(round(t_mid * 100))
        out_name = f"{frame_index:03d}.png"
        out_path = os.path.join(outdir, out_name)

        # choose base frame closer to mid
        base = a if abs(t_mid - a.t) < abs(t_mid - b.t) else b

        print(f"  -> generating midframe at t={t_mid:.2f} -> {out_name}")
        generate_midframe_openai(
            base_image_path=base.filename,
            out_path=out_path,
            expr_start=expr_start,
            expr_end=expr_end,
            pose_id=pose_id,
            t_mid=t_mid,
            cfg=cfg,
            size=size
        )

        mid_frame = Frame(t=t_mid, expr_id=f"{expr_start}_to_{expr_end}_mid", pose_id=pose_id, filename=out_path)
        frames.insert(i + 1, mid_frame)

        changed = True
        i += 2  # skip over the newly inserted frame
    return changed


def refine_path(
    frames: List[Frame],
    path_id: str,
    expr_start: str,
    expr_end: str,
    pose_id: str,
    cfg: dict,
    outdir: str,
    distance_threshold: float,
    max_depth: int,
    size: str
) -> None:
    depth = 0
    while depth < max_depth:
        print(f"\n=== refinement depth {depth} ===")
        changed = refine_once(
            frames,
            path_id,
            expr_start,
            expr_end,
            pose_id,
            cfg,
            outdir,
            distance_threshold,
            max_depth,
            current_depth=depth,
            size=size
        )
        frames.sort(key=lambda f: f.t)
        if not changed:
            print("No more segments above threshold; stopping.")
            break
        depth += 1

    print("\nFinal frame order:")
    for f in frames:
        print(f"  t={f.t:.2f}  -> {os.path.basename(f.filename)}")


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to expressions.json")
    parser.add_argument("--base-path", required=True, help="ID from base_paths, e.g. neutral_to_speaking_ah")
    parser.add_argument("--pose", required=True, help="Pose ID, e.g. center or tilt_left_small")
    parser.add_argument("--start-image", required=True, help="PNG for start expression at this pose")
    parser.add_argument("--end-image", required=True, help="PNG for end expression at this pose")
    parser.add_argument("--outdir", required=True, help="Directory to write frames into")
    parser.add_argument("--size", default="1024x1536", help="gpt-image-1 size, e.g. 1024x1536 or 1024x1024")
    parser.add_argument("--distance-threshold", type=float, default=6.0, help="RMS threshold to stop refining a segment")
    parser.add_argument("--max-depth", type=int, default=3, help="Max refinement depth")

    args = parser.parse_args()

    cfg = load_config(args.config)

    # find base path
    base_path = None
    for p in cfg["base_paths"]:
        if p["id"] == args.base_path:
            base_path = p
            break

    if base_path is None:
        raise SystemExit(f"Base path '{args.base_path}' not found in config.")

    expr_start = base_path["start"]
    expr_end = base_path["end"]
    pose_id = args.pose

    os.makedirs(args.outdir, exist_ok=True)

    # initial frames
    start_out = os.path.join(args.outdir, "000.png")
    end_out = os.path.join(args.outdir, "100.png")

    # copy or symlink could be used; here we just reuse paths directly
    # You can also copy the files into outdir if you want everything local.
    frames: List[Frame] = [
        Frame(t=0.0, expr_id=expr_start, pose_id=pose_id, filename=args.start_image),
        Frame(t=1.0, expr_id=expr_end,   pose_id=pose_id, filename=args.end_image),
    ]

    refine_path(
        frames=frames,
        path_id=f"{args.base_path}__{pose_id}",
        expr_start=expr_start,
        expr_end=expr_end,
        pose_id=pose_id,
        cfg=cfg,
        outdir=args.outdir,
        distance_threshold=args.distance_threshold,
        max_depth=args.max_depth,
        size=args.size
    )


if __name__ == "__main__":
    main()

