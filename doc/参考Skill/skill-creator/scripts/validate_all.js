#!/usr/bin/env node

/**
 * 全体検証スクリプト
 *
 * スキルディレクトリの全体構造とファイルを検証します。
 * validate_structure.js、validate_links.js、validate_schema.jsを統合した包括的な検証。
 *
 * 使用例:
 *   node scripts/validate_all.js .claude/skills/my-skill
 *   node scripts/validate_all.js .claude/skills/my-skill --fix
 *
 * 終了コード:
 *   0: 検証成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: パス不在
 *   4: 検証失敗
 */

import { readFileSync, existsSync, readdirSync, statSync, writeFileSync, mkdirSync } from "fs";
import { resolve, dirname, join, basename, extname } from "path";
import { fileURLToPath } from "url";
import { EXIT_CODES, getArg, normalizeLink } from "./utils.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

// 標準ディレクトリ構造
const STANDARD_DIRS = ["agents", "scripts", "schemas", "references", "assets"];
const REQUIRED_FILES = ["SKILL.md"];
const FORBIDDEN_FILES = ["README.md", "readme.md", "index.md", "INDEX.md"];


function showHelp() {
  console.log(`
全体検証スクリプト

Usage:
  node validate_all.js <skill-path> [options]

Options:
  --fix              自動修正可能な問題を修正
  --output <path>    検証結果の出力先（デフォルト: .tmp/validation-result.json）
  --verbose          詳細な検証結果を表示
  -h, --help         このヘルプを表示

Validations:
  1. 構造検証    - 必須ファイル、ディレクトリ構造
  2. リンク検証  - SKILL.md内の相対パス参照
  3. 品質検証    - SKILL.md行数、frontmatter形式
  4. 禁止検証    - 禁止ファイルの存在チェック
`);
}

function validateStructure(skillPath) {
  const errors = [];
  const warnings = [];

  // 必須ファイルの確認
  for (const file of REQUIRED_FILES) {
    if (!existsSync(join(skillPath, file))) {
      errors.push({ type: "missing", file, message: `必須ファイルが存在しません: ${file}` });
    }
  }

  // 禁止ファイルの確認
  for (const file of FORBIDDEN_FILES) {
    if (existsSync(join(skillPath, file))) {
      errors.push({ type: "forbidden", file, message: `禁止ファイルが存在します: ${file}` });
    }
  }

  // ディレクトリ構造の確認
  const existingDirs = [];
  const emptyDirs = [];

  for (const dir of STANDARD_DIRS) {
    const dirPath = join(skillPath, dir);
    if (existsSync(dirPath)) {
      existingDirs.push(dir);
      const files = readdirSync(dirPath).filter((f) => !f.startsWith("."));
      if (files.length === 0) {
        warnings.push({ type: "empty", dir, message: `空のディレクトリ: ${dir}` });
        emptyDirs.push(dir);
      }
    }
  }

  // スキル名の検証
  const skillName = basename(skillPath);
  if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(skillName)) {
    errors.push({
      type: "naming",
      file: skillPath,
      message: `スキル名がハイフンケースではありません: ${skillName}`
    });
  }

  return { errors, warnings, existingDirs, emptyDirs };
}

