// 既存アプリへ平賀配色を自動適用してよいか（適用資格）の判定。
// migrate-legacy-colors と catalog-default plan が同じ走査範囲・同じ規則で判定するための唯一の定義。
// T2（docs/product/T2-experience-spec.md）のブランド契約を最優先し、無ければソース中の信号から判断する。

import { readFile } from 'node:fs/promises'
import { extname, relative } from 'node:path'
import { walkSources } from './fs-walk.mjs'

export const T2_SPEC_NAME = 'T2-experience-spec.md'
export const SCAN_EXT = new Set(['.css', '.scss', '.html', '.tsx', '.jsx', '.ts', '.js', '.mjs', '.vue', '.svelte', '.astro'])
// 平賀の正本コピーは移行元ではないので判定にも移行にも含めない。
const SKIP_FILE = new Set(['hiraga-color-system.css', 'hiraga-color-tokens.json', 'hiraga-color-preview.html'])

export function isT2Spec(path) {
  const normalized = path.replaceAll('\\', '/').toLowerCase()
  return normalized === `docs/product/${T2_SPEC_NAME}`.toLowerCase()
    || normalized.endsWith(`/docs/product/${T2_SPEC_NAME}`.toLowerCase())
}

// root 相対パス → 本文 の Map。判定と移行計画はこの同じ集合を見る。
export async function readProjectSources(root) {
  const sources = new Map()
  const accept = (path, name) => (SCAN_EXT.has(extname(name)) || isT2Spec(path)) && !SKIP_FILE.has(name)
  for await (const file of walkSources(root, { accept })) sources.set(relative(root, file), await readFile(file, 'utf8'))
  return sources
}

function compact(values) {
  return values.filter(Boolean)
}

function readT2BrandContract(sources) {
  const specs = [...sources].filter(([path]) => isT2Spec(path))
  if (specs.length > 1) {
    return { conflict: true, paths: specs.map(([path]) => path).sort() }
  }
  if (specs.length === 0) return null
  const [path, body] = specs[0]
  const field = (name) => body.match(new RegExp(`^\\s*${name}\\s*:\\s*(.*?)\\s*$`, 'im'))?.[1]?.trim() || null
  return {
    conflict: false,
    path,
    status: field('brand_color_status'),
    source: field('brand_color_source'),
    approver: field('brand_color_approver'),
    approved_at: field('brand_color_approved_at')
  }
}

// 戻り値: { status: 'eligible'|'report-only', source_theme, reason, evidence[] }
export function projectEligibility(sources) {
  const combined = [...sources.values()].join('\n')
  const contract = readT2BrandContract(sources)
  if (contract?.conflict) {
    return { status: 'report-only', source_theme: 'undetermined', reason: 'T2ブランド契約が複数あり正本を一意に決められない', evidence: contract.paths }
  }
  const status = contract ? contract.status : combined.match(/brand_color_status\s*[:=]\s*([^\n|]+)/i)?.[1]?.trim()
  const source = contract ? contract.source : combined.match(/brand_color_source\s*[:=]\s*([^\n|]+)/i)?.[1]?.trim()
  const meaningful = (value) => value
    && !/^_+/.test(value)
    && !/^(?:未指定|unspecified|none)$/i.test(value)
  const approved = /^(?:approved|承認済み)(?:\b|$)/i.test(status || '')
  const pop = contract
    ? /^(?:mode\s*b|b\s*pop|pop)\b/i.test(source || '')
    : /(?:brand_color_source|配色)\s*[:=]\s*(?:mode\s*b|b\s*pop|pop)\b/im.test(combined)
  const legacyModeA = /mode\s*a\b|graphite\s*(?:x|×)\s*amber|mode-a-graphite-amber/i.test(combined)
    || ['--primary', '--accent', '--page-bg'].filter((signature) => combined.includes(signature)).length >= 2
  const declaredHiraga = /^(?:hiraga|default)$/i.test(source || '')
  const hiraga = declaredHiraga || combined.includes('hiraga-color-system.css') || combined.includes('--p-brand-indigo')
  const recognizedAutomaticSource = /^(?:legacy-mode-a|mode-a|hiraga|default)$/i.test(source || '')
  const allowedSource = !meaningful(source) || recognizedAutomaticSource
  const evidence = compact([contract?.path, status, source, contract?.approver, contract?.approved_at])

  if (pop && (legacyModeA || meaningful(source))) {
    return { status: 'report-only', source_theme: 'undetermined', reason: 'Pop/ブランド指定と旧Mode Aの信号が競合', evidence: compact([...evidence, 'conflicting-signals']) }
  }
  if (pop) return { status: 'report-only', source_theme: 'pop', reason: 'Popは利用者の明示指定であり自動移行対象外', evidence: compact([...evidence, 'explicit-pop']) }
  if (!allowedSource || (approved && !recognizedAutomaticSource)) {
    return { status: 'report-only', source_theme: 'external-brand', reason: 'T2で承認済みまたは別ブランドと記録された配色は自動変更しない', evidence }
  }
  if (legacyModeA) return { status: 'eligible', source_theme: 'legacy-mode-a', reason: '旧Mode Aの複数シグネチャを確認', evidence: compact([...evidence, 'legacy-mode-a']) }
  if (hiraga) return { status: 'eligible', source_theme: 'hiraga', reason: '平賀CSSまたはT2の平賀指定を確認。残る旧参照だけを安全規則で移行', evidence: compact([...evidence, 'hiraga-loaded']) }
  return { status: 'eligible', source_theme: 'unspecified', reason: 'T2にPop・別ブランド指定がなく配色未指定', evidence: compact([...evidence, 'no-explicit-brand']) }
}
