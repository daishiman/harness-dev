#!/usr/bin/env node

/**
 * リンク検証スクリプト
 *
 * SKILL.mdおよびagents/*.md内のリンクが正しいファイルを参照しているかを検証します。
 *
 * 使用例:
 *   node scripts/validate_links.js .claude/skills/my-skill
 *
 * 終了コード:
 *   0: 検証成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 検証失敗
 */

import { readFileSync, existsSync, readdirSync, statSync } from "fs";
import { join, basename } from "path";
import {
  EXIT_CODES,
  hasArg,
  resolvePath,
  normalizeLink,
  extractLinks,
} from "./utils.js";

function showHelp() {
  console.log(`
リンク検証スクリプト

Usage:
  node validate_links.js <skill-path> [options]

Arguments:
  <skill-path>    検証するスキルのパス（必須）

Options:
  --verbose       詳細な検証結果を表示
  --fix           壊れたリンクを報告（修正は行わない）
  -h, --help      このヘルプを表示

Validation checks:
  - SKILL.md内のMarkdownリンクが存在するファイルを参照
  - agents/*.md内のリンクが存在するファイルを参照
  - references/内のファイルがSKILL.mdからリンクされている
  - schemas/内のファイルがSKILL.mdからリンクされている

Examples:
  node scripts/validate_links.js .claude/skills/my-skill
  node scripts/validate_links.js .claude/skills/my-skill --verbose
`);
}

/**
 * Markdownコンテンツからリンクを抽出（外部URL・アンカーを除外）
 */
function extractMarkdownLinks(content) {
  return extractLinks(content).filter(
    (link) =>
      !link.startsWith("http://") &&
      !link.startsWith("https://") &&
      !link.startsWith("#")
  );
}

function validateLinks(skillPath, verbose = false) {
  const errors = [];
  const warnings = [];
  const passed = [];
  const skillName = basename(skillPath);

  // SKILL.md検証
  const skillMdPath = join(skillPath, "SKILL.md");
  if (!existsSync(skillMdPath)) {
    errors.push("SKILL.mdが存在しません");
    return { errors, warnings, passed };
  }

  const skillMdContent = readFileSync(skillMdPath, "utf-8");
  const skillMdLinks = extractMarkdownLinks(skillMdContent);

  // SKILL.md内のリンク検証
  for (const link of skillMdLinks) {
    const normalizedLink = normalizeLink(link, skillName);
    const linkPath = join(skillPath, normalizedLink);
    if (!existsSync(linkPath)) {
      errors.push(`SKILL.md: 壊れたリンク: ${link}`);
    } else {
      passed.push(`SKILL.md: 有効なリンク: ${link}`);
    }
  }

  // agents/内のリンク検証
  const agentsPath = join(skillPath, "agents");
  if (existsSync(agentsPath) && statSync(agentsPath).isDirectory()) {
    const agentFiles = readdirSync(agentsPath).filter((f) => f.endsWith(".md"));
    for (const agentFile of agentFiles) {
      const agentPath = join(agentsPath, agentFile);
      const agentContent = readFileSync(agentPath, "utf-8");
      const agentLinks = extractMarkdownLinks(agentContent);

      for (const link of agentLinks) {
        // リンクを正規化（.claude/skills/{skill-name}/ プレフィックスを除去）
        const normalizedLink = normalizeLink(link, skillName);

        // agents/からの相対パスを解決
        let resolvedLink;
        if (normalizedLink.startsWith("../")) {
          resolvedLink = join(skillPath, normalizedLink.substring(3));
        } else if (normalizedLink.startsWith("references/") || normalizedLink.startsWith("scripts/") || normalizedLink.startsWith("assets/") || normalizedLink.startsWith("schemas/")) {
          // スキルディレクトリからの相対パス
          resolvedLink = join(skillPath, normalizedLink);
        } else {
          resolvedLink = join(agentsPath, normalizedLink);
        }

        if (!existsSync(resolvedLink)) {
          errors.push(`agents/${agentFile}: 壊れたリンク: ${link}`);
        } else {
          passed.push(`agents/${agentFile}: 有効なリンク: ${link}`);
        }
      }
    }
  }

  // references/内のファイルがリンクされているか確認
  const referencesPath = join(skillPath, "references");
  if (existsSync(referencesPath) && statSync(referencesPath).isDirectory()) {
    const refFiles = readdirSync(referencesPath).filter((f) => f.endsWith(".md"));
    for (const refFile of refFiles) {
      const refLink = `references/${refFile}`;
      if (!skillMdContent.includes(refLink)) {
        warnings.push(`references/${refFile}がSKILL.mdからリンクされていません`);
      } else {
        passed.push(`references/${refFile}がSKILL.mdからリンクされている`);
      }
    }
  }

  // schemas/内のファイルがリンクされているか確認
  const schemasPath = join(skillPath, "schemas");
  if (existsSync(schemasPath) && statSync(schemasPath).isDirectory()) {
    const schemaFiles = readdirSync(schemasPath).filter((f) => f.endsWith(".json"));
    for (const schemaFile of schemaFiles) {
      const schemaLink = `schemas/${schemaFile}`;
      if (!skillMdContent.includes(schemaLink)) {
        warnings.push(`schemas/${schemaFile}がSKILL.mdからリンクされていません`);
      } else {
        passed.push(`schemas/${schemaFile}がSKILL.mdからリンクされている`);
      }
    }
  }

  // scripts/内のファイルがリンクされているか確認
  const scriptsPath = join(skillPath, "scripts");
  if (existsSync(scriptsPath) && statSync(scriptsPath).isDirectory()) {
    const scriptFiles = readdirSync(scriptsPath).filter((f) => f.endsWith(".js"));
    for (const scriptFile of scriptFiles) {
      // scripts/はSKILL.md内で`scripts/xxx.js`形式で参照されることが多い
      if (!skillMdContent.includes(scriptFile)) {
        warnings.push(`scripts/${scriptFile}がSKILL.mdで言及されていません`);
      } else {
        passed.push(`scripts/${scriptFile}がSKILL.mdで言及されている`);
      }
    }
  }

  return { errors, warnings, passed };
}

async function main() {
  const args = process.argv.slice(2);

  if (hasArg(args, "-h", "--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const verbose = hasArg(args, "--verbose");
  const skillPath = args.find((arg) => !arg.startsWith("-"));

  if (!skillPath) {
    console.error("Error: スキルパスが指定されていません");
    showHelp();
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedPath = resolvePath(skillPath);

  if (!existsSync(resolvedPath)) {
    console.error(`Error: パスが存在しません: ${resolvedPath}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  console.log(`リンクを検証中: ${skillPath}`);
  const { errors, warnings, passed } = validateLinks(resolvedPath, verbose);

  if (verbose && passed.length > 0) {
    console.log("\n✓ 有効なリンク:");
    passed.forEach((p) => console.log(`  - ${p}`));
  }

  if (warnings.length > 0) {
    console.log("\n⚠ 警告:");
    warnings.forEach((w) => console.log(`  - ${w}`));
  }

  if (errors.length > 0) {
    console.log("\n✗ エラー:");
    errors.forEach((e) => console.log(`  - ${e}`));
    console.log(`\n結果: ✗ 検証失敗 (${passed.length}パス, ${errors.length}エラー, ${warnings.length}警告)`);
    process.exit(EXIT_CODES.VALIDATION_FAILED);
  }

  console.log(`\n結果: ✓ 検証成功 (${passed.length}パス, ${errors.length}エラー, ${warnings.length}警告)`);
  process.exit(EXIT_CODES.SUCCESS);
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
