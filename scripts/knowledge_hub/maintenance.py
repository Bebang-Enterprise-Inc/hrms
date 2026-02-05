"""Maintenance functions for Knowledge Hub - cleanup, forgetting, optimization."""

from datetime import datetime, timedelta
from typing import Dict, Any, List

from .storage import get_supabase_client


def cleanup_unused_chunks(
    min_age_days: int = 90,
    min_access_count: int = 0,
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Remove chunks that haven't been accessed and are past their TTL.
    Implements "selective forgetting" from ARM research.

    Args:
        min_age_days: Minimum age in days for a chunk to be eligible for cleanup
        min_access_count: Maximum access count for a chunk to be considered unused
        dry_run: If True, only report what would be deleted without actually deleting

    Returns:
        Dict with candidates_found, dry_run flag, and deleted count
    """
    supabase = get_supabase_client()
    cutoff_date = datetime.now() - timedelta(days=min_age_days)

    candidates = supabase.table("kb_chunks")\
        .select("id, document_id, access_count, created_at")\
        .lt("created_at", cutoff_date.isoformat())\
        .lte("access_count", min_access_count)\
        .execute()

    result = {
        "candidates_found": len(candidates.data),
        "dry_run": dry_run,
        "deleted": 0
    }

    if not dry_run and candidates.data:
        chunk_ids = [c["id"] for c in candidates.data]
        supabase.table("kb_chunks").delete().in_("id", chunk_ids).execute()
        result["deleted"] = len(chunk_ids)

    return result


def cleanup_low_quality_chunks(
    quality_threshold: float = 0.3,
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Remove chunks below quality threshold.

    Args:
        quality_threshold: Minimum quality score to keep (default 0.3)
        dry_run: If True, only report what would be deleted without actually deleting

    Returns:
        Dict with candidates_found, dry_run flag, and deleted count
    """
    supabase = get_supabase_client()

    candidates = supabase.table("kb_chunks")\
        .select("id, quality_score")\
        .lt("quality_score", quality_threshold)\
        .execute()

    result = {
        "candidates_found": len(candidates.data),
        "dry_run": dry_run,
        "deleted": 0
    }

    if not dry_run and candidates.data:
        chunk_ids = [c["id"] for c in candidates.data]
        supabase.table("kb_chunks").delete().in_("id", chunk_ids).execute()
        result["deleted"] = len(chunk_ids)

    return result


def get_forgetting_stats() -> Dict[str, Any]:
    """
    Get statistics about chunk access patterns.

    Returns:
        Dict with total_chunks, never_accessed, low_quality counts and percentages
    """
    supabase = get_supabase_client()

    total = supabase.table("kb_chunks").select("id", count="exact").execute()
    never_accessed = supabase.table("kb_chunks").select("id", count="exact").eq("access_count", 0).execute()
    low_quality = supabase.table("kb_chunks").select("id", count="exact").lt("quality_score", 0.5).execute()

    total_count = total.count or 0
    never_accessed_count = never_accessed.count or 0
    low_quality_count = low_quality.count or 0

    return {
        "total_chunks": total_count,
        "never_accessed": never_accessed_count,
        "low_quality": low_quality_count,
        "never_accessed_pct": (never_accessed_count / total_count * 100) if total_count > 0 else 0,
        "low_quality_pct": (low_quality_count / total_count * 100) if total_count > 0 else 0
    }
