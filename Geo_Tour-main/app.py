"""
Simple Streamlit UI for the video generation pipeline
"""
import streamlit as st
import json
from pathlib import Path
import os

from pipeline import VideoPipeline
from config import OUTPUT_DIR, ensure_directories


# Page configuration
st.set_page_config(
    page_title="AI Video Generator",
    page_icon="🎬",
    layout="wide"
)

# Initialize directories
ensure_directories()

# Session state initialization
if 'pipeline' not in st.session_state:
    st.session_state.pipeline = None
if 'result' not in st.session_state:
    st.session_state.result = None
if 'generating' not in st.session_state:
    st.session_state.generating = False
if 'use_storyboard' not in st.session_state:
    st.session_state.use_storyboard = False
if 'progress_step' not in st.session_state:
    st.session_state.progress_step = 0
if 'progress_status' not in st.session_state:
    st.session_state.progress_status = ""
if 'progress_details' not in st.session_state:
    st.session_state.progress_details = ""


def progress_callback(step, total_steps, status, details=""):
    """Callback function for pipeline progress updates"""
    st.session_state.progress_step = step
    st.session_state.progress_status = status
    st.session_state.progress_details = details
    # Note: We avoid st.rerun() here to prevent infinite loops
    # Streamlit will automatically update the UI when state changes

def initialize_pipeline():
    """Initialize the pipeline with API keys from environment"""
    # Pre-flight checks
    errors = []
    warnings = []
    # Ensure ffmpeg path is available in process PATH if provided
    ffmpeg_path = "C:/Users/tanne/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.0.1-full_build/bin"
    if ffmpeg_path:
        try:
            to_add = ffmpeg_path
            if os.path.isfile(ffmpeg_path):
                to_add = str(Path(ffmpeg_path).parent)
            if to_add not in os.environ.get("PATH", ""):
                os.environ["PATH"] = to_add + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass
    
    # Check API keys
    openai_key = os.getenv("OPENAI_API_KEY")
    replicate_key = os.getenv("REPLICATE_API_KEY") or os.getenv("VIDEO_API_KEY")
    tts_key = os.getenv("TTS_API_KEY") or os.getenv("ELEVEN_LABS_API_KEY")
    
    if not openai_key:
        errors.append("❌ **OPENAI_API_KEY** not found in environment variables")
    elif not openai_key.startswith("sk-"):
        warnings.append("⚠️ OPENAI_API_KEY doesn't look valid (should start with 'sk-')")
    
    if not replicate_key:
        errors.append("❌ **REPLICATE_API_KEY** or **VIDEO_API_KEY** not found in environment variables")
    elif not replicate_key.startswith("r8_"):
        warnings.append("⚠️ Replicate API key doesn't look valid (should start with 'r8_')")
    
    # Check directories
    try:
        from config import OUTPUT_DIR, TEMP_DIR
        OUTPUT_DIR.mkdir(exist_ok=True)
        TEMP_DIR.mkdir(exist_ok=True)
        # Test write permission
        test_file = OUTPUT_DIR / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        errors.append(f"Directory check failed: {e}")
    # Check required modules
    missing_modules = []
    try:
        import openai
    except ImportError:
        missing_modules.append("openai")
    try:
        import replicate
    except ImportError:
        missing_modules.append("replicate")
    try:
        import requests
    except ImportError:
        missing_modules.append("requests")
    
    if missing_modules:
        errors.append(f"❌ **Missing dependencies**: Install with `pip install {' '.join(missing_modules)}`")
    
    # Show warnings if any
    if warnings:
        for warning in warnings:
            st.warning(warning)
    
    # Show errors and stop if critical issues
    if errors:
        st.error("**Cannot initialize pipeline - fix these issues:**")
        for error in errors:
            st.markdown(error)
        st.markdown("---")
        st.markdown("**Quick fixes:**")
        st.markdown("1. Create a `.env` file in the project root with your API keys")
        st.markdown("2. Run `pip install -r requirements.txt` to install dependencies")
        st.markdown("3. Ensure you have write permissions in the project directory")
        return False
    
    # Try to initialize
    try:
        pipeline = VideoPipeline(
            openai_api_key=openai_key,
            video_api_key=replicate_key,
            tts_api_key=tts_key,
            tts_provider="elevenlabs",
            use_storyboard=st.session_state.get("use_storyboard", False),
            svd_model=st.session_state.get("svd_model"),
            sdxl_model=st.session_state.get("sdxl_model"),
            # Face rig is always enabled
            use_face_rig=True,
            face_rig_url=st.session_state.get("face_rig_url", "http://localhost:8000"),
            face_rig_voice_id=st.session_state.get("face_rig_voice_id", "yoZ06aMxZJJ28mfd3POQ")  # Default to Sam
        )
        st.session_state.pipeline = pipeline
        return True
    except ImportError as e:
        st.error(f"**Import Error**: Missing module - `{str(e)}`\n\nRun: `pip install -r requirements.txt`")
        return False
    except (IOError, OSError) as e:
        st.error(f"**File System Error**: `{type(e).__name__}: {str(e)}`\n\n**Likely causes:**\n- Output/temp directories are read-only\n- Disk is full\n- Permission denied\n\n**Fix:** Check directory permissions and disk space")
        return False
    except ValueError as e:
        st.error(f"**Configuration Error**: `{str(e)}`\n\n**Likely causes:**\n- Invalid API key format\n- Missing required configuration\n\n**Fix:** Check your `.env` file and API key formats")
        return False
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        st.error(f"**Initialization Failed**: `{error_type}: {error_msg}`")
        
        # Provide specific guidance based on error
        if "API" in error_msg or "key" in error_msg.lower():
            st.markdown("**This looks like an API key issue:**")
            st.markdown("1. Verify your API keys in `.env` are correct")
            st.markdown("2. Check that keys haven't expired")
            st.markdown("3. Ensure keys have proper permissions")
        elif "module" in error_msg.lower() or "import" in error_msg.lower():
            st.markdown("**This looks like a missing dependency:**")
            st.markdown("1. Run `pip install -r requirements.txt`")
            st.markdown("2. Restart the Streamlit app")
        else:
            st.markdown("**Troubleshooting steps:**")
            st.markdown("1. Check the error message above")
            st.markdown("2. Verify all dependencies are installed")
            st.markdown("3. Check your `.env` file configuration")
            st.markdown("4. Try restarting the Streamlit app")
        
        with st.expander("🔍 Technical Details (for debugging)"):
            import traceback
            st.code(traceback.format_exc(), language="python")
        return False


