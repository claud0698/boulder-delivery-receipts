#!/bin/bash
# Deployment script for GCP Cloud Run
# Builds Docker image locally then pushes to GCR

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Boulder Delivery Receipt Tracker to GCP Cloud Run${NC}"

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
SERVICE_NAME="boulder-delivery-bot"
REGION="asia-southeast1"  # Singapore - closest to Indonesia
IMAGE_NAME="gcr.io/$PROJECT_ID/boulder-delivery-tracker"
IMAGE_TAG="latest"

# Configure Docker to use gcloud as credential helper
echo -e "${YELLOW}🔑 Configuring Docker authentication...${NC}"
gcloud auth configure-docker --quiet

# Build Docker image locally with explicit platform
echo -e "${YELLOW}🔨 Building Docker image locally for linux/amd64...${NC}"
docker build --platform linux/amd64 -t $IMAGE_NAME:$IMAGE_TAG .

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

# Configuration values from .env
GOOGLE_SHEETS_ID="1JTPv5xww3pzi7b8gRptnpLYsYQq9-r0N6exmutiYhiA"
GCS_BUCKET_NAME="boulder-delivery-receipts-481203"

gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME:$IMAGE_TAG \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300s \
  --min-instances 0 \
  --max-instances 10 \
  --concurrency 5 \
  --cpu-throttling \
  --cpu-boost \
  --session-affinity \
  --set-secrets TELEGRAM_BOT_TOKEN=telegram-bot-token:latest \
  --update-env-vars ENVIRONMENT=production,LOG_LEVEL=INFO,GOOGLE_SHEETS_ID=$GOOGLE_SHEETS_ID,GCS_BUCKET_NAME=$GCS_BUCKET_NAME,GCP_PROJECT_ID=$PROJECT_ID,GCP_LOCATION=us-central1 \
  --remove-env-vars GOOGLE_APPLICATION_CREDENTIALS

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Cloud Run deployment failed!${NC}"
    exit 1
fi

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)')

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo -e "${GREEN}🌐 Service URL: $SERVICE_URL${NC}"

# Automatically set Telegram webhook via Telegram API
echo -e "\n${YELLOW}📡 Setting Telegram webhook...${NC}"

# Load bot token from .env file
if [ -f .env ]; then
    BOT_TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" .env | cut -d '=' -f2)

    if [ -n "$BOT_TOKEN" ]; then
        WEBHOOK_URL="$SERVICE_URL/webhook"
        WEBHOOK_RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}")

        # Check if webhook was set successfully
        if echo "$WEBHOOK_RESPONSE" | grep -q '"ok":true'; then
            echo -e "${GREEN}✅ Webhook set successfully: $WEBHOOK_URL${NC}"
        else
            echo -e "${RED}❌ Failed to set webhook:${NC}"
            echo -e "${RED}$WEBHOOK_RESPONSE${NC}"
        fi
    else
        echo -e "${RED}❌ TELEGRAM_BOT_TOKEN not found in .env${NC}"
    fi
else
    echo -e "${RED}❌ .env file not found${NC}"
fi

# Update .env file with the webhook URL
echo -e "\n${YELLOW}📝 Updating .env file with webhook URL...${NC}"
if [ -f .env ]; then
    # Use sed to update the WEBHOOK_URL line
    if grep -q "^WEBHOOK_URL=" .env; then
        # Update existing line
        sed -i.bak "s|^WEBHOOK_URL=.*|WEBHOOK_URL=$SERVICE_URL/webhook|" .env && rm .env.bak
        echo -e "${GREEN}✅ .env updated with new webhook URL${NC}"
    else
        # Add new line
        echo "WEBHOOK_URL=$SERVICE_URL/webhook" >> .env
        echo -e "${GREEN}✅ Added webhook URL to .env${NC}"
    fi
fi

echo -e "\n${GREEN}🎉 Deployment Summary:${NC}"
echo -e "  • Image: $IMAGE_NAME:$IMAGE_TAG"
echo -e "  • Region: $REGION"
echo -e "  • Service: $SERVICE_NAME"
echo -e "  • URL: $SERVICE_URL"
echo -e "  • Webhook: $SERVICE_URL/webhook"
echo -e "\n${GREEN}✅ Bot is now live! Send a message to your Telegram bot to test.${NC}"
