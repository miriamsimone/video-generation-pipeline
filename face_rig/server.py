#!/usr/bin/env python3
import os
import sys
import json
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Dict, List
from pydantic import BaseModel

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from PIL import Image
import replicate
import openai

# --- CONFIG ---

REPLICATE_MODEL = os.environ.get("REPLICATE_MODEL")  # e.g. "minimax/hailuo-2.3:VERSION_HASH"
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# Video generation is optional - server can still serve existing frames without it
if not REPLICATE_MODEL or not REPLICATE_API_TOKEN:
    print("⚠️  REPLICATE_MODEL and/or REPLICATE_API_TOKEN not set")
    print("    Video generation features will be disabled")
    print("    Server will still serve existing frames and timelines")
    REPLICATE_MODEL = None

# Prompts per part/action — tweak as needed
PROMPTS: Dict[str, Dict[str, str]] = {
    "eyes": {
        "blink": (
            "[Static shot] A close-up of the boy's face, same framing as the first frame. "
            "The head does NOT move or tilt at all. Only the eyelids gently blink a few times. "
            "No changes to the mouth, nose, or eyebrows. Flat bright green background."
        ),
        "look_left": (
            "[Static shot] A close-up of the boy's face. The head stays perfectly still. "
            "Only the eyeballs move smoothly to look left and then return to center. "
            "Eyelids, eyebrows, mouth, and jaw remain almost completely still. Flat bright green background."
        ),
        "look_right": (
            "[Static shot] A close-up of the boy's face. The head stays perfectly still. "
            "Only the eyeballs move smoothly to look right and then return to center. "
            "Eyelids, eyebrows, mouth, and jaw remain almost completely still. Flat bright green background."
        ),
    },
    "brows": {
        "raise": (
            "[Static shot] A close-up of the boy's face. Camera and head do not move. "
            "Only the eyebrows lift slightly in surprise and then relax. "
            "Eyes mostly stay centered and the mouth stays neutral. Flat bright green background."
        ),
        "furrow": (
            "[Static shot] A close-up of the boy's face. Camera and head stay still. "
            "Only the eyebrows furrow into a thinking expression, then relax toward neutral. "
            "Eyes and mouth barely move. Flat bright green background."
        ),
    },
    "mouth": {
        "talk_loop": (
            "[Static shot] A close-up of the boy's face. No camera motion. "
            "The head does not move at all. Only the mouth moves in a natural, subtle talking loop "
            "as if speaking silently. Eyes and eyebrows stay mostly still. Flat bright green background."
        ),
        "smile": (
            "[Static shot] A close-up of the boy's face. Camera and head are completely still. "
            "Only the mouth slowly transitions from neutral to a gentle smile and then back to neutral. "
            "Eyes and eyebrows remain almost unchanged. Flat bright green background."
        ),
    },
}

# Timeline config
FRAMES_DIR = Path(__file__).parent / "frames"
SEQUENCES_DIR = FRAMES_DIR / "sequences"
TIMELINES_DIR = SEQUENCES_DIR  # Alias for compatibility
AUDIO_DIR = Path(__file__).parent / "audio"
CONFIG_PATH = Path(__file__).parent / "expressions.json"

# Ensure audio directory exists
AUDIO_DIR.mkdir(exist_ok=True)

# --- MODELS ---

class FrameInfo(BaseModel):
    t: float
    file: str

class Timeline(BaseModel):
    path_id: str
    expr_start: str
    expr_end: str
    pose: str
    frames: List[FrameInfo]

class RegenerateRequest(BaseModel):
    t: float

class EmotionRequest(BaseModel):
    transcript: str
    phoneme_timeline: List[Dict]
    total_duration_ms: int

class AlignmentRequest(BaseModel):
    transcript: str

class ExportRequest(BaseModel):
    combined_timeline: List[Dict]
    audio_url: str
    format: str  # "mp4" or "webm"
    fps: int = 24

app = FastAPI()

# CORS so your browser app can talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- TIMELINE HELPERS ---

