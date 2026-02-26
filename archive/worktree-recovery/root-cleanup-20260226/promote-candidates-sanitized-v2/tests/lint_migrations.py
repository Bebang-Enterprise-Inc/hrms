import os
import re
import glob

def lint_migrations(migrations_dir):
    print("--- Linting Migrations ---")
    
    files = glob.glob(os.path.join(migrations_dir, "*.sql"))
    
    findings = []
    
    # Patterns
    p_grant_anon = re.compile(r'GRANT\s+.*?\s+TO\s+.*?\banon\b', re.IGNORECASE)
    p_create_view = re.compile(r'CREATE\s+(OR\s+REPLACE\s+)?(MATERIALIZED\s+)?VIEW', re.IGNORECASE)
    p_security_invoker = re.compile(r'security_invoker\s*=\s*true', re.IGNORECASE)
    
    for file_path in files:
        filename = os.path.basename(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check 1: GRANT to anon
        for match in p_grant_anon.finditer(content):
            findings.append({
                "file": filename,
                "type": "CRITICAL",
                "message": "Grant to 'anon' role found: " + match.group(0),
                "line": content[:match.start()].count('\n') + 1
            })
            
        # Check 2: Views without security_invoker
        if p_create_view.search(content) and not p_security_invoker.search(content):
             findings.append({
                "file": filename,
                "type": "WARNING",
                "message": "View created without 'security_invoker=true'. Bypasses RLS on base tables.",
                "line": 0
            })

    # Report
    if not findings:
        print("[OK] No obvious security issues found.")
    else:
        print("Found issues:")
        for f in findings:
            print(f"[{f['type']}] {f['file']}:{f['line']} - {f['message']}")

if __name__ == '__main__':
    lint_migrations("supabase/migrations")
