"""
Integration tests for the full video pipeline
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from pipeline import VideoPipeline


def test_pipeline_init():
    """Test VideoPipeline initialization"""
    with patch('pipeline.ScriptGenerator'):
        with patch('pipeline.ScenePlanner'):
            with patch('pipeline.StoryboardGenerator'):
                with patch('pipeline.VideoGenerator'):
                    with patch('pipeline.AudioGenerator'):
                        pipeline = VideoPipeline(
                            openai_api_key="test-key",
                            video_provider="mock",
                            tts_provider="mock"
                        )
                        assert pipeline is not None


def test_full_pipeline_mock_mode(temp_dir, sample_user_prompt):
    """Test full pipeline execution in mock mode"""
    with patch('script_generator.ScriptGenerator.generate') as mock_script:
        with patch('scene_planner.ScenePlanner.create_plan') as mock_scene:
            with patch('video_generator.VideoGenerator.generate_clips') as mock_video:
                with patch('audio_generator.AudioGenerator.generate') as mock_audio:
                    with patch('video_assembler.VideoAssembler.assemble') as mock_assemble:
                        # Setup mocks
                        mock_script.return_value = {
                            "title": "Test Video",
                            "script": "Test script"
                        }
                        mock_scene.return_value = {
                            "scenes": [
                                {
                                    "scene_number": 1,
                                    "narration": "Test",
                                    "visual_description": "Test visual",
                                    "duration": 5
                                }
                            ]
                        }
                        mock_video.return_value = [str(temp_dir / "scene_1.mp4")]
                        mock_audio.return_value = str(temp_dir / "voiceover.mp3")
                        mock_assemble.return_value = str(temp_dir / "final.mp4")
                        
                        # Create mock files
                        (temp_dir / "scene_1.mp4").write_text("mock")
                        (temp_dir / "voiceover.mp3").write_text("mock")
                        (temp_dir / "final.mp4").write_text("mock")
                        
                        pipeline = VideoPipeline(
                            openai_api_key="test-key",
                            video_provider="mock",
                            tts_provider="mock",
                            use_storyboard=False
                        )
                        
                        result = pipeline.run(sample_user_prompt)
                        
                        assert result["success"] == True
                        assert "video_path" in result
                        assert "script" in result
                        assert "scenes" in result


def test_pipeline_with_storyboard(temp_dir, sample_user_prompt):
    """Test full pipeline with storyboard generation enabled"""
    with patch('video_pipeline.script_generator.ScriptGenerator.generate') as mock_script:
        with patch('video_pipeline.scene_planner.ScenePlanner.create_plan') as mock_scene:
            with patch('storyboard_generator.StoryboardGenerator.generate') as mock_storyboard:
                with patch('video_pipeline.video_generator.VideoGenerator.generate_clips') as mock_video:
                    with patch('video_pipeline.audio_generator.AudioGenerator.generate') as mock_audio:
                        with patch('video_pipeline.video_assembler.VideoAssembler.assemble') as mock_assemble:
                            # Setup mocks
                            mock_script.return_value = {
                                "title": "Test Video",
                                "script": "Test script"
                            }
                            mock_scene.return_value = {
                                "scenes": [
                                    {
                                        "scene_number": 1,
                                        "narration": "Test",
                                        "visual_description": "Test visual",
                                        "duration": 5
                                    }
                                ]
                            }
                            mock_storyboard.return_value = [str(temp_dir / "storyboard_1.png")]
                            mock_video.return_value = [str(temp_dir / "scene_1.mp4")]
                            mock_audio.return_value = str(temp_dir / "voiceover.mp3")
                            mock_assemble.return_value = str(temp_dir / "final.mp4")
                            
                            # Create mock files
                            (temp_dir / "storyboard_1.png").write_text("mock")
                            (temp_dir / "scene_1.mp4").write_text("mock")
                            (temp_dir / "voiceover.mp3").write_text("mock")
                            (temp_dir / "final.mp4").write_text("mock")
                            
                            pipeline = VideoPipeline(
                                openai_api_key="test-key",
                                video_provider="mock",
                                tts_provider="mock",
                                use_storyboard=True
                            )
                            
                            result = pipeline.run(sample_user_prompt)
                            
                            assert result["success"] == True
                            assert "storyboard" in result["project_data"]["steps"]
                            mock_storyboard.assert_called_once()


def test_pipeline_error_handling(sample_user_prompt):
    """Test pipeline error handling"""
    with patch('script_generator.ScriptGenerator.generate', side_effect=Exception("Test error")):
        pipeline = VideoPipeline(
            openai_api_key="test-key",
            video_provider="mock",
            tts_provider="mock"
        )
        
        result = pipeline.run(sample_user_prompt)
        
        assert result["success"] == False
        assert "error" in result
        assert "Test error" in result["error"]


def test_pipeline_metadata_saving(temp_dir, sample_user_prompt):
    """Test that pipeline saves project metadata"""
    with patch('script_generator.ScriptGenerator.generate') as mock_script:
        with patch('scene_planner.ScenePlanner.create_plan') as mock_scene:
            with patch('video_generator.VideoGenerator.generate_clips') as mock_video:
                with patch('audio_generator.AudioGenerator.generate') as mock_audio:
                    with patch('video_assembler.VideoAssembler.assemble') as mock_assemble:
                        # Setup mocks
                        mock_script.return_value = {"title": "Test", "script": "Test"}
                        mock_scene.return_value = {"scenes": []}
                        mock_video.return_value = []
                        mock_audio.return_value = str(temp_dir / "voiceover.mp3")
                        mock_assemble.return_value = str(temp_dir / "final.mp4")
                        
                        (temp_dir / "voiceover.mp3").write_text("mock")
                        (temp_dir / "final.mp4").write_text("mock")
                        
                        pipeline = VideoPipeline(
                            openai_api_key="test-key",
                            video_provider="mock",
                            tts_provider="mock"
                        )
                        
                        result = pipeline.run(sample_user_prompt)
                        
                        assert result["success"] == True
                        assert "project_data" in result
                        assert "steps" in result["project_data"]
