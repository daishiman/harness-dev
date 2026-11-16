#!/usr/bin/env node
/**
 * lint-thumbnail-prompt.js - サムネイル生成プロンプトの機械検証（決定論的処理）
 *
 * x-longpost-design-thumbnail-prompt.md に従って LLM が書いた x-thumb.prompt.txt /
 * note-thumb.prompt.txt を、画像生成に**入る前**に検査する。画像生成は課金される操作
 * なので、「守れているかを出力で確かめる」のではなく「守らせる指示が書けているか」を
 * 先に止める。thumbnail-style-canon.md §6 の3層のうち第3層にあたる。
 *
 * 検査する制約（thumbnail-style-canon.md / x-longpost-design-thumbnail-prompt.md §4）:
 *   TL-01  5ブロックが STYLE / LAYOUT / CONTENT / TYPOGRAPHY / NEGATIVE の順に揃う
 *   TL-02  STYLE がサムネイル palette の全色（背景・文字・アクセント2色）を hex で書いている
 *   TL-03  図解 palette の混入がない（純白背景・赤アクセントの指定が残っていない）
 *   TL-04  NEGATIVE が人物の描画を禁じている（TS-03）
 *   TL-05  NEGATIVE が §3 の情報商材的意匠を分類ごとに禁じている（TS-09）
 *   TL-06  NEGATIVE が透過背景とアルファチャンネルを禁じている（TS-02）
 *   TL-07  LAYOUT が四辺 5% 余白と枠線禁止を書いている（TS-08）
 *   TL-08  LAYOUT の canvas 比率が kind と一致する（TS-01）
 *   TL-09  引用符で囲まれた日本語が2本以内で、各字数上限を満たす（TS-06）
 *   TL-10  絵文字・禁止語を含まない（TS-10。判定器は check-no-emoji.js と共通）
 *
 * 使用例:
 *   node scripts/lint-thumbnail-prompt.js --image-dir /path/to/images
 *   node scripts/lint-thumbnail-prompt.js --image-dir /path/to/images --only x-thumb
 *
 * 終了コード: 0 = 全件PASS / 1 = 1件以上の違反 / 2 = 引数・入出力エラー
 */

"use strict";

const fs = require("fs");
const path = require("path");
const VISUAL_SPEC = require("../skills/run-x-visual-generate/references/visual-spec.json");
const { findEmoji } = require("./lib/text-rules.js");

const BLOCKS = ["STYLE", "LAYOUT", "CONTENT", "TYPOGRAPHY", "NEGATIVE"];
const THUMB_KINDS = Object.keys(VISUAL_SPEC.kinds).filter(
  (kind) => VISUAL_SPEC.kinds[kind].palette === "thumbnail"
);

// thumbnail-style-canon.md §3 の6分類。分類ごとに1語でも当たれば「その分類を禁じている」
// とみなす。完全一致の文言を強制すると、言い回しの改善が違反になってしまうため。
const NEGATIVE_TERM_GROUPS = [
  { id: "文字の装飾", terms: ["outlined text", "text outline", "drop shadow", "3d text", "gradient text"] },
  { id: "配色", terms: ["neon", "saturated", "high saturation", "vivid primary", "glowing"] },
  { id: "記号", terms: ["starburst", "star burst", "explosion", "speed lines", "sunburst", "lightning bolt", "crown"] },
  { id: "数字の煽り", terms: ["large number", "huge number", "circled number", "price"] },
  { id: "版面", terms: ["diagonal band", "diagonal stripe", "decorative rule", "cluttered"] },
  { id: "写実", terms: ["photographic", "photo-realistic", "photorealistic"] },
];

// TS-03（人物禁止）と TS-02（不透明背景）は分類ではなく単一の要件なので別枠で見る。
const HUMAN_TERMS = ["no human", "no person", "no people", "no human figures", "no silhouette"];
const OPAQUE_TERMS = ["transparent background", "alpha channel"];

// 図解 palette の混入。サムネイルは図解の STYLE を継承しない（TP-C02 の廃止）。
const DIAGRAM_LEAK_TERMS = ["pure white background", "#ffffff", "red ✕", "single red"];

// palette のロール名の日本語表記。visual-spec.json の palettes.* が持つ hex 値の
// キーだけを対象にし、"...Use" のような説明文フィールドは除外する。
const PALETTE_ROLE_LABELS = {
  background: "背景",
  text: "文字",
  accent: "アクセント（構造）",
  label: "アクセント（帯）",
};

/**
 * palette が実際に持つ色ロールを列挙する。
 *
 * ロール名をここへ直接並べず palette 側から導くのは、配色が増えたときに
 * lint が黙って検査対象から漏らすのを防ぐためである。未知のキーが来たら
 * 日本語名が無くてもキー名で報告し、「知らないから見なかった」を作らない。
 */
