# OpenSeeFace Quick Start

Get your face-tracked watercolor character running in 5 minutes.

## Prerequisites

- Python 3.8+
- Node.js 16+
- Webcam
- Microphone (optional, for audio-based mouth detection)

## Quick Setup

### 1. Install Dependencies

```bash
cd face_rig

# Initialize OpenSeeFace submodule
git submodule update --init --recursive

# Install Python deps
pip install -r osf_requirements.txt

# Install audio support (optional)
# macOS:
brew install portaudio && pip install pyaudio

# Ubuntu:
# sudo apt-get install portaudio19-dev && pip install pyaudio
```

### 2. Start the OSF Server

```bash
# From face_rig/
uvicorn osf_server:app --port 9000
```

You should see:
```
[OSF] Starting facetracker: python osf/facetracker.py ...
[OSF] Listening for UDP on 127.0.0.1:11573
[Audio] Started capture @ 44100Hz
[Server] Started. Connect to ws://localhost:9000/ws/tracking
```

### 3. Start the React App

In a new terminal:

```bash
cd face_rig/watercolor-rig
npm install  # first time only
npm run dev
```

### 4. Open in Browser

1. Navigate to `http://localhost:5173`
2. Click **"🎥 Face Tracking Mode"**
3. Allow camera and microphone access
4. See yourself as a watercolor character!

## What You Should See

- **Status indicator**: Green "● Connected" at the top
- **Character preview**: 320x480 watercolor character
- **Debug info**: Real-time tracking values (yaw, pitch, roll, eye open, mouth, audio)
- **Smooth animations**: Character transitions between states as you move

## Testing the Tracking

Try these actions:

| Action | Expected Result |
|--------|----------------|
| Tilt head left | Character tilts left |
| Tilt head right | Character tilts right |
| Nod up | Character looks up |
| Nod down | Character looks down |
| Open mouth wide | Character shows speaking expression |
| Speak / make noise | Mouth opens (via audio energy) |
| Blink | Character blinks |
| Return to center | Character returns to neutral |

## Troubleshooting

### Red "● Disconnected"

**Problem**: OSF server isn't running or WebSocket can't connect.

**Fix**:
```bash
# Check server is running:
curl http://localhost:9000/health

# If not, start it:
uvicorn osf_server:app --port 9000
```

### "Waiting for tracking data..."

**Problem**: Camera not accessible or OpenSeeFace failed to start.

**Fix**:
1. Check camera permissions
2. Try running OSF manually:
   ```bash
   cd osf
   python facetracker.py --camera 0 --model 3 --visualize 1
   ```
3. If you see a window with face tracking, it's working!
4. Check server logs for errors

### Character not moving

**Problem**: Tracking is running but thresholds are too high.

**Fix**: Edit `FaceTrackedPlayer.tsx`:
```typescript
const YAW_THRESHOLD = 0.10;  // Reduce from 0.15
const PITCH_THRESHOLD = 0.10;
```

### Jittery movement

**Problem**: Tracking is too sensitive.

**Fix**: Increase thresholds or add smoothing (see `OSF_INTEGRATION.md`).

### Audio not working

**Problem**: PyAudio not installed or microphone access denied.

**Fix**:
1. Check mic permissions
2. Install PyAudio (see Prerequisites)
3. Or disable audio: comment out audio code in `osf_server.py`

## Next Steps

- Read `OSF_INTEGRATION.md` for full documentation
- Customize expression mappings in `FaceTrackedPlayer.tsx`
- Adjust thresholds for your use case
- Deploy to OBS as a Browser Source
- Add more expressions to your character rig

## Using in OBS

1. Add **Browser Source** to your scene
2. Set URL: `http://localhost:5173/?mode=face-tracked`
3. Set Width: 640, Height: 960 (or match your character size)
4. Check "Control audio via OBS"
5. Check "Shutdown source when not visible"

Done! Your face-tracked character is now live in OBS.

## Performance Tips

For better performance:

```python
# In osf_server.py, reduce FPS and resolution:
def start_facetracker(
    camera_index: int = 0,
    model: int = 3,
    width: int = 320,      # Lower resolution
    height: int = 240,
    fps: int = 15,         # Lower FPS
    ...
)
```

## Architecture Diagram

```
┌─────────────┐         UDP          ┌──────────────┐
│ OpenSeeFace │ ──────────────────→  │  OSF Server  │
│ (subprocess)│      (port 11573)    │  (FastAPI)   │
└─────────────┘                      │              │
                                     │  + Audio     │
      ┌──────────────────────────────┤  Detector    │
      │                              └──────┬───────┘
      │ Camera frames                       │
      ↓                                     │ WebSocket
┌─────────────┐                            │ (port 9000)
│   Webcam    │                            ↓
└─────────────┘                   ┌────────────────┐
                                  │ React Browser  │
      ┌───────────────────────────┤ (Face Tracked) │
      │                           │    Player      │
      │ Mic audio                 └────────────────┘
      ↓                                    │
┌─────────────┐                            │ Displays
│ Microphone  │                            ↓
└─────────────┘                   ┌────────────────┐
                                  │   Character    │
                                  │   Animation    │
                                  └────────────────┘
```

## Files Created

```
face_rig/
├── osf/                          # OpenSeeFace submodule
├── osf_server.py                 # FastAPI WebSocket server
├── osf_requirements.txt          # Python dependencies
├── OSF_INTEGRATION.md            # Full documentation
├── QUICKSTART_OSF.md             # This file
└── watercolor-rig/
    └── src/
        ├── FaceTrackedPlayer.tsx # Face-tracked character component
        ├── transitionGraph.ts    # State machine routing
        └── App.tsx               # Updated with face tracking mode
```

## Support

For issues:
1. Check `OSF_INTEGRATION.md` troubleshooting section
2. Run with `--reload` and check server logs
3. Check browser console for frontend errors
4. Verify tracking works manually: `python osf/facetracker.py --visualize 1`

Happy tracking! 🎭

