#!/usr/bin/env python3
"""
OpenSeeFace integration server with audio energy detection.
Streams face tracking + audio via WebSocket for browser/OBS consumption.
"""
import asyncio
import json
import socket
import struct
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
import numpy as np

# ---- Configuration ----
FACETRACKER_PORT = 11573
FACETRACKER_HOST = "127.0.0.1"
ROOT_DIR = Path(__file__).resolve().parent
OSF_DIR = ROOT_DIR / "osf"
FACETRACKER_PY = OSF_DIR / "facetracker.py"

# Audio (we'll use simple energy detection via pyaudio)
AUDIO_RATE = 44100
AUDIO_CHUNK = 1024
AUDIO_CHANNELS = 1

# Feature indices from OpenSeeFace
FEATURES = [
    "eye_l", "eye_r",
    "eyebrow_steepness_l", "eyebrow_updown_l", "eyebrow_quirk_l",
    "eyebrow_steepness_r", "eyebrow_updown_r", "eyebrow_quirk_r",
    "mouth_corner_updown_l", "mouth_corner_inout_l",
    "mouth_corner_updown_r", "mouth_corner_inout_r",
    "mouth_open", "mouth_wide"
]

# ---- OSF facetracker subprocess ----
def start_facetracker(
    camera_index: int = 1,  # Mac's built-in camera (0 is iPhone via Continuity)
    model: int = 3,  # model 3 has best detection
    width: int = 320,  # Lower resolution works better with Mac webcam
    height: int = 240,
    fps: int = 24,
    port: int = FACETRACKER_PORT,
) -> subprocess.Popen:
    """
    Start OpenSeeFace facetracker.py as a subprocess sending tracking data over UDP.
    Model 3 with low threshold for good detection, single-threaded for stability.
    """
    cmd = [
        sys.executable,
        str(FACETRACKER_PY),
        "--model", str(model),
        "-c", str(camera_index),
        "-p", str(port),
        "-m", "1",  # Single thread to avoid race conditions
        "-F", str(fps),
        "-W", str(width),
        "-H", str(height),
        "-t", "0.0",  # Zero threshold - very permissive tracking
        "--detection-threshold", "0.3",  # Lower detection threshold
        "--try-hard", "1",  # Work harder to find faces
        "--faces", "1",
        "--scan-every", "1",  # Scan every frame for better detection
        "--scan-retinaface", "0",  # No RetinaFace background thread
        "-v", "0",
        "-s", "0",  # Not silent so we see detection messages
    ]
    print("[OSF] Starting facetracker:", " ".join(cmd))
    try:
        # Let both stdout and stderr go to console for debugging
        proc = subprocess.Popen(
            cmd,
            cwd=str(OSF_DIR),
            stdout=None,  # Let output print to console
            stderr=None,  # Let errors print to console
        )
        print(f"[OSF] Facetracker process started with PID {proc.pid}")
        return proc
    except Exception as e:
        print(f"[OSF] ERROR starting facetracker: {e}")
        raise


# ---- UDP packet parsing ----
def parse_osf_packet(data: bytes) -> Optional[Dict[str, Any]]:
    """
    Parse OpenSeeFace UDP packet.
    
    Structure (per facetracker.py):
    - double: timestamp
    - int: face_id
    - float: width
    - float: height
    - float: eye_blink[0] (right)
    - float: eye_blink[1] (left)
    - byte: success
    - float: pnp_error
    - float[4]: quaternion
    - float[3]: euler (pitch, yaw, roll)
    - float[3]: translation
    - float[68]: landmark confidence values
    - float[68*2]: landmark 2D coords (y, x pairs)
    - float[68*3]: landmark 3D coords (x, -y, -z triples)
    - float[14]: features
    """
    try:
        offset = 0
        
        # Header
        timestamp = struct.unpack_from("d", data, offset)[0]
        offset += 8
        face_id = struct.unpack_from("i", data, offset)[0]
        offset += 4
        width = struct.unpack_from("f", data, offset)[0]
        offset += 4
        height = struct.unpack_from("f", data, offset)[0]
        offset += 4
        eye_blink_r = struct.unpack_from("f", data, offset)[0]
        offset += 4
        eye_blink_l = struct.unpack_from("f", data, offset)[0]
        offset += 4
        success = struct.unpack_from("B", data, offset)[0]
        offset += 1
        pnp_error = struct.unpack_from("f", data, offset)[0]
        offset += 4
        
        # Rotation (quaternion + euler)
        quaternion = struct.unpack_from("ffff", data, offset)
        offset += 16
        euler = struct.unpack_from("fff", data, offset)  # pitch, yaw, roll
        offset += 12
        translation = struct.unpack_from("fff", data, offset)
        offset += 12
        
        # 68 landmark confidences
        lm_confs = struct.unpack_from("f" * 68, data, offset)
        offset += 68 * 4
        
        # 68 landmark 2D positions (y, x pairs)
        lm_2d_flat = struct.unpack_from("f" * (68 * 2), data, offset)
        lm_2d = [(lm_2d_flat[i*2+1], lm_2d_flat[i*2]) for i in range(68)]  # (x, y)
        offset += 68 * 2 * 4
        
        # 68 landmark 3D positions (x, -y, -z triples)
        lm_3d_flat = struct.unpack_from("f" * (68 * 3), data, offset)
        lm_3d = [
            (lm_3d_flat[i*3], lm_3d_flat[i*3+1], lm_3d_flat[i*3+2])
            for i in range(68)
        ]
        offset += 68 * 3 * 4
        
        # 14 features
        feature_vals = struct.unpack_from("f" * 14, data, offset)
        features_dict = {name: val for name, val in zip(FEATURES, feature_vals)}
        
        return {
            "timestamp": timestamp,
            "face_id": face_id,
            "success": bool(success),
            "pnp_error": pnp_error,
            "eye_blink": {
                "left": eye_blink_l,
                "right": eye_blink_r,
            },
            "rotation": {
                "quaternion": quaternion,
                "euler": {
                    "pitch": euler[0],
                    "yaw": euler[1],
                    "roll": euler[2],
                },
            },
            "translation": {
                "x": translation[0],
                "y": translation[1],
                "z": translation[2],
            },
            "features": features_dict,
            "landmarks_2d": lm_2d,
            "landmarks_3d": lm_3d,
        }
    except struct.error as e:
        print(f"[OSF] Packet parse error: {e}")
        return None


