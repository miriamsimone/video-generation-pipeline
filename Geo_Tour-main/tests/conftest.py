"""
Shared pytest fixtures for video pipeline tests
"""
import pytest
import json
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment variables from {env_path}")
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

# Add current directory to path (modules are in root)
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_script():
    """Sample script data for testing"""
    return {
        "title": "How Rainbows Form",
        "script": "Rainbows appear when sunlight passes through water droplets in the air. The light bends and separates into different colors, creating the beautiful arc we see in the sky."
    }


@pytest.fixture
def sample_scene_plan():
    """Sample scene plan for testing"""
    return {
        "scenes": [
            {
                "scene_number": 1,
                "narration": "Rainbows appear when sunlight passes through water droplets",
                "visual_description": "Sunlight rays passing through water droplets, creating a prism effect with rainbow colors",
                "duration": 6
            },
            {
                "scene_number": 2,
                "narration": "The light bends and separates into different colors",
                "visual_description": "Close-up of a single water droplet with light refracting inside, showing color separation",
                "duration": 5
            },
            {
                "scene_number": 3,
                "narration": "creating the beautiful arc we see in the sky",
                "visual_description": "Wide shot of rainbow arc in sky after rain, with vibrant colors",
                "duration": 6
            }
        ]
    }


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing"""
    client = Mock()
    message = Mock()
    message.content = json.dumps({
        "title": "Test Video",
        "script": "This is a test script."
    })
    choice = Mock()
    choice.message = message
    response = Mock()
    response.choices = [choice]
    client.chat.completions.create.return_value = response
    return client


@pytest.fixture
def mock_replicate_client():
    """Mock Replicate client for testing"""
    client = Mock()
    # Mock video output
    client.run.return_value = "https://example.com/video.mp4"
    return client


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for downloading files"""
    mock_response = Mock()
    mock_response.content = b"fake video content"
    mock_response.raise_for_status = Mock()
    mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
    mock_response.status_code = 200
    return mock_response


@pytest.fixture
def sample_user_prompt():
    """Sample user prompt for testing"""
    return "Explain how rainbows form"


@pytest.fixture
def mock_storyboard_images(temp_dir):
    """Create mock storyboard image files"""
    images = []
    for i in range(1, 4):
        img_path = temp_dir / f"storyboard_scene_{i}.png"
        img_path.write_text(f"Mock image {i}")
        images.append(str(img_path))
    return images


@pytest.fixture
def mock_video_clips(temp_dir):
    """Create mock video clip files"""
    clips = []
    for i in range(1, 4):
        clip_path = temp_dir / f"scene_{i}.mp4"
        clip_path.write_text(f"Mock video {i}")
        clips.append(str(clip_path))
    return clips
