# Character Animation System - Deployment

This directory contains everything needed to deploy the character animation system to production.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                         PRODUCTION                            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────┐         ┌─────────────┐      ┌──────────────┐│
│  │           │  HTTPS  │             │ HTTP │              ││
│  │  Browser  │────────▶│   Backend   │─────▶│  S3 Bucket   ││
│  │ (React)   │         │  (FastAPI)  │      │   (Frames)   ││
│  │           │◀────────│             │      │              ││
│  └───────────┘  JSON   └─────────────┘      └──────────────┘│
│                                                               │
│  Vercel/Netlify      Railway/Render         AWS S3           │
│  (Static Host)       (Container/VM)         (CDN Optional)   │
└──────────────────────────────────────────────────────────────┘
```

## Quick Links

- **[QUICKSTART_DEPLOYMENT.md](QUICKSTART_DEPLOYMENT.md)** - 30-minute deployment guide
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Comprehensive deployment documentation
- **[docker-compose.yml](docker-compose.yml)** - Docker configuration for local/server deployment
- **[upload_to_s3.py](upload_to_s3.py)** - Script to upload frames to S3

## Files in This Directory

### Application Files
- `server.py` - FastAPI backend server
- `expressions.json` - Character configuration (expressions, poses, transitions)
- `textgrid_to_timeline.py` - Convert phoneme alignment to animation timeline
- `watercolor-rig/` - React frontend (Timeline Director UI)

### Deployment Files
- `Dockerfile` - Container image for backend
- `docker-compose.yml` - Local development and production deployment
- `requirements.txt` - Python dependencies
- `.dockerignore` - Files to exclude from Docker build
- `env.example` - Environment variable template
- `upload_to_s3.py` - S3 upload script

### Documentation
- `QUICKSTART_DEPLOYMENT.md` - 30-minute quick start guide
- `DEPLOYMENT.md` - Full deployment documentation
- `README_DEPLOYMENT.md` - This file

### Asset Generation (Not Needed in Production)
- `generate_all_assets.py` - Master script to generate all frames
- `generate_extreme_expressions.py` - Generate expression endpoints
- `generate_head_tilts.py` - Generate pose variations
- `generate_all_sequences.py` - Generate transition animations
- `generate_neutral_pose_sequences.py` - Generate pose-to-pose transitions

## Deployment Workflow

### 1. Asset Generation (Local, One-Time)

Generate all animation frames locally before deployment:

```bash
python generate_all_assets.py \
  --base-image watercolor_boy_greenscreen.png \
  --endpoints-dir frames/endpoints \
  --sequences-dir frames/sequences \
  --size 1024x1536 \
  --max-workers 4
```

**Output**: 
- `frames/endpoints/` - ~50 PNG images (expression + pose combinations)
- `frames/sequences/` - ~200 directories with 5 frames each (~1000 PNGs total)
- Total size: ~2-5 GB

### 2. Upload to S3

Upload pre-generated frames to S3 for production serving:

```bash
python upload_to_s3.py \
  --bucket my-character-assets \
  --region us-east-1 \
  --prefix frames/
