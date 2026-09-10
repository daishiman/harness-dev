#!/usr/bin/env node
/**
 * embed-visual-paths.js - 生成画像を投稿ファイルの図解・サムネイル欄へ差し込む（決定論的処理）
 *
 * assets/output-template.md は `図解` / `Xサムネイル（5:2）` / `noteサムネイル（1280×670px）`
 * という3つのラベル行と、その直後の空行だけを持つ。本スクリプトはその空行へ画像への
 * 参照を書き込む。ラベル行は**行全体の完全一致**で探すため、`# Next Action` 配下の
 * `- [ ] 図解` を誤って書き換えることはない。
 *
 * 冪等である。既に参照が入っている欄は置き換えるので、再生成後に何度実行してもよい。
 *
 * 記法は既定で Obsidian の埋め込み。--attachment-dir を指定すると、実運用投稿と
 * 同じく投稿 basename を含む一意名で画像を指定添付先へ公開し、その basename を
 * `![[...]]` で参照する。vault 外では --markdown で絶対パスの Markdown 記法にする。
 *
 * 使用例:
 *   node scripts/embed-visual-paths.js --file /path/to/post.md --image-dir /path/to/work --attachment-dir /vault/02_Configs/Extra
 *   node scripts/embed-visual-paths.js --file /path/to/post.md --image-dir /path/to/images --markdown
 *
 * 終了コード: 0 = 差し込み完了 / 1 = 欄または画像が見つからない / 2 = 引数・入出力エラー
 */

const fs = require("fs");
const childProcess = require("child_process");
const crypto = require("crypto");
const path = require("path");

// ラベル行と画像種別の対応。ラベル文字列は assets/output-template.md と一字一句一致させる
// （テンプレート側を変えたらここも変える。片方だけ変えると差し込みが黙って空振りする）。
const SLOTS = [
  { label: "図解", kind: "diagram", alt: "図解" },
  { label: "Xサムネイル（5:2）", kind: "x-thumb", alt: "Xサムネイル" },
  { label: "noteサムネイル（1280×670px）", kind: "note-thumb", alt: "noteサムネイル" },
];

// 既存の差し込みを判定する。Obsidian 記法と Markdown 記法の両方を拾う。
const EMBED_RE = /^(!\[\[.*\]\]|!\[.*\]\(.*\))$/;

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--file") args.file = argv[++i];
    else if (argv[i] === "--image-dir") args.imageDir = argv[++i];
    else if (argv[i] === "--attachment-dir") args.attachmentDir = argv[++i];
    else if (argv[i] === "--only") args.only = argv[++i];
    else if (argv[i] === "--markdown") args.markdown = true;
  }
  return args;
}

