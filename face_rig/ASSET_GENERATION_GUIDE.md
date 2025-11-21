# Asset Generation Guide

Quick reference for generating all character rig assets using the master pipeline script.

## Prerequisites

1. **OpenAI API Key** (required):
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

2. **Base Image**: Neutral character image on greenscreen (1024x1536)
   - Example: `watercolor_boy_greenscreen.png`

3. **Config File**: `expressions.json` with expression definitions

## Quick Start

### Generate Everything

```bash
python generate_all_assets.py \
    --config expressions.json \
    --base-image watercolor_boy_greenscreen.png \
    --max-workers 4
```

This runs all 4 stages:
1. ✨ **Extreme Expressions** - Generate endpoint images for all expressions × all poses
2. 🎭 **Head Poses** - Generate head tilt/nod variants
3. 🔄 **Expression Transitions** - Generate smooth transitions between expressions
4. 🔀 **Pose Transitions** - Generate smooth transitions between poses

**Estimated time**: 2-4 hours depending on workers and API speed

## Stage-by-Stage

### Stage 1 Only: Extreme Expressions
```bash
python generate_all_assets.py \
    --config expressions.json \
    --base-image watercolor_boy_greenscreen.png \
    --skip-tilts \
    --skip-sequences \
    --skip-neutral-pose
```

### Stage 2 Only: Head Poses
```bash
python generate_all_assets.py \
    --config expressions.json \
    --base-image watercolor_boy_greenscreen.png \
    --skip-extremes \
    --skip-sequences \
    --skip-neutral-pose
```

### Stages 3+4 Only: All Transitions
```bash
python generate_all_assets.py \
    --config expressions.json \
    --base-image watercolor_boy_greenscreen.png \
    --skip-extremes \
    --skip-tilts \
    --overwrite
```

## Options

### Performance
- `--max-workers N` - Parallel workers (default: 4, higher = faster but more API load)
- `--max-depth N` - Intermediate frames for transitions (default: 3, lower = faster)

### Control
- `--overwrite` - Regenerate existing files
- `--dry-run` - Show what would be executed without running
- `--skip-extremes` - Skip stage 1
- `--skip-tilts` - Skip stage 2
- `--skip-sequences` - Skip stage 3
- `--skip-neutral-pose` - Skip stage 4

### Directories
- `--endpoints-dir PATH` - Output for expression endpoints (default: `frames/endpoints`)
- `--sequences-dir PATH` - Output for transitions (default: `frames/sequences`)

### Image Settings
- `--size WxH` - Image dimensions (default: `1024x1536`)

## Output Structure

```
frames/
├── endpoints/          # Stage 1+2 output
│   ├── neutral__center.png
│   ├── neutral__tilt_left_small.png
│   ├── happy_soft__center.png
│   ├── speaking_ah__nod_up_small.png
│   └── ... (~50 files)
│
└── sequences/          # Stage 3+4 output
    ├── neutral_to_happy_soft__center/
    │   ├── manifest.json
    │   ├── 000.png
    │   ├── 025.png
    │   ├── 050.png
    │   ├── 075.png
    │   └── 100.png
    ├── speaking_ah_to_speaking_ee__center/
    └── ... (~200+ directories)
```

## Troubleshooting

### "Missing prerequisites: OPENAI_API_KEY"
```bash
export OPENAI_API_KEY="sk-..."
```

### "Base image not found"
Ensure the path is correct:
```bash
ls -la watercolor_boy_greenscreen.png
```

### API Rate Limits
Reduce parallel workers:
```bash
--max-workers 2
```

### Out of Memory
Reduce workers or max-depth:
```bash
--max-workers 2 --max-depth 2
```

### Resume After Failure
The pipeline stops at the failed stage. Fix the issue and re-run:
```bash
# Skip completed stages
python generate_all_assets.py \
    --skip-extremes \
    --skip-tilts \
    ...
```

## Cost Estimation

Each OpenAI image generation costs approximately $0.04-0.08.

**Rough cost breakdown:**
- Stage 1 (Extremes): ~50 images × $0.06 = **~$3**
- Stage 2 (Tilts): Already done by Stage 1
- Stage 3 (Sequences): ~200 transitions × 3 frames × $0.06 = **~$36**
- Stage 4 (Poses): ~20 transitions × 3 frames × $0.06 = **~$4**

**Total**: **~$43** for complete rig generation

## Examples

### Full Generation (First Time)
```bash
export OPENAI_API_KEY="sk-..."

python generate_all_assets.py \
    --config expressions.json \
    --base-image watercolor_boy_greenscreen.png \
    --max-workers 4
```

### Regenerate Only Transitions
```bash
python generate_all_assets.py \
    --config expressions.json \
    --base-image watercolor_boy_greenscreen.png \
    --skip-extremes \
    --skip-tilts \
    --overwrite \
    --max-workers 6
```

### Test Run (No API Calls)
```bash
python generate_all_assets.py \
    --config expressions.json \
    --base-image watercolor_boy_greenscreen.png \
    --dry-run
```

### Minimal Quick Test (1 expression, 1 pose)
Edit `expressions.json` to include only `neutral` and `happy_soft`, then:
```bash
python generate_all_assets.py \
    --config expressions.json \
    --base-image watercolor_boy_greenscreen.png \
    --max-workers 2 \
    --max-depth 1
```

## Tips

1. **Start with a test run**: Use `--dry-run` to verify setup
2. **Run overnight**: Full generation takes hours
3. **Monitor progress**: Watch terminal output for errors
4. **Save incrementally**: Don't use `--overwrite` unless regenerating
5. **Backup**: Copy `frames/` directory before major changes
6. **Resume capability**: Pipeline can restart from any stage

## Next Steps

After generation completes:

1. **Verify output**:
   ```bash
   ls -R frames/endpoints/ | head -20
   ls -R frames/sequences/ | head -20
   ```

2. **Start animation server**:
   ```bash
   python server.py
   ```

3. **Open Timeline Director**:
   ```bash
   cd watercolor-rig && npm run dev
   ```

4. **Create your first animation**! 🎬

