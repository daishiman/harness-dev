#!/usr/bin/env node
/**
 * deck-postgen-hook.js — プレゼン生成完了をトリガに評価を自動起動するフック入口
 *
 * Claude Code の PostToolUse フック（matcher: Write|Edit|MultiEdit）から呼ばれる。
 * stdin にフックペイロード(JSON)を受け取り、書き込まれたファイルが
 * 「スライドデッキの中核ファイル」のときだけ評価を起動する。それ以外は無音で終了し、
 * 通常の編集作業を一切妨げない（graceful・非ブロッキング）。
 *
 * 動作:
 *  1. stdin の tool_input.file_path を取得
 *  2. それが 05_Project/スライド/<deck>/ の index.html / styles.css / scripts.js / structure.* かを判定
 *     （index.deploy.html / index-single.html は除外、index.html が同階層に必要）
 *  3. デッキなら evaluate-deck.js を --static-only で高速実行（chromium不要）
 *  4. 静的サマリ＋「完全評価＋deck-evaluatorで30種思考法評価せよ」という指示を
 *     additionalContext として返し、Claude に後続評価を促す（重いdynamic/LLMはここでは走らせない）
 *
 * 設計意図（トレードオン）:
 *  - 即時・安価な静的評価は必ず走らせ（崩れ/ナビ/仕様を即フィードバック）
 *  - 重い動的(playwright)・LLM(30種思考法)評価は additionalContext で遅延誘発
 *  → 「うるさすぎ/全く動かない」「速い/精密」の両立。
 *
 * 出力契約: 常に exit 0。デッキでなければ何も出力しない。
 */

import { existsSync, readFileSync } from 'fs';
import { dirname, join, basename, resolve } from 'path';
import { spawnSync } from 'child_process';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const EVALUATOR = join(__dirname, '..', 'evaluate-deck.js');

function readStdin() {
  try {
    return readFileSync(0, 'utf-8');
  } catch {
    return '';
  }
}

function resolveDeckDir(fp) {
  if (!fp) return false;
  const base = basename(fp);
  if (/index\.(deploy|single)\.html$/.test(fp)) return false;

  const coreFiles = new Set(['index.html', 'styles.css', 'scripts.js', 'structure.md', 'structure.json']);
  if (!coreFiles.has(base)) return false;

  const dir = dirname(fp);
  // スライド出力先 or slide-*/ ディレクトリ配下であること
  const looksLikeDeck = fp.includes('/スライド/') || /slide-[^/]+\/(index\.html|styles\.css|scripts\.js|structure\.(md|json))$/.test(fp);
  if (!looksLikeDeck) return false;

  // 評価の必須入力は index.html。CSS/JS/structure 書込時も、index が存在すれば生成後評価を起動する。
  if (!existsSync(join(dir, 'index.html'))) return false;
  return dir;
}

function emit(additionalContext) {
  // PostToolUse フックの追加コンテキスト出力
  const payload = {
    hookSpecificOutput: {
      hookEventName: 'PostToolUse',
      additionalContext
    }
  };
  process.stdout.write(JSON.stringify(payload));
}

function main() {
  const raw = readStdin();
  let data = {};
  try { data = JSON.parse(raw || '{}'); } catch { data = {}; }

  const ti = data.tool_input || data.toolInput || {};
  const filePath = ti.file_path || ti.filePath || ti.path || '';

  const deckDir = resolveDeckDir(filePath);
  if (!deckDir) {
    // デッキ中核ファイルでなければ無音終了（通常編集を妨げない）
    process.exit(0);
  }

  // 静的評価（高速・chromium不要）。レポートも書き出す。
  const r = spawnSync('node', [EVALUATOR, deckDir, '--static-only', '--json'], {
    encoding: 'utf-8', timeout: 60000
  });

  let summary = '（静的評価の実行に失敗しました）';
  let verdict = 'UNKNOWN';
  try {
    const rep = JSON.parse((r.stdout || '').trim());
    verdict = rep.verdict;
    const c = rep.summary || {};
    const top = (rep.findings || [])
      .filter((f) => f.severity !== 'info')
      .slice(0, 6)
      .map((f) => `  - [${f.severity}] (${f.dimension}) ${f.title}`)
      .join('\n');
    summary =
      `静的評価サマリ: ${verdict}（error ${c.error || 0} / warn ${c.warn || 0}）\n` +
      (top ? `主な指摘:\n${top}` : '主な指摘: なし');
  } catch {
    if (r.stderr) summary += `\n${r.stderr.toString().slice(0, 200)}`;
  }

  const ctx =
    `【プレゼン生成後評価フックが起動】\n` +
    `デッキ: ${basename(deckDir)}\n` +
    `${summary}\n\n` +
    `次の評価を必ず実施すること:\n` +
    `1) 完全な機械評価（broken img・カードはみ出し・computedフォント・16:9 を含む動的検証）:\n` +
    `   node .claude/skills/presentation-slide-generator/scripts/evaluate-deck.js "${deckDir}"\n` +
    `   （Chromium未導入なら plugin root の scripts/setup-playwright.py --install 後に再実行）\n` +
    `2) deck-evaluator エージェント（思考リセット後30種思考法）を起動し、評価レポート(evaluation-report.json)を入力に\n` +
    `   D5(要望↔構成の矛盾・仕組み反映)を含む多角的・視覚的評価と4条件(矛盾なし/漏れなし/整合性/依存関係整合)の最終判定を行う。\n` +
    `   参照: .claude/skills/presentation-slide-generator/references/post-generation-evaluation.md`;

  emit(ctx);
  process.exit(0);
}

main();
