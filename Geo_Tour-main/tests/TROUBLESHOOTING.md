# 🔧 Troubleshooting Guide

## Common Issues & Solutions

### Installation Issues

#### Problem: `pip install` fails
```
ERROR: Could not find a version that satisfies the requirement...
```

**Solutions:**
1. Upgrade pip:
   ```bash
   pip install --upgrade pip
   ```

2. Check Python version (need 3.8+):
   ```bash
   python --version
   ```

3. Use virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

---

#### Problem: `ModuleNotFoundError: No module named 'anthropic'`

**Solution:**
```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install anthropic streamlit requests
```

---

### API Key Issues

#### Problem: `ValueError: Anthropic API key is required`

**Solutions:**

**Option 1: Environment Variable**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Option 2: .env File**
```bash
cp .env.example .env
# Edit .env and add your key
```

**Option 3: Pass Directly**
```python
pipeline = VideoPipeline(anthropic_api_key="sk-ant-...")
```

**Verify it's set:**
```bash
echo $ANTHROPIC_API_KEY
```

---

#### Problem: `401 Unauthorized` from API

**Causes:**
- Invalid API key
- API key expired
- No credits remaining

**Solutions:**
1. Check key at https://console.anthropic.com/
2. Generate new API key
3. Verify billing/credits

---

### Video Generation Issues

#### Problem: Video generation is very slow

**This is NORMAL!** AI video generation takes time:
- Mock mode: Instant
- Real APIs: 1-5 minutes per scene
- Full video (5 scenes): 5-25 minutes

**Tips to speed up:**
- Reduce number of scenes (edit `config.py`)
- Use shorter scene durations
- Use mock mode for testing
- Process scenes in parallel (future feature)

---

#### Problem: `Video API error: 403 Forbidden`

**Solutions:**
1. Check API key is valid
2. Verify sufficient credits
3. Check API rate limits
4. Try again in a few minutes

---

#### Problem: Generated videos are poor quality

**Solutions:**
1. Improve visual descriptions in prompts
2. Be more specific about what you want
3. Try different video providers
4. Adjust scene duration (longer = better quality)

**Example:**
```
Bad:  "A tree"
Good: "A tall oak tree with green leaves swaying in gentle breeze, 
       sunlight filtering through branches, 4K cinematic"
```

---

### Audio/TTS Issues

#### Problem: `TTS API error: 401 Unauthorized`

**Solutions:**
1. Verify TTS API key
2. Check credits/subscription
3. Fall back to mock mode:
   ```python
   pipeline = VideoPipeline(tts_provider="mock")
   ```

---

#### Problem: Voiceover doesn't match video timing

**Current Limitation:** The basic pipeline doesn't sync audio to video cuts.

**Workarounds:**
1. Adjust scene durations manually
2. Use the "narration-sync" feature (if implemented)
3. Post-process with video editor

---

### ffmpeg Issues

#### Problem: `ffmpeg: command not found`

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
1. Download from https://ffmpeg.org/download.html
2. Extract to C:\ffmpeg
3. Add to PATH environment variable

**Verify:**
```bash
ffmpeg -version
```

---

#### Problem: `ffmpeg` fails with codec errors

**Solution:**
Update ffmpeg to latest version:
```bash
# macOS
brew upgrade ffmpeg

# Ubuntu
sudo apt update
sudo apt upgrade ffmpeg
```

---

#### Problem: Can't combine video clips

**Workaround:**
The pipeline saves individual clips in `temp/`:
```bash
ls temp/scene_*.mp4
```

Combine manually:
```bash
ffmpeg -i temp/scene_1.mp4 -i temp/scene_2.mp4 \
  -filter_complex "[0:v][1:v]concat=n=2:v=1[v]" \
  -map "[v]" combined.mp4
```

---

### Streamlit UI Issues

#### Problem: `streamlit: command not found`

**Solution:**
```bash
pip install streamlit
```

Or:
```bash
python -m streamlit run app.py
```

---

#### Problem: UI shows "Pipeline Not Initialized"

**Solution:**
1. Add API keys in sidebar
2. Select providers (use "mock" for testing)
3. Click "🚀 Initialize Pipeline"

---

#### Problem: Streamlit app won't start

**Check port availability:**
```bash
# Try different port
streamlit run app.py --server.port 8502
```

**Check firewall:**
- Allow port 8501
- Try http://localhost:8501 instead of 0.0.0.0

---

### CLI Issues

#### Problem: `python cli.py` shows help instead of running

**You need to provide a prompt:**
```bash
python cli.py "Your prompt here"
```

Not:
```bash
python cli.py  # ← This shows help
```

---

#### Problem: CLI exits immediately

**Check for errors:**
```bash
python cli.py "Test" --video-provider mock --tts-provider mock
```

**Enable debug output:**
```python
# Add to cli.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

### Script Generation Issues

#### Problem: Script is too short/long

**Solution:**
Edit prompt to be more specific:
```
Bad:  "Explain X"
Good: "Explain X in detail, covering A, B, and C, 
       suitable for a 60-second video"
