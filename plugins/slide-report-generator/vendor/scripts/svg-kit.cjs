/**
 * svg-kit.cjs — 決定論 SVG レイアウトカーネル (v7.6.0 新設)
 *
 * 目的: svg-builder.cjs の各ビルダーが共有する「崩れない図解」の土台を提供する。
 * 従来 svg-builder が個別に持っていた素朴な実装 (文字数固定スライスによる折返し、
 * 半径不整合の円弧、固定パレット) を置き換え、以下を単一責務で担う。
 *
 *   1. 日本語対応テキスト計測      measureText / charWidth
 *   2. 禁則処理つき折返し          wrapText (分割位置スコアは breakScore)
 *   3. 箱に収めるフォント自動決定  fitText / autoBlockHeight
 *   4. 幾何ソルバ                  boxRayDistance / circleBoxExit / ringArcPath / elbowPath
 *                                  safeElbow / trunkPaths / overArcPath (矢じり可視性)
 *   5. デザイントークン            TOKENS / SERIES / MARKER / resolvePalette / nodeStyle
 *   6. 描画プリミティブ            svgRoot / textBlock / arrowMarkers / arrowLabel / legendStrip
 *   7. 幅配分                      distributeWidths (Σ幅 === total を厳密に満たす)
 *
 * 設計原則の出典: cathrynlavery/diagram-design (MIT) の SKILL.md §5-§7 および
 * type-loop.md §2 / type-architecture.md。採用した規則:
 *   - 4px グリッド (座標・寸法・余白はすべて 4 の倍数へスナップ)
 *   - 1 図解あたり焦点は 1-2 要素のみ (accent は信号であり装飾ではない)
 *   - 直交エルボ必須 (軸を共有しないノード間の斜め直線は禁止)
 *   - 矢印ラベルは不透明マスク + コネクタから 6-10px のギャップ
 *   - 矢印はノードより先に描画 (z 順でコネクタがノードの背面に入る)
 *   - リング弧は「円 × 矩形の交点」で端点を求め marker overhang を補正する
 *
 * 本ハーネス固有の追加要件:
 *   - 日本語 (全角・半角カナ・約物) の実測幅にもとづく折返しと禁則処理
 *   - SR-3-05 (SVG text 最小 13px) を下限として尊重する自動フォント縮小
 *   - CSS 変数 + フォールバック形式の色指定 (SR-2-08)
 */
'use strict';

/* ============================================================
 * 0. グリッドと定数
 * ============================================================ */

/** 4px グリッド (diagram-design SKILL.md §7 の hard rule) */
const GRID = 4;

/** SR-3-05: SVG <text> の実用最小サイズ。軸ラベル等の例外は MIN_FONT_SMALL。 */
const MIN_FONT = 14;
const MIN_FONT_SMALL = 12;

/** 行送り係数 (SR-5-04: dy = font-size × 1.5) */
const LINE_HEIGHT_RATIO = 1.5;

/** 矢印ラベルとコネクタの必須ギャップ (diagram-design SKILL.md §6 rule 2) */
const LABEL_GAP = 8;

/** 4px グリッドへスナップ */
function snap(v) {
  return Math.round(v / GRID) * GRID;
}

/**
 * 4px グリッドへ切り上げ / 切り下げ。
 * 文字を包む矩形 (ラベルマスク・カード) の寸法は snapUp を使う。
 * snap だと最大 2px 縮んで文字が矩形からあふれるため、外接寸法は必ず切り上げる。
 * 逆に領域を等分して得る内寸は snapDown を使い、外枠をはみ出させない。
 */
function snapUp(v) {
  return Math.ceil(v / GRID) * GRID;
}

function snapDown(v) {
  return Math.floor(v / GRID) * GRID;
}

/** 数値を [min, max] へ収める */
function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

/** SVG 属性用に小数を丸める (座標の桁を安定させ diff を読みやすくする) */
function num(v) {
  return Number.isFinite(v) ? String(Math.round(v * 1000) / 1000) : '0';
}

function escapeXml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ============================================================
 * 1. デザイントークン
 * ============================================================ */

/**
 * セマンティックロール。
 *
 * 重要な制約: 本プラグインの配色は「既存のまま」を維持する。参考スキルの
 * パレット (atomic-tangerine 等) は一切持ち込まない。値はすべて
 *   - style-builder.cjs が :root へ実際に出力している CSS 変数 (SR-2-08 形式)
 *   - もしくは svg-builder.cjs が既に使っているリテラル (#FFFFFF / #F8F7F0 / #DCD7BA)
 * のいずれかであり、新しい色名・新しい変数を発明しない。
 *
 * 参考スキルから借りるのは「役割の分節 (paper / ink / muted / rule / accent)」
 * という構造であって、色そのものではない。
 */
const TOKENS = {
  /** カード地・不透明マスク。既存ビルダーの白カードと同一 */
  paper: '#FFFFFF',
  /** 副次的な面。既存 buildVs の項目行と同一 */
  paper2: '#F8F7F0',
  /** 主テキスト・主ストローク */
  ink: 'var(--fg, #43436c)',
  /** 副次テキスト・既定の矢印ストローク */
  muted: 'var(--fg-dim, #54546d)',
  /** 補助ラベル */
  soft: 'var(--fuji-gray, #8a8980)',
  /** ヘアライン。既存 buildVs のボーダーと同一 */
  rule: '#DCD7BA',
  ruleSolid: 'var(--fuji-gray, #8a8980)',
  /** 焦点 (1図解 1-2 件)。既存の強調色である桜ピンクを流用 */
  accent: 'var(--sakura-pink, #D27E99)',
  accentTint: 'rgba(210,126,153,0.14)',
  /** フロー・接続。既存の全ビルダーが矢印に使っている波青を流用 */
  link: 'var(--wave-blue, #7E9CD8)',
  white: '#FFFFFF',
};

/**
 * 系列色。既存 svg-builder.cjs の COLOR_PALETTE と**同一の順序**を保つ
 * (色替えを起こさないため。順序を変えると既存スライドの見た目が変わる)。
 */
const SERIES = [
  'var(--wave-blue, #7E9CD8)',
  'var(--wave-aqua, #7FB4CA)',
  'var(--sakura-pink, #D27E99)',
  'var(--autumn-yellow, #DCA561)',
  'var(--spring-violet, #957FB8)',
];

/** 旧 svg-builder との互換用エイリアス */
const VAR_BLUE = SERIES[0];
const VAR_AQUA = SERIES[1];
const VAR_PINK = SERIES[2];
const VAR_YELLOW = SERIES[3];
const VAR_VIOLET = SERIES[4];

/**
 * 線幅トークン。役割ごとに階層を持たせ、全ビルダーがここを参照する。
 *
 * なぜ「細ければ上品」でないか: SVG は必ず縮小されて表示される。viewBox 幅
 * 960-1080 の図解が記事本文幅 804px に入ると約 0.75 倍、スライドでも
 * 縦寸から逆算されて 0.7-0.9 倍になる。stroke-width 1 はそこで実効 0.7px と
 * なり、非 Retina では 1 デバイスピクセルを割ってアンチエイリアスで灰色に
 * 溶ける。印刷 (A4 174mm 幅) でも同様に潰れる。よって最も細い罫でも 1.25、
 * 意味を運ぶコネクタは 2 以上を下限にする。
 *
 * 階層は「太さ = 情報の重要度」で読ませるためのもので、太さが 1 種類しか
 * ないと全部が同じ強さで主張して視線の順序が生まれない。
 */
const STROKE = {
  /** 主コネクタ。図解の主張そのもの (フローの本線・矢印) */
  primary: 2.5,
  /** 副コネクタ。補足の流れ・戻り線 */
  secondary: 2,
  /** ノードの輪郭 */
  node: 1.5,
  /** 軸・基準線 */
  axis: 2,
  /** 補助罫・ゾーン境界・グリッド。これが最も細い許容値 */
  hairline: 1.25,
  /** ゲージ等の帯 (線でなく面として読ませる) */
  band: 24,
};

/**
 * 矢じり (marker) の幾何。**これが正本**。
 *
 * なぜ 1 箇所に固めるか: 従来 svg-kit の arrowMarkers (8×6 / refX=7) と
 * svg-builder の defs() (viewBox 10×8 / refX=9) が別々の形状を定義しており、
 * 同じ図の中でも経路によって矢じりの大きさと「先端がどこか」が変わっていた。
 * さらに ringArcPath の端点補正 (markerOverhang) はこの refX に依存するため、
 * 形状が二重定義だと補正量が常にどちらか片方で間違う。
 * 値は実際に report で使われている arrowMarkers 側 (8×6 / refX=7) に揃える。
 *
 *   overhang = w - refX  … 参照点 (線の終端) より先へ矢じりが張り出す長さ。
 *     refX は「線の終端に重ねる marker 内座標」なので、marker の右端 w との差が
 *     そのまま経路方向へのはみ出しになる。8 - 7 = 1 (marker 単位)。
 *     markerUnits="strokeWidth" なので実 px は overhang × stroke-width
 *     (→ markerOverhangPx)。
 */
const MARKER = {
  /** marker 座標系の幅 (= polygon の先端 x) */
  w: 8,
  /** marker 座標系の高さ (= 矢じりの開き) */
  h: 6,
  /** 線の終端に重ねる marker 内 x。先端 (w) より内側に置き、僅かに食い込ませる */
  refX: 7,
  /** 線の終端に重ねる marker 内 y (= h / 2) */
  refY: 3,
  /** 経路方向への張り出し量 (marker 単位) = w - refX */
  overhang: 1,
};

/** 矢じりの実 px 張り出し。markerUnits="strokeWidth" なので線幅に比例する */
function markerOverhangPx(strokeWidth = STROKE.primary) {
  return MARKER.overhang * strokeWidth;
}

/**
 * ノード種別 → 塗り/線の対応表。
 * diagram-design style-guide.md 「Node type → treatment」を、本ハーネスの
 * プレゼン用語彙 (塗りつぶしカード) と共存させた形で定義する。
 */
