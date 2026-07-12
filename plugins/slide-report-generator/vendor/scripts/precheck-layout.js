#!/usr/bin/env node
/**
 * precheck-layout — 全スライド一括レイアウト事前チェック
 *
 * Phase 3（HTML 生成）の直前に実行する必須ゲート。
 * layout-calculator のロジックを全スライドに適用し、はみ出しリスクを早期検出する。
 *
 * 使用方法:
 *   node scripts/precheck-layout.js <structure-path> [--format=json|text]
 *
 * 終了コード:
 *   0 = PASS（全スライドが安全マージン内）
 *   1 = FAIL（>95% 使用 or カード単独 overflow が 1 枚以上ある → 構成側に差し戻し）
 *   2 = WARN（85-95% 使用が 1 枚以上ある → ユーザー警告のうえ生成可）
 *   3 = ARGS_ERROR / FILE_NOT_FOUND
 */

import { existsSync } from 'fs';
import { parseArgs, hasFlag } from './utils.js';
import { loadStructure, evaluateSlide } from './layout-calculator.js';

const EXIT = { PASS: 0, FAIL: 1, WARN: 2, ARGS_ERROR: 3 };

const { flags, positional, options } = parseArgs();

if (hasFlag(flags, 'help', 'h')) {
  console.log(`precheck-layout <structure-path> [--format=json|text]
  終了コード: 0=PASS, 1=FAIL, 2=WARN, 3=ARGS_ERROR`);
  process.exit(EXIT.PASS);
}

const inputPath = positional[0];
const jsonOutput = options.format === 'json' || hasFlag(flags, 'json');

if (!inputPath) {
  console.error('ERROR: structure ファイルパスを指定してください');
  process.exit(EXIT.ARGS_ERROR);
}
if (!existsSync(inputPath)) {
  console.error(`ERROR: ファイルが見つかりません: ${inputPath}`);
  process.exit(EXIT.ARGS_ERROR);
}

const structure = loadStructure(inputPath);
const slides = Array.isArray(structure) ? structure : (structure.slides || []);

if (!slides.length) {
  console.error('ERROR: スライド配列が見つかりません（slides[]）');
  process.exit(EXIT.ARGS_ERROR);
}

const reports = slides.map(evaluateSlide);
const fail = reports.filter(r => r.verdict === 'FAIL');
const warn = reports.filter(r => r.verdict === 'WARN');
const pass = reports.filter(r => r.verdict === 'PASS');

const overall = fail.length ? 'FAIL' : warn.length ? 'WARN' : 'PASS';

const summary = {
  file: inputPath,
  total: reports.length,
  pass: pass.length,
  warn: warn.length,
  fail: fail.length,
  overall,
  failedSlides: fail.map(r => ({ id: r.id, type: r.type, usageRatio: r.usageRatio, recommendations: r.recommendations })),
  warnedSlides: warn.map(r => ({ id: r.id, type: r.type, usageRatio: r.usageRatio, recommendations: r.recommendations })),
};

if (jsonOutput) {
  console.log(JSON.stringify(summary, null, 2));
} else {
  console.log('================================================================');
  console.log('  precheck-layout: Phase 3 開始前ゲート');
  console.log('================================================================');
  console.log(`File: ${inputPath}`);
  console.log(`Total: ${summary.total} slides`);
  console.log(`  PASS: ${summary.pass}`);
  console.log(`  WARN: ${summary.warn}`);
  console.log(`  FAIL: ${summary.fail}`);
  console.log('');

  if (fail.length) {
    console.log('--- FAIL（差し戻し対象）---');
    for (const r of fail) {
      console.log(`[FAIL] slide=${r.id} type=${r.type} usage=${(r.usageRatio * 100).toFixed(1)}%`);
      for (const rec of r.recommendations) console.log(`     > ${rec}`);
    }
    console.log('');
  }
  if (warn.length) {
    console.log('--- WARN（警告のうえ生成可）---');
    for (const r of warn) {
      console.log(`[WARN] slide=${r.id} type=${r.type} usage=${(r.usageRatio * 100).toFixed(1)}%`);
      for (const rec of r.recommendations) console.log(`     > ${rec}`);
    }
    console.log('');
  }
  console.log(`Overall: ${overall}`);
  if (overall === 'FAIL') {
    console.log('=> structure-designer に差し戻してください（HTML生成しない）');
  } else if (overall === 'WARN') {
    console.log('=> ユーザーに警告を提示したうえで生成可');
  } else {
    console.log('=> PASS — Phase 3 へ進めます');
  }
}

process.exit(overall === 'FAIL' ? EXIT.FAIL : overall === 'WARN' ? EXIT.WARN : EXIT.PASS);
