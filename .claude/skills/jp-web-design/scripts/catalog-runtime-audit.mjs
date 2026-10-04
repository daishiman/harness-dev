#!/usr/bin/env node

import { spawnSync } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, isAbsolute, join, resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { failCli, parseArgs as parseCliArgs } from './lib/args.mjs'
import { evaluate, launchChrome } from './lib/cdp.mjs'
import { evidenceDigest, isInsideRoot, loadCanonicalSources } from './lib/provenance.mjs'

const selfPath = fileURLToPath(import.meta.url)
if (!globalThis.WebSocket && process.env.AIDD_CATALOG_WS_REEXEC !== '1') {
  const child = spawnSync(process.execPath, ['--experimental-websocket', selfPath, ...process.argv.slice(2)], {
    stdio: 'inherit',
    env: { ...process.env, AIDD_CATALOG_WS_REEXEC: '1' }
  })
  if (child.error) {
    console.error(child.error.message)
    process.exit(2)
  }
  process.exit(child.status ?? 2)
}
if (!globalThis.WebSocket) {
  console.error('WebSocket is required. Use Node 20+; the audit enables --experimental-websocket automatically when needed.')
  process.exit(2)
}

const usage = 'usage: catalog-runtime-audit.mjs <app-root> [--base-url=url] [--scenarios=path] [--json]'

function parseArgs(argv) {
  const { args: [rootArg], options } = parseCliArgs(argv, {
    positionals: 1,
    booleans: { '--json': 'json' },
    values: { '--base-url': 'baseUrl', '--scenarios': 'scenarios' }
  })
  return { root: resolve(rootArg), scenarios: 'docs/product/design-runtime-scenarios.json', json: false, ...options }
}

