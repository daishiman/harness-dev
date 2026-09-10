#!/usr/bin/env node
/**
 * build-visual-prompts.js - 図解構造データの検証と meta 生成（決定論的処理）
 *
 * x-longpost-analyze-visual-structure.md が出力した visual-structure.json を
 * スキーマと字数制約で検証し、3種（diagram / x-thumb / note-thumb）の meta.json を
 * 出力ディレクトリへ書き出す。プロンプト本文（.prompt.txt）はLLMが
 * x-longpost-design-{diagram,thumbnail}-prompt.md に従って書くため、本スクリプトは
 * 生成しない。ここで担うのは「LLMが守ったつもりの制約を機械で確かめる」ことだけである。
 *
 * 検証する制約（prompts/x-longpost-analyze-visual-structure.md §4）:
 *   VA-C02  zones はちょうど3要素
 *   VA-C03  primaryType は T1-T4。nestedType は T1-T4 または null
 *   VA-C04  label 6字以内 / conclusion 各行 20字以内 / headline 20-30字 / main 24字以内
 *   VA-C05  「僕」「私」「コメント」「キャッチコピー」をどのフィールドにも含めない
 *   VA-C06  絵文字を含めない（check-no-emoji.js と同一の判定器を使う）
 *   VA-C08  visual-spec.json で明示された記号以外の Unicode symbol を含めない
 *
 * 使用例:
 *   node scripts/build-visual-prompts.js --structure /path/to/visual-structure.json --out-dir /path/to/images
 *   node scripts/build-visual-prompts.js --structure ... --out-dir ... --only diagram
 *
 * 終了コード: 0 = 検証PASS・meta出力済み / 1 = 制約違反 / 2 = 引数・入出力エラー
 */

const fs = require("fs");
const path = require("path");
const VISUAL_SPEC = require("../skills/run-x-visual-generate/references/visual-spec.json");
const { validateVisualTextLeaves } = require("./lib/text-rules.js");

// 生成・納品寸法と比率の唯一の機械可読正本。
const KINDS = VISUAL_SPEC.kinds;
const STANDARD_KINDS = Object.keys(KINDS).filter(
  (kind) => KINDS[kind].palette === "thumbnail"
);
const VALID_TYPES = ["T1", "T2", "T3", "T4"];

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--structure") args.structure = argv[++i];
    else if (argv[i] === "--out-dir") args.outDir = argv[++i];
    else if (argv[i] === "--only") args.only = argv[++i];
  }
  return args;
}

// 日本語の字数はコードポイントで数える（サロゲートペアを2字と数えない）。
function charLen(s) {
  return [...String(s)].length;
}

function pushViolation(violations, field, rule, detail) {
  violations.push({ field, rule, detail });
}

