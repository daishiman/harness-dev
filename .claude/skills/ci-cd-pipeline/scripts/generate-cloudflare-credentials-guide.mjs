#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));

function arg(name, fallback = null) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

function has(name) {
  return process.argv.includes(name);
}

async function exists(file) {
  try {
    await access(file);
    return true;
  } catch {
    return false;
  }
}

function fail(message) {
  console.error(`エラー: ${message}`);
  process.exit(2);
}

function run(command, args, cwd = process.cwd()) {
  try {
    return execFileSync(command, args, {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return null;
  }
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function matches(content, pattern) {
  return unique([...content.matchAll(pattern)].map((match) => match[1]));
}

function stopAuto(reason, facts = []) {
  console.error("自動検出を安全に完了できないため、生成していません。");
  console.error(`停止理由: ${reason}`);
  for (const fact of facts) console.error(`- ${fact}`);
  process.exit(2);
}

async function autoDetect() {
  const detector = path.join(scriptDirectory, "detect-github-repository.mjs");
  const detectedText = run(process.execPath, [detector]);
  let github;
  try {
    github = JSON.parse(detectedText || "null");
  } catch {
    stopAuto("GitHub対象の検出結果を解釈できませんでした。");
  }
  if (github?.status !== "ok") {
    stopAuto("GitHub対象が一意ではありません。", [
      `status=${github?.status || "unknown"}`,
      github?.reason ? `reason=${github.reason}` : null,
      github?.safe_question || null,
    ].filter(Boolean));
  }

  const tracked = (run("git", ["ls-files", "--cached", "--others", "--exclude-standard"]) || "")
    .split(/\r?\n/)
    .filter(Boolean);
  const wranglerFiles = tracked.filter((file) => /(^|\/)wrangler\.(?:jsonc?|toml)$/.test(file));
  const requestedConfig = arg("--wrangler-config");
  let wranglerFile;
  if (requestedConfig) {
    const normalized = path.relative(process.cwd(), path.resolve(requestedConfig)).split(path.sep).join("/");
    if (!wranglerFiles.includes(normalized)) {
      stopAuto("--wrangler-configがgit管理対象のWrangler設定ではありません。", [`指定=${normalized}`]);
    }
    wranglerFile = normalized;
  } else if (wranglerFiles.length === 1) {
    [wranglerFile] = wranglerFiles;
  } else {
    stopAuto(wranglerFiles.length
      ? "Wrangler設定が複数あります。対象を--wrangler-configで1つ指定してください。"
      : "Wrangler設定が見つかりません。", wranglerFiles.map((file) => `候補=${file}`));
  }

  const wranglerContent = await readFile(path.resolve(wranglerFile), "utf8");
  const workerNames = matches(wranglerContent, /(?:^|[,\n]\s*)["']?name["']?\s*[:=]\s*["']([^"']+)["']/gm);
  const d1Names = matches(wranglerContent, /["']?database_name["']?\s*[:=]\s*["']([^"']+)["']/g);
  const r2Names = matches(wranglerContent, /["']?bucket_name["']?\s*[:=]\s*["']([^"']+)["']/g);
  const localAppUrls = matches(wranglerContent, /["']?APP_URL["']?\s*[:=]\s*["'](https:\/\/[^"']+)["']/g);

  if (!arg("--worker") && workerNames.length !== 1) {
    stopAuto("Worker名が一意ではありません。--workerで対象を指定してください。", workerNames.map((name) => `候補=${name}`));
  }
  if (!arg("--d1") && d1Names.length > 1) {
    stopAuto("D1が複数あります。--d1で対象を指定してください。", d1Names.map((name) => `候補=${name}`));
  }
  if (!arg("--r2") && r2Names.length > 1) {
    stopAuto("R2 bucketが複数あります。--r2で対象を指定してください。", r2Names.map((name) => `候補=${name}`));
  }

  const configDirectory = path.dirname(path.resolve(wranglerFile));
  const gitRoot = run("git", ["rev-parse", "--show-toplevel"]);
  const lockfiles = [
    { file: "pnpm-lock.yaml", manager: "pnpm" },
    { file: "yarn.lock", manager: "yarn" },
    { file: "package-lock.json", manager: "npm" },
    { file: "npm-shrinkwrap.json", manager: "npm" },
  ];
  let directory = configDirectory;
  let packageManager = null;
  let lockfileDirectory = null;
  while (gitRoot && directory.startsWith(gitRoot)) {
    const found = [];
    for (const candidate of lockfiles) {
      if (await exists(path.join(directory, candidate.file))) found.push(candidate);
    }
    const managers = unique(found.map((candidate) => candidate.manager));
    if (managers.length > 1) {
      stopAuto("同じ階層に複数種類のlockfileがあります。不要なlockfileを整理してください。", found.map((item) => `検出=${path.join(directory, item.file)}`));
    }
    if (found.length) {
      [packageManager] = found;
      lockfileDirectory = directory;
      break;
    }
    if (directory === gitRoot) break;
    directory = path.dirname(directory);
  }
  if (!arg("--wrangler-command-json") && !packageManager) {
    stopAuto("lockfileからpackage managerを特定できません。--wrangler-command-jsonを指定してください。");
  }

  const configRelative = path.relative(gitRoot, configDirectory).split(path.sep).join("/");
  const inSubdirectory = configRelative && configRelative !== ".";
  const installRelative = path.relative(gitRoot, lockfileDirectory || gitRoot).split(path.sep).join("/");
  const installInSubdirectory = installRelative && installRelative !== ".";
  const yarnBerry = packageManager?.manager === "yarn"
    && await exists(path.join(lockfileDirectory || gitRoot, ".yarnrc.yml"));
  const packageCommands = packageManager && {
    pnpm: {
      wrangler: ["pnpm", ...(inSubdirectory ? ["--dir", configRelative] : []), "exec", "wrangler"],
      install: ["pnpm", ...(installInSubdirectory ? ["--dir", installRelative] : []), "install", "--force", "--frozen-lockfile"],
    },
    npm: {
      wrangler: ["npm", ...(inSubdirectory ? ["--prefix", configRelative] : []), "exec", "--", "wrangler"],
      install: ["npm", ...(installInSubdirectory ? ["--prefix", installRelative] : []), "ci"],
    },
    yarn: {
      wrangler: ["yarn", ...(inSubdirectory ? ["--cwd", configRelative] : []), "exec", "wrangler"],
      install: [
        "yarn",
        ...(installInSubdirectory ? ["--cwd", installRelative] : []),
        "install",
        yarnBerry ? "--immutable" : "--frozen-lockfile",
      ],
    },
  }[packageManager.manager];

  const repository = github.recommended.repository;
  const githubAppUrl = run("gh", ["variable", "get", "APP_URL", "--repo", repository]);
  const appUrls = unique([...localAppUrls, githubAppUrl]);
  if (!arg("--app-url") && appUrls.length !== 1) {
    stopAuto(appUrls.length
      ? "Wrangler設定とGitHub Repository variableのAPP_URLが一致しません。--app-urlで正しい値を指定してください。"
      : "既存APP_URLが見つかりません。--app-urlで本番URLを指定してください。", appUrls.map((url) => `候補=${url}`));
  }

  let packageName = null;
  for (const packageFile of [path.join(configDirectory, "package.json"), path.join(gitRoot || "", "package.json")]) {
    if (!(await exists(packageFile))) continue;
    try {
      const parsed = JSON.parse(await readFile(packageFile, "utf8"));
      if (typeof parsed.name === "string" && parsed.name) {
        packageName = parsed.name.replace(/^@[^/]+\//, "");
        break;
      }
    } catch {}
  }

  return {
    appName: packageName || github.recommended.name,
    repo: repository,
    branch: github.recommended.default_branch,
    worker: workerNames[0] || null,
    d1: d1Names[0] || null,
    r2: r2Names[0] || null,
    appUrl: appUrls[0] || null,
    wranglerCommand: packageCommands?.wrangler || null,
    installCommand: packageCommands?.install || null,
    lockfileDirectory: installRelative || ".",
    yarnGeneration: packageManager?.manager === "yarn" ? (yarnBerry ? "berry" : "classic") : null,
    wranglerFile,
  };
}

function requireSimple(value, label, pattern) {
  if (!value || !pattern.test(value)) fail(`${label}の形式が不正です。`);
  return value;
}

function normalizeOrigin(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    fail("--app-urlはhttps://から始まる本番URLで指定してください。");
  }
  if (url.protocol !== "https:" || url.pathname !== "/" || url.search || url.hash) {
    fail("--app-urlはpath・query・hashなしのhttps originで指定してください。");
  }
  return url.origin;
}

function shellJoin(parts) {
  return parts.map((part) => (/^[A-Za-z0-9@%_+=:,./-]+$/.test(part)
    ? part
    : `'${part.replaceAll("'", `'\\''`)}'`)).join(" ");
}

function javascriptLiteral(value) {
  if (value === null) return "null";
  if (Array.isArray(value)) return `[${value.map(javascriptLiteral).join(", ")}]`;
  if (typeof value !== "string") fail("helperへ埋め込む値の形式が不正です。");
  return `'${value
    .replaceAll("\\", "\\\\")
    .replaceAll("'", "\\'")
    .replaceAll("\r", "\\r")
    .replaceAll("\n", "\\n")
    .replaceAll("\u2028", "\\u2028")
    .replaceAll("\u2029", "\\u2029")}'`;
}

const auto = has("--auto") || process.argv.length === 2;
const discovered = auto ? await autoDetect() : {};
if (auto) {
  console.log(JSON.stringify({
    status: "detected",
    recommended: {
      repository: discovered.repo,
      default_branch: discovered.branch,
      wrangler_config: discovered.wranglerFile,
      worker: discovered.worker,
      d1: discovered.d1,
      r2: discovered.r2,
      app_url: discovered.appUrl,
      wrangler_command: discovered.wranglerCommand,
      install_command: discovered.installCommand,
      lockfile_directory: discovered.lockfileDirectory,
      yarn_generation: discovered.yarnGeneration,
      account_mode: arg("--account-mode", "team"),
    },
  }, null, 2));
}
const appName = arg("--app-name", discovered.appName);
const repo = requireSimple(arg("--repo", discovered.repo), "--repo", /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/);
const environment = requireSimple(arg("--environment", "production"), "--environment", /^[A-Za-z0-9_.-]+$/);
const branch = requireSimple(arg("--branch", discovered.branch || "main"), "--branch", /^[A-Za-z0-9_./-]+$/);
const worker = requireSimple(arg("--worker", discovered.worker), "--worker", /^[a-z0-9][a-z0-9-]*$/);
const d1 = arg("--d1", discovered.d1);
const r2 = arg("--r2", discovered.r2);
const appUrl = normalizeOrigin(arg("--app-url", discovered.appUrl));
const accountName = arg("--account-name");
// A Wrangler config proves the intended resource names, not that those resources
// already exist in a particular Account.  New projects therefore stay on the
// team default.  The orchestrating agent passes `existing` only after a
// read-only Cloudflare ownership check has succeeded.
const accountMode = arg("--account-mode", "team");
const authPassword = arg("--auth-password-secret");
const sessionSecret = arg("--session-secret");
const output = path.resolve(arg("--output", "docs/cloudflare-credentials-setup.md"));
const helperOutput = path.resolve(arg("--helper-output", ".cloudflare/setup-production.mjs"));
const force = has("--force");

if (!appName) fail("--app-nameは必須です。");
if (!accountName) {
  stopAuto("Cloudflare Account名はローカル設定から安全に確定できません。", [
    "対象Accountを画面で確認し、--account-nameで表示名だけを指定してください。",
    "Account IDやTokenは指定・共有しないでください。",
  ]);
}
if (d1) requireSimple(d1, "--d1", /^[a-z0-9][a-z0-9-]*$/);
if (r2) requireSimple(r2, "--r2", /^[a-z0-9][a-z0-9-]*$/);
if (authPassword) requireSimple(authPassword, "--auth-password-secret", /^[A-Z][A-Z0-9_]*$/);
if (sessionSecret) requireSimple(sessionSecret, "--session-secret", /^[A-Z][A-Z0-9_]*$/);
if (!["team", "personal", "existing"].includes(accountMode)) fail("--account-modeはteam、personal、existingのいずれかです。");
if (accountMode === "personal" && !has("--allow-personal-account")) {
  fail("個人Accountは既定外です。利用者が明示指定した場合だけ--allow-personal-accountを付けてください。");
}

let wranglerCommand;
try {
  wranglerCommand = JSON.parse(arg(
    "--wrangler-command-json",
    JSON.stringify(discovered.wranglerCommand || ["pnpm", "exec", "wrangler"]),
  ));
} catch {
  fail("--wrangler-command-jsonはJSON配列で指定してください。");
}
if (!Array.isArray(wranglerCommand) || wranglerCommand.length < 2 || wranglerCommand.some((item) => typeof item !== "string" || !item)) {
  fail("--wrangler-command-jsonは空でない文字列のJSON配列にしてください。");
}
if (wranglerCommand.at(-1) !== "wrangler") fail("Wranglerコマンド配列の末尾はwranglerにしてください。");

let installCommand = discovered.installCommand;
const installCommandJson = arg("--install-command-json");
if (installCommandJson) {
  try {
    installCommand = JSON.parse(installCommandJson);
  } catch {
    fail("--install-command-jsonはJSON配列で指定してください。");
  }
}
if (!installCommand) {
  installCommand = wranglerCommand[0] === "npm" || wranglerCommand[0] === "npx"
    ? ["npm", "ci"]
    : wranglerCommand[0] === "yarn"
      ? ["yarn", "install", await exists(".yarnrc.yml") ? "--immutable" : "--frozen-lockfile"]
      : ["pnpm", "install", "--force", "--frozen-lockfile"];
}
if (!Array.isArray(installCommand) || installCommand.length < 2 || installCommand.some((item) => typeof item !== "string" || !item)) {
  fail("--install-command-jsonは空でない文字列のJSON配列にしてください。");
}

if (!force && ((await exists(output)) || (await exists(helperOutput)))) {
  fail("出力先が既にあります。AIが差分を確認した後だけ--forceを付けて更新してください。");
}

const permissionKeys = [
  { key: "account_settings", type: "read" },
  { key: "workers_scripts", type: "edit" },
];
if (d1) permissionKeys.push({ key: "d1", type: "edit" });
if (r2) permissionKeys.push({ key: "workers_r2", type: "edit" });
const tokenName = `${worker}-github-actions-${environment}`;
const tokenTemplateUrl = new URL("https://dash.cloudflare.com/");
tokenTemplateUrl.searchParams.set("to", "/:account/api-tokens");
tokenTemplateUrl.searchParams.set("permissionGroupKeys", JSON.stringify(permissionKeys));
tokenTemplateUrl.searchParams.set("name", tokenName);

const template = await readFile(path.resolve(scriptDirectory, "../assets/cloudflare-credentials-guide.md.template"), "utf8");
const helperTemplate = await readFile(path.resolve(scriptDirectory, "../assets/setup-cloudflare-production.template.mjs"), "utf8");
const helperRelative = path.relative(process.cwd(), helperOutput).split(path.sep).join("/");

const conditions = {
  TEAM: accountMode === "team",
  PERSONAL: accountMode === "personal",
  EXISTING: accountMode === "existing",
  D1: Boolean(d1),
  R2: Boolean(r2),
  AUTH_PASSWORD: Boolean(authPassword),
  SESSION_SECRET: Boolean(sessionSecret),
};
let markdown = template.replace(
  /<!-- IF_([A-Z0-9_]+) -->([\s\S]*?)<!-- END_IF_\1 -->/g,
  (_, name, content) => conditions[name] ? content : "",
);
const replacements = {
  __APP_NAME__: appName,
  __REPO__: repo,
  __ENVIRONMENT__: environment,
  __BRANCH__: branch,
  __ACCOUNT_NAME__: accountName,
  __WORKER__: worker,
  __D1__: d1 || "未使用",
  __R2__: r2 || "未使用",
  __APP_URL__: appUrl,
  __WRANGLER__: shellJoin(wranglerCommand),
  __INSTALL_COMMAND__: shellJoin(installCommand),
  __AUTH_PASSWORD__: authPassword || "AUTH_PASSWORD",
  __SESSION_SECRET__: sessionSecret || "SESSION_SECRET",
  __TOKEN_TEMPLATE_URL__: tokenTemplateUrl.toString(),
  __TOKEN_NAME__: tokenName,
  __HELPER_COMMAND__: `node ${shellJoin([helperRelative])}`,
};
for (const [token, value] of Object.entries(replacements)) {
  markdown = markdown.split(token).join(value);
}
const unresolvedGuide = markdown.match(/__[A-Z0-9_]+__|<!-- (?:IF|END_IF)_[A-Z0-9_]+ -->/);
if (unresolvedGuide) fail(`ガイドに未解決placeholderがあります: ${unresolvedGuide[0]}`);

let helper = helperTemplate;
const helperReplacements = {
  __REPO_JSON__: javascriptLiteral(repo),
  __ENVIRONMENT_JSON__: javascriptLiteral(environment),
  __BRANCH_JSON__: javascriptLiteral(branch),
  __ACCOUNT_NAME_JSON__: javascriptLiteral(accountName),
  __ACCOUNT_MODE_JSON__: javascriptLiteral(accountMode),
  __APP_URL_JSON__: javascriptLiteral(appUrl),
  __WRANGLER_COMMAND_JSON__: javascriptLiteral(wranglerCommand),
  __AUTH_PASSWORD_JSON__: javascriptLiteral(authPassword),
  __SESSION_SECRET_JSON__: javascriptLiteral(sessionSecret),
};
for (const [token, value] of Object.entries(helperReplacements)) {
  helper = helper.split(token).join(value);
}
const unresolvedHelper = helper.match(/__[A-Z0-9_]+__/);
if (unresolvedHelper) fail(`helperに未解決placeholderがあります: ${unresolvedHelper[0]}`);

await mkdir(path.dirname(output), { recursive: true });
await mkdir(path.dirname(helperOutput), { recursive: true });
await writeFile(output, markdown, { encoding: "utf8", mode: 0o644 });
await writeFile(helperOutput, helper, { encoding: "utf8", mode: 0o700 });

console.log(`✓ 非エンジニア向け手順書: ${output}`);
console.log(`✓ 秘密値を表示しない登録helper: ${helperOutput}`);
if (auto) console.log(`✓ 自動検出: ${repo} / ${branch} / ${discovered.wranglerFile}`);
console.log(`次に所有者が実行: node ${helperRelative}`);
