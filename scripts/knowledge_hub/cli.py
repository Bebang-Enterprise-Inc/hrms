"""CLI for Knowledge Hub operations."""

import argparse
import json
import sys
from pathlib import Path


def cmd_ingest(args):
    """Ingest a local file."""
    from .ingest import ingest_local_file

    result = ingest_local_file(args.file, category=args.category)
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


def main():
    parser = argparse.ArgumentParser(description="Knowledge Hub CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a local file")
    ingest_parser.add_argument("file", help="Path to file")
    ingest_parser.add_argument("--category", help="Document category")
    ingest_parser.set_defaults(func=cmd_ingest)

    # Search command
    search_parser = subparsers.add_parser("search", help="Search knowledge base")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--top-k", type=int, default=5, help="Max results")
    search_parser.set_defaults(func=cmd_search)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
