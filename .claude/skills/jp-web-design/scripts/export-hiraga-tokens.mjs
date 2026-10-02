#!/usr/bin/env node
// hiraga-color-system.css を唯一の正本として、JSON・standalone previewを生成する。
// 使い方: node scripts/export-hiraga-tokens.mjs [--check]
//   --check: 生成予定値との差分だけを検査し、ファイルは変更しない(CI用)
// 終了コード: 0=成功・一致 / 1=不一致 / 2=読込・正本エラー

import { readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { loadTokens, contrast } from './hiraga-tokens.mjs'
import { avoided, swatches, tones, contrastSamples, areaRatio } from './hiraga-spec.mjs'

const jsonPath = fileURLToPath(new URL('../assets/hiraga/hiraga-color-tokens.json', import.meta.url))
const previewPath = fileURLToPath(new URL('../assets/hiraga/hiraga-color-preview.html', import.meta.url))
const CSS_START = '/* BEGIN GENERATED: hiraga-color-system.css */'
const CSS_END = '/* END GENERATED: hiraga-color-system.css */'
const META_START = '<!-- BEGIN GENERATED: hiraga-metadata -->'
const META_END = '<!-- END GENERATED: hiraga-metadata -->'
// 見本の本文のうち、HEX と比率を載せる区画は生成物にする。手書きだと正本CSSを変えても静かに古いまま残る
// (v0.3 で実際に起きた: :root は青、色見本のコピー値とコントラスト数値はマゼンタ時代のまま)。
// [区画名, 既にマーカーが無いときに置き換える範囲, 中身を作る関数] の順で適用する
const BODY_REGIONS = [
  ['hiraga-palette', /<div class="palette">[\s\S]*?<\/div><div class="ratio"[\s\S]*?<\/p>/, renderPalette],
  ['hiraga-tones', /<div class="tone-list">[\s\S]*?<\/div>(?=<p class="mini-label")/, renderTones],
  ['hiraga-contrast', /<div class="contrast-grid">[\s\S]*?<\/div><div class="rule-box">[\s\S]*?<\/div>/, renderContrast]
]

let tokens
let preview
try {
  ;[tokens, preview] = await Promise.all([
    loadTokens(),
    readFile(previewPath, 'utf8')
  ])
} catch (error) {
  console.error(`ERROR ${error.message}`)
  process.exit(2)
}

const base = {}
const role = {}
for (const [name, value] of Object.entries(tokens.raw)) {
  if (name.startsWith('p-')) base[name] = value
  else role[name] = { ref: value.startsWith('var(') ? value.slice(6, -1) : null, value: tokens.resolved[name] }
}

const document = {
  schema_version: tokens.metadata.schema_version,
  name: tokens.metadata.name,
  version: tokens.metadata.version,
  date: tokens.metadata.date,
  status: tokens.metadata.status,
  source: 'hiraga-color-system.css(正本。このJSON・previewは生成物)',
  theme: tokens.metadata.theme,
  base,
  role
}
const jsonText = `${JSON.stringify(document, null, 2)}\n`
const previewText = renderPreview(preview, tokens.css, tokens.metadata)

if (process.argv.includes('--check')) {
  const checks = [
    ['hiraga-color-tokens.json', await readFile(jsonPath, 'utf8').catch(() => ''), jsonText],
    ['hiraga-color-preview.html (埋込みCSS・版表示)', preview, previewText]
  ]
  let failed = false
  for (const [name, current, expected] of checks) {
    if (current !== expected) {
      console.error(`FAIL ${name} が正本CSSからの生成予定値と一致しません。node scripts/export-hiraga-tokens.mjs で再生成してください`)
      failed = true
    } else {
      console.log(`PASS ${name} は正本CSSからの生成値と一致`)
    }
  }
  if (failed) process.exit(1)
} else {
  await Promise.all([
    writeFile(jsonPath, jsonText),
    writeFile(previewPath, previewText)
  ])
  console.log(`wrote JSON / standalone preview (base ${Object.keys(base).length} / role ${Object.keys(role).length})`)
}

function renderPreview(current, css, metadata) {
  const generatedCss = `${CSS_START}\n${css.trimEnd()}\n${CSS_END}`
  let next
  if (current.includes(CSS_START) && current.includes(CSS_END)) {
    next = current.replace(new RegExp(`${escapeRegExp(CSS_START)}[\\s\\S]*?${escapeRegExp(CSS_END)}`), generatedCss)
  } else {
    const styleOpen = current.indexOf('<style>')
    const previewOnly = current.indexOf('\n\n*{box-sizing:border-box}', styleOpen)
    if (styleOpen < 0 || previewOnly < 0) throw new Error('preview style boundary not found')
    next = `${current.slice(0, styleOpen)}<style data-generated-source="hiraga-color-system.css">${generatedCss}\n\n/* BEGIN PREVIEW-ONLY STYLES */${current.slice(previewOnly)}`
  }

  const metadataBlock = [
    META_START,
    `<meta name="hiraga-schema-version" content="${escapeHtml(String(metadata.schema_version))}">`,
    `<meta name="hiraga-version" content="${escapeHtml(metadata.version)}">`,
    `<meta name="hiraga-date" content="${escapeHtml(metadata.date)}">`,
    `<meta name="hiraga-status" content="${escapeHtml(metadata.status)}">`,
    META_END
  ].join('')
  if (next.includes(META_START) && next.includes(META_END)) {
    next = next.replace(new RegExp(`${escapeRegExp(META_START)}[\\s\\S]*?${escapeRegExp(META_END)}`), metadataBlock)
  } else {
    next = next.replace('</title>', `</title>${metadataBlock}`)
  }

  const provisional = /暫定/.test(metadata.status)
  const label = `${provisional ? '暫定提案' : '承認済み'} v${metadata.version} ・ ${provisional ? '公式HEX未検証' : '承認記録あり'}`
  const dateLabel = metadata.date.replaceAll('-', '.')
  next = next.replace(/(<span class="version">)[^<]*(<\/span>)/, `$1${label}$2`)
  next = next.replace(/(<footer class="footer">)[^<]*(<br>)/, `$1${dateLabel} / ${provisional ? '暫定提案' : '承認済み'} v${metadata.version}$2`)

  for (const [name, fallback, render] of BODY_REGIONS) {
    const [open, close] = [`<!-- BEGIN GENERATED: ${name} -->`, `<!-- END GENERATED: ${name} -->`]
    const block = `${open}${render()}${close}`
    const marked = new RegExp(`${escapeRegExp(open)}[\\s\\S]*?${escapeRegExp(close)}`)
    if (marked.test(next)) next = next.replace(marked, block)
    else if (fallback.test(next)) next = next.replace(fallback, block)
    else throw new Error(`preview body region not found: ${name}`)
  }
  return next
}

/** トークンの解決値。見本に載せる HEX は必ずここを通し、HTML へ直接書かない */
function hexOf(name) {
  const value = tokens.resolved[name]
  if (!/^#[0-9A-Fa-f]{6}$/.test(value ?? '')) throw new Error(`token --${name} が #RRGGBB に解決できません (${value})`)
  return value.toUpperCase()
}

function renderPalette() {
  const items = swatches.map(([name, title, description]) => {
    const hex = hexOf(name)
    return `<button class="swatch" data-copy="${hex}" aria-label="${escapeHtml(description)} ${hex} をコピー"><span class="swatch-color" style="background:var(--${name})"></span><span class="swatch-info"><strong>${escapeHtml(title)}</strong><code>${hex}</code><small>${escapeHtml(description)}</small></span></button>`
  })
  return `<div class="palette">${items.join('')}</div><div class="ratio" aria-label="${escapeHtml(areaRatio.aria)}"><span class="base"></span><span class="nav"></span><span class="accent"></span></div><p class="ratio-note">${escapeHtml(areaRatio.note)}</p>`
}

function renderTones() {
  const rows = tones.map(([label, ...names]) =>
    `<div class="tone-row"><span>${escapeHtml(label)}</span><code>${names.map(hexOf).join(' / ')}</code></div>`
  )
  return `<div class="tone-list">${rows.join('')}</div>`
}

function renderContrast() {
  const items = contrastSamples.map(({ label, fg, bg, border, sample }) => {
    const style = border
      ? `color:var(--${fg});background:var(--${bg});border:2px solid var(--${border})`
      : `color:var(--${fg});background:var(--${bg})`
    const ratio = contrast(hexOf(border ?? fg), hexOf(bg)).toFixed(2)
    return `<div class="contrast-item"><span class="contrast-sample" style="${style}">${escapeHtml(sample)}</span><span>${escapeHtml(label)}<strong>${ratio}:1</strong></span></div>`
  })
  const rules = avoided.map(([fg, bg, min, label]) =>
    `${escapeHtml(label)}は約${contrast(hexOf(fg), hexOf(bg)).toFixed(2)}:1で、${min >= 4.5 ? '通常文字' : '識別に必要な境界'}の基準(${min}:1)を満たしません。`
  )
  return `<div class="contrast-grid">${items.join('')}</div><div class="rule-box"><strong>避ける組み合わせ：</strong>${rules.join('')}</div>`
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function escapeHtml(value) {
  return value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
}
