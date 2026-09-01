#!/usr/bin/env node

/**
 * ファイル名を生成するスクリプト
 *
 * 命名規則: X長文投稿-prompt作成 - YYYY-MM-DD_[タイトル].md
 *
 * --title には見出し1（# タイトル）と完全に同一の文字列を渡す。
 * 見出し1がそのままファイル名のタイトル部になるため、
 * 50文字を超えるタイトルは切り詰めずエラーで停止する（絶対ルール）。
 *
 * Usage:
 *   node generate-filename.js --date 2026-02-05 --title "AIで開発環境を整えた"
 *   node generate-filename.js --date 2026-02-05 --title "AIで開発環境を整えた" --output-dir /path/to/dir
 *
 * Output:
 *   JSON形式でファイル名とパスを出力
 *
 * 終了コード: 0 = 成功 / 1 = 絶対ルール違反または出力先の解決不能 / 2 = 引数エラー
 */

const path = require("path");

const EXIT_SUCCESS = 0;
const EXIT_FAIL = 1;
const EXIT_ARGS_ERROR = 2;

// 出力先は env のみで解決する（plugin 本体に実パスを固定しないため）。
// XLP_OUTPUT_DIR が最優先、次に XLP_VAULT_ROOT/05_Project/X。
// どちらも未設定なら解決不能として停止する（fail-closed）。
// 推測したパスや他環境の既定値へ黙って書き出すと、利用者が意図しない場所へ
// ファイルが増えるため、既定値へのフォールバックは持たない。
const OUTPUT_SUBDIR = "05_Project/X";

function resolveOutputDir() {
  if (process.env.XLP_OUTPUT_DIR) return process.env.XLP_OUTPUT_DIR;
  if (process.env.XLP_VAULT_ROOT) {
    return path.join(process.env.XLP_VAULT_ROOT, OUTPUT_SUBDIR);
  }
  return null;
}

const MAX_TITLE_CHARS = 50;

function showHelp() {
  console.log(`
Usage: node generate-filename.js [options]

Options:
  --date <YYYY-MM-DD>   投稿日（必須）
  --title <string>      タイトル（必須・見出し1と完全一致・${MAX_TITLE_CHARS}文字以内）
  --output-dir <path>   出力先ディレクトリ（省略時は環境変数から解決）
  -h, --help            このヘルプを表示

出力先の解決順（--output-dir 未指定時）:
  1. XLP_OUTPUT_DIR       出力ディレクトリを直接指定
  2. XLP_VAULT_ROOT       出力先は \${XLP_VAULT_ROOT}/${OUTPUT_SUBDIR}
  どちらも未設定なら終了コード ${EXIT_FAIL} で停止する（既定値へのフォールバックはしない）。
  `);
}

function parseArgs(args) {
  const result = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "-h" || args[i] === "--help") {
      result.help = true;
    } else if (args[i] === "--date" && args[i + 1]) {
      result.date = args[++i];
    } else if (args[i] === "--title" && args[i + 1]) {
      result.title = args[++i];
    } else if (args[i] === "--output-dir" && args[i + 1]) {
      result.outputDir = args[++i];
    }
  }
  return result;
}

function countChars(title) {
  // macOS は濁点を分解して保存（NFD）することがあるため、NFC へ正規化してから数える
  return [...title.normalize("NFC")].length;
}

function sanitizeTitle(title) {
  // ファイル名に使えない文字を除去し、空白をアンダースコアへ置換する
  // 見出し1とファイル名を一致させるため、長さによる切り詰めは行わない
  return title
    .replace(/[\\/:*?"<>|]/g, "")
    .replace(/\s+/g, "_");
}

function validateDate(dateStr) {
  const pattern = /^\d{4}-\d{2}-\d{2}$/;
  if (!pattern.test(dateStr)) {
    return false;
  }
  const date = new Date(dateStr);
  return !isNaN(date.getTime());
}

function main() {
  const args = process.argv.slice(2);
  const parsed = parseArgs(args);

  if (parsed.help) {
    showHelp();
    process.exit(EXIT_SUCCESS);
  }

  if (!parsed.date) {
    console.error("Error: --date は必須です");
    showHelp();
    process.exit(EXIT_ARGS_ERROR);
  }

  if (!validateDate(parsed.date)) {
    console.error("Error: --date は YYYY-MM-DD 形式で指定してください");
    process.exit(EXIT_ARGS_ERROR);
  }

  if (!parsed.title) {
    console.error("Error: --title は必須です");
    showHelp();
    process.exit(EXIT_ARGS_ERROR);
  }

  // 出力先の解決。--output-dir が明示されていれば env は不要。
  // 明示も env もなければ推測せず停止する（fail-closed）。
  const outputDir = parsed.outputDir || resolveOutputDir();
  if (!outputDir) {
    console.error("Error: 出力先ディレクトリを解決できません");
    console.error("以下のいずれかを設定してください:");
    console.error("  XLP_OUTPUT_DIR   出力ディレクトリを直接指定");
    console.error(`  XLP_VAULT_ROOT   vault ルート（出力先は <root>/${OUTPUT_SUBDIR}）`);
    console.error("設定例:");
    console.error("  export XLP_VAULT_ROOT=\"$HOME/ObsidianVault\"");
    console.error("  export XLP_OUTPUT_DIR=\"$HOME/ObsidianVault/05_Project/X\"");
    console.error("または --output-dir <path> で直接指定してください。");
    process.exit(EXIT_FAIL);
  }

  const title = parsed.title.trim();
  const titleLength = countChars(title);

  if (titleLength === 0) {
    console.error("Error: --title が空です");
    process.exit(EXIT_FAIL);
  }

  if (titleLength > MAX_TITLE_CHARS) {
    console.error(JSON.stringify({
      ok: false,
      error: `タイトルが${MAX_TITLE_CHARS}文字を超えています（${titleLength}文字・${titleLength - MAX_TITLE_CHARS}文字超過）`,
      nextAction: "切り詰めではなく、${CLAUDE_PLUGIN_ROOT}/references/title-guidelines.md の構文パターンに沿って50文字以内へリライトし直す",
      title,
      titleLength,
      maxTitleChars: MAX_TITLE_CHARS
    }, null, 2));
    process.exit(EXIT_FAIL);
  }

  const sanitizedTitle = sanitizeTitle(title);
  const filename = `X長文投稿-prompt作成 - ${parsed.date}_${sanitizedTitle}.md`;
  const fullPath = path.join(outputDir, filename);

  const result = {
    filename,
    fullPath,
    date: parsed.date,
    originalTitle: title,
    sanitizedTitle,
    titleLength,
    maxTitleChars: MAX_TITLE_CHARS,
    outputDir
  };

  console.log(JSON.stringify(result, null, 2));
  process.exit(EXIT_SUCCESS);
}

main();
