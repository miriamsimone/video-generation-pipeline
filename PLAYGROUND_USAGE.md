# Video Model Playground - Quick Usage Guide

## New Features

✅ **70+ video models** from Replicate  
✅ **Model switching** in interactive mode  
✅ **Parallel testing** across multiple models  
✅ **Organized by category** (Premium, Fast, Budget, etc.)

## Usage Modes

### 1. Interactive Mode (Recommended)

```bash
python minimax_playground.py
```

**Commands:**
- Enter a prompt → Generate with current model
- `models` → Show all available models
- `switch` → Change current model
- `parallel` → Test prompt across multiple models
- `examples` → Show example prompts
- `quit` → Exit

### 2. Show All Models

```bash
python minimax_playground.py models
```

### 3. Use Specific Model

```bash
python minimax_playground.py --model google/veo-3.1-fast "A ball bouncing"
```

### 4. Parallel Test (Command Line)

```bash
python minimax_playground.py parallel "Numbers sorting themselves"
```

Uses 3 fast models by default.

### 5. Batch Test

```bash
python minimax_playground.py batch
```

## Parallel Testing in Interactive Mode

Type `parallel` at the prompt, then choose:

**1. Fast Models (3 models)** - Quick comparison
- minimax/hailuo-2.3-fast
- bytedance/seedance-1-pro-fast  
- wan-video/wan-2.5-t2v-fast

**2. Premium Models (5 models)** - Best quality
- openai/sora-2
- google/veo-3.1-fast
- minimax/hailuo-2.3-fast
- bytedance/seedance-1-pro-fast
- kwaivgi/kling-v2.5-turbo-pro

**3. Minimax Family (4 models)** - Compare minimax versions
- minimax/video-01
- minimax/hailuo-2.3
- minimax/hailuo-2.3-fast
- minimax/video-01-live

**4. Custom Selection** - Pick your own models

## Example Session

```bash
$ python minimax_playground.py

VIDEO GENERATION PLAYGROUND
Test different prompts across multiple video models!
Commands: 'quit', 'examples', 'models', 'switch', 'parallel'

[minimax/video-01]
Enter your prompt: switch

AVAILABLE VIDEO MODELS
...

Enter model name (or part of it) to switch: veo
Multiple matches found:
  1. google/veo-3.1
  2. google/veo-3.1-fast
  3. google/veo-3
  4. google/veo-3-fast
  5. google/veo-2

Select number: 2
✅ Switched to: google/veo-3.1-fast

[google/veo-3.1-fast]
Enter your prompt: parallel

PARALLEL MODEL COMPARISON

Suggested model groups:
  1. Fast models (3 models)
  2. Premium models (5 models)
  3. Minimax family (4 models)
  4. Custom selection

Select group (1-4) or press Enter for fast models: 1

Enter prompt to test across all models: Five cards numbered 5,2,8,1,4 sort into 1,2,4,5,8

🚀 Running parallel test with 3 models...
✅ minimax/hailuo-2.3-fast - completed
✅ bytedance/seedance-1-pro-fast - completed  
✅ wan-video/wan-2.5-t2v-fast - completed

PARALLEL TEST RESULTS
Success: 3/3
...
```

## Finding Best Model for Your Use Case

### For Sorting/Algorithm Visualization

Test these models in parallel:
```bash
# In interactive mode
> parallel
> [Select group 2 - Premium models]
> Prompt: Five numbered cards rearrange from 5,2,8,1,4 into sorted order 1,2,4,5,8
```

Compare results to see which handles sequential actions best.

### For Speed

Fast models (under 30 seconds):
- `minimax/hailuo-2.3-fast`
- `google/veo-3.1-fast`
- `bytedance/seedance-1-pro-fast`

### For Quality

Premium models:
- `openai/sora-2`
- `google/veo-3.1`
- `minimax/hailuo-2.3`

## Output Files

Videos are saved with model name included:
```
playground_outputs/20251114_150430_google_veo-3.1-fast_Five_cards.mp4
playground_outputs/20251114_150532_minimax_hailuo-2.3-fast_Five_cards.mp4
```

Easy to compare side-by-side!

## Tips

1. **Start with fast models** for iteration
2. **Use parallel mode** to compare 3-5 models at once
3. **Test same prompt** across models to find which interprets best
4. **Check model categories** - some are better for specific tasks
5. **Budget matters** - check Replicate pricing per model

## Model Categories

- **Premium T2V**: Best quality, expensive (Sora, Veo, Hailuo)
- **Fast/Turbo**: Quick iterations, good quality
- **High Quality**: Slower but detailed
- **Budget/Classic**: Cheaper, older models
- **Image-to-Video**: Requires starting frame

Try them all and find what works for your quicksort example! 🎬



