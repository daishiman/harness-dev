#!/usr/bin/env node
/**
 * validate-briefing-docs — 打ち合わせ資料の文書と briefing.json を、決まった型で検査する。編集はしない。
 *
 * 見るもの: ヒアリング.md・要件定義.md・仕様書.md・変更点.md の章立て・表・番号・版・根拠・相互参照、
 *          言い換え表 (assets/data/plain-language.json)、しきい値 (assets/data/quality-thresholds.json)、
 *          briefing.json の項目と型、pages、ボード HTML (_src/NN_*.html) の属性と見出し。
 *
 * --stage は工程の進み具合を表し、前の工程の検査も含めて行う (累積)。
 *   hearing      ヒアリング.md と briefing.json の項目
 *   requirements + 要件定義.md と 変更点.md
 *   spec         + 仕様書.md と、要件定義との突き合わせ
 *   pages        + briefing.json の pages (ボード HTML があればそれも)
 *   all          + ボード HTML が全部そろっていること、ボード本文の言い換え
 *
 * 使い方:
 *   node scripts/validate-briefing-docs.mjs --dir <打ち合わせ資料> [--stage hearing|requirements|spec|pages|all] [--quiet]
 *
 * 書く場所: <dir>/_check/docs.json だけ。
 * stdout: JSON {schema, status, stage, dir, version, summary, errors[], warnings[], counts{}} (--quiet で要約 1 行)
 * exit: 0=問題なし (warn だけなら 0) / 1=error あり / 2=使い方の誤り (フォルダや briefing.json が無い) / 3=Node が古い・しきい値のファイルが読めない
 */
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import {
  DATA_POLICIES,
  DEVICE_TYPES,
  FILE_RE,
  PAGE_TYPES,
  PLAIN_LANGUAGE_PATH,
  SCREEN_ID,
  expandHome,
  isDir,
  isFile,
  loadJson,
  loadThresholds,
  readText,
  realPath,
  scanMaterials,
  splitLines,
  threshold,
  toPosix,
  writeJson,
} from "./lib/briefing-files.mjs";
import { EXIT, UsageError, emitResult, isEntryPoint, parseOptions, runCli } from "./lib/cli-contract.mjs";
import { tokenizeHtml } from "./lib/html-tokens.mjs";

export { DATA_POLICIES, DEVICE_TYPES, FILE_RE, PAGE_TYPES, SCREEN_ID };

const USAGE = `
使い方:
  validate-briefing-docs.mjs --dir <打ち合わせ資料> [--stage hearing|requirements|spec|pages|all] [--quiet]
`;

export const STAGES = Object.freeze(["hearing", "requirements", "spec", "pages", "all"]);
const VERSION_RE = /^版\s*[:：]\s*(v\d+\.\d+)\s*$/;
const DATE_RE = /^更新日\s*[:：]\s*(\d{4}-\d{2}-\d{2})\s*$/;

const HEARING_H2 = ["1. 目的と範囲", "2. 画面の共通ルール", "3. しくみと基盤", "4. 運用", "5. あとで相談すること"];
const HEARING_TABLE = ["番号", "質問", "回答", "出どころ"];
const REQ_H2 = ["1. 目的", "2. 今の困りごと", "3. 範囲", "4. 使う人と端末", "5. 業務の流れ",
  "6. できること", "7. 守ること", "8. 用語", "9. 決めること"];
const REQ_H3 = { "3. 範囲": ["3.1 最初の版でやること", "3.2 やらないこと"], "5. 業務の流れ": ["5.1 今", "5.2 これから"] };
const REQ_TABLES = {
  "4. 使う人と端末": ["使う人", "人数", "端末", "主にすること"],
  "6. できること": ["番号", "できること", "画面", "最初の版"],
  "8. 用語": ["用語", "意味"],
  "9. 決めること": ["番号", "決めること", "案", "誰に聞くか"],
};
const SPEC_H2 = ["1. 画面一覧", "2. 画面の共通ルール", "3. 画面ごとの項目と動き", "4. データの形", "5. 処理のルール",
  "6. しくみと基盤", "7. 権限と運用", "8. 最初の版に入れないもの"];
const SPEC_RULES_H3 = ["2.1 骨組み", "2.2 ヘッダー", "2.3 メニュー", "2.4 フッター", "2.5 色の役割", "2.6 モーダル",
  "2.7 メッセージ", "2.8 空のときと読み込み中"];
const SPEC_OPS_H3 = ["7.1 権限", "7.2 運用"];
const SPEC_SCREEN_TABLE = ["画面番号", "画面名", "使う人", "端末", "ひとことで"];
const SPEC_ITEM_TABLE = ["項目", "種類", "必須", "初期値", "説明", "根拠"];
const SPEC_OPS_TABLE = ["操作", "動き", "次の画面"];
const SPEC_DATA_TABLE = ["項目", "型", "必須", "例", "根拠"];
const SPEC_RULE_TABLE = ["番号", "ルール", "いつ", "根拠"];
const SPEC_PLATFORM_TABLE = ["項目", "方式", "理由"];
const SPEC_PLATFORM_ITEMS = ["動かす場所", "データの置き場所", "ログイン", "外部とのつなぎ", "自動で動く処理", "バックアップ", "通知"];
const FUTURE_TIMING = ["次の版", "その先"];
const SPEC_ROLE_TABLE = ["役割", "できること", "できないこと", "見える範囲"];
const SCREEN_FIELDS = ["目的", "使う人", "端末", "開き方", "ボード"];
// Reproduction details live in the existing sections; legacy documents remain readable.
export const SPEC_DETAIL_FIELDS = Object.freeze({
  "2.1 骨組み": ["共通配置", "画面区分"],
  "2.3 メニュー": ["アイコン"],
  "2.4 フッター": ["ボタン"],
  "2.6 モーダル": ["モーダル"],
  "2.8 空のときと読み込み中": ["状態表示"],
  "6. しくみと基盤": ["処理境界", "安全対策", "稼働構成"],
  "7.2 運用": ["監視と復旧"],
});
export const SCREEN_DETAIL_FIELDS = Object.freeze(["配置", "画面区分", "状態"]);
const DEVICES = new Set(["スマホ", "PC", "スマホとPC"]);
const CHANGES_TABLE = ["番号", "変更", "場所", "きっかけ"];
const SOURCE_LABELS = new Set(["聞き取り", "既定案", "未定", "要望"]);
/** MATERIAL-UNUSED で名前を出す素材の数 */
const MATERIAL_UNUSED_SHOWN = 5;
/** 要件定義 6 章の できること の終わりの (要望:Hxx) と、9 章の 要望:Hxx */
const REQUEST_TAG = /[(（]\s*要望\s*[:：]\s*(H\d{2,})\s*[)）]/g;
const REQUEST_REF = /要望\s*[:：]\s*(H\d{2,})/g;
const DATA_ONE_RE = /^1\s*件\s*[=＝]\s*\S/;

// briefing.json の項目 (schemas/briefing.schema.json と同じ)。jsonschema を使わずに、ここで項目と型を確かめる
const BRIEFING_KEYS = ["schema", "title", "readers", "palette", "materials", "data_policy", "book", "pages"];
const BOOK_KEYS = ["include_hearing"];
const PAGE_KEYS = ["no", "file", "type", "title", "reader", "screens", "message"];

// 文書の型の正本は assets/templates/*.md.tmpl とここ。tests/test_single_source.py が雛形と document-structure.md に突き合わせる
export {
  BOOK_KEYS, BRIEFING_KEYS, CHANGES_TABLE, HEARING_H2, HEARING_TABLE, PAGE_KEYS, REQ_H2, REQ_H3, REQ_TABLES,
  SPEC_DATA_TABLE, SPEC_H2, SPEC_ITEM_TABLE, SPEC_OPS_H3, SPEC_OPS_TABLE, SPEC_PLATFORM_ITEMS, SPEC_PLATFORM_TABLE,
  SPEC_ROLE_TABLE, SPEC_RULE_TABLE, SPEC_RULES_H3, SPEC_SCREEN_TABLE,
};

/** Python の \b\d{2}\b と同じく、前後が文字 (かな・漢字を含む) でない 2 桁を拾う。 */
const BOARD_NO_RE = /(?<![\p{L}\p{N}_])\d{2}(?![\p{L}\p{N}_])/gu;

class Report {
  constructor() {
    this.errors = [];
    this.warnings = [];
  }

  add(level, code, file, line, message) {
    const item = { code, file, line: line ?? null, message };
    (level === "error" ? this.errors : this.warnings).push(item);
  }

  err(code, file, line, message) {
    this.add("error", code, file, line, message);
  }

  warn(code, file, line, message) {
    this.add("warn", code, file, line, message);
  }
}

