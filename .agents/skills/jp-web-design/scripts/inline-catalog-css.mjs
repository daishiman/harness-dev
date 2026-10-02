#!/usr/bin/env node
// assets/reference/catalog.html へ styles.css・平賀CSS・共通操作helperを埋め込み、HTML 1ファイルで共有できるようにする(手で貼らない)。
// 正本は styles.css / hiraga-color-system.css / reference-interactions.js。catalog.html の埋め込み部分は生成物。
// 使い方: node scripts/inline-catalog-css.mjs [--check]
//   --check: 埋め込み済みの CSS が正本と一致するかだけを確認する(CI用)
// 終了コード: 0=成功・一致 / 1=不一致 / 2=読込エラー

import { readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { defaultCssPath } from './hiraga-tokens.mjs'

const refPath = (name) => fileURLToPath(new URL(`../assets/reference/${name}`, import.meta.url))
const htmlPath = refPath('catalog.html')
const START = '<!-- inline-css:start (node scripts/inline-catalog-css.mjs で生成。直接編集しない) -->'
const END = '<!-- inline-css:end -->'
const JS_START = '<!-- inline-reference-interactions:start (node scripts/inline-catalog-css.mjs で生成。直接編集しない) -->'
const JS_END = '<!-- inline-reference-interactions:end -->'
const IMPORT = '@import url("../hiraga/hiraga-color-system.css");'

let html, styles, hiraga, interactions
try {
  ;[html, styles, hiraga, interactions] = await Promise.all([
    readFile(htmlPath, 'utf8'),
    readFile(refPath('styles.css'), 'utf8'),
    readFile(defaultCssPath, 'utf8'),
    readFile(refPath('reference-interactions.js'), 'utf8')
  ])
} catch (error) {
  console.error(`ERROR ${error.message}`)
  process.exit(2)
}
if (!styles.includes(IMPORT)) {
  console.error(`ERROR styles.css に ${IMPORT} が見つかりません`)
  process.exit(2)
}

// </style> を含むと埋め込みが壊れるので拒否する
const css = styles.replace(IMPORT, hiraga.trim())
if (/<\/style/i.test(css)) {
  console.error('ERROR CSS に </style が含まれています')
  process.exit(2)
}
const block = `${START}\n<style>\n${css.trim()}\n</style>\n${END}`
if (/<\/script/i.test(interactions)) {
  console.error('ERROR reference-interactions.js に </script が含まれています')
  process.exit(2)
}
const jsBlock = `${JS_START}\n<script>\n${interactions.trim()}\n</script>\n${JS_END}`

const linkTag = /<link rel="stylesheet" href="styles\.css">/
const existing = new RegExp(`${START.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[\\s\\S]*?${END}`)
let next
if (existing.test(html)) next = html.replace(existing, () => block)
else if (linkTag.test(html)) next = html.replace(linkTag, () => block)
else {
  console.error('ERROR catalog.html に styles.css の link も埋め込み範囲も見つかりません')
  process.exit(2)
}
const existingJs = new RegExp(`${JS_START.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[\\s\\S]*?${JS_END}`)
if (existingJs.test(next)) next = next.replace(existingJs, () => jsBlock)
else if (/<\/body>/.test(next)) next = next.replace('</body>', `${jsBlock}\n</body>`)
else {
  console.error('ERROR catalog.html に </body> が見つかりません')
  process.exit(2)
}

if (process.argv.includes('--check')) {
  if (next !== html) {
    console.error('FAIL catalog.html の埋め込みCSSが正本と一致しません。node scripts/inline-catalog-css.mjs で再生成してください')
    process.exit(1)
  }
  console.log('PASS catalog.html の埋め込みCSS・操作helperは正本と一致')
} else {
  await writeFile(htmlPath, next)
  console.log(`wrote ${htmlPath}`)
}
