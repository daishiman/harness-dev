#!/usr/bin/env node

/**
 * モード判定スクリプト
 *
 * ユーザー要求からスキルクリエイターの実行モードを判定します。
 *
 * 使用例:
 *   node scripts/detect_mode.js --request "新しいスキルを作成"
 *   node scripts/detect_mode.js --request "skill-creatorを更新" --skill-path .claude/skills/skill-creator
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 */

import { existsSync, writeFileSync, mkdirSync } from "fs";
import { dirname } from "path";
import {
  EXIT_CODES,
  getArg,
  hasArg,
  resolvePath,
  getSkillDir,
} from "./utils.js";

const SKILL_DIR = getSkillDir(import.meta.url);

// モード判定のキーワード
const MODE_KEYWORDS = {
  create: [
    "作成", "新規", "新しい", "create", "new", "implement", "add skill",
    "スキルを作る", "スキルを作成"
  ],
  update: [
    "更新", "修正", "変更", "改善", "refactor", "update", "modify", "change",
    "アップデート", "リファクタ", "構造を変更", "機能を追加", "機能を変更"
  ],
  "improve-prompt": [
    "プロンプト改善", "プロンプト最適化", "agents/を改善", "Task仕様書を",
    "improve prompt", "optimize prompt", "agents改善", "プロンプトを改善",
    "プロンプトの改善", "プロンプトを最適化"
  ],
  collaborative: [
    "対話", "インタビュー", "会話", "一緒に", "collaborative", "interactive", "chat"
  ],
  orchestrate: [
    "実行エンジン", "codex", "gemini", "エンジン選択", "orchestrate", "assign", "委譲"
  ]
};

function showHelp() {
  console.log(`
モード判定スクリプト

Usage:
  node detect_mode.js --request <text> [options]

Options:
  --request <text>     ユーザー要求文（必須）
  --skill-path <path>  既存スキルのパス（update/improve-prompt時に使用）
  --output <path>      出力先（デフォルト: .tmp/mode.json）
  -h, --help           このヘルプを表示

Modes:
  create          新規スキル作成
  update          既存スキルの更新
  improve-prompt  プロンプト（agents/*.md）の改善

Examples:
  node scripts/detect_mode.js --request "新しいスキルを作成"
  node scripts/detect_mode.js --request "skill-creatorのプロンプトを改善" --skill-path .claude/skills/skill-creator
`);
}

function detectMode(request) {
  const lowerRequest = request.toLowerCase();

  // 各モードのスコアを計算
  const scores = {
    create: 0,
    update: 0,
    "improve-prompt": 0
  };

  for (const [mode, keywords] of Object.entries(MODE_KEYWORDS)) {
    for (const keyword of keywords) {
      if (lowerRequest.includes(keyword.toLowerCase())) {
        scores[mode]++;
      }
    }
  }

  // 最高スコアのモードを選択
  let maxScore = 0;
  let detectedMode = "create"; // デフォルト

  for (const [mode, score] of Object.entries(scores)) {
    if (score > maxScore) {
      maxScore = score;
      detectedMode = mode;
    }
  }

  // スコアが0の場合は不確定
  const confidence = maxScore > 0 ? (maxScore >= 2 ? "high" : "medium") : "low";

  return {
    mode: detectedMode,
    confidence,
    scores,
    matchedKeywords: Object.entries(MODE_KEYWORDS)
      .filter(([mode]) => scores[mode] > 0)
      .reduce((acc, [mode, keywords]) => {
        acc[mode] = keywords.filter((kw) =>
          lowerRequest.includes(kw.toLowerCase())
        );
        return acc;
      }, {})
  };
}

async function main() {
  const args = process.argv.slice(2);

  if (hasArg(args, "-h", "--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const request = getArg(args, "--request");
  const skillPath = getArg(args, "--skill-path");
  const outputPath = getArg(args, "--output") || ".tmp/mode.json";

  if (!request) {
    console.error("Error: --request は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  // モード判定
  const detection = detectMode(request);

  // スキルパスの検証（update/improve-prompt時）
  let skillExists = false;
  let skillName = null;

  if (skillPath) {
    const resolvedPath = resolvePath(skillPath);
    skillExists = existsSync(resolvedPath);
    if (skillExists) {
      skillName = skillPath.split("/").pop();
    }
  }

  // update/improve-promptモードでスキルパスが必要だが存在しない場合
  if (
    (detection.mode === "update" || detection.mode === "improve-prompt") &&
    !skillExists &&
    detection.confidence !== "low"
  ) {
    console.warn(
      `⚠ モード "${detection.mode}" が検出されましたが、スキルパスが指定されていないか存在しません`
    );
    console.warn("  --skill-path オプションで既存スキルのパスを指定してください");
  }

  // 結果JSON
  const result = {
    mode: detection.mode,
    confidence: detection.confidence,
    request,
    skillPath: skillPath || null,
    skillExists,
    skillName,
    detection: {
      scores: detection.scores,
      matchedKeywords: detection.matchedKeywords
    },
    timestamp: new Date().toISOString()
  };

  // 出力ディレクトリ作成
  const resolvedOutputPath = resolvePath(outputPath);
  const outputDir = dirname(resolvedOutputPath);
  if (!existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true });
  }

  // 結果を出力
  writeFileSync(resolvedOutputPath, JSON.stringify(result, null, 2), "utf-8");

  console.log(`✓ モード判定完了: ${detection.mode}`);
  console.log(`  信頼度: ${detection.confidence}`);
  console.log(`  出力: ${outputPath}`);

  if (detection.confidence === "low") {
    console.log(`\n⚠ 信頼度が低いです。ユーザーに確認することを推奨します。`);
  }

  process.exit(EXIT_CODES.SUCCESS);
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
