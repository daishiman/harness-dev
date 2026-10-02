/**
 * PNG / JPEG / WebP のヘッダーから画像の大きさを読む (Chrome も画像ライブラリも使わない)。
 *
 * JPEG は EXIF の向き (Orientation) を見て、5〜8 (横倒しの写真) なら幅と高さを入れ替える。
 * Chrome は既定 (image-orientation: from-image) で写真を起こして描くので、--info の大きさと
 * 切り出すときの座標がそろう。
 */
import { closeSync, openSync, readFileSync, readSync } from "node:fs";

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const SOF_MARKERS = new Set([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf]);

/** ファイルの先頭 limit バイトを読む。JPEG は EXIF が大きいことがあるので多めに読む。 */
export function readHead(file, limit = 512 * 1024) {
  const fd = openSync(file, "r");
  try {
    const buffer = Buffer.alloc(limit);
    const read = readSync(fd, buffer, 0, limit, 0);
    return buffer.subarray(0, read);
  } finally {
    closeSync(fd);
  }
}

/** 画像の種類を先頭のバイトで見分ける。png / jpeg / webp / null。 */
export function sniffFormat(buffer) {
  if (buffer.length >= 8 && buffer.subarray(0, 8).equals(PNG_SIGNATURE)) return "png";
  if (buffer.length >= 3 && buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) return "jpeg";
  if (buffer.length >= 12 && buffer.toString("latin1", 0, 4) === "RIFF" && buffer.toString("latin1", 8, 12) === "WEBP") {
    return "webp";
  }
  return null;
}

function pngSize(buffer) {
  if (buffer.length < 24 || buffer.toString("latin1", 12, 16) !== "IHDR") return null;
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20), orientation: 1 };
}

/** EXIF (TIFF) の IFD0 から Orientation (0x0112) を読む。無ければ 1。 */
function exifOrientation(buffer, start, length) {
  if (length < 14 || buffer.toString("latin1", start, start + 6) !== "Exif\0\0") return 1;
  const tiff = start + 6;
  const order = buffer.toString("latin1", tiff, tiff + 2);
  if (order !== "II" && order !== "MM") return 1;
  const little = order === "II";
  const u16 = (at) => (little ? buffer.readUInt16LE(at) : buffer.readUInt16BE(at));
  const u32 = (at) => (little ? buffer.readUInt32LE(at) : buffer.readUInt32BE(at));
  const end = start + length;
  const ifd = tiff + u32(tiff + 4);
  if (ifd + 2 > end) return 1;
  const entries = u16(ifd);
  for (let i = 0; i < entries; i += 1) {
    const entry = ifd + 2 + i * 12;
    if (entry + 12 > end) break;
    if (u16(entry) === 0x0112) {
      const value = u16(entry + 8);
      return value >= 1 && value <= 8 ? value : 1;
    }
  }
  return 1;
}

function jpegSize(buffer) {
  let orientation = 1;
  let at = 2;
  while (at + 4 <= buffer.length) {
    if (buffer[at] !== 0xff) {
      at += 1;
      continue;
    }
    const marker = buffer[at + 1];
    if (marker === 0xff) {
      at += 1;
      continue;
    }
    if (marker === 0xd8 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) {
      at += 2;
      continue;
    }
    if (marker === 0xd9 || marker === 0xda) break;
    const length = buffer.readUInt16BE(at + 2);
    if (marker === 0xe1) orientation = exifOrientation(buffer, at + 4, length - 2);
    if (SOF_MARKERS.has(marker) && at + 9 <= buffer.length) {
      return { height: buffer.readUInt16BE(at + 5), width: buffer.readUInt16BE(at + 7), orientation };
    }
    at += 2 + length;
  }
  return null;
}

function webpSize(buffer) {
  if (buffer.length < 30) return null;
  const chunk = buffer.toString("latin1", 12, 16);
  if (chunk === "VP8 ") {
    return { width: buffer.readUInt16LE(26) & 0x3fff, height: buffer.readUInt16LE(28) & 0x3fff, orientation: 1 };
  }
  if (chunk === "VP8L") {
    const [b0, b1, b2, b3] = buffer.subarray(21, 25);
    return {
      width: 1 + (((b1 & 0x3f) << 8) | b0),
      height: 1 + (((b3 & 0x0f) << 10) | (b2 << 2) | ((b1 & 0xc0) >> 6)),
      orientation: 1,
    };
  }
  if (chunk === "VP8X") {
    return { width: 1 + buffer.readUIntLE(24, 3), height: 1 + buffer.readUIntLE(27, 3), orientation: 1 };
  }
  return null;
}

/**
 * 画像の大きさ {format, width, height, orientation} を返す。読めなければ null。
 * width / height は向きを直したあとの大きさ (見た目どおり)。
 */
export function imageSize(buffer) {
  const format = sniffFormat(buffer);
  const size = format === "png" ? pngSize(buffer) : format === "jpeg" ? jpegSize(buffer) : format === "webp" ? webpSize(buffer) : null;
  if (!size || !size.width || !size.height) return null;
  const turned = size.orientation >= 5;
  return {
    format,
    width: turned ? size.height : size.width,
    height: turned ? size.width : size.height,
    orientation: size.orientation,
  };
}

export function imageSizeOfFile(file) {
  try {
    return imageSize(readHead(file)) ?? imageSize(readFileSync(file));
  } catch {
    return null;
  }
}