const NODE_STYLES = {
  /** 焦点 (1図解に 1-2 件まで) */
  focal: { fill: TOKENS.accentTint, stroke: TOKENS.accent, strokeWidth: STROKE.secondary, text: TOKENS.ink },
  /** 通常ノード: 白地 + ink 罫 (editorial grammar) */
  plain: { fill: TOKENS.white, stroke: TOKENS.ink, strokeWidth: STROKE.node, text: TOKENS.ink },
  /** 状態・保管 */
  store: { fill: 'rgba(67,67,108,0.05)', stroke: TOKENS.muted, strokeWidth: STROKE.node, text: TOKENS.ink },
  /** 外部システム */
  external: { fill: 'rgba(67,67,108,0.03)', stroke: 'rgba(67,67,108,0.30)', strokeWidth: STROKE.node, text: TOKENS.muted },
  /** 入力・利用者 */
  input: { fill: 'rgba(84,84,109,0.10)', stroke: TOKENS.soft, strokeWidth: STROKE.node, text: TOKENS.ink },
  /** 任意・非同期 */
  optional: { fill: 'rgba(67,67,108,0.02)', stroke: 'rgba(67,67,108,0.20)', strokeWidth: STROKE.node, dash: '4,3', text: TOKENS.muted },
  /** 境界・セキュリティ */
  boundary: { fill: 'rgba(210,126,153,0.05)', stroke: 'rgba(210,126,153,0.50)', strokeWidth: STROKE.node, dash: '4,4', text: TOKENS.muted },
};

/** 塗りつぶしカード (従来グラマー) の色から style を組み立てる */
function filledStyle(color) {
  return { fill: color, stroke: 'none', strokeWidth: 0, text: TOKENS.white };
}

/**
 * 要素ごとの色・ノード種別を解決する。
 *
 * これまでの svg-builder は `COLOR_PALETTE[i % 5]` 固定で、item 側が持つ
 * color / tone / focal といった指定を無視していた (「特性や色が反映されない」の原因)。
 * ここで入力の意図を一元的に汲み取る。
 *
 * @param {Array} items 図解要素
 * @param {object} opts
 *   - palette: 明示パレット (配列)
 *   - paletteMode: 'series' (既定・5色循環) | 'focal' (焦点のみ accent、他は muted)
 *   - accentIndex: 焦点にする index (paletteMode='focal' 時の既定は 0)
 * @returns {Array<{color:string, style:object, focal:boolean}>}
 */
function resolvePalette(items, opts = {}) {
  const list = Array.isArray(items) ? items : [];
  const palette = Array.isArray(opts.palette) && opts.palette.length ? opts.palette : SERIES;
  const mode = opts.paletteMode === 'focal' ? 'focal' : 'series';
  // 明示 focal を優先し、無指定なら accentIndex (focal モードのみ) を焦点とする
  const explicitFocal = list
    .map((it, i) => (it && typeof it === 'object' && (it.focal === true || it.accent === true) ? i : -1))
    .filter((i) => i >= 0);
  const focalSet = new Set(
    explicitFocal.length
      ? explicitFocal.slice(0, 2) // 焦点は最大2件 (SKILL.md §5 focal rule)
      : mode === 'focal'
        ? [Number.isInteger(opts.accentIndex) ? opts.accentIndex : 0]
        : []
  );

  return list.map((it, i) => {
    const focal = focalSet.has(i);
    const explicit = it && typeof it === 'object' ? (it.color || it.fill || null) : null;
    const tone = it && typeof it === 'object' ? it.tone || it.kind || null : null;
    if (tone && NODE_STYLES[tone]) {
      return { color: NODE_STYLES[tone].stroke, style: NODE_STYLES[tone], focal };
    }
    if (explicit) return { color: explicit, style: filledStyle(explicit), focal };
    if (focal) return { color: TOKENS.accent, style: filledStyle(TOKENS.accent), focal: true };
    const color = mode === 'focal' ? TOKENS.muted : palette[i % palette.length];
    return { color, style: filledStyle(color), focal: false };
  });
}

/* ============================================================
 * 2. テキスト計測 (日本語対応)
 * ============================================================ */

// 全角として扱う範囲 (CJK・かな・ハングル・全角記号/英数)
const RE_FULLWIDTH =
  /[ᄀ-ᅟ⺀-〾ぁ-㏿㐀-䶿一-鿿ꀀ-꓏가-힣豈-﫿︰-﹏＀-｠￠-￦]/;
// 半角カナ
const RE_HALFWIDTH_KANA = /[｡-ﾟ]/;

/**
 * 1 文字の幅を em 単位で返す。
 * Noto Sans JP + system sans の実測に寄せた近似値。
 * 従来の「1文字 = font-size px」一律換算は英数字で 2 倍近く過大評価しており、
 * カード幅と文字量の不一致 (無意味な位置での折返し) を生んでいた。
 */
function charWidth(ch) {
  if (RE_FULLWIDTH.test(ch)) return 1.0;
  if (RE_HALFWIDTH_KANA.test(ch)) return 0.5;
  const code = ch.charCodeAt(0);
  if (ch === ' ') return 0.28;
  if (code >= 48 && code <= 57) return 0.56; // 0-9
  if (code >= 65 && code <= 90) return 0.66; // A-Z
  if (code >= 97 && code <= 122) return 0.52; // a-z
  if (code < 128) return 0.34; // ASCII 約物
  return 0.62; // その他 (ラテン拡張・記号)
}

/** テキストの描画幅 (px) を推定する */
function measureText(text, fontSize) {
  let w = 0;
  const s = String(text == null ? '' : text);
  for (const ch of s) w += charWidth(ch);
  return w * fontSize;
}

/* ============================================================
 * 3. 折返し (禁則処理つき)
 * ============================================================ */

/** 行頭に置いてはならない文字 (行頭禁則) */
const FORBID_LINE_START = '、。，．・：；？！‼⁉ー―〜～）］｝」』】〉》〕｣”’ゝゞ々ぁぃぅぇぉっゃゅょゎヵヶァィゥェォッャュョヮ,.!?:;)]}〟＂＇';
/** 行末に置いてはならない文字 (行末禁則) */
const FORBID_LINE_END = '（［｛「『【〈《〔｢“‘([{〝';

/**
 * 改行候補位置の「良さ」を 0..1 で返す。
 *
 * wrapText は 1 行に収まる範囲の全候補位置を評価し、この score が最大の位置で
 * 改行する (同点なら行が長くなる側を選ぶ)。ここが「変なところで改行される」問題の
 * 判断中枢であり、日本語の読みやすさを決める設計判断そのもの。
 *
 * 参考: references/spec-registry.md §5-a（SR-5-04 改行位置の判断基準）
 *   優先度1 読点「、」の直後 / 優先度2 助詞の直後 / 優先度3 意味の切れ目 /
 *   優先度4 最大文字数に達した位置 (強制改行・非推奨)
 *
 * @param {string} before 改行位置の直前の文字 (行末になる文字)
 * @param {string} after  改行位置の直後の文字 (次行の先頭になる文字)
 * @returns {number} 0 = 避けたい / 1 = 理想的な改行位置
 */
function breakScore(before, after) {
  // 優先度1: 句読点の直後。文の切れ目そのものなので探索を打ち切ってよい
  if (before === '、' || before === '。' || before === '，' || before === '．') return 1;
  // 優先度1': 閉じ括弧・中黒・コロンの直後も強い切れ目
  if ('）］｝」』】〉》・：；'.includes(before)) return 0.95;
  // 優先度2: 助詞の直後。
  // ただし1文字助詞は語中にも現れる (「できる」の「で」、「ところ」の「と」)。
  // 助詞として機能しているなら次に来るのは語頭 = 漢字/カタカナ/英数である、
  // という近似で誤爆を防ぐ (「生成で|きる」を弾き「図解を|作る」を通す)。
  if (JA_PARTICLES.includes(before) && WORD_HEAD_CLASSES.has(charClass(after))) return 0.8;
  // 優先度2': 開き括弧の直前 (次行が括弧で始まるのは自然)
  if ('（［｛「『【〈《'.includes(after)) return 0.75;
  // 助詞が行頭に来る割り方は読みにくいので減点する (「…階層|を可視化する」)
  if (JA_PARTICLES.includes(after)) return 0.15;
  // 優先度3: 意味の切れ目 — 文字種の切り替わり (漢字↔かな↔カタカナ↔英数)
  if (charClass(before) !== charClass(after)) {
    // ひらがな→漢字は語頭である可能性が高く、特に良い切れ目
    if (charClass(before) === 'hira' && charClass(after) === 'kanji') return 0.7;
    return 0.55;
  }
  // 優先度3': 空白の直後
  if (before === ' ' || before === '　') return 0.6;
  // 優先度4: 同一文字種の連なりの途中 (漢字熟語やカタカナ語を割る) — 最後の手段
  return 0.1;
}

/** 助詞 (1文字のもののみ。複合助詞は文字種切替で拾う) */
const JA_PARTICLES = 'をがにではともへやのかね';

/** 語頭に立ちやすい文字種 (助詞判定の誤爆抑止に使う) */
const WORD_HEAD_CLASSES = new Set(['kanji', 'kata', 'latin', 'digit']);

/**
 * 改行候補の探索窓。行の充填率がこの比率を下回る位置は、たとえ改行品質が
 * 高くても採用しない (行長の不揃いを防ぐ)。0.65 = 行の 65% 以上は埋める。
 */
const LOOKBACK_RATIO = 0.65;

/** 文字種の判定 (意味の切れ目検出用) */
function charClass(ch) {
  if (!ch) return 'none';
  if (/[ぁ-ゖー]/.test(ch)) return 'hira';
  if (/[ァ-ヺｦ-ﾟ]/.test(ch)) return 'kata';
  if (/[一-鿿々〆ヵヶ]/.test(ch)) return 'kanji';
  if (/[0-9０-９]/.test(ch)) return 'digit';
  if (/[A-Za-zＡ-Ｚａ-ｚ]/.test(ch)) return 'latin';
  return 'other';
}

/**
 * 禁則を満たすかどうか。満たさない位置は候補から除外する。
 */
function breakAllowed(before, after) {
  if (!before || !after) return false;
  if (FORBID_LINE_START.includes(after)) return false;
  if (FORBID_LINE_END.includes(before)) return false;
  // 半角英数の語中では割らない (アルファベット/数字が両側に連続する位置)
  if (/[0-9A-Za-z]/.test(before) && /[0-9A-Za-z]/.test(after)) return false;
  return true;
}

