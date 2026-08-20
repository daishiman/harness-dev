#!/usr/bin/env node

/**
 * スライド構成案検証スクリプト（Phase 2.5 仕様確定ゲート対応）
 *
 * 機能:
 *   - structure.md / structure.json の構造検証
 *   - V-001〜V-030 の機械検証項目（bp-classification.md §2-A 準拠）
 *   - structure.schema.json による JSON Schema 検証（--schema オプション）
 *   - SR-ID 参照付きエラーメッセージ
 *   - PASS / FAIL / WARN の3段階出力
 *
 * 使用例:
 *   node validate-structure.js structure.md
 *   node validate-structure.js structure.json --schema
 *   node validate-structure.js structure.md --strict --report report.json
 *   echo '{"title":"Test","slides":[]}' | node validate-structure.js
 *
 * 終了コード:
 *   0: PASS（検証成功）
 *   1: FAIL（P3進行不可）
 *   2: WARN（要確認だが進行可能）
 *   3: ファイル不在 / 引数エラー
 */

import { readFileSync, existsSync, writeFileSync } from "fs";
import { dirname, join, resolve, extname } from "path";
import { fileURLToPath } from "url";
import {
  parseArgs,
  hasFlag,
  VALID_SLIDE_TYPES,
  isValidSlideType as legacyIsValidSlideType,
  EXIT_CODES
} from "./utils.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = resolve(__dirname, "..");
// vendor 同梱 (vendor/schemas/) → plugin 直下 (schemas/) の順で解決する。
// vendor 側に schema が同梱されない配布形態では plugin 直下が正本で、
// どちらも無いときだけ legacy VALID_SLIDE_TYPES へフォールバックする。
const SCHEMA_PATH_CANDIDATES = [
  join(SKILL_ROOT, "schemas", "structure.schema.json"),
  resolve(SKILL_ROOT, "..", "schemas", "structure.schema.json"),
];
const SCHEMA_PATH = SCHEMA_PATH_CANDIDATES.find((p) => existsSync(p)) || SCHEMA_PATH_CANDIDATES[0];

// schema から slideType enum を取得（97 種）。失敗時は legacy にフォールバック
let SCHEMA_SLIDE_TYPES = null;
try {
  const schema = JSON.parse(readFileSync(SCHEMA_PATH, "utf8"));
  const findEnum = (obj) => {
    if (!obj || typeof obj !== "object") return null;
    if (Array.isArray(obj.enum) && obj.enum.length > 50 &&
        obj.enum.every(v => typeof v === "string")) return obj.enum;
    for (const k of Object.keys(obj)) {
      const r = findEnum(obj[k]);
      if (r) return r;
    }
    return null;
  };
  SCHEMA_SLIDE_TYPES = findEnum(schema);
} catch (e) { /* legacy fallback */ }

function isValidSlideType(t) {
  if (!t) return false;
  if (SCHEMA_SLIDE_TYPES && SCHEMA_SLIDE_TYPES.includes(t)) return true;
  return legacyIsValidSlideType(t);
}

// FontAwesomeアイコンパターン
const ICON_PATTERN = /^fa-[a-z0-9-]+$/;

// 質問系・背景系スライドタイプ（V-030 用）
const QUESTION_TYPES = new Set(["question", "質問", "slide-question"]);
const BACKGROUND_TYPES = new Set([
  "title", "subtitle", "agenda", "section",
  "context", "background", "intro", "introduction",
  "タイトル", "目次", "セクション", "背景", "導入"
]);

/**
 * engine の長い名 (slide-*) のテンプレートが本文として実際に読む「源のキー」。
 *
 * vendor/scripts/templates/ には短縮名 (message.html.tpl) と長い名
 * (slide-message.html.tpl) が対で置かれていて、render-slide.cjs の loadTemplate は
 * まず slideType そのままの名前を探し、無ければ TYPE_ALIASES を引く。短縮名の
 * slideType を書いた旧世代の deck はそのまま短縮名テンプレートへ落ちるので、
 * どちらも現役であり、片方は残骸ではない。ただし対の間で本文キーの名前が違う
 * ものがあり (message: {{message}} / slide-message: {{main}}、timeline: {{items}} /
 * slide-timeline: {{events}} など)、短縮名の書き方のまま slideType だけ長い名に
 * すると、検証は通るのに本文が空で出る。ここはその取り違えを止めるための表。
 *
 * 値は「テンプレートのプレースホルダ名」ではなく「render-slide.cjs が読む源の
 * キー」を書く。enrich が計算して差し込む派生キー (svg / headers / gridRows など)
 * があるため、両者は一致しない。表とテンプレートのずれは
 * tests/test_template_body_keys.py が検出する。
 */
const TEMPLATE_BODY_KEYS = {
  "slide-message": ["main"],
  "slide-title": ["title"],
  "slide-hero": ["title"],
  "slide-quote": ["quote"],
  "slide-highlight": ["value"],
  "slide-list": ["items"],
  "slide-icon-grid": ["items"],
  "slide-grid": ["cards"],
  "slide-table": ["rows"],
  "slide-timeline": ["events"],
  "slide-process": ["steps"],
  "slide-compare": ["left", "right"],
  "slide-code": ["code"],
  "slide-code-compare": ["before", "after"],
  // 図解 3 種は enrich が items 系から svg を組み立てる (render-slide.cjs の SVG dispatch)
  "slide-flow": ["steps", "items"],
  "slide-circle": ["steps", "satellites", "items"],
  "slide-pyramid": ["levels", "items", "layers"],
};

