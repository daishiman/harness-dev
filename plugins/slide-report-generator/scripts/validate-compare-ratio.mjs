#!/usr/bin/env node
/**
 * SR-4-03 / V-001: Before/After（比較）レイアウトの 2 パネル等幅 + 版面比の間隔。
 *
 * V-001 はこれまでどの工程にも実行体が無かった。structure.json には CSS が無いので
 * validate-structure.js では判定できず、生成された deck の CSS を読むこの検査器が
 * 実行体になる。判定対象は**生成物**であって、生成器や文書ではない。
 *
 * 判定の印は発明していない。実装が出している class をそのまま使う。
 *   - html-scaffold.js:199 が `<div class="compare-container">` を出す
 *   - style-builder.cjs:406,410 が `.compare-container` / `.compare-panel` を定義する
 *
 * パネルの class 名は経路で 2 つある。決定論経路が `.compare-panel`、骨格経路が
 * `.compare-item`（html-scaffold.js の COMPARE 直前のコメントが「class 名は異なるが
 * 規則が定めているのは比率であって class 名ではない」と明記している）。**両方を
 * パネルとして見る。**片方だけ見ると、骨格経路の deck が幅を 48% で宣言していても
 * 見えず、直す人が存在しない宣言を探すことになる。
 *
 * 現存 deck の `.compare-item` 側は `flex: 1` + `max-width: 480px` 系で `width` を
 * 宣言していない（`max-width` を `width` と数えない。両者は別の宣言で、等幅の根拠に
 * ならない。`flex: 1` は伸長の指示であって版面比でもない）。ただし「宣言なし」で
 * 丸めると、直す人は何が幅を決めているのかを自分で探し直すことになるので、
 * `max-width` / `flex-basis` / `flex` が宣言されていれば **その値を内訳として出す**
 * （`substitute` フィールド）。何本が「本当は max-width で壊れているのか」はここから数える。
 *
 * 規則が定めているのは 2 つ:
 *   - 2 パネル（`.compare-panel` / `.compare-item`）が**等幅**であること
 *   - `.compare-container` の間隔が**版面比**（% 単位）であること
 * `display: flex` は上を成立させる手段であって規則の数ではないので見ない。
 *
 * 中央に第 3 要素（`<div class="compare-vs">VS</div>`）を置いた deck が実在する。
 * 48/4/48 = 100 には第 3 要素の居場所が無いので、**中央要素があるときは 48%/4% の
 * 数値一致を求めない**。求めるのは等幅・版面比・そして 2*width + gap が 100% を
 * 超えないこと（超えれば中央要素が押し出されるか折り返す）。中央要素が無いときは
 * 従来どおり 48% / 4% の一致を求める（緩めない）。
 *
 * セレクタの主体（最後の compound）が `.compare-container` / `.compare-panel` の
 * 規則だけを見る。`.compare-panel h3 { gap: 1rem }` のような子孫規則は対象外。
 * これを区別しないと、実測 29 deck のうち 18 件が「パネルの gap が 4% でない」と
 * いう誤判定になる（h3 / li の内部間隔を比較レイアウトの隙間と取り違えるため）。
 * `.compare-panel--before` のような別クラスも対象外（クラス名は完全一致で見る）。
 *
 * 使用方法:
 *   node scripts/validate-compare-ratio.mjs <html-file...> [--json]
 *   node scripts/validate-compare-ratio.mjs --self-test
 *
 * exit: 0 = 違反なし / 1 = 違反あり / 2 = 引数エラー / 3 = 判定不能（fail-closed）
 */

import { readFileSync, existsSync } from "fs";

// SR-4-03 の値。正本は references/spec-registry.md の SR-4-03 行で、ここは写し。
// 写しが正本から離れていないことは tests/test_compare_ratio.py が突き合わせる。
const EXPECT = { gap: "4%", width: "48%" };

const CONTAINER = /\.compare-container(?![\w-])/;
const PANEL = /\.compare-(?:panel|item)(?![\w-])/;
// 中央の第 3 要素。CSS 規則にも markup の class 属性にも現れうる。
const CENTER = /(?<![\w-])compare-vs(?![\w-])/;

// width が宣言されていないときに「では何が幅を決めているのか」を出すための宣言。
// これらは width の代わりにならない（等幅の根拠にならない）が、直す人はここを見る。
const WIDTH_SUBSTITUTES = ["max-width", "flex-basis", "flex", "min-width"];

/**
 * CSS 規則ブロックを取り出す。deck には base64 画像が埋まっていることがあり、
 * `[^{}]*` を含む正規表現で丸ごと掴むと O(n^2) になるので、クラス名の位置から
 * 前後の区切りを索いて切り出す。
 */
