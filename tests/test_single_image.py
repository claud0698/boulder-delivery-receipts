#!/usr/bin/env python3
"""Test single image processing flow."""

import asyncio
import os
import sys
from pathlib import Path

from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.gemini_client import GeminiClient  # noqa: E402
from src.storage.sheets_client import SheetsClient  # noqa: E402
from src.models.delivery import DeliveryRecord  # noqa: E402


async def main():
    """Test single image processing flow."""
    logger.info("=" * 60)
    logger.info("SINGLE IMAGE PROCESSING TEST")
    logger.info("=" * 60)

    try:
        # Initialize clients
        sheets_client = SheetsClient()
        gemini_client = GeminiClient()

        # Test image (relative to tests folder)
        test_image = Path(__file__).parent / "Samples" / "Sample1.jpeg"
        if not test_image.exists():
            logger.error(f"Test image not found: {test_image}")
            return 1

        test_image = str(test_image)
        logger.info(f"Using test image: {test_image}")

        # Step 1: Upload to GCS
        logger.info("\n[1/5] Uploading image to GCS...")
        import time
        temp_receipt_id = f"test_{int(time.time())}"
        temp_datetime = time.strftime("%Y-%m-%d %H:%M:%S")

        receipt_url, gcs_uri = await asyncio.to_thread(
            sheets_client.upload_image_to_storage,
            image_path=test_image,
            receipt_number=temp_receipt_id,
            weighing_datetime=temp_datetime
        )
        logger.info(f"✅ Uploaded to: {gcs_uri}")
        logger.info(f"   Public URL: {receipt_url}")

        # Step 2: Extract data using GCS URI
        logger.info("\n[2/5] Extracting receipt data using GCS URI...")
        receipt_data, confidence, token_usage = await asyncio.to_thread(
            gemini_client.extract_receipt_data,
            gcs_uri=gcs_uri
        )

        if receipt_data is None:
            logger.error("❌ Failed to extract receipt data")
            return 1

        logger.info(f"✅ Receipt Number: {receipt_data.receipt_number}")
        logger.info(f"   Material: {receipt_data.material_name}")
        logger.info(f"   Gross Weight: {receipt_data.gross_weight} ton")
        logger.info(f"   Empty Weight: {receipt_data.empty_weight} ton")
        logger.info(f"   Net Weight: {receipt_data.net_weight} ton")
        logger.info(f"   Vehicle: {receipt_data.vehicle_number}")
        logger.info(f"   Confidence: {confidence:.2%}")

        if token_usage:
            logger.info(
                f"   Tokens: {token_usage.get('total_token_count', 0)} "
                f"(prompt: {token_usage.get('prompt_token_count', 0)}, "
                f"output: {token_usage.get('candidates_token_count', 0)})"
            )

        # Step 3: Create delivery record (material_type now in receipt_data)
        logger.info("\n[3/4] Creating delivery record...")
        delivery = DeliveryRecord.from_receipt_data(
            receipt=receipt_data,
            confidence=confidence,
            receipt_url=receipt_url,
            notes="Test - Single Image"
        )
        logger.info(f"✅ Delivery record created")
        logger.info(f"   Material Type: {delivery.material_type}")

        # Step 4: Save to Sheets
        logger.info("\n[4/4] Saving to Google Sheets...")
        logger.info("   ⚠️  Skipped - uncomment below to actually save")
        logger.info("   This prevents test data from being saved to production")

        # Uncomment to actually save to Google Sheets:
        # success = await asyncio.to_thread(
        #     sheets_client.append_delivery,
        #     delivery
        # )
        # if success:
        #     logger.info("✅ Saved to Google Sheets")
        # else:
        #     logger.error("❌ Failed to save to Sheets")
        #     return 1

        logger.info("\n" + "=" * 60)
        logger.info("✅ SINGLE IMAGE TEST PASSED")
        logger.info("=" * 60)
        return 0

    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
