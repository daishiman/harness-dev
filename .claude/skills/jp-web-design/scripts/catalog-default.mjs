#!/usr/bin/env node

import { spawnSync } from 'node:child_process'
import { access, mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { dirname, extname, isAbsolute, join, relative, resolve, sep } from 'node:path'
import { failCli, oneOf, parseArgs as parseCliArgs } from './lib/args.mjs'
import { projectEligibility, readProjectSources } from './lib/eligibility.mjs'
import { walkSources } from './lib/fs-walk.mjs'
import { evidenceDigest, isInsideRoot, loadCanonicalSources, sha256, skillRoot } from './lib/provenance.mjs'

const runtimeAuditPath = join(skillRoot, 'scripts/catalog-runtime-audit.mjs')
const usage = 'usage: catalog-default.mjs <plan|apply|verify> <app-root> [--app-state=new|existing] [--mode=standard|pop|external-brand] [--eligibility=eligible|unknown] [--reviewed-upgrade] [--entry-css=path] [--stage=v0|v1] [--base-url=url] [--scenarios=path] [--json]'
const entryCandidates = [
  'src/app/globals.css', 'app/globals.css', 'src/index.css', 'src/main.css',
  'src/App.css', 'src/app.css', 'styles/globals.css', 'styles.css'
]

function withoutComments(source) {
  const chars = source.split('')
  const output = source.split('')
  const voidTags = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'])
  let quote = null
  let markupDepth = 0
  let expressionDepth = 0
  const blank = (start, end) => {
    for (let index = start; index < end; index += 1) if (output[index] !== '\n' && output[index] !== '\r') output[index] = ' '
  }
  for (let index = 0; index < chars.length; index += 1) {
    const char = chars[index]
    const next = chars[index + 1]
    if (quote) {
      if (char === '\\') index += 1
      else if (char === quote) quote = null
      continue
    }
    if (source.startsWith('<!--', index)) {
      const end = source.indexOf('-->', index + 4)
      const stop = end < 0 ? source.length : end + 3
      blank(index, stop)
      index = stop - 1
      continue
    }
    if (char === '/' && next === '*' && (markupDepth === 0 || expressionDepth > 0)) {
      const end = source.indexOf('*/', index + 2)
      const stop = end < 0 ? source.length : end + 2
      blank(index, stop)
      index = stop - 1
      continue
    }
    if (char === '/' && next === '/' && (markupDepth === 0 || expressionDepth > 0)) {
      let end = source.indexOf('\n', index + 2)
      if (end < 0) end = source.length
      blank(index, end)
      index = end - 1
      continue
    }
    if (char === "'" || char === '"' || char === '`') {
      quote = char
      continue
    }
    if (markupDepth > 0 && char === '{') { expressionDepth += 1; continue }
    if (markupDepth > 0 && char === '}' && expressionDepth > 0) { expressionDepth -= 1; continue }
    if (expressionDepth === 0 && source.startsWith('<>', index)) { markupDepth += 1; index += 1; continue }
    if (expressionDepth === 0 && source.startsWith('</>', index)) { markupDepth = Math.max(0, markupDepth - 1); index += 2; continue }
    if (expressionDepth === 0 && char === '<' && /^<\/?[A-Za-z][A-Za-z0-9:_-]*/.test(source.slice(index))) {
      const tag = source.slice(index).match(/^<\/?([A-Za-z][A-Za-z0-9:_-]*)/)?.[1]?.toLowerCase()
      let end = index + 1
      let tagQuote = null
      for (; end < chars.length; end += 1) {
        const tagChar = chars[end]
        if (tagQuote) {
          if (tagChar === '\\') end += 1
          else if (tagChar === tagQuote) tagQuote = null
        } else if (tagChar === "'" || tagChar === '"' || tagChar === '`') tagQuote = tagChar
        else if (tagChar === '>') break
      }
      const body = source.slice(index, Math.min(end + 1, source.length))
      if (/^<\//.test(body)) markupDepth = Math.max(0, markupDepth - 1)
      else if (!/\/\s*>$/.test(body) && !voidTags.has(tag)) markupDepth += 1
      index = end
    }
  }
  return output.join('')
}

function executableMask(source) {
  const chars = source.split('')
  const masked = source.split('')
  let state = 'code'
  for (let index = 0; index < chars.length; index += 1) {
    const char = chars[index]
    const next = chars[index + 1]
    if (state === 'code') {
      if (source.startsWith('<!--', index)) { for (let offset = 0; offset < 4; offset += 1) masked[index + offset] = ' '; state = 'html-comment'; index += 3 }
      else if (char === '/' && next === '/') { masked[index] = masked[index + 1] = ' '; state = 'line-comment'; index += 1 }
      else if (char === '/' && next === '*') { masked[index] = masked[index + 1] = ' '; state = 'block-comment'; index += 1 }
      else if (char === "'") { masked[index] = ' '; state = 'single-quote' }
      else if (char === '"') { masked[index] = ' '; state = 'double-quote' }
      else if (char === '`') { masked[index] = ' '; state = 'template' }
      continue
    }
    if (char !== '\n') masked[index] = ' '
    if (state === 'line-comment' && char === '\n') state = 'code'
    else if (state === 'html-comment' && source.startsWith('-->', index)) { masked[index] = masked[index + 1] = masked[index + 2] = ' '; state = 'code'; index += 2 }
    else if (state === 'block-comment' && char === '*' && next === '/') { masked[index + 1] = ' '; state = 'code'; index += 1 }
    else if (['single-quote', 'double-quote', 'template'].includes(state) && char === '\\') {
      if (index + 1 < chars.length) { if (chars[index + 1] !== '\n') masked[index + 1] = ' '; index += 1 }
    } else if (state === 'single-quote' && char === "'") state = 'code'
    else if (state === 'double-quote' && char === '"') state = 'code'
    else if (state === 'template' && char === '`') state = 'code'
  }
  return masked.join('')
}

function executableTags(source) {
  const mask = executableMask(source)
  const tags = []
  for (let start = 0; start < mask.length; start += 1) {
    if (mask[start] !== '<' || !/[A-Za-z/]/.test(mask[start + 1] ?? '')) continue
    let quote = null
    let braces = 0
    let end = start + 1
    for (; end < source.length; end += 1) {
      const char = source[end]
      if (quote) {
        if (char === '\\') end += 1
        else if (char === quote) quote = null
        continue
      }
      if (char === '"' || char === "'" || char === '`') quote = char
      else if (char === '{') braces += 1
      else if (char === '}') braces = Math.max(0, braces - 1)
      else if (char === '>' && braces === 0) break
    }
    if (end >= source.length) break
    tags.push(source.slice(start, end + 1))
    start = end
  }
  return tags
}

function classTokens(source) {
  const tokens = new Set()
  for (const tag of executableTags(source)) {
    for (const match of tag.matchAll(/\bclass(?:Name)?\s*=\s*["'`]([^"'`]+)["'`]/g)) {
      for (const token of match[1].split(/\s+/).filter(Boolean)) tokens.add(token)
    }
  }
  return tokens
}

function attributeValues(source, attribute) {
  const values = new Set()
  const pattern = new RegExp("\\b" + attribute + "\\s*=\\s*[\"'`]([^\"'`]+)[\"'`]", 'g')
  for (const tag of executableTags(source)) for (const match of tag.matchAll(pattern)) values.add(match[1])
  return values
}

async function exists(path) {
  try { await access(path); return true } catch { return false }
}

// 配置先では部品CSSと色CSSが同じフォルダに並ぶため、import だけ書き換える。
async function readSources() {
  const { profile, token, component, digest } = await loadCanonicalSources()
  const appComponent = component.replace('@import url("../standard/standard-color-system.css");', '@import url("./standard-color-system.css");')
  const assets = [
    { id: 'token-asset', path: profile.generated_artifacts.token_css, body: token },
    { id: 'component-asset', path: profile.generated_artifacts.component_css, body: appComponent }
  ].map((asset) => ({ ...asset, sha256: sha256(asset.body) }))
  return { profile, token, component: appComponent, digest, assets }
}

// apply の生成宣言と plan/verify の期待値は同じ契約から作る。採用部品・例外は利用側の記録なので含めない。
function profileContract(sources) {
  return [
    ['schema_version', 'profile-schema-version', 1],
    ['profile_id', 'profile-id', sources.profile.profile_id],
    ['profile_version', 'profile-version', sources.profile.profile_version],
    ['profile_digest', 'profile-digest', sources.digest],
    ['mode', 'profile-mode', sources.profile.default_mode],
    ['source_catalog', 'profile-source-catalog', sources.profile.source.catalog],
    ['assets', 'profile-assets', sources.assets.map(({ path, sha256 }) => ({ path, sha256 }))],
    ['samples_copied', 'sample-copy-disabled', false]
  ]
}

function profileMetadataChecks(adopted, sources) {
  const checks = profileContract(sources).map(([key, id, expected]) => ({
    key, id, passed: JSON.stringify(adopted?.[key]) === JSON.stringify(expected), evidence: adopted?.[key] ?? 'missing'
  }))
  checks.push(
    { key: 'app_state', id: 'profile-app-state', passed: ['new', 'existing'].includes(adopted?.app_state), evidence: adopted?.app_state ?? 'missing' },
    { key: 'eligibility', id: 'profile-eligibility', passed: adopted?.eligibility === (adopted?.app_state === 'new' ? 'new-app' : 'eligible'), evidence: adopted?.eligibility ?? 'missing' },
    { key: 'reviewed_upgrade', id: 'profile-reviewed-upgrade', passed: typeof adopted?.reviewed_upgrade === 'boolean', evidence: adopted?.reviewed_upgrade ?? 'missing' }
  )
  return checks
}

function parseArgs(argv) {
  const { args: [command, rootArg], options } = parseCliArgs(argv, {
    positionals: 2,
    booleans: { '--json': 'json', '--reviewed-upgrade': 'reviewedUpgrade' },
    values: { '--app-state': 'appState', '--mode': 'mode', '--eligibility': 'eligibility', '--entry-css': 'entryCss', '--stage': 'stage', '--base-url': 'baseUrl', '--scenarios': 'scenarios' }
  })
  oneOf('command', command, ['plan', 'apply', 'verify'])
  const parsed = { appState: 'existing', mode: 'standard', reviewedUpgrade: false, stage: 'v0', json: false, ...options, command, root: resolve(rootArg) }
  oneOf('--app-state', parsed.appState, ['new', 'existing'])
  oneOf('--mode', parsed.mode, ['standard', 'pop', 'external-brand'])
  if (parsed.eligibility !== undefined) oneOf('--eligibility', parsed.eligibility, ['eligible', 'unknown'])
  oneOf('--stage', parsed.stage, ['v0', 'v1'])
  return parsed
}

// 既存アプリの適用資格。--eligibility の明示が最優先、無ければ migrate-legacy-colors と同じ共有判定で自動算出する。
async function resolveEligibility(options) {
  if (options.appState === 'new') return { ...options, eligibility: options.eligibility ?? 'unknown', eligibilityBasis: { basis: 'new-app' } }
  if (options.eligibility !== undefined) return { ...options, eligibilityBasis: { basis: 'explicit', value: options.eligibility } }
  const judged = projectEligibility(await readProjectSources(options.root))
  return { ...options, eligibility: judged.status === 'eligible' ? 'eligible' : 'unknown', eligibilityBasis: { basis: 'auto', ...judged } }
}

async function detectEntry(options) {
  if (options.entryCss) {
    if (isAbsolute(options.entryCss)) throw new Error('--entry-css must be a relative path inside app-root')
    const absolute = resolve(options.root, options.entryCss)
    if (!isInsideRoot(options.root, absolute)) throw new Error('--entry-css must stay inside app-root')
    return (await exists(absolute)) ? absolute : null
  }
  for (const candidate of entryCandidates) {
    const absolute = join(options.root, candidate)
    if (await exists(absolute)) return absolute
  }
  return null
}

async function consumerSourceFiles(root, adoption) {
  const extensions = new Set(['.html', '.htm', '.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx', '.vue', '.svelte', '.astro', '.md', '.mdx', '.php', '.erb', '.ejs', '.njk', '.twig', '.liquid', '.razor', '.css', '.scss', '.sass', '.less', '.json'])
  // 見本文言の検査は利用側の実装だけが対象。docs・テストは見本文言を正当に含みうるので読まない。
  const skipDirectories = ['docs', 'test', 'tests', '__tests__', 'spec', 'specs', 'eval-log']
  const candidateRoots = new Set(['src', 'app', 'pages', 'components', 'public'])
  const found = new Set()
  for (const item of adoption) {
    for (const file of Array.isArray(item?.source_files) ? item.source_files : []) {
      const declared = resolve(root, file)
      if (isInsideRoot(root, declared) && await exists(declared)) found.add(declared)
      const [first] = file.split(/[\\/]/)
      if (first && first !== '..' && !skipDirectories.includes(first)) candidateRoots.add(first)
    }
  }
  // 検査用ファイルだけを狭く除外する。declared source_files は上で先に追加済みなので必ず照合する。
  const accept = (_path, name) => extensions.has(extname(name).toLowerCase())
    && !/\.(?:test|spec)\.[^.]+$/i.test(name)
    && !/^(?:__check_nav_deploy\d*|__prod_check)\.mjs$/.test(name)
  for (const candidate of candidateRoots) {
    for await (const file of walkSources(join(root, candidate), { accept, skipDirectories, ignoreErrors: true })) found.add(file)
  }
  let rootEntries = []
  try { rootEntries = await readdir(root, { withFileTypes: true }) } catch {}
  for (const entry of rootEntries) if (entry.isFile() && accept(join(root, entry.name), entry.name)) found.add(join(root, entry.name))
  return [...found].sort()
}

function applyEligible(options) {
  if (options.mode !== 'standard') return false
  return options.appState === 'new' || options.eligibility === 'eligible'
}

async function existingManagedDrift(options, sources) {
  if (options.appState !== 'existing') return []
  const targets = sources.profile.generated_artifacts
  const drift = []
  for (const { path, body: expected } of sources.assets) {
    const target = join(options.root, path)
    if (!(await exists(target))) continue
    const actual = await readFile(target, 'utf8')
    if (actual !== expected) drift.push({ path, reason: 'managed-asset-drift', expected_sha256: sha256(expected), actual_sha256: sha256(actual) })
  }
  const designProfilePath = join(options.root, targets.design_profile)
  if (await exists(designProfilePath)) {
    try {
      const current = JSON.parse(await readFile(designProfilePath, 'utf8'))
      const mismatched = profileMetadataChecks(current, sources).filter((item) => !item.passed)
      if (mismatched.length > 0) {
        drift.push({ path: targets.design_profile, reason: 'profile-provenance-drift', mismatched_fields: mismatched.map((item) => item.key), expected_profile_id: sources.profile.profile_id, actual_profile_id: current.profile_id ?? null, expected_digest: sources.digest, actual_digest: current.profile_digest ?? null })
      }
    } catch {
      drift.push({ path: targets.design_profile, reason: 'invalid-design-profile' })
    }
  }
  return drift
}

async function plan(options, sources) {
  const entry = await detectEntry(options)
  const eligible = applyEligible(options)
  const drift = await existingManagedDrift(options, sources)
  const driftBlocksApply = drift.length > 0 && !options.reviewedUpgrade
  const writesOnApply = Object.entries(sources.profile.generated_artifacts)
    .filter(([name]) => name !== 'conformance_report')
    .map(([, path]) => path)
  return {
    schema_version: 1,
    action: 'plan',
    profile_id: sources.profile.profile_id,
    profile_version: sources.profile.profile_version,
    profile_digest: sources.digest,
    app_state: options.appState,
    mode: options.mode,
    eligibility: options.eligibility,
    eligibility_basis: options.eligibilityBasis,
    decision: eligible ? (entry && !driftBlocksApply ? 'apply' : 'blocked') : 'report-only',
    entry_css: entry ? relative(options.root, entry).split(sep).join('/') : null,
    blockers: [
      ...(options.mode !== 'standard' ? ['alternate-design-mode'] : []),
      ...(options.appState === 'existing' && options.eligibility !== 'eligible' ? ['existing-app-eligibility-unconfirmed'] : []),
      ...(driftBlocksApply ? ['existing-managed-artifact-drift'] : []),
      ...(!entry ? ['css-entry-not-found'] : [])
    ],
    drift,
    reviewed_upgrade: options.reviewedUpgrade,
    writes_on_apply: writesOnApply,
    samples_copied: false
  }
}

function importPath(fromEntry, targetCss) {
  let path = relative(dirname(fromEntry), targetCss).split(sep).join('/')
  if (!path.startsWith('.')) path = `./${path}`
  return path
}

// 有効な先頭at-ruleの末尾へ挿入する。改行の消費は1件だけにし、applyのbyte冪等性を保つ。
function addImportAfterExistingImports(body, cssImport) {
  const rules = cssTopLevelRules(body)
  let insertAt = rules[0]?.index ?? body.length
  for (const rule of rules) {
    if (!importPreambleRule(rule)) break
    insertAt = rule.end
  }
  if (body.startsWith('\r\n', insertAt)) insertAt += 2
  else if (body[insertAt] === '\n') insertAt += 1
  const before = body.slice(0, insertAt)
  return `${before}${before && !before.endsWith('\n') ? '\n' : ''}${cssImport}\n${body.slice(insertAt)}`
}

function cssWithoutComments(body) {
  // URLや文字列内のコメント風文字はCSSコメントではない。indexは元ソースと一致させる。
  const output = body.split('')
  let quote = null
  for (let index = 0; index < body.length; index += 1) {
    if (quote) {
      if (body[index] === '\\') index += 1
      else if (body[index] === quote) quote = null
    } else if (body[index] === '"' || body[index] === "'") quote = body[index]
    else if (body.startsWith('/*', index)) {
      const closing = body.indexOf('*/', index + 2)
      const end = closing < 0 ? body.length : closing + 2
      for (let cursor = index; cursor < end; cursor += 1) if (output[cursor] !== '\n' && output[cursor] !== '\r') output[cursor] = ' '
      index = end - 1
    }
  }
  return output.join('')
}

function cssTopLevelRules(body) {
  const clean = cssWithoutComments(body)
  const rules = []
  let start = null
  let quote = null
  let parentheses = 0
  let braces = 0
  let block = false
  for (let index = 0; index < clean.length; index += 1) {
    const char = clean[index]
    if (start === null) {
      if (/\s/.test(char)) continue
      start = index
    }
    if (quote) {
      if (char === '\\') index += 1
      else if (char === quote) quote = null
      continue
    }
    if (char === '"' || char === "'") { quote = char; continue }
    if (char === '(') parentheses += 1
    else if (char === ')') parentheses = Math.max(0, parentheses - 1)
    if (parentheses > 0) continue
    if (char === '{') { braces += 1; block = true }
    else if (char === '}') braces = Math.max(0, braces - 1)
    if (braces === 0 && (char === ';' || char === '}')) {
      const text = clean.slice(start, index + 1)
      rules.push({ index: start, end: index + 1, text, name: text.match(/^@([\w-]+)/)?.[1]?.toLowerCase() ?? '', block })
      start = null
      block = false
    }
  }
  return rules
}

function importPreambleRule(rule) {
  return !rule.block && ['charset', 'import', 'layer'].includes(rule.name)
}

function importStatements(body) {
  let preamble = true
  const imports = []
  for (const rule of cssTopLevelRules(body)) {
    if (rule.name === 'import' && !rule.block) imports.push({ ...rule, ...parseImport(rule.text), validPosition: preamble })
    if (!importPreambleRule(rule)) preamble = false
  }
  return imports
}

function parseImport(cssImport) {
  const match = cssImport.match(/^@import\s+(?:"([^"\\]*)"|'([^'\\]*)'|url\(\s*(?:"([^"\\]*)"|'([^'\\]*)'|([^'"\s()\\]+))\s*\))\s*([\s\S]*?);\s*$/i)
  return { target: match ? match.slice(1, 6).find((value) => value !== undefined) ?? '' : '', screenUnconditional: Boolean(match && /^(?:all|screen)?$/i.test(match[6].trim())) }
}

function canonicalImportState(body, cssImport) {
  const { target } = parseImport(cssImport)
  const statements = importStatements(body)
  const canonical = statements.filter((statement) => target && statement.target === target)
  const active = canonical.filter((statement) => statement.validPosition && statement.screenUnconditional)
  return {
    activeCount: active.length,
    orderedAfterImports: canonical.length === 1 && active.length === 1 && statements.filter((statement) => statement.validPosition).every((statement) => statement === canonical[0] || statement.index < canonical[0].index)
  }
}

// 単独行のimportは改行ごと除去する。文だけ削ると再挿入時に空行が増えるため、byte冪等性も保つ。
function dropRange(body, start, end) {
  const lineStart = body.lastIndexOf('\n', start - 1) + 1
  const newline = body.indexOf('\n', end)
  const lineEnd = newline === -1 ? body.length : newline
  const aloneOnLine = !body.slice(lineStart, start).trim() && !body.slice(end, lineEnd).trim()
  if (!aloneOnLine) return body.slice(0, start) + body.slice(end)
  return body.slice(0, lineStart) + body.slice(newline === -1 ? lineEnd : lineEnd + 1)
}

function normalizeCanonicalImport(body, cssImport) {
  const { target } = parseImport(cssImport)
  const ranges = importStatements(body)
    .filter((statement) => target && statement.target === target)
    .map((statement) => [statement.index, statement.end])
    .sort((a, b) => b[0] - a[0])
  let normalized = body
  for (const [start, end] of ranges) normalized = dropRange(normalized, start, end)
  return addImportAfterExistingImports(normalized, cssImport)
}

async function writeJson(path, value) {
  await mkdir(dirname(path), { recursive: true })
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`)
}

async function apply(options, sources) {
  const proposed = await plan(options, sources)
  if (proposed.decision !== 'apply') return { ...proposed, action: 'apply', status: 'REFUSED', changed: [] }
  const entry = await detectEntry(options)
  if (!entry) return { ...proposed, action: 'apply', status: 'REFUSED', changed: [] }

  const targets = sources.profile.generated_artifacts
  const componentTarget = join(options.root, targets.component_css)
  for (const asset of sources.assets) {
    const target = join(options.root, asset.path)
    await mkdir(dirname(target), { recursive: true })
    await writeFile(target, asset.body)
  }

  const cssImport = `@import url("${importPath(entry, componentTarget)}");`
  const entryBody = await readFile(entry, 'utf8')
  const normalizedEntry = normalizeCanonicalImport(entryBody, cssImport)
  if (normalizedEntry !== entryBody) await writeFile(entry, normalizedEntry)

  let previous = {}
  try { previous = JSON.parse(await readFile(join(options.root, targets.design_profile), 'utf8')) } catch {}
  const designProfile = {
    ...Object.fromEntries(profileContract(sources).map(([key, , value]) => [key, value])),
    app_state: options.appState,
    eligibility: options.appState === 'new' ? 'new-app' : options.eligibility,
    reviewed_upgrade: options.reviewedUpgrade,
    entry_css: relative(options.root, entry).split(sep).join('/'),
    adopted_components: Array.isArray(previous.adopted_components) ? previous.adopted_components : [],
    exceptions: Array.isArray(previous.exceptions) ? previous.exceptions : []
  }
  await writeJson(join(options.root, targets.design_profile), designProfile)
  const scenarioPath = join(options.root, targets.runtime_scenarios)
  if (!(await exists(scenarioPath))) {
    await writeJson(scenarioPath, {
      schema_version: 1,
      screens: [],
      dynamic_paths: []
    })
  }
  const evidencePath = join(options.root, targets.runtime_evidence)
  if (!(await exists(evidencePath))) {
    await writeJson(evidencePath, {
      schema_version: 1,
      profile_id: sources.profile.profile_id,
      viewports: sources.profile.v1_runtime_baseline.viewports,
      checks: Object.fromEntries(sources.profile.v1_runtime_baseline.checks.map((name) => [name, false])),
      dynamic_paths: [],
      status: 'PENDING'
    })
  }
  return {
    ...proposed,
    action: 'apply',
    status: 'APPLIED',
    changed: [targets.token_css, targets.component_css, targets.design_profile, targets.runtime_scenarios, targets.runtime_evidence, relative(options.root, entry).split(sep).join('/')]
  }
}

async function verify(options, sources) {
  const targets = sources.profile.generated_artifacts
  const checks = []
  const check = (id, passed, evidence) => checks.push({ id, passed: Boolean(passed), evidence })
  let adopted
  try { adopted = JSON.parse(await readFile(join(options.root, targets.design_profile), 'utf8')) } catch {}
  check('profile-present', adopted, targets.design_profile)
  for (const { id, passed, evidence } of profileMetadataChecks(adopted, sources)) check(id, passed, evidence)

  const adoption = Array.isArray(adopted?.adopted_components) ? adopted.adopted_components : []
  check('component-adoption-declared', adoption.length > 0, String(adoption.length))
  const adoptionScreens = adoption.map((item) => item?.screen).filter((value) => typeof value === 'string' && value.length > 0)
  const adoptionMarkers = adoption.map((item) => item?.runtime_marker).filter((value) => typeof value === 'string' && value.length > 0)
  check('adoption-screens-valid-and-unique', adoptionScreens.length === adoption.length && new Set(adoptionScreens).size === adoption.length, adoptionScreens.join(','))
  check('adoption-runtime-markers-unique', adoptionMarkers.length === adoption.length && new Set(adoptionMarkers).size === adoption.length, adoptionMarkers.join(','))
  for (const [index, item] of adoption.entries()) {
    const files = Array.isArray(item?.source_files) ? item.source_files : []
    const components = Array.isArray(item?.components) ? item.components : []
    const runtimeMarker = typeof item?.runtime_marker === 'string' ? item.runtime_marker : ''
    const bodies = []
    let filesExist = files.length > 0
    for (const file of files) {
      const sourcePath = resolve(options.root, file)
      if (!isInsideRoot(options.root, sourcePath)) { filesExist = false; continue }
      try { bodies.push(await readFile(sourcePath, 'utf8')) } catch { filesExist = false }
    }
    check(`adoption-${index}-source-files`, filesExist, files.join(','))
    check(`adoption-${index}-components`, components.length > 0, components.join(','))
    const joined = bodies.join('\n')
    const tokens = classTokens(joined)
    check(`adoption-${index}-screen`, /^[a-z0-9][a-z0-9-]*$/.test(item?.screen ?? ''), item?.screen ?? 'missing')
    const validRuntimeMarker = /^[a-z0-9][a-z0-9-]*$/.test(runtimeMarker)
    check(`adoption-${index}-runtime-marker`, validRuntimeMarker && attributeValues(joined, 'data-aidd-screen').has(runtimeMarker), runtimeMarker || 'missing')
    for (const component of components) {
      const marker = sources.profile.component_markers[component]
      check(`adoption-${index}-${component}`, Boolean(marker && tokens.has(marker)), marker ?? 'unknown-component')
    }
  }
  const sourceInventory = await consumerSourceFiles(options.root, adoption)
  check('consumer-source-inventory', sourceInventory.length > 0, String(sourceInventory.length))
  for (const file of sourceInventory) {
    const source = withoutComments(await readFile(file, 'utf8'))
    const sourceName = relative(options.root, file).split(sep).join('/')
    for (const denied of sources.profile.consumer_source_denylist) {
      check(`consumer-source-no-sample-${sha256(`${sourceName}:${denied}`).slice(0, 12)}`, !source.includes(denied), `${sourceName}: ${denied}`)
    }
  }

  for (const { id, path: target, body: expected } of sources.assets) {
    let actual
    try { actual = await readFile(join(options.root, target), 'utf8') } catch {}
    check(id, actual === expected, actual ? sha256(actual) : 'missing')
  }

  const entryCss = typeof adopted?.entry_css === 'string' ? adopted.entry_css : ''
  const entry = entryCss && !isAbsolute(entryCss) ? resolve(options.root, entryCss) : null
  const entryIsSafe = Boolean(entry && isInsideRoot(options.root, entry))
  check('entry-css-path-inside-root', entryIsSafe, entryCss || 'missing')
  let entryBody = ''
  if (entryIsSafe && await exists(entry)) entryBody = await readFile(entry, 'utf8')
  const expectedImport = entryIsSafe ? `@import url("${importPath(entry, join(options.root, targets.component_css))}");` : ''
  const entryImportState = entryBody && expectedImport ? canonicalImportState(entryBody, expectedImport) : { activeCount: 0, orderedAfterImports: false }
  check('entry-css-import', entryImportState.activeCount === 1, `${adopted?.entry_css ?? 'missing'} active=${entryImportState.activeCount}`)
  check('entry-css-import-order', entryImportState.orderedAfterImports, 'canonical import must be the final active @import')
  check('light-theme-only', sources.component.includes('ライトのみ') && !sources.component.includes('prefers-color-scheme: dark'), 'canonical component CSS')

  if (options.stage === 'v1') {
    const auditArgs = [runtimeAuditPath, options.root, '--json']
    if (options.baseUrl) auditArgs.push(`--base-url=${options.baseUrl}`)
    if (options.scenarios) auditArgs.push(`--scenarios=${options.scenarios}`)
    const audit = spawnSync(process.execPath, auditArgs, { encoding: 'utf8', maxBuffer: 20 * 1024 * 1024 })
    const auditEvidence = audit.status === 0 ? 'actual Chrome audit passed' : (audit.stderr || audit.stdout || audit.error?.message || `exit ${audit.status}`).trim().slice(-1600)
    check('runtime-audit-executed', audit.status === 0, auditEvidence)
    let runtime
    try { runtime = JSON.parse(await readFile(join(options.root, targets.runtime_evidence), 'utf8')) } catch {}
    check('runtime-evidence-present', runtime, targets.runtime_evidence)
    check('runtime-generator', runtime?.generator?.id === 'jp-web-design/catalog-runtime-audit' && runtime?.generator?.version === 1, JSON.stringify(runtime?.generator ?? null))
    check('runtime-profile-digest', runtime?.profile_digest === sources.digest, runtime?.profile_digest ?? 'missing')
    check('runtime-evidence-digest', Boolean(runtime?.evidence_digest) && runtime.evidence_digest === evidenceDigest(runtime), runtime?.evidence_digest ?? 'missing')
    check('runtime-viewports', JSON.stringify(runtime?.viewports) === JSON.stringify(sources.profile.v1_runtime_baseline.viewports), JSON.stringify(runtime?.viewports ?? []))
    for (const id of sources.profile.v1_runtime_baseline.checks) check(`runtime-${id}`, runtime?.checks?.[id] === true, String(runtime?.checks?.[id] ?? 'missing'))
    check('runtime-dynamic-paths', Array.isArray(runtime?.dynamic_paths) && runtime.dynamic_paths.length > 0, String(runtime?.dynamic_paths?.length ?? 0))
    const runtimeScreens = new Set(Array.isArray(runtime?.observations) ? runtime.observations.map((item) => item?.screen).filter(Boolean) : [])
    const adoptedScreens = adoption.map((item) => item?.screen).filter(Boolean)
    check('runtime-screen-coverage', adoptedScreens.length > 0 && adoptedScreens.every((screen) => runtimeScreens.has(screen)), `${[...runtimeScreens].join(',')} covers ${adoptedScreens.join(',')}`)
    check('runtime-status', runtime?.status === 'PASS', runtime?.status ?? 'missing')
  }

  const status = checks.every((item) => item.passed) ? 'PASS' : 'FAIL'
  const report = {
    schema_version: 1,
    profile_id: sources.profile.profile_id,
    profile_version: sources.profile.profile_version,
    profile_digest: sources.digest,
    stage: options.stage,
    status,
    checks,
    exceptions: adopted?.exceptions ?? []
  }
  await writeJson(join(options.root, targets.conformance_report), report)
  return report
}

function render(result, json) {
  if (json) console.log(JSON.stringify(result, null, 2))
  else console.log(`${result.status ?? result.decision} ${result.profile_id} ${result.profile_version}`)
}

async function main() {
  try {
    const parsed = parseArgs(process.argv.slice(2))
    if (!(await exists(parsed.root))) throw new Error(`app root does not exist: ${parsed.root}`)
    const options = parsed.command === 'verify' ? parsed : await resolveEligibility(parsed)
    const sources = await readSources()
    const result = options.command === 'plan' ? await plan(options, sources) : options.command === 'apply' ? await apply(options, sources) : await verify(options, sources)
    render(result, options.json)
    if (result.status === 'FAIL' || result.status === 'REFUSED') process.exitCode = 1
  } catch (error) {
    failCli(error, usage)
  }
}

await main()
