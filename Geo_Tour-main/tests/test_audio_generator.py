"""
Tests for audio_generator module
"""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from audio_generator import AudioGenerator


def test_audio_generator_init():
    """Test AudioGenerator initialization"""
    generator = AudioGenerator(api_key="test-key", provider="mock")
    assert generator.provider == "mock"


def test_audio_generation_mock_mode(temp_dir, sample_script):
    """Test audio generation in mock mode"""
    generator = AudioGenerator(api_key=None, provider="mock")
    result = generator.generate(sample_script, output_dir=temp_dir)
    
    assert Path(result).exists()
    assert "voiceover" in result


def test_audio_generation_elevenlabs_success(temp_dir, sample_script):
    """Test audio generation with ElevenLabs API (mocked)"""
    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"fake audio content"
        mock_post.return_value = mock_response
        
        generator = AudioGenerator(api_key="test-key", provider="elevenlabs")
        result = generator.generate(sample_script, output_dir=temp_dir)
        
        assert Path(result).exists()
        mock_post.assert_called_once()


def test_audio_generation_elevenlabs_error(temp_dir, sample_script):
    """Test audio generation falls back to mock on ElevenLabs error"""
    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        generator = AudioGenerator(api_key="test-key", provider="elevenlabs")
        result = generator.generate(sample_script, output_dir=temp_dir)
        
        # Should fall back to mock
        assert Path(result).exists()


def test_audio_generator_invalid_provider(temp_dir, sample_script):
    """Test audio generator with invalid provider falls back to mock"""
    generator = AudioGenerator(api_key="test-key", provider="invalid")
    assert generator.provider == "mock"
    
    result = generator.generate(sample_script, output_dir=temp_dir)
    assert Path(result).exists()