function sha256File(filePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function strictVisualProblem(imageDir, artifact) {
  if (!artifact.slot.kind.endsWith("-thumb") || !fs.existsSync(artifact.source)) return null;
  const validator = path.join(__dirname, "validate-visual-assets.js");
  const proc = childProcess.spawnSync(
    process.execPath,
    [validator, "--image-dir", imageDir, "--only", artifact.slot.kind, "--strict"],
    { encoding: "utf8" }
  );
  let payload = null;
  try {
    payload = JSON.parse(proc.stdout || "null");
  } catch {
    payload = { detail: proc.stderr || proc.stdout || "validator output is not JSON" };
  }
  if (proc.status === 0 && payload && payload.ok === true && payload.strict === true) return null;
  return {
    kind: artifact.slot.kind,
    reason: "strict-visual-validation-failed",
    detail: payload,
  };
}

function reviewProblem(imageDir, artifact) {
  if (!artifact.slot.kind.endsWith("-thumb") || !fs.existsSync(artifact.source)) return null;
  const receiptPath = path.join(imageDir, `${artifact.slot.kind}.review.json`);
  if (!fs.existsSync(receiptPath)) {
    return {
      kind: artifact.slot.kind,
      reason: "review-receipt-missing",
      detail: `${receiptPath} がありません。画像をRead/view_imageで開いて5項目を確認してください`,
    };
  }
  let receipt;
  try {
    receipt = JSON.parse(fs.readFileSync(receiptPath, "utf8"));
  } catch (err) {
    return { kind: artifact.slot.kind, reason: "review-receipt-invalid", detail: err.message };
  }
  const checks = receipt.checks || {};
  const presentation = receipt.presentation || {};
  const validation = receipt.validation || {};
  const validPresentation = (
    (presentation.host === "claude-code" && presentation.tool === "Read") ||
    (presentation.host === "codex" && presentation.tool === "view_image")
  );
  if (
    receipt.ok !== true ||
    receipt.kind !== artifact.slot.kind ||
    !validPresentation ||
    validation.strict !== true ||
    validation.kind !== artifact.slot.kind ||
    validation.actual !== validation.expected ||
    Object.keys(checks).length !== 5 ||
    Object.values(checks).some((value) => value !== "PASS")
  ) {
    return {
      kind: artifact.slot.kind,
      reason: "review-receipt-not-passed",
      detail: `${receiptPath} の5項目がすべてPASSではありません`,
    };
  }
  if (receipt.imagePath !== path.resolve(artifact.source) || receipt.imageSha256 !== sha256File(artifact.source)) {
    return {
      kind: artifact.slot.kind,
      reason: "review-image-hash-mismatch",
      detail: `${artifact.source} は目視確認後に変更されています`,
    };
  }
  return null;
}

function buildEmbed(slot, pngPath, useMarkdown) {
  return useMarkdown
    ? `![${slot.alt}](${pngPath})`
    : `![[${path.basename(pngPath)}]]`;
}

function main() {
  const args = parseArgs(process.argv);
  if (!args.file || !args.imageDir) {
    console.error(JSON.stringify({ error: "--file <path> と --image-dir <dir> を指定してください" }));
    process.exit(2);
  }
  if (!fs.existsSync(args.file)) {
    console.error(JSON.stringify({ error: `投稿ファイルが見つかりません: ${args.file}` }));
    process.exit(2);
  }
  args.file = path.resolve(args.file);
  args.imageDir = path.resolve(args.imageDir);
  const requestedKinds = args.only
    ? String(args.only).split(",").map((item) => item.trim()).filter(Boolean)
    : SLOTS.map((slot) => slot.kind);
  const unknownKinds = requestedKinds.filter((kind) => !SLOTS.some((slot) => slot.kind === kind));
  if (unknownKinds.length > 0) {
    console.error(JSON.stringify({ error: `未知の種別: ${unknownKinds.join(", ")}` }));
    process.exit(2);
  }
  if (args.attachmentDir) {
    args.attachmentDir = path.resolve(args.attachmentDir);
    if (!fs.existsSync(args.attachmentDir) || !fs.statSync(args.attachmentDir).isDirectory()) {
      console.error(JSON.stringify({ error: `添付ディレクトリが見つかりません: ${args.attachmentDir}` }));
      process.exit(2);
    }
  }

  let lines;
  try {
    lines = fs.readFileSync(args.file, "utf8").split("\n");
  } catch (err) {
    console.error(JSON.stringify({ error: `読み込めません: ${err.message}` }));
    process.exit(2);
  }

  const embedded = [];
  const problems = [];
  const postStem = path.basename(args.file, path.extname(args.file));
  const artifacts = SLOTS.filter((slot) => requestedKinds.includes(slot.kind)).map((slot) => {
    const source = path.join(args.imageDir, `${slot.kind}.png`);
    const published = args.attachmentDir
      ? path.join(args.attachmentDir, `${postStem}-${slot.kind}.png`)
      : source;
    return { slot, source, published };
  });

  // 前半は read-only preflight。全3 slot と全3 image を先に確かめ、
  // 1件でも問題があれば元ファイルの bytes を変えない。
  for (const artifact of artifacts) {
    const { slot, source } = artifact;
    if (!fs.existsSync(source)) {
      problems.push({ kind: slot.kind, reason: "image-missing", detail: `${source} がありません` });
    }

    const review = reviewProblem(args.imageDir, artifact);
    if (review) problems.push(review);
    const strictVisual = strictVisualProblem(args.imageDir, artifact);
    if (strictVisual) problems.push(strictVisual);

    const idx = lines.findIndex((line) => line === slot.label);
    if (idx === -1) {
      problems.push({ kind: slot.kind, reason: "slot-missing", detail: `ラベル行「${slot.label}」が投稿ファイルにありません` });
    }
  }

  if (problems.length > 0) {
    console.log(JSON.stringify({ ok: false, embedded, artifacts: [], problems }, null, 2));
    process.exit(1);
  }

  // 実運用の Obsidian 添付先を指定した場合だけ、固定名の作業画像を投稿固有名へ公開する。
  // 各ファイルは同一ディレクトリの一時ファイルへ書いてから rename し、中途半端な bytes を見せない。
  if (args.attachmentDir) {
    const staged = [];
    try {
      for (let index = 0; index < artifacts.length; index++) {
        const artifact = artifacts[index];
        const temporary = path.join(
          args.attachmentDir,
          `.${path.basename(artifact.published)}.${process.pid}.${index}.tmp`
        );
        fs.copyFileSync(artifact.source, temporary);
        staged.push({ temporary, published: artifact.published });
      }
      for (const item of staged) fs.renameSync(item.temporary, item.published);
    } catch (err) {
      for (const item of staged) {
        try { fs.rmSync(item.temporary, { force: true }); } catch { /* noop */ }
      }
      console.error(JSON.stringify({ error: `画像を添付先へ配置できません: ${err.message}` }));
      process.exit(2);
    }
  }

  // preflight PASS 後にのみメモリ上で全差し込みを完成させ、最後に1回だけ書く。
  for (const artifact of artifacts) {
    const { slot, published: pngPath } = artifact;
    const idx = lines.findIndex((line) => line === slot.label);

    const embed = buildEmbed(slot, pngPath, Boolean(args.markdown));
    const next = idx + 1;

    if (next < lines.length && EMBED_RE.test(lines[next].trim())) {
      // 既に差し込み済み。冪等になるよう置き換える。
      const before = lines[next];
      lines[next] = embed;
      embedded.push({ kind: slot.kind, action: before === embed ? "unchanged" : "replaced", line: next + 1, embed });
    } else {
      // ラベル直後へ挿入する。テンプレートは直後に空行を持つので、その1行を使う。
      if (next < lines.length && lines[next].trim() === "") {
        lines[next] = embed;
      } else {
        lines.splice(next, 0, embed);
      }
      embedded.push({ kind: slot.kind, action: "inserted", line: next + 1, embed });
    }
  }

  try {
    fs.writeFileSync(args.file, lines.join("\n"), "utf8");
  } catch (err) {
    console.error(JSON.stringify({ error: `書き込めません: ${err.message}` }));
    process.exit(2);
  }

  console.log(JSON.stringify({
    ok: true,
    embedded,
    artifacts: artifacts.map(({ slot, source, published }) => ({
      kind: slot.kind,
      source,
      path: published,
    })),
    problems,
  }, null, 2));
  process.exit(0);
}

main();
