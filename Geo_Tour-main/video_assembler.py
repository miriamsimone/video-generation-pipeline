"""
Video assembly module - combines clips and audio into final video
"""
import subprocess
import os
import shutil
from pathlib import Path
from config import OUTPUT_DIR, TEMP_DIR


def safe_print(*args, **kwargs):
    """Safely print messages, handling closed file errors in Streamlit"""
    try:
        print(*args, **kwargs)
    except (IOError, OSError, ValueError):
        # Silently fail if stdout is closed (Streamlit context)
        pass


class VideoAssembler:
    def __init__(self):
        self.ffmpeg_cmd = self._find_ffmpeg()
        self.ffmpeg_available = self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        try:
            if not self.ffmpeg_cmd:
                return False
            subprocess.run(
                [self.ffmpeg_cmd, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return True
        except Exception:
            return False

    def _find_ffmpeg(self):
        # Honor explicit env var
        p = os.getenv("FFMPEG_PATH", "").strip()
        if p:
            exe = p
            if os.path.isdir(p):
                exe = os.path.join(p, "ffmpeg.exe") if os.name == "nt" else os.path.join(p, "ffmpeg")
            if os.path.isfile(exe):
                return exe
        # Search PATH
        found = shutil.which("ffmpeg")
        if found:
            return found
        # Common Windows locations
        candidates = [
            r"C:\\ffmpeg\\bin\\ffmpeg.exe",
            r"C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
            r"C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe"
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None
    
    def assemble(self, clip_paths, audio_path, output_path=None, face_rig_videos=None):
        """
        Combine video clips and audio into final video
        
        Args:
            clip_paths (list): List of video clip file paths
            audio_path (str): Path to audio file
            output_path (str): Path for final output video
            face_rig_videos (list): Optional list of face_rig video paths for PiP overlay
            
        Returns:
            str: Path to assembled video
        """
        if not self.ffmpeg_available:
            return self._mock_assemble(clip_paths, audio_path, output_path)
        
        output_path = output_path or str(OUTPUT_DIR / "final_video.mp4")
        output_path = Path(output_path)
        output_path.parent.mkdir(exist_ok=True)
        
        safe_print("🎞️  Assembling video...")
        
        try:
            # Step 1: Concatenate video clips
            concat_path = TEMP_DIR / "concatenated.mp4"
            self._concatenate_clips(clip_paths, concat_path)
            
            # Step 2: Add face_rig overlay if provided
            if face_rig_videos:
                safe_print("🎭 Adding face_rig picture-in-picture overlay...")
                with_overlay_path = TEMP_DIR / "with_overlay.mp4"
                self._add_face_rig_overlay(concat_path, face_rig_videos, with_overlay_path)
                concat_path = with_overlay_path
            
            # Step 3: Add audio to video
            self._add_audio(concat_path, audio_path, output_path)
            
            # Cleanup temp files
            if (TEMP_DIR / "concatenated.mp4").exists():
                (TEMP_DIR / "concatenated.mp4").unlink()
            if (TEMP_DIR / "with_overlay.mp4").exists():
                (TEMP_DIR / "with_overlay.mp4").unlink()
            
            safe_print(f"✅ Video assembled: {output_path}")
            return str(output_path)
            
        except Exception as e:
            safe_print(f"❌ Assembly failed: {e}")
            return self._mock_assemble(clip_paths, audio_path, output_path)
    
    def _concatenate_clips(self, clip_paths, output_path):
        """Concatenate multiple video clips"""
        # Create file list for ffmpeg
        list_path = TEMP_DIR / "clips_list.txt"
        
        with open(list_path, 'w', encoding='utf-8') as f:
            for clip in clip_paths:
                # Escape single quotes and write path
                escaped_path = str(Path(clip)).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        # Concatenate using ffmpeg
        cmd = [
            self.ffmpeg_cmd, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Cleanup
        list_path.unlink()
    
    def _add_audio(self, video_path, audio_path, output_path):
        """Add audio track to video"""
        cmd = [
            self.ffmpeg_cmd, "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",  # Match to shortest input (video or audio)
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
    
    def _add_face_rig_overlay(self, main_video_path, face_rig_videos, output_path):
        """
        Add face_rig videos as picture-in-picture overlays in the bottom right
        
        Args:
            main_video_path: Path to main video
            face_rig_videos: List of face_rig video paths (one per scene)
            output_path: Path for output video with overlay
        """
        # First, concatenate face_rig videos
        face_rig_concat_path = TEMP_DIR / "face_rig_concatenated.mp4"
        self._concatenate_clips(face_rig_videos, face_rig_concat_path)
        
        # Now overlay the concatenated face_rig video on the main video
        # Position in bottom right corner, scaled to 25% of main video width
        # Using overlay filter with positioning
        cmd = [
            self.ffmpeg_cmd, "-y",
            "-i", str(main_video_path),  # Main video
            "-i", str(face_rig_concat_path),  # Overlay video
            "-filter_complex",
            "[1:v]scale=iw*0.25:-1[overlay];"  # Scale overlay to 25% width
            "[0:v][overlay]overlay=main_w-overlay_w-20:main_h-overlay_h-20",  # Position bottom-right with 20px margin
            "-c:a", "copy",  # Copy audio from main video
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Cleanup
        if face_rig_concat_path.exists():
            face_rig_concat_path.unlink()
    
    def _mock_assemble(self, clip_paths, audio_path, output_path):
        """
        Mock assembly for when ffmpeg is not available
        Creates a text file describing the assembly
        """
        output_path = output_path or str(OUTPUT_DIR / "final_video.txt")
        output_path = Path(output_path)
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("Mock Final Video\n")
            f.write("=" * 50 + "\n\n")
            f.write("Video Clips:\n")
            for i, clip in enumerate(clip_paths, 1):
                f.write(f"  {i}. {clip}\n")
            f.write(f"\nAudio Track:\n  {audio_path}\n")
            f.write("\n(Install ffmpeg to generate actual video)\n")
        
        safe_print(f"✅ Mock assembly created: {output_path}")
        return str(output_path)


if __name__ == "__main__":
    # Test the assembler
    assembler = VideoAssembler()
    test_clips = [
        "/home/claude/temp/scene_1.mp4",
        "/home/claude/temp/scene_2.mp4"
    ]
    test_audio = "/home/claude/temp/voiceover.mp3"
    
    output = assembler.assemble(test_clips, test_audio, "test_output.mp4")
    print(f"Assembled: {output}")
