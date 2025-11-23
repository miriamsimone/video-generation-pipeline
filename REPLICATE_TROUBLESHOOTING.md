# Replicate Video Generation Troubleshooting

## What We Know

✅ The `minimax/video-01` model EXISTS on Replicate  
✅ Your API token is configured correctly  
✅ The model accepts these parameters:
  - `prompt` (string) - Text prompt for generation
  - `prompt_optimizer` (boolean) - Use prompt optimizer (default: True)
  - `first_frame_image` (string) - Optional first frame image
  - `subject_reference` (string) - Optional character reference

## Current Issue

You're getting a `ModelError` when trying to generate videos. This could be caused by:

1. **Prompt is too long or complex** - The LLM-generated prompts might be too detailed
2. **Rate limiting** - Replicate has usage limits
3. **Model-specific requirements** - The model might need specific prompt formats
4. **Payment/billing** - Account might need payment method configured

## Testing Steps

### 1. Test Simple Generation

Run this to test with a minimal prompt:

```bash
python test_simple_video_gen.py
```

This tests with just: "A red ball bouncing on a white surface"

If this works, the issue is with the complex prompts from the play-by-play agent.

### 2. Check Your Replicate Account

Visit: https://replicate.com/account

- Check if you have predictions/usage shown
- Verify billing is set up (some models require it)
- Check if you have any rate limit warnings

### 3. Test with Alternative Models

If minimax/video-01 doesn't work, try these alternatives:

**Zeroscope (Text-to-Video)**
```python
output = client.run(
    "anotherjesse/zeroscope-v2-xl",
    input={"prompt": "A ball bouncing"}
)
```

**Stable Video Diffusion (Image-to-Video)**
```python
output = client.run(
    "stability-ai/stable-video-diffusion",
    input={
        "input_image": "https://replicate.delivery/pbxt/JvVcVYKAjNXc6J5ZPlJZR9JI8RmPo8cHBdLTSRIlS6yp9LZk/rocket.png"
    }
)
```

Update your `.env` to use a different model:
```env
REPLICATE_MODEL=anotherjesse/zeroscope-v2-xl
```

## Common Issues and Fixes

### Issue: Empty ModelError

**Cause:** The model is rejecting the input but not providing details.

**Fix:** 
1. Simplify the prompt
2. Check prompt length (max ~1000 characters)
3. Remove special characters

### Issue: Prompt Too Complex

The play-by-play agent generates very detailed prompts like:

```
Create a video for: Generate a video illustrating quicksort...

Visual style: Clean flat 2D animation...

For this 6000ms segment, follow this visual timeline:
* At 0ms: A horizontal row of...
* At 1000ms: The leftmost card...
...
```

**Fix:** We need to simplify these prompts for the video model.

### Issue: Model Requires Payment

Some models on Replicate require a payment method even for testing.

**Fix:**
1. Go to https://replicate.com/account/billing
2. Add a payment method
3. Note: You won't be charged without running predictions

## Modified Video Generator

I'm creating an updated version that:
1. Simplifies/shortens prompts for video models
2. Adds better error handling
3. Falls back to alternative models if needed
4. Validates prompts before sending

## Quick Workaround

For now, you can test just the play-by-play generation (which works!):

```bash
python test_play_by_play.py
```

This will show you the storyboards without attempting video generation.

## Next Steps

1. ✅ Test simple generation (`test_simple_video_gen.py`)
2. If that works: Simplify prompt builder
3. If that fails: Try alternative model
4. Check Replicate billing/limits
5. Consider using shorter video duration for testing

Check back in a minute or two - `test_simple_video_gen.py` is running in the background!