function validate(structure) {
  const violations = [];

  if (typeof structure.title !== "string" || structure.title.length === 0) {
    pushViolation(violations, "title", "schema", "title は非空文字列である必要がある");
  }

  const headline = structure.headline;
  if (typeof headline !== "string") {
    pushViolation(violations, "headline", "schema", "headline は文字列である必要がある");
  } else {
    const n = charLen(headline);
    if (n < 20 || n > 30) {
      pushViolation(violations, "headline", "VA-C04", `20〜30字である必要がある（実際 ${n} 字）`);
    }
  }

  if (!VALID_TYPES.includes(structure.primaryType)) {
    pushViolation(violations, "primaryType", "VA-C03", `T1〜T4 のいずれかである必要がある（実際 ${JSON.stringify(structure.primaryType)}）`);
  }
  if (structure.nestedType !== null && !VALID_TYPES.includes(structure.nestedType)) {
    pushViolation(violations, "nestedType", "VA-C03", `T1〜T4 または null である必要がある（実際 ${JSON.stringify(structure.nestedType)}）`);
  }
  if (structure.nestedType !== null && structure.nestedType === structure.primaryType) {
    pushViolation(violations, "nestedType", "VA-C03", "nestedType が primaryType と同一。従型を入れないなら null にする");
  }

  const zones = structure.zones;
  if (!Array.isArray(zones) || zones.length !== 3) {
    pushViolation(violations, "zones", "VA-C02", `ちょうど3要素である必要がある（実際 ${Array.isArray(zones) ? zones.length : typeof zones}）`);
  } else {
    zones.forEach((zone, zi) => {
      const at = `zones[${zi}]`;
      if (typeof zone.heading !== "string" || charLen(zone.heading) < 6 || charLen(zone.heading) > 14) {
        pushViolation(violations, `${at}.heading`, "VA-C04", `6〜14字である必要がある（実際 ${typeof zone.heading === "string" ? charLen(zone.heading) : typeof zone.heading}）`);
      }

      if (!Array.isArray(zone.chain) || zone.chain.length < 2 || zone.chain.length > 5) {
        pushViolation(violations, `${at}.chain`, "schema", `2〜5要素である必要がある（実際 ${Array.isArray(zone.chain) ? zone.chain.length : typeof zone.chain}）`);
      } else {
        zone.chain.forEach((link, li) => {
          const lat = `${at}.chain[${li}]`;
          if (typeof link.icon !== "string" || link.icon.length === 0) {
            pushViolation(violations, `${lat}.icon`, "VA-C07", "icon は非空の概念記述である必要がある");
          }
          if (typeof link.label !== "string") {
            pushViolation(violations, `${lat}.label`, "schema", "label は文字列である必要がある（不要なら空文字）");
          } else {
            if (charLen(link.label) > 6) {
              pushViolation(violations, `${lat}.label`, "VA-C04", `6字以内である必要がある（実際 ${charLen(link.label)} 字）`);
            }
          }
        });
      }

      if (!Array.isArray(zone.conclusion) || zone.conclusion.length !== 2) {
        pushViolation(violations, `${at}.conclusion`, "schema", `ちょうど2要素である必要がある（実際 ${Array.isArray(zone.conclusion) ? zone.conclusion.length : typeof zone.conclusion}）`);
      } else {
        zone.conclusion.forEach((line, ci) => {
          const cat = `${at}.conclusion[${ci}]`;
          if (typeof line !== "string") {
            pushViolation(violations, cat, "schema", "文字列である必要がある");
            return;
          }
          if (charLen(line) > 20) {
            pushViolation(violations, cat, "VA-C04", `20字以内である必要がある（実際 ${charLen(line)} 字）`);
          }
        });
      }
    });
  }

  const thumbs = structure.thumbnails;
  if (!thumbs || typeof thumbs !== "object") {
    pushViolation(violations, "thumbnails", "schema", "thumbnails オブジェクトが必要");
  } else {
    for (const key of ["x", "note"]) {
      const t = thumbs[key];
      const at = `thumbnails.${key}`;
      if (!t || typeof t !== "object") {
        pushViolation(violations, at, "schema", "オブジェクトが必要");
        continue;
      }
      if (typeof t.main !== "string" || charLen(t.main) < 6 || charLen(t.main) > 24) {
        pushViolation(violations, `${at}.main`, "VA-C04", `6〜24字である必要がある（実際 ${typeof t.main === "string" ? charLen(t.main) : typeof t.main}）`);
      }
      if (t.sub !== null && t.sub !== undefined) {
        const subMax = key === "x" ? 16 : 20;
        if (typeof t.sub !== "string" || charLen(t.sub) > subMax) {
          pushViolation(violations, `${at}.sub`, "VA-C04", `${subMax}字以内または null である必要がある`);
        }
      }
      if (!Array.isArray(t.icons) || t.icons.length < 1 || t.icons.length > 3) {
        pushViolation(violations, `${at}.icons`, "TP-C04", `1〜3要素である必要がある（実際 ${Array.isArray(t.icons) ? t.icons.length : typeof t.icons}）`);
      } else {
      }
    }
  }

  // title や将来追加される field を含む全文字列 leaf に同じ横断規則を適用する。
  violations.push(...validateVisualTextLeaves(structure, VISUAL_SPEC.textRules));
  return violations;
}

function buildMeta(kind, structure) {
  const spec = KINDS[kind];
  const generationSize = `${spec.generation.width}x${spec.generation.height}`;
  const deliverySize = `${spec.delivery.width}x${spec.delivery.height}`;
  return {
    kind,
    slug: kind,
    title: structure.title,
    generation: { size: generationSize, ratio: spec.ratio.label },
    deliverSize: deliverySize,
    // source は generate-images-codex.js が実生成後に実体名で上書きする。
    // 未生成の段階で backend 名を書かない（生成していない出自を記録しないため）。
    source: null,
    seed: null,
    promptFile: `${kind}.prompt.txt`,
    structureRef: "visual-structure.json",
  };
}

function main() {
  const args = parseArgs(process.argv);
  if (!args.structure || !args.outDir) {
    console.error(JSON.stringify({ error: "--structure <path> と --out-dir <dir> を指定してください" }));
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
    console.error(JSON.stringify({ error: `JSON として解析できません: ${err.message}` }));
    process.exit(2);
  }

  const kinds = args.only
    ? String(args.only).split(",").map((s) => s.trim()).filter(Boolean)
    : STANDARD_KINDS;
  for (const kind of kinds) {
    if (!KINDS[kind]) {
      console.error(JSON.stringify({ error: `未知の種別: ${kind}（有効: ${Object.keys(KINDS).join(", ")}）` }));
      process.exit(2);
    }
  }

  const violations = validate(structure);
  if (violations.length > 0) {
    console.log(JSON.stringify({ ok: false, violationCount: violations.length, violations }, null, 2));
    process.exit(1);
  }

  try {
    fs.mkdirSync(args.outDir, { recursive: true });
  } catch (err) {
    console.error(JSON.stringify({ error: `出力ディレクトリを作成できません: ${err.message}` }));
    process.exit(2);
  }

  const written = [];
  for (const kind of kinds) {
    const metaPath = path.join(args.outDir, `${kind}.meta.json`);
    fs.writeFileSync(metaPath, `${JSON.stringify(buildMeta(kind, structure), null, 2)}\n`, "utf8");
    written.push(metaPath);
  }

  console.log(JSON.stringify({ ok: true, violationCount: 0, written }, null, 2));
  process.exit(0);
}

main();
