"""
Video generation module - Replicate Stability-only implementation
Generates clips per scene using:
- Text-to-Image: stability-ai/sdxl
- Image-to-Video: stability-ai/stable-video-diffusion
- 3D Visualization: Three.js animated renders
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

# Import Three.js video generator
try:
    from threejs_video_generator import ThreeJSVideoGenerator
    THREEJS_AVAILABLE = True
except ImportError:
    THREEJS_AVAILABLE = False
    safe_print("⚠️  Three.js generator not available (missing dependencies)")


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

        # Initialize Three.js generator if available
        self.threejs_generator = None
        if THREEJS_AVAILABLE:
            try:
                self.threejs_generator = ThreeJSVideoGenerator(
                    width=1920,
                    height=1080,
                    fps=24
                )
                safe_print("✅ Three.js video generator initialized")
            except Exception as e:
                safe_print(f"⚠️  Could not initialize Three.js generator: {e}")
    
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
            scene_type = scene.get('scene_type', 'video')
            type_icon = "📊" if scene_type == "diagram" else "🎥"
            safe_print(f"  {type_icon} Scene {scene['scene_number']} ({scene_type}): {scene['visual_description'][:50]}...")

            # Get corresponding storyboard image if available
            storyboard_image = None
            if storyboard_images and idx < len(storyboard_images):
                storyboard_image = storyboard_images[idx]

            clip_path = self._generate_clip(
                description=scene['visual_description'],
                duration=scene['duration'],
                scene_number=scene['scene_number'],
                output_dir=output_dir,
                storyboard_image=storyboard_image,
                scene_type=scene_type
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
    
    def _generate_clip(self, description, duration, scene_number, output_dir, storyboard_image=None, scene_type="video"):
        """Generate a single clip with retry logic"""
        return self._retry_with_backoff(
            self._generate_clip_internal,
            description, duration, scene_number, output_dir, storyboard_image, scene_type
        )
    
    def _generate_clip_internal(self, description, duration, scene_number, output_dir, storyboard_image=None, scene_type="video"):
        """
        Internal method to generate a single clip

        Args:
            description: Visual description
            duration: Scene duration in seconds
            scene_number: Scene number
            output_dir: Output directory
            storyboard_image: Optional storyboard image path
            scene_type: "video" or "diagram"

        Returns:
            Path to generated video clip
        """
        # Route to appropriate generator based on scene type
        if scene_type == "diagram":
            return self._generate_matplotlib_diagram(description, duration, scene_number, output_dir)
        else:
            return self._generate_replicate_video(description, duration, scene_number, output_dir, storyboard_image)

    def _generate_matplotlib_diagram(self, description, duration, scene_number, output_dir, max_retries=3):
        """Generate a labeled matplotlib diagram with simple animation using gemini-3-pro-preview"""
        import os
        import google.generativeai as genai

        # Get Gemini API key
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_key:
            raise RuntimeError("Gemini API key required. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable")

        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-3-pro-preview")

        last_error = None

        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    safe_print(f"    📊 Generating matplotlib code with gemini-3-pro-preview...")
                    error_context = ""
                else:
                    safe_print(f"    🔄 Retry {attempt}/{max_retries-1}: Regenerating code after error...")
                    error_context = f"\n\nIMPORTANT: The previous code failed with this error:\n{last_error}\n\nPlease fix this error and generate valid matplotlib code that will run without errors."

                return self._generate_matplotlib_diagram_attempt(description, duration, scene_number, output_dir, error_context)

            except Exception as e:
                last_error = str(e)
                safe_print(f"    ⚠️  Attempt {attempt + 1} failed: {last_error}")

                if attempt == max_retries - 1:
                    raise RuntimeError(f"Failed to generate valid matplotlib code after {max_retries} attempts. Last error: {last_error}")

        raise RuntimeError("Matplotlib diagram generation failed")

    def _generate_matplotlib_diagram_attempt(self, description, duration, scene_number, output_dir, error_context=""):
        """Single attempt to generate matplotlib diagram"""
        import os
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-3-pro-preview")

        # Create prompt for matplotlib code generation
        prompt = f"""Generate Python matplotlib code to create a labeled diagram with a simple animation based on this description:

