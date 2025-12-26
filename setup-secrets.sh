#!/bin/bash
# Setup script for GCP Secret Manager
# Creates all required secrets from .env file

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔐 Setting up GCP Secret Manager secrets${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    exit 1
fi

# Load .env file
source .env

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

echo -e "${YELLOW}📦 Project: $PROJECT_ID${NC}\n"

# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2

    echo -e "${YELLOW}Processing secret: $secret_name${NC}"

    # Check if secret exists
    if gcloud secrets describe $secret_name &>/dev/null; then
        echo -e "  Secret exists, adding new version..."
        echo -n "$secret_value" | gcloud secrets versions add $secret_name --data-file=-
        echo -e "${GREEN}  ✅ Updated $secret_name${NC}"
    else
        echo -e "  Creating new secret..."
        echo -n "$secret_value" | gcloud secrets create $secret_name --data-file=-
        echo -e "${GREEN}  ✅ Created $secret_name${NC}"
    fi
}

# 1. Telegram Bot Token
echo -e "\n${YELLOW}[1/3] Telegram Bot Token${NC}"
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo -e "${RED}❌ TELEGRAM_BOT_TOKEN not found in .env${NC}"
    exit 1
fi
create_or_update_secret "telegram-bot-token" "$TELEGRAM_BOT_TOKEN"

# 2. Gemini API Key
echo -e "\n${YELLOW}[2/3] Gemini API Key${NC}"
if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${RED}❌ GEMINI_API_KEY not found in .env${NC}"
    exit 1
fi
create_or_update_secret "gemini-api-key" "$GEMINI_API_KEY"

# 3. Google Service Account Credentials
echo -e "\n${YELLOW}[3/3] Google Service Account Credentials${NC}"
if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo -e "${RED}❌ GOOGLE_APPLICATION_CREDENTIALS not found in .env${NC}"
    exit 1
fi

if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo -e "${RED}❌ Credentials file not found: $GOOGLE_APPLICATION_CREDENTIALS${NC}"
    exit 1
fi

# Check if secret exists
if gcloud secrets describe google-sheets-credentials &>/dev/null; then
    echo -e "  Secret exists, adding new version..."
    gcloud secrets versions add google-sheets-credentials --data-file="$GOOGLE_APPLICATION_CREDENTIALS"
    echo -e "${GREEN}  ✅ Updated google-sheets-credentials${NC}"
else
    echo -e "  Creating new secret..."
    gcloud secrets create google-sheets-credentials --data-file="$GOOGLE_APPLICATION_CREDENTIALS"
    echo -e "${GREEN}  ✅ Created google-sheets-credentials${NC}"
fi

# Grant Cloud Run service account access to secrets
echo -e "\n${YELLOW}🔑 Granting Cloud Run access to secrets...${NC}"

# Get the default compute service account
SERVICE_ACCOUNT=$(gcloud iam service-accounts list --filter="email:*-compute@developer.gserviceaccount.com" --format="value(email)" | head -1)

if [ -z "$SERVICE_ACCOUNT" ]; then
    echo -e "${YELLOW}⚠️  Could not find default compute service account.${NC}"
    echo -e "${YELLOW}   Secrets will be accessible, but you may need to grant permissions manually.${NC}"
else
    echo -e "  Service Account: $SERVICE_ACCOUNT"

    for secret in telegram-bot-token gemini-api-key google-sheets-credentials; do
        gcloud secrets add-iam-policy-binding $secret \
            --member="serviceAccount:$SERVICE_ACCOUNT" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet 2>/dev/null || true
    done
    echo -e "${GREEN}  ✅ Permissions granted${NC}"
fi

echo -e "\n${GREEN}✅ All secrets configured successfully!${NC}"
echo -e "${GREEN}You can now run: ./deploy.sh${NC}"
