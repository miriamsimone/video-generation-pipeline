#!/bin/bash
set -e

echo "🚀 Starting character-animation-api..."

if [ "$USE_S3" = "true" ]; then
    echo "📦 S3 enabled: bucket=${S3_BUCKET}, region=${S3_REGION}"
    echo "   Manifests will be loaded on-demand from S3"
else
    echo "📁 Using local filesystem for frames"
fi

echo "🌟 Starting uvicorn server..."
exec uvicorn server:app --host 0.0.0.0 --port 8000

