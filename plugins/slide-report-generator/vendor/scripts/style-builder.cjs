/**
 * style-builder.js — SR-ID 駆動 CSS 動的生成
 *
 * 入力: spec-values（spec-registry.md から固定化した値オブジェクト）
 * 出力: styles.css 全文（pagination.css を結合）
 *
 * 単位は vw / rem / mm のみ（SR-1-04, px 禁止）。
 */
'use strict';

const fs = require('fs');
const path = require('path');

/**
 * 寸法・書体・密度の契約を読む。
 *
 * ここが値を持たないことが要点。以前は frame-contract.json の値 (fontScale 下限・
 * engine の書体下限) を定数やリテラルで手写ししており、JSON を直しても生成 CSS が
 * 1 バイトも変わらなかった。写した側は必ず取り残されるので、契約は起動時に 1 回だけ
 * 読み、以降はこのオブジェクトだけを参照する。
 *
 * 読めなければ例外で落とす (fail-closed)。フォールバック値をここへ書くと、
 * その値がもう 1 つの正本になり、写経が再発する。
 */
const CONTRACT_PATH = path.resolve(__dirname, '..', '..', 'assets', 'slide-templates', 'frame-contract.json');
const CONTRACT = (() => {
  let raw;
  try {
    raw = fs.readFileSync(CONTRACT_PATH, 'utf8');
  } catch (e) {
    throw new Error(`[style-builder] frame-contract.json を読めない (${CONTRACT_PATH}): ${e.message}`);
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    throw new Error(`[style-builder] frame-contract.json を JSON として解釈できない (${CONTRACT_PATH}): ${e.message}`);
  }
  for (const key of ['typography', 'fill_policy', 'spacing']) {
    if (!parsed[key] || typeof parsed[key] !== 'object') {
      throw new Error(`[style-builder] frame-contract.json に ${key} が無い (${CONTRACT_PATH})`);
    }
  }
  return parsed;
})();

/** 契約から必ず値を取る。欠けていたら落とす (既定値で埋めない) */
function contractNumber(section, key) {
  const v = CONTRACT[section] && CONTRACT[section][key];
  if (typeof v !== 'number' || !Number.isFinite(v)) {
    throw new Error(`[style-builder] frame-contract.json の ${section}.${key} が数値でない`);
  }
  return v;
}

/**
 * fontScale の下限。導出と実測は frame-contract.json typography.note_min_font_scale にある。
 * ここは値を持たず契約を引くだけ。
 */
const MIN_FONT_SCALE = contractNumber('typography', 'min_font_scale');

/**
 * engine 経路の書体下限 (rem)。導出は frame-contract.json typography.note_engine。
 * clamp の下側と .code-block / .code-panel pre の font-size はこの 1 値だけを使う。
 */
const MIN_REM_ENGINE = contractNumber('typography', 'min_rem_engine');

/**
 * spec-registry.md の値を一元管理（SR-ID 対応コメント付き）
 */
const SPEC = {
  // §1 寸法・単位
  aspectRatio: '16 / 9', // SR-1-01
  aspectRatioNum: '16 / 9', // 同じ比を calc() の乗数として使う (SR-1-01)
  aspectRatioInvNum: '9 / 16', // その逆数。calc() は連続する除算を掛け算に畳めないため別に持つ
  printWidth: '297mm', // SR-1-03
  printHeight: '210mm',
  // §2 カラー — インク・オン・ペーパー (visual-generation-rules.md VGCONST_001 / VGCONST_002)
  //
  // 面に置いてよい色は 3 値だけ。紙 (地)・インク (文字・罫・反転面の地)・反転面の文字
  // (= 紙と同値) で、色相による意味づけ (種類ごとに色を割り当てる・連番で色を配る) は
  // 行わない。強調は色相ではなく反転ブロック (E4) で作る。
  //
  // inkMuted / hairline は新しい色ではなくインクの濃度で、紙の上へインクを alpha で
  // 重ねた solid。半透明のまま置かないのは、印刷経路と画像化経路で合成結果が環境依存に
  // なるため。値は下の assertDensity() が式と突き合わせるので、片方だけ書き換えると落ちる。
  //
  // tone1..3 は VGCONST_002 が図解の内部にだけ許す単一色相の濃度段。彩度 S15-30%・3 段。
  // 図解の従属関係を表すためだけに使い、面の地・文字・部材には使わない。
  colors: {
    paper: '#F7F6F3',
    ink: '#141412',
    inkMuted: '#6A6A68', // ink 62% on paper
    hairline: '#D5D4D1', // ink 15% on paper
    tone1: '#E1E6EA', // H210 S18% L90%
    tone2: '#9BADBF', // H210 S22% L68%
    tone3: '#4B6681', // H210 S26% L40%
  },
  // §3 フォント — SR-3-02..03
  fontScale: 1.3,
  fonts: {
    base: "'Noto Sans JP', sans-serif",
    mono: "'SF Mono', 'Fira Code', monospace",
  },
  /**
   * §3 型階層 — 天井 1 本 + 段差 2 種だけで作る単一系列 (E2 / VGCONST_007 / VGCONST_010)
   *
   * leadRem は面の第 1 位の基準値で、--font-scale を掛けた結果が
   * 「stage 高さの 10%」(VGCONST_010 の天井) を超えないことが条件。
   * 面座標では root font-size = 1.6 * --sv なので 10 --sv = 6.25rem にあたる。
   * 4.6rem * fontScale 1.3 = 5.98rem = stage 高さの 9.57% で天井の内側。
   *
   * 以降は 2 種類の段差だけで下ろす。stepMajor は順位を作る段 (lead -> heading -> body)、
   * stepMinor は同じ順位内の弱い区別 (body -> label)。中間比を発明しない。
   * これにより隣接比は常に E2 の下限 (1.50 / 1.15) を満たす。
   *
   * 最小の基準値は lead / (major^2 * minor) = 1.4069rem で、
   * これに frame-contract の min_font_scale を掛けた 1.5757rem が
   * min_rem_engine (1.5625rem) を上回る = 床を下げていない。
   */
  typeScale: {
    leadRem: 4.6,
    stepMajor: 1.667, // 体系比 0.60 の逆数。E2 の lead -> body 下限 1.50 を必ず満たす
    stepMinor: 1.176, // 体系比 0.85 の逆数。E2 の body -> label 下限 1.15 を必ず満たす
  },
  // §1-06 スペーシング
  spacing: ['0.25rem', '0.5rem', '0.75rem', '1rem', '1.5rem', '2rem', '3rem', '4rem', '6rem'],
  // §6 GSAP
  // §7 印刷
  // §8 ナビ
  navTopPadding: '4rem',
  navArrowPadding: '3rem',
  navBottomPadding: '5rem',
};

/**
 * inkMuted / hairline が「インクの濃度」であることを式で確かめる。
 *
 * この 2 値は独立した色ではなく、紙の上にインクを alpha で重ねた結果を solid に
 * 焼いたもの。手で書いた 16 進はいつでもずれるので、定義と式が食い違ったら
 * 生成前に落とす。VGCONST_001 の「面の色数 3」は、この 2 値が新しい色相を
 * 持ち込まないことに依存している。
 */
function composite(inkHex, paperHex, alpha) {
  const ch = (hex, i) => parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16);
  const out = [0, 1, 2].map((i) => Math.round(ch(inkHex, i) * alpha + ch(paperHex, i) * (1 - alpha)));
  return `#${out.map((v) => v.toString(16).toUpperCase().padStart(2, '0')).join('')}`;
}

(function assertDensity() {
  const c = SPEC.colors;
  const cases = [
    ['inkMuted', c.inkMuted, 0.62],
    ['hairline', c.hairline, 0.15],
  ];
  for (const [name, value, alpha] of cases) {
    const expected = composite(c.ink, c.paper, alpha);
    if (value.toUpperCase() !== expected) {
      throw new Error(
        `[style-builder] colors.${name}=${value} は ink ${alpha * 100}% on paper (${expected}) と一致しない。` +
          `濃度は式で決まる値なので、片方だけ書き換えてはいけない。`
      );
    }
  }
})();

