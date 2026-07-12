#!/usr/bin/env node

/**
 * スキルリスト更新スクリプト
 *
 * スキルのdescriptionをskill_list.mdに追記/更新します。
 *
 * 使用例:
 *   node update_skill_list.js --skill-path .claude/skills/my-skill
 *   node update_skill_list.js --skill-path .claude/skills/my-skill --dry-run
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 更新失敗
 */

import { readFileSync, writeFileSync, existsSync } from "fs";
import { resolve, dirname, join, basename } from "path";
import { fileURLToPath } from "url";
import { EXIT_CODES, getArg } from "./utils.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DEFAULT_SKILL_LIST_PATH = ".claude/skills/skill_list.md";

function showHelp() {
  console.log(`
スキルリスト更新スクリプト

Usage:
  node update_skill_list.js --skill-path <path> [options]

Options:
  --skill-path <path>     スキルディレクトリのパス（必須）
  --skill-list <path>     skill_list.mdのパス（デフォルト: ${DEFAULT_SKILL_LIST_PATH}）
  --dry-run               実際の更新は行わず、変更内容を表示のみ
  -h, --help              このヘルプを表示

Examples:
  node update_skill_list.js --skill-path .claude/skills/my-skill
  node update_skill_list.js --skill-path .claude/skills/my-skill --dry-run
`);
}

/**
 * SKILL.mdからfrontmatterを解析
 */
function parseFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return null;

  const frontmatter = {};
  const lines = match[1].split("\n");
  let currentKey = null;
  let multilineValue = "";
  let inMultiline = false;

  for (const line of lines) {
    if (inMultiline) {
      if (
        line.match(/^\S/) &&
        !line.startsWith(" ") &&
        !line.startsWith("\t")
      ) {
        frontmatter[currentKey] = multilineValue.trim();
        inMultiline = false;
      } else {
        multilineValue += line + "\n";
        continue;
      }
    }

    const keyMatch = line.match(/^(\w+(?:-\w+)*):\s*(.*)/);
    if (keyMatch) {
      currentKey = keyMatch[1];
      const value = keyMatch[2];
      if (value === "|" || value === ">") {
        inMultiline = true;
        multilineValue = "";
      } else if (value) {
        frontmatter[currentKey] = value;
      }
    }
  }

  if (inMultiline && currentKey) {
    frontmatter[currentKey] = multilineValue.trim();
  }

  return frontmatter;
}

/**
 * descriptionから概要行を抽出（最初の行または2行目まで）
 */
function extractSummary(description) {
  if (!description) return "";

  // 最初の段落（Anchors:やTrigger:の前）を取得
  const lines = description.split("\n");
  const summaryLines = [];

  for (const line of lines) {
    const trimmed = line.trim();
    // Anchors:やTrigger:で終了
    if (trimmed.startsWith("Anchors:") || trimmed.startsWith("Trigger:") || trimmed.startsWith("•")) {
      break;
    }
    if (trimmed) {
      summaryLines.push(trimmed);
    }
  }

  // 最大80文字に制限
  let summary = summaryLines.join(" ");
  if (summary.length > 80) {
    summary = summary.substring(0, 77) + "...";
  }

  return summary;
}

/**
 * skill_list.mdを更新
 */
function updateSkillList(skillListContent, skillName, skillPath, summary) {
  const lines = skillListContent.split("\n");
  const skillMdPath = `.claude/skills/${skillName}/SKILL.md`;
  const skillMdLink = `**.claude/skills/${skillName}/SKILL.md**`;

  // 既存のエントリを検索
  let existingLineIndex = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes(skillMdPath) || lines[i].includes(skillName + "/SKILL.md")) {
      existingLineIndex = i;
      break;
    }
  }

  // 新しいテーブル行を作成
  const newRow = `| ${skillMdLink} | \`${skillMdPath}\` | ${summary} |`;

  if (existingLineIndex !== -1) {
    // 既存のエントリを更新
    lines[existingLineIndex] = newRow;
    return {
      content: lines.join("\n"),
      action: "updated",
      line: existingLineIndex + 1
    };
  } else {
    // 追加位置を探す（「未分類」セクションまたはファイル末尾）
    let insertIndex = lines.length;

    // 「未分類」または「Uncategorized」セクションを探す
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].includes("未分類") || lines[i].toLowerCase().includes("uncategorized")) {
        // テーブルヘッダーの後を探す
        for (let j = i + 1; j < lines.length; j++) {
          if (lines[j].startsWith("|") && lines[j].includes("---")) {
            insertIndex = j + 1;
            break;
          }
        }
        break;
      }
    }

    // 「未分類」セクションがない場合、ファイル末尾に追加
    if (insertIndex === lines.length) {
      // 末尾に未分類セクションを追加
      const uncategorizedSection = `
## 未分類

| スキル名 | パス | 概要 |
| --- | --- | --- |
${newRow}
`;
      return {
        content: skillListContent + uncategorizedSection,
        action: "added (new section)",
        line: lines.length + 5
      };
    }

    // 既存のセクションに追加
    lines.splice(insertIndex, 0, newRow);
    return {
      content: lines.join("\n"),
      action: "added",
      line: insertIndex + 1
    };
  }
}

