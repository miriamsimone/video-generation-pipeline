# Face Rig Integration Guide

This guide explains how to use the integrated face_rig character animation system with Geo_Tour video generation.

## Overview

The face_rig integration adds animated character narration to your videos with:
- **Text-to-Speech**: ElevenLabs voice generation for scene narration
- **Phoneme Alignment**: Montreal Forced Aligner (MFA) for precise lip-sync
- **Emotion Generation**: AI-powered emotional expressions matching the content
- **Picture-in-Picture**: Character appears in bottom-right corner of final video

## Prerequisites

### 1. Face Rig Server Setup

The face_rig server must be running before you start video generation.

```bash
# Navigate to face_rig directory
cd ../face_rig

# Start the face_rig server (requires conda environment with MFA)
python server.py
```

The server will run on `http://localhost:8000` by default.

### 2. Required Environment Variables

Make sure you have these API keys set in your `.env` file:

```bash
# OpenAI API (for script and emotion generation)
OPENAI_API_KEY=sk-...

# ElevenLabs API (for text-to-speech)
ELEVENLABS_API_KEY=...

# Replicate API (for video generation)
REPLICATE_API_KEY=r8_...
```

### 3. Montreal Forced Aligner (MFA)

The face_rig server requires MFA to be installed in a conda environment:

```bash
# Create and activate conda environment
conda create -n aligner -c conda-forge montreal-forced-aligner
conda activate aligner

# Download required models
mfa model download acoustic english_us_arpa
mfa model download dictionary english_us_arpa
```

## Usage

### Using the Streamlit UI

1. Start the face_rig server (see Prerequisites)
2. Launch the Geo_Tour UI:
   ```bash
   streamlit run app.py
   ```
3. In the sidebar, configure:
   - **Face Rig Character Animation**: Enable/disable face_rig
   - **Face Rig Server URL**: Default is `http://localhost:8000`
   - **Character Voice**: Select voice for the character
4. Click "Initialize Pipeline"
5. Enter your video prompt and click "Generate Video"

### Using the Python API

```python
from pipeline import VideoPipeline

# Initialize pipeline with face_rig enabled
pipeline = VideoPipeline(
    openai_api_key="your-openai-key",
    video_api_key="your-replicate-key",
    tts_api_key="your-elevenlabs-key",
    use_face_rig=True,  # Enable face_rig integration
    face_rig_url="http://localhost:8000",
    face_rig_voice_id="21m00Tcm4TlvDq8ikWAM"  # Sam voice
)

# Generate video
result = pipeline.run(
    "Explain how photosynthesis works in plants",
    num_scenes=5,
    scene_duration=6
)

print(f"Video generated: {result['video_path']}")
```

## How It Works

### Pipeline Flow

1. **Script Generation**: AI generates script from your prompt
2. **Scene Planning**: Script is broken into visual scenes
3. **Storyboard Generation**: Visual storyboards created (optional)
4. **Face Rig Character Animation** (NEW):
   - For each scene:
     - Generate audio from scene narration (ElevenLabs TTS)
     - Generate phoneme alignment (MFA)
     - Generate emotion timeline (OpenAI)
     - Export face_rig video with lip-sync
     - Scene duration is adjusted to match actual audio length
5. **Video Clip Generation**: Main video clips for background
6. **Voiceover**: Uses audio from face_rig
7. **Final Assembly**: 
   - Concatenates main video clips
   - Overlays face_rig videos as picture-in-picture (bottom-right)
   - Adds synchronized audio

### Face Rig Video Features

- **Lip-Sync**: Precise phoneme-to-viseme mapping for realistic mouth movements
- **Emotions**: AI analyzes narration text to add appropriate emotional expressions:
  - `neutral`: Default, calm expression
  - `happy_soft`: Gentle smile for positive content
  - `concerned`: Worried expression for concerning topics
  - `surprised_ah`: Shocked expression for surprising information
- **Picture-in-Picture**: Character appears scaled to 25% of video width in bottom-right corner

## Retry Mechanism (NEW!)

The pipeline now includes automatic retry logic with exponential backoff for all external API calls. This handles transient failures like:
- Network timeouts
- Server disconnects
- Rate limiting (429 errors)
- Temporary service unavailability (503, 502, 500)

**Default behavior:**
- **3 retry attempts** with exponential backoff (5s, 10s, 20s)
- Automatic detection of retryable vs non-retryable errors
- Clear logging of retry attempts

