# OpenSeeFace Integration Guide

This guide covers the integration of OpenSeeFace for real-time face tracking in your watercolor character rig.

## Overview

The OSF integration consists of three components:

1. **OpenSeeFace** (vendored as git submodule): Handles face detection and landmark tracking
2. **`osf_server.py`**: Python FastAPI server that:
   - Spawns OpenSeeFace as a subprocess
   - Parses UDP tracking packets
   - Detects audio energy for mouth movement
   - Streams combined data over WebSocket
3. **`FaceTrackedPlayer.tsx`**: React component that:
   - Consumes tracking data from WebSocket
   - Maps face rotation to character poses
   - Maps mouth/audio to speaking expressions
   - Drives the character animation state machine

## Setup

### 1. Install OpenSeeFace

OpenSeeFace is already vendored as a git submodule. Initialize it:

```bash
cd face_rig
git submodule update --init --recursive
```

### 2. Install Python Dependencies

```bash
pip install -r osf_requirements.txt
```

**Note on PyAudio:**
- **macOS**: `brew install portaudio` then `pip install pyaudio`
- **Ubuntu**: `sudo apt-get install portaudio19-dev` then `pip install pyaudio`
- **Windows**: `pip install pipwin && pipwin install pyaudio`

### 3. Verify OpenSeeFace Models

Ensure the models are present:

```bash
ls osf/models/
# Should show: lm_modelGS.onnx, lm_model_i.onnx, lm_model_quant_i.onnx, etc.
```

If models are missing, download from the [OpenSeeFace releases](https://github.com/emilianavt/OpenSeeFace/releases).

## Running the Face-Tracked Character

### Step 1: Start the FastAPI Server

```bash
cd face_rig
uvicorn osf_server:app --host 0.0.0.0 --port 9000
```

The server will:
- Start OpenSeeFace facetracker on your default webcam
- Listen for UDP packets on port 11573
- Capture audio for energy-based mouth detection
- Stream combined data on `ws://localhost:9000/ws/tracking`

**Server Endpoints:**
- `GET /` - Status and endpoint list
- `GET /health` - Health check (OSF status, queue sizes)
- `WS /ws/tracking` - WebSocket for face + audio data

### Step 2: Start the React App

In a separate terminal:

```bash
cd face_rig/watercolor-rig
npm install  # if first time
npm run dev
```

Navigate to `http://localhost:5173` and click **"🎥 Face Tracking Mode"**.

### Step 3: Allow Camera & Microphone Access

- Grant camera permission when prompted (for OpenSeeFace)
- Grant microphone permission when prompted (for audio energy detection)

### Step 4: Track Your Face!

The character will now respond to:
- **Head tilt left/right** → `tilt_left_small` / `tilt_right_small`
- **Head nod up/down** → `nod_up_small` / `nod_down_small`
- **Mouth open / speaking** → `speaking_ah`, `speaking_ee`, etc.
- **Eye blink** → `blink_closed`

## How It Works

### Face Tracking → Character State Mapping

```typescript
// FaceTrackedPlayer.tsx
function mapTrackingToState(msg: TrackingMessage, currentState: State): State {
  const { face, audio } = msg;
  
  // Pose from head rotation (yaw, pitch, roll in radians)
  const { pitch, yaw, roll } = face.rotation.euler;
  
  if (Math.abs(roll) > 0.15) {
    // Tilt left/right based on roll
  } else if (Math.abs(pitch) > 0.15) {
    // Nod up/down based on pitch
  }
  
  // Expression from eye blink + mouth + audio
  const avgEyeOpen = (face.eye_blink.left + face.eye_blink.right) / 2;
  if (avgEyeOpen < 0.2) {
    return "blink_closed";
  }
  
  const mouthOpen = face.features.mouth_open;
  const audioEnergy = audio.energy;
  if (mouthOpen > 0.5 || audioEnergy > 0.03) {
    return "speaking_ah"; // or speaking_ee, etc.
  }
  
  return "neutral";
}
```

### OpenSeeFace UDP Packet Structure

The `parse_osf_packet()` function in `osf_server.py` parses the binary UDP packet:

```python
# Packet layout (from OpenSeeFace facetracker.py):
# - double: timestamp
# - int: face_id
# - float: width, height
# - float: eye_blink[0] (right), eye_blink[1] (left)
# - byte: success (1 or 0)
# - float: pnp_error
# - float[4]: quaternion (rotation)
# - float[3]: euler angles (pitch, yaw, roll)
# - float[3]: translation (x, y, z)
# - float[68]: landmark confidence values
# - float[68*2]: landmark 2D coords (y, x pairs)
# - float[68*3]: landmark 3D coords (x, -y, -z triples)
# - float[14]: features (eye_l, eye_r, eyebrow_*, mouth_*, etc.)
```

### Audio Energy Detection

The `AudioEnergyDetector` class uses PyAudio to:
1. Capture audio chunks (1024 samples @ 44.1kHz)
2. Calculate RMS energy
3. Smooth over 10 frames
4. Classify as `neutral`, `speaking_ee`, or `speaking_ah` based on thresholds

**Tuning:**
Edit `osf_server.py` to adjust:
```python
class AudioEnergyDetector:
    silence_threshold = 0.01  # Below this = neutral
    speaking_threshold = 0.03  # Above this = speaking_ah
```

### WebSocket Message Format

```json
{
  "face": {
    "timestamp": 1234.56,
    "face_id": 0,
    "success": true,
    "eye_blink": { "left": 0.85, "right": 0.90 },
    "rotation": {
      "quaternion": [x, y, z, w],
      "euler": { "pitch": 0.12, "yaw": -0.05, "roll": 0.02 }
    },
    "translation": { "x": 0.0, "y": 0.0, "z": -50.0 },
    "features": {
      "mouth_open": 0.3,
      "mouth_wide": 0.1,
      "eye_l": 0.9,
      "eye_r": 0.9,
      ...
    },
    "landmarks_2d": [[x, y], ...],  // 68 points
    "landmarks_3d": [[x, y, z], ...]  // 68 points
  },
  "audio": {
    "energy": 0.025,
    "phoneme": "speaking_ee"
  }
}
```

## Customization

### Adjusting Pose Thresholds

Edit `FaceTrackedPlayer.tsx`:

```typescript
const YAW_THRESHOLD = 0.15;  // radians (~8.6 degrees)
const PITCH_THRESHOLD = 0.15;

// Increase for less sensitive, decrease for more sensitive
```

### Adding More Expression Mappings

```typescript
// In mapTrackingToState():
const smile = face.features.mouth_corner_updown_l + face.features.mouth_corner_updown_r;
if (smile > 0.5) {
  targetExpr = "happy_soft";
}

const eyebrowRaise = face.features.eyebrow_updown_l + face.features.eyebrow_updown_r;
if (eyebrowRaise > 0.6) {
  targetExpr = "surprised_ah";
}
```

### Changing Camera / Model

Edit `osf_server.py`:

```python
def start_facetracker(
    camera_index: int = 0,  # Change camera (0, 1, 2, ...)
    model: int = 3,         # Model 3 is recommended (fastest + accurate)
    width: int = 640,
    height: int = 480,
    fps: int = 30,
    ...
):
```

**Available models:**
- `-1`: RetinaFace (slower, more accurate)
- `0`: UltraFace 320x240
- `1`: UltraFace 640x480
- `2`: UltraFace RFB 640x480 (good balance)
- `3`: UltraFace slim 320x240 (fastest, recommended)
- `4`: UltraFace slim 640x480

## Deployment Options

### 1. Local OBS Source (Browser Source)

Use the React app directly in OBS:
1. Add **Browser Source** in OBS
2. Set URL: `http://localhost:5173/?mode=face-tracked`
3. Set Width: 1920, Height: 1080
4. Check "Shutdown source when not visible" to save resources

### 2. Standalone Electron/Tauri App

Package the React app with Electron or Tauri for a native desktop app:
```bash
npm install -g electron
# ... wrap FaceTrackedPlayer in Electron window
```

### 3. Browser-Based WebRTC (No Server)

For fully browser-based tracking (no Python server):
1. Use [Mediapipe Face Mesh](https://github.com/google/mediapipe) in the browser
2. Replace OSF WebSocket with Mediapipe's JS API
3. Run face tracking directly in the React component

Example:
```typescript
import { FaceMesh } from "@mediapipe/face_mesh";

const faceMesh = new FaceMesh({
  locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`
});

