#!/usr/bin/env node

/**
 * テンプレート展開スクリプト
 *
 * output-template.mdの変数を実際の値で置換する
 *
 * Usage:
 *   node expand-template.js --template <path> --vars '{"title": "タイトル", ...}'
 *   node expand-template.js --template <path> --vars-file vars.json
 *
 * Output:
 *   展開されたテンプレート（標準出力、または --output でファイルへ）
 *   --output と --json は併用できる（ファイルへ書き、JSON も標準出力へ出す）
 *
 * 終了コード: 0 = 全変数を解決 / 1 = 未解決の変数が残る / 2 = 引数エラー / 3 = ファイルエラー
 */

const fs = require("fs");
const path = require("path");

const EXIT_SUCCESS = 0;
const EXIT_FAIL = 1;
const EXIT_ARGS_ERROR = 2;
const EXIT_FILE_ERROR = 3;

function showHelp() {
  console.log(`
Usage: node expand-template.js [options]

Options:
  --template <path>     テンプレートファイルのパス（必須）
  --vars <json>         変数をJSON形式で指定
  --vars-file <path>    変数をJSONファイルから読み込み
  --output <path>       出力ファイルパス（省略時は展開結果を標準出力へ）
                        親ディレクトリが無ければ作成する
  --json                展開結果のサマリをJSON形式で標準出力へ出す（--output と併用可）
  -h, --help            このヘルプを表示

Variables:
  テンプレート内の {{変数名}} を置換します（日本語変数名対応）。
  テンプレートに TEMPLATE-START/END マーカーがある場合はその間だけを展開します。

  主要な変数（assets/output-template.md 準拠。
  一覧は \${CLAUDE_PLUGIN_ROOT}/prompts/x-longpost-output-file.md §4.5）:
    - タイトル / キャッチコピー / メモ / 文字起こし
    - 投稿文_短文 / 投稿文_長文A / 投稿文_長文B
    - IdeaCompass / ハッシュタグ（生成時は空文字を渡す）
  `);
}

function parseArgs(args) {
  const result = { json: false };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "-h" || args[i] === "--help") {
      result.help = true;
    } else if (args[i] === "--template" && args[i + 1]) {
      result.template = args[++i];
    } else if (args[i] === "--vars" && args[i + 1]) {
      result.vars = args[++i];
    } else if (args[i] === "--vars-file" && args[i + 1]) {
      result.varsFile = args[++i];
    } else if (args[i] === "--output" && args[i + 1]) {
      result.output = args[++i];
    } else if (args[i] === "--json") {
      result.json = true;
    }
  }
  return result;
}

function loadVariables(parsed) {
  if (parsed.vars) {
    try {
      return JSON.parse(parsed.vars);
    } catch (err) {
      console.error("Error: --vars のJSONパースに失敗しました");
      console.error(err.message);
      process.exit(EXIT_ARGS_ERROR);
    }
  }

  if (parsed.varsFile) {
    try {
      const content = fs.readFileSync(parsed.varsFile, "utf-8");
      return JSON.parse(content);
    } catch (err) {
      console.error(`Error: 変数ファイルを読み込めません: ${parsed.varsFile}`);
      console.error(err.message);
      process.exit(EXIT_FILE_ERROR);
    }
  }

  return {};
}

function expandTemplate(template, vars) {
  let expanded = template;
  const usedVars = [];
  const missingVars = [];

  // {{variable_name}} パターンを検索（日本語変数名にも対応）
  const pattern = /\{\{([\p{L}\p{N}_]+)\}\}/gu;
  const matches = template.match(pattern) || [];
  const uniqueVars = [...new Set(matches.map(m => m.replace(/[{}]/g, "")))];

  for (const varName of uniqueVars) {
    const placeholder = `{{${varName}}}`;
    if (vars.hasOwnProperty(varName)) {
      expanded = expanded.split(placeholder).join(vars[varName] || "");
      usedVars.push(varName);
    } else {
      missingVars.push(varName);
    }
  }

  return {
    expanded,
    usedVars,
    missingVars,
    hasUnresolvedVars: missingVars.length > 0
  };
}

function main() {
  const args = process.argv.slice(2);
  const parsed = parseArgs(args);

  if (parsed.help) {
    showHelp();
    process.exit(EXIT_SUCCESS);
  }

  if (!parsed.template) {
    console.error("Error: --template は必須です");
    showHelp();
    process.exit(EXIT_ARGS_ERROR);
  }

  // テンプレート読み込み
  let template;
  try {
    template = fs.readFileSync(parsed.template, "utf-8");
  } catch (err) {
    console.error(`Error: テンプレートファイルを読み込めません: ${parsed.template}`);
    console.error(err.message);
    process.exit(EXIT_FILE_ERROR);
  }

  // マーカー間抽出（マーカーがあれば TEMPLATE-START/END の間だけを雛形として使う。
  // マーカーがないファイルは従来どおり全体を展開対象にする）
  const START_MARKER = "<!-- TEMPLATE-START -->";
  const END_MARKER = "<!-- TEMPLATE-END -->";
  if (template.includes(START_MARKER) && template.includes(END_MARKER)) {
    template = template.split(START_MARKER)[1].split(END_MARKER)[0].replace(/^\n/, "");
  }

  // 変数読み込み
  const vars = loadVariables(parsed);

  // テンプレート展開
  const result = expandTemplate(template, vars);

  // 出力先（--output）と出力形式（--json）は独立した軸として扱う。
  // 手順書は両方を同時に渡すため、排他分岐にはしない。
  if (parsed.output) {
    try {
      // 出力先の親ディレクトリが無い場合に ENOENT で落ちないよう先に作る
      fs.mkdirSync(path.dirname(path.resolve(parsed.output)), { recursive: true });
      fs.writeFileSync(parsed.output, result.expanded, "utf-8");
      console.error(`OK 出力完了: ${parsed.output}`);
    } catch (err) {
      console.error(`Error: ファイルを書き込めません: ${parsed.output}`);
      console.error(err.message);
      process.exit(EXIT_FILE_ERROR);
    }
  }

  if (parsed.json) {
    console.log(JSON.stringify({
      success: !result.hasUnresolvedVars,
      usedVars: result.usedVars,
      missingVars: result.missingVars,
      expandedLength: result.expanded.length,
      outputPath: parsed.output || null
    }, null, 2));
  } else if (!parsed.output) {
    // 出力先も出力形式も未指定なら展開結果そのものを標準出力へ
    process.stdout.write(result.expanded);
  }

  // 未解決の変数が残った成果物は不完全なので成功として返さない。
  // JSON の success フィールドと終了コードを一致させる。
  if (result.hasUnresolvedVars) {
    console.error(`Error: 未解決の変数が残っています: ${result.missingVars.join(", ")}`);
    process.exit(EXIT_FAIL);
  }

  process.exit(EXIT_SUCCESS);
}

main();
