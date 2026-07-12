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
const SCHEMA_PATH = join(SKILL_ROOT, "schemas", "structure.schema.json");

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

// V-ID 定義表（bp-classification.md §2-A 準拠）
const V_DEFINITIONS = {
  "V-001": { sr: "SR-4-03", desc: "Before/After 48%/4%/48%", level: "FAIL" },
  "V-002": { sr: "SR-4-06", desc: "補足テキスト最大3行", level: "FAIL" },
  "V-003": { sr: "SR-3-04", desc: "フォント最小1.4rem (≒1.75vw)", level: "FAIL" },
  "V-004": { sr: "SR-7-01", desc: "印刷=画面同一比率（vw統一）", level: "FAIL" },
  "V-005": { sr: "SR-10-01", desc: "code-block max-height 420px統一", level: "FAIL" },
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
  "V-021": { sr: "SR-3-09", desc: "20文字超は<br>挿入", level: "WARN" },
  "V-022": { sr: "SR-9-02", desc: "UIテキスト opacity ≥ 0.6", level: "WARN" },
  "V-023": { sr: "SR-9-01", desc: "focus-visible + reduced-motion", level: "FAIL" },
  "V-024": { sr: "SR-3-01", desc: "コードはSF Mono/Fira Code", level: "WARN" },
  "V-025": { sr: "SR-0-02", desc: "標準CSSクラス名のみ使用", level: "FAIL" },
  "V-026": { sr: "SR-3-07", desc: "質問スライドはfs-subheading", level: "FAIL" },
  "V-027": { sr: "SR-8-01", desc: "section-nav 常時表示", level: "WARN" },
  "V-028": { sr: "SR-8-03", desc: "ページネーション5個区切り", level: "WARN" },
  "V-029": { sr: "SR-4-08", desc: "図解はインラインSVG2描画", level: "WARN" },
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
  "V-043": { sr: "SR-13-01", desc: "コード系 slideType は aiVisual で image-only / baked-with-overlay にできない（コードは実HTMLコードブロックで描画）", level: "FAIL" }
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

  skip(vid, reason) {
    const def = V_DEFINITIONS[vid] || { sr: "?", desc: vid };
    this.skipped.push({ vid, ...def, reason });
  }

  get status() {
    if (this.failed.length > 0) return "FAIL";
    if (this.warned.length > 0) return "WARN";
    return "PASS";
  }

  get exitCode() {
    if (this.failed.length > 0) return 1;
    if (this.warned.length > 0) return 2;
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

    // message: 新スキーマでは content.* に分散するため、いずれかがあれば許容
    const c = slide.content || {};
    const hasText =
      typeof slide.message === "string" ||
      typeof c.main === "string" ||
      typeof c.title === "string" ||
      typeof c.message === "string" ||
      Array.isArray(c.items) ||
      Array.isArray(c.steps) ||
      Array.isArray(c.rows);
    if (!hasText) {
      errors.push(`スライド${n}: テキストコンテンツ（message / content.main / title / items 等）が欠落`);
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
    report.skip("V-030", "質問系スライドなし");
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
      report.skip("V-002", "補足テキストなし");
    }
  } else {
    report.skip("V-002", "raw textなし（json入力）");
  }

  // V-026: 質問スライドはfs-subheading (構成段階で type=question であれば後段でCSS確認)
  if (firstQuestionIdx >= 0) {
    report.skip("V-026", "CSS段階で確認（check-consistency.js）");
  }

  // 以降の V-* は HTML/CSS/JS 生成後にしか検証できないため skip
  const postPhaseChecks = [
    "V-001", "V-003", "V-004", "V-005", "V-006", "V-007", "V-008",
    "V-009", "V-010", "V-011", "V-012", "V-013", "V-014", "V-015",
    "V-016", "V-017", "V-018", "V-019", "V-020", "V-021", "V-022",
    "V-023", "V-024", "V-027", "V-028", "V-029"
  ];
  postPhaseChecks.forEach(vid => {
    report.skip(vid, "P3 HTML生成後に verify-slides.js / check-consistency.js / validate-print.js で検証");
  });

  // ----- v8 拡張検証 -----
  runV8Checks(data, report);

  // ----- コード非画像化 (V-043 / SR-13-01): 全 schemaVersion で実行 (aiVisual 不在時は no-op) -----
  runCodeNonImagingCheck(data, report);
}

function runV8Checks(data, report) {
  const schemaVersion = data?.meta?.schemaVersion || "7.0.0";
  const v8Vids = ["V-031", "V-032", "V-033", "V-034", "V-035", "V-036", "V-037", "V-038"];
  if (schemaVersion !== "8.0.0") {
    v8Vids.forEach(v => report.skip(v, "schemaVersion!=8.0.0 のため非対象"));
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

  // 結果集約
  if (v031Hit && v031ok) report.pass("V-031", "hero-icon の icon 指定OK");
  if (!v031Hit) report.skip("V-031", "hero-icon variant 未使用");
  if (v032Hit && v032ok) report.pass("V-032", "hero-image の imagePath 指定OK");
  if (!v032Hit) report.skip("V-032", "hero-image variant 未使用");
  if (v033Hit && v033ok) report.pass("V-033", "index データソースOK");
  if (!v033Hit) report.skip("V-033", "index slide 未使用");
  if (v034Hit && v034ok) report.pass("V-034", "currentSection 参照OK");
  if (!v034Hit) report.skip("V-034", "currentSection 未指定");
  if (v035Hit && v035ok) report.pass("V-035", "diagram edges 参照整合OK");
  if (!v035Hit) report.skip("V-035", "diagram edges 未使用");
  if (v036Hit && v036ok) report.pass("V-036", "diagram nodes ID 一意");
  if (!v036Hit) report.skip("V-036", "diagram 未使用");
  if (v037Hit && v037ok) report.pass("V-037", "pageOverride 背景画像指定OK");
  if (!v037Hit) report.skip("V-037", "pageOverride 未使用");
  if (v038Hit && v038ok) report.pass("V-038", "色は theme.accentColors 内");
  if (!v038Hit) report.skip("V-038", "section/page 色上書き未使用");
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
  if (!v043Hit) report.skip("V-043", "コード系 slideType + aiVisual の組み合わせ未使用");
}

// ==================================================
// レポート出力
// ==================================================

function printReport(report, options = {}) {
  const STATUS_ICON = { PASS: "✅", FAIL: "❌", WARN: "⚠️ " };
  console.log("");
  console.log("═".repeat(64));
  console.log(`  Phase 2.5 仕様確定ゲート 検証結果: ${STATUS_ICON[report.status]} ${report.status}`);
  console.log("═".repeat(64));
  console.log(`  PASS:    ${report.passed.length}`);
  console.log(`  FAIL:    ${report.failed.length}`);
  console.log(`  WARN:    ${report.warned.length}`);
  console.log(`  SKIPPED: ${report.skipped.length} （P3以降で検証）`);
  console.log("");

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
