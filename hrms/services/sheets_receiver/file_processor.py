"""
File Processor for POS File Extraction.

Downloads files from Google Drive, extracts data using POSExtractor,
and updates the processing queue.

This module is used by the background worker to process queued files.

Performance: Uses parallel processing with ThreadPoolExecutor to overcome
Google Drive API latency (~1.3s per file download).
"""

import logging
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .folder_watcher import get_folder_watcher
from .pos_extractor import process_pos_file
from .models import get_db
from . import notifications

logger = logging.getLogger(__name__)


class FileProcessor:
    """
    Processes POS files from Google Drive.

    Downloads file -> Extracts data -> Updates database

    Uses parallel processing to overcome Google Drive API latency.
    Default: 10 concurrent workers (configurable via PARALLEL_WORKERS env var)
    """

    def __init__(self, max_workers: int = None):
        self.watcher = get_folder_watcher()
        self.db = get_db()
        self.temp_dir = Path(tempfile.gettempdir()) / "pos_processing"
        self.temp_dir.mkdir(exist_ok=True)
        # Default 10 workers - thread-local Drive services allow safe parallel processing
        # Can adjust via PARALLEL_WORKERS env var if needed
        self.max_workers = max_workers or int(os.environ.get('PARALLEL_WORKERS', '10'))

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

            # Real-time notifications disabled - only daily summary is sent
            # See notifications.send_daily_summary() scheduled at 23:00 UTC (7 AM PHT)

            return {
                'status': 'failed',
                'file_id': file_id,
                'file_name': file_name,
                'store_code': store_code,
                'error': error_msg
            }

    def process_pending_files(self, limit: int = 10, parallel: bool = True) -> Dict[str, Any]:
        """
        Process multiple pending files from the queue.

        Args:
            limit: Maximum files to process in this batch
            parallel: Use parallel processing (default True for performance)

        Returns:
            Summary of processing results

        Performance:
            Sequential: ~1.3s/file (Google Drive latency)
            Parallel (10 workers): ~0.13s/file effective throughput
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
            'files': [],
            'parallel': parallel,
            'workers': self.max_workers if parallel else 1
        }

        # Parallel processing enabled - folder_watcher.py now uses thread-local Drive services
        if parallel and len(pending) > 1:
            # Parallel processing with ThreadPoolExecutor
            workers = min(self.max_workers, len(pending))
            logger.info(f"Processing {len(pending)} files with {workers} parallel workers")

            with ThreadPoolExecutor(max_workers=workers) as executor:
                # Submit all tasks
                future_to_entry = {
                    executor.submit(self.process_queued_file, entry): entry
                    for entry in pending
                }

                # Collect results as they complete
                for future in as_completed(future_to_entry):
                    try:
                        result = future.result()
                        results['files'].append(result)

                        if result['status'] == 'completed':
                            results['processed'] += 1
                            results['total_records'] += result.get('record_count', 0)
                        else:
                            results['failed'] += 1
                    except Exception as e:
                        entry = future_to_entry[future]
                        logger.error(f"Parallel processing error for {entry['file_name']}: {e}")
                        results['failed'] += 1
                        results['files'].append({
                            'status': 'failed',
                            'file_id': entry['file_id'],
                            'file_name': entry['file_name'],
                            'error': str(e)
                        })
        else:
            # Sequential processing (fallback or single file)
            for entry in pending:
                result = self.process_queued_file(entry)
                results['files'].append(result)

                if result['status'] == 'completed':
                    results['processed'] += 1
                    results['total_records'] += result.get('record_count', 0)
                else:
                    results['failed'] += 1

        return results


    def process_all_pending(self, batch_size: int = 25) -> Dict[str, Any]:
        """
        Process ALL pending files in batches with parallel processing.

        For initial backlog processing of large queues.

        Args:
            batch_size: Files per batch (default 25 - conservative for Google Drive API limits)

        Returns:
            Summary of all processing
        """
        import time

        total_results = {
            'status': 'completed',
            'processed': 0,
            'failed': 0,
            'total_records': 0,
            'batches': 0
        }

        while True:
            # Get next batch
            batch_result = self.process_pending_files(limit=batch_size, parallel=True)

            if batch_result.get('status') == 'no_pending_files':
                break

            total_results['batches'] += 1
            total_results['processed'] += batch_result['processed']
            total_results['failed'] += batch_result['failed']
            total_results['total_records'] += batch_result['total_records']

            logger.info(
                f"Batch {total_results['batches']}: "
                f"{batch_result['processed']} processed, "
                f"{batch_result['failed']} failed, "
                f"Total so far: {total_results['processed']}"
            )

            # Small delay between batches to let Google API connections settle
            time.sleep(1)

        return total_results


# Background worker function (for asyncio)
async def file_processing_worker(check_interval: int = 30, batch_size: int = 50):
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
