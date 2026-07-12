#!/usr/bin/env node

/**
 * スキル初期化スクリプト
 *
 * 18-skills.md §6.4 に準拠したスキルディレクトリを初期化します。
 *
 * 使用例:
 *   node init_skill.js my-new-skill --path .claude/skills
 *   node init_skill.js my-new-skill --path .claude/skills --resources agents,references
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在（パスが存在しない）
 */

import { mkdirSync, writeFileSync, existsSync } from "fs";
import { join } from "path";
import { EXIT_CODES } from "./utils.js";
import { validateSkillMdContent } from "./utils/validate-skill-md.js";

const DEFAULT_RESOURCES = ["agents", "scripts", "references", "assets"];
const ALLOWED_RESOURCES = new Set(DEFAULT_RESOURCES);

/**
 * スキル用 package.json を生成
 * @param {string} skillName - スキル名
 * @returns {string} JSON文字列
 */
function createPackageJson(skillName) {
  const today = new Date().toISOString().split("T")[0];
  return JSON.stringify(
    {
      name: `@skills/${skillName}`,
      version: "1.0.0",
      description: `Claude Code skill: ${skillName}`,
      type: "module",
      private: true,
      scripts: {
        validate: "node scripts/validate_all.js",
        log: "node scripts/log_usage.js",
        "deps:install": "pnpm install",
        "deps:add": "pnpm add",
      },
      engines: {
        node: ">=18.0.0",
      },
      dependencies: {},
      devDependencies: {},
      keywords: ["claude-code", "skill"],
      author: "AIWorkflowOrchestrator",
      license: "UNLICENSED",
      created: today,
    },
    null,
    2,
  );
}

function showHelp() {
  console.log(`
スキル初期化スクリプト (18-skills.md §6.4 準拠)

Usage:
  node init_skill.js <skill-name> [options]

Arguments:
  <skill-name>    スキル名（ハイフンケース、最大64文字）

Options:
  --path <path>   スキルを作成するベースパス（デフォルト: .claude/skills）
  --resources <list>
                  作成するリソースを指定（例: agents,scripts,references,assets）
                  all/none も指定可（デフォルト: all）
  -h, --help      このヘルプを表示

Examples:
  node init_skill.js my-new-skill
  node init_skill.js my-new-skill --path .claude/skills
  node init_skill.js my-new-skill --resources agents,references

Created structure (selected resources only):
  <skill-name>/
  ├── SKILL.md          # メインファイル（TODO付きテンプレート）
  ├── package.json      # 依存関係管理（PNPM使用）
  ├── LOGS fragment           # 実行ログ（フィードバック機構）
  ├── EVALS.json        # メトリクス（フィードバック機構）
  ├── agents/           # Task仕様書ディレクトリ（任意）
  ├── scripts/          # スクリプトディレクトリ（任意）
  │   └── log_usage.js  # フィードバック記録スクリプト（scripts指定時のみ）
  ├── references/       # 参照資料ディレクトリ（任意）
  │   └── patterns.md   # 成功/失敗パターン（references指定時のみ）
  └── assets/           # アセットディレクトリ（任意）

Notes:
  - 各スキルは自己完結型（独自のnode_modulesを持つ）
  - 依存関係の追加: cd <skill-dir> && pnpm add <package>
  `);
}

function validateSkillName(name) {
  if (!name) {
    return { valid: false, error: "スキル名が指定されていません" };
  }
  if (name.length > 64) {
    return { valid: false, error: "スキル名は64文字以内である必要があります" };
  }
  if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(name)) {
    return {
      valid: false,
      error:
        "スキル名はハイフンケース（小文字、数字、ハイフン）である必要があります",
    };
  }
  return { valid: true };
}

function parseResources(value) {
  if (!value) {
    return { valid: true, resources: DEFAULT_RESOURCES };
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return { valid: true, resources: [] };
  }

  if (trimmed === "all") {
    return { valid: true, resources: DEFAULT_RESOURCES };
  }

  if (trimmed === "none") {
    return { valid: true, resources: [] };
  }

  const resources = trimmed
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  const unknown = resources.filter((item) => !ALLOWED_RESOURCES.has(item));
  if (unknown.length > 0) {
    return {
      valid: false,
      error: `未知のリソース指定: ${unknown.join(", ")}`,
    };
  }

  return { valid: true, resources: [...new Set(resources)] };
}

