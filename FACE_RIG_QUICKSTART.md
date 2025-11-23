# Face Rig + Geo Tour Integration - Quick Start Guide

This guide will get you up and running with the integrated face_rig and Geo_Tour system in under 10 minutes.

## Prerequisites

- Python 3.8+
- Conda (for MFA)
- API Keys:
  - OpenAI API key
  - ElevenLabs API key
  - Replicate API key
- FFmpeg installed

## Step 1: Set Up Environment Variables

Create a `.env` file in the project root with your API keys:

```bash
# In video-generation-pipeline directory
cat > .env << EOF
OPENAI_API_KEY=sk-your-openai-key-here
ELEVENLABS_API_KEY=your-elevenlabs-key-here
REPLICATE_API_KEY=r8_your-replicate-key-here
EOF
```

## Step 2: Install Dependencies

### For Geo_Tour:
```bash
cd Geo_Tour-main
pip install -r requirements.txt
```

### For face_rig (MFA setup):
```bash
cd ../face_rig

# Create conda environment for MFA
conda create -n aligner -c conda-forge montreal-forced-aligner python=3.10
conda activate aligner

# Install Python dependencies
pip install -r requirements.txt

# Download MFA models (this may take a few minutes)
mfa model download acoustic english_us_arpa
mfa model download dictionary english_us_arpa

# Test MFA installation
mfa version
```

## Step 3: Start Face Rig Server

In a **separate terminal**:

```bash
cd face_rig

# Activate the aligner conda environment
conda activate aligner

# Set environment variables (if not using .env)
export OPENAI_API_KEY=sk-...
export ELEVENLABS_API_KEY=...

# Start the server
python server.py
```

You should see:
```
INFO:     Started server process [...]
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
✅ S3 enabled: bucket=..., region=...
```

**Keep this terminal running!**

## Step 4: Test the Integration

In your **main terminal**:

```bash
cd Geo_Tour-main

# Run the test suite
python test_face_rig_integration.py
```

Follow the prompts. If all tests pass, you're ready to go! ✅

## Step 5: Generate Your First Video

### Option A: Using the Streamlit UI (Recommended)

```bash
cd Geo_Tour-main
streamlit run app.py
```

Then:
1. Click "🚀 Initialize Pipeline" in the sidebar
2. Make sure "Enable Face Rig Character" is checked
3. Enter a prompt like: "Explain how rainbows form"
4. Click "🎬 Generate Video"

### Option B: Using Python Code

```python
from pipeline import VideoPipeline

# Initialize with face_rig enabled
pipeline = VideoPipeline(
    use_face_rig=True,
    face_rig_url="http://localhost:8000"
)

# Generate video
result = pipeline.run(
    "Explain how photosynthesis works in plants",
    num_scenes=3,
    scene_duration=6
)

print(f"✅ Video created: {result['video_path']}")
```

## What to Expect

### Timeline

For a 3-scene video (approx. 18 seconds):
- Script Generation: ~10 seconds
- Scene Planning: ~15 seconds
- Storyboard Generation: ~30 seconds
- **Face Rig Animation: ~2-3 minutes** (TTS + MFA + emotions + export for each scene)
- Video Clip Generation: ~2-3 minutes
- Final Assembly: ~30 seconds

**Total: 6-8 minutes**

### Output

Your final video will include:
- Main video clips showing visual scenes
- Animated character in bottom-right corner with:
  - Lip-synced mouth movements
  - Emotional expressions matching the content
- Synchronized audio narration

## Troubleshooting

### "Face_rig server not available"

**Solution**: Make sure face_rig server is running in a separate terminal
```bash
cd face_rig
conda activate aligner
python server.py
```

### "MFA alignment failed"

**Solution**: Re-download MFA models
```bash
conda activate aligner
mfa model download acoustic english_us_arpa
mfa model download dictionary english_us_arpa
```

### "ElevenLabs API error: 401"