function validateSkillMd(skillPath) {
  const errors = [];
  const warnings = [];
  const skillMdPath = join(skillPath, "SKILL.md");

  if (!existsSync(skillMdPath)) {
    return { errors: [{ type: "missing", message: "SKILL.mdが存在しません" }], warnings };
  }

  const content = readFileSync(skillMdPath, "utf-8");
  const lines = content.split("\n");

  // 行数チェック（500行以内）
  if (lines.length > 500) {
    errors.push({
      type: "size",
      message: `SKILL.mdが500行を超えています: ${lines.length}行`
    });
  } else if (lines.length > 400) {
    warnings.push({
      type: "size",
      message: `SKILL.mdが400行を超えています: ${lines.length}行（500行上限に注意）`
    });
  }

  // frontmatter検証
  if (!content.startsWith("---")) {
    errors.push({ type: "frontmatter", message: "frontmatterが存在しません（---で始まる）" });
  } else {
    const frontmatterEnd = content.indexOf("---", 3);
    if (frontmatterEnd === -1) {
      errors.push({ type: "frontmatter", message: "frontmatterが閉じられていません" });
    } else {
      const frontmatter = content.substring(3, frontmatterEnd);

      // name検証
      if (!/name:\s*[a-z0-9-]+/.test(frontmatter)) {
        errors.push({ type: "frontmatter", message: "name フィールドがありません" });
      }

      // description検証
      if (!/description:/.test(frontmatter)) {
        errors.push({ type: "frontmatter", message: "description フィールドがありません" });
      }

      // Markdown禁止検証（description内）
      const descMatch = frontmatter.match(/description:\s*\|?\s*([\s\S]*?)(?=\n[a-z-]+:|$)/);
      if (descMatch) {
        const desc = descMatch[1];
        if (/\[.*?\]\(.*?\)/.test(desc)) {
          errors.push({
            type: "frontmatter",
            message: "description内にMarkdownリンクが含まれています（禁止）"
          });
        }
      }

      // Anchors検証
      if (!/Anchors:/.test(frontmatter)) {
        warnings.push({ type: "frontmatter", message: "Anchors セクションがありません" });
      } else {
        // Anchorsセクションのみを抽出（Trigger:またはallowed-tools:まで）
        const anchorsMatch = frontmatter.match(/Anchors:([\s\S]*?)(?=Trigger:|allowed-tools:|$)/);
        if (anchorsMatch) {
          const anchorsSection = anchorsMatch[1];
          // Anchorsセクション内で行頭の - または * をチェック
          if (/^\s*[-*]\s+/m.test(anchorsSection)) {
            errors.push({
              type: "frontmatter",
              message: "Anchorsに「-」「*」が使用されています（「•」を使用してください）"
            });
          }
        }
      }

      // Trigger検証
      if (!/Trigger:/.test(frontmatter)) {
        warnings.push({ type: "frontmatter", message: "Trigger セクションがありません" });
      }
    }
  }

  return { errors, warnings, lineCount: lines.length };
}

function validateLinks(skillPath) {
  const errors = [];
  const warnings = [];
  const skillMdPath = join(skillPath, "SKILL.md");
  const skillName = basename(skillPath);

  if (!existsSync(skillMdPath)) {
    return { errors: [], warnings };
  }

  const content = readFileSync(skillMdPath, "utf-8");

  // Markdownリンクの抽出
  const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g;
  let match;

  while ((match = linkPattern.exec(content)) !== null) {
    const linkText = match[1];
    const linkPath = match[2];

    // 外部URLはスキップ
    if (linkPath.startsWith("http://") || linkPath.startsWith("https://")) {
      continue;
    }

    // リンクパスを正規化（.claude/skills/{skill-name}/ プレフィックスを除去）
    const normalizedPath = normalizeLink(linkPath, skillName);

    // 相対パスの検証
    const resolvedPath = join(skillPath, normalizedPath);
    if (!existsSync(resolvedPath)) {
      errors.push({
        type: "broken_link",
        link: linkPath,
        text: linkText,
        message: `リンク先が存在しません: ${linkPath}`
      });
    }
  }

  // agents/内のファイル参照確認
  const agentsDir = join(skillPath, "agents");
  if (existsSync(agentsDir)) {
    const agentFiles = readdirSync(agentsDir).filter((f) => f.endsWith(".md"));
    for (const file of agentFiles) {
      const linkPath = `agents/${file}`;
      if (!content.includes(linkPath)) {
        warnings.push({
          type: "unreferenced",
          file: linkPath,
          message: `SKILL.mdから参照されていません: ${linkPath}`
        });
      }
    }
  }

  return { errors, warnings };
}

