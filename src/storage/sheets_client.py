"""Google Sheets API client for delivery record storage."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from functools import lru_cache
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import storage
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models.delivery import DeliveryRecord
from ..config import settings


class SheetsClient:
    """Client for interacting with Google Sheets API."""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    SHEET_NAME = "Pengiriman"  # "Deliveries" in Indonesian

    # Class variable for singleton pattern to reuse client connections
    _instance: Optional['SheetsClient'] = None

    def __new__(cls):
        """Implement singleton pattern to reuse API client connections."""
        if cls._instance is None:
            cls._instance = super(SheetsClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the Sheets and Storage clients with service account."""
        # Skip if already initialized (singleton pattern)
        if self._initialized:
            return

        try:
            # Service account for Sheets
            credentials = service_account.Credentials.from_service_account_file(
                settings.google_application_credentials,
                scopes=self.SCOPES
            )
            self.service = build("sheets", "v4", credentials=credentials)
            self.spreadsheet_id = settings.google_sheets_id

            # Cloud Storage client (uses same service account)
            self.storage_client = storage.Client.from_service_account_json(
                settings.google_application_credentials
            )

            self._initialized = True
            logger.info("Google Sheets and Cloud Storage clients initialized (singleton)")
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            raise

    def initialize_sheet(self) -> bool:
        """Verify the expense sheet exists."""
        try:
            # Just verify the sheet exists
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()

            sheets = sheet_metadata.get("sheets", [])
            sheet_exists = any(
                sheet.get("properties", {}).get("title") == self.SHEET_NAME
                for sheet in sheets
            )

            if not sheet_exists:
                logger.error(
                    f"Sheet '{self.SHEET_NAME}' not found. "
                    "Please create it manually with your desired formatting."
                )
                return False

            logger.info(f"Sheet '{self.SHEET_NAME}' verified successfully")
            return True

        except HttpError as e:
            logger.error(f"Failed to verify sheet: {e}")
            return False

    def _get_next_no(self) -> int:
        """
        Get the next sequential number by reading only the last 10 rows.
        This is much faster than reading the entire column.
        """
        try:
            # First, get the sheet dimensions to know how many rows exist
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id,
                ranges=[f"{self.SHEET_NAME}!A:A"],
                fields="sheets.data.rowMetadata"
            ).execute()

            # Get row count
            sheets = sheet_metadata.get("sheets", [])
            if not sheets:
                return 1

            row_data = sheets[0].get("data", [{}])[0]
            row_metadata = row_data.get("rowMetadata", [])
            total_rows = len(row_metadata)

            if total_rows <= 1:  # Only header or empty
                return 1

            # Read only the last 10 rows instead of entire column
            # This reduces data transfer and processing time significantly
            start_row = max(2, total_rows - 9)  # Skip header, get last 10
            end_row = total_rows

            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.SHEET_NAME}!A{start_row}:A{end_row}"
            ).execute()

            values = result.get("values", [])

            if not values:
                return 1

            # Get the last row's No value
            for row in reversed(values):
                if row and row[0]:
                    try:
                        last_no = int(row[0])
                        return last_no + 1
                    except (ValueError, IndexError):
                        continue

            return 1  # Default to 1 if no valid number found

        except HttpError as e:
            logger.error(f"Failed to get next No: {e}")
            return 1  # Default to 1 on error

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def append_delivery(self, delivery: DeliveryRecord) -> bool:
        """Append a single delivery record to the sheet."""
        try:
            # Get the next sequential number
            next_no = self._get_next_no()

            row = delivery.to_sheets_row()
            row[0] = str(next_no)  # Set the No value

            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.SHEET_NAME}!A:O",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]}
            ).execute()

            logger.info(
                f"Appended delivery #{next_no}: {delivery.receipt_number} "
                f"- {delivery.material_name} ({delivery.net_weight}t)"
            )
            return True

        except HttpError as e:
            logger.error(f"Failed to append delivery: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def get_latest_deliveries(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get the latest N delivery records from the sheet.
        Optimized to read only the necessary rows instead of entire sheet.
        """
        try:
            # First, get the total row count efficiently
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id,
                ranges=[f"{self.SHEET_NAME}!A:A"],
                fields="sheets.data.rowMetadata"
            ).execute()

            sheets = sheet_metadata.get("sheets", [])
            if not sheets:
                return []

            row_data = sheets[0].get("data", [{}])[0]
            row_metadata = row_data.get("rowMetadata", [])
            total_rows = len(row_metadata)

            if total_rows <= 1:  # Only header or empty
                return []

            # Calculate range to read only the last N rows + buffer
            start_row = max(2, total_rows - limit + 1)
            end_row = total_rows

            # Read only the necessary rows
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.SHEET_NAME}!A{start_row}:O{end_row}"
            ).execute()

            values = result.get("values", [])

            if not values:
                return []

            # Reverse to get latest first
            latest_values = list(reversed(values))[:limit]

            # Convert to dictionaries (in Indonesian)
            headers = [
                "no", "tanggal", "no_nota", "waktu",
                "no_timbangan", "no_kendaraan", "nama_material",
                "jenis_material", "berat_isi", "berat_kosong",
                "berat_bersih", "status", "catatan", "url_bukti",
                "ditambahkan"
            ]

            deliveries = []
            for row in latest_values:
                # Pad row with empty strings if needed
                row = row + [""] * (len(headers) - len(row))
                delivery_dict = dict(zip(headers, row))
                deliveries.append(delivery_dict)

            logger.info(f"Retrieved {len(deliveries)} latest deliveries")
            return deliveries

        except HttpError as e:
            logger.error(f"Failed to get latest deliveries: {e}")
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def get_deliveries_by_date(self, date_str: str) -> List[Dict[str, Any]]:
        """Get all delivery records for a specific date.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            List of delivery dictionaries for the specified date
        """
        try:
            # Get all data
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.SHEET_NAME}!A2:O"  # Skip header
            ).execute()

            values = result.get("values", [])

            if not values:
                return []

            # Headers for conversion
            headers = [
                "no", "tanggal", "no_nota", "waktu",
                "no_timbangan", "no_kendaraan", "nama_material",
                "jenis_material", "berat_isi", "berat_kosong",
                "berat_bersih", "status", "catatan", "url_bukti",
                "ditambahkan"
            ]

            # Filter by date
            deliveries = []
            for row in values:
                # Pad row with empty strings if needed
                row = row + [""] * (len(headers) - len(row))
                delivery_dict = dict(zip(headers, row))

                # Check if date matches (tanggal is index 1)
                if delivery_dict.get("tanggal") == date_str:
                    deliveries.append(delivery_dict)

            logger.info(f"Retrieved {len(deliveries)} deliveries for {date_str}")
            return deliveries

        except HttpError as e:
            logger.error(f"Failed to get deliveries by date: {e}")
            return []

    def batch_append_deliveries(
        self, deliveries: List[DeliveryRecord]
    ) -> bool:
        """Append multiple delivery records efficiently."""
        try:
            # Get starting number
            next_no = self._get_next_no()

            rows = []
            for i, delivery in enumerate(deliveries):
                row = delivery.to_sheets_row()
                row[0] = str(next_no + i)  # Sequential numbering
                rows.append(row)

            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.SHEET_NAME}!A:O",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": rows}
            ).execute()

            logger.info(f"Batch appended {len(deliveries)} deliveries")
            return True

        except HttpError as e:
            logger.error(f"Failed to batch append deliveries: {e}")
            return False

    def upload_image_to_storage(
        self, image_path: str, receipt_number: str, weighing_datetime: str
    ) -> str:
        """Upload receipt image to Google Cloud Storage.

        Uploads to GCS bucket with public access.
        Filename format: YYYY-MM-DD_RECEIPT-NUMBER.jpg

        Args:
            image_path: Path to the image file
            receipt_number: Receipt number for filename
            weighing_datetime: Weighing datetime in YYYY-MM-DD HH:MM:SS

        Returns:
            Public URL to the uploaded image
        """
        try:
            # Get bucket name from settings
            bucket_name = settings.gcs_bucket_name

            if not bucket_name:
                logger.error("GCS_BUCKET_NAME not set in config")
                return ""

            # Extract date from weighing_datetime (YYYY-MM-DD)
            date_str = weighing_datetime.split()[0]

            # Create filename: YYYY-MM-DD_RECEIPT-NUMBER.jpg
            safe_receipt = "".join(
                c for c in receipt_number if c.isalnum() or c in ('-', '_')
            ).strip()
            filename = f"{date_str}_{safe_receipt}.jpg"

            # Get bucket
            bucket = self.storage_client.bucket(bucket_name)

            # Upload file
            blob = bucket.blob(filename)
            blob.upload_from_filename(image_path, content_type='image/jpeg')

            # Make publicly accessible
            blob.make_public()

            # Get public URL
            public_url = blob.public_url
            logger.info(f"Uploaded image to GCS: {filename} -> {public_url}")

            return public_url

        except Exception as e:
            logger.error(f"Failed to upload image to Cloud Storage: {e}")
            return ""
