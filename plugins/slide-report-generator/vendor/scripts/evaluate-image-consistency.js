#!/usr/bin/env node
/**
 * evaluate-image-consistency.js
 *
 * 生成済みデッキ画像群が style-genome の一次属性(lockTiers.tier1)と consistencyAnchors を
 * 満たすかを LLM-as-judge(codex exec 経由)で 0-1 採点し、閾値割れページの「再生成推奨リスト」を出す。
 * gpt-image-2 は seed 非対応で完全再現ができないため、目視(スクショ)の前段にこの自動ゲートを置き、
 * デッキ全体の一貫性を再現可能な基準でチェックする(OpenAI Image Evals の rubric+LLM-judge 方式に準拠)。
 *
 * 重要: 破壊的操作はしない。画像を消さず、再生成もしない。推奨リストを出すだけ。
 *
 * 使用方法:
 *   node scripts/evaluate-image-consistency.js <slide-dir> [--threshold 0.8] [--dry-run] [--json]
 *
 *   --threshold  合格閾値(既定 0.8)。これ未満を再生成推奨にする。
 *   --dry-run    codex を呼ばず、各画像へ渡す評価プロンプトと rubric だけ出力(コスト無し)。
 *   --json       機械可読(NDJSON)で結果を出力。
 *
 * 自己テスト(必須):
 *   1. assets/generated/ に style-genome.json と任意の <slug>.webp(or .png)を1枚置いたテストデッキを作る。
 *   2. node scripts/evaluate-image-consistency.js <test-deck> --dry-run
 *      がエラーなく rubric と評価プロンプトを出すことを確認する(codex 不在でも落ちない)。
 *
 * 運用注意(評価バイアス):
 *   LLM-judge は position/verbosity bias を持つ。可能なら人手ラベルで較正し、閾値は保守的に。
 *   本スクリプトは一次ゲート。最終判断は必ずユーザーの目視(スクショ)で行う。
 */

import { existsSync, readdirSync, readFileSync } from 'fs';
import { join, basename, dirname } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const skillDir = join(dirname(fileURLToPath(import.meta.url)), '..');
const VALUE_FLAGS = new Set(['threshold']);

function usage() {
  console.error('Usage: node scripts/evaluate-image-consistency.js <slide-dir> [--threshold 0.8] [--dry-run] [--json]');
  process.exit(2);
}

function parseArgs(argv) {
  const flags = {};
  const positional = [];
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg.startsWith('--')) {
      const eq = arg.indexOf('=');
      if (eq !== -1) {
        flags[arg.slice(2, eq)] = arg.slice(eq + 1);
      } else {
        const name = arg.slice(2);
        if (VALUE_FLAGS.has(name)) { flags[name] = argv[i + 1]; i += 1; } else { flags[name] = true; }
      }
    } else {
      positional.push(arg);
    }
  }
  return { flags, positional };
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, "'\\''")}'`;
}

function loadGenome(generatedDir) {
  const projectLocal = join(generatedDir, 'style-genome.json');
  const bundled = join(skillDir, 'assets', 'style-genome-kanagawa-comic-diagram.json');
  const path = existsSync(projectLocal) ? projectLocal : (existsSync(bundled) ? bundled : null);
  if (!path) return null;
  try { return JSON.parse(readFileSync(path, 'utf8')); } catch { return null; }
}

// lockTiers.tier1(絶対不変属性) + consistencyAnchors を rubric 化する(デッキ共通の画風基準)。
function buildRubric(genome) {
  const criteria = [];
  if (genome && genome.lockTiers && Array.isArray(genome.lockTiers.tier1)) {
    for (const c of genome.lockTiers.tier1) criteria.push(c);
  }
  if (genome && Array.isArray(genome.consistencyAnchors)) {
    for (const c of genome.consistencyAnchors) criteria.push(c);
  }
  return criteria;
}

// D10: per-slide meta(構図の意図)を読み、デッキ共通 rubric に2-3件 append する。
// 画風の一貫性(genome)だけでなく「そのページが意図した構図・主役・禁止構成を満たすか」も採点対象にし、
// 構図崩れ(誤ノード数・主役のズレ等)を目視前の自動ゲートで拾えるようにする。meta が無ければ空配列。
function perSlideCriteria(generatedDir, stem) {
  const metaPath = join(generatedDir, `${stem}.meta.json`);
  if (!existsSync(metaPath)) return [];
  let meta;
  try { meta = JSON.parse(readFileSync(metaPath, 'utf8')); } catch { return []; }
  const extra = [];
  if (meta.layout && typeof meta.layout === 'object') {
    if (meta.layout.emphasis) extra.push(`Per-slide composition intent: ${meta.layout.emphasis}`);
    if (meta.layout.focalPoint) extra.push(`The visual focal point must be the ${meta.layout.focalPoint} area`);
  }
  if (typeof meta.negativeSpecific === 'string' && meta.negativeSpecific.trim()) {
    extra.push(`Must NOT show: ${meta.negativeSpecific.trim()}`);
  }
  // D13: illustrated-full-table は表を画像内に焼き込む。その価値(セルが崩れず正しく読める)を
  // 目視前の自動ゲートでも採点するため、列数/行数と全セルの可読性を rubric に append する。
  // meta.negativeSpecific と同じく meta.tableContent を消費し、D11 と対称な「meta -> eval」連鎖にする。
  if (meta.tableMode === 'illustrated-full-table' && meta.tableContent && typeof meta.tableContent === 'object' && Array.isArray(meta.tableContent.headers)) {
    const tc = meta.tableContent;
    const cols = tc.headers.length;
    const rowCount = Array.isArray(tc.rows) ? tc.rows.length : 0;
    extra.push(`The in-image table must have exactly ${cols} column(s) and ${rowCount} body row(s) plus a header row, with no merged, dropped, added, reordered, or garbled cells`);
    const cells = [...tc.headers, ...((Array.isArray(tc.rows) ? tc.rows : []).flat())].filter((c) => String(c).trim().length > 0);
    if (cells.length > 0) {
      extra.push(`Every table cell text must be present and clearly legible verbatim: ${cells.join(' | ')}`);
    }
  }
  return extra;
}

