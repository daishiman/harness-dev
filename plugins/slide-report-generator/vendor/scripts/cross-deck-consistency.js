#!/usr/bin/env node
/**
 * cross-deck-consistency.js
 *
 * 複数スライドデッキ（研修シリーズ等）の横断整合性を自動チェック。
 * structure.md の shared-spec セクション、CSS変数、GSAP設定、
 * 印刷CSS、外部URL混入を機械的に検証する。
 *
 * Usage:
 *   node cross-deck-consistency.js <series-dir> [--check <category>] [--json]
 *
 * Options:
 *   --check inputs       必須入力ファイルの欠落検出
 *   --check shared-spec  共通仕様セクションの差分検出
 *   --check css-vars     CSS変数の統一性
 *   --check gsap         GSAPアニメーション設定の一貫性
 *   --check print        印刷CSSの統一性
 *   --check urls         不要な外部URL検出
 *   --check all          全カテゴリ（デフォルト）
 *   --json              結果をJSON形式で出力
 *
 * Exit codes:
 *   0 - 問題なし（PASS）
 *   1 - 警告あり（WARN）
 *   2 - エラーあり（FAIL）
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// --- Argument parsing ---
const args = process.argv.slice(2);
const seriesDir = args.find(a => !a.startsWith('--'));
const checkCategory = args.includes('--check')
  ? args[args.indexOf('--check') + 1] || 'all'
  : 'all';
const jsonOutput = args.includes('--json');

if (!seriesDir) {
  console.error('Usage: node cross-deck-consistency.js <series-dir> [--check <category>] [--json]');
  process.exit(1);
}

const resolvedDir = path.resolve(seriesDir);

// --- Find slide directories ---
function findSlideDecks(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  return entries
    .filter(e => e.isDirectory() && e.name.startsWith('slide-'))
    .map(e => ({
      name: e.name,
      path: path.join(dir, e.name),
      structureMd: path.join(dir, e.name, 'structure.md'),
      stylesCss: path.join(dir, e.name, 'styles.css'),
      scriptsJs: path.join(dir, e.name, 'scripts.js'),
      indexHtml: path.join(dir, e.name, 'index.html'),
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

// --- Check: required inputs ---
function checkRequiredInputs(decks) {
  const required = [
    ['structure.md', 'structureMd'],
    ['index.html', 'indexHtml'],
    ['styles.css', 'stylesCss'],
    ['scripts.js', 'scriptsJs'],
  ];
  const issues = [];
  for (const deck of decks) {
    for (const [file, key] of required) {
      if (!fs.existsSync(deck[key])) {
        issues.push({
          severity: 'error',
          category: 'inputs',
          message: `必須入力 ${file} が存在しない`,
          deck: deck.name,
          file,
        });
      }
    }
  }
  return issues;
}

// --- Extract shared-spec sections from structure.md ---
// 「全4回共通」と明記されたセクション、およびA4/コードブロック/GSAP/フォントの
// 共通ルール部分のみを抽出。回固有のスライドタイプ定義やSVG図解仕様は除外。
function extractSharedSpecs(content) {
  const sections = {};

  // A4印刷品質仕様（全回共通の基盤ルール）
  const a4Match = content.match(/### A4横配置・印刷品質保証仕様[\s\S]*?(?=\n### |\n---|\n## |$)/);
  sections['a4-print'] = a4Match ? a4Match[0].trim() : null;

  // コードブロック共通仕様のうち、アクセントカラー統一ルールより前の部分のみ
  const codeMatch = content.match(/### コードブロック共通仕様[\s\S]*?(?=####\s*アクセントカラー|\n### |\n---|\n## |$)/);
  sections['code-block'] = codeMatch ? codeMatch[0].trim() : null;

  // アクセントカラー統一ルール
  const accentMatch = content.match(/####\s*アクセントカラー統一ルール[\s\S]*?(?=\n### |\n---|\n## |$)/);
  sections['accent-color'] = accentMatch ? accentMatch[0].trim() : null;

  // GSAPアニメーション共通設定
  const gsapMatch = content.match(/### GSAPアニメーション共通設定[\s\S]*?(?=\n### |\n---|\n## |$)/);
  sections['gsap'] = gsapMatch ? gsapMatch[0].trim() : null;

  // フォント仕様
  const fontMatch = content.match(/### フォント仕様[\s\S]*?(?=\n### |\n---|\n## |$)/);
  sections['font'] = fontMatch ? fontMatch[0].trim() : null;

  // 共通SVG設計仕様のうち、回固有の図解定義を除いた基本ルール部分
  // viewBox基本設計〜テキスト文字数制限までを共通部分とする
  const svgMatch = content.match(/### 共通SVG設計仕様[\s\S]*?(?=####\s*(比較|サイクル|営業日報|フロー|変換|テスト|ハイライト|縦積み)|\n### |\n---|\n## )/);
  sections['svg-design-base'] = svgMatch ? svgMatch[0].trim() : null;

  return sections;
}

// 注意: スライドタイプ定義は各回で固有のタイプを持つため、
// 共通部分（基本9種: title/section/content/diagram/compare/quote/code/code-compare/list/icon-grid）
// のみ比較する別関数を用意
function extractCommonSlideTypes(content) {
  const commonTypes = [
    'タイトル', 'セクション区切り', 'コンテンツ', '図解',
    '対比・比較', '引用・メッセージ',
  ];
  const typeMatch = content.match(/### スライドタイプ定義[\s\S]*?(?=\n### |\n---|\n## |$)/);
  if (!typeMatch) return null;
  const lines = typeMatch[0].split('\n');
  // ヘッダー行 + 共通タイプの行のみ抽出
  const header = lines.filter(l => l.startsWith('|') && (l.includes('タイプ名') || l.includes('---')));
  const commonLines = lines.filter(l => commonTypes.some(t => l.includes(t)));
  return [...header, ...commonLines].join('\n');
}

// --- Check: shared-spec ---
function checkSharedSpec(decks) {
  const issues = [];
  const eligible = decks.filter(d => fs.existsSync(d.structureMd));
  if (eligible.length < 2) return issues;

  const allSpecs = eligible.map(d => ({
    name: d.name,
    specs: extractSharedSpecs(fs.readFileSync(d.structureMd, 'utf8')),
  }));

  const baseline = allSpecs[0];
  const sectionNames = {
    'svg-design': '共通SVG設計仕様',
    'a4-print': 'A4横配置・印刷品質保証仕様',
    'code-block': 'コードブロック共通仕様',
    'gsap': 'GSAPアニメーション共通設定',
    'font': 'フォント仕様',
  };

  for (let i = 1; i < allSpecs.length; i++) {
    for (const key of Object.keys(sectionNames)) {
      const baseText = baseline.specs[key];
      const compText = allSpecs[i].specs[key];

      if (!baseText && !compText) continue;
      if (!baseText || !compText) {
        issues.push({
          severity: 'error',
          category: 'shared-spec',
          message: `${sectionNames[key]}が${!compText ? allSpecs[i].name : baseline.name}に存在しない`,
          decks: [baseline.name, allSpecs[i].name],
          section: key,
        });
        continue;
      }

      if (baseText !== compText) {
        // Find specific differences
        const baseLines = baseText.split('\n');
        const compLines = compText.split('\n');
        const diffLines = [];
        const maxLen = Math.max(baseLines.length, compLines.length);
        for (let j = 0; j < maxLen; j++) {
          if (baseLines[j] !== compLines[j]) {
            diffLines.push({
              line: j + 1,
              baseline: baseLines[j] || '(なし)',
              compared: compLines[j] || '(なし)',
            });
          }
        }
        issues.push({
          severity: 'error',
          category: 'shared-spec',
          message: `${sectionNames[key]}に差分あり: ${baseline.name} vs ${allSpecs[i].name}`,
          decks: [baseline.name, allSpecs[i].name],
          section: key,
          diffs: diffLines.slice(0, 5), // 最大5行表示
        });
      }
    }
  }
  return issues;
}

// --- Check: external URLs ---
function checkUrls(decks) {
  const issues = [];
  const urlPattern = /https?:\/\/[^\s"'<>)}\]]+/g;
  const allowedDomains = [
    'fonts.googleapis.com',
    'fonts.gstatic.com',
    'cdnjs.cloudflare.com',
    'cdn.jsdelivr.net',
    'unpkg.com',
    'kit.fontawesome.com',
    'ka-f.fontawesome.com',
    'd3js.org',
    'www.w3.org',       // SVG/XHTML namespace URIs
    'w3.org',
  ];

  for (const deck of decks) {
    const files = [
      { name: 'structure.md', path: deck.structureMd },
      { name: 'index.html', path: deck.indexHtml },
    ];
    for (const file of files) {
      if (!fs.existsSync(file.path)) continue;
      const content = fs.readFileSync(file.path, 'utf8');
      const urls = content.match(urlPattern) || [];
      for (const url of urls) {
        const domain = url.replace(/https?:\/\//, '').split('/')[0];
        if (!allowedDomains.some(d => domain.includes(d))) {
          issues.push({
            severity: 'error',
            category: 'urls',
            message: `不要な外部URL検出: ${url}`,
            deck: deck.name,
            file: file.name,
          });
        }
      }
    }
  }
  return issues;
}

// --- Check: CSS variables consistency ---
function checkCssVars(decks) {
  const issues = [];
  if (decks.length < 2) return issues;

  const cssVarPattern = /--[\w-]+:\s*[^;]+;/g;
  const allVars = decks.map(d => {
    const cssPath = d.stylesCss;
    if (!fs.existsSync(cssPath)) return { name: d.name, vars: {} };
    const content = fs.readFileSync(cssPath, 'utf8');
    // Extract :root variables
    const rootMatch = content.match(/:root\s*\{([^}]+)\}/);
    if (!rootMatch) return { name: d.name, vars: {} };
    const vars = {};
    const matches = rootMatch[1].match(cssVarPattern) || [];
    for (const m of matches) {
      const [key, ...valueParts] = m.split(':');
      vars[key.trim()] = valueParts.join(':').replace(';', '').trim();
    }
    return { name: d.name, vars };
  });

  if (allVars.length < 2) return issues;
  const baseline = allVars[0];
  for (let i = 1; i < allVars.length; i++) {
    const compared = allVars[i];
    for (const [key, value] of Object.entries(baseline.vars)) {
      if (compared.vars[key] && compared.vars[key] !== value) {
        // Only flag theme/font variables, not slide-specific ones
        if (key.startsWith('--fs-') || key.startsWith('--color-') || key.startsWith('--accent-')) {
          issues.push({
            severity: 'warn',
            category: 'css-vars',
            message: `CSS変数 ${key} が異なる: ${baseline.name}="${value}" vs ${compared.name}="${compared.vars[key]}"`,
            decks: [baseline.name, compared.name],
          });
        }
      }
    }
  }
  return issues;
}

// --- Check: GSAP patterns ---
function checkGsap(decks) {
  const issues = [];
  if (decks.length < 2) return issues;

  for (const deck of decks) {
    if (!fs.existsSync(deck.scriptsJs)) continue;
    const content = fs.readFileSync(deck.scriptsJs, 'utf8');

    // Check for dangerous scale:0
    if (/scale\s*:\s*0[^.]/.test(content)) {
      issues.push({
        severity: 'error',
        category: 'gsap',
        message: 'scale: 0 を使用（最小0.8推奨）',
        deck: deck.name,
      });
    }

    // Check clearProps safety
    if (/querySelectorAll\s*\(\s*['"]?\*['"]?\s*\)/.test(content) && /clearProps/.test(content)) {
      issues.push({
        severity: 'error',
        category: 'gsap',
        message: "querySelectorAll('*')でclearProps適用（SVG破壊リスク）",
        deck: deck.name,
      });
    }

    // Check easing variety
    const easeMatches = content.match(/ease\s*:\s*['"]([^'"]+)['"]/g) || [];
    const uniqueEases = new Set(easeMatches.map(m => m.match(/['"]([^'"]+)['"]/)[1]));
    if (uniqueEases.size < 3) {
      issues.push({
        severity: 'warn',
        category: 'gsap',
        message: `イージング種類が${uniqueEases.size}種のみ（3種以上推奨）`,
        deck: deck.name,
      });
    }
  }
  return issues;
}

// --- Check: rem unit detection (unit-system.md Phase B migration) ---
// vw 移行進捗を可視化するため、各デッキの styles.css 内 rem 残数をカウント
function checkRemUnits(decks) {
  const issues = [];
  const remPattern = /(?<![\d.])\d+(?:\.\d+)?rem\b/g;
  for (const deck of decks) {
    if (!fs.existsSync(deck.stylesCss)) continue;
    const content = fs.readFileSync(deck.stylesCss, 'utf8');
    const matches = content.match(remPattern) || [];
    if (matches.length > 0) {
      issues.push({
        severity: 'warn',
        category: 'rem-units',
        message: `rem 単位が ${matches.length} 箇所検出（unit-system.md §3 に従い vw に移行推奨）`,
        deck: deck.name,
      });
    }
  }
  return issues;
}

// --- Check: Print CSS consistency ---
function checkPrint(decks) {
  const issues = [];
  if (decks.length < 2) return issues;

  for (const deck of decks) {
    if (!fs.existsSync(deck.stylesCss)) continue;
    const content = fs.readFileSync(deck.stylesCss, 'utf8');

    // Check @page margin: 0
    if (!/@page\s*\{[^}]*margin\s*:\s*0/.test(content)) {
      issues.push({
        severity: 'error',
        category: 'print',
        message: '@page { margin: 0 } が未設定',
        deck: deck.name,
      });
    }

    // Check slider__item print size
    const printSection = content.match(/@media\s+print\s*\{[\s\S]*$/);
    if (printSection) {
      if (!/297mm/.test(printSection[0])) {
        issues.push({
          severity: 'warn',
          category: 'print',
          message: '印刷時の幅297mmが未指定',
          deck: deck.name,
        });
      }
      if (!/210mm/.test(printSection[0])) {
        issues.push({
          severity: 'warn',
          category: 'print',
          message: '印刷時の高さ210mmが未指定',
          deck: deck.name,
        });
      }
    } else {
      issues.push({
        severity: 'error',
        category: 'print',
        message: '@media print セクションが存在しない',
        deck: deck.name,
      });
    }
  }
  return issues;
}

// --- Main ---
function main() {
  const decks = findSlideDecks(resolvedDir);

  if (decks.length === 0) {
    console.error(`エラー: ${resolvedDir} にslide-*ディレクトリが見つかりません`);
    process.exit(1);
  }

  console.log(`\n検出されたデッキ: ${decks.length}件`);
  decks.forEach(d => console.log(`  - ${d.name}`));
  console.log('');

  const allIssues = [];
  const checks = {
    'inputs': checkRequiredInputs,
    'shared-spec': checkSharedSpec,
    'urls': checkUrls,
    'css-vars': checkCssVars,
    'gsap': checkGsap,
    'print': checkPrint,
    'rem-units': checkRemUnits,
  };

  const categoriesToRun = checkCategory === 'all'
    ? Object.keys(checks)
    : [checkCategory];

  const unknown = categoriesToRun.filter(cat => !checks[cat]);
  if (unknown.length > 0) {
    console.error(`不明なカテゴリ: ${unknown.join(', ')}`);
    process.exit(2);
  }

  for (const cat of categoriesToRun) {
    const issues = checks[cat](decks);
    allIssues.push(...issues);
  }

  // --- Output ---
  const errors = allIssues.filter(i => i.severity === 'error');
  const warns = allIssues.filter(i => i.severity === 'warn');

  if (jsonOutput) {
    console.log(JSON.stringify({
      deckCount: decks.length,
      decks: decks.map(d => d.name),
      totalIssues: allIssues.length,
      errors: errors.length,
      warnings: warns.length,
      issues: allIssues,
      verdict: errors.length > 0 ? 'FAIL' : warns.length > 0 ? 'WARN' : 'PASS',
    }, null, 2));
  } else {
    if (allIssues.length === 0) {
      console.log('全チェック PASS - 問題なし');
    } else {
      if (errors.length > 0) {
        console.log(`\n[ERROR] ${errors.length}件:`);
        errors.forEach(e => {
          console.log(`  ${e.category}: ${e.message}`);
          if (e.deck) console.log(`    対象: ${e.deck}`);
          if (e.decks) console.log(`    対象: ${e.decks.join(' / ')}`);
          if (e.diffs) e.diffs.forEach(d => {
            console.log(`    L${d.line}: "${d.baseline}" → "${d.compared}"`);
          });
        });
      }
      if (warns.length > 0) {
        console.log(`\n[WARN] ${warns.length}件:`);
        warns.forEach(w => {
          console.log(`  ${w.category}: ${w.message}`);
          if (w.deck) console.log(`    対象: ${w.deck}`);
          if (w.decks) console.log(`    対象: ${w.decks.join(' / ')}`);
        });
      }
      console.log(`\n判定: ${errors.length > 0 ? 'FAIL' : 'WARN'}`);
    }
  }

  // Exit code
  if (errors.length > 0) process.exit(2);
  if (warns.length > 0) process.exit(1);
  process.exit(0);
}

main();
