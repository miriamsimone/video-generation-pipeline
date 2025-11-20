#!/bin/bash
# Start the OpenSeeFace server with proper virtual environment

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv_osf" ]; then
    echo "❌ Virtual environment not found!"
    echo "Run: python3.13 -m venv venv_osf"
    echo "Then: source venv_osf/bin/activate && pip install -r osf_requirements.txt"
    exit 1
fi

echo "🚀 Starting OpenSeeFace server..."
echo ""
echo "📍 Server will be available at:"
echo "   http://localhost:9000"
echo "   ws://localhost:9000/ws/tracking"
echo ""
echo "💡 To stop: Press Ctrl+C"
echo ""

# Activate virtual environment and run server
source venv_osf/bin/activate
uvicorn osf_server:app --host 0.0.0.0 --port 9000

