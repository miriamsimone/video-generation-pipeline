# Generate Neutral Pose Sequences

**Script:** `generate_neutral_pose_sequences.py`

Generates pose-to-pose transition sequences for the neutral expression using recursive midpoint refinement.

## What It Does

**Input:**
- Neutral expression at **all poses** (e.g., `neutral__center.png`, `neutral__tilt_left_small.png`, etc.)
- `expressions.json` defining all poses

**Output:**
- Pose transition sequences for neutral (e.g., `neutral_center_to_neutral_tilt_left_small`)
- Each sequence has endpoints + midpoints + `manifest.json`

**Why This Matters:**
- Neutral is your "hub state" for transitioning between expressions
- You need smooth pose transitions (center → tilt, center → nod, etc.)
- Without these, neutral can't move its head naturally
- Generated neutral matches the style of other model-generated frames

---

## Quick Start

```bash
export OPENAI_API_KEY=sk-...

python generate_neutral_pose_sequences.py \
  --config expressions.json \
  --endpoints-dir frames/endpoints \
  --sequences-dir frames/sequences \
  --source-pose center \
  --max-depth 2 \
  --max-workers 8
```

**Result:**
```
frames/sequences/
├── neutral_center_to_neutral_tilt_left_small/
│   ├── 000.png  (neutral at center)
│   ├── 025.png
│   ├── 050.png
│   ├── 075.png
│   ├── 100.png  (neutral at tilt_left)
│   └── manifest.json
├── neutral_center_to_neutral_tilt_right_small/
├── neutral_center_to_neutral_nod_up_small/
└── neutral_center_to_neutral_nod_down_small/
```

---

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--config` | ✅ | - | Path to `expressions.json` |
| `--endpoints-dir` | ❌ | `frames/endpoints` | Directory with neutral pose images |
| `--sequences-dir` | ❌ | `frames/sequences` | Output directory for sequences |
| `--source-pose` | ❌ | `center` | Pose to transition FROM |
| `--size` | ❌ | `1024x1536` | Image dimensions |
| `--max-workers` | ❌ | `4` | Parallel OpenAI API calls |
| `--max-depth` | ❌ | `2` | Recursive refinement depth (2 → 3 tweens) |
| `--overwrite` | ❌ | `false` | Overwrite existing tween frames |

---

## How It Works

### 1. Discovery Phase

Scans `frames/endpoints/` for neutral at all poses:

```
neutral__center.png          ✓ Found
neutral__tilt_left_small.png ✓ Found
neutral__tilt_right_small.png ✓ Found
neutral__nod_up_small.png     ✓ Found
neutral__nod_down_small.png   ✓ Found
```

If any pose is missing, it's skipped.

### 2. Sequence Initialization

For each target pose (not including source pose):
- Creates sequence directory: `neutral_<source>_to_neutral_<target>`
- Copies endpoints: `000.png` (source) and `100.png` (target)

### 3. Recursive Midpoint Refinement

Same algorithm as expression sequences:

**Depth 1:**
```
center ────────── 0.5 ────────── tilt_left
```

**Depth 2:**
```
center ── 0.25 ── 0.5 ── 0.75 ── tilt_left
```

All frames at each depth generate in parallel.

### 4. Manifest Creation

Each sequence gets a `manifest.json`:

```json
{
  "path_id": "neutral_center_to_neutral_tilt_left_small",
  "expr_start": "neutral",
  "expr_end": "neutral",
  "pose": "center_to_tilt_left_small",
  "frames": [
    { "t": 0.0, "file": "000.png" },
    { "t": 0.25, "file": "025.png" },
    { "t": 0.5, "file": "050.png" },
    { "t": 0.75, "file": "075.png" },
    { "t": 1.0, "file": "100.png" }
  ]
}
```

---

## Example Usage

### Standard workflow

```bash
export OPENAI_API_KEY=sk-...

# After Step 1-2 (generate expressions + head tilts)
python generate_neutral_pose_sequences.py \
  --config expressions.json \
  --endpoints-dir frames/endpoints \
  --sequences-dir frames/sequences \
  --source-pose center \
  --max-depth 2 \
  --max-workers 8
```

Output:
```
[i] Initialized 4 neutral pose sequences.

=== Pose refinement depth 1 ===
[i] Depth 1: 4 pose tween frames to generate.
[✓] neutral_center_to_neutral_tilt_left_small t=0.500 -> 050.png
[✓] neutral_center_to_neutral_tilt_right_small t=0.500 -> 050.png
[✓] neutral_center_to_neutral_nod_up_small t=0.500 -> 050.png
[✓] neutral_center_to_neutral_nod_down_small t=0.500 -> 050.png
[i] Depth 1 done. Success: 4, Failed: 0

