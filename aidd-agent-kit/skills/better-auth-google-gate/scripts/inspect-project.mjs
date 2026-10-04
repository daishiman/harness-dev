#!/usr/bin/env node
import { scanProject } from "./project-scan.mjs";

function getArg(name, fallback = null) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

const project = getArg("--project", process.cwd());
const json = process.argv.includes("--json");
const result = await scanProject(project);

if (json) {
  console.log(JSON.stringify(result, null, 2));
  process.exit(0);
}

const mark = (value) => value ? "✓" : "−";
console.log("Better Auth Google Gate: プロジェクト調査");
console.log(`対象: ${result.root}`);
console.log(`構成: ${result.framework} / ${result.packageManager}`);
console.log(`Next.js: ${result.versions.next ?? "未検出"}`);
console.log(`Better Auth: ${result.versions.betterAuth ?? "未検出"}`);
console.log(`OpenNext: ${result.versions.openNext ?? "未検出"}`);
console.log(`Wrangler: ${result.wranglerFile ?? "未検出"}`);
console.log(`D1: ${mark(result.d1.configured)} ${result.d1.databaseName ?? "未設定"} (${result.d1.binding ?? "binding未設定"})`);
console.log(`本番origin: ${result.productionOrigin ?? "未設定"}`);
console.log(`認証コード: ${mark(result.signals.betterAuth)} ${result.authFiles.length ? result.authFiles.join(", ") : "未検出"}`);
console.log(`Google provider / hd: ${mark(result.signals.googleProvider)} / ${mark(result.signals.hostedDomain)}`);
console.log(`サーバーsession検証: ${mark(result.signals.serverSession)}`);
console.log(`Secretキー名（値は非表示）: ${result.envKeys.length ? result.envKeys.join(", ") : "未検出"}`);

if (result.signals.betterAuth) {
  console.log("推奨経路: 既存認証を上書きせず、readiness監査から開始");
} else if (result.framework === "nextjs" && result.versions.openNext && result.d1.configured) {
  console.log("推奨経路: references/nextjs-opennext-d1.md");
} else if (["hono", "cloudflare-worker"].includes(result.framework)) {
  console.log("推奨経路: references/hono-workers-d1.md");
} else {
  console.log("推奨経路: Cloudflareデプロイ方式とDBを確認してから実装");
}
