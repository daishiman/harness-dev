#!/usr/bin/env node
// 未読込の定義や未検査の見本で色の検査をすり抜けないことを確かめる。
import { cp, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { check, finish, runScript, skillRoot, withTempDir } from './_harness.mjs'
import { required, contrastSamples } from '../scripts/standard-spec.mjs'

check(contrastSamples.every(({ fg, bg, border }) => required.some(([a, b]) => a === (border ?? fg) && b === bg)),
  'every preview contrast sample is derived from a required pair')

await withTempDir('aidd-color-contracts-', async (root) => {
  const copy = join(root, 'skill')
  await cp(skillRoot, copy, { recursive: true })
  const checker = join(copy, 'scripts/check-token-references.mjs')
  const preview = join(copy, 'assets/standard/standard-color-preview.html')
  const pop = join(copy, 'assets/reference/pop.html')
  const index = join(copy, 'assets/reference/index.html')
  const styles = join(copy, 'assets/reference/styles.css')
  const originalPreview = await readFile(preview, 'utf8')
  const originalStyles = await readFile(styles, 'utf8')
  const probe = '.contract-probe { color: var(--contract-probe-color); }'
  const insert = (html, css) => html.replace('</style>', `${css}\n</style>`)
  check(runScript(checker, []).status === 0, 'existing consumers and their loaded stylesheets pass')
  await writeFile(preview, insert(originalPreview, probe))
  await writeFile(pop, insert(await readFile(pop, 'utf8'), ':root { --contract-probe-color: #000000; }'))
  check(runScript(checker, []).status === 1, 'a separate HTML definition cannot rescue an undefined preview token')
  await writeFile(styles, `${originalStyles}\n:root { --contract-probe-color: #000000; }\n`)
  check(runScript(checker, []).status === 1, 'an unloaded stylesheet cannot rescue an undefined preview token')
  await writeFile(preview, originalPreview)
  await writeFile(index, (await readFile(index, 'utf8')).replace('</head>', `<style>${probe}</style></head>`))
  check(runScript(checker, []).status === 0, 'a loaded stylesheet supplies a local component token')
  await writeFile(preview, insert(originalPreview, `/* :root { --contract-probe-color: #000000; } */\n${probe}`))
  check(runScript(checker, []).status === 1, 'a commented declaration cannot define a token')
  await writeFile(preview, insert(originalPreview, '.contract-probe { color: var(--optional-host-color, var(--surface)); }'))
  check(runScript(checker, []).status === 0, 'an optional host token with a defined fallback is valid')

  const colorPath = join(copy, 'assets/standard/standard-color-system.css')
  const originalColor = await readFile(colorPath, 'utf8')
  await writeFile(preview, insert(originalPreview, '.contract-probe { color: var(--canonical-comment-only); }'))
  await writeFile(colorPath, originalColor.replace(':root {', ':root {\n/* --canonical-comment-only: #000000; */'))
  check(runScript(checker, []).status === 1, 'a comment in canonical CSS cannot define a token')
  for (const [token, value] of [
    ['text-inverse', 'var(--p-brand-indigo)'],
    ['action-danger-active', 'var(--p-white)'],
    ['action-secondary-active', 'var(--p-brand-indigo)']
  ]) {
    await writeFile(colorPath, originalColor.replace(new RegExp(`(--${token}:\\s*)[^;]+;`), `$1${value};`))
    check(runScript(join(copy, 'scripts/check-standard-contrast.mjs'), []).status === 1,
      `contrast rejects the low-contrast ${token} state`)
  }
})
finish()
