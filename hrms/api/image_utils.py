"""
Image utility APIs for photo processing

Provides server-side image processing including:
- Timestamp watermarking for store operations photos
- Image validation and compression
"""

import frappe
from frappe import _
import base64
import io
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ExifTags


@frappe.whitelist()
def add_timestamp_watermark(image_data: str, timestamp: str = None, location: str = None):
    """
    Add a timestamp watermark to an image

    Args:
        image_data: Base64 encoded image (with or without data URL prefix)
        timestamp: Optional timestamp string (ISO format). If not provided, uses current time.
        location: Optional location text to include in watermark

    Returns:
        dict with watermarked image as base64 data URL
    """
    try:
        # Parse the base64 data
        if ',' in image_data:
            # Has data URL prefix (e.g., "data:image/jpeg;base64,...")
            header, base64_data = image_data.split(',', 1)
            mime_type = header.split(':')[1].split(';')[0] if ':' in header else 'image/jpeg'
        else:
            base64_data = image_data
            mime_type = 'image/jpeg'

        # Decode the image
        image_bytes = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if necessary (for JPEG output)
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')

        # Get or parse timestamp
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                dt = datetime.now()
        else:
            dt = datetime.now()

        # Try to get original capture time from EXIF
        exif_date = _get_exif_datetime(image)
        if exif_date:
            dt = exif_date

        # Format timestamp for display
        timestamp_text = dt.strftime("%Y-%m-%d %H:%M:%S")

        # Build watermark text
        watermark_lines = [timestamp_text]
        if location:
            watermark_lines.append(location)
        watermark_text = "\n".join(watermark_lines)

        # Add watermark
        watermarked = _add_watermark_to_image(image, watermark_text)

        # Convert back to base64
        output_buffer = io.BytesIO()
        watermarked.save(output_buffer, format='JPEG', quality=85)
        output_base64 = base64.b64encode(output_buffer.getvalue()).decode('utf-8')

        return {
            "success": True,
            "image": f"data:image/jpeg;base64,{output_base64}",
            "timestamp": timestamp_text,
            "original_dimensions": f"{image.width}x{image.height}",
        }

    except Exception as e:
        frappe.log_error(f"Error adding watermark: {str(e)}", "Image Watermark Error")
        return {
            "success": False,
            "error": str(e)
        }


def _get_exif_datetime(image: Image.Image) -> datetime:
    """Extract original capture datetime from EXIF data"""
    try:
        exif = image._getexif()
        if not exif:
            return None

        # Find DateTimeOriginal tag
        for tag_id, value in exif.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            if tag == 'DateTimeOriginal':
                # EXIF format: "YYYY:MM:DD HH:MM:SS"
                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")

        # Fallback to DateTime tag
        for tag_id, value in exif.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            if tag == 'DateTime':
                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")

    except Exception:
        pass

    return None


def _add_watermark_to_image(image: Image.Image, text: str) -> Image.Image:
    """
    Add a semi-transparent watermark to the bottom-right corner of an image
    """
    # Create a copy to avoid modifying the original
    watermarked = image.copy()
    draw = ImageDraw.Draw(watermarked)

    # Calculate font size based on image dimensions (roughly 2.5% of min dimension)
    min_dim = min(image.width, image.height)
    font_size = max(16, min(48, int(min_dim * 0.025)))

    # Try to use a good font, fall back to default
    try:
        # Try common system fonts
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:\\Windows\\Fonts\\arial.ttf",
            "arial.ttf",
        ]
        font = None
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except (IOError, OSError):
                continue

        if font is None:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # Get text size using textbbox
    lines = text.split('\n')
    max_width = 0
    total_height = 0
    line_heights = []

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1]
        max_width = max(max_width, line_width)
        total_height += line_height + 4  # 4px line spacing
        line_heights.append(line_height)

    # Padding
    padding = 10

    # Position: bottom-right corner
    x = image.width - max_width - padding - 10
    y = image.height - total_height - padding - 10

    # Draw semi-transparent background
    bg_x1 = x - padding
    bg_y1 = y - padding
    bg_x2 = image.width - 10
    bg_y2 = image.height - 10

    # Create overlay for semi-transparent background
    overlay = Image.new('RGBA', watermarked.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill=(0, 0, 0, 160))

    # Convert to RGBA for compositing
    if watermarked.mode != 'RGBA':
        watermarked = watermarked.convert('RGBA')

    watermarked = Image.alpha_composite(watermarked, overlay)

    # Draw text on the composited image
    draw = ImageDraw.Draw(watermarked)
    current_y = y
    for i, line in enumerate(lines):
        draw.text((x, current_y), line, font=font, fill=(255, 255, 255, 255))
        current_y += line_heights[i] + 4

    # Convert back to RGB for JPEG
    return watermarked.convert('RGB')


@frappe.whitelist()
def validate_photo_metadata(image_data: str, max_age_minutes: int = 60):
    """
    Validate that a photo was taken within the specified time window

    Args:
        image_data: Base64 encoded image
        max_age_minutes: Maximum age in minutes (default: 60)

    Returns:
        dict with validation result
    """
    try:
        # Parse the base64 data
        if ',' in image_data:
            _, base64_data = image_data.split(',', 1)
        else:
            base64_data = image_data

        # Decode the image
        image_bytes = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_bytes))

        # Get EXIF datetime
        capture_date = _get_exif_datetime(image)

        if not capture_date:
            return {
                "valid": True,
                "reason": "no_exif_data",
                "message": "No EXIF timestamp found in image"
            }

        # Calculate age
        now = datetime.now()
        age_delta = now - capture_date
        age_minutes = int(age_delta.total_seconds() / 60)

        if age_minutes > max_age_minutes:
            return {
                "valid": False,
                "reason": "too_old",
                "age_minutes": age_minutes,
                "capture_date": capture_date.isoformat(),
                "message": f"Photo is {age_minutes} minutes old (max: {max_age_minutes})"
            }

        if age_minutes < -5:  # Allow 5 min tolerance for clock differences
            return {
                "valid": False,
                "reason": "future_date",
                "age_minutes": age_minutes,
                "capture_date": capture_date.isoformat(),
                "message": "Photo has a future timestamp"
            }

        return {
            "valid": True,
            "reason": "valid",
            "age_minutes": age_minutes,
            "capture_date": capture_date.isoformat(),
            "message": "Photo is within valid time window"
        }

    except Exception as e:
        frappe.log_error(f"Error validating photo: {str(e)}", "Photo Validation Error")
        return {
            "valid": True,  # Be lenient on errors
            "reason": "validation_error",
            "message": str(e)
        }
