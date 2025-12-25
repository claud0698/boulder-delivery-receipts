#!/usr/bin/env python3
"""
Script to clear all expense data and reset the Google Sheet.

WARNING: This will delete ALL expense data from the sheet!
Use this to start fresh with ID numbering from 1.

Usage:
    python scripts/clear_and_reset_sheet.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from storage.sheets_client import SheetsClient
from core.logging_config import logger


def main():
    """Clear all data and reset the sheet."""
    print("⚠️  WARNING: This will DELETE ALL expense data from the sheet!")
    print("This action cannot be undone.")

    response = input("\nAre you sure you want to continue? (yes/no): ")

    if response.lower() != "yes":
        print("❌ Operation cancelled")
        sys.exit(0)

    print("\n🗑️  Clearing all expense data...")

    try:
        client = SheetsClient()

        # Delete all rows except header
        client.service.spreadsheets().values().clear(
            spreadsheetId=client.spreadsheet_id,
            range=f"{client.SHEET_NAME}!A2:K"
        ).execute()

        print("✅ All expense data cleared!")

        # Re-apply formatting to ensure formulas are set correctly
        print("🔧 Reapplying formatting...")
        client._apply_formatting()

        print("✅ Sheet reset successfully!")
        print(f"📊 Sheet URL: https://docs.google.com/spreadsheets/d/{client.spreadsheet_id}/edit")
        print("\nThe next expense you add will have ID = 1")

    except Exception as e:
        logger.error(f"Error resetting sheet: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