# ---- Audio energy detection ----
PYAUDIO_AVAILABLE = False
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    print("[Audio] PyAudio not installed. Audio features will be disabled.")
    print("[Audio] To enable: brew install portaudio && pip install pyaudio")

class AudioEnergyDetector:
    """Simple RMS energy-based audio detector for mouth open estimation."""
    
    def __init__(self, rate=AUDIO_RATE, chunk=AUDIO_CHUNK, channels=AUDIO_CHANNELS):
        self.rate = rate
        self.chunk = chunk
        self.channels = channels
        self.stream = None
        self.pyaudio = None
        self.enabled = PYAUDIO_AVAILABLE
        
        # Smoothing
        self.energy_history = []
        self.history_len = 10
        
        # Thresholds (tunable)
        self.silence_threshold = 0.01
        self.speaking_threshold = 0.03
        
    def start(self):
        """Start audio capture."""
        if not PYAUDIO_AVAILABLE:
            print("[Audio] PyAudio not available, skipping audio capture")
            return
        
        try:
            import pyaudio
            self.pyaudio = pyaudio.PyAudio()
            self.stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
            )
            print(f"[Audio] Started capture @ {self.rate}Hz")
        except Exception as e:
            print(f"[Audio] Failed to start: {e}")
            print("[Audio] Install pyaudio: brew install portaudio && pip install pyaudio")
            self.stream = None
            self.enabled = False
    
    def stop(self):
        """Stop audio capture."""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.pyaudio:
            self.pyaudio.terminate()
    
    def get_energy(self) -> float:
        """Read audio chunk and return RMS energy [0, 1]."""
        if not self.enabled or not self.stream:
            return 0.0
        
        try:
            data = self.stream.read(self.chunk, exception_on_overflow=False)
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            rms = np.sqrt(np.mean(samples ** 2))
            
            # Smooth
            self.energy_history.append(rms)
            if len(self.energy_history) > self.history_len:
                self.energy_history.pop(0)
            
            return float(np.mean(self.energy_history))
        except Exception as e:
            print(f"[Audio] Read error: {e}")
            return 0.0
    
    def classify_phoneme(self, energy: float) -> str:
        """
        Simple phoneme hint from energy.
        In a real system you'd use a phoneme classifier.
        """
        if energy < self.silence_threshold:
            return "neutral"
        elif energy < self.speaking_threshold:
            return "speaking_ee"  # subtle
        else:
            return "speaking_ah"  # open


# ---- Main server ----
async def udp_listener(
    queue: "asyncio.Queue[Dict[str, Any]]",
    port: int = FACETRACKER_PORT
):
    """Listen for OpenSeeFace UDP packets and push to queue."""
    global _last_face_data_time
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((FACETRACKER_HOST, port))
    sock.settimeout(0.1)  # 100ms timeout
    
    loop = asyncio.get_running_loop()
    print(f"[OSF] Listening for UDP on {FACETRACKER_HOST}:{port}")
    
    while True:
        try:
            # Use run_in_executor for compatibility
            data, addr = await loop.run_in_executor(None, sock.recvfrom, 65535)
            parsed = parse_osf_packet(data)
            if parsed is not None:
                await queue.put(parsed)
                _last_face_data_time = loop.time()  # Update watchdog timestamp
                print(f"[OSF] Received face data (face_id: {parsed.get('face_id', '?')})")
        except socket.timeout:
            # No data available, just continue
            await asyncio.sleep(0.01)
        except Exception as e:
            print(f"[OSF] UDP error: {type(e).__name__}: {e}")
            await asyncio.sleep(0.1)