```

### 3. Deploy Backend

Choose your platform:

**Docker** (any VPS):
```bash
cp env.example .env
# Edit .env
docker-compose up -d
```

**Railway/Render/Heroku** (Platform-as-a-Service):
- Connect GitHub repo
- Set environment variables
- Deploy automatically

### 4. Deploy Frontend

Build and deploy static React app:

```bash
cd watercolor-rig
echo "VITE_API_BASE_URL=https://your-backend-url" > .env
npm install && npm run build
npx vercel --prod  # or netlify, etc.
```

## Environment Variables

### Backend (Required)

```bash
USE_S3=true                           # Enable S3 for frames
S3_BUCKET=my-character-assets         # Your S3 bucket name
S3_REGION=us-east-1                   # AWS region
S3_PREFIX=frames/                     # Prefix in bucket
OPENAI_API_KEY=sk-proj-...            # OpenAI API key
CORS_ORIGINS=https://yourdomain.com   # Frontend URL
```

### Backend (Optional)

```bash
S3_BASE_URL=https://cdn.yourdomain.com  # Custom CDN URL
ELEVENLABS_API_KEY=...                  # For TTS
AWS_ACCESS_KEY_ID=...                   # If not using IAM role
AWS_SECRET_ACCESS_KEY=...               # If not using IAM role
```

### Frontend (Required)

```bash
VITE_API_BASE_URL=https://api.yourdomain.com  # Backend API URL
```

## Features

### Timeline Director UI
- Upload audio (WAV)
- Upload transcript (TXT/LAB)
- Auto-generate phoneme timeline (Montreal Forced Aligner)
- AI emotion planning (GPT-4)
- Manual pose/expression keyframe editing
- Real-time preview with audio sync
- Video export (MP4/WebM)

### Backend API
- `/timelines` - List available animation sequences
- `/timeline/{path_id}` - Get timeline manifest
- `/frames/{path_id}/{filename}` - Serve frame (redirects to S3)
- `/generate-emotions` - AI emotion planning
- `/generate-alignment` - Auto phoneme alignment (MFA)
- `/generate-tts` - Text-to-speech (ElevenLabs)
- `/export-video` - Render and export video

## Performance

### Current Benchmarks
- **Frame serving**: Instant (302 redirect to S3)
- **Timeline loading**: <100ms
- **AI emotion planning**: 2-5s (GPT-4)
- **Video export**: ~1x real-time (30s audio = 30s render)

### Scaling
- Backend: Stateless, horizontally scalable
- Frontend: Static files, infinitely scalable on CDN
- Frames: S3 handles unlimited requests

## Cost Estimates (AWS)

| Component | Dev/Test | Production (1k users/day) |
|-----------|----------|---------------------------|
| S3 Storage (5GB) | $0.12/mo | $0.12/mo |
| S3 Requests | $0.01/mo | $0.36/mo |
| Data Transfer | $0.09/mo | $8.50/mo |
| Backend (Railway) | Free tier | $10-20/mo |
| Frontend (Vercel) | Free tier | Free tier |
| **Total** | **~$0.25/mo** | **~$20-40/mo** |

## Troubleshooting

### Frames return 404
- Check S3 bucket is public
- Verify `S3_BUCKET` and `S3_PREFIX` match your bucket structure

### CORS errors
- Add your frontend domain to `CORS_ORIGINS` backend env var
- Make sure it's the full URL with protocol: `https://app.yourdomain.com`

### Video export fails
- Ensure `ffmpeg` is installed (included in Dockerfile)
- Check backend has sufficient disk space for temp files

### OpenAI API errors
- Verify `OPENAI_API_KEY` is valid
- Check OpenAI account has available credits

## Security

✅ **Implemented**:
- Environment-based configuration (no hardcoded keys)
- CORS restrictions
- S3 bucket policy (public read only on frames prefix)
- Docker secrets support

⚠️ **Recommended**:
- Use IAM roles instead of access keys (EC2, ECS, Lambda)
- Enable CloudFront signed URLs for private content
- Rotate API keys regularly
- Use HTTPS for all production endpoints

## Monitoring

Add these for production:

- **Uptime**: [UptimeRobot](https://uptimerobot.com) (free)
- **Errors**: [Sentry](https://sentry.io) (has free tier)
- **Analytics**: [Plausible](https://plausible.io) or Google Analytics
- **Logs**: Platform-specific (Railway, Render, AWS CloudWatch)

## Next Steps

1. Read [QUICKSTART_DEPLOYMENT.md](QUICKSTART_DEPLOYMENT.md) for fast deployment
2. Or read [DEPLOYMENT.md](DEPLOYMENT.md) for detailed options
3. Generate assets locally with `generate_all_assets.py`
4. Upload to S3 with `upload_to_s3.py`
5. Deploy backend and frontend
6. Test end-to-end workflow

## Support

For issues or questions:
1. Check [DEPLOYMENT.md](DEPLOYMENT.md) troubleshooting section
2. Review backend logs for error messages
3. Test API endpoints with `curl` to isolate issues

## License

See main repository LICENSE file.