/**
 * 指定幅に収まるよう折り返す。
 *
 * アルゴリズム:
 *   1. 明示改行 (\n) は常に尊重する。
 *   2. 各行について、幅上限を超えない最大の位置までを候補範囲とする。
 *   3. 候補範囲内で breakAllowed を満たす位置を breakScore で採点し最良点で割る。
 *   4. 候補が皆無 (長い英単語など) の場合のみ幅上限位置で強制改行する。
 *
 * breakScore が未実装 (数値を返さない) 間は score=0 とみなし、
 * 「幅上限での強制改行」= 従来挙動へ安全に縮退する。
 *
 * @returns {{lines: string[], truncated: boolean}}
 */
function wrapText(text, maxWidth, fontSize, opts = {}) {
  const maxLines = opts.maxLines || 0;
  const ellipsis = opts.ellipsis !== false;
  const src = String(text == null ? '' : text);
  if (!src) return { lines: [], truncated: false };
  if (maxWidth <= 0) return { lines: [src], truncated: false };

  const out = [];
  for (const paragraph of src.split('\n')) {
    let rest = paragraph;
    while (rest.length > 0) {
      if (measureText(rest, fontSize) <= maxWidth) {
        out.push(rest);
        rest = '';
        break;
      }
      // 幅上限に収まる最大文字数 limit を求める
      let w = 0;
      let limit = 0;
      const chars = Array.from(rest);
      for (let i = 0; i < chars.length; i++) {
        const cw = charWidth(chars[i]) * fontSize;
        if (w + cw > maxWidth) break;
        w += cw;
        limit = i + 1;
      }
      if (limit <= 0) limit = 1; // 1文字も入らない極端な幅でも進行させる

      // 候補位置を採点 (cut = 行に含める文字数)。
      // 探索窓を limit の LOOKBACK_RATIO 倍までに限定するのが要点。
      // 窓が無いと「スコアは高いが極端に短い行」が選ばれて行長が不揃いになる
      // (例:「しっかりと」で切って次行が長くなる)。行の充填率と改行品質の
      // 両立は、品質最大化ではなく「十分埋まった候補の中での品質最大化」で得る。
      const minCut = Math.max(1, Math.ceil(limit * LOOKBACK_RATIO));
      let bestCut = -1;
      let bestScore = -1;
      for (let cut = limit; cut >= minCut; cut--) {
        const before = chars[cut - 1];
        const after = chars[cut];
        if (!breakAllowed(before, after)) continue;
        const raw = breakScore(before, after);
        const score = Number.isFinite(raw) ? clamp(raw, 0, 1) : 0;
        if (score > bestScore) {
          bestScore = score;
          bestCut = cut;
        }
        if (score >= 1) break; // 理想位置が見つかればそれ以上遡らない
      }
      let cut = bestCut > 0 ? bestCut : limit;
      // ぶら下げ: 直後が行頭禁則文字なら 1 文字だけ現行行へ取り込む
      if (cut < chars.length && FORBID_LINE_START.includes(chars[cut])) {
        cut += 1;
      }
      // 孤立回避: 最終行が 1-2 文字だけになるなら手前で切って行末へ寄せる
      // (「…ほしいで / す。」のような尻切れを防ぐ)
      const orphan = chars.length - cut;
      if (orphan >= 1 && orphan <= 2) {
        const back = 3 - orphan; // 残り1文字なら2戻し、2文字なら1戻す
        const alt = cut - back;
        if (alt >= minCut && breakAllowed(chars[alt - 1], chars[alt])) cut = alt;
      }
      out.push(chars.slice(0, cut).join('').replace(/\s+$/, ''));
      rest = chars.slice(cut).join('').replace(/^\s+/, '');
    }
    if (paragraph === '') out.push('');
  }

  if (maxLines > 0 && out.length > maxLines) {
    const kept = out.slice(0, maxLines);
    if (ellipsis && kept.length) {
      let last = kept[kept.length - 1];
      while (last.length > 1 && measureText(last + '…', fontSize) > maxWidth) {
        last = last.slice(0, -1);
      }
      kept[kept.length - 1] = last + '…';
    }
    return { lines: kept, truncated: true };
  }
  return { lines: out, truncated: false };
}

/**
 * 箱に収まるフォントサイズと行を決める。
 *
 * 「カードのサイズと文字のサイズが合わずに変なところで改行が入る」への直接の対策。
 * maxFont から 1px ずつ下げ、行数・総高さの両方が箱に収まる最大サイズを採用する。
 * 下限 (既定 MIN_FONT) でも収まらない場合のみ省略記号で切り詰める。
 *
 * @returns {{fontSize:number, lines:string[], lineHeight:number, height:number, truncated:boolean}}
 */
function fitText(text, boxW, boxH, opts = {}) {
  const padX = opts.padX != null ? opts.padX : 12;
  const padY = opts.padY != null ? opts.padY : 8;
  const minFont = opts.minFont || MIN_FONT;
  const maxFont = Math.max(minFont, opts.maxFont || 22);
  const maxLines = opts.maxLines || 0;
  const innerW = Math.max(8, boxW - padX * 2);
  const innerH = Math.max(8, boxH - padY * 2);
  const ratio = opts.lineHeightRatio || LINE_HEIGHT_RATIO;

  // 円形ノードのように幅が中心から離れるほど急に狭まる箱では、1 段小さくしてでも
  // 1 行に収めたほうが読みやすい。「改善につ / なげる」のような語中改行は、
  // フォントを 2px 落とした 1 行より確実に読みにくいため、下限を渡された場合だけ
  // 通常の「最大フォント優先」より 1 行化を優先する。
  const singleFloor = opts.singleLineFloor || 0;
  if (singleFloor) {
    const flat = String(text);
    for (let fs = maxFont; fs >= singleFloor; fs--) {
      if (measureText(flat, fs) <= innerW && fs <= innerH) {
        return {
          fontSize: fs, lines: [flat],
          lineHeight: Math.round(fs * ratio), height: fs, truncated: false,
        };
      }
    }
  }

  for (let fs = maxFont; fs >= minFont; fs--) {
    const { lines, truncated } = wrapText(text, innerW, fs, { maxLines: 0 });
    if (truncated) continue;
    const lineHeight = Math.round(fs * ratio);
    const height = lines.length ? (lines.length - 1) * lineHeight + fs : 0;
    const lineCap = maxLines > 0 ? lines.length <= maxLines : true;
    if (lineCap && height <= innerH) {
      return { fontSize: fs, lines, lineHeight, height, truncated: false };
    }
  }
  // 下限でも収まらない: 行数上限を算出して切り詰める
  const fs = minFont;
  const lineHeight = Math.round(fs * ratio);
  const capByBox = Math.max(1, Math.floor((innerH - fs) / lineHeight) + 1);
  const cap = maxLines > 0 ? Math.min(maxLines, capByBox) : capByBox;
  const { lines, truncated } = wrapText(text, innerW, fs, { maxLines: cap });
  const height = lines.length ? (lines.length - 1) * lineHeight + fs : 0;
  return { fontSize: fs, lines, lineHeight, height, truncated };
}

/**
 * テキスト量から必要な箱の高さを求める (カード高さの動的化)。
 * 固定 cardH で溢れる/余る問題を解消する。
 */
function autoBlockHeight(text, boxW, opts = {}) {
  const padX = opts.padX != null ? opts.padX : 12;
  const padY = opts.padY != null ? opts.padY : 8;
  const fs = opts.fontSize || 16;
  const ratio = opts.lineHeightRatio || LINE_HEIGHT_RATIO;
  const innerW = Math.max(8, boxW - padX * 2);
  const { lines } = wrapText(text, innerW, fs, { maxLines: opts.maxLines || 0 });
  const lineHeight = Math.round(fs * ratio);
  const h = lines.length ? (lines.length - 1) * lineHeight + fs : fs;
  return snap(h + padY * 2);
}

/* ============================================================
 * 4. 幾何ソルバ
 * ============================================================ */

/**
 * 中心から単位ベクトル u 方向へ進んだとき、半幅 halfW / 半高 halfH の矩形の
 * 境界に到達するまでの距離。(diagram-design type-loop.md §2.3)
 */
function boxRayDistance(ux, uy, halfW, halfH) {
  const cands = [];
  if (Math.abs(ux) > 1e-9) cands.push(halfW / Math.abs(ux));
  if (Math.abs(uy) > 1e-9) cands.push(halfH / Math.abs(uy));
  return cands.length ? Math.min(...cands) : Math.min(halfW, halfH);
}

/**
 * 中心 C・半径 R の円と、中心 (bx, by)・半幅/半高 の矩形との交点を返す。
 * (diagram-design type-loop.md §2.2)
 * @returns {Array<{x:number,y:number,theta:number}>} 角度昇順ではなく生の交点列
 */
function circleBoxIntersections(cx, cy, R, bx, by, halfW, halfH) {
  const pts = [];
  const push = (x, y) => {
    pts.push({ x, y, theta: Math.atan2(y - cy, x - cx) });
  };
  // 垂直辺 x = bx ± halfW
  for (const xe of [bx - halfW, bx + halfW]) {
    const d = R * R - (xe - cx) * (xe - cx);
    if (d < 0) continue;
    const root = Math.sqrt(d);
    for (const y of [cy + root, cy - root]) {
      if (y >= by - halfH - 1e-6 && y <= by + halfH + 1e-6) push(xe, y);
    }
  }
  // 水平辺 y = by ± halfH
  for (const ye of [by - halfH, by + halfH]) {
    const d = R * R - (ye - cy) * (ye - cy);
    if (d < 0) continue;
    const root = Math.sqrt(d);
    for (const x of [cx + root, cx - root]) {
      if (x >= bx - halfW - 1e-6 && x <= bx + halfW + 1e-6) push(x, ye);
    }
  }
  return pts;
}

/** 角度を [0, 2π) へ正規化 */
function normAngle(a) {
  const t = a % (Math.PI * 2);
  return t < 0 ? t + Math.PI * 2 : t;
}

/**
 * リング上のノード k から時計回りに出る点 (exit) と、ノード j へ入る点 (entry) を求める。
 * ノード中心角 theta の前後で交点を分類する。
 * @returns {{exit:{x,y,theta}|null, entry:{x,y,theta}|null}}
 */
