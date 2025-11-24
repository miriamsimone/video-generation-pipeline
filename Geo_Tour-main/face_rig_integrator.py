"""
Face Rig Integration Module
Handles communication with the face_rig server to generate
character animations with lip-sync for each scene.
"""
import requests
import json
from pathlib import Path
from typing import Dict, List, Optional
import time
import wave

from config import TEMP_DIR


def safe_print(*args, **kwargs):
    """Safely print messages, handling closed file errors in Streamlit"""
    try:
        print(*args, **kwargs)
    except (IOError, OSError, ValueError):
        # Silently fail if stdout is closed (Streamlit context)
        pass


class FaceRigIntegrator:
    def __init__(self, face_rig_url="http://localhost:8000", voice_id="yoZ06aMxZJJ28mfd3POQ", max_retries=3, retry_delay=5):
        """
        Initialize Face Rig integrator
        
        Args:
            face_rig_url: Base URL for the face_rig server
            voice_id: ElevenLabs voice ID (default is Sam - male conversational voice)
            max_retries: Maximum number of retry attempts for API calls
            retry_delay: Initial delay between retries (seconds, with exponential backoff)
        """
        self.face_rig_url = face_rig_url.rstrip("/")
        self.voice_id = voice_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.audio_dir = Path(TEMP_DIR) / "face_rig_audio"
        self.video_dir = Path(TEMP_DIR) / "face_rig_videos"
        self.audio_dir.mkdir(exist_ok=True, parents=True)
        self.video_dir.mkdir(exist_ok=True, parents=True)
    
    def _retry_api_call(self, func, *args, **kwargs):
        """
        Execute an API call with exponential backoff retry logic
        
        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                error_msg = str(e)
                
                # Determine if error is retryable
                retryable_errors = [
                    "Server disconnected",
                    "Connection",
                    "Timeout",
                    "timeout",
                    "503",
                    "502",
                    "500",
                    "429",  # Rate limit
                    "ConnectionError",
                    "ReadTimeout",
                    "timed out",
                ]
                
                is_retryable = any(err in error_msg for err in retryable_errors)
                
                if not is_retryable:
                    safe_print(f"    ❌ Non-retryable error: {error_msg}")
                    raise
                
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    safe_print(f"    ⚠️  Attempt {attempt + 1}/{self.max_retries} failed: {error_msg}")
                    safe_print(f"    ⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    safe_print(f"    ❌ All {self.max_retries} attempts failed")
        
        raise last_exception
    
    def generate_scene_video(self, scene_narration: str, scene_number: int) -> Dict:
        """
        Generate a complete face_rig video for a scene with lip-sync and emotions.
        
        Args:
            scene_narration: The text narration for this scene
            scene_number: Scene number for file naming
        
        Returns:
            dict: {
                'video_path': str,  # Path to generated face_rig video
                'audio_path': str,  # Path to generated audio
                'audio_duration': float,  # Duration in seconds
                'mfa_timeline': dict,  # MFA phoneme timeline data
                'emotion_timeline': dict  # Emotion keyframes
            }
        """
        safe_print(f"  🎭 Generating face_rig video for scene {scene_number}...")
        
        try:
            # Step 1: Generate TTS audio
            safe_print(f"    🎤 Generating audio with ElevenLabs...")
            audio_data = self._retry_api_call(self._generate_tts, scene_narration)
            audio_path = audio_data['path']
            audio_duration = audio_data['duration']
            
            safe_print(f"    ✅ Audio generated: {audio_duration:.2f}s")
            
            # Step 2: Generate MFA alignment
            safe_print(f"    📊 Generating phoneme alignment with MFA...")
            mfa_timeline = self._retry_api_call(self._generate_alignment, audio_path, scene_narration)
            total_duration_ms = int(audio_duration * 1000)
            
            safe_print(f"    ✅ Generated {len(mfa_timeline.get('keyframes', []))} phoneme keyframes")
            
            # Step 3: Generate emotion timeline
            safe_print(f"    😊 Generating emotion timeline with AI...")
            emotion_timeline = self._retry_api_call(
                self._generate_emotions,
                scene_narration, 
                mfa_timeline.get('keyframes', []),
                total_duration_ms
            )
            
            safe_print(f"    ✅ Generated {len(emotion_timeline.get('keyframes', []))} emotion keyframes")
            
            # Step 4: Combine phoneme and emotion timelines
            combined_timeline = self._combine_timelines(
                mfa_timeline.get('keyframes', []),
                emotion_timeline.get('keyframes', [])
            )
            
            # Step 5: Export face_rig video
            safe_print(f"    🎬 Exporting face_rig video...")
            video_path = self._retry_api_call(
                self._export_video,
                combined_timeline,
                audio_data['filename'],
                scene_number
            )
            
            safe_print(f"  ✅ Face_rig video complete: {Path(video_path).name}")
            
            return {
                'video_path': video_path,
                'audio_path': audio_path,
                'audio_duration': audio_duration,
                'mfa_timeline': mfa_timeline,
                'emotion_timeline': emotion_timeline,
                'combined_timeline': combined_timeline
            }
            
        except Exception as e:
            safe_print(f"  ❌ Face_rig generation failed for scene {scene_number}: {e}")
            raise RuntimeError(f"Failed to generate face_rig video for scene {scene_number}: {e}")
    
    def _generate_tts(self, transcript: str) -> Dict:
        """Generate audio using ElevenLabs via face_rig server"""
        endpoint = f"{self.face_rig_url}/generate-tts"
        
        response = requests.post(
            endpoint,
            json={
                "transcript": transcript,
                "voice_id": self.voice_id
            },
            timeout=300  # 5 minutes - increased for longer narrations
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"TTS generation failed: {response.status_code} - {response.text}")
        
        data = response.json()
        
        # Download audio file from face_rig server to local storage
        audio_filename = data['filename']
        audio_url = f"{self.face_rig_url}/audio/{audio_filename}"
        
        # Save to local audio directory
        local_audio_path = self.audio_dir / audio_filename
        
        audio_response = requests.get(audio_url, timeout=300)  # 5 minutes for audio download
        if audio_response.status_code != 200:
            raise RuntimeError(f"Failed to download audio from face_rig server: {audio_response.status_code}")
        
        with open(local_audio_path, 'wb') as f:
            f.write(audio_response.content)
        
        # Update data with local path
        data['path'] = str(local_audio_path)
        
        return data
    
    def _generate_alignment(self, audio_path: str, transcript: str) -> Dict:
        """Generate MFA phoneme alignment via face_rig server"""
        endpoint = f"{self.face_rig_url}/generate-alignment"
        
        # Read audio file for upload
        with open(audio_path, 'rb') as audio_file:
            files = {'audio': audio_file}
            data = {'transcript': transcript}
            
            response = requests.post(
                endpoint,
                files=files,
                data=data,
                timeout=1200  # 20 minutes - MFA can take a very long time for longer audio
            )
        
        if response.status_code != 200:
            raise RuntimeError(f"MFA alignment failed: {response.status_code} - {response.text}")
        
        return response.json()
    
    def _generate_emotions(self, transcript: str, phoneme_timeline: List[Dict], total_duration_ms: int) -> Dict:
        """Generate emotion keyframes via face_rig server"""
        endpoint = f"{self.face_rig_url}/generate-emotions"
        
        response = requests.post(
            endpoint,
            json={
                "transcript": transcript,
                "phoneme_timeline": phoneme_timeline,
                "total_duration_ms": total_duration_ms
            },
            timeout=300  # 5 minutes - AI emotion generation
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Emotion generation failed: {response.status_code} - {response.text}")
        
        return response.json()
    
    def _combine_timelines(self, phoneme_keyframes: List[Dict], emotion_keyframes: List[Dict]) -> List[Dict]:
        """
        Combine phoneme and emotion timelines into a single timeline.
        Emotion keyframes take precedence for expression changes.
        """
        combined = []
        
        # Create a map of emotion keyframes by time
        emotion_map = {kf['time_ms']: kf for kf in emotion_keyframes}
        
        # Add all phoneme keyframes, potentially overridden by emotions
        for phoneme_kf in phoneme_keyframes:
            time_ms = phoneme_kf['time_ms']
            
            # Check if there's an emotion at this time (within 50ms tolerance)
            emotion_kf = None
            for emo_time in emotion_map.keys():
                if abs(emo_time - time_ms) < 50:
                    emotion_kf = emotion_map[emo_time]
                    break
            
            if emotion_kf:
                # Merge emotion with phoneme
                combined_kf = {
                    'time_ms': time_ms,
                    'target_expr': emotion_kf['target_expr'],
                    'phoneme': phoneme_kf.get('phoneme', ''),
                    'transition_duration_ms': 300
                }
            else:
                # Just phoneme
                combined_kf = {
                    'time_ms': time_ms,
                    'target_expr': phoneme_kf.get('target_expr', 'neutral'),
                    'phoneme': phoneme_kf.get('phoneme', ''),
                    'transition_duration_ms': 100
                }
            
            combined.append(combined_kf)
        
        # Add any emotion keyframes that weren't near phoneme keyframes
        phoneme_times = set(kf['time_ms'] for kf in phoneme_keyframes)
        for emo_time, emo_kf in emotion_map.items():
            # Check if this emotion time is far from any phoneme time
            is_unique = True
            for phoneme_time in phoneme_times:
                if abs(emo_time - phoneme_time) < 50:
                    is_unique = False
                    break
            
            if is_unique:
                combined.append({
                    'time_ms': emo_time,
                    'target_expr': emo_kf['target_expr'],
                    'transition_duration_ms': 500
                })
        
        # Sort by time
        combined.sort(key=lambda kf: kf['time_ms'])
        
        return combined
    
    def _export_video(self, combined_timeline: List[Dict], audio_filename: str, scene_number: int) -> str:
        """Export face_rig video via face_rig server"""
        endpoint = f"{self.face_rig_url}/export-video"
        
        # Get audio URL relative to face_rig server
        audio_url = f"/audio/{audio_filename}"
        
        response = requests.post(
            endpoint,
            json={
                "combined_timeline": combined_timeline,
                "audio_url": audio_url,
                "format": "mp4",
                "fps": 24
            },
            timeout=1200  # 20 minutes - video export can take a long time rendering frames
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Video export failed: {response.status_code} - {response.text}")
        
        # Save the video file
        video_path = self.video_dir / f"face_rig_scene_{scene_number}.mp4"
        with open(video_path, 'wb') as f:
            f.write(response.content)
        
        return str(video_path)
    
    def get_audio_duration(self, audio_path: str) -> float:
        """Get duration of audio file in seconds"""
        try:
            with wave.open(str(audio_path), 'rb') as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                duration = frames / float(rate)
                return duration
        except Exception as e:
            safe_print(f"Warning: Could not get audio duration: {e}")
            return 0.0
    
    def check_server_health(self) -> bool:
        """Check if face_rig server is available"""
        try:
            response = requests.get(f"{self.face_rig_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


if __name__ == "__main__":
    # Test the integrator
    integrator = FaceRigIntegrator()
    
    # Check server health
    if not integrator.check_server_health():
        print("❌ Face_rig server is not running at http://localhost:8000")
        print("   Start it with: cd face_rig && python server.py")
        exit(1)
    
    print("✅ Face_rig server is running")
    
    # Test with a simple scene
    test_narration = "Hello! This is a test of the face rig integration system."
    
    try:
        result = integrator.generate_scene_video(test_narration, 1)
        print(f"\n✅ Test successful!")
        print(f"   Video: {result['video_path']}")
        print(f"   Audio: {result['audio_path']}")
        print(f"   Duration: {result['audio_duration']:.2f}s")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")