def parse_path_id(path_id: str) -> tuple:
    """Parse path_id like 'neutral_to_speaking_ah__center' -> (expr_start, expr_end, pose)"""
    if "__" not in path_id:
        raise ValueError(f"Invalid path_id format: {path_id}")
    
    base, pose = path_id.rsplit("__", 1)
    
    # Try to extract start/end from base_path pattern
    if "_to_" in base:
        parts = base.split("_to_")
        if len(parts) == 2:
            return parts[0], parts[1], pose
    
    # Fallback: assume it's in config
    return base.split("_")[0], base.split("_")[-1], pose


def scan_timeline_frames(path_id: str) -> Timeline:
    """Scan a frames directory and return Timeline manifest"""
    # Check sequences directory first, then fall back to frames root
    frames_path = SEQUENCES_DIR / path_id
    if not frames_path.exists() or not frames_path.is_dir():
        frames_path = FRAMES_DIR / path_id
    
    if not frames_path.exists() or not frames_path.is_dir():
        raise HTTPException(404, f"Timeline directory not found: {path_id}")
    
    # Check for manifest.json first
    manifest_path = frames_path / "manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path) as f:
                data = json.load(f)
            # Validate and return
            frames = [FrameInfo(**f) for f in data.get("frames", [])]
            return Timeline(
                path_id=data["path_id"],
                expr_start=data["expr_start"],
                expr_end=data["expr_end"],
                pose=data["pose"],
                frames=frames
            )
        except Exception as e:
            print(f"[!] Failed to load manifest.json: {e}, falling back to scan")
    
    
    # Parse path_id to get metadata
    try:
        expr_start, expr_end, pose = parse_path_id(path_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    
    # Scan for PNG files
    frames = []
    for png_file in sorted(frames_path.glob("*.png")):
        filename = png_file.name
        # Extract t from filename like "050.png" -> 0.50
        stem = png_file.stem
        try:
            t = int(stem) / 100.0
            frames.append(FrameInfo(t=t, file=filename))
        except ValueError:
            # Skip files that don't match NNN.png pattern
            continue
    
    return Timeline(
        path_id=path_id,
        expr_start=expr_start,
        expr_end=expr_end,
        pose=pose,
        frames=sorted(frames, key=lambda f: f.t)
    )


# --- TIMELINE ENDPOINTS ---

@app.get("/timelines")
def list_timelines() -> List[str]:
    """List all available timeline path_ids"""
    timelines = []
    
    # Check sequences directory first
    if SEQUENCES_DIR.exists():
        for item in SEQUENCES_DIR.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                timelines.append(item.name)
    
    # Also check root frames directory (legacy)
    if FRAMES_DIR.exists():
        for item in FRAMES_DIR.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                # Skip 'endpoints' and 'sequences' directories
                if item.name not in ("endpoints", "sequences") and item.name not in timelines:
                    timelines.append(item.name)
    
    return sorted(timelines)


@app.get("/timeline/{path_id:path}")
def get_timeline(path_id: str) -> Timeline:
    """Get timeline manifest with all frames"""
    return scan_timeline_frames(path_id)


@app.post("/timeline/{path_id:path}/regenerate")
async def regenerate_frame(
    path_id: str,
    req: RegenerateRequest,
    anchor_start_t: float = Query(None, description="t of left anchor; defaults to first frame"),
    anchor_end_t: float = Query(None, description="t of right anchor; defaults to last frame"),
) -> FrameInfo:
    """
    Regenerate a specific frame at time t using generate_sequence.py
    
    If anchor_start_t and anchor_end_t are provided, regenerates from those two
    frames as trusted anchors. Otherwise uses the nearest neighbor frame.
    """
    t = req.t
    
    # Don't regenerate endpoints
    if t <= 0 or t >= 1:
        raise HTTPException(400, "Cannot regenerate endpoint frames (t=0 or t=1)")
    
    # Parse path_id
    try:
        expr_start, expr_end, pose = parse_path_id(path_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    
    # Load config
    if not CONFIG_PATH.exists():
        raise HTTPException(500, "expressions.json not found")
    
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    
    # Get current timeline to find frames
    timeline = scan_timeline_frames(path_id)
    frames_path = FRAMES_DIR / path_id
    
    if not frames_path.exists():
        raise HTTPException(404, f"Timeline directory not found: {path_id}")
    
    # Determine output path
    frame_index = int(round(t * 100))
    out_name = f"{frame_index:03d}.png"
    out_path = frames_path / out_name
    
    # Import generation functions
    try:
        from generate_sequence import (
            generate_midframe_openai,
            generate_midframe_from_endpoints,
            load_config,
        )
        
        cfg = load_config(str(CONFIG_PATH))
        
        # Check if we're using anchors
        if anchor_start_t is not None and anchor_end_t is not None:
            # ANCHOR MODE: regenerate from two trusted endpoints
            print(f"[regenerate] Using anchor mode: t={t:.2f}, anchors=[{anchor_start_t:.2f}, {anchor_end_t:.2f}]")
            
            # Find the anchor frames
            def find_closest_frame(target_t: float):
                best = timeline.frames[0]
                best_diff = abs(best.t - target_t)
                for frame in timeline.frames[1:]:
                    diff = abs(frame.t - target_t)
                    if diff < best_diff:
                        best = frame
                        best_diff = diff
                return best
            
            left_frame = find_closest_frame(anchor_start_t)
            right_frame = find_closest_frame(anchor_end_t)
            
            if left_frame.t >= right_frame.t:
                raise HTTPException(400, "Invalid anchors: left.t must be < right.t")
            
            # Compute normalized position between anchors
            u = (t - left_frame.t) / (right_frame.t - left_frame.t)
            
            left_path = frames_path / left_frame.file
            right_path = frames_path / right_frame.file
            
            if not left_path.exists() or not right_path.exists():
                raise HTTPException(404, "Anchor frames not found")
            
            print(f"[regenerate] Anchors: left={left_frame.file} (t={left_frame.t:.2f}), right={right_frame.file} (t={right_frame.t:.2f}), u={u:.3f}")
            
            generate_midframe_from_endpoints(
                left_image_path=str(left_path),
                right_image_path=str(right_path),
                out_path=str(out_path),
                expr_start=expr_start,
                expr_end=expr_end,
                pose_id=pose,
                u=u,
                cfg=cfg,
            )
        else:
            # SINGLE-BASE MODE: use nearest neighbor (legacy behavior)
            print(f"[regenerate] Using single-base mode: t={t:.2f}")
            
            # Look for endpoint frames (or use endpoints directory)
            start_img = frames_path / "000.png"
            end_img = frames_path / "100.png"
            
            if not start_img.exists():
                endpoints_dir = FRAMES_DIR / "endpoints"
                start_img = endpoints_dir / f"{expr_start}_{pose}.png"
            
            if not end_img.exists():
                endpoints_dir = FRAMES_DIR / "endpoints"
                end_img = endpoints_dir / f"{expr_end}_{pose}.png"
            
            if not start_img.exists() or not end_img.exists():
                raise HTTPException(404, "Endpoint frames not found")
            
            # Choose which endpoint is closer to use as base
            base_image = start_img if abs(t - 0.0) < abs(t - 1.0) else end_img
            
            generate_midframe_openai(
                base_image_path=str(base_image),
                out_path=str(out_path),
                expr_start=expr_start,
                expr_end=expr_end,
                pose_id=pose,
                t_mid=t,
                cfg=cfg,
            )
        
        print(f"[regenerate] Successfully generated {out_path}")
        
    except Exception as e:
        print(f"[regenerate] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Regeneration failed: {e}")
    
    return FrameInfo(t=t, file=out_name)


@app.get("/frames/{path_id:path}/{filename}")
async def get_frame_image(path_id: str, filename: str):
    """Serve a frame PNG"""
    # Check sequences directory first, then fall back to frames root
    file_path = SEQUENCES_DIR / path_id / filename
    if not file_path.exists() or not file_path.is_file():
        file_path = FRAMES_DIR / path_id / filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "Frame not found")
    
    return FileResponse(file_path, media_type="image/png")


# --- FACE ANIMATOR ENDPOINT ---

def call_replicate_animate(part: str, action: str, crop_png: BytesIO) -> bytes:
    prompt = PROMPTS.get(part, {}).get(action)
    if not prompt:
        raise HTTPException(400, f"Unknown part/action: {part}/{action}")

    crop_png.seek(0)

    try:
        output = replicate.run(
            REPLICATE_MODEL,
            input={
                "prompt": prompt,
                "duration": 6,
                "first_frame_image": crop_png,
                "prompt_optimizer": False,
                "resolution": "1080p",
            },
        )
    except Exception as e:
        # Bubble up any Replicate error in a readable way
        raise HTTPException(500, f"Replicate run failed: {e}")

    # Debug – see what shape we're getting
    print("Replicate output type:", type(output))
    print("Replicate output repr (truncated):", repr(output)[:500])

    # Try to handle the common shapes:
    from replicate.helpers import FileOutput

    # Case 1: single FileOutput (newer Python client)
    if isinstance(output, FileOutput):
        return output.read()

    # Case 2: list[...] (older style or multi-output models)
    if isinstance(output, list) and output:
        first = output[0]

        # list[FileOutput]
        if isinstance(first, FileOutput):
            return first.read()

        # list[str] – URLs to the video
        if isinstance(first, str):
            import requests

            resp = requests.get(first)
            resp.raise_for_status()
            return resp.content

    # Case 3: raw bytes (just in case)
    if isinstance(output, (bytes, bytearray)):
        return output

    raise HTTPException(
        500,
        f"Unexpected Replicate output type: {type(output)}; "
        f"value (truncated): {repr(output)[:200]}",
    )


@app.post("/animate")
async def animate(
    part: str = Form(...),             # "eyes" | "brows" | "mouth" | etc.
    action: str = Form(...),           # "blink", "look_left", "talk_loop", ...
    x: int = Form(...),                # crop x (original image coordinates)
    y: int = Form(...),                # crop y
    width: int = Form(...),
    height: int = Form(...),
    file: UploadFile = File(...),      # full original image
):
    if not REPLICATE_MODEL:
        raise HTTPException(503, "Video generation not available. Set REPLICATE_MODEL and REPLICATE_API_TOKEN environment variables.")
    
    print(f"[/animate] Received request: part={part}, action={action}, x={x}, y={y}, width={width}, height={height}")
    
    try:
        raw = await file.read()
        img = Image.open(BytesIO(raw)).convert("RGBA")
        print(f"[/animate] Image loaded: {img.width}x{img.height}")
    except Exception as e:
        print(f"[/animate] Failed to read image: {e}")
        raise HTTPException(400, "Could not read image")

    # Clamp box to image bounds
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(img.width, x + width)
    y1 = min(img.height, y + height)
    if x1 <= x0 or y1 <= y0:
        raise HTTPException(400, "Invalid crop box")

    # Crop to selected region
    crop = img.crop((x0, y0, x1, y1))
    print(f"[/animate] Cropped region: {crop.width}x{crop.height}")

    # ---- NEW: wrap crop into a square canvas to keep aspect ratio valid ----
    cw, ch = crop.size
    side = max(cw, ch)

    # bright green background (for later chroma-key if you want)
    square = Image.new("RGBA", (side, side), (0, 255, 0, 255))

    # center the crop on the square canvas
    offset_x = (side - cw) // 2
    offset_y = (side - ch) // 2
    square.paste(crop, (offset_x, offset_y))

    print(f"[/animate] Wrapped crop in square: {square.width}x{square.height}")

    buf = BytesIO()
    square.save(buf, format="PNG")
    print(f"[/animate] Square PNG size: {len(buf.getvalue())} bytes")

    try:
        print(f"[/animate] Calling Replicate with part={part}, action={action}...")
        video_bytes = call_replicate_animate(part, action, buf)
        print(f"[/animate] Got video bytes: {len(video_bytes)} bytes")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[/animate] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Replicate error: {e}")

    # Assume mp4 from the video model
    return Response(content=video_bytes, media_type="video/mp4")


@app.post("/generate-emotions")
async def generate_emotions(request: EmotionRequest):
    """
    Use OpenAI to analyze transcript and suggest emotion keyframes.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(500, "OPENAI_API_KEY not set in environment")
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        # Format phoneme timeline for context
        timing_info = [
            {
                "time_ms": kf["time_ms"],
                "phoneme": kf.get("phoneme", ""),
                "expr": kf.get("target_expr", "")
            }
            for kf in request.phoneme_timeline
        ]
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """You are an animation director planning emotional expressions for a character speaking the provided transcript.

Your goal: Add expression keyframes that match the EMOTION and TONE of the text being spoken.

Available expressions:
- neutral: Default, calm
- happy_soft: Gentle smile, warm
- concerned: Worried, empathetic
- surprised_ah: Shocked, amazed

Guidelines:
- Match the emotion of the words being spoken
- Happy/positive text → happy_soft
- Worried/negative text → concerned  
- Surprising/shocking text → surprised_ah
- Neutral/matter-of-fact text → neutral
- Place keyframes at natural emotional shifts
- Don't overdo it - 2-5 keyframes for a 3-4 second clip is typical
- Keyframes should be at least 500ms apart

Respond with ONLY a JSON array of emotion keyframes:
[
  {"time_ms": 1200, "target_expr": "happy_soft", "reason": "positive greeting"},
  {"time_ms": 2500, "target_expr": "concerned", "reason": "worrying statement"}
]"""
                },
                {
                    "role": "user",
                    "content": f"""Transcript: "{request.transcript}"

Phoneme timing (for reference):
{json.dumps(timing_info, indent=2)}

Total duration: {request.total_duration_ms}ms

Please suggest emotion keyframes that match the emotional tone of this speech."""
                }
            ],
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        
        # Parse JSON from response
        import re
        json_match = re.search(r'\[[\s\S]*\]', content)
        if not json_match:
            raise ValueError("Could not parse emotion keyframes from OpenAI response")
        
        emotion_keyframes = json.loads(json_match.group(0))
        
        print(f"✨ Generated {len(emotion_keyframes)} emotion keyframes")
        return {"keyframes": emotion_keyframes}
        
    except Exception as e:
        print(f"Error generating emotions: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Failed to generate emotions: {str(e)}")


@app.post("/generate-alignment")
async def generate_alignment(
    audio: UploadFile = File(...),
    transcript: str = Form(...)
):
    """
    Generate phoneme alignment from audio + transcript using Montreal Forced Aligner.
    Returns the phoneme timeline JSON directly.
    """
    import tempfile
    import shutil
    
    # Create temp directory for MFA
    temp_dir = Path(tempfile.mkdtemp(prefix="mfa_align_"))
    
    try:
        # Save audio file
        audio_path = temp_dir / "audio.wav"
        with open(audio_path, "wb") as f:
            shutil.copyfileobj(audio.file, f)
        
        # Get audio duration to calculate appropriate timeout
        try:
            import wave
            with wave.open(str(audio_path), 'rb') as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                audio_duration_seconds = frames / float(rate)
        except:
            # Fallback if wave fails - estimate from file size
            audio_duration_seconds = 30  # Conservative default
        
        # Calculate timeout: ~90 seconds per minute of audio, minimum 120 seconds
        alignment_timeout = max(120, int(audio_duration_seconds * 90))
        
        print(f"[MFA] Audio duration: {audio_duration_seconds:.1f}s")
        print(f"[MFA] Alignment timeout: {alignment_timeout}s")
        
        # Save transcript as .lab file
        lab_path = temp_dir / "audio.lab"
        with open(lab_path, "w") as f:
            f.write(transcript.strip())
        
        print(f"[MFA] Running alignment on {audio_path.name}")
        print(f"[MFA] Transcript ({len(transcript)} chars): {transcript[:100]}...")
        print(f"[MFA] Temp directory: {temp_dir}")
        
        # Run MFA alignment
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        print(f"[MFA] Output directory: {output_dir}")
        
        # Get conda configuration from environment or detect from conda
        mfa_env = os.environ.get("MFA_ENV", "aligner")
        
        # Try to get conda base from environment, otherwise detect it
        conda_base = os.environ.get("CONDA_BASE")
        if not conda_base:
            try:
                conda_base = subprocess.check_output(
                    ["conda", "info", "--base"],
                    text=True,
                    timeout=5
                ).strip()
            except:
                # Fallback to common locations
                conda_base = os.path.expanduser("~/opt/miniconda3")
        
        print(f"[MFA] Using conda base: {conda_base}")
        print(f"[MFA] Using conda env: {mfa_env}")
        
        # Quick sanity check - verify MFA is available
        check_cmd = f"""
        source {conda_base}/etc/profile.d/conda.sh && \
        conda activate {mfa_env} && \
        which mfa && mfa version
        """
        
        check_result = subprocess.run(
            ["bash", "-c", check_cmd],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if check_result.returncode != 0:
            raise RuntimeError(f"MFA not available in conda env '{mfa_env}': {check_result.stderr}")
        
        print(f"[MFA] MFA check passed: {check_result.stdout.strip()}")
        
        # Activate conda environment and run MFA
        # Using bash to source conda and activate environment
        mfa_cmd = f"""
        source {conda_base}/etc/profile.d/conda.sh && \
        conda activate {mfa_env} && \
        mfa align {temp_dir} english_us_arpa english_us_arpa {output_dir} \
            --clean \
            --single_speaker \
            --beam 10 \
            --retry_beam 40 \
            --num_jobs 2
        """
        
        result = subprocess.run(
            ["bash", "-c", mfa_cmd],
            capture_output=True,
            text=True,
            timeout=alignment_timeout  # Scales with audio duration
        )
        
        print(f"[MFA] Command completed with exit code {result.returncode}")
        
        if result.stdout:
            print(f"[MFA] stdout:\n{result.stdout}")
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "No error output"
            print(f"[MFA] stderr:\n{error_msg}")
            
            # Check for common issues
            if "No such file or directory" in error_msg:
                raise RuntimeError(f"MFA alignment failed: Conda environment or MFA not found. Check that 'aligner' conda env is properly set up.")
            elif "dictionary" in error_msg.lower() or "acoustic" in error_msg.lower():
                raise RuntimeError(f"MFA alignment failed: Missing models. Run 'mfa model download acoustic english_us_arpa' and 'mfa model download dictionary english_us_arpa'")
            else:
                raise RuntimeError(f"MFA alignment failed (exit code {result.returncode}): {error_msg}")
        
        print(f"[MFA] Alignment complete")
        
        # Find the generated TextGrid
        textgrid_path = output_dir / "audio.TextGrid"
        if not textgrid_path.exists():
            raise RuntimeError(f"MFA did not generate TextGrid at {textgrid_path}")
        
        # Parse TextGrid and generate timeline using existing script
        timeline_script = Path(__file__).parent / "textgrid_to_timeline.py"
        timeline_result = subprocess.run(
            [sys.executable, str(timeline_script), str(textgrid_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if timeline_result.returncode != 0:
            print(f"[Timeline] Script failed with exit code {timeline_result.returncode}")
            print(f"[Timeline] stderr: {timeline_result.stderr}")
            print(f"[Timeline] stdout: {timeline_result.stdout}")
            raise RuntimeError(f"Timeline generation failed: {timeline_result.stderr or timeline_result.stdout}")
        
        print(f"[Timeline] Script output: {timeline_result.stdout}")
        
        # Read generated timeline JSON
        timeline_json_path = textgrid_path.with_suffix('.timeline.json')
        if not timeline_json_path.exists():
            raise RuntimeError(f"Timeline JSON not generated at {timeline_json_path}")
            
        with open(timeline_json_path) as f:
            timeline_data = json.load(f)
        
        print(f"✅ Generated {len(timeline_data['keyframes'])} phoneme keyframes")
        
        return timeline_data
        
    except subprocess.TimeoutExpired:
        raise HTTPException(500, f"Alignment timed out after {alignment_timeout}s. This may indicate MFA is not properly configured or the audio is exceptionally complex.")
    except Exception as e:
        print(f"Error in alignment: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Failed to generate alignment: {str(e)}")
    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/audio/upload")
async def upload_audio(file: UploadFile = File(...)):
    """
    Upload an audio file for use in video export.
    Returns the filename to use in subsequent requests.
    """
    import shutil
    
    try:
        # Generate unique filename
        timestamp = int(time.time() * 1000)
        ext = Path(file.filename).suffix
        filename = f"upload_{timestamp}{ext}"
        file_path = AUDIO_DIR / filename
        
        # Save file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        print(f"[Audio] Uploaded: {filename} ({file_path.stat().st_size} bytes)")
        
        return {"filename": filename, "path": str(file_path)}
    
    except Exception as e:
        print(f"[Audio] Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Failed to upload audio: {str(e)}")


@app.post("/export-video")
async def export_video(request: ExportRequest):
    """
    Export the timeline as a video file.
    Renders frame-by-frame with audio sync.
    """
    import subprocess
    import tempfile
    import shutil
    from pathlib import Path
    from PIL import Image
    import io
    
    temp_dir = None
    try:
        # Create temporary directory for frames
        temp_dir = tempfile.mkdtemp()
        frames_dir = Path(temp_dir) / "frames"
        frames_dir.mkdir()
        
        # Parse audio URL to get file path
        audio_path = None
        if request.audio_url:
            # Extract filename from URL (assumes format /audio/filename.wav)
            audio_filename = request.audio_url.split("/")[-1]
            audio_path = AUDIO_DIR / audio_filename
            if not audio_path.exists():
                raise HTTPException(404, f"Audio file not found: {audio_filename}")
        
        # Calculate total duration from timeline
        if not request.combined_timeline:
            raise HTTPException(400, "Empty timeline")
        
        last_keyframe = request.combined_timeline[-1]
        total_duration_ms = last_keyframe["time_ms"] + last_keyframe.get("transition_duration_ms", 500)
        
        # Frame timing
        fps = request.fps
        frame_duration_ms = 1000.0 / fps
        total_frames = int(total_duration_ms / frame_duration_ms) + 1
        
        print(f"[Export] Rendering {total_frames} frames at {fps} FPS ({total_duration_ms}ms total)")
        
        # Render each frame
        current_state = {"expr": "neutral", "pose": "center"}
        active_transition = None
        transition_segments = []
        segment_index = 0
        frame_index = 0
        
        for frame_num in range(total_frames):
            current_time_ms = frame_num * frame_duration_ms
            
            # Check if we need to start a new transition
            for kf in request.combined_timeline:
                if kf["time_ms"] <= current_time_ms < kf["time_ms"] + 10:  # Small window for triggering
                    # Start new transition
                    target_expr = kf.get("target_expr", current_state["expr"])
                    target_pose = kf.get("target_pose", current_state["pose"])
                    
                    if target_expr != current_state["expr"] or target_pose != current_state["pose"]:
                        # Plan route
                        from_state = f"{current_state['expr']}__{current_state['pose']}"
                        to_state = f"{target_expr}__{target_pose}"
                        
                        # Use transition graph logic (simplified for backend)
                        transition_path = f"{current_state['expr']}_to_{target_expr}__{current_state['pose']}"
                        timeline_dir = TIMELINES_DIR / transition_path
                        
                        if timeline_dir.exists():
                            json_file = timeline_dir / "timeline.json"
                            if json_file.exists():
                                with open(json_file, "r") as f:
                                    timeline_data = json.load(f)
                                    transition_segments = [{"pathId": transition_path, "timeline": timeline_data}]
                                    segment_index = 0
                                    frame_index = 0
                                    active_transition = {
                                        "start_ms": current_time_ms,
                                        "duration_ms": kf.get("transition_duration_ms", 500)
                                    }
                                    print(f"[Export] Frame {frame_num}: Starting transition {transition_path}")
                        
                        current_state["expr"] = target_expr
                        current_state["pose"] = target_pose
            
            # Render current frame
            frame_img = None
            
            if active_transition and transition_segments:
                # We're in a transition - use timeline frames
                elapsed_ms = current_time_ms - active_transition["start_ms"]
                
                if elapsed_ms < active_transition["duration_ms"]:
                    # Still animating
                    seg = transition_segments[segment_index]
                    timeline = seg["timeline"]
                    total_seg_frames = len(timeline)
                    
                    # Calculate which frame to show
                    progress = elapsed_ms / active_transition["duration_ms"]
                    target_frame = int(progress * sum(len(s["timeline"]) for s in transition_segments))
                    
                    # Advance through segments if needed
                    frames_so_far = sum(len(transition_segments[i]["timeline"]) for i in range(segment_index))
                    if target_frame >= frames_so_far + total_seg_frames and segment_index < len(transition_segments) - 1:
                        segment_index += 1
                        frame_index = 0
                        seg = transition_segments[segment_index]
                        timeline = seg["timeline"]
                        total_seg_frames = len(timeline)
                        frames_so_far = sum(len(transition_segments[i]["timeline"]) for i in range(segment_index))
                    
                    frame_index = max(0, min(target_frame - frames_so_far, total_seg_frames - 1))
                    
                    # Load frame
                    frame_data = timeline[frame_index]
                    frame_path = TIMELINES_DIR / seg["pathId"] / frame_data["frame"]
                    if frame_path.exists():
                        frame_img = Image.open(frame_path)
                else:
                    # Transition complete - show final frame
                    seg = transition_segments[-1]
                    timeline = seg["timeline"]
                    frame_path = TIMELINES_DIR / seg["pathId"] / timeline[-1]["frame"]
                    if frame_path.exists():
                        frame_img = Image.open(frame_path)
                    active_transition = None
            
            if not frame_img:
                # No active transition - show idle frame
                idle_path = f"{current_state['expr']}_to_{current_state['expr']}__{current_state['pose']}"
                idle_dir = TIMELINES_DIR / idle_path
                if idle_dir.exists():
                    json_file = idle_dir / "timeline.json"
                    if json_file.exists():
                        with open(json_file, "r") as f:
                            idle_timeline = json.load(f)
                            if idle_timeline:
                                frame_path = idle_dir / idle_timeline[-1]["frame"]
                                if frame_path.exists():
                                    frame_img = Image.open(frame_path)
            
            # Save frame (or black frame if nothing found)
            if frame_img:
                # Convert to RGBA for WebM transparency support
                if frame_img.mode != "RGBA":
                    frame_img = frame_img.convert("RGBA")
            else:
                # Create transparent frame as fallback
                frame_img = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
            
            # Save frame with zero-padded number
            frame_path = frames_dir / f"frame_{frame_num:06d}.png"
            frame_img.save(frame_path, "PNG")
        
        print(f"[Export] Rendered {total_frames} frames")
        
        # Use ffmpeg to create video
        output_file = Path(temp_dir) / f"output.{request.format}"
        
        if request.format == "webm":
            # WebM with VP9 codec and alpha channel
            cmd = [
                "ffmpeg",
                "-framerate", str(fps),
                "-i", str(frames_dir / "frame_%06d.png"),
                "-c:v", "libvpx-vp9",
                "-pix_fmt", "yuva420p",  # Alpha channel
                "-auto-alt-ref", "0",
                "-b:v", "2M"
            ]
        else:
            # MP4 with H.264 codec
            cmd = [
                "ffmpeg",
                "-framerate", str(fps),
                "-i", str(frames_dir / "frame_%06d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "medium",
                "-crf", "23"
            ]
        
        # Add audio if present
        if audio_path:
            cmd.extend(["-i", str(audio_path)])
            cmd.extend(["-c:a", "aac" if request.format == "mp4" else "libopus"])
            cmd.extend(["-shortest"])  # End video when shortest stream ends
        
        cmd.extend(["-y", str(output_file)])
        
        print(f"[Export] Running ffmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"[Export] FFmpeg error: {result.stderr}")
            raise HTTPException(500, f"FFmpeg failed: {result.stderr}")
        
        # Read output file and return as response
        with open(output_file, "rb") as f:
            video_data = f.read()
        
        # Clean up temp directory
        shutil.rmtree(temp_dir)
        
        # Return video file
        from fastapi.responses import Response
        content_type = "video/webm" if request.format == "webm" else "video/mp4"
        filename = f"export_{int(time.time())}.{request.format}"
        
        return Response(
            content=video_data,
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except subprocess.TimeoutExpired:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(500, "Video export timed out (>5min)")
    except Exception as e:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"[Export] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Failed to export video: {str(e)}")

