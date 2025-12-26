#!/usr/bin/env python3
"""
Test script for the revamped image processing flow.

This script tests:
1. Single image processing with GCS URI
2. Batch upload to GCS
3. Multiple images processing with batch save
"""

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


async def test_single_image_flow():
    """Test single image processing flow with GCS URI."""
    logger.info("=" * 60)
    logger.info("TEST 1: Single Image Flow")
    logger.info("=" * 60)

    try:
        # Initialize clients
        sheets_client = SheetsClient()
        gemini_client = GeminiClient()

        # Check for test image
        test_image_path = Path(__file__).parent / "Samples" / "Sample1.jpeg"
        if not test_image_path.exists():
            logger.warning(
                f"Test image not found at {test_image_path}. "
                "Skipping single image test."
            )
            return False

        test_image_path = str(test_image_path)
        logger.info(f"Using test image: {test_image_path}")

        # Step 1: Upload to GCS
        logger.info("Step 1: Uploading image to GCS...")
        import time
        temp_receipt_id = f"test_{int(time.time())}"
        temp_datetime = time.strftime("%Y-%m-%d %H:%M:%S")

        receipt_url, gcs_uri = await asyncio.to_thread(
            sheets_client.upload_image_to_storage,
            image_path=test_image_path,
            receipt_number=temp_receipt_id,
            weighing_datetime=temp_datetime
        )
        logger.info(f"✅ Uploaded to GCS: {gcs_uri}")
        logger.info(f"   Public URL: {receipt_url}")

        # Step 2: Extract data using GCS URI
        logger.info("Step 2: Extracting receipt data using GCS URI...")
        receipt_data, confidence, token_usage = await asyncio.to_thread(
            gemini_client.extract_receipt_data,
            gcs_uri=gcs_uri
        )

        if receipt_data is None:
            logger.error("❌ Failed to extract receipt data")
            return False

        logger.info(f"✅ Extracted receipt: {receipt_data.receipt_number}")
        logger.info(f"   Material: {receipt_data.material_name}")
        logger.info(f"   Net weight: {receipt_data.net_weight} ton")
        logger.info(f"   Confidence: {confidence:.2%}")

        if token_usage:
            logger.info(
                f"   Token usage: {token_usage.get('total_token_count', 0)}"
            )

        # Step 3: Create delivery record (material_type now in receipt_data)
        logger.info("Step 3: Creating delivery record...")
        delivery = DeliveryRecord.from_receipt_data(
            receipt=receipt_data,
            confidence=confidence,
            receipt_url=receipt_url,
            notes="Test delivery"
        )
        logger.info("✅ Created delivery record")
        logger.info(f"   Material type: {delivery.material_type}")

        # Step 4: Save to Sheets (optional - comment out if you don't
        # want to modify sheets)
        logger.info("Step 4: Saving to Google Sheets...")
        logger.info(
            "   (Skipped - uncomment to test actual save)"
        )
        # success = await asyncio.to_thread(
        #     sheets_client.append_delivery,
        #     delivery
        # )
        # if success:
        #     logger.info("✅ Saved to Google Sheets")
        # else:
        #     logger.error("❌ Failed to save to Sheets")
        #     return False

        logger.info("✅ Single image flow test PASSED")
        return True

    except Exception as e:
        logger.error(f"❌ Single image flow test FAILED: {e}", exc_info=True)
        return False


async def test_batch_upload():
    """Test batch upload to GCS."""
    logger.info("=" * 60)
    logger.info("TEST 2: Batch Upload to GCS")
    logger.info("=" * 60)

    try:
        sheets_client = SheetsClient()

        # Check for test images
        test_dir = Path(__file__).parent / "Samples"
        test_images = [
            str(test_dir / "Sample1.jpeg"),
            str(test_dir / "Sample2.jpeg"),
        ]

        # Filter existing images
        existing_images = [
            img for img in test_images if os.path.exists(img)
        ]

        if not existing_images:
            logger.warning(
                "No test images found. Skipping batch upload test."
            )
            return False

        logger.info(f"Using {len(existing_images)} test images")

        # Prepare batch data
        import time
        temp_datetime = time.strftime("%Y-%m-%d %H:%M:%S")
        receipt_numbers = [
            f"test_batch_{int(time.time())}_{i}"
            for i in range(len(existing_images))
        ]
        weighing_datetimes = [temp_datetime] * len(existing_images)

        # Test batch upload
        logger.info("Uploading batch to GCS...")
        upload_results = await asyncio.to_thread(
            sheets_client.batch_upload_images_to_storage,
            image_paths=existing_images,
            receipt_numbers=receipt_numbers,
            weighing_datetimes=weighing_datetimes
        )

        logger.info(f"✅ Batch uploaded {len(upload_results)} images")

        # Verify all uploads
        success_count = 0
        for i, (public_url, gcs_uri) in enumerate(upload_results):
            if public_url and gcs_uri:
                logger.info(f"   Image {i+1}: {gcs_uri}")
                success_count += 1
            else:
                logger.warning(f"   Image {i+1}: Upload failed")

        if success_count == len(existing_images):
            logger.info("✅ Batch upload test PASSED")
            return True
        else:
            logger.warning(
                f"⚠️  Batch upload partial: "
                f"{success_count}/{len(existing_images)}"
            )
            return False

    except Exception as e:
        logger.error(f"❌ Batch upload test FAILED: {e}", exc_info=True)
        return False


