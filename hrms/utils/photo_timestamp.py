# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Photo Timestamp Watermarking Utility

Adds visible timestamp + store + employee overlay to photos to prevent
employees from uploading old photos instead of taking fresh ones.

Scope (from CLOSING_REPORT_ENHANCEMENT_PLAN):
- Opening Report - Area Photos: YES
- Closing Report - Area Photos: YES
- Bank Deposit Photos: YES
- Store Visit Photos: YES
- Mid-Shift Checklist Photos: YES
- X-Read / Z-Read Photos: NO (receipt already has date)
- Dashboard Report Photos: NO (screen shows date)
- FQI Report Photos: YES
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime, cint
from datetime import datetime, timedelta
import os
import io
import base64

# Try to import PIL (Pillow)
try:
	from PIL import Image, ImageDraw, ImageFont, ExifTags
	PILLOW_AVAILABLE = True
except ImportError:
	PILLOW_AVAILABLE = False


# Maximum time difference allowed between photo capture and upload (in minutes)
MAX_TIME_DIFFERENCE_MINUTES = 60


def get_exif_datetime(image):
	"""
	Extract the datetime when the photo was taken from EXIF data.

	Args:
		image: PIL Image object

	Returns:
		datetime object or None if not found
	"""
	try:
		exif = image._getexif()
		if not exif:
			return None

		for tag_id, value in exif.items():
			tag = ExifTags.TAGS.get(tag_id, tag_id)
			if tag == 'DateTimeOriginal':
				return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
			elif tag == 'DateTime':
				return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')

		return None
	except Exception:
		return None


def validate_photo_time(image, upload_time=None):
	"""
	Validate that the photo was taken recently (within MAX_TIME_DIFFERENCE_MINUTES).

	Args:
		image: PIL Image object
		upload_time: datetime of upload (defaults to now)

	Returns:
		tuple: (is_valid, capture_time, message)
	"""
	if upload_time is None:
		upload_time = datetime.now()

	capture_time = get_exif_datetime(image)

	if capture_time is None:
		# No EXIF data - allow but flag
		return True, None, "No capture time found in photo metadata"

	time_diff = abs((upload_time - capture_time).total_seconds() / 60)

	if time_diff > MAX_TIME_DIFFERENCE_MINUTES:
		return False, capture_time, _(
			"Photo was taken {0} minutes ago. Please take a fresh photo."
		).format(int(time_diff))

	return True, capture_time, "Photo time validated"


def add_timestamp_watermark(file_url, store_name, employee_name, capture_time=None):
	"""
	Add a semi-transparent timestamp watermark to a photo.

	Args:
		file_url: URL/path to the uploaded file in Frappe
		store_name: Name of the store
		employee_name: Name of the employee who took the photo
		capture_time: Optional datetime when photo was taken (from EXIF)

	Returns:
		str: URL of the watermarked file, or original URL if watermarking failed
	"""
	if not PILLOW_AVAILABLE:
		frappe.log_error("Pillow not installed - cannot add watermark", "Photo Timestamp")
		return file_url

	try:
		# Get the file from Frappe
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		file_path = file_doc.get_full_path()

		if not os.path.exists(file_path):
			frappe.log_error(f"File not found: {file_path}", "Photo Timestamp")
			return file_url

		# Open the image
		image = Image.open(file_path)

		# Get capture time from EXIF if not provided
		if capture_time is None:
			capture_time = get_exif_datetime(image)

		# Use upload time if no EXIF data
		if capture_time is None:
			capture_time = datetime.now()

		# Create watermark text
		timestamp_str = capture_time.strftime("%Y-%m-%d %H:%M:%S")
		watermark_lines = [
			timestamp_str,
			store_name,
			employee_name
		]

		# Add watermark
		watermarked_image = _add_watermark_to_image(image, watermark_lines)

		# Save the watermarked image
		watermarked_path = file_path.replace('.', '_watermarked.')
		watermarked_image.save(watermarked_path, quality=95)

		# Create new file doc for watermarked version
		with open(watermarked_path, 'rb') as f:
			watermarked_content = f.read()

		new_file = frappe.get_doc({
			"doctype": "File",
			"file_name": os.path.basename(watermarked_path),
			"content": watermarked_content,
			"is_private": file_doc.is_private
		})
		new_file.insert(ignore_permissions=True)

		# Clean up temp file
		if os.path.exists(watermarked_path):
			os.remove(watermarked_path)

		return new_file.file_url

	except Exception as e:
		frappe.log_error(f"Failed to add watermark: {str(e)}", "Photo Timestamp")
		return file_url


