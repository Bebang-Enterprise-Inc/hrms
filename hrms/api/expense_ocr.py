"""
Expense Receipt OCR using Gemini 2.0 Flash
Extracts vendor, amount, date, and line items from receipt photos.

Author: Claude Code
Date: 2026-02-02
Reference: hrms/utils/zreading_ocr.py (proven pattern)
"""
import frappe
from frappe import _
import json
import base64
import google.generativeai as genai


# OCR extraction prompt
EXTRACTION_PROMPT = """Extract data from this receipt image.

Return ONLY valid JSON with these fields:
{
    "vendor": "Store or vendor name",
    "amount": 123.45,
    "date": "2026-01-30",
    "line_items": [
        {"description": "Item name", "amount": 50.00}
    ],
    "raw_text": "All visible text on receipt",
    "confidence": 0.95
}

Rules:
- amount: Total amount paid (look for TOTAL, AMOUNT DUE, or largest number)
- date: Transaction date in YYYY-MM-DD format
- vendor: Business name at top of receipt
- line_items: Individual items purchased (if visible)
- confidence: Your confidence in extraction accuracy (0-1)
- If any field cannot be extracted, use null

Return ONLY the JSON object, no markdown or explanation."""


def get_gemini_model():
    """Get configured Gemini model."""
    api_key = frappe.conf.get("gemini_api_key")
    if not api_key:
        raise ValueError("Gemini API key not configured. Add 'gemini_api_key' to site_config.json")

    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.0-flash")


@frappe.whitelist()
def extract_receipt_data(image_path: str = None, image_content: str = None):
    """
    Extract data from receipt image using Gemini Vision.

    Args:
        image_path: Frappe file URL (e.g., /files/receipt.jpg)
        image_content: Base64 encoded image data

    Returns:
        {
            "vendor": "Ace Hardware",
            "amount": 450.00,
            "date": "2026-01-30",
            "line_items": [...],
            "raw_text": "...",
            "confidence": 0.95,
            "status": "success" | "partial" | "failed"
        }
    """
    try:
        # Get image bytes
        if image_content:
            # Base64 input from frontend
            if "," in image_content:
                # Data URL format: data:image/jpeg;base64,/9j/4AAQ...
                header, data = image_content.split(",", 1)
                mime_type = "image/jpeg"
                if "png" in header:
                    mime_type = "image/png"
                elif "webp" in header:
                    mime_type = "image/webp"
                image_bytes = base64.b64decode(data)
            else:
                image_bytes = base64.b64decode(image_content)
                mime_type = "image/jpeg"
        elif image_path:
            # Frappe file URL
            file_doc = frappe.get_doc("File", {"file_url": image_path})
            image_bytes = file_doc.get_content()
            mime_type = "image/jpeg"
            if image_path.lower().endswith(".png"):
                mime_type = "image/png"
            elif image_path.lower().endswith(".webp"):
                mime_type = "image/webp"
        else:
            return {
                "status": "failed",
                "error": "No image provided"
            }

        # Prepare image for Gemini
        image_part = {
            "mime_type": mime_type,
            "data": image_bytes
        }

        # Call Gemini
        model = get_gemini_model()
        response = model.generate_content(
            [image_part, EXTRACTION_PROMPT],
            generation_config=genai.GenerationConfig(temperature=0.1)
        )

        # Parse response
        text = response.text.strip()

        # Clean markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
            if text.startswith("json"):
                text = text[4:]

        data = json.loads(text)

        # Validate and determine status
        has_vendor = bool(data.get("vendor"))
        has_amount = data.get("amount") is not None
        has_date = bool(data.get("date"))
        confidence = data.get("confidence", 0)

        if has_vendor and has_amount and has_date and confidence >= 0.7:
            data["status"] = "success"
        elif has_amount:  # At minimum we need amount
            data["status"] = "partial"
        else:
            data["status"] = "failed"

        return data

    except json.JSONDecodeError as e:
        frappe.log_error(f"OCR JSON parse error: {str(e)}", "Receipt OCR")
        return {
            "status": "failed",
            "error": f"Failed to parse OCR response: {str(e)}",
            "raw_text": text if 'text' in dir() else None
        }
    except Exception as e:
        frappe.log_error(f"OCR error: {str(e)}", "Receipt OCR")
        return {
            "status": "failed",
            "error": str(e)
        }


@frappe.whitelist()
def test_ocr(image_path: str):
    """
    Test OCR on a specific image.
    Usage: bench execute hrms.api.expense_ocr.test_ocr --args '["path/to/image.jpg"]'
    """
    result = extract_receipt_data(image_path=image_path)
    print(json.dumps(result, indent=2))
    return result
