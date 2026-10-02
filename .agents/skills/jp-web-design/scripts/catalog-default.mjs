#!/usr/bin/env node

import { spawnSync } from 'node:child_process'
import { access, copyFile, mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { dirname, extname, isAbsolute, join, relative, resolve, sep } from 'node:path'
import { failCli, oneOf, parseArgs as parseCliArgs } from './lib/args.mjs'
import { projectEligibility, readProjectSources } from './lib/eligibility.mjs'
import { walkSources } from './lib/fs-walk.mjs'
import { canonicalPaths, evidenceDigest, isInsideRoot, loadCanonicalSources, sha256, skillRoot } from './lib/provenance.mjs'

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
  return { profile, token, component: component.replace('@import url("../standard/standard-color-system.css");', '@import url("./standard-color-system.css");'), digest }
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
  const skipDirectories = ['docs', 'test', 'tests', '__tests__', 'eval-log']
  const candidateRoots = new Set(['src', 'app', 'pages', 'components', 'public'])
  const found = new Set()
  for (const item of adoption) {
    for (const file of Array.isArray(item?.source_files) ? item.source_files : []) {
      const declared = resolve(root, file)
      if (isInsideRoot(root, declared) && await exists(declared)) found.add(declared)
      const [first] = file.split(/[\\/]/)
      if (first && first !== '..') candidateRoots.add(first)
    }
  }
  const accept = (_path, name) => extensions.has(extname(name).toLowerCase())
  for (const candidate of candidateRoots) {
    for await (const file of walkSources(join(root, candidate), { accept, skipDirectories, ignoreErrors: true })) found.add(file)
  }
  let rootEntries = []
  try { rootEntries = await readdir(root, { withFileTypes: true }) } catch {}
  for (const entry of rootEntries) if (entry.isFile() && extensions.has(extname(entry.name).toLowerCase())) found.add(join(root, entry.name))
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
  for (const [path, expected] of [
    [targets.token_css, sources.token],
    [targets.component_css, sources.component]
  ]) {
    const target = join(options.root, path)
    if (!(await exists(target))) continue
    const actual = await readFile(target, 'utf8')
    if (actual !== expected) drift.push({ path, reason: 'managed-asset-drift', expected_sha256: sha256(expected), actual_sha256: sha256(actual) })
  }
  const designProfilePath = join(options.root, targets.design_profile)
  if (await exists(designProfilePath)) {
    try {
      const current = JSON.parse(await readFile(designProfilePath, 'utf8'))
      if (current.profile_id !== sources.profile.profile_id || current.profile_digest !== sources.digest) {
        drift.push({ path: targets.design_profile, reason: 'profile-provenance-drift', expected_profile_id: sources.profile.profile_id, actual_profile_id: current.profile_id ?? null, expected_digest: sources.digest, actual_digest: current.profile_digest ?? null })
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

// insertAt は「直近の @charset/@import/コメント終端の直後」= 確定位置。
// pending はそこから空行を跨いだ位置で、後ろに本文が現れたときだけ採用する。
// 空行で insertAt を直接進めると、import とコメントだけで終わるファイル
// (Tailwind v4 の `@import "tailwindcss";` など) では split('\n') が作る
// 末尾の空要素まで消費して挿入位置が毎回 1 行ずつ後退し、apply が非冪等になる。
function addImportAfterExistingImports(body, cssImport) {
  const lines = body.split('\n')
  let insertAt = 0
  let pending = 0
  let inComment = false
  for (let index = 0; index < lines.length; index += 1) {
    const trimmed = lines[index].trim()
    if (inComment) {
      pending = index + 1
      if (trimmed.includes('*/')) { inComment = false; insertAt = pending }
      continue
    }
    if (!trimmed) { pending = index + 1; continue }
    if (trimmed.startsWith('/*')) {
      pending = index + 1
      if (trimmed.includes('*/')) insertAt = pending
      else inComment = true
      continue
    }
    if (/^@(charset|import)\b/.test(trimmed)) { insertAt = index + 1; pending = insertAt; continue }
    insertAt = pending
    break
  }
  lines.splice(insertAt, 0, cssImport)
  return lines.join('\n')
}

function cssWithoutComments(body) {
  return body.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, ' '))
}

function importStatements(body) {
  return [...cssWithoutComments(body).matchAll(/@import\b[^;]*;/g)].map((match) => ({ index: match.index, text: match[0] }))
}

function importTarget(cssImport) {
  return cssImport.match(/["']([^"']+)["']/)?.[1] ?? ''
}

function canonicalImportState(body, cssImport) {
  const target = importTarget(cssImport)
  const statements = importStatements(body)
  const canonical = statements.filter((statement) => target && statement.text.includes(target))
  return {
    activeCount: canonical.length,
    orderedAfterImports: canonical.length === 1 && statements.every((statement) => statement === canonical[0] || statement.index < canonical[0].index)
  }
}

// 除去は行単位で行う。addImportAfterExistingImports が行を splice で挿入するため、
// 文の範囲だけ削ると空行が残り、apply のたびに 1 行ずつ増える(verify は @import の
// 個数と順序しか見ないので検出されない)。削除と挿入の単位を揃えて冪等にする。
function dropRange(body, start, end) {
  const lineStart = body.lastIndexOf('\n', start - 1) + 1
  const newline = body.indexOf('\n', end)
  const lineEnd = newline === -1 ? body.length : newline
  const aloneOnLine = !body.slice(lineStart, start).trim() && !body.slice(end, lineEnd).trim()
  if (!aloneOnLine) return body.slice(0, start) + body.slice(end)
  return body.slice(0, lineStart) + body.slice(newline === -1 ? lineEnd : lineEnd + 1)
}

function normalizeCanonicalImport(body, cssImport) {
  const target = importTarget(cssImport)
  const clean = cssWithoutComments(body)
  const ranges = [...clean.matchAll(/@import\b[^;]*;/g)]
    .filter((match) => target && match[0].includes(target))
    .map((match) => [match.index, match.index + match[0].length])
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
  const tokenTarget = join(options.root, targets.token_css)
  const componentTarget = join(options.root, targets.component_css)
  await mkdir(dirname(tokenTarget), { recursive: true })
  await copyFile(canonicalPaths.token, tokenTarget)
  await writeFile(componentTarget, sources.component)

  const cssImport = `@import url("${importPath(entry, componentTarget)}");`
  const entryBody = await readFile(entry, 'utf8')
  const normalizedEntry = normalizeCanonicalImport(entryBody, cssImport)
  if (normalizedEntry !== entryBody) await writeFile(entry, normalizedEntry)

  let previous = {}
  try { previous = JSON.parse(await readFile(join(options.root, targets.design_profile), 'utf8')) } catch {}
  const designProfile = {
    schema_version: 1,
    profile_id: sources.profile.profile_id,
    profile_version: sources.profile.profile_version,
    profile_digest: sources.digest,
    mode: sources.profile.default_mode,
    app_state: options.appState,
    eligibility: options.appState === 'new' ? 'new-app' : options.eligibility,
    reviewed_upgrade: options.reviewedUpgrade,
    source_catalog: sources.profile.source.catalog,
    entry_css: relative(options.root, entry).split(sep).join('/'),
    assets: [
      { path: targets.token_css, sha256: sha256(sources.token) },
      { path: targets.component_css, sha256: sha256(sources.component) }
    ],
    adopted_components: Array.isArray(previous.adopted_components) ? previous.adopted_components : [],
    exceptions: Array.isArray(previous.exceptions) ? previous.exceptions : [],
    samples_copied: false
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
  check('profile-id', adopted?.profile_id === sources.profile.profile_id, adopted?.profile_id ?? 'missing')
  check('profile-version', adopted?.profile_version === sources.profile.profile_version, adopted?.profile_version ?? 'missing')
  check('profile-digest', adopted?.profile_digest === sources.digest, adopted?.profile_digest ?? 'missing')
  check('sample-copy-disabled', adopted?.samples_copied === false, adopted?.samples_copied ?? 'missing')

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

  for (const [id, target, expected] of [
    ['token-asset', targets.token_css, sources.token],
    ['component-asset', targets.component_css, sources.component]
  ]) {
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
