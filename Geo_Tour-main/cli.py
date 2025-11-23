#!/usr/bin/env python3
"""
Simple command-line interface for the video generation pipeline
"""
import argparse
import sys
from pathlib import Path

from pipeline import VideoPipeline
from config import ensure_directories


def main():
    parser = argparse.ArgumentParser(
        description="Generate AI videos from text prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py "Explain how photosynthesis works"
  python cli.py "Tour of the solar system" --output my_video.mp4
  python cli.py "How rainbows form" --video-provider replicate --tts-provider openai
  python cli.py "Explain water cycle" --video-provider replicate --use-storyboard
  
For testing without paid APIs:
  python cli.py "Test prompt" --video-provider mock --tts-provider mock
        """
    )
    
    parser.add_argument(
        "prompt",
        help="Text prompt describing the video you want to create"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output filename (default: auto-generated from title)",
        default=None
    )
    
    parser.add_argument(
        "--openai-key",
        help="OpenAI API key (or set OPENAI_API_KEY env var)",
        default=None
    )
    
    parser.add_argument(
        "--video-key",
        help="Video generation API key (or set VIDEO_API_KEY env var)",
        default=None
    )
    
    parser.add_argument(
        "--tts-key",
        help="Text-to-speech API key (or set TTS_API_KEY env var)",
        default=None
    )
    
    parser.add_argument(
        "--video-provider",
        choices=["mock", "replicate", "runwayml", "pika", "stability"],
        default="mock",
        help="Video generation provider (default: mock, use 'replicate' for Replicate API)"
    )
    
    parser.add_argument(
        "--tts-provider",
        choices=["mock", "elevenlabs", "openai", "google"],
        default="mock",
        help="Text-to-speech provider (default: mock)"
    )
    
    parser.add_argument(
        "--use-storyboard",
        action="store_true",
        help="Generate storyboard images before video generation (for image-to-video mode)"
    )
    
    parser.add_argument(
        "--show-metadata",
        action="store_true",
        help="Display full project metadata after generation"
    )
    
    args = parser.parse_args()
    
    # Ensure directories exist
    ensure_directories()
    
    print("\n" + "=" * 70)
    print("🎬 AI VIDEO GENERATOR - CLI")
    print("=" * 70)
    
    # Initialize pipeline
    try:
        pipeline = VideoPipeline(
            openai_api_key=args.openai_key,
            video_api_key=args.video_key,
            tts_api_key=args.tts_key,
            video_provider=args.video_provider,
            tts_provider=args.tts_provider,
            use_storyboard=args.use_storyboard
        )
        print("✅ Pipeline initialized")
    except Exception as e:
        print(f"❌ Failed to initialize pipeline: {e}")
        print("\nMake sure you have set your API keys:")
        print("  - Set OPENAI_API_KEY environment variable (required), or")
        print("  - Use --openai-key flag")
        print("  - Set REPLICATE_API_KEY or VIDEO_API_KEY for video generation (if using replicate provider)")
        sys.exit(1)
    
    # Generate video
    try:
        result = pipeline.run(args.prompt, args.output)
        
        if result["success"]:
            print("\n" + "=" * 70)
            print("✨ SUCCESS!")
            print("=" * 70)
            print(f"Video saved to: {result['video_path']}")
            print(f"Title: {result['script']['title']}")
            print(f"Scenes: {len(result['scenes']['scenes'])}")
            
            if args.show_metadata:
                print("\n📊 Full Project Metadata:")
                print("-" * 70)
                import json
                print(json.dumps(result['project_data'], indent=2))
            
            return 0
        else:
            print("\n" + "=" * 70)
            print("❌ GENERATION FAILED")
            print("=" * 70)
            print(f"Error: {result.get('error', 'Unknown error')}")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Generation cancelled by user")
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
