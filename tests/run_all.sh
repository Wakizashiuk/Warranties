#!/usr/bin/env bash
# Run every check. Exits non-zero if anything fails.
#   One-off setup:  pip install playwright pillow && python3 -m playwright install chromium
set -u
cd "$(dirname "$0")/.."
status=0
run() { echo; echo "=== $1 ==="; shift; "$@" || status=1; }
run "Security policy hashes" python3 tools/update_csp.py --check
run "Real data guard"        python3 tools/check_no_data.py
run "Sync between phones"    python3 tests/e2e.py
run "Documents and viewer"   python3 tests/docs_test.py
run "Installed app / offline" python3 tests/pwa.py
echo
if [ $status -eq 0 ]; then echo "ALL CHECKS PASSED"; else echo "SOME CHECKS FAILED"; fi
exit $status
