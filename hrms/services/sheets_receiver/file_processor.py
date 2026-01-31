"""
File Processor for POS File Extraction.

Downloads files from Google Drive, extracts data using POSExtractor,
and updates the processing queue.

This module is used by the background worker to process queued files.
"""

import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .folder_watcher import get_folder_watcher
from .pos_extractor import process_pos_file
from .models import get_db

logger = logging.getLogger(__name__)


class FileProcessor:
    """
    Processes POS files from Google Drive.

    Downloads file -> Extracts data -> Updates database
    """

    def __init__(self):
        self.watcher = get_folder_watcher()
        self.db = get_db()
        self.temp_dir = Path(tempfile.gettempdir()) / "pos_processing"
        self.temp_dir.mkdir(exist_ok=True)

    def process_queued_file(self, queue_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single file from the queue.

        Args:
            queue_entry: Dict with file_id, file_name, store_code, etc.

        Returns:
            Result dict with status, record_count, etc.
        """
        file_id = queue_entry['file_id']
        file_name = queue_entry['file_name']
        store_code = queue_entry.get('store_code', 'unknown')
        folder_id = queue_entry.get('folder_id', '')

        logger.info(f"Processing file: {file_name} (store: {store_code})")

        # Update status to processing
        self.db.update_file_status(file_id, 'processing')

        try:
            # Step 1: Download file
            local_path = self.temp_dir / f"{file_id}_{file_name}"
            self.watcher.download_file(file_id, local_path)

            # Step 2: Extract data
            result = process_pos_file(local_path, store_code=store_code)

            # Step 3: Update database
            self.db.update_file_status(
                file_id,
                'completed',
                record_count=result['record_count'],
                report_type=result['report_type']
            )

            # Also mark in processed_files for deduplication
            self.db.mark_file_processed(
                file_id=file_id,
                file_name=file_name,
                folder_id=folder_id,
                store_code=store_code,
                md5_checksum=queue_entry.get('md5_checksum', ''),
                record_count=result['record_count'],
                report_type=result['report_type'],
                extracted_data={
                    'summary': result['summary'],
                    'metadata': result['metadata'],
                    'processed_at': datetime.utcnow().isoformat()
                }
            )

            # Cleanup temp file
            try:
                local_path.unlink()
            except Exception:
                pass

            logger.info(f"Successfully processed {file_name}: {result['record_count']} records")

            return {
                'status': 'completed',
                'file_id': file_id,
                'file_name': file_name,
                'store_code': store_code,
                'report_type': result['report_type'],
                'record_count': result['record_count'],
                'summary': result['summary']
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to process {file_name}: {error_msg}")

            self.db.update_file_status(
                file_id,
                'failed',
                error=error_msg
            )

            return {
                'status': 'failed',
                'file_id': file_id,
                'file_name': file_name,
                'error': error_msg
            }

    def process_pending_files(self, limit: int = 10) -> Dict[str, Any]:
        """
        Process multiple pending files from the queue.

        Args:
            limit: Maximum files to process in this batch

        Returns:
            Summary of processing results
        """
        pending = self.db.get_pending_files(limit=limit)

        if not pending:
            return {
                'status': 'no_pending_files',
                'processed': 0,
                'failed': 0
            }

        results = {
            'status': 'completed',
            'processed': 0,
            'failed': 0,
            'total_records': 0,
            'files': []
        }

        for entry in pending:
            result = self.process_queued_file(entry)
            results['files'].append(result)

            if result['status'] == 'completed':
                results['processed'] += 1
                results['total_records'] += result.get('record_count', 0)
            else:
                results['failed'] += 1

        return results


# Background worker function (for asyncio)
async def file_processing_worker(check_interval: int = 30, batch_size: int = 10):
    """
    Background worker that continuously processes queued files.

    Args:
        check_interval: Seconds between queue checks
        batch_size: Files to process per batch
    """
    import asyncio

    processor = FileProcessor()
    logger.info("File processing worker started")

    while True:
        try:
            # Process pending files
            result = processor.process_pending_files(limit=batch_size)

            if result['processed'] > 0 or result['failed'] > 0:
                logger.info(
                    f"Batch complete: {result['processed']} processed, "
                    f"{result['failed']} failed, {result['total_records']} records"
                )

        except Exception as e:
            logger.error(f"Worker error: {e}")

        # Wait before next check
        await asyncio.sleep(check_interval)


# Singleton processor
_processor: Optional[FileProcessor] = None


def get_file_processor() -> FileProcessor:
    """Get FileProcessor instance."""
    global _processor
    if _processor is None:
        _processor = FileProcessor()
    return _processor
