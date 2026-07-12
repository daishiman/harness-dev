#!/usr/bin/env node

/**
 * スキル依存関係追加スクリプト
 *
 * スキルディレクトリ内で PNPM を使用して依存関係を追加します。
 * 追加された依存関係はスキルの package.json に記録され、
 * node_modules はスキルディレクトリ内に配置されます。
 *
 * 使用例:
 *   node add_dependency.js axios                    # 本番依存関係として追加
 *   node add_dependency.js typescript --dev        # 開発依存関係として追加
 *   node add_dependency.js lodash@4.17.21          # バージョン指定で追加
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
スキル依存関係追加スクリプト

スキルディレクトリ内で PNPM を使用して依存関係を追加します。
各スキルは自己完結型として、独自の node_modules を持ちます。

Usage:
  node add_dependency.js <package[@version]> [options]

Arguments:
  <package[@version]>  追加するパッケージ名（バージョン指定可）

Options:
  --dev, -D            開発依存関係として追加
  --skill-path <path>  対象スキルのパス（デフォルト: 現在のスキル）
  --verbose            詳細出力
  -h, --help           このヘルプを表示

Examples:
  node add_dependency.js axios
  node add_dependency.js typescript --dev
  node add_dependency.js lodash@4.17.21
  node add_dependency.js zod ajv --skill-path .claude/skills/my-skill

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

  const isDev = hasArg(args, "--dev", "-D");
  const verbose = args.includes("--verbose");
  const skillPath = getArg(args, "--skill-path");

  // パッケージ名の抽出（オプションでない引数）
  const packages = args.filter(
    (arg) =>
      !arg.startsWith("-") &&
      arg !== skillPath
  );

  if (packages.length === 0) {
    console.error("Error: パッケージ名を指定してください");
    showHelp();
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

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
  const hasPnpmInstalled = await checkPnpmInstalled();
  if (!hasPnpmInstalled) {
    console.error("Error: pnpm がインストールされていません");
    console.error("インストール方法: npm install -g pnpm");
    process.exit(EXIT_CODES.ERROR);
  }

  // package.json の読み込み
  const packageJson = JSON.parse(readFileSync(packageJsonPath, "utf-8"));

  console.log(`📦 依存関係を追加します: ${packages.join(", ")}`);
  console.log(`  スキル: ${packageJson.name || skillDir}`);
  console.log(`  タイプ: ${isDev ? "devDependencies" : "dependencies"}`);

  // pnpm add の引数構築
  const pnpmArgs = ["add", ...packages];
  if (isDev) {
    pnpmArgs.push("-D");
  }

  try {
    await runPnpm(skillDir, pnpmArgs, verbose);

    // 追加されたパッケージの確認
    const updatedPackageJson = JSON.parse(readFileSync(packageJsonPath, "utf-8"));
    const depKey = isDev ? "devDependencies" : "dependencies";
    const deps = updatedPackageJson[depKey] || {};

    console.log(`✓ 依存関係を追加しました`);
    for (const pkg of packages) {
      const pkgName = pkg.split("@")[0];
      if (deps[pkgName]) {
        console.log(`  ${pkgName}: ${deps[pkgName]}`);
      }
    }

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