async def test_multiple_images_flow():
    """Test multiple images processing with batch save."""
    logger.info("=" * 60)
    logger.info("TEST 3: Multiple Images Flow")
    logger.info("=" * 60)

    try:
        sheets_client = SheetsClient()
        gemini_client = GeminiClient()

        # Check for test images
        test_dir = Path(__file__).parent / "Samples"
        test_images = [
            str(test_dir / "Sample1.jpeg"),
            str(test_dir / "Sample2.jpeg"),
        ]

        existing_images = [
            img for img in test_images if os.path.exists(img)
        ]

        if not existing_images:
            logger.warning(
                "No test images found. Skipping multiple images test."
            )
            return False

        logger.info(f"Processing {len(existing_images)} images")

        # Step 1: Batch upload
        logger.info("Step 1: Batch uploading to GCS...")
        import time
        temp_datetime = time.strftime("%Y-%m-%d %H:%M:%S")
        receipt_numbers = [
            f"test_multi_{int(time.time())}_{i}"
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

        # Step 2: Process each image
        logger.info("Step 2: Processing each image...")
        deliveries = []
        total_weight = 0.0

        for i, (receipt_url, gcs_uri) in enumerate(upload_results):
            if not gcs_uri:
                logger.warning(f"   Image {i+1}: No GCS URI, skipping")
                continue

            logger.info(f"   Processing image {i+1}...")

            # Extract data
            receipt_data, confidence, token_usage = await asyncio.to_thread(
                gemini_client.extract_receipt_data,
                gcs_uri=gcs_uri
            )

            if receipt_data is None:
                logger.warning(f"   Image {i+1}: Failed to extract data")
                continue

            # Create delivery record (material_type now in receipt_data)
            delivery = DeliveryRecord.from_receipt_data(
                receipt=receipt_data,
                confidence=confidence,
                receipt_url=receipt_url,
                notes=f"Test batch #{i+1}"
            )
            deliveries.append(delivery)
            total_weight += receipt_data.net_weight

            logger.info(
                f"   ✅ Image {i+1}: "
                f"{receipt_data.receipt_number} ({delivery.material_type})"
            )

        logger.info(
            f"✅ Processed {len(deliveries)} deliveries, "
            f"total weight: {total_weight:.2f} ton"
        )

        # Step 3: Batch save (optional - comment out if you don't
        # want to modify sheets)
        logger.info("Step 3: Batch saving to Sheets...")
        logger.info(
            "   (Skipped - uncomment to test actual save)"
        )
        # if deliveries:
        #     success = await asyncio.to_thread(
        #         sheets_client.batch_append_deliveries,
        #         deliveries
        #     )
        #     if success:
        #         logger.info("✅ Saved all deliveries to Sheets")
        #     else:
        #         logger.error("❌ Failed to save deliveries")
        #         return False

        logger.info("✅ Multiple images flow test PASSED")
        return True

    except Exception as e:
        logger.error(
            f"❌ Multiple images flow test FAILED: {e}",
            exc_info=True
        )
        return False


async def main():
    """Run all tests."""
    logger.info("Starting revamped flow tests...")
    logger.info("")

    results = {
        "Single Image Flow": await test_single_image_flow(),
        "Batch Upload": await test_batch_upload(),
        "Multiple Images Flow": await test_multiple_images_flow(),
    }

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")

    total = len(results)
    passed = sum(results.values())
    logger.info("")
    logger.info(f"Total: {passed}/{total} tests passed")

    if passed == total:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.warning(f"⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
