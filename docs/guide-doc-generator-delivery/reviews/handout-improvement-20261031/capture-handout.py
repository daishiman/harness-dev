import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

WORK = Path(__file__).resolve().parent
SOURCE = Path(json.loads((WORK / 'source.json').read_text())['source_dir'])
HTML = WORK / 'handout.html'
config = json.loads((WORK / 'normalized-config.json').read_text())
out = WORK / 'screens'
out.mkdir(exist_ok=True)
captures, measurements, assets = [], [], []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
    page.emulate_media(reduced_motion='reduce')
    page.goto(HTML.as_uri(), wait_until='load', timeout=120000)
    page.evaluate('document.fonts.ready')
    for width in [1440, 768, 375]:
        page.set_viewport_size({'width': width, 'height': 1000})
        page.locator('details').evaluate_all('(xs)=>xs.forEach(x=>x.open=false)')
        page.evaluate('window.scrollTo(0,0)')
        page.locator('.navbar').evaluate('(x)=>x.scrollTop=0')
        first = out / f'opening-{width}.png'
        page.screenshot(path=str(first), animations='disabled')
        captures.append({'section_id': 'opening', 'width_px': width, 'state': '初期表示', 'path': str(first)})
        for section in config['sections']:
            sid = section['id']
            target = page.locator(f'section[id="{sid}"]')
            target.scroll_into_view_if_needed()
            path = out / f'{sid}-{width}.png'
            target.screenshot(path=str(path), animations='disabled', timeout=30000)
            captures.append({'section_id': sid, 'width_px': width, 'state': '初期表示', 'path': str(path)})
            for index, diagram in enumerate(target.locator('.diagram').all()):
                diagram_path = out / f'{sid}-{width}-diagram-{index + 1}.png'
                diagram.screenshot(path=str(diagram_path), animations='disabled')
                captures.append({'section_id': sid, 'width_px': width, 'state': f'図{index + 1}の初期表示', 'path': str(diagram_path)})
            if target.locator('details').count():
                target.locator('details').evaluate_all('(xs)=>xs.forEach(x=>x.open=true)')
                expanded_path = out / f'{sid}-{width}-details-open.png'
                target.screenshot(path=str(expanded_path), animations='disabled')
                captures.append({'section_id': sid, 'width_px': width, 'state': '詳細をすべて開く', 'path': str(expanded_path)})
                target.locator('details').evaluate_all('(xs)=>xs.forEach(x=>x.open=false)')
            for index, region in enumerate(target.locator('.diagram-viewport, .table-wrap').all()):
                if region.evaluate('(x)=>x.scrollWidth>x.clientWidth+1'):
                    for position, fraction in [('middle', .5), ('end', 1)]:
                        region.evaluate('(x,f)=>x.scrollLeft=(x.scrollWidth-x.clientWidth)*f', fraction)
                        region_path = out / f'{sid}-{width}-scroll-{index}-{position}.png'
                        subject = region if 'table-wrap' in (region.get_attribute('class') or '') else region.locator('..')
                        subject.screenshot(path=str(region_path), animations='disabled')
                        captures.append({'section_id': sid, 'width_px': width, 'state': f'図{index + 1}を横スクロール（{position}）', 'path': str(region_path)})
                    region.evaluate('(x)=>x.scrollLeft=0')
                    region.focus()
                    page.keyboard.press('ArrowRight')
                    page.wait_for_timeout(80)
                    measurements.append({'section_id': sid, 'width_px': width, 'operation': 'scroll-keyboard', 'moved': region.evaluate('(x)=>x.scrollLeft>0')})
                    region.evaluate('(x)=>x.scrollLeft=0')
            for index, expand in enumerate(target.locator('.diagram-expand').all()):
                expand.focus()
                expand.press('Enter')
                page.locator('dialog[open]').wait_for()
                zoom_path = out / f'{sid}-{width}-zoom-{index + 1}.png'
                page.screenshot(path=str(zoom_path), animations='disabled')
                captures.append({'section_id': sid, 'width_px': width, 'state': f'図{index + 1}をキーボードで拡大', 'path': str(zoom_path)})
                page.keyboard.press('Escape')
                measurements.append({'section_id': sid, 'width_px': width, 'operation': 'zoom-each', 'dialog_closed': page.locator('dialog[open]').count()==0, 'focus_restored': expand.evaluate('(x)=>x===document.activeElement')})
            values = target.evaluate('''(root)=>({
                height:root.offsetHeight,
                diagramText:[...root.querySelectorAll('.diagram svg text')].map(x=>{let m=x.getScreenCTM();return {text:x.textContent,px:parseFloat(getComputedStyle(x).fontSize)*Math.hypot(m.a,m.b)}}),
                handson:[...root.querySelectorAll('.hs-row')].map(x=>({columns:getComputedStyle(x).gridTemplateColumns,labels:[...x.querySelectorAll('.hs-field-label')].map(y=>y.textContent)})),
                scrollRegions:[...root.querySelectorAll('.diagram-viewport,.table-wrap')].map(x=>({client:x.clientWidth,scroll:x.scrollWidth})),
                figureImages:[...root.querySelectorAll('.diagram-image')].map(x=>({alt:x.alt,width:x.getBoundingClientRect().width,height:x.getBoundingClientRect().height}))
            })''')
            measurements.append({'section_id': sid, 'width_px': width, **values})
        print('captured', width, flush=True)
        measurements.append({'width_px': width, 'page': page.evaluate('({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})')})
    page.set_viewport_size({'width': 768, 'height': 1000})
    qa = page.locator('#qa')
    qa.locator('details').evaluate_all('(xs)=>xs.forEach(x=>x.open=true)')
    qpath = out / 'qa-768-open.png'
    qa.screenshot(path=str(qpath), animations='disabled')
    captures.append({'section_id': 'qa', 'width_px': 768, 'state': '詳細を開く', 'path': str(qpath)})
    qa.locator('details').evaluate_all('(xs)=>xs.forEach(x=>x.open=false)')
    button = page.locator('#ask .diagram-expand').first
    button.focus()
    button.press('Enter')
    dialog = page.locator('dialog[open]')
    dialog.wait_for()
    zoom = out / 'ask-768-zoom.png'
    page.screenshot(path=str(zoom), animations='disabled')
    captures.append({'section_id': 'ask', 'width_px': 768, 'state': 'キーボードで図を拡大', 'path': str(zoom)})
    page.keyboard.press('Escape')
    measurements.append({'operation': 'zoom-keyboard', 'dialog_closed': page.locator('dialog[open]').count() == 0, 'focus_restored': button.evaluate('(x)=>x===document.activeElement')})
    page.evaluate('document.querySelector("#qa details").open=true;window.dispatchEvent(new Event("beforeprint"))')
    opened = page.locator('details:not([open])').count() == 0
    page.evaluate('window.dispatchEvent(new Event("afterprint"))')
    measurements.append({'operation': 'print-details', 'all_open_beforeprint': opened, 'restored_open_count': page.locator('details[open]').count()})
    for asset in config['assets']:
        source = SOURCE / asset['src']
        if not source.exists():
            source = WORK / 'materialized' / asset['src']
        if source.suffix.lower() == '.svg':
            asset_page = browser.new_page(viewport={'width': 640, 'height': 640})
            asset_page.goto(source.as_uri())
            raster = out / (asset['id'] + '-original.png')
            asset_page.locator('svg').screenshot(path=str(raster))
            asset_page.close()
            source = raster
        assets.append({'asset_id': asset['id'], 'path': str(source)})
    browser.close()
measurements_path = WORK / 'display-measurements.json'
measurements_path.write_text(json.dumps(measurements, ensure_ascii=False, indent=2) + '\n')
manifest = {'html_sha256': hashlib.sha256(HTML.read_bytes()).hexdigest(), 'captures': captures, 'assets': assets, 'measurements_path': str(measurements_path), 'unavailable': []}
(WORK / 'visual-evidence.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
print('captures:', len(captures), 'assets:', len(assets), flush=True)
