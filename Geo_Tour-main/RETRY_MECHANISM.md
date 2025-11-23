# Retry Mechanism Documentation

## Overview

The video generation pipeline now includes a robust retry mechanism with exponential backoff to handle transient failures from external API services (Replicate, ElevenLabs, face_rig server, etc.).

## Problem Solved

External API calls can fail due to:
- Network connectivity issues
- Server timeouts
- Rate limiting (429 errors)
- Temporary service unavailability (503, 502, 500 errors)
- Connection resets ("Server disconnected without sending a response")

Without retry logic, these transient failures would cause the entire pipeline to fail, wasting time and API credits already spent on previous steps.

## How It Works

### Exponential Backoff Strategy

When a retryable error occurs:
1. **Attempt 1 fails** → Wait 5 seconds → Retry
2. **Attempt 2 fails** → Wait 10 seconds → Retry  
3. **Attempt 3 fails** → Give up, raise exception

This gives temporary issues time to resolve while avoiding aggressive retries.

### Retryable vs Non-Retryable Errors

**Retryable errors** (will retry):
- Server disconnected
- Connection errors
- Timeouts
- HTTP 503 (Service Unavailable)
- HTTP 502 (Bad Gateway)
- HTTP 500 (Internal Server Error)
- HTTP 429 (Rate Limit)

**Non-retryable errors** (fail immediately):
- HTTP 401 (Unauthorized - bad API key)
- HTTP 404 (Not Found)
- Invalid input/parameters
- Missing files
- Any other error not matching retryable patterns

## Components with Retry Logic

### 1. Video Generator (`video_generator.py`)

**What's protected:**
- Text-to-image generation (SDXL, Imagen-3)
- Image-to-video generation (Seedance, Stable Video Diffusion)
- Video file downloads

**Configuration:**
```python
generator = VideoGenerator(
    max_retries=3,      # Default: 3 attempts
    retry_delay=5       # Default: 5 seconds initial delay
)
```

**Example usage:**
```python
# Automatically retries on transient failures
clips = generator.generate_clips(scene_plan)
```

### 2. Face Rig Integrator (`face_rig_integrator.py`)

**What's protected:**
- TTS generation (ElevenLabs API)
- MFA alignment (face_rig server)
- Emotion generation (OpenAI API via face_rig)
- Video export (face_rig server)

**Configuration:**
```python
integrator = FaceRigIntegrator(
    max_retries=3,      # Default: 3 attempts
    retry_delay=5       # Default: 5 seconds initial delay
)
```

**Example usage:**
```python
# All API calls automatically retry on failure
result = integrator.generate_scene_video(narration, scene_number)
```

### 3. Storyboard Generator (`storyboard_generator.py`)

**What's protected:**
- Storyboard image generation (SDXL, Imagen-3)

**Configuration:**
```python
generator = StoryboardGenerator(
    max_retries=3,      # Default: 3 attempts
    retry_delay=5       # Default: 5 seconds initial delay
)
```

## Configuration

### Global Configuration

Set retry parameters when initializing the pipeline:

```python
from pipeline import VideoPipeline

pipeline = VideoPipeline(
    # ... other settings ...
)

# The pipeline components use default retry settings:
# - max_retries: 3
# - retry_delay: 5 seconds
```

### Per-Component Configuration

For fine-grained control, configure components individually:

```python
from video_generator import VideoGenerator
from face_rig_integrator import FaceRigIntegrator
from storyboard_generator import StoryboardGenerator

# More aggressive retry for video generation
video_gen = VideoGenerator(
    max_retries=5,      # Try 5 times
    retry_delay=10      # Wait longer between attempts
)

# Standard retry for face_rig
face_rig = FaceRigIntegrator(
    max_retries=3,
    retry_delay=5
)

# Quick fail for storyboard (less critical)
storyboard = StoryboardGenerator(
    max_retries=2,
    retry_delay=3
)
```

## Output Messages

### Successful Retry

```
Scene 4: Detailed view of a sunbeam tr...
  🎨 Generating image via Google Imagen 3...
  ⚠️  Attempt 1/3 failed: Server disconnected without sending a response
  ⏳ Retrying in 5 seconds...
  🎨 Generating image via Google Imagen 3...
  ✅ Video saved: scene_4.mp4
```

### Failed After Retries

```
Scene 4: Detailed view of a sunbeam tr...
  🎨 Generating image via Google Imagen 3...
  ⚠️  Attempt 1/3 failed: Server disconnected
  ⏳ Retrying in 5 seconds...
  ⚠️  Attempt 2/3 failed: Connection timeout
  ⏳ Retrying in 10 seconds...
  ⚠️  Attempt 3/3 failed: Connection reset
  ❌ All 3 attempts failed
Pipeline failed: Failed to generate image after 3 attempts
```

### Non-Retryable Error

```
Scene 4: Detailed view of a sunbeam tr...
  🎨 Generating image via Google Imagen 3...
  ❌ Non-retryable error: 401 Unauthorized - Invalid API key
Pipeline failed: Invalid API key
```

## Best Practices

### 1. Use Default Settings

The default settings (3 retries, 5 second delay) work well for most cases:

