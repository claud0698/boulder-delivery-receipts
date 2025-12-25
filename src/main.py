"""Main FastAPI application for expense tracker bot."""

import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from loguru import logger

from .config import settings
from .messaging.telegram_handler import TelegramHandler


# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.log_level
)


# Global telegram handler
telegram_handler: TelegramHandler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global telegram_handler

    # Startup
    logger.info("🚀 Starting Expense Tracker Bot")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Log Level: {settings.log_level}")

    # Initialize Telegram handler
    telegram_handler = TelegramHandler()

    # Create application
    telegram_app = telegram_handler.create_application()

    # Initialize bot
    await telegram_app.initialize()
    await telegram_app.bot.initialize()

    # Set webhook if in production
    if settings.is_production and settings.webhook_url:
        webhook_url = f"{settings.webhook_url}/webhook"
        logger.info(f"Setting webhook to: {webhook_url}")

        await telegram_app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "edited_message"]
        )

        webhook_info = await telegram_app.bot.get_webhook_info()
        logger.info(f"Webhook info: {webhook_info}")
    else:
        logger.info("Development mode - webhook not set")

    # Store app in state
    app.state.telegram_app = telegram_app
    app.state.telegram_handler = telegram_handler

    logger.info("✅ Bot initialized successfully")

    yield

    # Shutdown
    logger.info("Shutting down bot...")
    await telegram_app.shutdown()
    logger.info("Bot shut down complete")


# Create FastAPI app
app = FastAPI(
    title="Expense Tracker Bot",
    description="Automated expense tracking with AI",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Expense Tracker Bot",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {
        "status": "healthy",
        "environment": settings.environment
    }


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Webhook endpoint for Telegram updates.

    Telegram POSTs updates here when users send messages.
    """
    try:
        # Get update data
        data = await request.json()
        logger.debug(f"Received webhook update: {data}")

        # Convert to Telegram Update object
        telegram_app = request.app.state.telegram_app
        update = Update.de_json(data, telegram_app.bot)

        # Process the update
        await telegram_app.process_update(update)

        return {"ok": True}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return Response(status_code=500)


@app.get("/set_webhook")
async def set_webhook_endpoint(request: Request):
    """Manually set webhook (for testing/debugging)."""
    if not settings.webhook_url:
        return {"error": "WEBHOOK_URL not configured"}

    try:
        telegram_app = request.app.state.telegram_app
        webhook_url = f"{settings.webhook_url}/webhook"

        await telegram_app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "edited_message"]
        )

        webhook_info = await telegram_app.bot.get_webhook_info()

        return {
            "success": True,
            "webhook_url": webhook_url,
            "webhook_info": webhook_info.to_dict()
        }

    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return {"error": str(e)}


@app.get("/webhook_info")
async def get_webhook_info(request: Request):
    """Get current webhook information."""
    try:
        telegram_app = request.app.state.telegram_app
        webhook_info = await telegram_app.bot.get_webhook_info()

        return {
            "webhook_info": webhook_info.to_dict()
        }

    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        return {"error": str(e)}


# For local development with polling
async def run_polling():
    """Run bot in polling mode for local development."""
    global telegram_handler

    logger.info("🔄 Starting bot in polling mode (development)")

    telegram_handler = TelegramHandler()
    application = telegram_handler.create_application()

    # Initialize and start polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    logger.info("✅ Bot is running in polling mode. Press Ctrl+C to stop.")

    # Keep running
    import asyncio
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    import asyncio
    import argparse

    parser = argparse.ArgumentParser(description="Expense Tracker Bot")
    parser.add_argument(
        "--mode",
        choices=["polling", "webhook"],
        default="polling",
        help="Run mode: polling (local dev) or webhook (production)"
    )
    args = parser.parse_args()

    if args.mode == "polling":
        # Run with polling for local development
        asyncio.run(run_polling())
    else:
        # Run with uvicorn for webhook mode
        import uvicorn
        uvicorn.run(
            "src.main:app",
            host="0.0.0.0",
            port=settings.port,
            log_level=settings.log_level.lower(),
            reload=not settings.is_production
        )