function ringNodePorts(cx, cy, R, theta, halfW, halfH) {
  const bx = cx + R * Math.cos(theta);
  const by = cy + R * Math.sin(theta);
  const pts = circleBoxIntersections(cx, cy, R, bx, by, halfW, halfH);
  if (pts.length < 2) return { exit: null, entry: null };
  // theta を基準に時計回り (角度増加方向) の距離で分類
  let exit = null;
  let entry = null;
  let exitDelta = Infinity;
  let entryDelta = Infinity;
  for (const p of pts) {
    const fwd = normAngle(p.theta - theta); // 時計回りに進んだ量
    const bwd = normAngle(theta - p.theta); // 反時計回りに進んだ量
    if (fwd <= bwd) {
      if (fwd < exitDelta) { exitDelta = fwd; exit = p; }
    } else if (bwd < entryDelta) { entryDelta = bwd; entry = p; }
  }
  return { exit, entry };
}

/**
 * ノード k → ノード j のリング弧パス (時計回り)。
 *
 * 旧 buildCycle は端点を半径 (R - rNode - 6) の円上に置きながら弧半径に R を
 * 指定していたため、SVG 側で半径が強制補正され弧の膨らみと矢じりの向きが崩れていた。
 * ここでは端点も弧半径も同一の R に揃え、marker overhang 分だけ手前で止める。
 *
 * @param {number} markerOverhang 矢じりの張り出し量。既定は MARKER.overhang
 *   (= MARKER.w - MARKER.refX)。ここを marker 形状と別に持つと、形状を変えた
 *   ときに補正だけが取り残されて矢じりがノードへ食い込む/浮くため正本を参照する。
 * @returns {string|null} SVG path の d 属性
 */
function ringArcPath(cx, cy, R, thetaFrom, thetaTo, halfW, halfH, markerOverhang = MARKER.overhang) {
  const from = ringNodePorts(cx, cy, R, thetaFrom, halfW, halfH).exit;
  const to = ringNodePorts(cx, cy, R, thetaTo, halfW, halfH).entry;
  if (!from || !to) return null;
  const phiEnd = to.theta - markerOverhang / R;
  const ex = cx + R * Math.cos(phiEnd);
  const ey = cy + R * Math.sin(phiEnd);
  // 隣接ノード間は常に 180 度未満なので large-arc = 0、時計回りなので sweep = 1
  const largeArc = normAngle(phiEnd - from.theta) > Math.PI ? 1 : 0;
  return `M${num(from.x)},${num(from.y)} A ${num(R)} ${num(R)} 0 ${largeArc} 1 ${num(ex)},${num(ey)}`;
}

/**
 * 直交エルボ (角丸付き) のパス。
 * 軸を共有しないノード間の斜め直線は diagram-design SKILL.md §6 rule 1 で禁止。
 * @param {'h'|'v'} first 最初に進む向き ('h' = 水平から)
 */
function elbowPath(x1, y1, x2, y2, opts = {}) {
  const r = opts.radius || 8;
  const first = opts.first === 'v' ? 'v' : 'h';
  if (Math.abs(y1 - y2) < 0.5) return `M${num(x1)},${num(y1)} H${num(x2)}`;
  if (Math.abs(x1 - x2) < 0.5) return `M${num(x1)},${num(y1)} V${num(y2)}`;

  // opts.mid = 折れ位置 (first==='h' なら x、'v' なら y) の明示指定。
  // 既定の中点だと、同じ段の間を走る複数本が全部同じ高さで横走りし、
  // 区間が重なった箇所で 2 本が 1 本に見える (本数が読めない)。
  // 呼び出し側が本数分の車線へ散らせるようにここを開ける。
  if (first === 'h') {
    const mid = opts.mid != null ? opts.mid : (x1 + x2) / 2;
    const sx = Math.sign(x2 - x1) || 1;
    const sy = Math.sign(y2 - y1) || 1;
    const rr = Math.min(r, Math.abs(x2 - x1) / 2, Math.abs(y2 - y1) / 2);
    return (
      `M${num(x1)},${num(y1)} H${num(mid - sx * rr)} ` +
      `Q${num(mid)},${num(y1)} ${num(mid)},${num(y1 + sy * rr)} ` +
      `V${num(y2 - sy * rr)} ` +
      `Q${num(mid)},${num(y2)} ${num(mid + sx * rr)},${num(y2)} ` +
      `H${num(x2)}`
    );
  }
  const mid = opts.mid != null ? opts.mid : (y1 + y2) / 2;
  const sx = Math.sign(x2 - x1) || 1;
  const sy = Math.sign(y2 - y1) || 1;
  const rr = Math.min(r, Math.abs(x2 - x1) / 2, Math.abs(y2 - y1) / 2);
  return (
    `M${num(x1)},${num(y1)} V${num(mid - sy * rr)} ` +
    `Q${num(x1)},${num(mid)} ${num(x1 + sx * rr)},${num(mid)} ` +
    `H${num(x2 - sx * rr)} ` +
    `Q${num(x2)},${num(mid)} ${num(x2)},${num(mid + sy * rr)} ` +
    `V${num(y2)}`
  );
}

/**
 * 迂回経路 (同じ辺から出て同じ辺へ入る U 字)。
 *
 * elbowPath は始点と終点の y が等しいと水平 1 本を返す。行内で間のノードを
 * 跨ぐ遷移をそれで引くと、途中の箱を線が貫き「その箱を経由する」と誤読される。
 * 帯 (level) までいったん外へ出し、そこを走らせてから戻す。
 *
 * @param {number} level 横走りさせる y (行の外の空き帯)
 */
function detourPath(x1, y1, x2, y2, level, opts = {}) {
  const r = opts.radius || 8;
  const sx = Math.sign(x2 - x1) || 1;
  const s1 = Math.sign(level - y1) || 1;
  const s2 = Math.sign(y2 - level) || 1;
  const rr = Math.max(0, Math.min(
    r, Math.abs(x2 - x1) / 2, Math.abs(level - y1), Math.abs(y2 - level)));
  return (
    `M${num(x1)},${num(y1)} V${num(level - s1 * rr)} ` +
    `Q${num(x1)},${num(level)} ${num(x1 + sx * rr)},${num(level)} ` +
    `H${num(x2 - sx * rr)} ` +
    `Q${num(x2)},${num(level)} ${num(x2)},${num(level + s2 * rr)} ` +
    `V${num(y2)}`
  );
}

/* ---- マーカー可視性 (入射規則) --------------------------------- */

/**
 * 点 p が矩形 box のどの辺に載っているか (最も近い辺) を返す。
 * @returns {'left'|'right'|'top'|'bottom'|null}
 */
function nearestEdge(p, box) {
  if (!box || !Number.isFinite(box.x) || !Number.isFinite(box.w)) return null;
  const d = {
    left: Math.abs(p.x - box.x),
    right: Math.abs(box.x + box.w - p.x),
    top: Math.abs(p.y - box.y),
    bottom: Math.abs(box.y + box.h - p.y),
  };
  let best = null;
  let bestD = Infinity;
  for (const k of ['left', 'right', 'top', 'bottom']) {
    if (d[k] < bestD) { bestD = d[k]; best = k; }
  }
  return best;
}

/**
 * 辺ごとの「許容される入射」。矢じりは経路方向へ MARKER.overhang ぶん張り出すので、
 * 外向き法線と逆向き (= 辺の内側から外へ向かって当てる) に入射させると、
 * 矢の胴体が矩形の内側へ埋まり読者には矢頭しか見えない。図の向き = 主張の向きが
 * 伝わらなくなるため、許容は下記 4 通りだけとする。
 *   左辺 ← 右向き (dx > 0) / 右辺 ← 左向き (dx < 0)
 *   上辺 ← 下向き (dy > 0) / 下辺 ← 上向き (dy < 0)
 */
const INCIDENCE_RULE = {
  left: { axis: 'h', dir: 1 },
  right: { axis: 'h', dir: -1 },
  top: { axis: 'v', dir: 1 },
  bottom: { axis: 'v', dir: -1 },
};

/**
 * elbowPath が実際に「宛先へ入る」ときの軸と向きを求める。
 * elbowPath は first='h' なら最後が H (水平入射)、first='v' なら最後が V (垂直入射)。
 * 直線に縮退する場合 (dx≈0 / dy≈0) は first に関係なくその軸で入射する。
 */
function elbowIncidence(x1, y1, x2, y2, first) {
  if (Math.abs(y1 - y2) < 0.5) return { axis: 'h', dir: Math.sign(x2 - x1) || 1 };
  if (Math.abs(x1 - x2) < 0.5) return { axis: 'v', dir: Math.sign(y2 - y1) || 1 };
  return first === 'v'
    ? { axis: 'v', dir: Math.sign(y2 - y1) || 1 }
    : { axis: 'h', dir: Math.sign(x2 - x1) || 1 };
}

/**
 * 矢じりが読める向きで宛先へ入るエルボ。
 *
 * elbowPath の屈曲順 (水平優先 / 垂直優先) を、INCIDENCE_RULE を満たす側へ
 * 自動選択する。どちらでも満たせない配置 (ノードが重なっている・宛先の辺の
 * 外側に発点が無い等) では従来どおりの経路を返し、incidence='degraded' と
 * 申告する。呼出し側はこれを見て「その線は引かない」判断ができる。
 *
 * 既存 elbowPath のシグネチャと挙動は変えない (呼出し側が多数あるため)。
 *
 * @param {{x:number,y:number}} from 発点 (通常は srcBox の辺上)
 * @param {{x:number,y:number}} to   着点 (通常は dstBox の辺上)
 * @param {object} srcBox 発ノード矩形 (任意。同点なら屈曲順の優先に使う)
 * @param {object} dstBox 宛先ノード矩形 (任意。無ければ入射規則を課さない)
 * @returns {{d:string, incidence:'ok'|'degraded', first:'h'|'v'}}
 */
function safeElbow(from, to, srcBox, dstBox, opts = {}) {
  const fallbackFirst = opts.first === 'v' ? 'v' : 'h';
  const build = (first) => elbowPath(from.x, from.y, to.x, to.y, { ...opts, first });
  const edge = nearestEdge(to, dstBox);
  const rule = edge ? INCIDENCE_RULE[edge] : null;
  if (!rule) return { d: build(fallbackFirst), incidence: 'ok', first: fallbackFirst };

  // 発ノードの辺に合わせた優先順。'h' で出る辺 (左右) から出発する線は
  // 水平優先のほうが折れ数が少なく読みやすいので、同点時はそちらを先に試す。
  const srcEdge = nearestEdge(from, srcBox);
  const prefer = srcEdge && INCIDENCE_RULE[srcEdge] ? INCIDENCE_RULE[srcEdge].axis : fallbackFirst;
  const order = prefer === 'v' ? ['v', 'h'] : ['h', 'v'];

  for (const first of order) {
    const inc = elbowIncidence(from.x, from.y, to.x, to.y, first);
    if (inc.axis === rule.axis && inc.dir === rule.dir) {
      return { d: build(first), incidence: 'ok', first };
    }
  }
  return { d: build(fallbackFirst), incidence: 'degraded', first: fallbackFirst };
}

