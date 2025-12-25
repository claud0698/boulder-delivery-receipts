"""Google Gemini Vision API client for delivery receipt processing."""

import json
from typing import Optional, Tuple
from io import BytesIO
from functools import lru_cache
from google import genai
from google.genai import types
from PIL import Image
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models.delivery import DeliveryReceiptData, MATERIAL_TYPES
from ..config import settings
from .prompts import (
    SYSTEM_PROMPT,
    RECEIPT_EXTRACTION_PROMPT,
    CATEGORIZATION_SYSTEM_PROMPT,
    CATEGORIZATION_PROMPT
)


class GeminiClient:
    """Client for Google Gemini Vision API."""

    def __init__(self):
        """Initialize Gemini client."""
        try:
            self.client = genai.Client(
                api_key=settings.gemini_api_key
            )
            self.model = "gemini-2.5-flash-lite"
            logger.info("Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
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
        image_bytes: bytes
    ) -> Tuple[Optional[DeliveryReceiptData], float]:
        """
        Extract delivery receipt data from image.

        Returns:
            Tuple of (DeliveryReceiptData or None, confidence_score)
        """
        try:
            # Preprocess image
            img = self.preprocess_image(image_bytes)

            # Convert to bytes for Gemini (JPEG is smaller and faster to upload)
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format="JPEG", quality=85, optimize=True)
            img_bytes = img_byte_arr.getvalue()

            # Create content with system instruction and user prompt
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=(
                                f"{SYSTEM_PROMPT}\n\n"
                                f"{RECEIPT_EXTRACTION_PROMPT}"
                            )
                        ),
                        types.Part.from_bytes(
                            data=img_bytes,
                            mime_type="image/jpeg"
                        ),
                    ],
                ),
            ]

            # Configure generation with JSON response
            generate_content_config = types.GenerateContentConfig(
                response_mime_type="application/json",
            )

            # Call Gemini Vision API with structured output
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            )

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

            return receipt_data, confidence

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            logger.error(f"Response text: {response_text}")
            return None, 0.0

        except Exception as e:
            logger.error(f"Failed to extract receipt data: {e}")
            if 'response_text' in locals():
                logger.error(f"Gemini response was: {response_text}")
            return None, 0.0

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

    @lru_cache(maxsize=128)
    def _categorize_with_rules(self, material_name: str) -> Optional[str]:
        """
        Fast rule-based categorization for common materials.
        Cached to avoid repeated processing of same material names.

        Args:
            material_name: Material name (Indonesian/Chinese)

        Returns:
            Category name if matched, None otherwise
        """
        material_lower = material_name.lower()

        # Quick categorization rules for Indonesian boulder materials
        if "batu pecah 1/2" in material_lower or ("1/2" in material_lower and "pecah" in material_lower):
            return "Batu Pecah 1/2"
        elif "batu pecah 2/3" in material_lower or ("2/3" in material_lower and "pecah" in material_lower):
            return "Batu Pecah 2/3"
        elif "batu pecah 3/5" in material_lower or ("3/5" in material_lower and "pecah" in material_lower):
            return "Batu Pecah 3/5"
        elif "batu sungai" in material_lower:
            return "Batu Sungai"
        elif "boulder" in material_lower:
            return "Boulder"
        elif "kerikil" in material_lower:
            return "Kerikil"
        elif "pasir" in material_lower:
            return "Pasir"
        elif "abu batu" in material_lower or "screenings" in material_lower:
            return "Abu Batu"

        return None

    @lru_cache(maxsize=128)
    def _categorize_with_gemini(self, material_name: str) -> str:
        """
        Categorize material using Gemini API.
        Cached to avoid redundant API calls for same material names.

        Args:
            material_name: Material name (Indonesian/Chinese)

        Returns:
            Category name from MATERIAL_TYPES
        """
        try:
            prompt_text = CATEGORIZATION_PROMPT.format(
                merchant=material_name
            )

            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=(
                                f"{CATEGORIZATION_SYSTEM_PROMPT}\n\n"
                                f"{prompt_text}"
                            )
                        ),
                    ],
                ),
            ]

            generate_content_config = types.GenerateContentConfig(
                temperature=0.1,
            )

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            )

            category = response.text.strip()
            # Validate category
            if category in MATERIAL_TYPES:
                logger.info(f"Gemini categorized '{material_name}' as '{category}'")
                return category
            else:
                logger.warning(
                    f"Invalid category '{category}', defaulting to 'Lainnya'"
                )
                return "Lainnya"

        except Exception as e:
            logger.error(f"Failed to categorize material with Gemini: {e}")
            return "Lainnya"

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    def categorize_material(
        self,
        material_name: str
    ) -> str:
        """
        Categorize material type using rules first, then Gemini if needed.
        Results are cached to avoid redundant processing and API calls.

        Args:
            material_name: Material name (Indonesian/Chinese)

        Returns:
            Category name from MATERIAL_TYPES
        """
        # Try rule-based categorization first (fast, cached)
        category = self._categorize_with_rules(material_name)
        if category:
            logger.debug(f"Rule-based categorization: '{material_name}' -> '{category}'")
            return category

        # Fall back to Gemini API (slower, but cached)
        logger.debug(f"Using Gemini for categorization: '{material_name}'")
        return self._categorize_with_gemini(material_name)
