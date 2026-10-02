#!/usr/bin/env node
// aidd-agent-kit (jp-web-design) の配色正本と部品CSS正本を assets/vendor/ へ無改変で取り込み、
// 出所とハッシュを SOURCE.json に記録する。レポートの生成・検査は assets/vendor/ だけで完結する。
// キットが要るのは、キット側の配色・部品が更新されて取り込み直すときだけ。
//
//   node scripts/sync-kit.mjs --verify                              vendor と SOURCE.json の一致だけ検査 (キット不要)
//   node scripts/sync-kit.mjs --kit <aidd-agent-kit のパス> --check  キットとの乖離だけ検査
//   node scripts/sync-kit.mjs --kit <aidd-agent-kit のパス>          取り込み(上書き)
//
// キットの置き場所は環境ごとに違うので推測しない。--kit か環境変数 AIDD_KIT_DIR で必ず指定する。
// 終了コード: 0=一致/成功 1=乖離あり 2=入力エラー
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SKILL_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const VENDOR_DIR = join(SKILL_DIR, "assets/vendor");
export const SOURCE_JSON = join(VENDOR_DIR, "SOURCE.json");

/**
 * 取り込む正本。埋め込み順もこの順 (配色トークン → 部品)。
 * kit はキットのルートからの相対パス。vendor は assets/vendor/ 内のファイル名。
 */
export const VENDOR_FILES = [
  { vendor: "hiraga-color-system.css", kit: "skills/jp-web-design/assets/hiraga/hiraga-color-system.css" },
  { vendor: "hiraga-components.css", kit: "skills/jp-web-design/assets/reference/styles.css" },
];
export const vendorPath = (f) => join(VENDOR_DIR, f.vendor);

export const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");

/** vendor の全ファイルが SOURCE.json 記録どおり(手で書き換えられていない)かを返す */
export function verifyVendor() {
  if (!existsSync(SOURCE_JSON)) return { ok: false, reason: "SOURCE.json がありません。sync-kit.mjs --kit で取り込んでください" };
  const source = JSON.parse(readFileSync(SOURCE_JSON, "utf8"));
  for (const f of VENDOR_FILES) {
    const rec = (source.files || []).find((r) => r.vendor === f.vendor);
    if (!rec) return { ok: false, reason: `SOURCE.json に ${f.vendor} の記録がありません。sync-kit.mjs --kit で取り込み直してください` };
    if (!existsSync(vendorPath(f))) return { ok: false, reason: `assets/vendor/${f.vendor} がありません` };
    const actual = sha256(readFileSync(vendorPath(f)));
    if (actual !== rec.sha256) return { ok: false, reason: `assets/vendor/${f.vendor} が改変されています (記録 ${rec.sha256.slice(0, 12)} / 実物 ${actual.slice(0, 12)})` };
  }
  return { ok: true, source };
}

function kitMeta(kitDir) {
  const version = existsSync(join(kitDir, "VERSION")) ? readFileSync(join(kitDir, "VERSION"), "utf8").trim() : "unknown";
  let commit = "unknown";
  try {
    commit = execFileSync("git", ["-C", kitDir, "log", "-1", "--format=%h", "--", "."], { encoding: "utf8" }).trim() || "unknown";
  } catch {}
  return { version, commit };
}

const colorVersion = (css) => {
  const meta = css.match(/@hiraga-meta\s+(\{.*\})/);
  return meta ? JSON.parse(meta[1]).version : undefined;
};

function main(argv) {
  const args = new Set(argv);
  if (args.has("--verify")) {
    const r = verifyVendor();
    console.log(r.ok ? `OK: vendor は SOURCE.json と一致 (kit ${r.source.kit_version} / ${VENDOR_FILES.length} ファイル)` : `NG: ${r.reason}`);
    return r.ok ? 0 : 1;
  }
  const i = argv.indexOf("--kit");
  const kitDir = i >= 0 ? argv[i + 1] : process.env.AIDD_KIT_DIR;
  if (!kitDir) {
    console.error("入力エラー: --kit <aidd-agent-kit のパス> か環境変数 AIDD_KIT_DIR でキットの場所を指定してください");
    return 2;
  }
  for (const f of VENDOR_FILES) {
    if (!existsSync(join(kitDir, f.kit))) {
      console.error(`入力エラー: ${resolve(kitDir)} に ${f.kit} がありません (aidd-agent-kit のルートを指定してください)`);
      return 2;
    }
  }
  const pairs = VENDOR_FILES.map((f) => {
    const buf = readFileSync(join(kitDir, f.kit));
    const vendorHash = existsSync(vendorPath(f)) ? sha256(readFileSync(vendorPath(f))) : null;
    return { f, buf, hash: sha256(buf), changed: sha256(buf) !== vendorHash };
  });

  if (args.has("--check")) {
    const changed = pairs.filter((p) => p.changed);
    if (!changed.length) {
      console.log("OK: キットの配色・部品の正本と一致");
      return 0;
    }
    console.log(`NG: キット側が更新されています (${changed.map((p) => p.f.kit).join(", ")})。--check を外して取り込み、selftest を通してください`);
    return 1;
  }

  const meta = kitMeta(kitDir);
  for (const p of pairs) writeFileSync(vendorPath(p.f), p.buf);
  const source = {
    kit: "aidd-agent-kit",
    kit_version: meta.version,
    kit_commit: meta.commit,
    files: pairs.map((p) => ({
      vendor: p.f.vendor,
      kit_path: p.f.kit,
      ...(colorVersion(p.buf.toString("utf8")) ? { color_version: colorVersion(p.buf.toString("utf8")) } : {}),
      sha256: p.hash,
    })),
  };
  writeFileSync(SOURCE_JSON, JSON.stringify(source, null, 2) + "\n");
  console.log(`取り込み完了: kit ${meta.version} (${meta.commit}) / ${pairs.map((p) => `${p.f.vendor}: ${p.changed ? "更新あり" : "変更なし"}`).join(" / ")}`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(main(process.argv.slice(2)));
