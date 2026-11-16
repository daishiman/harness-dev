#!/usr/bin/env node
/**
 * generate-images-codex.js - Codex Image2 による図解・サムネイル生成
 *
 * codex exec で meta.generation.size に従う PNG を生成し、meta.json の source を
 * 実生成系（codex-image2）へ更新する。
 *
 * 注意: codex exec は課金が発生する（1枚あたり概ね 1-2 分）。--dry-run で
 * 組み立てたコマンドを目視してから本実行できる。
 *
 * 出自: slide-report-generator の同名スクリプトから 2026-08-31 に回収ロジックを移植。
 * 本 plugin 固有の差分は kind ごとの画風指示と meta 契約。upstream の回収方式や
 * Codex の session/image 保存契約が変わったときは再 audit する。
 *
 * 画風の伝え方は2経路ある。
 *   (a) 文章 - prompt.txt（画像内テキストと版面の正本）と、本スクリプトが visual-spec.json の
 *       palette から組む起動指示文。指示文は kind ごとに分岐する。共通の固定文にすると、
 *       図解の「純白・白黒」がサムネイルの「オフホワイト・藍アクセント」を上書きしてしまう。
 *   (b) 絵 - assets/reference-images/ の見本を codex exec -i で添付する。線の太さや
 *       簡略度は数値へ落とすと窮屈になるため、絵で渡すほうが正確に伝わる。見本は複製の
 *       対象ではないので、構図・文言・個々のアイコンの複製は指示文で禁じる。
 *
 * 事故対策:
 *   [事故1] codex の内蔵 image_gen は $CODEX_HOME/generated_images/<session-id>/ へ保存し、
 *           指定パスへは書かない。
 *           対策: codex に保存を任せず、session dir から自前で回収する。
 *   [事故2] codex が画像生成に失敗すると、説明テキストを .png 拡張子で書くことがある。
 *           対策: 先頭4バイトの PNG署名（89 50 4E 47）で本物だけを通す。
 *   [事故3] codex は指示しないと PIL/matplotlib 等のコード描画へ退化し、
 *           単色角丸ボックスにテキストを詰めた平坦図を返す。
 *           対策: 指示文で imagegen を明示強制し、コード描画を名指しで禁じる。
 *   [事故4] codex exec の出力をプロセス内でキャプチャすると session-id が取れず回収に失敗する。
 *           対策: shell を介さず executable + argv で起動し、stdout/stderr は同じログ fd、
 *           stdin は ignore に接続する。
 *
 * 実行ファイルは XLP_CODEX_BIN（既定: codex）で指定する。shell alias は解決しない。
 * 課金ループへ入る前に実在・実行可能性を検査し、失敗時は一度も retry せず exit 2。
 *
 * 使用例:
 *   node scripts/generate-images-codex.js --image-dir /path/to/images --dry-run
 *   node scripts/generate-images-codex.js --image-dir /path/to/images
 *   node scripts/generate-images-codex.js --image-dir /path/to/images --only diagram
 *
 * 終了コード: 0 = 全件成功（dry-run 含む） / 1 = 1件以上失敗 / 2 = 引数・入出力エラー
 */

const fs = require("fs");
const crypto = require("crypto");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const VISUAL_SPEC = require("../skills/run-x-visual-generate/references/visual-spec.json");
const { resolveForKind } = require("./lib/reference-images.js");

const PNG_SIGNATURE = [0x89, 0x50, 0x4e, 0x47];
const MAX_RETRIES = 3;
const KINDS = Object.keys(VISUAL_SPEC.kinds);
const STANDARD_KINDS = KINDS.filter(
  (kind) => VISUAL_SPEC.kinds[kind].palette === "thumbnail"
);

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--image-dir") args.imageDir = argv[++i];
    else if (argv[i] === "--only") args.only = argv[++i];
    else if (argv[i] === "--dry-run") args.dryRun = true;
    else if (argv[i] === "--source") args.source = argv[++i];
    else if (argv[i] === "--require-reference-images") args.requireReferences = true;
  }
  return args;
}

