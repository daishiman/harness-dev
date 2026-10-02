// 利用側ソースの再帰走査。生成物・依存物のディレクトリは全スクリプト共通で読まない。
// 目的ごとの追加除外（例: 見本文言検査では docs/tests を読まない）は skipDirectories で足す。

import { readdir } from 'node:fs/promises'
import { join } from 'node:path'

export const GENERATED_DIRECTORIES = Object.freeze(['.git', 'node_modules', 'dist', 'build', 'coverage', '.next', '.nuxt', '.svelte-kit', '.turbo', '.wrangler'])

// accept(path, name) が true のファイルだけを名前順で返す。ignoreErrors は読めないディレクトリを黙って飛ばす。
export async function* walkSources(directory, { accept, skipDirectories = [], ignoreErrors = false }) {
  const skip = new Set([...GENERATED_DIRECTORIES, ...skipDirectories])
  let entries
  try {
    entries = await readdir(directory, { withFileTypes: true })
  } catch (error) {
    if (ignoreErrors) return
    throw error
  }
  entries.sort((a, b) => a.name.localeCompare(b.name, 'en'))
  for (const entry of entries) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) {
      if (!skip.has(entry.name)) yield* walkSources(path, { accept, skipDirectories, ignoreErrors })
    } else if (entry.isFile() && accept(path, entry.name)) {
      yield path
    }
  }
}
