import { access, readFile, readdir } from "node:fs/promises";
import path from "node:path";

const SOURCE_EXTENSIONS = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]);
const SKIP_DIRS = new Set([
  ".git",
  ".next",
  ".open-next",
  ".wrangler",
  "dist",
  "build",
  "coverage",
  "node_modules",
]);

async function exists(file) {
  try {
    await access(file);
    return true;
  } catch {
    return false;
  }
}

async function readText(file) {
  try {
    return await readFile(file, "utf8");
  } catch {
    return "";
  }
}

async function walk(dir, output, depth = 0) {
  if (depth > 8) return;
  let entries = [];
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      await walk(full, output, depth + 1);
    } else if (SOURCE_EXTENSIONS.has(path.extname(entry.name))) {
      output.push(full);
    }
  }
}

function parseEnvKeys(text) {
  const keys = new Set();
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=/);
    if (match) keys.add(match[1]);
  }
  return [...keys].sort();
}

function firstMatch(text, expression) {
  return text.match(expression)?.[1] ?? null;
}

export async function scanProject(inputRoot) {
  const root = path.resolve(inputRoot);
  const packageFile = path.join(root, "package.json");
  const packageText = await readText(packageFile);
  let pkg = {};
  try {
    pkg = packageText ? JSON.parse(packageText) : {};
  } catch {
    pkg = {};
  }
  const deps = { ...(pkg.dependencies ?? {}), ...(pkg.devDependencies ?? {}) };

  const locks = {
    npm: await exists(path.join(root, "package-lock.json")),
    pnpm: await exists(path.join(root, "pnpm-lock.yaml")),
    yarn: await exists(path.join(root, "yarn.lock")),
    bun: await exists(path.join(root, "bun.lockb")) || await exists(path.join(root, "bun.lock")),
  };
  const packageManager = Object.entries(locks).find(([, present]) => present)?.[0] ?? "npm";

  const wranglerCandidates = ["wrangler.jsonc", "wrangler.json", "wrangler.toml"];
  let wranglerName = null;
  for (const name of wranglerCandidates) {
    if (await exists(path.join(root, name))) {
      wranglerName = name;
      break;
    }
  }
  const wranglerPath = wranglerName ? path.join(root, wranglerName) : null;
  const wranglerText = wranglerPath ? await readText(wranglerPath) : "";

  const sourceFiles = [];
  for (const sourceRoot of ["src", "app", "lib", "server"].map((dir) => path.join(root, dir))) {
    if (await exists(sourceRoot)) await walk(sourceRoot, sourceFiles);
  }
  let sourceText = "";
  const matchedFiles = [];
  for (const file of [...new Set(sourceFiles)]) {
    const text = await readText(file);
    if (/betterAuth|createAuthClient|signIn\.social|api\.getSession|auth\.handler|toNextJsHandler/.test(text)) {
      matchedFiles.push(path.relative(root, file));
      sourceText += `\n${text}`;
    }
  }

  const migrationDir = path.join(root, "migrations");
  let migrationText = "";
  if (await exists(migrationDir)) {
    let entries = [];
    try {
      entries = await readdir(migrationDir, { withFileTypes: true });
    } catch {
      entries = [];
    }
    for (const entry of entries) {
      if (entry.isFile() && entry.name.endsWith(".sql")) {
        migrationText += `\n${await readText(path.join(migrationDir, entry.name))}`;
      }
    }
  }

  const envFiles = [];
  const envKeys = new Set();
  for (const name of [".dev.vars", ".env", ".env.local", ".dev.vars.example", ".env.example"]) {
    const file = path.join(root, name);
    if (!(await exists(file))) continue;
    envFiles.push(name);
    for (const key of parseEnvKeys(await readText(file))) envKeys.add(key);
  }

  const gitignore = await readText(path.join(root, ".gitignore"));
  const framework = deps.next ? "nextjs" : deps.hono ? "hono" : wranglerPath ? "cloudflare-worker" : "unknown";
  const d1Section = wranglerText.match(/d1_databases[\s\S]{0,1200}/)?.[0] ?? "";

  // 静的SPAアセットとWorkerの同居チェック。ここを誤ると OAuth コールバック(=ブラウザの
  // トップレベル遷移 Accept: text/html)が SPA フォールバックに横取りされ、Worker=Better Auth に
  // 届かずセッションが張れない。fetch(JSON)は届くので気づきにくい。run_worker_first で /api/* を
  // Worker 先行にするのが対策。詳細は references/hono-workers-d1.md。
  const workerMain = /["']?main["']?\s*[:=]\s*["'][^"']+["']/.test(wranglerText);
  const assetsConfigured = /["']?assets["']?\s*[:=]/.test(wranglerText) || /\[\s*assets\s*\]/.test(wranglerText);
  const notFoundHandling = firstMatch(
    wranglerText,
    /["']?not_found_handling["']?\s*[:=]\s*["']([^"']+)["']/,
  );
  const spaFallback = notFoundHandling ? /single[-_ ]?page|spa/i.test(notFoundHandling) : false;
  const runWorkerFirstRaw = firstMatch(
    wranglerText,
    /["']?run_worker_first["']?\s*[:=]\s*(true|false|\[[^\]]*\])/,
  );
  // OAuth コールバックを含む /api/auth/* と、保護APIの /api/me が Worker に先行ルートされるか。
  const probePaths = ["/api/auth/callback/google", "/api/me"];
  let apiRoutedToWorker = false;
  if (runWorkerFirstRaw === "true") {
    apiRoutedToWorker = true;
  } else if (runWorkerFirstRaw && runWorkerFirstRaw.startsWith("[")) {
    const entries = [...runWorkerFirstRaw.matchAll(/["']([^"']+)["']/g)].map((m) => m[1]);
    const toRegExp = (glob) =>
      new RegExp("^" + glob.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*") + "$");
    const positives = entries.filter((e) => !e.startsWith("!"));
    const negatives = entries.filter((e) => e.startsWith("!")).map((e) => e.slice(1));
    const covered = (p) =>
      positives.some((e) => toRegExp(e).test(p)) && !negatives.some((e) => toRegExp(e).test(p));
    apiRoutedToWorker = probePaths.every(covered);
  }
  // 危険な組み合わせ: Worker があり、静的アセットを SPA フォールバックで配り、/api/* を Worker 先行に
  // していない。この状態だと OAuth コールバックの遷移が index.html に化ける。
  const spaInterceptsAuth = workerMain && assetsConfigured && spaFallback && !apiRoutedToWorker;

  return {
    root,
    packageFile: packageText ? "package.json" : null,
    packageManager,
    framework,
    versions: {
      next: deps.next ?? null,
      betterAuth: deps["better-auth"] ?? null,
      drizzle: deps["drizzle-orm"] ?? null,
      wrangler: deps.wrangler ?? null,
      openNext: deps["@opennextjs/cloudflare"] ?? null,
    },
    wranglerFile: wranglerName,
    d1: {
      configured: /d1_databases/.test(wranglerText),
      binding: firstMatch(d1Section, /["']?binding["']?\s*[:=]\s*["']([^"']+)/),
      databaseName: firstMatch(d1Section, /["']?database_name["']?\s*[:=]\s*["']([^"']+)/),
    },
    assets: {
      configured: assetsConfigured,
      workerMain,
      notFoundHandling,
      spaFallback,
      runWorkerFirst: runWorkerFirstRaw,
      apiRoutedToWorker,
      // true = OAuth コールバックの遷移が SPA に横取りされる危険な設定
      spaInterceptsAuth,
    },
    productionOrigin: firstMatch(
      wranglerText,
      /["']?BETTER_AUTH_URL["']?\s*[:=]\s*["'](https?:\/\/[^"']+)/,
    ),
    envFiles,
    envKeys: [...envKeys].sort(),
    gitignore: {
      devVars: /(^|\n)\s*\.dev\.vars(?:\.\*|\s|$)/m.test(gitignore),
      env: /(^|\n)\s*\.env(?:\*|\.\*|\s|$)/m.test(gitignore),
    },
    authFiles: matchedFiles.sort(),
    signals: {
      betterAuth: /betterAuth\s*\(/.test(sourceText),
      authClient: /createAuthClient\s*\(/.test(sourceText),
      googleProvider: /socialProviders[\s\S]{0,800}google\s*:/.test(sourceText),
      hostedDomain: /\bhd\s*:\s*["'`]/.test(sourceText),
      baseURL: /\bbaseURL\s*:/.test(sourceText),
      trustedOrigins: /\btrustedOrigins\s*(?::|,)/.test(sourceText),
      emailVerifiedGate: /emailVerified/.test(sourceText) && /APIError|FORBIDDEN|Unauthorized/.test(sourceText),
      databaseRateLimit: /rateLimit[\s\S]{0,500}storage\s*:\s*["']database["']/.test(sourceText),
      cloudflareIp: /cf-connecting-ip/.test(sourceText),
      authHandler: /auth\.handler\s*\(|toNextJsHandler\s*\(/.test(sourceText),
      serverSession: /api\.getSession\s*\(/.test(sourceText),
      googleSignIn: /signIn\.social\s*\([\s\S]{0,300}provider\s*:\s*["']google["']/.test(sourceText),
    },
    migrations: {
      user: /CREATE TABLE\s+[`"']?user[`"']?/i.test(migrationText),
      account: /CREATE TABLE\s+[`"']?account[`"']?/i.test(migrationText),
      session: /CREATE TABLE\s+[`"']?session[`"']?/i.test(migrationText),
      verification: /CREATE TABLE\s+[`"']?verification[`"']?/i.test(migrationText),
      rateLimit: /CREATE TABLE\s+[`"']?rate[_-]?limit[`"']?/i.test(migrationText),
    },
  };
}
