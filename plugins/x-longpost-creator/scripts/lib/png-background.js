/**
 * png-background.js - PNG の背景色を四隅から標本抽出する（外部依存なし）
 *
 * 生成画像の「背景が指定の色で塗られているか」を機械判定するために、PNG の IDAT を
 * 展開して四隅近傍の画素を読む。Node 同梱の zlib だけで完結させ、画像ライブラリを
 * 足さない（plugin の依存を Node v18 以上だけに保つため）。
 *
 * 四隅を標本にする理由: thumbnail-style-canon.md TS-08 が四辺 5% 以上の余白を要求して
 * いるので、辺から 2% 内側の点は必ず背景である。中央を読むと文字や図形に当たる。
 *
 * 対応範囲は bit depth 8・非インタレースの color type 0 / 2 / 4 / 6 に限る。範囲外は
 * null を返し、呼び出し側は「検査せず」として扱う（誤判定するくらいなら判定しない）。
 */

const fs = require("fs");
const zlib = require("zlib");

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

// color type -> 1画素あたりのサンプル数。3（パレット）は対応しない。
const SAMPLES_PER_PIXEL = { 0: 1, 2: 3, 4: 2, 6: 4 };

// color type -> そのサンプル列から RGB を取り出す関数。
const TO_RGB = {
  0: (px) => [px[0], px[0], px[0]],
  2: (px) => [px[0], px[1], px[2]],
  4: (px) => [px[0], px[0], px[0]],
  6: (px) => [px[0], px[1], px[2]],
};

function paeth(a, b, c) {
  const p = a + b - c;
  const pa = Math.abs(p - a);
  const pb = Math.abs(p - b);
  const pc = Math.abs(p - c);
  if (pa <= pb && pa <= pc) return a;
  if (pb <= pc) return b;
  return c;
}

/** 1 走査線をフィルタ解除する。PNG spec 9.2 の 5 種をそのまま実装する。 */
function unfilterRow(filterType, row, prev, bpp) {
  switch (filterType) {
    case 0:
      break;
    case 1:
      for (let i = bpp; i < row.length; i++) row[i] = (row[i] + row[i - bpp]) & 0xff;
      break;
    case 2:
      for (let i = 0; i < row.length; i++) row[i] = (row[i] + prev[i]) & 0xff;
      break;
    case 3:
      for (let i = 0; i < row.length; i++) {
        const left = i >= bpp ? row[i - bpp] : 0;
        row[i] = (row[i] + ((left + prev[i]) >> 1)) & 0xff;
      }
      break;
    case 4:
      for (let i = 0; i < row.length; i++) {
        const left = i >= bpp ? row[i - bpp] : 0;
        const upLeft = i >= bpp ? prev[i - bpp] : 0;
        row[i] = (row[i] + paeth(left, prev[i], upLeft)) & 0xff;
      }
      break;
    default:
      return false;
  }
  return true;
}

/** IHDR と全 IDAT を1回の走査で集める。 */
function readChunks(buf) {
  if (buf.length < 8 || !buf.subarray(0, 8).equals(PNG_SIGNATURE)) return null;
  let offset = 8;
  let ihdr = null;
  const idat = [];
  while (offset + 8 <= buf.length) {
    const length = buf.readUInt32BE(offset);
    const type = buf.toString("ascii", offset + 4, offset + 8);
    const dataStart = offset + 8;
    if (dataStart + length > buf.length) return null;
    if (type === "IHDR") {
      ihdr = {
        width: buf.readUInt32BE(dataStart),
        height: buf.readUInt32BE(dataStart + 4),
        bitDepth: buf[dataStart + 8],
        colorType: buf[dataStart + 9],
        interlace: buf[dataStart + 12],
      };
    } else if (type === "IDAT") {
      idat.push(buf.subarray(dataStart, dataStart + length));
    } else if (type === "IEND") {
      break;
    }
    offset = dataStart + length + 4; // +4 は CRC
  }
  if (!ihdr || idat.length === 0) return null;
  return { ihdr, idat: Buffer.concat(idat) };
}

/**
 * 四隅（各辺から 2% 内側）の RGB を返す。
 * @returns {{samples: number[][], rgb: number[]}|null}
 *   samples は4点の [r,g,b]、rgb は各チャンネルの中央値（4点なので中2点の平均）。
 *   対応範囲外・破損時は null。
 */
