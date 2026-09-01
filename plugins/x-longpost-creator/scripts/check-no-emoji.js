#!/usr/bin/env node
/**
 * check-no-emoji.js - 絵文字ゼロ検証（決定論的処理）
 *
 * テキストまたはファイルに絵文字（Extended_Pictographic）が含まれていないか検証する。
 * ✓ ✗ → ① などのテキスト記号は絵文字として扱わない。
 *
 * 使用例:
 *   node scripts/check-no-emoji.js --file /path/to/file.md
 *   node scripts/check-no-emoji.js --text "検証したいテキスト"
 *
 * 終了コード: 0 = 絵文字なし / 1 = 絵文字あり / 2 = 引数・入出力エラー
 */

const fs = require("fs");
const { findEmojiByLine } = require("./lib/text-rules.js");

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--file") args.file = argv[++i];
    else if (argv[i] === "--text") args.text = argv[++i];
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv);
  let text;
  if (args.file) {
    if (!fs.existsSync(args.file)) {
      console.error(JSON.stringify({ error: `ファイルが見つかりません: ${args.file}` }));
      process.exit(2);
    }
    text = fs.readFileSync(args.file, "utf8");
  } else if (typeof args.text === "string") {
    text = args.text;
  } else {
    console.error(JSON.stringify({ error: "--file <path> または --text <text> を指定してください" }));
    process.exit(2);
  }

  const hits = findEmojiByLine(text);
  const result = {
    ok: hits.length === 0,
    count: hits.reduce((n, h) => n + h.emoji.length, 0),
    hits: hits.slice(0, 50),
  };
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.ok ? 0 : 1);
}

main();
