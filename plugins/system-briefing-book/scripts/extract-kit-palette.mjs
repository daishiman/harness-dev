#!/usr/bin/env node
/**
 * extract-kit-palette — 既定の配色 (standard) の正本を aidd-agent-kit の jp-web-design から取り出し、
 * assets/css/vendor/ へ 1 バイトも変えずに写す。出所とハッシュは assets/css/vendor/SOURCE.json に書く。
 * 資料を作るときはキットが要らない (vendor の写しだけで完結する)。キットが要るのは、キットの配色が
 * 更新されて取り込み直すときだけ。
 *
 * 使い方:
 *   node scripts/extract-kit-palette.mjs --verify                 写しが SOURCE.json の記録どおりかだけ見る (キット不要)
 *   node scripts/extract-kit-palette.mjs --kit <キットのルート> --check   キットの正本と写しが同じかだけ見る
 *   node scripts/extract-kit-palette.mjs --kit <キットのルート>           取り込む (写しと SOURCE.json を上書き)
 *
 * キットの置き場所は環境ごとに違うので推測しない。--kit か環境変数 AIDD_KIT_DIR で指定する。
 * stdout: JSON {status, command, ...} (--quiet で要約 1 行)
 * exit: 0=一致・取り込み済み / 1=違いがある / 2=使い方の誤り / 3=Node が古い
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { PALETTE_SOURCE, STANDARD_PALETTE, VENDOR_DIR, colorVersion, verifyVendor } from "./lib/palette.mjs";
import { sha256, toPosix } from "./lib/briefing-files.mjs";
import { EXIT, UsageError, emitResult, isEntryPoint, parseOptions, runCli } from "./lib/cli-contract.mjs";

const USAGE = `
extract-kit-palette.mjs --verify [--quiet]
extract-kit-palette.mjs --kit <aidd-agent-kit のルート> [--check] [--quiet]
`;

function kitMeta(kitDir) {
  const versionFile = path.join(kitDir, "VERSION");
  const version = existsSync(versionFile) ? readFileSync(versionFile, "utf8").trim() : "unknown";
  let commit = "unknown";
  try {
    commit = execFileSync("git", ["-C", kitDir, "log", "-1", "--format=%h", "--", "."], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim() || "unknown";
  } catch {
    // git でないフォルダから取り込むときは unknown のまま
  }
  return { version, commit };
}

export function main(argv) {
  const { options } = parseOptions(argv, { verify: "boolean", kit: "string", check: "boolean", quiet: "boolean" });
  if (options.verify) {
    const r = verifyVendor();
    const result = { status: r.ok ? "ok" : "ng", command: "verify", ...(r.ok ? {} : { reason: r.reason }), kit_version: r.source?.kit_version, color_version: r.source?.color_version };
    emitResult(result, options.quiet ? `verify: ${result.status}${r.ok ? "" : ` ${r.reason}`}` : null);
    return r.ok ? EXIT.OK : EXIT.FOUND;
  }

  const kitDir = options.kit ?? process.env.AIDD_KIT_DIR;
  if (!kitDir) throw new UsageError("--verify か、--kit <aidd-agent-kit のルート> (または環境変数 AIDD_KIT_DIR) を指定してください");
  const kitFile = path.join(kitDir, STANDARD_PALETTE.kit);
  if (!existsSync(kitFile)) throw new UsageError(`${path.resolve(kitDir)} に ${STANDARD_PALETTE.kit} がありません (aidd-agent-kit のルートを指定してください)`);
  const buf = readFileSync(kitFile);
  const hash = sha256(buf);
  const vendorHash = existsSync(STANDARD_PALETTE.vendor) ? sha256(readFileSync(STANDARD_PALETTE.vendor)) : null;
  const same = hash === vendorHash;

  if (options.check) {
    const result = { status: same ? "ok" : "ng", command: "check", kit_path: STANDARD_PALETTE.kit, kit_sha256: hash, vendor_sha256: vendorHash };
    if (!same) result.reason = "キットの配色が更新されています。--check を外して取り込み、テストを通してください";
    emitResult(result, options.quiet ? `check: ${result.status}` : null);
    return same ? EXIT.OK : EXIT.FOUND;
  }

  const meta = kitMeta(kitDir);
  const source = {
    kit: "aidd-agent-kit",
    kit_version: meta.version,
    kit_commit: meta.commit,
    kit_path: STANDARD_PALETTE.kit,
    vendor: toPosix(path.relative(VENDOR_DIR, STANDARD_PALETTE.vendor)),
    color_version: colorVersion(buf.toString("utf8")) ?? null,
    sha256: hash,
  };
  mkdirSync(VENDOR_DIR, { recursive: true });
  writeFileSync(STANDARD_PALETTE.vendor, buf);
  writeFileSync(PALETTE_SOURCE, `${JSON.stringify(source, null, 2)}\n`);
  const result = { status: "ok", command: "extract", changed: !same, ...source };
  emitResult(result, options.quiet ? `extract: ok ${same ? "変更なし" : "更新あり"} (kit ${meta.version} / ${meta.commit})` : null);
  return EXIT.OK;
}

if (isEntryPoint(import.meta.url)) {
  runCli(main, USAGE);
}
