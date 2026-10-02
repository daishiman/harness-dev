#!/usr/bin/env node

import assert from 'node:assert/strict'
import { cp, mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { runScript, skillRoot, withTempDir } from './_harness.mjs'
import { loadTokens } from '../scripts/hiraga-tokens.mjs'

const script = join(skillRoot, 'scripts', 'migrate-legacy-colors.mjs')
const fixtures = join(skillRoot, 'tests', 'fixtures', 'migrate-legacy-colors')

// migrate-legacy-colors は「現行パレットの解決値と一致する生HEX」だけをトークンへ畳む。
// fixture がHEXをリテラルで持つ以上、正本の色を動かすと fixture は静かに陳腐化する。
// ここで先に検出しておかないと、本体のアサーションが「変換されない」という分かりにくい形で落ちる。
// 8桁(alpha)と3桁は対象外。変換されない側の fixture なのでそのままでよい。
async function assertFixtureHexesMatchPalette() {
  const { resolved } = await loadTokens()
  const paletteHexes = new Set(
    Object.values(resolved).filter((v) => /^#[0-9A-Fa-f]{6}$/.test(v)).map((v) => v.toUpperCase())
  )
  const stale = []
  for (const name of await readdir(fixtures)) {
    const dir = join(fixtures, name)
    for (const file of await readdir(dir, { recursive: true })) {
      if (!/\.(css|scss)$/.test(file)) continue
      const source = await readFile(join(dir, file), 'utf8')
      for (const [hex] of source.matchAll(/#[0-9A-Fa-f]{6}(?![0-9A-Fa-f])/g)) {
        if (!paletteHexes.has(hex.toUpperCase())) stale.push(`${name}/${file}: ${hex}`)
      }
    }
  }
  assert.deepEqual(
    stale,
    [],
    `fixture のHEXが現行パレットに無くなっています。正本 assets/hiraga/hiraga-color-system.css の値へ更新してください:\n  ${stale.join('\n  ')}`
  )
}
await assertFixtureHexesMatchPalette()

async function withFixture(name, callback) {
  await withTempDir(`hiraga-migration-${name}-`, async (temp) => {
    const root = join(temp, name)
    await cp(join(fixtures, name), root, { recursive: true })
    await callback(root)
  })
}

function run(root, ...args) {
  const result = runScript(script, [root, ...args, '--json'])
  assert.notEqual(result.status, 2, result.stderr || result.stdout)
  assert.equal(result.stderr, '')
  return { ...result, report: result.json }
}

function runWithFault(root, faults) {
  return runScript(script, [root, '--apply', '--json'], {
    env: { ...process.env, NODE_ENV: 'test', AIDD_MIGRATION_TEST_FAULT: faults }
  })
}

await withFixture('safe', async (root) => {
  const dry = run(root)
  assert.equal(dry.status, 1)
  assert.equal(dry.report.schema_version, '1.0')
  assert.equal(dry.report.mode, 'dry-run')
  assert.equal(dry.report.eligibility.status, 'eligible')
  assert.equal(dry.report.summary.safe, 2)
  assert.equal(dry.report.summary.detected, 2)
  assert.equal(dry.report.summary.planned_files, 1)
  assert.equal(dry.report.summary.changed_files, 0)
  assert.ok(dry.report.items.every((item) => item.automation === 'safe' && item.status === 'detected'))

  const plan = run(root, '--plan')
  assert.equal(plan.status, 1)
  assert.equal(plan.report.mode, 'plan')
  assert.equal(plan.report.summary.planned, 2)
  assert.equal(plan.report.transaction.planned_files, 1)
  assert.equal(await readFile(join(root, 'input.css'), 'utf8'), await readFile(join(fixtures, 'safe', 'input.css'), 'utf8'))

  const applied = run(root, '--apply')
  assert.equal(applied.status, 0)
  assert.equal(applied.report.mode, 'apply')
  assert.equal(applied.report.summary.applied, 2)
  assert.equal(applied.report.transaction.strategy, 'stage-then-rename-with-rollback')
  assert.equal(await readFile(join(root, 'input.css'), 'utf8'), await readFile(join(root, 'expected.txt'), 'utf8'))

  const second = run(root, '--apply')
  assert.equal(second.status, 0)
  assert.equal(second.report.summary.total, 0)
  assert.equal(second.report.summary.changed_files, 0)
})

await withFixture('review-only', async (root) => {
  const before = await readFile(join(root, 'input.css'), 'utf8')
  const applied = run(root, '--apply')
  assert.equal(applied.status, 1)
  assert.equal(await readFile(join(root, 'input.css'), 'utf8'), before)
  assert.equal(applied.report.summary.applied, 0)
  assert.equal(applied.report.summary.review_only, 3)
  assert.ok(applied.report.items.every((item) => item.automation === 'review-only' && item.status === 'unchanged'))
})

for (const name of ['pop', 'external-brand']) {
  await withFixture(name, async (root) => {
    const file = name === 'pop' ? 'pop-theme.css' : 'brand.css'
    const before = await readFile(join(root, file), 'utf8')
    const applied = run(root, '--apply')
    assert.equal(await readFile(join(root, file), 'utf8'), before)
    assert.equal(applied.report.summary.applied, 0)
    assert.equal(applied.report.summary.excluded_files, 1)
    assert.ok(applied.report.items.every((item) => item.type === 'eligibility' && item.status === 'excluded'))
  })
}

for (const [name, sourceTheme] of [['pop-gate', 'undetermined'], ['external-brand-gate', 'external-brand']]) {
  await withFixture(name, async (root) => {
    const before = await readFile(join(root, 'input.css'), 'utf8')
    const applied = run(root, '--apply')
    assert.equal(applied.report.eligibility.status, 'report-only')
    assert.equal(applied.report.eligibility.source_theme, sourceTheme)
    assert.equal(applied.report.summary.applied, 0)
    assert.equal(await readFile(join(root, 'input.css'), 'utf8'), before)
  })
}

await withFixture('unspecified-template', async (root) => {
  const applied = run(root, '--apply')
  assert.equal(applied.report.eligibility.status, 'eligible')
  assert.equal(applied.report.eligibility.source_theme, 'unspecified')
  assert.match(await readFile(join(root, 'input.css'), 'utf8'), /color: var\(--text-heading\)/)
})

await withFixture('t2-approved-external', async (root) => {
  const cssPath = join(root, 'src', 'input.css')
  const before = await readFile(cssPath, 'utf8')
  const applied = run(root, '--apply')
  assert.equal(applied.status, 1)
  assert.equal(applied.report.eligibility.status, 'report-only')
  assert.equal(applied.report.eligibility.source_theme, 'external-brand')
  assert.ok(applied.report.eligibility.evidence.includes('docs/product/T2-experience-spec.md'))
  assert.equal(applied.report.summary.applied, 0)
  assert.equal(await readFile(cssPath, 'utf8'), before)
})

await withFixture('t2-approved-only', async (root) => {
  const applied = run(root, '--apply')
  assert.equal(applied.status, 1)
  assert.equal(applied.report.eligibility.status, 'report-only')
  assert.equal(applied.report.eligibility.source_theme, 'external-brand')
  assert.equal(applied.report.summary.total, 0)
  assert.equal(applied.report.summary.changed_files, 0)
})

await withFixture('multiple-declarations', async (root) => {
  const applied = run(root, '--apply')
  assert.equal(applied.status, 0)
  assert.equal(await readFile(join(root, 'input.css'), 'utf8'), await readFile(join(root, 'expected.txt'), 'utf8'))
  assert.deepEqual(applied.report.items.map((item) => item.new_value), [
    'var(--text-heading)',
    'var(--surface)',
    'var(--border-control)'
  ])
})

await withFixture('unsupported', async (root) => {
  const plan = run(root, '--plan')
  assert.equal(plan.status, 1)
  assert.equal(plan.report.mode, 'plan')
  assert.ok(plan.report.items.some((item) => item.type === 'theme' && item.automation === 'manual'))
  assert.ok(plan.report.items.some((item) => item.type === 'unsupported-syntax' && item.old_value.includes('rgb(')))
  // 検査したいのは「alpha付きHEXは自動適用しない」こと。どの色かは無関係なので値を固定しない
  assert.ok(plan.report.items.some((item) => item.type === 'unsupported-syntax' && /^#[0-9A-Fa-f]{8}$/.test(item.old_value)))
  assert.match(plan.report.supported_syntax.direct_colors, /#RGB/)
})

await withFixture('transaction', async (root) => {
  const aPath = join(root, 'a.css')
  const bPath = join(root, 'b.css')
  const [aBefore, bBefore] = await Promise.all([readFile(aPath, 'utf8'), readFile(bPath, 'utf8')])
  const failed = runWithFault(root, 'commit-after-first')
  assert.equal(failed.status, 2)
  assert.match(failed.stderr, /ERROR transaction rolled back: injected fault: commit-after-first/)
  assert.doesNotMatch(failed.stderr, /rollback incomplete/)
  assert.equal(await readFile(aPath, 'utf8'), aBefore)
  assert.equal(await readFile(bPath, 'utf8'), bBefore)
  assert.ok((await readdir(root)).every((name) => !name.includes('.hiraga-migration-')))
})

await withFixture('transaction', async (root) => {
  const aPath = join(root, 'a.css')
  const bPath = join(root, 'b.css')
  const [aBefore, bBefore] = await Promise.all([readFile(aPath, 'utf8'), readFile(bPath, 'utf8')])
  const failed = runWithFault(root, 'commit-after-first,rollback-before-restore')
  assert.equal(failed.status, 2)
  assert.match(failed.stderr, /ERROR transaction rollback incomplete:/)
  assert.match(failed.stderr, /backups preserved:/)
  assert.doesNotMatch(failed.stderr, /ERROR transaction rolled back:/)
  const entries = await readdir(root)
  const backup = entries.find((name) => name.startsWith('.a.css.hiraga-migration-') && name.endsWith('.backup'))
  assert.ok(backup, 'rollback失敗時はpreimage backupを保持する')
  assert.equal(await readFile(join(root, backup), 'utf8'), aBefore)
  assert.equal(await readFile(bPath, 'utf8'), bBefore)
  assert.ok(!entries.some((name) => name.endsWith('.staged')))
  await assert.rejects(readFile(aPath, 'utf8'), { code: 'ENOENT' })
})

await withFixture('safe', async (root) => {
  // 生成物ディレクトリは catalog-default と共通の除外集合で読まない（.nuxt/.turbo を含む）。
  for (const generated of ['.nuxt', '.turbo', 'node_modules']) {
    await mkdir(join(root, generated), { recursive: true })
    await writeFile(join(root, generated, 'legacy.css'), '.x { color: var(--ink); }\n')
  }
  const dry = run(root)
  assert.ok(dry.report.items.every((item) => item.file === 'input.css'), 'generated directories are not scanned')

  const typo = runScript(script, [root, '--aply'])
  assert.equal(typo.status, 2, 'unknown options are input errors')
  assert.match(typo.stderr, /unknown option: --aply[\s\S]*usage: migrate-legacy-colors\.mjs/)
  assert.equal(runScript(script, [root, '--plan', '--apply']).status, 2)
  assert.equal(runScript(script, []).status, 2)
})

console.log('PASS migrate-legacy-colors fixtures (T2 brand SSOT / dry-run-plan-apply / safe-review / eligibility / syntax / idempotence / rollback success-failure)')
