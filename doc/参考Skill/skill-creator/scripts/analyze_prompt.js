#!/usr/bin/env node

/**
 * プロンプト分析スクリプト
 *
 * agents/*.mdファイルを分析し、改善点を特定します。
 *
 * 使用例:
 *   node scripts/analyze_prompt.js --input agents/analyze-request.md
 *   node scripts/analyze_prompt.js --skill-path .claude/skills/skill-creator
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 */

import { readFileSync, existsSync, readdirSync, writeFileSync, mkdirSync } from "fs";
import { resolve, dirname, join, basename } from "path";
import { fileURLToPath } from "url";
import { EXIT_CODES, getArg } from "./utils.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

// 5セクション構造
const REQUIRED_SECTIONS = [
  "メタ情報",
  "プロフィール",
  "知識ベース",
  "実行仕様",
  "インターフェース"
];

// 曖昧な表現パターン
const AMBIGUOUS_PATTERNS = [
  { pattern: /適切に/g, issue: "「適切に」は曖昧" },
  { pattern: /必要に応じて/g, issue: "「必要に応じて」は判断基準が不明確" },
  { pattern: /など/g, issue: "「など」は具体性に欠ける" },
  { pattern: /その他/g, issue: "「その他」は具体性に欠ける" },
  { pattern: /場合によっては/g, issue: "「場合によっては」は条件が不明確" },
  { pattern: /可能であれば/g, issue: "「可能であれば」は条件が不明確" },
  { pattern: /適宜/g, issue: "「適宜」は判断基準が不明確" },
];

function showHelp() {
  console.log(`
プロンプト分析スクリプト

Usage:
  node analyze_prompt.js --input <file> [options]
  node analyze_prompt.js --skill-path <path> [options]

Options:
  --input <file>       単一のagents/*.mdファイルを分析
  --skill-path <path>  スキルディレクトリ内の全agents/*.mdを分析
  --output <path>      出力先（デフォルト: .tmp/prompt-analysis.json）
  --verbose            詳細な分析結果を表示
  -h, --help           このヘルプを表示

Analysis Criteria:
  - 5セクション構造（メタ/プロフィール/知識/実行/インターフェース）
  - 曖昧な表現の検出
  - 出力テンプレートの有無
  - チェックリストの有無
  - 思考プロセスの具体性
`);
}

function analyzeStructure(content) {
  const foundSections = [];
  const missingSections = [];

  for (const section of REQUIRED_SECTIONS) {
    // セクション番号付きパターンも許容
    const patterns = [
      new RegExp(`^##\\s*\\d*\\.?\\s*${section}`, "m"),
      new RegExp(`^##\\s*${section}`, "m")
    ];
    const found = patterns.some((p) => p.test(content));
    if (found) {
      foundSections.push(section);
    } else {
      missingSections.push(section);
    }
  }

  const score = Math.round((foundSections.length / REQUIRED_SECTIONS.length) * 5);
  return { foundSections, missingSections, score };
}

function analyzeClarity(content) {
  const issues = [];

  for (const { pattern, issue } of AMBIGUOUS_PATTERNS) {
    const matches = content.match(pattern);
    if (matches) {
      issues.push({
        type: "ambiguous",
        issue,
        count: matches.length,
        pattern: pattern.source
      });
    }
  }

  // スコア計算（問題が少ないほど高スコア）
  const score = Math.max(1, 5 - Math.min(4, issues.length));
  return { issues, score };
}

function analyzeReproducibility(content) {
  const issues = [];

  // 思考プロセスセクションの確認
  const hasThinkingProcess = /思考プロセス/i.test(content);
  if (!hasThinkingProcess) {
    issues.push({ type: "missing", issue: "思考プロセスセクションがない" });
  }

  // ステップ番号付きテーブルの確認
  const hasStepTable = /\|\s*ステップ\s*\|/i.test(content) || /\|\s*\d+\s*\|/i.test(content);
  if (!hasStepTable) {
    issues.push({ type: "missing", issue: "ステップ番号付きの思考プロセステーブルがない" });
  }

  // 出力テンプレートの確認
  const hasOutputTemplate = /出力テンプレート/i.test(content) || /```(json|markdown)/i.test(content);
  if (!hasOutputTemplate) {
    issues.push({ type: "missing", issue: "出力テンプレートがない" });
  }

  // チェックリストの確認
  const hasChecklist = /チェックリスト/i.test(content);
  if (!hasChecklist) {
    issues.push({ type: "missing", issue: "チェックリストがない" });
  }

  const score = Math.max(1, 5 - issues.length);
  return { issues, score };
}

function analyzeEfficiency(content) {
  const issues = [];
  const lines = content.split("\n");

  // 行数チェック
  if (lines.length > 200) {
    issues.push({ type: "verbose", issue: `行数が多い (${lines.length}行)`, severity: "warning" });
  }

  // 長い段落の検出
  const paragraphs = content.split(/\n\n+/);
  const longParagraphs = paragraphs.filter((p) => p.length > 500 && !p.startsWith("```"));
  if (longParagraphs.length > 0) {
    issues.push({
      type: "verbose",
      issue: `長い段落が${longParagraphs.length}個ある（表形式への変換を推奨）`,
      severity: "suggestion"
    });
  }

  // 重複の検出（簡易）
  const uniqueLines = new Set(lines.filter((l) => l.trim().length > 20));
  const duplicateRate = 1 - uniqueLines.size / lines.filter((l) => l.trim().length > 20).length;
  if (duplicateRate > 0.1) {
    issues.push({
      type: "duplicate",
      issue: `重複率が高い (${Math.round(duplicateRate * 100)}%)`,
      severity: "warning"
    });
  }

  const score = Math.max(1, 5 - issues.length);
  return { issues, score, metrics: { lineCount: lines.length, uniqueRate: 1 - duplicateRate } };
}