function createSkillTemplate(skillName, resources, includeLogUsage) {
  const today = new Date().toISOString().split("T")[0];
  const resourceSections = [];

  if (resources.includes("references")) {
    resourceSections.push(`### references/

- **TODO**: See [references/TODO.md](references/TODO.md)`);
  }

  if (resources.includes("scripts")) {
    const scriptLines = [];
    if (includeLogUsage) {
      scriptLines.push("- `scripts/log_usage.js`: フィードバック記録");
    }
    scriptLines.push("- TODO: 必要なスクリプトを追加");
    resourceSections.push(`### scripts/

${scriptLines.join("\n")}`);
  }

  if (resources.includes("assets")) {
    resourceSections.push(`### assets/

- TODO: テンプレート/素材を配置`);
  }

  const resourceBlock =
    resourceSections.length > 0
      ? `## リソース参照

${resourceSections.join("\n\n")}
`
      : "";

  return `---
name: ${skillName}
description: |
  TODO: スキルの概要説明（2-3行）

  Anchors:
  • TODO: アンカー名 / 適用: 適用範囲 / 目的: 目的

  Trigger:
  TODO: 発動条件を日本語で記述。
tags:
  - TODO
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
---

# ${skillName
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")}

## 概要

TODO: 1-2文でスキルの目的を説明

## ワークフロー

### Phase 1: TODO

**目的**: TODO

**アクション**:
1. TODO

### Phase 2: TODO

**目的**: TODO

**アクション**:
1. TODO

## ベストプラクティス

### すべきこと

- TODO

### 避けるべきこと

- TODO

${resourceBlock}

## 変更履歴

| Version | Date       | Changes  |
|---------|------------|----------|
| 1.0.0   | ${today} | 初版作成 |
`;
}

function createLogUsageScript() {
  return `#!/usr/bin/env node

/**
 * スキル使用記録スクリプト
 *
 * 18-skills.md §7.3 に準拠したフィードバック記録を行います。
 */

import { existsSync, mkdirSync, writeFileSync } from "fs";
import { randomBytes } from "crypto";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = join(__dirname, "..");

const EXIT_SUCCESS = 0;
const EXIT_ARGS_ERROR = 2;

function escapeBranch(branch) {
  const escaped = branch
    .toLowerCase()
    .replace(/\\//g, "-")
    .replace(/[^a-z0-9_-]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "");
  return (escaped || "unknown").slice(0, 64);
}

function compactTimestamp(now) {
  const pad = (n) => String(n).padStart(2, "0");
  return \`\${now.getUTCFullYear()}\${pad(now.getUTCMonth() + 1)}\${pad(now.getUTCDate())}-\${pad(now.getUTCHours())}\${pad(now.getUTCMinutes())}\${pad(now.getUTCSeconds())}\`;
}

function writeLogFragment(body, timestamp) {
  const branch = escapeBranch(process.env.GIT_BRANCH || process.env.BRANCH || "unknown");
  const author = process.env.GIT_AUTHOR_EMAIL || process.env.USER || "claude-code";
  const dir = join(SKILL_DIR, "LOGS");
  mkdirSync(dir, { recursive: true });
  for (let i = 0; i < 4; i += 1) {
    const nonce = randomBytes(4).toString("hex");
    const file = join(dir, \`\${compactTimestamp(new Date(timestamp))}-\${branch}-\${nonce}.md\`);
    if (existsSync(file)) continue;
    const content = \`---\\ntimestamp: \${timestamp.replace(/\\.\\d{3}Z$/, "Z")}\\nbranch: \${branch}\\nauthor: \${author}\\ntype: log\\n---\\n\${body.trimEnd()}\\n\`;
    writeFileSync(file, content, "utf-8");
    return;
  }
  throw new Error("fragment path collision unresolved after 4 attempts");
}

function showHelp() {
  console.log(\`
Usage: node log_usage.js [options]

Options:
  --result <success|failure>  実行結果（必須）
  --phase <name>              実行したPhase名（任意）
  --agent <name>              実行したエージェント名（任意）
  --notes <text>              追加のフィードバックメモ（任意）
  -h, --help                  このヘルプを表示
  \`);
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_SUCCESS);
  }

  const getArg = (name) => {
    const index = args.indexOf(name);
    return index !== -1 && args[index + 1] ? args[index + 1] : null;
  };

  const result = getArg("--result");
  const phase = getArg("--phase") || "unknown";
  const agent = getArg("--agent") || "unknown";
  const notes = getArg("--notes") || "";

  if (!result || !["success", "failure"].includes(result)) {
    console.error("Error: --result は success または failure を指定してください");
    process.exit(EXIT_ARGS_ERROR);
  }

  const timestamp = new Date().toISOString();
  const logEntry = \`
## [\${timestamp}]
- Agent: \${agent}
- Phase: \${phase}
- Result: \${result}
- Notes: \${notes || "なし"}
---
\`;

  try {
    writeLogFragment(logEntry, timestamp);
    console.log(\`✓ フィードバックを記録しました: \${result}\`);
  } catch (err) {
    console.error(\`Error: fragment ログの作成に失敗しました: \${err.message}\`);
    process.exit(1);
  }

  process.exit(EXIT_SUCCESS);
}

main().catch((err) => {
  console.error(\`Error: \${err.message}\`);
  process.exit(1);
});
`;
}

