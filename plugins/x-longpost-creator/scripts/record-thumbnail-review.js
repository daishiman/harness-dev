#!/usr/bin/env node
/**
 * record-thumbnail-review.js - サムネイルの目視確認を画像hashへ結びつける。
 *
 * Claude Code の Read または Codex の view_image で指定フォルダの同じ絶対パスを
 * 開いた後に実行する。5項目がすべて PASS の場合だけ {kind}.review.json を書く。
 * embed-visual-paths.js は現在のPNG hashとreceiptが一致しない限り公開しない。
 *
 * 終了コード: 0=receipt記録 / 1=確認NG / 2=引数・入出力エラー
 */

"use strict";

const crypto = require("crypto");
const childProcess = require("child_process");
const fs = require("fs");
const path = require("path");

const THUMB_KINDS = new Set(["x-thumb", "note-thumb"]);
const PRESENTATION_TOOLS = { "claude-code": "Read", codex: "view_image" };
const CHECK_ARGS = {
  "--no-people": "noPeople",
  "--no-info-product": "noInfoProduct",
  "--text-readable-correct": "textReadableCorrect",
  "--gentle-off-white": "gentleOffWhite",
  "--impact": "impact",
};

function parseArgs(argv) {
  const args = { checks: {} };
  for (let i = 2; i < argv.length; i++) {
    const token = argv[i];
    if (token === "--image-dir") args.imageDir = argv[++i];
    else if (token === "--kind") args.kind = argv[++i];
    else if (token === "--host") args.host = argv[++i];
    else if (token === "--out") args.out = argv[++i];
    else if (CHECK_ARGS[token]) args.checks[CHECK_ARGS[token]] = argv[++i];
  }
  return args;
}

function sha256File(filePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function validateStrict(imageDir, kind) {
  const validator = path.join(__dirname, "validate-visual-assets.js");
  const proc = childProcess.spawnSync(
    process.execPath,
    [validator, "--image-dir", imageDir, "--only", kind, "--strict"],
    { encoding: "utf8" }
  );
  let payload = null;
  try {
    payload = JSON.parse(proc.stdout || "null");
  } catch {
    return { ok: false, detail: proc.stderr || proc.stdout || "validator output is not JSON" };
  }
  const result = payload && Array.isArray(payload.results) ? payload.results[0] : null;
  if (proc.status !== 0 || payload.ok !== true || payload.strict !== true || !result || result.ok !== true) {
    return { ok: false, detail: payload };
  }
  return {
    ok: true,
    receipt: {
      strict: true,
      kind,
      actual: result.actual,
      expected: result.expected,
    },
  };
}

function main() {
  const args = parseArgs(process.argv);
  if (!args.imageDir || !THUMB_KINDS.has(args.kind) || !PRESENTATION_TOOLS[args.host]) {
    console.error(JSON.stringify({
      error: "--image-dir <dir>、--kind x-thumb|note-thumb、--host claude-code|codex を指定してください",
    }));
    process.exit(2);
  }

  const imageDir = path.resolve(args.imageDir);
  const imagePath = path.join(imageDir, `${args.kind}.png`);
  if (!fs.existsSync(imagePath)) {
    console.error(JSON.stringify({ error: `画像が見つかりません: ${imagePath}` }));
    process.exit(2);
  }

  const strictValidation = validateStrict(imageDir, args.kind);
  if (!strictValidation.ok) {
    console.log(JSON.stringify({
      ok: false,
      reason: "strict-visual-validation-failed",
      validation: strictValidation.detail,
    }, null, 2));
    process.exit(1);
  }

  const missing = Object.values(CHECK_ARGS).filter((key) => !(key in args.checks));
  const failed = Object.entries(args.checks)
    .filter(([, value]) => value !== "PASS")
    .map(([key, value]) => ({ key, value }));
  if (missing.length > 0 || failed.length > 0) {
    console.log(JSON.stringify({ ok: false, missing, failed }, null, 2));
    process.exit(1);
  }

  const receipt = {
    version: 1,
    kind: args.kind,
    ok: true,
    imagePath,
    imageSha256: sha256File(imagePath),
    presentation: { host: args.host, tool: PRESENTATION_TOOLS[args.host] },
    validation: strictValidation.receipt,
    checks: args.checks,
  };
  const outPath = path.resolve(args.out || path.join(imageDir, `${args.kind}.review.json`));
  fs.writeFileSync(outPath, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ ok: true, receipt: outPath, review: receipt }, null, 2));
  process.exit(0);
}

main();
