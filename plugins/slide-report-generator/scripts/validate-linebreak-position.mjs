#!/usr/bin/env node
/**
 * SR-3-09 / V-021: <br> の位置が文節の切れ目かを見る。
 *
 * 判定は「<br> の直前が句読点・文末表現・助詞・中黒か」だけ。文字数は一切
 * 使わない。正本（references/spec-registry.md SR-3-09）が「改行位置は文字数では
 * なく句読点・助詞など文節の切れ目で決める」と明示しており、文字数を持ち込むと
 * 正本が否定した基準を実装することになる。
 *
 * 語彙の正本は vendor/scripts/utils.js の LINEBREAK_RULES。挿入器
 * （auto-linebreak.js）と同じ集合を読む。別々に持つと、挿入器が入れた <br> を
 * この検査器が落とす。
 *
 * 検査対象は <br> を持つテキストだけ。「長いのに <br> が無い」場合は見ない。
 * 長さの判定には箱の幅が要り、それは描画後にしか分からないので、ここで長さを
 * 決めると根拠のない数値が 1 つ増える。取りこぼす分は描画後の持ち場
 * （ui-quality-checklist の「テキスト切れ」「カード内無折り返し」）が拾う。
 *
 * 使用方法:
 *   node scripts/validate-linebreak-position.mjs <html-file...> [--json]
 *   node scripts/validate-linebreak-position.mjs --self-test
 *
 * exit: 0 = 違反なし / 1 = 違反あり / 2 = 引数エラー / 3 = 判定不能（fail-closed）
 */

import { readFileSync, existsSync } from "fs";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const UTILS_PATH = resolve(__dirname, "..", "vendor", "scripts", "utils.js");

// 語彙が取れないなら判定しない。空集合で走ると「違反ゼロ」に見えるが、それは
// 検査できていないだけで、緑が何も保証しない。
let LINEBREAK_RULES;
try {
  if (!existsSync(UTILS_PATH)) {
    throw new Error(`語彙の正本が見つからない: ${UTILS_PATH}`);
  }
  ({ LINEBREAK_RULES } = await import(`file://${UTILS_PATH}`));
  if (!Array.isArray(LINEBREAK_RULES) || LINEBREAK_RULES.length === 0) {
    throw new Error("LINEBREAK_RULES が配列として取れない");
  }
  for (const rule of LINEBREAK_RULES) {
    if (!rule || !Array.isArray(rule.chars) || rule.chars.length === 0) {
      throw new Error(`LINEBREAK_RULES の要素に chars が無い: ${JSON.stringify(rule)}`);
    }
  }
} catch (err) {
  console.error(`改行語彙を読めない (fail-closed): ${err.message}`);
  process.exit(3);
}

// 直前に来てよい語。長い語から先に見ないと「ます」が「す」で当たらない。
const ALLOWED = LINEBREAK_RULES
  .flatMap(rule => rule.chars.map(ch => ({ token: ch, group: rule.name })))
  .sort((a, b) => b.token.length - a.token.length);

const BR = new RegExp("<br\\s*/?>", "gi");
const TAG = new RegExp("<[^>]+>", "g");
// script / style / HTML コメントの中身は「読者が読む文章」ではない。ここを剥がさずに
// 生の HTML へ正規表現をかけると、検査器自身のパターン定義（/([。！？])(?!<br>)/ など）や
// テンプレートリテラルの断片を「文節でない位置の <br>」として拾う。実測で、この 3 種を
// 剥がさない状態では検出 13 件が全件そういう誤検出だった。
const NON_PROSE = new RegExp(
  "<script\\b[^>]*>[\\s\\S]*?</script\\s*>" +
    "|<style\\b[^>]*>[\\s\\S]*?</style\\s*>" +
    "|<!--[\\s\\S]*?-->",
  "gi",
);

/**
 * 文章でない領域を、同じ長さの空白へ潰す。
 *
 * 削除ではなく同長置換なのは、findings の行番号が元ファイルの行番号と一致し続ける
 * ようにするため。改行だけは残す。
 */
function maskNonProse(html) {
  return html.replace(NON_PROSE, block => block.replace(/[^\n]/g, " "));
}

/**
 * <br> の直前の語を判定する。
 *
 * 直前がタグ（<span> 等）で終わっている場合は、タグを剥がした上で最後の文字を
 * 見る。剥がした結果が空なら「行頭の <br>」で、文節の切れ目とは言えない。
 *
 * 末尾の空白・改行・字下げは落としてから見る。整形された HTML では
 * 「文章です。\n            <br>」のように <br> が次行に来るのが普通で、
 * 落とさないと直前の語が空白になり、正しい改行が全部落ちる。
 */
function judge(before) {
  const text = before.replace(TAG, "").replace(/\s+$/, "");
  if (text.length === 0) return { ok: false, reason: "直前にテキストが無い（行頭の改行）" };
  for (const { token, group } of ALLOWED) {
    if (text.endsWith(token)) return { ok: true, group, token };
  }
  return { ok: false, reason: `直前が「${text.slice(-4)}」で、句読点・文末表現・助詞・中黒のどれでもない` };
}

function inspect(html) {
  const masked = maskNonProse(html);
  const findings = [];
  let checked = 0;
  BR.lastIndex = 0;
  let m;
  while ((m = BR.exec(masked)) !== null) {
    checked++;
    const verdict = judge(masked.slice(0, m.index));
    if (!verdict.ok) {
      const line = masked.slice(0, m.index).split("\n").length;
      findings.push({ line, reason: verdict.reason });
    }
  }
  return { checked, findings };
}

