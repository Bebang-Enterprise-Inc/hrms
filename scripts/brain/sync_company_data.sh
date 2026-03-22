#!/bin/bash
# BEI Brain: Weekly company data re-ingestion
# Scheduled: Sunday 3am PHT via crontab
# crontab -e entry: 0 3 * * 0 /path/to/sync_company_data.sh >> /var/log/bei-brain-sync.log 2>&1
#
# The ingestion script uses row_hash for change detection:
# - Unchanged rows: skipped (no API calls)
# - Modified rows: re-embedded and updated
# - New rows: embedded and inserted

cd "$(dirname "$0")/../.." || exit 1
python scripts/brain/ingest_company_data.py
