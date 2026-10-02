#!/usr/bin/env node
// 暫定標準カラーの主要ペアを検査する。本文4.5:1、非テキスト(入力枠・フォーカス・大きい文字)3:1。
// 避けるペアは「基準未満であること」を確認し、資料記載の値から逸脱していないかも見る。
// 使い方: node scripts/check-standard-contrast.mjs [css-path]
// 終了コード: 0=全PASS / 1=FAILあり / 2=CSS読込・解決エラー
// 画面全体の検査(axe等)や WCAG 全体への適合を置き換えない。

import { loadTokens, contrast, isHex, hueGap } from './standard-tokens.mjs'
import { required, avoided, series, seriesMinHueGap } from './standard-spec.mjs'

// 検査するペアと基準の正本は standard-spec.mjs。見本HTMLの生成 (export-standard-tokens.mjs) と共有する
const SERIES = series
const SERIES_MIN_HUE_GAP = seriesMinHueGap

let tokens
try {
  ;({ resolved: tokens } = await loadTokens(process.argv[2]))
} catch (error) {
  console.error(`ERROR ${error.message}`)
  process.exit(2)
}

let failed = false
const measure = (fg, bg) => {
  const a = tokens[fg]
  const b = tokens[bg]
  if (!isHex(a ?? '') || !isHex(b ?? '')) {
    console.error(`ERROR --${fg}(${a}) / --${bg}(${b}) は #RRGGBB に解決できません`)
    process.exit(2)
  }
  return contrast(a, b)
}

for (const [fg, bg, min, label] of required) {
  const value = measure(fg, bg)
  const pass = value >= min
  failed ||= !pass
  console.log(`${pass ? 'PASS' : 'FAIL'} ${label} --${fg}/--${bg}: ${value.toFixed(2)}:1 (基準 ${min})`)
}
for (const [fg, bg, min, label] of avoided) {
  const value = measure(fg, bg)
  const pass = value < min
  failed ||= !pass
  console.log(`${pass ? 'AVOID' : 'FAIL'} ${label} --${fg}/--${bg}: ${value.toFixed(2)}:1 (基準 ${min} 未満であるべき)`)
}

let minGap = { gap: Infinity, a: '', b: '' }
for (let i = 0; i < SERIES.length; i += 1) {
  for (let j = i + 1; j < SERIES.length; j += 1) {
    const [a, b] = [SERIES[i], SERIES[j]]
    for (const name of [a, b]) {
      if (!isHex(tokens[name] ?? '')) {
        console.error(`ERROR --${name}(${tokens[name]}) は #RRGGBB に解決できません`)
        process.exit(2)
      }
    }
    const gap = hueGap(tokens[a], tokens[b])
    if (gap < minGap.gap) minGap = { gap, a, b }
  }
}
{
  const pass = minGap.gap >= SERIES_MIN_HUE_GAP
  failed ||= !pass
  console.log(
    `${pass ? 'PASS' : 'FAIL'} グラフ系列の見分け 最小色相差 --${minGap.a}/--${minGap.b}: ${minGap.gap}度 (基準 ${SERIES_MIN_HUE_GAP}度以上)`
  )
}

if (failed) process.exitCode = 1
