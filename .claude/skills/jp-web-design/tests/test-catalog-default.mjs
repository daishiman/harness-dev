#!/usr/bin/env node

import { cp, mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { check, finish, runScript, skillRoot } from './_harness.mjs'

const script = join(skillRoot, 'scripts/catalog-default.mjs')
const fixtures = join(skillRoot, 'tests/fixtures/migrate-legacy-colors')
const root = await mkdtemp(join(tmpdir(), 'aidd-catalog-default-'))

function run(args, expected = 0) {
  const { status, json } = runScript(script, [...args, '--json'])
  check(status === expected, `${args[0]} exits ${expected}`)
  check(Boolean(json), `${args[0]} returns JSON`)
  return json
}

function runError(args, label = 'rejects an unsafe path') {
  const result = runScript(script, [...args, '--json'])
  check(result.status === 2, `${args[0]} ${label} with exit 2`)
  return result
}

function activeCss(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, '')
}

try {
  const newApp = join(root, 'new-app')
  await mkdir(join(newApp, 'src'), { recursive: true })
  await writeFile(join(newApp, 'src/index.css'), '@import "tailwindcss";\nbody { margin: 0; }\n')
  const plan = run(['plan', newApp, '--app-state=new'])
  check(plan.decision === 'apply' && plan.entry_css === 'src/index.css', 'new visual app is eligible by default')

  const applied = run(['apply', newApp, '--app-state=new'])
  check(applied.status === 'APPLIED' && applied.samples_copied === false, 'apply records no sample copy')
  const profile = JSON.parse(await readFile(join(newApp, 'docs/product/design-profile.json'), 'utf8'))
  check(profile.profile_id === 'jp-web-design/catalog-default' && profile.profile_digest.length === 64, 'profile records versioned provenance')
  const entry = await readFile(join(newApp, 'src/index.css'), 'utf8')
  check(entry.indexOf('@import "tailwindcss";') < entry.indexOf('@import url("./styles/aidd/catalog-default.css");'), 'entry CSS loads the canonical default after framework imports')
  const canonicalImport = '@import url("./styles/aidd/catalog-default.css");'
  await writeFile(join(newApp, 'src/index.css'), `${canonicalImport}\n@import "tailwindcss";\nbody { margin: 0; }\n`)
  const legacyOrder = run(['verify', newApp, '--stage=v0'], 1)
  check(legacyOrder.checks.some((item) => item.id === 'entry-css-import-order' && !item.passed), 'verify rejects a canonical import that framework imports can override')
  run(['apply', newApp, '--app-state=new'])
  const reorderedEntry = await readFile(join(newApp, 'src/index.css'), 'utf8')
  check(reorderedEntry.indexOf('@import "tailwindcss";') < reorderedEntry.indexOf(canonicalImport), 'reapply normalizes a legacy canonical import after framework imports')
  await writeFile(join(newApp, 'src/index.css'), `/* ${canonicalImport} */\n@import "tailwindcss";\nbody { margin: 0; }\n`)
  const commentImport = run(['verify', newApp, '--stage=v0'], 1)
  check(commentImport.checks.some((item) => item.id === 'entry-css-import' && !item.passed), 'verify does not count a commented canonical import')
  run(['apply', newApp, '--app-state=new'])
  const uncommentedEntry = await readFile(join(newApp, 'src/index.css'), 'utf8')
  check((activeCss(uncommentedEntry).match(/catalog-default\.css/g) || []).length === 1 && uncommentedEntry.indexOf('@import "tailwindcss";') < uncommentedEntry.lastIndexOf(canonicalImport), 'commented imports do not satisfy apply and one active canonical import is inserted in order')
  const copied = await readFile(join(newApp, 'src/styles/aidd/catalog-default.css'), 'utf8')
  check(!/練馬区|川口市|船橋市|提案メール/.test(copied), 'generated assets contain no sample UI copy')
  const scenarios = JSON.parse(await readFile(join(newApp, 'docs/product/design-runtime-scenarios.json'), 'utf8'))
  check(scenarios.schema_version === 1 && scenarios.screens.length === 0, 'apply creates an empty runtime scenario contract without guessing business flows')
  const pendingV0 = run(['verify', newApp, '--stage=v0'], 1)
  check(pendingV0.status === 'FAIL', 'v0 refuses an undeclared UI adoption')
  profile.adopted_components = [{ screen: 'home', source_files: ['src/App.tsx'], components: ['app-shell', 'button'], runtime_marker: 'home' }]
  await writeFile(join(newApp, 'docs/product/design-profile.json'), `${JSON.stringify(profile, null, 2)}\n`)

  await writeFile(join(newApp, 'src/App.tsx'), '// className="app-shell btn" must not count as adoption\nexport const App = () => null\n')
  const commentOnly = run(['verify', newApp, '--stage=v0'], 1)
  check(commentOnly.status === 'FAIL' && commentOnly.checks.some((item) => item.id === 'adoption-0-app-shell' && !item.passed), 'v0 requires exact class tokens in executable markup, not comments or substrings')

  await writeFile(join(newApp, 'src/App.tsx'), 'const example = \'<main data-aidd-screen="home" className="app-shell"><button className="btn">保存する</button></main>\'\nexport const App = () => example\n')
  const stringOnly = run(['verify', newApp, '--stage=v0'], 1)
  check(stringOnly.status === 'FAIL' && stringOnly.checks.some((item) => item.id === 'adoption-0-button' && !item.passed), 'v0 does not treat quoted complete markup as rendered component adoption')

  profile.adopted_components[0].source_files = ['src/App.html']
  await writeFile(join(newApp, 'docs/product/design-profile.json'), `${JSON.stringify(profile, null, 2)}\n`)
  await writeFile(join(newApp, 'src/App.html'), '<!-- <main data-aidd-screen="home" class="app-shell"><button class="btn">保存する</button></main> -->\n')
  const htmlCommentOnly = run(['verify', newApp, '--stage=v0'], 1)
  check(htmlCommentOnly.status === 'FAIL' && htmlCommentOnly.checks.some((item) => item.id === 'adoption-0-app-shell' && !item.passed), 'v0 does not treat HTML comments as rendered component adoption')
  await rm(join(newApp, 'src/App.html'))
  profile.adopted_components[0].source_files = ['src/App.tsx']
  await writeFile(join(newApp, 'docs/product/design-profile.json'), `${JSON.stringify(profile, null, 2)}\n`)

  await writeFile(join(root, 'outside.tsx'), '<main data-aidd-screen="home" className="app-shell"><button className="btn">保存する</button></main>\n')
  profile.adopted_components[0].source_files = ['../outside.tsx']
  await writeFile(join(newApp, 'docs/product/design-profile.json'), `${JSON.stringify(profile, null, 2)}\n`)
  const outsideSource = run(['verify', newApp, '--stage=v0'], 1)
  check(outsideSource.checks.some((item) => item.id === 'adoption-0-source-files' && !item.passed), 'v0 never reads adoption source files outside app-root')
  profile.adopted_components[0].source_files = ['src/App.tsx']
  await writeFile(join(newApp, 'docs/product/design-profile.json'), `${JSON.stringify(profile, null, 2)}\n`)
  await writeFile(join(root, 'outside.css'), 'body {}\n')
  runError(['apply', newApp, '--app-state=new', '--entry-css=../outside.css'])
  const safeEntryCss = profile.entry_css
  profile.entry_css = '../outside.css'
  await writeFile(join(newApp, 'docs/product/design-profile.json'), `${JSON.stringify(profile, null, 2)}\n`)
  const outsideProfileEntry = run(['verify', newApp, '--stage=v0'], 1)
  check(outsideProfileEntry.checks.some((item) => item.id === 'entry-css-path-inside-root' && !item.passed), 'v0 never follows an entry_css path outside app-root from a hand-written profile')
  profile.entry_css = safeEntryCss
  await writeFile(join(newApp, 'docs/product/design-profile.json'), `${JSON.stringify(profile, null, 2)}\n`)

  await writeFile(join(newApp, 'src/App.tsx'), '<main data-aidd-screen="home" className="app-shell"><button className="btn btn-primary">練馬区 一棟マンション</button></main>\n')
  const sampleCopy = run(['verify', newApp, '--stage=v0'], 1)
  check(sampleCopy.status === 'FAIL' && sampleCopy.checks.some((item) => item.id.includes('no-sample') && !item.passed), 'v0 rejects reference sample copy in consumer source')

  await writeFile(join(newApp, 'src/App.tsx'), '<main data-aidd-screen="home" className="app-shell"><button className="btn btn-primary">保存する</button></main>\n')
  await writeFile(join(newApp, 'src/Other.tsx'), 'export const Other = () => <p>田中様</p>\n')
  const undeclaredSampleCopy = run(['verify', newApp, '--stage=v0'], 1)
  check(undeclaredSampleCopy.status === 'FAIL' && undeclaredSampleCopy.checks.some((item) => item.id.startsWith('consumer-source-no-sample') && !item.passed), 'v0 scans the consumer source inventory, not only declared adoption files')
  await rm(join(newApp, 'src/Other.tsx'))
  await writeFile(join(newApp, 'src/App.tsx'), '// 田中様\nexport const App = () => <main data-aidd-screen="home" className="app-shell"><button className="btn btn-primary">保存する</button></main>\n')
  const sourceComment = run(['verify', newApp, '--stage=v0'])
  check(sourceComment.status === 'PASS', 'v0 excludes an actual source comment from visible sample-copy checks')
  await writeFile(join(newApp, 'src/App.tsx'), 'export const App = () => <>\n//田中様\n<main data-aidd-screen="home" className="app-shell"><button className="btn btn-primary">保存する</button></main>\n</>\n')
  const slashLiteral = run(['verify', newApp, '--stage=v0'], 1)
  check(slashLiteral.checks.some((item) => item.id.startsWith('consumer-source-no-sample') && !item.passed), 'v0 preserves visible JSX fragment text after // when checking sample copy')
  profile.adopted_components[0].source_files = ['src/Page.astro']
  await writeFile(join(newApp, 'docs/product/design-profile.json'), `${JSON.stringify(profile, null, 2)}\n`)
  await writeFile(join(newApp, 'src/Page.astro'), '<main data-aidd-screen="home" class="app-shell"><button class="btn btn-primary">田中様</button></main>\n')
  const astroSample = run(['verify', newApp, '--stage=v0'], 1)
  check(astroSample.checks.some((item) => item.id.startsWith('consumer-source-no-sample') && !item.passed), 'v0 scans declared Astro sources for forbidden reference sample copy')
  await rm(join(newApp, 'src/Page.astro'))
  profile.adopted_components[0].source_files = ['src/App.tsx']
  await writeFile(join(newApp, 'docs/product/design-profile.json'), `${JSON.stringify(profile, null, 2)}\n`)
  await writeFile(join(newApp, 'src/App.tsx'), '<main data-aidd-screen="home" className="app-shell"><button className="btn btn-primary">保存する</button></main>\n')
  const v0 = run(['verify', newApp, '--stage=v0'])
  check(v0.status === 'PASS', 'v0 machine baseline passes')

  const v1Fail = run(['verify', newApp, '--stage=v1'], 1)
  check(v1Fail.status === 'FAIL' && v1Fail.checks.some((item) => item.id === 'runtime-audit-executed' && !item.passed), 'v1 refuses pending or hand-written evidence and executes the browser audit itself')

  const consumerHtml = `<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="./src/index.css"><title>案件管理</title></head>
<body>
  <header class="app-header"><h1 class="app-name">案件管理</h1></header>
  <div class="app-shell" data-aidd-screen="home">
    <nav class="side-nav" aria-label="主要メニュー"><button type="button" aria-current="page">ホーム</button></nav>
    <main>
      <h2 class="page-title">案件</h2>
      <section class="card card-pad" aria-label="案件入力">
        <div class="field"><label for="email">メールアドレス</label><input id="email" type="email" value="tanto@example.jp"></div>
        <label for="consent" style="display:inline-flex;align-items:center;gap:8px;min-width:44px;min-height:44px"><input id="consent" type="checkbox">確認</label>
        <div class="chip-grid"><button id="choice" class="chip" type="button" aria-pressed="false">進行中</button></div>
        <button id="noop" class="btn btn-secondary" type="button">開く</button>
        <button id="save" class="btn btn-primary" type="button">保存する</button>
        <p id="status" role="status" hidden></p>
      </section>
    </main>
  </div>
  <nav class="bottom-tabs" aria-label="モバイルメニュー"><button type="button" aria-current="page">ホーム</button></nav>
  <script>
    const choice = document.getElementById('choice');
    const toggle = () => choice.setAttribute('aria-pressed', choice.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
    choice.addEventListener('click', toggle);
    choice.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggle(); } });
    document.getElementById('save').addEventListener('click', () => { const status = document.getElementById('status'); status.textContent = '保存しました'; status.hidden = false; });
  </script>
</body>
</html>
`
  await writeFile(join(newApp, 'index.html'), consumerHtml)
  profile.adopted_components = [{ screen: 'home', source_files: ['index.html'], components: ['app-shell', 'navigation', 'button', 'field', 'selection'], runtime_marker: 'home' }]
  await writeFile(join(newApp, 'docs/product/design-profile.json'), `${JSON.stringify(profile, null, 2)}\n`)
  const renderedSourceV0 = run(['verify', newApp, '--stage=v0'])
  check(renderedSourceV0.status === 'PASS', 'the runtime-audited screen is also the declared v0 source with a shared marker')
  profile.adopted_components.push({ screen: 'home', source_files: ['index.html'], components: ['app-shell'], runtime_marker: 'home' })
  await writeFile(join(newApp, 'docs/product/design-profile.json'), `${JSON.stringify(profile, null, 2)}\n`)
  const duplicateAdoption = run(['verify', newApp, '--stage=v0'], 1)
  check(duplicateAdoption.checks.some((item) => item.id === 'adoption-screens-valid-and-unique' && !item.passed) && duplicateAdoption.checks.some((item) => item.id === 'adoption-runtime-markers-unique' && !item.passed), 'v0 rejects duplicate screen identities and runtime markers')
  profile.adopted_components.pop()
  await writeFile(join(newApp, 'docs/product/design-profile.json'), `${JSON.stringify(profile, null, 2)}\n`)
  await writeFile(join(newApp, 'docs/product/design-runtime-scenarios.json'), `${JSON.stringify({
    schema_version: 1,
    screens: [{ name: 'home', url: 'index.html' }],
    dynamic_paths: [
      { name: 'noop-pointer', screen: 'home', steps: [{ assert: 'visible', selector: '#noop', equals: true }, { action: 'click', selector: '#noop' }, { assert: 'visible', selector: '#noop', equals: true }] },
      { name: 'static-keyboard', screen: 'home', steps: [{ assert: 'attribute', selector: '#choice', name: 'type', equals: 'button' }, { action: 'focus', selector: '#choice' }, { action: 'key', key: 'Enter' }, { assert: 'attribute', selector: '#choice', name: 'type', equals: 'button' }] }
    ]
  }, null, 2)}\n`)
  const noAssertion = run(['verify', newApp, '--stage=v1'], 1)
  check(noAssertion.status === 'FAIL' && noAssertion.checks.some((item) => item.id === 'runtime-audit-executed' && !item.passed), 'v1 rejects no-op or static assertions that prove no state change')

  await writeFile(join(newApp, 'docs/product/design-runtime-scenarios.json'), `${JSON.stringify({
    schema_version: 1,
    screens: [{ name: 'home', url: 'index.html' }],
    dynamic_paths: [
      {
        name: 'save-pointer',
        screen: 'home',
        steps: [
          { assert: 'visible', selector: '#status', equals: false },
          { action: 'click', selector: '#save' },
          { assert: 'text', selector: '#status', equals: '保存しました' },
          { assert: 'visible', selector: '#status', equals: true }
        ]
      },
      {
        name: 'choice-keyboard',
        screen: 'home',
        steps: [
          { assert: 'attribute', selector: '#choice', name: 'aria-pressed', equals: 'false' },
          { action: 'focus', selector: '#choice' },
          { action: 'key', key: 'Enter' },
          { assert: 'attribute', selector: '#choice', name: 'aria-pressed', equals: 'true' }
        ]
      }
    ]
  }, null, 2)}\n`)
  const adversarialHtml = consumerHtml
    .replace('<body>', '<body style="font-size:10px">常設の補足説明')
    .replace('  <nav class="bottom-tabs" aria-label="モバイルメニュー"><button type="button" aria-current="page">ホーム</button></nav>\n', '')
    .replace('<label for="consent" style="display:inline-flex;align-items:center;gap:8px;min-width:44px;min-height:44px"><input id="consent" type="checkbox">確認</label>', '<input id="consent" type="checkbox" style="opacity:0;width:1px;height:1px"><label for="consent">確認</label>')
    .replace('</section>', '<div class="helper-label">ここから登録できます。</div><div class="unit" style="font-size:10px">操作方法の説明</div></section>')
  await writeFile(join(newApp, 'index.html'), adversarialHtml)
  const bypasses = run(['verify', newApp, '--stage=v1'], 1)
  check(bypasses.checks.some((item) => item.id === 'runtime-body_and_controls_at_least_16px' && !item.passed), 'v1 checks body text and does not treat arbitrary .unit text as a small numeric fragment')
  check(bypasses.checks.some((item) => item.id === 'runtime-no_persistent_supplemental_copy' && !item.passed), 'v1 classifies direct body text and does not exempt helper-like class names')
  check(bypasses.checks.some((item) => item.id === 'runtime-controls_at_least_44px' && !item.passed), 'v1 rejects a visually hidden native checkbox with an undersized visible label')
  check(bypasses.checks.some((item) => item.id === 'runtime-responsive_navigation_present' && !item.passed), 'v1 rejects a sidebar screen whose mobile bottom navigation is missing')
  await writeFile(join(newApp, 'index.html'), consumerHtml)
  const lowLoadHtml = consumerHtml
    .replace('<section class="card card-pad"', '<section class=""')
    .replace('class="app-header"', 'class=""')
    .replace('class="side-nav"', 'class=""')
    .replace('class="chip"', 'class="" style="min-width:44px;min-height:44px;font-size:16px"')
    .replace('class="btn btn-secondary"', 'class="" style="min-width:44px;min-height:44px;font-size:16px"')
    .replace('class="btn btn-primary"', 'class="" style="min-width:44px;min-height:44px;font-size:16px"')
    .replace('</section>', '<span style="font-size:10px">小さすぎる本文</span><div>ここから案件を登録できます。必要事項を入力してください。</div></section>')
  await writeFile(join(newApp, 'index.html'), lowLoadHtml)
  const cognitiveAndGlassFail = run(['verify', newApp, '--stage=v1'], 1)
  check(cognitiveAndGlassFail.checks.some((item) => item.id === 'runtime-body_and_controls_at_least_16px' && !item.passed), 'v1 detects undersized visible text on any text-bearing element')
  check(cognitiveAndGlassFail.checks.some((item) => item.id === 'runtime-no_persistent_supplemental_copy' && !item.passed), 'v1 rejects unclassified persistent copy even in a generic div')
  check(cognitiveAndGlassFail.checks.some((item) => item.id === 'runtime-liquid_glass_material_present' && !item.passed), 'v1 requires an actually rendered Liquid Glass material on every screen')
  await writeFile(join(newApp, 'index.html'), consumerHtml)
  const v1 = run(['verify', newApp, '--stage=v1'])
  check(v1.status === 'PASS', 'v1 passes only after a real four-width browser and interaction audit')
  const runtime = JSON.parse(await readFile(join(newApp, 'docs/product/design-runtime-evidence.json'), 'utf8'))
  check(runtime.generator?.id === 'jp-web-design/catalog-runtime-audit' && runtime.observations.length === 4 && runtime.dynamic_paths.length === 8 && runtime.dynamic_paths.every((path) => path.passed && path.post_state_observation), 'runtime evidence contains initial and post-interaction audits across all four widths')

  const delayedCopyHtml = consumerHtml
    .replace('</section>', '<div id="late-note" hidden style="font-size:10px">ここから登録できます。</div></section>')
    .replace("status.hidden = false;", "status.hidden = false; document.getElementById('late-note').hidden = false;")
  await writeFile(join(newApp, 'index.html'), delayedCopyHtml)
  const delayedCopy = run(['verify', newApp, '--stage=v1'], 1)
  check(delayedCopy.checks.some((item) => item.id === 'runtime-body_and_controls_at_least_16px' && !item.passed), 'v1 audits text revealed after an interaction at every viewport')
  check(delayedCopy.checks.some((item) => item.id === 'runtime-no_persistent_supplemental_copy' && !item.passed), 'v1 rejects supplemental copy revealed only after an interaction')
  await writeFile(join(newApp, 'index.html'), consumerHtml)
  await writeFile(join(root, 'outside-scenarios.json'), `${JSON.stringify({ schema_version: 1, screens: [{ name: 'home', url: 'index.html' }], dynamic_paths: [] })}\n`)
  const outsideScenarios = run(['verify', newApp, '--stage=v1', '--scenarios=../outside-scenarios.json'], 1)
  check(outsideScenarios.checks.some((item) => item.id === 'runtime-audit-executed' && !item.passed), 'v1 never reads scenario files outside app-root')

  const duplicateScreenScenarios = JSON.parse(await readFile(join(newApp, 'docs/product/design-runtime-scenarios.json'), 'utf8'))
  duplicateScreenScenarios.screens.push({ name: 'home', url: 'index-copy.html' })
  await writeFile(join(newApp, 'docs/product/duplicate-screen-scenarios.json'), `${JSON.stringify(duplicateScreenScenarios, null, 2)}\n`)
  const duplicateScreens = run(['verify', newApp, '--stage=v1', '--scenarios=docs/product/duplicate-screen-scenarios.json'], 1)
  check(duplicateScreens.checks.some((item) => item.id === 'runtime-audit-executed' && !item.passed), 'v1 rejects duplicate scenario screen names before coverage is counted')

  const externalOriginScenarios = JSON.parse(await readFile(join(newApp, 'docs/product/design-runtime-scenarios.json'), 'utf8'))
  externalOriginScenarios.screens[0].url = 'https://example.com/'
  await writeFile(join(newApp, 'docs/product/external-origin-scenarios.json'), `${JSON.stringify(externalOriginScenarios, null, 2)}\n`)
  const externalOrigin = run(['verify', newApp, '--stage=v1', '--base-url=http://127.0.0.1:9', '--scenarios=docs/product/external-origin-scenarios.json'], 1)
  check(externalOrigin.checks.some((item) => item.id === 'runtime-audit-executed' && !item.passed), 'v1 rejects absolute and cross-origin screen URLs before navigation')

  await writeFile(join(newApp, 'src/styles/aidd/catalog-default.css'), `${copied}\n.drift { color: red; }\n`)
  const drift = run(['verify', newApp, '--stage=v0'], 1)
  check(drift.status === 'FAIL' && drift.checks.some((item) => item.id === 'component-asset' && !item.passed), 'verify detects copied asset drift')

  const existing = join(root, 'existing-app')
  await mkdir(join(existing, 'src'), { recursive: true })
  await writeFile(join(existing, 'src/index.css'), 'body {}\n')
  const refused = run(['apply', existing, '--app-state=existing', '--eligibility=unknown'], 1)
  check(refused.status === 'REFUSED' && refused.eligibility_basis?.basis === 'explicit', 'an explicit --eligibility=unknown keeps an existing app report-only')
  const adoptedExisting = run(['apply', existing, '--app-state=existing', '--eligibility=eligible'])
  check(adoptedExisting.status === 'APPLIED', 'an explicitly eligible existing app can adopt the default when no managed drift exists')
  const existingCanonical = await readFile(join(existing, 'src/styles/aidd/catalog-default.css'), 'utf8')
  const customizedExisting = `${existingCanonical}\n.user-owned-change { color: red; }\n`
  await writeFile(join(existing, 'src/styles/aidd/catalog-default.css'), customizedExisting)
  const driftPlan = run(['plan', existing, '--app-state=existing', '--eligibility=eligible'])
  check(driftPlan.decision === 'blocked' && driftPlan.drift.some((item) => item.reason === 'managed-asset-drift'), 'plan reports exact managed drift before an existing-app upgrade')
  const driftRefused = run(['apply', existing, '--app-state=existing', '--eligibility=eligible'], 1)
  check(driftRefused.status === 'REFUSED' && await readFile(join(existing, 'src/styles/aidd/catalog-default.css'), 'utf8') === customizedExisting, 'existing managed CSS is preserved without reviewed-upgrade evidence')
  const reviewedUpgrade = run(['apply', existing, '--app-state=existing', '--eligibility=eligible', '--reviewed-upgrade'])
  check(reviewedUpgrade.status === 'APPLIED' && await readFile(join(existing, 'src/styles/aidd/catalog-default.css'), 'utf8') === existingCanonical, 'reviewed-upgrade explicitly replaces reported managed drift')
  const alternate = run(['apply', existing, '--app-state=new', '--mode=external-brand'], 1)
  check(alternate.status === 'REFUSED', 'alternate brand is never overwritten by default')

  // --eligibility 未指定の既存アプリは migrate-legacy-colors と同じ共有判定で適用資格を自動算出する。
  for (const [fixture, entryCss, expected] of [
    ['safe', 'input.css', { eligibility: 'eligible', theme: 'legacy-mode-a', decision: 'apply' }],
    ['t2-approved-external', 'src/input.css', { eligibility: 'unknown', theme: 'external-brand', decision: 'report-only' }],
    ['pop-gate', 'input.css', { eligibility: 'unknown', theme: 'undetermined', decision: 'report-only' }]
  ]) {
    const app = join(root, `auto-${fixture}`)
    await cp(join(fixtures, fixture), app, { recursive: true })
    const auto = run(['plan', app, '--app-state=existing', `--entry-css=${entryCss}`])
    check(auto.eligibility === expected.eligibility && auto.decision === expected.decision && auto.eligibility_basis?.basis === 'auto' && auto.eligibility_basis?.source_theme === expected.theme && Array.isArray(auto.eligibility_basis?.evidence),
      `plan auto-detects ${fixture} as ${expected.decision} (${expected.theme}) with the shared eligibility judgment`)
  }
  const overridden = run(['plan', join(root, 'auto-t2-approved-external'), '--app-state=existing', '--entry-css=src/input.css', '--eligibility=eligible'])
  check(overridden.decision === 'apply' && overridden.eligibility_basis?.basis === 'explicit', 'an explicit --eligibility overrides the automatic judgment')
  const newBasis = run(['plan', newApp, '--app-state=new'])
  check(newBasis.eligibility_basis?.basis === 'new-app' && newBasis.eligibility === 'unknown', 'new apps keep the previous eligibility output and record the new-app basis')
  // apply の冪等性を入口CSSの byte 一致で固定する。入口が @import とコメントだけで
  // 終わる形 (Tailwind v4 の既定エントリなど) は挿入位置の計算が末尾の空要素を
  // 消費しやすく、再実行のたびに空行が 1 行ずつ積み増す回帰を起こす。verify は
  // @import の個数と順序しか見ないため、この回帰は byte 比較でしか捕まらない。
  for (const [label, entryBody] of [
    ['import only', '@import "tailwindcss";\n'],
    ['import then trailing blank line', '@import "tailwindcss";\n\n'],
    ['comment then import', '/* design entry */\n@import "tailwindcss";\n'],
    ['comment, blank line, then rules', '/* design entry */\n\n@import "tailwindcss";\nbody { margin: 0; }\n']
  ]) {
    const app = join(root, `idempotent-${label.replace(/[^a-z]+/gi, '-')}`)
    await mkdir(join(app, 'src'), { recursive: true })
    await writeFile(join(app, 'src/index.css'), entryBody)
    const entryPath = join(app, 'src/index.css')
    run(['apply', app, '--app-state=new'])
    const first = await readFile(entryPath, 'utf8')
    run(['apply', app, '--app-state=new'])
    const second = await readFile(entryPath, 'utf8')
    check(first === second, `apply keeps the entry CSS byte-identical on re-run (${label})`)
    const canonicalCount = [...activeCss(second).matchAll(/@import\b[^;]*catalog-default\.css[^;]*;/g)].length
    check(canonicalCount === 1, `apply keeps exactly one canonical import (${label})`)
  }

  runError(['plan', existing, '--eligibility=maybe'], 'rejects an invalid eligibility value')
  const unknownFlag = runError(['plan', existing, '--eligibilty=eligible'], 'rejects an unknown option')
  check(/usage: catalog-default\.mjs/.test(unknownFlag.stderr), 'input errors print the usage line')
} finally {
  await rm(root, { recursive: true, force: true })
}

finish()
