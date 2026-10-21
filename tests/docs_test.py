"""Documents: camera/gallery photos (shrunk), PDFs, the in-app viewer, zoom, download, rename, delete, offline rules."""
import json, base64, hashlib, time, os
from playwright.sync_api import sync_playwright
from _common import wait_js, REPO, SAMPLE_DATA, OUT, SHOTS, TOKEN, serve, Checks, make_big_photo, make_pdf
APP=REPO; DATA=SAMPLE_DATA
PHOTO=make_big_photo(os.path.join(OUT,'big-receipt.jpg')); PDF=make_pdf(os.path.join(OUT,'Baxi certificate.pdf'))
srv,BASE=serve(APP)
files={}  # path -> (bytes, sha)
data={'content':open(DATA).read(),'sha':'s0'}
H={'access-control-allow-origin':'*','content-type':'application/json'}
def handler(route,req):
    if req.headers.get('authorization')!='Bearer '+TOKEN: return route.fulfill(status=401,body='{}',headers=H)
    u=req.url.split('?')[0]
    if u.endswith('/repos/Wakizashiuk/Warranties-data'): return route.fulfill(status=200,body='{}',headers=H)
    if u.endswith('/contents/warranties.json'):
        if req.method=='GET': return route.fulfill(status=200,headers=H,body=json.dumps({'sha':data['sha'],'content':base64.b64encode(data['content'].encode()).decode()}))
        b=json.loads(req.post_data)
        if b.get('sha')!=data['sha']: return route.fulfill(status=409,body='{}',headers=H)
        data['content']=base64.b64decode(b['content']).decode(); data['sha']=hashlib.sha1(data['content'].encode()).hexdigest()
        return route.fulfill(status=200,body='{}',headers=H)
    if '/contents/files/' in u:
        from urllib.parse import unquote
        path=unquote(u.split('/contents/',1)[1])
        if req.method=='PUT':
            b=json.loads(req.post_data); raw=base64.b64decode(b['content']); sha=hashlib.sha1(raw).hexdigest(); files[path]=(raw,sha)
            return route.fulfill(status=201,body=json.dumps({'content':{'sha':sha,'path':path}}),headers=H)
        if req.method=='GET':
            if path not in files: return route.fulfill(status=404,body='{}',headers=H)
            if 'raw' in (req.headers.get('accept') or ''): return route.fulfill(status=200,body=files[path][0],headers={'access-control-allow-origin':'*','content-type':'application/octet-stream'})
            return route.fulfill(status=200,body=json.dumps({'sha':files[path][1]}),headers=H)
        if req.method=='DELETE':
            b=json.loads(req.post_data)
            if path in files and files[path][1]==b.get('sha'): del files[path]; return route.fulfill(status=200,body='{}',headers=H)
            return route.fulfill(status=409,body='{}',headers=H)
    return route.fulfill(status=404,body='{}',headers=H)
check=Checks('documents')
def phone(b,name):
    ctx=b.new_context(viewport={'width':390,'height':844},service_workers='block'); ctx.route('https://api.github.com/**',handler)
    pg=ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(BASE); pg.fill('input[name=token]',TOKEN); pg.fill('input[name=device]',name); pg.click('form[data-setup] button[type=submit]')
    wait_js(pg, "document.querySelector('#pill').textContent.includes('Synced')"); return ctx,pg,errs
