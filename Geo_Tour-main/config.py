"""
Configuration settings for the video generation pipeline
"""
import os
from pathlib import Path

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

# API Keys - Set these as environment variables or edit directly
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VIDEO_API_KEY = os.getenv("VIDEO_API_KEY")
TTS_API_KEY = os.getenv("TTS_API_KEY", os.getenv("ELEVENLABS_API_KEY"))

# Directory settings
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"

# Model settings
OPENAI_MODEL = "gpt-4o"  # or "gpt-4o-mini" for faster/cheaper
SCRIPT_MAX_TOKENS = 2000
SCENE_MAX_TOKENS = 3000

# Video settings
DEFAULT_VIDEO_DURATION = 30  # seconds
SCENE_DURATION_MIN = 4  # seconds
SCENE_DURATION_MAX = 8  # seconds
TARGET_SCENES = 5

# Audio settings
TTS_VOICE_ID = "default"  # Change based on TTS provider
AUDIO_FORMAT = "mp3"

# Video API settings (customize based on provider)
VIDEO_API_PROVIDER = "replicate"  # Options: replicate, runwayml, pika, stability, mock
VIDEO_MODEL = "gen-3-alpha"

# Replicate API settings
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY", os.getenv("VIDEO_API_KEY"))
REPLICATE_MODEL = "anotherjesse/zeroscope-v2-xl"  # Text-to-video model
STABILITY_MODEL = "bytedance/seedance-1-pro"  # Default image-to-video model (Replicate)

# Storyboard settings
STORYBOARD_PROVIDER = "replicate"  # Options: replicate, mock
STORYBOARD_MODEL = "google/imagen-3"  # Default text-to-image model for storyboards
USE_STORYBOARD = False  # Default: False for text-to-video, True for image-to-video providers

def safe_print(message):
    """Safely print messages with Unicode characters, handling encoding errors"""
    try:
        print(message)
    except UnicodeEncodeError:
        # Fallback to ASCII-safe version
        safe_message = message.encode('ascii', errors='replace').decode('ascii')
        print(safe_message)

def ensure_directories():
    """Create necessary directories if they don't exist"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)
