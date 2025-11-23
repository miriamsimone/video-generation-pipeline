# Generate Head Tilts

**Script:** `generate_head_tilts.py`

Multiplies your extreme expressions across all head poses by taking a single source pose (e.g., `center`) and generating all other head tilts while preserving facial expressions.

## What It Does

**Input:**
- **All extreme expressions** at **one pose** (e.g., `neutral__center.png`, `speaking_ah__center.png`, `speaking_ee__center.png`, etc.)
- `expressions.json` defining all poses

**Output:**
- **Each expression** at **all poses** (e.g., `speaking_ah__tilt_left_small.png`, `speaking_ee__nod_up_small.png`, etc.)

**Strategy:**
- Uses OpenAI `gpt-image-1` to change **only head orientation**
- Preserves facial expression, hairstyle, clothing, and identity
- Runs in parallel using `ThreadPoolExecutor`

---

## Quick Start

```bash
export OPENAI_API_KEY=sk-...

python generate_head_tilts.py \
  --config expressions.json \
  --endpoints-dir frames/endpoints \
  --base-neutral watercolor_boy_greenscreen.png \
  --source-pose center \
  --max-workers 6
```

**Result:**
```
frames/endpoints/
├── neutral__center.png
├── neutral__tilt_left_small.png
├── neutral__tilt_right_small.png
├── neutral__nod_up_small.png
├── neutral__nod_down_small.png
├── speaking_ah__center.png
├── speaking_ah__tilt_left_small.png
├── speaking_ah__tilt_right_small.png
├── speaking_ah__nod_up_small.png
├── speaking_ah__nod_down_small.png
└── ...
```

---

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--config` | ✅ | - | Path to `expressions.json` |
| `--endpoints-dir` | ❌ | `frames/endpoints` | Directory with expression images |
| `--base-neutral` | ❌ | - | Base neutral image (used if `neutral__center.png` missing) |
| `--source-pose` | ❌ | `center` | Pose that existing expressions are in |
| `--size` | ❌ | `1024x1536` | Image dimensions |
| `--max-workers` | ❌ | `4` | Parallel OpenAI API calls |
| `--overwrite` | ❌ | `false` | Overwrite existing head tilt images |

---

## How It Works

### 1. Discovery Phase

Scans `frames/endpoints/` for files matching `<expr_id>__<source_pose>.png`:

```
neutral__center.png         ✓ Found
speaking_ah__center.png     ✓ Found
speaking_ee__center.png     ✓ Found
speaking_uw__center.png     ✓ Found
```

If `neutral__center.png` is missing but `--base-neutral` is provided, it will be copied into place.

### 2. Job Building

For each discovered expression:
- **Source:** Expression at `source_pose` (e.g., `speaking_ah__center.png`)
- **Targets:** All other poses in `expressions.json["poses"]`
  - `tilt_left_small`
  - `tilt_right_small`
  - `nod_up_small`
  - `nod_down_small`

### 3. Parallel Generation

Uses OpenAI `gpt-image-1` to:
1. Load source expression image as reference
2. Generate same expression with new head pose
3. Preserve facial features, hairstyle, clothing
4. Save as `<expr_id>__<pose>.png`

All jobs run in parallel using `ThreadPoolExecutor`.

### 4. Prompt Strategy

```python
prompt = f"""
Watercolor portrait of the same young boy on a transparent background.
Use the reference image for his identity, hairstyle, clothing, earrings,
framing, and facial expression.

Head pose:
  - Change the head pose to: {pose_desc}.

Facial expression:
  - Keep the facial expression identical to the reference image.
  - The expression should match this description:
    {expr_desc}

Only adjust the head's orientation/tilt. Do NOT change the mouth, eyes,
eyebrows shape (other than small perspective adjustments), hairstyle,
clothing, earrings, or background.
"""
```

---

## Example Usage

### Standard workflow

```bash
export OPENAI_API_KEY=sk-...

# Step 1: Generate extreme expressions at 'center' pose
python generate_extreme_expressions.py \
  --config expressions.json \
  --base-image watercolor_boy_greenscreen.png \
  --output-dir frames/endpoints \
  --pose center \
  --max-workers 6

# Step 2: Generate all head tilts for each expression
python generate_head_tilts.py \
  --config expressions.json \
  --endpoints-dir frames/endpoints \
  --base-neutral watercolor_boy_greenscreen.png \
  --source-pose center \
  --max-workers 6
