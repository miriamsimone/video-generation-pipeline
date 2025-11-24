#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import time
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse, RedirectResponse
from PIL import Image
import openai

# --- CONFIG ---

# S3 Configuration
USE_S3 = os.environ.get("USE_S3", "false").lower() == "true"
S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")
S3_PREFIX = os.environ.get("S3_PREFIX", "frames/")  # Prefix within bucket for frames
S3_BASE_URL = os.environ.get("S3_BASE_URL", "")  # Optional: custom CDN URL

# Initialize S3 client if enabled
s3_client = None
if USE_S3:
    try:
        import boto3
        s3_client = boto3.client('s3', region_name=S3_REGION)
        print(f"✅ S3 enabled: bucket={S3_BUCKET}, region={S3_REGION}")
        if S3_BASE_URL:
            print(f"   Using custom CDN URL: {S3_BASE_URL}")
    except ImportError:
        print("⚠️  boto3 not installed, S3 support disabled. Install with: pip install boto3")
        USE_S3 = False
    except Exception as e:
        print(f"⚠️  Failed to initialize S3 client: {e}")
        USE_S3 = False

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

class TTSRequest(BaseModel):
    transcript: str
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Default ElevenLabs voice (Rachel)

app = FastAPI()

# CORS configuration from environment variable
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
# Parse comma-separated origins, or use ["*"] for allow-all
cors_origins = [origin.strip() for origin in CORS_ORIGINS.split(",")] if CORS_ORIGINS != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- HEALTH CHECK ---

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring and load balancers"""
    return {
        "status": "ok",
        "s3_enabled": USE_S3,
        "s3_bucket": S3_BUCKET if USE_S3 else None
    }


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
    
    # If S3 is enabled, try to fetch manifest from S3 first
    if USE_S3 and s3_client:
        try:
            s3_key = f"{S3_PREFIX}sequences/{path_id}/manifest.json"
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
            data = json.load(response['Body'])
            
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
            print(f"[!] Failed to load manifest from S3: {e}")
            raise HTTPException(404, f"Timeline not found in S3: {path_id}")
    
    # Fall back to local filesystem
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
    """Serve a frame PNG (from S3 or local filesystem)"""
    if USE_S3:
        # Construct S3 URL and redirect
        s3_key = f"{S3_PREFIX}{path_id}/{filename}"
        
        if S3_BASE_URL:
            # Use custom CDN URL
            s3_url = f"{S3_BASE_URL.rstrip('/')}/{s3_key}"
        else:
            # Use standard S3 URL
            s3_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
        
        # Redirect to S3 URL (client fetches directly from S3)
        return RedirectResponse(url=s3_url, status_code=302)
    else:
        # Serve from local filesystem
        # Check sequences directory first, then fall back to frames root
        file_path = SEQUENCES_DIR / path_id / filename
        if not file_path.exists() or not file_path.is_file():
            file_path = FRAMES_DIR / path_id / filename
        
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(404, "Frame not found")
        
        return FileResponse(file_path, media_type="image/png")


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
            model="gpt-4o",  # 128K context window vs 8K for gpt-4
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
            [sys.executable, str(timeline_script), str(textgrid_path), "--mode", "phonemes", "--cooldown", "350"],
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


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serve an audio file"""
    file_path = AUDIO_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "Audio file not found")
    
    return FileResponse(file_path, media_type="audio/wav")


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