function paletteRoles(palette) {
  return Object.keys(palette)
    .filter((key) => typeof palette[key] === "string" && palette[key].startsWith("#"))
    .map((key) => ({ key, hex: palette[key], label: PALETTE_ROLE_LABELS[key] || key }));
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--image-dir") args.imageDir = argv[++i];
    else if (argv[i] === "--structure") args.structure = argv[++i];
    else if (argv[i] === "--only") args.only = argv[++i];
  }
  return args;
}

function charLen(s) {
  return [...String(s)].length;
}

/** ブロック名から次のブロック名までを切り出す。見つからないブロックは null。 */
function splitBlocks(text) {
  const found = BLOCKS.map((name) => ({ name, index: text.indexOf(`${name}:`) }));
  const present = found.filter((b) => b.index >= 0).sort((a, b) => a.index - b.index);
  const blocks = {};
  present.forEach((b, i) => {
    const end = i + 1 < present.length ? present[i + 1].index : text.length;
    blocks[b.name] = text.slice(b.index, end);
  });
  return { blocks, order: present.map((b) => b.name) };
}

/** 画像へ描かれる日本語は「引用符で囲まれた行」だけである（TS-11）。 */
function extractQuotedJapanese(contentBlock) {
  const hits = String(contentBlock).match(/"([^"]*)"/g) || [];
  return hits
    .map((h) => h.slice(1, -1))
    .filter((s) => /[぀-ヿ一-鿿]/.test(s));
}

function lintOne(kind, promptPath, structure) {
  const violations = [];
  const push = (rule, detail) => violations.push({ kind, rule, detail });

  if (!fs.existsSync(promptPath)) {
    return [{ kind, rule: "TL-01", detail: `${promptPath} がありません` }];
  }
  const text = fs.readFileSync(promptPath, "utf8");
  const lower = text.toLowerCase();
  const spec = VISUAL_SPEC.kinds[kind];
  const palette = VISUAL_SPEC.palettes[spec.palette];

  const { blocks, order } = splitBlocks(text);
  const missing = BLOCKS.filter((b) => !blocks[b]);
  if (missing.length > 0) {
    push("TL-01", `ブロックが欠けている: ${missing.join(", ")}`);
  }
  if (missing.length === 0 && order.join(",") !== BLOCKS.join(",")) {
    push("TL-01", `ブロックの順序が違う（実際 ${order.join(" -> ")}）`);
  }

  const style = blocks.STYLE || "";
  // 検査するロールを palette から導く。ロール名をここへ並べると、規範に色が
  // 増えたときに検査だけが取り残され、「規範にはあるがプロンプトには書かれて
  // いない色」が課金前の関門を素通りする。
  const styleLower = style.toLowerCase();
  for (const role of paletteRoles(palette)) {
    if (!styleLower.includes(role.hex.toLowerCase())) {
      push("TL-02", `STYLE に${role.label}色 ${role.hex} の hex 指定がない。色名だけでは生成のたびに色味が動く`);
    }
  }

  for (const leak of DIAGRAM_LEAK_TERMS) {
    if (lower.includes(leak)) {
      push("TL-03", `図解 palette の指定が混入している: "${leak}"。サムネイルは図解の STYLE を継承しない`);
    }
  }

  const negative = (blocks.NEGATIVE || "").toLowerCase();
  if (!HUMAN_TERMS.some((t) => negative.includes(t))) {
    push("TL-04", `NEGATIVE に人物の描画禁止がない（TS-03）。想定語のいずれか: ${HUMAN_TERMS.join(" / ")}`);
  }
  for (const group of NEGATIVE_TERM_GROUPS) {
    if (!group.terms.some((t) => negative.includes(t))) {
      push("TL-05", `NEGATIVE に「${group.id}」の禁止がない（TS-09）。想定語のいずれか: ${group.terms.join(" / ")}`);
    }
  }
  for (const t of OPAQUE_TERMS) {
    if (!negative.includes(t)) {
      push("TL-06", `NEGATIVE に "${t}" の禁止がない（TS-02）。透過背景はダークテーマで全文が消える`);
    }
  }

  const layout = (blocks.LAYOUT || "").toLowerCase();
  // 単なる "5%" の部分一致では、ゾーン幅の "65% width" / "35% width" にも当たってしまう。
  // 直前が数字でない 5% と、margin の語の両方を要求する。
  if (!/(?<![0-9])5%/.test(layout) || !layout.includes("margin")) {
    push("TL-07", "LAYOUT に四辺 5% 余白の指示がない（TS-08）");
  }
  if (!layout.includes("border") && !layout.includes("frame")) {
    push("TL-07", "LAYOUT に枠線で囲まない指示がない（TS-08）");
  }
  if (!layout.includes(spec.ratio.label.toLowerCase())) {
    push("TL-08", `LAYOUT の canvas 比率が ${spec.ratio.label} でない（TS-01）`);
  }

  const quoted = extractQuotedJapanese(blocks.CONTENT || "");
  if (quoted.length === 0) {
    push("TL-09", "CONTENT に引用符で囲まれた日本語がない。画像内テキストの正本が定まらない");
  } else if (quoted.length > 2) {
    push("TL-09", `画像へ描く日本語が ${quoted.length} 本ある。主文1本 + 補助句1本まで（TS-06）`);
  }
  const subMax = kind === "x-thumb" ? 16 : 20;
  quoted.forEach((s, i) => {
    const n = charLen(s);
    const max = i === 0 ? 24 : subMax;
    if (i === 0 && n < 6) {
      push("TL-09", `主文が ${n} 字（下限 6 字。TS-06）: "${s}"`);
    }
    if (n > max) {
      push("TL-09", `引用文字列 ${i + 1} 本目が ${n} 字（上限 ${max} 字）: "${s}"`);
    }
  });
  const total = quoted.reduce((sum, s) => sum + charLen(s), 0);
  if (total > 44) {
    push("TL-09", `画像内の総字数が ${total} 字（上限 44 字。TS-06）`);
  }

  const structureKey = kind === "x-thumb" ? "x" : "note";
  const expectedThumb = structure.thumbnails && structure.thumbnails[structureKey];
  if (!expectedThumb || typeof expectedThumb.main !== "string") {
    push("TL-11", `visual-structure.json の thumbnails.${structureKey} が不正`);
  } else {
    const expected = [expectedThumb.main];
    if (expectedThumb.sub !== null && expectedThumb.sub !== undefined) expected.push(expectedThumb.sub);
    if (JSON.stringify(quoted) !== JSON.stringify(expected)) {
      push(
        "TL-11",
        `引用文が visual-structure.json と一致しない（期待 ${JSON.stringify(expected)} / 実際 ${JSON.stringify(quoted)}）`
      );
    }
  }

  const emoji = findEmoji(text);
  if (emoji.length > 0) {
    push("TL-10", `絵文字を含む: ${emoji.join(" ")}`);
  }
  for (const word of VISUAL_SPEC.textRules.forbiddenWords) {
    if (text.includes(word)) {
      push("TL-10", `禁止語「${word}」を含む（TS-10）`);
    }
  }

  return violations;
}