def generate_video(prompt):
    """Generate video from prompt"""
    st.session_state.generating = True
    st.session_state.progress_step = 0
    st.session_state.progress_status = "Starting..."
    st.session_state.progress_details = ""
    
    try:
        ns = st.session_state.get("num_scenes", 5)
        sd = st.session_state.get("scene_duration", 6)
        result = st.session_state.pipeline.run(prompt, num_scenes=ns, scene_duration=sd, progress_callback=progress_callback)
        st.session_state.result = result
        st.session_state.generating = False
        st.session_state.progress_step = 0
        st.session_state.progress_status = ""
        st.session_state.progress_details = ""
        return result
            
    except (IOError, OSError) as e:
        st.error(f"**File System Error During Generation**\n\n`{type(e).__name__}: {str(e)}`\n\n**This usually means:**\n- A file operation failed (read/write permission issue)\n- Output directory is not accessible\n- Disk space is full\n\n**Fix:**\n1. Check that the `output/` and `temp/` directories exist and are writable\n2. Ensure you have sufficient disk space\n3. Check file permissions in the project directory")
        st.session_state.generating = False
        st.session_state.progress_step = 0
        st.session_state.progress_status = ""
        st.session_state.progress_details = ""
        return None
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        
        st.error(f"**Generation Failed**\n\n`{error_type}: {error_msg}`")
        
        # Provide specific guidance
        if "I/O" in error_msg or "closed file" in error_msg.lower():
            st.markdown("**This is a file I/O error:**")
            st.markdown("1. The app tried to write to a file but it was closed or inaccessible")
            st.markdown("2. This can happen if Streamlit redirects stdout/stderr")
            st.markdown("3. **Workaround:** The generation may have actually succeeded - check the `output/` folder")
            st.markdown("4. Try generating again - this is often a transient issue")
        elif "API" in error_msg or "key" in error_msg.lower():
            st.markdown("**This looks like an API issue:**")
            st.markdown("1. Check your API keys are valid and not expired")
            st.markdown("2. Verify you have sufficient API credits/quota")
            st.markdown("3. Check your internet connection")
        elif "module" in error_msg.lower() or "import" in error_msg.lower():
            st.markdown("**Missing dependency:**")
            st.markdown("1. Run `pip install -r requirements.txt`")
            st.markdown("2. Restart the Streamlit app")
        else:
            st.markdown("**Troubleshooting:**")
            st.markdown("1. Check the error message above")
            st.markdown("2. Verify all dependencies are installed")
            st.markdown("3. Try generating with a simpler prompt")
            st.markdown("4. Check the `output/` folder - generation may have partially succeeded")
        
        with st.expander("🔍 Technical Details"):
            import traceback
            st.code(traceback.format_exc(), language="python")
        
        st.session_state.generating = False
        return None



# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # API Keys Status (loaded from .env file)
    with st.expander("🔑 API Keys Status", expanded=False):
        # Check which keys are loaded
        openai_key = os.getenv("OPENAI_API_KEY", "")
        replicate_key = os.getenv("REPLICATE_API_KEY") 
        eleven_labs_key= os.getenv("ELEVEN_LABS_API_KEY", "")
        
        # Show status for each key
        if openai_key:
            st.success("✅ OpenAI API Key: Loaded from environment")
        else:
            st.warning("⚠️ OpenAI API Key: Not found (set OPENAI_API_KEY in .env)")
        
        if replicate_key:
            st.success("✅ Replicate API Key: Loaded from environment")
        else:
            st.warning("⚠️ Replicate API Key: Not found (set REPLICATE_API_KEY in .env)")
        
        if eleven_labs_key:
            st.success("✅ Eleven Labs API Key: Loaded from environment")
        else:
            st.info("ℹ️ Eleven Labs API Key: Optional (set ELEVEN_LABS_API_KEY in .env)")
    
    # Provider Selection
    with st.expander("🎨 Providers", expanded=True):
        _replicate_key = os.getenv("REPLICATE_API_KEY") or os.getenv("VIDEO_API_KEY")
        _providers = ["replicate"]
        if not _replicate_key:
            st.error("Replicate API key not found. Please set REPLICATE_API_KEY in your .env file.")
        st.selectbox("Video Provider", _providers, index=0, key="video_provider", disabled=not _replicate_key)
        from config import STABILITY_MODEL, STORYBOARD_MODEL
        st.text_input("Image-to-Video Model (Replicate)", value=STABILITY_MODEL, key="svd_model")
        st.text_input("Text-to-Image Model (Replicate)", value=STORYBOARD_MODEL, key="sdxl_model")
        # Auto-default storyboard BEFORE widget instantiation to avoid Streamlit state errors
        if "use_storyboard" not in st.session_state and st.session_state.get("video_provider") == "replicate":
            st.session_state.use_storyboard = True
        st.checkbox(
            "Use Storyboard Generation",
            key="use_storyboard",
            help="Generate storyboard images first, then use image-to-video (better quality, slower)"
        )

    # Face Rig Settings
    with st.expander("🎭 Character Voice & Settings", expanded=True):
        st.text_input(
            "Face Rig Server URL",
            value="http://localhost:8000",
            key="face_rig_url",
            help="URL of the running face_rig server"
        )
        
        st.markdown("**Narrator Voice**")
        face_rig_voice_options = {
            "Sam (Male, Conversational)": "yoZ06aMxZJJ28mfd3POQ",  # Correct Sam voice ID
            "Rachel (Female, Calm)": "21m00Tcm4TlvDq8ikWAM",  # Rachel's voice ID
            "Bella (Female, Engaging)": "EXAVITQu4vr4xnSDxMaL",
            "Domi (Female, Confident)": "AZnzlk1XvdvUeBnXmlld",
            "Adam (Male, Deep)": "pNInz6obpgDQGcFmaJgB",
            "Antoni (Male, Young)": "ErXwobaYiN019PkySvjV",
        }
        selected_fr_voice = st.selectbox(
            "Choose Voice",
            list(face_rig_voice_options.keys()),
            index=0,  # Default to Sam
            key="face_rig_voice_name",
            help="This voice will be used for all narration and character animation"
        )
        st.session_state.face_rig_voice_id = face_rig_voice_options[selected_fr_voice]
        
        st.info("💡 Animated character with lip-sync will appear in bottom-right corner")

    
    # Initialize pipeline button
    if st.button("🚀 Initialize Pipeline", type="primary", use_container_width=True):
        with st.spinner("Initializing..."):
            if initialize_pipeline():
                st.success("✅ Pipeline ready!")
            else:
                st.error("❌ Initialization failed")
    
    # Status
    st.divider()
    if st.session_state.pipeline:
        st.success("✅ Pipeline Ready")
    else:
        st.warning("⚠️ Pipeline Not Initialized")