function rulesFor(css, needle) {
  const found = [];
  let i = 0;
  while ((i = css.indexOf(needle, i)) !== -1) {
    const open = css.indexOf("{", i);
    if (open === -1) break;
    const close = css.indexOf("}", open);
    if (close === -1) break;
    let start = Math.max(css.lastIndexOf("}", i), css.lastIndexOf("{", i), css.lastIndexOf(";", i));
    start = start === -1 ? 0 : start + 1;
    const selectorList = css.slice(start, open).replace(/\s+/g, " ").trim();
    const body = css.slice(open + 1, close).replace(/\s+/g, " ").trim();
    if (selectorList.includes(needle)) found.push({ selectorList, body });
    i = close + 1;
  }
  return found;
}

/** セレクタ群のうち、主体（最後の compound）が対象クラスであるものが 1 つでもあるか。 */
function hasSubject(selectorList, re) {
  return selectorList
    .split(",")
    .map(s => s.trim())
    .filter(Boolean)
    .some(sel => {
      const last = sel.split(/[\s>+~]+/).filter(Boolean).pop() || "";
      return re.test(last);
    });
}

function declaration(body, prop) {
  const m = body.match(new RegExp(`(?:^|;)\\s*${prop}\\s*:\\s*([^;]+)`, "i"));
  if (!m) return null;
  return m[1].replace(/!important/i, "").trim();
}

/** 値が版面比（% 単位）ならその数値、そうでなければ null。 */
function percent(value) {
  const m = /^(\d+(?:\.\d+)?)\s*%$/.exec(value || "");
  return m ? parseFloat(m[1]) : null;
}

