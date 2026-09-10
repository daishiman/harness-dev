#!/usr/bin/env node

/**
 * 文字数カウント・検証スクリプト
 *
 * 投稿文の文字数をカウントし、基準を満たしているかチェックする
 *
 * Usage:
 *   node count-chars.js --text "投稿文テキスト"
 *   node count-chars.js --file /path/to/file.md
 *   node count-chars.js --text "テキスト" --min 2000 --max 3000
 *
 * Output:
 *   JSON形式で文字数と検証結果を出力
 */

const fs = require("fs");

const EXIT_SUCCESS = 0;
const EXIT_FAIL = 1;
const EXIT_ARGS_ERROR = 2;
const EXIT_FILE_ERROR = 3;

// --min / --max に既定値は置かない。
// 長文パターンA(1800〜2200)・短文(180〜220)・投稿9 要約型(400〜499) と用途ごとに
// レンジが異なるため、どれか一つを既定値にすると他用途で沈黙のまま通過する。
// 未指定は EXIT_ARGS_ERROR で止める(fail-closed)。純カウントが要るときも
// --min 0 --max 999999 のように意図を明示して渡す。
const DEFAULT_LINE_MIN = 30;
const DEFAULT_LINE_MAX = 40;

function showHelp() {
  console.log(`
Usage: node count-chars.js [options]

Options:
  --text <string>     カウント対象のテキスト（--text または --file のいずれか必須）
  --file <path>       カウント対象のファイル
  --min <number>      最小文字数（必須。既定値なし）
  --max <number>      最大文字数（必須。既定値なし）
  --check-lines       1行あたりの文字数もチェック
  --line-min <number> 1行の最小文字数（デフォルト: ${DEFAULT_LINE_MIN}）
  --line-max <number> 1行の最大文字数（デフォルト: ${DEFAULT_LINE_MAX}）
  -h, --help          このヘルプを表示
  `);
}

function parseArgs(args) {
  const result = {
    min: null,
    max: null,
    lineMin: DEFAULT_LINE_MIN,
    lineMax: DEFAULT_LINE_MAX,
    checkLines: false
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "-h" || args[i] === "--help") {
      result.help = true;
    } else if (args[i] === "--text" && args[i + 1]) {
      result.text = args[++i];
    } else if (args[i] === "--file" && args[i + 1]) {
      result.file = args[++i];
    } else if (args[i] === "--min" && args[i + 1]) {
      result.min = parseInt(args[++i], 10);
    } else if (args[i] === "--max" && args[i + 1]) {
      result.max = parseInt(args[++i], 10);
    } else if (args[i] === "--check-lines") {
      result.checkLines = true;
    } else if (args[i] === "--line-min" && args[i + 1]) {
      result.lineMin = parseInt(args[++i], 10);
    } else if (args[i] === "--line-max" && args[i + 1]) {
      result.lineMax = parseInt(args[++i], 10);
    }
  }
  return result;
}

function countChars(text) {
  // 空白・改行を除いた文字数
  const withoutSpaces = text.replace(/\s/g, "").length;
  // 空白含む文字数
  const withSpaces = text.length;
  // 改行数
  const lineBreaks = (text.match(/\n/g) || []).length;

  return {
    withoutSpaces,
    withSpaces,
    lineBreaks,
    lines: text.split("\n").length
  };
}

function checkLineLength(text, minLen, maxLen) {
  const lines = text.split("\n").filter(line => line.trim().length > 0);
  const issues = [];

  lines.forEach((line, index) => {
    const len = line.length;
    if (len > 0 && len < minLen) {
      issues.push({
        lineNumber: index + 1,
        length: len,
        issue: "too_short",
        content: line.slice(0, 50) + (line.length > 50 ? "..." : "")
      });
    } else if (len > maxLen) {
      issues.push({
        lineNumber: index + 1,
        length: len,
        issue: "too_long",
        content: line.slice(0, 50) + (line.length > 50 ? "..." : "")
      });
    }
  });

  return {
    totalLines: lines.length,
    issueCount: issues.length,
    issues: issues.slice(0, 10) // 最初の10件のみ
  };
}

function main() {
  const args = process.argv.slice(2);
  const parsed = parseArgs(args);

  if (parsed.help) {
    showHelp();
    process.exit(EXIT_SUCCESS);
  }

  // テキスト取得
  let text;
  if (parsed.text) {
    text = parsed.text;
  } else if (parsed.file) {
    try {
      text = fs.readFileSync(parsed.file, "utf-8");
    } catch (err) {
      console.error(`Error: ファイルを読み込めません: ${parsed.file}`);
      console.error(err.message);
      process.exit(EXIT_FILE_ERROR);
    }
  } else {
    console.error("Error: --text または --file のいずれかを指定してください");
    showHelp();
    process.exit(EXIT_ARGS_ERROR);
  }

  if (!Number.isFinite(parsed.min) || !Number.isFinite(parsed.max)) {
    console.error(
      "Error: --min と --max は必須です（用途ごとにレンジが異なるため既定値は持ちません）"
    );
    showHelp();
    process.exit(EXIT_ARGS_ERROR);
  }

  // 文字数カウント
  const counts = countChars(text);

  // 基準チェック
  const validation = {
    minChars: parsed.min,
    maxChars: parsed.max,
    meetsMinimum: counts.withoutSpaces >= parsed.min,
    meetsMaximum: counts.withoutSpaces <= parsed.max,
    isValid: counts.withoutSpaces >= parsed.min && counts.withoutSpaces <= parsed.max
  };

  const result = {
    ok: validation.isValid,
    counts,
    validation
  };

  // 行長チェック（オプション）。行長は warning 扱いで終了コードには影響させない
  if (parsed.checkLines) {
    result.lineCheck = checkLineLength(text, parsed.lineMin, parsed.lineMax);
  }

  if (!validation.isValid) {
    result.failed = [
      !validation.meetsMinimum
        ? `文字数不足: ${counts.withoutSpaces}文字 / 下限${parsed.min}文字`
        : `文字数超過: ${counts.withoutSpaces}文字 / 上限${parsed.max}文字`
    ];
    result.nextAction =
      "レンジに収まるまで加筆または圧縮してから再実行する。PASSするまで出力を確定しない。";
  }

  console.log(JSON.stringify(result, null, 2));
  process.exit(validation.isValid ? EXIT_SUCCESS : EXIT_FAIL);
}

main();
