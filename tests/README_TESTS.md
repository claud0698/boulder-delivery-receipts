# Test Scripts for Revamped Image Processing Flow

This folder contains test scripts to verify the new image processing flow that uses GCS URIs for Vertex AI processing.

## Available Tests

### 1. Single Image Test (`test_single_image.py`)
Tests the complete flow for processing a single receipt image:
- Upload image to Google Cloud Storage
- Extract receipt data using Vertex AI with GCS URI
- Categorize material type
- Create delivery record

**Run:**
```bash
python tests/test_single_image.py
```

### 2. Multiple Images Test (`test_multiple_images.py`)
Tests the batch processing flow for 2 receipt images:
- Batch upload all images to GCS (parallel)
- Process each image sequentially with Vertex AI
- Aggregate results
- Prepare for batch save to Sheets

**Run:**
```bash
python tests/test_multiple_images.py
```

### 3. Comprehensive Test Suite (`test_revamped_flow.py`)
Runs all tests together:
- Single image flow
- Batch upload to GCS
- Multiple images flow

**Run:**
```bash
python tests/test_revamped_flow.py
```

## Test Data

Tests use sample images from `tests/Samples/`:
- `Sample1.jpeg` - First test receipt
- `Sample2.jpeg` - Second test receipt

## Important Notes

### Saving to Google Sheets

**By default, tests do NOT save to Google Sheets** to prevent test data pollution.

To enable actual saving, uncomment the save sections in the test scripts:

```python
# Uncomment to actually save to Google Sheets:
# success = await asyncio.to_thread(
#     sheets_client.append_delivery,
#     delivery
# )
```

### Requirements

Before running tests, ensure:
1. **Environment variables** are set (see `.env.example`)
2. **Google credentials** are configured (`GOOGLE_APPLICATION_CREDENTIALS`)
3. **GCS bucket** exists and is accessible
4. **Sample images** exist in `tests/Samples/`

### Expected Output

Successful test output should show:
```
============================================================
SINGLE IMAGE PROCESSING TEST
============================================================
Using test image: tests/Samples/Sample1.jpeg

[1/5] Uploading image to GCS...
✅ Uploaded to: gs://your-bucket/...

[2/5] Extracting receipt data using GCS URI...
✅ Receipt Number: ABC123
   Material: Batu Pecah 1/2
   Net Weight: 15.5 ton
   Confidence: 98%

[3/5] Categorizing material...
✅ Material Type: Batu Pecah 1/2

[4/5] Creating delivery record...
✅ Delivery record created

[5/5] Saving to Google Sheets...
   ⚠️  Skipped - uncomment to actually save

============================================================
✅ SINGLE IMAGE TEST PASSED
============================================================
```

## Troubleshooting

### Image Not Found
```
Test image not found: tests/Samples/Sample1.jpeg
```
**Solution**: Ensure sample images exist in `tests/Samples/` folder

### GCS Upload Failed
```
Failed to upload image to Cloud Storage
```
**Solution**: Check GCS bucket permissions and credentials

### Extraction Failed
```
Failed to extract receipt data
```
**Solution**: Verify Vertex AI API is enabled and credentials are valid

## Running in Production

To test with actual Sheets saving (use with caution):

1. Use a **test spreadsheet** (not production)
2. Uncomment save sections in test scripts
3. Run the tests
4. Verify data in test spreadsheet
5. Delete test data when done

## CI/CD Integration

To run tests in CI/CD:

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
export GCS_BUCKET_NAME=your-test-bucket

# Run tests (without saving to Sheets)
python tests/test_single_image.py
python tests/test_multiple_images.py
```

Exit code:
- `0` = Test passed
- `1` = Test failed
