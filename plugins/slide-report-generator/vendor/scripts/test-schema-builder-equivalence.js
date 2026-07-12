#!/usr/bin/env node
/**
 * test-schema-builder-equivalence.js
 *
 * 目的(L-06 対策・elegant-review 再検証で確定):
 *   schemas/image-deck-plan.schema.json の allOf 条件分岐(宣言的)と
 *   scripts/build-image-prompts.js の validateSlide(手続き的)は「同値」と複数箇所に明記されているが、
 *   別言語・別ファイルの二重宣言のため、片方だけ変更(例: minLength 20->30、トリガ条件追加)すると
 *   もう片方が取り残されるドリフトを機械的に検出できなかった。
 *
 *   本テストは「実際の schema ファイルの allOf を毎回読み取って評価する mini-evaluator」と
 *   「builder を CLI で黒箱実行した accept/reject」を、同一スライドの一連の変異(mutation)に対して
 *   突き合わせ、両者が常に一致することを assert する。schema か builder のどちらかを編集して同値が
 *   崩れると、いずれかの境界ケースで不一致になり本テストが FAIL する(ドリフト検出)。
 *
 *   対象は schema.allOf で二重宣言されている条件分岐(pattern x textPolicy/backgroundSource、
 *   baked-with-overlay->bakedText、camera=structural->negativeSpecific、
 *   illustrated-full-table->tableContent/textPolicy/negativeSpecific)に限定する。
 *   セル文字数(schema maxLength)・monospaceColumns 範囲(builder 専用)・accent 警告などの
 *   builder 追加検査は本テストの対象外(別の負テストで担保)。
 *
 * 実行:
 *   node scripts/test-schema-builder-equivalence.js
 *   -> 全ケースで builder と schema allOf が一致すれば PASS(exit 0)、不一致があれば FAIL(exit 1)。
 *
 * 注意: 破壊的操作はしない。OS 一時ディレクトリに使い捨てデッキを作り、終了時に削除する。
 */

