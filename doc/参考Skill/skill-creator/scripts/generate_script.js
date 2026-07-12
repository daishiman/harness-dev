#!/usr/bin/env node

/**
 * scripts/*.js生成スクリプト
 *
 * Script定義JSONからscripts/*.jsを生成します。
 *
 * 使用例:
 *   node scripts/generate_script.js --def .tmp/scripts/validate.json --output .claude/skills/my-skill/scripts/validate.js
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 検証失敗
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { dirname, basename } from "path";
import { EXIT_CODES, getArg, resolvePath } from "./utils.js";

function showHelp() {
  console.log(`
scripts/*.js生成スクリプト

Usage:
  node generate_script.js --def <def-json> --output <output-path>

Options:
  --def <path>     Script定義JSONファイルのパス（必須）
  --output <path>  出力先scripts/*.jsのパス（必須）
  --type <type>    スクリプトタイプ: task, validator, generator（デフォルト: task）
  -h, --help       このヘルプを表示

Script JSON形式:
  {
    "name": "validate-something",
    "description": "何かを検証するスクリプト",
    "type": "validator",
    "args": [
      { "name": "--input", "required": true, "description": "入力ファイル" },
      { "name": "--verbose", "required": false, "description": "詳細出力" }
    ],
    "exitCodes": [
      { "code": 0, "meaning": "成功" },
      { "code": 4, "meaning": "検証失敗" }
    ]
  }

Examples:
  node scripts/generate_script.js --def .tmp/scripts/validate.json --output scripts/validate.js
`);
}

function generateTaskScript(def) {
  const name = def.name || "task-script";
  const description = def.description || "タスク実行スクリプト";
  const args = def.args || [{ name: "--input", required: true, description: "入力" }];

  const requiredArgs = args.filter((a) => a.required);
  const optionalArgs = args.filter((a) => !a.required);

  const argsDoc = args.map((a) => `  ${a.name.padEnd(15)} ${a.description}${a.required ? "（必須）" : ""}`).join("\n");
  const exitCodesDoc = (def.exitCodes || [
    { code: 0, meaning: "成功" },
    { code: 1, meaning: "一般的なエラー" },
    { code: 2, meaning: "引数エラー" },
  ]).map((e) => `  ${e.code}: ${e.meaning}`).join("\n");

  const argChecks = requiredArgs.map((a) => `
  const ${a.name.replace("--", "").replace(/-/g, "_")} = getArg(args, "${a.name}");
  if (!${a.name.replace("--", "").replace(/-/g, "_")}) {
    console.error("Error: ${a.name} は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }`).join("\n");

  return `#!/usr/bin/env node

/**
 * ${description}
 *
 * 使用例:
 *   node scripts/${name}.js ${requiredArgs.map((a) => `${a.name} <value>`).join(" ")}
 *
 * 終了コード:
${exitCodesDoc}
 */

import { existsSync } from "fs";
import { EXIT_CODES, getArg, resolvePath } from "./utils.js";

