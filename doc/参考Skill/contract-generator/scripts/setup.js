#!/usr/bin/env node
/**
 * セットアップスクリプト - 依存関係のチェックとインストール案内
 *
 * Usage:
 *   node setup.js          # チェック + インストール案内
 *   node setup.js --check  # チェックのみ
 *   node setup.js --install # 自動インストール（macOS/Homebrew）
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const SKILL_DIR = path.resolve(__dirname, '..');

// 依存関係の定義
const DEPENDENCIES = [
  {
    name: 'Node.js',
    command: 'node --version',
    required: true,
    minVersion: '18.0.0',
    installMac: 'brew install node',
    installLinux: 'sudo apt install nodejs',
    installWin: 'winget install OpenJS.NodeJS',
  },
  {
    name: 'pandoc',
    command: 'pandoc --version',
    required: true,
    minVersion: '2.0',
    installMac: 'brew install pandoc',
    installLinux: 'sudo apt install pandoc',
    installWin: 'winget install JohnMacFarlane.Pandoc',
  },
  {
    name: 'LibreOffice',
    command: 'libreoffice --version',
    required: false,
    minVersion: null,
    installMac: 'brew install --cask libreoffice',
    installLinux: 'sudo apt install libreoffice',
    installWin: 'winget install TheDocumentFoundation.LibreOffice',
    note: 'DOCX→PDF変換に必要（オプション）',
  },
];

// プラットフォーム検出
function getPlatform() {
  switch (process.platform) {
    case 'darwin': return 'mac';
    case 'win32': return 'win';
    default: return 'linux';
  }
}

// コマンド実行チェック
function checkCommand(command) {
  try {
    const output = execSync(command, { stdio: 'pipe', encoding: 'utf-8' });
    return { success: true, output: output.trim() };
  } catch (e) {
    return { success: false, output: null };
  }
}

// バージョン比較
function compareVersions(v1, v2) {
  const parts1 = v1.split('.').map(Number);
  const parts2 = v2.split('.').map(Number);
  for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
    const p1 = parts1[i] || 0;
    const p2 = parts2[i] || 0;
    if (p1 > p2) return 1;
    if (p1 < p2) return -1;
  }
  return 0;
}

// バージョン抽出
function extractVersion(output) {
  const match = output.match(/(\d+\.\d+(\.\d+)?)/);
  return match ? match[1] : null;
}

// メイン処理
function main() {
  const args = process.argv.slice(2);
  const checkOnly = args.includes('--check');
  const autoInstall = args.includes('--install');
  const platform = getPlatform();

  console.log('\n========================================');
  console.log('  Contract Generator - セットアップ');
  console.log('========================================\n');
  console.log(`プラットフォーム: ${process.platform} (${platform})`);
  console.log(`スキルディレクトリ: ${SKILL_DIR}\n`);

  const results = [];
  let hasError = false;

  // 依存関係チェック
  console.log('依存関係チェック:');
  console.log('-'.repeat(50));

  for (const dep of DEPENDENCIES) {
    const check = checkCommand(dep.command);
    const version = check.success ? extractVersion(check.output) : null;
    const versionOk = !dep.minVersion || (version && compareVersions(version, dep.minVersion) >= 0);

    let status;
    let statusIcon;

    if (check.success && versionOk) {
      status = 'OK';
      statusIcon = '✓';
    } else if (check.success && !versionOk) {
      status = `要更新 (${version} < ${dep.minVersion})`;
      statusIcon = '⚠';
      if (dep.required) hasError = true;
    } else {
      status = '未インストール';
      statusIcon = dep.required ? '✗' : '○';
      if (dep.required) hasError = true;
    }

    const requiredLabel = dep.required ? '[必須]' : '[任意]';
    console.log(`  ${statusIcon} ${dep.name} ${requiredLabel}: ${status}${version ? ` (v${version})` : ''}`);
    if (dep.note && !check.success) {
      console.log(`      ${dep.note}`);
    }

    results.push({ ...dep, check, version, versionOk, status });
  }

  console.log('-'.repeat(50));

  // インストール案内
  const needsInstall = results.filter(r => !r.check.success || !r.versionOk);

  if (needsInstall.length > 0 && !checkOnly) {
    console.log('\nインストール方法:');
    console.log('-'.repeat(50));

    for (const dep of needsInstall) {
      const installCmd = dep[`install${platform.charAt(0).toUpperCase() + platform.slice(1)}`];
      console.log(`\n${dep.name}:`);
      console.log(`  $ ${installCmd}`);
    }

    // 自動インストール（macOSのみ）
    if (autoInstall && platform === 'mac') {
      console.log('\n自動インストールを実行します...\n');

      for (const dep of needsInstall) {
        if (dep.required) {
          console.log(`Installing ${dep.name}...`);
          try {
            execSync(dep.installMac, { stdio: 'inherit' });
            console.log(`✓ ${dep.name} installed successfully`);
          } catch (e) {
            console.error(`✗ ${dep.name} installation failed`);
          }
        }
      }
    }
  }

  // ディレクトリ構造チェック
  console.log('\nディレクトリ構造:');
  console.log('-'.repeat(50));

  const requiredDirs = ['scripts', 'assets', 'references', 'schemas', 'knowledge', 'agents'];
  for (const dir of requiredDirs) {
    const dirPath = path.join(SKILL_DIR, dir);
    const exists = fs.existsSync(dirPath);
    console.log(`  ${exists ? '✓' : '✗'} ${dir}/`);
  }

  // リファレンスDOCXチェック
  const refDocx = path.join(SKILL_DIR, 'assets', 'reference.docx');
  const hasRefDocx = fs.existsSync(refDocx);
  console.log(`  ${hasRefDocx ? '✓' : '○'} assets/reference.docx (スタイル定義)`);

  if (!hasRefDocx) {
    console.log('      → 生成: pnpm cli init-reference');
  }

  // サマリー
  console.log('\n========================================');
  if (hasError) {
    console.log('  ✗ セットアップ未完了');
    console.log('    上記の必須依存関係をインストールしてください');
    if (platform === 'mac') {
      console.log('    自動インストール: pnpm setup --install');
    }
    process.exit(1);
  } else {
    console.log('  ✓ セットアップ完了');
    console.log('\n使用方法:');
    console.log('  pnpm cli                       # インタラクティブモード');
    console.log('  pnpm convert <file.md>         # DOCX変換');
    console.log('  pnpm validate <file.md>        # 契約書検証');
    console.log('  pnpm help                      # ヘルプ表示');
  }
  console.log('========================================\n');

  process.exit(hasError ? 1 : 0);
}

main();
