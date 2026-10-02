#!/usr/bin/env node
// 各ファイルの var(--x) が、正本CSSかそのファイル自身で定義されたトークンを指しているかを検査する。
// 未定義トークンは CSS では静かに無視され、色が消えても検査もブラウザーも何も言わない。
// v0.3 の改名 (--p-brand-magenta → --p-brand-accent) で見本の3か所が実際にこうなった。
// 使い方: node scripts/check-token-references.mjs
// 終了コード: 0=全PASS / 1=未定義参照あり / 2=読込エラー

import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { loadTokens } from './hiraga-tokens.mjs'

// 正本のトークンを使う側のファイル。ここに足し忘れると検査の外に出るので、色を使うCSS/HTMLは必ず載せる
const CONSUMERS = [
  '../assets/hiraga/hiraga-color-preview.html',
  '../assets/reference/styles.css',
  '../assets/reference/catalog.html',
  '../assets/reference/index.html',
  '../assets/reference/pop.html'
]

let master
try {
  ;({ raw: master } = await loadTokens())
} catch (error) {
  console.error(`ERROR ${error.message}`)
  process.exit(2)
}

const sources = new Map()
for (const relative of CONSUMERS) {
  try {
    sources.set(relative, await readFile(fileURLToPath(new URL(relative, import.meta.url)), 'utf8'))
  } catch (error) {
    console.error(`ERROR ${error.message}`)
    process.exit(2)
  }
}
// 定義は正本CSSと、キット内で互いに読み込み合うこれらのファイル (styles.css は部品用トークンを自前で持ち、
// pop.html / index.html はそれを読み込む。--stagger のように style 属性で渡すものもある) の和で判定する
const defined = new Set(Object.keys(master))
for (const text of sources.values()) {
  for (const match of text.matchAll(/--([\w-]+)\s*:/g)) defined.add(match[1])
}

let failed = false
for (const [relative, text] of sources) {
  const missing = new Map()
  for (const match of text.matchAll(/var\(\s*--([\w-]+)/g)) {
    const name = match[1]
    if (defined.has(name)) continue
    const line = text.slice(0, match.index).split('\n').length
    if (!missing.has(name)) missing.set(name, line)
  }
  const name = relative.replace('../', '')
  if (missing.size === 0) {
    console.log(`PASS ${name} の var() は全て定義済み`)
  } else {
    failed = true
    for (const [token, line] of missing) console.error(`FAIL ${name}:${line} 未定義のトークンを参照: --${token}`)
  }
}

if (failed) process.exitCode = 1
