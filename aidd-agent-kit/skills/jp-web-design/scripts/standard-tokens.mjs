// 暫定標準カラーの CSS を読み、:root のカスタムプロパティを var() 解決済みで返す共有モジュール。
// 正本は assets/standard/standard-color-system.css の1つだけ。JSON や検査はここから導出する。

import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

export const defaultCssPath = fileURLToPath(new URL('../assets/standard/standard-color-system.css', import.meta.url))

export async function loadTokens(cssPath = defaultCssPath) {
  const css = await readFile(cssPath, 'utf8')
  const metadataMatch = css.match(/@standard-meta\s+(\{[^\n]+\})/)
  if (!metadataMatch) throw new Error(`@standard-meta not found: ${cssPath}`)
  let metadata
  try {
    metadata = JSON.parse(metadataMatch[1])
  } catch (error) {
    throw new Error(`invalid @standard-meta: ${error.message}`)
  }
  for (const key of ['schema_version', 'name', 'version', 'date', 'status', 'theme']) {
    if (metadata[key] === undefined || metadata[key] === '') throw new Error(`@standard-meta.${key} is required`)
  }
  const root = css.match(/:root\s*\{([\s\S]*?)\n\}/)
  if (!root) throw new Error(`:root block not found: ${cssPath}`)
  const raw = Object.fromEntries(
    [...root[1].matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()])
  )
  const resolve = (name, seen = new Set()) => {
    if (seen.has(name)) throw new Error(`circular var(): --${name}`)
    seen.add(name)
    const value = raw[name]
    if (value === undefined) throw new Error(`undefined token: --${name}`)
    const ref = value.match(/^var\(--([\w-]+)\)$/)
    return ref ? resolve(ref[1], seen) : value
  }
  const resolved = Object.fromEntries(Object.keys(raw).map((name) => [name, resolve(name)]))
  return { css, metadata, raw, resolved }
}

export function isHex(value) {
  return /^#[0-9a-fA-F]{6}$/.test(value)
}

function luminance(hex) {
  const [r, g, b] = hex.match(/[0-9a-fA-F]{2}/g)
    .map((part) => Number.parseInt(part, 16) / 255)
    .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function contrast(foreground, background) {
  const a = luminance(foreground)
  const b = luminance(background)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

/** 色相(0-359度)。順序のないカテゴリの見分けは明度差ではなく色相差で作るため、系列色の間隔を測るのに使う */
export function hue(hex) {
  const [r, g, b] = hex.match(/[0-9a-fA-F]{2}/g).map((part) => Number.parseInt(part, 16) / 255)
  const max = Math.max(r, g, b)
  const delta = max - Math.min(r, g, b)
  if (delta === 0) return 0
  const sector = max === r ? ((g - b) / delta) % 6 : max === g ? (b - r) / delta + 2 : (r - g) / delta + 4
  return Math.round((sector * 60 + 360) % 360)
}

/** 2色の色相の隔たり(0-180度)。色相環は巡回するので近い側を返す */
export function hueGap(a, b) {
  const raw = Math.abs(hue(a) - hue(b))
  return Math.min(raw, 360 - raw)
}
