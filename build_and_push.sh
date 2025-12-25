#!/bin/bash
# Build Docker image locally and push to Google Container Registry
# Use this for faster deployments (no need to upload source code)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🏗️  Building and Pushing Docker Image${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker.${NC}"
    exit 1
fi

# Get project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ No GCP project set. Run: gcloud config set project PROJECT_ID${NC}"
    exit 1
fi

# Variables
IMAGE_NAME="gcr.io/$PROJECT_ID/expense-tracker"
IMAGE_TAG="${1:-latest}"  # Allow custom tag, default to 'latest'

echo -e "${YELLOW}📦 Project: $PROJECT_ID${NC}"
echo -e "${YELLOW}🏷️  Tag: $IMAGE_TAG${NC}"

# Configure Docker authentication
echo -e "${YELLOW}🔑 Configuring Docker authentication...${NC}"
gcloud auth configure-docker --quiet

# Build image for Cloud Run (linux/amd64 platform)
echo -e "${YELLOW}🔨 Building Docker image for linux/amd64...${NC}"
docker build --platform linux/amd64 -t $IMAGE_NAME:$IMAGE_TAG .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Image built: $IMAGE_NAME:$IMAGE_TAG${NC}"

# Also tag as latest if using custom tag
if [ "$IMAGE_TAG" != "latest" ]; then
    docker tag $IMAGE_NAME:$IMAGE_TAG $IMAGE_NAME:latest
    echo -e "${GREEN}✅ Also tagged as: $IMAGE_NAME:latest${NC}"
fi

# Push to GCR
echo -e "${YELLOW}📤 Pushing to Google Container Registry...${NC}"
docker push $IMAGE_NAME:$IMAGE_TAG

if [ "$IMAGE_TAG" != "latest" ]; then
    docker push $IMAGE_NAME:latest
fi

echo -e "${GREEN}✅ Image pushed successfully!${NC}"
echo -e "${GREEN}🎉 Ready to deploy to Cloud Run${NC}"
echo -e "\nNext step:"
echo -e "  ${YELLOW}gcloud run deploy expense-tracker-bot --image $IMAGE_NAME:$IMAGE_TAG${NC}"