/** 主体が対象クラスである規則だけを、重複を落として返す。 */
function subjectRules(html, needles, re) {
  // 1 つの規則が両方の class を含むことがある（`.compare-panel, .compare-item {}`）。
  // needle ごとに拾うと同じ規則を 2 回数えるので、選択子と本文で重複を落とす。
  const seen = new Set();
  return needles
    .flatMap(n => rulesFor(html, n))
    .filter(r => hasSubject(r.selectorList, re))
    .filter(r => {
      const key = `${r.selectorList}{${r.body}}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

const PANEL_LABEL = "パネル（.compare-panel / .compare-item）";

function inspect(html) {
  const findings = [];
  let checked = 0;

  // 中央に第 3 要素があるか。あるときは 48%/4% の一致でなく等幅・版面比を求める。
  const hasCenter = CENTER.test(html);

  // 比較レイアウトを使っているか。CSS 規則と markup の両方を見る。
  // markup にだけ出てくる（CSS が外にある）場合も「使っている」と数え、下の
  // 宣言なし判定へ回す。比率を決める宣言が見当たらないなら緑にはしない。
  // class 名は完全一致で見る。前側の境界を落とすと `code-compare-container`
  // （別クラス。SR-4-03 の対象ではない）を拾って、比較レイアウトを使っていない
  // deck に「宣言なし」の違反が出る（実測で 1 件この誤検出が出た）。
  const usesCompare = CONTAINER.test(html) || PANEL.test(html)
    || /class="[^"]*(?<![\w-])compare-(?:container|panel|item)(?![\w-])/.test(html);

  const containerRules = subjectRules(html, [".compare-container"], CONTAINER);
  const panelRules = subjectRules(html, [".compare-panel", ".compare-item"], PANEL);

  // --- 間隔 ---
  const gaps = [];
  const gapWant = hasCenter ? "版面比（% 単位）" : EXPECT.gap;
  for (const rule of containerRules) {
    const got = declaration(rule.body, "gap");
    if (got === null) continue;
    checked++;
    gaps.push(got);
    if (hasCenter ? percent(got) !== null : got === EXPECT.gap) continue;
    findings.push({
      selector: rule.selectorList, prop: "gap", expected: gapWant, actual: got,
      reason: `.compare-container の gap が ${gapWant} でない`
    });
  }

  // --- パネルの幅 ---
  const widths = [];
  const widthWant = hasCenter ? "版面比（% 単位）で等幅" : EXPECT.width;
  for (const rule of panelRules) {
    const got = declaration(rule.body, "width");
    if (got === null) continue;
    checked++;
    widths.push({ selector: rule.selectorList, value: got });
    if (hasCenter ? percent(got) !== null : got === EXPECT.width) continue;
    findings.push({
      selector: rule.selectorList, prop: "width", expected: widthWant, actual: got,
      reason: `${PANEL_LABEL} の width が ${widthWant} でない`
    });
  }

  // 比率を決める宣言がどこにも無い場合。既定値（gap 0 / width auto）で描かれるので
  // 等幅にも版面比にもならない。「宣言が無い」を見逃すと規則が緑で通ってしまう。
  if (usesCompare && gaps.length === 0) {
    findings.push({
      selector: ".compare-container", prop: "gap", expected: gapWant, actual: "(宣言なし)",
      reason: "比較レイアウトを使っているのに .compare-container の gap を宣言していない"
    });
  }
  if (usesCompare && widths.length === 0) {
    // 「宣言なし」で丸めない。幅を実際に決めている宣言を内訳として出す。
    // 直す人はここを見て、max-width で壊れているのか何も無いのかを区別する。
    const substitute = [];
    for (const rule of panelRules) {
      for (const prop of WIDTH_SUBSTITUTES) {
        const value = declaration(rule.body, prop);
        if (value !== null) substitute.push({ selector: rule.selectorList, prop, value });
      }
    }
    const detail = substitute.map(s => `${s.prop}: ${s.value}`).join(" / ");
    findings.push({
      selector: PANEL_LABEL, prop: "width", expected: widthWant, actual: "(宣言なし)", substitute,
      reason: substitute.length
        ? `${PANEL_LABEL} の width が無く、幅は ${detail} で決まっている（版面比でも等幅の宣言でもない）`
        : `比較レイアウトを使っているのに ${PANEL_LABEL} の width を宣言していない`
    });
  }

  // --- 等幅 ---
  // パネルごとに違う幅が宣言されていれば、値が版面比でも規則の本体を満たさない。
  const distinct = [...new Set(widths.map(w => w.value))];
  if (distinct.length > 1) {
    findings.push({
      selector: widths.map(w => w.selector).join(" | "), prop: "width",
      expected: "2 パネル等幅", actual: distinct.join(" / "),
      reason: `${PANEL_LABEL} に異なる幅が宣言されている（等幅でない）`
    });
  }

  // --- 中央要素の居場所 ---
  // 2*width + gap が 100% を超えると、中央要素は押し出されるか折り返す。
  if (hasCenter && distinct.length === 1 && gaps.length > 0) {
    const w = percent(distinct[0]);
    const g = percent(gaps[0]);
    if (w !== null && g !== null && 2 * w + g > 100) {
      findings.push({
        selector: PANEL_LABEL, prop: "width", expected: "2*width + gap <= 100%",
        actual: `2*${distinct[0]} + ${gaps[0]} = ${(2 * w + g).toFixed(1)}%`,
        reason: "中央要素（.compare-vs）があるのに 2 パネルと間隔で版面を使い切っている"
      });
    }
  }

  return { usesCompare, hasCenter, checked, findings };
}

// ---- self-test ----
function selfTest() {
  const style = css => `<style>${css}</style>`;
  const cases = [
    [style(".compare-container { display: flex; gap: 4%; } .compare-panel { width: 48%; }"), 0,
      "正: 48/4/48"],
    [style(".compare-container { display: flex; gap: 2rem; } .compare-panel { width: 48%; }"), 1,
      "gap が 4% でない"],
    [style(".compare-container { display: flex; gap: 4%; } .compare-panel { width: 50%; }"), 1,
      "width が 48% でない"],
    [style(".compare-container { display: flex; gap: 2rem; justify-content: center; }"), 2,
      "gap 違反 + panel の width 宣言なし"],
    [style(".compare-container { gap: 4%; } .compare-panel { width: 48%; } .compare-panel h3 { gap: 1rem; }"), 0,
      "子孫規則の gap は比較レイアウトの隙間ではない"],
    [style(".compare-container { gap: 4%; } .compare-panel { width: 48%; } .compare-panel--before { width: 30%; }"), 0,
      "別クラス（--before）は対象外"],
    [style(".slide-compare .compare-container { gap: 4%; } .compare-panel { width: 48%; }"), 0,
      "祖先付きセレクタでも主体なら見る"],
    [style(".pc-container, .compare-container, .ps-container { gap: 8mm !important; } .compare-panel { width: 48%; }"), 1,
      "まとめ書きの中の主体も見る（!important も値で判定）"],
    [style(".compare-container { gap: 4%; } .compare-panel { width : 48% ; }"), 0,
      "空白の入った宣言も同値と見る"],
    ["<p>比較レイアウトを使わない HTML</p>", 0, "使っていないなら検査 0"],
    ['<div class="code-compare-container"><div class="code-compare-column"></div></div>', 0,
      "別クラス code-compare-container は SR-4-03 の対象でない"],
    ['<div class="compare-left compare-panel">左</div>', 2,
      "markup で使っているのに比率の宣言がどこにも無い"],
    [style(".compare-container { gap: 4%; } .compare-item { width: 48%; }"), 0,
      "骨格経路のパネル class（.compare-item）も同じ規則で見る"],
    [style(".compare-container { gap: 4%; } .compare-item { width: 550px; }"), 1,
      "陽性対照: .compare-item の px 固定は落ちる（宣言なしではなく値違反として出す）"],
    [style(".compare-container { gap: 4%; } .compare-panel, .compare-item { width: 48%; }"), 0,
      "両 class をまとめ書きした規則を 2 回数えない"],
    [style(".compare-container { gap: 4%; } .compare-item-label { width: 10px; } .compare-panel { width: 48%; }"), 0,
      "別クラス compare-item-label は対象外"],
    [style(".compare-container { gap: 4%; } .compare-item { flex: 1; max-width: 480px; }"), 1,
      "max-width は width と数えない（既存 deck の実態。等幅の根拠にならない）"],
    [style(".compare-container { gap: 4%; } .compare-panel { width: 48%; } .compare-item { width: 40%; }"), 2,
      "パネルごとに違う幅は等幅違反（値違反と等幅違反の 2 件）"],
    ['<div class="compare-vs">VS</div>' + style(".compare-container { gap: 3%; } .compare-panel { width: 46%; }"), 0,
      "中央要素があるときは 48%/4% でなくてよい（等幅・版面比なら通す）"],
    ['<div class="compare-vs">VS</div>' + style(".compare-container { gap: 4%; } .compare-panel { width: 48%; }"), 0,
      "中央要素があっても 48/4/48 ちょうどは通す（2*48+4 = 100）"],
    ['<div class="compare-vs">VS</div>' + style(".compare-container { gap: 2rem; } .compare-panel { width: 46%; }"), 1,
      "中央要素があっても間隔が版面比でなければ落ちる"],
    ['<div class="compare-vs">VS</div>' + style(".compare-container { gap: 4%; } .compare-panel { width: 49%; }"), 1,
      "中央要素の居場所が無い（2*49+4 = 102%）"],
    [style(".compare-container { gap: 4%; } .compare-vs { width: 4%; } .compare-panel { width: 46%; }"), 0,
      "中央要素は CSS 規則側にあっても認める"],
  ];
  let ng = 0;
  for (const [html, want, label] of cases) {
    const got = inspect(html).findings.length;
    const ok = got === want;
    if (!ok) ng++;
    console.log(`  ${ok ? "PASS" : "FAIL"}  ${label} (期待 ${want} / 実測 ${got})`);
  }

  // 内訳が出ることは件数では確かめられないので、値そのものを見る。
  // これが空に戻ると「宣言なし」に丸めた昔の出力へ逆戻りする。
  const sub = inspect(style(".compare-container { gap: 4%; } .compare-item { flex: 1; max-width: 480px; }"))
    .findings.find(f => f.actual === "(宣言なし)")?.substitute || [];
  const subOk = sub.some(s => s.prop === "max-width" && s.value === "480px")
    && sub.some(s => s.prop === "flex" && s.value === "1");
  if (!subOk) ng++;
  console.log(`  ${subOk ? "PASS" : "FAIL"}  width 宣言なしのとき max-width / flex を内訳として出す (実測 ${JSON.stringify(sub)})`);

  console.log("");
  const total = cases.length + 1; // 件数比較 + 内訳の値検査
  console.log(ng === 0 ? `PASS ${total}/${total}` : `FAIL ${ng} 件`);
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
  const { usesCompare, hasCenter, checked, findings } = inspect(readFileSync(p, "utf8"));
  results.push({ file: p, usesCompare, hasCenter, checked, findings });
}

const violations = results.reduce((n, r) => n + r.findings.length, 0);

if (jsonMode) {
  console.log(JSON.stringify({ rule: "SR-4-03", vid: "V-001", expected: EXPECT, results, violations }, null, 2));
} else {
  for (const r of results) {
    const center = r.hasCenter ? "・中央要素あり" : "";
    console.log(`${r.file}: ${r.usesCompare ? `比較レイアウトあり（宣言 ${r.checked} 件を検査${center}）` : "比較レイアウトなし"}`);
    for (const f of r.findings) console.log(`  ${f.selector} { ${f.prop}: ${f.actual} } 期待 ${f.expected} — ${f.reason}`);
  }
  console.log("");
  console.log(violations === 0 ? "SR-4-03: 違反なし" : `SR-4-03: ${violations} 件の違反`);
}

process.exit(violations === 0 ? 0 : 1);
