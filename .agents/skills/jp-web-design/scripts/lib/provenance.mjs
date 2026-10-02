// 由来証明の共通処理: ハッシュ、証跡digest、app-root内判定、正本一式のdigest。
// catalog-default と catalog-runtime-audit が同じ正本digestを計算しないと verify が一致しないため1か所に置く。

import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { isAbsolute, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

export const skillRoot = fileURLToPath(new URL('../../', import.meta.url))
export const canonicalPaths = Object.freeze({
  profile: join(skillRoot, 'assets/reference/catalog-default-profile.json'),
  token: join(skillRoot, 'assets/hiraga/hiraga-color-system.css'),
  component: join(skillRoot, 'assets/reference/styles.css'),
  catalog: join(skillRoot, 'assets/reference/catalog.html'),
  interaction: join(skillRoot, 'assets/reference/reference-interactions.js')
})

export function sha256(value) {
  return createHash('sha256').update(value).digest('hex')
}

// evidence_digest 自身を除いた内容のハッシュ。手書き証跡の改ざん検出に使う。
export function evidenceDigest(value) {
  const clone = { ...value }
  delete clone.evidence_digest
  return sha256(JSON.stringify(clone))
}

export function isInsideRoot(root, path) {
  const rel = relative(root, resolve(path))
  return rel === '' || (!rel.startsWith(`..${sep}`) && rel !== '..' && !isAbsolute(rel))
}

// profile・色・部品CSS・カタログ・操作JSのどれが変わっても digest が変わる。
export async function loadCanonicalSources() {
  const [profileBody, token, component, catalog, interaction] = await Promise.all(
    ['profile', 'token', 'component', 'catalog', 'interaction'].map((name) => readFile(canonicalPaths[name], 'utf8'))
  )
  const profile = JSON.parse(profileBody)
  return { profile, token, component, catalog, interaction, digest: sha256(JSON.stringify(profile) + token + component + catalog + interaction) }
}