/**
 * 型を特定できない面 (schemaVersion 差・拡張型・unknown) に使う「何かしら本文がある」判定の
 * 受理キー集合。TEMPLATE_BODY_KEYS から導出する。
 *
 * 以前はここが独立した手書きの列挙 (main / title / message / items / steps / rows) だった。
 * そのため content に quote しか無い slide-quote、value しか無い slide-highlight、cards しか
 * 無い slide-grid のように、テンプレートが読む本文を正しく持っている面が「テキストコンテンツ
 * が欠落」で落ちていた (実測: 17 型中 9 型 — quote / highlight / grid / timeline / compare /
 * code / code-compare / circle / pyramid)。列挙を 2 箇所に持つ限り、型を足すたびに片方だけ
 * 更新され「テンプレートは読むのに検証は本文と認めない」ずれが再発する。導出にして源を 1 つにする。
 *
 * message は TEMPLATE_BODY_KEYS に無いが、旧短縮名テンプレート (message: {{message}}) と
 * md 形式の deck が使うため受理側に残す。
 */
const GENERIC_BODY_KEYS = [
  ...new Set([...Object.values(TEMPLATE_BODY_KEYS).flat(), "message"]),
];

// 本文キーが「実際に中身を持っているか」。空文字・空配列は無いのと同じに扱う。
function hasBodyValue(slide, content, key) {
  const v = content[key] !== undefined ? content[key] : slide[key];
  if (v === undefined || v === null) return false;
  if (typeof v === "string") return v.trim() !== "";
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === "object") return Object.keys(v).length > 0;
  return true;
}

// V-ID 定義表（bp-classification.md §2-A 準拠）
//
// desc の書き方（規則）: 正本（references/spec-registry.md）から写すとき、
// **空白を落として切り詰めないこと。**desc はレポートと未検査ブロックへそのまま
// 出るので、切り詰めた写しが第 2 の正本として読まれる。
//
// 実例: SR-4-08「図解はインライン SVG2 で描画」の空白を落として "図解はインライン
// SVG2描画" と書いた結果、「SVG」「2 描画」と切れて数量に読まれ、実行体の無い
// 規則として保留され続けた（実際は SVG 仕様のバージョン 2 のことだった）。
//
// この種の誤読は「英字の直後に数字」で機械的に見つかる。
// tests/test_v_definitions_desc.py が許可語（h2 / A4 のような確立した綴り）以外を落とす。
const V_DEFINITIONS = {
  "V-001": { sr: "SR-4-03", desc: "Before/After は 2 パネル等幅・間隔は版面比（中央要素が無いときは 48% / 4% / 48%）", level: "FAIL" },
  "V-002": { sr: "SR-4-06", desc: "補足テキスト最大3行", level: "FAIL" },
  "V-003": { sr: "SR-3-04", desc: "フォント最小1.4rem (≒1.75vw)", level: "FAIL" },
  "V-004": { sr: "SR-7-01", desc: "印刷=画面同一比率（vw統一）", level: "FAIL" },
  "V-005": { sr: "SR-10-01", desc: "code-block の縦上限統一（値は SR-10-01）", level: "FAIL" },
  "V-006": { sr: "SR-6-02", desc: "GSAP scale最小0.8（残留transform対策）", level: "FAIL" },
  "V-007": { sr: "SR-3-05", desc: "SVG <text> 最小font-size 13px", level: "FAIL" },
  "V-008": { sr: "SR-3-06", desc: "SVG内 FA unicode禁止 (&#xf...)", level: "FAIL" },
  "V-009": { sr: "SR-3-08", desc: "全スライドタイプにh2 CSS定義", level: "FAIL" },
  "V-010": { sr: "SR-8-02", desc: "section-nav 全セクション網羅", level: "FAIL" },
  "V-011": { sr: "SR-4-05", desc: "list-item/ig-item width:100%/box-sizing", level: "FAIL" },
  "V-012": { sr: "SR-7-02", desc: "A4横フルサイズ余白なし @page margin:0", level: "FAIL" },
  "V-013": { sr: "SR-7-01", desc: "印刷=画面同レイアウト（display:none禁止）", level: "WARN" },
  "V-014": { sr: "SR-7-03", desc: "印刷CSS GSAPスタイルリセット", level: "FAIL" },
  "V-015": { sr: "SR-6-03", desc: "clearPropsはcontent.childrenのみ", level: "FAIL" },
  "V-016": { sr: "SR-6-04", desc: "foreignObject内div = class=fo-card", level: "FAIL" },
  "V-017": { sr: "SR-2-08", desc: "SVG fill/strokeにCSS変数使用", level: "FAIL" },
  "V-018": { sr: "SR-2-02", desc: "CSS変数使用（カラー直書き禁止）", level: "FAIL" },
  "V-019": { sr: "SR-1-04", desc: "画像はWebP形式", level: "WARN" },
  "V-020": { sr: "SR-0-01", desc: "CSS/JS分離出力（インライン禁止）", level: "FAIL" },
  "V-021": { sr: "SR-3-09", desc: "1行が長いテキストは文節の切れ目で改行", level: "WARN" },
  "V-022": { sr: "SR-9-02", desc: "UIテキスト opacity ≥ 0.6", level: "WARN" },
  "V-023": { sr: "SR-9-01", desc: "focus-visible + reduced-motion", level: "FAIL" },
  "V-024": { sr: "SR-3-01", desc: "コードはSF Mono/Fira Code", level: "WARN" },
  // V-025 の desc は 2026-08-14 に実態へ寄せた。旧 desc「標準CSSクラス名のみ使用」は
  // 実装が一度も見ていない規則で、書いた時点から誰も守らせていなかった（class= の値は
  // どこでも照合していない）。実装が見ている 3 つはいずれも必要な検査なので、名前の側を
  // 直した。CSS クラス名の照合を本当に入れるなら、それは V-025 の話ではなく新しい V-ID を
  // 起こす話になる。「元の規則はどこへ行った」と探す人のためにここに残す。
  // 分割候補: 1 つの V-ID に 3 役が乗っており、どれで落ちたかが V-ID からは分からない。
  // 3 つの V-ID へ割るのが筋だが、採番は下流の消費者に効くので符号系の着地と混ぜない。
  "V-025": { sr: "SR-0-02", desc: "構成の基本的な妥当性。slideType が有効・JSON schema 適合・基本構造エラーなし の 3 つの受け皿を兼ねる", level: "FAIL" },
  "V-026": { sr: "SR-3-07", desc: "質問スライドはfs-subheading", level: "FAIL" },
  "V-027": { sr: "SR-8-01", desc: "section-nav 常時表示", level: "WARN" },
  "V-028": { sr: "SR-8-03", desc: "ページネーション5個区切り", level: "WARN" },
  "V-029": { sr: "SR-4-08", desc: "図解はインライン svg で描画。position:absolute の図解は禁止", level: "WARN" },
  "V-030": { sr: "SR-4-07", desc: "背景→質問の順で配置", level: "FAIL" },

  // v8 拡張（schemaVersion=8.0.0 のみ実行、それ以外は skip）
  "V-031": { sr: "SR-V8-COVER", desc: "cover.variant=hero-icon は cover.hero.icon (fa-*) 必須", level: "FAIL" },
  "V-032": { sr: "SR-V8-COVER", desc: "cover.variant=hero-image は cover.hero.imagePath 必須・WebP推奨", level: "FAIL" },
  "V-033": { sr: "SR-V8-INDEX", desc: "index.items または sections のいずれかが必要", level: "FAIL" },
  "V-034": { sr: "SR-V8-INDEX", desc: "index.currentSection は sections.id に存在", level: "FAIL" },
  "V-035": { sr: "SR-V8-DIAGRAM", desc: "diagram.edges の from/to は nodes.id に存在", level: "FAIL" },
  "V-036": { sr: "SR-V8-DIAGRAM", desc: "diagram.nodes.id は重複なし", level: "FAIL" },
  "V-037": { sr: "SR-V8-PAGE", desc: "pageOverride.background=image は backgroundImage 必須", level: "FAIL" },
  "V-038": { sr: "SR-V8-COLOR", desc: "section.theme/pageOverride の色は theme.accentColors に含む", level: "WARN" },
  "V-043": { sr: "SR-13-01", desc: "コード系 slideType は aiVisual で image-only / baked-with-overlay にできない（コードは実HTMLコードブロックで描画）", level: "FAIL" },
  "V-044": { sr: "SR-16-01", desc: "slideType 別の本文キー整合（テンプレートが読む content キーを持つ）", level: "FAIL" }
};

