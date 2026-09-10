/**
 * render-report.js — report-structure.json → report.html (決定論生成)
 *
 * 契約: report-structure.schema.json (正本) / BUILD CONTRACT §F・§E・§D。
 *   実行: node render-report.js <report-structure.json> <out.html>
 *
 * schema 語彙で読む (consumer は正本 schema に conform):
 *   - meta: title/reportType/audience/keyMessage/subtitle/length(brief|standard|deep)/author…
 *   - section: id(^section-)/heading/paragraphs[]/role/visual/readingOrder(視線方向 enum・任意)/callouts
 *   - visual: {kind, spec, caption, alt, rationale}  ← caption/alt は visual 直下 (spec 内でない)
 *       kind=svg         → svgSpec {variant, nodes[](^n-), edges?, groups?} を svg-builder.cjs へ dispatch
 *       kind=mermaid     → mermaidSpec {diagramType, definition} を mermaid-render.js へ
 *       kind=codex-image → aiVisualSpec {pattern, backgroundSource, asset?, slug, overlayText…} を <img>/composite へ
 *       kind=none        → spec 省略・テキストのみ
 *
 * 意匠トークン (Kanagawa Lotus 配色 / フォント / spacing / 最小サイズ) は
 * vendored `style-builder.cjs` の SPEC を **唯一のソース** として流用する
 * (slide と同一 SSOT・新規発明しない)。report は A4 縦向き・縦スクロールの読み物レイアウト。
 *
 * ESM (vendor/package.json type=module)。vendored .cjs は createRequire で require。
 * CLI と import (renderReport) の両対応。決定論・fail-soft (visual 失敗は fallback、render は落ちない)。
 */

import { readFileSync, writeFileSync } from 'fs';
import { createRequire } from 'module';
import { pathToFileURL } from 'url';
import { renderMermaidFragment, mermaidInitScript } from './mermaid-render.js';

// vendored CommonJS primitives を ESM から require する (共有意匠 SSOT の流用)
const require = createRequire(import.meta.url);
const { SPEC } = require('./style-builder.cjs');
const { escapeHtml } = require('./template-engine.cjs');
const svg = require('./svg-builder.cjs');
// 構造図 10 種 (architecture / data-flow / swimlane …)。slide 側からしか呼べて
// いなかったため report では 1 つも描けなかった。schema の variant enum へ追加した
// 3 種を report からも引けるようにここで読み込む。
const struct = require('./svg-structures.cjs');
// 線幅・配色の語彙は svg-kit が正本。report engine が自前で描く SVG
// (buildNeutralComparison) も同じ語彙を使わないと、節ごとに図の grammar が変わる。
const kit = require('./svg-kit.cjs');

/**
 * 角丸 (VGCONST_003: 面は 0px・図版のみ 2px) の値を style-builder が実際に出す
 * CSS から実行時に採る。ここへ 0 / 2px を書き写すと正本が 2 つになり、slide 側だけ
 * 直した後も report は古い値で描けてしまう (見た目が変わるだけなので誰も気付けない)。
 * 採れない場合は黙って既定値へ落とさず即座に落とす。
 */
const RADIUS = (() => {
  const css = require('./style-builder.cjs').buildStyles();
  const pick = (name) => {
    const m = css.match(new RegExp('--' + name + ':\\s*([^;]+);'));
    if (!m) throw new Error(`style-builder の出力に --${name} が無い (角丸の正本が動いた)`);
    return m[1].trim();
  };
  return { surface: pick('radius'), figure: pick('radius-figure') };
})();

// reportType (§D の 4 enum) → アクセント色。読み物の視覚的アイデンティティ付与。
const REPORT_TYPE_ACCENT = {
  'internal-analysis': 'accent-blue-vivid',
  'client-proposal': 'accent-aqua-vivid',
  'tech-doc': 'accent-violet-vivid',
  learning: 'accent-yellow-vivid',
};

// svgSpec.variant (schema enum) → svg-builder.cjs のノードベース図解ビルダーへ写像。
// 単一配列引数 (items|events|circles|quadrants, opts) のビルダーはここで統一 dispatch。
// mindmap/comparison/network は多引数のため renderSvgVisual 内で個別処理。
const VARIANT_SINGLE_ARG = {
  flow: 'buildHorizontalFlow',
  stepper: 'buildVerticalFlow',
  'wave-step': 'buildSnake',
  snake: 'buildSnake',
  cycle: 'buildCycle',
  pyramid: 'buildPyramid',
  tree: 'buildHierarchy',
  org: 'buildHierarchy',
  matrix: 'buildMatrix',
  venn: 'buildVenn',
  timeline: 'buildVerticalTimeline',
  roadmap: 'buildVerticalTimeline',
  chevron: 'buildChevron',
  funnel: 'buildFunnel',
  concentric: 'buildConcentric',
  'value-stack': 'buildValueStack',
};

// svgSpec.variant → svg-structures.cjs の構造図ビルダー 10 種。VARIANT_SINGLE_ARG と違い
// 素材が items[] でなく zones[]/entities[]/tiers[] という入れ子だったり、2 引数
// (actors + messages / states + transitions / hub + spokes) だったりするので、
// 共通コア (nodes[]/edges[]/groups[]) からの射影 (project) を行ごとに持つ。
//
// project は「ビルダーへ渡す引数配列 + opts」を返すか、素材が足りなければ null を返す
// (空の枠を黙って描かせない)。第 2 引数 (links / relations / transitions …) を spec から
// 直接受け取らないのは、svgSpec が additionalProperties:false で variant/viewBox/nodes/
// edges/groups しか持てず、spec.links のような追加キーは schema 検証を通れないため。
// 関係はすべて edges[] から、入れ子はすべて groups[] + node.group から導く。
// 引数の語彙は scripts/render-diagram-golden.cjs の BUILDERS 表 (= render-slide.cjs の
// slideType 分岐と同一) に揃える。揃えないと同じビルダーが surface ごとに別物になる。
const VARIANT_STRUCT = {
  architecture: { builder: 'buildArchitecture', project: projectZones },
  'data-flow': { builder: 'buildDataFlow', project: projectStages },
  swimlane: { builder: 'buildSwimlane', project: projectLanes },
  er: { builder: 'buildEr', project: projectEntities },
  sequence: { builder: 'buildSequence', project: projectSequence },
  state: { builder: 'buildState', project: projectStates },
  'it-state': { builder: 'buildItState', project: projectItStateRows },
  medallion: { builder: 'buildMedallion', project: projectTiers },
  'high-level': { builder: 'buildHighLevel', project: projectLevels },
  'dp-integration': { builder: 'buildDpIntegration', project: projectHubSpokes },
};

// ===== 1.2.0: footnote インライン係り先アンカー (文書レベル採番) =====
// renderReport 開始時に本文中 `[^id]` 参照 ↔ footnote 実体を突合するため、id を持つ脚注を
// 文書順に連番採番したレジストリを構築する。determinism: 入力配列順に一意採番するため決定論的。
// inlineMd は非再入で単一 renderReport 呼び出し中のみこの state を読む。
let _footnoteRegistry = Object.create(null); // id -> 連番 (1..)
let _emittedFnrefs = new Set();               // back-link アンカー id の重複防止 (最初の参照のみ id 付与)

/** 全 section の body footnote block を走査し、id を持つ脚注を文書順連番でレジストリ化 */
function buildFootnoteRegistry(sections) {
  const reg = Object.create(null);
  let n = 0;
  for (const sec of Array.isArray(sections) ? sections : []) {
    const body = Array.isArray(sec && sec.body) ? sec.body : [];
    for (const b of body) {
      if (b && b.type === 'footnote' && Array.isArray(b.footnotes)) {
        for (const fn of b.footnotes) {
          if (fn && fn.id && !(fn.id in reg)) {
            n += 1;
            reg[fn.id] = n;
          }
        }
      }
    }
  }
  return reg;
}

/** theme を string|object の両方許容し正規化 (schema: kanagawa-lotus 固定) */
function themeName(theme) {
  if (!theme) return 'kanagawa-lotus';
  if (typeof theme === 'string') return theme;
  return theme.name || 'kanagawa-lotus';
}

/**
 * 共有意匠 SSOT (SPEC) から report 用 :root と読み物レイアウト CSS を生成。
 * 色/フォント/spacing の値は SPEC が唯一のソース。単位は rem/mm (縦スクロール文書)。
 */
