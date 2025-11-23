# Quick Start: Deploy to Production

**Goal**: Get your character animation system live in under 30 minutes.

## Prerequisites Checklist

- [ ] All animation frames generated (ran `generate_all_assets.py`)
- [ ] AWS account with S3 access
- [ ] OpenAI API key
- [ ] Domain name (optional, can use platform subdomain)

---

## Step 1: Upload Frames to S3 (10 min)

```bash
# Create S3 bucket
aws s3 mb s3://my-character-frames --region us-east-1

# Make frames publicly readable
aws s3api put-bucket-policy --bucket my-character-frames --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicRead",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::my-character-frames/frames/*"
  }]
}'

# Upload frames (takes ~10 minutes for 5GB)
cd face_rig
pip install boto3
python upload_to_s3.py --bucket my-character-frames --region us-east-1
```

✅ **Verify**: Visit `https://my-character-frames.s3.amazonaws.com/frames/sequences/neutral_to_happy_soft__center/025.png` in browser

---

## Step 2: Deploy Backend (10 min)

### Option A: AWS App Runner (Production-Ready)

**Prerequisites**: AWS CLI configured with appropriate credentials

```bash
cd face_rig

# 1. Create ECR repository
aws ecr create-repository \
  --repository-name character-animation-api \
  --region us-east-1

# 2. Create IAM role for ECR access
aws iam create-role \
  --role-name AppRunnerECRAccessRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "build.apprunner.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

aws iam attach-role-policy \
  --role-name AppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

# 3. Build and push Docker image (amd64 for App Runner)
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

docker buildx build \
  --platform linux/amd64 \
  -t ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/character-animation-api:latest \
  --load \
  .

docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/character-animation-api:latest

# 4. Create App Runner service
export ECR_ACCESS_ROLE=$(aws iam get-role --role-name AppRunnerECRAccessRole --query 'Role.Arn' --output text)

aws apprunner create-service \
  --service-name character-api \
  --region us-east-1 \
  --source-configuration "{
    \"ImageRepository\": {
      \"ImageIdentifier\": \"${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/character-animation-api:latest\",
      \"ImageRepositoryType\": \"ECR\",
      \"ImageConfiguration\": {
        \"Port\": \"8000\",
        \"RuntimeEnvironmentVariables\": {
          \"USE_S3\": \"true\",
          \"S3_BUCKET\": \"my-character-frames\",
          \"S3_REGION\": \"us-east-1\",
          \"S3_PREFIX\": \"frames/\",
          \"CORS_ORIGINS\": \"*\"
        }
      }
    },
    \"AuthenticationConfiguration\": {
      \"AccessRoleArn\": \"${ECR_ACCESS_ROLE}\"
    },
    \"AutoDeploymentsEnabled\": false
  }" \
  --instance-configuration '{
    "Cpu": "1024",
    "Memory": "2048"
  }' \
  --health-check-configuration '{
    "Protocol": "HTTP",
    "Path": "/health",
    "Interval": 10,
    "Timeout": 5,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 5
  }'

# Wait 5 minutes for deployment
echo "⏳ Waiting for service to deploy (5 min)..."
```

**Get your service URL**:
```bash
aws apprunner list-services --region us-east-1 --query 'ServiceSummaryList[?ServiceName==`character-api`].ServiceUrl' --output text
```

### Option B: Railway (Easiest)

1. Visit [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repo and set root directory to `face_rig`
4. Add environment variables:
   ```
   USE_S3=true
   S3_BUCKET=my-character-frames
   S3_REGION=us-east-1
   S3_PREFIX=frames/
   OPENAI_API_KEY=sk-proj-...
   CORS_ORIGINS=*
   ```
5. Railway auto-detects Dockerfile and deploys
6. Copy your Railway URL: `https://your-app.railway.app`

### Option C: Render (Free Tier Available)

1. Visit [render.com](https://render.com)
2. New → Web Service → Connect GitHub repo
3. Root directory: `face_rig`
4. Add environment variables (same as above)
5. Deploy
6. Copy your Render URL: `https://your-app.onrender.com`

### Option D: Docker on Your Server

```bash
cd face_rig
cp env.example .env
# Edit .env with your values
nano .env

docker-compose up -d
```

✅ **Verify**: `curl https://your-backend-url/health`

---

## Step 3: Deploy Frontend (10 min)

### Option A: Vercel (Recommended)

```bash
cd face_rig/watercolor-rig
echo "VITE_API_BASE_URL=https://your-backend-url" > .env
npm install
npm run build

# Deploy
npx vercel --prod
```

### Option B: Netlify

```bash
cd face_rig/watercolor-rig
echo "VITE_API_BASE_URL=https://your-backend-url" > .env
npm install
npm run build

# Deploy
npx netlify-cli deploy --prod --dir=dist
```

### Option C: Static Host (S3, GitHub Pages, etc.)

```bash
cd face_rig/watercolor-rig
echo "VITE_API_BASE_URL=https://your-backend-url" > .env
npm install
npm run build

# Upload dist/ to your static host
```

✅ **Verify**: Visit your frontend URL, try uploading audio and generating timeline

---

## Step 4: Update CORS (if needed)

If you get CORS errors, update backend environment:

```bash
# For Railway/Render: Update in dashboard
CORS_ORIGINS=https://your-frontend-url.vercel.app

# For Docker: Edit .env and restart
docker-compose restart backend
```

---

## Troubleshooting

### Frames don't load (404)
- Check S3 bucket is public: `aws s3api get-bucket-policy --bucket my-character-frames`
- Verify `S3_BUCKET` environment variable on backend

### CORS errors
- Add your frontend URL to `CORS_ORIGINS`: `https://your-app.vercel.app`
- Make sure there's no trailing slash

### Backend health check fails
- Check logs on your platform dashboard
- Verify all required environment variables are set

### OpenAI API errors
- Verify `OPENAI_API_KEY` is set correctly
- Check your OpenAI account has credits

---

## Production Checklist

- [ ] Backend deployed and health check passes
- [ ] Frontend deployed and connects to backend
- [ ] S3 frames load correctly in browser
- [ ] Upload audio and generate timeline works
- [ ] Preview animation works
- [ ] Video export works
- [ ] Custom domain configured (optional)
- [ ] CORS restricted to your domain (not `*`)
- [ ] Monitoring/logging configured

---

## Estimated Costs

**Free Tier (getting started)**:
- Backend: Railway free tier or Render free tier
- Frontend: Vercel/Netlify free tier (generous)
- S3: $0.25/month (under free tier limits for low traffic)
- **Total: $0-5/month**

**Production (1000 users/day)**:
- Backend: $10-20/month (Railway/Render paid tier)
- Frontend: Free (static hosting)
- S3 + CloudFront: $10-20/month
- **Total: $20-40/month**

---

## Next Steps

1. Add custom domain
2. Set up CloudFront CDN for S3 (faster, cheaper)
3. Enable monitoring (Railway/Render have built-in metrics)
4. Set up error tracking (Sentry, etc.)
5. Optimize: Convert PNGs to WebP (30% size reduction)

Full documentation: [DEPLOYMENT.md](DEPLOYMENT.md)