function screenUrl(options, screen) {
  if (options.baseUrl) {
    if (/^[A-Za-z][A-Za-z0-9+.-]*:|^\/\//.test(screen.url) || screen.url.startsWith('/') || screen.url.split(/[?#]/, 1)[0].split('/').includes('..')) throw new Error(`screen URL must be relative to --base-url: ${screen.url}`)
    const base = new URL(options.baseUrl.endsWith('/') ? options.baseUrl : `${options.baseUrl}/`)
    const resolved = new URL(screen.url, base)
    if (resolved.origin !== base.origin) throw new Error(`screen URL must keep the --base-url origin: ${screen.url}`)
    return resolved.href
  }
  if (isAbsolute(screen.url)) throw new Error(`screen URL must be relative when --base-url is omitted: ${screen.url}`)
  const localPath = resolve(options.root, screen.url)
  if (!isInsideRoot(options.root, localPath)) throw new Error(`screen URL must stay inside app-root: ${screen.url}`)
  return pathToFileURL(localPath).href
}

function browserAuditExpression(denylist, copyAllowlist, smallTextExemptions, runtimeMarker) {
  return `new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => {
    const denylist = ${JSON.stringify(denylist)};
    const copyAllowlist = new Set(${JSON.stringify(copyAllowlist)});
    const smallTextExemptions = ${JSON.stringify(smallTextExemptions)};
    const runtimeMarker = ${JSON.stringify(runtimeMarker)};
    const visible = (node) => {
      if (!node || node.closest('[hidden], [aria-hidden="true"]')) return false;
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0;
    };
    const describe = (node) => node.id ? '#' + node.id : node.tagName.toLowerCase() + (typeof node.className === 'string' && node.className.trim() ? '.' + node.className.trim().split(/\\s+/).join('.') : '');
    const nodes = (selector) => [...document.querySelectorAll(selector)].filter(visible);
    const textNodes = nodes('body, body *').filter((node) => [...node.childNodes].some((child) => child.nodeType === Node.TEXT_NODE && child.textContent.trim()));
    const siblingText = (node, direction) => {
      let sibling = direction === 'previous' ? node.previousSibling : node.nextSibling;
      while (sibling && !String(sibling.textContent || '').trim()) sibling = direction === 'previous' ? sibling.previousSibling : sibling.nextSibling;
      return String(sibling?.textContent || '').trim();
    };
    const validNumericFragment = (node) => {
      if (!smallTextExemptions.some((selector) => node.matches(selector))) return false;
      const text = node.textContent.replace(/\\s+/g, '').trim();
      const parentText = node.parentElement?.textContent.replace(/\\s+/g, '') || '';
      if (!/[0-9０-９]/.test(parentText)) return false;
      if (node.matches('.currency')) return /^[¥￥$€£]$/.test(text) && /[0-9０-９]/.test(siblingText(node, 'next'));
      if (node.matches('.num-sep')) return /^[,，]$/.test(text) && /[0-9０-９]$/.test(siblingText(node, 'previous')) && /^[0-9０-９]/.test(siblingText(node, 'next'));
      if (node.matches('.unit')) return /^(?:\\/?[0-9０-９]+(?:[.,][0-9０-９]+)*)?(?:%|％|円|万円|件|通|人|社|回|日|月|年|時|分|秒|個|本|台|枚|kg|g|km|m|cm|mm|pt)$/i.test(text);
      return false;
    };
    const fontCandidates = [...new Set([...textNodes, ...nodes('input:not([type="checkbox"]):not([type="radio"]), select, textarea')])].filter((node) => !validNumericFragment(node));
    const fontIssues = fontCandidates
      .map((node) => ({ selector: describe(node), px: Number.parseFloat(getComputedStyle(node).fontSize) }))
      .filter((item) => !Number.isFinite(item.px) || item.px < 16);
    const controlSelector = 'button, a[href], summary, input:not([type="hidden"]), select, textarea, [role="button"], [role="tab"], [role="checkbox"], [role="radio"]';
    const controlCandidates = [...document.querySelectorAll(controlSelector)].filter((node) => {
      const type = node instanceof HTMLInputElement ? node.type : '';
      return type === 'checkbox' || type === 'radio' || visible(node);
    });
    const controlIssues = controlCandidates
      .map((node) => {
        const type = node instanceof HTMLInputElement ? node.type : '';
        const targets = [node];
        if (type === 'checkbox' || type === 'radio') {
          for (const label of node.labels || []) if (visible(label)) targets.push(label);
          const roleTarget = node.closest('[role="checkbox"], [role="radio"]');
          if (roleTarget && visible(roleTarget)) targets.push(roleTarget);
        }
        const rects = targets.map((target) => target.getBoundingClientRect());
        const effective = rects.find((rect) => rect.width + 0.01 >= 44 && rect.height + 0.01 >= 44) || rects[0];
        return { selector: describe(node), width: effective.width, height: effective.height };
      })
      .filter((item) => item.width + 0.01 < 44 || item.height + 0.01 < 44);
    const inputIssues = nodes('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), select, textarea').filter((node) => {
      const style = getComputedStyle(node);
      const width = Number.parseFloat(style.borderTopWidth);
      const color = style.borderTopColor.replace(/\\s+/g, '');
      return !Number.isFinite(width) || width < 1 || style.borderTopStyle === 'none' || color === 'transparent' || /rgba\\([^)]*,0(?:\\.0+)?\\)$/.test(color);
    }).map(describe);
    const implementationPatterns = [
      ['interaction-note', /hover\\s*\\/\\s*pressed|hover.{0,24}(?:ms|border|surface)|pressed.{0,24}(?:scale|ms)/i],
      ['layout-note', /grid-cols|@media|container-query|breakpoint/i],
      ['css-note', /var\\(--|font-size|border\\s*\\/\\s*surface|tailwind|css\\s*(?:class|token|variable)/i],
      ['debug-note', /debug|developer note|implementation note|\\bTODO\\b/i]
    ];
    const supplementalIssues = [];
    for (const node of textNodes) {
      const text = node.textContent.replace(/\\s+/g, ' ').trim();
      const explicitRole = node.getAttribute('data-aidd-copy');
      const semanticCopy = node.closest('[role="status"], [role="alert"], .error-msg, .toast, .caution-panel, .empty-state');
      const intrinsicTag = node.matches('h1, h2, h3, h4, h5, h6, label, legend, button, a, summary, option, th, td, dt, dd, output, time, data');
      if (explicitRole && !copyAllowlist.has(explicitRole)) supplementalIssues.push({ selector: describe(node), rule: 'invalid-copy-role', text: text.slice(0, 120) });
      if (!intrinsicTag && !semanticCopy && !validNumericFragment(node) && !copyAllowlist.has(explicitRole)) supplementalIssues.push({ selector: describe(node), rule: 'unclassified-persistent-copy', text: text.slice(0, 120) });
      for (const denied of denylist) if (text.includes(denied)) supplementalIssues.push({ selector: describe(node), rule: 'reference-sample', text: text.slice(0, 120) });
      for (const [rule, pattern] of implementationPatterns) if (pattern.test(text)) supplementalIssues.push({ selector: describe(node), rule, text: text.slice(0, 120) });
    }
    const parseTime = (value) => value.split(',').map((part) => {
      const item = part.trim();
      return item.endsWith('ms') ? Number.parseFloat(item) : Number.parseFloat(item) * 1000;
    }).filter(Number.isFinite);
    const motionIssues = nodes('body *').map((node) => {
      const style = getComputedStyle(node);
      const max = Math.max(0, ...parseTime(style.animationDuration), ...parseTime(style.animationDelay), ...parseTime(style.transitionDuration), ...parseTime(style.transitionDelay));
      return { selector: describe(node), maxMs: max };
    }).filter((item) => item.maxMs > 0.1);
    const glassCandidates = nodes('.app-header, .side-nav, .bottom-tabs, .modal, .btn-primary, .btn-secondary, .chip').map((node) => {
      const style = getComputedStyle(node);
      const backdrop = style.backdropFilter || style.webkitBackdropFilter || 'none';
      const opticalLayers = style.backgroundImage !== 'none' && style.boxShadow !== 'none';
      return { selector: describe(node), backdrop, backgroundImage: style.backgroundImage, boxShadow: style.boxShadow, qualifies: backdrop !== 'none' || opticalLayers };
    });
    const declaredScreenRendered = nodes('[data-aidd-screen]').some((node) => node.getAttribute('data-aidd-screen') === runtimeMarker);
    const sideNav = document.querySelector('.side-nav');
    const bottomTabs = document.querySelector('body > .bottom-tabs');
    const usableNavigation = (container) => visible(container)
      && [...container.querySelectorAll('a[href], button')].some(visible)
      && [...container.querySelectorAll('[aria-current="page"], [aria-selected="true"]')].some(visible);
    const responsiveNavigationPresent = !sideNav || (window.innerWidth <= 639
      ? !visible(sideNav) && usableNavigation(bottomTabs)
      : usableNavigation(sideNav) && (!bottomTabs || !visible(bottomTabs)));
    resolve({
      viewport: window.innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      fontIssues,
      controlIssues,
      inputIssues,
      supplementalIssues,
      motionIssues,
      glassCandidates,
      declaredScreenRendered,
      responsiveNavigationPresent
    });
  })))`
}

function runtimeObservation(normal, reduced, screen, width, runtimeMarker, extra = {}) {
  return {
    screen,
    width,
    requested_viewport_active: Math.abs(normal.viewport - width) <= 1,
    no_horizontal_overflow: normal.scrollWidth <= normal.clientWidth + 1,
    font_issues: normal.fontIssues,
    control_size_issues: normal.controlIssues,
    input_boundary_issues: normal.inputIssues,
    supplemental_copy_issues: normal.supplementalIssues,
    reduced_motion_issues: reduced.motionIssues,
    liquid_glass_material_present: normal.glassCandidates.length > 0 && normal.glassCandidates.every((item) => item.qualifies),
    glass_candidates: normal.glassCandidates,
    declared_screen_is_rendered: normal.declaredScreenRendered,
    responsive_navigation_present: normal.responsiveNavigationPresent,
    runtime_marker: runtimeMarker,
    ...extra
  }
}

function keyDefinition(key) {
  const definitions = {
    Enter: { key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 },
    ' ': { key: ' ', code: 'Space', text: ' ', windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32 },
    Space: { key: ' ', code: 'Space', text: ' ', windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32 },
    Tab: { key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 },
    ArrowRight: { key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39, nativeVirtualKeyCode: 39 },
    ArrowLeft: { key: 'ArrowLeft', code: 'ArrowLeft', windowsVirtualKeyCode: 37, nativeVirtualKeyCode: 37 }
  }
  return definitions[key] || { key, code: key, text: key.length === 1 ? key : undefined }
}

async function navigate(client, url) {
  const loaded = client.waitFor('Page.loadEventFired')
  await client.send('Page.navigate', { url })
  await loaded
  await evaluate(client, 'new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
}

async function runStep(client, step) {
  if (!step || typeof step !== 'object') throw new Error('step must be an object')
  if (step.action === 'click') {
    const selector = JSON.stringify(step.selector)
    const rect = await evaluate(client, `(() => { const node = document.querySelector(${selector}); if (!node) throw new Error('selector not found: ' + ${selector}); node.scrollIntoView({ block: 'center', inline: 'center' }); const rect = node.getBoundingClientRect(); return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }; })()`)
    await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rect.x, y: rect.y })
    await client.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
    await client.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
    await delay(30)
    return { kind: 'action', action: 'click', selector: step.selector, input_mode: 'pointer', passed: true }
  }
  if (step.action === 'focus') {
    const selector = JSON.stringify(step.selector)
    const focused = await evaluate(client, `(() => { const node = document.querySelector(${selector}); if (!node) return false; node.focus(); return document.activeElement === node; })()`)
    if (!focused) throw new Error(`could not focus: ${step.selector}`)
    return { kind: 'action', action: 'focus', selector: step.selector, input_mode: 'keyboard', passed: true }
  }
  if (step.action === 'key') {
    const definition = keyDefinition(step.key)
    await client.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', ...definition })
    if (definition.text) await client.send('Input.dispatchKeyEvent', { type: 'char', ...definition })
    await client.send('Input.dispatchKeyEvent', { type: 'keyUp', ...definition, text: undefined })
    await delay(30)
    return { kind: 'action', action: 'key', key: step.key, input_mode: 'keyboard', passed: true }
  }
  if (step.action === 'wait') {
    const milliseconds = Math.min(Math.max(Number(step.ms) || 0, 0), 2000)
    await delay(milliseconds)
    return { kind: 'action', action: 'wait', ms: milliseconds, passed: true }
  }
  if (step.assert) {
    const payload = JSON.stringify(step)
    const actual = await evaluate(client, `(() => {
      const step = ${payload};
      const node = document.querySelector(step.selector);
      if (!node) return { passed: false, actual: 'selector-not-found' };
      if (step.assert === 'text') { const actual = node.textContent.replace(/\\s+/g, ' ').trim(); return { passed: actual === step.equals, actual }; }
      if (step.assert === 'attribute') { const actual = node.getAttribute(step.name); return { passed: actual === step.equals, actual }; }
      if (step.assert === 'value') { const actual = node.value; return { passed: actual === step.equals, actual }; }
      if (step.assert === 'visible') { const style = getComputedStyle(node); const rect = node.getBoundingClientRect(); const actual = style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0; return { passed: actual === Boolean(step.equals), actual }; }
      return { passed: false, actual: 'unknown-assertion' };
    })()`)
    return { kind: 'assertion', assert: step.assert, selector: step.selector, expected: step.equals, ...actual }
  }
  throw new Error(`unknown scenario step: ${JSON.stringify(step)}`)
}

