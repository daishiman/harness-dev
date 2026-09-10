#!/usr/bin/env node
/**
 * validate-visual-assets.js - 生成画像の機械検証（決定論的処理）
 *
 * 生成された PNG が「本物の PNG か」「意図した比率か」「意図した寸法か」「背景が不透明か」
 * 「背景が種別ごとの規定色か」を外部依存なしで検証する。PNG の IHDR チャンク（署名8バイトの
 * 直後、offset 16 から width・height が各4バイトのビッグエンディアン、offset 25 が
 * color type）を直接読み、背景色は lib/png-background.js が IDAT を展開して四隅から採る。
 *
 * 背景色を FAIL にする理由:
 *   規定色は種別で違う（図解は純白 #FFFFFF、サムネイルはオフホワイト #F7F5F1）。
 *   規範に両方の指定が並存する以上、生成系はどちらへも転ぶ。サムネイルが純白で返ると
 *   X / note の白い UI と地続きになって画像の輪郭が消えるが、単体で見ると正常なので
 *   目視では気づけない。規則は visual-spec.json の kinds.*.background に置く。
 *
 * 比率と寸法で扱いを分ける理由:
 *   比率が違う画像は貼り先（X のカード・note のヘッダ）でトリミングされて文字が欠けるため
 *   FAIL にする。一方、比率が合っていれば寸法は縮小で合わせられるので WARN に留める。
 *   --strict を付けると寸法不一致も FAIL になる。
 *
 * 透過を FAIL にする理由:
 *   diagram-style-canon.md の絶対ルールは「背景は必ず白」である。生成系はこれを
 *   「背景を描かない」と解釈してアルファ付きで出すことがあり、その画像は貼り先の
 *   背景色を透かすので、ダークテーマでは黒地に黒文字となって全文が消える。白紙で
 *   出てくるわけではないぶん目視でも見落としやすい。比率違いと同格の FAIL とする。
 *
 * 画風・退化（diagram-style-canon.md §5）は機械判定できない。本スクリプトが緑でも
 * 生成物は必ず目視すること。
 *
 * 使用例:
 *   node scripts/validate-visual-assets.js --image-dir /path/to/images
 *   node scripts/validate-visual-assets.js --image-dir /path/to/images --only diagram --strict
 *
 * 終了コード: 0 = 全件PASS / 1 = 1件以上FAIL / 2 = 引数・入出力エラー
 */

const fs = require("fs");
const path = require("path");
const VISUAL_SPEC = require("../skills/run-x-visual-generate/references/visual-spec.json");
const { classifyBackground } = require("./lib/png-background.js");

const PNG_SIGNATURE = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

const EXPECTED = VISUAL_SPEC.kinds;
const STANDARD_KINDS = Object.keys(EXPECTED).filter(
  (kind) => EXPECTED[kind].palette === "thumbnail"
);

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--image-dir") args.imageDir = argv[++i];
    else if (argv[i] === "--only") args.only = argv[++i];
    else if (argv[i] === "--strict") args.strict = true;
  }
  return args;
}

// PNG の color type。4 = グレースケール+アルファ、6 = RGB+アルファ。
// 3（パレット）も tRNS チャンクで透過を持てるが、拡散モデルはパレット PNG を出さない。
const ALPHA_COLOR_TYPES = new Set([4, 6]);

/**
 * PNG のヘッダから寸法と color type を読む。PNG でなければ null を返す。
 * レイアウト: [0-7] 署名 / [8-11] IHDR長 / [12-15] "IHDR" / [16-19] width /
 *             [20-23] height / [24] bit depth / [25] color type
 */