/* ---- 分岐の束ね ------------------------------------------------- */

/**
 * 同一辺に並ぶ矢じり同士が重ならない最小間隔。
 *
 * 導出: 矢じりは markerUnits="strokeWidth" なので実寸は marker 座標 × 線幅。
 * 辺へ正対して入る矢の「辺に沿った見かけの幅」は MARKER.h × stroke-width で、
 * 主コネクタ (STROKE.primary) を最悪ケースとすると 6 × 2.5 = 15px。
 * これを 4px グリッドへ寄せて 16px を下限とする (snap(MARKER.h * STROKE.primary))。
 * 新しいマジックナンバーではなく MARKER / STROKE からの導出値。
 */
const FAN_MIN_GAP = snap(MARKER.h * STROKE.primary);

/**
 * 辺長 length に、FAN_MIN_GAP を保って何本まで取り付けられるか。
 * 取付点は L*k/(N+1) なので間隔は L/(N+1)。
 *   L/(N+1) >= FAN_MIN_GAP  ⇔  N <= L/FAN_MIN_GAP - 1
 * 呼出し側はこれを容量判定に使い、超える本数は図に載せない (契約 §2)。
 */
function fanCapacity(length) {
  return Math.max(1, Math.floor(length / FAN_MIN_GAP) - 1);
}

/**
 * 同一辺から複数コネクタが出る場合の取付点。
 * 辺長 L・本数 N のとき k 番目 (1..N) は L * k / (N + 1)。
 * (diagram-design SKILL.md §6 rule 4)
 *
 * count が fanCapacity を超える場合は「収まる本数」まで詰めて配置する。
 * 上限なしに等分すると矢じりが重なって束が黒い塊になり、何本あるのかすら
 * 読めなくなるため、間隔のほうを不変量として守る。
 * count<=1 は従来どおり辺の中央を返す (既存呼出しの挙動は変わらない)。
 */
function fanAttach(start, length, index, count) {
  const cap = fanCapacity(length);
  const n = Math.max(1, Math.min(count, cap));
  const k = clamp(index, 0, n - 1);
  return start + (length * (k + 1)) / (n + 1);
}

/**
 * 1→多 分岐を 1 本のトランクへ束ねる経路群。
 *
 * 1 対 1 の elbowPath を独立に引くと、各線が自分の中点で折れるため 4 分岐で
 * 4 本が別々の x で曲がり「束」に見えない (どこで分岐したのかが読めない)。
 * 発ノードの外に単一の trunkX を立て、[水平 → トランクで垂直 → 各宛先へ水平]
 * の 3 セグメントに統一する。全セグメントが軸平行なので D5 も自動的に満たす。
 *
 * trunkY を渡さないと横走りを宛先の上辺 (p.y) で行う。宛先が矩形ノードだと
 * この横線が枠線と同一直線上に重なり、線が枠に溶けて消え、矢じりも横向きの
 * まま辺へ刺さる (「分岐が描かれていない」ように見える)。段組の図では必ず
 * 段間の空きへ trunkY を立て、最後に垂直で上辺へ落として矢じりを下向きにする。
 *
 * @param {{x:number,y:number}} srcPort 発ノードの取付点
 * @param {Array<{x:number,y:number}>} dstPorts 宛先の取付点 (fanAttach で分散済み)
 * @param {number} trunkX 縦に走らせるトランクの x
 * @param {number} [trunkY] 横走りの y。省略時は宛先の上辺 (後方互換)
 * @returns {Array<{d:string, arrow:boolean}>} 幹 (arrow=false) と枝 (arrow=true)
 */
function trunkPaths(srcPort, dstPorts, trunkX, trunkY) {
  const list = Array.isArray(dstPorts) ? dstPorts.filter(Boolean) : [];
  const out = [];
  // 同じ y ならトランクを経由せず 1 本の水平線で足りる (無駄な折れを作らない)
  const branched = [];
  list.forEach((p) => {
    if (Math.abs(p.y - srcPort.y) < 0.5) {
      out.push({ d: `M${num(srcPort.x)},${num(srcPort.y)} H${num(p.x)}`, arrow: true });
    } else {
      branched.push(p);
    }
  });
  if (!branched.length) return out;

  // 幹は 1 本だけ引き、枝には自分だけの区間を持たせる。宛先ごとに発ノードから
  // フルパスを引くと共有区間へ同じストロークが n 本重なり、半透明では幹だけ
  // 濃くなるうえ、重なった区間では「何本あるのか」が数えられない。
  if (trunkY == null) {
    // 縦の幹を最遠の宛先まで下ろし、枝は各自の高さで横へ出るだけにする。
    const deepest = branched.reduce((m, p) => (p.y > m ? p.y : m), branched[0].y);
    out.push({
      d: `M${num(srcPort.x)},${num(srcPort.y)} H${num(trunkX)} V${num(deepest)}`,
      arrow: false,
    });
    branched.forEach((p) => {
      if (Math.abs(p.x - trunkX) < 0.5) return; // 幹がそのまま宛先へ着いている
      out.push({ d: `M${num(trunkX)},${num(p.y)} H${num(p.x)}`, arrow: true });
    });
    return out;
  }

  // 段間の trunkY へ落とし、そこで横一本の母線を張り、枝は垂直に落とすだけ。
  out.push({
    d: `M${num(srcPort.x)},${num(srcPort.y)} H${num(trunkX)} V${num(trunkY)}`,
    arrow: false,
  });
  const xs = branched.map((p) => p.x).concat([trunkX]);
  const minX = Math.min.apply(null, xs);
  const maxX = Math.max.apply(null, xs);
  if (maxX - minX >= 0.5) {
    out.push({ d: `M${num(minX)},${num(trunkY)} H${num(maxX)}`, arrow: false });
  }
  branched.forEach((p) => {
    out.push({ d: `M${num(p.x)},${num(trunkY)} V${num(p.y)}`, arrow: true });
  });
  return out;
}

/**
 * 昇格弧 (隣接カードの上辺どうしを結ぶ 3 次ベジエ)。
 *
 * 制御点を各アンカーの真上 (bandTop の y) に置くのが要点。端点での接線が鉛直に
 * なるので、着地側は「上辺へ下向き」= INCIDENCE_RULE.top を自動的に満たし、
 * 矢じりが上辺へ正対して入る。斜めに着地する弧は矢じりが辺へ食い込んで
 * 向きが読めなくなる。
 *
 * bandTop は Math.max(0, …) で clamp する。D1 は path の通過点しか測らず弧の
 * 膨らみを見逃す (契約 §4「意図的な検出漏れ」) ため、viewBox 上端をはみ出さない
 * 保証は実装側で持つ必要がある。
 */
function overArcPath(x1, y1, x2, y2, bandTop) {
  const top = Math.max(0, Number.isFinite(bandTop) ? bandTop : 0);
  return `M${num(x1)},${num(y1)} C${num(x1)},${num(top)} ${num(x2)},${num(top)} ${num(x2)},${num(y2)}`;
}

/**
 * overArcPath の頂点 (t=0.5 の点)。ラベルはこの直下へ置けば曲線と交差しないので
 * マスクが要らない。B(0.5) = (P0 + 3P1 + 3P2 + P3) / 8 を展開したもの。
 */
function overArcApex(x1, y1, x2, y2, bandTop) {
  const top = Math.max(0, Number.isFinite(bandTop) ? bandTop : 0);
  return { x: (x1 + x2) / 2, y: (y1 + y2 + 6 * top) / 8 };
}

/* ============================================================
 * 5. 描画プリミティブ
 * ============================================================ */

/** marker id に使える安全なキーへ変換 */
function markerKey(color) {
  return String(color).replace(/[^a-zA-Z0-9]/g, '').slice(-16) || 'default';
}

/**
 * 名前→色 の対応表から `<defs>` の marker 定義文字列を作る。
 *
 * 形状はすべて MARKER (§1 の正本) から生成する。svg-builder / svg-structures が
 * それぞれ自前の marker を書くと形状が分岐して ringArcPath の端点補正が壊れるため、
 * 「marker を出すなら必ずここを通る」入口を 1 本だけ用意する。
 *
 * @param {object|Array<string>} colors {name: color} か色の配列 (配列は markerKey で命名)
 * @returns {string} `<defs>…</defs>`
 */
function markerDefs(colors) {
  const map = Array.isArray(colors)
    ? colors.reduce((acc, c) => { acc[markerKey(c)] = c; return acc; }, {})
    : (colors && typeof colors === 'object' ? colors : {});
  const markers = Object.entries(map).map(
    ([name, color]) =>
      `<marker id="arrow-${name}" markerWidth="${num(MARKER.w)}" markerHeight="${num(MARKER.h)}" refX="${num(MARKER.refX)}" refY="${num(MARKER.refY)}" orient="auto" markerUnits="strokeWidth">` +
      `<polygon points="0 0, ${num(MARKER.w)} ${num(MARKER.refY)}, 0 ${num(MARKER.h)}" fill="${color}"/></marker>`
  );
  return `<defs>\n    ${markers.join('\n    ')}\n  </defs>`;
}

/**
 * 矢印マーカー定義。
 * 既定 (muted) / 焦点 (accent) / 外部 (link) / 補助 (soft) の 4 種を常に定義し、
 * 旧 svg-builder 互換の arrow-blue/pink/aqua/yellow/violet も併せて出力する。
 * 形状は MARKER が正本 (stroke-width 1.2-3 に対して視認できる 8×6)。
 */
function arrowMarkers(extraColors = []) {
  const base = {
    muted: TOKENS.muted,
    accent: TOKENS.accent,
    link: TOKENS.link,
    soft: TOKENS.soft,
    ink: TOKENS.ink,
    blue: VAR_BLUE,
    aqua: VAR_AQUA,
    pink: VAR_PINK,
    yellow: VAR_YELLOW,
    violet: VAR_VIOLET,
  };
  for (const c of extraColors) base[markerKey(c)] = c;
  return markerDefs(base);
}