function createLogsTemplate() {
  return `# Skill Usage Logs

このファイルにはスキルの使用記録が追記されます。

---

`;
}

function createEvalsTemplate(skillName) {
  const today = new Date().toISOString().split("T")[0];
  return JSON.stringify(
    {
      skillName: skillName,
      currentLevel: 1,
      metrics: {
        totalUsageCount: 0,
        successCount: 0,
        failureCount: 0,
        successRate: 0,
        averageDuration: 0,
        lastEvaluated: null,
      },
      levelHistory: [
        {
          level: 1,
          achievedAt: today,
        },
      ],
      patterns: {
        commonErrors: [],
        slowPhases: [],
        successPatterns: [],
      },
    },
    null,
    2,
  );
}

function createPatternsTemplate() {
  return `# 実行パターン集

> **読み込み条件**: スキル実行時、改善検討時
> **更新タイミング**: パターンを発見したら追記

---

## 成功パターン

成功した実行から学んだベストプラクティス。

<!--
### パターン名
- **状況**: どんな状況で
- **アプローチ**: 何をしたか
- **結果**: なぜうまくいったか
- **適用条件**: いつ使うべきか
- **発見日**: YYYY-MM-DD
-->

---

## 失敗パターン（避けるべきこと）

失敗から学んだアンチパターン。

<!--
### パターン名
- **状況**: どんな状況で
- **問題**: 何が起きたか
- **原因**: なぜ失敗したか
- **教訓**: 何を学んだか
- **発見日**: YYYY-MM-DD
-->

---

## ガイドライン

実行時の判断基準。

<!--
### 判断基準名
- **状況**: どんな時に適用
- **指針**: どう判断すべきか
- **根拠**: なぜそう判断するか
-->
`;
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  // 引数解析
  const skillName = args.find((arg) => !arg.startsWith("-"));
  const pathIndex = args.indexOf("--path");
  const basePath =
    pathIndex !== -1 && args[pathIndex + 1]
      ? args[pathIndex + 1]
      : ".claude/skills";
  const resourcesIndex = args.indexOf("--resources");
  const resourcesValue =
    resourcesIndex !== -1 ? args[resourcesIndex + 1] : null;

  // スキル名検証
  const validation = validateSkillName(skillName);
  if (!validation.valid) {
    console.error(`Error: ${validation.error}`);
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  if (
    resourcesIndex !== -1 &&
    (!resourcesValue || resourcesValue.startsWith("-"))
  ) {
    console.error("Error: --resources の値が指定されていません");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resourcesResult = parseResources(resourcesValue);
  if (!resourcesResult.valid) {
    console.error(`Error: ${resourcesResult.error}`);
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resources = resourcesResult.resources;
  const includeLogUsage = resources.includes("scripts");

  // ベースパス存在確認
  if (!existsSync(basePath)) {
    console.error(`Error: ベースパスが存在しません: ${basePath}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  const skillDir = join(basePath, skillName);

  // 既存スキルの確認（冪等性: 既存の場合はスキップ）
  if (existsSync(skillDir)) {
    console.log(`ℹ スキルディレクトリは既に存在します: ${skillDir}`);
    console.log("  既存のファイルは上書きされません（冪等性）");
    process.exit(EXIT_CODES.SUCCESS);
  }

  // ディレクトリ作成
  const dirs = resources;

  try {
    mkdirSync(skillDir, { recursive: true });
    for (const dir of dirs) {
      mkdirSync(join(skillDir, dir), { recursive: true });
    }

    // SKILL.md 作成（書き込み前に Codex 検証ルール R-01〜R-05 を強制）
    const skillMdContent = createSkillTemplate(skillName, resources, includeLogUsage);
    const validation = validateSkillMdContent(skillMdContent);
    if (!validation.ok) {
      throw new Error(
        `[skill-creator] init_skill.js: SKILL.md 検証失敗:\n  - ${validation.errors.join("\n  - ")}`,
      );
    }
    writeFileSync(join(skillDir, "SKILL.md"), skillMdContent, "utf-8");

    // package.json 作成（自己完結型スキルのため）
    writeFileSync(
      join(skillDir, "package.json"),
      createPackageJson(skillName),
      "utf-8",
    );

    // フィードバック機構ファイル作成
    mkdirSync(join(skillDir, "LOGS"), { recursive: true });
    writeFileSync(join(skillDir, "LOGS", ".gitkeep"), "", "utf-8");

    // EVALS.json
    writeFileSync(
      join(skillDir, "EVALS.json"),
      createEvalsTemplate(skillName),
      "utf-8",
    );

    // references/patterns.md (references ディレクトリが存在する場合)
    if (resources.includes("references")) {
      writeFileSync(
        join(skillDir, "references", "patterns.md"),
        createPatternsTemplate(),
        "utf-8",
      );
    }

    if (includeLogUsage) {
      // log_usage.js 作成
      writeFileSync(
        join(skillDir, "scripts", "log_usage.js"),
        createLogUsageScript(),
        "utf-8",
      );
    }

    const createdItems = [
      join(skillDir, "SKILL.md"),
      join(skillDir, "package.json"),
      join(skillDir, "LOGS", ".gitkeep"),
      join(skillDir, "EVALS.json"),
    ];
    for (const dir of resources) {
      createdItems.push(`${join(skillDir, dir)}/`);
    }
    if (resources.includes("references")) {
      createdItems.push(join(skillDir, "references", "patterns.md"));
    }
    if (includeLogUsage) {
      createdItems.push(join(skillDir, "scripts", "log_usage.js"));
    }

    const nextSteps = ["SKILL.md の TODO を編集"];
    if (resources.includes("agents")) {
      nextSteps.push("必要に応じて agents/*.md を作成");
    }
    if (resources.includes("references")) {
      nextSteps.push("必要に応じて references/*.md を作成");
    }
    if (resources.includes("scripts")) {
      nextSteps.push("必要に応じて pnpm add <package> で依存関係を追加");
    }
    nextSteps.push("quick_validate.js で検証");

    console.log(`✓ スキルを初期化しました: ${skillDir}`);
    console.log(`
作成された内容:
${createdItems.map((item) => `  - ${item}`).join("\n")}

次のステップ:
${nextSteps.map((step, index) => `  ${index + 1}. ${step}`).join("\n")}
`);

    process.exit(EXIT_CODES.SUCCESS);
  } catch (err) {
    console.error(`Error: ディレクトリ作成に失敗しました: ${err.message}`);
    process.exit(EXIT_CODES.ERROR);
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
