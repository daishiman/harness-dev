#!/usr/bin/env node
// 既存アプリの旧配色を「検出 → 計画 → 安全な規則だけ適用」の順で移行する。
// dry-run: 検出のみ / --plan: 同じ計画を安定JSON等へ渡す段階 / --apply: automation=safe だけを一括適用。
// review-only / manual、Pop、別ブランド、適用資格を証明できないプロジェクトは --apply でも変更しない。
// 使い方: node scripts/migrate-legacy-colors.mjs <dir> [--plan|--apply] [--json]
// 終了コード: 0=残件なし / 1=計画・要確認・対象外あり / 2=引数・読込・transactionエラー

import { readFile, rename, stat, unlink, writeFile } from 'node:fs/promises'
import { basename, dirname, extname, join } from 'node:path'
import { loadTokens } from './hiraga-tokens.mjs'
import { UsageError, failCli, parseArgs } from './lib/args.mjs'
import { isT2Spec, projectEligibility, readProjectSources } from './lib/eligibility.mjs'
import { sha256 as digest } from './lib/provenance.mjs'

const usage = 'usage: migrate-legacy-colors.mjs <dir> [--plan|--apply] [--json]'
let cli
try {
  cli = parseArgs(process.argv.slice(2), { positionals: 1, booleans: { '--apply': 'apply', '--plan': 'plan', '--json': 'json' } })
  if (cli.options.apply && cli.options.plan) throw new UsageError('--plan and --apply cannot be combined')
} catch (error) {
  failCli(error, usage)
  process.exit()
}
const [root] = cli.args
const apply = Boolean(cli.options.apply)
const planOnly = Boolean(cli.options.plan)
const asJson = Boolean(cli.options.json)

const mode = apply ? 'apply' : planOnly ? 'plan' : 'dry-run'
const SCHEMA_VERSION = '1.0'
const DECLARATION_EXT = new Set(['.css', '.scss'])
const SUPPORTED_SYNTAX = Object.freeze({
  token_references: 'var(--token) in .css/.scss/.html/.tsx/.jsx/.ts/.js/.mjs/.vue/.svelte/.astro',
  direct_colors: '#RGB and #RRGGBB in CSS/SCSS declarations only',
  declaration_parser: 'plain property:value declarations separated by ; or }',
  eligibility_contract: 'brand_color_status/source/approver/approved_at in docs/product/T2-experience-spec.md',
  report_only: 'CSS color functions, alpha HEX, Tailwind palette classes, Dark/theme-switch code, custom-property definitions',
  unsupported_warning: 'nested/preprocessor-generated properties and CSS-in-JS object semantics are not auto-applied'
})

