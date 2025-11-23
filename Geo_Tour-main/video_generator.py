"""
Video generation module - Replicate Stability-only implementation
Generates clips per scene using:
- Text-to-Image: stability-ai/sdxl
- Image-to-Video: stability-ai/stable-video-diffusion
"""
import replicate
import requests
import time
from pathlib import Path
from config import (
    REPLICATE_API_KEY,
    STABILITY_MODEL,
    STORYBOARD_MODEL,
    TEMP_DIR,
)


def safe_print(*args, **kwargs):
    """Safely print messages, handling closed file errors in Streamlit"""
    try:
        print(*args, **kwargs)
    except (IOError, OSError, ValueError):
        # Silently fail if stdout is closed (Streamlit context)
        pass


class VideoGenerator:
    def __init__(self, api_key=None, svd_model=None, sdxl_model=None, max_retries=3, retry_delay=5):
        self.api_key = api_key or REPLICATE_API_KEY
        self.svd_model = svd_model or STABILITY_MODEL
        self.sdxl_model = sdxl_model or STORYBOARD_MODEL
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def generate_clips(self, scene_plan, output_dir=None, storyboard_images=None):
        """
        Generate video clips for all scenes
        
        Args:
            scene_plan (dict): Scene plan with visual descriptions
            output_dir (Path): Directory to save clips
            storyboard_images (list): Optional list of storyboard image paths (one per scene)
            
        Returns:
            list: Paths to generated video clips
        """
        output_dir = output_dir or TEMP_DIR
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        safe_print(f"🎥 Generating {len(scene_plan['scenes'])} video clips...")
        
        clip_paths = []
        
        for idx, scene in enumerate(scene_plan['scenes']):
            safe_print(f"  Scene {scene['scene_number']}: {scene['visual_description'][:50]}...")
            
            # Get corresponding storyboard image if available
            storyboard_image = None
            if storyboard_images and idx < len(storyboard_images):
                storyboard_image = storyboard_images[idx]
            
            clip_path = self._generate_clip(
                description=scene['visual_description'],
                duration=scene['duration'],
                scene_number=scene['scene_number'],
                output_dir=output_dir,
                storyboard_image=storyboard_image
            )
            
            clip_paths.append(clip_path)
        
        safe_print(f"✅ Generated {len(clip_paths)} clips")
        return clip_paths
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Execute a function with exponential backoff retry logic
        
        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                error_msg = str(e)
                
                # Determine if error is retryable
                retryable_errors = [
                    "Server disconnected",
                    "Connection",
                    "Timeout",
                    "timeout",
                    "503",
                    "502",
                    "500",
                    "429",  # Rate limit
                    "ConnectionError",
                    "ReadTimeout",
                ]
                
                is_retryable = any(err in error_msg for err in retryable_errors)
                
                if not is_retryable:
                    safe_print(f"    ❌ Non-retryable error: {error_msg}")
                    raise
                
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    safe_print(f"    ⚠️  Attempt {attempt + 1}/{self.max_retries} failed: {error_msg}")
                    safe_print(f"    ⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    safe_print(f"    ❌ All {self.max_retries} attempts failed")
        
        raise last_exception
    
    def _generate_clip(self, description, duration, scene_number, output_dir, storyboard_image=None):
        """Generate a single clip using Stability models via Replicate with retry logic"""
        return self._retry_with_backoff(
            self._generate_clip_internal,
            description, duration, scene_number, output_dir, storyboard_image
        )
    
    def _generate_clip_internal(self, description, duration, scene_number, output_dir, storyboard_image=None):
        """Internal method to generate a single clip using Stability models via Replicate"""
        replicate_key = self.api_key or REPLICATE_API_KEY
        if not replicate_key:
            raise RuntimeError("Replicate API key is required")

        client = replicate.Client(api_token=replicate_key)
        clip_path = output_dir / f"scene_{scene_number}.mp4"

        # Ensure we have an image: use provided storyboard or create one from text
        image_path = None
        if storyboard_image and Path(storyboard_image).exists():
            image_path = storyboard_image
        if not image_path:
            image_path = output_dir / f"t2i_scene_{scene_number}.png"
            if "google/imagen-3" in self.sdxl_model:
                safe_print("    🎨 Generating image via Google Imagen 3...")
                output_img = client.run(
                    self.sdxl_model,
                    input={
                        "prompt": description,
                        "aspect_ratio": "16:9",
                        "output_format": "png",
                        "safety_filter_level": "block_only_high"
                    },
                    use_file_output=False
                )
            else:
                safe_print("    🎨 Generating image via Stability SDXL...")
                output_img = client.run(
                    self.sdxl_model,
                    input={
                        "prompt": description,
                        "width": 1024,
                        "height": 576,
                        "num_outputs": 1
                    },
                    use_file_output=False
                )
            # Save output image (supports URL or base64 output formats)
            self._save_image_output(output_img, image_path)

        # Image-to-video via selected Replicate model
        if "bytedance/seedance" in self.svd_model:
            safe_print("    🎬 Generating video via ByteDance Seedance...")
            output_vid = client.run(
                self.svd_model,
                input={
                    "image": open(image_path, "rb"),
                    "prompt": description,
                    "duration": max(2, min(int(duration), 12)),
                    "resolution": "1080p",
                    "aspect_ratio": "16:9",
                    "fps": 24,
                    "camera_fixed": False
                },
                use_file_output=False
            )
        else:
            # Stable Video Diffusion schema
            desired_frames = max(14, min(duration * 6, 25))
            video_length = "25_frames_with_svd_xt" if desired_frames >= 25 else "14_frames_with_svd"
            fps = 6
            safe_print("    🎬 Generating video from image via Stable Video Diffusion...")
            output_vid = client.run(
                self.svd_model,
                input={
                    "input_image": open(image_path, "rb"),
                    "video_length": video_length,
                    "frames_per_second": fps,
                    "sizing_strategy": "maintain_aspect_ratio",
                    "motion_bucket_id": 127,
                    "cond_aug": 0.02,
                    "decoding_t": 14
                },
                use_file_output=False
            )

        video_url = self._first_url(output_vid)
        if not video_url:
            raise RuntimeError("No video URL returned from image-to-video model")
        self._download_video(video_url, clip_path)
        safe_print(f"    ✅ Video saved: {clip_path.name}")
        return str(clip_path)
    
    def _download_video(self, url, output_path):
        """Download video with retry logic"""
        for attempt in range(self.max_retries):
            try:
                resp = requests.get(url, timeout=300, stream=True)
                resp.raise_for_status()
                with open(output_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    safe_print(f"    ⚠️  Download attempt {attempt + 1}/{self.max_retries} failed: {str(e)}")
                    safe_print(f"    ⏳ Retrying download in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    safe_print(f"    ❌ Failed to download video after {self.max_retries} attempts")
                    raise RuntimeError(f"Failed to download video from {url}: {str(e)}")
    
    def _download_image(self, url, output_path):
        import io
        from PIL import Image
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        try:
            img = Image.open(io.BytesIO(resp.content))
            img.load()
        except Exception:
            raise RuntimeError(f"Invalid image content at URL: {url}")
        try:
            if img.mode in ("P", "RGBA", "LA"):
                img = img.convert("RGB")
            img.save(output_path, format="PNG")
        except Exception:
            raise RuntimeError(f"Failed to save image to: {output_path}")

    def _first_url(self, data):
        if isinstance(data, list):
            if not data:
                return None
            first = data[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                for k in ("url", "image", "video"):
                    if k in first:
                        return first[k]
                return None
        if isinstance(data, dict):
            for k in ("output", "url", "image", "video"):
                v = data.get(k)
                if isinstance(v, str):
                    return v
                if isinstance(v, list) and v:
                    if isinstance(v[0], str):
                        return v[0]
                    if isinstance(v[0], dict):
                        return v[0].get("url")
        if isinstance(data, str):
            return data
        return None

    def _save_image_output(self, output, output_path):
        import io, base64
        from PIL import Image
        try:
            from replicate.helpers import FileOutput
        except Exception:
            FileOutput = None
        val = None
        if FileOutput and isinstance(output, FileOutput):
            data = output.read()
            img = Image.open(io.BytesIO(data))
            img = img.convert("RGB")
            img.save(output_path, format="PNG")
            return
        if isinstance(output, str):
            val = output
        elif isinstance(output, list):
            if output:
                item = output[0]
                if FileOutput and isinstance(item, FileOutput):
                    data = item.read()
                    img = Image.open(io.BytesIO(data))
                    img = img.convert("RGB")
                    img.save(output_path, format="PNG")
                    return
                if isinstance(item, str):
                    val = item
                elif isinstance(item, dict):
                    for k in ("url", "image", "image_url", "base64", "image_base64", "data", "content"):
                        if k in item:
                            val = item[k]
                            break
        elif isinstance(output, dict):
            if "images" in output and isinstance(output["images"], list) and output["images"]:
                first = output["images"][0]
                if isinstance(first, dict):
                    val = first.get("content") or first.get("url")
            if not val:
                for k in ("output", "url", "image", "image_url", "base64", "image_base64", "images", "data", "content"):
                    v = output.get(k)
                    if isinstance(v, str):
                        val = v
                        break
                    if isinstance(v, list) and v:
                        if isinstance(v[0], str):
                            val = v[0]
                            break
                        if isinstance(v[0], dict):
                            for kk in ("url", "image", "image_url", "base64", "image_base64", "data", "content"):
                                if kk in v[0]:
                                    val = v[0][kk]
                                    break
                            if val:
                                break
        if not val:
            raise RuntimeError("No image output received")
        if isinstance(val, str) and val.startswith("http"):
            self._download_image(val, output_path)
            return
        try:
            if isinstance(val, str) and val.startswith("data:"):
                b64 = val.split(",", 1)[1]
            elif isinstance(val, str):
                b64 = val
            else:
                raise RuntimeError("Unsupported image output format")
            data = base64.b64decode(b64, validate=False)
            img = Image.open(io.BytesIO(data))
            img.load()
            if img.mode in ("P", "RGBA", "LA"):
                img = img.convert("RGB")
            img.save(output_path, format="PNG")
        except Exception:
            raise RuntimeError("Failed to decode image output")

    # 16:9 aspect is requested at model level (Imagen-3: aspect_ratio, SDXL: width/height)


if __name__ == "__main__":
    generator = VideoGenerator()
    test_plan = {
        "scenes": [
            {
                "scene_number": 1,
                "visual_description": "Sunlight rays passing through water droplets",
                "duration": 6
            }
        ]
    }
    clips = generator.generate_clips(test_plan)
    print(f"Generated clips: {clips}")

