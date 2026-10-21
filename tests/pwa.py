"""Installed-app behaviour as hosted on GitHub Pages under /Warranties/: upgrading from the last committed
version (HEAD) to your working copy, the no-slash redirect, offline launch, slow network, on-screen errors."""
import http.server, threading, os, re, shutil, subprocess
from playwright.sync_api import sync_playwright
from _common import REPO, OUT, SHOTS, free_port, Checks

OLD = os.path.join(OUT, 'old-version')
shutil.rmtree(OLD, ignore_errors=True); os.makedirs(OLD)
# "old" = last committed version (what is live after the previous push); "new" = the working copy
subprocess.run(['git', '-C', REPO, 'archive', 'HEAD', '-o', OLD + '/old.tar'], check=True)
subprocess.run(['tar', '-xf', OLD + '/old.tar', '-C', OLD], check=True)
NEW_CACHE = re.search(r"const CACHE = '([^']+)'", open(os.path.join(REPO, 'sw.js')).read()).group(1)
serve = {'dir': OLD}

class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def translate_path(self, path):
        path = path.split('?')[0]
        if path.startswith('/Warranties/'):
            return os.path.join(serve['dir'], path[len('/Warranties/'):] or 'index.html')
        return '/nonexistent'
    def do_GET(self):
        if self.path.split('?')[0] == '/Warranties':
            self.send_response(301); self.send_header('Location', '/Warranties/'); self.end_headers(); return
        return super().do_GET()

srv = http.server.ThreadingHTTPServer(('127.0.0.1', free_port()), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
B = 'http://127.0.0.1:%d' % srv.server_address[1]
check = Checks('installed app')

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 390, 'height': 844})
    ctx.route('https://api.github.com/**', lambda r: r.fulfill(status=401, body='{}', headers={'access-control-allow-origin': '*'}))
    pg = ctx.new_page()
    pg.goto(B + '/Warranties/')
    pg.evaluate("navigator.serviceWorker.ready.then(()=>1)")
    check('previous version loads', pg.locator('h1').first.text_content() == 'Home warranties')

    # Deploy the new version, as if re-uploaded to GitHub
    serve['dir'] = REPO
    pg.reload(); pg.wait_for_timeout(1500)
    pg.evaluate("navigator.serviceWorker.getRegistration().then(r=>r&&r.update())")
    pg.wait_for_timeout(1500)
    keys = pg.evaluate("caches.keys()")
    check('upgraded to the new cache ' + str(keys), keys == [NEW_CACHE])

    # Launch like the installed app (start_url) and via the no-slash URL
    app = ctx.new_page(); errs = []
    app.on('pageerror', lambda e: errs.append(str(e)))
    app.goto(B + '/Warranties/'); app.wait_for_timeout(500)
    check('app launch shows connect screen', app.locator('text=Connect to your private data').count() == 1)
    check('default repo is Warranties-data', app.input_value('input[name=repo]') == 'Warranties-data')
    app.goto(B + '/Warranties'); app.wait_for_timeout(500)
    check('no-slash URL with redirect still renders', app.locator('text=Connect to your private data').count() == 1)

    # Offline launch
    ctx.set_offline(True)
    app.goto(B + '/Warranties/'); app.wait_for_timeout(500)
    check('offline launch renders from saved copy', app.locator('text=Connect to your private data').count() == 1)
    ctx.set_offline(False)

    # Server hangs (very slow network): should fall back after ~4s instead of blank
    import time
    orig = H.do_GET
    def slow(self):
        if self.path.split('?')[0] in ('/Warranties/', '/Warranties/index.html'):
            time.sleep(8)
        return orig(self)
    H.do_GET = slow
    t = time.time(); app.goto(B + '/Warranties/', timeout=15000); el = time.time() - t
    check('slow network falls back to saved copy (%.1fs)' % el, el < 7 and app.locator('h1').first.text_content() == 'Home warranties')
    H.do_GET = orig

    # Error banner appears instead of blank on a JS error
    app.evaluate("setTimeout(()=>{throw new Error('test boom')},0)"); app.wait_for_timeout(200)
    check('JS errors shown on screen', app.locator('text=Something went wrong: test boom').count() == 1 or app.locator('text=test boom').count() >= 1)
    check('no page errors on launch', not [e for e in errs if 'test boom' not in e])
    app.screenshot(path=SHOTS + '/6-pwa.png')
    b.close()
srv.shutdown()
check.finish()
