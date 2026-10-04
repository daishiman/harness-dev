"""The delivered file works alone, including direct links and no-script reading."""
from __future__ import annotations

import json
from pathlib import Path

from conftest import needs_browser, node_eval, run_script


@needs_browser
def test_standalone_navigation_and_fallback(case_with_png: Path, tmp_path: Path) -> None:
    rc, result, err = run_script('build-briefing-book', '--dir', str(case_with_png))
    assert rc == 0, err
    # Only this file travels: none of its original neighbours are available here.
    standalone = tmp_path / 'delivery' / 'book.html'
    standalone.parent.mkdir()
    standalone.write_bytes(Path(result['out']).read_bytes())
    out = node_eval('''
import {launchBrowser, findBrowser} from "./lib/browser-session.mjs";
const browser = await launchBrowser(findBrowser());
try {
  const page = await browser.newPage({width: 1440, height: 1000});
  const url = URL_VALUE;
  const load = async hash => { await page.goto('about:blank'); await page.goto(url + hash); };
  const snapshot = () => page.evaluate(`({
    on: [...document.querySelectorAll('main > .page.on')].map(p => p.id),
    visible: [...document.querySelectorAll('main > .page')].filter(p => getComputedStyle(p).display !== 'none').length,
    current: document.querySelectorAll('.toc a[aria-current="page"]').length,
    overflow: document.documentElement.scrollWidth > innerWidth
  })`);
  const initial = [];
  for (const hash of ['#toc', '#%E0%A4%A', '#missing']) {
    await load(hash);
    initial.push(await snapshot());
  }
  await load('');
  const links = await page.evaluate("[...document.querySelectorAll('.toc a')].map(a => a.getAttribute('href'))");
  const navigated = [];
  for (const href of links) {
    await page.evaluate(`new Promise(resolve => {
      const href = ${JSON.stringify(href)};
      const link = [...document.querySelectorAll('.toc a')].find(a => a.getAttribute('href') === href);
      if (location.hash === href) { link.click(); resolve(); return; }
      addEventListener('hashchange', () => requestAnimationFrame(() => resolve()), {once: true});
      link.click();
    })`);
    navigated.push(await snapshot());
  }
  const images = await page.evaluate(`Promise.all([...document.images].map(async img => {
    try { await img.decode(); return img.src.startsWith('data:') && img.naturalWidth > 0; }
    catch { return false; }
  }))`);
  await page.send('Emulation.setDeviceMetricsOverride', {width: 390, height: 844, deviceScaleFactor: 1, mobile: false});
  await load('#p-req');
  const mobile = await snapshot();
  await page.send('Emulation.setScriptExecutionDisabled', {value: true});
  await load('');
  const noScript = await snapshot();
  const count = await page.evaluate("document.querySelectorAll('main > .page').length");
  console.log(JSON.stringify({initial, navigated, images, mobile, noScript, count}));
} finally { await browser.close(); }
'''.replace('URL_VALUE', json.dumps(standalone.as_uri())), timeout=180)
    assert all(s['on'] == ['p-cover'] and s['visible'] == 1 for s in out['initial'])
    assert out['navigated']
    assert all(s['visible'] == 1 and s['current'] == 1 for s in out['navigated'])
    assert out['images'] and all(out['images'])
    assert out['mobile']['on'] == ['p-req'] and not out['mobile']['overflow']
    assert out['noScript']['visible'] == out['count']
