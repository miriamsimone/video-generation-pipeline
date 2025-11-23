# Deployment Guide

This guide covers deploying the character animation system to production, including S3 storage for frames and hosting the backend and frontend.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [S3 Setup and Frame Upload](#s3-setup-and-frame-upload)
4. [Backend Deployment](#backend-deployment)
5. [Frontend Deployment](#frontend-deployment)
6. [Environment Configuration](#environment-configuration)
7. [Deployment Options](#deployment-options)
8. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)

---

## Overview

The deployment architecture consists of:

- **S3 Bucket**: Hosts all pre-generated animation frames (PNG images)
- **Backend API**: FastAPI server that serves timelines, handles TTS, alignment, and video export
- **Frontend**: React app (Vite) for the Timeline Director UI

```
┌─────────────┐
│   Browser   │
│  (Frontend) │
└──────┬──────┘
       │
       │ API Calls
       ▼
┌─────────────┐      ┌─────────────┐
│   Backend   │─────▶│  S3 Bucket  │
│  (FastAPI)  │      │   (Frames)  │
└─────────────┘      └─────────────┘
```

---

## Prerequisites

### Required Tools

- Python 3.11+
- Node.js 18+ (for frontend)
- AWS Account with S3 access
- Docker (optional, for containerized deployment)

### Required API Keys

- **OpenAI API Key**: For emotion planning (`OPENAI_API_KEY`)
- **ElevenLabs API Key** (optional): For TTS generation (`ELEVENLABS_API_KEY`)

### Generated Assets

Before deployment, you must generate all animation frames locally:

```bash
cd face_rig

# Generate all assets (expressions, poses, transitions)
python generate_all_assets.py \
  --base-image watercolor_boy_greenscreen.png \
  --endpoints-dir frames/endpoints \
  --sequences-dir frames/sequences \
  --size 1024x1536 \
  --max-workers 4
```

This will create:
- `frames/endpoints/`: Expression and pose endpoint images
- `frames/sequences/`: All transition animation sequences

---

## S3 Setup and Frame Upload

### 1. Create S3 Bucket

```bash
# Using AWS CLI
aws s3 mb s3://your-character-assets --region us-east-1

# Enable public read access (for direct browser access)
aws s3api put-public-access-block \
  --bucket your-character-assets \
  --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# Set bucket policy for public read
cat > bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::your-character-assets/frames/*"
    }
  ]
}
EOF

aws s3api put-bucket-policy \
  --bucket your-character-assets \
  --policy file://bucket-policy.json
```

**Optional: Set up CloudFront CDN** for better performance and lower costs:

```bash
# Create CloudFront distribution pointing to S3
aws cloudfront create-distribution \
  --origin-domain-name your-character-assets.s3.amazonaws.com \
  --default-root-object index.html
```

### 2. Upload Frames to S3

```bash
cd face_rig

# Install boto3 if not already installed
pip install boto3

# Dry run to preview what will be uploaded
python upload_to_s3.py \
  --bucket your-character-assets \
  --region us-east-1 \
  --prefix frames/ \
  --dry-run

# Upload all frames
python upload_to_s3.py \
  --bucket your-character-assets \
  --region us-east-1 \
  --prefix frames/

# Optional: Upload expressions.json config
python upload_to_s3.py \
  --bucket your-character-assets \
  --region us-east-1 \
  --prefix frames/ \
  --upload-config
```

**Upload Progress**: The script will show progress for each file. A typical full asset set is ~2-5 GB and takes 10-30 minutes depending on your connection.

---

## Backend Deployment

### Option 1: Docker (Recommended)

1. **Create environment file**:

```bash
cd face_rig
cp env.example .env

# Edit .env with your values
nano .env
```

Required variables:
```env
USE_S3=true
S3_BUCKET=your-character-assets
S3_REGION=us-east-1
S3_PREFIX=frames/

OPENAI_API_KEY=sk-proj-...
ELEVENLABS_API_KEY=your-key  # Optional

CORS_ORIGINS=https://yourdomain.com
```

2. **Build and run with Docker Compose**:

```bash
docker-compose up -d
```

3. **Verify deployment**:

```bash
curl http://localhost:8000/health
# Should return: {"status":"ok"}

curl http://localhost:8000/timelines | head
# Should list available timelines
```

### Option 2: Direct Python (Development/Small Scale)

1. **Install dependencies**:

```bash
cd face_rig
pip install -r requirements.txt
```

2. **Set environment variables**:

```bash
export USE_S3=true
export S3_BUCKET=your-character-assets
export S3_REGION=us-east-1
export S3_PREFIX=frames/
export OPENAI_API_KEY=sk-proj-...
export CORS_ORIGINS=https://yourdomain.com
```

3. **Run server**:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

### Option 3: Cloud Platforms

#### **AWS Elastic Beanstalk**

```bash
# Install EB CLI
pip install awsebcli

# Initialize EB application
eb init -p python-3.11 character-animation-api

# Create environment with environment variables
eb create production \
  --envvars USE_S3=true,S3_BUCKET=your-bucket,OPENAI_API_KEY=sk-...

# Deploy
eb deploy
```

#### **Google Cloud Run**

```bash
# Build container
gcloud builds submit --tag gcr.io/PROJECT_ID/character-api

# Deploy
gcloud run deploy character-api \
  --image gcr.io/PROJECT_ID/character-api \
  --platform managed \
  --region us-central1 \
  --set-env-vars USE_S3=true,S3_BUCKET=your-bucket,OPENAI_API_KEY=sk-...
```

#### **Heroku**

```bash
# Create app
heroku create your-character-api

# Set environment variables
heroku config:set USE_S3=true S3_BUCKET=your-bucket OPENAI_API_KEY=sk-...

# Deploy
git push heroku main
```

#### **Railway / Render / Fly.io**

All of these platforms support Docker deployment. Simply:
1. Connect your Git repository
2. Set environment variables in their dashboard
3. Deploy

---

## Frontend Deployment

### 1. Configure API URL

```bash
cd face_rig/watercolor-rig

# Copy environment example
cp env.example .env

# Edit with your backend URL
echo "VITE_API_BASE_URL=https://api.yourdomain.com" > .env
```

### 2. Build Frontend

```bash
npm install
npm run build
```

This creates a `dist/` directory with static files.

### 3. Deploy Static Files

#### **Option A: Vercel** (Recommended)

```bash
npm install -g vercel
vercel --prod
```

Or connect your GitHub repo at [vercel.com](https://vercel.com).

#### **Option B: Netlify**

```bash
npm install -g netlify-cli
netlify deploy --prod --dir=dist
```

Or drag-and-drop the `dist` folder at [netlify.com](https://netlify.com).

#### **Option C: AWS S3 + CloudFront**

```bash
# Upload to S3
aws s3 sync dist/ s3://your-frontend-bucket --delete

# Set bucket as website
aws s3 website s3://your-frontend-bucket --index-document index.html

# Create CloudFront distribution for HTTPS
aws cloudfront create-distribution \
  --origin-domain-name your-frontend-bucket.s3-website-us-east-1.amazonaws.com
```

#### **Option D: GitHub Pages**

```bash
# Install gh-pages
npm install -g gh-pages

# Deploy
gh-pages -d dist
```

---

## Environment Configuration

### Backend Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `USE_S3` | Yes | `false` | Enable S3 for frame serving |
| `S3_BUCKET` | Yes* | - | S3 bucket name |
| `S3_REGION` | No | `us-east-1` | AWS region |
| `S3_PREFIX` | No | `frames/` | Prefix for frames in bucket |
| `S3_BASE_URL` | No | - | Custom CDN URL (e.g., CloudFront) |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `ELEVENLABS_API_KEY` | No | - | ElevenLabs API key (for TTS) |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins |
| `AWS_ACCESS_KEY_ID` | No** | - | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | No** | - | AWS credentials |

\* Required when `USE_S3=true`  
\** Not needed if using IAM role (recommended for EC2, ECS, Lambda)

### Frontend Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | Yes | `http://localhost:8000` | Backend API URL |

---

## Deployment Options

### Recommended: Serverless + Static Hosting

**Best for**: Most use cases, automatic scaling, low maintenance

- **Backend**: AWS Lambda (via API Gateway) or Google Cloud Run
- **Frontend**: Vercel or Netlify
- **Frames**: S3 + CloudFront CDN

**Pros**: Auto-scaling, pay-per-use, minimal ops  
**Cons**: Cold starts (mitigated with provisioned concurrency)

### Traditional: VM/Container Hosting

**Best for**: Predictable costs, long-running processes

- **Backend**: EC2, Digital Ocean Droplet, or GCP Compute Engine
- **Frontend**: Same server (nginx) or separate static host
- **Frames**: S3 + CloudFront CDN

**Pros**: No cold starts, full control  
**Cons**: Manual scaling, always-on costs

### Kubernetes

**Best for**: Enterprise, multi-service deployments

Deploy using Helm charts and Kubernetes manifests. See `k8s/` directory (create if needed).

---

## Monitoring and Troubleshooting

### Health Check

```bash
curl https://api.yourdomain.com/health
```

Expected response:
```json
{"status": "ok"}
```

### Common Issues

#### 1. **CORS Errors**

**Symptom**: Browser console shows "blocked by CORS policy"

**Fix**: Ensure `CORS_ORIGINS` includes your frontend domain:
```bash
export CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

#### 2. **Frames Not Loading (404)**

**Symptom**: Animation doesn't play, browser shows 404 for frame images

**Fixes**:
- Verify S3 bucket policy allows public read
- Check `S3_BUCKET` and `S3_PREFIX` environment variables
- Test S3 URL directly: `https://your-bucket.s3.amazonaws.com/frames/sequences/neutral_to_happy_soft__center/025.png`

#### 3. **OpenAI API Errors**

**Symptom**: Emotion generation fails

**Fixes**:
- Verify `OPENAI_API_KEY` is set and valid
- Check OpenAI account has credits
- Review logs for specific error messages

#### 4. **Video Export Fails**

**Symptom**: Export button returns error

**Fixes**:
- Ensure `ffmpeg` is installed in backend environment
- Check disk space for temporary files
- Verify audio file was uploaded successfully

### Logs

**Docker**:
```bash
docker-compose logs -f backend
```

**Cloud Platform**: Check platform-specific logging (CloudWatch, Cloud Logging, etc.)

### Performance Optimization

1. **Enable CloudFront CDN** for S3 to reduce latency and costs
2. **Use WebM format** for exports (smaller than MP4)
3. **Set aggressive caching headers** for frame images (already configured in upload script)
4. **Consider image optimization**: Convert PNGs to WebP for ~30% size reduction

---

## Security Best Practices

1. **Never commit API keys**: Use environment variables
2. **Use IAM roles** instead of access keys when possible (EC2, Lambda, etc.)
3. **Restrict S3 bucket policy** to only the frames prefix
4. **Use HTTPS** for all production deployments
5. **Set CORS_ORIGINS** to specific domains (not `*`) in production
6. **Rotate API keys** regularly
7. **Enable CloudFront signed URLs** for private content if needed

---

## Scaling Considerations

### Current Limits

- **Concurrent Users**: Backend can handle ~100 concurrent timeline playback users on a single instance
- **Video Export**: CPU-intensive, limit concurrent exports or use job queue
- **Frame Storage**: ~2-5 GB for full character rig

### Scaling Strategies

1. **Backend**: 
   - Horizontal scaling with load balancer
   - Separate video export to background workers (Celery + Redis)
   
2. **Frontend**: Static files, scales infinitely on CDN

3. **S3**: No scaling needed, handles unlimited requests

---

## Cost Estimates (AWS)

### Minimal Usage (Development/Testing)
- S3 Storage (5 GB): $0.12/month
- S3 Requests (1k/day): $0.01/month
- CloudFront (1 GB transfer): $0.09/month
- Lambda (10k invocations): Free tier
- **Total**: ~$0.25/month

### Production (1000 users/day)
- S3 Storage (5 GB): $0.12/month
- S3 Requests (100k/day): $0.36/month
- CloudFront (100 GB transfer): $8.50/month
- Lambda/Fargate: $10-30/month
- **Total**: ~$20-40/month

---

## Next Steps

1. ✅ Generate all animation assets locally
2. ✅ Upload frames to S3
3. ✅ Deploy backend with S3 configuration
4. ✅ Deploy frontend with backend API URL
5. ✅ Test end-to-end: upload audio, generate timeline, preview, export
6. 🚀 Go live!

For questions or issues, check the [main README](README.md) or [open an issue](https://github.com/your-repo/issues).


