# Setup Guide - Expense Tracker Bot

Complete guide to set up and deploy your automated expense tracker.

## Prerequisites

- Python 3.11+
- Google Cloud account
- Telegram account
- Basic command line knowledge

## Part 1: Get API Keys & Credentials

### 1. Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the prompts:
   - Choose a name (e.g., "My Expense Tracker")
   - Choose a username (e.g., "my_expense_tracker_bot")
4. Copy the API token provided
5. Save it - you'll need it as `TELEGRAM_BOT_TOKEN`

### 2. Get Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Select or create a Google Cloud project
4. Copy the API key
5. Save it - you'll need it as `GEMINI_API_KEY`

### 3. Set Up Google Sheets

#### Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create new one)
3. Navigate to "IAM & Admin" → "Service Accounts"
4. Click "Create Service Account"
5. Fill in details:
   - Name: `expense-tracker-bot`
   - Description: "Service account for expense tracker"
6. Click "Create and Continue"
7. Skip role assignment (click "Continue")
8. Click "Done"

#### Generate JSON Key

1. Click on the service account you just created
2. Go to "Keys" tab
3. Click "Add Key" → "Create new key"
4. Choose JSON format
5. Click "Create" - file will download
6. Save this file as `credentials/service_account.json`

#### Create and Share Google Sheet

1. Go to [Google Sheets](https://sheets.google.com/)
2. Create a new spreadsheet
3. Name it (e.g., "Expense Tracker")
4. Copy the Sheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
   ```
5. Click "Share" button
6. Add the service account email (found in the JSON file: `client_email`)
7. Give it "Editor" permissions
8. Click "Send"

## Part 2: Local Development Setup

### 1. Clone and Setup

```bash
cd /Users/claudio/Documents/Personal/expense_tracker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env file
nano .env  # or use your preferred editor
```

Fill in your credentials:
```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
GEMINI_API_KEY=AIzaSyD...your...key...here
GOOGLE_SHEETS_ID=1BxiMVs...your...sheet...id...here
GOOGLE_APPLICATION_CREDENTIALS=./credentials/service_account.json
ENVIRONMENT=development
LOG_LEVEL=INFO
PORT=8080
```

### 3. Add Service Account Credentials

```bash
# Create credentials directory
mkdir -p credentials

# Move your downloaded service account JSON
mv ~/Downloads/your-project-*.json credentials/service_account.json
```

### 4. Test Locally (Polling Mode)

```bash
# Run bot in polling mode (for local testing)
python -m src.main --mode=polling
```

You should see:
```
✅ Bot is running in polling mode. Press Ctrl+C to stop.
```

### 5. Test the Bot

1. Open Telegram
2. Search for your bot by username
3. Send `/start`
4. Try commands:
   - `/help` - View help
   - Send a photo of a receipt
   - `/check_expense` - View recent expenses

## Part 3: Deploy to GCP Cloud Run

### 1. Install Google Cloud SDK

```bash
# macOS
brew install google-cloud-sdk

# Or download from: https://cloud.google.com/sdk/docs/install
```

### 2. Initialize GCP

```bash
# Login to GCP
gcloud auth login

# Create or select project
gcloud projects create expense-tracker-bot --name="Expense Tracker"
# Or use existing:
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Set default region
gcloud config set run/region us-central1
```

### 3. Store Secrets in Secret Manager

```bash
# Store Telegram bot token
echo -n "YOUR_TELEGRAM_BOT_TOKEN" | gcloud secrets create telegram-bot-token --data-file=-

# Store Gemini API key
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create gemini-api-key --data-file=-

# Grant Cloud Run access to secrets
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format="value(projectNumber)")

gcloud secrets add-iam-policy-binding telegram-bot-token \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 4. Deploy with Script

```bash
# Make deploy script executable (already done)
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

Or deploy manually:

```bash
# Build and push container
gcloud builds submit --tag gcr.io/$(gcloud config get-value project)/expense-tracker:latest

# Deploy to Cloud Run
gcloud run deploy expense-tracker-bot \
  --image gcr.io/$(gcloud config get-value project)/expense-tracker:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60s \
  --min-instances 0 \
  --max-instances 10 \
  --set-secrets TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,GEMINI_API_KEY=gemini-api-key:latest \
  --set-env-vars GOOGLE_SHEETS_ID=YOUR_SHEET_ID,ENVIRONMENT=production
```

### 5. Configure Telegram Webhook

Get your service URL:
```bash
SERVICE_URL=$(gcloud run services describe expense-tracker-bot --region us-central1 --format='value(status.url)')
echo $SERVICE_URL
```

Set webhook:
```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$SERVICE_URL/webhook" \
  -d "allowed_updates=[\"message\",\"edited_message\"]"
```

Verify webhook:
```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

## Part 4: Verify Deployment

### 1. Check Cloud Run Logs

```bash
gcloud run logs read expense-tracker-bot --limit 50
```

### 2. Test the Bot

1. Send a message to your bot
2. Upload a receipt photo
3. Check `/check_expense`
4. Verify data appears in Google Sheets

### 3. Monitor Health

```bash
# Visit health endpoint
curl https://YOUR_SERVICE_URL/health

# Check webhook info
curl https://YOUR_SERVICE_URL/webhook_info
```

## Troubleshooting

### Bot not responding

**Check webhook status:**
```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

**Delete webhook (to test locally):**
```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook"
```

### Image processing errors

- Ensure image is clear and well-lit
- Check Gemini API quota/billing
- Review Cloud Run logs for errors

### Google Sheets errors

- Verify service account has edit access
- Check `GOOGLE_SHEETS_ID` is correct
- Ensure service account JSON is valid

### Cloud Run deployment issues

```bash
# Check service status
gcloud run services describe expense-tracker-bot --region us-central1

# View logs
gcloud run logs read expense-tracker-bot --limit 100

# Check secrets are accessible
gcloud secrets versions access latest --secret=telegram-bot-token
```

## Cost Monitoring

### View current usage:
```bash
# Cloud Run metrics
gcloud run services describe expense-tracker-bot --format="yaml(status.traffic)"

# Check billing
open https://console.cloud.google.com/billing
```

### Set budget alerts:

1. Go to [Billing](https://console.cloud.google.com/billing)
2. Click "Budgets & alerts"
3. Create budget (e.g., $5/month)
4. Set alert at 50%, 90%, 100%

## Maintenance

### Update deployment:

```bash
# Make code changes, then:
./deploy.sh
```

### View logs:

```bash
# Last 50 entries
gcloud run logs read expense-tracker-bot --limit 50

# Follow logs in real-time
gcloud run logs tail expense-tracker-bot
```

### Rollback:

```bash
# List revisions
gcloud run revisions list --service expense-tracker-bot

# Rollback to previous
gcloud run services update-traffic expense-tracker-bot \
  --to-revisions=PREVIOUS_REVISION=100
```

## Next Steps

- Set up Cloud Monitoring alerts
- Add more expense categories
- Implement budget tracking
- Create monthly expense reports
- Add WhatsApp integration
- Build web dashboard

## Support

- Cloud Run docs: https://cloud.google.com/run/docs
- Telegram Bot API: https://core.telegram.org/bots/api
- Gemini API: https://ai.google.dev/docs

---

**Congratulations! Your expense tracker is now live! 🎉**
