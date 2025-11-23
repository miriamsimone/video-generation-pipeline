"""
Tests for video_assembler module
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from video_assembler import VideoAssembler


def test_video_assembler_init_with_ffmpeg():
    """Test VideoAssembler initialization with ffmpeg available"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0)
        assembler = VideoAssembler()
        assert assembler.ffmpeg_available == True


def test_video_assembler_init_without_ffmpeg():
    """Test VideoAssembler initialization without ffmpeg"""
    with patch('subprocess.run', side_effect=FileNotFoundError()):
        assembler = VideoAssembler()
        assert assembler.ffmpeg_available == False


def test_video_assembly_mock_mode(temp_dir, mock_video_clips):
    """Test video assembly in mock mode (no ffmpeg)"""
    with patch('subprocess.run', side_effect=FileNotFoundError()):
        assembler = VideoAssembler()
        audio_path = temp_dir / "voiceover.mp3"
        audio_path.write_text("mock audio")
        
        result = assembler.assemble(mock_video_clips, str(audio_path), temp_dir / "output.mp4")
        
        assert Path(result).exists()


def test_video_assembly_with_ffmpeg(temp_dir, mock_video_clips):
    """Test video assembly with ffmpeg available"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0)
        
        assembler = VideoAssembler()
        audio_path = temp_dir / "voiceover.mp3"
        audio_path.write_text("mock audio")
        
        output_path = temp_dir / "output.mp4"
        result = assembler.assemble(mock_video_clips, str(audio_path), output_path)
        
        assert result == str(output_path)
        # Verify ffmpeg was called
        assert mock_run.called


def test_video_assembly_ffmpeg_error(temp_dir, mock_video_clips):
    """Test video assembly falls back to mock on ffmpeg error"""
    with patch('subprocess.run') as mock_run:
        # First call (check) succeeds, subsequent calls fail
        mock_run.side_effect = [
            Mock(returncode=0),  # ffmpeg check
            Mock(returncode=1)   # ffmpeg concat fails
        ]
        
        assembler = VideoAssembler()
        audio_path = temp_dir / "voiceover.mp3"
        audio_path.write_text("mock audio")
        
        # Should fall back to mock assembly
        result = assembler.assemble(mock_video_clips, str(audio_path), temp_dir / "output.mp4")
        assert Path(result).exists()