// $CODEX_HOME を解決する（未設定時は ~/.codex）。image_gen の出力先の基点。
function codexHome() {
  return process.env.CODEX_HOME && process.env.CODEX_HOME.trim()
    ? process.env.CODEX_HOME.trim()
    : path.join(os.homedir(), ".codex");
}

// 先頭4バイトが PNG署名かを確認する（事故2対策）。
function isPngFile(filePath) {
  if (!fs.existsSync(filePath)) return false;
  let fd;
  try {
    fd = fs.openSync(filePath, "r");
    const buf = Buffer.alloc(4);
    if (fs.readSync(fd, buf, 0, 4, 0) < 4) return false;
    return PNG_SIGNATURE.every((b, i) => buf[i] === b);
  } catch {
    return false;
  } finally {
    if (fd !== undefined) {
      try { fs.closeSync(fd); } catch { /* noop */ }
    }
  }
}

/**
 * kind の palette から、その kind の見た目を1文で述べる。
 *
 * ここを共通の固定文にしてはいけない。palette が図解（純白・白黒）とサムネイル
 * （オフホワイト・墨黒・藍アクセント）で違う以上、起動指示文が片方を名指しすると、
 * prompt.txt が正しく書かれていても指示文がそれを上書きしてしまう。実際にこの関数は
 * kind によらず "pure white background" と "black-and-white" を強制しており、
 * サムネイルの規範と正面から矛盾していた。色の実体は visual-spec.json だけが持つ。
 */
function describeAppearance(kind) {
  const spec = VISUAL_SPEC.kinds[kind];
  const palette = VISUAL_SPEC.palettes[spec.palette];
  if (spec.palette === "diagram") {
    return [
      `The result must be a flat, minimal, black-and-white Japanese infographic`,
      `on a solid opaque background of exactly ${palette.background},`,
      `built from clean vector-style pictograms connected by arrows.`,
      `Text and shapes are ${palette.text}.`,
    ].join(" ");
  }
  return [
    `The result must be a flat, minimal Japanese thumbnail`,
    `on a solid opaque background of exactly ${palette.background} (a soft off-white, NOT pure white).`,
    `All text is ${palette.text}.`,
    // アクセントは色数ではなく役割で縛る（TS-05）。「1色だけ」と言うと、
    // どちらの色を捨てるかを生成系が勝手に決めてしまう。
    `Use ${palette.accent} only for structural lines, rails and rings, never on text.`,
    `Use ${palette.label} only for a single small band holding the supporting phrase, with white text inside it.`,
    `No other color appears. Never use red.`,
    `Do not draw any human figure or silhouette.`,
  ].join(" ");
}

/**
 * codex exec へ渡す単一指示を組み立てる。
 *
 * prompt.txt を画像内テキストの単一正本に据え、この指示文と衝突したら prompt.txt を
 * 優先させる。prompt.txt が引用符で指定した日本語ラベルは意図したテキストであり、
 * 禁じるのは崩れた字・意図しない追加テキストだけである（この区別を書かないと、
 * モデルが「テキストを描くな」と解釈して版面ごと壊す）。
 *
 * 事故3対策: imagegen の明示強制とコード描画の名指し禁止を必ず含める。
 * 質感・陰影・立体は kind によらず禁じる（slide-report-generator が求めるマンガ風
 * アイソメ絵とは逆方向のため）。一方で配色は kind ごとに違うので describeAppearance に委ねる。
 */