import { existsSync, readFileSync, writeFileSync, mkdirSync, mkdtempSync, rmSync, copyFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { tmpdir } from 'os';
import { execFileSync } from 'child_process';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const skillDir = join(scriptDir, '..');
const schemaPath = join(skillDir, 'schemas', 'image-deck-plan.schema.json');
const samplePath = join(scriptDir, 'test-fixtures', 'image-deck-plan.sample.json');
const genomePath = join(skillDir, 'assets', 'style-genome-kanagawa-comic-diagram.json');
const builderPath = join(scriptDir, 'build-image-prompts.js');

function fail(msg) {
  console.error(`FAIL: ${msg}`);
  process.exit(1);
}

for (const [label, p] of [['schema', schemaPath], ['sample', samplePath], ['genome', genomePath], ['builder', builderPath]]) {
  if (!existsSync(p)) fail(`required ${label} not found: ${p}`);
}

const schema = JSON.parse(readFileSync(schemaPath, 'utf8'));
const sample = JSON.parse(readFileSync(samplePath, 'utf8'));
const allOf = (schema.definitions && schema.definitions.slide && schema.definitions.slide.allOf) || [];
if (allOf.length === 0) fail('schema.definitions.slide.allOf is empty; nothing to cross-check');

// ===== mini allOf evaluator =====
// 本 schema の allOf が使う機能だけを評価する: if.properties[k].const / if.required、
// then.required / then.properties[k].{const, enum, minLength(string), minItems(array)}。
function ifMatches(slide, ifSpec) {
  if (!ifSpec) return false;
  if (Array.isArray(ifSpec.required)) {
    for (const k of ifSpec.required) {
      if (slide[k] === undefined || slide[k] === null) return false;
    }
  }
  const props = ifSpec.properties || {};
  for (const [k, cond] of Object.entries(props)) {
    if ('const' in cond) {
      if (slide[k] !== cond.const) return false;
    } else if (Array.isArray(cond.enum)) {
      if (!cond.enum.includes(slide[k])) return false;
    }
  }
  return true;
}

function thenViolations(slide, thenSpec) {
  const v = [];
  if (!thenSpec) return v;
  if (Array.isArray(thenSpec.required)) {
    for (const k of thenSpec.required) {
      if (slide[k] === undefined || slide[k] === null) v.push(`required "${k}" missing`);
    }
  }
  const props = thenSpec.properties || {};
  for (const [k, cond] of Object.entries(props)) {
    const val = slide[k];
    if (val === undefined || val === null) continue; // 存在検査は required 側が担う
    if ('const' in cond && val !== cond.const) v.push(`"${k}" must be const ${JSON.stringify(cond.const)} (got ${JSON.stringify(val)})`);
    if (Array.isArray(cond.enum) && !cond.enum.includes(val)) v.push(`"${k}" must be one of ${JSON.stringify(cond.enum)} (got ${JSON.stringify(val)})`);
    if (typeof cond.minLength === 'number' && typeof val === 'string' && val.trim().length < cond.minLength) v.push(`"${k}" must be >= ${cond.minLength} chars`);
    if (typeof cond.minItems === 'number' && Array.isArray(val) && val.length < cond.minItems) v.push(`"${k}" must have >= ${cond.minItems} items`);
  }
  return v;
}

function evalSchemaAllOf(slide) {
  const violations = [];
  for (const entry of allOf) {
    if (ifMatches(slide, entry.if)) {
      violations.push(...thenViolations(slide, entry.then).map((m) => `[${entry.description ? entry.description.slice(0, 24) : 'allOf'}] ${m}`));
    }
  }
  return { pass: violations.length === 0, violations };
}

// ===== builder を CLI で黒箱実行(accept/reject) =====
const workRoot = mkdtempSync(join(tmpdir(), 'img-equiv-'));
const generatedDir = join(workRoot, 'assets', 'generated');
mkdirSync(generatedDir, { recursive: true });
copyFileSync(genomePath, join(generatedDir, 'style-genome.json'));

function builderAccepts(slide) {
  const plan = { styleGenome: 'assets/generated/style-genome.json', slides: [slide] };
  writeFileSync(join(generatedDir, 'image-deck-plan.json'), JSON.stringify(plan, null, 2));
  try {
    // --check で書き込みせず検証のみ。validateSlide は check/write 前に走り、不正なら exit 1。
    execFileSync('node', [builderPath, workRoot, '--check'], { stdio: ['ignore', 'ignore', 'ignore'] });
    return true;
  } catch {
    return false;
  }
}

function clone(obj) { return JSON.parse(JSON.stringify(obj)); }

const baseTable = sample.slides.find((s) => s.tableMode === 'illustrated-full-table');
const baseDefault = sample.slides.find((s) => s.camera === 'default' && s.tableMode !== 'illustrated-full-table');
if (!baseTable || !baseDefault) fail('sample fixture must contain an illustrated-full-table slide and a camera=default slide');

// allOf で二重宣言された不変条件のみを変異させる(builder 追加検査には触れない)。
// expect は schema/builder 双方の期待 accept/reject。両者が一致しなければドリフト。
const cases = [
  { name: 'baseline full-table valid', base: baseTable, mutate: () => {}, expect: 'accept' },
  { name: 'baseline default slide valid', base: baseDefault, mutate: () => {}, expect: 'accept' },

  // D11 camera=structural -> negativeSpecific 必須(>=20)
  { name: 'default->structural without negativeSpecific', base: baseDefault, mutate: (s) => { s.camera = 'structural'; delete s.negativeSpecific; }, expect: 'reject' },
  { name: 'default->structural with short negativeSpecific(19)', base: baseDefault, mutate: (s) => { s.camera = 'structural'; s.negativeSpecific = 'x'.repeat(19); }, expect: 'reject' },
  { name: 'default->structural with negativeSpecific(20)', base: baseDefault, mutate: (s) => { s.camera = 'structural'; s.negativeSpecific = 'no extra or missing nodes here ok'; }, expect: 'accept' },

  // D12 illustrated-full-table -> tableContent + textPolicy=baked-with-overlay + negativeSpecific(>=20)
  { name: 'full-table remove negativeSpecific', base: baseTable, mutate: (s) => { delete s.negativeSpecific; }, expect: 'reject' },
  { name: 'full-table negativeSpecific too short(19)', base: baseTable, mutate: (s) => { s.negativeSpecific = 'y'.repeat(19); }, expect: 'reject' },

  // pattern x textPolicy/backgroundSource
  { name: 'image-only with backgroundSource=raster', base: baseDefault, mutate: (s) => { s.backgroundSource = 'raster'; }, expect: 'reject' },
  { name: 'image-only with textPolicy=none', base: baseDefault, mutate: (s) => { s.textPolicy = 'none'; }, expect: 'reject' },

  // baked-with-overlay -> bakedText 必須
  { name: 'baked-with-overlay remove bakedText', base: baseDefault, mutate: (s) => { delete s.bakedText; }, expect: 'reject' },
];

let mismatches = 0;
let expectFails = 0;
console.log(`Schema<->builder equivalence: ${cases.length} case(s), allOf rules ${allOf.length}`);
console.log('---');
for (const c of cases) {
  const slide = clone(c.base);
  c.mutate(slide);
  const builder = builderAccepts(slide) ? 'accept' : 'reject';
  const schemaRes = evalSchemaAllOf(slide);
  const schemaVerdict = schemaRes.pass ? 'accept' : 'reject';

  const agree = builder === schemaVerdict;
  const meetsExpect = builder === c.expect && schemaVerdict === c.expect;
  if (!agree) mismatches += 1;
  if (!meetsExpect) expectFails += 1;

  const flag = agree && meetsExpect ? 'OK  ' : 'BAD ';
  console.log(`${flag}${c.name}: builder=${builder} schema=${schemaVerdict} expect=${c.expect}`);
  if (!agree) console.log(`     DRIFT: builder and schema disagree (schema violations: ${schemaRes.violations.join(' | ') || 'none'})`);
  else if (!meetsExpect) console.log(`     EXPECT-MISS: both gave ${builder} but expected ${c.expect}`);
}
console.log('---');

// 後始末(使い捨てデッキ削除)。
try { rmSync(workRoot, { recursive: true, force: true }); } catch { /* ignore */ }

if (mismatches > 0) {
  fail(`${mismatches} case(s) where schema allOf and builder validateSlide DISAGREE (drift between the two duplicated declarations).`);
}
if (expectFails > 0) {
  fail(`${expectFails} case(s) where the agreed verdict did not match the expected accept/reject (a shared invariant changed).`);
}
console.log(`PASS: schema allOf and builder validateSlide agree on all ${cases.length} equivalence case(s).`);
