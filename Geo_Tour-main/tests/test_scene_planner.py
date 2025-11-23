"""
Tests for scene_planner module
"""
import pytest
import json
from unittest.mock import Mock, patch
from scene_planner import ScenePlanner


def test_scene_planner_init_with_key():
    """Test ScenePlanner initialization with API key"""
    planner = ScenePlanner(api_key="test-key")
    assert planner.api_key == "test-key"
    assert planner.client is not None


def test_scene_planner_init_without_key():
    """Test ScenePlanner initialization without API key raises error"""
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            ScenePlanner(api_key=None)


def test_scene_planning_success(mock_openai_client, sample_script):
    """Test successful scene planning"""
    with patch('scene_planner.OpenAI', return_value=mock_openai_client):
        planner = ScenePlanner(api_key="test-key")
        
        # Mock the response
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = json.dumps({
            "scenes": [
                {
                    "scene_number": 1,
                    "narration": "Rainbows appear when sunlight passes through water droplets",
                    "visual_description": "Sunlight rays passing through water droplets",
                    "duration": 6
                },
                {
                    "scene_number": 2,
                    "narration": "The light bends and separates",
                    "visual_description": "Close-up of water droplet with light refracting",
                    "duration": 5
                }
            ]
        })
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        result = planner.create_plan(sample_script)
        
        assert "scenes" in result
        assert len(result["scenes"]) == 2
        assert result["scenes"][0]["scene_number"] == 1
        assert "visual_description" in result["scenes"][0]


def test_scene_planning_invalid_structure(mock_openai_client, sample_script):
    """Test scene planning with invalid structure"""
    with patch('scene_planner.OpenAI', return_value=mock_openai_client):
        planner = ScenePlanner(api_key="test-key")
        
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = json.dumps({"invalid": "structure"})
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        with pytest.raises(ValueError, match="Invalid scene plan structure"):
            planner.create_plan(sample_script)


def test_scene_planning_missing_fields(mock_openai_client, sample_script):
    """Test scene planning with missing required fields"""
    with patch('scene_planner.OpenAI', return_value=mock_openai_client):
        planner = ScenePlanner(api_key="test-key")
        
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = json.dumps({
            "scenes": [
                {
                    "scene_number": 1,
                    "narration": "Test"
                    # Missing visual_description and duration
                }
            ]
        })
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        with pytest.raises(ValueError, match="Scene missing required fields"):
            planner.create_plan(sample_script)


def test_scene_planning_invalid_json(mock_openai_client, sample_script):
    """Test scene planning with invalid JSON"""
    with patch('scene_planner.OpenAI', return_value=mock_openai_client):
        planner = ScenePlanner(api_key="test-key")
        
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Invalid JSON"
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        with pytest.raises(ValueError, match="Failed to parse scene plan"):
            planner.create_plan(sample_script)
