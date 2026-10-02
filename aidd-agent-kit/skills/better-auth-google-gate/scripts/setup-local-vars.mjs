#!/usr/bin/env node
import { randomBytes } from "node:crypto";
import { access, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

function arg(name, fallback = null) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

async function exists(file) {
  try { await access(file); return true; } catch { return false; }
}

const project = path.resolve(arg("--project", process.cwd()));
const localOriginInput = arg("--local-origin", "http://localhost:3000");
const dryRun = process.argv.includes("--dry-run");
let localOrigin;
try {
  const url = new URL(localOriginInput);
  if (url.origin !== localOriginInput || url.pathname !== "/") throw new Error();
  localOrigin = url.origin;
} catch {
  console.error("--local-originはパスなしの完全なoriginで指定してください");
  process.exit(2);
}

const target = path.join(project, ".dev.vars");
if (await exists(target)) {
  console.log(`既存の.dev.varsは変更しません: ${target}`);
  process.exit(0);
}
for (const envName of [".env", ".env.local"]) {
  if (await exists(path.join(project, envName))) {
    console.error(`${envName}が存在します。.dev.varsとの併用を避けるため中止しました。`);
    process.exit(3);
  }
}

let gitignore = "";
try { gitignore = await readFile(path.join(project, ".gitignore"), "utf8"); } catch {}
if (!/(^|\n)\s*\.dev\.vars(?:\.\*|\s|$)/m.test(gitignore)) {
  console.error(".gitignoreに.dev.varsがないため中止しました。先にGit除外を追加してください。");
  process.exit(3);
}
if (dryRun) {
  console.log(`[dry-run] ${target}をmode 600で新規作成し、local secretを自動生成します。値は表示しません。`);
  process.exit(0);
}

const secret = randomBytes(48).toString("base64url");
const content = [
  `BETTER_AUTH_SECRET=${secret}`,
  `BETTER_AUTH_URL=${localOrigin}`,
  "GOOGLE_CLIENT_ID=",
  "GOOGLE_CLIENT_SECRET=",
  "",
].join("\n");
await writeFile(target, content, { encoding: "utf8", mode: 0o600, flag: "wx" });
console.log(`ローカル認証設定を作成しました: ${target}`);
console.log("BETTER_AUTH_SECRETは自動生成済みです。値は表示していません。");
console.log("次にsetup-google-local-secrets.shをTerminalから実行し、Googleの2項目を非表示入力してください。");