/**
 * 最終更新日を更新
 */
function updateLastModified(content, skillName) {
  const today = new Date().toISOString().split("T")[0];
  const lastUpdateRegex = /最終更新日: \d{4}-\d{2}-\d{2}[^\n]*/;

  if (lastUpdateRegex.test(content)) {
    return content.replace(
      lastUpdateRegex,
      `最終更新日: ${today} (${skillName}更新)`
    );
  }

  // 最終更新日がない場合は先頭に追加
  const lines = content.split("\n");
  if (lines[0].startsWith("#")) {
    lines.splice(1, 0, "", `最終更新日: ${today} (${skillName}更新)`);
    return lines.join("\n");
  }

  return `最終更新日: ${today} (${skillName}更新)\n\n${content}`;
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const skillPath = getArg(args, "--skill-path");
  const skillListPath = getArg(args, "--skill-list") || DEFAULT_SKILL_LIST_PATH;
  const dryRun = args.includes("--dry-run");

  if (!skillPath) {
    console.error("Error: --skill-path は必須です");
    showHelp();
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  // スキルパスの解決
  const resolvedSkillPath = resolve(process.cwd(), skillPath);
  const skillMdPath = join(resolvedSkillPath, "SKILL.md");

  if (!existsSync(skillMdPath)) {
    console.error(`Error: SKILL.mdが存在しません: ${skillMdPath}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  // skill_list.mdの解決
  const resolvedSkillListPath = resolve(process.cwd(), skillListPath);
  if (!existsSync(resolvedSkillListPath)) {
    console.error(`Error: skill_list.mdが存在しません: ${resolvedSkillListPath}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  // SKILL.mdを読み込み
  const skillMdContent = readFileSync(skillMdPath, "utf-8");
  const frontmatter = parseFrontmatter(skillMdContent);

  if (!frontmatter || !frontmatter.name) {
    console.error("Error: SKILL.mdのfrontmatterからnameを取得できません");
    process.exit(EXIT_CODES.ERROR);
  }

  const skillName = frontmatter.name;
  const description = frontmatter.description || "";
  const summary = extractSummary(description);

  console.log("=== スキルリスト更新 ===");
  console.log(`スキル名: ${skillName}`);
  console.log(`概要: ${summary}`);
  console.log(`スキルリスト: ${skillListPath}`);
  console.log(`モード: ${dryRun ? "DRY-RUN" : "実行"}`);
  console.log("");

  // skill_list.mdを読み込み
  const skillListContent = readFileSync(resolvedSkillListPath, "utf-8");

  // 更新
  const result = updateSkillList(skillListContent, skillName, skillPath, summary);
  const finalContent = updateLastModified(result.content, skillName);

  console.log(`アクション: ${result.action}`);
  console.log(`行番号: ${result.line}`);

  if (dryRun) {
    console.log("\n[DRY-RUN] 以下の行が追加/更新されます:");
    const skillMdLink = `**.claude/skills/${skillName}/SKILL.md**`;
    console.log(`| ${skillMdLink} | \`.claude/skills/${skillName}/SKILL.md\` | ${summary} |`);
    process.exit(EXIT_CODES.SUCCESS);
  }

  // 実際に更新
  try {
    writeFileSync(resolvedSkillListPath, finalContent, "utf-8");
    console.log("\n✓ skill_list.mdを更新しました");
    process.exit(EXIT_CODES.SUCCESS);
  } catch (err) {
    console.error(`Error: ファイルの書き込みに失敗しました: ${err.message}`);
    process.exit(EXIT_CODES.UPDATE_FAILED);
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
