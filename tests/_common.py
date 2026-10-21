"""Shared helpers for the browser tests. Uses only fake sample data; never point these at the real data repo."""
import functools, http.server, os, socket, sys, threading

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO, 'tests')
FIXTURES = os.path.join(TESTS, 'fixtures')
SAMPLE_DATA = os.path.join(FIXTURES, 'sample-warranties.json')
OUT = os.path.join(TESTS, '.output')          # screenshots and generated files (git-ignored)
SHOTS = os.path.join(OUT, 'shots')
os.makedirs(SHOTS, exist_ok=True)

TOKEN = 'github_pat_TEST'                      # fake token the mock GitHub accepts
DATA_REPO = '/repos/Wakizashiuk/Warranties-data'

def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p

class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def serve(directory):
    """Serve a folder on a random local port. Returns (server, base_url)."""
    port = free_port()
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', port), functools.partial(_Quiet, directory=directory))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f'http://127.0.0.1:{port}/'

class Checks:
    def __init__(self, name):
        self.name, self.fails = name, []
    def __call__(self, label, ok):
        print(('PASS ' if ok else 'FAIL ') + label)
        if not ok: self.fails.append(label)
    def finish(self):
        print(f'[{self.name}] ' + ('ALL PASSED' if not self.fails else f'FAILED: {self.fails}'))
        sys.exit(1 if self.fails else 0)

def make_big_photo(path):
    """A ~10 MB noisy JPEG, to prove photos are shrunk before upload."""
    if os.path.exists(path): return path
    from PIL import Image
    Image.effect_noise((4000, 3000), 60).convert('RGB').save(path, quality=95)
    return path

def make_pdf(path):
    """A tiny valid one-page PDF."""
    if not os.path.exists(path):
        open(path, 'wb').write(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
                               b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
    return path

def wait_js(page, expr, timeout_ms=30000):
    """Wait until a JS expression is truthy. Playwright's wait_for_function uses eval, which the app's
    Content-Security-Policy (rightly) blocks, so poll with page.evaluate instead."""
    waited = 0
    while not page.evaluate(expr):
        if waited >= timeout_ms:
            raise TimeoutError('Timed out waiting for: ' + expr)
        page.wait_for_timeout(100); waited += 100