```

Output:
```
[i] Generating 20 head-tilted endpoints with 6 workers...
[✓] neutral @ tilt_left_small -> neutral__tilt_left_small.png
[✓] neutral @ tilt_right_small -> neutral__tilt_right_small.png
[✓] neutral @ nod_up_small -> neutral__nod_up_small.png
[✓] neutral @ nod_down_small -> neutral__nod_down_small.png
[✓] speaking_ah @ tilt_left_small -> speaking_ah__tilt_left_small.png
...
[i] Done. Success: 20, Failed: 0
```

### Regenerate specific poses

```bash
python generate_head_tilts.py \
  --config expressions.json \
  --overwrite
```

### Custom source pose

If you generated extremes at `tilt_left_small` instead of `center`:

```bash
python generate_head_tilts.py \
  --config expressions.json \
  --source-pose tilt_left_small \
  --max-workers 6
```

---

## Output Structure

After running, `frames/endpoints/` contains a **full expression × pose matrix**:

| Expression | center | tilt_left | tilt_right | nod_up | nod_down |
|------------|--------|-----------|------------|--------|----------|
| neutral | ✓ | ✓ | ✓ | ✓ | ✓ |
| speaking_ah | ✓ | ✓ | ✓ | ✓ | ✓ |
| speaking_ee | ✓ | ✓ | ✓ | ✓ | ✓ |
| speaking_uw | ✓ | ✓ | ✓ | ✓ | ✓ |
| smile_big | ✓ | ✓ | ✓ | ✓ | ✓ |

Each cell is a PNG file: `<expr_id>__<pose>.png`

---

## Integration with Sequence Generation

Once you have the full expression × pose matrix, `generate_all_sequences.py` can create tween sequences for **every combination**:

```bash
python generate_all_sequences.py \
  --config expressions.json \
  --endpoints-dir frames/endpoints \
  --sequences-dir frames/sequences \
  --max-depth 2 \
  --max-workers 6
```

This generates sequences like:
- `neutral_to_speaking_ah__center`
- `neutral_to_speaking_ah__tilt_left_small`
- `neutral_to_speaking_ah__tilt_right_small`
- `neutral_to_speaking_ah__nod_up_small`
- `neutral_to_speaking_ah__nod_down_small`
- ... (and all other expression pairs × all poses)

---

## Cost Estimation

**Per expression:**
- 1 source pose (already exists)
- 4 target poses (generated)
- = 4 OpenAI API calls

**For 5 expressions (including neutral):**
- 5 × 4 = **20 API calls**
- At ~$0.10 per image = **~$2.00**

**For 10 expressions:**
- 10 × 4 = **40 API calls**
- = **~$4.00**

---

## Tips

### Start with center pose

`center` is the most natural source pose because:
- Easiest to generate extreme expressions for
- Simplest geometry for tilting/rotating
- Best reference for identity consistency

### Check quality early

Generate 1-2 expressions first:

```bash
# Just generate tilts for 'neutral' and 'speaking_ah'
# (manually delete other expression files from endpoints temporarily)
python generate_head_tilts.py \
  --config expressions.json \
  --max-workers 2
```

Preview results before running full batch.

### Regenerate bad tilts

If one tilt looks wrong:

```bash
# Delete the bad file
rm frames/endpoints/speaking_ah__tilt_left_small.png

# Rerun (skips existing files)
python generate_head_tilts.py \
  --config expressions.json
```

---

## Next Steps

1. **Generate extreme expressions at center pose:**
   ```bash
   python generate_extreme_expressions.py --pose center
   ```

2. **Generate all head tilts:**
   ```bash
   python generate_head_tilts.py
   ```

3. **Generate tween sequences for all combinations:**
   ```bash
   python generate_all_sequences.py
   ```

4. **Preview and refine in UI:**
   ```bash
   cd watercolor-rig && npm run dev
   ```

---

## Troubleshooting

### "Missing source pose for expr 'X'"

The expression doesn't exist at the source pose. Generate it first:

```bash
python generate_extreme_expressions.py \
  --config expressions.json \
  --pose center
```

### "No 'poses' array found in expressions.json"

Add a `poses` array to your config:

```json
{
  "expressions": { ... },
  "poses": [
    "center",
    "tilt_left_small",
    "tilt_right_small",
    "nod_up_small",
    "nod_down_small"
  ]
}
```

### Tilts look distorted

Try adjusting the prompt or using a higher quality source image. The model works best with:
- Clear facial features
- Good lighting
- Consistent framing
- 1024×1536 or 1024×1024 resolution