def _add_watermark_to_image(image, text_lines):
	"""
	Internal function to add watermark text to an image.

	Args:
		image: PIL Image object
		text_lines: List of strings to add as watermark

	Returns:
		PIL Image with watermark
	"""
	# Convert to RGBA for transparency support
	if image.mode != 'RGBA':
		image = image.convert('RGBA')

	# Create a transparent overlay
	overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
	draw = ImageDraw.Draw(overlay)

	# Calculate font size based on image dimensions
	img_width, img_height = image.size
	font_size = max(int(img_height * 0.025), 16)  # 2.5% of height, min 16px

	# Try to use a system font, fall back to default
	try:
		font = ImageFont.truetype("arial.ttf", font_size)
	except Exception:
		try:
			font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
		except Exception:
			font = ImageFont.load_default()

	# Calculate text dimensions
	padding = 10
	line_height = font_size + 5
	text_height = len(text_lines) * line_height + padding * 2

	# Position at bottom-left
	x = padding
	y = img_height - text_height - padding

	# Draw semi-transparent background
	max_text_width = 0
	for line in text_lines:
		bbox = draw.textbbox((0, 0), line, font=font)
		text_width = bbox[2] - bbox[0]
		max_text_width = max(max_text_width, text_width)

	bg_width = max_text_width + padding * 2
	bg_height = text_height

	draw.rectangle(
		[x - padding, y - padding, x + bg_width, y + bg_height],
		fill=(0, 0, 0, 180)  # Semi-transparent black
	)

	# Draw text lines
	current_y = y
	for line in text_lines:
		draw.text((x, current_y), line, font=font, fill=(255, 255, 255, 255))
		current_y += line_height

	# Composite the overlay onto the original image
	watermarked = Image.alpha_composite(image, overlay)

	# Convert back to RGB for JPEG compatibility
	if watermarked.mode == 'RGBA':
		rgb_image = Image.new('RGB', watermarked.size, (255, 255, 255))
		rgb_image.paste(watermarked, mask=watermarked.split()[3])
		return rgb_image

	return watermarked


@frappe.whitelist()
def process_photo_with_timestamp(file_url, store, employee):
	"""
	API endpoint to process a photo with timestamp watermark.

	Args:
		file_url: URL of the uploaded file
		store: Store name or code
		employee: Employee name

	Returns:
		dict with status and watermarked_url
	"""
	if not file_url:
		return {"status": "error", "message": "No file URL provided"}

	try:
		# Get store name if store code provided
		store_name = store
		if frappe.db.exists("BEI Store", store):
			store_doc = frappe.get_doc("BEI Store", store)
			store_name = store_doc.store_name or store_doc.store_code

		# Get employee name
		employee_name = employee
		if frappe.db.exists("Employee", employee):
			emp_doc = frappe.get_doc("Employee", employee)
			employee_name = emp_doc.employee_name or employee

		# Add watermark
		watermarked_url = add_timestamp_watermark(file_url, store_name, employee_name)

		return {
			"status": "success",
			"original_url": file_url,
			"watermarked_url": watermarked_url
		}

	except Exception as e:
		frappe.log_error(f"Photo timestamp processing failed: {str(e)}", "Photo Timestamp")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def validate_and_watermark_photo(file_url, store, employee, strict=False):
	"""
	Validate photo time and add watermark.

	Args:
		file_url: URL of the uploaded file
		store: Store name or code
		employee: Employee name
		strict: If True, reject photos older than MAX_TIME_DIFFERENCE_MINUTES

	Returns:
		dict with validation result and watermarked URL
	"""
	if not PILLOW_AVAILABLE:
		return {
			"status": "warning",
			"message": "Photo validation unavailable - Pillow not installed",
			"watermarked_url": file_url
		}

	try:
		# Get the file
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		file_path = file_doc.get_full_path()

		if not os.path.exists(file_path):
			return {"status": "error", "message": "File not found"}

		# Open and validate
		image = Image.open(file_path)
		is_valid, capture_time, message = validate_photo_time(image)

		if not is_valid and strict:
			return {
				"status": "error",
				"message": message,
				"capture_time": capture_time.isoformat() if capture_time else None
			}

		# Get store and employee names
		store_name = store
		if frappe.db.exists("BEI Store", store):
			store_doc = frappe.get_doc("BEI Store", store)
			store_name = store_doc.store_name or store_doc.store_code

		employee_name = employee
		if frappe.db.exists("Employee", employee):
			emp_doc = frappe.get_doc("Employee", employee)
			employee_name = emp_doc.employee_name or employee

		# Add watermark
		watermarked_url = add_timestamp_watermark(file_url, store_name, employee_name, capture_time)

		return {
			"status": "success" if is_valid else "warning",
			"message": message,
			"original_url": file_url,
			"watermarked_url": watermarked_url,
			"capture_time": capture_time.isoformat() if capture_time else None
		}

	except Exception as e:
		frappe.log_error(f"Photo validation failed: {str(e)}", "Photo Timestamp")
		return {"status": "error", "message": str(e)}