**Solution**: Check your ElevenLabs API key in `.env`
- Make sure it's valid
- Check you have sufficient quota
- Verify no extra spaces in the key

### "FFmpeg not found"

**Solution**: Install FFmpeg
- **Mac**: `brew install ffmpeg`
- **Ubuntu**: `sudo apt install ffmpeg`
- **Windows**: Download from https://ffmpeg.org/download.html

### Video generation is slow

**Tips**:
- Start with fewer scenes (3 scenes = ~6-8 minutes)
- Use shorter narration text per scene
- Consider disabling storyboard generation for faster results
- Make sure face_rig server is running on the same machine

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Geo_Tour Pipeline                       │
│                                                               │
│  1. Script Gen → 2. Scene Planning → 3. Storyboard          │
│                                                               │
│  4. Face Rig Integration ←──────────────┐                   │
│     ├─ TTS (ElevenLabs)                  │                   │
│     ├─ MFA Phoneme Alignment             │                   │
│     ├─ Emotion Generation (OpenAI)       │                   │
│     └─ Video Export                      │                   │
│                                           │                   │
│  5. Video Clips → 6. Voiceover → 7. Assembly               │
│                                           │                   │
│  Final Output:                            │                   │
│  ┌──────────────────────────┐           │                   │
│  │  Main Video (Background) │           │                   │
│  │                           │           │                   │
│  │              ┌─────────┐  │←──────────┘                   │
│  │              │ Character│ │  Picture-in-Picture           │
│  │              │  (PiP)   │ │  (Bottom Right)               │
│  │              └─────────┘  │                               │
│  └──────────────────────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

## Example Prompts

Try these prompts to test the system:

1. **Educational**:
   - "Explain how rainbows form when light passes through water droplets"
   - "Describe the water cycle from ocean to clouds to rain"
   - "Explain photosynthesis in simple terms"

2. **Narrative**:
   - "Tell the story of how the moon was formed"
   - "Explain the journey of a salmon swimming upstream"

3. **Procedural**:
   - "Demonstrate how to bake chocolate chip cookies"
   - "Show how to plant a seed and grow a flower"

## Next Steps

1. **Customize the character voice**: Edit the voice ID in the UI or code
2. **Adjust character size**: Modify the PiP scale in `video_assembler.py` (line ~1165)
3. **Add more emotions**: Extend the emotion set in `face_rig/server.py`
4. **Experiment with different scenes**: Try 3-7 scenes for optimal results

## Production Tips

### For Best Quality:
- Use detailed visual descriptions in your prompts
- Keep scenes 4-8 seconds long
- Use clear, concise narration (2-4 sentences per scene)
- Enable storyboard generation for better visual consistency

### For Faster Generation:
- Reduce number of scenes (3-4 is ideal)
- Disable storyboard generation
- Use shorter narration text
- Consider pre-generating storyboard images

### For Lower Costs:
- Reduce number of scenes
- Use shorter prompts
- Disable face_rig for quick tests (set `use_face_rig=False`)
- Cache and reuse storyboards when possible

## Resources

- **Face Rig Integration Docs**: `Geo_Tour-main/FACE_RIG_INTEGRATION.md`
- **Geo Tour Docs**: `Geo_Tour-main/README.md`
- **Face Rig Docs**: `face_rig/README.md`
- **Test Suite**: `Geo_Tour-main/test_face_rig_integration.py`

## Getting Help

If you encounter issues:

1. Check the face_rig server logs
2. Run the test suite: `python test_face_rig_integration.py`
3. Review the troubleshooting section above
4. Check that all API keys are valid
5. Verify MFA is properly installed: `conda activate aligner && mfa version`

## Success! 🎉

If you've made it this far and generated a video, congratulations! You now have a working system that can:

✅ Generate AI-written scripts  
✅ Create visual storyboards  
✅ Generate animated video clips  
✅ Add lip-synced character narration  
✅ Combine everything into a professional video  

Enjoy creating videos! 🎬