{description}

Requirements:
1. Create a labeled diagram (use plt.text() or plt.annotate() for labels)
2. Add a simple animation that lasts approximately {duration} seconds at 24 fps
3. Use matplotlib.animation.FuncAnimation for the animation
4. The animation should be smooth and professional (e.g., highlighting layers, zooming, fading elements)
5. Save the animation as an MP4 file at 1920x1080 resolution, 24 fps
6. Use 'Agg' backend for non-interactive rendering
7. The code should be complete and runnable as-is
8. ONLY use valid matplotlib properties - do NOT use properties that don't exist like 'letter_spacing'

Output ONLY the Python code, no explanations. The code should:
- Import all necessary libraries (matplotlib, numpy, etc.)
- Set figure size to (19.2, 10.8) for 1920x1080
- Use matplotlib.use('Agg') at the start
- Save the animation using writer = FFMpegWriter(fps=24, bitrate=5000)
- Include the save path as a parameter that can be passed in
- Use ONLY valid matplotlib text properties: fontsize, fontweight, color, alpha, ha, va, fontfamily, fontstyle
- DO NOT use invalid properties like letter_spacing, text_spacing, or any other non-existent properties{error_context}

Example structure:
```python
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.animation import FFMpegWriter
import numpy as np

def create_diagram_animation(output_path, duration={duration}):
    fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=100)

    # Your diagram code here

    def animate(frame):
        # Animation logic here
        pass

    fps = 24
    frames = int(duration * fps)
    anim = animation.FuncAnimation(fig, animate, frames=frames, interval=1000/fps)

    writer = FFMpegWriter(fps=fps, bitrate=5000)
    anim.save(output_path, writer=writer)
    plt.close()

# This will be called externally
# create_diagram_animation('output.mp4', {duration})
```