/** 色から marker-end の url を得る (未知色は extraColors 経由で定義済みの前提) */
function arrowUrl(color) {
  const named = { [TOKENS.muted]: 'muted', [TOKENS.accent]: 'accent', [TOKENS.link]: 'link', [TOKENS.soft]: 'soft', [TOKENS.ink]: 'ink', [VAR_BLUE]: 'blue', [VAR_AQUA]: 'aqua', [VAR_PINK]: 'pink', [VAR_YELLOW]: 'yellow', [VAR_VIOLET]: 'violet' };
  return `url(#arrow-${named[color] || markerKey(color)})`;
}

/**
 * 折返し済みテキストブロックを描画する。
 * @param {object} o
 *   - x, y: y は valign により基準が変わる ('middle' なら行ブロックの垂直中心)
 *   - lines: 事前に wrapText/fitText で得た行配列
 *   - valign: 'middle' (既定) | 'top'
 */
function textBlock(o) {
  const lines = (o.lines || []).filter((l) => l !== undefined && l !== null);
  if (!lines.length) return '';
  const fontSize = o.fontSize || MIN_FONT;
  const lineHeight = o.lineHeight || Math.round(fontSize * LINE_HEIGHT_RATIO);
  const anchor = o.anchor || 'middle';
  const fill = o.fill || TOKENS.ink;
  const weight = o.weight != null ? o.weight : 600;
  const family = o.family || "'Noto Sans JP', 'Hiragino Sans', 'Yu Gothic', sans-serif";
  const blockH = (lines.length - 1) * lineHeight;
  // baseline 位置: middle は視覚中心へ寄せるため fontSize*0.35 補正
  const firstY =
    (o.valign === 'top' ? o.y + fontSize * 0.85 : o.y - blockH / 2 + fontSize * 0.35);
  const tspans = lines
    .map((ln, i) => `<tspan x="${num(o.x)}" dy="${i === 0 ? 0 : lineHeight}">${escapeXml(ln)}</tspan>`)
    .join('');
  const letter = o.letterSpacing ? ` letter-spacing="${o.letterSpacing}"` : '';
  return `<text x="${num(o.x)}" y="${num(firstY)}" text-anchor="${anchor}" fill="${fill}" font-size="${fontSize}" font-weight="${weight}" font-family="${family}"${letter}>${tspans}</text>`;
}

/**
 * 箱の中にテキストを自動フィットさせて描画する (最頻出の合成プリミティブ)。
 */
function fittedTextInBox(text, box, opts = {}) {
  if (!text) return '';
  const fit = fitText(text, box.w, box.h, opts);
  return textBlock({
    x: box.x + box.w / 2,
    y: box.y + box.h / 2,
    lines: fit.lines,
    fontSize: fit.fontSize,
    lineHeight: fit.lineHeight,
    anchor: 'middle',
    fill: opts.fill || TOKENS.ink,
    weight: opts.weight != null ? opts.weight : 700,
  });
}

/**
 * コネクタ上のラベル。不透明マスク + 6-10px ギャップを強制する。
 * (diagram-design SKILL.md §6 rule 2 / 「Arrow labels」)
 * @param {'above'|'right'} side 水平線なら above、垂直線なら right
 * @param {'mid'|'start'} anchor 基準点の意味。既定 'mid' は (x,y) を経路中点として
 *   扱う従来挙動。'start' は (x,y) を経路の始点として扱い、発ノードの直後へ置く。
 * @param {'right'|'left'|'down'|'up'} dir anchor='start' のときの第1セグメント方向
 */
function arrowLabel(text, x, y, opts = {}) {
  if (!text) return '';
  const fontSize = opts.fontSize || MIN_FONT_SMALL;
  const gap = opts.gap || LABEL_GAP;
  const paper = opts.paper || TOKENS.paper;
  const fill = opts.fill || TOKENS.soft;
  // 文字数での切り詰めはしない。指定幅 (既定 140px) で最大2行へ折り返す
  const maxW = opts.maxWidth || 140;
  const lineHeight = fontSize + 4;
  const lines = wrapText(String(text), maxW, fontSize, { maxLines: opts.maxLines || 2 }).lines;
  // マスクは <rect> なので D6 (4px グリッド) の検査対象。文字がはみ出さないよう
  // 実測幅・行送りからの必要寸法を切り上げでグリッドへ載せる。
  const w = snapUp(Math.max(...lines.map((l) => measureText(l, fontSize))) + 12);
  const h = snapUp(lines.length * lineHeight + 6);
  const side = opts.side === 'right' ? 'right' : 'above';
  let rx = side === 'above' ? x - w / 2 : x + gap;
  let ry = side === 'above' ? y - gap - h : y - h / 2;
  let tx = side === 'above' ? x : x + gap + w / 2;

  // 始点側配置。日本語ラベルは同じ意味で英語の 1.6-2 倍の幅になるため、中点に
  // 置くと隣の線・ノードと必ず衝突する。始点側なら発ノードの直後に空白がある
  // ことが構造上保証される (ノードは辺で終わり、そこから線が出るため)。
  //
  // オフセットは LABEL_GAP からの導出のみで作る (新しい数値定数を置かない):
  //   経路方向  along  = gap * 2  … 矢の付け根と重ならせないため線方向は 2 倍取る
  //   法線方向  normal = gap + 箱の半寸  … 箱の縁が線から gap だけ離れる距離
  if (opts.anchor === 'start') {
    const along = gap * 2;
    const dir = opts.dir || (side === 'right' ? 'down' : 'right');
    if (dir === 'up' || dir === 'down') {
      const sy = dir === 'down' ? 1 : -1;
      rx = x + gap; // 垂直経路なので法線は水平方向
      ry = y + sy * (along + h / 2) - h / 2;
    } else {
      const sx = dir === 'left' ? -1 : 1;
      rx = x + sx * (along + w / 2) - w / 2;
      ry = y - (gap + h / 2) - h / 2; // 水平経路なので法線は上方向
    }
    tx = rx + w / 2;
  }

  // どの分岐でも文字はマスクの中心に置く (tx は常に rx + w/2 に一致する)。
  // 位置もグリッドへ載せる。ずれは最大 2px で、ギャップ規約 (6-10px) を割らない。
  // 画布の外へ出さない。始点側配置は発ノードの取付位置で決まるため、辺の端に
  // 寄った取付点では簡単に viewBox を越える (越えた文字は切れて読めない)。
  // 呼出し側が画布寸法を渡したときだけ、内側へ寄せる。
  if (opts.canvasW) rx = clamp(rx, GRID, opts.canvasW - w - GRID);
  if (opts.canvasH) ry = clamp(ry, GRID, opts.canvasH - h - GRID);
  rx = snap(rx);
  ry = snap(ry);
  tx = rx + w / 2;
  const ty = ry + h / 2;
  return (
    `<rect x="${num(rx)}" y="${num(ry)}" width="${num(w)}" height="${num(h)}" rx="2" fill="${paper}"/>` +
    textBlock({ x: tx, y: ty, lines, fontSize, lineHeight, fill, weight: 500, anchor: 'middle', letterSpacing: '0.06em' })
  );
}

/**
 * 凡例 (図解領域の外・下端の水平ストリップ)。
 * 図中に浮かせるのは diagram-design の明示的なアンチパターン。
 */

/**
 * 凡例の配置計算 (描画しない純関数)。legendStrip と legendHeight の共通土台。
 *
 * 日本語ラベルは英語の 1.6-2 倍幅になるので、1 行に収まる前提で書くと必ず
 * 右へはみ出す (D1 error)。ここで width を超えたら次の行へ折り返し、必要な
 * 総高さを返す。呼出し側はこの高さを見てから viewBox 高を確定できる。
 *
 * 寸法はすべて既存トークンからの導出:
 *   swatch      = MIN_FONT_SMALL - 2 を 4px グリッドへ切り上げ (文字の視覚高に揃えた色見本)
 *   swatch→文字 = LABEL_GAP - 2       (見本と語の結びつきを保つ近接)
 *   項目間      = LABEL_GAP * 2       (項目どうしは語間より明確に離す)
 *   行送り      = fontSize + LABEL_GAP
 *   罫線↔1行目 = LABEL_GAP
 */
function legendLayout(items, width, opts = {}) {
  const list = (items || []).filter(Boolean);
  const fontSize = opts.fontSize || MIN_FONT_SMALL;
  // 見本矩形は <rect> なので D6 (4px グリッド) の検査対象。寸法も x も 4 の倍数へ。
  const sw = snapUp(fontSize - 2);
  const swGap = LABEL_GAP - 2;
  const itemGap = LABEL_GAP * 2;
  const rowH = fontSize + LABEL_GAP;
  const rows = [];
  let row = [];
  let cx = 0;
  for (const it of list) {
    const label = typeof it === 'string' ? it : it.label || '';
    // kind は見本の**形**を選ぶ。線種で意味を分けている図 (実線=同期 /
    // 破線=非同期 / 二重線=正本) では、色の四角を並べても凡例にならない。
    const kind = (it && it.kind) || 'fill';
    const color = (it && it.color) || (kind === 'fill' ? TOKENS.muted : TOKENS.ink);
    const w = sw + swGap + measureText(label, fontSize);
    if (row.length && cx + w > width) {
      rows.push(row);
      row = [];
      cx = 0;
    }
    row.push({ label, color, kind, dx: snap(cx) });
    cx += w + itemGap;
  }
  if (row.length) rows.push(row);
  // 罫線は 1 行目の LABEL_GAP 上にあるので、その分も占有高へ含める
  const height = rows.length ? LABEL_GAP + rows.length * rowH : 0;
  return { rows, height, rowH, fontSize, sw, swGap };
}

/**
 * 凡例に必要な高さ。viewBox 高を先に固定してから凡例を押し込むと、折返しが
 * 起きた瞬間に必ず D1 (はみ出し・error) を踏むため、呼出し側はこれで高さを
 * 確定してから描く。
 */
function legendHeight(items, width, opts = {}) {
  return legendLayout(items, width, opts).height;
}