function buildReportCss(spec = SPEC) {
  const c = spec.colors;
  const fs = spec.fontScale;
  const spacingVars = spec.spacing.map((v, i) => `  --space-${i + 1}: ${v};`).join('\n');
  return `:root {
  /* §2 インク・オン・ペーパー (VGCONST_001)。色値は style-builder の SPEC.colors だけを
     出どころにする。SPEC が持たないキーを読むと値が空のまま CSS へ出て、
     宣言ごと無効になったことに実行時も検査も気付けない。 */
  --paper: ${c.paper};
  --ink: ${c.ink};
  --paper-on-ink: ${c.paper};
  --fg-muted: ${c.inkMuted};
  --hairline: ${c.hairline};
  /* 地・文字・罫の別名。slide 側 (style-builder) と同じ名前で同じ値を指す。 */
  --bg-dark: var(--paper);
  /* --fg-dim は **値を持たない後方互換の別名**である。この濃度に値を代入して
     いるのは上の --fg-muted 1 行だけで、report 経路の CSS 規則はすべてそちらを
     直接参照するよう寄せた (本ファイル内 19 箇所)。
     以前ここには「d3-components/base.js の TOKEN_CHAINS はこの名前で解決する」と
     書いてあったが、**実際の base.js は --fg-muted を先に引き、--fg-dim は
     チェーンの後段の控えでしかない** (base.js:20 / :378 / :383)。
     つまり repo 内にこの別名を必要とする参照はもう無い。
     残してあるのは既に出力済みの report HTML が古い名前を持つ可能性のためだけで、
     base.js のチェーンから控えが落ちた時点でこの 1 行も落とせる。
     **新しい記述でこの名前を使わないこと。増える区別は 1 つも無い。** */
  --fg-dim: var(--fg-muted);
  --border: var(--hairline);
  /* §2 濃度段 (VGCONST_002)。図解の内部でだけ使う単一色相 3 段 */
  --tone-1: ${c.tone1};
  --tone-2: ${c.tone2};
  --tone-3: ${c.tone3};
  /* 旧色相名の別名。本文 CSS と生成済み report がこの名前で参照しているので名前は
     残すが、色相へ意味を割り当てる運用は廃した (強調は反転ブロックで作る)。
     --spring-violet と --fuji-gray はここから落とした。前者は --wave-blue と、
     後者は --fg-dim と**同じ値を指す別名**で、名前が 2 つある状態そのものが
     「区別がある」という誤った主張になっていた。参照側も同じ便で寄せてある。 */
  --wave-blue: var(--tone-3);
  --sakura-pink: var(--ink);
  --wave-aqua: var(--tone-2);
  --autumn-yellow: var(--tone-1);
  --accent-blue-vivid: var(--ink);
  --accent-pink-vivid: var(--ink);
  --accent-aqua-vivid: var(--ink);
  --accent-violet-vivid: var(--ink);
  --accent-yellow-vivid: var(--ink);
  /* §2 角丸 (VGCONST_003)。面は 0、図版だけ 2px。値は style-builder の出力から採る */
  --radius: ${RADIUS.surface};
  --radius-figure: ${RADIUS.figure};
  /* §2 影ゼロ (VGCONST_003)。浮きは影でなく hairline の輪郭 1 本で表す。
     --shadow-subtle はここで打ち消すのをやめ、定義と参照の両方を落とした。
     値を与えてから同じ経路で none に上書きする形は、どちらが正なのか読んで
     判定できず、意匠方針の抜け穴が 1 つ残る。 */
  --shadow-medium: none;
  /* §3 フォント (SPEC 流用) */
  --font-scale: ${fs};
  --font-base: ${spec.fonts.base};
  --font-mono: ${spec.fonts.mono};
  /* report タイポは slide の --font-scale(1.3)から分離し、本文 16-18px の読み物レンジへ固定
     (title/body 比 <=2.2)。過大な見出しと窮屈感を根治する。 */
  --fs-title: 2.05rem;      /* ~33px */
  --fs-heading: 1.5rem;     /* ~24px */
  --fs-subheading: 1.2rem;  /* ~19px */
  --fs-body: 1.0625rem;     /* ~17px (16-18px 読書レンジ) */
  --fs-small: 0.92rem;      /* ~14.7px */
${spacingVars}
  /* report ページ幅 (A4 縦・print 層の正本) */
  --report-width: 190mm;
  /* screen 読書レイアウト。パワポ的に横空間を使い切る (空白>本文 の逆転を根治) */
  /* 可読幅は「全角 40 字」を正本にする。ch は数字 0 の字幅 (= 半角) なので日本語の
     行長指定には使えない。em なら全角 1 字 = 1em で一致するため 40em とする。
     40 字は日本語組版の一般的な上限帯 (35-45) の中央で、視線の戻り距離が長すぎず、
     かつ 1 行が細切れになって文の切れ目を見失うこともない。 */
  --report-measure: 40em;      /* プレーン段落のみの可読幅。グラフィカル block は全幅で横を使う */
  --report-sidebar-w: 16rem;   /* sticky sidebar TOC 幅 */
  /* sidebar 16rem + gap 3rem + 本文 40em(17px 換算 680px) ≒ 984px。
     page-max はここへ図解が横へ伸びる余地を足した値。広げすぎると本文右の
     空白だけが増えるので、図解の実効幅 (本文幅の 1.5 倍程度) で頭打ちにする。 */
  --report-page-max: 1160px;   /* sidebar + 本文の実効利用幅 (空白>本文 の逆転防止) */
  --report-topbar-h: 3.25rem;  /* 追従ヘッダーの高さ。sticky 要素の top はこれを基準に揃える */
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 16px; }
body {
  background: var(--bg-dark);
  color: var(--fg);
  font-family: var(--font-base);
  font-size: var(--fs-body);
  line-height: 1.75;
  -webkit-font-smoothing: antialiased;
}
html { scroll-behavior: smooth; }

/* ===== 追従ヘッダー (1.4.0) =====
   スクロールで文書冒頭の .report-header が視界から消えると「いま何の文書を読んで
   いるか」の手掛かりが失われる。細い帯を常時残し、文書名と現在節を出す。
   帯は薄くする (3.25rem) — 追従 UI が縦を食うほど本文の可視行数が減るため。 */
.report-topbar {
  position: sticky; top: 0; z-index: 30;
  height: var(--report-topbar-h);
  display: flex; align-items: center; gap: var(--space-3, 0.75rem);
  padding: 0 var(--space-6, 2rem);
  background: var(--paper);
  border-bottom: 1px solid var(--hairline);
}
.report-topbar__title {
  font-size: var(--fs-small); font-weight: 700; color: var(--fg);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 45%;
}
.report-topbar__sep { color: var(--fg-muted); flex: none; }
.report-topbar__here {
  font-size: var(--fs-small); color: var(--fg-muted); font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0;
}
/* 読了進捗。位置の手掛かりを 1px の帯で与える (面積を食わずに全体の何割かが分かる) */
.report-topbar__progress {
  position: absolute; left: 0; bottom: -1px; height: 2px; width: 0;
  background: var(--report-accent, var(--accent-blue-vivid));
}
@media print { .report-topbar { display: none !important; } }

/* ===== 読み物レイアウト (screen: sidebar+可読幅 2 カラム / print: A4 縦 190mm 温存) ===== */
.report-layout {
  display: grid;
  grid-template-columns: var(--report-sidebar-w) minmax(0, 1fr);
  gap: var(--space-7, 3rem);
  max-width: var(--report-page-max);
  margin: 0 auto;
  padding: 0 var(--space-6, 2rem);
}
.report-layout--no-toc { grid-template-columns: 1fr; }
.report-layout--no-toc .report { margin: 0 auto; }
.report-sidebar { min-width: 0; }
.report {
  max-width: none;
  min-width: 0;
  margin: 0;
  padding: var(--space-7, 3rem) 0 var(--space-8, 4rem);
}
/* プレーン段落・リストのみ可読幅に制限。グラフィカル block (narrative/stats/visual/table/keypoint 等) は
   全幅でパワポ的に横空間を使う (窮屈=右側の空白過多を根治)。 */
.report-section > p,
.report-section > ul,
.report-section > ol { max-width: var(--report-measure); }
/* 文 (句点まで) を 1 つの行ブロックにする。
   句点をまたいで次の文が行の途中から始まると、どこで話題が切り替わったかを
   読者が字面から拾い直すことになる。文頭が必ず行頭に来れば、視線を左端へ
   戻した瞬間に次の文の始まりだと分かる。
   40 字を超える長文はそのまま自然折り返しに委ねる (<br> だと折返しと二重の
   改行が起きて段落が縦に間延びする)。 */
.report-sent { display: block; }
.report-sent + .report-sent { margin-top: 0.15em; }
/* アンカー遷移時、節見出しが追従ヘッダーの下に潜らないよう帯のぶん送る */
.report-section[id] { scroll-margin-top: calc(var(--report-topbar-h) + var(--space-4, 1rem)); }
.report-header { margin-bottom: var(--space-7, 3rem); border-bottom: 3px solid var(--report-accent, var(--accent-blue-vivid)); padding-bottom: var(--space-4, 1rem); }
.report-title { font-size: var(--fs-title); font-weight: 800; line-height: 1.25; color: var(--fg); }
.report-subtitle { margin-top: var(--space-2, 0.5rem); font-size: var(--fs-subheading); color: var(--fg-muted); font-weight: 500; }
.report-keymessage { margin-top: var(--space-3, 0.75rem); font-size: var(--fs-body); color: var(--fg); font-weight: 500; border-left: 0.3rem solid var(--report-accent, var(--accent-blue-vivid)); padding-left: var(--space-3, 0.75rem); }
.report-meta { margin-top: var(--space-3, 0.75rem); font-size: var(--fs-small); color: var(--fg-muted); display: flex; flex-wrap: wrap; gap: var(--space-4, 1rem); align-items: center; }
.report-meta .report-type-badge {
  display: inline-block; padding: 0.2rem 0.7rem; border-radius: var(--radius);
  background: var(--report-accent, var(--accent-blue-vivid)); color: var(--paper-on-ink); font-weight: 700;
}

/* ===== section ===== */
.report-section { margin-bottom: var(--space-8, 4rem); }
.report-section > h2 {
  font-size: var(--fs-heading); font-weight: 700; line-height: 1.35;
  color: var(--fg);
  padding-left: var(--space-3, 0.75rem);
  border-left: 0.35rem solid var(--section-accent, var(--accent-blue-vivid));
  margin-bottom: var(--space-4, 1rem);
}
.report-section p { font-size: var(--fs-body); margin-bottom: var(--space-4, 1rem); }
.report-section strong { color: var(--section-accent, var(--accent-blue-vivid)); font-weight: 700; }
.report-section code { font-family: var(--font-mono); font-size: 0.92em; background: var(--hairline); padding: 0.1em 0.35em; border-radius: var(--radius); }
.report-section a { color: var(--accent-blue-vivid); }
.report-section ul { margin: 0 0 var(--space-4, 1rem) var(--space-5, 1.5rem); }
.report-section li { font-size: var(--fs-body); margin-bottom: var(--space-2, 0.5rem); }

/* ===== callouts (注記/警告/ヒント) ===== */
/* 吹き出し(左バー+ベタ塗り)を廃し、余白リッチのフラットカードへ。トーンは上端の細アクセント線で示す。 */
.report-callout { display: block; margin: var(--space-5, 1.5rem) 0; padding: var(--space-4, 1rem) var(--space-5, 1.5rem); border-radius: var(--radius); font-size: var(--fs-small); background: var(--paper); border: 1px solid var(--hairline); border-top: 3px solid var(--accent-blue-vivid); }
.report-callout--warning, .report-callout--caution { border-top-color: var(--accent-pink-vivid); }
.report-callout--tip { border-top-color: var(--accent-yellow-vivid); }

/* ===== 本質図解 (essence diagram) — 各実質節の論理構造を一目化する主役ブロック ===== */
/* essence-visual: 「小さく中央浮遊の装飾」→「本文幅いっぱいの枠付き figure (読解の主役)」へ。
   screen は本文可読幅を満たし、print は @media print 側で A4 幅 (--report-width) にキャップ。 */
.report-visual {
  margin: var(--space-7, 3rem) 0;
  padding: var(--space-6, 2rem);
  text-align: center;
  background: var(--paper);
  border: 1px solid var(--hairline);
  /* 図版の枠。VGCONST_003 の 2px 例外に当たる (面でなく図版の輪郭) */
  border-radius: var(--radius-figure);
}
.report-visual svg { width: 100%; max-width: 100%; height: auto; display: block; margin: 0 auto; }
.report-visual img { max-width: 100%; height: auto; border-radius: var(--radius-figure); box-shadow: var(--shadow-medium); object-position: var(--focal, 50% 50%); }
.report-visual figcaption { margin-top: var(--space-3, 0.75rem); font-size: var(--fs-small); color: var(--fg-muted); text-align: center; }
.report-visual--mermaid pre.mermaid {
  display: block; text-align: left; font-family: var(--font-mono); font-size: var(--fs-small);
  background: var(--paper); border: 1px solid var(--hairline);
  border-radius: var(--radius-figure); padding: var(--space-3, 0.75rem); overflow-x: auto; white-space: pre;
}
.report-visual--image .composite-overlay { list-style: none; margin: var(--space-2, 0.5rem) 0 0; padding: 0; font-size: var(--fs-small); color: var(--fg-muted); }

.report-footer { margin-top: var(--space-8, 4rem); padding-top: var(--space-3, 0.75rem); border-top: 1px solid var(--hairline); font-size: var(--fs-small); color: var(--fg-muted); text-align: center; }

/* ===== 印刷 (A4 縦・読み物・screen 二層の print 側 = 従来 190mm 契約温存) ===== */
@page { size: A4 portrait; margin: 18mm; }
@media print {
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
  body { background: var(--paper); }
  /* sidebar grid を解除し従来の一段組へ (sticky TOC 非適用・.report は A4 幅) */
  .report-layout { display: block; max-width: none; padding: 0; }
  .report-sidebar { display: none !important; }
  .report-toc a.is-active { color: inherit; font-weight: inherit; } /* scrollspy ハイライト無効 (print) */
  .report { max-width: 100%; margin: 0 auto; padding: 0; }
  .report-section { break-inside: avoid-page; }
  .report-visual { break-inside: avoid; }
}
/* ===== 狭画面 (max-width: 900px・タブレット縦含む): 折り畳み可能な sticky TOC を維持 ===== */
@media screen and (max-width: 900px) {
  .report-layout { display: block; max-width: 46rem; padding: 0 var(--space-4, 1rem); }
  /* 狭画面でも追従は残す。static に落とすと、読み進めた先から他の節へ移動する
     手段が無くなり (先頭へ戻る操作が要る)、読み物として辿れなくなる。
     代わりに畳めるようにし、開いていても画面の 45% までに抑える。
     背景を不透明にするのは、本文の上に重なったとき文字が透けて二重に見えるため。 */
  /* sticky は親の box の中でしか動かない。.report-sidebar は内容ぶんの高さしか
     持たないので、そのままだと移動できる余地がゼロで即座に流れ去る。
     display:contents で器を外し、文書全体の高さを持つ .report-layout を
     直接の親にする (grid の配置には関与しない狭画面だからできる)。 */
  .report-sidebar { display: contents; }
  .report-toc--sidebar {
    position: sticky; top: var(--report-topbar-h); z-index: 20;
    max-height: 45vh; overflow-y: auto; margin: 0 0 var(--space-5, 1.5rem);
    background: var(--bg-dark); border-color: var(--hairline);
  }
  .report-toc--sidebar ol { columns: 2; }
  .report { max-width: none; margin: 0 auto; padding-top: var(--space-6, 2rem); }
}
/* ===== 1.1.0: 構造化本文ブロック ===== */
/* section 番号 (01, 02 …) — h2 の data-secnum を CSS ::before で前置 (h2 テキスト本体は見出しのみに保つ) */
.report-section > h2[data-secnum]::before {
  content: attr(data-secnum); display: inline-block; min-width: 2.2em; margin-right: 0.6rem;
  color: var(--section-accent, var(--accent-blue-vivid)); font-weight: 800;
  font-variant-numeric: tabular-nums; opacity: 0.85;
}
/* 節内論理展開リード帯 (本質課題→解決→活用) */
/* 節の論理アーク(本質課題→解決→活用): 外枠の吹き出しを廃し、余白の大きい独立 3 カードのパワポ図解へ。
   各カードは白地・上端アクセント・大きめ padding で「文字敷き詰め」から「余白のある図解」へ転換。 */
.report-narrative {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--space-5, 1.5rem); margin: var(--space-5,1.5rem) 0 var(--space-6, 2rem);
  padding: 0; background: none; border: 0;
}
.report-narrative__cell {
  display: flex; flex-direction: column; gap: 0.6rem;
  background: var(--paper); border: 1px solid var(--hairline); border-radius: var(--radius);
  border-top: 3px solid var(--section-accent, var(--accent-blue-vivid));
  padding: var(--space-5,1.5rem);
}
.report-narrative__label {
  font-size: var(--fs-small); font-weight: 800; letter-spacing: 0.03em;
  color: var(--section-accent, var(--accent-blue-vivid));
}
.report-narrative__cell--approach .report-narrative__label { color: var(--accent-aqua-vivid); }
.report-narrative__cell--leverage .report-narrative__label { color: var(--accent-violet-vivid); }
.report-narrative__text { font-size: var(--fs-small); line-height: 1.7; color: var(--fg); }
/* 節内小見出し */
.report-subheading { font-size: var(--fs-subheading); font-weight: 700; margin: var(--space-5,1.5rem) 0 var(--space-3,0.75rem); color: var(--fg); }
h4.report-subheading { font-size: calc(1.12rem * var(--font-scale)); }
/* 番号/箇条書きリスト */
.report-list { margin: 0 0 var(--space-4,1rem) var(--space-5,1.5rem); }
.report-list--ol { list-style: decimal; }
.report-list--ul { list-style: disc; }
.report-list li { font-size: var(--fs-body); margin-bottom: var(--space-2,0.5rem); }
/* 要点の色付きハイライト (inline ==...==) — 1.2.0: 色に依存しない第2チャネル (font-weight + underline) を必須併存し色覚非依存 */
mark.report-hl {
  background: var(--ink);
  color: var(--paper-on-ink); padding: 0.05em 0.28em; border-radius: var(--radius); font-weight: 700;
  text-decoration: underline; text-decoration-thickness: 0.11em; text-underline-offset: 0.18em;
  text-decoration-color: var(--paper-on-ink);
  box-decoration-break: clone; -webkit-box-decoration-break: clone;
}
/* markdown 表 (<br> で潰さない) */
.report-table-wrap { margin: var(--space-5,1.5rem) 0; overflow-x: auto; }
.report-table { width: 100%; border-collapse: collapse; font-size: var(--fs-small); background: var(--paper); border-radius: var(--radius); overflow: hidden; }
.report-table th, .report-table td { padding: 0.55rem 0.8rem; text-align: left; border-bottom: 1px solid var(--hairline); vertical-align: top; }
.report-table thead th { background: var(--ink); color: var(--paper-on-ink); font-weight: 700; }
.report-table tbody tr:nth-child(even) { background: transparent; }
.report-table-wrap figcaption, .report-code-wrap figcaption { margin-top: 0.4rem; font-size: var(--fs-small); color: var(--fg-muted); font-weight: 500; }
/* コードブロック (ダーク・ターミナル風) */
.report-code-wrap { position: relative; margin: var(--space-5,1.5rem) 0; }
.report-code__lang { position: absolute; top: 0.5rem; right: 0.7rem; font-size: 0.72rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--hairline); font-family: var(--font-mono); z-index: 1; }
pre.report-code { background: var(--ink); color: var(--paper-on-ink); font-family: var(--font-mono); font-size: 0.86rem; line-height: 1.6; padding: var(--space-4,1rem); border-radius: var(--radius-figure); overflow-x: auto; box-shadow: var(--shadow-medium); }
pre.report-code code { background: none; padding: 0; color: inherit; font-size: inherit; white-space: pre; }
/* キーポイント強調ボックス (色付き・トーン別) */
/* キーポイント: 吹き出しをやめ、余白の大きい白カード + 上端アクセント + タイトル前の色ドット。 */
.report-keypoint { margin: var(--space-5,1.5rem) 0; padding: var(--space-5,1.5rem); border-radius: var(--radius); background: var(--paper); border: 1px solid var(--hairline); border-top: 3px solid var(--accent-pink-vivid); --kp-accent: var(--accent-pink-vivid); }
.report-keypoint--accent   { border-top-color: var(--accent-blue-vivid);   --kp-accent: var(--accent-blue-vivid); }
.report-keypoint--positive { border-top-color: var(--accent-aqua-vivid);   --kp-accent: var(--accent-aqua-vivid); }
.report-keypoint--caution  { border-top-color: var(--accent-yellow-vivid); --kp-accent: var(--accent-yellow-vivid); }
.report-keypoint--neutral  { border-top-color: var(--fg-muted);           --kp-accent: var(--fg-muted); }
.report-keypoint__title { font-weight: 800; margin-bottom: 0.5rem; color: var(--fg); display: flex; align-items: center; gap: 0.5rem; }
.report-keypoint__title::before { content: ""; width: 0.6rem; height: 0.6rem; border-radius: var(--radius); background: var(--kp-accent, var(--accent-pink-vivid)); flex: none; }
.report-keypoint__body { font-size: var(--fs-body); line-height: 1.75; }
/* 統計タイル */
.report-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px,1fr)); gap: var(--space-3,0.75rem); margin: var(--space-5,1.5rem) 0; }
.report-stat { display: flex; flex-direction: column; gap: 0.2rem; padding: var(--space-3,0.75rem) var(--space-4,1rem); border-radius: var(--radius); background: var(--paper); border: 1px solid var(--hairline); }
.report-stat__label { font-size: var(--fs-small); color: var(--fg-muted); font-weight: 600; }
.report-stat__value { font-size: calc(1.9rem * var(--font-scale)); font-weight: 800; line-height: 1.1; color: var(--section-accent, var(--accent-blue-vivid)); font-variant-numeric: tabular-nums; }
.report-stat__note { font-size: 0.78rem; color: var(--fg-muted); }
.report-stat__trend { font-size: 0.9rem; margin-left: 0.2rem; }
.report-stat__trend--up { color: var(--accent-aqua-vivid); }
.report-stat__trend--down { color: var(--accent-pink-vivid); }
.report-stat__trend--flat { color: var(--fg-muted); }
/* 引用ブロック */
.report-quote { margin: var(--space-4,1rem) 0; padding: var(--space-3,0.75rem) var(--space-5,1.5rem); border-left: 0.3rem solid var(--fg-muted); color: var(--fg-muted); font-style: italic; background: var(--paper); border-radius: var(--radius); }
/* callout に title を許容 */
.report-callout__title { color: var(--fg); }
/* 意味的配置: 本文と図の 2 カラム分割 */
.report-grid--2col { display: grid; grid-template-columns: 1.1fr 1fr; gap: var(--space-5,1.5rem); align-items: start; }
/* 2 列でも本文の可読幅は効かせる。.report-section > p の直下子セレクタは
   prose 用の器に包んだ時点で外れるため、ここで別途指定する。 */
.report-grid__prose > p,
.report-grid__prose > ul,
.report-grid__prose > ol,
.report-keypoint__body,
.report-callout,
.report-deflist dd { max-width: var(--report-measure); }
.report-grid__visual .report-visual { margin: 0; }
@media (max-width: 720px) { .report-grid--2col { grid-template-columns: 1fr; } }
/* section 強調度 (placement.emphasis) */
.report-section[data-emphasis="highlight"] { padding: var(--space-4,1rem) var(--space-4,1rem); border-radius: var(--radius); background: var(--paper); }
.report-section[data-emphasis="muted"] { opacity: 0.82; }
/* 目次 (TOC) */
.report-toc { margin: 0 0 var(--space-7,3rem); padding: var(--space-4,1rem) var(--space-5,1.5rem); border-radius: var(--radius); background: var(--paper); border: 1px solid var(--hairline); }
.report-toc__title { font-weight: 800; font-size: var(--fs-small); letter-spacing: 0.08em; color: var(--fg-muted); margin-bottom: 0.5rem; cursor: pointer; list-style: none; }
.report-toc__title::-webkit-details-marker { display: none; }
/* 開閉の向きを ▾/▸ で示す。summary の既定マーカーを消しているので、
   代わりの手掛かりがないと畳めることに気付けない。 */
.report-toc__title::after { content: '▾'; margin-left: 0.5em; opacity: 0.7; }
.report-toc__box:not([open]) .report-toc__title::after { content: '▸'; }
.report-toc ol { list-style: none; margin: 0; padding: 0; columns: 2; column-gap: var(--space-6,2rem); }
.report-toc li { margin-bottom: 0.35rem; break-inside: avoid; }
.report-toc a { color: var(--fg); text-decoration: none; font-size: var(--fs-small); }
.report-toc a:hover { color: var(--report-accent, var(--accent-blue-vivid)); }
.report-toc__num { display: inline-block; min-width: 1.9em; color: var(--report-accent, var(--accent-blue-vivid)); font-weight: 700; font-variant-numeric: tabular-nums; }
/* report-uiux: sticky sidebar TOC (スクロール追従・scrollspy 現在位置ハイライト) */
.report-toc--sidebar {
  /* top は追従ヘッダーの直下へ揃える。0 にすると帯の下へ潜り、見出し 1 行ぶんが
     常に隠れて「今どこ」の項目が読めなくなる。
     max-height はビューポートから帯と上下余白を引いた残り。これを指定しないと
     項目数の多い文書で TOC が画面より高くなり、下端の節へ飛べなくなる。 */
  position: sticky; top: calc(var(--report-topbar-h) + var(--space-4, 1rem));
  max-height: calc(100vh - var(--report-topbar-h) - var(--space-5, 1.5rem) * 2);
  overflow-y: auto; margin: var(--space-6, 2rem) 0 0;
}
.report-toc--sidebar ol { columns: 1; }
.report-toc--sidebar li { margin-bottom: 0.45rem; }
.report-toc a.is-active { color: var(--report-accent, var(--accent-blue-vivid)); font-weight: 700; }
@media print { pre.report-code { box-shadow: none; } .report-toc ol { columns: 2; } }

/* ===== 1.2.0: 文書アーク / 節間接続 / 文書メタ / 新 block 型 ===== */
/* 文書全体の通し筋 (throughLine) — 導入部のアーク帯 */
.report-throughline {
  margin: var(--space-5,1.5rem) 0 var(--space-7, 3rem); padding: var(--space-5, 1.5rem) var(--space-6, 2rem);
  border-radius: var(--radius); font-size: var(--fs-body); line-height: 1.8; color: var(--fg);
  background: var(--paper); border: 1px solid var(--hairline);
  border-top: 3px solid var(--report-accent, var(--accent-blue-vivid));
  display: flex; gap: var(--space-4,1rem); align-items: baseline; flex-wrap: wrap;
}
.report-throughline__label { font-size: var(--fs-small); font-weight: 800; letter-spacing: 0.05em; color: var(--report-accent, var(--accent-blue-vivid)); white-space: nowrap; }
/* part 単位 sub-arc (大規模文書の道標) */
.report-throughline-parts { list-style: none; margin: 0 0 var(--space-6, 2rem); padding: 0; display: grid; gap: 0.4rem; counter-reset: tlpart; }
.report-throughline__part { display: flex; gap: 0.7rem; align-items: baseline; padding: 0.4rem 0.7rem; border-left: 0.2rem solid var(--ink); background: var(--paper); border-radius: var(--radius); }
.report-throughline__part-title { font-size: var(--fs-small); font-weight: 800; color: var(--report-accent, var(--accent-blue-vivid)); white-space: nowrap; }
.report-throughline__part-arc { font-size: var(--fs-small); line-height: 1.6; color: var(--fg); }
/* 文書メタ (version/updatedDate/readingTime) は report-meta の span を流用 */
/* 節末の次節への橋渡し (transition) */
.report-transition {
  margin: var(--space-4, 1rem) 0 0; padding: 0.5rem 0 0 var(--space-4, 1rem);
  font-size: var(--fs-small); color: var(--fg-muted); font-style: italic;
  border-left: 0.2rem solid var(--hairline);
}
.report-transition::before { content: "→ "; font-weight: 700; font-style: normal; color: var(--section-accent, var(--accent-blue-vivid)); }
/* 定義リスト (term ↔ definition) */
.report-deflist { margin: var(--space-4,1rem) 0; display: grid; grid-template-columns: minmax(8rem, 14rem) 1fr; gap: 0.4rem var(--space-4,1rem); }
.report-deflist dt { font-weight: 800; color: var(--section-accent, var(--accent-blue-vivid)); }
.report-deflist dd { margin: 0; font-size: var(--fs-body); line-height: 1.75; }
@media (max-width: 720px) { .report-deflist { grid-template-columns: 1fr; } .report-deflist dd { margin-bottom: 0.5rem; } }
/* 脚注引用 (footnote + citation)。marker が採番を担うため ol の decimal は出さない (二重採番回避) */
.report-footnotes { margin: var(--space-5,1.5rem) 0 0; padding-top: var(--space-3,0.75rem); border-top: 1px solid var(--hairline); font-size: var(--fs-small); color: var(--fg-muted); }
.report-footnotes ol { list-style: none; margin: 0; padding: 0; }
.report-footnotes li { margin-bottom: 0.35rem; line-height: 1.6; }
.report-footnotes li:target { background: var(--hairline); border-radius: var(--radius); }
.report-footnotes__marker { font-weight: 700; color: var(--section-accent, var(--accent-blue-vivid)); font-variant-numeric: tabular-nums; }
.report-footnotes__back { margin-left: 0.4rem; text-decoration: none; color: var(--section-accent, var(--accent-blue-vivid)); }
.report-footnotes cite { display: block; font-style: normal; font-size: 0.8rem; color: var(--fg-muted); margin-top: 0.1rem; }
/* 本文中の脚注参照 (上付き番号リンク) */
sup.report-fnref { font-size: 0.7em; line-height: 0; }
sup.report-fnref a { text-decoration: none; color: var(--section-accent, var(--accent-blue-vivid)); font-weight: 700; }
sup.report-fnref a:hover { text-decoration: underline; }
/* タスクリスト (次アクション・チェックボックス) */
.report-tasklist { list-style: none; margin: var(--space-4,1rem) 0; padding: 0; }
.report-tasklist li { display: flex; gap: 0.55rem; align-items: baseline; font-size: var(--fs-body); margin-bottom: 0.5rem; }
.report-tasklist__box { font-family: var(--font-mono); font-weight: 800; color: var(--section-accent, var(--accent-blue-vivid)); white-space: nowrap; }
.report-tasklist__box--done { color: var(--accent-aqua-vivid); }
.report-tasklist li.is-done .report-tasklist__text { color: var(--fg-muted); text-decoration: line-through; }
.report-tasklist__owner { font-size: var(--fs-small); color: var(--fg-muted); margin-left: 0.3rem; }
.visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}`;
}

