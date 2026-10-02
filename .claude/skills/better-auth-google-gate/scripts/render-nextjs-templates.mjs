#!/usr/bin/env node
import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

function arg(name, fallback = null) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

const output = path.resolve(arg("--output", "auth-scaffold"));
const values = {
  __APP_NAME__: arg("--app-name"),
  __WORKSPACE_DOMAIN__: arg("--workspace-domain"),
  __LOCAL_ORIGIN__: arg("--local-origin", "http://localhost:3000"),
  __PRODUCTION_ORIGIN__: arg("--production-origin"),
  __D1_DATABASE_NAME__: arg("--d1-name"),
  __D1_DATABASE_ID__: arg("--d1-id"),
};

const missing = Object.entries(values).filter(([, value]) => !value).map(([key]) => key);
if (missing.length) {
  console.error(`必須引数が不足しています: ${missing.join(", ")}`);
  process.exit(2);
}

for (const key of ["__LOCAL_ORIGIN__", "__PRODUCTION_ORIGIN__"]) {
  try {
    const url = new URL(values[key]);
    if (url.origin !== values[key] || url.pathname !== "/") throw new Error();
  } catch {
    console.error(`${key}はパスなしの完全なoriginで指定してください`);
    process.exit(2);
  }
}

const assetRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../assets/nextjs-opennext-d1");
const files = new Map([
  ["auth.ts.template", "src/lib/auth.ts"],
  ["auth.cli.ts.template", "src/auth.cli.ts"],
  ["cf-runtime.ts.template", "src/lib/cf-runtime.ts"],
  ["auth-route.ts.template", "src/app/api/auth/[...all]/route.ts"],
  ["auth-client.ts.template", "src/lib/auth-client.ts"],
  ["google-sign-in-button.tsx.template", "src/components/GoogleSignInButton.tsx"],
  ["sign-in-page.tsx.template", "src/app/sign-in/page.tsx"],
  ["drizzle.config.ts.template", "drizzle.config.ts"],
  ["dev.vars.example", ".dev.vars.example"],
  ["wrangler.auth.fragment.jsonc", "wrangler.auth.fragment.jsonc"],
]);

const destinations = [...files.values()].map((relative) => path.join(output, relative));
for (const destination of destinations) {
  try {
    await access(destination);
    console.error(`既存ファイルがあるため中止しました: ${destination}`);
    console.error("既存認証は上書きせず、inspect-projectと差分監査を使ってください。");
    process.exit(3);
  } catch {
    // File does not exist. Safe to continue.
  }
}

for (const [sourceName, relativeDestination] of files) {
  const source = path.join(assetRoot, sourceName);
  const destination = path.join(output, relativeDestination);
  let content = await readFile(source, "utf8");
  for (const [token, value] of Object.entries(values)) {
    content = content.split(token).join(value);
  }
  await mkdir(path.dirname(destination), { recursive: true });
  await writeFile(destination, content, { encoding: "utf8", mode: 0o644, flag: "wx" });
  console.log(`作成: ${destination}`);
}

console.log("テンプレート生成完了。wrangler.auth.fragment.jsoncは既存wrangler設定へ安全に統合してください。");
