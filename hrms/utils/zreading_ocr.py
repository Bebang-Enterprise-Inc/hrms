# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Z-Reading OCR Extraction and Validation

Uses Gemini 3 Flash for extracting sales data from Z-Reading thermal receipt photos.
Cross-validates OCR results against POS CSV exports for fraud detection.

Dual-Source Validation Principle:
- CSV data = primary source (accurate, structured)
- Z-Reading photo = audit evidence (tamper-proof physical receipt)
- Any difference between CSV and OCR = flag for accounting review

Cost: ~$0.0002 per extraction (300K images = ~$60/month)
"""

import frappe
import json
from typing import Dict, Any, Optional, List
import base64


# Gemini 3 Flash model ID
GEMINI_MODEL = "gemini-3.0-flash"

# OCR extraction prompt
EXTRACTION_PROMPT = """
You are analyzing a Z-Reading thermal receipt from a MOSAIC POS system.
Extract the following fields from this receipt image.

Return ONLY valid JSON with these exact keys (no explanation, no markdown):

{
  "store_name": "string - store/location name if visible",
  "date": "YYYY-MM-DD format",
  "beginning_si": "integer - beginning invoice number",
  "ending_si": "integer - ending invoice number",
  "transaction_count": "integer - number of transactions (often labeled EOD Counter)",
  "gross_sales": "float - gross sales amount",
  "net_sales": "float - net sales amount",
  "vat_amount": "float - VAT amount",
  "vatable_sales": "float - vatable sales if shown",
  "vat_exempt_sales": "float - vat exempt sales if shown",
  "sc_discount": "float - senior citizen discount amount",
  "pwd_discount": "float - PWD discount amount",
  "other_discount": "float - other discounts if shown",
  "confidence": "float 0-1 - your confidence in the extraction accuracy"
}

Important:
- Use null for any field you cannot read clearly
- Numbers should NOT include commas
- Confidence should reflect overall readability
- Look for common labels: "GROSS SALES", "NET SALES", "VAT", "DISC", "SI FROM", "SI TO"
"""


def extract_zreading(image_data: bytes, mime_type: str = "image/jpeg") -> Dict[str, Any]:
    """
    Extract Z-Reading data from a receipt photo using Gemini 3 Flash.

    Args:
        image_data: Raw image bytes
        mime_type: Image MIME type (image/jpeg, image/png)

    Returns:
        Dictionary with extracted fields:
        {
            "store_name": "BEBANG UPTOWN",
            "date": "2026-01-30",
            "beginning_si": 16526,
            "ending_si": 16735,
            "gross_sales": 65474.00,
            "net_sales": 55587.24,
            "vat_amount": 5575.73,
            "sc_discount": 1223.28,
            "pwd_discount": 1056.85,
            "confidence": 0.95,
            "success": True
        }
    """
    try:
        import google.generativeai as genai

        # Get API key from site config
        api_key = frappe.conf.get("gemini_api_key")
        if not api_key:
            return {"success": False, "error": "Gemini API key not configured"}

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)

        # Prepare image part
        image_part = {
            "mime_type": mime_type,
            "data": image_data
        }

        # Generate content
        response = model.generate_content(
            [image_part, EXTRACTION_PROMPT],
            generation_config=genai.GenerationConfig(temperature=0.1)
        )

        # Parse response
        text = response.text.strip()

        # Clean up markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
            if text.startswith("json"):
                text = text[4:]

        # Parse JSON
        data = json.loads(text)
        data["success"] = True

        # Convert string numbers to actual numbers
        for field in ["beginning_si", "ending_si", "transaction_count"]:
            if data.get(field) is not None:
                try:
                    data[field] = int(data[field])
                except (ValueError, TypeError):
                    pass

        for field in ["gross_sales", "net_sales", "vat_amount", "vatable_sales",
                      "vat_exempt_sales", "sc_discount", "pwd_discount",
                      "other_discount", "confidence"]:
            if data.get(field) is not None:
                try:
                    data[field] = float(data[field])
                except (ValueError, TypeError):
                    pass

        return data

    except json.JSONDecodeError as e:
        frappe.log_error(f"OCR JSON parse error: {str(e)}", "Z-Reading OCR")
        return {"success": False, "error": f"Failed to parse OCR response: {str(e)}"}

    except Exception as e:
        frappe.log_error(f"OCR extraction error: {str(e)}", "Z-Reading OCR")
        return {"success": False, "error": str(e)}


def validate_zreading(csv_data: Dict[str, Any], ocr_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare CSV-extracted data against OCR-extracted data.

    Args:
        csv_data: Data extracted from POS CSV files
        ocr_data: Data extracted from Z-Reading photo OCR

    Returns:
        Validation result:
        {
            "status": "match" | "mismatch" | "low_confidence",
            "errors": [
                {
                    "field": "gross_sales",
                    "csv_value": 65474.00,
                    "ocr_value": 65474.00,
                    "diff": 0.00,
                    "is_match": True
                },
                ...
            ],
            "recommendation": "Use CSV values",
            "confidence": 0.95
        }
    """
    # Fields to compare
    integer_fields = ["beginning_si", "ending_si", "transaction_count"]
    currency_fields = ["gross_sales", "net_sales", "vat_amount", "sc_discount", "pwd_discount"]

    # Tolerance: ₱1 for currency (rounding), 0 for integers
    currency_tolerance = 1.0
    integer_tolerance = 0

    errors = []
    has_mismatch = False

    # Compare integer fields (must match exactly)
    for field in integer_fields:
        csv_val = csv_data.get(field)
        ocr_val = ocr_data.get(field)

        if csv_val is not None and ocr_val is not None:
            diff = abs(csv_val - ocr_val)
            is_match = diff <= integer_tolerance

            errors.append({
                "field": field,
                "csv_value": csv_val,
                "ocr_value": ocr_val,
                "diff": diff,
                "is_match": is_match
            })

            if not is_match:
                has_mismatch = True

    # Compare currency fields (allow ₱1 tolerance for centavo rounding)
    for field in currency_fields:
        csv_val = csv_data.get(field)
        ocr_val = ocr_data.get(field)

        # Map CSV field names if different
        csv_field_map = {
            "sc_discount": "discount_senior",
            "pwd_discount": "discount_pwd"
        }
        if field in csv_field_map:
            csv_val = csv_data.get(csv_field_map[field], csv_val)

        if csv_val is not None and ocr_val is not None:
            diff = abs(float(csv_val) - float(ocr_val))
            is_match = diff <= currency_tolerance

            errors.append({
                "field": field,
                "csv_value": csv_val,
                "ocr_value": ocr_val,
                "diff": diff,
                "is_match": is_match
            })

            if not is_match:
                has_mismatch = True

    # Determine status
    confidence = ocr_data.get("confidence", 0)

    if confidence < 0.7:
        status = "low_confidence"
        recommendation = "Manual verification required - OCR confidence too low"
    elif has_mismatch:
        status = "mismatch"
        recommendation = "Flag for accounting review - CSV and OCR values differ"
    else:
        status = "match"
        recommendation = "Use CSV values (OCR confirms)"

    return {
        "status": status,
        "errors": errors,
        "recommendation": recommendation,
        "confidence": confidence,
        "has_mismatch": has_mismatch
    }