function showHelp() {
  console.log(\`
${description}

Usage:
  node ${name}.js ${requiredArgs.map((a) => `${a.name} <value>`).join(" ")} [options]

Options:
${argsDoc}
  -h, --help       このヘルプを表示
\`);
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }
${argChecks}

  try {
    // TODO: タスクロジックを実装
    console.log("✓ タスクが完了しました");
    process.exit(EXIT_CODES.SUCCESS);
  } catch (err) {
    console.error(\`Error: \${err.message}\`);
    process.exit(EXIT_CODES.ERROR);
  }
}

main().catch((err) => {
  console.error(\`Error: \${err.message}\`);
  process.exit(EXIT_CODES.ERROR);
});
`;
}

function generateValidatorScript(def) {
  const name = def.name || "validator";
  const description = def.description || "検証スクリプト";

  return `#!/usr/bin/env node

/**
 * ${description}
 *
 * 使用例:
 *   node scripts/${name}.js --input <path>
 *
 * 終了コード:
 *   0: 検証成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 検証失敗
 */

import { readFileSync, existsSync } from "fs";
import { EXIT_CODES, getArg, resolvePath } from "./utils.js";

function showHelp() {
  console.log(\`
${description}

Usage:
  node ${name}.js --input <path> [options]

Options:
  --input <path>   検証対象のパス（必須）
  --verbose        詳細な検証結果を表示
  -h, --help       このヘルプを表示
\`);
}

function validate(input) {
  const errors = [];
  const warnings = [];

  // TODO: 検証ロジックを実装
  // errors.push("エラーメッセージ");
  // warnings.push("警告メッセージ");

  return { errors, warnings };
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const verbose = args.includes("--verbose");
  const inputPath = getArg(args, "--input");

  if (!inputPath) {
    console.error("Error: --input は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedInput = resolvePath(inputPath);

  if (!existsSync(resolvedInput)) {
    console.error(\`Error: ファイルが存在しません: \${resolvedInput}\`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  try {
    const { errors, warnings } = validate(resolvedInput);

    if (verbose && warnings.length > 0) {
      console.log("⚠ 警告:");
      warnings.forEach((w) => console.log(\`  - \${w}\`));
    }

    if (errors.length > 0) {
      console.error("✗ 検証失敗:");
      errors.forEach((e) => console.error(\`  - \${e}\`));
      process.exit(EXIT_CODES.VALIDATION_FAILED);
    }

    console.log(\`✓ 検証成功: \${inputPath}\`);
    process.exit(EXIT_CODES.SUCCESS);
  } catch (err) {
    console.error(\`Error: \${err.message}\`);
    process.exit(EXIT_CODES.ERROR);
  }
}

main().catch((err) => {
  console.error(\`Error: \${err.message}\`);
  process.exit(EXIT_CODES.ERROR);
});
`;
}

function generateGeneratorScript(def) {
  const name = def.name || "generator";
  const description = def.description || "生成スクリプト";

  return `#!/usr/bin/env node

/**
 * ${description}
 *
 * 使用例:
 *   node scripts/${name}.js --input <path> --output <path>
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { dirname } from "path";
import { EXIT_CODES, getArg, resolvePath } from "./utils.js";

function showHelp() {
  console.log(\`
${description}

Usage:
  node ${name}.js --input <path> --output <path> [options]

Options:
  --input <path>   入力ファイルのパス（必須）
  --output <path>  出力先のパス（必須）
  -h, --help       このヘルプを表示
\`);
}

function generate(input) {
  // TODO: 生成ロジックを実装
  return \`// Generated content based on: \${input}\n\`;
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const inputPath = getArg(args, "--input");
  const outputPath = getArg(args, "--output");

  if (!inputPath) {
    console.error("Error: --input は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  if (!outputPath) {
    console.error("Error: --output は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedInput = resolvePath(inputPath);
  const resolvedOutput = resolvePath(outputPath);

  if (!existsSync(resolvedInput)) {
    console.error(\`Error: 入力ファイルが存在しません: \${resolvedInput}\`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  try {
    const input = readFileSync(resolvedInput, "utf-8");
    const content = generate(input);

    const outputDir = dirname(resolvedOutput);
    if (!existsSync(outputDir)) {
      mkdirSync(outputDir, { recursive: true });
    }

    writeFileSync(resolvedOutput, content, "utf-8");
    console.log(\`✓ 生成完了: \${outputPath}\`);
    process.exit(EXIT_CODES.SUCCESS);
  } catch (err) {
    console.error(\`Error: \${err.message}\`);
    process.exit(EXIT_CODES.ERROR);
  }
}

main().catch((err) => {
  console.error(\`Error: \${err.message}\`);
  process.exit(EXIT_CODES.ERROR);
});
`;
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const defPath = getArg(args, "--def");
  const outputPath = getArg(args, "--output");
  const scriptType = getArg(args, "--type") || "task";

  if (!defPath) {
    console.error("Error: --def は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  if (!outputPath) {
    console.error("Error: --output は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedDef = resolvePath(defPath);
  const resolvedOutput = resolvePath(outputPath);

  if (!existsSync(resolvedDef)) {
    console.error(`Error: Script定義ファイルが存在しません: ${resolvedDef}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  try {
    const def = JSON.parse(readFileSync(resolvedDef, "utf-8"));
    const type = def.type || scriptType;

    let content;
    switch (type) {
      case "validator":
        content = generateValidatorScript(def);
        break;
      case "generator":
        content = generateGeneratorScript(def);
        break;
      default:
        content = generateTaskScript(def);
    }

    // 出力ディレクトリの作成
    const outputDir = dirname(resolvedOutput);
    if (!existsSync(outputDir)) {
      mkdirSync(outputDir, { recursive: true });
    }

    writeFileSync(resolvedOutput, content, "utf-8");
    console.log(`✓ scripts/${basename(resolvedOutput)}を生成しました (type: ${type})`);
    process.exit(EXIT_CODES.SUCCESS);
  } catch (err) {
    if (err instanceof SyntaxError) {
      console.error(`Error: JSONの解析に失敗しました: ${err.message}`);
    } else {
      console.error(`Error: ${err.message}`);
    }
    process.exit(EXIT_CODES.ERROR);
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
