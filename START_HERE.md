# 🚀 START HERE - Face Rig + Geo Tour Integration

## ✅ Integration Complete!

The face_rig character animation system is now fully integrated with Geo_Tour video generation.

## 🎯 Quick Start (5 minutes)

### Step 1: Start Face Rig Server

Open a terminal and run:

```bash
cd face_rig
conda activate aligner
python server.py
```

Keep this terminal running! You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
✅ Face_rig server ready
```

### Step 2: Launch Geo Tour UI

Open a **second terminal** and run:

```bash
cd Geo_Tour-main
streamlit run app.py
```

Your browser will open to `http://localhost:8501`

### Step 3: Generate Your First Video

1. Click **"🚀 Initialize Pipeline"** in the sidebar
2. Make sure **"Enable Face Rig Character"** is checked ✓
3. Enter a prompt: `"Explain how rainbows form"`
4. Click **"🎬 Generate Video"**

Wait 6-8 minutes and your video will be ready with an animated character! 🎉

## 📚 Documentation

- **New to this?** → Read [FACE_RIG_QUICKSTART.md](FACE_RIG_QUICKSTART.md)
- **Need details?** → Read [FACE_RIG_INTEGRATION.md](Geo_Tour-main/FACE_RIG_INTEGRATION.md)
- **Want to test?** → Run `python Geo_Tour-main/test_face_rig_integration.py`
- **Need config help?** → Check [config_face_rig.example.py](Geo_Tour-main/config_face_rig.example.py)
- **Integration overview?** → Read [INTEGRATION_COMPLETE.md](INTEGRATION_COMPLETE.md)

## 🎭 What You Get

Your videos will now include:

✅ **Animated Character** - Appears in bottom-right corner  
✅ **Lip-Sync** - Mouth movements match speech perfectly  
✅ **Emotions** - AI-generated expressions match content sentiment  
✅ **Per-Scene Audio** - Each scene has individually generated narration  
✅ **Perfect Timing** - Scene lengths automatically adjust to audio duration  

## 🔧 Prerequisites Check

Make sure you have:

- [ ] Face_rig server running (`http://localhost:8000`)
- [ ] MFA installed in conda environment (`conda activate aligner && mfa version`)
- [ ] API keys set in `.env`:
  - `OPENAI_API_KEY`
  - `ELEVENLABS_API_KEY`
  - `REPLICATE_API_KEY`
- [ ] FFmpeg installed (`ffmpeg -version`)

## 🎬 Example Prompts to Try

1. **"Explain how photosynthesis works in plants"**
2. **"Describe the journey of water from ocean to clouds to rain"**
3. **"Tell me about the solar system and its planets"**
4. **"Explain what causes thunder and lightning"**

## ⚙️ Key Settings

### Change Character Voice

In the UI sidebar under "Face Rig Character Animation":
- **Sam** (default) - Conversational male
- **Bella** - Conversational female
- **Domi** - Strong female
- **Adam** - Deep male

### Adjust Scene Count

Recommended: **3-5 scenes** for 18-30 second videos

- Fewer scenes = Faster generation
- More scenes = More detailed story

### Toggle Face Rig

Uncheck "Enable Face Rig Character" to generate videos without the character overlay.

## 🐛 Troubleshooting

### "Face_rig server not available"
```bash
cd face_rig
conda activate aligner
python server.py
```

### "MFA alignment failed"
```bash
conda activate aligner
mfa model download acoustic english_us_arpa
mfa model download dictionary english_us_arpa
```

### "API error"
Check your `.env` file has valid API keys with no extra spaces.

## 📊 What to Expect

For a **3-scene video** (~18 seconds):

| Step | Time | Cost |
|------|------|------|
| Script Generation | 10s | $0.01 |
| Scene Planning | 15s | $0.02 |
| Storyboard | 30s | $0.15 |
| **Face Rig** | **2-3 min** | **$0.15** |
| Video Clips | 2-3 min | $0.30 |
| Assembly | 30s | - |
| **Total** | **6-8 min** | **~$0.65** |

## 🎓 Next Steps

1. **Test the integration**: `python Geo_Tour-main/test_face_rig_integration.py`
2. **Generate your first video** using the UI
3. **Explore customization** in `config_face_rig.example.py`
4. **Read detailed docs** in `FACE_RIG_INTEGRATION.md`

## 🆘 Need Help?

1. Run the test suite: `python Geo_Tour-main/test_face_rig_integration.py`
2. Check face_rig server logs in Terminal 1
3. Check Geo_Tour logs in Terminal 2
4. Review `FACE_RIG_INTEGRATION.md` troubleshooting section

## 🎉 You're All Set!

The integration is complete and ready to use. Just start the face_rig server and launch the UI to begin creating videos with animated character narration!

**Happy creating!** 🎬✨

---

**Quick Links**:
- 📖 [Quick Start Guide](FACE_RIG_QUICKSTART.md)
- 📚 [Full Documentation](Geo_Tour-main/FACE_RIG_INTEGRATION.md)
- 🧪 [Test Suite](Geo_Tour-main/test_face_rig_integration.py)
- ⚙️ [Configuration Reference](Geo_Tour-main/config_face_rig.example.py)
- ✅ [Integration Summary](INTEGRATION_COMPLETE.md)