# ==============================================================================
# FRAPPE API ENDPOINTS
# ==============================================================================

@frappe.whitelist()
def extract_zreading_from_file(file_url: str = None, file_content: str = None):
    """
    Extract Z-Reading data from a file URL or base64 content.

    Args:
        file_url: Frappe file URL (e.g., /files/zreading.jpg)
        file_content: Base64 encoded image data

    Returns:
        Extracted Z-Reading data
    """
    image_data = None
    mime_type = "image/jpeg"

    if file_url:
        # Get file from Frappe
        try:
            file_doc = frappe.get_doc("File", {"file_url": file_url})
            image_data = file_doc.get_content()

            # Determine mime type from extension
            if file_url.lower().endswith(".png"):
                mime_type = "image/png"
            elif file_url.lower().endswith(".webp"):
                mime_type = "image/webp"
        except Exception as e:
            return {"success": False, "error": f"Failed to load file: {str(e)}"}

    elif file_content:
        # Decode base64
        try:
            if "," in file_content:
                # Data URL format: data:image/jpeg;base64,/9j/4AAQ...
                header, data = file_content.split(",", 1)
                if "png" in header:
                    mime_type = "image/png"
                elif "webp" in header:
                    mime_type = "image/webp"
                image_data = base64.b64decode(data)
            else:
                image_data = base64.b64decode(file_content)
        except Exception as e:
            return {"success": False, "error": f"Failed to decode image: {str(e)}"}

    else:
        return {"success": False, "error": "Either file_url or file_content is required"}

    return extract_zreading(image_data, mime_type)


@frappe.whitelist()
def validate_pos_upload(pos_upload_name: str):
    """
    Validate a POS Upload against its Z-Reading photo.

    Args:
        pos_upload_name: Name of BEI POS Upload document

    Returns:
        Validation result with comparison details
    """
    doc = frappe.get_doc("BEI POS Upload", pos_upload_name)

    # Get CSV extracted data
    if not doc.extracted_data:
        return {"success": False, "error": "POS data not yet extracted. Upload files first."}

    try:
        csv_data = json.loads(doc.extracted_data)
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid extracted data format"}

    # Check if there's a Z-Reading photo
    # First check if linked to a closing report
    closing_report = frappe.db.get_value(
        "BEI Store Closing Report",
        {"store": doc.store, "report_date": doc.pos_date},
        "name"
    )

    if not closing_report:
        return {"success": False, "error": "No closing report found for this date"}

    closing_doc = frappe.get_doc("BEI Store Closing Report", closing_report)

    if not closing_doc.photo_zread:
        return {"success": False, "error": "No Z-Reading photo attached to closing report"}

    # Extract from Z-Reading photo
    ocr_result = extract_zreading_from_file(file_url=closing_doc.photo_zread)

    if not ocr_result.get("success"):
        return ocr_result

    # Validate
    validation = validate_zreading(csv_data, ocr_result)

    # Store validation result
    doc.db_set("validation_status", validation["status"])
    doc.db_set("validation_result", json.dumps({
        "ocr_data": ocr_result,
        "validation": validation
    }))

    if validation["status"] == "mismatch":
        doc.db_set("status", "Discrepancy")
    elif validation["status"] == "match":
        doc.db_set("status", "Verified")

    return {
        "success": True,
        "csv_data": csv_data,
        "ocr_data": ocr_result,
        "validation": validation
    }