/**
 * 凡例の見本 1 つ。
 *
 * data-legend は凡例であることの構造的な印。文言で凡例を見分けると
 * 「処理」「入力」のような本文でも普通に出る語を凡例扱いしてしまう。
 * 検査器 (validate-diagram-information.py I3) はこの印で見本の塗りを
 * 語彙の数から除く。除かないと「凡例を描くほど凡例を要求される」
 * 自己敗北ループになる。
 *
 * 線種の見本は塗りの見本と**同じ幅**を占める。占有幅が kind で変わると
 * legendLayout の折返し計算 (幅は sw 固定で見積る) と食い違い、右端で
 * はみ出す (D1)。
 */
function legendSwatch(it, x, y, sw) {
  const kind = it.kind || 'fill';
  if (kind === 'fill') {
    return `<rect data-legend="1" x="${num(x)}" y="${num(y)}" width="${num(sw)}" height="${num(sw)}" rx="2" fill="${it.color}"/>`;
  }
  const my = y + sw / 2;
  const line = (yy, w, dash) =>
    `<line data-legend="1" x1="${num(x)}" y1="${num(yy)}" x2="${num(x + sw)}" y2="${num(yy)}" stroke="${it.color}" stroke-width="${w}"${dash ? ` stroke-dasharray="${dash}"` : ''}/>`;
  if (kind === 'double') return `${line(my - 2, STROKE.hairline)}${line(my + 2, STROKE.hairline)}`;
  if (kind === 'dashed') return line(my, STROKE.secondary, '4,3');
  if (kind === 'thick') return line(my, STROKE.primary);
  return line(my, STROKE.secondary);
}

function legendStrip(items, x, y, width, opts = {}) {
  const lay = legendLayout(items, width, opts);
  if (!lay.rows.length) return '';
  const { fontSize, rowH, sw, swGap } = lay;
  const parts = [
    `<line x1="${num(x)}" y1="${num(y - LABEL_GAP)}" x2="${num(x + width)}" y2="${num(y - LABEL_GAP)}" stroke="${TOKENS.rule}" stroke-width="${STROKE.hairline}"/>`,
  ];
  lay.rows.forEach((row, r) => {
    const ry = y + r * rowH;
    // 行の中で見本を垂直中央に置く。オフセットもグリッド上に載せる
    const sy = ry + snap((rowH - sw) / 2);
    for (const it of row) {
      parts.push(legendSwatch(it, x + it.dx, sy, sw));
      parts.push(
        textBlock({ x: x + it.dx + sw + swGap, y: sy + sw / 2, lines: [it.label], fontSize, lineHeight: fontSize, fill: TOKENS.muted, weight: 500, anchor: 'start' })
      );
    }
  });
  return parts.join('\n  ');
}

/**
 * SVG ルート要素。title/desc を持たせてスクリーンリーダーからも読めるようにする。
 */
function svgRoot(o) {
  const cls = o.className ? ` class="${o.className}"` : '';
  const desc = o.desc ? `\n  <desc>${escapeXml(o.desc)}</desc>` : '';
  return `<svg viewBox="0 0 ${num(o.width)} ${num(o.height)}"${cls} role="img" aria-label="${escapeXml(o.ariaLabel || '図解')}" xmlns="http://www.w3.org/2000/svg">
  <title>${escapeXml(o.ariaLabel || '図解')}</title>${desc}
  ${o.body}
</svg>`;
}

/**
 * 角丸ノード矩形。style は NODE_STYLES の値または filledStyle の戻り値。
 */
function nodeRect(box, style, opts = {}) {
  const rx = opts.radius != null ? opts.radius : 6;
  const st = style || NODE_STYLES.plain;
  const dash = st.dash ? ` stroke-dasharray="${st.dash}"` : '';
  const strokeAttr = st.stroke && st.stroke !== 'none' ? ` stroke="${st.stroke}" stroke-width="${st.strokeWidth || STROKE.node}"` : '';
  // 不透明マスク: 半透明塗りのノードでも背面の矢印が透けないようにする
  const mask = opts.mask === false ? '' : `<rect x="${num(box.x)}" y="${num(box.y)}" width="${num(box.w)}" height="${num(box.h)}" rx="${rx}" fill="${opts.paper || TOKENS.paper}"/>`;
  return `${mask}<rect x="${num(box.x)}" y="${num(box.y)}" width="${num(box.w)}" height="${num(box.h)}" rx="${rx}" fill="${st.fill}"${strokeAttr}${dash}/>`;
}

/* ============================================================
 * 6. 配置戦略 (composition strategies)
 * ============================================================
 *
 * 参考スキルの 31 図解を観察すると、個々の「図解タイプ」は
 *   配置戦略 × ノード語彙 × コネクタ語彙
 * の直積として記述できる。例:
 *   loop        = ring   × box  × ring-arc + dashed-spoke
 *   process     = lane   × box  × elbow
 *   layers      = stack  × band × なし
 *   quadrant    = matrix × cell × なし
 *   architecture= zone   × box  × elbow
 *   tree        = level  × box  × elbow
 *
 * したがってビルダーを 1 タイプ 1 関数で増やすのではなく、
 * 下記の配置戦略を組み合わせて任意のタイプを合成できるようにする。
 * これが「本リポジトリに無い図解も同じ構成で作れる」ための土台。
 *
 * すべての戦略は {x,y,w,h} の box 配列 (+付随情報) を返す純関数であり、
 * 描画も色も持たない。描画は §5 のプリミティブが担う。
 */

/** 全戦略共通: 与えられた領域を表す */
function area(x, y, w, h) {
  return { x, y, w, h };
}

/**
 * 総幅 total を weights の比で配り、丸め残りを末尾要素に吸収させる。
 *
 * なぜ必要か: 各戦略が `Math.floor(total / n)` で等分すると、n が total を割り
 * 切らない限り必ず数 px が余り、その余りは常に右端 (下端) の外側へ落ちる。
 * さらに 4px グリッド (snap) へ寄せると誤差が積み上がって右端が数 px ずれる。
 * 「Σw_i === total を厳密に満たす」を不変量にすれば、この崩れは構造的に消える。
 *
 * さらに丸め残りを末尾 1 個へ押し込むと、その 1〜3px のせいで末尾セルだけが
 * 4 の倍数でなくなり、そこへ置く矩形がすべて D6 (4px グリッド) 違反になる。
 * そこで配分の単位自体を GRID にする。
 *
 * 手順: 理想値 raw_i = total * weight_i / Σweights を GRID 単位へ切り下げ
 *      → 余り (GRID の倍数) を「切り捨てた端数が大きい順」に 1 GRID ずつ配る。
 * これで Σw_i === total と「全要素が GRID の倍数」を同時に満たす
 * (total が GRID の倍数である限り。呼出し側の領域幅は常にそう作られている)。
 * minW を満たせない場合だけ、先頭側から minW を超えている余剰を削って補う。
 * (total < n * minW は呼出し側の容量超過であり、ここでは救わない。契約 §2 に従い
 *  呼出し側が「載せない」判断をする。)
 *
 * @returns {number[]} Σ === total を満たす幅の配列 (total >= n * minW のとき厳密)
 */
function distributeWidths(total, weights, minW = 0) {
  const ws = (Array.isArray(weights) ? weights : []).map((w) => (Number.isFinite(w) && w > 0 ? w : 1));
  const n = ws.length;
  if (n === 0) return [];
  if (n === 1) return [total];
  const sum = ws.reduce((a, b) => a + b, 0) || n;
  const floorW = snapUp(minW);
  const raw = ws.map((w) => (total * w) / sum);
  const out = raw.map((r) => Math.max(floorW, snapDown(r)));
  // 余りは GRID 単位で、切り捨て量が大きかった要素から順に返す
  // (同量なら添字の小さい方。同じ入力から常に同じ配分になるようにするため)
  let rest = total - out.reduce((a, b) => a + b, 0);
  const order = out
    .map((v, i) => ({ i, loss: raw[i] - v }))
    .sort((a, b) => b.loss - a.loss || a.i - b.i);
  for (let k = 0; rest >= GRID && k < order.length; k++) {
    out[order[k].i] += GRID;
    rest -= GRID;
  }
  const headSum = () => out.slice(0, n - 1).reduce((a, b) => a + b, 0);
  let last = total - headSum();
  if (last < minW) {
    // 先頭側の余剰 (minW を超えている分) から不足を回収する
    let deficit = minW - last;
    for (let i = 0; i < n - 1 && deficit > 0; i++) {
      const room = out[i] - minW;
      if (room <= 0) continue;
      const cut = Math.min(room, deficit);
      out[i] -= cut;
      deficit -= cut;
    }
    last = total - headSum();
  }
  // 負の幅は SVG として不正なので、そこだけは Σ===total より安全側を採る。
  // ここへ落ちるのは total < n * minW、すなわち呼出し側の容量超過のときだけ。
  out[n - 1] = Math.max(0, last);
  return out;
}

/**
 * distributeWidths の結果を起点 start から gap 込みで並べた開始座標を返す。
 * (各戦略が同じ累積計算を書き写さないための小道具)
 * @returns {Array<{pos:number, size:number}>}
 */
function distributeTrack(start, total, weights, gap, minW = 0) {
  const n = (Array.isArray(weights) ? weights : []).length;
  if (n === 0) return [];
  const sizes = distributeWidths(total - gap * (n - 1), weights, minW);
  let pos = start;
  return sizes.map((size) => {
    const cell = { pos, size };
    pos += size + gap;
    return cell;
  });
}

/** n 個の等分割用の重み (すべて 1) */
function evenWeights(n) {
  return Array.from({ length: Math.max(0, n) }, () => 1);
}

/**
 * ring — 円周等間隔配置。loop / cycle / star / mindmap の土台。
 * 12時から時計回り (参考 type-loop §2.1: theta_k = -90deg + k*360/N)。
 */
function ringLayout(n, opts = {}) {
  const cx = opts.cx || 0;
  const cy = opts.cy || 0;
  const R = opts.radius || 200;
  const w = opts.nodeW || 160;
  const h = opts.nodeH || 64;
  const out = [];
  for (let k = 0; k < n; k++) {
    const theta = -Math.PI / 2 + (2 * Math.PI * k) / n;
    const bx = cx + R * Math.cos(theta);
    const by = cy + R * Math.sin(theta);
    out.push({
      index: k, theta, cx: bx, cy: by,
      x: snap(bx - w / 2), y: snap(by - h / 2), w, h,
    });
  }
  return out;
}