@app.post("/generate-tts")
async def generate_tts(request: TTSRequest):
    """
    Generate audio from text using ElevenLabs TTS.
    Returns the audio file information.
    """
    import requests
    
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise HTTPException(500, "ELEVENLABS_API_KEY not set in environment")
    
    try:
        # Call ElevenLabs API
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{request.voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        
        data = {
            "text": request.transcript,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        print(f"[TTS] Generating audio for {len(request.transcript)} chars with voice {request.voice_id}")
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code != 200:
            error_text = response.text
            print(f"[TTS] ElevenLabs error: {error_text}")
            raise HTTPException(500, f"ElevenLabs API error: {response.status_code} - {error_text}")
        
        # Save audio file
        timestamp = int(time.time() * 1000)
        filename = f"tts_{timestamp}.mp3"
        file_path = AUDIO_DIR / filename
        
        with open(file_path, "wb") as f:
            f.write(response.content)
        
        # Convert MP3 to WAV for MFA compatibility
        wav_filename = f"tts_{timestamp}.wav"
        wav_path = AUDIO_DIR / wav_filename
        
        # Use ffmpeg to convert
        convert_cmd = [
            "ffmpeg",
            "-i", str(file_path),
            "-ar", "16000",  # 16kHz sample rate for MFA
            "-ac", "1",      # Mono
            "-y", str(wav_path)
        ]
        
        convert_result = subprocess.run(convert_cmd, capture_output=True, text=True, timeout=30)
        
        if convert_result.returncode != 0:
            print(f"[TTS] FFmpeg conversion error: {convert_result.stderr}")
            raise HTTPException(500, f"Audio conversion failed: {convert_result.stderr}")
        
        print(f"[TTS] Generated and converted: {wav_filename} ({wav_path.stat().st_size} bytes)")
        
        # Get audio duration
        try:
            import wave
            with wave.open(str(wav_path), 'rb') as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                duration = frames / float(rate)
        except:
            duration = 0
        
        return {
            "filename": wav_filename,
            "path": str(wav_path),
            "duration": duration,
            "original_mp3": filename
        }
        
    except requests.exceptions.RequestException as e:
        print(f"[TTS] Request error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Failed to call ElevenLabs API: {str(e)}")
    except Exception as e:
        print(f"[TTS] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Failed to generate TTS: {str(e)}")


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
        last_triggered_kf_idx = -1
        
        for frame_num in range(total_frames):
            current_time_ms = frame_num * frame_duration_ms
            
            # Check if we need to start a new transition
            for kf_idx, kf in enumerate(request.combined_timeline):
                if kf_idx <= last_triggered_kf_idx:
                    continue  # Already triggered this keyframe
                    
                if kf["time_ms"] <= current_time_ms < kf["time_ms"] + frame_duration_ms * 2:  # Wider window for triggering
                    # Start new transition
                    target_expr = kf.get("target_expr", current_state["expr"])
                    target_pose = kf.get("target_pose", current_state["pose"])
                    
                    if target_expr != current_state["expr"] or target_pose != current_state["pose"]:
                        # Plan route with proper fallback through neutral
                        from_expr = current_state['expr']
                        from_pose = current_state['pose']
                        
                        segments = []
                        
                        # Try direct path first
                        if from_expr != target_expr:
                            direct_path = f"{from_expr}_to_{target_expr}__{from_pose}"
                            direct_dir = TIMELINES_DIR / direct_path
                            
                            if direct_dir.exists() and (direct_dir / "manifest.json").exists():
                                # Direct transition exists
                                with open(direct_dir / "manifest.json", "r") as f:
                                    manifest_data = json.load(f)
                                    timeline_data = manifest_data.get("frames", [])
                                    segments.append({"pathId": direct_path, "timeline": timeline_data})
                                    print(f"[Export] Frame {frame_num} ({current_time_ms:.0f}ms): Direct transition {direct_path}")
                            else:
                                # No direct path, route through neutral
                                # Step 1: current_expr -> neutral (may need to reverse neutral_to_current_expr)
                                step1_path = f"{from_expr}_to_neutral__{from_pose}"
                                step1_dir = TIMELINES_DIR / step1_path
                                
                                if step1_dir.exists() and (step1_dir / "manifest.json").exists():
                                    with open(step1_dir / "manifest.json", "r") as f:
                                        manifest_data = json.load(f)
                                        timeline_data = manifest_data.get("frames", [])
                                        segments.append({"pathId": step1_path, "timeline": timeline_data, "reverse": False})
                                else:
                                    # Try reversed transition: neutral_to_from_expr played backwards
                                    reverse_path = f"neutral_to_{from_expr}__{from_pose}"
                                    reverse_dir = TIMELINES_DIR / reverse_path
                                    if reverse_dir.exists() and (reverse_dir / "manifest.json").exists():
                                        with open(reverse_dir / "manifest.json", "r") as f:
                                            manifest_data = json.load(f)
                                            timeline_data = manifest_data.get("frames", [])
                                            # Reverse the timeline for playback
                                            timeline_data_reversed = list(reversed(timeline_data))
                                            segments.append({"pathId": reverse_path, "timeline": timeline_data_reversed, "reverse": True})
                                
                                # Step 2: neutral -> target_expr
                                step2_path = f"neutral_to_{target_expr}__{from_pose}"
                                step2_dir = TIMELINES_DIR / step2_path
                                if step2_dir.exists() and (step2_dir / "manifest.json").exists():
                                    with open(step2_dir / "manifest.json", "r") as f:
                                        manifest_data = json.load(f)
                                        timeline_data = manifest_data.get("frames", [])
                                        segments.append({"pathId": step2_path, "timeline": timeline_data, "reverse": False})
                                
                                if len(segments) == 2:
                                    reverse_note = " (reversed)" if segments[0].get("reverse") else ""
                                    print(f"[Export] Frame {frame_num} ({current_time_ms:.0f}ms): Routing {from_expr} → neutral{reverse_note} → {target_expr}")
                        
                        # TODO: Handle pose changes too (for now, assume pose stays same)
                        
                        if segments:
                            transition_segments = segments
                            segment_index = 0
                            frame_index = 0
                            active_transition = {
                                "start_ms": current_time_ms,
                                "duration_ms": kf.get("transition_duration_ms", 500)
                            }
                        
                        current_state["expr"] = target_expr
                        current_state["pose"] = target_pose
                        last_triggered_kf_idx = kf_idx
            
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
                    frame_path = TIMELINES_DIR / seg["pathId"] / frame_data["file"]
                    if frame_path.exists():
                        frame_img = Image.open(frame_path)
                else:
                    # Transition complete - show final frame
                    seg = transition_segments[-1]
                    timeline = seg["timeline"]
                    frame_path = TIMELINES_DIR / seg["pathId"] / timeline[-1]["file"]
                    if frame_path.exists():
                        frame_img = Image.open(frame_path)
                    active_transition = None
            
            if not frame_img:
                # No active transition - show idle frame
                idle_path = f"{current_state['expr']}_to_{current_state['expr']}__{current_state['pose']}"
                idle_dir = TIMELINES_DIR / idle_path
                
                if idle_dir.exists():
                    json_file = idle_dir / "manifest.json"
                    if json_file.exists():
                        with open(json_file, "r") as f:
                            manifest_data = json.load(f)
                            idle_timeline = manifest_data.get("frames", [])
                            if idle_timeline:
                                frame_path = idle_dir / idle_timeline[-1]["file"]
                                if frame_path.exists():
                                    frame_img = Image.open(frame_path)
                                    if frame_num == 0:
                                        print(f"[Export] Using idle frame: {frame_path}")
                                else:
                                    print(f"[Export] Idle frame not found: {frame_path}")
                
                # If still no frame, try endpoints directory as fallback
                if not frame_img:
                    endpoints_dir = FRAMES_DIR / "endpoints"
                    endpoint_file = endpoints_dir / f"{current_state['expr']}__{current_state['pose']}.png"
                    if endpoint_file.exists():
                        frame_img = Image.open(endpoint_file)
                        if frame_num == 0:
                            print(f"[Export] Using endpoint: {endpoint_file.name}")
                    else:
                        if frame_num == 0:
                            print(f"[Export] Endpoint not found: {endpoint_file}")
            
            # Save frame (or black frame if nothing found)
            if frame_img:
                # Convert to RGBA for WebM transparency support
                if frame_img.mode != "RGBA":
                    frame_img = frame_img.convert("RGBA")
                
                if frame_num == 0:
                    width, height = frame_img.size
                    print(f"[Export] Video dimensions: {width}x{height}")
            else:
                # Create transparent frame as fallback (use same dimensions as source images)
                if frame_num == 0:
                    print(f"[Export] WARNING: No frame found for {current_state['expr']}__{current_state['pose']}, using transparent fallback")
                frame_img = Image.new("RGBA", (1024, 1536), (0, 0, 0, 0))
            
            # Save frame with zero-padded number
            frame_path = frames_dir / f"frame_{frame_num:06d}.png"
            frame_img.save(frame_path, "PNG")
        
        print(f"[Export] Rendered {total_frames} frames")
        
        # Use ffmpeg to create video
        output_file = Path(temp_dir) / f"output.{request.format}"
        
        # Build ffmpeg command: inputs first, then output options
        cmd = [
            "ffmpeg",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%06d.png"),
        ]
        
        # Add audio input if present
        if audio_path:
            cmd.extend(["-i", str(audio_path)])
        
        # Add output encoding options
        if request.format == "webm":
            # WebM with VP9 codec and alpha channel
            cmd.extend([
                "-c:v", "libvpx-vp9",
                "-pix_fmt", "yuva420p",  # Alpha channel
                "-auto-alt-ref", "0",
                "-b:v", "2M"
            ])
        else:
            # MP4 with H.264 codec
            cmd.extend([
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "medium",
                "-crf", "23"
            ])
        
        # Add audio encoding if present
        if audio_path:
            cmd.extend(["-c:a", "aac" if request.format == "mp4" else "libopus"])
            cmd.extend(["-shortest"])  # End video when shortest stream ends
        
        # Add output file
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

