#!/usr/bin/env node
// consumer自身と、実際に読み込むstylesheetの定義だけでvar()を検査する。
// 別HTMLの局所定義で未定義参照を救済しない。fallback付きvar()は未定義でも有効。
// 使い方: node scripts/check-token-references.mjs
// 終了コード: 0=全PASS / 1=未定義参照あり / 2=読込エラー

import { readFile } from 'node:fs/promises'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { loadTokens } from './standard-tokens.mjs'

const CONSUMERS = [
  '../assets/standard/standard-color-preview.html',
  '../assets/reference/styles.css',
  '../assets/reference/catalog.html',
  '../assets/reference/index.html',
  '../assets/reference/pop.html'
]
const withoutComments = (text) => text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '')
const attribute = (tag, name) => tag.match(new RegExp(`\\b${name}\\s*=\\s*(["'])(.*?)\\1`, 'i'))?.[2]

function cssOf(text, path) {
  const source = withoutComments(text)
  if (path.endsWith('.css')) return source
  return [
    ...[...source.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)].map((match) => match[1]),
    ...[...source.matchAll(/\bstyle\s*=\s*(["'])([\s\S]*?)\1/gi)].map((match) => match[2])
  ].join('\n')
}

function importsOf(text, css, path) {
  const links = path.endsWith('.css') ? [] : [...withoutComments(text).matchAll(/<link\b[^>]*>/gi)]
    .filter((match) => attribute(match[0], 'rel')?.split(/\s+/).includes('stylesheet'))
    .map((match) => attribute(match[0], 'href'))
  const imports = [...css.matchAll(/@import\s+(?:url\(\s*(["']?)([^\s)"']+)\1\s*\)|(["'])(.*?)\3)/gi)]
    .map((match) => match[2] || match[4])
  return [...links, ...imports].filter((ref) => ref && !/^(?:[a-z][\w+.-]*:|\/\/|#)/i.test(ref))
}

const cache = new Map()
async function source(path) {
  if (!cache.has(path)) cache.set(path, await readFile(path, 'utf8'))
  return cache.get(path)
}

async function definitionsOf(path, seen = new Set()) {
  if (seen.has(path)) return []
  seen.add(path)
  const text = await source(path)
  const css = cssOf(text, path)
  const definitions = [...css.matchAll(/--([\w-]+)\s*:/g)].map((match) => match[1])
  for (const ref of importsOf(text, css, path)) {
    definitions.push(...await definitionsOf(fileURLToPath(new URL(ref, pathToFileURL(path))), seen))
  }
  return definitions
}

try {
  const { raw: master } = await loadTokens()
  let failed = false
  for (const relative of CONSUMERS) {
    const path = fileURLToPath(new URL(relative, import.meta.url))
    const text = await source(path)
    const css = cssOf(text, path)
    const defined = new Set([...Object.keys(master), ...await definitionsOf(path)])
    const missing = new Set()
    for (const match of css.matchAll(/var\(\s*--([\w-]+)\s*([,)])/g)) {
      if (!defined.has(match[1]) && match[2] !== ',') missing.add(match[1])
    }
    const name = relative.replace('../', '')
    if (!missing.size) console.log(`PASS ${name} の var() は全て定義済み、またはfallbackあり`)
    else {
      failed = true
      for (const token of missing) console.error(`FAIL ${name} 未定義のトークンを参照: --${token}`)
    }
  }
  if (failed) process.exitCode = 1
} catch (error) {
  console.error(`ERROR ${error.message}`)
  process.exitCode = 2
}
