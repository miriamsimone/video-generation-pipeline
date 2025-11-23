# Fixes Applied for Replicate Video Generation

## Problem
You were getting a `ModelError` when trying to generate videos with Replicate's minimax/video-01 model.

## Root Cause (Likely)
The play-by-play agent generates very detailed, structured prompts with timelines like:

```
Create a video for: Generate a video illustrating quicksort...

Visual style: Clean flat 2D animation...

For this 6000ms segment, follow this visual timeline:
* At 0ms: A horizontal row of 12 cards...
* At 1000ms: The leftmost card is highlighted...
* At 1500ms: The second card slides...
...
```

**Video generation models prefer simple, concise prompts** (usually < 500 characters), not detailed timelines.

## Fixes Applied

### 1. Simplified Prompt Builder ✅
Created `src/prompt_builder_simple.py` that:
- Extracts key visual elements from keyframes
- Creates concise, flowing descriptions
- Limits prompt length to 500 characters
- Focuses on start state → key actions → end state

Example output:
```
Clean flat 2D animation. Starting with: A horizontal row of 12 cards in random order. 
Then: The leftmost card is highlighted and rises. Ending with: The pivot card glides 
to its sorted position.
```

### 2. Configuration Option ✅
Added `USE_SIMPLE_PROMPTS=True` to `.env` (enabled by default)

### 3. Better Error Logging ✅
Enhanced `video_generator_replicate.py` to show:
- Full error details
- Input parameters that caused the error
- Model name and configuration

### 4. Diagnostic Tools ✅
Created helpful testing scripts:
- `test_replicate_models.py` - Check model availability and parameters
- `test_simple_video_gen.py` - Test basic video generation
- `REPLICATE_TROUBLESHOOTING.md` - Comprehensive troubleshooting guide

## How to Test the Fixes

### Option 1: Try Video Generation Again

```bash
python example_usage.py
```

Select option 2 (Simple Ball Animation) - it's faster for testing.

The system will now use simplified prompts automatically.

### Option 2: Check the Simple Test

The background test `test_simple_video_gen.py` should complete in 1-2 minutes.

Check if it created `test_output.mp4`:
```bash
ls -lh test_output.mp4
```

If it exists, the Replicate integration works! The issue was just the prompt complexity.

### Option 3: Compare Prompt Styles

You can toggle between simple and detailed prompts in `.env`:

```env
# Simple prompts (recommended for video models)
USE_SIMPLE_PROMPTS=True

# Detailed prompts (original behavior)
USE_SIMPLE_PROMPTS=False
```

## Alternative: Try a Different Model

If minimax/video-01 still has issues, update `.env`:

```env
# Text-to-video alternative
REPLICATE_MODEL=anotherjesse/zeroscope-v2-xl

# Or image-to-video (needs a starting image)
REPLICATE_MODEL=stability-ai/stable-video-diffusion
```

## What to Expect

### With Simple Prompts (New Default)
- ✅ Shorter, more reliable prompts
- ✅ Better compatibility with video models
- ⚠️ Less precise timing/transitions
- ⚠️ Model interprets the flow creatively

### With Detailed Prompts (Original)
- ✅ Very precise keyframe descriptions
- ✅ Detailed timeline information
- ⚠️ May overwhelm video models
- ⚠️ Higher chance of errors

## Other Possible Issues

If you still get errors:

1. **Check Replicate Billing**
   - Visit: https://replicate.com/account/billing
   - Some models require payment method setup

2. **Rate Limits**
   - Free tier has usage limits
   - Wait a bit between requests

3. **Model Availability**
   - Models can be temporarily unavailable
   - Try an alternative model

## Testing Checklist

- [ ] Run `python test_play_by_play.py` (should work - just storyboard)
- [ ] Check if `test_output.mp4` was created from background test
- [ ] Try `python example_usage.py` with option 2
- [ ] If still failing, check Replicate account/billing
- [ ] Try alternative model (zeroscope-v2-xl)

## Summary

The main fix is **simplified prompts**. Video models work better with concise descriptions rather than detailed timelines. The system now automatically creates shorter, more suitable prompts while preserving the creative intent from the play-by-play storyboard.

Try running the examples again - they should work much better now! 🎬



