# ✅ OpenSeeFace Setup Complete!

Your face tracking system is ready to use!

## Current Status

✅ **OpenSeeFace**: Installed as git submodule with all models  
✅ **Python Environment**: Virtual environment `venv_osf` with Python 3.13.9  
✅ **Dependencies**: FastAPI, Uvicorn, OpenCV, ONNX Runtime installed  
✅ **Server**: Running on `http://localhost:9000`  
⚠️ **Audio**: Disabled (PyAudio not installed - optional)  
✅ **Frontend**: React app on `http://localhost:5173`

## Quick Start

### Option 1: Use the Startup Script (Recommended)

```bash
cd face_rig
./start_osf_server.sh
```

### Option 2: Manual Start

```bash
cd face_rig
source venv_osf/bin/activate
uvicorn osf_server:app --port 9000
```

## Test It Now!

1. **The OSF server is already running** on port 9000
2. **The React dev server is running** on port 5173
3. **Open your browser**: http://localhost:5173
4. **Click**: "🎥 Face Tracking Mode"
5. **Allow camera access** when prompted
6. **Move your head** and watch the character respond!

## What Works Right Now

| Your Action | Character Response |
|-------------|-------------------|
| 👈 Tilt head left | Character tilts left |
| 👉 Tilt head right | Character tilts right |
| 👆 Nod up | Character looks up |
| 👇 Nod down | Character looks down |
| 😊 Face in center | Neutral center pose |

**Note**: Audio-based mouth detection is disabled since PyAudio isn't installed. The character will still respond to head movements!

## Enabling Audio (Optional)

If you want audio-based mouth movements:

```bash
# Install PortAudio
brew install portaudio

# Activate virtual environment
cd face_rig
source venv_osf/bin/activate

# Install PyAudio
pip install pyaudio

# Restart the server
pkill -f "uvicorn osf_server"
./start_osf_server.sh
```

After enabling audio:
- 🗣️ **Speak** → Speaking expressions
- 😮 **Open mouth** → Mouth animations

## Server Endpoints

- **Status**: http://localhost:9000
- **Health Check**: http://localhost:9000/health
- **WebSocket**: ws://localhost:9000/ws/tracking

## Troubleshooting

### "No face detected"

The health endpoint shows `osf_running: false`? This is normal - the facetracker subprocess starts when a WebSocket client connects. Try:

1. Open the browser at http://localhost:5173
2. Click "🎥 Face Tracking Mode"
3. Allow camera access
4. Check health again: `curl http://localhost:9000/health`

### "Connection Failed" in Browser

Make sure:
1. OSF server is running: `curl http://localhost:9000/health`
2. React dev server is running: `curl http://localhost:5173`
3. Hard refresh browser: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)

### Camera Not Working

1. Check camera permissions: System Settings → Privacy & Security → Camera
2. Close other apps using the camera (Zoom, FaceTime, etc.)
3. Try a different camera: Edit `osf_server.py`, change `camera_index: int = 0` to `1` or `2`

### Server Won't Start

If you see errors:
```bash
# Kill any existing server
pkill -f "uvicorn osf_server"

# Remove and recreate virtual environment
cd face_rig
rm -rf venv_osf
python3.13 -m venv venv_osf
source venv_osf/bin/activate
pip install fastapi 'uvicorn[standard]' websockets numpy opencv-python onnxruntime Pillow

# Start server
./start_osf_server.sh
```

## File Structure

```
face_rig/
├── osf/                      # OpenSeeFace (git submodule)
│   ├── facetracker.py       # Face tracking script
│   └── models/              # ONNX models (10 files)
├── venv_osf/                # Python virtual environment
├── osf_server.py            # FastAPI WebSocket server
├── start_osf_server.sh      # Startup script ⭐
├── osf_requirements.txt     # Python dependencies
├── OSF_SETUP_COMPLETE.md    # This file
└── watercolor-rig/
    └── src/
        ├── FaceTrackedPlayer.tsx   # Face-tracked character
        └── transitionGraph.ts      # State machine

```

## Next Steps

### 1. Customize Sensitivity

Edit `FaceTrackedPlayer.tsx`:

```typescript
// Line ~48: Adjust pose thresholds
const YAW_THRESHOLD = 0.15;   // Lower = more sensitive (try 0.10)
const PITCH_THRESHOLD = 0.15;
```

### 2. Add More Expressions

Map facial features to expressions:

```typescript
// In mapTrackingToState():
const smile = face.features.mouth_corner_updown_l + 
              face.features.mouth_corner_updown_r;
if (smile > 0.5) {
  targetExpr = "happy_soft";
}
```

### 3. Use in OBS

1. Add **Browser Source** in OBS
2. URL: `http://localhost:5173/?mode=face-tracked`
3. Width: 640, Height: 960
4. Check "Shutdown source when not visible"

### 4. Enable Audio

Follow the "Enabling Audio (Optional)" section above.

## Performance Tuning

If the tracking is slow, edit `osf_server.py`:

```python
def start_facetracker(
    camera_index: int = 0,
    model: int = 3,         # Model 3 is fastest
    width: int = 320,       # Lower resolution = faster
    height: int = 240,
    fps: int = 15,          # Lower FPS = less CPU
    ...
):
```

## Support

- **Full Documentation**: `OSF_INTEGRATION.md`
- **Quick Start**: `QUICKSTART_OSF.md`
- **TypeScript Notes**: `watercolor-rig/VITE_TS_NOTES.md`

## Summary

You now have a fully functional face-tracked watercolor character! 🎉

**What's Running:**
- ✅ OSF Server (port 9000)
- ✅ React Dev Server (port 5173)
- ✅ Face tracking (via OpenSeeFace)
- ⚠️ Audio detection (disabled, optional)

**To Use:**
1. Go to http://localhost:5173
2. Click "🎥 Face Tracking Mode"
3. Allow camera access
4. Move your head!

Enjoy your animated watercolor character! 🎨✨

