"""Execute SQL against Supabase BEI Data Lake via Management API."""
import httpx
import os
import sys
import json

TOKEN = os.environ['SUPABASE_MGMT_TOKEN']
PROJECT_REF = "csnniykjrychgajfrgua"
BASE_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"


def execute_sql(sql: str) -> dict:
    r = httpx.post(
        BASE_URL,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=60,
    )
    if r.status_code != 201:
        print(f"ERROR {r.status_code}: {r.text[:500]}", file=sys.stderr)
        sys.exit(1)
    return r.json()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sql = " ".join(sys.argv[1:])
    else:
        sql = sys.stdin.read()

    result = execute_sql(sql)
    print(json.dumps(result, indent=2, default=str))
