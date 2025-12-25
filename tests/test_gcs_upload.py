"""Test script for Google Cloud Storage upload."""

import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file from project root (override=True for testing)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

from src.storage.sheets_client import SheetsClient
from loguru import logger


def test_storage_upload():
    """Test uploading image to Google Cloud Storage."""
    logger.info("Starting Google Cloud Storage upload test...")

    # Initialize client
    client = SheetsClient()

    # Test with sample image
    sample_path = Path(__file__).parent.parent / "Samples" / "Sample1.jpeg"

    if not sample_path.exists():
        logger.error(f"Sample file not found: {sample_path}")
        return False

    logger.info(f"Test image: {sample_path}")

    # Test upload
    logger.info("\nUploading to Google Cloud Storage...")
    receipt_number = "TEST" + datetime.now().strftime("%H%M%S")
    weighing_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = weighing_datetime.split()[0]

    try:
        url = client.upload_image_to_storage(
            image_path=str(sample_path),
            receipt_number=receipt_number,
            weighing_datetime=weighing_datetime
        )

        if url:
            logger.success("\n✓ Image uploaded successfully!")
            logger.info(f"Filename: {date_str}_{receipt_number}.jpg")
            logger.info(f"Public URL: {url}")
            return True
        else:
            logger.error("✗ Upload returned empty URL")
            return False

    except Exception as e:
        logger.error(f"✗ Upload failed: {e}")
        return False


if __name__ == "__main__":
    success = test_storage_upload()
    sys.exit(0 if success else 1)