function buildCodexInstruction(promptPath, pngPath, size, kind, referenceCount = 0) {
  const finishRule = VISUAL_SPEC.kinds[kind].palette === "thumbnail"
    ? `Keep all lettering completely flat with no outline, gradient or shadow. Geometric objects may use restrained paper-cut texture and a shallow soft shadow only; no dramatic 3D depth and no photographic rendering.`
    : `Do NOT add gradients, shadows, 3D depth, photographic texture or decorative color.`;
  const lines = [
    `Read the file ${promptPath} in full.`,
    `Render it using your built-in text-to-image image generation tool (a diffusion imagegen model such as gpt-image).`,
    `This is mandatory: do NOT draw the image programmatically with PIL/Pillow/matplotlib/cairo/numpy/SVG or any code-based drawing.`,
    describeAppearance(kind),
    finishRule,
    `Resize to exactly ${size} if needed and save the final PNG to ${pngPath}.`,
    `The prompt file is the single source of truth for in-image text: render the quoted Japanese strings it specifies crisply and undistorted;`,
    `only garbled, distorted, or unintended extra text is forbidden, not the intentional quoted labels.`,
    `Honor every constraint in the NEGATIVE block of the prompt file.`,
  ];
  if (referenceCount > 0) {
    // 見本は粒度の参照であって複製の対象ではない。ここを書かないと、どの投稿でも
    // 見本と同じ構図・同じ文字の絵が出てきて、本文の構造を表す図解にならなくなる。
    lines.push(
      `${referenceCount} reference image(s) are attached.`,
      `Use them ONLY as a guide to line weight, fill density and level of simplification.`,
      `Do NOT copy their composition, their text, or their specific icons: the content must come from the prompt file alone.`
    );
  }
  lines.push(`Output only the PNG file.`);
  return lines.join(" ");
}

function isExecutableFile(candidate) {
  try {
    fs.accessSync(candidate, fs.constants.X_OK);
    return fs.statSync(candidate).isFile();
  } catch {
    return false;
  }
}

/**
 * shell alias に依存せず実行ファイルを解決する。
 * パスを含む指定はその1件だけ、コマンド名は PATH の各ディレクトリだけを調べる。
 */
function resolveCodexExecutable(configured) {
  const requested = String(configured || "").trim();
  if (requested === "") return null;
  if (requested.includes("/") || requested.includes("\\")) {
    const candidate = path.resolve(requested);
    return isExecutableFile(candidate) ? candidate : null;
  }
  for (const directory of String(process.env.PATH || "").split(path.delimiter)) {
    const candidate = path.resolve(directory || ".", requested);
    if (isExecutableFile(candidate)) return candidate;
  }
  return null;
}

/**
 * codex exec の argv を組む。見本画像は -i を繰り返して渡す。
 * 1つの -i に複数値を並べると、後続の指示文まで画像パスとして解釈されうるため。
 */
function codexArgv(instruction, referenceImages) {
  const argv = ["exec"];
  for (const image of referenceImages) argv.push("-i", image);
  argv.push(instruction);
  return argv;
}

function codexInvocation(executable, instruction, logPath, referenceImages = []) {
  return {
    executable,
    argv: codexArgv(instruction, referenceImages),
    stdio: { stdin: "ignore", stdout: logPath, stderr: logPath },
  };
}

// 生成プロセスの次に、実行ホストが同じ画像実体を開くための引き継ぎ。
// パスを出しただけでは目視にならないため、呼び出し側は対応 tool を実行する。
function presentationHandoff(pngPath) {
  const absolutePath = path.resolve(pngPath);
  return {
    absolutePath,
    claudeCode: { tool: "Read", path: absolutePath },
    codex: { tool: "view_image", path: absolutePath },
  };
}

// 事故4対策: shell を介さず argv 実行し、出力はログ fd、stdin は ignore に接続する。
function runCodex(executable, instruction, logPath, referenceImages = []) {
  let logFd;
  try {
    logFd = fs.openSync(logPath, "w");
    return spawnSync(executable, codexArgv(instruction, referenceImages), {
      shell: false,
      stdio: ["ignore", logFd, logFd],
    });
  } finally {
    if (logFd !== undefined) {
      try { fs.closeSync(logFd); } catch { /* noop */ }
    }
  }
}

