#!/usr/bin/env node

/**
 * 00ネタファイル更新スクリプト
 *
 * 00ネタファイルのリスト最上部に新規投稿リンクを追記する
 *
 * Usage:
 *   node update-neta-file.js --neta-file <path> --filename "X長文投稿-prompt作成 - 2026-02-05_タイトル.md"
 *
 * Output:
 *   JSON形式で更新結果を出力
 */

const fs = require("fs");

const EXIT_SUCCESS = 0;
const EXIT_ARGS_ERROR = 2;
const EXIT_FILE_ERROR = 3;

function showHelp() {
  console.log(`
Usage: node update-neta-file.js [options]

Options:
  --neta-file <path>    00ネタファイルのパス（必須）
  --filename <string>   追加するファイル名（.md拡張子含む）（必須）
  --dry-run             実際には更新せず、結果のみ表示
  -h, --help            このヘルプを表示
  `);
}

function parseArgs(args) {
  const result = { dryRun: false };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "-h" || args[i] === "--help") {
      result.help = true;
    } else if (args[i] === "--neta-file" && args[i + 1]) {
      result.netaFile = args[++i];
    } else if (args[i] === "--filename" && args[i + 1]) {
      result.filename = args[++i];
    } else if (args[i] === "--dry-run") {
      result.dryRun = true;
    }
  }
  return result;
}

function findInsertPosition(content) {
  // チェックボックスリストの先頭を探す
  // パターン: "- [ ] [[" で始まる行
  const lines = content.split("\n");

  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim().startsWith("- [ ] [[")) {
      return i;
    }
  }

  // 見つからない場合は最後に追加
  return lines.length;
}

function linkNameOf(filename) {
  // .md拡張子を除いたWikiリンク名
  return filename.replace(/\.md$/, "");
}

function generateLink(filename) {
  return `- [ ] [[${linkNameOf(filename)}]]`;
}

/**
 * 同一ファイル名のリンクが既に存在するか判定する。
 * チェック状態（- [ ] / - [x]）や表示名（|エイリアス）の違いは無視し、
 * NFC 正規化した Wikilink 名の完全一致で判定する。
 */
function hasExistingLink(content, filename) {
  const target = linkNameOf(filename).normalize("NFC").trim();
  const re = /\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]/g;
  const normalized = content.normalize("NFC");
  let m;
  while ((m = re.exec(normalized)) !== null) {
    if (m[1].trim() === target) return true;
  }
  return false;
}

function main() {
  const args = process.argv.slice(2);
  const parsed = parseArgs(args);

  if (parsed.help) {
    showHelp();
    process.exit(EXIT_SUCCESS);
  }

  if (!parsed.netaFile) {
    console.error("Error: --neta-file は必須です");
    showHelp();
    process.exit(EXIT_ARGS_ERROR);
  }

  if (!parsed.filename) {
    console.error("Error: --filename は必須です");
    showHelp();
    process.exit(EXIT_ARGS_ERROR);
  }

  // ファイル読み込み
  let content;
  try {
    content = fs.readFileSync(parsed.netaFile, "utf-8");
  } catch (err) {
    console.error(`Error: ファイルを読み込めません: ${parsed.netaFile}`);
    console.error(err.message);
    process.exit(EXIT_FILE_ERROR);
  }

  const newLink = generateLink(parsed.filename);

  // 重複登録の防止: 同一ファイル名のリンクが既にあれば追記しない
  if (hasExistingLink(content, parsed.filename)) {
    console.log(JSON.stringify({
      ok: true,
      skipped: true,
      reason: "duplicate",
      netaFile: parsed.netaFile,
      filename: parsed.filename,
      link: newLink,
      dryRun: parsed.dryRun,
      success: true,
      message: "同一ファイル名のリンクが既に存在するため追記をスキップしました"
    }, null, 2));
    process.exit(EXIT_SUCCESS);
  }

  // 挿入位置を特定
  const insertPosition = findInsertPosition(content);

  // 新しいコンテンツを生成
  const lines = content.split("\n");
  lines.splice(insertPosition, 0, newLink);
  const newContent = lines.join("\n");

  const result = {
    ok: true,
    skipped: false,
    netaFile: parsed.netaFile,
    filename: parsed.filename,
    link: newLink,
    insertPosition,
    dryRun: parsed.dryRun,
    success: true
  };

  if (!parsed.dryRun) {
    try {
      fs.writeFileSync(parsed.netaFile, newContent, "utf-8");
      result.message = "00ネタファイルを更新しました";
    } catch (err) {
      console.error(`Error: ファイルを書き込めません: ${parsed.netaFile}`);
      console.error(err.message);
      process.exit(EXIT_FILE_ERROR);
    }
  } else {
    result.message = "dry-runモード: 実際の更新はスキップしました";
    result.preview = newLink;
  }

  console.log(JSON.stringify(result, null, 2));
  process.exit(EXIT_SUCCESS);
}

main();
