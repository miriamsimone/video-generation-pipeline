"""
Audio generation module - converts script to voiceover
"""
import requests
from pathlib import Path
from config import TTS_API_KEY, AUDIO_FORMAT, TEMP_DIR


def safe_print(*args, **kwargs):
    """Safely print messages, handling closed file errors in Streamlit"""
    try:
        print(*args, **kwargs)
    except (IOError, OSError, ValueError):
        # Silently fail if stdout is closed (Streamlit context)
        pass


class AudioGenerator:
    def __init__(self, api_key=None, provider="elevenlabs", voice_id=None):
        self.api_key = api_key or TTS_API_KEY
        self.provider = provider
        self.voice_id = voice_id
        self.providers = {
            "elevenlabs": self._generate_elevenlabs,
            "openai": self._generate_openai,
            "google": self._generate_google,
            "mock": self._generate_mock,
        }
        if self.provider not in self.providers:
            raise ValueError(f"TTS provider '{self.provider}' not supported. Available: {list(self.providers.keys())}")
    
    def generate(self, script_data, output_dir=None):
        """
        Generate voiceover audio from script
        
        Args:
            script_data (dict): Script with narration text
            output_dir (Path): Directory to save audio
            
        Returns:
            str: Path to generated audio file
        """
        output_dir = output_dir or TEMP_DIR
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        safe_print("🎤 Generating voiceover...")
        
        generator_func = self.providers[self.provider]
        audio_path = generator_func(
            text=script_data['script'],
            output_dir=output_dir
        )
        
        safe_print(f"✅ Voiceover generated: {Path(audio_path).name}")
        return audio_path
    
    def _generate_elevenlabs(self, text, output_dir):
        """Generate audio using ElevenLabs API"""
        if not self.api_key:
            raise ValueError("No API key provided for TTS generation. Please set TTS_API_KEY in your .env file.")
        voice_id = self.voice_id if self.voice_id else "Lny4bN2CTZWgKZAgIHKa"
        endpoint = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        response = requests.post(
            endpoint,
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json"
            },
            json={
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5
                }
            }
        )
        
        if response.status_code == 200:
            audio_path = output_dir / f"voiceover.{AUDIO_FORMAT}"
            with open(audio_path, 'wb') as f:
                f.write(response.content)
            return str(audio_path)
        else:
            raise RuntimeError(f"ElevenLabs API error: {response.status_code} - {response.text}")
    
    def _generate_openai(self, text, output_dir):
        """Generate audio using OpenAI TTS"""
        raise NotImplementedError("OpenAI TTS implementation not yet available. Please use 'elevenlabs' provider.")
    
    def _generate_google(self, text, output_dir):
        """Generate audio using Google Cloud TTS"""
        raise NotImplementedError("Google TTS implementation not yet available. Please use 'elevenlabs' provider.")

    def _generate_mock(self, text, output_dir):
        """Generate a mock audio file for testing"""
        audio_path = output_dir / f"voiceover.{AUDIO_FORMAT}"
        with open(audio_path, 'w') as f:
            f.write("mock audio")
        return str(audio_path)


if __name__ == "__main__":
    # Test the audio generator
    generator = AudioGenerator(provider="elevenlabs")
    test_script = {
        "title": "Test Video",
        "script": "This is a test voiceover for the video pipeline."
    }
    audio = generator.generate(test_script)
    print(f"Generated audio: {audio}")
