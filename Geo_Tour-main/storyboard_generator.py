"""
Storyboard generation module - generates storyboard images from scene visual descriptions using Replicate
"""
import replicate
import requests
import time
from pathlib import Path
from config import REPLICATE_API_KEY, STORYBOARD_PROVIDER, STORYBOARD_MODEL, TEMP_DIR


def safe_print(*args, **kwargs):
    """Safely print messages, handling closed file errors in Streamlit"""
    try:
        print(*args, **kwargs)
    except (IOError, OSError, ValueError):
        # Silently fail if stdout is closed (Streamlit context)
        pass


class StoryboardGenerator:
    def __init__(self, api_key=None, provider=None, max_retries=3, retry_delay=5):
        self.api_key = api_key or REPLICATE_API_KEY
        self.provider = provider or STORYBOARD_PROVIDER
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Map of supported providers
        self.providers = {
            "replicate": self._generate_replicate,
        }
        
        if self.provider not in self.providers:
            raise ValueError(f"Storyboard provider '{self.provider}' not supported. Available: {list(self.providers.keys())}")
            
    
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
    
    def generate(self, scene_plan, output_dir=None):
        """
        Generate storyboard images for all scenes
        
        Args:
            scene_plan (dict): Scene plan with visual descriptions
            output_dir (Path): Directory to save storyboard images
            
        Returns:
            list: Paths to generated storyboard images (one per scene, in order)
        """
        output_dir = output_dir or TEMP_DIR
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        safe_print(f"🎨 Generating {len(scene_plan['scenes'])} storyboard images...")
        
        image_paths = []
        generator_func = self.providers[self.provider]
        
        for scene in scene_plan['scenes']:
            safe_print(f"  Scene {scene['scene_number']}: {scene['visual_description'][:50]}...")
            
            # Use retry logic for storyboard generation
            image_path = self._retry_with_backoff(
                generator_func,
                visual_description=scene['visual_description'],
                scene_number=scene['scene_number'],
                output_dir=output_dir
            )
            
            image_paths.append(image_path)
        
        safe_print(f"✅ Generated {len(image_paths)} storyboard images")
        return image_paths
    
    def _generate_replicate(self, visual_description, scene_number, output_dir):
        """Generate storyboard image using Replicate API"""
        if not self.api_key:
            raise ValueError("No API key provided for storyboard generation. Please set REPLICATE_API_KEY in your .env file.")
        
        client = replicate.Client(api_token=self.api_key)
        
        # Generate storyboard image using selected T2I model
        safe_print(f"    🎨 Generating image via Replicate...")
        if "google/imagen-3" in STORYBOARD_MODEL:
            output = client.run(
                STORYBOARD_MODEL,
                input={
                    "prompt": visual_description,
                    "aspect_ratio": "16:9",
                    "output_format": "png",
                    "safety_filter_level": "block_only_high"
                },
                use_file_output=False
            )
        else:
            output = client.run(
                STORYBOARD_MODEL,
                input={
                    "prompt": visual_description,
                    "width": 1024,
                    "height": 576,  # 16:9 aspect ratio for video
                    "num_outputs": 1
                },
                use_file_output=False
            )
        try:
            t = type(output).__name__
            safe_print(f"    📦 T2I output type: {t}")
        except Exception:
            pass
        image_path = output_dir / f"storyboard_scene_{scene_number}.png"
        self._save_image_output(output, image_path)
        
        safe_print(f"    ✅ Storyboard image saved: {image_path.name}")
        return str(image_path)
    
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
                for k in ("url", "image"):
                    if k in first:
                        return first[k]
                return None
        if isinstance(data, dict):
            for k in ("output", "url", "image"):
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


if __name__ == "__main__":
    # Test the storyboard generator
    generator = StoryboardGenerator(provider="replicate")
    test_plan = {
        "scenes": [
            {
                "scene_number": 1,
                "visual_description": "Sunlight rays passing through water droplets, creating a prism effect",
                "duration": 6
            },
            {
                "scene_number": 2,
                "visual_description": "Close-up of a single water droplet with light refracting inside",
                "duration": 5
            }
        ]
    }
    images = generator.generate(test_plan)
    print(f"Generated storyboard images: {images}")