function inspectExecutor(executable) {
  const result = spawnSync(executable, ["--version"], {
    shell: false,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  const version = `${result.stdout || ""}${result.stderr || ""}`.trim().split(/\r?\n/)[0] || null;
  return {
    path: path.resolve(executable),
    version,
    versionAvailable: result.status === 0 && Boolean(version),
  };
}

function sha256File(filePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

// codex exec のログから session id を抽出する（事故4対策の核心）。
function extractSessionId(logPath) {
  if (!fs.existsSync(logPath)) return null;
  let text;
  try { text = fs.readFileSync(logPath, "utf8"); } catch { return null; }
  const m = text.match(/session\s*id[:=]?\s*([0-9a-fA-F-]{8,})/i);
  return m ? m[1] : null;
}

// session dir 内で PNG署名を持つファイルを新しい順に1件返す（事故1+2対策）。
function findFreshPngInSession(sessionDir) {
  if (!fs.existsSync(sessionDir)) return null;
  let entries;
  try { entries = fs.readdirSync(sessionDir); } catch { return null; }
  const candidates = entries
    .map((name) => path.join(sessionDir, name))
    .filter((p) => {
      try { return fs.statSync(p).isFile(); } catch { return false; }
    })
    .filter(isPngFile)
    .sort((a, b) => {
      try { return fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs; } catch { return 0; }
    });
  return candidates.length > 0 ? candidates[0] : null;
}

/**
 * 1件分の生成と回収。成功時は pngPath、失敗時は null を返す。
 *   (a) 一時ログへリダイレクトして codex exec
 *   (b) ログから session id を抽出して session dir を特定
 *   (c) session dir から PNG署名つきファイルを新しい順に1件回収
 *   (d) pngPath へコピーして再度署名確認
 *   (e) 有効な PNG が取れなければ最大3回までリトライ
 */
function generateAndRecover(kind, instruction, pngPath, codexExecutable, referenceImages = []) {
  const genImagesBase = path.join(codexHome(), "generated_images");
  const logDir = fs.mkdtempSync(path.join(os.tmpdir(), "xlp-img-"));
  try {
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      const logPath = path.join(logDir, `${kind}.attempt${attempt}.log`);
      console.log(`  [RUN ${attempt}/${MAX_RETRIES}] ${kind}`);
      const invocation = runCodex(codexExecutable, instruction, logPath, referenceImages);
      if (invocation.error) {
        const error = new Error(`codex 実行ファイルを起動できません: ${invocation.error.message}`);
        error.code = "CODEX_EXEC_UNAVAILABLE";
        throw error;
      }
      if (invocation.status !== 0) {
        // 非ゼロ終了でも session dir に PNG が残ることがあるので回収は試みる。
        console.error(`  [WARN] codex exec exited non-zero (attempt ${attempt}, status ${invocation.status})`);
      }

      const sessionId = extractSessionId(logPath);
      if (!sessionId) {
        console.error(`  [WARN] session id をログから抽出できません (attempt ${attempt})`);
        continue;
      }

      const srcPng = findFreshPngInSession(path.join(genImagesBase, sessionId));
      if (!srcPng) {
        console.error(`  [WARN] PNG署名を持つファイルが session ${sessionId} にありません (attempt ${attempt})。テキストを .png として書いた可能性があるため再試行します`);
        continue;
      }

      try {
        fs.copyFileSync(srcPng, pngPath);
      } catch (err) {
        console.error(`  [WARN] コピー失敗 (attempt ${attempt}): ${err.message}`);
        continue;
      }
      if (!isPngFile(pngPath)) {
        console.error(`  [WARN] コピー後のファイルが PNG ではありません (attempt ${attempt})`);
        continue;
      }

      console.log(`  [PNG ] ${path.basename(srcPng)} (session ${sessionId}) -> ${path.basename(pngPath)} (${fs.statSync(pngPath).size} bytes)`);
      return { pngPath, sessionId };
    }
    console.error(`  [FAIL] ${kind}: ${MAX_RETRIES} 回試行しても有効な PNG を取得できませんでした`);
    return null;
  } finally {
    try { fs.rmSync(logDir, { recursive: true, force: true }); } catch { /* noop */ }
  }
}

function updateMetaSource(metaPath, sourceName, references, provenance) {
  if (!fs.existsSync(metaPath)) return false;
  let meta;
  try { meta = JSON.parse(fs.readFileSync(metaPath, "utf8")); } catch { return false; }
  meta.source = sourceName;
  if (!("seed" in meta)) meta.seed = null;
  // 再現性の記録。どの見本を実際に添付して出た絵なのかが後から辿れないと、
  // 同じプロンプトで違う絵が出た理由を切り分けられない。
  meta.referenceImages = {
    declared: references.declared,
    attached: references.attached.map((p) => path.basename(p)),
    missing: references.missing,
  };
  meta.seed = null;
  meta.provenance = {
    mode: "stochastic",
    seed: { supported: false, value: null },
    sessionId: provenance.sessionId,
    executor: provenance.executor,
    sha256: {
      prompt: sha256File(provenance.promptPath),
      structure: sha256File(provenance.structurePath),
      references: references.attached.map((referencePath) => ({
        file: path.basename(referencePath),
        sha256: sha256File(referencePath),
      })),
      png: sha256File(provenance.pngPath),
    },
  };
  fs.writeFileSync(metaPath, `${JSON.stringify(meta, null, 2)}\n`, "utf8");
  return true;
}

function main() {
  const args = parseArgs(process.argv);
  if (!args.imageDir) {
    console.error(JSON.stringify({ error: "--image-dir <dir> を指定してください" }));
    process.exit(2);
  }
  if (!fs.existsSync(args.imageDir)) {
    console.error(JSON.stringify({ error: `画像ディレクトリが見つかりません: ${args.imageDir}` }));
    process.exit(2);
  }
  args.imageDir = path.resolve(args.imageDir);

  const targets = args.only
    ? String(args.only).split(",").map((s) => s.trim()).filter(Boolean)
    : STANDARD_KINDS;
  for (const kind of targets) {
    if (!KINDS.includes(kind)) {
      console.error(JSON.stringify({ error: `未知の種別: ${kind}（有効: ${KINDS.join(", ")}）` }));
      process.exit(2);
    }
  }

  // --dry-run も明示された実行ファイルの契約を検査する。ただし実行はしない。
  // 実行不能なら課金 retry ループへ一度も入らず、呼び出し環境エラーとして exit 2。
  const configuredCodex = process.env.XLP_CODEX_BIN || "codex";
  const codexExecutable = resolveCodexExecutable(configuredCodex);
  if (!codexExecutable) {
    console.error(JSON.stringify({
      ok: false,
      error: "codex-not-found",
      executable: configuredCodex,
      hint: "XLP_CODEX_BIN に実行可能ファイルを指定するか、codex を PATH に追加してください",
    }, null, 2));
    process.exit(2);
  }

  // meta.source には実際に生成したバックエンドの実体名を記録する。
  // codex は呼び出し起点であって画像生成器ではないため、plain "codex" は使わない。
  const sourceName = args.source ? String(args.source) : "codex-image2";
  const executor = inspectExecutor(codexExecutable);
  const results = [];
  let failed = 0;

  for (const kind of targets) {
    const promptPath = path.join(args.imageDir, `${kind}.prompt.txt`);
    const metaPath = path.join(args.imageDir, `${kind}.meta.json`);
    const pngPath = path.join(args.imageDir, `${kind}.png`);

    if (!fs.existsSync(promptPath)) {
      console.error(`FAIL: ${promptPath} がありません（プロンプト設計を先に済ませてください）`);
      failed++;
      results.push({ kind, ok: false, reason: "prompt-missing" });
      continue;
    }
    if (!fs.existsSync(metaPath)) {
      console.error(`FAIL: ${metaPath} がありません（build-visual-prompts.js を先に実行してください）`);
      failed++;
      results.push({ kind, ok: false, reason: "meta-missing" });
      continue;
    }

    let size;
    try {
      const meta = JSON.parse(fs.readFileSync(metaPath, "utf8"));
      size = meta.generation && meta.generation.size;
    } catch (err) {
      console.error(`FAIL: ${metaPath} を解析できません: ${err.message}`);
      failed++;
      results.push({ kind, ok: false, reason: "meta-unparsable" });
      continue;
    }
    if (!/^\d+x\d+$/.test(String(size))) {
      console.error(`FAIL: ${metaPath} の generation.size が不正です: ${size}`);
      failed++;
      results.push({ kind, ok: false, reason: "bad-size" });
      continue;
    }

    // 画風の見本画像。無くても生成は動く（正本は文章の canon）が、宣言と実体の差は
    // 必ず記録へ残す。--require-reference-images を付けたときだけ FAIL へ昇格する。
    const references = resolveForKind(kind, KINDS);
    if (!references.ok) {
      console.error(`FAIL: ${kind}: 見本画像の宣言が不正です: ${references.error}`);
      failed++;
      results.push({ kind, ok: false, reason: "reference-manifest-invalid", detail: references.error });
      continue;
    }
    if (references.missing.length > 0) {
      const label = args.requireReferences ? "FAIL" : "WARN";
      console.error(`  [${label}] ${kind}: 宣言された見本画像の実体がありません: ${references.missing.join(", ")}`);
      if (args.requireReferences) {
        failed++;
        results.push({ kind, ok: false, reason: "reference-images-missing", missing: references.missing });
        continue;
      }
    }

    const instruction = buildCodexInstruction(promptPath, pngPath, size, kind, references.attached.length);

    if (args.dryRun) {
      console.log(`[DRY  ] ${kind} (${size}) references=${references.attached.length}/${references.declared}`);
      const invocation = codexInvocation(
        codexExecutable,
        instruction,
        `<tmp>/${kind}.attempt1.log`,
        references.attached
      );
      console.log(JSON.stringify(invocation));
      results.push({ kind, ok: true, dryRun: true, invocation, referenceImages: references });
      continue;
    }

    console.log(`[GEN  ] ${kind} (${size})`);
    let produced;
    try {
      produced = generateAndRecover(kind, instruction, pngPath, codexExecutable, references.attached);
    } catch (err) {
      if (err.code === "CODEX_EXEC_UNAVAILABLE") {
        console.error(JSON.stringify({ ok: false, error: "codex-not-executable", message: err.message }));
        process.exit(2);
      }
      throw err;
    }
    if (produced) {
      const structurePath = path.join(args.imageDir, "visual-structure.json");
      if (!fs.existsSync(structurePath)) {
        console.error(`FAIL: ${structurePath} がありません（provenance を記録できません）`);
        failed++;
        results.push({ kind, ok: false, reason: "structure-missing" });
        continue;
      }
      updateMetaSource(metaPath, sourceName, references, {
        sessionId: produced.sessionId,
        executor,
        promptPath,
        structurePath,
        pngPath: produced.pngPath,
      });
      results.push({
        kind,
        ok: true,
        png: path.resolve(produced.pngPath),
        presentation: presentationHandoff(pngPath),
        referenceImages: references,
      });
    } else {
      failed++;
      results.push({ kind, ok: false, reason: "generation-failed" });
    }
  }

  console.log(JSON.stringify({ ok: failed === 0, dryRun: Boolean(args.dryRun), results }, null, 2));
  process.exit(failed === 0 ? 0 : 1);
}

main();
