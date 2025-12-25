#!/usr/bin/env python3
"""
Script to initialize the Google Sheets expense tracker.

Run this script once to set up the sheet with headers and formatting.
This should be run manually, not automatically on bot startup.

Usage:
    python scripts/init_sheet.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from storage.sheets_client import SheetsClient
from core.logging_config import logger


def main():
    """Initialize the expense sheet."""
    print("🚀 Initializing Google Sheets...")

    try:
        client = SheetsClient()
        success = client.initialize_sheet()

        if success:
            print("✅ Sheet initialized successfully!")
            print(f"📊 Sheet URL: https://docs.google.com/spreadsheets/d/{client.spreadsheet_id}/edit")
            print("\nThe sheet is ready to use with:")
            print("  - Headers configured")
            print("  - Auto-numbering for IDs")
            print("  - IDR number formatting")
            print("  - Frozen header row")
        else:
            print("❌ Failed to initialize sheet")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error initializing sheet: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