/**
 * 最小 Markdown → HTML (決定論・安全)。
 * 先に escapeHtml して注入を防いだ上で、安全なパターンのみ再装飾する。
 * ブロック配列の各要素を段落 or 箇条書きへ変換。
 */
function renderParagraphs(paragraphs) {
  const blocks = Array.isArray(paragraphs) ? paragraphs : paragraphs ? [String(paragraphs)] : [];
  return blocks
    .map((raw) => {
      const block = String(raw == null ? '' : raw);
      const lines = block.split('\n').map((l) => l.trimEnd());
      const isList = lines.length > 0 && lines.every((l) => l.trim() === '' || /^\s*[-*]\s+/.test(l));
      if (isList && lines.some((l) => l.trim() !== '')) {
        const items = lines
          .filter((l) => l.trim() !== '')
          .map((l) => `    <li>${inlineMd(l.replace(/^\s*[-*]\s+/, ''))}</li>`)
          .join('\n');
        return `  <ul>\n${items}\n  </ul>`;
      }
      // 段落は文ごとの行ブロックへ組む。.report-sent は display:block なので、
      // その直後に <br> を置くと空行が 1 つ余分に生まれる (行の文数で段落の
      // 縦間隔が変わる)。span を返した行の後ろでは <br> を落とす。
      const rendered = lines.map((l) => {
        const html = renderSentenceHtml(l);
        return { html, block: html.indexOf('<span class="report-sent">') === 0 };
      });
      const html = rendered
        .map((r, i) => {
          if (i === rendered.length - 1) return r.html;
          return r.block || rendered[i + 1].block ? r.html : `${r.html}<br>\n    `;
        })
        .join('');
      return `  <p>${html}</p>`;
    })
    .join('\n');
}

/**
 * 段落テキストを文の配列へ分割する。
 * 分割は inlineMd の「前」、まだ生テキストの段階で行う。装飾後の HTML を割ると
 * <strong> や <a> をまたいで切ってしまい、閉じタグを失った断片ができる。
 *
 * 戻り値は文の配列 (分割しない場合は要素 1 つ)。空文字は含めない。
 */
function splitSentences(text) {
  const s = String(text == null ? '' : text);
  if (!s.trim()) return [];

  // 括弧の内側の句点では切らない。「〜だ。」と述べた、のような引用や、
  // (〜する。ただし〜) のような補足を途中で断ち切ると、係り先を失う。
  // 対応表は開き→閉じ。ネストは深さで数え、深さ 0 のときだけ文末を認める。
  // 開きと閉じが同じ字 (" や ') は入れない。深さで数える方式では開きとして
  // 数え続け、以降その段落は永久に「括弧の内側」になって分割が止まる。
  // 対を持つ引用符 (“ ” 〝 〟) だけを扱う。
  const OPEN = {
    '「': '」', '『': '』', '（': '）', '(': ')', '【': '】', '〈': '〉', '《': '》',
    '“': '”', '〝': '〟',
  };
  const CLOSE = new Set(Object.values(OPEN));
  // 文末記号の直後に続くとき、前の文へ含める字。閉じ括弧・閉じ引用符・
  // 連続する終止符 (「本当に!?」) がこれに当たる。
  const TRAILING = new Set([...CLOSE, '。', '！', '？', '!', '?', '」', '』', '）', ')']);

  // markdown 記法の内側でも切らない。**強調です。次も強調** を割ると、
  // 断片ごとに inlineMd を通したとき ** が対にならず記号が生のまま読者へ出る。
  // 開きと閉じが同じ綴りなので深さでなく開閉のトグルで数える。
  const TOGGLES = ['**', '==', '__', '`'];

  const out = [];
  let buf = '';
  let depth = 0;
  const openToggles = new Set();
  let linkDepth = 0;   // [label](url) の label 内
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    const tog = TOGGLES.find((t) => s.startsWith(t, i));
    if (tog) {
      buf += tog;
      if (openToggles.has(tog)) openToggles.delete(tog);
      else openToggles.add(tog);
      i += tog.length - 1;
      continue;
    }
    buf += ch;
    if (ch === '[') { linkDepth++; continue; }
    if (ch === ']' && linkDepth > 0) { linkDepth--; continue; }
    if (OPEN[ch]) { depth++; continue; }
    if (CLOSE.has(ch) && depth > 0) { depth--; continue; }
    if (depth > 0 || linkDepth > 0 || openToggles.size) continue;

    // 半角 . は文末として扱わない。Node.js / 1.5倍 / e.g. のような
    // 語中の点と区別する術が無く、誤って切ると語が割れる。日本語の
    // 文書として組む以上、句点は全角の 。 に統一されている前提を取る。
    if (ch !== '。' && ch !== '！' && ch !== '？' && ch !== '!' && ch !== '?') continue;

    // 終止符が続く間は前の文へ吸わせる (。」 や !? を割らない)
    while (i + 1 < s.length && TRAILING.has(s[i + 1])) {
      buf += s[i + 1];
      i++;
    }
    out.push(buf);
    buf = '';
  }
  if (buf.trim()) out.push(buf);

  // 前後の空白は行ブロックにすると行頭・行末の余白として見えてしまう
  return out.map((t) => t.trim()).filter(Boolean);
}

/**
 * 段落の中身を「文ごとの行ブロック」へ組む。
 * 文が 1 つしかない段落は包まない (span を足しても表示は変わらず、DOM だけ増える)。
 */
function renderSentenceHtml(text) {
  const parts = splitSentences(text);
  if (parts.length <= 1) return inlineMd(text || '');
  return parts.map((s) => `<span class="report-sent">${inlineMd(s)}</span>`).join('');
}

