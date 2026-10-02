#!/usr/bin/env node

import { mkdir, writeFile } from 'node:fs/promises'
import { basename, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { evaluate, launchChrome } from '../scripts/lib/cdp.mjs'
import { check, finish, skillRoot } from './_harness.mjs'

if (!globalThis.WebSocket) throw new Error('WebSocket is required. On Node 20, run with --experimental-websocket.')

const referenceDir = join(skillRoot, 'assets/reference')
const widths = [375, 768, 1280, 1600]
const pages = ['catalog.html', 'index.html', 'pop.html']
const screenshotIndex = process.argv.indexOf('--screenshots')
const screenshotDir = screenshotIndex >= 0 ? resolve(process.argv[screenshotIndex + 1] || 'reference-screenshots') : null

const auditExpression = `new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => {
  const visible = (selector) => [...document.querySelectorAll(selector)].filter((node) => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden');
  const px = (selector) => visible(selector).map((node) => Number.parseFloat(getComputedStyle(node).fontSize));
  const heights = (selector) => visible(selector).map((node) => node.getBoundingClientRect().height);
  const styleOf = (selector) => {
    const node = document.querySelector(selector);
    if (!node) return null;
    const style = getComputedStyle(node);
    return { borderColor: style.borderColor, backgroundColor: style.backgroundColor, boxShadow: style.boxShadow };
  };
  const resolvedColor = (name) => {
    const probe = document.createElement('span');
    probe.style.color = 'var(' + name + ')';
    document.body.appendChild(probe);
    const value = getComputedStyle(probe).color;
    probe.remove();
    return value;
  };
  const normal = document.querySelector('#cat-email')?.getBoundingClientRect();
  const invalid = document.querySelector('#cat-email-err')?.getBoundingClientRect();
  resolve({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    innerWidth: window.innerWidth,
    bodyFonts: px('body'),
    controlFonts: px('button, input:not([type="checkbox"]):not([type="radio"]), select, textarea'),
    navFonts: px('.app-nav button, .side-nav :is(a, button), .bottom-tabs :is(a, button), .pop-nav button'),
    controlHeights: heights('button, input:not([type="checkbox"]):not([type="radio"]), select, textarea'),
    shortControls: visible('button, input:not([type="checkbox"]):not([type="radio"]), select, textarea')
      .map((node) => ({ tag: node.tagName, id: node.id, className: node.className, text: node.textContent.trim().slice(0, 30), height: node.getBoundingClientRect().height }))
      .filter((item) => item.height + 0.01 < 44),
    fieldTopDelta: normal && invalid ? Math.abs(normal.top - invalid.top) : null,
    fieldHeightDelta: normal && invalid ? Math.abs(normal.height - invalid.height) : null,
    inputDefault: styleOf('#cat-email'),
    inputInvalid: styleOf('#cat-email-err'),
    inputTokens: {
      normal: resolvedColor('--input-border'),
      hover: resolvedColor('--input-border-hover'),
      focus: resolvedColor('--input-border-focus'),
      invalid: resolvedColor('--input-invalid-border')
    },
    sideNavDisplay: getComputedStyle(document.querySelector('.app-shell .side-nav') || document.body).display,
    bottomTabsDisplay: getComputedStyle(document.querySelector('.bottom-tabs') || document.body).display,
    catalogTheadDisplay: getComputedStyle(document.querySelector('.catalog-section thead') || document.body).display
  });
})))`

const interactionExpressions = {
  'catalog.html': `(() => {
    const chips = [...document.querySelectorAll('.chip-grid .chip')];
    chips[1].click();
    const clickSelection = chips[1].getAttribute('aria-pressed') === 'true';
    chips[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    const arrowSelection = chips[2].getAttribute('aria-pressed') === 'true';
    chips[3].dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    const enterSelection = chips[3].getAttribute('aria-pressed') === 'true';
    chips[0].dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    const spaceSelection = chips[0].getAttribute('aria-pressed') === 'true';
    const listTab = document.querySelector('[data-tab="list"]');
    listTab.click();
    const tabSwitched = listTab.getAttribute('aria-current') === 'page' && !document.getElementById('catalog-panel-list').hidden && document.getElementById('catalog-panel-home').hidden;
    document.querySelector('[data-action-message="送信しました"]').click();
    const actionResult = document.getElementById('catalog-status').textContent === '送信しました';
    const invalid = document.getElementById('cat-email-err');
    invalid.value = 'sato@example.com';
    invalid.dispatchEvent(new Event('input', { bubbles: true }));
    const validationRecovered = invalid.getAttribute('aria-invalid') === 'false' && document.getElementById('cat-email-error').hidden;
    document.querySelector('[data-clear-form]').click();
    const formCleared = document.getElementById('cat-email').value === '' && document.getElementById('catalog-form-status').textContent === '入力をクリアしました';
    document.querySelector('[data-sort-table]').click();
    const sorted = document.querySelector('#catalog-table tbody tr').dataset.sortValue === '7350' && document.querySelector('#catalog-table th[aria-sort]').getAttribute('aria-sort') === 'ascending';
    const filter = document.getElementById('catalog-status-filter');
    filter.value = 'closed';
    filter.dispatchEvent(new Event('change', { bubbles: true }));
    const visibleRows = [...document.querySelectorAll('#catalog-table tbody tr')].filter((row) => !row.hidden);
    const filtered = visibleRows.length === 1 && visibleRows[0].dataset.status === 'closed';
    const term = document.querySelector('a.term');
    term.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    const pop = document.getElementById('term-pop');
    const termExplained = Boolean(pop) && !pop.hidden && pop.textContent.includes('データの件数');
    const glossary = document.querySelector('.glossary > details');
    const termExplanationIsNotAlwaysVisible = !glossary.open;
    term.click();
    const termStaysOnPage = !pop.hidden && !document.location.hash;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    const termClosedByEscape = pop.hidden && document.activeElement === term;
    const howto = document.querySelector('details.howto');
    howto.querySelector('summary').click();
    const details = document.querySelector('details.disclosure');
    details.querySelector('summary').click();
    return { clickSelection, arrowSelection, enterSelection, spaceSelection, tabSwitched, actionResult, validationRecovered, formCleared, sorted, filtered, termExplained, termExplanationIsNotAlwaysVisible, termStaysOnPage, termClosedByEscape, howtoOpened: howto.open, disclosureOpened: details.open };
  })()`,
  'index.html': `(() => {
    const report = document.querySelector('.side-nav [data-nav="report"]');
    report.click();
    const navSwitched = report.getAttribute('aria-current') === 'page' && !document.getElementById('view-report').hidden && document.getElementById('view-home').hidden;
    document.getElementById('btn-reply-unanswered').click();
    return { navSwitched, actionResult: document.getElementById('toast-region').textContent.includes('未返信11件の返信を開始しました') };
  })()`,
  'pop.html': `(() => {
    const chips = [...document.querySelectorAll('#pop-chips .pop-chip')];
    chips[1].click();
    const clickSelection = chips[1].getAttribute('aria-pressed') === 'true';
    chips[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    const keyboardSelection = chips[2].getAttribute('aria-pressed') === 'true';
    const tone = document.querySelectorAll('.segmented button')[1];
    tone.click();
    const segmentSelection = tone.getAttribute('aria-pressed') === 'true';
    document.getElementById('tune-btn').click();
    const disclosureOpened = document.getElementById('tune-btn').getAttribute('aria-expanded') === 'true' && !document.getElementById('settings-panel').hidden;
    const checkbox = document.querySelector('.pop-row input[type="checkbox"]');
    checkbox.click();
    const countSynced = document.getElementById('deal-count').textContent === '2件が選択済み' && document.getElementById('pop-send').textContent.startsWith('2件');
    document.getElementById('pop-send').click();
    return { clickSelection, keyboardSelection, segmentSelection, disclosureOpened, countSynced, actionResult: document.getElementById('pop-status').textContent === '2件を送信しました' };
  })()`
}

const evaluateValue = (expression) => evaluate(client, expression)

const { client, close } = await launchChrome({ purpose: 'the reference browser contract', tempPrefix: 'aidd-reference-browser-' })
try {
  await client.send('Page.enable')
  if (screenshotDir) await mkdir(screenshotDir, { recursive: true })

  for (const page of pages) {
    const sourcePath = join(referenceDir, page)
    for (const width of widths) {
      await client.send('Emulation.setDeviceMetricsOverride', {
        width,
        height: 1200,
        deviceScaleFactor: 1,
        mobile: false,
        screenWidth: width,
        screenHeight: 1200
      })
      const loaded = client.waitFor('Page.loadEventFired')
      await client.send('Page.navigate', { url: pathToFileURL(sourcePath).href })
      await loaded
      const evaluated = await client.send('Runtime.evaluate', { expression: auditExpression, awaitPromise: true, returnByValue: true })
      const audit = evaluated.result.value

      check(Math.abs(audit.innerWidth - width) <= 1, `${page} ${width}px: requested CSS viewport is active (${audit.innerWidth}px)`)
      check(audit.scrollWidth <= audit.clientWidth, `${page} ${width}px: no horizontal page overflow (${audit.scrollWidth}/${audit.clientWidth})`)
      check(audit.bodyFonts.every((size) => size >= 16), `${page} ${width}px: body text is at least 16px`)
      check(audit.controlFonts.every((size) => size >= 16), `${page} ${width}px: controls are at least 16px`)
      check(audit.navFonts.every((size) => size >= 16), `${page} ${width}px: navigation is at least 16px`)
      check(audit.controlHeights.every((height) => height + 0.01 >= 44), `${page} ${width}px: controls are at least 44px high${audit.shortControls.length ? ` (${JSON.stringify(audit.shortControls)})` : ''}`)

      if (page === 'catalog.html' && width >= 768) {
        check(audit.fieldTopDelta <= 1, `${page} ${width}px: paired input tops align within 1px (${audit.fieldTopDelta}px)`)
        check(audit.fieldHeightDelta <= 1, `${page} ${width}px: paired input heights align within 1px (${audit.fieldHeightDelta}px)`)
      }
      if (page === 'catalog.html') {
        check(width < 640 ? audit.catalogTheadDisplay === 'none' : audit.catalogTheadDisplay !== 'none', `${page} ${width}px: table uses the expected responsive presentation`)
        check(audit.inputDefault?.borderColor === audit.inputTokens.normal, `${page} ${width}px: default input uses the control border (${audit.inputDefault?.borderColor})`)
        check(audit.inputDefault?.backgroundColor !== 'rgba(0, 0, 0, 0)' && audit.inputDefault?.boxShadow !== 'none', `${page} ${width}px: default input keeps a visible fill and inset depth`)
        check(audit.inputInvalid?.borderColor === audit.inputTokens.invalid, `${page} ${width}px: invalid input uses the error border (${audit.inputInvalid?.borderColor})`)

        const rect = await evaluateValue(`new Promise((resolve) => {
          const input = document.getElementById('cat-email');
          input.scrollIntoView({ block: 'center' });
          requestAnimationFrame(() => requestAnimationFrame(() => {
            const box = input.getBoundingClientRect();
            resolve({ x: box.left + box.width / 2, y: box.top + box.height / 2 });
          }));
        })`)
        await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rect.x, y: rect.y })
        const hoverBorder = await evaluateValue(`new Promise((resolve) => setTimeout(() => resolve(getComputedStyle(document.getElementById('cat-email')).borderColor), 180))`)
        check(hoverBorder === audit.inputTokens.hover, `${page} ${width}px: hovered input strengthens its border (${hoverBorder})`)
        const focusBorder = await evaluateValue(`new Promise((resolve) => {
          document.getElementById('cat-email').focus();
          setTimeout(() => resolve(getComputedStyle(document.getElementById('cat-email')).borderColor), 180);
        })`)
        check(focusBorder === audit.inputTokens.focus, `${page} ${width}px: focused input uses the focus border (${focusBorder})`)
      }
      if (page === 'index.html' && width < 640) {
        check(audit.sideNavDisplay === 'none' && audit.bottomTabsDisplay === 'grid', `${page} ${width}px: sidebar becomes labeled bottom tabs`)
      }

      const interaction = await evaluateValue(interactionExpressions[page])
      Object.entries(interaction).forEach(([name, passed]) => {
        check(passed === true, `${page} ${width}px: interaction ${name}`)
      })

      if (screenshotDir) {
        const reloaded = client.waitFor('Page.loadEventFired')
        await client.send('Page.reload', { ignoreCache: true })
        await reloaded
        await client.send('Runtime.evaluate', { expression: 'new Promise((resolve) => { window.scrollTo(0, 0); setTimeout(resolve, 350); })', awaitPromise: true })
        const { cssContentSize } = await client.send('Page.getLayoutMetrics')
        const screenshot = await client.send('Page.captureScreenshot', {
          format: 'png',
          fromSurface: true,
          captureBeyondViewport: true,
          clip: { x: 0, y: 0, width: cssContentSize.width, height: Math.min(cssContentSize.height, 10000), scale: 1 }
        })
        const screenshotPath = join(screenshotDir, `${basename(page, '.html')}-${width}.png`)
        await writeFile(screenshotPath, screenshot.data, 'base64')
        console.log(`PASS screenshot ${screenshotPath}`)
      }
    }
  }
} finally {
  await close()
}

finish()