function main() {
  const args = parseArgs(process.argv);
  if (!args.imageDir || !args.structure) {
    console.error(JSON.stringify({ error: "--image-dir <dir> と --structure <visual-structure.json> を指定してください" }));
    process.exit(2);
  }
  if (!fs.existsSync(args.imageDir)) {
    console.error(JSON.stringify({ error: `画像ディレクトリが見つかりません: ${args.imageDir}` }));
    process.exit(2);
  }
  if (!fs.existsSync(args.structure)) {
    console.error(JSON.stringify({ error: `構造データが見つかりません: ${args.structure}` }));
    process.exit(2);
  }
  let structure;
  try {
    structure = JSON.parse(fs.readFileSync(args.structure, "utf8"));
  } catch (err) {
    console.error(JSON.stringify({ error: `構造データを解析できません: ${err.message}` }));
    process.exit(2);
  }

  const kinds = args.only
    ? String(args.only).split(",").map((s) => s.trim()).filter(Boolean)
    : THUMB_KINDS;
  for (const kind of kinds) {
    if (!THUMB_KINDS.includes(kind)) {
      console.error(JSON.stringify({ error: `サムネイル種別ではありません: ${kind}（有効: ${THUMB_KINDS.join(", ")}）` }));
      process.exit(2);
    }
  }

  const violations = [];
  const checked = [];
  for (const kind of kinds) {
    const promptPath = path.join(path.resolve(args.imageDir), `${kind}.prompt.txt`);
    checked.push(promptPath);
    violations.push(...lintOne(kind, promptPath, structure));
  }


  if (kinds.includes("x-thumb") && kinds.includes("note-thumb")) {
    const shared = ["STYLE", "TYPOGRAPHY", "NEGATIVE"];
    const xText = fs.existsSync(path.join(path.resolve(args.imageDir), "x-thumb.prompt.txt"))
      ? fs.readFileSync(path.join(path.resolve(args.imageDir), "x-thumb.prompt.txt"), "utf8") : "";
    const noteText = fs.existsSync(path.join(path.resolve(args.imageDir), "note-thumb.prompt.txt"))
      ? fs.readFileSync(path.join(path.resolve(args.imageDir), "note-thumb.prompt.txt"), "utf8") : "";
    const xBlocks = splitBlocks(xText).blocks;
    const noteBlocks = splitBlocks(noteText).blocks;
    for (const block of shared) {
      if (xBlocks[block] && noteBlocks[block] && xBlocks[block] !== noteBlocks[block]) {
        violations.push({
          kind: "x-thumb,note-thumb",
          rule: "TL-12",
          detail: `${block} は2枚で完全に同一である必要がある`,
        });
      }
    }
  }

  console.log(JSON.stringify({
    ok: violations.length === 0,
    checked,
    violationCount: violations.length,
    violations,
    note: "本検査はプロンプト文の充足だけを見る。描かれた絵が規範どおりかは thumbnail-style-canon.md §5 に従って目視する",
  }, null, 2));
  process.exit(violations.length === 0 ? 0 : 1);
}

main();