// 多義語は候補を示すだけにし、意味が一意な旧Mode Aトークンだけを安全規則にする。
const LEGACY_RULES = Object.freeze({
  'page-bg': rule('app-background', 'safe', 'high', '旧Mode Aのページ背景と役割が一意'),
  bg: rule('app-background', 'safe', 'high', '旧Mode Aのルート背景と役割が一意'),
  subtle: rule('surface-alt', 'safe', 'high', '旧Mode Aの補助面と役割が一意'),
  ink: rule('text-primary', 'safe', 'high', '旧Mode Aの本文色と役割が一意'),
  'ink-muted': rule('text-secondary', 'safe', 'high', '旧Mode Aの補助本文色と役割が一意'),
  'border-strong': rule('border-control', 'safe', 'high', '旧Mode Aの操作境界と役割が一意'),
  'primary-hover': rule('action-primary-hover', 'safe', 'high', '旧Mode Aの主操作hoverと役割が一意'),
  'primary-text': rule('action-primary-text', 'safe', 'high', '旧Mode Aの主操作文字と役割が一意'),
  'brand-soft': rule('surface-selected', 'safe', 'high', '旧Mode Aの選択面と役割が一意'),
  'brand-mist': rule('surface-selected', 'safe', 'high', '旧Mode Aの選択面と役割が一意'),
  'accent-text': rule('text-inverse', 'safe', 'high', '旧Mode Aの濃色面上文字と役割が一意'),
  success: rule('status-success-text', 'safe', 'high', '旧Mode Aの成功文字色'),
  'success-bg': rule('status-success-bg', 'safe', 'high', '旧Mode Aの成功背景'),
  warning: rule('status-warning-text', 'safe', 'high', '旧Mode Aの注意文字色'),
  'warning-bg': rule('status-warning-bg', 'safe', 'high', '旧Mode Aの注意背景'),
  'danger-bg': rule('status-danger-bg', 'safe', 'high', '旧Mode Aのエラー背景'),
  'danger-soft': rule('status-danger-bg', 'safe', 'high', '旧Mode Aのエラー背景'),
  'caution-soft': rule('status-warning-bg', 'safe', 'high', '旧Mode Aの注意背景'),
  'caution-border': rule('status-warning-text', 'safe', 'high', '旧Mode Aの注意境界'),
  neutral: rule('status-neutral-text', 'safe', 'high', '旧Mode Aの中立文字色'),
  'neutral-bg': rule('status-neutral-bg', 'safe', 'high', '旧Mode Aの中立背景'),
  text: rule('text-primary', 'review-only', 'low', '本文・逆引き文字・ボタン文字のいずれか判定が必要'),
  'text-muted': rule('text-secondary', 'review-only', 'medium', '既存の役割トークンと旧トークンを判別する必要がある'),
  border: rule('border-subtle', 'review-only', 'low', '装飾罫線・入力枠・選択線の判定が必要'),
  line: rule('border-subtle', 'review-only', 'low', '装飾罫線・入力枠の判定が必要'),
  primary: rule('action-primary-bg', 'review-only', 'low', '主操作・リンク・現在地・見出しの判定が必要'),
  brand: rule('action-primary-bg', 'review-only', 'low', '主操作・リンク・見出し・ナビの判定が必要'),
  'brand-deep': rule('text-heading', 'review-only', 'low', '見出し文字・hover塗りの判定が必要'),
  accent: rule('status-info-text', 'review-only', 'low', '状態・CTA・装飾の判定が必要'),
  'accent-deep': rule('status-info-text', 'review-only', 'low', '状態・CTAの判定が必要'),
  danger: rule('status-danger-text', 'review-only', 'low', '危険文字・危険ボタン背景の判定が必要')
})