// ---- self-test ----
function selfTest() {
  // 期待値は findings だけでなく checked も置く。findings だけを見ると、
  // 「script の中まで走査しているが、たまたま中身が合法だったので 0 件」を
  // PASS と読んでしまう。数えた対象の数まで縛らないと、除外の検証にならない。
  const cases = [
    ["文章が続きます。<br>次の行", 0, 1, "句点の直後"],
    ["前半があり、<br>後半", 0, 1, "読点の直後"],
    ["これは動きます<br>次", 0, 1, "文末表現の直後"],
    ["対象の資料を<br>配布", 0, 1, "助詞の直後"],
    ["赤・青・<br>緑", 0, 1, "中黒の直後"],
    ["<span>ここまでです。</span><br>次", 0, 1, "タグ越しでも直前の語を見る"],
    ["途中で切れる文字<br>列", 1, 1, "文節でない位置は落とす"],
    ["<br>行頭", 1, 1, "直前にテキストが無い"],
    ["改行の無い長い長い長い長い長い長い長い長い長い長い長い文章", 0, 0, "<br> が無いものは対象外"],
    // 以下 4 件は、実ファイルに初めて当てて出た誤検出を再現するために足した。
    // self-test が script を含まない裸の断片だけだったので、この欠陥は
    // 合成入力では一度も出ず、実物に当てるまで緑のままだった。
    ['<script>const P = /([。！？])(?!<br>)/g;</script>', 0, 0, "script 内の <br> は文章でない"],
    ['<script>tpl(`${d.label}<br>${d.value}`)</script>', 0, 0, "script 内のテンプレートリテラルも同じ"],
    ['<style>.x::after{content:"<br>"}</style>', 0, 0, "style 内も同じ"],
    ["<!-- 旧実装では 文字数<br>で切っていた -->", 0, 0, "HTML コメント内も同じ"],
    ["<p>ここまでです。\n            <br>\n            次</p>", 0, 1, "字下げで <br> が次行にあっても落とさない"],
    ['<script>x="<br>"</script><p>本文です。<br>次</p>', 0, 1, "script を挟んでも後続の本文は検査する"],
  ];
  let ng = 0;
  for (const [html, want, wantChecked, label] of cases) {
    const got = inspect(html);
    const ok = got.findings.length === want && got.checked === wantChecked;
    if (!ok) ng++;
    console.log(
      `  ${ok ? "PASS" : "FAIL"}  ${label} ` +
        `(違反 期待 ${want} / 実測 ${got.findings.length}, ` +
        `対象 期待 ${wantChecked} / 実測 ${got.checked})`,
    );
  }
  console.log("");
  console.log(`語彙の由来: ${UTILS_PATH}`);
  console.log(`許可する直前の語: ${ALLOWED.map(a => a.token).join(" ")}`);
  console.log(ng === 0 ? `PASS ${cases.length}/${cases.length}` : `FAIL ${ng} 件`);
  return ng === 0 ? 0 : 1;
}

// ---- entry ----
const args = process.argv.slice(2);
if (args.includes("--self-test")) {
  process.exit(selfTest());
}

const jsonMode = args.includes("--json");
const paths = args.filter(a => !a.startsWith("--"));
if (paths.length === 0) {
  console.error("HTML ファイルを 1 つ以上指定してください（--self-test で自己診断）");
  process.exit(2);
}

const results = [];
for (const p of paths) {
  if (!existsSync(p)) {
    console.error(`ファイルが見つからない (fail-closed): ${p}`);
    process.exit(3);
  }
  const { checked, findings } = inspect(readFileSync(p, "utf8"));
  results.push({ file: p, checked, findings });
}

const violations = results.reduce((n, r) => n + r.findings.length, 0);
const checkedTotal = results.reduce((n, r) => n + r.checked, 0);
// 「対象が 0 件だった」と「対象を見た結果 違反が無かった」は、どちらも違反 0 件だが
// 保証している内容が違う。前者は何も保証していない。exit code では区別できないので、
// 出力側で必ず言い分ける。verdict を機械可読側にも出す。
const verdict = checkedTotal === 0 ? "not-checked" : violations === 0 ? "pass" : "fail";

if (jsonMode) {
  console.log(
    JSON.stringify(
      { rule: "SR-3-09", vid: "V-021", verdict, checked: checkedTotal, results, violations },
      null,
      2,
    ),
  );
} else {
  for (const r of results) {
    console.log(
      r.checked === 0
        ? `${r.file}: <br> が 0 件（未検査。この規則は何も保証していない）`
        : `${r.file}: <br> ${r.checked} 件を検査`,
    );
    for (const f of r.findings) {
      console.log(`  行 ${f.line}: ${f.reason}`);
    }
  }
  console.log("");
  if (verdict === "not-checked") {
    console.log("SR-3-09: 対象 0 件（未検査）。違反なしとは別の状態です");
  } else if (verdict === "pass") {
    console.log(`SR-3-09: 違反なし（<br> ${checkedTotal} 件を検査）`);
  } else {
    console.log(`SR-3-09: ${violations} 件が文節の切れ目でない（<br> ${checkedTotal} 件中）`);
  }
}

process.exit(violations === 0 ? 0 : 1);
