// テスト共通: PASS/FAIL 行の出力と終了コード、使い捨てディレクトリ、スクリプト実行。

import { spawnSync } from 'node:child_process'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const skillRoot = fileURLToPath(new URL('../', import.meta.url))

let failed = false

export function check(condition, message) {
  if (condition) console.log(`PASS ${message}`)
  else {
    failed = true
    console.error(`FAIL ${message}`)
  }
}

// check が1件でも落ちていれば終了コード1。各テストの最後で呼ぶ。
export function finish() {
  if (failed) process.exitCode = 1
}

export async function withTempDir(prefix, callback) {
  const root = await mkdtemp(join(tmpdir(), prefix))
  try {
    return await callback(root)
  } finally {
    await rm(root, { recursive: true, force: true })
  }
}

// node <script> <args...> を同期実行し、stdout を JSON として読めれば json に入れて返す。
export function runScript(script, args, options = {}) {
  const result = spawnSync(process.execPath, [script, ...args], { encoding: 'utf8', ...options })
  let json = null
  try { json = JSON.parse(result.stdout) } catch {}
  return { ...result, json }
}