faceMesh.onResults((results) => {
  const landmarks = results.multiFaceLandmarks[0];
  // Map landmarks to character state
  const state = mapLandmarksToState(landmarks);
  playRouteTo(state);
});
```

### 4. Network Streaming (VMC / OSC Protocol)

For streaming tracking data over the network (e.g., to remote OBS or VTuber software):

**Server side (`osf_server.py`):**
```python
import socket

# VMC protocol (VirtualMotionCapture)
def send_vmc(tracking_data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Pack as OSC message
    sock.sendto(osc_message, ("192.168.1.100", 39539))
```

**Clients:**
- VSeeFace
- Warudo
- VTube Studio
- VRChat (via OSC)

## Troubleshooting

### "Failed to start facetracker"

- Check that `osf/facetracker.py` exists
- Ensure models are downloaded in `osf/models/`
- Try running manually: `python osf/facetracker.py --help`

### "No face detected"

- Ensure camera is working (test with Photo Booth / Camera app)
- Check lighting (face should be well-lit)
- Try different camera: `camera_index=1` in `start_facetracker()`
- Reduce `--threshold` (default 0.3): add `"--threshold", "0.2"` to cmd

### "PyAudio error"

- If PyAudio fails to install, comment out audio code in `osf_server.py`
- Or run without audio: remove `_audio_task` and audio-related code

### "WebSocket disconnected"

- Check that OSF server is running on port 9000
- Check browser console for CORS errors
- Ensure FastAPI CORS middleware allows your frontend origin

### High CPU Usage

- Reduce FPS: `fps: int = 15` in `start_facetracker()`
- Use faster model: `model: int = 3`
- Reduce resolution: `width: int = 320, height: int = 240`

### Tracking Jitter

- Increase thresholds in `FaceTrackedPlayer.tsx`
- Add smoothing to rotation values:
  ```typescript
  const smoothedYaw = lerp(prevYaw, yaw, 0.3);  // 30% interpolation
  ```

## Next Steps

- [ ] Add phoneme detection (replace energy-based audio with real phoneme classifier)
- [ ] Implement expression smoothing (blend between expressions)
- [ ] Add "auto-pilot" mode (random poses + blinks when idle)
- [ ] Create OBS plugin for direct integration
- [ ] Support multiple face tracking (switch active speaker)

## Credits

- [OpenSeeFace](https://github.com/emilianavt/OpenSeeFace) by Emiliana
- FastAPI for the WebSocket server
- React + Vite for the frontend