/** 見出し・表・箇条書きを行番号つきで取り出す最小の Markdown 読み取り。行番号は 0 始まりで持ち、出すときに +1 する。 */
export class MdDoc {
  constructor(name, text) {
    this.name = name;
    this.lines = splitLines(text);
    /** [level, title, lineIndex] の並び。コードブロックの中は数えない。 */
    this.headings = [];
    let fenced = false;
    this.lines.forEach((raw, idx) => {
      if (/^\s*(```|~~~)/.test(raw)) {
        fenced = !fenced;
        return;
      }
      if (fenced) return;
      const m = /^(#{1,6})\s+(.*?)\s*#*\s*$/.exec(raw);
      if (m) this.headings.push([m[1].length, m[2].trim(), idx]);
    });
  }

  find(level, title) {
    const out = [];
    this.headings.forEach(([lv, t], i) => {
      if (lv === level && t === title) out.push(i);
    });
    return out;
  }

  /** 見出しの次の行から、同じか上の段の見出しの手前まで。 */
  span(headingIndex) {
    const [level, , start] = this.headings[headingIndex];
    let end = this.lines.length;
    for (const [lv, , idx] of this.headings.slice(headingIndex + 1)) {
      if (lv <= level) {
        end = idx;
        break;
      }
    }
    return [start + 1, end];
  }

  section(level, title) {
    const found = this.find(level, title);
    return found.length ? this.span(found[0]) : null;
  }

  subheadings(start, end, level) {
    const out = [];
    this.headings.forEach(([lv, t, idx], i) => {
      if (lv === level && start <= idx && idx < end) out.push([i, t, idx]);
    });
    return out;
  }

  /** 範囲の中の表。2 行目が区切り行 (|---|) のものだけ。rows は [行番号, セル] の並び。 */
  tables(start, end) {
    const tables = [];
    let i = start;
    while (i < end) {
      if (this.lines[i].trim().startsWith("|")) {
        const blockStart = i;
        const block = [];
        while (i < end && this.lines[i].trim().startsWith("|")) {
          block.push([i, this.lines[i]]);
          i += 1;
        }
        if (block.length >= 2 && /^\|?\s*:?-{3,}/.test(block[1][1].trim())) {
          tables.push({
            header: splitRow(block[0][1]),
            rows: block.slice(2).map(([idx, line]) => [idx, splitRow(line)]),
            line: blockStart,
          });
        }
        continue;
      }
      i += 1;
    }
    return tables;
  }

  bullets(start, end) {
    const out = [];
    for (let idx = start; idx < end; idx += 1) {
      const m = /^(?:[-*+]|\d+\.)\s+(.*)$/.exec(this.lines[idx]);
      if (m) out.push([idx, m[1].trim()]);
    }
    return out;
  }

  textLines(start, end) {
    return this.lines.slice(start, end).filter((line) => line.trim());
  }
}

function splitRow(line) {
  let inner = line.trim();
  if (inner.startsWith("|")) inner = inner.slice(1);
  if (inner.endsWith("|") && !inner.endsWith("\\|")) inner = inner.slice(0, -1);
  return inner.split(/(?<!\\)\|/).map((c) => c.replace(/\\\|/g, "|").trim());
}

function ln(idx) {
  return idx === null || idx === undefined ? null : idx + 1;
}

function cell(cells, i) {
  return i < cells.length ? cells[i] : "";
}

function sameList(a, b) {
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

/** メッセージに値を出す形。無ければ空、文字列はそのまま、そのほかは JSON。 */
function show(value) {
  if (value === null || value === undefined) return "";
  return typeof value === "string" ? value : JSON.stringify(value);
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function duplicatesOf(items) {
  const seen = new Set();
  const dup = new Set();
  for (const item of items) {
    if (seen.has(item)) dup.add(item);
    seen.add(item);
  }
  return [...dup];
}

function compareVersions(a, b) {
  const ka = a.replace(/^v+/, "").split(".").map(Number);
  const kb = b.replace(/^v+/, "").split(".").map(Number);
  for (let i = 0; i < Math.max(ka.length, kb.length); i += 1) {
    if (i >= ka.length) return -1;
    if (i >= kb.length) return 1;
    if (ka[i] !== kb[i]) return ka[i] < kb[i] ? -1 : 1;
  }
  return 0;
}

class Context {
  constructor(base, stage) {
    this.base = base;
    this.stage = stage;
    this.report = new Report();
    this.thresholds = loadThresholds();
    let plain = loadJson(PLAIN_LANGUAGE_PATH, null);
    if (plain === null) {
      this.report.warn("PLAIN-LIST-MISSING", "assets/data/plain-language.json", null,
        "言い換え表が読めないため、言い換えの検査を飛ばしました");
      plain = { terms: [] };
    }
    this.terms = Array.isArray(plain.terms) ? plain.terms : [];
    this.briefing = {};
    this.docs = new Map();
    this.version = null;
    this.date = null;
    this.hearingIds = new Set();
    /** ヒアリングの出どころが 要望 の行 [番号, 行] */
    this.requests = [];
    this.questionIds = new Set();
    this.reqScreens = [];
    /** 要件定義 6 章の行。番号 → {screens, first, idx}。表が読めなければ null */
    this.features = null;
    /** 仕様書 4 章の根拠にある 素材: の数 */
    this.dataSources = 0;
    /** 読めたボード (phone / pc) の [screens, data-req の並び, ファイル] */
    this.deviceBoards = [];
    this.definedTerms = [];
    this.termRows = new Map();
    /** 画面番号 → 画面名 (仕様書の画面一覧の順) */
    this.screens = new Map();
    /** 画面番号 → [ボード番号の並び, 行, 未定か] */
    this.screenBoards = new Map();
    this.counts = {};
    /** 素材フォルダの中身 (scanMaterials の結果) と、ファイル名と相対パスの集まり。はじめて要るときに歩く */
    this.materialScan = null;
    this.materialNames = null;
    /** 根拠・出どころの 素材: と、ボードの data-source に出てきた素材の名前 */
    this.usedMaterials = new Set();
  }

  at(stage) {
    return STAGES.indexOf(this.stage) >= STAGES.indexOf(stage);
  }

  thr(group, key) {
    return threshold(this.thresholds, group, key);
  }

  materialsDir() {
    const materials = this.briefing.materials ?? "..";
    return path.resolve(this.base, show(materials));
  }

  materials() {
    if (this.materialScan === null) {
      const root = this.materialsDir();
      this.materialScan = isDir(root) ? scanMaterials(root, this.base) : { items: [], truncated: false };
      this.materialNames = new Set(this.materialScan.items.flatMap((item) => [item.path, path.posix.basename(item.path)]));
    }
    return this.materialScan;
  }

  materialExists(name) {
    if (existsSync(path.resolve(this.materialsDir(), name))) return true;
    this.materials();
    return this.materialNames.has(name);
  }

  useMaterial(name) {
    const value = String(name).replace(/#.*$/, "").trim();
    if (value) this.usedMaterials.add(value);
  }

  loadDoc(name, required = true) {
    if (this.docs.has(name)) return this.docs.get(name);
    const file = path.join(this.base, name);
    if (!isFile(file)) {
      if (required) this.report.err("DOC-MISSING", name, null, `${name} がありません`);
      return null;
    }
    const doc = new MdDoc(name, readText(file));
    this.docs.set(name, doc);
    return doc;
  }
}

// ── 共通の検査 ───────────────────────────────

function checkTitle(ctx, doc, kind) {
  const first = doc.lines.length ? doc.lines[0].trim() : "";
  const m = new RegExp(`^#\\s+${escapeRegExp(kind)}\\s*[:：]\\s*(.+)$`).exec(first);
  if (!m) {
    ctx.report.err("TITLE-LINE", doc.name, 1, `1 行目は「# ${kind}: <タイトル>」にします`);
    return;
  }
  const title = show(ctx.briefing.title).trim();
  if (title && m[1].trim() !== title) {
    ctx.report.warn("TITLE-MISMATCH", doc.name, 1, `タイトルが briefing.json と違います: ${m[1].trim()} / ${title}`);
  }
}

function findHeadValue(doc, pattern) {
  for (const [idx, line] of doc.lines.slice(0, 8).entries()) {
    const m = pattern.exec(line.trim());
    if (m) return [m[1], idx];
  }
  return [null, null];
}

function checkDate(ctx, doc) {
  const [value, idx] = findHeadValue(doc, DATE_RE);
  if (value === null) ctx.report.err("DATE-MISSING", doc.name, null, "先頭に「更新日: YYYY-MM-DD」の行がありません");
  return [value, idx];
}

function checkHeadings(ctx, doc, level, titles, within = null) {
  const positions = [];
  for (const title of titles) {
    let found = doc.find(level, title);
    if (within) found = found.filter((i) => within[0] <= doc.headings[i][2] && doc.headings[i][2] < within[1]);
    if (!found.length) {
      ctx.report.err("HEADING-MISSING", doc.name, null, `見出し「${"#".repeat(level)} ${title}」がありません`);
      continue;
    }
    if (found.length > 1) {
      ctx.report.err("HEADING-DUP", doc.name, ln(doc.headings[found[1]][2]), `見出し「${title}」が 2 回以上あります`);
    }
    positions.push([found[0], title]);
  }
  for (let i = 0; i + 1 < positions.length; i += 1) {
    const [a, titleA] = positions[i];
    const [b, titleB] = positions[i + 1];
    if (b < a) {
      ctx.report.err("HEADING-ORDER", doc.name, ln(doc.headings[b][2]), `見出しの順番が違います: 「${titleA}」より後に「${titleB}」を置きます`);
    }
  }
}

function findTable(ctx, doc, span, header, where, required = true) {
  if (span === null) return null;
  const tables = doc.tables(...span);
  for (const table of tables) {
    if (sameList(table.header, header)) return table;
  }
  if (required) {
    const line = tables.length ? ln(tables[0].line) : ln(span[0] - 1);
    const got = tables.length ? ` (見つかった表: | ${tables[0].header.join(" | ")} |)` : "";
    ctx.report.err("TABLE-MISSING", doc.name, line, `${where} に表 | ${header.join(" | ")} | がありません${got}`);
  }
  return null;
}

function checkIds(ctx, doc, table, prefix, column = 0) {
  const seen = new Set();
  const ids = [];
  const idRe = new RegExp(`^${prefix}\\d{2,}$`);
  for (const [idx, cells] of table.rows) {
    const value = cell(cells, column);
    if (!idRe.test(value)) {
      ctx.report.err("ID-FORMAT", doc.name, ln(idx), `番号は ${prefix}01 の形にします: 「${value}」`);
      continue;
    }
    if (seen.has(value)) ctx.report.err("ID-DUP", doc.name, ln(idx), `番号 ${value} が重複しています`);
    seen.add(value);
    ids.push([value, idx]);
  }
  return ids;
}

function checkEvidence(ctx, doc, raw, idx) {
  const value = raw.trim();
  if (!value) {
    ctx.report.err("EVIDENCE-EMPTY", doc.name, ln(idx), "根拠が空です (素材:<ファイル名> / 聞き取り:Hxx / 例 / 決めること:Qxx)");
    return;
  }
  const parts = value.split(/[、，]|,\s*(?=素材|聞き取り|例|決めること)/).map((p) => p.trim()).filter(Boolean);
  for (const part of parts) {
    if (part === "例") continue;
    let m = /^素材\s*[:：]\s*([^#]+?)(?:#.+)?$/.exec(part);
    if (m) {
      ctx.useMaterial(m[1]);
      if (!ctx.materialExists(m[1].trim())) {
        ctx.report.warn("EVIDENCE-SOURCE-NOT-FOUND", doc.name, ln(idx), `素材フォルダに見つかりません: ${m[1].trim()}`);
      }
      continue;
    }
    m = /^聞き取り\s*[:：]\s*(H\d{2,})$/.exec(part);
    if (m) {
      if (ctx.hearingIds.size && !ctx.hearingIds.has(m[1])) {
        ctx.report.err("EVIDENCE-REF-UNKNOWN", doc.name, ln(idx), `ヒアリング.md に ${m[1]} がありません`);
      }
      continue;
    }
    m = /^決めること\s*[:：]\s*(Q\d{2,})$/.exec(part);
    if (m) {
      if (ctx.questionIds.size && !ctx.questionIds.has(m[1])) {
        ctx.report.err("EVIDENCE-REF-UNKNOWN", doc.name, ln(idx), `要件定義.md の決めることに ${m[1]} がありません`);
      }
      continue;
    }
    ctx.report.err("EVIDENCE-FORMAT", doc.name, ln(idx),
      `根拠の書き方が違います: 「${part}」 (素材:<ファイル名>[#場所] / 聞き取り:Hxx / 例 / 決めること:Qxx)`);
  }
}

/** 「S01, S02」を並びにする。空や なし は []、S01 の形でないものがあれば null。 */
function parseScreenList(raw) {
  const value = raw.trim();
  if (["", "-", "なし", "―"].includes(value)) return [];
  const parts = value.split(/[,、，\s]+/).map((p) => p.trim()).filter(Boolean);
  return parts.every((p) => SCREEN_ID.test(p)) ? parts : null;
}

function escapeRegExp(text) {
  return text.replace(/[\\^$.*+?()[\]{}|]/g, "\\$&");
}

// ── briefing.json の項目と型 ───────────────────────────────

/** 上の階層の項目と型を確かめる (jsonschema の代わり)。pages の中身は checkPages で見る。 */
function checkBriefingShape(ctx) {
  const b = ctx.briefing;
  const name = "briefing.json";
  const shape = (message) => ctx.report.err("BRIEFING-SHAPE", name, null, message);
  for (const key of Object.keys(b)) {
    if (!BRIEFING_KEYS.includes(key)) shape(`知らない項目があります: ${key} (使える項目: ${BRIEFING_KEYS.join(" / ")})`);
  }
  // schema と title の中身は BRIEFING-SCHEMA と BRIEFING-TITLE が見る。ここでは title の型だけ
  if (b.title !== undefined && b.title !== null && typeof b.title !== "string") shape("title は文字列にします");

  if (!Object.hasOwn(b, "readers")) {
    shape("readers がありません (資料を読む人の並び)");
  } else if (!Array.isArray(b.readers) || !b.readers.length) {
    shape("readers は 1 人以上の並びにします");
  } else {
    if (b.readers.some((r) => typeof r !== "string" || !r.trim())) shape("readers の中身は空でない文字列にします");
    const dup = duplicatesOf(b.readers.filter((r) => typeof r === "string"));
    if (dup.length) shape(`readers が重複しています: ${dup.join(" / ")}`);
  }

  if (!Object.hasOwn(b, "palette")) {
    shape("palette がありません (hiraga か、配色の CSS ファイルの場所)");
  } else if (b.palette !== "hiraga" && !(typeof b.palette === "string" && /\.css$/.test(b.palette))) {
    shape(`palette は hiraga か、.css で終わるファイルの場所にします: 「${show(b.palette)}」`);
  }

  if (!Object.hasOwn(b, "materials")) {
    shape("materials がありません (素材フォルダの場所。既定は \"..\")");
  } else if (typeof b.materials !== "string" || !b.materials) {
    shape("materials は素材フォルダの場所 (空でない文字列) にします");
  }

  if (!Object.hasOwn(b, "data_policy")) {
    shape("data_policy がありません (source = 素材のまま (素材をくれた先方と、作る側だけで見る) / masked = 伏せる (それ以外の人にも見せる))");
  } else if (!DATA_POLICIES.includes(b.data_policy)) {
    shape(`data_policy は ${DATA_POLICIES.join(" か ")} にします: 「${show(b.data_policy)}」`);
  }

  if (Object.hasOwn(b, "book")) {
    if (!isPlainObject(b.book)) {
      shape("book はオブジェクトにします (例: {\"include_hearing\": false})");
    } else {
      for (const key of Object.keys(b.book)) {
        if (!BOOK_KEYS.includes(key)) shape(`book に知らない項目があります: ${key} (使える項目: ${BOOK_KEYS.join(" / ")})`);
      }
      if (Object.hasOwn(b.book, "include_hearing") && typeof b.book.include_hearing !== "boolean") {
        shape("book.include_hearing は true か false にします");
      }
    }
  }

  // pages 段からは PAGES-EMPTY が見るので、ここでは前の段のときだけ
  if (!ctx.at("pages")) {
    if (!Object.hasOwn(b, "pages")) shape("pages がありません (まだ決めていなければ [])");
    else if (!Array.isArray(b.pages)) shape("pages は配列にします");
  }
}

/** ページ 1 枚の項目と型。ほかのコード (PAGE-NO など) が見る中身とは重ねない。 */
function checkPageShape(ctx, page, where) {
  const shape = (message) => ctx.report.err("BRIEFING-SHAPE", "briefing.json", null, message);
  for (const key of Object.keys(page)) {
    if (!PAGE_KEYS.includes(key)) shape(`${where} に知らない項目があります: ${key} (使える項目: ${PAGE_KEYS.join(" / ")})`);
  }
  // 数の 12 は PAGE-NO を通ってしまうので、形が合っているときだけ型を言う
  if (page.no !== undefined && page.no !== null && typeof page.no !== "string" && /^\d{2}$/.test(show(page.no))) {
    shape(`${where} の no は文字列にします ("${show(page.no)}" のように引用符で囲む)`);
  }
  for (const key of ["title", "message"]) {
    if (page[key] !== undefined && page[key] !== null && typeof page[key] !== "string") shape(`${where} の ${key} は文字列にします`);
  }
  if (typeof page.reader !== "string" || !page.reader) {
    shape(`${where} の reader がありません (readers のどれかを書く)`);
  }
  if (Array.isArray(page.screens)) {
    const bad = page.screens.filter((s) => typeof s !== "string" || !SCREEN_ID.test(s));
    if (bad.length) shape(`${where} の screens は S01 の形の画面番号にします: ${bad.map((s) => `「${show(s)}」`).join(" ")}`);
    const dup = duplicatesOf(page.screens.filter((s) => typeof s === "string"));
    if (dup.length) shape(`${where} の screens が重複しています: ${dup.join(" / ")}`);
  }
}

// ── ヒアリング.md ───────────────────────────────

function checkHearing(ctx) {
  const doc = ctx.loadDoc("ヒアリング.md");
  if (doc === null) return;
  checkTitle(ctx, doc, "ヒアリング記録");
  checkDate(ctx, doc);
  checkHeadings(ctx, doc, 2, HEARING_H2);
  const seen = new Set();
  const requests = [];
  let items = 0;
  let undecided = 0;
  for (const title of HEARING_H2.slice(0, 4)) {
    const table = findTable(ctx, doc, doc.section(2, title), HEARING_TABLE, `「## ${title}」`);
    if (table === null) continue;
    for (const [value, idx] of checkIds(ctx, doc, table, "H")) {
      if (seen.has(value)) ctx.report.err("ID-DUP", doc.name, ln(idx), `番号 ${value} がほかの章と重複しています`);
      seen.add(value);
    }
    for (const [idx, cells] of table.rows) {
      items += 1;
      const source = cell(cells, 3);
      if (source === "未定") {
        undecided += 1;
      } else if (/^素材\s*[:：]\s*\S.*$/.test(source)) {
        ctx.useMaterial(source.replace(/^素材\s*[:：]\s*/, ""));
      } else if (!SOURCE_LABELS.has(source)) {
        ctx.report.err("SOURCE-FORMAT", doc.name, ln(idx), `出どころは 聞き取り / 素材:<ファイル名> / 既定案 / 未定 / 要望 のどれかにします: 「${source}」`);
      }
      // 名前を挙げて頼まれた機能。番号の続きで 1 章の表の最後に足す (番号の形と重複だけ見るので、並びは通る)
      if (source === "要望" && /^H\d{2,}$/.test(cell(cells, 0))) requests.push([cell(cells, 0), idx]);
      if (!cell(cells, 2) && source !== "未定") {
        ctx.report.warn("ANSWER-EMPTY", doc.name, ln(idx), `${cell(cells, 0)} の回答が空です (分からなければ出どころを 未定 に)`);
      }
    }
  }
  ctx.hearingIds = seen;
  ctx.requests = requests;
  Object.assign(ctx.counts, { hearing_items: items, hearing_undecided: undecided, requests: requests.length });
}

// ── 要件定義.md ───────────────────────────────

function checkRequirements(ctx) {
  const doc = ctx.loadDoc("要件定義.md");
  if (doc === null) return;
  checkTitle(ctx, doc, "要件定義書");
  const [version] = findHeadValue(doc, VERSION_RE);
  if (version === null) ctx.report.err("VERSION-MISSING", doc.name, 2, "2 行目に「版: vX.Y」の行がありません (版の正はここ 1 か所)");
  ctx.version = version;
  [ctx.date] = checkDate(ctx, doc);
  checkHeadings(ctx, doc, 2, REQ_H2);
  for (const [parent, children] of Object.entries(REQ_H3)) {
    checkHeadings(ctx, doc, 3, children, doc.section(2, parent));
  }

  const first = doc.section(3, "3.1 最初の版でやること");
  if (first) {
    const items = doc.bullets(...first).filter(([idx]) => !/^[ \t]/.test(doc.lines[idx]));
    ctx.counts.first_version_items = items.length;
    const limit = ctx.thr("docs", "first_version_items_warn");
    if (!items.length) {
      ctx.report.err("FIRST-VERSION-EMPTY", doc.name, ln(first[0] - 1), "「最初の版でやること」が空です");
    } else if (items.length > limit) {
      ctx.report.warn("FIRST-VERSION-MANY", doc.name, ln(first[0] - 1),
        `最初の版でやることが ${items.length} 個あります。${limit} 個までに絞り、残りは「あとで」に回します`);
    }
  }

  const tables = {};
  for (const [title, header] of Object.entries(REQ_TABLES)) {
    tables[title] = findTable(ctx, doc, doc.section(2, title), header, `「## ${title}」`);
  }
  const users = tables["4. 使う人と端末"];
  if (users !== null && !users.rows.length) ctx.report.err("TABLE-EMPTY", doc.name, ln(users.line), "使う人の表が空です");

  const features = tables["6. できること"];
  /** 要望の番号 → [[できることの番号, 行, 最初の版], ...] */
  const requested = new Map();
  if (features !== null) {
    const ids = checkIds(ctx, doc, features, "F");
    ctx.features = new Map();
    let firstCount = 0;
    for (const [idx, cells] of features.rows) {
      const screens = parseScreenList(cell(cells, 2));
      if (screens === null) {
        ctx.report.err("SCREEN-FORMAT", doc.name, ln(idx), `画面は S01 の形をカンマで区切ります (無ければ なし): 「${cell(cells, 2)}」`);
      } else {
        for (const s of screens) ctx.reqScreens.push([s, idx]);
      }
      const flag = cell(cells, 3);
      if (flag !== "○" && flag !== "あとで") {
        ctx.report.err("FIRST-VERSION-FLAG", doc.name, ln(idx), `最初の版は ○ か あとで にします: 「${flag}」`);
      }
      if (flag === "○") firstCount += 1;
      const fid = cell(cells, 0);
      if (/^F\d{2,}$/.test(fid)) ctx.features.set(fid, { screens: screens ?? [], first: flag === "○", idx });
      for (const [, hid] of cell(cells, 1).matchAll(REQUEST_TAG)) {
        if (!requested.has(hid)) requested.set(hid, []);
        requested.get(hid).push([fid, idx, flag]);
      }
    }
    Object.assign(ctx.counts, { features: ids.length, features_first: firstCount });
  }

  const guard = doc.section(2, "7. 守ること");
  if (guard && !doc.bullets(...guard).length) {
    ctx.report.warn("LIST-EMPTY", doc.name, ln(guard[0] - 1), "「守ること」が空です (速さ・安全・バックアップ・使いやすさ)");
  }

  const terms = tables["8. 用語"];
  if (terms !== null) {
    ctx.definedTerms = terms.rows.map(([, c]) => cell(c, 0)).filter(Boolean);
    ctx.termRows.set(doc.name, new Set([...terms.rows.map(([idx]) => idx), terms.line, terms.line + 1]));
    ctx.counts.terms_defined = ctx.definedTerms.length;
  }

  const questions = tables["9. 決めること"];
  if (questions !== null) {
    ctx.questionIds = new Set(checkIds(ctx, doc, questions, "Q").map(([value]) => value));
    ctx.counts.questions = ctx.questionIds.size;
  }
  if (features !== null) checkRequests(ctx, doc, requested, questions);
}

/** 名前を挙げて頼まれた機能 (ヒアリングの出どころ 要望) が 6 章に残っていること。あとで に回したものは 9 章で聞くこと。 */
function checkRequests(ctx, doc, requested, questions) {
  for (const [hid, idx] of ctx.requests) {
    if (!requested.has(hid)) {
      ctx.report.warn("REQUEST-MISSING", "ヒアリング.md", ln(idx),
        `${hid} は 要望 ですが、要件定義.md 6 章の できること に (要望:${hid}) がありません (外すなら あとで に回して 9 章で聞く)`);
    }
  }
  const asked = new Set();
  for (const [, cells] of questions?.rows ?? []) {
    for (const [, hid] of cells.join(" ").matchAll(REQUEST_REF)) asked.add(hid);
  }
  const deferred = new Set();
  for (const [hid, rows] of requested) {
    for (const [fid, idx, flag] of rows) {
      if (flag !== "あとで") continue;
      deferred.add(hid);
      if (questions !== null && !asked.has(hid)) {
        ctx.report.warn("REQUEST-DEFERRED-NO-Q", doc.name, ln(idx),
          `${fid} (要望:${hid}) を あとで に回しています。9 章の 決めること に 要望:${hid} の行を足して聞きます`);
      }
    }
  }
  ctx.counts.requests_deferred = deferred.size;
}

// ── 変更点.md ───────────────────────────────

function checkChanges(ctx) {
  const doc = ctx.loadDoc("変更点.md");
  if (doc === null) return;
  checkTitle(ctx, doc, "変更点");
  const versions = [];
  doc.headings.forEach(([level, title, idx], i) => {
    if (level !== 2) return;
    const m = /^(v\d+\.\d+)\s*[(（]\s*(\d{4}-\d{2}-\d{2})\s*[)）]$/.exec(title);
    if (!m) {
      ctx.report.err("CHANGES-HEADING", doc.name, ln(idx), `版の見出しは「## v0.2 (YYYY-MM-DD)」にします: 「${title}」`);
      return;
    }
    versions.push([m[1], idx]);
    const table = findTable(ctx, doc, doc.span(i), CHANGES_TABLE, `「## ${title}」`);
    if (table !== null) {
      checkIds(ctx, doc, table, "C");
      if (!table.rows.length) ctx.report.err("CHANGES-EMPTY", doc.name, ln(table.line), `${m[1]} の変更が空です`);
      table.rows.forEach(([idx, cells], n) => {
        const want = `C${String(n + 1).padStart(2, "0")}`;
        const value = cell(cells, 0);
        if (/^C\d{2,}$/.test(value) && value !== want) {
          ctx.report.err("CHANGES-NUMBER", doc.name, ln(idx), `番号は版ごとに C01 から順に振ります: 「${value}」は ${want} にします`);
        }
        const blank = CHANGES_TABLE.slice(1).filter((_, i) => !cell(cells, i + 1));
        if (blank.length) ctx.report.err("CHANGES-CELL-EMPTY", doc.name, ln(idx), `${value || "この行"} の ${blank.join("・")} が空です`);
      });
    }
  });
  ctx.counts.changes_versions = versions.length;
  for (let i = 0; i + 1 < versions.length; i += 1) {
    const [a] = versions[i];
    const [b, idx] = versions[i + 1];
    if (compareVersions(b, a) >= 0) ctx.report.warn("CHANGES-ORDER", doc.name, ln(idx), "新しい版を上に書きます");
  }
  if (ctx.version) {
    if (versions.length && versions[0][0] !== ctx.version) {
      ctx.report.err("CHANGES-VERSION", doc.name, ln(versions[0][1]),
        `一番上の版 ${versions[0][0]} が要件定義.md の版 ${ctx.version} と違います`);
    }
    if (!versions.length && ctx.version !== "v0.1") {
      ctx.report.err("CHANGES-VERSION", doc.name, null, `版が ${ctx.version} なのに変更点がありません`);
    }
  }
}

// ── 仕様書.md ───────────────────────────────

function checkDetailFields(ctx, doc, span, fields, where) {
  if (!span) return;
  const text = doc.lines.slice(...span).join("\n").replace(/<!--[\s\S]*?-->/g, "");
  for (const field of fields) {
    const values = [...text.matchAll(new RegExp(`^[-*+][ \t]+${field}[ \t]*[:：][ \t]*(.*)$`, "gm"))].map((m) => m[1].trim());
    if (!values.some((value) => value && !/^(?:[-—]|未定|要確認|TBD|TODO|\{\{.*\}\})$/i.test(value))) {
      ctx.report.warn("SPEC-DETAIL-MISSING", doc.name, ln(span[0]), `${where} の「${field}」が未記入です。具体的な内容、使わない理由、または案と決めることの番号を仕様書に残してください`);
    }
  }
}

function checkSpec(ctx) {
  const doc = ctx.loadDoc("仕様書.md");
  if (doc === null) return;
  checkTitle(ctx, doc, "仕様書");
  const [version, vidx] = findHeadValue(doc, VERSION_RE);
  if (version === null) {
    ctx.report.err("VERSION-MISSING", doc.name, 2, "2 行目に「版: vX.Y」の行がありません");
  } else if (ctx.version && version !== ctx.version) {
    ctx.report.err("VERSION-MISMATCH", doc.name, ln(vidx), `版 ${version} が要件定義.md の版 ${ctx.version} と違います`);
  }
  const [date, didx] = checkDate(ctx, doc);
  if (date !== null && ctx.date && date !== ctx.date) {
    ctx.report.err("DATE-MISMATCH", doc.name, ln(didx), `更新日 ${date} が要件定義.md の更新日 ${ctx.date} と違います`);
  }
  checkHeadings(ctx, doc, 2, SPEC_H2);
  for (const [title, fields] of Object.entries(SPEC_DETAIL_FIELDS)) {
    checkDetailFields(ctx, doc, doc.section(title.startsWith("6.") ? 2 : 3, title), fields, title);
  }
  checkHeadings(ctx, doc, 3, SPEC_RULES_H3, doc.section(2, "2. 画面の共通ルール"));
  for (const title of SPEC_RULES_H3) {
    const span = doc.section(3, title);
    if (span && !doc.textLines(...span).length) {
      ctx.report.warn("RULE-EMPTY", doc.name, ln(span[0] - 1), `「${title}」が空です (決まっていなければ 案 と 決めること:Qxx を書く)`);
    }
  }

  const listing = findTable(ctx, doc, doc.section(2, "1. 画面一覧"), SPEC_SCREEN_TABLE, "「## 1. 画面一覧」");
  if (listing !== null) {
    const rowsByLine = new Map(listing.rows);
    for (const [value, idx] of checkIds(ctx, doc, listing, "S")) ctx.screens.set(value, cell(rowsByLine.get(idx), 1));
    ctx.counts.screens = ctx.screens.size;
    const limit = ctx.thr("docs", "screens_warn");
    if (ctx.screens.size > limit) {
      ctx.report.warn("SCREENS-MANY", doc.name, ln(listing.line), `画面が ${ctx.screens.size} 個あります。最初の版は ${limit} 個までに絞ります`);
    }
  }

  const screensSpan = doc.section(2, "3. 画面ごとの項目と動き");
  const seenSections = new Map();
  const pendingNext = [];
  if (screensSpan) {
    for (const [hi, title, idx] of doc.subheadings(...screensSpan, 3)) {
      const m = /^(S\d{2,})\s+(.+)$/.exec(title);
      if (!m) {
        ctx.report.err("SCREEN-HEADING", doc.name, ln(idx), `画面の見出しは「### S01 画面名」にします: 「${title}」`);
        continue;
      }
      const sid = m[1];
      const name = m[2].trim();
      seenSections.set(sid, idx);
      if (!ctx.screens.has(sid)) {
        ctx.report.err("SCREEN-MISMATCH", doc.name, ln(idx), `${sid} が「1. 画面一覧」にありません`);
      } else if (ctx.screens.get(sid) !== name) {
        ctx.report.err("SCREEN-MISMATCH", doc.name, ln(idx), `${sid} の画面名が画面一覧と違います: 「${name}」 / 「${ctx.screens.get(sid)}」`);
      }
      const span = doc.span(hi);
      checkDetailFields(ctx, doc, span, SCREEN_DETAIL_FIELDS, sid);
      const fields = new Map();
      for (let lidx = span[0]; lidx < span[1]; lidx += 1) {
        const fm = /^[-*]\s*(目的|使う人|端末|開き方|ボード)\s*[:：]\s*(.*)$/.exec(doc.lines[lidx]);
        if (fm) fields.set(fm[1], [fm[2].trim(), lidx]);
      }
      for (const key of SCREEN_FIELDS) {
        if (!fields.has(key)) ctx.report.err("SCREEN-FIELD-MISSING", doc.name, ln(idx), `${sid} に「- ${key}:」の行がありません`);
      }
      if (fields.has("端末")) {
        const [device, lidx] = fields.get("端末");
        if (!DEVICES.has(device.replace(/[ 　]/g, ""))) {
          ctx.report.err("SCREEN-DEVICE", doc.name, ln(lidx), `端末は スマホ / PC / スマホと PC のどれかにします: 「${device}」`);
        }
      }
      if (fields.has("ボード")) {
        const [raw, lidx] = fields.get("ボード");
        const nos = raw.match(BOARD_NO_RE) || [];
        const undecided = ["", "-", "未定", "なし"].includes(raw);
        if (!nos.length && !undecided) {
          ctx.report.err("BOARD-REF-FORMAT", doc.name, ln(lidx), `ボードは 02 の形 (複数はカンマ) か 未定 にします: 「${raw}」`);
        }
        ctx.screenBoards.set(sid, [nos, lidx, undecided]);
      }
      const items = findTable(ctx, doc, span, SPEC_ITEM_TABLE, `「### ${title}」`);
      if (items !== null) {
        for (const [ridx, cells] of items.rows) checkEvidence(ctx, doc, cell(cells, 5), ridx);
      }
      const ops = findTable(ctx, doc, span, SPEC_OPS_TABLE, `「### ${title}」`);
      if (ops !== null) {
        for (const [ridx, cells] of ops.rows) {
          const value = cell(cells, 2);
          if (value === "同じ画面" || value === "なし") continue;
          const targets = parseScreenList(value);
          if (!targets || !targets.length) {
            ctx.report.err("NEXT-SCREEN-FORMAT", doc.name, ln(ridx), `次の画面は S01 / 同じ画面 / なし にします: 「${value}」`);
            continue;
          }
          for (const t of targets) pendingNext.push([t, ridx]);
        }
      }
    }
  }
  for (const [sid, name] of ctx.screens) {
    if (!seenSections.has(sid)) ctx.report.err("SCREEN-MISMATCH", doc.name, null, `${sid} ${name} の「### ${sid} …」がありません`);
  }
  for (const [target, ridx] of pendingNext) {
    if (!ctx.screens.has(target)) ctx.report.err("NEXT-SCREEN-UNKNOWN", doc.name, ln(ridx), `次の画面 ${target} が画面一覧にありません`);
  }
  for (const [sid, idx] of ctx.reqScreens) {
    if (!ctx.screens.has(sid)) {
      ctx.report.err("REQ-SCREEN-UNKNOWN", "要件定義.md", ln(idx), `「できること」の画面 ${sid} が仕様書の画面一覧にありません`);
    }
  }

  const dataSpan = doc.section(2, "4. データの形");
  let dataCount = 0;
  if (dataSpan) {
    for (const [hi, title, idx] of doc.subheadings(...dataSpan, 3)) {
      if (!/^D\d{2,}\s+.+$/.test(title)) {
        ctx.report.err("DATA-HEADING", doc.name, ln(idx), `データの見出しは「### D01 データ名」にします: 「${title}」`);
        continue;
      }
      dataCount += 1;
      const span = doc.span(hi);
      const table = findTable(ctx, doc, span, SPEC_DATA_TABLE, `「### ${title}」`);
      // /build-app が読む欄: 何を 1 件と数えるか (表の前の 1 行) と、数の単位
      const head = doc.lines.slice(span[0], table === null ? span[1] : table.line);
      if (!head.some((line) => DATA_ONE_RE.test(line.trim()))) {
        ctx.report.warn("DATA-ONE-MISSING", doc.name, ln(idx), `「### ${title}」の下 (表の前) に「1 件 = <何を 1 件と数えるか>」の行がありません`);
      }
      if (table !== null) {
        for (const [ridx, cells] of table.rows) {
          checkEvidence(ctx, doc, cell(cells, 4), ridx);
          ctx.dataSources += (cell(cells, 4).match(/素材\s*[:：]/g) || []).length;
          if (cell(cells, 1).replace(/[ 　]/g, "") === "数") {
            ctx.report.warn("DATA-UNIT-MISSING", doc.name, ln(ridx),
              `${cell(cells, 0)} の 型 が「数」だけです。単位をかっこで書きます (例: 数 (円))。番号なら 型 を 番号 にします`);
          }
        }
      }
    }
    if (!dataCount) ctx.report.err("DATA-MISSING", doc.name, ln(dataSpan[0] - 1), "データの形 (### D01 …) が 1 つもありません");
  }
  ctx.counts.data = dataCount;

  const rules = findTable(ctx, doc, doc.section(2, "5. 処理のルール"), SPEC_RULE_TABLE, "「## 5. 処理のルール」");
  if (rules !== null) {
    ctx.counts.rules = checkIds(ctx, doc, rules, "R").length;
    for (const [ridx, cells] of rules.rows) checkEvidence(ctx, doc, cell(cells, 3), ridx);
  }

  const platform = findTable(ctx, doc, doc.section(2, "6. しくみと基盤"), SPEC_PLATFORM_TABLE, "「## 6. しくみと基盤」");
  if (platform !== null) {
    const names = platform.rows.map(([, c]) => cell(c, 0));
    for (const item of SPEC_PLATFORM_ITEMS) {
      if (!names.some((n) => n.includes(item))) {
        ctx.report.warn("PLATFORM-ITEM-MISSING", doc.name, ln(platform.line), `しくみと基盤に「${item}」の行がありません (決まっていなければ 方式 を「案: 〜 (Qxx)」に)`);
      }
    }
    for (const [ridx, cells] of platform.rows) {
      if (!cell(cells, 1)) ctx.report.warn("PLATFORM-EMPTY", doc.name, ln(ridx), `「${cell(cells, 0)}」の方式が空です (決まっていなければ 方式 を「案: 〜 (Qxx)」に)`);
    }
  }

  checkHeadings(ctx, doc, 3, SPEC_OPS_H3, doc.section(2, "7. 権限と運用"));
  findTable(ctx, doc, doc.section(3, "7.1 権限"), SPEC_ROLE_TABLE, "「### 7.1 権限」");
  const running = doc.section(3, "7.2 運用");
  if (running && !doc.bullets(...running).length) ctx.report.warn("LIST-EMPTY", doc.name, ln(running[0] - 1), "「7.2 運用」が空です");
  const later = doc.section(2, "8. 最初の版に入れないもの");
  if (later && !doc.bullets(...later).length) {
    ctx.report.warn("LIST-EMPTY", doc.name, ln(later[0] - 1), "「最初の版に入れないもの」(次に広げる候補) が空です");
  } else if (later) {
    checkFutureFields(ctx, doc, later);
  }
}

// 8 章の候補ごとに、字下げした「備え:」と「時期: 次の版|その先」があるか
function checkFutureFields(ctx, doc, [start, end]) {
  const items = [];
  for (let idx = start; idx < end; idx += 1) {
    const line = doc.lines[idx];
    const top = /^[-*+]\s+(.*)$/.exec(line);
    if (top) {
      items.push({ idx, name: top[1].split(/[:：]/)[0].trim(), fields: {} });
      continue;
    }
    const sub = /^[ \t]+[-*+]\s+(備え|時期)\s*[:：]\s*(.*)$/.exec(line);
    if (sub && items.length) items.at(-1).fields[sub[1]] = sub[2].trim();
  }
  for (const { idx, name, fields } of items) {
    const missing = [];
    if (!fields["備え"]) missing.push("備え");
    if (!fields["時期"]) missing.push("時期");
    if (missing.length) {
      ctx.report.warn("FUTURE-FIELD-MISSING", doc.name, ln(idx),
        `「${name}」の下に ${missing.map((k) => `「${k}:」`).join("と")}の行がありません (時期は ${FUTURE_TIMING.join(" か ")}、備え が無ければ「なし」)`);
    }
    const timing = (fields["時期"] ?? "").replace(/[。.]$/, "");
    if (timing && !FUTURE_TIMING.includes(timing)) {
      ctx.report.warn("FUTURE-FIELD-MISSING", doc.name, ln(idx),
        `「${name}」の「時期: ${timing}」は ${FUTURE_TIMING.join(" か ")} のどちらかにします`);
    }
  }
}

// ── briefing.json の pages と ボード ───────────────────────────────

const BOARD_SKIP_TAGS = new Set(["script", "style", "title"]);

/** ボード HTML から、本文の文字 (タグの間ごと)、h1 と .lead の文字、最初の class="board" の属性、要件の札 (.req の data-req)、素材の印 (data-source) を取る。 */
function readBoard(html) {
  const board = { text: [], h1: [], lead: [], attrs: null, reqs: [], sources: [] };
  let skip = 0;
  let h1Depth = 0;
  let leadTag = null;
  let leadDepth = 0;
  const end = (tag) => {
    if (BOARD_SKIP_TAGS.has(tag) && skip) skip -= 1;
    if (tag === "h1" && h1Depth) h1Depth -= 1;
    if (tag === leadTag && leadDepth) leadDepth -= 1;
  };
  for (const token of tokenizeHtml(html)) {
    if (token.type === "start") {
      if (BOARD_SKIP_TAGS.has(token.tag)) skip += 1;
      const classes = (token.attrs.class || "").split(/\s+/);
      if (board.attrs === null && classes.includes("board")) board.attrs = token.attrs;
      if (!skip && classes.includes("req") && typeof token.attrs["data-req"] === "string") board.reqs.push(token.attrs["data-req"].trim());
      if (!skip && typeof token.attrs["data-source"] === "string") board.sources.push(token.attrs["data-source"]);
      if (token.tag === "h1") {
        h1Depth += 1;
        board.h1.push("");
      }
      if (leadDepth && token.tag === leadTag) {
        leadDepth += 1;
      } else if (!leadDepth && !skip && classes.includes("lead")) {
        leadTag = token.tag;
        leadDepth = 1;
        board.lead.push("");
      }
      if (token.selfClosing) end(token.tag);
    } else if (token.type === "end") {
      end(token.tag);
    } else if (token.type === "text" && !skip) {
      board.text.push(token.text);
      if (h1Depth && board.h1.length) board.h1[board.h1.length - 1] += token.text;
      if (leadDepth) board.lead[board.lead.length - 1] += token.text;
    }
  }
  return board;
}

/**
 * 素材フォルダの読める素材 (PDF・画像・CSV・文字) が、根拠や出どころの 素材: か、ボードの data-source のどこかに出ていること。
 * Excel は CSV に書き出したほうを見るので数えない。
 */
function checkMaterialsUsed(ctx) {
  const unused = ctx.materials().items
    .filter((item) => item.type !== "excel" && item.type !== "other")
    .map((item) => item.path)
    .filter((rel) => !ctx.usedMaterials.has(rel) && !ctx.usedMaterials.has(path.posix.basename(rel)));
  ctx.counts.materials_unused = unused.length;
  if (!unused.length) return;
  const shown = unused.slice(0, MATERIAL_UNUSED_SHOWN).join("、") + (unused.length > MATERIAL_UNUSED_SHOWN ? ` ほか ${unused.length - MATERIAL_UNUSED_SHOWN} 個` : "");
  ctx.report.warn("MATERIAL-UNUSED", show(ctx.briefing.materials ?? ".."), null,
    `どの根拠にもボードにも出ていない素材が ${unused.length} 個あります: ${shown}`);
}

function checkPages(ctx) {
  const pages = ctx.briefing.pages;
  const name = "briefing.json";
  if (!Array.isArray(pages) || !pages.length) {
    ctx.report.err("PAGES-EMPTY", name, null, "pages が空です (ページ構成を決めて pages に書く)");
    return;
  }
  const readers = Array.isArray(ctx.briefing.readers) ? ctx.briefing.readers : [];
  ctx.counts.pages = pages.length;
  const pagesLimit = ctx.thr("docs", "pages_warn");
  if (pages.length > pagesLimit) ctx.report.warn("PAGES-MANY", name, null, `ボードが ${pages.length} 枚あります。${pagesLimit} 枚までに絞ります`);
  const seen = new Set();
  const covered = new Set();
  let found = 0;
  pages.forEach((page, i) => {
    const where = `pages[${i}]`;
    if (!isPlainObject(page)) {
      ctx.report.err("PAGE-FORMAT", name, null, `${where} がオブジェクトではありません`);
      return;
    }
    checkPageShape(ctx, page, where);
    const no = show(page.no);
    const file = show(page.file);
    const kind = page.type;
    let screens = Array.isArray(page.screens) ? page.screens : null;
    if (!/^\d{2}$/.test(no)) {
      ctx.report.err("PAGE-NO", name, null, `${where} の no は 2 桁にします: 「${no}」`);
    } else if (seen.has(no)) {
      ctx.report.err("PAGE-NO", name, null, `${where} の no ${no} が重複しています`);
    }
    seen.add(no);
    const m = FILE_RE.exec(file);
    if (!m || m[1] !== no) {
      ctx.report.err("PAGE-FILE", name, null, `${where} の file は「${no}_<slug>.html」(slug は英小文字・数字・-) にします: 「${file}」`);
    }
    if (!PAGE_TYPES.includes(kind)) {
      ctx.report.err("PAGE-TYPE", name, null, `${where} の type が不明です: 「${show(kind)}」 (${PAGE_TYPES.join(" / ")})`);
    }
    for (const key of ["title", "message"]) {
      if (!show(page[key]).trim()) ctx.report.err("PAGE-FIELD", name, null, `${where} の ${key} が空です`);
    }
    // reader が無いときは BRIEFING-SHAPE が言うので、ここは readers に無い名前のときだけ
    if (readers.length && typeof page.reader === "string" && page.reader && !readers.includes(page.reader)) {
      ctx.report.warn("PAGE-READER", name, null, `${where} の reader が readers にありません: 「${page.reader}」`);
    }
    if (screens === null) {
      ctx.report.err("PAGE-SCREENS", name, null, `${where} の screens は配列にします`);
      screens = [];
    }
    if (DEVICE_TYPES.includes(kind) && !screens.length) {
      ctx.report.err("PAGE-SCREENS", name, null, `${where} (${kind}) には screens を 1 つ以上書きます`);
    }
    for (const sid of screens) {
      if (ctx.screens.size && !ctx.screens.has(sid)) {
        ctx.report.err("PAGE-SCREEN-UNKNOWN", name, null, `${where} の画面 ${show(sid)} が仕様書の画面一覧にありません`);
      }
      if (DEVICE_TYPES.includes(kind)) covered.add(sid);
      if (DEVICE_TYPES.includes(kind) && ctx.screenBoards.has(sid) && !ctx.screenBoards.get(sid)[0].includes(no)) {
        ctx.report.warn("BOARD-REF-MISMATCH", "仕様書.md", ln(ctx.screenBoards.get(sid)[1]), `${sid} の「ボード:」に ${no} がありません`);
      }
    }

    if (!m) return;
    const file_ = path.join(ctx.base, "_src", file);
    if (!isFile(file_)) {
      if (ctx.at("all")) {
        ctx.report.err("BOARD-MISSING", `_src/${file}`, null, "ボード HTML がありません (build-briefing-scaffold.mjs boards で作る)");
      }
      return;
    }
    found += 1;
    checkBoard(ctx, page, file_);
  });
  ctx.counts.boards_found = found;
  // 最初の版の画面は 1 枚に 1 つずつ phone か pc のボードにする
  let withoutBoard = 0;
  for (const [sid, screenName] of ctx.screens) {
    if (covered.has(sid)) continue;
    withoutBoard += 1;
    ctx.report.warn("SCREEN-BOARD-MISSING", name, null, `${sid} ${screenName} を screens に持つ phone か pc のページがありません`);
  }
  ctx.counts.screens_without_board = withoutBoard;
  const sourcesLimit = ctx.thr("docs", "data_map_sources");
  if (ctx.dataSources >= sourcesLimit && !pages.some((page) => isPlainObject(page) && page.type === "data-map")) {
    ctx.report.warn("DATA-MAP-MISSING", name, null,
      `仕様書 4 章の根拠に 素材: が ${ctx.dataSources} 個あります。data-map のページを置きます (${sourcesLimit} 個以上のとき)`);
  }
  checkReqTags(ctx);
  for (const [sid, [nos, lidx, undecided]] of ctx.screenBoards) {
    for (const no of nos) {
      if (!seen.has(no)) ctx.report.err("BOARD-REF-UNKNOWN", "仕様書.md", ln(lidx), `${sid} の「ボード:」${no} が pages にありません`);
    }
    if (undecided) ctx.report.warn("BOARD-REF-EMPTY", "仕様書.md", ln(lidx), `${sid} の「ボード:」が未定です`);
  }
}

function checkBoard(ctx, page, file) {
  const rel = `_src/${path.basename(file)}`;
  const board = readBoard(readText(file));
  for (const source of board.sources) ctx.useMaterial(source);
  const attrs = board.attrs || {};
  const no = show(page.no);
  const kind = page.type;
  const pageScreens = Array.isArray(page.screens) ? page.screens : [];
  if (!board.attrs) {
    ctx.report.err("BOARD-ATTR", rel, null, "class=\"board\" の要素がありません");
  } else {
    if (attrs["data-board"] !== no) {
      ctx.report.err("BOARD-ATTR", rel, null, `data-board が pages の no と違います: 「${show(attrs["data-board"])}」 / 「${no}」`);
    }
    if (attrs["data-type"] !== kind) {
      ctx.report.err("BOARD-ATTR", rel, null, `data-type が pages の type と違います: 「${show(attrs["data-type"])}」 / 「${show(kind)}」`);
    }
    const boardScreens = (attrs["data-screens"] || "").split(/\s+/).filter(Boolean).sort();
    if (DEVICE_TYPES.includes(kind) && !sameList(boardScreens, [...pageScreens].map(show).sort())) {
      ctx.report.warn("BOARD-SCREENS-MISMATCH", rel, null, "data-screens が pages の screens と違います");
    }
  }
  if (ctx.features !== null) {
    for (const req of new Set(board.reqs)) {
      if (!ctx.features.has(req)) ctx.report.err("REQ-TAG-UNKNOWN", rel, null, `.req の data-req="${req}" が要件定義.md 6 章にありません`);
    }
  }
  if (DEVICE_TYPES.includes(kind)) ctx.deviceBoards.push([pageScreens, board.reqs, rel]);
  const h1 = board.h1.map((t) => t.trim()).join(" ");
  const title = show(page.title).trim();
  if (h1 && h1 !== title) {
    ctx.report.warn("BOARD-TITLE-MISMATCH", rel, null, `h1 が pages の title と違います: 「${h1}」 / 「${show(page.title)}」`);
  }
  // 空白は HTML の折り返しで増減するので外してくらべる
  const lead = board.lead.join("").replace(/\s+/g, " ").trim();
  const bare = (text) => text.replace(/\s+/g, "");
  if (lead && bare(lead) !== bare(show(page.message))) {
    ctx.report.warn("BOARD-LEAD-MISMATCH", rel, null, `.lead が pages の message と違います: 「${lead}」 / 「${show(page.message)}」`);
  }
  if (DEVICE_TYPES.includes(kind) && ctx.screens.size) {
    const names = pageScreens.map((s) => ctx.screens.get(s) || "");
    if (!names.some((n) => n && h1.includes(n))) {
      ctx.report.warn("BOARD-TITLE-SCREEN", rel, null, `h1 に画面名 (${names.filter(Boolean).join(" / ")}) を入れます`);
    }
  }
  if (ctx.at("all")) checkPlainText(ctx, rel, splitLines(board.text.join(" ")), new Set());
}

/** 6 章で最初の版 ○ の行は、その画面の phone / pc のボードに要件の札 (.req[data-req]) を置く。HTML が読めたボードだけで見る。 */
function checkReqTags(ctx) {
  if (ctx.features === null) return;
  for (const [fid, { screens, first, idx }] of ctx.features) {
    if (!first) continue;
    const boards = ctx.deviceBoards.filter(([boardScreens]) => screens.some((s) => boardScreens.includes(s)));
    if (boards.length && !boards.some(([, reqs]) => reqs.includes(fid))) {
      ctx.report.warn("REQ-TAG-MISSING", "要件定義.md", ln(idx),
        `${fid} の要件の札 (.req data-req="${fid}") が ${boards.map(([, , rel]) => rel).join(" / ")} のどれにもありません`);
    }
  }
}

// ── 言い換え ───────────────────────────────

/**
 * 言い換え表の語を本文から探す正規表現 (g は付けない)。
 * - 英数字の語は前後が英数字でないときだけ、大文字小文字を区別しない (「UI」を「GUI」に当てない)
 * - カタカナ語は前後がカタカナでないときだけ (「ログ」を「ログイン」や「カタログ」に当てない)。
 *   後ろの長音だけは許す (「マスタ」で「マスター」も拾う)
 */
export function termPattern(term) {
  // eslint-disable-next-line no-control-regex
  if (/^[\x00-\x7f]+$/.test(term)) return new RegExp(`(?<![A-Za-z0-9])${escapeRegExp(term)}(?![A-Za-z0-9])`, "i");
  if (/^[ァ-ヺー・]+$/.test(term)) return new RegExp(`(?<![ァ-ヺー])${escapeRegExp(term)}ー?(?![ァ-ヺー])`);
  return new RegExp(escapeRegExp(term));
}

const termCounters = new Map();

function countTerm(term, line) {
  if (!termCounters.has(term)) {
    const p = termPattern(term);
    termCounters.set(term, new RegExp(p.source, `${p.flags}g`));
  }
  return (line.match(termCounters.get(term)) || []).length;
}

function isDefined(ctx, term) {
  const lowered = term.toLowerCase();
  for (const raw of ctx.definedTerms) {
    const tokens = new Set(raw.split(/[（()）/／・、,，\s]+/).filter(Boolean).map((t) => t.toLowerCase()));
    if (raw.toLowerCase() === lowered || tokens.has(lowered)) return true;
  }
  return false;
}

function checkPlainText(ctx, name, lines, skip) {
  /** 語 → [最初の行, 回数, 表の項目] */
  const hits = new Map();
  lines.forEach((raw, idx) => {
    if (skip.has(idx)) return;
    const line = raw.replace(/`[^`]*`/g, " ").replace(/素材\s*[:：]\s*[^\s|、,]+/g, " ");
    for (const entry of ctx.terms) {
      const term = show(entry?.term);
      if (!term || (hits.has(term) && hits.get(term)[0] < idx)) {
        if (hits.has(term)) {
          const count = countTerm(term, line);
          if (count) {
            const [first, total, e] = hits.get(term);
            hits.set(term, [first, total + count, e]);
          }
        }
        continue;
      }
      const count = countTerm(term, line);
      if (count) hits.set(term, [idx, count, entry]);
    }
  });
  for (const [term, [idx, count, entry]] of hits) {
    if (isDefined(ctx, term)) continue;
    const level = entry.level === "error" ? "error" : "warn";
    ctx.report.add(level, "PLAIN-TERM", name, name.endsWith(".md") ? ln(idx) : null,
      `「${term}」が ${count} 回出ています。言い換える (例: ${show(entry.say)}) か、要件定義.md の「## 8. 用語」で説明します`);
  }
}

function checkPlainLanguage(ctx) {
  if (!ctx.terms.length) return;
  for (const name of ["要件定義.md", "仕様書.md"]) {
    const doc = ctx.docs.get(name);
    if (doc) checkPlainText(ctx, name, doc.lines, ctx.termRows.get(name) || new Set());
  }
}

// ── 全体 ───────────────────────────────

/** briefing.json を読む。UTF-8 として正しくない・JSON でない・オブジェクトでないときは理由を返す。 */
function readBriefing(file) {
  try {
    const text = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(readFileSync(file));
    const data = JSON.parse(text);
    if (!isPlainObject(data)) return [null, "オブジェクトではありません"];
    return [data, null];
  } catch (error) {
    return [null, error.message];
  }
}

export function validate(base, stage) {
  const ctx = new Context(base, stage);
  const [briefing, problem] = readBriefing(path.join(base, "briefing.json"));
  if (problem !== null) ctx.report.err("BRIEFING-JSON", "briefing.json", null, `briefing.json が読めません: ${problem}`);
  ctx.briefing = briefing || {};
  if (Object.keys(ctx.briefing).length) {
    if (ctx.briefing.schema !== "briefing-v1") ctx.report.err("BRIEFING-SCHEMA", "briefing.json", null, "schema は briefing-v1 にします");
    if (!show(ctx.briefing.title).trim()) ctx.report.err("BRIEFING-TITLE", "briefing.json", null, "title が空です");
    checkBriefingShape(ctx);
  }

  checkHearing(ctx);
  if (ctx.at("requirements")) {
    checkRequirements(ctx);
    checkChanges(ctx);
  }
  if (ctx.at("spec")) checkSpec(ctx);
  if (ctx.at("requirements")) checkPlainLanguage(ctx);
  if (ctx.at("pages")) checkPages(ctx);
  if (ctx.at("all")) checkMaterialsUsed(ctx);
  const { errors, warnings } = ctx.report;
  return {
    schema: "briefing-docs-check-v1",
    status: errors.length ? "ng" : "ok",
    stage,
    dir: toPosix(realPath(base)),
    version: ctx.version,
    summary: { errors: errors.length, warnings: warnings.length },
    errors,
    warnings,
    counts: ctx.counts,
  };
}

export async function main(argv) {
  const { options } = parseOptions(argv, { dir: "string", stage: "string", quiet: "boolean" });
  if (!options.dir) throw new UsageError("--dir を指定してください (打ち合わせ資料フォルダ)");
  const stage = options.stage ?? "all";
  if (!STAGES.includes(stage)) throw new UsageError(`--stage は ${STAGES.join(" / ")} のどれかです: ${stage}`);
  const base = expandHome(options.dir);
  if (!isDir(base)) throw new UsageError(`フォルダがありません: ${base}`);
  if (!isFile(path.join(base, "briefing.json"))) {
    throw new UsageError(`briefing.json がありません (先に build-briefing-scaffold.mjs init): ${base}`);
  }
  const result = validate(base, stage);
  writeJson(path.join(base, "_check", "docs.json"), result);
  const lines = [];
  for (const item of result.errors) lines.push(`error ${item.code} ${item.line ? `${item.file}:${item.line}` : item.file} ${item.message}`);
  for (const item of result.warnings) lines.push(`warn  ${item.code} ${item.line ? `${item.file}:${item.line}` : item.file} ${item.message}`);
  if (lines.length) process.stderr.write(`${lines.join("\n")}\n`);
  const quietLine = `docs(${stage}): ${result.status} error ${result.summary.errors} 件 / warn ${result.summary.warnings} 件`;
  emitResult(result, options.quiet ? quietLine : null);
  return result.errors.length ? EXIT.FOUND : EXIT.OK;
}

if (isEntryPoint(import.meta.url)) {
  runCli(main, USAGE);
}
