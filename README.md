# Home warranties

A small offline-friendly web app for tracking home warranties, guarantees and renewals (appliances, car insurance, home policies).

This repo holds **only the app code**. The actual warranty list lives in a separate **private** repo (`home-warranties-data`, file `warranties.json`). The app reads and writes that file through the GitHub API using a fine-grained access token that each device enters once. Without a token, the app shows nothing but its setup screen.

## How it works

- Changes are saved on the device first, so it works offline.
- When online, each device syncs with the private repo. Edits from different devices are merged item by item (newest change wins), and deletions carry across.
- Every save is a commit in the private repo, so there's a full history of changes and who made them.
- Photos and PDFs of receipts and certificates can be attached to any item. Photos are shrunk to about 500 KB, and everything is stored in the private repo under `files/`. Documents need a connection to add or open; the text works offline.
- PDFs open inside the app using [PDF.js](https://mozilla.github.io/pdf.js/) (in `pdfjs/`, Apache 2.0 licence), with zoom and a Download button.

## Setup

1. **This repo (public):** upload `index.html`, `sw.js`, `manifest.webmanifest`, `icon.svg`, `icon-180.png`, `icon-192.png`, `icon-512.png`. Then go to Settings → Pages → Deploy from a branch → `main` / root.
2. **Data repo (private):** create `Warranties-data` as a private repo and upload `warranties.json` to it. Never put that file in this public repo.
3. **A token for each device:** GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token.
   - Repository access: Only select repositories → `Warranties-data`
   - Permissions → Repository permissions → Contents: **Read and write**
   - Pick the longest expiry offered, and note the date.
4. **On each phone:** open the Pages link, paste the token, give the device a name, then use the browser menu → Add to Home screen.

If a phone is lost, delete that device's token on GitHub; the other phone keeps working.
