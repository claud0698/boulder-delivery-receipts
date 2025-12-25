"""Test script for Google Sheets API with delivery records."""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.sheets_client import SheetsClient
from src.models.delivery import DeliveryRecord
from loguru import logger


def test_sheets_operations():
    """Test Google Sheets operations for delivery tracking."""
    logger.info("Starting Google Sheets test...")

    # Initialize client
    client = SheetsClient()

    # Test 1: Initialize/verify sheet
    logger.info("Test 1: Verifying sheet exists...")
    if client.initialize_sheet():
        logger.success("✓ Sheet verified successfully")
    else:
        logger.error("✗ Sheet verification failed")
        return False

    # Test 2: Create a test delivery record
    logger.info("Test 2: Creating test delivery record...")
    test_delivery = DeliveryRecord(
        receipt_number="TEST123456789",
        weighing_datetime="2025-12-25 10:30:00",
        scale_number="T99",
        vehicle_number="B1234TEST",
        material_name="BATU PECAH 1/2 (TEST)",
        material_type="Crushed Stone 1/2",
        gross_weight=25.50,
        empty_weight=9.25,
        net_weight=16.25,
        status="Delivered",
        notes="Test delivery - dapat dihapus",
        receipt_url="https://drive.google.com/test",
        confidence=0.95
    )

    # Test 3: Append delivery
    logger.info("Test 3: Appending test delivery to sheet...")
    try:
        if client.append_delivery(test_delivery):
            logger.success("✓ Test delivery appended successfully")
        else:
            logger.error("✗ Failed to append test delivery")
            return False
    except Exception as e:
        logger.error(f"✗ Error appending delivery: {e}")
        return False

    # Test 4: Get latest deliveries
    logger.info("Test 4: Retrieving latest deliveries...")
    deliveries = client.get_latest_deliveries(limit=5)

    if deliveries:
        logger.success(f"✓ Retrieved {len(deliveries)} latest deliveries")
        for i, delivery in enumerate(deliveries, 1):
            logger.info(f"\nDelivery {i}:")
            logger.info(f"  No: {delivery.get('no')}")
            logger.info(f"  Receipt #: {delivery.get('no_nota')}")
            logger.info(f"  Material: {delivery.get('nama_material')}")
            logger.info(f"  Net Weight: {delivery.get('berat_bersih')} tons")
    else:
        logger.warning("No deliveries found")

    logger.success("\n✓ All Google Sheets tests completed successfully!")
    return True


if __name__ == "__main__":
    success = test_sheets_operations()
    sys.exit(0 if success else 1)
