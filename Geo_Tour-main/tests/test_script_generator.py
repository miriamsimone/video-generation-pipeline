"""
Tests for script_generator module
"""
import pytest
import json
from unittest.mock import Mock, patch
from script_generator import ScriptGenerator


def test_script_generator_init_with_key():
    """Test ScriptGenerator initialization with API key"""
    generator = ScriptGenerator(api_key="test-key")
    assert generator.api_key == "test-key"
    assert generator.client is not None


def test_script_generator_init_without_key():
    """Test ScriptGenerator initialization without API key raises error"""
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            ScriptGenerator(api_key=None)


def test_script_generation_success(mock_openai_client, sample_user_prompt):
    """Test successful script generation"""
    with patch('script_generator.OpenAI', return_value=mock_openai_client):
        generator = ScriptGenerator(api_key="test-key")
        
        # Mock the response
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = json.dumps({
            "title": "How Rainbows Form",
            "script": "Rainbows appear when sunlight passes through water droplets."
        })
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        result = generator.generate(sample_user_prompt)
        
        assert "title" in result
        assert "script" in result
        assert result["title"] == "How Rainbows Form"
        assert len(result["script"]) > 0


def test_script_generation_invalid_json(mock_openai_client, sample_user_prompt):
    """Test script generation with invalid JSON response"""
    with patch('script_generator.OpenAI', return_value=mock_openai_client):
        generator = ScriptGenerator(api_key="test-key")
        
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Invalid JSON response"
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        with pytest.raises(ValueError, match="Failed to parse script"):
            generator.generate(sample_user_prompt)


def test_script_generation_missing_fields(mock_openai_client, sample_user_prompt):
    """Test script generation with missing required fields"""
    with patch('script_generator.OpenAI', return_value=mock_openai_client):
        generator = ScriptGenerator(api_key="test-key")
        
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = json.dumps({"title": "Test"})  # Missing script field
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        with pytest.raises(ValueError, match="Invalid script structure"):
            generator.generate(sample_user_prompt)


def test_script_generation_api_error(mock_openai_client, sample_user_prompt):
    """Test script generation with API error"""
    with patch('script_generator.OpenAI', return_value=mock_openai_client):
        generator = ScriptGenerator(api_key="test-key")
        
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        with pytest.raises(RuntimeError, match="Script generation failed"):
            generator.generate(sample_user_prompt)