function validateAgents(skillPath) {
  const errors = [];
  const warnings = [];
  const agentsDir = join(skillPath, "agents");

  if (!existsSync(agentsDir)) {
    return { errors, warnings };
  }

  const agentFiles = readdirSync(agentsDir).filter((f) => f.endsWith(".md"));

  for (const file of agentFiles) {
    const filePath = join(agentsDir, file);
    const content = readFileSync(filePath, "utf-8");

    // 5セクション構造の簡易チェック
    const requiredSections = ["メタ情報", "プロフィール", "知識ベース", "実行仕様", "インターフェース"];
    const missingSections = requiredSections.filter(
      (s) => !new RegExp(`##\\s*\\d*\\.?\\s*${s}`, "m").test(content)
    );

    if (missingSections.length > 0) {
      warnings.push({
        type: "structure",
        file: `agents/${file}`,
        message: `5セクション構造が不完全: 不足=${missingSections.join(", ")}`
      });
    }
  }

  return { errors, warnings };
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const skillPath = args.find((arg) => !arg.startsWith("-"));
  const outputPath = getArg(args, "--output") || ".tmp/validation-result.json";
  const verbose = args.includes("--verbose");
  const fix = args.includes("--fix");

  if (!skillPath) {
    console.error("Error: スキルパスを指定してください");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedPath = resolve(process.cwd(), skillPath);
  if (!existsSync(resolvedPath)) {
    console.error(`Error: パスが存在しません: ${resolvedPath}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  console.log("=== スキル全体検証 ===");
  console.log(`パス: ${skillPath}`);
  console.log("");

  // 各検証を実行
  const structureResult = validateStructure(resolvedPath);
  const skillMdResult = validateSkillMd(resolvedPath);
  const linksResult = validateLinks(resolvedPath);
  const agentsResult = validateAgents(resolvedPath);

  // 結果集計
  const allErrors = [
    ...structureResult.errors,
    ...skillMdResult.errors,
    ...linksResult.errors,
    ...agentsResult.errors
  ];

  const allWarnings = [
    ...structureResult.warnings,
    ...skillMdResult.warnings,
    ...linksResult.warnings,
    ...agentsResult.warnings
  ];

  // 結果表示
  console.log("--- 構造検証 ---");
  console.log(`  ディレクトリ: ${structureResult.existingDirs.join(", ") || "なし"}`);
  if (structureResult.emptyDirs.length > 0) {
    console.log(`  空ディレクトリ: ${structureResult.emptyDirs.join(", ")}`);
  }

  console.log("");
  console.log("--- SKILL.md検証 ---");
  console.log(`  行数: ${skillMdResult.lineCount || "N/A"}`);

  console.log("");
  console.log("--- エラー ---");
  if (allErrors.length === 0) {
    console.log("  なし");
  } else {
    for (const err of allErrors) {
      console.log(`  ✗ ${err.message}`);
    }
  }

  console.log("");
  console.log("--- 警告 ---");
  if (allWarnings.length === 0) {
    console.log("  なし");
  } else {
    for (const warn of allWarnings) {
      console.log(`  ⚠ ${warn.message}`);
    }
  }

  // 結果JSON
  const output = {
    timestamp: new Date().toISOString(),
    skillPath,
    summary: {
      errors: allErrors.length,
      warnings: allWarnings.length,
      passed: allErrors.length === 0
    },
    details: {
      structure: structureResult,
      skillMd: skillMdResult,
      links: linksResult,
      agents: agentsResult
    },
    errors: allErrors,
    warnings: allWarnings
  };

  // 出力ディレクトリ作成
  const outputDir = dirname(resolve(process.cwd(), outputPath));
  if (!existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true });
  }

  // 結果を出力
  writeFileSync(resolve(process.cwd(), outputPath), JSON.stringify(output, null, 2), "utf-8");

  console.log("");
  console.log("=== 結果 ===");
  console.log(`エラー: ${allErrors.length}, 警告: ${allWarnings.length}`);
  console.log(`出力: ${outputPath}`);

  if (allErrors.length > 0) {
    console.log("\n✗ 検証失敗");
    process.exit(EXIT_CODES.VALIDATION_FAILED);
  }

  console.log("\n✓ 検証成功");
  process.exit(EXIT_CODES.SUCCESS);
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