async def audio_loop(audio_queue: "asyncio.Queue[Dict[str, Any]]"):
    """Continuously read audio and push energy data to queue."""
    detector = AudioEnergyDetector()
    detector.start()
    
    try:
        while True:
            energy = detector.get_energy()
            phoneme = detector.classify_phoneme(energy)
            await audio_queue.put({
                "energy": energy,
                "phoneme": phoneme,
            })
            await asyncio.sleep(0.02)  # 50 Hz
    finally:
        detector.stop()


# ---- FastAPI app ----
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="OpenSeeFace + Audio Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

face_tracking_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
audio_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()

_facetracker_proc: Optional[subprocess.Popen] = None
_udp_task: Optional[asyncio.Task] = None
_audio_task: Optional[asyncio.Task] = None
_watchdog_task: Optional[asyncio.Task] = None
_last_face_data_time: float = 0.0


async def facetracker_watchdog():
    """Monitor face data and restart facetracker if it stops sending for >10 seconds."""
    global _facetracker_proc, _last_face_data_time
    
    await asyncio.sleep(15)  # Initial grace period (allow time for face detection)
    
    while True:
        await asyncio.sleep(5)  # Check every 5 seconds
        
        if _facetracker_proc and _facetracker_proc.poll() is None:
            # Process is running
            idle_time = asyncio.get_event_loop().time() - _last_face_data_time
            
            if idle_time > 10:  # No data for 10 seconds (only restart if truly stuck)
                print(f"[Watchdog] No face data for {idle_time:.1f}s. Restarting facetracker...")
                
                try:
                    _facetracker_proc.terminate()
                    _facetracker_proc.wait(timeout=2)
                except:
                    _facetracker_proc.kill()
                
                # Restart
                _facetracker_proc = start_facetracker()
                _last_face_data_time = asyncio.get_event_loop().time()
                print("[Watchdog] Facetracker restarted.")


@app.on_event("startup")
async def startup_event():
    """Start OpenSeeFace subprocess and UDP listener."""
    global _facetracker_proc, _udp_task, _audio_task, _watchdog_task, _last_face_data_time
    
    _last_face_data_time = asyncio.get_event_loop().time()
    _facetracker_proc = start_facetracker()
    _udp_task = asyncio.create_task(udp_listener(face_tracking_queue))
    _audio_task = asyncio.create_task(audio_loop(audio_queue))
    _watchdog_task = asyncio.create_task(facetracker_watchdog())
    
    print("[Server] Started. Connect to ws://localhost:9000/ws/tracking")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup."""
    global _facetracker_proc, _udp_task, _audio_task, _watchdog_task
    
    if _facetracker_proc and _facetracker_proc.poll() is None:
        _facetracker_proc.terminate()
        _facetracker_proc.wait()
    
    if _udp_task:
        _udp_task.cancel()
    
    if _audio_task:
        _audio_task.cancel()
    
    if _watchdog_task:
        _watchdog_task.cancel()


@app.get("/")
async def root():
    return {
        "status": "ok",
        "endpoints": {
            "websocket": "/ws/tracking",
            "health": "/health",
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    global _facetracker_proc
    
    osf_running = _facetracker_proc and _facetracker_proc.poll() is None
    
    return {
        "osf_running": osf_running,
        "face_queue_size": face_tracking_queue.qsize(),
        "audio_queue_size": audio_queue.qsize(),
    }


@app.websocket("/ws/tracking")
async def ws_tracking(websocket: WebSocket):
    """
    Stream combined face + audio data.
    
    Message format:
    {
        "face": { ... osf data ... },
        "audio": { "energy": float, "phoneme": str }
    }
    """
    try:
        await websocket.accept()
        print("[WS] Client connected")
    except Exception as e:
        print(f"[WS] Failed to accept connection: {e}")
        return
    
    latest_face = None
    latest_audio = {"energy": 0.0, "phoneme": "neutral"}
    
    try:
        # Merge face + audio at ~30fps
        while True:
            # Drain queues (keep latest)
            while not face_tracking_queue.empty():
                latest_face = await face_tracking_queue.get()
            
            while not audio_queue.empty():
                latest_audio = await audio_queue.get()
            
            # Send combined message (send even if no face data yet, with null face)
            message = {
                "face": latest_face,
                "audio": latest_audio,
            }
            try:
                await websocket.send_json(message)
            except Exception as send_err:
                print(f"[WS] Send error: {send_err}")
                break
            
            await asyncio.sleep(1.0 / 30)  # 30 fps
    except Exception as e:
        print(f"[WS] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[WS] Client disconnected")
        try:
            await websocket.close()
        except:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)

