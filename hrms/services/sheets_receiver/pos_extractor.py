"""
POS File Extractor for Sheets Receiver Service.

Extracts data from POS export files (Daily Sales, Transactions, Product Mix, etc.)
using the same logic developed for January 2026 extraction.

File Types Supported:
- Daily Sales Revenue (header row 9)
- Sales Summary (header row 9)
- Transaction Report (header row 0)
- Product Mix (header row 11)
- Discount Report (header row 9)
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)

# Report type detection patterns
REPORT_PATTERNS = {
    'daily_sales_revenue': [
        r'daily.?sales.?revenue',
        r'dailysales',
    ],
    'sales_summary': [
        r'sales.?summary',
        r'salessummary',
    ],
    'transaction_report': [
        r'transaction.?report',
        r'transactions?\.xlsx',
    ],
    'productmix': [
        r'product.?mix',
        r'productmix',
    ],
    'discount_report': [
        r'discount.?report',
        r'discounts?\.xlsx',
    ]
}

# Schema definitions (from POS_SCHEMAS.json)
REPORT_SCHEMAS = {
    'daily_sales_revenue': {
        'header_row': 9,
        'key_columns': ['Date', 'Bill No', 'Net Sales', 'Gross Sales', 'Payment Type'],
        'numeric_columns': [
            'Discount Amount', 'Vat Adjustment', 'Tax Amount', 'VAT',
            'Service Charge Amount', 'Net Sales', 'Gross Sales', 'Gc Excess'
        ]
    },
    'sales_summary': {
        'header_row': 9,
        'key_columns': ['Date', 'Net Sales', 'Gross Sales'],
        'numeric_columns': [
            'Beginning Balance', 'Ending Balance', 'Net Sales', 'Gross Sales',
            'VATABLE Sales', 'VAT', 'VAT Exempt Sales', 'Zero Rated Sales',
            'Delivery Fee', 'Other Income', 'Gc Excess', 'Discount Pwd',
            'Discount Senior', 'Discount Other', 'Vat Adjustment',
            'Sales Overrun Amount', 'Returns', 'Void'
        ]
    },
    'transaction_report': {
        'header_row': 0,
        'key_columns': ['Bill #', 'Receipt #', 'Total', 'Gross Sales', 'Payment Type', 'Date'],
        'numeric_columns': ['Guest Count', 'Tax', 'Sub-total', 'Total', 'Gross Sales']
    },
    'productmix': {
        'header_row': 11,
        'key_columns': ['SKU/Item Code', 'Item Name', 'Item Qty', 'Net Sales', 'Gross Sales'],
        'numeric_columns': [
            'Per Price (item price w/o VAT)', 'Total Forced Modifier Price with VAT',
            'Item Qty', 'Discount Qty', 'Complimentary/Non-Revenue Qty',
            'Gross Sales', 'Discount Amount', 'VAT Adjustment', 'VAT',
            'Service Charge', 'Net Sales'
        ],
        'skip_patterns': ['Grand Totals:']
    },
    'discount_report': {
        'header_row': 9,
        'key_columns': ['Bill No', 'Discount Name', 'Discount Amount', 'Final Amount'],
        'numeric_columns': [
            'Discount Amount', 'Vat Adjustment', 'VAT',
            'Service Charge Amount', 'Sub Total', 'Other Charges', 'Final Amount'
        ]
    }
}


class POSExtractor:
    """
    Extract data from POS export files.

    Automatically detects report type from filename and applies
    appropriate schema for extraction.
    """

    def __init__(self, store_code: str = None):
        self.store_code = store_code

    def detect_report_type(self, filename: str) -> Optional[str]:
        """
        Detect report type from filename.

        Args:
            filename: Name of the file (e.g., 'Daily Sales Revenue_2026-01-15.xlsx')

        Returns:
            Report type key or None if not recognized
        """
        filename_lower = filename.lower()

        for report_type, patterns in REPORT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower):
                    return report_type

        logger.warning(f"Unknown report type for file: {filename}")
        return None

    def extract_file(self, file_path: Path) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        """
        Extract data from a POS file.

        Args:
            file_path: Path to the Excel file

        Returns:
            Tuple of (report_type, list of row dicts, metadata dict)

        Raises:
            ValueError: If report type cannot be detected
            Exception: If extraction fails
        """
        filename = file_path.name
        report_type = self.detect_report_type(filename)

        if not report_type:
            raise ValueError(f"Cannot detect report type for: {filename}")

        schema = REPORT_SCHEMAS.get(report_type)
        if not schema:
            raise ValueError(f"No schema for report type: {report_type}")

        logger.info(f"Extracting {report_type} from {filename}")

        # Read Excel file
        try:
            df = pd.read_excel(
                file_path,
                header=schema['header_row'],
                engine='openpyxl'
            )
        except Exception as e:
            logger.error(f"Failed to read Excel file {filename}: {e}")
            raise

        # Clean column names
        df.columns = df.columns.str.strip()

        # Skip summary rows if defined
        if 'skip_patterns' in schema:
            for pattern in schema['skip_patterns']:
                # Check first column for pattern
                first_col = df.columns[0]
                df = df[~df[first_col].astype(str).str.contains(pattern, na=False)]

        # Convert numeric columns
        for col in schema['numeric_columns']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Add metadata columns
        df['_store_code'] = self.store_code
        df['_report_type'] = report_type
        df['_source_file'] = filename
        df['_extracted_at'] = datetime.utcnow().isoformat()

        # Convert to list of dicts
        records = df.to_dict('records')

        # Extract metadata (for reports with metadata rows)
        metadata = self._extract_metadata(file_path, schema)
        metadata['report_type'] = report_type
        metadata['record_count'] = len(records)
        metadata['source_file'] = filename

        logger.info(f"Extracted {len(records)} rows from {filename}")

        return report_type, records, metadata

    def _extract_metadata(self, file_path: Path, schema: dict) -> Dict[str, Any]:
        """Extract metadata from header rows of POS file."""
        metadata = {}

        # Only extract metadata for reports with header_row > 0
        if schema['header_row'] == 0:
            return metadata

        try:
            # Read first N rows as metadata
            df_meta = pd.read_excel(
                file_path,
                header=None,
                nrows=schema['header_row'],
                engine='openpyxl'
            )

            # Common metadata patterns
            for idx, row in df_meta.iterrows():
                row_str = ' '.join(str(v) for v in row.values if pd.notna(v))

                if 'Location:' in row_str or 'Store:' in row_str:
                    # Extract store name after label
                    match = re.search(r'(?:Location|Store):\s*(.+)', row_str)
                    if match:
                        metadata['store_name'] = match.group(1).strip()

                elif 'TIN:' in row_str:
                    match = re.search(r'TIN:\s*(\S+)', row_str)
                    if match:
                        metadata['tin'] = match.group(1).strip()

                elif 'From Date:' in row_str:
                    match = re.search(r'From Date:\s*(\S+)', row_str)
                    if match:
                        metadata['from_date'] = match.group(1).strip()

                elif 'To Date:' in row_str:
                    match = re.search(r'To Date:\s*(\S+)', row_str)
                    if match:
                        metadata['to_date'] = match.group(1).strip()

        except Exception as e:
            logger.warning(f"Failed to extract metadata: {e}")

        return metadata

    def extract_summary(self, records: List[Dict[str, Any]], report_type: str) -> Dict[str, Any]:
        """
        Generate summary statistics from extracted records.

        Args:
            records: List of extracted row dicts
            report_type: Type of report

        Returns:
            Summary dict with totals and counts
        """
        if not records:
            return {'record_count': 0}

        df = pd.DataFrame(records)
        schema = REPORT_SCHEMAS.get(report_type, {})
        summary = {'record_count': len(records)}

        # Sum numeric columns
        for col in schema.get('numeric_columns', []):
            if col in df.columns:
                total = df[col].sum()
                summary[f'total_{col.lower().replace(" ", "_")}'] = float(total)

        # Count unique values in key columns
        for col in schema.get('key_columns', []):
            if col in df.columns:
                summary[f'unique_{col.lower().replace(" ", "_")}'] = df[col].nunique()

        return summary


def process_pos_file(
    file_path: Path,
    store_code: str = None
) -> Dict[str, Any]:
    """
    Process a single POS file and return extraction results.

    Args:
        file_path: Path to downloaded file
        store_code: Store identifier

    Returns:
        Dict with report_type, records, metadata, summary
    """
    extractor = POSExtractor(store_code=store_code)

    report_type, records, metadata = extractor.extract_file(file_path)
    summary = extractor.extract_summary(records, report_type)

    return {
        'report_type': report_type,
        'record_count': len(records),
        'records': records,
        'metadata': metadata,
        'summary': summary,
        'store_code': store_code
    }


# Singleton extractor
_extractor: Optional[POSExtractor] = None


def get_extractor(store_code: str = None) -> POSExtractor:
    """Get POSExtractor instance."""
    global _extractor
    if _extractor is None or _extractor.store_code != store_code:
        _extractor = POSExtractor(store_code=store_code)
    return _extractor
