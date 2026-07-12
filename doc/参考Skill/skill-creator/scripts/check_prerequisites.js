#!/usr/bin/env node
/**
 * 事前条件チェックスクリプト
 *
 * Codex実行に必要な事前条件をチェックします。
 *
 * 使用方法:
 *   node check_prerequisites.js [--verbose]
 *
 * 終了コード:
 *   0: 全ての条件を満たす
 *   1: 条件を満たさない
 */

import { execSync } from "node:child_process";
import { parseArgs } from "node:util";
import { EXIT_CODES } from "./utils.js";

const { values } = parseArgs({
  options: {
    verbose: { type: "boolean", short: "v" },
    help: { type: "boolean", short: "h" },
  },
  strict: true,
});

if (values.help) {
  console.log(`
事前条件チェックスクリプト

Usage:
  node check_prerequisites.js [options]

Options:
  --verbose, -v   詳細な出力
  --help, -h      ヘルプを表示

Checks:
  1. gitリポジトリであること
  2. Codex CLIがインストールされていること
`);
  process.exit(EXIT_CODES.SUCCESS);
}

const verbose = values.verbose || false;

function log(message) {
  if (verbose) {
    console.error(message);
  }
}

function checkGitRepo() {
  try {
    const result = execSync("git rev-parse --is-inside-work-tree", {
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "pipe"],
    }).trim();
    return result === "true";
  } catch {
    return false;
  }
}

function checkCodexCli() {
  try {
    execSync("which codex", {
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "pipe"],
    });
    return true;
  } catch {
    return false;
  }
}

function getCodexVersion() {
  try {
    return execSync("codex --version", {
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "pipe"],
    }).trim();
  } catch {
    return null;
  }
}

function main() {
  const results = {
    gitRepo: { passed: false, message: "" },
    codexCli: { passed: false, message: "" },
  };

  // Git リポジトリチェック
  log("[Check] gitリポジトリ...");
  if (checkGitRepo()) {
    results.gitRepo.passed = true;
    results.gitRepo.message = "gitリポジトリ内です";
    log("  ✅ OK");
  } else {
    results.gitRepo.message = "gitリポジトリではありません。`git init` を実行してください。";
    log("  ❌ FAILED");
  }

  // Codex CLI チェック
  log("[Check] Codex CLI...");
  if (checkCodexCli()) {
    results.codexCli.passed = true;
    const version = getCodexVersion();
    results.codexCli.message = version
      ? `Codex CLI (${version}) がインストールされています`
      : "Codex CLI がインストールされています";
    log(`  ✅ OK ${version ? `(${version})` : ""}`);
  } else {
    results.codexCli.message = "Codex CLI がインストールされていません。";
    log("  ❌ FAILED");
  }

  // 結果出力
  const allPassed = Object.values(results).every((r) => r.passed);

  const output = {
    passed: allPassed,
    checks: results,
    timestamp: new Date().toISOString(),
  };

  console.log(JSON.stringify(output, null, 2));

  if (!allPassed) {
    console.error("\n事前条件を満たしていません:");
    Object.entries(results).forEach(([key, value]) => {
      if (!value.passed) {
        console.error(`  - ${value.message}`);
      }
    });
    process.exit(EXIT_CODES.ERROR);
  }

  process.exit(EXIT_CODES.SUCCESS);
}

main();
