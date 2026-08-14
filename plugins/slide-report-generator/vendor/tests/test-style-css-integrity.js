/**
 * test-style-css-integrity.js — 生成 CSS の構文健全性
 *
 * 背景 (実際に起きた事故):
 * style-builder.cjs の CSS はテンプレートリテラル中に直接書かれており、そこに置く
 * `/* ... *\/` は JS のコメントではなく **CSS のコメント** としてそのまま出力される。
 * 長い解説コメントの途中に `*\/` を余分に書くと、そこでコメントが閉じ、残りの解説文が
 * 生の文字列として CSS へ流れ出す。流れ出した文はセレクタとして解釈され、**直後の
 * `{...}` を丸ごと飲み込む**。実際に .grid-container[data-layout="stack"] の中核規則が
 * これで消え、DOM もセレクタも正しいのに規則だけが存在しない状態になった。
 *
 * 目で見て気付ける類ではない (書いた本人も読み手も読み飛ばした) ので機械で見る。
 * 検査は 2 段:
 *   1. コメントの対応が取れているか (閉じていない `/*` / 宙に浮いた `*\/`)
 *   2. コメントを除いた後、規則の前置き (セレクタ) に日本語などセレクタに現れ得ない
 *      文字が混じっていないか = 解説文が漏れ出していないか
 * 2 は特定のセレクタ名を列挙しないので、今回の面に限らず同じ事故を拾える。
 */
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const here = path.dirname(fileURLToPath(import.meta.url));
const { buildStyles } = require(path.join(here, '..', 'scripts', 'style-builder.cjs'));

let failures = 0;
const fail = (msg) => {
  failures += 1;
  process.stdout.write('FAIL ' + msg + '\n');
};
const ok = (msg) => process.stdout.write('ok   ' + msg + '\n');

/** 位置つきで行番号を出す (指摘だけされても直せないため) */
const lineOf = (s, i) => s.slice(0, i).split('\n').length;

/**
 * コメントを取り除きつつ、対応の崩れを報告する。
 * 文字列リテラル (url("...") 等) の中の `/*` は CSS では稀なので扱わない。
 */
function stripComments(css) {
  let out = '';
  let i = 0;
  const errors = [];
  while (i < css.length) {
    if (css.startsWith('/*', i)) {
      const end = css.indexOf('*/', i + 2);
      if (end < 0) {
        errors.push('閉じていない /* が ' + lineOf(css, i) + ' 行目にある');
        break;
      }
      // 除去した分は改行だけ残して行番号をずらさない
      out += css.slice(i, end + 2).replace(/[^\n]/g, '');
      i = end + 2;
      continue;
    }
    if (css.startsWith('*/', i)) {
      errors.push(
        '対応する /* を持たない */ が ' + lineOf(css, i) + ' 行目にある' +
          ' (直前のコメントが早く閉じている。以降の解説文がセレクタとして扱われ、次の規則が飲まれる)'
      );
      i += 2;
      continue;
    }
    out += css[i];
    i += 1;
  }
  return { text: out, errors };
}

/** セレクタ / at-rule の前置きに現れてよい文字。日本語や句読点は含めない */
const SELECTOR_OK = /^[\s\w\-.#:,>+~*[\]()='"@%/!$^|\\]*$/;

function checkPreludes(css) {
  const bad = [];
  const good = [];
  let depth = 0;
  let prelude = '';
  let preludeStart = 0;
  for (let i = 0; i < css.length; i += 1) {
    const ch = css[i];
    if (ch === '{') {
      if (depth === 0) {
        const p = prelude.trim();
        if (p && !SELECTOR_OK.test(p)) {
          bad.push({ line: lineOf(css, preludeStart), text: p.replace(/\s+/g, ' ').slice(0, 90) });
        } else if (p) {
          good.push(p.replace(/\s+/g, ' '));
        }
      }
      depth += 1;
      prelude = '';
      continue;
    }
    if (ch === '}') {
      depth = Math.max(0, depth - 1);
      prelude = '';
      preludeStart = i + 1;
      continue;
    }
    if (depth === 0) {
      if (!prelude.trim() && !/\s/.test(ch)) preludeStart = i;
      prelude += ch;
    }
  }
  return { bad, good };
}

const css = buildStyles({});

const { text, errors } = stripComments(css);
if (errors.length) errors.forEach((e) => fail('コメントの対応が崩れている: ' + e));
else ok('CSS コメントの対応が取れている (宙に浮いた */ なし)');

const { bad, good } = checkPreludes(text);
if (bad.length) {
  bad.forEach((b) =>
    fail('セレクタに解説文が漏れている (生成 CSS ' + b.line + ' 行目付近): ' + b.text)
  );
} else {
  ok('規則の前置きがすべてセレクタとして妥当 (解説文の漏れなし)');
}

/**
 * 事故そのものの回帰ガード。上の 2 段で拾えるはずだが、飲まれた側は「規則が無い」という
 * 不在なので、消えて困る中核規則は名指しでも見ておく。文字列を含むかではなく
 * **正しい前置き (セレクタ) として成立しているか** で見る。飲まれた規則は前置きの先頭に
 * 解説文が付くため、単なる部分一致では素通りしてしまう。
 */
const MUST_EXIST = [
  '.grid-container[data-layout="stack"]',
  '.grid-container[data-rows="1"] .grid-cell',
];
const preludeParts = new Set(good.flatMap((p) => p.split(',').map((x) => x.trim())));
for (const sel of MUST_EXIST) {
  if (preludeParts.has(sel)) ok('規則が存在する: ' + sel);
  else fail('規則が生成 CSS に存在しない (コメント漏れに飲まれた可能性): ' + sel);
}

if (failures) {
  process.stdout.write('\ntest-style-css-integrity: FAIL (' + failures + ' 件)\n');
  process.exit(1);
}
process.stdout.write('\ntest-style-css-integrity: PASS\n');