async function writeJson(path, value) {
  await mkdir(dirname(path), { recursive: true })
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`)
}

async function main() {
  const options = parseArgs(process.argv.slice(2))
  const { profile, digest } = await loadCanonicalSources()
  if (isAbsolute(options.scenarios)) throw new Error('--scenarios must be a relative path inside app-root')
  const scenarioPath = resolve(options.root, options.scenarios)
  if (!isInsideRoot(options.root, scenarioPath)) throw new Error('--scenarios must stay inside app-root')
  const scenarios = JSON.parse(await readFile(scenarioPath, 'utf8'))
  const designProfile = JSON.parse(await readFile(join(options.root, profile.generated_artifacts.design_profile), 'utf8'))
  const rawScreens = Array.isArray(scenarios.screens) ? scenarios.screens : []
  const screens = rawScreens.filter((screen) => typeof screen?.name === 'string' && screen.name.length > 0 && typeof screen?.url === 'string' && screen.url.length > 0)
  const paths = Array.isArray(scenarios.dynamic_paths) ? scenarios.dynamic_paths : []
  const evidencePath = join(options.root, profile.generated_artifacts.runtime_evidence)
  const observations = []
  const pathResults = []
  const checks = Object.fromEntries(profile.v1_runtime_baseline.checks.map((name) => [name, false]))

  if (scenarios.schema_version !== 1 || screens.length === 0 || screens.length !== rawScreens.length || paths.length === 0) {
    const evidence = {
      schema_version: 1,
      generator: { id: 'jp-web-design/catalog-runtime-audit', version: 1 },
      profile_id: profile.profile_id,
      profile_digest: digest,
      scenario_file: options.scenarios,
      viewports: profile.v1_runtime_baseline.viewports,
      checks,
      observations,
      dynamic_paths: pathResults,
      status: 'FAIL'
    }
    evidence.evidence_digest = evidenceDigest(evidence)
    await writeJson(evidencePath, evidence)
    if (options.json) console.log(JSON.stringify(evidence, null, 2))
    else console.error('FAIL runtime scenarios require schema_version 1, at least one screen, and at least one dynamic path')
    return 1
  }

  const adoption = Array.isArray(designProfile.adopted_components) ? designProfile.adopted_components : []
  const screenNames = screens.map((screen) => screen.name)
  const screenUrls = screens.map((screen) => screen.url)
  const adoptionNames = adoption.map((item) => item?.screen)
  const adoptionMarkers = adoption.map((item) => item?.runtime_marker)
  const pathNames = paths.map((path) => path?.name)
  if (new Set(screenNames).size !== screenNames.length) throw new Error('scenario screen names must be unique')
  if (new Set(screenUrls).size !== screenUrls.length) throw new Error('scenario screen URLs must be unique')
  if (adoptionNames.some((value) => typeof value !== 'string' || !value) || new Set(adoptionNames).size !== adoptionNames.length) throw new Error('adopted component screen names must be present and unique')
  if (adoptionMarkers.some((value) => typeof value !== 'string' || !value) || new Set(adoptionMarkers).size !== adoptionMarkers.length) throw new Error('adopted component runtime markers must be present and unique')
  if (pathNames.some((value) => typeof value !== 'string' || !value) || new Set(pathNames).size !== pathNames.length) throw new Error('dynamic path names must be present and unique')
  const knownScreens = new Map(screens.map((screen) => [screen.name, screen]))
  const adoptedScreens = new Map(adoption.map((item) => [item.screen, item]))
  const invalidPath = paths.find((path) => !path?.name || !knownScreens.has(path.screen) || !Array.isArray(path.steps) || path.steps.length === 0)
  if (invalidPath) throw new Error(`invalid dynamic path: ${JSON.stringify(invalidPath)}`)
  for (const screen of screens) {
    const adoption = adoptedScreens.get(screen.name)
    if (!adoption || !/^[a-z0-9][a-z0-9-]*$/.test(adoption.runtime_marker ?? '')) throw new Error(`screen requires matching adopted_components runtime_marker: ${screen.name}`)
  }
  for (const path of paths) {
    const inputIndexes = path.steps.map((step, index) => ['click', 'key'].includes(step?.action) ? index : -1).filter((index) => index >= 0)
    const firstInputAction = Math.min(...inputIndexes)
    const lastInputAction = Math.max(...inputIndexes)
    const assertionKey = (step) => `${step.assert}:${step.selector}:${step.name ?? ''}`
    const before = new Map(path.steps.slice(0, firstInputAction).filter((step) => typeof step?.assert === 'string').map((step) => [assertionKey(step), step.equals]))
    const provesChange = path.steps.slice(lastInputAction + 1).filter((step) => typeof step?.assert === 'string').some((step) => before.has(assertionKey(step)) && JSON.stringify(before.get(assertionKey(step))) !== JSON.stringify(step.equals))
    if (!Number.isFinite(firstInputAction) || !provesChange) throw new Error(`dynamic path requires a precondition and a different postcondition around click/key input: ${path.name}`)
  }

  const { client, close } = await launchChrome({ purpose: 'the catalog runtime audit', tempPrefix: 'aidd-catalog-runtime-' })
  try {
    await client.send('Page.enable')
    await client.send('Runtime.enable')

    for (const screen of screens) {
      for (const width of profile.v1_runtime_baseline.viewports) {
        await client.send('Emulation.setDeviceMetricsOverride', { width, height: 1200, deviceScaleFactor: 1, mobile: false, screenWidth: width, screenHeight: 1200 })
        await client.send('Emulation.setEmulatedMedia', { media: '', features: [] })
        await navigate(client, screenUrl(options, screen))
        const runtimeMarker = adoptedScreens.get(screen.name).runtime_marker
        const normal = await evaluate(client, browserAuditExpression(profile.consumer_source_denylist, profile.visible_copy_allowlist, profile.small_text_exemptions, runtimeMarker))
        await client.send('Emulation.setEmulatedMedia', { media: '', features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
        const reduced = await evaluate(client, browserAuditExpression(profile.consumer_source_denylist, profile.visible_copy_allowlist, profile.small_text_exemptions, runtimeMarker))
        observations.push(runtimeObservation(normal, reduced, screen.name, width, runtimeMarker, { phase: 'initial' }))
      }
    }

    for (const path of paths) {
      for (const width of profile.v1_runtime_baseline.viewports) {
        await client.send('Emulation.setDeviceMetricsOverride', { width, height: 1200, deviceScaleFactor: 1, mobile: false, screenWidth: width, screenHeight: 1200 })
        await client.send('Emulation.setEmulatedMedia', { media: '', features: [] })
        await navigate(client, screenUrl(options, knownScreens.get(path.screen)))
        const steps = []
        let passed = true
        let postState
        try {
          for (const step of path.steps) {
            const result = await runStep(client, step)
            steps.push(result)
            if (result.passed !== true) passed = false
          }
          const runtimeMarker = adoptedScreens.get(path.screen).runtime_marker
          const normal = await evaluate(client, browserAuditExpression(profile.consumer_source_denylist, profile.visible_copy_allowlist, profile.small_text_exemptions, runtimeMarker))
          await client.send('Emulation.setEmulatedMedia', { media: '', features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
          const reduced = await evaluate(client, browserAuditExpression(profile.consumer_source_denylist, profile.visible_copy_allowlist, profile.small_text_exemptions, runtimeMarker))
          postState = runtimeObservation(normal, reduced, path.screen, width, runtimeMarker, { phase: 'post-interaction', dynamic_path: path.name })
        } catch (error) {
          passed = false
          steps.push({ kind: 'error', passed: false, message: error.message })
        }
        pathResults.push({ name: path.name, screen: path.screen, width, passed, input_modes: [...new Set(steps.map((step) => step.input_mode).filter(Boolean))], steps, post_state_observation: postState ?? null })
      }
    }
  } finally {
    await close()
  }

  const postStateObservations = pathResults.map((path) => path.post_state_observation).filter(Boolean)
  const completePostStateCoverage = postStateObservations.length === paths.length * profile.v1_runtime_baseline.viewports.length
  const auditedStates = [...observations, ...postStateObservations]
  checks.no_horizontal_overflow = completePostStateCoverage && auditedStates.every((item) => item.requested_viewport_active && item.no_horizontal_overflow)
  checks.body_and_controls_at_least_16px = completePostStateCoverage && auditedStates.every((item) => item.font_issues.length === 0)
  checks.controls_at_least_44px = completePostStateCoverage && auditedStates.every((item) => item.control_size_issues.length === 0)
  checks.inputs_have_visible_boundaries = completePostStateCoverage && auditedStates.every((item) => item.input_boundary_issues.length === 0)
  checks.no_persistent_supplemental_copy = completePostStateCoverage && auditedStates.every((item) => item.supplemental_copy_issues.length === 0)
  checks.reduced_motion_preserves_meaning = completePostStateCoverage && auditedStates.every((item) => item.reduced_motion_issues.length === 0)
  const inputModes = new Set(pathResults.flatMap((path) => path.input_modes))
  checks.keyboard_and_pointer_paths_work = pathResults.length > 0 && pathResults.every((path) => path.passed) && inputModes.has('keyboard') && inputModes.has('pointer')
  checks.liquid_glass_material_present = completePostStateCoverage && auditedStates.every((item) => item.liquid_glass_material_present)
  checks.declared_screen_is_rendered = completePostStateCoverage && auditedStates.every((item) => item.declared_screen_is_rendered)
  checks.responsive_navigation_present = completePostStateCoverage && auditedStates.every((item) => item.responsive_navigation_present)
  const status = Object.values(checks).every(Boolean) ? 'PASS' : 'FAIL'
  const evidence = {
    schema_version: 1,
    generator: { id: 'jp-web-design/catalog-runtime-audit', version: 1 },
    profile_id: profile.profile_id,
    profile_digest: digest,
    scenario_file: options.scenarios,
    viewports: profile.v1_runtime_baseline.viewports,
    checks,
    observations,
    dynamic_paths: pathResults,
    status
  }
  evidence.evidence_digest = evidenceDigest(evidence)
  await writeJson(evidencePath, evidence)
  if (options.json) console.log(JSON.stringify(evidence, null, 2))
  else console.log(`${status} ${profile.profile_id} (${observations.length} viewport checks, ${pathResults.length} dynamic paths)`)
  return status === 'PASS' ? 0 : 1
}

try {
  process.exitCode = await main()
} catch (error) {
  failCli(error, usage)
}
