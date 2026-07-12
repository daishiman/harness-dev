#!/usr/bin/env node
/**
 * Contract Generator CLI - 統合コマンドラインツール
 *
 * Usage:
 *   contract-cli <command> [options] [file]
 *
 * Commands:
 *   convert <file.md>     Markdown → DOCX 変換
 *   pdf <file.md>         Markdown → PDF 変換（DOCX経由）
 *   validate <file.md>    契約書の条項検証
 *   layout <file.md>      レイアウト崩れ検証
 *   tax <file.json>       印紙税・源泉徴収・インボイス判定
 *   init-reference        リファレンスDOCXを生成
 *   setup                 依存関係チェック
 *   help                  ヘルプ表示
 *
 * Examples:
 *   pnpm cli convert contract.md
 *   pnpm cli pdf contract.md --open
 *   pnpm cli validate contract.md
 */

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const SKILL_DIR = path.resolve(__dirname, '..');
const SCRIPTS_DIR = __dirname;
const ASSETS_DIR = path.join(SKILL_DIR, 'assets');

// カラー出力
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function logSuccess(message) { log(`✓ ${message}`, 'green'); }
function logError(message) { log(`✗ ${message}`, 'red'); }
function logWarn(message) { log(`⚠ ${message}`, 'yellow'); }
function logInfo(message) { log(`ℹ ${message}`, 'cyan'); }

// ヘルプ表示
function showHelp() {
  console.log(`
${colors.bright}Contract Generator CLI v3.4.0${colors.reset}
取引基本契約書の変換・検証ツール

${colors.cyan}Usage:${colors.reset}
  node contract-cli.js <command> [options] [file]

${colors.cyan}Commands:${colors.reset}
  ${colors.green}convert${colors.reset} <file.md>     Markdown → DOCX 変換
  ${colors.green}pdf${colors.reset} <file.md>         Markdown → PDF 変換（DOCX経由）
  ${colors.green}validate${colors.reset} <file.md>    契約書の条項検証（27条+別紙）
  ${colors.green}layout${colors.reset} <file.md>      レイアウト崩れ検証
  ${colors.green}tax${colors.reset} <file.json>       印紙税・源泉徴収・インボイス判定
  ${colors.green}init-reference${colors.reset}        リファレンスDOCXを生成
  ${colors.green}setup${colors.reset}                 依存関係チェック
  ${colors.green}help${colors.reset}                  このヘルプを表示

${colors.cyan}Options:${colors.reset}
  --open                変換後にファイルを開く
  --strict              警告もエラーとして扱う
  --output <path>       出力ファイルパス指定

${colors.cyan}Examples:${colors.reset}
  # DOCX変換
  node contract-cli.js convert 取引基本契約書.md

  # PDF変換（変換後に開く）
  node contract-cli.js pdf 取引基本契約書.md --open

  # 契約書検証
  node contract-cli.js validate 取引基本契約書.md

  # レイアウト検証（厳格モード）
  node contract-cli.js layout 取引基本契約書.md --strict

${colors.cyan}pnpm scripts:${colors.reset}
  pnpm setup            依存関係チェック
  pnpm convert          DOCX変換
  pnpm validate         契約書検証
  pnpm help             ヘルプ表示
`);
}

// pandocチェック
function checkPandoc() {
  try {
    execSync('pandoc --version', { stdio: 'pipe' });
    return true;
  } catch (e) {
    return false;
  }
}

// LibreOfficeチェック
function checkLibreOffice() {
  try {
    execSync('libreoffice --version', { stdio: 'pipe' });
    return true;
  } catch (e) {
    return false;
  }
}

// コマンド: convert (Markdown → DOCX)
async function cmdConvert(inputFile, options) {
  if (!inputFile) {
    logError('入力ファイルを指定してください');
    console.log('Usage: contract-cli convert <file.md>');
    process.exit(1);
  }

  if (!checkPandoc()) {
    logError('pandocがインストールされていません');
    console.log('インストール: brew install pandoc');
    process.exit(1);
  }

  const input = path.resolve(inputFile);
  if (!fs.existsSync(input)) {
    logError(`ファイルが見つかりません: ${input}`);
    process.exit(1);
  }

  const output = options.output || input.replace(/\.md$/, '.docx');
  const refDocx = path.join(ASSETS_DIR, 'reference.docx');

  logInfo(`変換中: ${path.basename(input)} → ${path.basename(output)}`);

  const args = ['node', path.join(SCRIPTS_DIR, 'convert-to-docx.js'), input, output];
  if (options.open) args.push('--open');

  try {
    execSync(args.join(' '), { stdio: 'inherit' });
  } catch (e) {
    logError('変換に失敗しました');
    process.exit(1);
  }
}