// ==================================================
// 結果オブジェクト
// ==================================================

class ValidationReport {
  constructor() {
    this.passed = [];
    this.failed = [];
    this.warned = [];
    this.skipped = [];
    this.startTime = new Date();
  }

  pass(vid, detail = "") {
    this.passed.push({ vid, ...V_DEFINITIONS[vid], detail });
  }

  fail(vid, detail) {
    const def = V_DEFINITIONS[vid] || { sr: "?", desc: vid, level: "FAIL" };
    this.failed.push({ vid, ...def, detail });
  }

  warn(vid, detail) {
    const def = V_DEFINITIONS[vid] || { sr: "?", desc: vid, level: "WARN" };
    this.warned.push({ vid, ...def, detail });
  }

  /**
   * この gate で判定しなかった項目。
   *
   * kind は 3 種類あり、混ぜてはいけない。
   *   "deferred"       この gate では材料が無いだけで、対象は在る。後段が判定する
   *   "not-applicable" 判定する対象がこの構成に無い。後段でも見ることは無い
   *   "no-checker"     どの工程にも判定する実行体が無い（＝その規則は未検査）
   * 同じ「SKIPPED」に数えて区別を消すと、"no-checker" が「後段で見てもらえる」と
   * 読まれる。誤った安心を作らないため、集計も表示も分けている。
   *
   * "not-applicable" は 2026-08-14 に足した。それまでは「対象が無い」も既定の
   * "deferred" に入っており、コメントの定義（後段に実行体がある）と実態がずれて
   * いた。V-030 / V-043 / V-044 のように後段でも永久に見ないものが "deferred" に
   * 溜まっていたので、「滞留している deferred を洗い出す」検査を誰かが書けば全部
   * 引っかかる状態だった。1 つの語に 2 つの意味を載せない。
   */
  skip(vid, reason, kind = "deferred") {
    const def = V_DEFINITIONS[vid] || { sr: "?", desc: vid };
    this.skipped.push({ vid, ...def, reason, kind });
  }

  get unchecked() {
    return this.skipped.filter(e => e.kind === "no-checker");
  }

  /** 対象がこの構成に無いもの。後段へ渡らないので、滞留として数えてはいけない。 */
  get notApplicable() {
    return this.skipped.filter(e => e.kind === "not-applicable");
  }

  /** 後段が判定するもの。ここに溜まったまま誰も見ていないなら、それは異常。 */
  get deferred() {
    return this.skipped.filter(e => e.kind === "deferred");
  }

  /**
   * FAIL が無くても、どの工程にも実行体が無い規則を抱えているなら PASS とは
   * 名乗らない。未検査は「見て問題が無かった」ではなく「誰も見ていない」で、
   * それを PASS に混ぜると緑が何を保証しているのか読めなくなる。
   */
  get status() {
    if (this.failed.length > 0) return "FAIL";
    if (this.warned.length > 0) return "WARN";
    if (this.unchecked.length > 0) return "PASS_WITH_UNCHECKED";
    return "PASS";
  }

  /**
   * PASS_WITH_UNCHECKED の exit code は WARN と同じ 2 にする。呼び出し側
   * （SKILL.md / R1-orchestrate / R2-agent-structure-validator）は status 文字列
   * ではなく exit code だけで分岐しており、2 は「影響を説明しユーザー許容可否を
   * 確認」の経路に入る。未検査に対して取りたい運用（何が未検査かを見せた上で
   * 承認を求める）がこの既存経路と一致する。
   *
   * 新しい番号を作らないのは、読み手が知らない値になるため。未知の exit code は
   * 呼び出し側の else に落ちて PASS 扱いになるか例外で止まるかのどちらかで、
   * 前者なら偽緑を移動しただけになる。
   */
  get exitCode() {
    if (this.failed.length > 0) return 1;
    if (this.warned.length > 0) return 2;
    if (this.unchecked.length > 0) return 2;
    return 0;
  }

