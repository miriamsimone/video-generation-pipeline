"""
Tests for specific workflows
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from pipeline import VideoPipeline


def test_workflow_a_text_to_video(temp_dir, sample_user_prompt):
    """Test Workflow A: Direct text-to-video (no storyboard)"""
    with patch('script_generator.ScriptGenerator.generate') as mock_script:
        with patch('scene_planner.ScenePlanner.create_plan') as mock_scene:
            with patch('video_generator.VideoGenerator.generate_clips') as mock_video:
                with patch('audio_generator.AudioGenerator.generate') as mock_audio:
                    with patch('video_assembler.VideoAssembler.assemble') as mock_assemble:
                        # Setup mocks
                        mock_script.return_value = {"title": "Test", "script": "Test"}
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
                        
                        # Create files
                        (temp_dir / "scene_1.mp4").write_text("mock")
                        (temp_dir / "voiceover.mp3").write_text("mock")
                        (temp_dir / "final.mp4").write_text("mock")
                        
                        pipeline = VideoPipeline(
                            openai_api_key="test-key",
                            video_provider="replicate",
                            tts_provider="mock",
                            use_storyboard=False
                        )
                        
                        result = pipeline.run(sample_user_prompt)
                        
                        assert result["success"] == True
                        # Verify storyboard was NOT called
                        assert "storyboard" not in result["project_data"]["steps"]
                        # Verify video generator was called without storyboard images
                        mock_video.assert_called_once()
                        call_args = mock_video.call_args
                        assert call_args[1].get("storyboard_images") is None


def test_workflow_b_storyboard_guided(temp_dir, sample_user_prompt):
    """Test Workflow B: Storyboard-guided image-to-video"""
    with patch('video_pipeline.script_generator.ScriptGenerator.generate') as mock_script:
        with patch('video_pipeline.scene_planner.ScenePlanner.create_plan') as mock_scene:
            with patch('storyboard_generator.StoryboardGenerator.generate') as mock_storyboard:
                with patch('video_pipeline.video_generator.VideoGenerator.generate_clips') as mock_video:
                    with patch('video_pipeline.audio_generator.AudioGenerator.generate') as mock_audio:
                        with patch('video_pipeline.video_assembler.VideoAssembler.assemble') as mock_assemble:
                            # Setup mocks
                            mock_script.return_value = {"title": "Test", "script": "Test"}
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
                            storyboard_images = [str(temp_dir / "storyboard_1.png")]
                            mock_storyboard.return_value = storyboard_images
                            mock_video.return_value = [str(temp_dir / "scene_1.mp4")]
                            mock_audio.return_value = str(temp_dir / "voiceover.mp3")
                            mock_assemble.return_value = str(temp_dir / "final.mp4")
                            
                            # Create files
                            (temp_dir / "storyboard_1.png").write_text("mock")
                            (temp_dir / "scene_1.mp4").write_text("mock")
                            (temp_dir / "voiceover.mp3").write_text("mock")
                            (temp_dir / "final.mp4").write_text("mock")
                            
                            pipeline = VideoPipeline(
                                openai_api_key="test-key",
                                video_provider="replicate",
                                tts_provider="mock",
                                use_storyboard=True
                            )
                            
                            result = pipeline.run(sample_user_prompt)
                            
                            assert result["success"] == True
                            # Verify storyboard was generated
                            assert "storyboard" in result["project_data"]["steps"]
                            mock_storyboard.assert_called_once()
                            # Verify video generator was called WITH storyboard images
                            mock_video.assert_called_once()
                            call_args = mock_video.call_args
                            assert call_args[1].get("storyboard_images") == storyboard_images


def test_workflow_replicate_provider(temp_dir, sample_user_prompt):
    """Test workflow with Replicate provider"""
    with patch('script_generator.ScriptGenerator.generate') as mock_script:
        with patch('scene_planner.ScenePlanner.create_plan') as mock_scene:
            with patch('video_generator.VideoGenerator.generate_clips') as mock_video:
                with patch('audio_generator.AudioGenerator.generate') as mock_audio:
                    with patch('video_assembler.VideoAssembler.assemble') as mock_assemble:
                        mock_script.return_value = {"title": "Test", "script": "Test"}
                        mock_scene.return_value = {"scenes": []}
                        mock_video.return_value = []
                        mock_audio.return_value = str(temp_dir / "voiceover.mp3")
                        mock_assemble.return_value = str(temp_dir / "final.mp4")
                        
                        (temp_dir / "voiceover.mp3").write_text("mock")
                        (temp_dir / "final.mp4").write_text("mock")
                        
                        pipeline = VideoPipeline(
                            openai_api_key="test-key",
                            video_provider="replicate",
                            tts_provider="mock"
                        )
                        
                        result = pipeline.run(sample_user_prompt)
                        assert result["success"] == True