// コマンド: pdf (Markdown → PDF)
async function cmdPdf(inputFile, options) {
  if (!inputFile) {
    logError('入力ファイルを指定してください');
    console.log('Usage: contract-cli pdf <file.md>');
    process.exit(1);
  }

  if (!checkPandoc()) {
    logError('pandocがインストールされていません');
    console.log('インストール: brew install pandoc');
    process.exit(1);
  }

  const input = path.resolve(inputFile);
  if (!fs.existsSync(input)) {
    logError(`ファイルが見つかりません: ${input}`);
    process.exit(1);
  }

  const docxOutput = options.output || input.replace(/\.md$/, '.docx');
  const pdfOutput = docxOutput.replace(/\.docx$/, '.pdf');

  // Step 1: Markdown → DOCX
  logInfo(`Step 1: ${path.basename(input)} → ${path.basename(docxOutput)}`);
  const convertArgs = ['node', path.join(SCRIPTS_DIR, 'convert-to-docx.js'), input, docxOutput];
  try {
    execSync(convertArgs.join(' '), { stdio: 'inherit' });
  } catch (e) {
    logError('DOCX変換に失敗しました');
    process.exit(1);
  }

  // Step 2: DOCX → PDF
  logInfo(`Step 2: ${path.basename(docxOutput)} → ${path.basename(pdfOutput)}`);

  if (checkLibreOffice()) {
    try {
      execSync(`libreoffice --headless --convert-to pdf --outdir "${path.dirname(docxOutput)}" "${docxOutput}"`, {
        stdio: 'pipe'
      });
      logSuccess(`PDF: ${pdfOutput}`);

      if (options.open) {
        if (process.platform === 'darwin') {
          execSync(`open "${pdfOutput}"`);
        } else if (process.platform === 'win32') {
          execSync(`start "" "${pdfOutput}"`);
        } else {
          execSync(`xdg-open "${pdfOutput}"`);
        }
      }
    } catch (e) {
      logWarn('PDF変換に失敗しました');
    }
  } else {
    logWarn('LibreOfficeがインストールされていません');
    console.log('手動でPDF変換してください:');
    console.log(`  1. ${docxOutput} をWordで開く`);
    console.log('  2. ファイル > 名前を付けて保存 > PDF');
    console.log('');
    console.log('LibreOfficeインストール: brew install --cask libreoffice');

    if (options.open) {
      if (process.platform === 'darwin') {
        execSync(`open "${docxOutput}"`);
      }
    }
  }
}

// コマンド: validate (契約書検証)
async function cmdValidate(inputFile, options) {
  if (!inputFile) {
    logError('入力ファイルを指定してください');
    console.log('Usage: contract-cli validate <file.md>');
    process.exit(1);
  }

  const input = path.resolve(inputFile);
  if (!fs.existsSync(input)) {
    logError(`ファイルが見つかりません: ${input}`);
    process.exit(1);
  }

  logInfo(`契約書検証: ${path.basename(input)}`);

  const args = ['node', path.join(SCRIPTS_DIR, 'validate-contract.js'), input];
  try {
    execSync(args.join(' '), { stdio: 'inherit' });
  } catch (e) {
    process.exit(1);
  }
}

// コマンド: layout (レイアウト検証)
async function cmdLayout(inputFile, options) {
  if (!inputFile) {
    logError('入力ファイルを指定してください');
    console.log('Usage: contract-cli layout <file.md>');
    process.exit(1);
  }

  const input = path.resolve(inputFile);
  if (!fs.existsSync(input)) {
    logError(`ファイルが見つかりません: ${input}`);
    process.exit(1);
  }

  logInfo(`レイアウト検証: ${path.basename(input)}`);

  const args = ['node', path.join(SCRIPTS_DIR, 'validate-layout.js'), input];
  if (options.strict) args.push('--strict');

  try {
    execSync(args.join(' '), { stdio: 'inherit' });
  } catch (e) {
    process.exit(1);
  }
}

