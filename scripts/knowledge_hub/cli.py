"""CLI for Knowledge Hub operations."""

import argparse
import json
import sys
from pathlib import Path


def cmd_ingest(args):
    """Ingest a local file."""
    from .ingest import ingest_local_file

    result = ingest_local_file(
        args.file,
        category=args.category,
        generate_metadata=getattr(args, 'with_metadata', False)
    )
    print(json.dumps(result, indent=2))


def cmd_search(args):
    """Search the knowledge base."""
    from .search import search, search_with_context

    # Get detailed results for sources
    results = search(args.query, top_k=args.top_k)

    # Get formatted context string
    context = search_with_context(args.query, top_k=args.top_k)

    print("=" * 60)
    print("CONTEXT:")
    print("=" * 60)
    print(context if context else "(No results found)")
    print()
    print("=" * 60)
    print("SOURCES:")
    print("=" * 60)
    for i, result in enumerate(results, start=1):
        title = result.get("title", "Unknown")
        score = result.get("score", 0)
        source = result.get("source", "")
        print(f"  [{i}] {title} (score: {score:.2f})")
        print(f"      {source}")


def cmd_stats(args):
    """Show knowledge base statistics."""
    from .storage import get_supabase_client

    supabase = get_supabase_client()

    docs = supabase.table("kb_documents").select("id, status", count="exact").execute()
    chunks = supabase.table("kb_chunks").select("id", count="exact").execute()

    print(f"Documents: {docs.count}")
    print(f"Chunks: {chunks.count}")

    # Status breakdown
    by_status = supabase.table("kb_documents").select("status").execute()
    status_counts = {}
    for doc in by_status.data:
        s = doc["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    print("\nBy Status:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")


def cmd_search_recency(args):
    """Search with recency weighting."""
    from .search import search_with_recency

    results = search_with_recency(
        args.query,
        top_k=args.top_k,
        decay_rate=args.decay_rate,
        recency_weight=args.recency_weight
    )

    print("=" * 60)
    print(f"RESULTS (decay={args.decay_rate}, recency_weight={args.recency_weight}):")
    print("=" * 60)

    if not results:
        print("\n(No results found)")
        return

    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r['title']} (score: {r['score']:.2f})")
        print(f"    Semantic: {r['similarity']:.2f} | Recency: {r['recency']:.2f}")
        print(f"    Date: {r.get('date', 'Unknown')}")
        print(f"    {r['content'][:200]}...")


def cmd_maintenance(args):
    """Run maintenance/cleanup tasks."""
    from .maintenance import cleanup_unused_chunks, cleanup_low_quality_chunks, get_forgetting_stats

    if args.action == "stats":
        stats = get_forgetting_stats()
        print("Forgetting Statistics:")
        for k, v in stats.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.2f}")
            else:
                print(f"  {k}: {v}")

    elif args.action == "cleanup-unused":
        result = cleanup_unused_chunks(
            min_age_days=args.min_age,
            dry_run=args.dry_run
        )
        prefix = "[DRY RUN] " if result["dry_run"] else ""
        print(f"{prefix}Cleanup unused chunks:")
        print(f"  Candidates found: {result['candidates_found']}")
        print(f"  Deleted: {result['deleted']}")

    elif args.action == "cleanup-low-quality":
        result = cleanup_low_quality_chunks(
            quality_threshold=args.quality_threshold,
            dry_run=args.dry_run
        )
        prefix = "[DRY RUN] " if result["dry_run"] else ""
        print(f"{prefix}Cleanup low-quality chunks (threshold: {args.quality_threshold}):")
        print(f"  Candidates found: {result['candidates_found']}")
        print(f"  Deleted: {result['deleted']}")


def main():
    parser = argparse.ArgumentParser(description="Knowledge Hub CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a local file")
    ingest_parser.add_argument("file", help="Path to file")
    ingest_parser.add_argument("--category", help="Document category")
    ingest_parser.add_argument("--with-metadata", action="store_true",
                               help="Generate LLM metadata for chunks (summary, keywords, quality)")
    ingest_parser.set_defaults(func=cmd_ingest)

    # Search command
    search_parser = subparsers.add_parser("search", help="Search knowledge base")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--top-k", type=int, default=5, help="Max results")
    search_parser.set_defaults(func=cmd_search)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # Search with recency
    search_recency_parser = subparsers.add_parser("search-recency",
                                                   help="Search with recency weighting")
    search_recency_parser.add_argument("query", help="Search query")
    search_recency_parser.add_argument("--top-k", type=int, default=5,
                                       help="Max results (default: 5)")
    search_recency_parser.add_argument("--decay-rate", type=float, default=0.01,
                                       help="Higher = faster decay (default: 0.01)")
    search_recency_parser.add_argument("--recency-weight", type=float, default=0.3,
                                       help="0-1, how much recency matters (default: 0.3)")
    search_recency_parser.set_defaults(func=cmd_search_recency)

    # Maintenance
    maint_parser = subparsers.add_parser("maintenance", help="Run maintenance tasks")
    maint_parser.add_argument("action", choices=["stats", "cleanup-unused", "cleanup-low-quality"],
                              help="Maintenance action to perform")
    maint_parser.add_argument("--dry-run", action="store_true", default=True,
                              help="Only report what would be deleted (default: True)")
    maint_parser.add_argument("--no-dry-run", dest="dry_run", action="store_false",
                              help="Actually delete the chunks")
    maint_parser.add_argument("--min-age", type=int, default=90,
                              help="Days before considering for cleanup (default: 90)")
    maint_parser.add_argument("--quality-threshold", type=float, default=0.3,
                              help="Quality score threshold for cleanup (default: 0.3)")
    maint_parser.set_defaults(func=cmd_maintenance)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
