#!/usr/bin/env node
/**
 * Markdown → DOCX 変換スクリプト
 *
 * Usage:
 *   node convert-to-docx.js <input.md> [output.docx]
 *
 * Options:
 *   --reference <path>  リファレンスDOCXのパス（デフォルト: ../assets/reference.docx）
 *   --open              変換後にファイルを開く
 *   --pdf               DOCX変換後にPDFも生成（LibreOffice必須）
 *
 * Examples:
 *   node convert-to-docx.js contract.md
 *   node convert-to-docx.js contract.md output.docx --open
 *   node convert-to-docx.js contract.md --pdf
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// 引数解析
const args = process.argv.slice(2);
const options = {
  input: null,
  output: null,
  reference: null,
  open: false,
  pdf: false
};

for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (arg === '--reference' && args[i + 1]) {
    options.reference = args[++i];
  } else if (arg === '--open') {
    options.open = true;
  } else if (arg === '--pdf') {
    options.pdf = true;
  } else if (!arg.startsWith('--')) {
    if (!options.input) {
      options.input = arg;
    } else if (!options.output) {
      options.output = arg;
    }
  }
}

// バリデーション
if (!options.input) {
  console.error('Usage: node convert-to-docx.js <input.md> [output.docx]');
  console.error('');
  console.error('Options:');
  console.error('  --reference <path>  リファレンスDOCXのパス');
  console.error('  --open              変換後にファイルを開く');
  console.error('  --pdf               DOCX変換後にPDFも生成');
  process.exit(1);
}

const input = path.resolve(options.input);
const output = options.output
  ? path.resolve(options.output)
  : input.replace(/\.md$/, '.docx');

if (!fs.existsSync(input)) {
  console.error(`Error: Input file not found: ${input}`);
  process.exit(1);
}

// リファレンスDOCXの検索
const scriptDir = __dirname;
const referenceDocPaths = [
  options.reference,
  path.join(scriptDir, '../assets/reference.docx'),
  path.join(path.dirname(input), 'reference.docx'),
  path.join(path.dirname(input), '../assets/reference.docx')
].filter(Boolean);

const referenceDoc = referenceDocPaths.find(p => fs.existsSync(p));

// pandocコマンド構築
const pandocArgs = [
  'pandoc',
  `"${input}"`,
  '-o', `"${output}"`,
  '--standalone',
  '-V', 'lang=ja'
];

if (referenceDoc) {
  pandocArgs.push(`--reference-doc="${referenceDoc}"`);
  console.log(`Reference: ${path.basename(referenceDoc)}`);
} else {
  console.log('Warning: reference.docx not found, using pandoc defaults');
}

const cmd = pandocArgs.join(' ');

// 変換実行
console.log(`Converting: ${path.basename(input)} → ${path.basename(output)}`);

try {
  execSync(cmd, { stdio: 'inherit' });
  console.log(`✓ DOCX: ${output}`);
} catch (error) {
  console.error('Error: pandoc conversion failed');
  console.error('Make sure pandoc is installed: brew install pandoc');
  process.exit(1);
}

// PDF変換（オプション）
if (options.pdf) {
  const pdfOutput = output.replace(/\.docx$/, '.pdf');
  console.log(`Converting: ${path.basename(output)} → ${path.basename(pdfOutput)}`);

  try {
    // LibreOfficeを試行
    execSync(`libreoffice --headless --convert-to pdf --outdir "${path.dirname(output)}" "${output}"`, {
      stdio: 'pipe'
    });
    console.log(`✓ PDF: ${pdfOutput}`);
  } catch (e) {
    console.log('LibreOffice not available. Please convert DOCX to PDF manually.');
    console.log('Options:');
    console.log('  - Open in Microsoft Word → Export as PDF');
    console.log('  - Open in LibreOffice → Export as PDF');
  }
}

// ファイルを開く（オプション）
if (options.open) {
  const fileToOpen = options.pdf && fs.existsSync(output.replace(/\.docx$/, '.pdf'))
    ? output.replace(/\.docx$/, '.pdf')
    : output;

  try {
    if (process.platform === 'darwin') {
      execSync(`open "${fileToOpen}"`);
    } else if (process.platform === 'win32') {
      execSync(`start "" "${fileToOpen}"`);
    } else {
      execSync(`xdg-open "${fileToOpen}"`);
    }
  } catch (e) {
    console.log(`Could not open file automatically: ${fileToOpen}`);
  }
}