// コマンド: tax (税務判定)
async function cmdTax(inputFile, options) {
  if (!inputFile) {
    logError('入力ファイル（JSON）を指定してください');
    console.log('Usage: contract-cli tax <file.json>');
    process.exit(1);
  }

  const input = path.resolve(inputFile);
  if (!fs.existsSync(input)) {
    logError(`ファイルが見つかりません: ${input}`);
    process.exit(1);
  }

  logInfo(`税務判定: ${path.basename(input)}`);

  const args = ['node', path.join(SCRIPTS_DIR, 'determine-tax.js'), input];
  try {
    execSync(args.join(' '), { stdio: 'inherit' });
  } catch (e) {
    process.exit(1);
  }
}

// コマンド: init-reference (リファレンスDOCX生成)
async function cmdInitReference() {
  if (!checkPandoc()) {
    logError('pandocがインストールされていません');
    console.log('インストール: brew install pandoc');
    process.exit(1);
  }

  const refDocx = path.join(ASSETS_DIR, 'reference.docx');

  if (fs.existsSync(refDocx)) {
    logWarn(`既存のファイルがあります: ${refDocx}`);

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    const answer = await new Promise(resolve => {
      rl.question('上書きしますか？ (y/N): ', resolve);
    });
    rl.close();

    if (answer.toLowerCase() !== 'y') {
      logInfo('キャンセルしました');
      return;
    }
  }

  logInfo('リファレンスDOCXを生成中...');

  // スタイル定義用の最小Markdown
  const styleContent = `# 取引基本契約書

## 第1条（目的）

本契約は、甲乙間の取引に関する基本的な事項を定めることを目的とする。

## 第2条（業務内容）

1. 乙が甲に対して提供する業務の内容は、次のとおりとする。
   - (1) **AIコンサルティング業務**
   - (2) **AI研修業務**

---

**甲（発注者）**

住所

名称

代表取締役　　　　　　　　　　　　　　　　　　㊞
`;

  const tempMd = path.join(ASSETS_DIR, '_temp_reference.md');
  fs.writeFileSync(tempMd, styleContent, 'utf-8');

  try {
    execSync(`pandoc "${tempMd}" -o "${refDocx}" --standalone -V lang=ja`, { stdio: 'pipe' });
    fs.unlinkSync(tempMd);
    logSuccess(`リファレンスDOCX生成完了: ${refDocx}`);
    console.log('');
    console.log('このファイルをWordで開いてスタイルを調整してください:');
    console.log('  1. フォント: 游明朝 or MS明朝');
    console.log('  2. 見出し1: 14pt 太字');
    console.log('  3. 見出し2: 12pt 太字');
    console.log('  4. 本文: 10.5pt');
    console.log('  5. 余白: 上下左右25mm');
    console.log('');
    console.log('調整後は上書き保存してください。');
  } catch (e) {
    if (fs.existsSync(tempMd)) fs.unlinkSync(tempMd);
    logError('リファレンスDOCX生成に失敗しました');
    process.exit(1);
  }
}

// コマンド: setup
async function cmdSetup() {
  const args = ['node', path.join(SCRIPTS_DIR, 'setup.js')];
  try {
    execSync(args.join(' '), { stdio: 'inherit' });
  } catch (e) {
    process.exit(1);
  }
}

// メイン処理
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === 'help' || args[0] === '--help' || args[0] === '-h') {
    showHelp();
    process.exit(0);
  }

  const command = args[0];
  const options = {
    open: args.includes('--open'),
    strict: args.includes('--strict'),
    output: null,
  };

  // --output オプション
  const outputIdx = args.indexOf('--output');
  if (outputIdx !== -1 && args[outputIdx + 1]) {
    options.output = args[outputIdx + 1];
  }

  // ファイル引数（オプション以外の最初の引数）
  const fileArg = args.slice(1).find(a => !a.startsWith('--') && a !== options.output);

  switch (command) {
    case 'convert':
      await cmdConvert(fileArg, options);
      break;
    case 'pdf':
      await cmdPdf(fileArg, options);
      break;
    case 'validate':
      await cmdValidate(fileArg, options);
      break;
    case 'layout':
      await cmdLayout(fileArg, options);
      break;
    case 'tax':
      await cmdTax(fileArg, options);
      break;
    case 'init-reference':
      await cmdInitReference();
      break;
    case 'setup':
      await cmdSetup();
      break;
    default:
      logError(`不明なコマンド: ${command}`);
      console.log('ヘルプを表示: contract-cli help');
      process.exit(1);
  }
}

main().catch(e => {
  logError(e.message);
  process.exit(1);
});