# Main content area
if not st.session_state.pipeline:
    st.info("👈 Configure and initialize the pipeline in the sidebar to get started")
else:
    # Input section
    st.header("📝 Video Prompt")
    
    # Initialize video_prompt if not set
    if "video_prompt" not in st.session_state:
        st.session_state.video_prompt = ""
    
    # Example texts
    example_texts = {
        "rainbow": "Explain how rainbows form when light passes through water droplets",
        "solar": "Give a tour of the planets in our solar system",
        "photosynthesis": "Explain how plants convert sunlight into energy through photosynthesis"
    }
    
    # Handle example selection from previous run
    if "selected_example" in st.session_state:
        example_key = st.session_state.selected_example
        if example_key in example_texts:
            st.session_state.video_prompt = example_texts[example_key]
        del st.session_state.selected_example
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        prompt = st.text_area(
            "Describe the video you want to create",
            height=100,
            key="video_prompt"
        )
        st.number_input("Number of scenes", min_value=1, max_value=20, value=5, step=1, key="num_scenes")
        st.number_input("Seconds per scene (max 12)", min_value=2, max_value=12, value=6, step=1, key="scene_duration")
    
    with col2:
        st.markdown("### Quick Examples")
        if st.button("🌈 Rainbow Formation", key="btn_rainbow"):
            st.session_state.selected_example = "rainbow"
            st.rerun()
        if st.button("🌍 Solar System", key="btn_solar"):
            st.session_state.selected_example = "solar"
            st.rerun()
        if st.button("🔬 Photosynthesis", key="btn_photosynthesis"):
            st.session_state.selected_example = "photosynthesis"
            st.rerun()
    
    # Progress tracking section
    if st.session_state.generating:
        st.header("⏳ Generation Progress")
        
        # Progress bar (6 steps with parallel generation)
        total_steps = 6
        progress_percent = (st.session_state.progress_step / total_steps) if st.session_state.progress_step > 0 else 0.01
        st.progress(progress_percent)
        
        # Status display
        col1, col2 = st.columns([1, 3])
        with col1:
            st.metric("Step", f"{st.session_state.progress_step}/{total_steps}")
        with col2:
            if st.session_state.progress_status:
                st.info(f"**{st.session_state.progress_status}**")
                if st.session_state.progress_details:
                    st.caption(st.session_state.progress_details)
        
        # Timeline visualization
        with st.expander("📋 Detailed Timeline", expanded=True):
            steps = [
                ("📝", "Script Generation", "Creating narrative structure"),
                ("🎬", "Scene Planning", "Breaking down into visual scenes"),
                ("🎨", "Storyboard Generation", "Creating visual storyboards"),
                ("🚀", "Parallel Scene Generation", "Character animation + video clips (parallel)"),
                ("🎙️", "Audio Assembly", "Combining character audio"),
                ("🎬", "Final Assembly", "Combining video with picture-in-picture")
            ]
            
            for i, (emoji, title, description) in enumerate(steps, 1):
                if i < st.session_state.progress_step:
                    st.success(f"✅ {emoji} **{title}** - Complete")
                elif i == st.session_state.progress_step or (isinstance(st.session_state.progress_step, float) and int(st.session_state.progress_step) == i - 1):
                    st.warning(f"⏳ {emoji} **{title}** - {description}")
                else:
                    st.text(f"⏸️ {emoji} **{title}** - Pending")
    
    # Generate button
    if st.button("🎬 Generate Video", type="primary", disabled=not prompt or st.session_state.generating):
        with st.spinner("Generating video... This may take a few minutes"):
            result = generate_video(prompt)

    # Results section
    if st.session_state.result:
        st.divider()
        result = st.session_state.result
        
        if result['success']:
            st.success("✨ Video generated successfully!")
            
            # Display results in tabs
            has_storyboard = bool(result.get('project_data', {}).get('steps', {}).get('storyboard'))
            if has_storyboard:
                tab1, tab2, tab3, tab_storyboard, tab4 = st.tabs(["📹 Video", "📄 Script", "🎬 Scenes", "🎨 Storyboard", "📊 Metadata"])
            else:
                tab1, tab2, tab3, tab4 = st.tabs(["📹 Video", "📄 Script", "🎬 Scenes", "📊 Metadata"])
                tab_storyboard = None
            
            with tab1:
                st.subheader("Generated Video")
                video_path = Path(result['video_path'])
                
                # Check if file exists and is a valid video
                if video_path.exists():
                    # Read video file as bytes for Streamlit
                    with open(video_path, 'rb') as f:
                        video_bytes = f.read()
                    st.video(video_bytes)
                    
                    # Download button
                    st.download_button(
                        label="⬇️ Download Video",
                        data=video_bytes,
                        file_name=video_path.name,
                        mime="video/mp4"
                    )
                else:
                    st.error(f"❌ Video file not found: {video_path}")
                    st.info(f"Expected path: {video_path.absolute()}")
            
            with tab2:
                st.subheader("Video Script")
                script = result['script']
                st.markdown(f"**Title:** {script['title']}")
                st.markdown("**Narration:**")
                st.code(script['script'])
            
            with tab3:
                st.subheader("Scene Breakdown")
                for scene in result['scenes']['scenes']:
                    with st.expander(f"Scene {scene['scene_number']} ({scene['duration']}s)"):
                        st.markdown(f"**Narration:** {scene['narration']}")
                        st.markdown(f"**Visual:** {scene['visual_description']}")
            
            if has_storyboard and tab_storyboard:
                with tab_storyboard:
                    st.subheader("Storyboard Images")
                    storyboard_images = result['project_data']['steps']['storyboard']
                    for i, img_path in enumerate(storyboard_images):
                        img_file = Path(img_path)
                        if img_file.exists() and img_file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                            st.image(str(img_file), caption=f"Scene {i+1}", use_container_width=True)
                        else:
                            st.text(f"Scene {i+1}: {img_path}")
            
            with tab4:
                st.subheader("Project Metadata")
                st.json(result['project_data'])
        else:
            st.error(f"❌ Generation failed: {result.get('error', 'Unknown error')}")

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>Built with OpenAI GPT-4, Streamlit, and AI video generation</p>
    <p><small>Configure API keys for full functionality</small></p>
</div>
""", unsafe_allow_html=True)