```

---

#### Problem: Script quality is poor

**Solutions:**
1. Be more specific in prompt
2. Provide examples of desired style
3. Iterate on prompt phrasing
4. Use system prompt customization

**Example:**
```python
# In script_generator.py, modify the prompt:
prompt = f"""Create a SHORT educational video script...

Style: Engaging, simple language
Audience: General public
Tone: Friendly and informative

Topic: {user_prompt}
"""
```

---

### Scene Planning Issues

#### Problem: Too many/few scenes generated

**Solution:**
Edit `config.py`:
```python
TARGET_SCENES = 3  # Fewer scenes
# or
TARGET_SCENES = 8  # More scenes
```

---

#### Problem: Scenes don't flow well

**Solution:**
The scene planner uses Claude. Improve by:
1. Better script quality (clearer prompts)
2. More specific visual descriptions
3. Edit scene_planner.py prompt template

---

### File System Issues

#### Problem: `Permission denied` when saving files

**Solutions:**
```bash
# Check permissions
ls -la output/

# Fix permissions
chmod 755 output/
chmod 755 temp/
```

---

#### Problem: Disk full

**Check disk space:**
```bash
df -h
```

**Clean up temp files:**
```bash
rm -rf temp/*
```

**Clean old outputs:**
```bash
# Keep only last 5 videos
ls -t output/*.mp4 | tail -n +6 | xargs rm
```

---

### Memory Issues

#### Problem: `MemoryError` or system freezing

**Causes:**
- Large video files
- Multiple concurrent generations
- System resources exhausted

**Solutions:**
1. Generate one video at a time
2. Reduce scene count
3. Use shorter durations
4. Clear temp files between runs
5. Increase system RAM/swap

---

### Network Issues

#### Problem: `ConnectionError` or timeouts

**Solutions:**
1. Check internet connection
2. Check API status pages
3. Add retry logic:

```python
import time

def retry_api_call(func, max_retries=3):
    for i in range(max_retries):
        try:
            return func()
        except Exception as e:
            if i == max_retries - 1:
                raise
            print(f"Retry {i+1}/{max_retries}...")
            time.sleep(2 ** i)  # Exponential backoff
```

---

### JSON Parsing Issues

#### Problem: `JSONDecodeError: Expecting value`

**Cause:** API returned non-JSON response

**Debug:**
```python
# In script_generator.py
print("Raw response:", response.content[0].text)
```

**Solution:**
The code strips markdown formatting, but if it still fails:
1. Check prompt is clear
2. Verify API is working
3. Add better error handling

---

### Import Issues

#### Problem: `ImportError: cannot import name 'X'`

**Solution:**
Ensure all files are in same directory:
```
video_pipeline/
├── config.py
├── pipeline.py
├── script_generator.py
├── scene_planner.py
└── ... (all .py files)
```

Run from parent directory:
```bash
cd /path/to/parent
python -m video_pipeline.cli "Test"
```

Or set PYTHONPATH:
```bash
export PYTHONPATH=/path/to/video_pipeline:$PYTHONPATH
```

---

## Debug Checklist

When something isn't working:

1. ✅ Python 3.8+ installed?
   ```bash
   python --version
   ```

2. ✅ Dependencies installed?
   ```bash
   pip list | grep anthropic
   pip list | grep streamlit
   ```

3. ✅ API key set?
   ```bash
   echo $ANTHROPIC_API_KEY
   ```

4. ✅ ffmpeg installed?
   ```bash
   ffmpeg -version
   ```

5. ✅ Directories created?
   ```bash
   ls -la output/ temp/
   ```

6. ✅ Internet connection?
   ```bash
   ping google.com
   ```

7. ✅ Disk space available?
   ```bash
   df -h .
   ```

---

## Getting Help

Still stuck?

1. **Check logs:**
   - Streamlit: Look at terminal output
   - CLI: Use verbose mode
   - Code: Add print statements

2. **Minimal reproduction:**
   ```python
   # Test each module independently
   from script_generator import ScriptGenerator
   gen = ScriptGenerator()
   result = gen.generate("Test")
   print(result)
   ```

3. **Check API status:**
   - Anthropic: https://status.anthropic.com/
   - Your video/TTS provider status page

4. **GitHub Issues:**
   - Search for similar issues
   - Create detailed bug report

5. **Community:**
   - Anthropic Discord
   - Stack Overflow
   - Reddit r/ClaudeAI

---

## Reporting Bugs

Include:
1. Error message (full traceback)
2. Python version
3. OS (macOS/Linux/Windows)
4. Steps to reproduce
5. What you expected
6. What actually happened

**Example:**
```
Environment:
- Python 3.11.5
- macOS 14.0
- All dependencies installed

Steps:
1. Run: python cli.py "Test prompt"
2. Pipeline initializes
3. Script generation succeeds
4. Scene planning fails

Error:
JSONDecodeError: Expecting value: line 1 column 1 (char 0)

Expected: Scenes generated
Actual: Crash with JSON error
```

---

## Performance Tips

### Speed Up Generation

1. **Use parallel processing** (future feature)
2. **Reduce scene count:**
   ```python
   TARGET_SCENES = 3  # Instead of 5
   ```
3. **Shorter scenes:**
   ```python
   SCENE_DURATION_MAX = 5  # Instead of 8
   ```
4. **Cache results:**
   - Save successful generations
   - Reuse scenes for similar prompts

### Reduce Costs

1. **Use mock mode for testing**
2. **Iterate on scripts before video gen**
3. **Batch similar videos**
4. **Use cheaper TTS providers**

### Improve Quality

1. **More detailed prompts**
2. **Longer scene durations**
3. **Higher quality video models**
4. **Professional voice options**

---

## Emergency Fixes

### Quick Reset

```bash
# Delete all temp files
rm -rf temp/*

# Reset output
rm -rf output/*
mkdir output

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Start Fresh

```bash
# Complete clean install
rm -rf venv/
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

Good luck! 🚀
