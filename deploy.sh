#!/bin/bash
# Deployment script for GCP Cloud Run
# Builds Docker image locally then pushes to GCR

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Expense Tracker Bot to GCP Cloud Run${NC}"

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Please install it first.${NC}"
    exit 1
fi

# Get project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ No GCP project set. Run: gcloud config set project PROJECT_ID${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Project: $PROJECT_ID${NC}"

# Set variables
SERVICE_NAME="expense-tracker-bot"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/expense-tracker"
IMAGE_TAG="latest"

# Configure Docker to use gcloud as credential helper
echo -e "${YELLOW}🔑 Configuring Docker authentication...${NC}"
gcloud auth configure-docker --quiet

# Build Docker image locally
echo -e "${YELLOW}🔨 Building Docker image locally...${NC}"
docker build -t $IMAGE_NAME:$IMAGE_TAG .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker image built successfully${NC}"

# Push to Google Container Registry
echo -e "${YELLOW}📤 Pushing image to Google Container Registry...${NC}"
docker push $IMAGE_NAME:$IMAGE_TAG

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to push image to GCR!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Image pushed to GCR${NC}"

# Deploy to Cloud Run
echo -e "${YELLOW}🚢 Deploying to Cloud Run...${NC}"

# Note: Make sure to set these values or configure them in GCP Secret Manager
# You can pass GOOGLE_SHEETS_ID as an argument or set it as an environment variable
GOOGLE_SHEETS_ID=${GOOGLE_SHEETS_ID:-""}
GCS_BUCKET_NAME=${GCS_BUCKET_NAME:-"boulder-delivery-receipts-481203"}

gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME:$IMAGE_TAG \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60s \
  --min-instances 0 \
  --max-instances 10 \
  --concurrency 10 \
  --set-secrets TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,GEMINI_API_KEY=gemini-api-key:latest,GOOGLE_APPLICATION_CREDENTIALS=google-sheets-credentials:latest \
  --update-env-vars ENVIRONMENT=production,LOG_LEVEL=INFO,GOOGLE_SHEETS_ID=$GOOGLE_SHEETS_ID,GCS_BUCKET_NAME=$GCS_BUCKET_NAME

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Cloud Run deployment failed!${NC}"
    exit 1
fi

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)')

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo -e "${GREEN}🌐 Service URL: $SERVICE_URL${NC}"

# Prompt to set webhook
echo -e "\n${YELLOW}📡 To activate the bot, set the Telegram webhook:${NC}"
echo -e "curl -X POST \"https://api.telegram.org/bot\$TELEGRAM_BOT_TOKEN/setWebhook\" \\"
echo -e "  -d \"url=$SERVICE_URL/webhook\""

echo -e "\n${YELLOW}Or visit: $SERVICE_URL/set_webhook${NC}"

echo -e "\n${GREEN}🎉 Deployment Summary:${NC}"
echo -e "  • Image: $IMAGE_NAME:$IMAGE_TAG"
echo -e "  • Region: $REGION"
echo -e "  • Service: $SERVICE_NAME"
echo -e "  • URL: $SERVICE_URL"
