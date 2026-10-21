#!/usr/bin/env python3
"""Keep the Content-Security-Policy script hashes in index.html in step with its inline <script> blocks.

The CSP only lets inline scripts run if their sha256 hash is listed. Edit an inline script without
updating the hash and the app silently shows a blank page on phones.

    python3 tools/update_csp.py          # rewrite the hashes to match the current scripts
    python3 tools/update_csp.py --check  # exit 1 if they don't match (used by the tests)
"""
import base64, hashlib, os, re, sys

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'index.html')
html = open(PATH, encoding='utf-8').read()

meta = re.search(r'(<meta http-equiv="Content-Security-Policy" content=")([^"]+)(")', html)
if not meta:
    sys.exit('No Content-Security-Policy meta tag found in index.html')
csp = meta.group(2)

# Inline scripts are exactly <script>...</script> with no attributes.
blocks = re.findall(r'<script>(.*?)</script>', html, re.S)
hashes = ["'sha256-" + base64.b64encode(hashlib.sha256(b.encode('utf-8')).digest()).decode() + "'" for b in blocks]
current = re.findall(r"'sha256-[^']+'", csp)

if sorted(current) == sorted(hashes):
    print(f'CSP OK: {len(hashes)} inline script hash(es) match.')
    sys.exit(0)

if '--check' in sys.argv:
    print('CSP MISMATCH: inline scripts changed but their hashes in the CSP were not updated.')
    print('Run: python3 tools/update_csp.py')
    sys.exit(1)

script_src = re.search(r"script-src ([^;]+)", csp)
if not script_src:
    sys.exit('CSP has no script-src directive')
others = [t for t in script_src.group(1).split() if not t.startswith("'sha256-")]
new_csp = csp.replace(script_src.group(0), 'script-src ' + ' '.join(others + hashes))
html = html[:meta.start(2)] + new_csp + html[meta.end(2):]
open(PATH, 'w', encoding='utf-8').write(html)
print(f'CSP updated with {len(hashes)} inline script hash(es).')