/**
 * row — 水平等間隔。horizontal flow / chevron / timeline の土台。
 * 幅は distributeWidths 経由で配るので Σ(幅) + Σ(隙間) === region.w を厳密に満たす
 * (末尾要素だけが丸め残りを数 px 吸収する)。
 */
function rowLayout(n, region, opts = {}) {
  const gap = opts.gap != null ? opts.gap : 20;
  const h = opts.h || region.h;
  const y = opts.y != null ? opts.y : region.y;
  const track = distributeTrack(region.x, region.w, opts.weights || evenWeights(n), gap, opts.minW || 0);
  return track.map((c, i) => ({
    index: i, x: c.pos, y, w: c.size, h,
    cx: c.pos + c.size / 2, cy: y + h / 2,
  }));
}

/** column — 垂直等間隔。vertical flow / vertical timeline の土台 */
function columnLayout(n, region, opts = {}) {
  const gap = opts.gap != null ? opts.gap : 18;
  const w = opts.w || region.w;
  const x = opts.x != null ? opts.x : region.x;
  // 高さ指定があるときは従来どおり固定高で積む (総高を region.h に合わせない)
  if (opts.h) {
    const h = opts.h;
    return Array.from({ length: n }, (_, i) => ({
      index: i, x, y: region.y + i * (h + gap), w, h,
      cx: x + w / 2, cy: region.y + i * (h + gap) + h / 2,
    }));
  }
  const track = distributeTrack(region.y, region.h, evenWeights(n), gap, opts.minH || 0);
  return track.map((c, i) => ({
    index: i, x, y: c.pos, w, h: c.size,
    cx: x + w / 2, cy: c.pos + c.size / 2,
  }));
}

/** grid — 行列折返し。snake / card grid / nested の土台 */
function gridLayout(n, region, opts = {}) {
  const cols = opts.cols || Math.min(4, Math.ceil(Math.sqrt(n)));
  const rows = Math.ceil(n / cols);
  const gapX = opts.gapX != null ? opts.gapX : 20;
  const gapY = opts.gapY != null ? opts.gapY : 20;
  // 列・行とも distributeTrack で配り、右端/下端の丸め残りを消す
  const colTrack = distributeTrack(region.x, region.w, evenWeights(cols), gapX);
  const rowTrack = distributeTrack(region.y, region.h, evenWeights(rows), gapY);
  return Array.from({ length: n }, (_, i) => {
    const r = Math.floor(i / cols);
    let c = i % cols;
    if (opts.serpentine && r % 2 === 1) c = cols - 1 - c; // snake 用の折返し
    const x = colTrack[c].pos;
    const y = rowTrack[r].pos;
    const w = colTrack[c].size;
    const h = rowTrack[r].size;
    return { index: i, row: r, col: c, x, y, w, h, cx: x + w / 2, cy: y + h / 2 };
  });
}

/** stack — 全幅の積層帯。layers / pyramid / medallion / value-stack の土台 */
function stackLayout(n, region, opts = {}) {
  // 帯・隙間とも 4px グリッド上に載せる (帯は矩形として D6 の検査対象)
  const gap = opts.gap != null ? opts.gap : LABEL_GAP;
  const h = snapDown((region.h - gap * (n - 1)) / n);
  // taper: 0 で矩形、1 でピラミッド状に上を細くする
  const taper = opts.taper || 0;
  return Array.from({ length: n }, (_, i) => {
    const ratio = taper ? 1 - taper * (1 - (i + 1) / n) : 1;
    const w = snapDown(region.w * ratio);
    const x = region.x + snap((region.w - w) / 2);
    const y = region.y + i * (h + gap);
    return { index: i, x, y, w, h, cx: x + w / 2, cy: y + h / 2 };
  });
}

/**
 * lane — スイムレーン。process / data-flow / swimlane の土台。
 * @returns {{lanes: Array, cells: Array}} lanes は帯、cells は lane×step の交点
 */
function laneLayout(laneCount, stepCount, region, opts = {}) {
  const headerW = opts.headerW != null ? opts.headerW : 160;
  const laneGap = opts.laneGap != null ? opts.laneGap : 12;
  const stepGap = opts.stepGap != null ? opts.stepGap : 24;
  const trackX = region.x + headerW;
  const trackW = region.w - headerW;
  // レーン高・ステップ幅とも distributeTrack で配り、下端/右端のズレを消す
  const laneTrack = distributeTrack(region.y, region.h, evenWeights(laneCount), laneGap);
  const stepTrack = distributeTrack(trackX, trackW, evenWeights(stepCount), stepGap);
  const lanes = laneTrack.map((lt, l) => ({
    index: l, x: region.x, y: lt.pos,
    w: region.w, h: lt.size,
    header: area(region.x, lt.pos, headerW, lt.size),
  }));
  const cells = [];
  for (let l = 0; l < laneCount; l++) {
    for (let s = 0; s < stepCount; s++) {
      const x = stepTrack[s].pos;
      const y = laneTrack[l].pos;
      const w = stepTrack[s].size;
      const h = laneTrack[l].size;
      cells.push({ lane: l, step: s, x, y, w, h, cx: x + w / 2, cy: y + h / 2 });
    }
  }
  return { lanes, cells };
}

/** matrix — 行列 (見出し付き)。quadrant / security-matrix / comparison の土台 */
function matrixLayout(rowCount, colCount, region, opts = {}) {
  const headerW = opts.headerW != null ? opts.headerW : 0;
  const headerH = opts.headerH != null ? opts.headerH : 0;
  const gap = opts.gap != null ? opts.gap : 8;
  const bodyX = region.x + headerW;
  const bodyY = region.y + headerH;
  // セル寸法を 4px グリッドへ切り下げる。gap・headerW/H・region が 4 の倍数なら
  // 全セルの x/y も 4 の倍数になり、そこへ置く矩形が D6 を満たす
  const cw = snapDown((region.w - headerW - gap * (colCount - 1)) / colCount);
  const chh = snapDown((region.h - headerH - gap * (rowCount - 1)) / rowCount);
  const cells = [];
  for (let r = 0; r < rowCount; r++) {
    for (let c = 0; c < colCount; c++) {
      const x = bodyX + c * (cw + gap);
      const y = bodyY + r * (chh + gap);
      cells.push({ row: r, col: c, index: r * colCount + c, x, y, w: cw, h: chh, cx: x + cw / 2, cy: y + chh / 2 });
    }
  }
  const colHeaders = Array.from({ length: colCount }, (_, c) =>
    area(bodyX + c * (cw + gap), region.y, cw, headerH));
  const rowHeaders = Array.from({ length: rowCount }, (_, r) =>
    area(region.x, bodyY + r * (chh + gap), headerW, chh));
  return { cells, colHeaders, rowHeaders };
}

/**
 * zone — 論理グループの帯 (縦バンド)。architecture / high-level / dp-integration の土台。
 * 参考 type-architecture: zone は最大3、ラベル余白は 16px 以上。
 */
function zoneLayout(zoneSizes, region, opts = {}) {
  const gap = opts.gap != null ? opts.gap : 32;
  const labelH = opts.labelH != null ? opts.labelH : 24;
  // 重み付き配分。丸め残りは末尾ゾーンが吸収するので右端が region.x + region.w に一致する
  const track = distributeTrack(region.x, region.w, zoneSizes, gap);
  return track.map((c, i) => ({
    index: i, x: c.pos, y: region.y, w: c.size, h: region.h,
    body: area(c.pos, region.y + labelH, c.size, region.h - labelH),
    label: area(c.pos, region.y, c.size, labelH),
  }));
}

/** level — 階層の段 (段ごとに任意個)。tree / org-chart / hierarchy の土台 */
function levelLayout(countsPerLevel, region, opts = {}) {
  const gapY = opts.gapY != null ? opts.gapY : 40;
  const gapX = opts.gapX != null ? opts.gapX : 20;
  const levels = countsPerLevel.length;
  const levelTrack = distributeTrack(region.y, region.h, evenWeights(levels), gapY);
  return countsPerLevel.map((count, l) => {
    const y = levelTrack[l].pos;
    const h = levelTrack[l].size;
    // 段ごとに個数が違うので、段内でも Σ幅 + Σ隙間 === region.w を保つ
    const track = distributeTrack(region.x, region.w, evenWeights(count), gapX);
    return track.map((c, i) => ({
      level: l, index: i, x: c.pos, y, w: c.size, h,
      cx: c.pos + c.size / 2, cy: y + h / 2,
    }));
  });
}

/** 配置戦略の名前解決 (仕様/エージェントから文字列で選べるようにする) */
const LAYOUTS = {
  ring: ringLayout,
  row: rowLayout,
  column: columnLayout,
  grid: gridLayout,
  stack: stackLayout,
  lane: laneLayout,
  matrix: matrixLayout,
  zone: zoneLayout,
  level: levelLayout,
};

module.exports = {
  // 定数
  GRID, MIN_FONT, MIN_FONT_SMALL, LINE_HEIGHT_RATIO, LABEL_GAP,
  MARKER, FAN_MIN_GAP, INCIDENCE_RULE,
  TOKENS, SERIES, NODE_STYLES, STROKE,
  VAR_BLUE, VAR_AQUA, VAR_PINK, VAR_YELLOW, VAR_VIOLET,
  FORBID_LINE_START, FORBID_LINE_END,
  // ユーティリティ
  snap, snapUp, snapDown, clamp, num, escapeXml,
  // 色
  filledStyle, resolvePalette,
  // テキスト
  charWidth, measureText, breakScore, breakAllowed, charClass, wrapText, fitText, autoBlockHeight,
  // 配置戦略
  area, distributeWidths, distributeTrack, evenWeights,
  ringLayout, rowLayout, columnLayout, gridLayout, stackLayout,
  laneLayout, matrixLayout, zoneLayout, levelLayout, LAYOUTS,
  // 幾何
  boxRayDistance, circleBoxIntersections, normAngle, ringNodePorts, ringArcPath, elbowPath, detourPath, fanAttach,
  nearestEdge, elbowIncidence, safeElbow, fanCapacity, trunkPaths, overArcPath, overArcApex,
  markerOverhangPx,
  // 描画
  arrowMarkers, markerDefs, arrowUrl, markerKey, textBlock, fittedTextInBox, arrowLabel,
  legendStrip, legendLayout, legendHeight, svgRoot, nodeRect,
};
