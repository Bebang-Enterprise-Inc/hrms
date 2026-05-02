"""S232 Phase 1 verifier — uses shared template (Phase 0.8 deliverable).

Resolves audit C1 — filesystem-based, not prose self-assessment.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.s232_verify_phase_template import verify_phase

verify_phase(
    phase_num=1,
    required_files=[
        "scripts/sync_pos_to_supabase.py",
        "hrms/api/mosaic_webhook.py",
        "hrms/utils/pos_dedup.py",
        "scripts/s232_supabase_migrations/001_bill_number_unique_index.sql",
        "scripts/s232_supabase_migrations/002_pos_duplicates_table.sql",
        "scripts/s232_supabase_migrations/003_pos_orders_dedup_fields.sql",
        "scripts/s232_supabase_migrations/004_short_order_id.sql",
    ],
    required_strings=[
        # Helper module
        ("hrms/utils/pos_dedup.py", "def find_bill_number_twin"),
        ("hrms/utils/pos_dedup.py", "def find_cluster_twin"),
        ("hrms/utils/pos_dedup.py", "sha256"),
        # Poll path (PRIMARY)
        ("scripts/sync_pos_to_supabase.py", "find_bill_number_twin_batch"),
        ("scripts/sync_pos_to_supabase.py", "pos_duplicates"),
        ("scripts/sync_pos_to_supabase.py", "race_409"),
        ("scripts/sync_pos_to_supabase.py", "_handle_pos_orders_409"),
        ("scripts/sync_pos_to_supabase.py", "short_order_id"),
        ("scripts/sync_pos_to_supabase.py", "webhook_received_at"),
        # Webhook path (FUTURE-PROOFING)
        ("hrms/api/mosaic_webhook.py", "_find_bill_number_twin"),
        ("hrms/api/mosaic_webhook.py", "_write_pos_duplicate_webhook"),
        ("hrms/api/mosaic_webhook.py", "pos_duplicates"),
        ("hrms/api/mosaic_webhook.py", "race_409"),
        ('hrms/api/mosaic_webhook.py', 'module="pos_ingest"'),
        ("hrms/api/mosaic_webhook.py", "short_order_id"),
        # Migration files
        ("scripts/s232_supabase_migrations/001_bill_number_unique_index.sql",
         "pos_orders_bill_number_natural_key"),
        ("scripts/s232_supabase_migrations/001_bill_number_unique_index.sql",
         "WHERE bill_number IS NOT NULL AND is_duplicate = false"),
        ("scripts/s232_supabase_migrations/002_pos_duplicates_table.sql",
         "pos_duplicates"),
        ("scripts/s232_supabase_migrations/002_pos_duplicates_table.sql",
         "kept_order_id"),
        ("scripts/s232_supabase_migrations/003_pos_orders_dedup_fields.sql",
         "is_duplicate BOOLEAN DEFAULT false"),
        ("scripts/s232_supabase_migrations/003_pos_orders_dedup_fields.sql",
         "webhook_received_at"),
        ("scripts/s232_supabase_migrations/004_short_order_id.sql",
         "short_order_id"),
    ],
)
