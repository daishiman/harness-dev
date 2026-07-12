#!/usr/bin/env node

/**
 * スキル構造検証スクリプト
 *
 * 18-skills.md §6.6 および §8.1 に準拠した検証を行います。
 *
 * 使用例:
 *   node quick_validate.js .claude/skills/my-skill
 *
 * 終了コード:
 *   0: 成功（すべての検証をパス）
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 検証失敗
 */

import { readFileSync, existsSync, statSync, readdirSync } from "fs";
import { join, basename } from "path";
import {
  EXIT_CODES,
  hasArg,
  parseFrontmatter,
  ValidationResult,
} from "./utils.js";

function showHelp() {
  console.log(`
スキル構造検証スクリプト (18-skills.md §6.6 準拠)

Usage:
  node quick_validate.js <skill-path> [options]

Arguments:
  <skill-path>    検証するスキルのパス

Options:
  --verbose       詳細な検証結果を表示
  -h, --help      このヘルプを表示

Validation checks (§8.1):
  - SKILL.md の存在
  - SKILL.md が 500 行以内
  - YAML frontmatter の有効性
  - name がハイフンケース（最大64文字）
  - description が 1024 文字以内
  - description に Anchors と Trigger が含まれる
  - 不要な補助ドキュメント（README.md等）がない
  - references/ のファイルが SKILL.md からリンクされている
  - agents/*.md が Task仕様書テンプレに準拠

Examples:
  node quick_validate.js .claude/skills/my-skill
  node quick_validate.js .claude/skills/my-skill --verbose
  `);
}

/**
 * スキル構造検証クラス（validate_structure用拡張）
 * utils.jsのValidationResultを拡張して、passedリストと詳細表示をサポート
 */
class StructureValidationResult extends ValidationResult {
  constructor() {
    super();
    this.passed = [];
  }

  addError(message) {
    this.errors.push({ message });
  }

  addWarning(message) {
    this.warnings.push({ message });
  }

  addPassed(message) {
    this.passed.push(message);
  }

  isValid() {
    return this.errors.length === 0;
  }

  print(verbose = false) {
    if (verbose) {
      console.log("\n=== 検証結果 ===\n");
      if (this.passed.length > 0) {
        console.log("✓ パスした項目:");
        this.passed.forEach((p) => console.log(`  - ${p}`));
      }
    }

    if (this.warnings.length > 0) {
      console.log("\n⚠ 警告:");
      this.warnings.forEach((w) => console.log(`  - ${w.message || w}`));
    }

    if (this.errors.length > 0) {
      console.log("\n✗ エラー:");
      this.errors.forEach((e) => console.log(`  - ${e.message || e}`));
    }

    console.log(
      `\n結果: ${this.isValid() ? "✓ 検証成功" : "✗ 検証失敗"} (${this.passed.length}項目パス, ${this.errors.length}エラー, ${this.warnings.length}警告)`,
    );
  }
}

