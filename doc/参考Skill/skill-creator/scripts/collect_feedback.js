#!/usr/bin/env node
/**
 * フィードバック収集スクリプト
 *
 * スキルのLOGS fragmentsとEVALS.jsonからフィードバックデータを収集・集計する。
 * 決定論的な処理（LLM不要）。
 *
 * 使用方法:
 *   node scripts/collect_feedback.js --skill-path <path> --output <path>
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般エラー
 *   2: 引数エラー
 *   3: ファイル不在
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from "fs";
import { dirname, join } from "path";
import { EXIT_CODES, getArg, resolvePath } from "./utils.js";

function showHelp() {
  console.log(`
フィードバック収集スクリプト

Usage:
  node collect_feedback.js --skill-path <path> [--output <path>]

Options:
  --skill-path <path>  スキルディレクトリパス（必須）
  --output <path>      結果出力先（指定なしで標準出力）
  --verbose            詳細出力
  -h, --help           ヘルプ表示
`);
}


// LOGS fragment bodyをパース
function parseLogs(logsContent) {
  const entries = [];
  const logPattern = /## \[([^\]]+)\]\s*([\s\S]*?)(?=## \[|$)/g;

  let match;
  while ((match = logPattern.exec(logsContent)) !== null) {
    const timestamp = match[1];
    const content = match[2];

    const entry = {
      timestamp,
      result: null,
      phase: null,
      agent: null,
      duration: null,
      notes: null,
    };

    // 各フィールドを抽出
    const resultMatch = content.match(/\*\*Result\*\*:\s*([^\n]+)/);
    if (resultMatch) {
      entry.result = resultMatch[1].includes("✓") ? "success" : "failure";
    }

    const phaseMatch = content.match(/\*\*Phase\*\*:\s*([^\n]+)/);
    if (phaseMatch) {
      entry.phase = phaseMatch[1].trim();
    }

    const agentMatch = content.match(/\*\*Agent\*\*:\s*([^\n]+)/);
    if (agentMatch) {
      entry.agent = agentMatch[1].trim();
    }

    const durationMatch = content.match(/\*\*Duration\*\*:\s*(\d+)/);
    if (durationMatch) {
      entry.duration = parseInt(durationMatch[1], 10);
    }

    const notesMatch = content.match(/\*\*Notes\*\*:\s*([^\n]+)/);
    if (notesMatch) {
      entry.notes = notesMatch[1].trim();
    }

    entries.push(entry);
  }

  return entries;
}

function readLogFragments(skillPath) {
  const logsDir = join(skillPath, "LOGS");
  const chunks = [];
  if (!existsSync(logsDir)) return "";
  for (const name of readdirSync(logsDir).sort()) {
    if (name === ".gitkeep") continue;
    if (!name.endsWith(".md")) continue;
    const content = readFileSync(join(logsDir, name), "utf-8");
    const body = content.replace(/^---\n[\s\S]*?\n---\n?/, "");
    chunks.push(body);
  }
  return chunks.join("\n");
}

// メトリクスを計算
function calculateMetrics(entries) {
  const total = entries.length;
  const successes = entries.filter((e) => e.result === "success").length;
  const failures = total - successes;
  const successRate = total > 0 ? successes / total : 0;

  const durations = entries.filter((e) => e.duration).map((e) => e.duration);
  const avgDuration =
    durations.length > 0
      ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length)
      : 0;

  return {
    totalUsageCount: total,
    successCount: successes,
    failureCount: failures,
    successRate: Math.round(successRate * 100) / 100,
    averageDuration: avgDuration,
    lastExecuted: entries.length > 0 ? entries[0].timestamp : null,
  };
}

// エラーパターンを分析
function analyzeErrorPatterns(entries) {
  const failedEntries = entries.filter((e) => e.result === "failure");
  const patterns = {};

  for (const entry of failedEntries) {
    const key = entry.notes || "Unknown Error";
    if (!patterns[key]) {
      patterns[key] = {
        type: extractErrorType(key),
        count: 0,
        phases: new Set(),
        lastOccurred: null,
      };
    }
    patterns[key].count++;
    if (entry.phase) {
      patterns[key].phases.add(entry.phase);
    }
    if (
      !patterns[key].lastOccurred ||
      entry.timestamp > patterns[key].lastOccurred
    ) {
      patterns[key].lastOccurred = entry.timestamp;
    }
  }

  return Object.entries(patterns).map(([message, data]) => ({
    message,
    type: data.type,
    count: data.count,
    phases: Array.from(data.phases),
    lastOccurred: data.lastOccurred,
  }));
}

function extractErrorType(message) {
  if (message.includes("Validation")) return "ValidationError";
  if (message.includes("Schema")) return "SchemaError";
  if (message.includes("File") || message.includes("not found"))
    return "FileNotFoundError";
  if (message.includes("Timeout")) return "TimeoutError";
  return "GeneralError";
}

// 遅いフェーズを特定
function analyzeSlowPhases(entries) {
  const phaseStats = {};

  for (const entry of entries) {
    if (!entry.phase || !entry.duration) continue;

    if (!phaseStats[entry.phase]) {
      phaseStats[entry.phase] = {
        durations: [],
        count: 0,
      };
    }
    phaseStats[entry.phase].durations.push(entry.duration);
    phaseStats[entry.phase].count++;
  }

  // 全体平均を計算
  const allDurations = entries.filter((e) => e.duration).map((e) => e.duration);
  const overallAvg =
    allDurations.length > 0
      ? allDurations.reduce((a, b) => a + b, 0) / allDurations.length
      : 0;

  const slowPhases = [];
  for (const [phase, stats] of Object.entries(phaseStats)) {
    const avgDuration =
      stats.durations.reduce((a, b) => a + b, 0) / stats.durations.length;
    if (avgDuration > overallAvg * 1.5) {
      // 平均の1.5倍以上
      slowPhases.push({
        phase,
        avgDuration: Math.round(avgDuration),
        threshold: Math.round(overallAvg * 1.5),
        count: stats.count,
      });
    }
  }

  return slowPhases.sort((a, b) => b.avgDuration - a.avgDuration);
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const skillPath = getArg(args, "--skill-path");
  const outputPath = getArg(args, "--output");
  const verbose = args.includes("--verbose");

  if (!skillPath) {
    console.error("Error: --skill-path は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedSkillPath = resolvePath(skillPath);

  if (!existsSync(resolvedSkillPath)) {
    console.error(
      `Error: スキルディレクトリが存在しません: ${resolvedSkillPath}`
    );
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  const evalsPath = join(resolvedSkillPath, "EVALS.json");

  try {
    // LOGS fragmentsを読み込み
    let entries = [];
    const logsContent = readLogFragments(resolvedSkillPath);
    if (logsContent.length > 0) {
      entries = parseLogs(logsContent);
      if (verbose) {
        console.log(`LOGS fragments: ${entries.length}エントリを解析`);
      }
    } else {
      if (verbose) {
        console.log("LOGS fragment が存在しません（新規スキル）");
      }
    }

    // EVALS.jsonを読み込み（あれば）
    let existingEvals = {};
    if (existsSync(evalsPath)) {
      existingEvals = JSON.parse(readFileSync(evalsPath, "utf-8"));
    }

    // メトリクス計算
    const metrics = calculateMetrics(entries);

    // エラーパターン分析
    const errorPatterns = analyzeErrorPatterns(entries);

    // 遅いフェーズ分析
    const slowPhases = analyzeSlowPhases(entries);

    // 結果を構築
    const result = {
      skillName: existingEvals.skillName || skillPath.split("/").pop(),
      collectedAt: new Date().toISOString(),
      metrics,
      errorPatterns,
      slowPhases,
      recentLogs: entries.slice(0, 10), // 最新10件
      currentLevel: existingEvals.currentLevel || 1,
    };

    if (verbose) {
      console.log(`\n収集結果:`);
      console.log(`  使用回数: ${metrics.totalUsageCount}`);
      console.log(`  成功率: ${(metrics.successRate * 100).toFixed(1)}%`);
      console.log(`  エラーパターン: ${errorPatterns.length}種類`);
      console.log(`  遅いフェーズ: ${slowPhases.length}件`);
    }

    const output = JSON.stringify(result, null, 2);

    if (outputPath) {
      const resolvedOutput = resolvePath(outputPath);
      const outputDir = dirname(resolvedOutput);
      if (!existsSync(outputDir)) {
        mkdirSync(outputDir, { recursive: true });
      }
      writeFileSync(resolvedOutput, output, "utf-8");
      console.log(`✓ フィードバック収集完了: ${outputPath}`);
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