function buildEvalInstruction(imagePath, rubric) {
  const lines = [
    `Open and view the image file ${imagePath}.`,
    'Score how well it satisfies EACH of the following style-consistency criteria.',
    'For each criterion answer 1 (clearly satisfied), 0.5 (partially), or 0 (violated).',
    'Criteria:',
  ];
  rubric.forEach((c, i) => lines.push(`${i + 1}. ${c}`));
  lines.push('Return ONLY a compact JSON object: {"scores":[...],"overall":<average 0-1>,"notes":"<one short line>"}.');
  lines.push('Do not modify or regenerate the image. Output JSON only.');
  return lines.join(' ');
}

function main() {
  const { flags, positional } = parseArgs(process.argv.slice(2));
  const slideDir = positional[0];
  if (!slideDir) usage();

  const generatedDir = join(slideDir, 'assets', 'generated');
  if (!existsSync(generatedDir)) { console.error(`FAIL: not found: ${generatedDir}`); process.exit(1); }

  const threshold = Math.min(1, Math.max(0, parseFloat(flags.threshold || '0.8') || 0.8));
  const dryRun = Boolean(flags['dry-run']);
  const asJson = Boolean(flags.json);

  const genome = loadGenome(generatedDir);
  const rubric = buildRubric(genome);
  if (rubric.length === 0) {
    console.error('WARN: style genome has no lockTiers.tier1 / consistencyAnchors; rubric is empty. Nothing to score.');
  }

  const files = readdirSync(generatedDir);
  const stems = Array.from(new Set(
    files.filter((f) => f.endsWith('.webp') || f.endsWith('.png')).map((f) => basename(basename(f, '.webp'), '.png'))
  )).sort();
  // .webp 優先、無ければ .png
  const targets = stems.map((stem) => {
    const webp = join(generatedDir, `${stem}.webp`);
    const png = join(generatedDir, `${stem}.png`);
    return { stem, path: existsSync(webp) ? webp : png };
  }).filter((t) => existsSync(t.path));

  if (targets.length === 0) { console.error('FAIL: no .webp/.png images found to evaluate'); process.exit(1); }

  console.log(`Consistency eval: ${targets.length} image(s), threshold ${threshold}, rubric ${rubric.length} criteria`);
  if (dryRun) console.log('Mode: DRY-RUN (codex is NOT called; rubric and eval prompts only)');
  console.log('---');

  const belowThreshold = [];
  for (const { stem, path } of targets) {
    // デッキ共通 rubric に、そのページの構図意図(emphasis/focalPoint/negativeSpecific)を append する。
    const slideRubric = rubric.concat(perSlideCriteria(generatedDir, stem));
    const instruction = buildEvalInstruction(path, slideRubric);
    if (dryRun) {
      console.log(`[IMAGE] ${stem}`);
      console.log(`[EVAL ] codex exec ${shellQuote(instruction)}`);
      continue;
    }
    let score = null;
    try {
      const out = execSync(`codex exec ${shellQuote(instruction)}`, { stdio: ['ignore', 'pipe', 'pipe'] }).toString();
      const m = out.match(/\{[\s\S]*\}/);
      if (m) { const parsed = JSON.parse(m[0]); score = typeof parsed.overall === 'number' ? parsed.overall : null; }
    } catch (err) {
      console.error(`  [SKIP] ${stem}: eval failed (${err.message.slice(0, 80)})`);
      continue;
    }
    if (score === null) { console.error(`  [SKIP] ${stem}: could not parse score`); continue; }
    const ok = score >= threshold;
    if (asJson) console.log(JSON.stringify({ stem, score, pass: ok }));
    else console.log(`  ${ok ? '[PASS]' : '[LOW ]'} ${stem}: ${score.toFixed(2)}`);
    if (!ok) belowThreshold.push({ stem, score });
  }

  console.log('---');
  if (dryRun) {
    console.log(`DRY-RUN done: ${targets.length} eval prompt(s) prepared (no scoring, no cost).`);
    return;
  }
  if (belowThreshold.length > 0) {
    console.log(`Regeneration recommended (below ${threshold}): ${belowThreshold.map((b) => `${b.stem}(${b.score.toFixed(2)})`).join(', ')}`);
    console.log('This is a recommendation only; no image was deleted or regenerated. Confirm visually before regenerating.');
  } else {
    console.log(`All ${targets.length} image(s) meet the consistency threshold. Still confirm visually (screenshot).`);
  }
}

main();
