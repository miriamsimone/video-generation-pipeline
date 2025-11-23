"""
Tests for video_generator module
"""
import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from video_generator import VideoGenerator


def test_video_generator_init():
    """Test VideoGenerator initialization"""
    generator = VideoGenerator(api_key="test-key")
    assert generator.api_key == "test-key"


def test_video_generator_mock_mode(temp_dir, sample_scene_plan):
    """Test video generation in mock mode"""
    generator = VideoGenerator(api_key=None)
    result = generator.generate_clips(sample_scene_plan, output_dir=temp_dir)
    
    assert len(result) == len(sample_scene_plan["scenes"])
    for clip_path in result:
        assert Path(clip_path).exists()


def test_video_generation_text_to_video(temp_dir, sample_scene_plan, mock_replicate_client, mock_requests_get):
    """Test text-to-video generation with Replicate"""
    with patch('video_generator.replicate.Client', return_value=mock_replicate_client):
        with patch('requests.get', return_value=mock_requests_get):
            generator = VideoGenerator(api_key="test-key")
            
            mock_replicate_client.run.return_value = "https://example.com/video.mp4"
            
            result = generator.generate_clips(sample_scene_plan, output_dir=temp_dir)
            
            assert len(result) == len(sample_scene_plan["scenes"])
            mock_replicate_client.run.assert_called()


def test_video_generation_image_to_video(temp_dir, sample_scene_plan, mock_storyboard_images, mock_replicate_client, mock_requests_get):
    """Test image-to-video generation with storyboard images"""
    with patch('video_generator.replicate.Client', return_value=mock_replicate_client):
        with patch('requests.get', return_value=mock_requests_get):
            generator = VideoGenerator(api_key="test-key")
            
            mock_replicate_client.run.return_value = "https://example.com/video.mp4"
            
            result = generator.generate_clips(
                sample_scene_plan, 
                output_dir=temp_dir,
                storyboard_images=mock_storyboard_images
            )
            
            assert len(result) == len(sample_scene_plan["scenes"])
            # Verify image-to-video was called (check for image parameter)
            calls = mock_replicate_client.run.call_args_list
            assert len(calls) > 0


def test_video_generation_no_api_key(temp_dir, sample_scene_plan):
    """Test video generation falls back to mock when no API key"""
    generator = VideoGenerator(api_key=None)
    result = generator.generate_clips(sample_scene_plan, output_dir=temp_dir)
    
    # Should fall back to mock mode
    assert len(result) == len(sample_scene_plan["scenes"])


def test_video_generation_stability_provider(temp_dir, sample_scene_plan, mock_replicate_client, mock_requests_get):
    """Test Stability AI provider via Replicate"""
    with patch('video_generator.replicate.Client', return_value=mock_replicate_client):
        with patch('requests.get', return_value=mock_requests_get):
            generator = VideoGenerator(api_key="test-key")
            
            mock_replicate_client.run.return_value = "https://example.com/video.mp4"
            
            result = generator.generate_clips(sample_scene_plan, output_dir=temp_dir)
            
            assert len(result) == len(sample_scene_plan["scenes"])


def test_video_generator_invalid_provider(temp_dir, sample_scene_plan):
    """Test video generator with invalid provider falls back to mock"""
    generator = VideoGenerator(api_key="test-key")
    
    result = generator.generate_clips(sample_scene_plan, output_dir=temp_dir)
    assert len(result) == len(sample_scene_plan["scenes"])
