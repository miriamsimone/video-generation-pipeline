# Minimax Video Playground Guide

Interactive tool for testing minimax/video-01 prompts and understanding what the model can do.

## Quick Start

### Interactive Mode

```bash
python minimax_playground.py
```

This starts an interactive session where you can:
- Enter custom prompts
- Optionally provide a starting frame image
- See results immediately
- Iterate quickly

### Single Prompt Mode

```bash
python minimax_playground.py "Your prompt here"
```

Generate a single video from command line.

### Batch Test Mode

```bash
python minimax_playground.py batch
```

Test multiple pre-defined prompts to compare results.

## Usage Examples

### Test Simple vs Detailed Prompts

**Simple:**
```
A red ball bounces
```

**Detailed:**
```
A red rubber ball bounces on a wooden surface, starting high on the left, 
bouncing three times while moving right, each bounce getting lower
```

### Test Sorting Animation Granularity

**Very Simple:**
```
Cards arrange themselves in numerical order
```

**Medium Detail:**
```
Five cards numbered 5, 2, 8, 1, 4 rearrange into 1, 2, 4, 5, 8
```

**Maximum Detail:**
```
Five cards are shown in a row: 5, 2, 8, 1, 4. 
First, cards 1 and 5 swap positions.
Then cards 2 and 8 swap.
Then card 4 moves to middle.
Final order: 1, 2, 4, 5, 8.
```

### Test with Starting Frames

1. Create a starting frame image (or use a screenshot)
2. In interactive mode, provide the path when asked:
   ```
   First frame image path: my_starting_frame.png
   ```

This is useful for:
- Continuing from a specific state
- Testing frame-to-frame continuity
- Building multi-step sequences

## Finding the Right Level of Detail

The playground helps you discover:

### ✅ What Works
- Clear, descriptive language
- Specific visual details (colors, positions)
- Simple sequential actions
- Visual style descriptions

### ❌ What Might Not Work
- Too many steps (model may simplify)
- Precise timing requirements
- Complex logic (like actual sorting algorithms)
- Abstract concepts without visual grounding

## Testing Strategy

### 1. Start Simple
Test basic prompts to see if the concept works:
```
python minimax_playground.py "Cards sorting from random to ordered"
```

### 2. Add Detail Gradually
```
python minimax_playground.py "Five colored cards numbered 1-5 shuffle then sort"
```

### 3. Test Granularity
```
python minimax_playground.py "Card 1 moves left. Card 2 moves right. Card 3 stays still"
```

### 4. Compare Results
All videos are saved to `playground_outputs/` with timestamps, so you can:
- Compare different prompt styles
- See which level of detail works best
- Build a library of working prompts

## Outputs

Videos are saved as:
```
playground_outputs/YYYYMMDD_HHMMSS_prompt_preview.mp4
```

Each includes:
- Timestamp for easy sorting
- First 30 chars of prompt for identification
- Full metadata in the filename

## Tips for Quicksort Example

Based on your experience, test these variations:

### Option 1: Abstract Animation
```
Colorful numbered cards smoothly rearrange from random order to sorted order, 
showing a visual sorting process
```

### Option 2: Step-by-Step
```
Cards labeled 3, 1, 4, 1, 5, 9, 2, 6 are shown. 
The smallest card (1) moves to first position.
Then the next smallest moves to second position.
This continues until all cards are sorted.
```

### Option 3: Highlight-Based
```
Cards in a row. One card glows (pivot). Other cards rearrange around it based on 
their values, smaller to left, larger to right.
```

### Option 4: Comparison-Based
```
Two cards at a time light up, compare, and swap if needed. This repeats across 
the row until all cards are in order.
```

## Advanced: Multi-Video Sequences

Generate a sequence with frame chaining:

```bash
# Generate first part
python minimax_playground.py "Initial state: cards 5,2,8,1,4 in a row"

# Use last frame of that video as first frame for next
# (extract frame with ffmpeg first)
ffmpeg -i playground_outputs/first_video.mp4 -vframes 1 -update 1 last_frame.png

# Then in interactive mode, use last_frame.png for next prompt
python minimax_playground.py
> Enter prompt: Cards begin to sort, 1 moves to first position
> First frame: last_frame.png
```

## Keyboard Shortcuts in Interactive Mode

- **Enter** with empty prompt: skip
- **quit**: exit
- **examples**: show example prompts
- **n** when asked about optimizer: disable prompt optimization

## What to Look For

When testing, observe:
1. **Accuracy**: Does it do what you asked?
2. **Smoothness**: Are transitions natural?
3. **Consistency**: Do repeated prompts give similar results?
4. **Granularity**: How detailed can you be before it ignores details?
5. **Duration**: Does it use the full 6 seconds effectively?

## Next Steps

Once you find prompts that work well:
1. Note the successful patterns
2. Adjust the pipeline's prompt builder to match that style
3. Update `src/prompt_builder_simple.py` with insights
4. Test the full pipeline again with quicksort

The goal is to find the "sweet spot" of detail that the model responds to best!



