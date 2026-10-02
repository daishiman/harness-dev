#!/usr/bin/env node
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

function arg(name, fallback = null) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

const appName = arg("--app-name");
const productionOriginInput = arg("--production-origin");
const workspaceDomain = arg("--workspace-domain");
const localOriginInput = arg("--local-origin", "http://localhost:3000");
const cloudflareTarget = arg("--cloudflare-target", "workers");
const cloudflareProjectName = arg("--cloudflare-project-name");
const cloudflareEnvironment = arg("--cloudflare-env");
const workerName = arg("--worker-name");
const output = path.resolve(arg("--output", "auth-google-setup.md"));

if (!appName || !productionOriginInput || !workspaceDomain) {
  console.error("必須: --app-name --production-origin --workspace-domain");
  process.exit(2);
}
if (!/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(workspaceDomain)) {
  console.error("--workspace-domain の形式が不正です");
  process.exit(2);
}
if (!["workers", "pages"].includes(cloudflareTarget)) {
  console.error("--cloudflare-target は workers または pages を指定してください");
  process.exit(2);
}
if (cloudflareTarget === "pages" && !cloudflareProjectName) {
  console.error("Pagesでは --cloudflare-project-name が必須です");
  process.exit(2);
}

function normalizeOrigin(value, label) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`${label}は完全なURLで指定してください`);
  }
  if (!["http:", "https:"].includes(url.protocol) || url.pathname !== "/" || url.search || url.hash) {
    throw new Error(`${label}はパス・query・hashなしのoriginで指定してください`);
  }
  return url.origin;
}

let productionOrigin;
let localOrigin;
try {
  productionOrigin = normalizeOrigin(productionOriginInput, "--production-origin");
  localOrigin = normalizeOrigin(localOriginInput, "--local-origin");
} catch (error) {
  console.error(error.message);
  process.exit(2);
}

const localCallback = `${localOrigin}/api/auth/callback/google`;
const productionCallback = `${productionOrigin}/api/auth/callback/google`;
const projectRoot = path.dirname(output);
const templatePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../assets/google-cloud-beginner-guide.md.template",
);
let markdown = await readFile(templatePath, "utf8");
const replacements = {
  __APP_NAME__: appName,
  __WORKSPACE_DOMAIN__: workspaceDomain,
  __LOCAL_ORIGIN__: localOrigin,
  __PRODUCTION_ORIGIN__: productionOrigin,
  __LOCAL_CALLBACK__: localCallback,
  __PRODUCTION_CALLBACK__: productionCallback,
  __SIGN_IN_URL__: `${productionOrigin}/sign-in`,
};
for (const [token, value] of Object.entries(replacements)) {
  markdown = markdown.split(token).join(value);
}

await writeFile(output, markdown, { encoding: "utf8", mode: 0o644 });

const helperTemplatePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../assets/setup-secrets.mjs.template",
);
let helper = await readFile(helperTemplatePath, "utf8");
const cloudflareArgs = [];
if (cloudflareTarget === "pages") cloudflareArgs.push("--project-name", cloudflareProjectName);
if (cloudflareTarget === "workers" && workerName) cloudflareArgs.push("--name", workerName);
if (cloudflareEnvironment) cloudflareArgs.push("--env", cloudflareEnvironment);
const helperReplacements = {
  __LOCAL_ORIGIN_JSON__: JSON.stringify(localOrigin),
  __CLOUDFLARE_TARGET_JSON__: JSON.stringify(cloudflareTarget),
  __CLOUDFLARE_ARGS_JSON__: JSON.stringify(cloudflareArgs),
};
for (const [token, value] of Object.entries(helperReplacements)) {
  helper = helper.split(token).join(value);
}
const helperDirectory = path.join(projectRoot, ".better-auth-google");
await mkdir(helperDirectory, { recursive: true });
await writeFile(path.join(helperDirectory, "setup-secrets.mjs"), helper, { encoding: "utf8", mode: 0o700 });
console.log(`初心者向け案内書を生成しました: ${output}`);
console.log(`安全な入力コマンドを生成しました: ${path.join(helperDirectory, "setup-secrets.mjs")}`);
console.log(`開発Redirect URI: ${localCallback}`);
console.log(`本番Redirect URI: ${productionCallback}`);
