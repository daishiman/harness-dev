import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

work = Path(__file__).resolve().parent
html = work / 'handout.html'
manifest_path = work / 'visual-evidence.json'
manifest = json.loads(manifest_path.read_text())
assert manifest['html_sha256'] == hashlib.sha256(html.read_bytes()).hexdigest()
measurements = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless=True)
    page = browser.new_page(viewport={'width': 375, 'height': 1000}, device_scale_factor=1)
    page.emulate_media(reduced_motion='reduce')
    page.goto(html.as_uri(), wait_until='load', timeout=120000)
    page.evaluate('document.fonts.ready')
    for width in [375, 768, 1440]:
        page.set_viewport_size({'width': width, 'height': 1000})
        for sid in ['what', 'make']:
            section = page.locator('#' + sid)
            page.locator('.navbar a[href="#' + sid + '"]').evaluate('(x)=>x.click()')
            path = work / 'screens' / f'{sid}-{width}-viewport-nav.png'
            page.screenshot(path=str(path), animations='disabled')
            manifest['captures'].append({'section_id': sid, 'width_px': width, 'state': '実ビューポート：目次から移動した直後', 'path': str(path)})
            measurements.append(page.evaluate('''(sid)=>{let h=document.querySelector('.pop-header').getBoundingClientRect();let t=document.querySelector('.toolbar').getBoundingClientRect();let s=document.getElementById(sid);let f=s.querySelector('[data-hb-field="lead_line"]').getBoundingClientRect();return {section_id:sid,width_px:innerWidth,header_bottom:h.bottom,toolbar_top:t.top,lead_top:f.top,lead_bottom:f.bottom,lead_visible:f.top>=h.bottom&&f.bottom<=t.top}}''',sid))
            if width == 1440:
                continue
            targets = ([section.locator('[data-hb-part="B03"]')] if sid == 'what'
                       else section.locator('.hs-row').all() + section.locator('[data-hb-part="B11"]').all())
            details = section.locator('details').all()
            for detail in details:
                detail.evaluate('(x)=>x.open=true')
            targets += details
            for index, target in enumerate(targets):
                for position in ['top', 'bottom']:
                    target.evaluate('''(x,position)=>{let r=x.getBoundingClientRect();let h=document.querySelector('.pop-header').getBoundingClientRect().height;let f=document.querySelector('.toolbar').getBoundingClientRect().height;window.scrollTo(0,position==='top'?r.top+scrollY-h-16:r.bottom+scrollY-innerHeight+f+16)}''',position)
                    path = work / 'screens' / f'{sid}-{width}-viewport-{index}-{position}.png'
                    page.screenshot(path=str(path), animations='disabled')
                    manifest['captures'].append({'section_id': sid, 'width_px': width, 'state': f'実ビューポート：部品{index + 1}の{position}（詳細は展開）', 'path': str(path)})
            for detail in details:
                detail.evaluate('(x)=>x.open=false')
        print('viewport captured:',width,flush=True)
    browser.close()
(work / 'viewport-measurements.json').write_text(json.dumps(measurements,ensure_ascii=False,indent=2)+'\n')
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('viewport lead measurements:',measurements,flush=True)