**Example output:**
```
Scene 4: Detailed view...
  🎨 Generating image via Google Imagen 3...
  ⚠️  Attempt 1/3 failed: Server disconnected without sending a response
  ⏳ Retrying in 5 seconds...
  ✅ Video saved: scene_4.mp4
```

**See [RETRY_MECHANISM.md](RETRY_MECHANISM.md) for detailed documentation.**

## Configuration Options

### Face Rig Settings

```python
pipeline = VideoPipeline(
    # ... other settings ...
    use_face_rig=True,              # Enable/disable face_rig
    face_rig_url="http://localhost:8000",  # Face_rig server URL
    face_rig_voice_id="21m00Tcm4TlvDq8ikWAM"  # ElevenLabs voice ID
)
```

### Available Voice IDs

Common ElevenLabs voice IDs:
- `21m00Tcm4TlvDq8ikWAM`: Sam (default, conversational male)
- `EXAVITQu4vr4xnSDxMaL`: Bella (conversational female)
- `AZnzlk1XvdvUeBnXmlld`: Domi (strong female)

### Disabling Face Rig

To generate videos without face_rig character:

```python
pipeline = VideoPipeline(
    # ... other settings ...
    use_face_rig=False
)
```

Or in the Streamlit UI, uncheck "Enable Face Rig Character" in the sidebar.

## Troubleshooting

### Face Rig Server Not Available

**Error**: `Face_rig server not available, disabling face_rig integration`

**Solution**:
1. Make sure the face_rig server is running: `cd ../face_rig && python server.py`
2. Check the server URL is correct (default: `http://localhost:8000`)
3. Test server health: `curl http://localhost:8000/health`

### MFA Alignment Failed

**Error**: `MFA alignment failed: Missing models`

**Solution**:
```bash
conda activate aligner
mfa model download acoustic english_us_arpa
mfa model download dictionary english_us_arpa
```

### ElevenLabs API Error

**Error**: `ElevenLabs API error: 401`

**Solution**:
1. Check your `ELEVENLABS_API_KEY` in `.env`
2. Verify the key is valid and has sufficient quota
3. Check your internet connection

### Video Export Timeout

**Error**: `Video export timed out`

**Solution**:
- This can happen with very long videos
- Try reducing the number of scenes
- Check server logs for more details

## Performance Considerations

### Generation Time

Face_rig integration adds processing time:
- **TTS Generation**: ~2-5 seconds per scene
- **MFA Alignment**: ~10-30 seconds per scene
- **Emotion Generation**: ~3-5 seconds per scene
- **Video Export**: ~20-60 seconds per scene

Total face_rig time per scene: ~35-100 seconds

### Optimization Tips

1. **Shorter Scenes**: Keep narration concise (2-4 sentences per scene)
2. **Fewer Scenes**: Start with 3-5 scenes for faster generation
3. **Local Server**: Run face_rig server on the same machine for lower latency
4. **Cache Audio**: The system caches generated audio for reuse

## File Structure

```
Geo_Tour-main/
├── face_rig_integrator.py  # Main integration module
├── pipeline.py              # Updated with face_rig support
├── video_assembler.py       # Updated with PiP overlay
├── app.py                   # UI with face_rig controls
└── temp/
    ├── face_rig_audio/      # Generated audio files
    └── face_rig_videos/     # Generated character videos

face_rig/
├── server.py                # Face_rig FastAPI server
├── audio/                   # Server audio directory
└── frames/sequences/        # Character animation frames
```

## Advanced Usage

### Custom Emotion Timeline

You can customize how emotions are generated by modifying the face_rig server's emotion generation prompt in `server.py`.

### Custom Character Poses

The face_rig system supports different character poses:
- `center`: Default forward-facing pose
- `left`: Character looking left
- `right`: Character looking right

To use different poses, you would need to modify the `FaceRigIntegrator` to specify pose in the timeline.

### Audio Duration Control

The integration automatically adjusts scene durations to match the actual audio length from face_rig. This ensures:
- No audio cutoff
- Proper synchronization
- Natural pacing

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review face_rig server logs
3. Test face_rig independently: `python face_rig_integrator.py`
4. Check Geo_Tour logs for detailed error messages

## Future Enhancements

Potential improvements:
- Multiple character support
- Character position customization
- Background transparency options
- Real-time preview
- Emotion intensity control
- Custom viseme mappings

