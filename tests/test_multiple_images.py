#!/usr/bin/env python3
"""Test multiple images processing flow (batch)."""

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
    """Test multiple images processing flow."""
    logger.info("=" * 60)
    logger.info("MULTIPLE IMAGES PROCESSING TEST (BATCH)")
    logger.info("=" * 60)

    try:
        # Initialize clients
        sheets_client = SheetsClient()
        gemini_client = GeminiClient()

        # Test images (relative to tests folder)
        test_dir = Path(__file__).parent / "Samples"
        test_images = [
            str(test_dir / "Sample1.jpeg"),
            str(test_dir / "Sample2.jpeg"),
        ]

        # Verify images exist
        existing_images = [img for img in test_images if os.path.exists(img)]
        if len(existing_images) < 2:
            logger.error(
                f"Need 2 test images, found {len(existing_images)}. "
                f"Missing: {set(test_images) - set(existing_images)}"
            )
            return 1

        logger.info(f"Processing {len(existing_images)} images:")
        for i, img in enumerate(existing_images, 1):
            logger.info(f"  {i}. {img}")

        # Step 1: Batch upload to GCS
        logger.info(f"\n[1/4] Batch uploading {len(existing_images)} images to GCS...")
        import time
        temp_datetime = time.strftime("%Y-%m-%d %H:%M:%S")
        receipt_numbers = [
            f"test_batch_{int(time.time())}_{i}"
            for i in range(len(existing_images))
        ]
        weighing_datetimes = [temp_datetime] * len(existing_images)

        upload_results = await asyncio.to_thread(
            sheets_client.batch_upload_images_to_storage,
            image_paths=existing_images,
            receipt_numbers=receipt_numbers,
            weighing_datetimes=weighing_datetimes
        )
        logger.info(f"✅ Uploaded {len(upload_results)} images")
        for i, (public_url, gcs_uri) in enumerate(upload_results, 1):
            if gcs_uri:
                logger.info(f"   {i}. {gcs_uri}")
            else:
                logger.warning(f"   {i}. Upload failed")

        # Step 2: Process each image sequentially
        logger.info(f"\n[2/4] Processing each image with Gemini...")
        deliveries = []
        total_weight = 0.0

        for i, (receipt_url, gcs_uri) in enumerate(upload_results, 1):
            if not gcs_uri:
                logger.warning(f"   Image {i}: Skipping (no GCS URI)")
                continue

            logger.info(f"\n   Processing image {i}/{len(upload_results)}...")

            # Extract data
            receipt_data, confidence, token_usage = await asyncio.to_thread(
                gemini_client.extract_receipt_data,
                gcs_uri=gcs_uri
            )

            if receipt_data is None:
                logger.warning(f"   ❌ Image {i}: Failed to extract data")
                continue

            logger.info(f"   ✅ Receipt: {receipt_data.receipt_number}")
            logger.info(f"      Material: {receipt_data.material_name}")
            logger.info(f"      Net Weight: {receipt_data.net_weight} ton")
            logger.info(f"      Confidence: {confidence:.2%}")

            if token_usage:
                logger.info(
                    f"      Tokens: {token_usage.get('total_token_count', 0)}"
                )

            # Create delivery record (material_type now in receipt_data)
            delivery = DeliveryRecord.from_receipt_data(
                receipt=receipt_data,
                confidence=confidence,
                receipt_url=receipt_url,
                notes=f"Test - Batch Image #{i}"
            )
            logger.info(f"      Type: {delivery.material_type}")
            deliveries.append(delivery)
            total_weight += receipt_data.net_weight

        logger.info(
            f"\n✅ Processed {len(deliveries)}/{len(upload_results)} images"
        )

        # Step 3: Display summary
        logger.info(f"\n[3/4] Batch Summary:")
        for i, delivery in enumerate(deliveries, 1):
            logger.info(
                f"   {i}. {delivery.receipt_number}: "
                f"{delivery.net_weight}t ({delivery.material_type})"
            )
        logger.info(f"\n   Total Weight: {total_weight:.2f} ton")

        # Step 4: Batch save to Sheets
        logger.info(f"\n[4/4] Batch saving {len(deliveries)} deliveries...")
        logger.info("   ⚠️  Skipped - uncomment below to actually save")
        logger.info("   This prevents test data from being saved to production")

        # Uncomment to actually save to Google Sheets:
        # if deliveries:
        #     success = await asyncio.to_thread(
        #         sheets_client.batch_append_deliveries,
        #         deliveries
        #     )
        #     if success:
        #         logger.info(f"✅ Saved {len(deliveries)} deliveries to Sheets")
        #     else:
        #         logger.error("❌ Failed to save deliveries")
        #         return 1

        logger.info("\n" + "=" * 60)
        logger.info("✅ MULTIPLE IMAGES TEST PASSED")
        logger.info(f"   Processed: {len(deliveries)} deliveries")
        logger.info(f"   Total Weight: {total_weight:.2f} ton")
        logger.info("=" * 60)
        return 0

    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