def synced(pg): wait_js(pg, "document.querySelector('#pill').textContent.includes('Synced')")
meta=lambda: json.loads(data['content']).get('files',[])
with sync_playwright() as p:
    b=p.chromium.launch()
    ca,a,ea=phone(b,"Dave's phone"); cc,c,ec=phone(b,"Corin's phone")
    a.click('button[data-tab=kitchen]')
    check('docs section on card', a.locator('[data-camdoc=boiler]').count()==1 and a.locator('[data-adddoc=boiler]').count()==1)
    # big photo via gallery
    with a.expect_file_chooser() as fc: a.click('[data-adddoc=boiler]')
    fc.value.set_files(PHOTO)
    a.wait_for_selector('text=Document added.'); synced(a)
    m=meta(); jp=[f for f in m if f['kind']=='image']
    check('photo uploaded + listed', len(jp)==1 and jp[0]['path'] in files)
    sz=len(files[jp[0]['path']][0]); check('photo shrunk to <=500KB (%d KB from %d KB)'%(sz//1024,os.path.getsize(PHOTO)//1024), sz<=500*1024)
    # camera button uses capture input
    with a.expect_file_chooser() as fc: a.click('[data-camdoc=boiler]')
    check('camera input has capture', a.evaluate("document.getElementById('caminput').getAttribute('capture')")=='environment')
    fc.value.set_files(PHOTO); wait_js(a, "document.querySelectorAll('article.card:has([data-camdoc=boiler]) .doc').length==2"); synced(a)
    print([f['name'] for f in meta()])
    check('camera photo named Photo <date>', any(f['name'].startswith('Photo ') for f in meta()))
    # pdf
    with a.expect_file_chooser() as fc: a.click('[data-adddoc=boiler]')
    fc.value.set_files(PDF); wait_js(a, "document.querySelectorAll('article.card:has([data-camdoc=boiler]) .doc').length==3"); synced(a)
    check('pdf uploaded with its name', any(f['kind']=='pdf' and f['name']=='Baxi certificate' for f in meta()))
    a.screenshot(path=SHOTS+'/7-docs-card.png',full_page=False)
    a.locator('article.card:has([data-camdoc=boiler])').screenshot(path=SHOTS+'/7b-boiler.png')
    # Corin sees + opens the photo
    c.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); c.wait_for_timeout(800); c.click('button[data-tab=kitchen]')
    check('Corin sees 3 docs on boiler', c.locator('article.card:has([data-camdoc=boiler]) .doc').count()==3)
    pid=jp[0]['id']; c.click(f'[data-viewdoc="{pid}"]'); c.wait_for_selector('#viewer img')
    ok=c.evaluate("new Promise(r=>{const i=document.querySelector('#viewer img');if(i.complete)r(i.naturalWidth);else i.onload=()=>r(i.naturalWidth)})")
    check('photo opens in viewer (%spx wide)'%ok, ok>0)
    c.screenshot(path=SHOTS+'/8-viewer.png')
    with c.expect_download() as dli: c.click('#vdl')
    check('photo download is a jpg', dli.value.suggested_filename.endswith('.jpg'))
    # rename
    c.fill('#viewer input[name=name]','Boiler receipt'); c.click('#viewer button[type=submit]'); synced(c)
    check('rename synced', any(f['name']=='Boiler receipt' for f in meta()))
    c.click('[data-vclose]')
    # pdf opens
    pdfid=[f['id'] for f in meta() if f['kind']=='pdf'][0]; c.click(f'[data-viewdoc="{pdfid}"]'); c.wait_for_selector('#pdfpages canvas')
    check('pdf renders inside the app', c.locator('#pdfpages canvas').count()>=1 and not c.locator('#vdl').is_hidden())
    w1=c.evaluate("document.querySelector('#pdfpages canvas').getBoundingClientRect().width"); c.click('[data-vzoom="1"]'); c.wait_for_timeout(600)
    w2=c.evaluate("document.querySelector('#pdfpages canvas').getBoundingClientRect().width"); check('zoom in works (%d -> %d px)'%(w1,w2), w2>w1)
    with c.expect_download() as dl: c.click('#vdl')
    check('download gives the PDF ('+dl.value.suggested_filename+')', dl.value.suggested_filename.endswith('.pdf')); c.click('[data-vclose]')
    # concurrent adds on both phones to same item
    with a.expect_file_chooser() as fc: a.click('[data-adddoc=oven]')
    with c.expect_file_chooser() as fc2: c.click('[data-adddoc=oven]')
    fc.value.set_files(PDF); fc2.value.set_files(PHOTO)
    wait_js(a, "document.querySelectorAll('article.card:has([data-camdoc=oven]) .doc').length>=1"); wait_js(c, "document.querySelectorAll('article.card:has([data-camdoc=oven]) .doc').length>=1"); synced(a); synced(c)
    a.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); a.wait_for_timeout(800); synced(a)
    check('both phones adding at once keeps both', len([f for f in meta() if f['item']=='oven'])==2)
    # delete
    with_path=[f for f in meta() if f['kind']=='pdf' and f['item']=='boiler'][0]
    c.click(f'[data-viewdoc="{with_path["id"]}"]'); c.click('[data-vask]'); c.click('[data-vdel]'); synced(c); c.wait_for_timeout(500)
    check('delete removes metadata and file', with_path['id'] not in [f['id'] for f in meta()] and with_path['path'] not in files)
    # offline: text works, docs blocked with message
    ca.set_offline(True); a.evaluate("window.dispatchEvent(new Event('offline'))")
    a.click('[data-adddoc=boiler]')
    check('offline add blocked with message', a.locator('text=needs an internet connection').count()==1)
    a.click('.doc >> nth=0'); a.wait_for_selector('#viewer >> text=need an internet connection')
    check('offline view shows message', True); a.click('[data-vclose]')
    ca.set_offline(False)
    # reopen app with docs saved
    a.reload(); synced(a); a.click('button[data-tab=kitchen]')
    check('reopen ok with docs', a.locator('text=Something went wrong').count()==0 and a.locator('.doc').count()>=3)
    # search by doc name
    a.click('button[data-tab=__overview]'); a.fill('[data-search]','boiler receipt')
    check('search finds item by document name', a.locator('#results article.card').count()==1)
    # deleting item removes its docs
    a.click('button[data-tab=kitchen]'); n_before=len(files)
    a.click('button[data-edit=oven]'); a.click('[data-askdel=oven]'); a.click('[data-delitem=oven]'); synced(a); a.wait_for_timeout(600)
    check('deleting item removes its documents', not [f for f in meta() if f['item']=='oven'] and len(files)==n_before-2)
    check('no JS errors', not (ea+ec)); print(ea+ec)
    b.close()
srv.shutdown(); check.finish()