Generate the complete, runnable code now:"""

        try:
            response = model.generate_content(prompt)

            # Extract code from response
            code = response.text.strip()

            # Remove markdown code blocks if present
            if code.startswith("```python"):
                code = code.split("```python")[1]
                code = code.split("```")[0]
            elif code.startswith("```"):
                code = code.split("```")[1]
                code = code.split("```")[0]

            code = code.strip()

            safe_print(f"    ✅ Generated matplotlib code ({len(code)} chars)")

            # Save generated code for debugging
            code_path = Path(output_dir) / f"scene_{scene_number}_matplotlib.py"
            with open(code_path, 'w') as f:
                f.write(code)
            safe_print(f"    💾 Saved code to: {code_path.name}")

            safe_print(f"    🎬 Executing matplotlib code to create animation...")

            # Create output path
            video_path = Path(output_dir) / f"scene_{scene_number}.mp4"

            # Execute the code with better error handling
            exec_globals = {}
            try:
                exec(code, exec_globals)
            except Exception as e:
                raise RuntimeError(f"Code execution failed: {e}")

            # Call the function
            if 'create_diagram_animation' not in exec_globals:
                raise RuntimeError("Generated code does not contain 'create_diagram_animation' function")

            try:
                exec_globals['create_diagram_animation'](str(video_path), duration)
            except Exception as e:
                raise RuntimeError(f"Animation creation failed: {e}")

            # Verify the video was created
            if not video_path.exists():
                raise RuntimeError(f"Video file was not created at: {video_path}")

            if video_path.stat().st_size < 1000:
                raise RuntimeError(f"Video file is too small ({video_path.stat().st_size} bytes), likely corrupted")

            safe_print(f"    ✅ Matplotlib animation saved: {video_path.name}")
            return str(video_path)

        except Exception as e:
            # Re-raise to trigger retry
            raise

    def _generate_3d_visualization(self, description, duration, scene_number, output_dir):
        """Generate a 3D visualization using gemini-3-pro-image-preview slideshow"""
        import os
        import google.generativeai as genai

        # Get Gemini API key
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_key:
            raise RuntimeError("Gemini API key required. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable")

        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-3-pro-image-preview")

        safe_print(f"    🎨 Generating image slideshow with gemini-3-pro-image-preview...")

        # Calculate number of images (one every 2 seconds, minimum 3 images)
        num_images = max(3, int(duration / 2))
        safe_print(f"    📸 Generating {num_images} images for {duration}s slideshow...")

        # Create directory for images
        images_dir = Path(output_dir) / f"scene_{scene_number}_images"
        images_dir.mkdir(exist_ok=True)

        # Generate images with gemini-3-pro-image-preview
        image_paths = []
        for i in range(num_images):
            safe_print(f"       Generating image {i+1}/{num_images}...")

            try:
                response = model.generate_content(description)

                # Save image from response
                image_path = images_dir / f"image_{i:03d}.png"

                # Debug: check response structure
                import base64

                # Extract image data from response
                if hasattr(response, 'parts') and len(response.parts) > 0:
                    part = response.parts[0]

                    # Check if it's inline_data
                    if hasattr(part, 'inline_data') and part.inline_data:
                        image_data = part.inline_data.data

                        # Save directly if already bytes, otherwise decode from base64
                        if isinstance(image_data, bytes):
                            with open(image_path, 'wb') as f:
                                f.write(image_data)
                        else:
                            with open(image_path, 'wb') as f:
                                f.write(base64.b64decode(image_data))
                    else:
                        raise ValueError(f"No inline_data in response part. Part has: {dir(part)}")
                else:
                    raise ValueError(f"No parts in response. Response has: {dir(response)}")

                # Verify the image was saved correctly
                if not image_path.exists() or image_path.stat().st_size < 1000:
                    raise ValueError(f"Image file is too small or doesn't exist: {image_path.stat().st_size if image_path.exists() else 0} bytes")

                image_paths.append(image_path)
                safe_print(f"       ✅ Image {i+1} saved ({image_path.stat().st_size} bytes)")

            except Exception as e:
                raise RuntimeError(f"Image generation failed for image {i+1}: {e}")

        # Create slideshow video using FFmpeg
        safe_print(f"    🎬 Creating slideshow video...")
        video_path = Path(output_dir) / f"scene_{scene_number}.mp4"

        try:
            self._create_slideshow_video(image_paths, duration, video_path)
            safe_print(f"    ✅ Slideshow video saved: {video_path.name}")
            return str(video_path)
        except Exception as e:
            raise RuntimeError(f"Slideshow creation failed: {e}")

    def _create_slideshow_video(self, image_paths, duration, output_path):
        """
        Create a slideshow video from images using FFmpeg with smooth transitions

        Args:
            image_paths: List of image file paths
            duration: Total duration in seconds
            output_path: Output video path
        """
        import subprocess

        if not image_paths:
            raise ValueError("No images provided for slideshow")

        num_images = len(image_paths)

        # Calculate duration per image (with slight overlap for transitions)
        image_duration = duration / num_images

        # Create a temporary file list for FFmpeg concat
        concat_file = output_path.parent / f"concat_{output_path.stem}.txt"

        try:
            # Write concat file with duration for each image
            with open(concat_file, 'w') as f:
                for img_path in image_paths:
                    f.write(f"file '{img_path.absolute()}'\n")
                    f.write(f"duration {image_duration}\n")
                # Add last image again without duration (FFmpeg requirement)
                f.write(f"file '{image_paths[-1].absolute()}'\n")

            # FFmpeg command to create slideshow with crossfade transitions
            # Specs: 1920x1080, 24fps, H.264, yuv420p (matching pipeline specs)
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-vf", f"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=24",
                "-c:v", "libx264",
                "-crf", "18",  # High quality
                "-preset", "medium",
                "-movflags", "+faststart",
                str(output_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            return True

        finally:
            # Clean up concat file
            if concat_file.exists():
                concat_file.unlink()

    def _generate_replicate_video(self, description, duration, scene_number, output_dir, storyboard_image=None):
        """Generate a video using Replicate API (original implementation)"""
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

