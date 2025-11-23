#!/usr/bin/env python3
"""
Start the Streamlit UI
"""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    print("🚀 Starting Streamlit UI...")
    print("📝 The app will open at http://localhost:8501")
    print("=" * 50)
    
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "app.py"],
            cwd=Path(__file__).parent
        )
    except KeyboardInterrupt:
        print("\n👋 Streamlit app stopped")
    except Exception as e:
        print(f"❌ Error starting Streamlit: {e}")
        print("\n💡 Try running manually:")
        print("   streamlit run app.py")
        sys.exit(1)