  toJSON() {
    return {
      status: this.status,
      timestamp: this.startTime.toISOString(),
      counts: {
        passed: this.passed.length,
        failed: this.failed.length,
        warned: this.warned.length,
        skipped: this.skipped.length
      },
      passed: this.passed,
      failed: this.failed,
      warned: this.warned,
      skipped: this.skipped
    };
  }
}

// ==================================================
// structure.md パーサー
// ==================================================

/**
 * structure.md から JSON 風の構造を抽出
 * 抽出項目: title, sections, slides[].type, slides[].message, slides[].icon
 */
function parseStructureMd(md) {
  const data = { title: "", slides: [], _raw: md, _format: "md" };

  // タイトル抽出（最初の # 行）
  const titleMatch = md.match(/^#\s+(.+)$/m);
  if (titleMatch) data.title = titleMatch[1].trim();

  // テーブル形式: | 番号 | タイトル | タイプ | アイコン | ... |
  const tableRegex = /^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|/gm;
  let m;
  while ((m = tableRegex.exec(md)) !== null) {
    const [, num, title, type] = m;
    data.slides.push({
      _index: parseInt(num, 10),
      message: title.trim(),
      type: type.trim(),
      icon: null
    });
  }

  // ## スライド\d+ 形式（補完）
  if (data.slides.length === 0) {
    const slideRegex = /^##+\s+スライド\s*(\d+)\s*[:：]?\s*(.*?)$/gm;
    while ((m = slideRegex.exec(md)) !== null) {
      data.slides.push({
        _index: parseInt(m[1], 10),
        message: m[2].trim(),
        type: "unknown",
        icon: null
      });
    }
  }

  // タイプ別の補足: type: xxx 表記
  const typeLineRegex = /^[-*]\s*(?:type|タイプ)\s*[:：]\s*([a-z0-9-]+)/gim;

  return data;
}

// ==================================================
// JSON Schema 検証（簡易版 - ajv未使用）
// ==================================================

function validateAgainstSchema(data, schema) {
  const errors = [];

  if (!schema) return errors;

  // required トップレベル
  if (schema.required) {
    for (const key of schema.required) {
      if (!(key in data)) {
        errors.push(`schema: 必須プロパティ "${key}" が欠落`);
      }
    }
  }

  // properties.slides.items.required
  const slideItem = schema?.properties?.slides?.items;
  if (slideItem?.required && Array.isArray(data.slides)) {
    data.slides.forEach((slide, i) => {
      for (const key of slideItem.required) {
        if (slide && !(key in slide)) {
          errors.push(`schema: slides[${i}].${key} が欠落`);
        }
      }
    });
  }

  return errors;
}

// ==================================================
// 構造検証（既存ロジック維持）
// ==================================================

function validateBasicStructure(data, isMdFormat) {
  const errors = [];

  if (!data || typeof data !== "object") {
    errors.push("構造データがオブジェクトではありません");
    return errors;
  }

  const title = data.title || (data.meta && data.meta.title);
  if (!title || typeof title !== "string" || title.trim() === "") {
    errors.push("title（または meta.title）: 必須（非空文字列）");
  }

  if (!Array.isArray(data.slides)) {
    errors.push("slides: 配列である必要があります");
    return errors;
  }
  if (data.slides.length === 0) {
    errors.push("slides: 1つ以上のスライドが必要です");
    return errors;
  }

  data.slides.forEach((slide, i) => {
    const n = i + 1;
    if (!slide || typeof slide !== "object") {
      errors.push(`スライド${n}: オブジェクトでない`);
      return;
    }

    // type / slideType（新旧スキーマ両対応）
    const stype = slide.slideType || slide.type;
    if (!stype) {
      errors.push(`スライド${n}: slideType（または type）が欠落`);
    } else if (!isValidSlideType(stype) && stype !== "unknown") {
      errors.push(
        `スライド${n}: slideType "${stype}" は無効 [V-025 / SR-0-02]`
      );
    }
    // 後段の V-* チェックで slide.type を参照しているため正規化
    if (!slide.type && slide.slideType) slide.type = slide.slideType;

    // message: 新スキーマでは content.* に分散するため、いずれかがあれば許容。
    // 受理キーは GENERIC_BODY_KEYS (TEMPLATE_BODY_KEYS からの導出) を使う。
    const c = slide.content || {};
    const hasText = GENERIC_BODY_KEYS.some((k) => hasBodyValue(slide, c, k));
    if (!hasText) {
      errors.push(
        `スライド${n}: テキストコンテンツ（content.main / title / items / quote / value 等、いずれか 1 つ）が欠落`
      );
    }

    // 上の hasText は slideType を見ない。どの型でも content.message があれば通るが、
    // engine の slide-message テンプレートが読むのは {{main}} なので、content.message
    // だけを持つ slide-message は「検証は通るのに本文が空で出る」。旧短縮名 (message)
    // のテンプレートが {{message}} を読む一方、長い名 (slide-message) は {{main}} を
    // 読むという名前のずれがそのまま素通りしていた。型ごとに、テンプレートが実際に
    // 読む源のキーを持っているかを見る。
    const bodyKeys = TEMPLATE_BODY_KEYS[stype];
    if (bodyKeys && !bodyKeys.some((k) => hasBodyValue(slide, c, k))) {
      errors.push(
        `スライド${n}: slideType "${stype}" のテンプレートが読む本文キー（${bodyKeys
          .map((k) => `content.${k}`)
          .join(" / ")}）が無い。この型は他のキーがあっても本文が空で描画される [V-044 / SR-16-01]`
      );
    }

    // icon: md 形式・新 schema 形式どちらでも省略可（content.icon など任意）
    if (!isMdFormat && slide.icon && !ICON_PATTERN.test(slide.icon)) {
      errors.push(`スライド${n}: icon "${slide.icon}" は無効形式（fa-xxx必要）`);
    }
  });

  return errors;
}

// ==================================================
// V-001 〜 V-030 機械検証
// ==================================================

/**
 * structure 段階で検証可能な項目を実行
 * 注: 多くの V-* は HTML/CSS/JS 生成後に verify-slides.js / check-consistency.js で検証される。
 *     本スクリプトでは structure.md / structure.json の段階で判定可能な項目のみ実施し、
 *     それ以外は skip（後段で検証）として記録する。
 */
function runVChecks(data, report, options = {}) {
  const slides = data.slides || [];
  const raw = data._raw || "";

  // V-025: 標準CSSクラス名のみ（type が VALID_SLIDE_TYPES に含まれる）
  let v025ok = true;
  slides.forEach((s, i) => {
    if (s.type && s.type !== "unknown" && !isValidSlideType(s.type)) {
      report.fail("V-025", `スライド${i + 1}: 不正なtype "${s.type}"`);
      v025ok = false;
    }
  });
  if (v025ok) report.pass("V-025", `${slides.length}スライド全てが標準タイプ`);

  // V-030: 背景→質問の順で配置（各セクション内 / 全体）
  // 実装: 最初に出現する質問系の前に、何らかの背景系スライドが存在すること
  const firstQuestionIdx = slides.findIndex(s => QUESTION_TYPES.has(s.type));
  if (firstQuestionIdx >= 0) {
    const hasBackgroundBefore = slides
      .slice(0, firstQuestionIdx)
      .some(s => BACKGROUND_TYPES.has(s.type));
    if (!hasBackgroundBefore) {
      report.fail(
        "V-030",
        `スライド${firstQuestionIdx + 1}が質問系だが、それ以前に背景情報スライドが存在しない`
      );
    } else {
      report.pass("V-030", `背景→質問の順序OK`);
    }
  } else {
    report.skip("V-030", "質問系スライドなし", "not-applicable");
  }

  // V-002: 補足テキスト最大3行（structure.md内に "補足:" 行があれば近傍を確認）
  if (raw) {
    const supplementBlocks = raw.match(/補足[:：][\s\S]+?(?=\n\n|\n#|\n---|$)/g) || [];
    let v002fail = 0;
    supplementBlocks.forEach((blk) => {
      const lineCount = (blk.match(/<br>/g) || []).length + 1;
      if (lineCount > 3) {
        v002fail++;
        report.fail("V-002", `補足ブロックが${lineCount}行（最大3行）`);
      }
    });
    if (supplementBlocks.length > 0 && v002fail === 0) {
      report.pass("V-002", `補足ブロック${supplementBlocks.length}件すべて3行以内`);
    } else if (supplementBlocks.length === 0) {
      report.skip("V-002", "補足テキストなし", "not-applicable");
    }
  } else {
    // 対象が無いのではなく、この入力形式では材料（raw text）が取れないだけ。
    // 補足テキスト自体は json 側に在りうるので not-applicable にはしない。
    report.skip("V-002", "raw textなし（json入力）");
  }

  // V-026: 質問スライドはfs-subheading (構成段階では CSS がまだ無い)
  if (firstQuestionIdx >= 0) {
    report.skip("V-026", "構成段階では判定しない（CSS が要る）");
  }

  // 以降の V-* は HTML/CSS/JS が揃ってからでないと判定できないため、この
  // ゲートでは判定しない。
  //
  // skip の理由に検査先を書かないのは意図的である。以前はここで
  // verify-slides.js / check-consistency.js / validate-print.js の 3 本を
  // 名指ししていたが、下の 25 件のうちその 3 本が実際に判定しているのは
  // V-004 / V-007 / V-013 / V-018 だけで、残りは evaluate-deck.js /
  // validate-slide-layout.js / validate-svg-diagram.py / phase-gate.js /
  // cross-deck-consistency.js / lint-contract-drift.py が拾うか、どこも
  // 拾っていない。名指しは実測と食い違っていたうえ、検査器を動かすたびに
  // 腐る。腐った名指しは「後段で検査される」という誤った地図になり、
  // 実際には誰も見ていない規則を検査済みだと思わせる。
  // 「ここでは判定しない」とだけ言えば、その誤解は生まれない。
  //
  // V-001 をこの一覧から外して個別に書くのは、非該当と後段送りを分けるためである。
  //
  // 2026-08-14 の午前時点では SR-4-03（48%/4%/48%）を判定する実行体がどこにも無く、
  // ここは "no-checker" を上げていた。同日中に scripts/validate-compare-ratio.mjs が
  // 実行体として入り（SKILL.md の検査コマンド一覧から実行され、plugin-composition.yaml
  // が存在を宣言する）、後段で判定されるようになったので deferred へ戻した。
  // 構成段階で判定できないのは、比率が CSS の値で structure.json に無いためである。
  //
  // 比較レイアウトの面を 1 枚も持たない構成は、後段送りですらない（送った先にも
  // 見るものが無い）。「材料が後段にある」と「対象がそもそも無い」を同じ理由文で
  // 出すと、skip の一覧から構成の性質が読めなくなるので分けている。理由文だけでなく
  // kind も分ける（"not-applicable"）。理由文は人が読むためのもので、機械が数える
  // ときには使えないため、分けたつもりが集計では混ざったままになる。
  // V-043 / V-044 が「未使用なら skip」を採っているのと同じ形。
  //
  // 該当型は compare-container を出すテンプレートから採る。短縮名と長い名が対で
  // 現役なので両方を見る（templates/compare.html.tpl と slide-compare.html.tpl が
  // どちらも .compare-container を出す）。code-compare は .code-panel で組む別の
  // レイアウトで、SR-4-03 が実装列に挙げているのは .compare-container /
  // .compare-panel なので対象外。diagram-vs は SVG（vs-svg）で描くのでこれも外。
  const COMPARE_TYPES = new Set(["compare", "slide-compare"]);
  const compareSlides = slides.filter(s => COMPARE_TYPES.has(s.slideType || s.type));
  if (compareSlides.length === 0) {
    report.skip("V-001", "比較レイアウトの面が構成に無い（SR-4-03 非該当）", "not-applicable");
  } else {
    report.skip(
      "V-001",
      `比較レイアウトの面が ${compareSlides.length} 枚。比率は CSS の値なので構成段階では判定しない（生成後の deck を読む検査が判定する）`
    );
  }

  const postPhaseChecks = [
    "V-003", "V-004", "V-005", "V-006", "V-007", "V-008",
    "V-009", "V-010", "V-011", "V-012", "V-013", "V-014", "V-015",
    "V-016", "V-017", "V-018", "V-019", "V-020", "V-021", "V-022",
    "V-023", "V-024", "V-027", "V-028", "V-029"
  ];
  postPhaseChecks.forEach(vid => {
    report.skip(vid, "構成段階では判定しない（HTML/CSS/JS が要る）");
  });

  // ----- v8 拡張検証 -----
  runV8Checks(data, report);

  // ----- コード非画像化 (V-043 / SR-13-01): 全 schemaVersion で実行 (aiVisual 不在時は no-op) -----
  runCodeNonImagingCheck(data, report);

  // ----- slideType 別の本文キー整合 (V-044 / SR-16-01) -----
  runBodyKeyCheck(data, report);
}

function runV8Checks(data, report) {
  const schemaVersion = data?.meta?.schemaVersion || "7.0.0";
  const v8Vids = ["V-031", "V-032", "V-033", "V-034", "V-035", "V-036", "V-037", "V-038"];
  if (schemaVersion !== "8.0.0") {
    v8Vids.forEach(v => report.skip(v, "schemaVersion!=8.0.0 のため非対象", "not-applicable"));
    return;
  }

  const slides = data.slides || [];
  const sections = data.sections || [];
  const sectionIds = new Set(sections.map(s => s.id));
  const accentSet = new Set((data?.theme?.accentColors) || []);

  let v031ok = true, v032ok = true, v033ok = true, v034ok = true;
  let v035ok = true, v036ok = true, v037ok = true, v038ok = true;
  let v031Hit = false, v032Hit = false, v033Hit = false, v034Hit = false;
  let v035Hit = false, v036Hit = false, v037Hit = false, v038Hit = false;

  slides.forEach((s, i) => {
    const tag = `slide[${i + 1}]${s.id ? ` (${s.id})` : ""}`;

    // V-031 / V-032: cover variant
    if (s.cover) {
      const v = s.cover.variant;
      if (v === "hero-icon") {
        v031Hit = true;
        const icon = s.cover.hero?.icon;
        if (!icon || !/^fa-/.test(icon)) {
          report.fail("V-031", `${tag}: hero-icon に cover.hero.icon (fa-*) が必要`);
          v031ok = false;
        }
      }
      if (v === "hero-image") {
        v032Hit = true;
        const ip = s.cover.hero?.imagePath;
        if (!ip) {
          report.fail("V-032", `${tag}: hero-image に cover.hero.imagePath が必要`);
          v032ok = false;
        } else if (!/\.webp$/i.test(ip)) {
          report.warn("V-032", `${tag}: ${ip} は WebP 推奨 (SR-1-04)`);
        }
      }
    }

    // V-033 / V-034: index
    if (s.index) {
      v033Hit = true;
      const hasItems = Array.isArray(s.index.items) && s.index.items.length > 0;
      const hasSections = sections.length > 0;
      if (!hasItems && !hasSections) {
        report.fail("V-033", `${tag}: index.items または sections が必要`);
        v033ok = false;
      }
      if (s.index.currentSection) {
        v034Hit = true;
        if (!sectionIds.has(s.index.currentSection)) {
          report.fail("V-034", `${tag}: currentSection="${s.index.currentSection}" は sections に存在しない`);
          v034ok = false;
        }
      }
    }

    // V-035 / V-036: diagram
    if (s.diagram) {
      const nodes = s.diagram.nodes || [];
      const ids = nodes.map(n => n.id);
      const dup = ids.filter((id, idx) => ids.indexOf(id) !== idx);
      if (dup.length > 0) {
        v036Hit = true;
        report.fail("V-036", `${tag}: 重複ノードID ${[...new Set(dup)].join(", ")}`);
        v036ok = false;
      } else if (nodes.length > 0) {
        v036Hit = true;
      }
      const idSet = new Set(ids);
      (s.diagram.edges || []).forEach((e, ei) => {
        v035Hit = true;
        if (!idSet.has(e.from) || !idSet.has(e.to)) {
          report.fail("V-035", `${tag}: edges[${ei}] from=${e.from} to=${e.to} のうちノード未定義`);
          v035ok = false;
        }
      });
    }

    // V-037: pageOverride 背景
    if (s.pageOverride) {
      v037Hit = true;
      if (s.pageOverride.background === "image" && !s.pageOverride.backgroundImage) {
        report.fail("V-037", `${tag}: background=image なのに backgroundImage 未指定`);
        v037ok = false;
      }
      // V-038: 色は theme.accentColors に含まれるか
      const colors = [
        s.pageOverride.primaryAccent,
        s.pageOverride.secondaryAccent,
        s.pageOverride.pagination?.color
      ].filter(Boolean);
      colors.forEach(c => {
        v038Hit = true;
        if (accentSet.size > 0 && !accentSet.has(c)) {
          report.warn("V-038", `${tag}: 色 "${c}" が theme.accentColors に未登録`);
          v038ok = false;
        }
      });
    }
  });

  // sections.theme の色も V-038 対象
  sections.forEach(sec => {
    const colors = [sec.theme?.primaryAccent, sec.theme?.secondaryAccent, sec.theme?.paginationColor, sec.color].filter(Boolean);
    colors.forEach(c => {
      v038Hit = true;
      if (accentSet.size > 0 && !accentSet.has(c)) {
        report.warn("V-038", `section ${sec.id}: 色 "${c}" が theme.accentColors に未登録`);
        v038ok = false;
      }
    });
  });

  // 結果集約。未使用の skip はいずれも「対象がこの構成に無い」ので not-applicable。
  // 後段へ送っても見るものが無く、deferred に入れると滞留として数えられてしまう。
  if (v031Hit && v031ok) report.pass("V-031", "hero-icon の icon 指定OK");
  if (!v031Hit) report.skip("V-031", "hero-icon variant 未使用", "not-applicable");
  if (v032Hit && v032ok) report.pass("V-032", "hero-image の imagePath 指定OK");
  if (!v032Hit) report.skip("V-032", "hero-image variant 未使用", "not-applicable");
  if (v033Hit && v033ok) report.pass("V-033", "index データソースOK");
  if (!v033Hit) report.skip("V-033", "index slide 未使用", "not-applicable");
  if (v034Hit && v034ok) report.pass("V-034", "currentSection 参照OK");
  if (!v034Hit) report.skip("V-034", "currentSection 未指定", "not-applicable");
  if (v035Hit && v035ok) report.pass("V-035", "diagram edges 参照整合OK");
  if (!v035Hit) report.skip("V-035", "diagram edges 未使用", "not-applicable");
  if (v036Hit && v036ok) report.pass("V-036", "diagram nodes ID 一意");
  if (!v036Hit) report.skip("V-036", "diagram 未使用", "not-applicable");
  if (v037Hit && v037ok) report.pass("V-037", "pageOverride 背景画像指定OK");
  if (!v037Hit) report.skip("V-037", "pageOverride 未使用", "not-applicable");
  if (v038Hit && v038ok) report.pass("V-038", "色は theme.accentColors 内");
  if (!v038Hit) report.skip("V-038", "section/page 色上書き未使用", "not-applicable");
}

// V-043 (SR-13-01): コード非画像化原則。全 schemaVersion で実行（aiVisual 不在時は no-op）。
// コード系 slideType (slide-code / slide-code-compare) は aiVisual で
// image-only / baked-with-overlay にできない（コードは実HTMLコードブロックで描画）。
function runCodeNonImagingCheck(data, report) {
  const CODE_SLIDE_TYPES = new Set(["slide-code", "slide-code-compare"]);
  const slides = data.slides || [];
  let v043ok = true, v043Hit = false;
  slides.forEach((s, i) => {
    const tag = `slide[${i + 1}]${s.id ? ` (${s.id})` : ""}`;
    const stype = s.slideType || s.type;
    if (CODE_SLIDE_TYPES.has(stype) && s.aiVisual) {
      v043Hit = true;
      if (s.aiVisual.pattern === "image-only" || s.aiVisual.textPolicy === "baked-with-overlay") {
        report.fail("V-043", `${tag}: slideType="${stype}" は aiVisual.pattern=image-only / textPolicy=baked-with-overlay にできない（コードは実HTMLコードブロックで描画）`);
        v043ok = false;
      }
    }
  });
  if (v043Hit && v043ok) report.pass("V-043", "コード系 slideType の aiVisual は image-only / baked-with-overlay 不使用");
  if (!v043Hit) report.skip("V-043", "コード系 slideType + aiVisual の組み合わせ未使用", "not-applicable");
}

// V-044 (SR-16-01): slideType 別の本文キー整合。全 schemaVersion で実行。
// 長い名 (slide-*) のテンプレートが読む源のキー (TEMPLATE_BODY_KEYS) を持たない面は、
// 他のテキストキーを持っていても本文が空で描画される。短縮名の書き方 (content.message)
// のまま slideType だけ長い名にした構造がここで止まる。
function runBodyKeyCheck(data, report) {
  const slides = data.slides || [];
  let ok = true, hit = false;
  slides.forEach((s, i) => {
    const stype = s.slideType || s.type;
    const keys = TEMPLATE_BODY_KEYS[stype];
    if (!keys) return;
    hit = true;
    const c = s.content || {};
    if (!keys.some((k) => hasBodyValue(s, c, k))) {
      ok = false;
      const tag = `slide[${i + 1}]${s.id ? ` (${s.id})` : ""}`;
      report.fail(
        "V-044",
        `${tag}: slideType="${stype}" のテンプレートが読む本文キー（${keys
          .map((k) => `content.${k}`)
          .join(" / ")}）が無い。本文が空で描画される`
      );
    }
  });
  if (hit && ok) report.pass("V-044", "各 slideType がテンプレートの読む本文キーを持つ");
  if (!hit) report.skip("V-044", "本文キー表の対象 slideType 未使用", "not-applicable");
}

// ==================================================
// レポート出力
// ==================================================

function printReport(report, options = {}) {
  const STATUS_ICON = { PASS: "✅", FAIL: "❌", WARN: "⚠️ " };
  // 未検査つきの合格は警告と同じ見た目にする。緑の印を出すと、未検査があること
  // が一目では伝わらない。
  STATUS_ICON.PASS_WITH_UNCHECKED = STATUS_ICON.WARN;
  console.log("");
  console.log("═".repeat(64));
  console.log(`  Phase 2.5 仕様確定ゲート 検証結果: ${STATUS_ICON[report.status]} ${report.status}`);
  console.log("═".repeat(64));
  console.log(`  PASS:    ${report.passed.length}`);
  console.log(`  FAIL:    ${report.failed.length}`);
  console.log(`  WARN:    ${report.warned.length}`);
  const unchecked = report.unchecked;
  // 3 つの kind を 1 行にまとめない。まとめると「後段が見る」「見る対象が無い」
  // 「誰も見ていない」が同じ数字になり、この画面から性質が読めなくなる。
  console.log(`  後段送り: ${report.deferred.length} （このゲートでは材料が無い。後段が判定する）`);
  console.log(`  非該当:   ${report.notApplicable.length} （判定する対象がこの構成に無い）`);
  console.log(`  未検査:   ${unchecked.length} （どの工程にも判定する実行体が無い）`);
  console.log("");

  // 未検査は常に出す。件数だけだと「skip の一種」に見えて、実行体が無いこと
  // 自体が伝わらない。
  if (unchecked.length > 0) {
    console.log("--- 未検査（実行体なし）---");
    unchecked.forEach(e => {
      console.log(`  [${e.vid} / ${e.sr}] ${e.desc}`);
      console.log(`    -> ${e.reason}`);
    });
    console.log("");
  }

  if (report.failed.length > 0) {
    console.log("--- ❌ FAIL ---");
    report.failed.forEach(e => {
      console.log(`  [${e.vid} / ${e.sr}] ${e.desc}`);
      if (e.detail) console.log(`    → ${e.detail}`);
    });
    console.log("");
  }
  if (report.warned.length > 0) {
    console.log("--- ⚠️  WARN ---");
    report.warned.forEach(e => {
      console.log(`  [${e.vid} / ${e.sr}] ${e.desc}`);
      if (e.detail) console.log(`    → ${e.detail}`);
    });
    console.log("");
  }
  if (options.verbose && report.passed.length > 0) {
    console.log("--- ✅ PASS ---");
    report.passed.forEach(e => {
      console.log(`  [${e.vid} / ${e.sr}] ${e.desc}`);
    });
    console.log("");
  }

  if (report.status === "FAIL") {
    console.log("⛔ Phase 2.5 ゲート: 不合格。Phase 2 (structure-designer) に差し戻してください。");
  } else if (report.status === "WARN") {
    console.log("⚠️  Phase 2.5 ゲート: 警告あり。--strict モードでは不合格扱い。");
  } else if (report.status === "PASS_WITH_UNCHECKED") {
    // この分岐が無いと下の else に落ちて「合格」と出る。未検査を抱えたまま
    // 合格を名乗るのが偽緑そのものなので、明示的に受ける。
    console.log("⚠️  Phase 2.5 ゲート: FAIL は無いが、上の未検査を誰も判定していない。");
    console.log("   未検査の一覧を利用者に見せた上で、進行の可否を承認してもらうこと。");
  } else {
    console.log("✅ Phase 2.5 ゲート: 合格。Phase 3 (html-generator) に進行可能。");
  }
  console.log("");
}

// ==================================================
// エントリ
// ==================================================

function showHelp() {
  console.log(`
スライド構成案検証スクリプト（Phase 2.5 仕様確定ゲート）

Usage:
  node validate-structure.js <structure-path> [options]

Arguments:
  <structure-path>  structure.md または structure.json

Options:
  --schema           structure.schema.json による JSON Schema 検証を実施
  --strict           WARN を FAIL として扱う（exit code 1）
  --report <path>    JSON レポートを出力
  --verbose, -v      PASS 項目も表示
  -h, --help         ヘルプ

検証項目: V-001 〜 V-030 (bp-classification.md §2-A)
仕様参照: references/spec-registry.md (SR-*)

終了コード:
  0: PASS（P3進行可）
  1: FAIL（P3進行不可、Phase 2 差し戻し）
  2: WARN（要確認、--strict なら FAIL 扱い）
  3: 引数/ファイルエラー
`);
}

async function readInput(filePath) {
  if (filePath) {
    if (!existsSync(filePath)) {
      console.error(`Error: ファイルが見つかりません: ${filePath}`);
      process.exit(3);
    }
    return { content: readFileSync(filePath, "utf-8"), path: filePath };
  }
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf-8");
    if (process.stdin.isTTY) {
      reject(new Error("ファイルパスを指定するか stdin から渡してください"));
      return;
    }
    process.stdin.on("data", c => data += c);
    process.stdin.on("end", () => resolve({ content: data, path: null }));
    process.stdin.on("error", reject);
  });
}

async function main() {
  const { flags, positional, options } = parseArgs();

  if (hasFlag(flags, "help", "h")) {
    showHelp();
    process.exit(0);
  }

  const filePath = positional[0];
  let input;
  try {
    input = await readInput(filePath);
  } catch (e) {
    console.error(`Error: ${e.message}`);
    process.exit(3);
  }

  if (!input.content || input.content.trim() === "") {
    console.error("Error: 入力が空です");
    process.exit(3);
  }

  // フォーマット判定
  const ext = input.path ? extname(input.path).toLowerCase() : "";
  const isMd = ext === ".md" || (!ext && /^#\s/m.test(input.content));

  let data;
  if (isMd) {
    data = parseStructureMd(input.content);
  } else {
    try {
      data = JSON.parse(input.content);
      data._format = "json";
    } catch (e) {
      console.error(`Error: JSONパース失敗: ${e.message}`);
      process.exit(3);
    }
  }

  const report = new ValidationReport();

  // schema 検証
  if (hasFlag(flags, "schema") && !isMd) {
    if (existsSync(SCHEMA_PATH)) {
      try {
        const schema = JSON.parse(readFileSync(SCHEMA_PATH, "utf-8"));
        const schemaErrors = validateAgainstSchema(data, schema);
        if (schemaErrors.length > 0) {
          schemaErrors.forEach(err => report.fail("V-025", err));
        }
      } catch (e) {
        report.warn("V-025", `schema読み込み失敗: ${e.message}`);
      }
    } else {
      report.warn("V-025", `schema未配置: ${SCHEMA_PATH}（schemas/ で別タスク作成中）`);
    }
  }

  // 基本構造検証
  const basicErrors = validateBasicStructure(data, isMd);
  basicErrors.forEach(err => report.fail("V-025", err));

  // V-001〜V-030 機械検証
  if (basicErrors.length === 0) {
    runVChecks(data, report, { verbose: hasFlag(flags, "verbose", "v") });
  }

  // レポート出力
  printReport(report, { verbose: hasFlag(flags, "verbose", "v") });

  if (options.report) {
    writeFileSync(options.report, JSON.stringify(report.toJSON(), null, 2), "utf-8");
    console.log(`📄 JSON レポート: ${options.report}`);
  }

  // strict モード: WARN を FAIL に格上げ
  let exitCode = report.exitCode;
  if (hasFlag(flags, "strict") && exitCode === 2) {
    exitCode = 1;
    console.log("⚠️  --strict: WARN を FAIL に格上げ");
  }
  process.exit(exitCode);
}

main().catch(err => {
  console.error(`Error: ${err.message}`);
  console.error(err.stack);
  process.exit(1);
});