function buildRootVars(spec) {
  const c = spec.colors;
  return `:root {
  /* §1 単位・基準 */
  --aspect-ratio: ${spec.aspectRatio};

  /* 版面 (stage) の実寸。意匠は 16:9 で定義されている (canvas 1280x720、
     frame-contract の type_area_ratio 0.770 = 1152x616 / 1280x720) ので、
     画面の縦横比に追随させず常に 16:9 を保ち、余った方向へ帯を出す。
     min() 1 本なので上限・下限の分岐は無い。画面が横長なら幅が、縦長なら
     高さが律速する。build-deck-html.js の .slide-area と同じ作法。 */
  --stage-w: min(100vw, calc(100vh * ${spec.aspectRatioNum}));
  --stage-h: calc(var(--stage-w) * ${spec.aspectRatioInvNum});
  /* 版面内で使う長さの基準。--su は stage 幅の 1%、--sv は stage 高の 1%。
     16:9 の画面では stage = 画面なので、それぞれ 1vw / 1vh と完全に一致する。
     版面の中身はこの 2 つ (と rem) だけで書き、vw / vh を直接参照しない。
     そうして初めて stage 内部の見え方が全画面で同一になり、契約の
     type_area_ratio 0.770 や fill_policy の充填レンジが「固定値」として成立する。 */
  --su: calc(var(--stage-w) / 100);
  --sv: calc(var(--stage-h) / 100);

  /* §2 インク・オン・ペーパー (VGCONST_001)。面に出る色はこの 3 値だけ */
  --paper: ${c.paper};
  --ink: ${c.ink};
  --paper-on-ink: ${c.paper};

  /* インクの濃度 (新しい色ではない)。導出は SPEC.colors のコメントと assertDensity() */
  --fg-muted: ${c.inkMuted};
  --hairline: ${c.hairline};

  /* 地と文字の別名。この 2 つが面の既定で、外部 (pagination.css / ひな形 /
     render-slide.cjs) もこの名前で参照している。値は上の紙とインクそのもの。 */
  --bg-dark: var(--paper);
  --fg: var(--ink);
  --fg-dim: var(--fg-muted);

  /* §2 反転ブロック (E4)。本規約における唯一のアクセント手段で、色相では作らない。
     面にちょうど 1 個・stage 面積比 0.08-0.15。幅いっぱいの帯なら面積比は高さ比に
     等しいので、下の --accent-h-min / --accent-h-max がその条件をそのまま表す。
     帯でない反転ブロックの面積は検査器が実測で見る。 */
  --accent-bg: var(--ink);
  --accent-fg: var(--paper-on-ink);
  --accent-h-min: calc(8 * var(--sv));
  --accent-h-max: calc(15 * var(--sv));

  /* §2 濃度段 (VGCONST_002)。図解の内部だけで使う単一色相の 3 段。
     面の地・文字・部材には使わない (使うと面の色数が 3 を超える)。 */
  --tone-1: ${c.tone1};
  --tone-2: ${c.tone2};
  --tone-3: ${c.tone3};

  /* §2 罫 (VGCONST_003)。影は使わず、区切りはこの 1 本だけで表す。
     px で持つのは、罫の太さが面の大きさではなく画面の解像度に対する量だから。
     面単位 (--su) で持つと小さい観測点で 0.2px 以下へ落ちて消える。 */
  --rule-hair: 0.75px;
  --rule-solid: 1px;

  /* §2 角丸 (VGCONST_003)。0 が既定で、ラスタ端が地とぶつかる写真・図版だけ 2px */
  --radius: 0;
  --radius-figure: 2px;

  /* §3 フォント (SR-3-01..03) */
  --font-scale: ${spec.fontScale};
  --font-base: ${spec.fonts.base};
  --font-mono: ${spec.fonts.mono};
  /* 型階層は天井 1 本と段差 2 種だけの単一系列。ここが唯一の定義で、
     個別の面が rem を直に書かない (書いた瞬間に系列が 2 本になる)。 */
  --fs-lead: calc(${spec.typeScale.leadRem}rem * var(--font-scale));
  --fs-heading: calc(var(--fs-lead) / ${spec.typeScale.stepMajor});
  --fs-body: calc(var(--fs-heading) / ${spec.typeScale.stepMajor});
  --fs-label: calc(var(--fs-body) / ${spec.typeScale.stepMinor});

  /* §3 ウェイト 3 段 (VGCONST_005)。700 は 1 面に 1 箇所 (面の第 1 位) */
  --fw-body: 400;
  --fw-label: 500;
  --fw-lead: 700;

  /* §3 字間 (VGCONST_006) */
  --ls-lead: -0.02em;
  --ls-body: 0;
  --ls-label: 0.1em;

  /* §3 行送り。群と群の間隔はこの行送りの整数倍で取る (VGCONST_009)。
     面ごとに新しい間隔値を発明しないための単位固定。 */
  --lh-body: 1.6;
  --gap-line: calc(var(--fs-body) * var(--lh-body));
  --gap-group: var(--gap-line);
  --gap-section: calc(var(--gap-line) * 2);

  /* §1-06 spacing scale */
${spec.spacing.map((v, i) => `  --space-${i + 1}: ${v};`).join('\n')}

  /* §8 ナビ余白 */
  --nav-top-padding: ${spec.navTopPadding};
  --nav-arrow-padding: ${spec.navArrowPadding};
  --nav-bottom-padding: ${spec.navBottomPadding};
  /* 浮遊ページネーション UI が実際に占める領域。各値は下の .pg-* 定義と対で、
     ここを変えずに .pg-* の位置だけ動かすと本文が下に潜り込む。
       下: pg-controls (bottom 4vh + btn 5vh) と pg-dots (bottom 1.6vh + dot 域) の外側
       右: pg-controls (right 1.6vw + btn 5vh)
       上: pg-counter (top 1.6vh + 高さ) / pg-section-nav */
  --pg-reserve-bottom: calc(calc(4 * var(--sv)) + calc(5 * var(--sv)) + calc(1.2 * var(--sv)));
  --pg-reserve-side: calc(calc(1.6 * var(--su)) + calc(5 * var(--sv)) + calc(1.2 * var(--sv)));
  --pg-reserve-top: calc(calc(1.6 * var(--sv)) + calc(4.2 * var(--sv)) + calc(1.2 * var(--sv)));
}
`;
}