function sampleCornerBackground(filePath) {
  let parsed;
  try {
    parsed = readChunks(fs.readFileSync(filePath));
  } catch {
    return null;
  }
  if (!parsed) return null;

  const { width, height, bitDepth, colorType, interlace } = parsed.ihdr;
  const spp = SAMPLES_PER_PIXEL[colorType];
  if (bitDepth !== 8 || interlace !== 0 || spp === undefined) return null;
  if (width < 4 || height < 4) return null;

  let raw;
  try {
    raw = zlib.inflateSync(parsed.idat);
  } catch {
    return null;
  }

  const bpp = spp;
  const stride = width * bpp;
  if (raw.length < (stride + 1) * height) return null;

  const insetX = Math.max(1, Math.round(width * 0.02));
  const insetY = Math.max(1, Math.round(height * 0.02));
  const sampleRows = new Set([insetY, height - 1 - insetY]);
  const sampleCols = [insetX, width - 1 - insetX];

  // フィルタ解除は前行に依存するので、下側の標本行までは全行を順に処理する必要がある。
  // 保持するのは前行1本だけなので、画像サイズによらずメモリは stride の2倍で済む。
  const maxRow = Math.max(...sampleRows);
  let prev = Buffer.alloc(stride);
  const samples = [];
  for (let y = 0; y <= maxRow; y++) {
    const base = y * (stride + 1);
    const filterType = raw[base];
    const row = Buffer.from(raw.subarray(base + 1, base + 1 + stride));
    if (!unfilterRow(filterType, row, prev, bpp)) return null;
    if (sampleRows.has(y)) {
      for (const x of sampleCols) {
        samples.push(TO_RGB[colorType](row.subarray(x * bpp, x * bpp + bpp)));
      }
    }
    prev = row;
  }
  if (samples.length === 0) return null;

  // 中央値を使うのは、四隅のうち1点がアクセント図形に掛かっていても結論が動かないため。
  const rgb = [0, 1, 2].map((c) => {
    const sorted = samples.map((s) => s[c]).sort((a, b) => a - b);
    const mid = sorted.length >> 1;
    return sorted.length % 2 === 0 ? Math.round((sorted[mid - 1] + sorted[mid]) / 2) : sorted[mid];
  });
  return { samples, rgb };
}

/**
 * 背景の標本を visual-spec.json の kind.background 規則に照らす。
 * @returns {{status: "pass"|"fail"|"unchecked", reason: string|null, detail: string|undefined, rgb: number[]|null}}
 */
function classifyBackground(filePath, backgroundRule) {
  if (!backgroundRule) return { status: "unchecked", reason: null, rgb: null };
  const sampled = sampleCornerBackground(filePath);
  if (!sampled) {
    return {
      status: "unchecked",
      reason: null,
      rgb: null,
      detail: "背景色を読めない PNG 形式（bit depth 8・非インタレース・color type 0/2/4/6 以外）。背景色は目視で確認する",
    };
  }
  const { rgb } = sampled;
  const hex = `#${rgb.map((v) => v.toString(16).padStart(2, "0").toUpperCase()).join("")}`;

  if (backgroundRule.rule === "white") {
    if (rgb.every((v) => v >= backgroundRule.minChannel)) {
      return { status: "pass", reason: null, rgb, hex };
    }
    return {
      status: "fail",
      reason: "background-not-white",
      rgb,
      hex,
      detail: `背景が白でない（四隅の中央値 ${hex}。全チャンネル ${backgroundRule.minChannel} 以上が必要）`,
    };
  }

  if (backgroundRule.rule === "off-white") {
    if (rgb.every((v) => v > backgroundRule.maxChannel)) {
      return {
        status: "fail",
        reason: "background-too-white",
        rgb,
        hex,
        detail: `背景が純白に寄りすぎている（四隅の中央値 ${hex}）。オフホワイトでないと貼り先の白い UI と地続きになり画像の輪郭が消える`,
      };
    }
    if (rgb.some((v) => v < backgroundRule.minChannel)) {
      return {
        status: "fail",
        reason: "background-too-dark",
        rgb,
        hex,
        detail: `背景が暗すぎる（四隅の中央値 ${hex}。全チャンネル ${backgroundRule.minChannel} 以上が必要）。色面や写真が全面に敷かれた可能性`,
      };
    }
    return { status: "pass", reason: null, rgb, hex };
  }

  return { status: "unchecked", reason: null, rgb, hex };
}

module.exports = { sampleCornerBackground, classifyBackground };
