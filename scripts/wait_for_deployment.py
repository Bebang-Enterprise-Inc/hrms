"""
Reusable deployment polling utility for autonomous agents.

Usage:
    from scripts.wait_for_deployment import wait_for_frappe_migration, wait_for_vercel_deployment

    if wait_for_frappe_migration(max_wait_seconds=300):
        print("Migration complete, continue testing")
    else:
        print("Timeout - continue anyway and document failure")
"""

import time
import requests
import sys

def check_frappe_doctype_field_exists(doctype: str, field: str, api_key: str, api_secret: str) -> bool:
    """Check if a field exists in a Frappe DocType (indicates migration complete)"""
    try:
        response = requests.get(
            f"https://hq.bebang.ph/api/resource/DocType/{doctype}",
            headers={"Authorization": f"token {api_key}:{api_secret}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            field_order = data.get('data', {}).get('field_order', [])
            return field in field_order
        return False
    except Exception as e:
        print(f"Error checking DocType: {e}")
        return False

def check_vercel_page_live(url: str) -> bool:
    """Check if a Vercel page is live (not 404)"""
    try:
        response = requests.get(url, timeout=10)
        return response.status_code == 200 and "404" not in response.text
    except Exception as e:
        print(f"Error checking Vercel page: {e}")
        return False

def wait_for_frappe_migration(
    doctype: str,
    field: str,
    api_key: str,
    api_secret: str,
    max_wait_seconds: int = 300,
    poll_interval: int = 30
) -> bool:
    """
    Poll Frappe until migration is complete.

    Returns:
        True if migration completed successfully
        False if timeout occurred
    """
    start_time = time.time()
    attempt = 0

    print(f"Waiting for Frappe migration ({doctype}.{field})...")
    print(f"Max wait: {max_wait_seconds}s, polling every {poll_interval}s")

    while (time.time() - start_time) < max_wait_seconds:
        attempt += 1
        elapsed = int(time.time() - start_time)

        print(f"[Attempt {attempt}, {elapsed}s] Checking migration status...")

        if check_frappe_doctype_field_exists(doctype, field, api_key, api_secret):
            print(f"[SUCCESS] Migration complete! Field '{field}' found in {doctype}")
            return True

        remaining = max_wait_seconds - elapsed
        if remaining > 0:
            wait_time = min(poll_interval, remaining)
            print(f"[WAITING] Field not found yet. Waiting {wait_time}s...")
            time.sleep(wait_time)
        else:
            break

    print(f"[TIMEOUT] Migration did not complete within {max_wait_seconds}s")
    return False

def wait_for_vercel_deployment(
    url: str,
    max_wait_seconds: int = 120,
    poll_interval: int = 15
) -> bool:
    """
    Poll Vercel until deployment is live.

    Returns:
        True if deployment went live
        False if timeout occurred
    """
    start_time = time.time()
    attempt = 0

    print(f"Waiting for Vercel deployment ({url})...")
    print(f"Max wait: {max_wait_seconds}s, polling every {poll_interval}s")

    while (time.time() - start_time) < max_wait_seconds:
        attempt += 1
        elapsed = int(time.time() - start_time)

        print(f"[Attempt {attempt}, {elapsed}s] Checking deployment status...")

        if check_vercel_page_live(url):
            print(f"[SUCCESS] Deployment live! Page accessible at {url}")
            return True

        remaining = max_wait_seconds - elapsed
        if remaining > 0:
            wait_time = min(poll_interval, remaining)
            print(f"[WAITING] Page not live yet (404). Waiting {wait_time}s...")
            time.sleep(wait_time)
        else:
            break

    print(f"[TIMEOUT] Deployment did not go live within {max_wait_seconds}s")
    return False

if __name__ == "__main__":
    # Example usage
    if len(sys.argv) < 2:
        print("Usage: python wait_for_deployment.py <frappe|vercel>")
        sys.exit(1)

    deployment_type = sys.argv[1]

    if deployment_type == "frappe":
        # Example: Wait for BEI Payment Request rfp_type field
        success = wait_for_frappe_migration(
            doctype="BEI Payment Request",
            field="rfp_type",
            api_key="4a17c23aca83560",
            api_secret="38ecc0e1054b1d2",
            max_wait_seconds=300
        )
        sys.exit(0 if success else 1)

    elif deployment_type == "vercel":
        # Example: Wait for accounting dashboard
        success = wait_for_vercel_deployment(
            url="https://my.bebang.ph/dashboard/accounting",
            max_wait_seconds=120
        )
        sys.exit(0 if success else 1)

    else:
        print(f"Unknown deployment type: {deployment_type}")
        sys.exit(1)
