import json
import os
import re

def audit_deps():
    print("--- Auditing Frontend Dependencies ---")
    
    try:
        with open('frontend/package.json', 'r') as f:
            pkg = json.load(f)
            deps = set(pkg.get('dependencies', {}).keys())
            dev_deps = set(pkg.get('devDependencies', {}).keys())
            all_deps = deps | dev_deps
            print(f"Loaded {len(all_deps)} dependencies from package.json")
    except FileNotFoundError:
        print("Error: frontend/package.json not found")
        return

    used_imports = set()
    # Regex: match import/from followed by quote, then capture package name
    # Ignore relative imports starting with . or @
    import_regex = re.compile(r"""(?:import|from)\s+['"]([^@\.][\w\-/]+)['"]""")
    
    for root, _, files in os.walk('frontend/src'):
        for file in files:
            if file.endswith('.vue') or file.endswith('.js') or file.endswith('.ts'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        matches = import_regex.findall(content)
                        for m in matches:
                            if m.startswith('@'):
                                parts = m.split('/')
                                if len(parts) >= 2:
                                    pkg_name = f"{parts[0]}/{parts[1]}"
                                    used_imports.add(pkg_name)
                            else:
                                pkg_name = m.split('/')[0]
                                used_imports.add(pkg_name)
                except Exception:
                    pass

    missing = used_imports - all_deps
    # Filter built-ins or special cases
    ignored = {'frappe-ui', 'vue', 'vue-router', 'pinia'} # frappe-ui often provides these
    missing = {m for m in missing if m not in ignored}
    
    if missing:
        print("POSSIBLE MISSING DEPENDENCIES:")
        for m in sorted(missing):
            print(f"  - {m}")
    else:
        print("[OK] All imports seem to be covered by package.json")

if __name__ == '__main__':
    audit_deps()
