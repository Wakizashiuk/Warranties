# Home warranties: project guide for Claude Code

A small installable web app (PWA) that Dave and his wife use on their Android phones to track home warranties,
guarantees, insurance renewals and the documents that go with them. Hosted on GitHub Pages at
https://wakizashiuk.github.io/Warranties/ from the `main` branch of this repo.

## The one rule that matters most

**This repo is PUBLIC. It holds app code only. Real data never goes here.**

- The real list and documents live in the **private** repo `Wakizashiuk/Warranties-data`
  (`warranties.json` + `files/<item-id>/<doc-id>.jpg|pdf`). The app reads and writes it through the GitHub API with a
  fine-grained token that each phone enters once.
- Claude Code sessions in this repo work on **app code only**. Do not clone, read or edit `Warranties-data`, and don't
  ask for access to it. Data changes happen in the app on the phones. If a task truly needs the data repo
  (for example a bulk import), stop and ask Dave first.
- Never commit names, addresses, serial numbers, IMEIs, policy numbers, tokens or screenshots of real data.
  Tests use the fake `tests/fixtures/sample-warranties.json` only.
- `tools/check_no_data.py` runs as part of the tests and fails if anything that looks like real data or a token is in
  the repo. Keep it passing.

## Working with Dave

- Ask before assuming when a request is ambiguous; Dave prefers questions to guesses.
- He's comfortable with GitHub and web work but isn't reading the code line by line, so explain outcomes in plain
  English (UK spelling, dates like 21 Oct 2026). Say what he needs to do on his phone, if anything.
- Commit as `Wakizashiuk <188109147+Wakizashiuk@users.noreply.github.com>`. GitHub's email privacy setting rejects
  pushes from his personal address.
- After pushing to `main`, GitHub Pages takes 1–2 minutes. Phones pick up the new version on the next launch; if not,
  tell him to fully close the installed app and reopen it once.

## Files

| Path | What it is |
| --- | --- |
| `index.html` | The whole app: HTML, CSS and vanilla JS in one file. No build step, no framework, no npm. |
| `sw.js` | Service worker: caches the app shell so it opens offline. Never caches data or documents. |
| `manifest.webmanifest`, `icon*.png`, `icon.svg` | Install-to-home-screen metadata and icons. |
| `pdfjs/` | Vendored PDF.js 4.10.38 **legacy** build (Apache 2.0), renamed `.mjs`→`.js` so GitHub Pages serves a JS MIME type. Loaded lazily the first time a PDF is opened. |
| `tools/update_csp.py` | Rewrites (or `--check`s) the CSP script hashes. |
| `tools/check_no_data.py` | Real-data and token guard for this public repo. |
| `tests/` | Browser tests (Playwright + Python) against a mock GitHub API. `tests/run_all.sh` runs everything. |

## How the app works

- **Storage:** everything is saved to `localStorage` first (keys prefixed `hw.`: `cfg`, `data`, `dirty`, `lastSync`,
  `tab`), so the text works fully offline. Sync runs on load, on reconnect, when the app becomes visible, and ~0.4 s
  after each change.
- **Sync** (`doSync`): GET `warranties.json` from the data repo → merge with local → PUT with the file's `sha`.
  A 409/422 means another phone saved first: re-read, re-merge and retry (up to 3 times).
- **Merge** (`merge`): per record, the newest `updatedAt` wins. Deletions are tombstones in `deleted: {id: timestamp}`
  that beat any copy with an older `updatedAt`. Always bump `updatedAt` when changing a record and add a tombstone when
  removing one, or the change will be undone by the other phone.
- **Data shape** (`version: 2`):
  - `rooms[]`: `{id, name, order, updatedAt}` (shown as tabs; "Overview" is a virtual tab `__overview`).
  - `items[]`: `{id, room, name, type, brand, model, serial, purchased, retailer, cover, provider, policy, expires,
    cost, contact, docs, notes, updatedAt}`. Dates are `YYYY-MM-DD`.
    Types `car` and `insurance` are *policies* and relabel fields (for example `expires` → "Renews on",
    `serial` → "Registration" for cars); see `fieldsFor()`.
  - `files[]`: `{id, item, name, kind: image|pdf, path, sha, size, addedAt, updatedAt, by}`. Document bytes live at
    `path` in the data repo, which must match `files/<…>/<…>.jpg|pdf` (enforced by `okPath()`).
  - `deleted{}`: tombstones (see above). `normalise()` upgrades the old nested v1 format.
- **Status badges** come from `expires`: expired/lapsed, ≤60 days left (amber), covered/active, or no end date.
- **Documents:** photos are shrunk in the browser to about 500 KB JPEG (`shrink()`), PDFs up to 15 MB are uploaded as
  they are. Adding, opening and deleting documents need a connection; the viewer says so politely when offline.
  The viewer renders PDFs in-app with PDF.js (`isEvalSupported:false`), with zoom and a Download button.
  Prev/next arrows (`navDoc()`), ←/→ keys and a horizontal swipe (ignored while zoomed) cycle through the
  same item's documents, wrapping round, with an "N of M" counter.
- **Rendering:** `render()` rebuilds `#root` from state. Background events (sync finishing, going on/offline, the
  1-minute timer) call `renderBg()`, which only updates the sync pill while a form is open, so typing is never wiped.

## Rules that will bite you

1. **Content-Security-Policy.** `index.html` has a CSP meta tag that only allows inline `<script>` blocks whose sha256
   is listed. **After editing any inline script, run `python3 tools/update_csp.py`**, or the app shows a blank page.
   No inline event handlers (`onclick=`), no `eval`/`new Function`, and no third-party hosts without updating the CSP.
   Network calls may only go to `self` and `https://api.github.com`.
2. **Service worker cache version.** When you change any file the app loads, bump `const CACHE = 'hw-app-vN'` in
   `sw.js` so installed copies update.
3. **Start-up order.** `state` is loaded from storage only after every function and constant it needs is defined
   (near the bottom of the main script). Loading it earlier caused a "Cannot access … before initialization" crash on
   every launch after the first. Keep new top-level code that touches state below its dependencies.
4. **Errors must be visible.** A tiny first script shows a red "Something went wrong" banner for uncaught errors.
   Keep it, so a phone never just shows a blank screen.
5. **Mobile first.** It's used as an installed app on Android Chrome at about 390 px wide. Inputs are 16 px (stops
   zoom-on-focus), no horizontal page scroll, light and dark themes via CSS variables.
6. **Don't move the data repo name** (`Warranties-data`, the default in `DEFAULT_CFG`) or the file layout without a
   migration, because both phones already point at it.

## Testing

```bash
pip install playwright pillow          # once per environment
python3 -m playwright install chromium  # once per environment
tests/run_all.sh                        # CSP check, real-data guard, then all browser tests
```

- `tests/e2e.py`: two phones syncing, import, offline edits, merging, deletes, a save race (409 then retry).
- `tests/docs_test.py`: camera/gallery photos (shrunk), PDFs, in-app viewer, zoom, download, rename, delete, offline.
- `tests/pwa.py`: hosted under `/Warranties/` like GitHub Pages; upgrades from the last commit (`HEAD`) to your
  working copy, then checks the no-slash redirect, offline launch, slow-network fallback and the error banner.
- The tests run with the CSP on. Playwright's `wait_for_function` is blocked by the CSP, so use `wait_js()` from
  `tests/_common.py`.
- Screenshots go to `tests/.output/shots/` (git-ignored). Look at them after UI changes.
- Run the whole suite before every push to `main`, because `main` is what the phones run.
