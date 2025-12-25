# Quick Start Guide

Get your expense tracker running in 10 minutes!

## Prerequisites

- Python 3.11+
- Telegram account
- Google account

## Step 1: Get API Keys (5 minutes)

### Telegram Bot Token
1. Open Telegram, search for `@BotFather`
2. Send: `/newbot`
3. Follow prompts, copy the token

### Gemini API Key
1. Visit: https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key

### Google Sheets Setup
1. Go to https://console.cloud.google.com
2. Create project → IAM & Admin → Service Accounts
3. Create service account, download JSON key
4. Create new Google Sheet
5. Share sheet with service account email (from JSON)
6. Copy sheet ID from URL

## Step 2: Configure (2 minutes)

```bash
cd expense_tracker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
nano .env  # Add your API keys
```

Edit `.env`:
```env
TELEGRAM_BOT_TOKEN=your_token_here
GEMINI_API_KEY=your_key_here
GOOGLE_SHEETS_ID=your_sheet_id
GOOGLE_APPLICATION_CREDENTIALS=./credentials/service_account.json
```

```bash
# Add service account JSON
mkdir -p credentials
mv ~/Downloads/your-service-account.json credentials/service_account.json
```

## Step 3: Run (1 minute)

```bash
# Test locally
python -m src.main --mode=polling
```

## Step 4: Test (2 minutes)

1. Open Telegram
2. Find your bot
3. Send `/start`
4. Send a receipt photo
5. Try `/check_expense`

## Deploy to Cloud Run (Optional)

See [SETUP.md](SETUP.md) for full deployment guide.

```bash
# Quick deploy
./deploy.sh
```

## Bot Commands

- `/start` - Welcome message
- `/help` - Show commands
- `/upload_expense` - Upload receipt (or just send photo)
- `/check_expense` - View 5 recent expenses

## Troubleshooting

**Bot not responding?**
- Check `.env` file has correct tokens
- Ensure bot is running (`python -m src.main --mode=polling`)

**Can't extract receipt?**
- Ensure image is clear
- Check Gemini API key is valid
- Try a different receipt

**Sheets error?**
- Verify service account has edit permission on sheet
- Check `GOOGLE_SHEETS_ID` in `.env`

## Next Steps

- Deploy to GCP Cloud Run for 24/7 availability
- Set up monthly budgets
- Add more categories
- Export expense reports

---

Need help? See [SETUP.md](SETUP.md) for detailed instructions.
