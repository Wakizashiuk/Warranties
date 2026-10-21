#!/usr/bin/env python3
"""Guard: this repo is PUBLIC. Fail if anything that looks like real warranty data or a secret is about to be committed.

Checks every file git would include (tracked + staged + untracked-not-ignored):
  - no warranty data files outside tests/fixtures/ (warranties.json, backups, files/ folders)
  - no GitHub tokens (except the fake test token)
  - no 15-digit numbers that look like phone IMEIs
"""
import os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
listed = subprocess.run(['git', '-C', REPO, 'ls-files', '--cached', '--others', '--exclude-standard'],
                        capture_output=True, text=True, check=True).stdout.split('\n')
problems = []
for rel in filter(None, listed):
    path = os.path.join(REPO, rel)
    if not os.path.isfile(path):
        continue
    name = os.path.basename(rel).lower()
    in_fixtures = rel.startswith('tests/fixtures/')
    if not in_fixtures and (name == 'warranties.json' or name.startswith('warranties-backup') or rel.startswith('files/')):
        problems.append(f'{rel}: looks like real warranty data; it belongs in the private Warranties-data repo')
        continue
    if rel.startswith('pdfjs/') or rel.endswith(('.png', '.jpg', '.pdf')):
        continue  # vendored library and images
    text = open(path, encoding='utf-8', errors='ignore').read()
    for tok in re.findall(r'github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9]{20,}', text):
        if tok != 'github_pat_TEST':
            problems.append(f'{rel}: contains what looks like a GitHub token')
    if re.search(r'(?<!\d)\d{15}(?!\d)', text):
        problems.append(f'{rel}: contains a 15-digit number (possible phone IMEI)')

if problems:
    print('REAL DATA GUARD FAILED:'); [print('  - ' + p) for p in problems]; sys.exit(1)
print(f'Real data guard OK ({len([l for l in listed if l])} files checked).')
