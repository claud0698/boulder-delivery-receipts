"""Full end-to-end test of delivery receipt processing pipeline."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.gemini_client import GeminiClient
from src.storage.sheets_client import SheetsClient
from src.models.delivery import DeliveryRecord
from loguru import logger


def test_full_pipeline():
    """Test complete pipeline: Image -> Gemini -> Categorize -> Drive -> Sheets."""
    logger.info("=" * 60)
    logger.info("FULL PIPELINE TEST: Delivery Receipt Processing")
    logger.info("=" * 60)

    # Initialize clients
    logger.info("\n[1/5] Initializing clients...")
    gemini_client = GeminiClient()
    sheets_client = SheetsClient()
    logger.success("✓ Clients initialized")

    # Read sample image
    logger.info("\n[2/5] Reading sample receipt image...")
    sample_path = Path(__file__).parent.parent / "Samples" / "Sample1.jpeg"

    if not sample_path.exists():
        logger.error(f"Sample file not found: {sample_path}")
        return False

    with open(sample_path, "rb") as f:
        image_bytes = f.read()
    logger.success(f"✓ Image loaded: {sample_path.name}")

    # Extract data with Gemini
    logger.info("\n[3/5] Extracting data with Gemini Vision API...")
    receipt_data, confidence = gemini_client.extract_receipt_data(image_bytes)

    if not receipt_data:
        logger.error("✗ Failed to extract receipt data")
        return False

    logger.success("✓ Data extracted successfully")
    logger.info(f"  Receipt #: {receipt_data.receipt_number}")
    logger.info(f"  Material: {receipt_data.material_name}")
    logger.info(f"  Net Weight: {receipt_data.net_weight} tons")
    logger.info(f"  Confidence: {confidence:.2%}")

    # Categorize material
    material_type = gemini_client.categorize_material(receipt_data.material_name)
    logger.info(f"  Material Type: {material_type}")

    # Upload to Google Cloud Storage
    logger.info("\n[4/5] Uploading receipt image to Google Cloud Storage...")
    try:
        receipt_url = sheets_client.upload_image_to_storage(
            image_path=str(sample_path),
            receipt_number=receipt_data.receipt_number,
            weighing_datetime=receipt_data.weighing_datetime
        )

        if receipt_url:
            logger.success(f"✓ Image uploaded to GCS")
            logger.info(f"  URL: {receipt_url}")
        else:
            logger.warning("⚠ GCS upload returned empty URL (continuing...)")
            receipt_url = ""

    except Exception as e:
        logger.error(f"✗ GCS upload failed: {e}")
        receipt_url = ""

    # Create delivery record
    logger.info("\n[5/5] Saving to Google Sheets...")
    delivery_record = DeliveryRecord.from_receipt_data(
        receipt=receipt_data,
        material_type=material_type,
        confidence=confidence,
        receipt_url=receipt_url,
        notes="Test pipeline - dapat dihapus"
    )

    # Save to sheets
    try:
        if sheets_client.append_delivery(delivery_record):
            logger.success("✓ Delivery record saved to Google Sheets")
        else:
            logger.error("✗ Failed to save to sheets")
            return False
    except Exception as e:
        logger.error(f"✗ Error saving to sheets: {e}")
        return False

    # Summary
    logger.info("\n" + "=" * 60)
    logger.success("✓ FULL PIPELINE TEST COMPLETED SUCCESSFULLY!")
    logger.info("=" * 60)
    logger.info("\nProcessed Delivery:")
    logger.info(f"  Receipt #: {receipt_data.receipt_number}")
    logger.info(f"  Date/Time: {receipt_data.weighing_datetime}")
    logger.info(f"  Vehicle: {receipt_data.vehicle_number}")
    logger.info(f"  Material: {receipt_data.material_name}")
    logger.info(f"  Type: {material_type}")
    logger.info(f"  Net Weight: {receipt_data.net_weight} tons")
    logger.info(f"  GCS URL: {receipt_url or 'N/A'}")
    logger.info("=" * 60)

    return True


if __name__ == "__main__":
    success = test_full_pipeline()
    sys.exit(0 if success else 1)