function buildBase() {
  return `
/* ===== Reset & Base ===== */
* { box-sizing: border-box; margin: 0; padding: 0; }
/* 根を 1vw だけで決めると、書体は幅に、面の高さ (100vh から --pg-reserve-* を
   引いた残り) は高さに連動するので、画面の縦横比が変わるたびに縦の予算だけが
   置いていかれる。実測で 1440x900 -> 1920x1080 は幅 1.333 倍に対し有効高が
   745 -> 893px の 1.198 倍しかなく、字だけが 11% 大きくなって外側余白を食い、
   1920 でだけ slide-title の h1 が溢れ slide4/6/7 の L9 が割れていた。
   根を stage の実寸に置くと、この不整合は原理的に消える。stage は常に 16:9 な
   ので幅と高さは連動して動き、字も入れ物も同じ倍率で拡縮する。画面 (vw / vh)
   ではなく版面を基準にする、というのが要点で、画面の縦横比が何であれ stage
   内部の見え方は変わらない。個別の面に px を足すのではなく、単位系の側で揃える。
   係数を stage 高さの 1.6% に取るのは、これが min(1vw, 1.6vh) が 16:9 の画面で
   選んでいた値そのもの (1920x1080 で 17.28px) だからで、既存の実測値を動かさずに
   基準だけを画面から版面へ移せる。16:9 では stage 幅の 0.9% にも等しい。 */
html, body { width: 100%; height: 100%; background: var(--bg-dark); color: var(--fg); font-family: var(--font-base); font-size: calc(1.6 * var(--sv)); line-height: 1.6; }

/* ===== 3層構造 (SR-4-01) ===== */
/* .slider は画面いっぱいの器で、その中央へ 16:9 の stage を置く。画面が
   16:9 でなければ余った方向に帯が出る (レターボックス / ピラーボックス)。
   PowerPoint / Keynote / Google Slides と同じ挙動で、意匠を画面の形へ
   作り直さない。帯は .slider の地色で、stage の外側なので L9 の外側余白
   (region = stage) には数えられない。 */
.slider { position: relative; width: 100vw; height: 100vh; overflow: hidden; display: flex; align-items: center; justify-content: center; }
.slide-area { position: relative; width: var(--stage-w); height: var(--stage-h); aspect-ratio: var(--aspect-ratio); margin: auto; }
.slider__container { position: relative; width: 100%; height: 100%; aspect-ratio: var(--aspect-ratio); }
.slider__item {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  /* SR-4-02。浮遊 UI (pg-controls / pg-dots / pg-counter) は position:fixed で
     vh・vw 指定、一方この逃げは rem 固定だった。単位系が違うため画面の縦横比が
     変わると必ずどこかで衝突し、実測では 1440x900 で送りボタンと図解が
     556px² 重なった。max() で「rem の意匠」と「浮遊 UI の占有域」の大きい方を
     取り、どの比率でも重ならないことを保証する。 */
  padding:
    max(var(--nav-top-padding), var(--pg-reserve-top))
    max(var(--nav-arrow-padding), var(--pg-reserve-side))
    max(var(--nav-bottom-padding), var(--pg-reserve-bottom));
  opacity: 0; visibility: hidden;
  display: flex; flex-direction: column;
  background: var(--bg-dark);
}
.slider__item.is-active { opacity: 1; visibility: visible; }
/* justify-content: center は伸長ではなく配置。内容高は一切変わらず、残余高さの
   置き場所だけが上下へ分かれる。既定の flex-start では残余が必ず下へ偏り、
   frame-contract.json vertical_margin_policy.max_symmetry_delta (0.02) を
   構造的に満たせない。しかも上詰めは内容量と無関係なので、CONST_008 が許す
   直し方 (面の統合・分割、項目の増減) では動かせず、規約内に解の無い検査に
   なってしまう。CONST_008 の「残余は群の外側余白として残す」を既定で満たす。
   fill_policy.note_antipattern が禁じる伸長 (flex: 1 1 0 /
   grid-auto-rows: 1fr / align-content: stretch) とは別物で、充填率は動かない。
   safe を付けるのは、内容が面より高い面 (fill_policy 上限超え) で素の center を
   使うと溢れが上下へ二分され、上側の溢れが chrome の予約帯 (pg-counter /
   pg-progress) へ食い込んで L1 衝突・L2 はみ出しを新たに作るため。safe は
   溢れているときだけ flex-start へ退避するので、収まっている面だけが中央寄せに
   なる。溢れ自体は L3 と fill_policy 上限で別途落とす。 */
.slider__content { width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: safe center; gap: var(--space-4); }

/* ===== 共通見出し (SR-3-08) =====
   4 つの型トークンをそのまま役割へ割り当てる。h1 と h2 が同じウェイト (旧 800/700)
   だと順位が字の大きさだけで作られ、面を縮小したとき最初に消える差になる。
   700 は面の第 1 位に 1 箇所 (VGCONST_005) なので、h2 以下は 500 と 400 で下ろす。
   h3 は h2 の下位だが型は body と同じにし、区別はウェイトと字間で付ける。
   ここで新しい段を作ると系列が 2 本になる (T3 が統合した理由そのもの)。 */
.slider__item h1 { font-size: var(--fs-lead); font-weight: var(--fw-lead); line-height: 1.2; letter-spacing: var(--ls-lead); }
.slider__item h2 { font-size: var(--fs-heading); font-weight: var(--fw-label); line-height: 1.3; letter-spacing: var(--ls-lead); }
.slider__item h3 { font-size: var(--fs-body); font-weight: var(--fw-label); line-height: 1.35; letter-spacing: var(--ls-body); }
.slider__item p { font-size: var(--fs-body); font-weight: var(--fw-body); letter-spacing: var(--ls-body); }
.text-note { font-size: var(--fs-label); color: var(--fg-muted); letter-spacing: var(--ls-label); -webkit-line-clamp: 3; line-clamp: 3; } /* SR-4-06, SR-9-04 */

/* ===== :focus-visible (SR-9-02) ===== */
:focus-visible { outline: calc(0.3 * var(--sv)) solid var(--ink); outline-offset: calc(0.2 * var(--sv)); }

/* ===== sr-only ===== */
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
`;
}

