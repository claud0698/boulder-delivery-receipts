"""Test script for Gemini Vision API with delivery receipts."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.gemini_client import GeminiClient
from loguru import logger


def test_gemini_extraction():
    """Test extracting data from sample delivery receipt."""
    logger.info("Starting Gemini extraction test...")

    # Initialize client
    client = GeminiClient()

    # Test with sample image
    sample_path = Path(__file__).parent.parent / "Samples" / "Sample1.jpeg"

    if not sample_path.exists():
        logger.error(f"Sample file not found: {sample_path}")
        return False

    logger.info(f"Reading sample image: {sample_path}")

    with open(sample_path, "rb") as f:
        image_bytes = f.read()

    # Extract receipt data
    receipt_data, confidence = client.extract_receipt_data(image_bytes)

    if receipt_data:
        logger.success("✓ Successfully extracted delivery receipt data!")
        logger.info(f"Receipt Number: {receipt_data.receipt_number}")
        logger.info(f"Scale Number: {receipt_data.scale_number}")
        logger.info(f"Weighing DateTime: {receipt_data.weighing_datetime}")
        logger.info(f"Vehicle Number: {receipt_data.vehicle_number}")
        logger.info(f"Material Name: {receipt_data.material_name}")
        logger.info(f"Gross Weight: {receipt_data.gross_weight} tons")
        logger.info(f"Empty Weight: {receipt_data.empty_weight} tons")
        logger.info(f"Net Weight: {receipt_data.net_weight} tons")
        logger.info(f"Confidence: {confidence:.2%}")

        # Test material categorization
        material_type = client.categorize_material(receipt_data.material_name)
        logger.info(f"Material Type: {material_type}")

        return True
    else:
        logger.error("✗ Failed to extract receipt data")
        return False


if __name__ == "__main__":
    success = test_gemini_extraction()
    sys.exit(0 if success else 1)
