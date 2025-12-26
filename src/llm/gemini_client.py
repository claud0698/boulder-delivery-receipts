"""Google Gemini Vision API client for delivery receipt processing."""

import json
import os
from typing import Optional, Tuple, Dict
from io import BytesIO
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from PIL import Image
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models.delivery import DeliveryReceiptData
from ..config import settings
from .prompts import (
    SYSTEM_PROMPT,
    RECEIPT_EXTRACTION_PROMPT
)


class GeminiClient:
    """Client for Google Gemini Vision API."""

    def __init__(self):
        """Initialize Gemini client with Vertex AI."""
        try:
            # Set GOOGLE_APPLICATION_CREDENTIALS only for local development
            # In Cloud Run, use the attached service account instead
            if (settings.google_application_credentials and
                    not settings.is_production):
                creds = settings.google_application_credentials
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds

            # Initialize Vertex AI
            # In Cloud Run, this will automatically use the service account
            # attached to the Cloud Run service
            # For local development, it will use GOOGLE_APPLICATION_CREDENTIALS
            vertexai.init(
                project=settings.gcp_project_id,
                location=settings.gcp_location,
            )

            # Create generative model
            # Use Gemini 2.5 Flash-Lite for Vertex AI
            self.model_name = "gemini-2.5-flash-lite"
            self.model = GenerativeModel(
                self.model_name,
                system_instruction=[SYSTEM_PROMPT]
            )
            logger.info(
                f"Vertex AI initialized (project: {settings.gcp_project_id}, "
                f"location: {settings.gcp_location}, model: {self.model_name})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI Gemini client: {e}")
            raise

    def preprocess_image(self, image_bytes: bytes) -> Image.Image:
        """Preprocess image for better OCR results."""
        try:
            img = Image.open(BytesIO(image_bytes))

            # Auto-rotate based on EXIF orientation
            try:
                from PIL import ImageOps
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            # Convert to RGB if needed
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Resize if too large (optimize for speed and cost)
            # Receipts don't need full resolution - 800x800 is sufficient
            max_size = (800, 800)
            if (img.size[0] > max_size[0] or
                    img.size[1] > max_size[1]):
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                logger.info(f"Resized image to {img.size}")

            return img

        except Exception as e:
            logger.error(f"Failed to preprocess image: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def extract_receipt_data(
        self,
        image_bytes: bytes = None,
        gcs_uri: str = None
    ) -> Tuple[Optional[DeliveryReceiptData], float, Optional[Dict]]:
        """
        Extract delivery receipt data from image.

        Args:
            image_bytes: Image data as bytes (optional if gcs_uri provided)
            gcs_uri: GCS URI (gs://bucket/path) to image (preferred method)

        Returns:
            Tuple of (DeliveryReceiptData or None, confidence_score, token_usage_dict)
        """
        try:
            # Use GCS URI if provided (more efficient)
            if gcs_uri:
                logger.info(
                    f"Using GCS URI for Vertex AI: {gcs_uri}"
                )
                image_part = Part.from_uri(
                    uri=gcs_uri,
                    mime_type="image/jpeg"
                )
            else:
                # Fall back to inline image data
                if not image_bytes:
                    raise ValueError(
                        "Either image_bytes or gcs_uri must be provided"
                    )

                # Preprocess image
                img = self.preprocess_image(image_bytes)

                # Convert to bytes (JPEG smaller, faster)
                img_byte_arr = BytesIO()
                img.save(
                    img_byte_arr, format="JPEG", quality=85, optimize=True
                )
                img_bytes = img_byte_arr.getvalue()

                # Create image part (Vertex AI inline data)
                image_part = Part.from_data(
                    mime_type="image/jpeg",
                    data=img_bytes
                )

            # Configure generation with JSON response
            generation_config = GenerationConfig(
                response_mime_type="application/json",
            )

            # Call Gemini Vision API with structured output
            response = self.model.generate_content(
                contents=[RECEIPT_EXTRACTION_PROMPT, image_part],
                generation_config=generation_config
            )

            # Extract token usage metadata
            token_usage = None
            if hasattr(response, 'usage_metadata'):
                token_usage = {
                    'prompt_token_count': getattr(
                        response.usage_metadata, 'prompt_token_count', 0
                    ),
                    'candidates_token_count': getattr(
                        response.usage_metadata, 'candidates_token_count', 0
                    ),
                    'total_token_count': getattr(
                        response.usage_metadata, 'total_token_count', 0
                    ),
                }
                logger.info(f"Token usage: {token_usage}")

            # Parse JSON response
            response_text = response.text.strip()
            logger.info(f"Gemini response: {response_text}")

            # Parse JSON
            data = json.loads(response_text)

            # Create DeliveryReceiptData object with validation
            receipt_data = DeliveryReceiptData(**data)

            # Get confidence score from response
            confidence = data.get("confidence_score", 0.0)

            # Enhance confidence with validation checks
            confidence = self._calculate_confidence(receipt_data, confidence)

            logger.info(
                f"Extracted delivery: {receipt_data.receipt_number} "
                f"- {receipt_data.material_name} "
                f"{receipt_data.net_weight}t (confidence: {confidence:.2f})"
            )

            return receipt_data, confidence, token_usage

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            logger.error(f"Response text: {response_text}")
            return None, 0.0, None

        except Exception as e:
            logger.error(f"Failed to extract receipt data: {e}")
            if 'response_text' in locals():
                logger.error(f"Gemini response was: {response_text}")
            return None, 0.0, None

    def _calculate_confidence(
        self,
        receipt: DeliveryReceiptData,
        base_confidence: float = 1.0
    ) -> float:
        """
        Calculate final confidence score for extracted data.

        Args:
            receipt: Extracted delivery receipt data
            base_confidence: Initial confidence from AI model

        Returns:
            Enhanced confidence score (0.0 to 1.0)
        """
        confidence = base_confidence

        # Check if net weight = gross weight - empty weight
        calculated_net = receipt.gross_weight - receipt.empty_weight
        diff = abs(calculated_net - receipt.net_weight)

        if diff > 0.5:  # More than 0.5 tons difference
            confidence *= 0.7
            logger.warning(
                f"Weight calculation mismatch: "
                f"{receipt.gross_weight} - {receipt.empty_weight} "
                f"= {calculated_net} vs {receipt.net_weight}"
            )

        # Check receipt number quality
        if len(receipt.receipt_number) < 5:
            confidence *= 0.8

        # Check material name quality
        if len(receipt.material_name) < 3:
            confidence *= 0.7

        # Check vehicle number format (should have letters and numbers)
        if len(receipt.vehicle_number) < 4:
            confidence *= 0.8

        return confidence
