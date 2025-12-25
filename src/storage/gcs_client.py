"""Google Cloud Storage client for uploading receipt images."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from google.cloud import storage
from loguru import logger

from ..config import settings


class GCSClient:
    """Client for uploading files to Google Cloud Storage."""

    def __init__(self, bucket_name: Optional[str] = None):
        """
        Initialize GCS client.

        Args:
            bucket_name: Name of the GCS bucket. If None, uses settings.
        """
        self.bucket_name = bucket_name or settings.gcs_bucket_name
        if not self.bucket_name:
            raise ValueError("GCS_BUCKET_NAME must be set in environment variables")

        # Initialize GCS client
        self.client = storage.Client.from_service_account_json(
            settings.google_application_credentials
        )
        self.bucket = self.client.bucket(self.bucket_name)
        logger.info(f"GCS Client initialized for bucket: {self.bucket_name}")

    def upload_receipt_image(
        self,
        image_path: str,
        receipt_number: Optional[str] = None,
        upload_date: Optional[datetime] = None,
    ) -> str:
        """
        Upload receipt image to GCS with organized folder structure.

        Files are organized by date: YYYY-MM-DD/receipt_number.jpg

        Args:
            image_path: Path to the local image file
            receipt_number: Receipt number (from NO NOTA field). Used as filename.
            upload_date: Date for folder organization. Defaults to today.

        Returns:
            Public URL of the uploaded file

        Raises:
            FileNotFoundError: If image file doesn't exist
            Exception: If upload fails
        """
        # Validate file exists
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Get file extension
        file_ext = Path(image_path).suffix or ".jpg"

        # Use upload date or current date
        date = upload_date or datetime.now()
        date_folder = date.strftime("%Y-%m-%d")

        # Generate blob name
        if receipt_number:
            # Clean receipt number (remove special chars)
            clean_receipt = "".join(
                c for c in receipt_number if c.isalnum() or c in "-_"
            )
            blob_name = f"{date_folder}/{clean_receipt}{file_ext}"
        else:
            # Use timestamp if no receipt number
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            blob_name = f"{date_folder}/receipt_{timestamp}{file_ext}"

        try:
            # Upload to GCS
            blob = self.bucket.blob(blob_name)
            blob.upload_from_filename(image_path)

            # Make the blob publicly accessible (optional)
            # blob.make_public()

            # Get the public URL
            public_url = blob.public_url
            logger.info(f"Image uploaded successfully to {blob_name}")

            return public_url

        except Exception as e:
            logger.error(f"Failed to upload image to GCS: {e}")
            raise

    def upload_from_bytes(
        self,
        image_bytes: bytes,
        filename: str,
        receipt_number: Optional[str] = None,
        upload_date: Optional[datetime] = None,
        content_type: str = "image/jpeg",
    ) -> str:
        """
        Upload image from bytes to GCS.

        Args:
            image_bytes: Image data as bytes
            filename: Original filename
            receipt_number: Receipt number for naming
            upload_date: Date for folder organization
            content_type: MIME type of the image

        Returns:
            Public URL of the uploaded file
        """
        # Get file extension
        file_ext = Path(filename).suffix or ".jpg"

        # Use upload date or current date
        date = upload_date or datetime.now()
        date_folder = date.strftime("%Y-%m-%d")

        # Generate blob name
        if receipt_number:
            clean_receipt = "".join(
                c for c in receipt_number if c.isalnum() or c in "-_"
            )
            blob_name = f"{date_folder}/{clean_receipt}{file_ext}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            blob_name = f"{date_folder}/receipt_{timestamp}{file_ext}"

        try:
            # Upload to GCS
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(image_bytes, content_type=content_type)

            # Get the public URL
            public_url = blob.public_url
            logger.info(f"Image uploaded successfully from bytes to {blob_name}")

            return public_url

        except Exception as e:
            logger.error(f"Failed to upload image bytes to GCS: {e}")
            raise

    def list_receipts_by_date(self, date: datetime) -> list[str]:
        """
        List all receipt images for a specific date.

        Args:
            date: Date to filter receipts

        Returns:
            List of blob names (file paths in bucket)
        """
        date_folder = date.strftime("%Y-%m-%d")
        prefix = f"{date_folder}/"

        blobs = self.bucket.list_blobs(prefix=prefix)
        return [blob.name for blob in blobs]

    def get_signed_url(self, blob_name: str, expiration_minutes: int = 60) -> str:
        """
        Generate a signed URL for temporary access to a private file.

        Args:
            blob_name: Name of the blob in the bucket
            expiration_minutes: URL expiration time in minutes

        Returns:
            Signed URL string
        """
        from datetime import timedelta

        blob = self.bucket.blob(blob_name)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
        )
        return url