```python
# This is sufficient for most use cases
pipeline = VideoPipeline(use_face_rig=True)
```

### 2. Increase Retries for Production

For production environments where reliability is critical:

```python
video_gen = VideoGenerator(
    max_retries=5,
    retry_delay=10
)
```

### 3. Decrease Retries for Development

For faster failure during testing:

```python
video_gen = VideoGenerator(
    max_retries=1,  # Fail fast
    retry_delay=2
)
```

### 4. Monitor Retry Patterns

If you see frequent retries:
- Check your network connection
- Verify API service status
- Consider rate limiting issues
- Check API key validity

## Performance Impact

### Timing

With default settings (3 retries, 5s delay):
- **Successful first attempt**: No delay
- **Success on retry 2**: ~5 seconds added
- **Success on retry 3**: ~15 seconds added (5s + 10s)
- **All retries fail**: ~15 seconds lost before failure

### Cost

Retries do NOT increase API costs because:
- Failed requests are not billed by most APIs
- Only successful completions count toward quota
- The alternative (pipeline failure) wastes previous steps

## Troubleshooting

### Too Many Retries

**Symptom**: Pipeline takes very long, many retry messages

**Causes**:
- Network issues
- API service degradation
- Rate limiting

**Solutions**:
1. Check internet connection
2. Check API service status pages
3. Reduce request frequency
4. Consider using different models/providers

### Not Retrying When Expected

**Symptom**: Pipeline fails immediately on transient error

**Cause**: Error classified as non-retryable

**Solution**: 
Check the error message. If it should be retryable, update the `retryable_errors` list in the component's `_retry_with_backoff` method.

### Excessive Wait Times

**Symptom**: Waiting too long between retries

**Solution**:
Reduce `retry_delay`:
```python
VideoGenerator(retry_delay=2)  # 2, 4, 8 seconds instead of 5, 10, 20
```

## Example Scenarios

### Scenario 1: Network Hiccup

```
[4/7] Video Clip Generation
Scene 4: Detailed view...
  🎨 Generating image via Google Imagen 3...
  ⚠️  Attempt 1/3 failed: Connection timeout
  ⏳ Retrying in 5 seconds...
  ✅ Video saved: scene_4.mp4
```

**Result**: Pipeline continues successfully, adding only 5 seconds

### Scenario 2: Rate Limiting

```
[3.5/7] Face_rig Character Animation
  🎤 Generating audio with ElevenLabs...
  ⚠️  Attempt 1/3 failed: 429 Rate limit exceeded
  ⏳ Retrying in 5 seconds...
  ✅ Audio generated: 5.75s
```

**Result**: Rate limit respected, request succeeds on retry

### Scenario 3: Invalid API Key

```
[4/7] Video Clip Generation
Scene 1: Wide view...
  🎨 Generating image via Google Imagen 3...
  ❌ Non-retryable error: 401 Unauthorized
Pipeline failed: Invalid API key
```

**Result**: Fails immediately (no wasted retries on unrecoverable error)

## Code Example

Here's how retry logic is implemented:

```python
def _retry_with_backoff(self, func, *args, **kwargs):
    """Execute a function with exponential backoff retry logic"""
    last_exception = None
    
    for attempt in range(self.max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            error_msg = str(e)
            
            # Check if error is retryable
            retryable_errors = [
                "Server disconnected",
                "Connection",
                "Timeout",
                "503", "502", "500", "429"
            ]
            
            is_retryable = any(err in error_msg for err in retryable_errors)
            
            if not is_retryable:
                raise  # Fail immediately
            
            if attempt < self.max_retries - 1:
                wait_time = self.retry_delay * (2 ** attempt)
                print(f"⚠️  Attempt {attempt + 1}/{self.max_retries} failed")
                print(f"⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
    
    raise last_exception
```

## Advanced Configuration

### Custom Retry Logic

To add custom retryable error patterns, modify the `retryable_errors` list:

```python
# In video_generator.py, face_rig_integrator.py, or storyboard_generator.py

retryable_errors = [
    "Server disconnected",
    "Connection",
    "Timeout",
    "503", "502", "500", "429",
    # Add your custom patterns:
    "Your custom error pattern",
    "Another retryable error"
]
```

### Conditional Retries

For different retry strategies based on error type:

```python
def _retry_with_backoff(self, func, *args, **kwargs):
    for attempt in range(self.max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = str(e)
            
            # Different handling for different errors
            if "429" in error_msg:
                # Rate limit: wait longer
                wait_time = 30
            elif "503" in error_msg:
                # Service unavailable: exponential backoff
                wait_time = self.retry_delay * (2 ** attempt)
            else:
                # Other errors: standard backoff
                wait_time = self.retry_delay * (2 ** attempt)
            
            time.sleep(wait_time)
    
    raise last_exception
```

## Summary

✅ **Automatic retry** on transient failures  
✅ **Exponential backoff** to avoid aggressive retries  
✅ **Smart error detection** (retryable vs non-retryable)  
✅ **Configurable** retry count and delay  
✅ **Clear logging** of retry attempts  
✅ **Production-ready** default settings  

The retry mechanism makes your pipeline more robust and reliable without any code changes required!