function validateSkill(skillPath, verbose = false) {
  const result = new StructureValidationResult();
  const skillName = basename(skillPath);

  // 1. SKILL.md の存在確認
  const skillMdPath = join(skillPath, "SKILL.md");
  if (!existsSync(skillMdPath)) {
    result.addError("SKILL.md が存在しません");
    return result;
  }
  result.addPassed("SKILL.md が存在する");

  const content = readFileSync(skillMdPath, "utf-8");
  const lines = content.split("\n");

  // 2. 行数制限（500行以内）
  if (lines.length > 500) {
    result.addError(`SKILL.md が 500 行を超えています (${lines.length}行)`);
  } else {
    result.addPassed(`SKILL.md が 500 行以内 (${lines.length}行)`);
  }

  // 3. YAML frontmatter の検証
  const frontmatter = parseFrontmatter(content);
  if (!frontmatter) {
    result.addError("YAML frontmatter が見つかりません");
    return result;
  }
  result.addPassed("YAML frontmatter が存在する");

  // 4. name フィールドの検証
  if (!frontmatter.name) {
    result.addError("name フィールドが存在しません");
  } else {
    const name = frontmatter.name;
    if (name.length > 64) {
      result.addError(`name が 64 文字を超えています (${name.length}文字)`);
    } else if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(name)) {
      result.addError(`name がハイフンケースではありません: ${name}`);
    } else if (name !== skillName) {
      result.addWarning(
        `name (${name}) がディレクトリ名 (${skillName}) と一致しません`,
      );
    } else {
      result.addPassed(`name がハイフンケース: ${name}`);
    }
  }

  // 5. description フィールドの検証
  if (!frontmatter.description) {
    result.addError("description フィールドが存在しません");
  } else {
    const desc = frontmatter.description;
    if (desc.length > 1024) {
      result.addError(
        `description が 1024 文字を超えています (${desc.length}文字)`,
      );
    } else {
      result.addPassed(`description が 1024 文字以内 (${desc.length}文字)`);
    }

    if (desc.includes("<") || desc.includes(">")) {
      result.addError("description に角括弧 (<>) が含まれています");
    }

    // Anchors と Trigger の存在確認
    if (!desc.includes("Anchors:") && !desc.includes("•")) {
      result.addWarning(
        "description に Anchors が含まれていない可能性があります",
      );
    } else {
      result.addPassed("description に Anchors が含まれている");
    }

    if (
      !desc.includes("Trigger:") &&
      !desc.toLowerCase().includes("use when")
    ) {
      result.addWarning(
        "description に Trigger が含まれていない可能性があります",
      );
    } else {
      result.addPassed("description に Trigger が含まれている");
    }
  }

  // 6. 不要な補助ドキュメントの確認
  const forbiddenFiles = [
    "README.md",
    "INSTALLATION_GUIDE.md",
    "QUICK_REFERENCE.md",
  ];
  for (const file of forbiddenFiles) {
    if (existsSync(join(skillPath, file))) {
      result.addError(`不要な補助ドキュメントが存在します: ${file}`);
    }
  }
  result.addPassed("不要な補助ドキュメントが存在しない");

  // 7. references/ のリンク確認
  const referencesPath = join(skillPath, "references");
  if (existsSync(referencesPath) && statSync(referencesPath).isDirectory()) {
    const refFiles = readdirSync(referencesPath).filter((f) =>
      f.endsWith(".md"),
    );
    for (const refFile of refFiles) {
      const refLink = `references/${refFile}`;
      if (!content.includes(refLink)) {
        result.addWarning(
          `references/${refFile} が SKILL.md からリンクされていません`,
        );
      }
    }
    if (refFiles.length > 0) {
      result.addPassed(`references/ に ${refFiles.length} ファイル存在`);
    }
  }

  // 8. agents/*.md の Task仕様書テンプレ準拠確認
  const agentsPath = join(skillPath, "agents");
  if (existsSync(agentsPath) && statSync(agentsPath).isDirectory()) {
    const agentFiles = readdirSync(agentsPath).filter((f) => f.endsWith(".md"));
    const requiredSections = [
      "## 1. メタ情報",
      "## 2. プロフィール",
      "## 3. 知識ベース",
      "## 4. 実行仕様",
      "## 5. インターフェース",
    ];

    for (const agentFile of agentFiles) {
      const agentContent = readFileSync(join(agentsPath, agentFile), "utf-8");
      const missingSections = requiredSections.filter(
        (section) => !agentContent.includes(section),
      );
      if (missingSections.length > 0) {
        result.addWarning(
          `agents/${agentFile} に不足セクション: ${missingSections.join(", ")}`,
        );
      } else {
        result.addPassed(`agents/${agentFile} が Task仕様書テンプレに準拠`);
      }
    }
  }

  return result;
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

  if (!existsSync(skillPath)) {
    console.error(`Error: パスが存在しません: ${skillPath}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  console.log(`スキルを検証中: ${skillPath}`);
  const result = validateSkill(skillPath, verbose);
  result.print(verbose);

  process.exit(result.isValid() ? EXIT_CODES.SUCCESS : EXIT_CODES.VALIDATION_FAILED);
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