/** インライン装飾 (escape 後の安全な文字列に対してのみ適用) */
function inlineMd(text) {
  let s = escapeHtml(text);
  // [^id] footnote 参照 → 上付き番号リンク (id がレジストリに在るときのみ・無ければ字面温存)。
  // link 記法 [label](url) より先に処理し、footnote ref を確実に消費する。
  s = s.replace(/\[\^([a-z0-9][a-z0-9-]*)\]/gi, (m, id) => {
    const key = id.toLowerCase();
    const num = _footnoteRegistry[key];
    if (!num) return m;
    let refId = '';
    if (!_emittedFnrefs.has(key)) {
      _emittedFnrefs.add(key);
      refId = ` id="fnref-${escapeHtml(key)}"`;
    }
    return `<sup class="report-fnref"${refId}><a href="#fn-${escapeHtml(key)}">[${num}]</a></sup>`;
  });
  // [label](url) → <a> (url は http/https/相対のみ許可)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/[^\s)]*|[^\s):]+)\)/g, '<a href="$2">$1</a>');
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  // ==要点== → 色付きハイライト (1.1.0・要点の色付き強調)。** より先に処理し衝突を避ける
  s = s.replace(/==([^=\n]+)==/g, '<mark class="report-hl">$1</mark>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  return s;
}

/**
 * visual (schema §visual: {kind, spec, caption, alt, rationale}) → HTML 片。
 * caption/alt は visual 直下から読む (spec 内ではない)。例外は fallback へ (render は落ちない)。
 * @returns {{ html: string, usesMermaid: boolean }}
 */
function renderVisual(visual, counters) {
  if (!visual || !visual.kind || visual.kind === 'none') return { html: '', usesMermaid: false };
  const spec = visual.spec || {};
  let caption = visual.caption || '';
  // 図表番号を自動付与。caption の有無で採番したりしなかったりすると、
  // 番号付きの図と無番号の図が交互に現れて本文から参照できなくなる。
  // caption が無い図にも番号だけは振る。
  if (counters) {
    counters.fig += 1;
    caption = caption ? `図${counters.fig}. ${caption}` : `図${counters.fig}.`;
  }
  const alt = visual.alt || '';
  try {
    if (visual.kind === 'mermaid') {
      const def = spec.definition || '';
      return { html: renderMermaidFragment(def, { caption, ariaLabel: alt || spec.diagramType }), usesMermaid: true };
    }
    if (visual.kind === 'codex-image') {
      return { html: renderCodexImage(spec, { caption, alt }), usesMermaid: false };
    }
    if (visual.kind === 'svg') {
      return { html: renderSvgVisual(spec, { caption, alt }), usesMermaid: false };
    }
  } catch (e) {
    return { html: fallbackVisual(`ビジュアル生成に失敗: ${e.message}`, caption), usesMermaid: false };
  }
  return { html: '', usesMermaid: false };
}

/** diagramNode[] → svg-builder が食う item 配列に射影 (label/subtext を保持) */
function nodesToItems(nodes) {
  const arr = Array.isArray(nodes) ? nodes : [];
  return arr.map((n, i) => {
    if (n == null) return { label: '', number: i + 1 };
    if (typeof n === 'string') return { label: n, number: i + 1 };
    return { label: n.label || '', desc: n.subtext || '', number: i + 1, date: n.subtext || '' };
  });
}

/* ===== 構造図 (svg-structures.cjs) 用の射影 =====
 * report の svgSpec は nodes[]/edges[]/groups[] しか持たない (additionalProperties:false)。
 * 構造図は入れ子の素材や 2 引数を取るので、共通コアを次の 2 つの読み替えで写す:
 *   - groups[] = 入れ子の外側 (ゾーン / レーン / 実体 / 層 / 段)、node.group がその所属
 *   - edges[]  = 関係 (接続 / 関連 / メッセージ / 遷移 / 昇格 / 向き)
 * 素材が足りないときは null を返し、呼び側に「未対応」ではなく「素材が足りない」と
 * 分かる形で落とさせる (空図を黙って出さない)。
 * 返り値は { args: ビルダー引数の配列, opts: 追加オプション }。
 */

/** groups[] → architecture の zones[]{label, nodes[]}。edges[] は接続線 (links) になる */
function projectZones(spec) {
  const nodes = Array.isArray(spec.nodes) ? spec.nodes.filter(Boolean) : [];
  const groups = Array.isArray(spec.groups) ? spec.groups.filter(Boolean) : [];
  if (!nodes.length) return null;
  const zones = groups.length
    ? groups.map((g) => ({
      label: g.label || g.id || '',
      nodes: nodes.filter((n) => n && n.group === g.id).map((n) => ({ label: n.label || '', sublabel: n.subtext || '' })),
    })).filter((z) => z.nodes.length)
    : [{ label: '', nodes: nodes.map((n) => ({ label: (n && n.label) || '', sublabel: (n && n.subtext) || '' })) }];
  if (!zones.length) return null;
  // links を渡さないと buildArchitecture は「隣接ゾーンの先頭ノードを鎖状につなぐ」
  // 既定へ落ちる。edges[] を書いた読者の意図はそこに無いので、あるときは必ず渡す。
  const links = edgesByName(spec, nodes, (e) => ({
    dashed: e.kind === 'dashed',
    external: e.emphasis === 'highlight',
  }));
  return { args: [zones], opts: links.length ? { links } : {} };
}

/** nodes[] → data-flow の stages[]{label, sublabel, via}。via は edges[] のラベルから拾う */
function projectStages(spec) {
  const nodes = Array.isArray(spec.nodes) ? spec.nodes.filter(Boolean) : [];
  if (!nodes.length) return null;
  const edges = Array.isArray(spec.edges) ? spec.edges.filter(Boolean) : [];
  const stages = nodes.map((n, i) => {
    const next = nodes[i + 1];
    const e = next ? edges.find((x) => x && x.from === n.id && x.to === next.id) : null;
    return { label: n.label || '', sublabel: n.subtext || '', via: (e && e.label) || '' };
  });
  return { args: [stages], opts: {} };
}

/** groups[] → swimlane の lanes[]{label, steps[]}。group がレーン、所属 node が工程 */
function projectLanes(spec) {
  const nodes = Array.isArray(spec.nodes) ? spec.nodes.filter(Boolean) : [];
  const groups = Array.isArray(spec.groups) ? spec.groups.filter(Boolean) : [];
  if (!nodes.length || !groups.length) return null;
  const lanes = groups.map((g) => ({
    label: g.label || g.id || '',
    steps: nodes.filter((n) => n && n.group === g.id)
      .map((n, i) => ({ id: n.id, label: n.label || '', sublabel: n.subtext || '', step: i })),
  })).filter((l) => l.steps.length);
  if (!lanes.length) return null;
  // 受け渡しは edges[] に宣言されている。これを渡さないと buildSwimlane は
  // 順序の手がかりを持てず、同じレーンの中しか結べない (レーンをまたぐ線が
  // 消える)。svgSpec は id で辺を書くので id のまま渡す。
  // kind:'dashed' は projectSequence と同じ語彙で「同じ向きの受け渡しではない辺」
  // (差戻し・再送) を指す。落とすと buildSwimlane は全部の辺を実線で引くので、
  // 凡例が破線を語っている図で**凡例だけが嘘をつく**状態になる。
  const links = (Array.isArray(spec.edges) ? spec.edges.filter(Boolean) : [])
    .map((e) => ({ from: e.from, to: e.to, label: e.label || '', dashed: e.kind === 'dashed' }));
  return { args: [lanes], opts: links.length ? { links } : {} };
}

/* 共通コアから「名前」を引く小道具。svg-structures の builder は関係 (relations /
 * messages / transitions) を **id ではなく表示名** で突合するので、edges[] の
 * from/to (node.id) は必ずここで名前へ置き換えてから渡す。 */
function nameByIdOf(nodes) {
  return new Map(nodes.map((n) => [n && n.id, (n && n.label) || '']));
}

/** edges[] → [{from, to, label, ...}] を表示名で。両端が nodes[] に無い辺は落とす */
function edgesByName(spec, nodes, extra) {
  const nameById = nameByIdOf(nodes);
  const edges = Array.isArray(spec.edges) ? spec.edges.filter(Boolean) : [];
  return edges.map((e) => {
    const from = nameById.get(e.from), to = nameById.get(e.to);
    if (!from || !to) return null;
    return { from, to, label: e.label || '', ...(extra ? extra(e) : {}) };
  }).filter(Boolean);
}

/** nodes[] → er の entities[]{name, fields[]}。fields は subtext を "/" 区切りで読む
 *  (共通コアに列一覧の器が無いため。空なら見出しだけのカードになる) */
function projectEntities(spec) {
  const nodes = Array.isArray(spec.nodes) ? spec.nodes.filter(Boolean) : [];
  if (!nodes.length) return null;
  const entities = nodes.map((n) => ({
    name: n.label || '',
    fields: String(n.subtext || '').split('/').map((s) => s.trim()).filter(Boolean),
  }));
  const relations = edgesByName(spec, nodes);
  return { args: [entities], opts: relations.length ? { relations } : {} };
}

/** nodes[] → sequence の actors[]、edges[] → messages[]。時系列は edges の配列順そのもの。
 *  kind:'dashed' を返信 (破線)、emphasis:'highlight' を外部連携 (link 色) と読む */
function projectSequence(spec) {
  const nodes = Array.isArray(spec.nodes) ? spec.nodes.filter(Boolean) : [];
  if (nodes.length < 2) return null;
  const messages = edgesByName(spec, nodes, (e) => ({
    dashed: e.kind === 'dashed',
    external: e.emphasis === 'highlight',
  }));
  if (!messages.length) return null;
  return { args: [nodes.map((n) => n.label || ''), messages], opts: {} };
}

/** nodes[] → state の states[]{label, sublabel, focal}、edges[] → transitions[]。
 *  遷移が 1 本も無いものは状態遷移図として成立しないので素材不足に倒す */
function projectStates(spec) {
  const nodes = Array.isArray(spec.nodes) ? spec.nodes.filter(Boolean) : [];
  if (!nodes.length) return null;
  const transitions = edgesByName(spec, nodes);
  if (!transitions.length) return null;
  const states = nodes.map((n) => ({
    label: n.label || '', sublabel: n.subtext || '', focal: n.emphasis === 'highlight',
  }));
  return { args: [states, transitions], opts: {} };
}

/** groups[] → it-state の rows[]{label, cells[]}。group が行 (観点)、所属 node が
 *  左からの列 (現状 / 課題 / あるべき姿)。列見出しは builder の既定に委ねる */
function projectItStateRows(spec) {
  const nodes = Array.isArray(spec.nodes) ? spec.nodes.filter(Boolean) : [];
  const groups = Array.isArray(spec.groups) ? spec.groups.filter(Boolean) : [];
  if (!nodes.length || !groups.length) return null;
  const rows = groups.map((g) => ({
    label: g.label || g.id || '',
    cells: nodes.filter((n) => n && n.group === g.id).map((n) => n.label || ''),
  })).filter((r) => r.cells.length);
  return rows.length ? { args: [rows], opts: {} } : null;
}

/** groups[] → medallion の tiers[]{label, items[], via}。group が層、所属 node が中身、
 *  層をまたぐ edge のラベルが昇格の語 (via)。groups[] が無いときは nodes[] 自体を層と読む */
function projectTiers(spec) {
  const nodes = Array.isArray(spec.nodes) ? spec.nodes.filter(Boolean) : [];
  const groups = Array.isArray(spec.groups) ? spec.groups.filter(Boolean) : [];
  const edges = Array.isArray(spec.edges) ? spec.edges.filter(Boolean) : [];
  if (!nodes.length) return null;
  const filled = groups
    .map((g) => ({ group: g, members: nodes.filter((n) => n && n.group === g.id) }))
    .filter((t) => t.members.length);
  if (filled.length) {
    const tiers = filled.map(({ group, members }, i) => {
      const next = filled[i + 1];
      const e = next ? edges.find((x) => x
        && members.some((m) => m.id === x.from) && next.members.some((m) => m.id === x.to)) : null;
      return {
        label: group.label || group.id || '',
        items: members.map((m) => m.label || ''),
        via: (e && e.label) || '',
      };
    });
    return { args: [tiers], opts: {} };
  }
  const tiers = nodes.map((n, i) => {
    const next = nodes[i + 1];
    const e = next ? edges.find((x) => x && x.from === n.id && x.to === next.id) : null;
    return { label: n.label || '', sublabel: n.subtext || '', via: (e && e.label) || '' };
  });
  return { args: [tiers], opts: {} };
}

/** groups[] (無ければ node.level) → high-level の levels[]{label, items[]}。
 *  段の順は groups[] の並び順、level 経由のときは値の昇順。段見出しは group.label */
function projectLevels(spec) {
  const nodes = Array.isArray(spec.nodes) ? spec.nodes.filter(Boolean) : [];
  const groups = Array.isArray(spec.groups) ? spec.groups.filter(Boolean) : [];
  if (!nodes.length) return null;

  // 段を「ノードの並び」として先に決める。項目へ畳むのは最後にする。
  // 先に {label, sublabel} へ畳むと id が消え、edges と突き合わせられない。
  let tiers = null;
  if (groups.length) {
    tiers = groups
      .map((g) => ({ label: g.label || g.id || '', nodes: nodes.filter((n) => n && n.group === g.id) }))
      .filter((t) => t.nodes.length);
    if (!tiers.length) return null;
  } else {
    // group が無いときだけ node.level を段として読む。一部だけ level を持つ入力は
    // 段の割り当てが恣意的になるので素材不足に倒す (欠けた段を勝手に作らない)。
    if (!nodes.every((n) => Number.isInteger(n.level))) return null;
    const byLevel = new Map();
    for (const n of nodes) {
      if (!byLevel.has(n.level)) byLevel.set(n.level, []);
      byLevel.get(n.level).push(n);
    }
    // 段見出しは持たない (builder 側が「第 N 層」を補う)
    tiers = [...byLevel.keys()].sort((a, b) => a - b).map((lv) => ({ label: '', nodes: byLevel.get(lv) }));
    if (!tiers.length) return null;
  }

  // 段間の帰属を edges から渡す。渡さないと buildHighLevel には宣言が 1 つも
  // 届かず、段レベルのトランク 1 本へ落ちる — 入力が持っている依存関係が
  // 図から丸ごと消える。宣言できるのに宣言しないのは、情報の取りこぼしである。
  // 渡すのは**次の段へ向かう辺だけ**。段を飛ばす辺や逆向きの辺をここで
  // 上下対応として渡すと、隣り合っていない関係を隣接として描くことになる。
  const labelOf = new Map(nodes.map((n) => [n.id, n.label || '']));
  const edges = Array.isArray(spec.edges) ? spec.edges.filter(Boolean) : [];
  const levels = tiers.map((t, ti) => {
    const nextIds = ti + 1 < tiers.length ? new Set(tiers[ti + 1].nodes.map((n) => n.id)) : null;
    return {
      label: t.label,
      items: t.nodes.map((n) => {
        const item = { label: n.label || '', sublabel: n.subtext || '' };
        if (!nextIds) return item;
        // builder は次段の label で引き当てる。label が空のノードは引き当て
        // 不能なので落とす (空文字で当たると別のノードへ線が付く)。
        const to = edges
          .filter((e) => e.from === n.id && nextIds.has(e.to))
          .map((e) => labelOf.get(e.to))
          .filter(Boolean);
        if (to.length) item.to = to;
        return item;
      }),
    };
  });
  return { args: [levels], opts: {} };
}

/** nodes[] → dp-integration の hub + spokes[]{label, sublabel, direction}。
 *  ハブは emphasis:'highlight' の最初の node、無ければ先頭 node。向きは edge の
 *  差し向き (ハブ→周辺 = out / 周辺→ハブ = in / 両方 = both)。辺が無ければ in 扱い */
function projectHubSpokes(spec) {
  const nodes = Array.isArray(spec.nodes) ? spec.nodes.filter(Boolean) : [];
  const edges = Array.isArray(spec.edges) ? spec.edges.filter(Boolean) : [];
  if (nodes.length < 2) return null;
  const hubNode = nodes.find((n) => n.emphasis === 'highlight') || nodes[0];
  const spokeNodes = nodes.filter((n) => n !== hubNode);
  if (!spokeNodes.length) return null;
  const spokes = spokeNodes.map((n) => {
    const out = edges.some((e) => e.from === hubNode.id && e.to === n.id);
    const into = edges.some((e) => e.from === n.id && e.to === hubNode.id);
    return {
      label: n.label || '',
      sublabel: n.subtext || '',
      direction: out && into ? 'both' : (out ? 'out' : 'in'),
    };
  });
  return { args: [{ label: hubNode.label || '', sublabel: hubNode.subtext || '' }, spokes], opts: {} };
}

/** diagramNode[] → {label, value} 配列 (slope/butterfly 用。value は node.value か subtext 内の数値) */
function nodesToValued(nodes) {
  const arr = Array.isArray(nodes) ? nodes : [];
  return arr.map((n, i) => {
    if (n == null) return { label: '', value: 0 };
    if (typeof n === 'string') return { label: n, value: 0 };
    let v = n.value;
    if (v == null && typeof n.subtext === 'string') {
      const m = n.subtext.match(/-?\d+(?:\.\d+)?/);
      v = m ? Number(m[0]) : 0;
    }
    return { label: n.label || '', value: Number(v) || 0 };
  });
}

/**
 * 中立 A対B 対比図 (report engine 固有・決定論)。svg-builder.buildVs が Before/After(bad/good) を
 * 固定描画するため、中立対比 (両列対等・group 名タイトル・bullet) を
 * ここで描く。列色は wave-blue / wave-aqua の対等な2色。逐語値は本文表に温存し、図は対比構造を一目化する。
 *
 * 契約 (diagram-layout-contract §2/§3): ラベルを切り詰めず、容量を超える素材も詰めない。
 * 26 字を超えるラベル、または 6 件を超える列があれば **この図自体を作らない** (null を返す)。
 * 以前はここで `slice(0,26)+'…'` と `slice(0,6)` を黙って行っていたが、日本語は述部が
 * 末尾に来るため途中で切ると否定・条件・留保が落ち、図が本文と逆の主張になる。
 * 呼び側 (renderSvgVisual / 導出) は null を受けたら図を出さずフォールバックへ倒す。
 */
const NEUTRAL_COMPARISON_MAX_LABEL = 26;  // 決定表 R04 の label_max_length と同値
const NEUTRAL_COMPARISON_MAX_ITEMS = 6;   // 決定表 R04 の capacity と同値

function buildNeutralComparison(leftItems, rightItems, opts = {}) {
  const colW = 540, gap = 64, leftX = 40;
  const rightX = leftX + colW + gap;
  const headerH = 60, itemH = 54, padX = 22, itemGap = 12, topY = 36, bottomPad = 26;
  const L = Array.isArray(leftItems) ? leftItems : [];
  const R = Array.isArray(rightItems) ? rightItems : [];
  const textOf = (it) => (typeof it === 'string' ? it : (it && (it.label || it.text)) || '');
  // 容量超過は不採用 (詰めて載せると読者は全部が描かれていると信じる)
  if (L.length > NEUTRAL_COMPARISON_MAX_ITEMS || R.length > NEUTRAL_COMPARISON_MAX_ITEMS) return null;
  // 入らないラベルが 1 つでもあれば図ごと中止 (conciseLabel と同じ契約)
  if ([...L, ...R].some((it) => textOf(it).length > NEUTRAL_COMPARISON_MAX_LABEL)) return null;
  const maxItems = Math.max(L.length, R.length, 1);
  const cardH = headerH + 18 + maxItems * itemH + Math.max(0, maxItems - 1) * itemGap + bottomPad;
  const W = 1200, H = topY + cardH + 28;
  // 左右 2 列は対等なので色相では区別しない。濃度段 2 段の差だけで書き分ける
  // (VGCONST_002)。どちらもヘッダに paper 文字を載せるため濃い側 2 段から採る。
  const BLUE = kit.TOKENS.ink;
  const AQUA = kit.TOKENS.link;

  function column(x, items, color, title) {
    const b = [];
    b.push(`<rect x="${x}" y="${topY}" width="${colW}" height="${cardH}" fill="${kit.TOKENS.paper}" stroke="${kit.TOKENS.rule}" stroke-width="1.5"/>`);
    b.push(`<rect x="${x}" y="${topY}" width="${colW}" height="${headerH}" fill="${color}" opacity="0.92"/>`);
    b.push(`<rect x="${x}" y="${topY + headerH - 16}" width="${colW}" height="16" fill="${color}" opacity="0.92"/>`);
    b.push(`<text x="${x + 24}" y="${topY + 38}" text-anchor="start" fill="${kit.TOKENS.white}" font-size="22" font-weight="800" font-family="'Noto Sans JP', sans-serif">${escapeHtml(title)}</text>`);
    items.forEach((it, i) => {
      const y = topY + headerH + 16 + i * (itemH + itemGap);
      const text = textOf(it);
      b.push(`<rect x="${x + padX}" y="${y}" width="${colW - padX * 2}" height="${itemH}" fill="${kit.TOKENS.paper2}" stroke="${kit.TOKENS.rule}" stroke-width="${kit.STROKE.hairline}"/>`);
      b.push(`<rect x="${x + padX}" y="${y}" width="6" height="${itemH}" fill="${color}"/>`);
      b.push(`<circle cx="${x + padX + 30}" cy="${y + itemH / 2}" r="6" fill="${color}"/>`);
      b.push(`<text x="${x + padX + 50}" y="${y + itemH / 2 + 6}" text-anchor="start" fill="${kit.TOKENS.ink}" font-size="17" font-weight="600" font-family="'Noto Sans JP', sans-serif">${escapeHtml(text)}</text>`);
    });
    return b.join('\n  ');
  }

  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeHtml(opts.ariaLabel || `${opts.leftTitle} と ${opts.rightTitle} の対比`)}" xmlns="http://www.w3.org/2000/svg">
  ${column(leftX, L, BLUE, opts.leftTitle || 'A')}
  ${column(rightX, R, AQUA, opts.rightTitle || 'B')}
</svg>`;
}

/** svgSpec {variant, nodes[], groups?} → svg-builder への dispatch (決定論) */
/* 参照検査 (I-ER-REF / I-REL-ISO) が読む宣言を、描画結果へそのまま載せる。
 *
 * 描画済み SVG から実体と関係を復元しようとすると、線の端点と矩形を座標で
 * 突き合わせることになり、必ず近似が入る。近似で error 重大度の失格を出すのは
 * 誤検知の温床なので、検査器は生成物 (.html) を参照検査の対象から外していた
 * — つまり本番の図は参照の取りこぼしを一度も見られていなかった。
 *
 * 復元する代わりに**宣言をそのまま運ぶ**。図が申告した実体・節点・関係だけを
 * figure の属性へ載せ、検査器は JSON 経路と同一の検査を掛ける。近似は 0 になる。
 * 宣言を持たない図 (本文からの導出図など) には属性が付かず、検査器はそれを
 * 「参照検査をしていない」と数える (合格にはしない = 空振りガード)。
 *
 * 属性値は escapeHtml を通すので `<` `>` `"` が生の形で入らない。検査器側の
 * タグ剥がし正規表現 `<[^>]+>` を壊さず、本文領域へ JSON が混ざることもない。
 */
function declarationAttr(spec) {
  if (!spec || typeof spec !== 'object') return '';
  const decl = {};
  if (Array.isArray(spec.entities) && spec.entities.length) {
    decl.entities = spec.entities
      .filter((e) => e && typeof e === 'object')
      .map((e) => ({ name: e.name, fields: Array.isArray(e.fields) ? e.fields.map(String) : [] }));
  }
  if (Array.isArray(spec.nodes) && spec.nodes.length) {
    decl.nodes = spec.nodes
      .filter((n) => n && typeof n === 'object')
      .map((n) => {
        const o = {};
        if (n.id != null) o.id = n.id;
        if (n.label != null) o.label = n.label;
        if (n.name != null) o.name = n.name;
        // role は「線を持たなくてよい節点」の免除根拠。落とすと凡例や注記が
        // 孤立節点として error になるので、宣言されていれば必ず運ぶ。
        if (n.role != null) o.role = n.role;
        return o;
      });
  }
  const rel = spec.relations || spec.links || spec.edges;
  if (Array.isArray(rel) && rel.length) {
    decl.relations = rel
      .filter((r) => r && typeof r === 'object')
      .map((r) => ({
        from: r.from != null ? r.from : r.source,
        to: r.to != null ? r.to : r.target,
      }));
  }
  // 参照検査の語彙 (entities / nodes) を 1 つも持たない図には属性を付けない。
  // 空の宣言を載せると「宣言したが空だった」と「そもそも宣言が無い」が
  // 見分けられなくなり、検査したことにされる。
  if (!decl.entities && !decl.nodes) return '';
  return ` data-srg-declaration="${escapeHtml(JSON.stringify(decl))}"`;
}

function renderSvgVisual(spec, meta) {
  const variant = spec.variant || 'flow';
  const opts = meta && meta.alt ? { ariaLabel: meta.alt } : {};
  // 出所と時点は figcaption ではなく図の**内側**へ置く。図が単独で引用された
  // ときに根拠ごと消えないようにするため (情報契約 §I1)。
  if (spec.source) opts.source = spec.source;
  if (spec.asOf) opts.asOf = spec.asOf;
  // 線種で意味を分けている図は、色見本だけの凡例では読み解けない。
  if (spec.legend && Array.isArray(spec.legend.items) && spec.legend.items.length) {
    opts.legendItems = spec.legend.items.filter(Boolean);
  }
  const items = nodesToItems(spec.nodes);
  let inner = '';

  if (variant === 'mindmap' && typeof svg.buildMindmap === 'function') {
    const center = items.length ? items[0].label : '';
    inner = svg.buildMindmap(center, items.slice(1).map((it) => it.label), opts);
  } else if (variant === 'network' && typeof svg.buildMindmap === 'function') {
    const center = items.length ? items[0].label : '';
    inner = svg.buildMindmap(center, items.slice(1).map((it) => it.label), opts);
  } else if (variant === 'comparison') {
    // comparison = 中立の A対B 対比。svg-builder.buildVs は Before/After(×○/pink=bad/good) を固定描画し
    // ため中立比較には使えない。report engine 側の中立レンダラ (両列対等・group 名タイトル・
    // bullet マーカー) で描く。before→after / bad→good の対比は slope/butterfly が担当 (owner 分離)。
    const cmpNodes = spec.nodes || [];
    const { left, right } = splitForComparison(cmpNodes);
    const cmpGroups = [...new Set(cmpNodes.map((n) => (n && n.group) || '').filter(Boolean))];
    const cmpGroupLabel = (gid) => {
      const g = (Array.isArray(spec.groups) ? spec.groups : []).find((x) => x && x.id === gid);
      return (g && g.label) || gid;
    };
    inner = buildNeutralComparison(
      nodesToItems(left).map((i) => i.label),
      nodesToItems(right).map((i) => i.label),
      {
        leftTitle: cmpGroups.length ? cmpGroupLabel(cmpGroups[0]) : 'A',
        rightTitle: cmpGroups.length > 1 ? cmpGroupLabel(cmpGroups[1]) : 'B',
        ariaLabel: meta.alt,
      },
    );
    // 切り詰め禁止・容量超過不採用に触れた場合は null。空図を黙って出さずフォールバックへ。
    if (!inner) {
      return fallbackVisual('comparison: ラベルが 26 字を超えるか列が 6 件を超えるため図にしません', meta.caption);
    }
  } else if (VARIANT_STRUCT[variant]) {
    // 構造図 (svg-structures.cjs)。素材が射影できないときは空の枠を描かせず理由を出す。
    // 射影の戻り値は 2 形: 単一引数のビルダーは素材配列そのまま、複数引数 (actors+messages
    // など) や opts (er の relations) を要るものは { args, opts }。
    const def = VARIANT_STRUCT[variant];
    const material = def.project(spec);
    const call = Array.isArray(material) ? { args: [material], opts: {} } : material;
    if (!call || !Array.isArray(call.args) || !call.args.length) {
      return fallbackVisual(`${variant}: 図にできる素材 (nodes[]/edges[]/groups[]) がありません`, meta.caption);
    }
    inner = struct[def.builder](...call.args, { ...opts, ...(call.opts || {}) });
  } else if ((variant === 'slope' || variant === 'butterfly') && typeof svg[variant === 'slope' ? 'buildSlope' : 'buildButterfly'] === 'function') {
    // 数値対比 (before→after / 左右量): group で二分、node.value か subtext 数値を採る
    const { left, right } = splitForComparison(spec.nodes || []);
    const fn = variant === 'slope' ? svg.buildSlope : svg.buildButterfly;
    inner = fn(nodesToValued(left), nodesToValued(right), opts);
  } else if (VARIANT_SINGLE_ARG[variant] && typeof svg[VARIANT_SINGLE_ARG[variant]] === 'function') {
    inner = svg[VARIANT_SINGLE_ARG[variant]](items, opts);
  } else {
    return fallbackVisual(`未対応の svg variant: ${variant}`, meta.caption);
  }
  // ビルダーが空文字を返した場合も黙って空の figure を出さない。
  if (!inner) return fallbackVisual(`svg variant ${variant} の描画結果が空です`, meta.caption);
  const caption = meta.caption ? `\n  <figcaption>${escapeHtml(meta.caption)}</figcaption>` : '';
  // role="img" を figure に付けると子孫が presentational になり figcaption が
  // 支援技術へ届かない。説明は内側 svg の aria-label が持つので figure は素のまま。
  return `<figure class="report-visual report-visual--svg"${declarationAttr(spec)}>\n  ${inner}${caption}\n</figure>`;
}

/* ===== 見出しごとの図解を保証する自動導出 (v7.7.0) =====
 *
 * 要件: 「各見出しごとに、その見出しの内容に含まれている情報を図解で表現する」。
 * 読者はまず図で全体像を掴み、分からない箇所だけ本文へ降りる。そのため図解が
 * 無い節があると、その節だけ読み方が変わってしまう。
 *
 * 設計上の一線: **この節に書かれている情報だけ**から作る。外部知識で補ったり
 * 一般論の図を当てたりすると、図と本文が食い違って読者を誤らせる。導出できる
 * 構造が本文に無ければ図解を作らない (無理に作らない方が正しい)。
 */

/** 図解に載せる 1 行ラベル。1 文に収まらない/収めると意味が変わるものは null。
 *
 * 日本語は述部が末尾に来るため、途中で切ると「〜しない」「〜する場合に限り」が
 * 落ちて、本文と逆の主張が図に載る。だから「詰めれば載る」ではなく
 * 「そのまま載る場合だけ載せる」に倒す。逆接を含む文も同じ理由で載せない。
 * 文末の判定は splitSentences と同じもの (半角 . は語中と区別できないので使わない)。
 */
const RESERVATION_RE = /(ただし|ただ、|しかし|一方|とはいえ|ものの|except|however)/;

function conciseLabel(text) {
  const s = String(text == null ? '' : text)
    .replace(/\s+/g, ' ')
    .replace(/`[^`]*`/g, '')       // インラインコードは図解に載せない
    .replace(/\*\*|__|\*|_/g, '')  // 強調記号を落とす
    .trim();
  if (!s) return null;
  const sents = splitSentences(s);
  const head = (sents.length ? sents[0] : s).replace(/[。！？]$/, '');
  if (sents.length > 1 && RESERVATION_RE.test(s.slice(sents[0].length))) return null;
  if (RESERVATION_RE.test(head)) return null;
  if (head.length > 28) return null;  // 切り詰めない。載せない
  return head;
}

/**
 * 節の body[] から図解の素材を決定論的に取り出す。
 * どの構造を選ぶかは「本文が実際に持っている形」で決める:
 *   ordered-list / task-list → 順序がある     → 横フロー (chevron)
 *   bullet-list              → 並列の要素     → 価値スタック (value-stack)
 *   stat-tile                → 量の対比       → 横棒
 * どれも無ければ null を返し、図解を作らない。
 *
 * 「1 項目でもラベルにできなければ導出をやめる」のは意図的。一部だけ落とすと
 * 読者は図を全体像だと信じてしまう。全部載るか作らないかの二択にする。
 */
function labelsOf(items, pick) {
  const out = [];
  for (const it of items) {
    const label = conciseLabel(pick(it));
    if (!label) return null;
    out.push(label);
  }
  return out;
}

/** ビルダーの上限を超える素材は、その variant では扱わない (黙って切らない)。
 *
 * fail-closed: 上限がどこにも宣言されていなければ「無制限」ではなく **不採用** にする。
 * 以前は cap===0 を無制限と読んでいたため、CAPACITY への登録漏れが静かに通り、
 * 超過分が黙って消えた図が出ていた (契約 §2 の思想と逆)。
 * 上限の出所は 2 つあり、両方あるときは厳しい方を採る:
 *   - svg-builder.cjs の CAPACITY (ビルダー実装の上限。正本)
 *   - 決定表 rows[].result.capacity (CAPACITY 未登録のビルダーに対し、表が
 *     schema の maxItems や実装の slice 値を代替として明示している値)
 */
function fitsCapacity(builderName, n, declaredCap) {
  const registered = svg && svg.CAPACITY ? svg.CAPACITY[builderName] : undefined;
  const caps = [registered, declaredCap].filter((v) => typeof v === 'number' && isFinite(v) && v > 0);
  if (!caps.length) return false;
  return n <= Math.min(...caps);
}

/* ===== 決定表 (visual-derivation-table.json) をそのまま実行する =====
 *
 * 図種選定の正本は schemas/visual-derivation-table.json 1 つ。ここでは表を
 * **実行時に読み込んで評価する**。表からコードを生成する方式だと「表」と「生成物」が
 * 二重に存在し、両者のズレを別の検査で塞ぎ続けなければならないが、表そのものを
 * 入力として評価すれば乖離が構造的に起こり得ない (機械が気づくまでもなく起きない)。
 * 表は HTML 生成時にしか読まないので、成果物 HTML の自己完結性 (外部参照を増やさない)
 * には影響しない。
 *
 * 表が読めない場合は導出を行わない (fail-closed)。勝手な既定の順序で図を作ると、
 * 正本を 2 箇所に持っていた元の問題に戻る。
 */
let DERIVATION_TABLE = null;
try {
  DERIVATION_TABLE = require('../../schemas/visual-derivation-table.json');
} catch (e) {
  DERIVATION_TABLE = null;
}

/** definitions.numeric: 量として読めるなら数値、読めなければ null */
function numericValue(v) {
  if (v == null) return null;
  const n = parseFloat(String(v).replace(/,/g, '').replace(/[^0-9.\-]/g, ''));
  return Number.isFinite(n) ? n : null;
}

/** source.label / source.value の式を関数化。未知の式は null (=その行を不採用) */
function makePicker(expr) {
  const e = String(expr == null ? '' : expr).trim();
  if (!e) return null;
  if (e === 'item') return (x) => (typeof x === 'string' ? x : '');
  const m = /^item\.([A-Za-z_][A-Za-z0-9_]*)$/.exec(e);
  if (m) return (x) => (x && x[m[1]] != null ? x[m[1]] : '');
  const r = /^row\[(\d+)\]$/.exec(e);
  if (r) {
    const i = Number(r[1]);
    return (x) => (Array.isArray(x) && x[i] != null ? x[i] : '');
  }
  return null;
}

/** source.field → { blk, items }。実体が items[] でないブロックの取り違えを防ぐ */
function materialsOf(sec, body, row) {
  const field = (row.source && row.source.field) || '';
  if (field === 'body[type=paragraph]') {
    return { blk: null, items: body.filter((b) => b && b.type === 'paragraph') };
  }
  if (field === 'section.paragraphs') {
    return { blk: null, items: Array.isArray(sec && sec.paragraphs) ? sec.paragraphs : [] };
  }
  const blk = body.find((b) => b && b.type === row.block); // select: first
  if (!blk) return null;
  return Array.isArray(blk[field]) ? { blk, items: blk[field] } : null;
}

/** predicate.has_block / no_block */
function predicateBlocks(body, p) {
  const types = new Set(body.map((b) => (b && b.type) || ''));
  if (Array.isArray(p && p.has_block) && !p.has_block.every((t) => types.has(t))) return false;
  if (Array.isArray(p && p.no_block) && p.no_block.some((t) => types.has(t))) return false;
  return true;
}

/** predicate.header_matches (all = 各パターンが別々の列に一致 / any / ordered) */
function matchHeaders(headers, spec) {
  const flags = spec.flags == null ? 'i' : String(spec.flags).replace(/g/g, '');
  let pats;
  try {
    pats = (spec.patterns || []).map((s) => new RegExp(s, flags));
  } catch (e) {
    return false; // 表の正規表現が壊れていたら成立させない
  }
  if (!pats.length) return false;
  const mode = spec.mode || 'all';
  if (mode === 'any') return pats.some((re) => headers.some((h) => re.test(h)));
  if (mode === 'ordered') {
    let i = 0;
    for (const h of headers) if (i < pats.length && pats[i].test(h)) i += 1;
    return i === pats.length;
  }
  const used = new Set();
  for (const re of pats) {
    const idx = headers.findIndex((h, i) => !used.has(i) && re.test(h));
    if (idx < 0) return false;
    used.add(idx);
  }
  return true;
}

/** predicate.value_matches */
function matchValues(items, spec) {
  let re;
  try {
    re = new RegExp(spec.pattern, spec.flags == null ? '' : String(spec.flags).replace(/g/g, ''));
  } catch (e) {
    return false;
  }
  const pick = makePicker(spec.field) || ((x) => (x && x[spec.field] != null ? x[spec.field] : ''));
  const hit = items.map((it) => re.test(String(pick(it) == null ? '' : pick(it))));
  return (spec.mode || 'any') === 'any' ? hit.some(Boolean) : hit.every(Boolean);
}

/* 決定表の result.builder → report 経路の実配線。
 * ここに居ないビルダーの行は、表が status:'implemented' と書いていても採用しない
 * (fail-closed)。逆に status:'planned' の行でも、ここへ配線した時点で有効になる。
 * status は表側の宣言、実際の可否はこの表への配線が決める — 宣言だけで描けたことに
 * しないためにゲートを配線側へ置く。
 * materialize は「素材を、ラベルを切り詰めずに載せられる形へ写す」。写せなければ
 * null を返し、その行は不成立として次行へ落ちる。 */
const DERIVED_BUILDERS = {
  // R02: stat-tile → 横棒 (label + 量)
  buildBarChart: {
    materialize: (ctx) => {
      const nodes = [];
      for (let i = 0; i < ctx.items.length; i += 1) {
        const v = numericValue(ctx.pickValue(ctx.items[i]));
        if (v === null) return null;
        nodes.push({ label: ctx.labels[i], value: v });
      }
      return { nodes };
    },
    render: (d, opts) => svg.buildBarChart(d.nodes, opts),
  },
  // R03: table(開始/終了列あり) → 縦タイムライン
  buildVerticalTimeline: {
    materialize: (ctx) => {
      const headers = ctx.headers;
      // 行が成立した理由そのものである「開始」列の値を各段の日付として添える。
      // 本文のセルをそのまま引くだけなので、図が本文以上のことを主張しない。
      const si = headers.findIndex((h) => /(開始|着手|start|from|before)/i.test(h));
      const nodes = ctx.labels.map((label, i) => {
        const cell = si > 0 && Array.isArray(ctx.items[i]) ? String(ctx.items[i][si] == null ? '' : ctx.items[i][si]) : '';
        const date = cell ? conciseLabel(cell) : null;
        return date ? { label, subtext: date } : { label };
      });
      return { nodes };
    },
    render: (d, opts) => svg.buildVerticalTimeline(nodesToItems(d.nodes), opts),
  },
  // R04: 2 列の table → 中立 A対B 対比
  buildNeutralComparison: {
    materialize: (ctx) => {
      const right = labelsOf(ctx.items, (r) => (Array.isArray(r) ? r[1] : ''));
      if (!right) return null;
      const max = (ctx.row.predicate && ctx.row.predicate.label_max_length) || NEUTRAL_COMPARISON_MAX_LABEL;
      // 右列にも同じラベル契約を課す (表の predicate は row[0] にしか掛からないが、
      // 図に載るのは両列なので、右列が切り詰め対象になるならこの行ごと落とす)。
      if (right.some((t) => t.length > max)) return null;
      return {
        left: ctx.labels,
        right,
        leftTitle: ctx.headers[0] || 'A',
        rightTitle: ctx.headers[1] || 'B',
      };
    },
    render: (d, opts) => buildNeutralComparison(d.left, d.right, { ...opts, leftTitle: d.leftTitle, rightTitle: d.rightTitle }),
  },
  // R05: 担当列を持つ table → スイムレーン (svg-structures.cjs)
  buildSwimlane: {
    materialize: (ctx) => {
      const headers = ctx.headers;
      const lanes = [];
      for (let i = 0; i < ctx.items.length; i += 1) {
        const row = Array.isArray(ctx.items[i]) ? ctx.items[i] : [];
        const steps = [];
        for (let c = 1; c < headers.length; c += 1) {
          const cell = String(row[c] == null ? '' : row[c]).trim();
          if (!cell) continue;
          const lab = conciseLabel(cell);
          if (!lab) return null; // 1 セルでも載らなければレーン図ごと作らない
          steps.push({ label: lab, step: c - 1 });
        }
        if (!steps.length) return null;
        lanes.push({ label: ctx.labels[i], steps });
      }
      return { lanes, stepLabels: headers.slice(1) };
    },
    render: (d, opts) => struct.buildSwimlane(d.lanes, { ...opts, stepLabels: d.stepLabels }),
  },
  // R06 / R08: 順序のある列 → 矢羽根
  buildChevron: {
    materialize: (ctx) => ({ nodes: ctx.labels }),
    render: (d, opts) => svg.buildChevron(nodesToItems(d.nodes), opts),
  },
  // R09 / R10: 並列の要素 → 価値スタック
  buildValueStack: {
    materialize: (ctx) => ({ nodes: ctx.labels }),
    render: (d, opts) => svg.buildValueStack(nodesToItems(d.nodes), opts),
  },
  // R07 / R11 / R12 / R13: 縦フロー (connector は行の builderOptions が決める)
  buildVerticalFlow: {
    materialize: (ctx) => ({ nodes: ctx.labels }),
    render: (d, opts) => svg.buildVerticalFlow(nodesToItems(d.nodes), { ...opts, ...(d.builderOptions || {}) }),
  },
};

/** 1 行を評価する。成立すれば導出結果、しなければ null (=次行へ) */
function evalSvgRow(sec, body, row) {
  const p = row.predicate || {};
  const res = row.result || {};
  const reg = DERIVED_BUILDERS[res.builder];
  if (!reg) return null; // report 経路へ未配線 (status:'planned' のまま) の行はここで落ちる

  if (p.body_empty === true && body.length) return null;
  if (p.body_empty === false && !body.length) return null;
  if (!predicateBlocks(body, p)) return null;

  const got = materialsOf(sec, body, row);
  if (!got) return null;
  const { blk, items } = got;
  const headers = Array.isArray(blk && blk.headers) ? blk.headers.map((h) => String(h == null ? '' : h)) : [];

  if (p.header_count) {
    if (p.header_count.min != null && headers.length < p.header_count.min) return null;
    if (p.header_count.max != null && headers.length > p.header_count.max) return null;
  }
  if (p.header_matches && !matchHeaders(headers, p.header_matches)) return null;
  if (p.count) {
    if (p.count.min != null && items.length < p.count.min) return null;
    if (p.count.max != null && items.length > p.count.max) return null;
  }
  if (p.value_matches && !matchValues(items, p.value_matches)) return null;
  if (p.has_mixed_done != null) {
    const dones = items.map((t) => (t && t.done === true));
    const mixed = dones.some(Boolean) && dones.some((x) => !x);
    if (mixed !== p.has_mixed_done) return null;
  }

  const pick = makePicker((row.source || {}).label);
  if (!pick) return null;
  let labels;
  if (p.all_labelable === true) {
    labels = labelsOf(items, pick);
    if (!labels) return null; // 1 件でも載らなければこの行は不成立 (切り詰めない)
  } else {
    labels = items.map((it) => String(pick(it) == null ? '' : pick(it)));
  }
  if (p.label_max_length != null && labels.some((t) => t.length > p.label_max_length)) return null;
  if (p.min_label_length != null && labels.some((t) => t.length < p.min_label_length)) return null;

  if (p.all_numeric === true || p.any_non_numeric === true) {
    const pv = makePicker((row.source || {}).value);
    if (!pv) return null;
    const vals = items.map((it) => numericValue(pv(it)));
    if (p.all_numeric === true && vals.some((v) => v === null)) return null;
    if (p.any_non_numeric === true && !vals.some((v) => v === null)) return null;
  }

  if (!fitsCapacity(res.builder, items.length, res.capacity)) return null;

  const pickValue = makePicker((row.source || {}).value) || (() => null);
  const extra = reg.materialize({ sec, body, blk, items, labels, headers, row, pickValue });
  if (!extra) return null;
  return {
    rowId: row.id,
    block: row.block,
    variant: res.variant,
    builder: res.builder,
    builderOptions: res.builderOptions || {},
    ...extra,
  };
}

/** subheading を分割子として body[] をグループへ切る (小見出し自体は素材にしない) */
function splitBySubheading(body) {
  const groups = [];
  let cur = [];
  for (const b of body) {
    if (b && b.type === 'subheading') {
      if (cur.length) groups.push(cur);
      cur = [];
      continue;
    }
    cur.push(b);
  }
  if (cur.length) groups.push(cur);
  return groups;
}

/** 決定表を order 昇順に評価し、最初に成立した行を採用する (first-match-wins) */
function evaluateDerivationTable(sec, body, depth) {
  const table = DERIVATION_TABLE;
  if (!table || !Array.isArray(table.rows)) return null;
  const rows = table.rows.slice().sort((a, b) => (a.order || 0) - (b.order || 0));
  for (const row of rows) {
    const res = (row && row.result) || {};
    if (res.kind === 'none') return null; // 無条件フォールバック行 = 図解を作らない
    if (res.kind === 'recurse') {
      // 分割子。深さ 1 段だけ (節の中の小見出しは 1 階層しか無い)。
      if (depth > 0) continue;
      if (!predicateBlocks(body, row.predicate)) continue;
      for (const g of splitBySubheading(body)) {
        const d = evaluateDerivationTable(sec, g, depth + 1);
        if (d) return d; // 非 none を返した最初のグループ 1 件のみ (RCONST_003)
      }
      // 分割した以上、平坦走査へは戻らない (小見出しをまたいだ素材の混在を防ぐ)
      return null;
    }
    if (res.kind !== 'svg') continue;
    const d = evalSvgRow(sec, body, row);
    if (d) return d;
  }
  return null;
}

/**
 * 節の body[] から図解の素材を決定論的に取り出す。
 * どの構造をどの図種に写すかは visual-derivation-table.json が唯一の正本で、
 * この関数はその表の実行器にすぎない (順序も上限もここには書かない)。
 */
function deriveVisualFromBody(sec) {
  const body = Array.isArray(sec && sec.body) ? sec.body : [];
  return evaluateDerivationTable(sec, body, 0);
}

/** 導出した素材を SVG へ。導出元が無ければ空を返す (呼び側は図解なしで進む)。 */
function renderDerivedVisual(sec, counters) {
  const derived = deriveVisualFromBody(sec);
  if (!derived) return { html: '', usesMermaid: false };
  const reg = DERIVED_BUILDERS[derived.builder];
  if (!reg) return { html: '', usesMermaid: false };
  const heading = (sec && sec.heading) || '';
  const opts = { ariaLabel: `${heading}の要点を図にしたもの` };
  let inner = '';
  try {
    inner = reg.render(derived, opts) || '';
  } catch (e) {
    // 図解の失敗で節そのものを落とさない。本文は残す。
    return { html: '', usesMermaid: false };
  }
  if (!inner) return { html: '', usesMermaid: false };
  if (counters) counters.fig += 1;
  // 「構造」と名乗れるのは素材が構造を持っていたときだけ。段落を並べただけの
  // 導出図は「論点」と呼ぶ (図が本文以上のことを主張しないため)。
  const noun = (derived.block === 'paragraph' || derived.block === 'paragraphs') ? '論点' : '構造';
  const cap = counters ? `\n  <figcaption>図${counters.fig}. ${escapeHtml(heading)}の${noun}</figcaption>` : '';
  return {
    // 図の説明は内側 svg の role="img" + aria-label が担う。figure にも aria-label を
    // 付けると figcaption と二重に読み上げられるので付けない。
    html: `<figure class="report-visual report-visual--svg report-visual--derived">`
      + `\n  ${inner}${cap}\n</figure>`,
    usesMermaid: false,
  };
}

/** comparison 用に nodes を左右へ決定論分割 (group 優先、無ければ半々) */
function splitForComparison(nodes) {
  const groups = [...new Set(nodes.map((n) => (n && n.group) || '').filter(Boolean))];
  if (groups.length >= 2) {
    return {
      left: nodes.filter((n) => n && n.group === groups[0]),
      right: nodes.filter((n) => n && n.group !== groups[0]),
    };
  }
  const mid = Math.ceil(nodes.length / 2);
  return { left: nodes.slice(0, mid), right: nodes.slice(mid) };
}

/**
 * aiVisualSpec → <img> (asset/slug) or composite プレースホルダ。
 * asset (WebP/PNG) 明示 or slug から images/<slug>.png を導出し <img> 参照埋込。
 * 双方無い場合 (backgroundSource=none 等) は overlayText を並べた決定論プレースホルダ。
 */
function renderCodexImage(spec, meta) {
  const alt = escapeHtml(meta.alt || spec.alt || (Array.isArray(spec.overlayText) ? spec.overlayText[0] : '') || '図');
  const caption = meta.caption ? `\n  <figcaption>${escapeHtml(meta.caption)}</figcaption>` : '';
  const src = spec.asset || (spec.slug ? `images/${spec.slug}.png` : '');
  if (src) {
    return `<figure class="report-visual report-visual--image">\n  <img src="${escapeHtml(src)}" alt="${alt}">${caption}\n</figure>`;
  }
  const overlays = Array.isArray(spec.overlayText) ? spec.overlayText : [];
  const overlayHtml = overlays.map((t) => `    <li>${escapeHtml(t)}</li>`).join('\n');
  return `<figure class="report-visual report-visual--image" aria-label="${alt}">
  <svg viewBox="0 0 960 320" role="img" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="960" height="320" fill="${SPEC.colors.paper}"/><text x="480" y="60" text-anchor="middle" fill="${SPEC.colors.ink}" font-size="20" font-weight="700" font-family="'Noto Sans JP', sans-serif">Codex Image (${escapeHtml(spec.pattern || 'image')})</text><text x="480" y="170" text-anchor="middle" fill="${SPEC.colors.inkMuted}" font-size="16" font-family="'Noto Sans JP', sans-serif">${alt}</text></svg>
  <ul class="composite-overlay">
${overlayHtml}
  </ul>${caption}
</figure>`;
}

/** 決定論フォールバック (render を落とさない) */
function fallbackVisual(msg, caption) {
  const cap = caption ? `\n  <figcaption>${escapeHtml(caption)}</figcaption>` : '';
  return `<figure class="report-visual report-visual--fallback">\n  <svg viewBox="0 0 960 200" role="img" aria-label="placeholder" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="960" height="200" fill="${SPEC.colors.paper}"/><text x="480" y="105" text-anchor="middle" fill="${SPEC.colors.inkMuted}" font-size="18" font-family="'Noto Sans JP', sans-serif">${escapeHtml(msg)}</text></svg>${cap}\n</figure>`;
}

/** callouts[] → HTML (任意) */
function renderCallouts(callouts) {
  if (!Array.isArray(callouts) || callouts.length === 0) return '';
  return callouts
    .map((c) => {
      const kind = (c && c.kind) || 'note';
      return `  <aside class="report-callout report-callout--${escapeHtml(kind)}">${inlineMd((c && c.text) || '')}</aside>`;
    })
    .join('\n');
}

// ===== 1.1.0: 節内論理展開 / 構造化本文ブロック / 目次 =====

/** section.narrative (本質課題→解決→活用 / logic[]) → heading 直下の論理リード帯 */
function renderNarrative(narrative) {
  if (!narrative || typeof narrative !== 'object') return '';
  const cells = [];
  if (narrative.essence) cells.push(['本質課題', narrative.essence, 'essence']);
  if (narrative.approach) cells.push(['解決アプローチ', narrative.approach, 'approach']);
  if (narrative.leverage) cells.push(['どう活かすか', narrative.leverage, 'leverage']);
  let inner = '';
  if (cells.length) {
    inner = cells
      .map(([label, text, cls]) => `    <div class="report-narrative__cell report-narrative__cell--${cls}"><span class="report-narrative__label">${escapeHtml(label)}</span><span class="report-narrative__text">${inlineMd(text)}</span></div>`)
      .join('\n');
  } else if (Array.isArray(narrative.logic) && narrative.logic.length) {
    const roleLabel = { claim: '主張', evidence: '根拠', implication: '含意', action: '行動' };
    inner = narrative.logic
      .map((x) => `    <div class="report-narrative__cell"><span class="report-narrative__label">${escapeHtml(roleLabel[x && x.role] || (x && x.role) || '')}</span><span class="report-narrative__text">${inlineMd((x && x.text) || '')}</span></div>`)
      .join('\n');
  }
  if (!inner) return '';
  return `  <div class="report-narrative" role="note">\n${inner}\n  </div>`;
}

/** body[] (構造化ブロック配列) → HTML。table/code は counters で図表番号を採番 */
function renderBody(body, counters) {
  const blocks = Array.isArray(body) ? body : [];
  return blocks
    .map((b) => renderBlock(b, counters))
    .filter(Boolean)
    .join('\n');
}

/** 単一 body block → HTML (type で分岐・決定論) */
function renderBlock(b, counters) {
  if (!b || !b.type) return '';
  switch (b.type) {
    case 'paragraph':
      return `  <p>${renderSentenceHtml(b.text || '')}</p>`;
    case 'subheading': {
      const lv = b.level === 4 ? 4 : 3;
      return `  <h${lv} class="report-subheading">${inlineMd(b.text || '')}</h${lv}>`;
    }
    case 'bullet-list':
      return renderListBlock(b.items, 'ul');
    case 'ordered-list':
      return renderListBlock(b.items, 'ol');
    case 'table':
      return renderTableBlock(b, counters);
    case 'code':
      return renderCodeBlock(b, counters);
    case 'key-point':
      return renderKeyPoint(b);
    case 'stat-tile':
      return renderStatTile(b);
    case 'callout': {
      const variant = ['note', 'warning', 'tip', 'caution'].includes(b.variant) ? b.variant : 'note';
      const title = b.title ? `<strong class="report-callout__title">${inlineMd(b.title)}</strong> ` : '';
      return `  <aside class="report-callout report-callout--${variant}">${title}${inlineMd(b.text || '')}</aside>`;
    }
    case 'blockquote':
      return `  <blockquote class="report-quote">${inlineMd(b.text || '')}</blockquote>`;
    case 'definition-list':
      return renderDefinitionList(b);
    case 'footnote':
      return renderFootnotes(b);
    case 'task-list':
      return renderTaskList(b);
    default:
      return '';
  }
}

/** definition-list → <dl> (用語定義対 term↔definition・1.2.0) */
function renderDefinitionList(b) {
  const terms = Array.isArray(b.terms) ? b.terms : [];
  if (!terms.length) return '';
  const rows = terms
    .filter((t) => t && t.term)
    .map((t) => `    <dt>${inlineMd(String(t.term))}</dt>\n    <dd>${inlineMd(String(t.definition == null ? '' : t.definition))}</dd>`)
    .join('\n');
  if (!rows) return '';
  return `  <dl class="report-deflist">\n${rows}\n  </dl>`;
}

/** footnote → 脚注引用帯 (marker 自動採番 + citation・1.2.0) */
function renderFootnotes(b) {
  const notes = Array.isArray(b.footnotes) ? b.footnotes : [];
  if (!notes.length) return '';
  const lis = notes
    .filter((n) => n && (n.text || n.citation))
    .map((n, i) => {
      const reg = n.id ? _footnoteRegistry[n.id] : 0;
      let anchorId = '';
      let marker;
      let backlink = '';
      if (reg) {
        // id 付き: 文書レベル連番 + 係り先アンカー + 本文へ戻るリンク。
        anchorId = ` id="fn-${escapeHtml(n.id)}"`;
        marker = `<span class="report-footnotes__marker">[${reg}]</span> `;
        backlink = ` <a class="report-footnotes__back" href="#fnref-${escapeHtml(n.id)}" aria-label="本文へ戻る">↩</a>`;
      } else {
        marker = n.marker ? `<span class="report-footnotes__marker">${escapeHtml(String(n.marker))}</span> ` : `<span class="report-footnotes__marker">[${i + 1}]</span> `;
      }
      const cite = n.citation ? `<cite>${inlineMd(String(n.citation))}</cite>` : '';
      return `    <li${anchorId}>${marker}${inlineMd(String(n.text == null ? '' : n.text))}${cite}${backlink}</li>`;
    })
    .join('\n');
  if (!lis) return '';
  return `  <aside class="report-footnotes" role="doc-endnotes">\n    <ol>\n${lis}\n    </ol>\n  </aside>`;
}

/** task-list → 次アクションのチェックリスト (done でチェック状態・1.2.0) */
function renderTaskList(b) {
  const tasks = Array.isArray(b.tasks) ? b.tasks : [];
  if (!tasks.length) return '';
  const lis = tasks
    .filter((t) => t && t.text)
    .map((t) => {
      const done = t.done === true;
      const box = done
        ? '<span class="report-tasklist__box report-tasklist__box--done" aria-hidden="true">[x]</span>'
        : '<span class="report-tasklist__box" aria-hidden="true">[ ]</span>';
      const owner = t.owner ? `<span class="report-tasklist__owner">(${escapeHtml(String(t.owner))})</span>` : '';
      const state = done ? ' 完了' : ' 未完了';
      return `    <li class="${done ? 'is-done' : ''}"><span class="visually-hidden">${state}</span>${box}<span class="report-tasklist__text">${inlineMd(String(t.text))}</span>${owner}</li>`;
    })
    .join('\n');
  if (!lis) return '';
  return `  <ul class="report-tasklist" role="list">\n${lis}\n  </ul>`;
}

/** bullet-list / ordered-list → <ul>/<ol> (番号リストの順序保持) */
function renderListBlock(items, tag) {
  const arr = Array.isArray(items) ? items : [];
  if (!arr.length) return '';
  const lis = arr.map((i) => `    <li>${inlineMd(String(i))}</li>`).join('\n');
  return `  <${tag} class="report-list report-list--${tag}">\n${lis}\n  </${tag}>`;
}

/** table block → <table> (markdown 表が <br> で潰れる問題を解消・図表番号採番) */
function renderTableBlock(b, counters) {
  const headers = Array.isArray(b.headers) ? b.headers : [];
  const rows = Array.isArray(b.rows) ? b.rows : [];
  if (!headers.length && !rows.length) return '';
  const thead = headers.length
    ? `    <thead><tr>${headers.map((h) => `<th>${inlineMd(String(h))}</th>`).join('')}</tr></thead>\n`
    : '';
  const tbody = `    <tbody>${rows
    .map((r) => `<tr>${(Array.isArray(r) ? r : []).map((c) => `<td>${inlineMd(String(c))}</td>`).join('')}</tr>`)
    .join('')}</tbody>`;
  let cap = '';
  if (b.caption) {
    counters.table += 1;
    cap = `\n    <figcaption>表${counters.table}. ${escapeHtml(b.caption)}</figcaption>`;
  }
  return `  <figure class="report-table-wrap">\n    <table class="report-table">\n${thead}${tbody}\n    </table>${cap}\n  </figure>`;
}

/** code block → <pre><code> (フェンスドコードブロックのパース・言語ラベル/図表番号) */
function renderCodeBlock(b, counters) {
  const code = String(b.code == null ? '' : b.code);
  const lang = b.language ? `<span class="report-code__lang">${escapeHtml(b.language)}</span>` : '';
  let cap = '';
  if (b.caption) {
    counters.code += 1;
    cap = `\n    <figcaption>コード${counters.code}. ${escapeHtml(b.caption)}</figcaption>`;
  }
  return `  <figure class="report-code-wrap">${lang}\n    <pre class="report-code"><code>${escapeHtml(code)}</code></pre>${cap}\n  </figure>`;
}

/** key-point → 色付きハイライトボックス (要点の色付き強調・意匠 accent トーン流用) */
function renderKeyPoint(b) {
  const tone = ['accent', 'positive', 'caution', 'neutral'].includes(b.tone) ? b.tone : 'accent';
  const title = b.title ? `<div class="report-keypoint__title">${inlineMd(b.title)}</div>` : '';
  return `  <div class="report-keypoint report-keypoint--${tone}">${title}<div class="report-keypoint__body">${inlineMd(b.text || '')}</div></div>`;
}

/** stat-tile → 統計タイル群 (label/value/trend) */
function renderStatTile(b) {
  const stats = Array.isArray(b.stats) ? b.stats : [];
  if (!stats.length) return '';
  const glyph = { up: '▲', down: '▼', flat: '—' };
  const tiles = stats
    .map((s) => {
      const label = s && s.label ? `<span class="report-stat__label">${escapeHtml(s.label)}</span>` : '';
      const trend = s && s.trend ? `<span class="report-stat__trend report-stat__trend--${escapeHtml(s.trend)}">${glyph[s.trend] || ''}</span>` : '';
      const note = s && s.note ? `<span class="report-stat__note">${escapeHtml(s.note)}</span>` : '';
      return `    <div class="report-stat">${label}<span class="report-stat__value">${escapeHtml((s && s.value) || '')} ${trend}</span>${note}</div>`;
    })
    .join('\n');
  return `  <div class="report-stats">\n${tiles}\n  </div>`;
}

/** meta.toc=true 時、section heading から決定論的に目次を生成 */
function renderToc(sections) {
  const items = sections
    .filter((s) => s && s.heading)
    .map((s, i) => {
      const num = String(i + 1).padStart(2, '0');
      const id = s.id ? escapeHtml(s.id) : `section-${i + 1}`;
      return `      <li><a href="#${id}"><span class="report-toc__num">${num}</span>${escapeHtml(s.heading)}</a></li>`;
    })
    .join('\n');
  if (!items) return '';
  // details/summary にしてあるのは狭画面のため。狭い画面でも目次を追従させると
  // 本文の上に居座って可読域を食うので、読者が畳める必要がある。
  // open を既定にしてあるので、広い画面では従来どおり開いたまま出る。
  return `  <nav class="report-toc report-toc--sidebar" aria-label="目次">
    <details class="report-toc__box" open>
      <summary class="report-toc__title">目次</summary>
      <ol>
${items}
      </ol>
    </details>
  </nav>`;
}

/**
 * sticky sidebar TOC の scrollspy (report-uiux)。
 * 自己完結・再実行可能な controller として、初期 hash / TOC click / manual scroll /
 * hashchange / popstate / font-ready / print lifecycle を同じ activate 経路へ収束させる。
 * beforeprint で監視を停止し、afterprint で直前位置を復元して再起動する
 * (ハイライトは print CSS 側でも無効化する二重化)。
 */
/**
 * 追従ヘッダーの「現在節」と読了進捗を更新する。
 * scrollspy とは分けてある。あちらは sidebar TOC が前提で nav が無ければ即 return
 * するが、追従ヘッダーは目次を出さない文書でも要るため。
 */
function reportTopbarScript() {
  return `<script>
(function () {
  'use strict';
  // 狭画面では目次が本文の上に重なる。開いたままだと目次リンクで飛んだ見出しが
  // 目次の背後へ着地するので、既定で畳んでおく (開くのは読者の意思で)。
  var toc = document.querySelector('.report-toc__box');
  if (toc && window.matchMedia && window.matchMedia('(max-width: 900px)').matches) {
    toc.removeAttribute('open');
  }
  var here = document.querySelector('[data-report-here]');
  var bar = document.querySelector('[data-report-progress]');
  if (!here && !bar) return;
  var secs = Array.prototype.slice.call(document.querySelectorAll('.report-section[id]'));
  var frame = null;
  function sync() {
    frame = null;
    if (bar) {
      var doc = document.documentElement;
      var span = doc.scrollHeight - window.innerHeight;
      /* span<=0 は文書がビューポートに収まっている状態。0 除算を避けつつ
         「全部見えている = 100%」を出す。 */
      var ratio = span > 0 ? window.pageYOffset / span : 1;
      bar.style.width = Math.max(0, Math.min(1, ratio)) * 100 + '%';
    }
    if (here && secs.length) {
      /* 判定線を画面上部 28% に置く。上端 (0) だと節の境界で表示が
         ちらつき、中央だと見出しを読んでいるのに前の節が出続ける。 */
      var marker = Math.max(1, window.innerHeight * 0.28);
      var cur = secs[0];
      secs.forEach(function (s) { if (s.getBoundingClientRect().top <= marker) cur = s; });
      var h = cur.querySelector('h2');
      var text = h ? (h.textContent || '').trim() : '';
      if (text && here.textContent !== text) here.textContent = text;
    }
  }
  function onScroll() { if (frame === null) frame = window.requestAnimationFrame(sync); }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll, { passive: true });
  sync();
})();
</script>`;
}

function reportScrollspyScript() {
  return `<script>
(function () {
  'use strict';
  var CONTROLLER_KEY = '__slideReportScrollspy';
  if (window[CONTROLLER_KEY] && typeof window[CONTROLLER_KEY].destroy === 'function') {
    window[CONTROLLER_KEY].destroy(); /* script 再評価時も listener/observer を重複させない */
  }
  var nav = document.querySelector('.report-toc--sidebar');
  if (!nav) return;
  var links = Array.prototype.slice.call(nav.querySelectorAll('a[href^="#"]'));
  var map = {};
  var targets = [];
  function fragmentId(value) {
    try { return decodeURIComponent(String(value || '').replace(/^#/, '')); }
    catch (_) { return ''; }
  }
  links.forEach(function (a) {
    var id = fragmentId(a.getAttribute('href'));
    var el = document.getElementById(id);
    if (el) { map[id] = { link: a, target: el }; targets.push(el); }
  });
  if (!targets.length) return;
  var current = null;
  var restoreAfterPrint = null;
  var observer = null;
  var scrollFrame = null;
  var running = false;
  var printing = !!(window.matchMedia && window.matchMedia('print').matches);
  function activate(id) {
    if (current === id || !map[id]) return;
    current = id;
    links.forEach(function (a) { a.classList.remove('is-active'); a.removeAttribute('aria-current'); });
    map[id].link.classList.add('is-active');
    map[id].link.setAttribute('aria-current', 'location'); /* 現在位置を支援技術へ同期 (色非依存の第2チャネル) */
  }
  function syncFromScroll() {
    if (!running || printing) return;
    var marker = Math.max(1, window.innerHeight * 0.28);
    var candidate = targets[0];
    targets.forEach(function (target) {
      if (target.getBoundingClientRect().top <= marker) candidate = target;
    });
    activate(candidate.id);
  }
  function scheduleScrollSync() {
    if (scrollFrame !== null) return;
    scrollFrame = window.requestAnimationFrame(function () {
      scrollFrame = null;
      syncFromScroll();
    });
  }
  function syncFromLocation(reland) {
    var id = fragmentId(window.location.hash);
    if (!map[id]) return false;
    activate(id);
    if (reland) {
      window.requestAnimationFrame(function () {
        if (!printing && map[id]) {
          map[id].target.scrollIntoView({ block: 'start' });
          activate(id);
        }
      });
    }
    return true;
  }
  function start() {
    if (running || printing) return;
    running = true;
    window.addEventListener('scroll', scheduleScrollSync, { passive: true });
    if (typeof IntersectionObserver !== 'undefined') {
      observer = new IntersectionObserver(scheduleScrollSync, {
        rootMargin: '0px 0px -72% 0px', threshold: 0
      });
      targets.forEach(function (target) { observer.observe(target); });
    }
    if (!syncFromLocation(false)) syncFromScroll();
  }
  function stop() {
    if (!running) return;
    running = false;
    window.removeEventListener('scroll', scheduleScrollSync);
    if (observer) { observer.disconnect(); observer = null; }
    if (scrollFrame !== null) {
      window.cancelAnimationFrame(scrollFrame);
      scrollFrame = null;
    }
  }
  function onTocClick(event) {
    var id = fragmentId(event.currentTarget.getAttribute('href'));
    activate(id); /* default anchor navigation/hash update は維持し、active 状態だけ即時同期 */
  }
  function onHistoryNavigation() {
    if (!printing) window.requestAnimationFrame(function () { syncFromLocation(true); });
  }
  function onBeforePrint() {
    restoreAfterPrint = current;
    printing = true;
    stop();
  }
  function onAfterPrint() {
    printing = false;
    start();
    var id = fragmentId(window.location.hash);
    if (map[id]) activate(id);
    else if (restoreAfterPrint && map[restoreAfterPrint]) activate(restoreAfterPrint);
    else syncFromScroll();
    restoreAfterPrint = null;
  }
  function destroy() {
    stop();
    links.forEach(function (a) { a.removeEventListener('click', onTocClick); });
    window.removeEventListener('hashchange', onHistoryNavigation);
    window.removeEventListener('popstate', onHistoryNavigation);
    window.removeEventListener('beforeprint', onBeforePrint);
    window.removeEventListener('afterprint', onAfterPrint);
    if (window[CONTROLLER_KEY] === controller) delete window[CONTROLLER_KEY];
  }
  var controller = { start: start, stop: stop, destroy: destroy, sync: onHistoryNavigation };
  window[CONTROLLER_KEY] = controller;
  links.forEach(function (a) { a.addEventListener('click', onTocClick); });
  window.addEventListener('hashchange', onHistoryNavigation);
  window.addEventListener('popstate', onHistoryNavigation);
  window.addEventListener('beforeprint', onBeforePrint);
  window.addEventListener('afterprint', onAfterPrint);
  start();
  syncFromLocation(true); /* 初期 hash を observer の初回 callback より優先 */
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () {
      if (!printing && !syncFromLocation(true)) scheduleScrollSync();
    });
  }
})();
</scr` + `ipt>`;
}

/** meta.throughLine (+ throughLineParts) → 導入部の文書アーク帯 (本質課題→解決→活用の通し筋・1.2.0) */
function renderThroughLine(throughLine, parts) {
  const hasTL = throughLine && typeof throughLine === 'string' && throughLine.trim();
  const partList = Array.isArray(parts) ? parts.filter((p) => p && p.arc) : [];
  if (!hasTL && !partList.length) return '';
  const mainBand = hasTL
    ? `  <div class="report-throughline" role="note"><span class="report-throughline__label">通し筋</span><span class="report-throughline__text">${inlineMd(throughLine)}</span></div>`
    : '';
  if (!partList.length) return mainBand;
  // part 単位 sub-arc (大規模文書の道標)。
  const items = partList
    .map((p, i) => {
      const title = p.title ? inlineMd(String(p.title)) : `第${i + 1}部`;
      return `    <li class="report-throughline__part"><span class="report-throughline__part-title">${title}</span><span class="report-throughline__part-arc">${inlineMd(String(p.arc))}</span></li>`;
    })
    .join('\n');
  const partsBand = `  <ol class="report-throughline-parts" aria-label="部構成">\n${items}\n  </ol>`;
  return mainBand ? mainBand + '\n' + partsBand : partsBand;
}

/** section.transition → 節末の次節への橋渡し1文 (節間接続・1.2.0) */
function renderTransition(transition) {
  if (!transition || typeof transition !== 'string' || !transition.trim()) return '';
  return `  <p class="report-transition">${inlineMd(transition)}</p>`;
}

/**
 * report-structure オブジェクト → report.html 全文 (決定論)。
 * section は配列順でレンダ (readingOrder は視線方向ヒントであり並び替えキーではない)。
 * @param {object} structure report-structure.schema.json 準拠オブジェクト
 * @returns {string} 完結した HTML 文書
 */
export function renderReport(structure) {
  const meta = (structure && structure.meta) || {};
  const reportType = meta.reportType || 'internal-analysis';
  const accent = REPORT_TYPE_ACCENT[reportType] || 'accent-blue-vivid';
  const title = escapeHtml(meta.title || 'レポート');
  const sections = Array.isArray(structure && structure.sections) ? structure.sections : [];

  // 1.2.0: footnote インライン係り先アンカーの文書レベルレジストリを本文レンダ前に構築する。
  _footnoteRegistry = buildFootnoteRegistry(sections);
  _emittedFnrefs = new Set();

  let usesMermaid = false;
  const counters = { fig: 0, table: 0, code: 0 }; // 図表番号の決定論採番 (1.1.0)
  const sectionHtml = sections
    .map((sec, idx) => {
      const heading = escapeHtml((sec && sec.heading) || '');
      const secNum = String(idx + 1).padStart(2, '0');
      const secAccent = REPORT_TYPE_ACCENT[(sec && sec.reportType) || reportType] || accent;
      // 各見出しに図解を 1 つ用意する。明示 visual があればそれを使い、
      // 無い節だけ本文の構造から導出する (導出できなければ図解なしで進む)。
      // visual.kind === 'none' は「この節に図解は要らない」という明示の指定なので、
      // 導出で埋めない。指定が無い節 (visual 自体が無い) だけ導出の対象にする。
      const visualOptOut = !!(sec && sec.visual && sec.visual.kind === 'none');
      let vis = renderVisual(sec && sec.visual, counters);
      if (!vis.html && !visualOptOut) vis = renderDerivedVisual(sec, counters);
      if (vis.usesMermaid) usesMermaid = true;
      const narrative = renderNarrative(sec && sec.narrative);
      // body[] 優先・排他 (1.1.0)。存在すれば paragraphs[] を無視。無ければ paragraphs[] (1.0.0 後方互換)
      const bodyHtml = Array.isArray(sec && sec.body) && sec.body.length
        ? renderBody(sec.body, counters)
        : renderParagraphs(sec && sec.paragraphs);
      const callouts = renderCallouts(sec && sec.callouts);
      const idAttr = sec && sec.id ? ` id="${escapeHtml(sec.id)}"` : '';
      const roleAttr = sec && sec.role ? ` data-role="${escapeHtml(sec.role)}"` : '';
      const layout = (sec && sec.visual && sec.visual.layout) || {};
      // readingOrder: section 直下 (1.1.0) を優先し、無ければ placement へ移設された layout.readingOrder (1.2.0)
      const readingOrder = (sec && sec.readingOrder) || layout.readingOrder;
      const orderAttr = readingOrder ? ` data-reading-order="${escapeHtml(readingOrder)}"` : '';
      // emphasisZone (1.2.0) を優先し emphasis (1.1.0 deprecated alias) へ後方互換フォールバック
      const emphasis = (layout.emphasisZone && layout.emphasisZone !== 'normal' ? layout.emphasisZone : '') || (layout.emphasis && layout.emphasis !== 'normal' ? layout.emphasis : '');
      const emphAttr = emphasis ? ` data-emphasis="${escapeHtml(emphasis)}"` : '';
      // focalPoint (1.2.0): placement へ移設された focal を優先し section 直下へ後方互換フォールバック。
      // readingOrder と同じく視覚配置ヒントとして data 属性 + CSS var で live 露出する (dead field 化を防ぐ)。
      const focal = layout.focalPoint || (sec && sec.focalPoint);
      const hasFocal = focal && (typeof focal.x === 'number' || typeof focal.y === 'number');
      const fx = hasFocal && typeof focal.x === 'number' ? focal.x : 50;
      const fy = hasFocal && typeof focal.y === 'number' ? focal.y : 50;
      const focalAttr = hasFocal ? ` data-focal="${fx},${fy}"` : '';
      const focalVar = hasFocal ? ` --focal: ${fx}% ${fy}%;` : '';
      // 意味的配置 (1.1.0): grid が 2 列 (例 '2x1') かつ visual があれば本文と図を左右分割。無ければ従来の縦積み
      const twoCol = typeof layout.grid === 'string' && /^2x/.test(layout.grid) && vis.html;
      let inner;
      if (twoCol) {
        // 2 列でも図解を先 (左) に置く。横組みの視線は左から入るので、
        // 縦積みの「図解 → 本文」と同じ順序が保たれる。狭画面では 1 列へ
        // 落ちる (CSS) が、そのときも DOM 順のまま図解が先に来る。
        inner = `${narrative ? narrative + '\n' : ''}  <div class="report-grid report-grid--2col">
    <div class="report-grid__visual">${vis.html}</div>
    <div class="report-grid__prose">
${bodyHtml}
${callouts ? callouts + '\n' : ''}    </div>
  </div>`;
      } else {
        // 縦積みは「図解 → 本文」の順に置く。
        // 読者はまず図で全体像を掴み、そこで分からなかった箇所だけを本文で補う。
        // 逆順 (本文 → 図) だと、読者は全体像を持たないまま文章を頭から処理する
        // ことになり、図に辿り着く頃には本文で組み立てた理解と図の構造を
        // 突き合わせ直す二度手間が生じる。
        // narrative (本質課題→解決→活用のリード帯) は図の意味を先に規定する
        // 見出しの一部なので、図より前に置く。
        inner = `${narrative ? narrative + '\n' : ''}  ${vis.html}
${bodyHtml}
${callouts ? callouts + '\n' : ''}`;
      }
      const transition = renderTransition(sec && sec.transition);
      return `<section class="report-section"${idAttr}${roleAttr}${orderAttr}${emphAttr}${focalAttr} style="--section-accent: var(--${secAccent});${focalVar}">
  <h2 data-secnum="${secNum}">${heading}</h2>
${inner}${transition ? '\n' + transition : ''}
</section>`;
    })
    .join('\n');

  // 目次は既定 ON。読み物として成立させるには「全体像」と「任意の節へ飛べる手段」が
  // 常に要る。節が 1 つしかない文書だけは目次が情報を足さないので出さない。
  // 明示的に meta.toc:false を書いた文書のみ従来どおり非表示にする。
  const wantToc = meta.toc !== false && sections.length >= 2;
  const tocHtml = wantToc ? renderToc(sections) : '';
  const throughLineHtml = renderThroughLine(meta.throughLine, meta.throughLineParts);

  // meta 行 (schema 準拠: audience/keyMessage/author/length。date/reader は無い)
  const metaBits = [];
  metaBits.push(`<span class="report-type-badge">${escapeHtml(reportTypeLabel(reportType))}</span>`);
  if (meta.audience) metaBits.push(`<span>読者: ${escapeHtml(meta.audience)}</span>`);
  if (meta.author) metaBits.push(`<span>著者: ${escapeHtml(meta.author)}</span>`);
  if (meta.length) metaBits.push(`<span>分量: ${escapeHtml(lengthLabel(meta.length))}</span>`);
  if (meta.createdAt) metaBits.push(`<span>作成: ${escapeHtml(meta.createdAt)}</span>`);
  // 文書メタ (1.2.0): version/updatedDate/readingTime
  if (meta.version) metaBits.push(`<span class="report-meta__doc">版: ${escapeHtml(meta.version)}</span>`);
  if (meta.updatedDate) metaBits.push(`<span class="report-meta__doc">更新: ${escapeHtml(meta.updatedDate)}</span>`);
  if (meta.readingTime) metaBits.push(`<span class="report-meta__doc">読了目安: ${escapeHtml(meta.readingTime)}</span>`);

  const subtitle = meta.subtitle ? `\n    <p class="report-subtitle">${escapeHtml(meta.subtitle)}</p>` : '';
  const keyMessage = meta.keyMessage ? `\n    <p class="report-keymessage">${escapeHtml(meta.keyMessage)}</p>` : '';

  const head = [
    '<!DOCTYPE html>',
    '<html lang="' + escapeHtml(meta.language || 'ja') + '">',
    '<head>',
    '<meta charset="UTF-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
    '<meta name="generator" content="slide-report-generator/render-report">',
    `<meta name="report-type" content="${escapeHtml(reportType)}">`,
    `<meta name="theme-name" content="${escapeHtml(themeName(structure && structure.theme))}">`,
    `<title>${title}</title>`,
    `<style>\n${buildReportCss(SPEC)}\n</style>`,
    usesMermaid ? mermaidInitScript() : '',
    '</head>',
  ]
    .filter(Boolean)
    .join('\n');

  // report-uiux: screen は sidebar(TOC)+本文カラムの grid、print/狭画面は CSS 側で block へ degrade。
  // TOC が無ければ --no-toc で本文 1 カラム中央寄せ。
  const sidebarHtml = tocHtml ? `  <aside class="report-sidebar">\n${tocHtml}\n  </aside>\n` : '';
  const layoutClass = tocHtml ? 'report-layout' : 'report-layout report-layout--no-toc';
  const scrollspy = tocHtml ? reportScrollspyScript() : '';

  // 追従ヘッダー。現在節 (__here) と読了進捗 (__progress) は scrollspy が更新する。
  // JS が動かない環境でも文書名だけは出るよう、初期値をサーバ側で埋めておく。
  const topbarHtml = `<header class="report-topbar">
  <span class="report-topbar__progress" data-report-progress></span>
  <span class="report-topbar__title">${title}</span>
  <span class="report-topbar__sep" aria-hidden="true">›</span>
  <span class="report-topbar__here" data-report-here>${escapeHtml(
    (sections[0] && sections[0].heading) || '',
  )}</span>
</header>
`;

  return `${head}
<body style="--report-accent: var(--${accent});">
${topbarHtml}<div class="${layoutClass}">
${sidebarHtml}  <main class="report">
  <header class="report-header">
    <h1 class="report-title">${title}</h1>${subtitle}${keyMessage}
    <div class="report-meta">
      ${metaBits.join('\n      ')}
    </div>
  </header>
${throughLineHtml ? throughLineHtml + '\n' : ''}${sectionHtml}
  <footer class="report-footer">slide-report-generator · report mode · theme: ${escapeHtml(themeName(structure && structure.theme))}</footer>
  </main>
</div>
${scrollspy}
${reportTopbarScript()}
</body>
</html>
`;
}

/** reportType enum → 日本語ラベル (§D) */
function reportTypeLabel(rt) {
  return (
    {
      'internal-analysis': '社内報告分析',
      'client-proposal': '顧客提案',
      'tech-doc': '技術ドキュメント',
      learning: '学習解説',
    }[rt] || rt
  );
}

/** length enum → 日本語ラベル */
function lengthLabel(len) {
  return { brief: '短報', standard: '標準', deep: '精読' }[len] || len;
}

// ---- CLI ----
// 決定表 (visual-derivation-table.json) の実行結果を行単位で検査できるよう導出器を
// 公開する。表が正本であることは「どの入力でどの行が引かれたか」を機械で確かめられて
// 初めて主張できる。既存の renderReport export はそのまま。
export { deriveVisualFromBody };

function isMain() {
  return process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
}

if (isMain()) {
  const [inPath, outPath] = process.argv.slice(2);
  if (!inPath || !outPath) {
    console.error('usage: node render-report.js <report-structure.json> <out.html>');
    process.exit(2);
  }
  try {
    const structure = JSON.parse(readFileSync(inPath, 'utf-8'));
    const html = renderReport(structure);
    writeFileSync(outPath, html, 'utf-8');
    console.log(`render-report: wrote ${outPath} (${Buffer.byteLength(html)} bytes, ${(structure.sections || []).length} sections)`);
  } catch (e) {
    console.error(`render-report error: ${e.message}`);
    process.exit(1);
  }
}