function buildSlideTypes() {
  return `
/* ===== slide-title ===== */
.slide-title { justify-content: center; align-items: center; text-align: center; }
/* slide-hero h1 と同じ理由。行送り 1.2 (.slider__item h1 の既定) はこの書体の
   字面 (実測で約 1.32em) より狭く、行ボックスから溢れる。1440x900 では丸めで
   隠れていたが 1920x1080 では 15px 露出した (根が 19.2px へ上がり字面も比例して
   伸びるのに対し、面の高さは 745->893 の 1.2 倍しか伸びないため)。章扉なので
   縦の余りは十分あり、字を小さくせず行送りを字面へ合わせる。 */
.slide-title h1 { font-size: var(--fs-lead); margin-bottom: var(--space-4); line-height: 1.35; }
.slide-title .subtitle { font-size: var(--fs-heading); font-weight: var(--fw-body); color: var(--fg-muted); }

/* ===== slide-message (SR-3-08) ===== */
.slide-message { justify-content: center; align-items: center; text-align: center; }
/* この面は主張が 1 つだけなので、第 1 位は h2 ではなく main-message の側にある。
   見出しはその上に置くラベルとして扱い、順位を取り違えない (VGCONST_005)。 */
.slide-message h2 { font-size: var(--fs-label); font-weight: var(--fw-label); letter-spacing: var(--ls-label); margin-bottom: var(--space-3); color: var(--fg-muted); }
.slide-message .main-message { font-size: var(--fs-heading); font-weight: var(--fw-lead); letter-spacing: var(--ls-lead); line-height: 1.4; }

/* ===== slide-list =====
   カードをやめて行に戻した面。旧版は 1 項目ごとに「地色 + 左の色帯 + 角丸 + 影」の
   4 つを重ねており、VGCONST_008 (1 情報 1 装飾) に対して装飾が 4 倍あった。しかも
   色帯は 5 項目で 5 色を巡回するので、意味の無いところに意味があるように見える。
   区切りは項目間の罫 1 本だけにする (VGCONST_003)。地は紙のままで、囲わない。 */
.slide-list h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.slide-list .list { display: flex; flex-direction: column; gap: 0; width: 100%; }
.slide-list .list-item {
  width: 100%; box-sizing: border-box; /* SR-4-05 */
  padding: var(--space-3) 0;
  border-bottom: var(--rule-hair) solid var(--hairline);
  font-size: var(--fs-body);
  /* 段組みを縦から横へ変えている。縦だと i (Font Awesome) が 1 行を占有するが、
     アイコンは ::before の content なのでテキストノードが無く、L8-ink の走査に
     一切数えられない。つまり 1 項目あたり約 43px の「インクの無い高さ」が積まれ、
     4 項目で面が 47px 溢れて chrome 帯 (pg-controls) に食い込みつつ、面積比だけ
     90.6% に見えて中身は 14.5% という状態になっていた。横並びにすると同じ文字量が
     半分以下の高さに収まり、block が減って ink はそのままなので block_ink が上がる。
     desc の flex-basis を可変にしてあるので、幅が足りない面では従来どおり次の行へ
     折り返す (縮んで読めなくなるのではなく行が増える方へ倒す)。 */
  display: flex; flex-flow: row wrap; align-items: baseline;
  column-gap: var(--space-4); row-gap: calc(0.4 * var(--su));
}
.slide-list .list-item:last-child { border-bottom: none; }
.slide-list .list-item > i { color: var(--fg-muted); font-size: var(--fs-label); flex: 0 0 auto; }
/* 旧版のラベルは 800 で、h1 と同じウェイト・h2 の 0.93 倍という大きさだった。
   面の中で最も強い要素が本文の見出しと同格になると順位が消える。ラベルは
   heading の下・body の上ではなく body と同じ段に置き、ウェイトだけで前へ出す。 */
.slide-list .list-label { font-size: var(--fs-body); font-weight: var(--fw-lead); color: var(--fg); line-height: 1.35; letter-spacing: var(--ls-body); flex: 0 0 auto; }
.slide-list .list-desc { font-size: var(--fs-body); font-weight: var(--fw-body); color: var(--fg-muted); line-height: 1.45; flex: 1 1 20rem; }

/* ===== slide-compare (SR-4-03..04) ===== */
.slide-compare h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.compare-container { display: flex; gap: 4%; width: 100%; }
/* before / after は色相 (桃 / 青緑) で区別していたが、この 2 つは対等な選択肢では
   なく「今」と「これから」の順序なので、色を 2 つ使うより強弱で表すほうが正しい。
   after だけを反転面にして、面のアクセント 1 個 (E4) をここへ充てる。 */
.compare-panel { width: 48%; padding: var(--space-4); }
.compare-panel--before { border-top: var(--rule-solid) solid var(--hairline); color: var(--fg-muted); }
.compare-panel--after { border-top: var(--rule-solid) solid var(--ink); background: var(--accent-bg); color: var(--accent-fg); }
.compare-panel h3 { margin-bottom: var(--space-3); }

/* ===== slide-flow ===== */
.slide-flow h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.flow-container { display: flex; align-items: center; gap: var(--space-3); width: 100%; flex-wrap: wrap; }
/* 工程は全部が等しく重要なので、全部を塗ると強調が 1 つも無いのと同じになる。
   箱は罫で囲うだけにし、矢印は本文より弱い色で流れだけを示す。 */
.flow-step { flex: 1; min-width: calc(14 * var(--su)); padding: var(--space-3); border: var(--rule-hair) solid var(--hairline); text-align: center; font-size: var(--fs-body); }
.flow-arrow { font-size: var(--fs-body); color: var(--fg-muted); }

/* ===== slide-timeline ===== */
.slide-timeline h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.timeline { position: relative; padding-left: var(--space-5); }
.timeline::before { content: ""; position: absolute; left: calc(0.6 * var(--su)); top: 0; bottom: 0; width: var(--rule-solid); background: var(--hairline); }
/* 日付を上の行ではなく左の列へ出す。縦積みのままだと 1 項目が 3 行になり、
   行数ぶんの高さを使いきってしまうので書体を上げられず、実測で本文の字幅が
   135-571px しか無いのに矩形は 1261px 全幅を張る (面積比だけ 0.767 で高く出て、
   右半分は空) という状態になっていた。日付を列へ逃がして 1 行ぶん空けた高さを
   書体へ回すと、同じ高さのまま文字が横へ伸びて右の空きが埋まり、ink も増える。
   列の 1fr は横方向の配分で、fill_policy.note_antipattern が禁じる縦の伸長
   (grid-auto-rows: 1fr 等) とは別物。行は auto のままで内容が高さを決める。 */
.timeline-item {
  position: relative; padding-bottom: var(--space-4);
  display: grid;
  grid-template-columns: minmax(0, 14rem) minmax(0, 1fr);
  grid-template-rows: auto auto;
  column-gap: var(--space-4);
  align-items: baseline;
}
.timeline-item > .timeline-date { grid-column: 1; grid-row: 1 / 3; }
.timeline-item > .timeline-title,
.timeline-item > .timeline-desc { grid-column: 2; }
.timeline-item::before { content: ""; position: absolute; left: calc(-1.4 * var(--su)); top: calc(0.4 * var(--su)); width: calc(1.2 * var(--su)); height: calc(1.2 * var(--su)); border-radius: 50%; background: var(--ink); }
/* 既定の行送り 1.6 (body) のままだと 4 件で群が 609px になり、面の上下に
   17px ずつしか残らない (L9 下限 12% 割れ)。行送りは ink に効かない
   (行矩形の高さは字面で決まる) ので、詰めた分はそのまま block だけが減り、
   外側余白が戻って block_ink も上がる。 */
/* 日付はラベルなので label 段 + 字送りを開ける。旧版は色と 700 の両方で押していたが、
   日付は探すための目印であって主張ではない。 */
.timeline-date { font-size: var(--fs-label); color: var(--fg-muted); font-weight: var(--fw-label); letter-spacing: var(--ls-label); line-height: 1.35; }
.timeline-title { font-size: var(--fs-body); font-weight: var(--fw-lead); line-height: 1.35; }
.timeline-desc { font-size: var(--fs-body); font-weight: var(--fw-body); color: var(--fg-muted); line-height: 1.45; }

/* ===== slide-table =====
   罫は横だけ。縦罫・外枠・zebra・角丸・影を全部やめる。表の読み方は行を追うことで、
   縦罫はその視線を分断するだけの線であり、zebra は行を区別しない (どの行も同じ意味の
   ものなのに 1 行おきに違う地が付く)。見出し行はベタ塗りをやめ、下に太めの罫を 1 本。 */
.slide-table h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.slide-table table {
  width: 100%; border-collapse: collapse;
  font-size: var(--fs-body);
}
.slide-table th, .slide-table td {
  padding: var(--space-2) var(--space-3); text-align: left;
  border-bottom: var(--rule-hair) solid var(--hairline);
  vertical-align: top;
  line-height: 1.5;
}
.slide-table td { font-weight: var(--fw-body); }
.slide-table th {
  font-weight: var(--fw-label); font-size: var(--fs-label); letter-spacing: var(--ls-label);
  color: var(--fg-muted);
  border-bottom: var(--rule-solid) solid var(--ink);
}

/* ===== slide-code (SR-10-01..04) ===== */
.slide-code h2 { font-size: var(--fs-heading); margin-bottom: var(--space-3); }
/* 字も箱も面 (--su / --sv) で決める。箱の側だけ px だと、面が縮んだとき箱は縮まず
   字だけが小さくなり、同じコードでも見える行数が面ごとに変わる。実測 (--measure) で
   stage_fill が 1280x1024 0.775 / 1440x900 0.700 / 1920x1080 0.548 と割れていたのが
   これで、SR-1-04 の px 禁止にも反していた。1920x1080 の面 (--su 19.2px /
   --sv 10.8px) での実寸を保つ換算に置く。
     padding 上下   20px =  20 / 10.8 =  1.8519 --sv (縦なので --sv)
     padding 左右   24px =  24 / 19.2 =  1.25  --su (横なので --su)
   角丸だけは面単位にしない。図版の角丸 2px は「ラスタの角が地とぶつからない
   最小量」であって面に対する割合ではないので、--radius-figure を使う。
   縦を --sv、横を --su と軸で分けるのは、印刷 (297x210mm) では stage が 16:9 で
   なくなり 2 つの比が一致しなくなるため。画面側は常に 16:9 なのでどちらでも同じ。
   面単位にしても行が余計に切れることはない。字も箱も同じ --sv 由来で動くので、
   収まる行数はどの面でも一定になる (それがこの修正の目的)。

   max-height は 420px 相当 (38.889 --sv) をやめて 60 --sv に上げた。1920 の面で
   実測すると、内容枠 894.3px から h2 (87.6px)・その下余白 (12.96px)・行間
   (17.28px) を引いた残りは 776.5px = 71.9 --sv あるのに、420px の箱はその 54% しか
   使わず、コードが主役の面で 356px が常に空いたままだった。充填率も 10 行で 0.548 に
   頭打ちになり、fill_policy.exceptions.code の下限へ行数をいくら増やしても届かない。
   60 --sv はこの engine が pyramid / circle / cycle / diagram / chart / mermaid の
   主役要素へ既に使っている値で、コード面だけが例外だった。h2 が 2 行へ折り返しても
   (175.2px) 残りは 688.9px あるので 648px の箱は収まる。

   font-size は frame-contract の typography.min_rem_engine (typography.min の 18px を
   面座標で表した値) をそのまま使う。ここへ数値を書き写すと契約と二重管理になるので
   書かない。これより小さい基準では最小の観測点 1280x1024 で typography.min を割る。--font-scale は掛けない (下の .code-panel pre も同じ。
   意図か事故かは未確認で、frame-contract.json の typography.note_font_scale_code に
   申し送りとして残してある)。 */
/* 地は紙のまま。コード面へ専用の暗い地と低彩度の字を与えると、面の 3 色 (VGCONST_001)
   に無い色が 2 つ増え、しかも面の大半を占めるので反転ブロック (E4・面積 8-15%) にも
   収まらない。コードは図版なので、囲いは罫 1 本と図版用の角丸だけにして、強調は
   書体の等幅性が既に担っている。 */
.code-block { max-height: calc(60 * var(--sv)); overflow-y: auto; font-family: var(--font-mono); font-size: ${MIN_REM_ENGINE}rem; line-height: 1.7; padding: calc(1.8519 * var(--sv)) calc(1.25 * var(--su)); border: var(--rule-hair) solid var(--hairline); border-radius: var(--radius-figure); background: var(--paper); color: var(--ink); }
/* コード内の強調は 2 種類だけ。色相を足さず、ウェイトと反転で区別する。 */
.code-block .hl-header { font-weight: var(--fw-lead); }
.code-block .hl-var { background: var(--accent-bg); color: var(--accent-fg); padding: 0 0.2em; }

/* ===== slide-code-compare (SR-10-05..06) ===== */
.slide-code-compare h2 { font-size: var(--fs-heading); margin-bottom: var(--space-3); }
.code-compare { display: flex; gap: 4%; width: 100%; }
/* 上の .code-block と同じ理由で面単位にし、max-height も同じ 60 --sv へ揃える。
   280px 相当 (25.926 --sv) では、左右に並ぶパネルが使える縦 776.5px のうち 36% しか
   使わず、比較したい 2 つのコードがどちらも数行で切れていた。左右に並ぶぶん横幅は
   48% しかないので、縦は .code-block と同じだけ与えてよい。width 48% と gap 4% は
   無次元なのでそのままで面に追随する。 */
.code-panel { width: 48%; max-height: calc(60 * var(--sv)); overflow-y: auto; border: var(--rule-hair) solid var(--hairline); border-radius: var(--radius-figure); }
/* 見出しは前後どちらのパネルかを示すラベル。.compare-panel と同じく、after 側だけを
   反転させて順序を出す。ここは帯 1 本ぶんなので E4 の面積に収まる。 */
.code-panel__header { padding: var(--space-2) var(--space-3); font-weight: var(--fw-label); font-size: var(--fs-label); letter-spacing: var(--ls-label); border-bottom: var(--rule-hair) solid var(--hairline); color: var(--fg-muted); }
.code-panel--after .code-panel__header { background: var(--accent-bg); color: var(--accent-fg); border-bottom-color: var(--ink); }
.code-panel pre { margin: 0; padding: var(--space-3); font-family: var(--font-mono); font-size: ${MIN_REM_ENGINE}rem; line-height: 1.7; background: var(--paper); color: var(--ink); }

/* ===== slide-pyramid ===== */
.slide-pyramid h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.slide-pyramid .pyramid-svg { width: 100%; max-height: calc(60 * var(--sv)); }

/* ===== slide-circle ===== */
.slide-circle h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.slide-circle .circle-svg { width: 100%; max-height: calc(60 * var(--sv)); }

/* ===== slide-grid =====
   カードの地色・角丸・影・左の色帯をすべて外し、区切りは罫 1 本にする。並列に置いた
   項目は「並んでいること」が既に関係を表しているので、1 枚ずつ囲うと囲いの数だけ
   ノイズが増える (VGCONST_008)。色の巡回 (5n+1..5n+5) も外した。順番に配る色は
   項目の内容と何の関係も無いのに、読み手には意味があるものとして見える。 */
.slide-grid h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.grid-container { display: grid; grid-template-columns: repeat(var(--grid-cols, 3), 1fr); gap: var(--space-4); width: 100%; }
/* 既定は「2 段以上でも溢れない詰まった寸法」。1 段の面だけを data-rows="1" で
   拡大する (下の定義)。逆向き (既定を大きくして多段だけ縮める) にすると、
   段数の判定が届かなかったときに 2 段目が stage を溢れて error 側へ倒れるため。
   段数は render-slide.cjs が枚数と列数から確定させて data-rows へ出している。 */
.grid-cell {
  padding: var(--space-3) 0;
  font-size: var(--fs-body);
  border-top: var(--rule-solid) solid var(--ink);
  display: flex; flex-direction: column; gap: var(--space-2);
}
/* アイコンは Font Awesome の ::before なので DOM 上にテキストノードが無く、
   validate-slide-layout.js の ink 走査 (TreeWalker + Range の行ボックス) に
   一切数えられない。つまり大きくすると block (カード高) だけが伸びて ink は
   増えず、block_ink を押し下げる。面を埋めるためにここを大きくしてはいけない。
   増やす高さは行矩形が付いてくる側 (title / desc の font-size) へ寄せる。 */
.grid-cell > i { font-size: var(--fs-label); color: var(--fg-muted); }
/* ink は Range.getClientRects() で採る。返る行矩形の高さは line-height ではなく
   書体の実寸で決まり、実測でも font-size の約 1.44 倍で一定だった
   (44.9px -> 65px / 48.7px -> 70px、line-height は 1.3 と 1.25 で別)。
   つまり line-height を広げても block (カード高) だけが伸びて ink は増えない。
   面を埋めるぶんは line-height ではなく font-size 側で取り、行間は詰めておく。 */
/* 折り返しが起きたときに最終行へ 1 文字だけ残る (「参加はこち」/「ら」) のを防ぐ。
   text-wrap: balance は行の最大幅を揃える方向で割るので 3 文字 / 3 文字になる。
   word-break: auto-phrase も試したが、文節ごとに割るため説明文が 4 行 (実測で
   217/217/217/326px) に散り、かえって行数と高さが増えたので入れていない。
   未対応環境では
   既定の折り返しに戻るだけで、寸法は下の font-size 側で 1 行に収まるよう
   取ってあるため、効かなくても溢れない。面積比と ink 比はこの見た目の破綻を
   検出できない (font-size を上げると block も ink も一緒に上がるため) ので、
   ここを触ったら数値ではなくスクリーンショットで確認すること。 */
/* 旧版は見出し 800 / 説明 500 で、比 0.88 という中途半端な段を作っていた。この 0.88 が
   本文系列 (段差 1.176) と別の 2 本目の系列で、順位が読めない原因になっていた。
   見出しと説明は同じ段 (body) に置き、区別はウェイトと濃度で付ける。 */
.grid-cell-title { font-size: var(--fs-body); font-weight: var(--fw-lead); color: var(--fg); line-height: 1.2; text-wrap: balance; }
.grid-cell-desc { font-size: var(--fs-body); font-weight: var(--fw-body); color: var(--fg-muted); line-height: 1.4; text-wrap: balance; }
/* 上の型トークンと下の data-rows="1" の値は「この面ならこの段」という設計であって、
   文字列が入るかどうかは見ていない。段だけで決めると、セル幅が変わったときや
   文字列が長い面で熟語が割れる (かつて 1 段の面の見出しが 74.13px に解決し、
   内寸 520px のセルに 8 文字が入らなくなっていた)。
   そこで段は上限としてだけ使い、セル幅に入らなければ下げる。分母 --fit-t /
   --fit-d は面内で最も長い文字列の幅 (em) で、render-slide.cjs が出す。
   100cqi はセルの内寸そのもの (container-type: inline-size の inline 方向)。
   見出しは 100cqi (1 行に収める)、説明は 190cqi (2 行まで許す) で割る。見出しは
   語で読ませるものなので割れた時点で意味が壊れるが、説明は文なので 2 行に流れて
   正しい。1 行に収めようとして説明だけ極端に小さくすると、今度は面が空く
   (実測: 説明も 1 行に収める版では 1 段 3 枚の面で stage_fill が 0.40 まで落ちた。
   190cqi にすると 0.65 前後に戻り、見出しは 1 行のまま)。3 行以上は 190cqi の
   上限側で自動的に止まる。
   下限は frame-contract.json の typography.min_rem_engine で、ここで
   独自の下限を決めない。下限に当たった文字列は縮まずに折り返す。
   1 行 1 項目へ倒した data-layout="stack" は見出し列が 31% で 100cqi と一致しない
   ため対象外。実測でも stack の面は旧エンジン・新エンジンのどちらでも全行 1 行に
   収まっており、直す対象が無い。
   ここを触ったら、行数が増えていないことを実描画の行矩形 (Range#getClientRects)
   で数えて確かめること。font-size と面積比は連動して動くので L8 では検出できない。 */
.grid-cell { container-type: inline-size; }
.grid-container:not([data-layout="stack"]) .grid-cell-title {
  font-size: clamp(${MIN_REM_ENGINE}rem, calc(100cqi / var(--fit-t, 8)), var(--fs-body));
}
.grid-container:not([data-layout="stack"]) .grid-cell-desc {
  font-size: clamp(${MIN_REM_ENGINE}rem, calc(190cqi / var(--fit-d, 14)), var(--fs-body));
}
/* 履歴 (次にここを触る人へ): この data-rows="1" ブロックは、書かれてから
   letterbox 対応の日まで一度も適用されたことがない。旧エンジンは grid の
   コンテナに data-rows 属性自体を出しておらず、セレクタが常に外れていた =
   実質の死にコードだった。letterbox で属性が出るようになって初めて表に出た
   結果、ここに書かれていた 3.3rem が誰の目にも触れないまま fontScale と掛かって
   74.13px に解決し、見出しが折り返した。
   つまり「letterbox が壊した」のではなく「letterbox が初めて実行させた」。
   下の段も設計であって検証値ではない。上の clamp でセル幅の上限に押さえてある
   ので折り返しは起きないが、段を上げ下げしたときの見え方は誰も確かめていない
   前提で扱うこと。
   1 段しか無い面は、カードの高さがそのまま面の高さになるので、既定のままだと
   面の下半分が丸ごと空く (実測 stage_fill 0.31-0.37)。padding と書体を一段上げて
   中身ごと大きくする。grid-auto-rows: 1fr / align-content: stretch で面積だけ
   稼ぐと block_ink が落ちる (= fill_policy.note_antipattern の伸長) ので採らない。
   ここを触ったら stage_fill と block_ink が両方上がることを
   validate-slide-layout.js --measure で確認すること。
   1 段の面は見出しを 1 段上げて heading にする。カード内の独自 rem を置くのではなく
   系列の隣の段へ移すだけなので、ここに 2 本目の系列は生まれない。 */
.grid-container[data-rows="1"] .grid-cell { padding: var(--space-6) 0; gap: var(--space-3); }
.grid-container[data-rows="1"] .grid-cell > i { font-size: var(--fs-body); }
.grid-container[data-rows="1"]:not([data-layout="stack"]) .grid-cell-title {
  font-size: clamp(${MIN_REM_ENGINE}rem, calc(100cqi / var(--fit-t, 8)), var(--fs-heading));
  line-height: 1.25;
}
.grid-container[data-rows="1"]:not([data-layout="stack"]) .grid-cell-desc {
  font-size: clamp(${MIN_REM_ENGINE}rem, calc(190cqi / var(--fit-d, 14)), var(--fs-body));
  line-height: 1.45;
}
/* 説明が長い面を 1 行 1 項目へ倒す (structure の content.layout = "stack")。
   3 列のままだと 1 行あたり 10 字前後で折り返し、見出しまで語中で割れる
   (実測「データ整 / 理・分析」「企画・ネーミング・キ / ャッチコピー」)。
   横一列にすれば折返しが消え、視線も上から下の 1 方向で済む。 */
/* grid-template-columns: 1fr は列を 1 本にするだけで、行を残余まで引き伸ばす
   grid-auto-rows: 1fr / align-content: stretch とは別物。行高は中身で決まるので
   fill_policy.note_antipattern の「伸長で充填率を作る」には当たらない。 */
/* 長さはすべて rem で書く。版面では root font-size が calc(1.6 * var(--sv)) なので
   rem 自体が面の単位であり、vh を書くと画面比率で見え方が変わってしまう。 */
/* 行の高さは cards の枚数ぶんだけ積み上がるので、寸法は schema の上限 6 枚が
   入る側で取る。実測: 上下 padding 1.5rem / gap 2.8 --sv だと 5 枚で
   slider__content を 80px (1920x1080) 溢れて L3 の error になった。 */
.grid-container[data-layout="stack"] { grid-template-columns: 1fr; gap: clamp(0.9rem, calc(2.0 * var(--sv)), 2rem); align-content: center; }
/* 見出し列は 31%。26% では実測 430px しか取れず、8 字の見出し「データ整理・分析」
   (1 字 63px で 504px) が語中で割れた。31% は 1920x1080 で
   534px なので 1 行に収まる。34% まで広げると今度は説明列が 953px に痩せ、18 字の
   「報告書・提案書・議事録の下書きを作成」(972px) が折り返した。31% はこの両側から
   挟んで決めた値で、上下いずれにも動かす余地はほぼ無い。 */
/* 下限を 0 にしてあるのは、見出しが短い面で列が痩せても desc 側が伸びるだけで
   崩れないから。列幅を % で書くのは、面 (16:9 のステージ) に対する割合であって
   画面比率では変わらないため。実測: 1920x1080 と 1280x1024 のどちらでも
   slide6 / slide7 の見出し・説明はすべて 1 行に収まる。 */
.grid-container[data-layout="stack"] .grid-cell {
  display: grid;
  grid-template-columns: 3.6rem minmax(0, 31%) 1fr;
  align-items: center;
  column-gap: 1.8rem;
  row-gap: 0;
  padding: 1.1rem 0;
  text-align: left;
  /* 1 行 1 項目なので、行と行の区切りは表と同じ細罫でよい。既定の
     .grid-cell が使う 1px の実線は列が並ぶときの区切りで、縦に積むと強すぎる。 */
  border-top: var(--rule-hair) solid var(--hairline);
}
.grid-container[data-layout="stack"] .grid-cell > i { font-size: var(--fs-label); justify-self: center; }
.grid-container[data-layout="stack"] .grid-cell-title { line-height: 1.25; }
.grid-container[data-layout="stack"] .grid-cell-desc { margin: 0; }
/* 段数が少ない stack 面は縦に余る。既定の body 段のままだと slide6 (3 段) で
   充填率 43.6% と当時の下限 48% を割った (実測)。埋め方は padding ではなく字面で
   取る。padding は block だけを増やして ink を増やさないので block_ink を押し下げる
   (.grid-cell > i と同じ理由)。 */
/* data-rows で段数別に分けるのは、上の
   .grid-container[data-rows="1"] が 1 段の面を拡大しているのと同じ考え方。
   4 段以上は既定のままにする。5 段の slide7 は既定でも slider__content の
   高さぎりぎりで、ここを上げると L3 の溢れ側へ倒れるため。 */
/* 上げ幅は見出しを 1 段 (heading) までとする。系列の外に中間値を作って更に上げると
   充填率は稼げるが、稼いだぶんは見出しが 2 行に折り返して増えた ink であり、
   この rule が消そうとしている折返しそのものを呼び戻す。 */
.grid-container[data-layout="stack"][data-rows="1"] .grid-cell-title,
.grid-container[data-layout="stack"][data-rows="2"] .grid-cell-title,
.grid-container[data-layout="stack"][data-rows="3"] .grid-cell-title { font-size: var(--fs-heading); }
/* slide-flow / slide-circle / slide-diagram-vs / slide-diagram-mindmap SVG を画面いっぱいに */
.slide-flow .slider__content,
.slide-diagram-cycle .slider__content,
.slide-diagram-vs .slider__content,
.slide-diagram-mindmap .slider__content { display: flex; flex-direction: column; }
.slide-flow svg,
.slide-diagram-cycle svg.cycle-svg,
.slide-diagram-vs svg.vs-svg,
.slide-diagram-mindmap svg { width: 100%; max-height: calc(70 * var(--sv)); height: auto; flex: 1; }

/* ===== slide-highlight ===== */
.slide-highlight { justify-content: center; align-items: center; text-align: center; }
/* 数字が面の第 1 位なので lead をそのまま使う。旧値 8rem は lead を上回る独自の
   天井で、VGCONST_010 の「第 1 位は stage 高の 10% まで」を超えていた。
   900 も系列の外 (400/500/700 の 3 段) なので 700 へ戻す。 */
.slide-highlight .highlight-num { font-size: var(--fs-lead); font-weight: var(--fw-lead); letter-spacing: var(--ls-lead); color: var(--ink); }
.slide-highlight .highlight-label { font-size: var(--fs-body); color: var(--fg-muted); }

/* ===== slide-icon-grid =====
   アイコンは項目の目印であって主役ではないので、地・角丸・影で囲わず、字より弱い
   濃度で置く。囲いを外すと項目同士の間隔だけが群を作る (VGCONST_009)。 */
.slide-icon-grid h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.ig-container { display: grid; grid-template-columns: repeat(var(--ig-cols, 3), 1fr); gap: var(--space-3); width: 100%; }
.ig-item { width: 100%; box-sizing: border-box; padding: var(--space-3) 0; text-align: center; }
.ig-icon { font-size: var(--fs-heading); color: var(--fg-muted); margin-bottom: var(--space-2); }
.ig-label { font-size: var(--fs-body); font-weight: var(--fw-label); }

/* ===== slide-process =====
   番号は丸のベタ塗りをやめ、字だけで示す。丸は 1 項目ごとに面積を持つ装飾で、
   項目が増えるほど「同じ形が何個も並ぶ」ノイズになる。順序は数字が既に表している。 */
.slide-process h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.process-container { display: flex; flex-direction: column; gap: 0; }
.process-item { display: flex; align-items: baseline; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: var(--rule-hair) solid var(--hairline); }
.process-item:last-child { border-bottom: none; }
.process-num { width: calc(3 * var(--su)); flex-shrink: 0; font-weight: var(--fw-lead); font-size: var(--fs-body); color: var(--fg-muted); letter-spacing: var(--ls-label); }

/* ===== slide-quote (SR-3-08) ===== */
.slide-quote { justify-content: center; align-items: center; text-align: center; }
/* 引用面の第 1 位は引用文。見出しはその上のラベルなので label 段へ落とす。 */
.slide-quote h2 { font-size: var(--fs-label); font-weight: var(--fw-label); letter-spacing: var(--ls-label); color: var(--fg-muted); margin-bottom: var(--space-3); }
.slide-quote blockquote { font-size: var(--fs-heading); font-weight: var(--fw-body); letter-spacing: var(--ls-lead); max-width: 80%; line-height: 1.5; }
.slide-quote cite { display: block; margin-top: var(--space-3); font-size: var(--fs-label); font-style: normal; color: var(--fg-muted); letter-spacing: var(--ls-label); }

/* ===== slide-hero =====
   表紙は面ごと反転させる。これは E4 が数える「面の中の反転ブロック」ではなく面
   そのものの地なので、面積の 8-15% には当たらない (地と文字が入れ替わるだけで、
   面に出ている色は依然として 2 つ)。グラデーションは色数が数えられなくなるので使わない。 */
.slide-hero { justify-content: center; align-items: center; text-align: center; background: var(--ink); color: var(--paper-on-ink); }
/* 行送り 1.2 (.slider__item h1 の既定) だと、この字面 (実測で約 1.32em) が
   行ボックスに収まらず 16px 溢れる。字を小さくするのではなく行送りを字面に
   合わせる (表紙なので縦の余りは十分ある)。 */
.slide-hero h1 { font-size: var(--fs-lead); line-height: 1.35; }
.slide-hero .hero-sub { font-size: var(--fs-body); font-weight: var(--fw-body); }

/* ===== slide-cycle (SR-3-08) ===== */
.slide-cycle h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.slide-cycle .cycle-svg { width: 100%; max-height: calc(60 * var(--sv)); }

/* ===== diagram-* / chart-* / d3-* 共通 ===== */
.slide-diagram h2, .slide-chart h2, .slide-d3 h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.slide-diagram svg, .slide-chart svg { width: 100%; max-height: calc(60 * var(--sv)); }
.slide-d3 .d3-mount { width: 100%; height: calc(60 * var(--sv)); }

/* ===== ビジュアルの縦寸は「残った空き」で決める (SR-4-02 の実効化) =====
   上の 60vh / 70vh は見出しの行数を知らない固定値で、h2 が 2 行になると
   nav-top(4rem) + 見出し + 60vh + nav-bottom(5rem) が 100vh を超え、
   あふれた図解がページネーション帯へせり出す。ここで残余割当に上書きする。

   セレクタを [class*=] にしているのは、.slide-diagram が完全一致であり
   slide-diagram-architecture のような派生タイプに 1 つも効かないため。 */
.slider__item[class*="slide-diagram"] > .slider__content > svg,
.slider__item[class*="slide-chart"] > .slider__content > svg,
.slider__item[class*="slide-flow"] > .slider__content > svg,
.slider__item[class*="slide-cycle"] > .slider__content > svg,
.slider__item[class*="slide-pyramid"] > .slider__content > svg,
.slider__item[class*="slide-circle"] > .slider__content > svg {
  /* 伸びない・縮むだけ。旧値 flex: 1 1 auto は grow が 1 で、図が残余の高さを
     必ず食い切るため群の外側余白が構造的に 0 になっていた (実測 slide-circle の
     L9 が上 0px / 下 0px)。fill_policy.note_antipattern が禁じる伸長そのもので、
     しかも充填率は図の実寸でなく枠の消費で稼がれる。縮む側 (shrink) は残余に
     収めるために要るので残す。 */
  flex: 0 1 auto;
  /* flex item の既定 min-height:auto は「内容より小さくならない」を意味し、
     これがある限り max-height を書いても縮まずにはみ出す。0 にして初めて
     残余に収まる。この 1 行が実際の効き所。 */
  min-height: 0;
  /* 旧値 100% は「残余いっぱい」で、上の grow と対で外側余白を 0 にしていた。
     60vh は .slide-circle / .slide-pyramid 側の既定と同じ値で、見出しと合わせて
     群が面の 86% に収まる (実測 1440x900・1920x1080 とも外側余白 13.9%)。
     残余が 60vh より狭い面では 100% 側が選ばれて溢れを防ぐ。 */
  max-height: min(100%, calc(60 * var(--sv)));
  width: 100%;
  height: auto;
  /* SVG 自身のアスペクト比を保ったまま残余の中央へ置く */
  object-fit: contain;
}
/* d3 のマウント先も同様に残余へ従わせる (60vh 固定を上書き) */
.slider__item[class*="slide-d3"] > .slider__content > .d3-mount {
  flex: 1 1 auto; min-height: 0; height: auto;
}
/* 見出しと本文は縮まない側に固定する。これが無いと flex が見出しを潰し、
   「図解は収まったが見出しが読めない」という逆の破綻になる。 */
.slider__content > h1,
.slider__content > h2,
.slider__content > h3,
.slider__content > .slide-lead { flex: 0 0 auto; }

/* ===== foreignObject card (SR-6-04) ===== */
.fo-card { width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: calc(0.8 * var(--su)); box-sizing: border-box; font-family: var(--font-base); }
.fo-card--row { flex-direction: row; }
`;
}

