"""
Tests for storyboard_generator module
"""
import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from storyboard_generator import StoryboardGenerator


def test_storyboard_generator_init():
    """Test StoryboardGenerator initialization"""
    generator = StoryboardGenerator(api_key="test-key", provider="replicate")
    assert generator.api_key == "test-key"
    assert generator.provider == "replicate"


def test_storyboard_generator_mock_mode(temp_dir, sample_scene_plan):
    """Test storyboard generation in mock mode"""
    generator = StoryboardGenerator(api_key=None, provider="mock")
    result = generator.generate(sample_scene_plan, output_dir=temp_dir)
    
    assert len(result) == len(sample_scene_plan["scenes"])
    for i, img_path in enumerate(result):
        assert Path(img_path).exists()
        assert f"storyboard_scene_{i+1}" in img_path


def test_storyboard_generation_replicate_success(temp_dir, sample_scene_plan, mock_replicate_client, mock_requests_get):
    """Test storyboard generation with Replicate API"""
    with patch('storyboard_generator.replicate.Client', return_value=mock_replicate_client):
        with patch('requests.get', return_value=mock_requests_get):
            generator = StoryboardGenerator(api_key="test-key", provider="replicate")
            
            # Mock Replicate response
            mock_replicate_client.run.return_value = "https://example.com/image.png"
            
            result = generator.generate(sample_scene_plan, output_dir=temp_dir)
            
            assert len(result) == len(sample_scene_plan["scenes"])
            mock_replicate_client.run.assert_called()
            # Verify images were downloaded
            for img_path in result:
                assert Path(img_path).exists()


def test_storyboard_generation_no_api_key(temp_dir, sample_scene_plan):
    """Test storyboard generation falls back to mock when no API key"""
    generator = StoryboardGenerator(api_key=None, provider="replicate")
    result = generator.generate(sample_scene_plan, output_dir=temp_dir)
    
    # Should fall back to mock mode
    assert len(result) == len(sample_scene_plan["scenes"])
    for img_path in result:
        assert Path(img_path).exists()


def test_storyboard_generation_api_error(temp_dir, sample_scene_plan, mock_replicate_client):
    """Test storyboard generation handles API errors gracefully"""
    with patch('storyboard_generator.replicate.Client', return_value=mock_replicate_client):
        generator = StoryboardGenerator(api_key="test-key", provider="replicate")
        
        # Mock API error
        mock_replicate_client.run.side_effect = Exception("API Error")
        
        # Should fall back to mock mode
        result = generator.generate(sample_scene_plan, output_dir=temp_dir)
        assert len(result) == len(sample_scene_plan["scenes"])


def test_storyboard_generator_invalid_provider(temp_dir, sample_scene_plan):
    """Test storyboard generator with invalid provider falls back to mock"""
    generator = StoryboardGenerator(api_key="test-key", provider="invalid")
    assert generator.provider == "mock"
    
    result = generator.generate(sample_scene_plan, output_dir=temp_dir)
    assert len(result) == len(sample_scene_plan["scenes"])
