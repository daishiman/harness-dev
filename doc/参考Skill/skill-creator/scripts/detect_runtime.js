#!/usr/bin/env node
/**
 * ランタイム判定スクリプト
 *
 * スクリプト要件から最適なランタイムを判定する。
 * 決定論的なルールに基づいて判定（LLM不要）。
 *
 * 使用方法:
 *   node scripts/detect_runtime.js --requirement <path> --output <path>
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般エラー
 *   2: 引数エラー
 *   3: ファイル不在
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { dirname } from "path";
import { EXIT_CODES, getArg, resolvePath } from "./utils.js";

// タイプ別推奨ランタイム
const TYPE_RUNTIME_MAP = {
  "api-client": { primary: "node", secondary: "python" },
  "webhook": { primary: "node", secondary: "python" },
  "scraper": { primary: "python", secondary: "node" },
  "parser": { primary: "node", secondary: "python" },
  "transformer": { primary: "node", secondary: "python" },
  "aggregator": { primary: "python", secondary: "node" },
  "file-processor": { primary: "bash", secondary: "node" },
  "database": { primary: "node", secondary: "python" },
  "cache": { primary: "node", secondary: "python" },
  "queue": { primary: "node", secondary: "python" },
  "git-ops": { primary: "bash", secondary: "node" },
  "test-runner": { primary: "node", secondary: "python" },
  "linter": { primary: "node", secondary: "bash" },
  "formatter": { primary: "node", secondary: "bash" },
  "builder": { primary: "node", secondary: "bash" },
  "deployer": { primary: "bash", secondary: "node" },
  "docker": { primary: "bash", secondary: null },
  "cloud": { primary: "bash", secondary: "python" },
  "monitor": { primary: "node", secondary: "python" },
  "ai-tool": { primary: "bash", secondary: "node" },
  "mcp-bridge": { primary: "node", secondary: null },
  "notification": { primary: "node", secondary: "python" },
  "shell": { primary: "bash", secondary: null },
  "universal": { primary: "node", secondary: "python" },
};

// キーワード→ランタイムのマッピング
const KEYWORD_RUNTIME_MAP = {
  // Python優先キーワード
  "pandas": "python",
  "numpy": "python",
  "beautifulsoup": "python",
  "selenium": "python",
  "pytorch": "python",
  "tensorflow": "python",
  "scikit": "python",
  "データ分析": "python",
  "機械学習": "python",
  "AI": "python",

  // Bash優先キーワード
  "シェル": "bash",
  "システム": "bash",
  "docker": "bash",
  "kubectl": "bash",
  "aws": "bash",
  "gcloud": "bash",

  // Node.js優先キーワード
  "react": "node",
  "vue": "node",
  "next": "node",
  "express": "node",
  "vitest": "node",
  "jest": "node",

  // TypeScript/Bun優先キーワード
  "typescript": "bun",
  "bun": "bun",
  "deno": "deno",
};

function showHelp() {
  console.log(`
ランタイム判定スクリプト

Usage:
  node detect_runtime.js --requirement <path> [--output <path>]

Options:
  --requirement <path>  スクリプト要件JSONファイルパス（必須）
  --output <path>       結果出力先（指定なしで標準出力）
  --verbose             詳細出力
  -h, --help            ヘルプ表示
`);
}


function detectRuntime(requirement, verbose = false) {
  const { type, purpose = "", dependencies = {}, keywords = [] } = requirement;

  let detectedRuntime = "node"; // デフォルト
  let confidence = 0.5;
  const reasons = [];

  // 1. タイプによる判定（最優先）
  if (type && TYPE_RUNTIME_MAP[type]) {
    detectedRuntime = TYPE_RUNTIME_MAP[type].primary;
    confidence = 0.8;
    reasons.push(`タイプ "${type}" の推奨ランタイム`);
  }

  // 2. キーワードによる判定
  const allText = [purpose, ...keywords].join(" ").toLowerCase();
  for (const [keyword, runtime] of Object.entries(KEYWORD_RUNTIME_MAP)) {
    if (allText.includes(keyword.toLowerCase())) {
      if (detectedRuntime !== runtime) {
        reasons.push(`キーワード "${keyword}" により ${runtime} を検討`);
      }
      // キーワードが複数マッチした場合は最初のものを優先
      if (confidence < 0.9) {
        detectedRuntime = runtime;
        confidence = 0.9;
        reasons.push(`キーワード "${keyword}" により決定`);
        break;
      }
    }
  }

  // 3. 依存関係による判定
  if (dependencies.pip && dependencies.pip.length > 0) {
    if (detectedRuntime !== "python") {
      reasons.push("pip依存関係があるため Python を検討");
    }
    detectedRuntime = "python";
    confidence = 0.95;
  }

  if (dependencies.npm && dependencies.npm.length > 0) {
    if (detectedRuntime !== "node" && detectedRuntime !== "bun") {
      reasons.push("npm依存関係があるため Node.js を検討");
    }
    if (detectedRuntime !== "python") {
      detectedRuntime = "node";
      confidence = 0.95;
    }
  }

  // 4. 明示的な指定があれば最優先
  if (requirement.runtime) {
    detectedRuntime = requirement.runtime;
    confidence = 1.0;
    reasons.push("明示的に指定されたランタイム");
  }

  // ランタイム設定を生成
  const runtimeConfig = {
    runtime: detectedRuntime,
    confidence,
    reasons,
    settings: getRuntimeSettings(detectedRuntime),
    alternatives: getAlternatives(type, detectedRuntime),
  };

  if (verbose) {
    console.log(`\n判定結果:`);
    console.log(`  ランタイム: ${detectedRuntime}`);
    console.log(`  確信度: ${(confidence * 100).toFixed(0)}%`);
    console.log(`  理由:`);
    reasons.forEach((r) => console.log(`    - ${r}`));
  }

  return runtimeConfig;
}

function getRuntimeSettings(runtime) {
  const settings = {
    node: {
      shebang: "#!/usr/bin/env node",
      extension: ".js",
      moduleSystem: "esm",
      packageManager: "pnpm",
    },
    python: {
      shebang: "#!/usr/bin/env python3",
      extension: ".py",
      packageManager: "uv",
    },
    bash: {
      shebang: "#!/usr/bin/env bash",
      extension: ".sh",
      flags: "set -euo pipefail",
    },
    bun: {
      shebang: "#!/usr/bin/env bun",
      extension: ".ts",
      moduleSystem: "esm",
    },
    deno: {
      shebang: "#!/usr/bin/env -S deno run --allow-all",
      extension: ".ts",
    },
  };

  return settings[runtime] || settings.node;
}

function getAlternatives(type, primary) {
  if (!type || !TYPE_RUNTIME_MAP[type]) return [];

  const mapping = TYPE_RUNTIME_MAP[type];
  const alternatives = [];

  if (mapping.secondary && mapping.secondary !== primary) {
    alternatives.push({
      runtime: mapping.secondary,
      reason: `${type} の代替ランタイム`,
    });
  }

  return alternatives;
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const requirementPath = getArg(args, "--requirement");
  const outputPath = getArg(args, "--output");
  const verbose = args.includes("--verbose");

  if (!requirementPath) {
    console.error("Error: --requirement は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedRequirement = resolvePath(requirementPath);

  if (!existsSync(resolvedRequirement)) {
    console.error(`Error: 要件ファイルが存在しません: ${resolvedRequirement}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  try {
    const requirement = JSON.parse(readFileSync(resolvedRequirement, "utf-8"));
    const result = detectRuntime(requirement, verbose);

    const output = JSON.stringify(result, null, 2);

    if (outputPath) {
      const resolvedOutput = resolvePath(outputPath);
      const outputDir = dirname(resolvedOutput);
      if (!existsSync(outputDir)) {
        mkdirSync(outputDir, { recursive: true });
      }
      writeFileSync(resolvedOutput, output, "utf-8");
      console.log(`✓ ランタイム判定完了: ${result.runtime}`);
    } else {
      console.log(output);
    }

    process.exit(EXIT_CODES.SUCCESS);
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(EXIT_CODES.ERROR);
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