function buildPrint() {
  return `
/* ===== §7 印刷 (SR-7-01..10) ===== */
@page { size: A4 landscape; margin: 0; }
@media print {
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; box-shadow: none !important; }
  /* グラデ文字(background-clip:text)は印刷で塗りつぶし矩形になり読めなくなるため通常色に戻す */
  .gradient-text,
  [style*="-webkit-background-clip: text"], [style*="background-clip: text"] {
    background: none !important;
    -webkit-background-clip: border-box !important; background-clip: border-box !important;
    -webkit-text-fill-color: var(--ink) !important; color: var(--ink) !important;
  }
  /* SR-7-09 Chrome 拡張・外部 UI 非表示（slider 直系のみ表示） */
  body > *:not(.slider):not(script):not(style) { display: none !important; visibility: hidden !important; width: 0 !important; height: 0 !important; overflow: hidden !important; }
  /* 印刷の版面は 297x210mm の full-bleed (SR-1-03)。画面側の 16:9 レターボックス
     はここでは効かせず、stage の実寸を紙面へ差し替える。--su は 2.97mm、--sv は
     2.1mm となり、これは変更前の 1vw / 1vh と同値なので印刷結果は動かない。
     font-size は上書きしない (validate-print P05)。 */
  :root { --stage-w: 297mm; --stage-h: 210mm; }
  /* 印刷では地を塗らない。画面の --paper (#F7F6F3) は「紙に見える色」を光で
     作るための値で、実物の紙の上ではその役を紙自身が果たす。ここを塗ると
     全面ベタになり、インクが乗っていない部分にインクが乗る。 */
  html, body { width: 297mm; height: auto; background: #fff; }
  /* 画面では stage を中央へ置くために flex にしているが、印刷では面が縦に
     連なるので block へ戻す (flex のままだと面が横一列に並ぶ)。 */
  .slider { width: 297mm; height: auto; overflow: visible; display: block; }
  .slide-area, .slider__container { width: 297mm; height: 210mm; }
  /* SR-7-08 スライド番号動的化（attr(data-total) を使用） */
  .slider__item { counter-increment: slide-num; }
  .slider__item::after { content: counter(slide-num) " / " attr(data-total); }
  .slider__item {
    position: relative; inset: auto;
    width: 297mm; height: 210mm; min-height: 210mm; max-height: 210mm; /* SR-1-03, SR-7-02 */
    border: none; margin: 0; padding: 8mm; /* SR-7-03 / SR-7-11 印刷パディング */
    page-break-after: always; break-after: page;
    opacity: 1 !important; visibility: visible !important;
    box-shadow: none !important; /* SR-7-10 */
    isolation: isolate; /* SR-7-08 印刷時 z-index 競合回避 */
  }
  /* 最終面だけ強制改ページを外す。.slider-footer は position: absolute で下端が
     794px になり、印刷ページ高 793.688px を 0.3px 超える。最終面の break-after: page
     と合わさると、その 0.3px のために content stream 93 バイトの空白ページが 1 枚
     増える (面数 16 のデッキが 17 ページになる)。footer を印刷で隠せば消えるが、
     footer は紙面にも要るので改ページ側を外す。
     .slide-area { overflow: hidden } で切ってはいけない。祖先が clip すると子孫の
     page-break-after が効かなくなり、全面が 2 ページに潰れる。 */
  .slider__item:last-child { page-break-after: auto; break-after: auto; }
  /* SR-7-04 GSAP リセット */
  .slider__content, .slider__content > *, .slider__content * {
    visibility: visible !important;
    opacity: 1 !important;
    transform: none !important;
  }
  /* SR-7-05 ナビ非表示 */
  .pg-progress, .pg-controls, .pg-counter, .pg-dots, .pg-section-nav,
  .progress-bar, .navigation, .slide-counter, .dot-pagination, .agenda-indicator {
    display: none !important;
  }
  /* SR-7-07 hidden slides */
  [data-hidden="true"] { display: none !important; height: 0 !important; }
}

/* ===== §9 prefers-reduced-motion (SR-9-03) ===== */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
`;
}

