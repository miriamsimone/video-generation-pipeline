# 🎬 AI Video Generation Pipeline

A modular, automated pipeline that transforms text prompts into complete videos using AI.

## 📋 Features

- **Automated Script Generation** - Claude creates engaging narration from your prompt
- **Intelligent Scene Planning** - Breaks scripts into visual scenes with descriptions
- **Video Clip Generation** - Generates video clips using AI (RunwayML, Pika, Stability AI)
- **Voiceover Synthesis** - Creates natural-sounding narration (ElevenLabs, OpenAI TTS)
- **🎭 NEW: Face Rig Character Animation** - Animated character with lip-sync and emotions
- **Final Assembly** - Combines everything into a polished video
- **Simple Web UI** - Easy-to-use Streamlit interface

### 🎭 Face Rig Integration (NEW!)

The pipeline now supports animated character narration with:
- **Lip-Sync**: Precise phoneme-to-viseme mapping using Montreal Forced Aligner
- **Emotion AI**: Automatic emotional expressions matching content sentiment
- **Picture-in-Picture**: Character overlay in bottom-right corner
- **Per-Scene Audio**: Individual TTS generation for each scene with accurate timing

**Quick Start**: See [FACE_RIG_QUICKSTART.md](FACE_RIG_QUICKSTART.md) for setup instructions.

**Documentation**: See [FACE_RIG_INTEGRATION.md](FACE_RIG_INTEGRATION.md) for detailed usage.

## 🏗️ Architecture

```
video_pipeline/
├── config.py              # Configuration and settings
├── script_generator.py    # Step 1: Prompt → Script
├── scene_planner.py       # Step 2: Script → Scene Plan
├── video_generator.py     # Step 3: Scenes → Video Clips
├── audio_generator.py     # Step 4: Script → Voiceover
├── video_assembler.py     # Step 5: Clips + Audio → Final Video
├── pipeline.py            # Orchestrates all modules
├── app.py                 # Streamlit UI
└── requirements.txt       # Dependencies
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install ffmpeg (for video assembly)

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html)

### 3. Configure API Keys

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
```
ANTHROPIC_API_KEY=your_actual_key_here
VIDEO_API_KEY=your_video_api_key (optional)
TTS_API_KEY=your_tts_api_key (optional)
```

### 4. Run the Application

**Web UI (Recommended):**
```bash
streamlit run app.py
```

**Command Line:**
```python
from pipeline import VideoPipeline

pipeline = VideoPipeline(
    anthropic_api_key="your-key",
    video_provider="mock",  # or "runwayml", "pika", etc.
    tts_provider="mock"     # or "elevenlabs", "openai", etc.
)

result = pipeline.run("Explain how photosynthesis works")
print(f"Video created: {result['video_path']}")
```

## 📖 Usage Examples

### Example 1: Educational Video
```python
pipeline.run("Explain the water cycle with visual examples")
```

### Example 2: Product Demo
```python
pipeline.run("Show how to use a smartphone camera effectively")
```

### Example 3: Storytelling
```python
pipeline.run("Tell the story of how the internet was invented")
```

## 🔧 Configuration

### Providers

**Video Generation:**
- `mock` - Testing mode (no API required)
- `runwayml` - RunwayML Gen-3 API
- `pika` - Pika Labs API
- `stability` - Stability AI Video API

**Text-to-Speech:**
- `mock` - Testing mode (no API required)
- `elevenlabs` - ElevenLabs TTS
- `openai` - OpenAI TTS
- `google` - Google Cloud TTS

Edit `config.py` to customize:
- Scene duration (4-8 seconds default)
- Number of scenes (5 default)
- Video quality settings
- Audio settings

## 📁 Project Structure

### Module Responsibilities

**config.py**
- Central configuration
- API key management
- Directory setup

**script_generator.py**
- Takes user prompt
- Generates video script using Claude
- Returns title and narration

**scene_planner.py**
- Takes script
- Breaks into 4-6 scenes
- Creates visual descriptions for each scene

**video_generator.py**
- Takes scene descriptions
- Generates video clips via API
- Supports multiple providers

**audio_generator.py**
- Takes script
- Generates voiceover audio
- Supports multiple TTS providers

**video_assembler.py**
- Combines video clips
- Adds audio track
- Uses ffmpeg for assembly

**pipeline.py**
- Orchestrates all modules
- Handles error recovery
- Saves project metadata

**app.py**
- Streamlit web interface
- User-friendly controls
- Real-time progress updates

## 🔌 API Integration

### Adding a New Video Provider

Edit `video_generator.py`:

```python
def _generate_your_provider(self, description, duration, scene_number, output_dir):
    """Generate video using YourProvider API"""
    endpoint = "https://api.yourprovider.com/generate"
    
    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {self.api_key}"},
        json={
            "prompt": description,
            "duration": duration
        }
    )
    
    # Save video
    clip_path = output_dir / f"scene_{scene_number}.mp4"
    with open(clip_path, 'wb') as f:
        f.write(response.content)
    
    return str(clip_path)
```

### Adding a New TTS Provider

Edit `audio_generator.py`:

```python
def _generate_your_tts(self, text, output_dir):
    """Generate audio using YourTTS API"""
    endpoint = "https://api.yourtts.com/synthesize"
    
    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {self.api_key}"},
        json={"text": text}
    )
    
    # Save audio
    audio_path = output_dir / "voiceover.mp3"
    with open(audio_path, 'wb') as f:
        f.write(response.content)
    
    return str(audio_path)
```

## 🧪 Testing Without APIs

The pipeline works in "mock mode" without any paid APIs:

```python
pipeline = VideoPipeline(
    anthropic_api_key="your-anthropic-key",  # Only this is required
    video_provider="mock",
    tts_provider="mock"
)
```

This creates placeholder files so you can test the pipeline logic before integrating real APIs.

## 📊 Output Files

Each generation creates:
- `final_video.mp4` - The assembled video
- `project_TIMESTAMP.json` - Metadata and script
- `temp/` - Intermediate files (clips, audio)

## ⚙️ Advanced Configuration

### Custom Scene Count
```python
# In config.py
TARGET_SCENES = 8  # Create more scenes
```

### Custom Video Duration
```python
# In config.py
SCENE_DURATION_MIN = 3
SCENE_DURATION_MAX = 10
```

### Custom Output Directory
```python
# In config.py
OUTPUT_DIR = Path("/path/to/your/output")
```

## 🐛 Troubleshooting

**Issue: ffmpeg not found**
- Install ffmpeg using instructions above
- Verify with: `ffmpeg -version`

**Issue: API key errors**
- Check `.env` file has correct keys
- Verify keys are active and have credits

**Issue: Video generation slow**
- Normal - AI video generation takes 1-5 minutes per scene
- Use fewer scenes for faster results

**Issue: Import errors**
- Run: `pip install -r requirements.txt`
- Check Python version (3.8+ required)

## 📝 Development Roadmap

- [ ] Add subtitle generation
- [ ] Support background music
- [ ] Add video transitions
- [ ] Support multiple aspect ratios (vertical, square)
- [ ] Batch processing for multiple videos
- [ ] Custom branding/watermarks
- [ ] Advanced scene timing controls

## 🤝 Contributing

To add features:
1. Create a new module in `video_pipeline/`
2. Update `pipeline.py` to integrate it
3. Add UI controls in `app.py`
4. Update this README

## 📄 License

MIT License - feel free to use and modify

## 🙏 Acknowledgments

- Claude API for script and scene generation
- Anthropic for AI capabilities
- Streamlit for the web interface
- ffmpeg for video processing
