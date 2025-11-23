"""
Example configuration for Face Rig Integration

Copy this file to your pipeline initialization to customize face_rig settings.
"""

# Face Rig Server Configuration
FACE_RIG_CONFIG = {
    # Enable/disable face_rig integration
    "use_face_rig": True,
    
    # Face rig server URL
    "face_rig_url": "http://localhost:8000",
    
    # ElevenLabs voice ID for character narration
    # Available voices:
    # - "21m00Tcm4TlvDq8ikWAM": Sam (conversational male) - DEFAULT
    # - "EXAVITQu4vr4xnSDxMaL": Bella (conversational female)
    # - "AZnzlk1XvdvUeBnXmlld": Domi (strong, confident female)
    # - "pNInz6obpgDQGcFmaJgB": Adam (deep male)
    # - "ThT5KcBeYPX3keUQqHPh": Dorothy (pleasant British female)
    "face_rig_voice_id": "21m00Tcm4TlvDq8ikWAM",  # Sam voice
}

# Video Assembly Configuration
VIDEO_ASSEMBLY_CONFIG = {
    # Picture-in-Picture settings
    "pip_scale": 0.25,  # Scale factor for face_rig video (25% of main video width)
    "pip_position": "bottom_right",  # Position: bottom_right, bottom_left, top_right, top_left
    "pip_margin": 20,  # Margin from edges in pixels
    
    # Video quality settings
    "fps": 24,  # Frames per second
    "video_codec": "libx264",  # Video codec for MP4
    "audio_codec": "aac",  # Audio codec
    "crf": 23,  # Constant Rate Factor (lower = higher quality, 18-28 recommended)
}

# Face Rig Character Settings
CHARACTER_CONFIG = {
    # Default pose for character
    "default_pose": "center",  # Options: center, left, right
    
    # Emotion mapping (how AI maps text sentiment to emotions)
    "emotion_mapping": {
        "positive": "happy_soft",
        "negative": "concerned",
        "neutral": "neutral",
        "surprised": "surprised_ah"
    },
    
    # Emotion transition settings
    "emotion_transition_ms": 500,  # Time for emotion transitions
    "phoneme_transition_ms": 100,  # Time for phoneme transitions
}

# Scene Generation Settings
SCENE_CONFIG = {
    # Audio duration settings
    "use_face_rig_audio_duration": True,  # Adjust scene duration to match audio
    "min_scene_duration": 2,  # Minimum scene duration in seconds
    "max_scene_duration": 12,  # Maximum scene duration in seconds
    
    # Scene splitting
    "target_words_per_scene": 30,  # Target words per scene for optimal pacing
    "max_words_per_scene": 50,  # Maximum words per scene
}

# API Settings
API_CONFIG = {
    # Timeouts for various operations (in seconds)
    "tts_timeout": 120,  # TTS generation timeout
    "mfa_timeout": 300,  # MFA alignment timeout (scales with audio length)
    "emotion_timeout": 60,  # Emotion generation timeout
    "video_export_timeout": 600,  # Video export timeout
    
    # Retry settings
    "max_retries": 3,  # Maximum retries for failed API calls
    "retry_delay": 2,  # Delay between retries in seconds
}


# Usage Example
def create_pipeline_with_face_rig():
    """
    Example function showing how to create a pipeline with custom face_rig settings
    """
    from pipeline import VideoPipeline
    
    pipeline = VideoPipeline(
        # Standard settings
        openai_api_key="your-openai-key",
        video_api_key="your-replicate-key",
        tts_api_key="your-elevenlabs-key",
        
        # Face rig settings
        use_face_rig=FACE_RIG_CONFIG["use_face_rig"],
        face_rig_url=FACE_RIG_CONFIG["face_rig_url"],
        face_rig_voice_id=FACE_RIG_CONFIG["face_rig_voice_id"],
        
        # Other settings
        use_storyboard=True,
        video_provider="replicate",
        tts_provider="elevenlabs"
    )
    
    return pipeline


# Voice ID Reference
ELEVENLABS_VOICES = {
    # Male Voices
    "Sam": "21m00Tcm4TlvDq8ikWAM",  # Conversational, friendly
    "Adam": "pNInz6obpgDQGcFmaJgB",  # Deep, authoritative
    "Antoni": "ErXwobaYiN019PkySvjV",  # Well-rounded, young
    "Arnold": "VR6AewLTigWG4xSOukaG",  # Crisp, resonant
    "Josh": "TxGEqnHWrfWFTfGW9XjX",  # Young, casual
    
    # Female Voices
    "Bella": "EXAVITQu4vr4xnSDxMaL",  # Conversational, engaging
    "Domi": "AZnzlk1XvdvUeBnXmlld",  # Strong, confident
    "Dorothy": "ThT5KcBeYPX3keUQqHPh",  # Pleasant, British
    "Elli": "MF3mGyEYCl7XYWbV9V6O",  # Emotional, friendly
    "Rachel": "21m00Tcm4TlvDq8ikWAM",  # Calm, soothing
}

# Emotion to Expression Mapping
# This maps the AI-generated emotions to face_rig expressions
EMOTION_EXPRESSIONS = {
    "neutral": "neutral",
    "happy": "happy_soft",
    "sad": "concerned",
    "surprised": "surprised_ah",
    "worried": "concerned",
    "excited": "happy_soft",
    "concerned": "concerned",
    "calm": "neutral",
}

# Performance Tips
PERFORMANCE_CONFIG = {
    # For faster generation (lower quality)
    "fast_mode": {
        "use_storyboard": False,  # Skip storyboard generation
        "num_scenes": 3,  # Fewer scenes
        "scene_duration": 4,  # Shorter scenes
        "fps": 12,  # Lower FPS
    },
    
    # For best quality (slower)
    "quality_mode": {
        "use_storyboard": True,
        "num_scenes": 7,
        "scene_duration": 8,
        "fps": 24,
    },
    
    # Balanced mode
    "balanced_mode": {
        "use_storyboard": True,
        "num_scenes": 5,
        "scene_duration": 6,
        "fps": 24,
    }
}


if __name__ == "__main__":
    print("Face Rig Configuration Reference")
    print("=" * 70)
    print("\n📋 Available Configuration Options:")
    print("\n1. Face Rig Settings:")
    for key, value in FACE_RIG_CONFIG.items():
        print(f"   - {key}: {value}")
    
    print("\n2. Video Assembly Settings:")
    for key, value in VIDEO_ASSEMBLY_CONFIG.items():
        print(f"   - {key}: {value}")
    
    print("\n3. Available ElevenLabs Voices:")
    for voice_name, voice_id in ELEVENLABS_VOICES.items():
        print(f"   - {voice_name}: {voice_id}")
    
    print("\n4. Performance Modes:")
    for mode_name, mode_config in PERFORMANCE_CONFIG.items():
        print(f"\n   {mode_name}:")
        for key, value in mode_config.items():
            print(f"     - {key}: {value}")