/**
 * メイン: spec + pagination.css 結合 → styles.css 全文
 */
function buildStyles({ specOverride = {}, paginationCssPath } = {}) {
  const spec = { ...SPEC, ...specOverride, colors: { ...SPEC.colors, ...(specOverride.colors || {}) } };
  // fontScale の下限を fail-closed で守る。下回る値を通すと系列の最下段 (--fs-label) が
  // typography.min_rem_engine を割る CSS を生成してしまい、後段の layout 検証でしか気付けない。
  // 最下段の基準値は leadRem / (stepMajor^2 * stepMinor) で、系列が 1 本なのでこの 1 式で足りる。
  const ts = spec.typeScale;
  const labelRem = ts.leadRem / (ts.stepMajor * ts.stepMajor * ts.stepMinor);
  const fsNum = Number(spec.fontScale);
  if (!Number.isFinite(fsNum) || fsNum < MIN_FONT_SCALE) {
    throw new Error(
      `[style-builder] fontScale=${spec.fontScale} は下限 ${MIN_FONT_SCALE} を下回る。` +
        `--fs-label = calc(${labelRem.toFixed(4)}rem * fontScale) が typography.min_rem_engine (${MIN_REM_ENGINE}rem) を割るため CSS を生成しない。`
    );
  }
  // 下限を通った fontScale でも、typeScale 側を触れば床は割れる。値ではなく式で確かめる。
  if (labelRem * MIN_FONT_SCALE < MIN_REM_ENGINE) {
    throw new Error(
      `[style-builder] typeScale の最下段 ${labelRem.toFixed(4)}rem x 下限 fontScale ${MIN_FONT_SCALE} = ` +
        `${(labelRem * MIN_FONT_SCALE).toFixed(4)}rem が typography.min_rem_engine (${MIN_REM_ENGINE}rem) を割る。` +
        `天井 (leadRem) か段差を見直すこと。床は下げない。`
    );
  }
  let paginationCss = '';
  if (paginationCssPath && fs.existsSync(paginationCssPath)) {
    paginationCss = fs.readFileSync(paginationCssPath, 'utf8');
  }
  return [
    '/* ===================================================================',
    '   styles.css — render-slide.js 自動生成 (spec-registry.md SR-ID 駆動)',
    '   単位: vw / rem / mm のみ (SR-1-04)。px は禁止。',
    '   ===================================================================*/',
    buildRootVars(spec),
    buildBase(),
    buildSlideTypes(),
    buildPrint(),
    buildV8Layer(),
    '/* ===== pagination.css 結合 ===== */',
    paginationCss,
  ].join('\n');
}

