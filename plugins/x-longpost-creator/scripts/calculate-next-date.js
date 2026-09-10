#!/usr/bin/env node

/**
 * 次の投稿日を計算するスクリプト
 *
 * 00ネタファイルから最新投稿日を抽出し、+1日した日付を返す
 *
 * Usage:
 *   node calculate-next-date.js --neta-file <path>
 *   node calculate-next-date.js --neta-file /path/to/00ネタ.md
 *
 * Output:
 *   JSON形式で次の投稿日を出力
 *   { "nextDate": "2026-02-05", "latestDate": "2026-02-04", "source": "00ネタファイル" }
 *
 * 終了コード: 0 = 成功 / 1 = 日付を抽出できない / 2 = 引数エラー / 3 = ファイルエラー
 */

const fs = require("fs");

const EXIT_SUCCESS = 0;
const EXIT_FAIL = 1;
const EXIT_ARGS_ERROR = 2;
const EXIT_FILE_ERROR = 3;

function showHelp() {
  console.log(`
Usage: node calculate-next-date.js [options]

Options:
  --neta-file <path>  00ネタファイルのパス（必須）
  -h, --help          このヘルプを表示
  `);
}

function parseArgs(args) {
  const result = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "-h" || args[i] === "--help") {
      result.help = true;
    } else if (args[i] === "--neta-file" && args[i + 1]) {
      result.netaFile = args[++i];
    }
  }
  return result;
}

function extractLatestDate(content) {
  // パターン: X長文投稿-prompt作成 - YYYY-MM-DD
  const datePattern = /X長文投稿-prompt作成 - (\d{4}-\d{2}-\d{2})/g;
  const dates = [];

  let match;
  while ((match = datePattern.exec(content)) !== null) {
    dates.push(match[1]);
  }

  if (dates.length === 0) {
    return null;
  }

  // 最新日付を取得（日付文字列をソートして最大値を取得）
  dates.sort((a, b) => b.localeCompare(a));
  return dates[0];
}

function addDays(dateStr, days) {
  const date = new Date(dateStr);
  date.setDate(date.getDate() + days);
  return date.toISOString().split("T")[0];
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

  // ファイル読み込み
  let content;
  try {
    content = fs.readFileSync(parsed.netaFile, "utf-8");
  } catch (err) {
    console.error(`Error: ファイルを読み込めません: ${parsed.netaFile}`);
    console.error(err.message);
    process.exit(EXIT_FILE_ERROR);
  }

  // 最新日付を抽出
  const latestDate = extractLatestDate(content);

  if (!latestDate) {
    // 本スクリプトの唯一の責務は「ネタファイルの最新日付 + 1日」を返すこと。
    // 抽出できなかったときに今日の日付を返すと、それは別の規則で作られた値であり、
    // 呼び出し側は正しい日付として受け取ってしまう（既存の投稿日と重複・逆行し得る）。
    // 警告を出しつつ値を返す選択肢もあるが、JSON を機械的に読む呼び出し側は
    // stderr を無視するため沈黙のフォールバックと変わらない。よって停止する。
    console.error(`Error: ネタファイルから投稿日を抽出できません: ${parsed.netaFile}`);
    console.error("期待する記載形式: X長文投稿-prompt作成 - YYYY-MM-DD");
    console.error("ネタファイルのパスが正しいか、日付付きの行が存在するかを確認してください。");
    process.exit(EXIT_FAIL);
  }

  // +1日した日付を計算
  const nextDate = addDays(latestDate, 1);

  const result = {
    nextDate,
    latestDate,
    source: "00ネタファイル"
  };

  console.log(JSON.stringify(result, null, 2));
  process.exit(EXIT_SUCCESS);
}

main();
