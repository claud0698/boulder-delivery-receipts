"""Google Sheets API client for delivery record storage."""

import os
import socket
import threading
from typing import List, Dict, Any
from io import BytesIO
import google.auth
from google.oauth2 import service_account
from google.cloud import storage
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from PIL import Image
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models.delivery import DeliveryRecord, TokenUsageRecord
from ..config import settings

# Set default socket timeout to prevent hanging
socket.setdefaulttimeout(60)


class SheetsClient:
    """Client for interacting with Google Sheets API."""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/devstorage.full_control",
    ]
    SHEET_NAME = "Pengiriman"  # "Deliveries" in Indonesian
    TOKEN_USAGE_SHEET_NAME = "Token Usage"

    def __init__(self):
        """Initialize the Sheets and Storage clients."""
        try:
            creds_path = settings.google_application_credentials

            # Try to use credentials file if it exists (local dev)
            if creds_path and os.path.isfile(creds_path):
                self.credentials = service_account.Credentials.from_service_account_file(
                    creds_path,
                    scopes=self.SCOPES
                )
                self._use_adc = False
                logger.info("Using service account file for credentials")
            else:
                # Use Application Default Credentials (ADC)
                # In Cloud Run, this uses the attached service account
                # No SSL issues because it uses metadata server
                self.credentials, _ = google.auth.default(scopes=self.SCOPES)
                self._use_adc = True
                logger.info("Using Application Default Credentials (ADC)")

            self.spreadsheet_id = settings.google_sheets_id

            # Thread-local storage for per-request client reuse
            self._local = threading.local()

            logger.info("Google Sheets client initialized (per-request reuse)")
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            raise

    def _get_sheets_service(self):
        """Get or create Sheets service for current thread/request."""
        if not hasattr(self._local, 'sheets_service'):
            self._local.sheets_service = build(
                "sheets",
                "v4",
                credentials=self.credentials,
                cache_discovery=False
            )
        return self._local.sheets_service

    def _get_storage_client(self):
        """Get or create Storage client for current thread/request."""
        if not hasattr(self._local, 'storage_client'):
            # Use default credentials - works with ADC in Cloud Run
            self._local.storage_client = storage.Client(
                credentials=self.credentials,
                project=settings.gcp_project_id
            )
        return self._local.storage_client

    def initialize_sheet(self) -> bool:
        """Verify the expense sheet exists."""
        try:
            service = self._get_sheets_service()
            # Just verify the sheet exists
            sheet_metadata = service.spreadsheets().get(
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
        Get the next sequential number efficiently.
        Uses row count to estimate last row, then reads only recent rows.
        """
        try:
            service = self._get_sheets_service()

            # Get sheet metadata to find row count (fast operation)
            sheet_metadata = service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id,
                ranges=[f"{self.SHEET_NAME}!A:A"],
                fields="sheets.properties.gridProperties.rowCount"
            ).execute()

            sheets = sheet_metadata.get("sheets", [])
            if not sheets:
                return 1

            row_count = sheets[0].get("properties", {}).get(
                "gridProperties", {}
            ).get("rowCount", 1)

            if row_count <= 1:
                logger.info("Sheet empty, starting from 1")
                return 1

            # Read only last 10 rows of column A (much faster than entire column)
            start_row = max(2, row_count - 10)
            result = service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.SHEET_NAME}!A{start_row}:A{row_count}"
            ).execute()

            values = result.get("values", [])

            if not values:
                return 1

            # Find max from recent rows
            max_no = 0
            for row in values:
                if row and row[0]:
                    try:
                        num = int(row[0])
                        max_no = max(max_no, num)
                    except (ValueError, IndexError):
                        continue

            next_no = max_no + 1 if max_no > 0 else 1
            logger.info(f"Next No: {next_no}")
            return next_no

        except HttpError as e:
            logger.error(f"Failed to get next No: {e}")
            return 1

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    def append_delivery(self, delivery: DeliveryRecord) -> bool:
        """Append a single delivery record to the sheet."""
        try:
            logger.info("Getting Sheets service...")
            service = self._get_sheets_service()

            logger.info("Getting next row number...")
            next_no = self._get_next_no()

            row = delivery.to_sheets_row()
            row[0] = str(next_no)

            logger.info(f"Appending row #{next_no} to Sheets...")
            service.spreadsheets().values().append(
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
            service = self._get_sheets_service()
            # First, get the total row count efficiently
            sheet_metadata = service.spreadsheets().get(
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
            result = service.spreadsheets().values().get(
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
            service = self._get_sheets_service()
            # Get all data
            result = service.spreadsheets().values().get(
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
            service = self._get_sheets_service()
            # Get starting number
            next_no = self._get_next_no()

            rows = []
            for i, delivery in enumerate(deliveries):
                row = delivery.to_sheets_row()
                row[0] = str(next_no + i)  # Sequential numbering
                rows.append(row)

            service.spreadsheets().values().append(
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

    def batch_upload_images_to_storage(
        self,
        image_paths: List[str],
        receipt_numbers: List[str],
        weighing_datetimes: List[str]
    ) -> List[tuple[str, str]]:
        """Upload multiple images to GCS concurrently.

        Args:
            image_paths: List of paths to image files
            receipt_numbers: List of receipt numbers for filenames
            weighing_datetimes: List of weighing datetimes in format
                YYYY-MM-DD HH:MM:SS

        Returns:
            List of (public_url, gcs_uri) tuples in same order as inputs.
            Returns ("", "") for failed uploads.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not image_paths:
            return []

        if len(image_paths) != len(receipt_numbers) != len(weighing_datetimes):
            logger.error("Batch upload: mismatched list lengths")
            return [("", "")] * len(image_paths)

        results = [("", "")] * len(image_paths)

        def upload_single(
            index: int, img_path: str, receipt_num: str, weighing_dt: str
        ):
            """Upload single image and return index with result."""
            try:
                public_url, gcs_uri = self.upload_image_to_storage(
                    img_path, receipt_num, weighing_dt
                )
                return index, (public_url, gcs_uri)
            except Exception as e:
                logger.warning(f"Failed to upload image {index}: {e}")
                return index, ("", "")

        # Upload concurrently using ThreadPoolExecutor
        max_workers = min(len(image_paths), 5)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    upload_single, i, img_path, receipt_num, weighing_dt
                ): i
                for i, (img_path, receipt_num, weighing_dt) in enumerate(
                    zip(image_paths, receipt_numbers, weighing_datetimes)
                )
            }

            for future in as_completed(futures):
                index, result = future.result()
                results[index] = result

        logger.info(f"Batch uploaded {len(image_paths)} images to GCS")
        return results

    def _preprocess_image(self, image_path: str) -> bytes:
        """Preprocess image before upload to reduce size and token usage.

        Uses fast BILINEAR resampling instead of slow LANCZOS.
        Target: 800x800 max, JPEG quality 80.
        """
        try:
            img = Image.open(image_path)

            # Auto-rotate based on EXIF (fast operation)
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)

            # Convert to RGB if needed
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Fast resize using BILINEAR (much faster than LANCZOS)
            max_size = (800, 800)
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.BILINEAR)
                logger.info(f"Resized to {img.size}")

            # Convert to JPEG bytes (quality 80, no optimize for speed)
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format="JPEG", quality=80)
            return img_byte_arr.getvalue()

        except Exception as e:
            logger.warning(f"Preprocessing failed: {e}")
            with open(image_path, 'rb') as f:
                return f.read()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4)
    )
    def upload_image_to_storage(
        self, image_path: str, receipt_number: str, weighing_datetime: str
    ) -> tuple[str, str]:
        """Upload receipt image to Google Cloud Storage.

        Uploads to GCS bucket with public access.
        Image is preprocessed (resized to 800x800) to reduce token usage.
        Filename format: YYYY-MM-DD_RECEIPT-NUMBER.jpg

        Args:
            image_path: Path to the image file
            receipt_number: Receipt number for filename
            weighing_datetime: Weighing datetime in YYYY-MM-DD HH:MM:SS

        Returns:
            Tuple of (public_url, gcs_uri) where:
            - public_url: HTTPS URL for browser access
            - gcs_uri: gs:// URI for Vertex AI
        """
        try:
            bucket_name = settings.gcs_bucket_name

            if not bucket_name:
                logger.warning("GCS_BUCKET_NAME not set - skipping image upload")
                return "", ""

            # Extract date from weighing_datetime (YYYY-MM-DD)
            date_str = weighing_datetime.split()[0]

            # Create filename: YYYY-MM-DD_RECEIPT-NUMBER.jpg
            safe_receipt = "".join(
                c for c in receipt_number if c.isalnum() or c in ('-', '_')
            ).strip()
            filename = f"{date_str}_{safe_receipt}.jpg"

            # Preprocess image (resize to reduce token usage)
            preprocessed_bytes = self._preprocess_image(image_path)

            # Reuse storage client (per-thread)
            storage_client = self._get_storage_client()
            bucket = storage_client.bucket(bucket_name)

            # Upload preprocessed image from bytes
            blob = bucket.blob(filename)
            blob.upload_from_string(
                preprocessed_bytes,
                content_type='image/jpeg',
                timeout=60
            )

            # Make publicly accessible
            blob.make_public()

            # Get both public URL and GCS URI
            public_url = blob.public_url
            gcs_uri = f"gs://{bucket_name}/{filename}"
            logger.info(f"GCS upload complete: {filename}")

            return public_url, gcs_uri

        except Exception as e:
            logger.warning(f"GCS upload failed (non-critical): {e}")
            return "", ""

    def _get_next_token_usage_no(self) -> int:
        """
        Get the next sequential number for token usage sheet.
        Always reads from sheet to handle Cloud Run cold starts.
        """
        try:
            service = self._get_sheets_service()
            # Read the entire A column (No column)
            result = service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.TOKEN_USAGE_SHEET_NAME}!A:A"
            ).execute()

            values = result.get("values", [])

            # First row is header, so we need at least 2 rows
            if len(values) <= 1:
                logger.info("Token Usage sheet only has header, starting from 1")
                return 1

            # Find max number from all rows (skip header)
            max_no = 0
            for row in values[1:]:  # Skip header
                if row and row[0]:
                    try:
                        num = int(row[0])
                        max_no = max(max_no, num)
                    except ValueError:
                        continue

            # If no valid numbers found, start from 1
            if max_no == 0:
                logger.info("No valid numbers in Token Usage sheet, starting from 1")
                return 1

            next_no = max_no + 1
            logger.info(f"Token Usage - Last No: {max_no}, next No: {next_no}")
            return next_no

        except Exception as e:
            logger.warning(f"Could not determine next token usage number: {e}")
            return 1

    @retry(
        stop=stop_after_attempt(2),  # Reduced retries for token usage
        wait=wait_exponential(multiplier=1, min=1, max=5)  # Faster backoff
    )
    def append_token_usage(self, token_usage: TokenUsageRecord) -> bool:
        """Append a token usage record to the Token Usage sheet.

        Non-critical operation - fails gracefully without affecting main flow.
        """
        try:
            service = self._get_sheets_service()
            next_no = self._get_next_token_usage_no()
            row = token_usage.to_sheets_row()
            row[0] = str(next_no)

            service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.TOKEN_USAGE_SHEET_NAME}!A:H",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]}
            ).execute()

            logger.info(
                f"Appended token usage #{next_no}: {token_usage.operation} - "
                f"{token_usage.total_tokens} tokens"
            )
            return True

        except Exception as e:
            # Log but don't raise - token usage logging is non-critical
            logger.warning(f"Failed to append token usage (non-critical): {e}")
            return False