=== Pose refinement depth 2 ===
[i] Depth 2: 8 pose tween frames to generate.
[✓] neutral_center_to_neutral_tilt_left_small t=0.250 -> 025.png
[✓] neutral_center_to_neutral_tilt_left_small t=0.750 -> 075.png
...
[i] Depth 2 done. Success: 8, Failed: 0

[i] Wrote manifest: frames/sequences/neutral_center_to_neutral_tilt_left_small/manifest.json
[i] Wrote manifest: frames/sequences/neutral_center_to_neutral_tilt_right_small/manifest.json
...
```

### Dense sequences

For ultra-smooth pose transitions:

```bash
python generate_neutral_pose_sequences.py \
  --config expressions.json \
  --max-depth 3 \
  --max-workers 10
```

This generates 7 tweens per sequence instead of 3.

---

## Integration with Pipeline

This script fits into the complete workflow as **Step 4**:

1. **Step 1:** Generate extreme expressions at center (`generate_extreme_expressions.py --include-neutral`)
2. **Step 2:** Generate head tilts for all expressions (`generate_head_tilts.py`)
3. **Step 3:** Generate expression sequences (`generate_all_sequences.py`)
4. **Step 4:** Generate pose sequences (`generate_neutral_pose_sequences.py`) ← YOU ARE HERE
5. **Step 5-7:** Start backend, start UI, refine

---

## Why Generate Neutral?

**Problem:** If you use the base image as neutral, it won't match the style of model-generated frames.

**Solution:** Generate neutral with `--include-neutral` in Step 1:

```bash
python generate_extreme_expressions.py \
  --config expressions.json \
  --base-image watercolor_boy_greenscreen.png \
  --pose center \
  --outdir frames/endpoints \
  --include-neutral \
  --max-workers 6
```

Now `neutral__center.png` is model-generated and style-consistent with all other frames.

---

## Prompt Strategy

The script generates pose transitions while **preserving the neutral facial expression**:

```python
prompt = f"""
Watercolor portrait of the same young boy on a transparent background,
matching the style, identity, hairstyle, clothing, and framing of the
reference images.

Facial expression:
  - Keep the expression identical to the neutral reference:
    {expr_desc}

Head pose:
  - This frame is an in-between at relative t = {job.mid_t:.2f}
    between these head poses:
      * Start: {pose_start_desc}
      * End:   {pose_end_desc}

  - Only adjust the head orientation/tilt smoothly between these two
    poses. Do NOT change the mouth, eyes, eyebrows shape (beyond minor
    perspective effects), hairstyle, clothing, earrings, or background.
"""
```

---

## Cost Estimation

**For 5 poses:**
- 4 pose sequences (center → 4 other poses)
- At `max_depth=2`: 4 × 3 tweens = **12 API calls**
- Cost: 12 × $0.10 = **$1.20**

**For `max_depth=3`:**
- 4 × 7 tweens = **28 API calls**
- Cost: 28 × $0.10 = **$2.80**

---

## Use Cases

### Animation Hub State

Neutral at center is typically your "rest" state. From there:
- Transition to any expression (via expression sequences)
- Transition to any pose (via pose sequences)

### Character Looking Around

Pose sequences let your character naturally:
- Look left/right (tilt sequences)
- Nod up/down (nod sequences)
- All while maintaining neutral expression

### Combining Transitions

In your animation system:
1. Play `neutral_center_to_neutral_tilt_left_small` (pose change)
2. Then `neutral_to_happy_soft__tilt_left_small` (expression change at new pose)
3. Then `happy_soft__tilt_left_small` to `happy_soft__center` (return to center)

All smooth, all generated!

---

## Troubleshooting

### "Missing endpoint image for neutral at source pose"

Generate neutral first:

```bash
python generate_extreme_expressions.py \
  --config expressions.json \
  --base-image watercolor_boy_greenscreen.png \
  --pose center \
  --include-neutral
```

### "Skipping pose 'X' (no neutral__X.png)"

Generate head tilts:

```bash
python generate_head_tilts.py \
  --config expressions.json \
  --endpoints-dir frames/endpoints \
  --base-neutral watercolor_boy_greenscreen.png \
  --source-pose center
```

### "Expression 'neutral' not found in expressions.json"

Add neutral to your config:

```json
{
  "expressions": {
    "neutral": { "mouth": "neutral", "eyes": "neutral", "brows": "neutral" },
    ...
  }
}
```

---

## Next Steps

1. **Generate extreme expressions** (with `--include-neutral`)
2. **Generate head tilts** (for all expressions including neutral)
3. **Generate expression sequences** (expression × pose transitions)
4. **Generate pose sequences** (neutral pose transitions) ← Run this script
5. **Preview in UI** and refine

Your complete animation rig is ready! 🎬