const DARK_PATTERNS = [
  [/html\[data-theme=["']?dark/gi, 'Darkテーマ定義は手作業で削除'],
  [/prefers-color-scheme\s*:\s*dark/gi, 'OS追従Dark定義は手作業で削除'],
  [/data-theme-choice|theme-toggle|localStorage[^\n]*theme/gi, 'テーマ切替UI・永続化は手作業で削除'],
  [/color-scheme["']?\s*(?:content=["']|:)\s*["']?light dark/gi, 'color-schemeをlightへ手作業で変更']
]
const TAILWIND_DEFAULT = /\b(?:bg|text|border|ring|fill|stroke|from|to|via|outline|divide|accent|decoration)-(?:slate|gray|zinc|neutral|stone|blue|sky|indigo|violet|purple|amber|yellow|orange)-\d{2,3}\b/g
const COLOR_FUNCTION = /\b(?:rgba?|hsla?|oklch|oklab|lab|lch|color|color-mix)\([^;{}]*\)/gi
const ALPHA_HEX = /#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{4}\b/g
const PLAIN_HEX = /#[0-9a-fA-F]{6}(?![0-9a-fA-F])|#[0-9a-fA-F]{3}(?![0-9a-fA-F])/g
const EXTERNAL_BRAND_MARKER = /aidd-color-migration\s*:\s*exclude-(?:brand|file)/i
const TEST_FAULTS = process.env.NODE_ENV === 'test'
  ? new Set((process.env.AIDD_MIGRATION_TEST_FAULT || '').split(',').filter(Boolean))
  : new Set()

function rule(candidate, automation, confidence, reason) {
  return { candidate, automation, confidence, reason }
}

function normalizeHex(hex) {
  const upper = hex.toUpperCase()
  return upper.length === 4 ? `#${upper[1]}${upper[1]}${upper[2]}${upper[2]}${upper[3]}${upper[3]}` : upper
}

function propertyKind(property) {
  if (/^(?:background|background-color|fill)$/.test(property)) return 'background'
  if (/(?:border|outline|stroke|box-shadow|ring)/.test(property)) return 'border'
  if (/^(?:color|caret-color|text-decoration-color)$/.test(property)) return 'color'
  return 'unknown'
}

function locationAt(source, index) {
  const prefix = source.slice(0, index)
  const line = prefix.split('\n').length
  const lastBreak = prefix.lastIndexOf('\n')
  return { line, column: index - lastBreak }
}

function declarationRanges(source) {
  const declarations = []
  const pattern = /([-\w]+)\s*:\s*([^;{}]*)(;|(?=\}))/g
  for (const match of source.matchAll(pattern)) {
    const valueOffset = match[0].indexOf(match[2])
    declarations.push({
      property: match[1].toLowerCase(),
      value: match[2],
      start: match.index,
      end: match.index + match[0].length,
      valueStart: match.index + valueOffset
    })
  }
  return declarations
}

function containingDeclaration(declarations, index) {
  return declarations.find((declaration) => index >= declaration.start && index < declaration.end)
}

function isPopFile(path) {
  return /(^|[\/_.-])pop([_.-]|$)/i.test(path)
}

function fileExclusion(path, source) {
  if (isPopFile(path)) return 'Popファイルは全検出・全置換の対象外'
  if (EXTERNAL_BRAND_MARKER.test(source)) return '別ブランドの明示除外マーカーを確認'
  return null
}

function buildHexRoles(resolved) {
  const byHex = new Map()
  const add = (token, kind) => {
    const value = resolved[token]
    if (!/^#[0-9a-fA-F]{6}$/.test(value || '')) return
    const key = normalizeHex(value)
    if (!byHex.has(key)) byHex.set(key, {})
    byHex.get(key)[kind] ??= token
  }
  for (const [token, kind] of [
    ['text-heading', 'color'], ['nav-background', 'background'], ['action-secondary-border', 'border'],
    ['required-text', 'color'], ['action-primary-bg', 'background'], ['input-border-focus', 'border'],
    ['action-primary-hover', 'background'], ['action-primary-active', 'background'],
    ['text-inverse', 'color'], ['surface', 'background'], ['focus-gap', 'border'],
    ['surface-alt', 'background'], ['table-stripe-bg', 'background'], ['surface-selected', 'background'],
    ['text-primary', 'color'], ['text-secondary', 'color'], ['text-muted', 'color'],
    ['border-subtle', 'border'], ['border-control', 'border'],
    ['status-danger-text', 'color'], ['action-danger-bg', 'background'], ['input-invalid-border', 'border'],
    ['status-danger-bg', 'background'], ['status-warning-text', 'color'], ['status-warning-bg', 'background'],
    ['status-success-text', 'color'], ['status-success-bg', 'background'],
    ['status-info-text', 'color'], ['status-info-bg', 'background']
  ]) add(token, kind)
  return byHex
}

function makeItem({ path, source, index = 0, type, oldValue = null, newValue = null, automation, status, reason, confidence = null }) {
  const location = locationAt(source, index)
  return {
    id: '',
    file: path,
    line: location.line,
    column: location.column,
    type,
    old_value: oldValue,
    new_value: newValue,
    automation,
    confidence,
    status,
    reason
  }
}

function safeStatus(eligible) {
  if (!eligible) return 'unchanged'
  if (apply) return 'applied'
  return planOnly ? 'planned' : 'detected'
}

function planFile(path, source, eligibility, hexRoles) {
  if (isT2Spec(path)) {
    return {
      path,
      preimage_sha256: digest(source),
      excluded: false,
      exclusion_reason: null,
      metadata_only: true,
      changed: false,
      would_change: false,
      nextSource: source,
      items: []
    }
  }
  const exclusion = fileExclusion(path, source)
  if (exclusion) {
    return {
      path,
      preimage_sha256: digest(source),
      excluded: true,
      exclusion_reason: exclusion,
      changed: false,
      would_change: false,
      nextSource: source,
      items: [makeItem({ path, source, type: 'eligibility', automation: 'manual', status: 'excluded', reason: exclusion })]
    }
  }

  const eligibleFile = eligibility.status === 'eligible'
  const ext = extname(path)
  const declarations = DECLARATION_EXT.has(ext) ? declarationRanges(source) : []
  const items = []
  const edits = []
  const addItem = (item) => items.push(item)
  const addEdit = (start, end, replacement, item) => {
    edits.push({ start, end, replacement })
    addItem(item)
  }

  for (const [pattern, reason] of DARK_PATTERNS) {
    for (const match of source.matchAll(pattern)) {
      addItem(makeItem({ path, source, index: match.index, type: 'theme', oldValue: match[0], automation: 'manual', status: 'unchanged', reason }))
    }
  }
  for (const match of source.matchAll(TAILWIND_DEFAULT)) {
    addItem(makeItem({ path, source, index: match.index, type: 'tailwind', oldValue: match[0], automation: 'review-only', status: 'unchanged', reason: '平賀の役割ユーティリティへ手で割り当てる' }))
  }

  for (const match of source.matchAll(/var\(--([\w-]+)/g)) {
    const name = match[1]
    const mapping = LEGACY_RULES[name]
    if (!mapping) continue
    const declaration = containingDeclaration(declarations, match.index)
    if (declaration?.property.startsWith('--')) continue
    const candidate = `var(--${mapping.candidate})`
    const safeCandidate = eligibleFile && mapping.automation === 'safe'
    const item = makeItem({
      path,
      source,
      index: match.index,
      type: 'token',
      oldValue: match[0],
      newValue: candidate,
      automation: mapping.automation,
      confidence: mapping.confidence,
      status: mapping.automation === 'safe' ? safeStatus(safeCandidate) : 'unchanged',
      reason: eligibility.status === 'eligible' ? mapping.reason : `${mapping.reason}。${eligibility.reason}`
    })
    if (safeCandidate) addEdit(match.index, match.index + match[0].length, candidate.slice(0, -1), item)
    else addItem(item)
  }

  for (const declaration of declarations) {
    if (declaration.property.startsWith('--')) {
      const legacyName = declaration.property.slice(2)
      if (LEGACY_RULES[legacyName]) {
        addItem(makeItem({
          path,
          source,
          index: declaration.start,
          type: 'definition',
          oldValue: declaration.property,
          automation: 'manual',
          status: 'unchanged',
          reason: '旧トークン定義ブロックはhiraga-color-system.cssの読み込みへ手で差し替える'
        }))
      }
      continue
    }

    for (const match of declaration.value.matchAll(COLOR_FUNCTION)) {
      addItem(makeItem({
        path,
        source,
        index: declaration.valueStart + match.index,
        type: 'unsupported-syntax',
        oldValue: match[0],
        automation: 'review-only',
        status: 'unchanged',
        reason: '色関数は対応構文外。宣言の意味を確認して役割トークンへ割り当てる'
      }))
    }
    for (const match of declaration.value.matchAll(ALPHA_HEX)) {
      addItem(makeItem({
        path,
        source,
        index: declaration.valueStart + match.index,
        type: 'unsupported-syntax',
        oldValue: match[0],
        automation: 'review-only',
        status: 'unchanged',
        reason: 'alpha付きHEXは対応構文外。合成後のコントラストを確認する'
      }))
    }
    for (const match of declaration.value.matchAll(PLAIN_HEX)) {
      const index = declaration.valueStart + match.index
      const kind = propertyKind(declaration.property)
      const token = hexRoles.get(normalizeHex(match[0]))?.[kind]
      if (!token) {
        addItem(makeItem({
          path,
          source,
          index,
          type: 'hex',
          oldValue: match[0],
          automation: 'review-only',
          status: 'unchanged',
          reason: kind === 'unknown'
            ? `プロパティ ${declaration.property} の色役割を自動判定しない`
            : '平賀の既知値と一致しないため色の意味を手で決める'
        }))
        continue
      }
      const replacement = `var(--${token})`
      const safeCandidate = eligibleFile
      const item = makeItem({
        path,
        source,
        index,
        type: 'hex',
        oldValue: match[0],
        newValue: replacement,
        automation: 'safe',
        confidence: 'high',
        status: safeStatus(safeCandidate),
        reason: eligibility.status === 'eligible'
          ? `宣言 ${declaration.property} と平賀の既知値から役割が一意`
          : `役割候補は一意だが適用資格なし。${eligibility.reason}`
      })
      if (safeCandidate) addEdit(index, index + match[0].length, replacement, item)
      else addItem(item)
    }
  }

  if (!DECLARATION_EXT.has(ext)) {
    for (const match of source.matchAll(ALPHA_HEX)) {
      addItem(makeItem({ path, source, index: match.index, type: 'unsupported-syntax', oldValue: match[0], automation: 'review-only', status: 'unchanged', reason: `${ext}内のalpha付きHEXは検出のみ` }))
    }
    for (const match of source.matchAll(PLAIN_HEX)) {
      addItem(makeItem({ path, source, index: match.index, type: 'unsupported-syntax', oldValue: match[0], automation: 'review-only', status: 'unchanged', reason: `${ext}内の直書きHEXは検出のみ。CSS宣言へ移して役割を決める` }))
    }
  }

  const ordered = [...edits].sort((a, b) => b.start - a.start)
  for (let index = 1; index < ordered.length; index += 1) {
    if (ordered[index - 1].start < ordered[index].end) throw new Error(`overlapping edits: ${path}`)
  }
  let nextSource = source
  for (const edit of ordered) nextSource = `${nextSource.slice(0, edit.start)}${edit.replacement}${nextSource.slice(edit.end)}`
  return {
    path,
    preimage_sha256: digest(source),
    excluded: false,
    exclusion_reason: null,
    changed: apply && nextSource !== source,
    would_change: nextSource !== source,
    nextSource,
    items
  }
}

async function exists(path) {
  return Boolean(await stat(path).catch(() => null))
}

async function removeIfPresent(path) {
  if (await exists(path)) await unlink(path)
}

function injectTestFault(name) {
  if (TEST_FAULTS.has(name)) throw new Error(`injected fault: ${name}`)
}

async function rollbackTransaction(records, commitError) {
  const rollbackErrors = []
  const attempt = async (label, action) => {
    try {
      await action()
    } catch (error) {
      rollbackErrors.push(`${label}: ${error.message}`)
    }
  }

  for (const record of [...records].reverse()) {
    if (record.replacementInstalled) {
      await attempt(`remove replacement ${record.file}`, async () => {
        await removeIfPresent(record.file)
        record.replacementInstalled = false
      })
    }
    if (record.originalMoved) {
      await attempt(`restore preimage ${record.file}`, async () => {
        injectTestFault('rollback-before-restore')
        if (!await exists(record.backup)) throw new Error(`backup missing: ${record.backup}`)
        await rename(record.backup, record.file)
        record.originalMoved = false
      })
    }
    await attempt(`remove staged file ${record.staged}`, async () => removeIfPresent(record.staged))
  }

  for (const record of records) {
    await attempt(`verify preimage ${record.file}`, async () => {
      const restored = await readFile(record.file, 'utf8')
      if (digest(restored) !== record.preimage) throw new Error('sha256 mismatch')
    })
  }

  if (rollbackErrors.length === 0) {
    for (const record of records) {
      await attempt(`remove verified backup ${record.backup}`, async () => removeIfPresent(record.backup))
    }
  }

  if (rollbackErrors.length === 0) {
    throw new Error(`transaction rolled back: ${commitError.message}`)
  }

  const preserved = []
  for (const record of records) {
    if (await exists(record.backup)) preserved.push(record.backup)
  }
  throw new Error(
    `transaction rollback incomplete: commit failed: ${commitError.message}; rollback errors: ${rollbackErrors.join(' | ')}; backups preserved: ${preserved.join(', ') || 'none'}`
  )
}

async function applyTransaction(changes) {
  if (changes.length === 0) return
  const suffix = `.hiraga-migration-${process.pid}`
  const records = changes.map((change) => ({
    ...change,
    staged: join(dirname(change.file), `.${basename(change.file)}${suffix}.staged`),
    backup: join(dirname(change.file), `.${basename(change.file)}${suffix}.backup`),
    originalMoved: false,
    replacementInstalled: false
  }))
  try {
    for (const record of records) {
      const original = await stat(record.file)
      if (digest(await readFile(record.file, 'utf8')) !== record.preimage) throw new Error(`source changed after planning: ${record.file}`)
      await writeFile(record.staged, record.nextSource, { flag: 'wx', mode: original.mode })
      if (digest(await readFile(record.staged, 'utf8')) !== digest(record.nextSource)) throw new Error(`staged verification failed: ${record.file}`)
    }
    for (const [index, record] of records.entries()) {
      if (digest(await readFile(record.file, 'utf8')) !== record.preimage) throw new Error(`source changed before commit: ${record.file}`)
      await rename(record.file, record.backup)
      record.originalMoved = true
      await rename(record.staged, record.file)
      record.replacementInstalled = true
      if (index === 0) injectTestFault('commit-after-first')
    }
  } catch (error) {
    await rollbackTransaction(records, error)
  }
  for (const record of records) {
    await removeIfPresent(record.backup).catch((error) => {
      console.error(`WARN backup cleanup failed: ${record.backup}: ${error.message}`)
    })
  }
}

const rootStat = await stat(root).catch(() => null)
if (!rootStat?.isDirectory()) {
  console.error(`ERROR ディレクトリではありません: ${root}`)
  process.exit(2)
}

let tokens
try {
  tokens = await loadTokens()
} catch (error) {
  console.error(`ERROR ${error.message}`)
  process.exit(2)
}

const sources = await readProjectSources(root)
const eligibility = projectEligibility(sources)
const hexRoles = buildHexRoles(tokens.resolved)

let filePlans
try {
  filePlans = [...sources].map(([path, source]) => planFile(path, source, eligibility, hexRoles))
} catch (error) {
  console.error(`ERROR ${error.message}`)
  process.exit(2)
}

const plannedChanges = filePlans
  .filter((file) => file.would_change)
  .map((file) => ({ file: join(root, file.path), nextSource: file.nextSource, preimage: file.preimage_sha256 }))
try {
  if (apply) await applyTransaction(plannedChanges)
} catch (error) {
  console.error(`ERROR ${error.message}`)
  process.exit(2)
}

const items = filePlans.flatMap((file) => file.items)
  .sort((a, b) => a.file.localeCompare(b.file, 'en') || a.line - b.line || a.column - b.column || a.type.localeCompare(b.type, 'en'))
items.forEach((item, index) => { item.id = `MIG-${String(index + 1).padStart(4, '0')}` })

const summary = {
  total: items.length,
  safe: items.filter((item) => item.automation === 'safe').length,
  review_only: items.filter((item) => item.automation === 'review-only').length,
  manual: items.filter((item) => item.automation === 'manual').length,
  detected: items.filter((item) => item.status === 'detected').length,
  planned: items.filter((item) => item.status === 'planned').length,
  applied: items.filter((item) => item.status === 'applied').length,
  unchanged: items.filter((item) => item.status === 'unchanged').length,
  excluded_files: filePlans.filter((file) => file.excluded).length,
  planned_files: plannedChanges.length,
  changed_files: apply ? plannedChanges.length : 0
}
const report = {
  schema_version: SCHEMA_VERSION,
  tool: 'migrate-legacy-colors',
  mode,
  root,
  eligibility,
  supported_syntax: SUPPORTED_SYNTAX,
  transaction: {
    strategy: 'stage-then-rename-with-rollback',
    preimage_hash: 'sha256',
    planned_files: plannedChanges.length,
    applied: apply
  },
  summary,
  files: filePlans.map(({ nextSource: _nextSource, items: _items, ...file }) => file),
  items
}

if (asJson) {
  console.log(JSON.stringify(report, null, 2))
} else {
  console.log(`${basename(root)}: ${mode} / eligibility=${eligibility.status}(${eligibility.source_theme}) / 検出 ${summary.total} / safe ${summary.safe} / review-only ${summary.review_only} / manual ${summary.manual} / 適用 ${summary.applied} / 対象外ファイル ${summary.excluded_files}`)
  for (const item of items.filter((entry) => entry.status !== 'applied')) {
    const target = item.new_value ? ` -> ${item.new_value}` : ''
    console.log(`${item.status.padEnd(9)} ${item.automation.padEnd(11)} ${item.file}:${item.line}:${item.column} ${item.old_value || item.type}${target} (${item.reason})`)
  }
}

const unresolved = eligibility.status !== 'eligible' || items.some((item) => item.status !== 'applied')
if (unresolved) process.exitCode = 1