function readPngHeader(filePath) {
  let fd;
  try {
    fd = fs.openSync(filePath, "r");
    const buf = Buffer.alloc(26);
    if (fs.readSync(fd, buf, 0, 26, 0) < 26) return null;
    for (let i = 0; i < PNG_SIGNATURE.length; i++) {
      if (buf[i] !== PNG_SIGNATURE[i]) return null;
    }
    if (buf.toString("ascii", 12, 16) !== "IHDR") return null;
    return {
      width: buf.readUInt32BE(16),
      height: buf.readUInt32BE(20),
      colorType: buf[25],
    };
  } catch {
    return null;
  } finally {
    if (fd !== undefined) {
      try { fs.closeSync(fd); } catch { /* noop */ }
    }
  }
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

  const kinds = args.only
    ? String(args.only).split(",").map((s) => s.trim()).filter(Boolean)
    : STANDARD_KINDS;
  const strict = Boolean(args.strict || !args.only);
  for (const kind of kinds) {
    if (!EXPECTED[kind]) {
      console.error(JSON.stringify({ error: `未知の種別: ${kind}（有効: ${Object.keys(EXPECTED).join(", ")}）` }));
      process.exit(2);
    }
  }

  const results = [];
  let failed = 0;

  for (const kind of kinds) {
    const pngPath = path.join(args.imageDir, `${kind}.png`);
    const kindSpec = EXPECTED[kind];
    const exp = {
      width: kindSpec.generation.width,
      height: kindSpec.generation.height,
      ratio: kindSpec.ratio.numerator / kindSpec.ratio.denominator,
      ratioLabel: kindSpec.ratio.label,
    };

    if (!fs.existsSync(pngPath)) {
      results.push({ kind, ok: false, path: pngPath, reason: "missing", detail: `${pngPath} がありません` });
      failed++;
      continue;
    }

    const header = readPngHeader(pngPath);
    if (!header) {
      // 生成系が説明テキストを .png として書いた場合にここで止まる。
      results.push({ kind, ok: false, path: pngPath, reason: "not-png", detail: "PNG署名または IHDR が読めません（テキストを .png として保存した可能性）" });
      failed++;
      continue;
    }

    const actualRatio = header.width / header.height;
    const ratioDrift = Math.abs(actualRatio - exp.ratio) / exp.ratio;
    const ratioOk = ratioDrift <= VISUAL_SPEC.ratioTolerance;
    const sizeOk = header.width === exp.width && header.height === exp.height;
    const opaqueOk = !ALPHA_COLOR_TYPES.has(header.colorType);

    // 背景色は kind ごとに規則が違う（図解は純白、サムネイルはオフホワイト）。
    // 透過していると四隅の RGB を読んでも意味がないので、不透明なときだけ検査する。
    const background = opaqueOk
      ? classifyBackground(pngPath, kindSpec.background)
      : { status: "unchecked", reason: null, rgb: null };

    const warnings = [];
    if (ratioOk && !sizeOk) {
      warnings.push(`寸法が期待値と異なる（期待 ${exp.width}x${exp.height} / 実際 ${header.width}x${header.height}）。比率は許容内なので縮小で合わせられる`);
    }
    if (background.status === "unchecked" && background.detail) {
      warnings.push(background.detail);
    }

    // 失敗理由は複数同時に立ちうるので、重い順に並べて全部返す。片方だけ直して
    // 再生成しても緑にならない事態を避けるため。
    const reasons = [];
    if (!opaqueOk) reasons.push("has-alpha");
    if (background.status === "fail") reasons.push(background.reason);
    if (!ratioOk) reasons.push("ratio-mismatch");
    if (!sizeOk && strict) reasons.push("size-mismatch");

    const ok = reasons.length === 0;
    if (!ok) failed++;

    results.push({
      kind,
      ok,
      path: pngPath,
      actual: `${header.width}x${header.height}`,
      expected: `${exp.width}x${exp.height}`,
      expectedRatio: exp.ratioLabel,
      ratioDrift: Number(ratioDrift.toFixed(4)),
      colorType: header.colorType,
      opaque: opaqueOk,
      palette: kindSpec.palette,
      expectedBackground: kindSpec.background ? kindSpec.background.rule : null,
      backgroundHex: background.hex ?? null,
      backgroundStatus: background.status,
      reason: reasons.length === 0 ? null : reasons[0],
      reasons,
      detail: !opaqueOk
        ? `背景が透過している（color type ${header.colorType}）。貼り先の背景色を透かすので不透明背景の絶対ルールを満たさない。再生成が必要`
        : background.status === "fail" ? background.detail : undefined,
      warnings,
    });
  }

  console.log(JSON.stringify({
    ok: failed === 0,
    strict,
    note: "画風と退化（diagram-style-canon.md §5）は機械判定できない。緑でも生成物は必ず目視すること",
    results,
  }, null, 2));
  process.exit(failed === 0 ? 0 : 1);
}

main();
