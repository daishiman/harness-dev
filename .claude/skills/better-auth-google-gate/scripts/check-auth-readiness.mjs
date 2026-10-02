#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { scanProject } from "./project-scan.mjs";

function arg(name, fallback = null) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

const project = arg("--project", process.cwd());
const expectedOrigin = arg("--production-origin");
const expectedDomain = arg("--workspace-domain");
const remote = process.argv.includes("--remote");
const result = await scanProject(project);
const rows = [];

function check(label, pass, detail, required = true) {
  rows.push({ label, pass: Boolean(pass), detail, required });
}

check("Better Auth dependency", Boolean(result.versions.betterAuth), result.versions.betterAuth ?? "未検出");
check("Wrangler config", Boolean(result.wranglerFile), result.wranglerFile ?? "未検出");
check("D1 binding", result.d1.configured, result.d1.databaseName ?? "未設定");
check("Better Auth server config", result.signals.betterAuth, result.authFiles.join(", ") || "未検出");
check("Google provider", result.signals.googleProvider, "socialProviders.google");
check("Workspace hd gate", result.signals.hostedDomain, expectedDomain ?? "hd未検出");
check("baseURL", result.signals.baseURL, result.productionOrigin ?? "未検出");
check("trustedOrigins", result.signals.trustedOrigins, "固定origin");
check("emailVerified gate", result.signals.emailVerifiedGate, "未検証メール拒否");
check("DB-backed rate limit", result.signals.databaseRateLimit, "serverless memory依存なし");
check("Cloudflare client IP", result.signals.cloudflareIp, "cf-connecting-ip");
check("Auth route handler", result.signals.authHandler, "/api/auth/*");
check("Google sign-in client", result.signals.googleSignIn, "signIn.social");
check("Server-side session verification", result.signals.serverSession, "api.getSession");
check("Auth migrations", Object.values(result.migrations).every(Boolean), JSON.stringify(result.migrations));

// 静的SPAアセットとの同居チェック。OAuth コールバック(ブラウザのトップレベル遷移)が SPA
// フォールバックに横取りされると Worker=Better Auth に届かず、セッションが張れない。
if (result.assets.configured && result.assets.workerMain) {
  check(
    "Assets: /api/* を Worker 先行にする",
    !result.assets.spaInterceptsAuth,
    result.assets.spaInterceptsAuth
      ? 'SPAフォールバックがOAuthコールバックの遷移を横取りする恐れ → wrangler の assets.run_worker_first に "/api/*" を追加'
      : result.assets.spaFallback
        ? "run_worker_first が /api/* を先行"
        : "SPAフォールバック無し",
  );
}

check(".dev.vars ignored", result.gitignore.devVars, ".gitignore");
check(".env ignored", result.gitignore.env, ".gitignore", false);

const requiredLocalKeys = ["BETTER_AUTH_SECRET", "BETTER_AUTH_URL", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"];
const hasLocalSecretFile = result.envFiles.includes(".dev.vars") || result.envFiles.includes(".env") || result.envFiles.includes(".env.local");
check(
  "Local auth keys",
  !hasLocalSecretFile || requiredLocalKeys.every((key) => result.envKeys.includes(key)),
  hasLocalSecretFile ? "値は非表示、キー名のみ確認" : "local secret file未作成",
  false,
);

if (expectedOrigin) {
  let normalized = null;
  try { normalized = new URL(expectedOrigin).origin; } catch {}
  check("Production origin exact match", normalized && result.productionOrigin === normalized, `${result.productionOrigin ?? "未設定"} / expected ${normalized ?? "不正"}`);
}

if (expectedDomain) {
  const valid = /^[a-z0-9.-]+\.[a-z]{2,}$/i.test(expectedDomain);
  check("Workspace domain format", valid, expectedDomain);
}

if (remote) {
  const common = [];
  const env = arg("--env");
  const name = arg("--name");
  if (env) common.push("--env", env);
  if (name) common.push("--name", name);
  try {
    const output = execFileSync("npx", ["wrangler", "secret", "list", ...common, "--format", "json"], {
      cwd: result.root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    const names = new Set(JSON.parse(output).map((row) => row.name));
    const missing = ["BETTER_AUTH_SECRET", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"].filter((key) => !names.has(key));
    check("Remote Secret names", missing.length === 0, missing.length ? `不足: ${missing.join(", ")}` : "3件登録済み");
  } catch (error) {
    check("Remote Secret names", false, `Wrangler確認失敗: ${error.status ?? "unknown"}`);
  }

  if (result.d1.databaseName) {
    try {
      const output = execFileSync(
        "npx",
        ["wrangler", "d1", "migrations", "list", result.d1.databaseName, "--remote", ...(env ? ["--env", env] : [])],
        { cwd: result.root, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
      );
      const pending = /\.sql\b/.test(output);
      check("Remote D1 migrations", !pending, pending ? "未適用migrationあり" : "未適用なし");
    } catch (error) {
      check("Remote D1 migrations", false, `Wrangler確認失敗: ${error.status ?? "unknown"}`);
    }
  }

  // 本番へ「ブラウザのトップレベル遷移」を模して /api/me を叩く。ここで index.html(SPA)が
  // 返るなら、OAuth コールバックの遷移も同じく横取りされ、ログインが完了しない(今回のバグ)。
  // Worker の JSON/リダイレクトが返るのが正しい。expectedOrigin があるときだけ実施。
  if (expectedOrigin) {
    try {
      const probe = new URL("/api/me", expectedOrigin);
      probe.searchParams.set("_ready", String(Date.now()));
      const res = await fetch(probe, {
        headers: { Accept: "text/html,application/xhtml+xml", "Sec-Fetch-Mode": "navigate" },
        redirect: "manual",
      });
      const body = await res.text().catch(() => "");
      const looksHtml = /<!doctype html|<html[\s>]|<title[\s>]/i.test(body);
      check(
        "Live: /api/* の遷移がWorkerに届く",
        !looksHtml,
        looksHtml
          ? 'SPA(index.html)が返っている＝OAuthコールバックの遷移が横取りされる → run_worker_first:["/api/*"] を設定し再デプロイ'
          : "遷移リクエストでもWorkerが応答",
      );
    } catch (error) {
      check("Live: /api/* の遷移がWorkerに届く", false, `到達確認失敗: ${error.message}`, false);
    }
  }
}

console.log("Better Auth Google Gate: readiness");
for (const row of rows) {
  const icon = row.pass ? "PASS" : row.required ? "FAIL" : "WARN";
  console.log(`[${icon}] ${row.label}: ${row.detail}`);
}

const failures = rows.filter((row) => row.required && !row.pass);
console.log(`結果: ${rows.length - failures.length}/${rows.length} checks non-failing, required failures=${failures.length}`);
process.exit(failures.length ? 1 : 0);