function analyzeFile(filePath) {
  const content = readFileSync(filePath, "utf-8");
  const fileName = basename(filePath);

  const structure = analyzeStructure(content);
  const clarity = analyzeClarity(content);
  const reproducibility = analyzeReproducibility(content);
  const efficiency = analyzeEfficiency(content);

  const overallScore = Math.round(
    (structure.score + clarity.score + reproducibility.score + efficiency.score) / 4
  );

  return {
    file: fileName,
    path: filePath,
    scores: {
      structure: structure.score,
      clarity: clarity.score,
      reproducibility: reproducibility.score,
      efficiency: efficiency.score,
      overall: overallScore
    },
    analysis: {
      structure,
      clarity,
      reproducibility,
      efficiency
    },
    improvements: [
      ...structure.missingSections.map((s) => ({
        type: "structure",
        priority: "high",
        suggestion: `セクション「${s}」を追加`
      })),
      ...clarity.issues.map((i) => ({
        type: "clarity",
        priority: "medium",
        suggestion: `${i.issue} (${i.count}箇所)`
      })),
      ...reproducibility.issues.map((i) => ({
        type: "reproducibility",
        priority: i.type === "missing" ? "high" : "medium",
        suggestion: i.issue
      })),
      ...efficiency.issues.map((i) => ({
        type: "efficiency",
        priority: i.severity === "warning" ? "medium" : "low",
        suggestion: i.issue
      }))
    ]
  };
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const inputFile = getArg(args, "--input");
  const skillPath = getArg(args, "--skill-path");
  const outputPath = getArg(args, "--output") || ".tmp/prompt-analysis.json";
  const verbose = args.includes("--verbose");

  if (!inputFile && !skillPath) {
    console.error("Error: --input または --skill-path のいずれかが必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const filesToAnalyze = [];

  if (inputFile) {
    const resolvedInput = resolve(process.cwd(), inputFile);
    if (!existsSync(resolvedInput)) {
      console.error(`Error: ファイルが存在しません: ${resolvedInput}`);
      process.exit(EXIT_CODES.FILE_NOT_FOUND);
    }
    filesToAnalyze.push(resolvedInput);
  }

  if (skillPath) {
    const agentsDir = join(resolve(process.cwd(), skillPath), "agents");
    if (!existsSync(agentsDir)) {
      console.error(`Error: agents/ディレクトリが存在しません: ${agentsDir}`);
      process.exit(EXIT_CODES.FILE_NOT_FOUND);
    }
    const agentFiles = readdirSync(agentsDir)
      .filter((f) => f.endsWith(".md"))
      .map((f) => join(agentsDir, f));
    filesToAnalyze.push(...agentFiles);
  }

  if (filesToAnalyze.length === 0) {
    console.error("Error: 分析対象のファイルがありません");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  // 分析実行
  const results = filesToAnalyze.map((file) => analyzeFile(file));

  // 集計
  const summary = {
    totalFiles: results.length,
    averageScores: {
      structure: Math.round(results.reduce((sum, r) => sum + r.scores.structure, 0) / results.length * 10) / 10,
      clarity: Math.round(results.reduce((sum, r) => sum + r.scores.clarity, 0) / results.length * 10) / 10,
      reproducibility: Math.round(results.reduce((sum, r) => sum + r.scores.reproducibility, 0) / results.length * 10) / 10,
      efficiency: Math.round(results.reduce((sum, r) => sum + r.scores.efficiency, 0) / results.length * 10) / 10,
      overall: Math.round(results.reduce((sum, r) => sum + r.scores.overall, 0) / results.length * 10) / 10
    },
    totalImprovements: results.reduce((sum, r) => sum + r.improvements.length, 0),
    highPriorityCount: results.reduce(
      (sum, r) => sum + r.improvements.filter((i) => i.priority === "high").length,
      0
    )
  };

  const output = {
    timestamp: new Date().toISOString(),
    summary,
    results
  };

  // 出力ディレクトリ作成
  const outputDir = dirname(resolve(process.cwd(), outputPath));
  if (!existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true });
  }

  // 結果を出力
  writeFileSync(resolve(process.cwd(), outputPath), JSON.stringify(output, null, 2), "utf-8");

  console.log(`✓ プロンプト分析完了`);
  console.log(`  分析ファイル数: ${summary.totalFiles}`);
  console.log(`  平均スコア: ${summary.averageScores.overall}/5`);
  console.log(`  改善提案数: ${summary.totalImprovements} (高優先度: ${summary.highPriorityCount})`);
  console.log(`  出力: ${outputPath}`);

  if (verbose) {
    console.log("\n--- 詳細スコア ---");
    for (const r of results) {
      console.log(`\n${r.file}:`);
      console.log(`  構造: ${r.scores.structure}/5, 明確性: ${r.scores.clarity}/5`);
      console.log(`  再現性: ${r.scores.reproducibility}/5, 効率性: ${r.scores.efficiency}/5`);
      if (r.improvements.length > 0) {
        console.log(`  改善点:`);
        for (const imp of r.improvements.slice(0, 3)) {
          console.log(`    - [${imp.priority}] ${imp.suggestion}`);
        }
        if (r.improvements.length > 3) {
          console.log(`    ... 他 ${r.improvements.length - 3} 件`);
        }
      }
    }
  }

  process.exit(EXIT_CODES.SUCCESS);
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
