#!/usr/bin/env node

/**
 * スキル依存関係インストールスクリプト
 *
 * スキルディレクトリ内で PNPM を使用して依存関係をインストールします。
 * スキルを自己完結型にするため、node_modules はスキルディレクトリ内に配置されます。
 *
 * 使用例:
 *   node install_deps.js                           # 現在のスキルの依存関係をインストール
 *   node install_deps.js --skill-path /path/to/skill  # 指定スキルの依存関係をインストール
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: PNPM 実行エラー
 */

import { existsSync, readFileSync } from "fs";
import { join } from "path";
import { spawn } from "child_process";
import {
  EXIT_CODES,
  getArg,
  hasArg,
  resolvePath,
  getSkillDir,
} from "./utils.js";

const DEFAULT_SKILL_DIR = getSkillDir(import.meta.url);

function showHelp() {
  console.log(`
スキル依存関係インストールスクリプト

スキルディレクトリ内で PNPM を使用して依存関係をインストールします。
各スキルは自己完結型として、独自の node_modules を持ちます。

Usage:
  node install_deps.js [options]

Options:
  --skill-path <path>  対象スキルのパス（デフォルト: 現在のスキル）
  --prod               本番依存関係のみインストール
  --frozen             lockfile を変更しない（CI向け）
  --verbose            詳細出力
  -h, --help           このヘルプを表示

Examples:
  node install_deps.js
  node install_deps.js --skill-path .claude/skills/my-skill
  node install_deps.js --prod --frozen

Requirements:
  - pnpm がインストールされていること
  - 対象スキルに package.json が存在すること
`);
}

function runPnpm(skillDir, pnpmArgs, verbose) {
  return new Promise((resolve, reject) => {
    if (verbose) {
      console.log(`実行: pnpm ${pnpmArgs.join(" ")}`);
      console.log(`ディレクトリ: ${skillDir}`);
    }

    const proc = spawn("pnpm", pnpmArgs, {
      cwd: skillDir,
      stdio: verbose ? "inherit" : "pipe",
      shell: true,
    });

    let stdout = "";
    let stderr = "";

    if (!verbose) {
      proc.stdout?.on("data", (data) => {
        stdout += data.toString();
      });
      proc.stderr?.on("data", (data) => {
        stderr += data.toString();
      });
    }

    proc.on("close", (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        reject(new Error(`pnpm exited with code ${code}\n${stderr}`));
      }
    });

    proc.on("error", (err) => {
      reject(new Error(`pnpm の実行に失敗しました: ${err.message}`));
    });
  });
}

async function checkPnpmInstalled() {
  return new Promise((resolve) => {
    const proc = spawn("pnpm", ["--version"], {
      stdio: "pipe",
      shell: true,
    });

    proc.on("close", (code) => {
      resolve(code === 0);
    });

    proc.on("error", () => {
      resolve(false);
    });
  });
}

async function main() {
  const args = process.argv.slice(2);

  if (hasArg(args, "-h", "--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const skillPath = getArg(args, "--skill-path");
  const prod = args.includes("--prod");
  const frozen = args.includes("--frozen");
  const verbose = args.includes("--verbose");

  // スキルディレクトリの解決
  const skillDir = skillPath ? resolvePath(skillPath) : DEFAULT_SKILL_DIR;

  // package.json の存在確認
  const packageJsonPath = join(skillDir, "package.json");
  if (!existsSync(packageJsonPath)) {
    console.error(`Error: package.json が存在しません: ${packageJsonPath}`);
    console.error("ヒント: 先に package.json を作成するか、init_skill.js を使用してください");
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  // PNPM のインストール確認
  const hasPnpm = await checkPnpmInstalled();
  if (!hasPnpm) {
    console.error("Error: pnpm がインストールされていません");
    console.error("インストール方法: npm install -g pnpm");
    process.exit(EXIT_CODES.ERROR);
  }

  // package.json の読み込み
  const packageJson = JSON.parse(readFileSync(packageJsonPath, "utf-8"));
  const deps = Object.keys(packageJson.dependencies || {});
  const devDeps = Object.keys(packageJson.devDependencies || {});

  if (deps.length === 0 && devDeps.length === 0) {
    console.log("ℹ 依存関係がありません（dependencies/devDependencies が空）");
    process.exit(EXIT_CODES.SUCCESS);
  }

  console.log(`📦 スキル依存関係をインストールします: ${packageJson.name || skillDir}`);
  if (verbose) {
    console.log(`  dependencies: ${deps.length}個`);
    console.log(`  devDependencies: ${devDeps.length}個`);
  }

  // pnpm install の引数構築
  const pnpmArgs = ["install"];
  if (prod) {
    pnpmArgs.push("--prod");
  }
  if (frozen) {
    pnpmArgs.push("--frozen-lockfile");
  }

  try {
    await runPnpm(skillDir, pnpmArgs, verbose);
    console.log(`✓ 依存関係のインストールが完了しました`);
    console.log(`  場所: ${join(skillDir, "node_modules")}`);
    process.exit(EXIT_CODES.SUCCESS);
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(EXIT_CODES.PNPM_ERROR);
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
