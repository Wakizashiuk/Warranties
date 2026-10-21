"""Two phones syncing through a mock GitHub: setup, import, edits, offline edits, merges, deletes, save races."""
import json, base64, hashlib, time, os
from playwright.sync_api import sync_playwright
from _common import wait_js, REPO, SAMPLE_DATA, SHOTS, TOKEN, serve, Checks

APP = REPO
DATA = SAMPLE_DATA
srv, BASE = serve(APP)

# --- fake GitHub ---
remote = {'content': None, 'sha': None, 'puts': 0, 'conflicts': 0}
def handler(route, req):
    url = req.url
    if req.headers.get('authorization') != 'Bearer ' + TOKEN:
        return route.fulfill(status=401, body='{}', headers={'access-control-allow-origin': '*'})
    h = {'access-control-allow-origin': '*', 'content-type': 'application/json'}
    if req.method == 'OPTIONS':
        return route.fulfill(status=204, headers={**h, 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET,PUT'})
    if url.endswith('/repos/Wakizashiuk/Warranties-data'):
        return route.fulfill(status=200, body='{"private":true}', headers=h)
    if '/contents/warranties.json' in url:
        if req.method == 'GET':
            if remote['content'] is None:
                return route.fulfill(status=404, body='{}', headers=h)
            return route.fulfill(status=200, headers=h, body=json.dumps({'sha': remote['sha'], 'content': base64.encodebytes(remote['content'].encode()).decode()}))
        if req.method == 'PUT':
            body = json.loads(req.post_data)
            if remote.get('inject'):
                d = json.loads(remote['content']); d['items'].append({'id':'sneaky','room':'kitchen','name':'Microwave','type':'other','updatedAt':int(time.time()*1000)})
                remote['content'] = json.dumps(d); remote['sha'] = 'changed-by-other-phone'; remote['inject'] = False
            if remote['sha'] != body.get('sha'):
                remote['conflicts'] += 1
                return route.fulfill(status=409, body='{}', headers=h)
            remote['content'] = base64.b64decode(body['content']).decode()
            remote['sha'] = hashlib.sha1(remote['content'].encode()).hexdigest()
            remote['puts'] += 1
            return route.fulfill(status=200, body='{}', headers=h)
    return route.fulfill(status=404, body='{}', headers=h)

def rdata(): return json.loads(remote['content'])
check = Checks('e2e')

def new_phone(b, dark=False):
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, service_workers='block', color_scheme='dark' if dark else 'light')
    ctx.route('https://api.github.com/**', handler)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(BASE)
    return ctx, pg, errs

def connect(pg, device):
    pg.fill('input[name=token]', TOKEN)
    pg.fill('input[name=device]', device)
    pg.click('form[data-setup] button[type=submit]')

with sync_playwright() as p:
    b = p.chromium.launch()

    # 1. First run, missing data file, import
    ctx1, a, errs1 = new_phone(b)
    check('setup screen shows', a.locator('text=Connect to your private data').count() == 1)
    a.screenshot(path=SHOTS + '/1-setup.png', full_page=True)
    connect(a, "Dave's phone")
    a.wait_for_selector('text=Start fresh')
    check('missing-file banner', True)
    a.set_input_files('#importfile', DATA)
    for _ in range(300):  # wait for the import to reach the mock GitHub (the pill says "Synced never" before this)
        if remote['content'] is not None: break
        a.wait_for_timeout(100)
    wait_js(a, "document.querySelector('#pill').textContent.includes('Synced') && !document.querySelector('#pill').textContent.includes('never')")
    check('imported + pushed', remote['content'] is not None and len(rdata()['items']) == 13)
    check('4 tabs', len(rdata()['rooms']) == 4)
    a.screenshot(path=SHOTS + '/2-overview.png', full_page=True)

    # reopen the app with the list already saved on the phone (the bug Dave hit)
    a.reload()
    wait_js(a, "document.querySelector('#pill') && document.querySelector('#pill').textContent.includes('Synced')")
    check('reopen with saved data renders', a.locator('text=Something went wrong').count() == 0 and a.locator('button[data-tab=kitchen]').count() == 1)
    a.goto(BASE); a.wait_for_timeout(300)
    check('fresh launch with saved data, before sync, shows items', a.locator('button[data-tab=kitchen]').count() == 1)

    # kitchen tab
    a.click('button[data-tab=kitchen]')
    a.screenshot(path=SHOTS + '/3-kitchen.png', full_page=True)
    check('kitchen has 10 cards', a.locator('article.card').count() == 10)

    # 2. Second phone (Corin) connects and sees data
    ctx2, c, errs2 = new_phone(b, dark=True)
    connect(c, "Corin's phone")
    wait_js(c, "document.querySelector('#pill').textContent.includes('Synced')")
    c.click('button[data-tab=master-bedroom]')
    check('Corin sees bedroom items', c.locator('article.card').count() == 3)
    c.screenshot(path=SHOTS + '/4-corin-dark.png', full_page=True)

    # 3. Add car insurance on Corin's phone
    c.click('button[data-tab=car-policies]')
    c.click('[data-additembtn]')
    c.fill('form[data-additem] input[name=name]', 'Car insurance')
    c.select_option('form[data-additem] select[name=type]', 'car')
    c.click('form[data-additem] button[type=submit]')
    c.wait_for_selector('form[data-form]')
    check('policy labels shown', c.locator('text=Renews on').count() >= 1 and c.locator('text=Registration').count() >= 1)
    c.fill('form[data-form] input[name=provider]', 'Admiral')
    c.fill('form[data-form] input[name=serial]', 'AB12 CDE')
    soon = time.strftime('%Y-%m-%d', time.localtime(time.time() + 20 * 86400))
    c.fill('form[data-form] input[name=expires]', soon)
    c.fill('form[data-form] input[name=cost]', '£540 a year')
    c.click('form[data-form] button[type=submit]')
    wait_js(c, "document.querySelector('#pill').textContent.includes('Synced')")
    c.screenshot(path=SHOTS + '/5-car.png', full_page=True)
    ci = [i for i in rdata()['items'] if i['name'] == 'Car insurance']
    check('car insurance synced', len(ci) == 1 and ci[0]['provider'] == 'Admiral')

    # 4. Dave offline edit, while Corin edits another item online -> merge
    ctx1.set_offline(True)
    a.evaluate("window.dispatchEvent(new Event('offline'))")
    a.click('button[data-tab=kitchen]')
    a.click('button[data-edit=freezer]')
    a.fill('form[data-form] input[name=brand]', 'Hotpoint')
    a.click('form[data-form] button[type=submit]')
    a.wait_for_timeout(800)
    pill = a.locator('#pill').text_content()
    check('offline pill shows saved here (' + pill + ')', 'Offline' in pill)
    check('offline edit stored on device', 'Hotpoint' in a.evaluate("localStorage.getItem('hw.data')"))

    c.click('button[data-tab=kitchen]')
    c.click('button[data-edit=dishwasher]')
    c.fill('form[data-form] input[name=brand]', 'Bosch')
    c.click('form[data-form] button[type=submit]')
    wait_js(c, "document.querySelector('#pill').textContent.includes('Synced')")

    ctx1.set_offline(False)
    a.evaluate("window.dispatchEvent(new Event('online'))")
    wait_js(a, "document.querySelector('#pill').textContent.includes('Synced')")
    items = {i['id']: i for i in rdata()['items']}
    check('Dave offline edit merged', items['freezer']['brand'] == 'Hotpoint')
    check('Corin edit kept', items['dishwasher']['brand'] == 'Bosch')
    check('car insurance still there', any(i['name'] == 'Car insurance' for i in items.values()))

    # 5. Delete on Dave's phone propagates to Corin
    a.click('button[data-tab=kitchen]')
    a.click('button[data-edit=dryer]')
    a.click('[data-askdel=dryer]')
    a.click('[data-delitem=dryer]')
    wait_js(a, "document.querySelector('#pill').textContent.includes('Synced')")
    c.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    c.wait_for_timeout(1000)
    c.click('button[data-tab=kitchen]')
    check('delete propagated', c.locator('button[data-edit=dryer]').count() == 0 and 'dryer' not in {i['id'] for i in rdata()['items']})

    # 6. Overview "coming up" shows car insurance; search works
    c.click('button[data-tab=__overview]')
    check('coming up lists car insurance', c.locator('.row:has-text("Car insurance")').count() == 1)
    c.fill('[data-search]', 'shark')
    check('search finds 3 shark items', c.locator('#results article.card').count() == 3)
    c.fill('[data-search]', '')

    # 6b. Race: other phone saves between our read and write
    remote['inject'] = True
    a.click('button[data-tab=kitchen]')
    a.click('button[data-edit=boiler]')
    a.fill('form[data-form] input[name=model]', 'EcoBlue')
    a.click('form[data-form] button[type=submit]')
    wait_js(a, "document.querySelector('#pill').textContent.includes('Synced')")
    items = {i['id']: i for i in rdata()['items']}
    check('race resolved: both changes kept', items['boiler']['model'] == 'EcoBlue' and 'sneaky' in items and remote['conflicts'] == 1)

    # 7. Data never in the app files
    shell = open(APP + '/index.html').read()
    check('no sample serials in app code', 'SAMPLE-SERIAL-001' not in shell and 'SAMPLE-IMEI-000' not in shell)

    # 8. Bad token
    ctx3, d, errs3 = new_phone(b)
    d.fill('input[name=token]', 'nope')
    d.click('form[data-setup] button[type=submit]')
    d.wait_for_selector('text=didn’t accept the access token')
    check('bad token message', True)

    # 9. Offline app shell via service worker
    ctx4 = b.new_context(viewport={'width': 390, 'height': 844})
    ctx4.route('https://api.github.com/**', handler)
    e = ctx4.new_page()
    e.goto(BASE)
    e.evaluate("navigator.serviceWorker.ready")
    e.wait_for_timeout(1000)
    e.reload()
    e.wait_for_timeout(500)
    ctx4.set_offline(True)
    try:
        e.reload()
        check('app loads offline via service worker', e.locator('h1').text_content() == 'Home warranties')
    except Exception as ex:
        check('app loads offline via service worker: ' + str(ex)[:80], False)

    for pg_ in (a, c):
        pg_.reload(); pg_.wait_for_timeout(500)
    check('both phones reopen cleanly at the end', a.locator('text=Something went wrong').count() == 0 and c.locator('text=Something went wrong').count() == 0 and c.locator('button[data-tab=kitchen]').count() == 1)
    check('no JS errors', not (errs1 + errs2 + errs3))
    print('errors:', errs1 + errs2 + errs3)
    print('puts', remote['puts'], 'conflicts handled', remote['conflicts'])
    b.close()
srv.shutdown()
check.finish()
