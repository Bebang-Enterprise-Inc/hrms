#!/bin/bash

set -e

cd ~ || exit

sudo apt update
sudo apt remove mysql-server mysql-client
sudo apt install libcups2-dev redis-server mariadb-client libmariadb-dev

pip install frappe-bench

githubbranch=${GITHUB_BASE_REF:-${GITHUB_REF##*/}}
frappeuser=${FRAPPE_USER:-"frappe"}
defaultstablebranch=${DEFAULT_STABLE_BRANCH:-"version-15"}
frappebranchcandidate=${FRAPPE_BRANCH:-$githubbranch}
erpnextbranchcandidate=${ERPNEXT_BRANCH:-$githubbranch}
paymentsbranchcandidate=${PAYMENTS_BRANCH:-${githubbranch%"-hotfix"}}
lendingbranchcandidate=${LENDING_BRANCH:-$githubbranch}

resolve_branch() {
	repo="$1"
	branch="$2"
	if git ls-remote --exit-code --heads "https://github.com/${frappeuser}/${repo}" "${branch}" > /dev/null 2>&1; then
		echo "$branch"
	else
		echo "WARNING: Branch '${branch}' not found in ${frappeuser}/${repo}. Falling back to '${defaultstablebranch}'." >&2
		echo "$defaultstablebranch"
	fi
}

frappebranch=$(resolve_branch "frappe" "$frappebranchcandidate")
erpnextbranch=$(resolve_branch "erpnext" "$erpnextbranchcandidate")
paymentsbranch=$(resolve_branch "payments" "$paymentsbranchcandidate")
lendingbranch=$(resolve_branch "lending" "$lendingbranchcandidate")

git clone "https://github.com/${frappeuser}/frappe" --branch "${frappebranch}" --depth 1
bench init --skip-assets --frappe-path ~/frappe --python "$(which python)" frappe-bench

# Compatibility shim for older Frappe branches where these symbols are not exported
# from frappe.tests directly (HRMS tests import them from frappe.tests).
python - <<'PY'
from pathlib import Path

tests_init = Path.home() / "frappe-bench" / "apps" / "frappe" / "frappe" / "tests" / "__init__.py"
if not tests_init.exists():
    raise SystemExit(0)

content = tests_init.read_text(encoding="utf-8")
marker = "# hrms ci compatibility exports"
if marker not in content:
    shim = """

# hrms ci compatibility exports
try:
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase
except Exception:
    pass
try:
    from frappe.tests.utils import FrappeTestCase as UnitTestCase
except Exception:
    pass
try:
    from frappe.tests.utils import change_settings
except Exception:
    pass
"""
    tests_init.write_text(content + shim, encoding="utf-8")
PY

mkdir ~/frappe-bench/sites/test_site
cp -r "${GITHUB_WORKSPACE}/.github/helper/site_config.json" ~/frappe-bench/sites/test_site/

mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "SET GLOBAL character_set_server = 'utf8mb4'"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "SET GLOBAL collation_server = 'utf8mb4_unicode_ci'"

mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "CREATE USER 'test_frappe'@'localhost' IDENTIFIED BY 'test_frappe'"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "CREATE DATABASE test_frappe"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "GRANT ALL PRIVILEGES ON \`test_frappe\`.* TO 'test_frappe'@'localhost'"

mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "FLUSH PRIVILEGES"

install_whktml() {
    wget -O /tmp/wkhtmltox.tar.xz https://github.com/frappe/wkhtmltopdf/raw/master/wkhtmltox-0.12.3_linux-generic-amd64.tar.xz
    tar -xf /tmp/wkhtmltox.tar.xz -C /tmp
    sudo mv /tmp/wkhtmltox/bin/wkhtmltopdf /usr/local/bin/wkhtmltopdf
    sudo chmod o+x /usr/local/bin/wkhtmltopdf
}
install_whktml &

cd ~/frappe-bench || exit

sed -i 's/watch:/# watch:/g' Procfile
sed -i 's/schedule:/# schedule:/g' Procfile
sed -i 's/socketio:/# socketio:/g' Procfile
sed -i 's/redis_socketio:/# redis_socketio:/g' Procfile

bench get-app "https://github.com/${frappeuser}/payments" --branch "$paymentsbranch"
bench get-app "https://github.com/${frappeuser}/erpnext" --branch "$erpnextbranch" --resolve-deps
bench get-app "https://github.com/${frappeuser}/lending" --branch "$lendingbranch"
bench get-app hrms "${GITHUB_WORKSPACE}"
bench setup requirements --dev

bench start &>> ~/frappe-bench/bench_start.log &
CI=Yes bench build --app frappe &
bench --site test_site reinstall --yes

bench --verbose --site test_site install-app lending
# On some upstream branch combinations, ERPNext seeds "Employee Self Service" as standard.
# HRMS user-type setup expects a custom role, so align this before hrms install in CI.
bench --site test_site execute "frappe.db.sql" --kwargs "{'query': \"UPDATE \`tabRole\` SET is_custom = 1 WHERE name = 'Employee Self Service'\"}" || true
bench --site test_site execute "frappe.db.commit" || true
# Newer Frappe builds enforce permission dependency rules more strictly.
# Normalize legacy permission rows to avoid amend-without-create validation errors in CI.
bench --site test_site execute "frappe.db.sql" --kwargs "{'query': \"UPDATE \`tabDocPerm\` SET \`create\` = 1 WHERE \`amend\` = 1 AND \`create\` = 0\"}" || true
bench --site test_site execute "frappe.db.sql" --kwargs "{'query': \"UPDATE \`tabCustom DocPerm\` SET \`create\` = 1 WHERE \`amend\` = 1 AND \`create\` = 0\"}" || true
bench --site test_site execute "frappe.db.commit" || true
bench --verbose --site test_site install-app hrms
