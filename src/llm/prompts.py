"""Prompts for Gemini Vision API - Boulder Delivery Receipt Extraction."""

SYSTEM_PROMPT = """You are an AI-Powered Delivery Receipt OCR bot \
specializing in extracting data from Indonesian weighing receipts \
(BUKTI PENIMBANGAN). Your primary goal is to extract structured, \
quantitative data from the provided image and format it into a single, \
valid JSON object. You must adhere strictly to the specified JSON schema \
and must not include any additional commentary, markdown formatting, or \
text outside of the JSON object. The receipts are in Indonesian language \
and may contain Chinese characters.

IMPORTANT: The image may be rotated at any angle (90°, 180°, 270°). You must \
read the text regardless of orientation and extract the data accurately. \

If the image is unreadable or not a weighing receipt, return the required \
JSON fields with empty strings/zeros."""

RECEIPT_EXTRACTION_PROMPT = """Extract the complete delivery data from \
this Indonesian weighing receipt (BUKTI PENIMBANGAN).

Focus on accurately identifying and extracting the following fields:
1. NO NOTA: Receipt/note number (e.g., A125BD00183725122415O1)
2. NOMOR TIMBANGAN: Scale number (e.g., T21)
3. WAKTU PENIMBANGAN: Weighing date and time (e.g., 2025-12-24 15:23:34)
4. NOMOR UNIT: Vehicle registration number (e.g., B9683TVX)
5. NAMA MATERIAL: Material name (may include Chinese characters, e.g., \
"BATU PECAH 1/2 石子")
6. BERAT ISI: Gross weight in tons (weight with material)
7. BERAT KOSONG: Empty weight in tons (vehicle weight without material)
8. BERAT BERSIH: Net weight in tons (actual material weight)

Required fields:
- receipt_number: NO NOTA value (string)
- scale_number: NOMOR TIMBANGAN value (string)
- weighing_datetime: WAKTU PENIMBANGAN in YYYY-MM-DD HH:MM:SS format (string)
- vehicle_number: NOMOR UNIT value (string)
- material_name: NAMA MATERIAL value, include both Indonesian and Chinese \
text if present (string)
- gross_weight: BERAT ISI value in tons (number)
- empty_weight: BERAT KOSONG value in tons (number)
- net_weight: BERAT BERSIH value in tons (number)
- confidence_score: Your confidence in extraction accuracy 0.0-1.0 (number)

Important constraints:
- Convert datetime to YYYY-MM-DD HH:MM:SS format (24-hour format)
- All weight values must be numerical (float), representing tons
- Net weight should approximately equal gross_weight - empty_weight
- Preserve material name exactly as shown, including special characters
- If you cannot clearly read a value, make your best guess but note lower \
confidence score"""

RECEIPT_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "receipt_number": {
            "type": "string",
            "description": "NO NOTA - Receipt/note number"
        },
        "scale_number": {
            "type": "string",
            "description": "NOMOR TIMBANGAN - Scale identification number"
        },
        "weighing_datetime": {
            "type": "string",
            "description": "WAKTU PENIMBANGAN in YYYY-MM-DD HH:MM:SS format"
        },
        "vehicle_number": {
            "type": "string",
            "description": "NOMOR UNIT - Vehicle registration plate number"
        },
        "material_name": {
            "type": "string",
            "description": "NAMA MATERIAL - Material/boulder type name"
        },
        "gross_weight": {
            "type": "number",
            "description": "BERAT ISI - Gross weight in tons (numeric only)"
        },
        "empty_weight": {
            "type": "number",
            "description": "BERAT KOSONG - Empty vehicle weight in tons"
        },
        "net_weight": {
            "type": "number",
            "description": "BERAT BERSIH - Net material weight in tons"
        },
        "confidence_score": {
            "type": "number",
            "description": "Extraction confidence level (0.0 to 1.0)"
        }
    },
    "required": [
        "receipt_number",
        "scale_number",
        "weighing_datetime",
        "vehicle_number",
        "material_name",
        "gross_weight",
        "empty_weight",
        "net_weight",
        "confidence_score"
    ]
}


CATEGORIZATION_SYSTEM_PROMPT = """You are a Material Type Categorization \
specialist for boulder and construction materials. Your task is to analyze \
the provided material name (which may be in Indonesian and/or Chinese) and \
assign it to one category from the list. You must return ONLY the category \
name in Indonesian. Common patterns: 'BATU PECAH' = crushed stone, look for \
size like 1/2, 2/3, 3/5."""

CATEGORIZATION_PROMPT = """Material: "{merchant}"

Categories: Batu Pecah 1/2, Batu Pecah 2/3, Batu Pecah 3/5, Batu Sungai, \
Boulder, Kerikil, Pasir, Abu Batu, Lainnya

Return ONLY the category name (in Indonesian)."""