// v8.0.0: schemaVersion=8.0.0 のときに render-slide.cjs が付与する
// data-* / CSS 変数を解釈するスタイル層 (SR-V8-COLOR / SR-V8-PAGE / SR-V8-COVER)
function buildV8Layer() {
  return `
/* ===== v8.0.0 拡張レイヤ (schemaVersion=8.0.0 のみ作動) ===== */

/* per-slide CSS 変数フォールバック (SR-V8-COLOR)
   面ごとに色を差し替える口だが、既定は色相を持たないインクにする。deck 側が
   --accent-primary を上書きしなければ、面の色数は 3 のまま変わらない。 */
.slider__item { --accent-primary: var(--ink); --accent-secondary: var(--fg-muted); --accent-pagination: var(--accent-primary); }

/* 背景バリアント (SR-V8-PAGE)
   tint / gradient は「地に薄く色を敷く」指定で、面の色数を 3 から増やしたうえに
   境界の無いグラデーションを作る。のべっとした見えの主因なのでここで潰し、
   default と同じ紙へ倒す。面の切り替えは地の色ではなく反転 (dark) で行う。 */
.slider__item[data-bg="default"],
.slider__item[data-bg="tint"],
.slider__item[data-bg="gradient"] { background: var(--bg-dark); }
/* dark は反転面。地と文字を入れ替えるだけで、新しい色は持ち込まない。 */
.slider__item[data-bg="dark"]    { background: var(--ink); color: var(--paper-on-ink); }
.slider__item[data-bg="dark"] h2,
.slider__item[data-bg="dark"] h3 { color: var(--paper-on-ink); }
.slider__item[data-bg="image"]   { background: var(--bg-image, none) center/cover no-repeat, var(--bg-dark); }

/* per-slide ナビ非表示 (例: 表紙) */
.slider[data-pg-style] .slider__item[data-pg-hide="true"] ~ * { /* placeholder */ }
.slider__item[data-pg-hide="true"] + .pg-controls,
.slider__item.is-active[data-pg-hide="true"] ~ .pg-section-nav,
.slider__item.is-active[data-pg-hide="true"] ~ .pg-dots { opacity: 0; pointer-events: none; }

/* ヘッダ・フッタ (SR-V8-PAGE) */
/* 走り (ヘッダ・フッタ) は面の内容ではないので label 段 + 弱い濃度。opacity を
   掛けると地に対する見え方が面ごとに変わるので、色そのもので弱める。 */
.slider-header { position: absolute; top: 0; left: 0; right: 0; height: calc(3 * var(--sv)); padding: 0 calc(2 * var(--su)); display: flex; align-items: center; gap: calc(1 * var(--su)); font-size: var(--fs-label); letter-spacing: var(--ls-label); color: var(--fg-muted); z-index: 5; }
.slider-header__logo { color: var(--fg); font-weight: var(--fw-label); }
.slider-header__event { margin-left: auto; }
.slider-footer { position: absolute; bottom: 0; left: 0; right: 0; height: calc(2.6 * var(--sv)); padding: 0 calc(2 * var(--su)); display: flex; align-items: center; justify-content: space-between; font-size: var(--fs-label); letter-spacing: var(--ls-label); color: var(--fg-muted); z-index: 5; }
.slider-footer__center { text-align: center; flex: 1; }

/* ページネーションスタイル切替 (SR-V8-PAGE) */
.slider[data-pg-style="none"] .pg-controls,
.slider[data-pg-style="none"] .pg-dots,
.slider[data-pg-style="none"] .pg-section-nav { display: none; }
.slider[data-pg-style="numeric"] .pg-dots { display: none; }
.slider[data-pg-style="bar"] .pg-dots { display: none; }
.slider[data-pg-style="section-dots"] .pg-dots { display: none; }

/* cover variant (SR-V8-COVER) — テンプレ未対応時のフォールバック表示 */
.slider__item[data-v8-cover="hero-icon"] .slider__content,
.slider__item[data-v8-cover="hero-image"] .slider__content,
.slider__item[data-v8-cover="centered-large"] .slider__content { text-align: center; }
.slider__item[data-v8-cover] h1 { color: var(--fg); }

/* index variant (SR-V8-INDEX) */
.slider__item[data-v8-index="stepper"] .list-item { counter-increment: v8step; position: relative; padding-left: calc(4 * var(--su)); }
.slider__item[data-v8-index="stepper"] .list-item::before { content: counter(v8step); position: absolute; left: calc(1 * var(--su)); top: 50%; transform: translateY(-50%); width: calc(2.4 * var(--su)); display: flex; align-items: center; justify-content: center; font-weight: var(--fw-lead); color: var(--fg-muted); letter-spacing: var(--ls-label); }

/* diagram マーカー (SR-V8-DIAGRAM) — 共通枠
   凡例の丸は図解の内部なので、VGCONST_002 が許す濃度段を使ってよい。既定は
   最も薄い段で、図解側が --tone-2 / --tone-3 を指定して段を上げる。 */
.slider__item[data-v8-diagram] .diagram-legend { display: flex; flex-wrap: wrap; gap: calc(1 * var(--su)); justify-content: center; margin-top: calc(1 * var(--su)); font-size: var(--fs-label); letter-spacing: var(--ls-label); color: var(--fg-muted); }
.slider__item[data-v8-diagram] .diagram-legend__item { display: inline-flex; align-items: center; gap: calc(0.4 * var(--su)); }
.slider__item[data-v8-diagram] .diagram-legend__dot { width: calc(0.8 * var(--su)); height: calc(0.8 * var(--su)); border-radius: 50%; background: var(--tone-2); }
/* 注記の 3 種 (既定 / warning / tip) は、旧版では地の色相だけで分けていた。色を
   見分けられない条件では 3 つが同じものになるので、区別は罫の太さで付ける。 */
.slider__item[data-v8-diagram] .diagram-annotation { display: inline-flex; align-items: center; gap: calc(0.4 * var(--su)); padding: calc(0.4 * var(--su)) calc(0.8 * var(--su)); font-size: var(--fs-label); margin-top: calc(1 * var(--su)); border-left: var(--rule-hair) solid var(--hairline); }
.slider__item[data-v8-diagram] .diagram-annotation--warning { border-left: calc(0.3 * var(--su)) solid var(--ink); font-weight: var(--fw-label); }
.slider__item[data-v8-diagram] .diagram-annotation--tip { border-left: var(--rule-solid) solid var(--fg-muted); }
`;
}

module.exports = { buildStyles, SPEC, buildV8Layer };
