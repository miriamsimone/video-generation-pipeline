#!/usr/bin/env python3
"""
Test script for face_rig integration
Verifies that the face_rig server is working and can generate character animations
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from face_rig_integrator import FaceRigIntegrator


def test_server_health():
    """Test if face_rig server is running"""
    print("=" * 70)
    print("TEST 1: Face Rig Server Health Check")
    print("=" * 70)
    
    integrator = FaceRigIntegrator()
    
    if integrator.check_server_health():
        print("✅ Face_rig server is running at http://localhost:8000")
        return True
    else:
        print("❌ Face_rig server is NOT running")
        print("\nTo start the server:")
        print("  cd ../face_rig")
        print("  python server.py")
        return False


def test_tts_generation():
    """Test TTS generation"""
    print("\n" + "=" * 70)
    print("TEST 2: TTS Generation")
    print("=" * 70)
    
    integrator = FaceRigIntegrator()
    
    try:
        test_text = "Hello! This is a test of the text to speech system."
        print(f"Generating audio for: '{test_text}'")
        
        result = integrator._generate_tts(test_text)
        
        print(f"✅ Audio generated successfully")
        print(f"   Filename: {result['filename']}")
        print(f"   Duration: {result.get('duration', 'unknown')}s")
        return True
        
    except Exception as e:
        print(f"❌ TTS generation failed: {e}")
        return False


def test_full_scene_generation():
    """Test complete scene generation with face_rig"""
    print("\n" + "=" * 70)
    print("TEST 3: Complete Scene Generation")
    print("=" * 70)
    
    integrator = FaceRigIntegrator()
    
    try:
        test_narration = "Welcome to this demonstration of the face rig integration system. This test will generate audio, align phonemes, create emotions, and export a video."
        
        print(f"Generating scene video...")
        print(f"Narration: '{test_narration[:80]}...'")
        print("\nThis will take 30-90 seconds...")
        
        result = integrator.generate_scene_video(test_narration, scene_number=1)
        
        print(f"\n✅ Scene generation successful!")
        print(f"   Video: {result['video_path']}")
        print(f"   Audio: {result['audio_path']}")
        print(f"   Duration: {result['audio_duration']:.2f}s")
        print(f"   Phoneme keyframes: {len(result['mfa_timeline'].get('keyframes', []))}")
        print(f"   Emotion keyframes: {len(result['emotion_timeline'].get('keyframes', []))}")
        
        # Verify files exist
        if Path(result['video_path']).exists():
            print(f"   ✓ Video file exists ({Path(result['video_path']).stat().st_size} bytes)")
        else:
            print(f"   ✗ Video file not found!")
            
        return True
        
    except Exception as e:
        print(f"❌ Scene generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_environment():
    """Check required environment variables"""
    print("\n" + "=" * 70)
    print("Environment Check")
    print("=" * 70)
    
    required_vars = {
        "OPENAI_API_KEY": "OpenAI API (for emotion generation)",
        "ELEVENLABS_API_KEY": "ElevenLabs API (for TTS)",
    }
    
    all_set = True
    for var, description in required_vars.items():
        if os.getenv(var):
            print(f"✅ {var}: Set")
        else:
            print(f"❌ {var}: Not set ({description})")
            all_set = False
    
    if not all_set:
        print("\nPlease set missing environment variables in your .env file")
    
    return all_set


def main():
    print("\n" + "=" * 70)
    print("FACE RIG INTEGRATION TEST SUITE")
    print("=" * 70 + "\n")
    
    # Check environment first
    if not check_environment():
        print("\n⚠️  Some environment variables are missing")
        print("Tests may fail without proper API keys")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Run tests
    results = []
    
    # Test 1: Server health
    results.append(("Server Health", test_server_health()))
    
    if not results[-1][1]:
        print("\n" + "=" * 70)
        print("⚠️  Cannot continue tests - face_rig server is not running")
        print("=" * 70)
        return
    
    # Test 2: TTS generation
    results.append(("TTS Generation", test_tts_generation()))
    
    # Test 3: Full scene generation (only if previous tests passed)
    if all(r[1] for r in results):
        print("\n⚠️  The next test will take 30-90 seconds and will consume API credits")
        print("   (ElevenLabs TTS + OpenAI GPT-4 + MFA processing)")
        response = input("\nRun full scene generation test? (y/n): ")
        if response.lower() == 'y':
            results.append(("Full Scene Generation", test_full_scene_generation()))
        else:
            print("Skipping full scene generation test")
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {test_name}")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    
    print(f"\nResults: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 All tests passed! Face rig integration is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    main()

