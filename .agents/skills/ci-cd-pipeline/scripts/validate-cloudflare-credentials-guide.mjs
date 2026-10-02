#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const files = {
  guide: await readFile(path.join(root, "assets/cloudflare-credentials-guide.md.template"), "utf8"),
  helper: await readFile(path.join(root, "assets/setup-cloudflare-production.template.mjs"), "utf8"),
  skill: await readFile(path.join(root, "SKILL.md"), "utf8"),
  ci: await readFile(path.join(root, "assets/ci.yml"), "utf8"),
  detectPm: await readFile(path.join(root, "assets/detect-pm.yml"), "utf8"),
  deploy: await readFile(path.join(root, "assets/deploy.yml"), "utf8"),
  migrate: await readFile(path.join(root, "assets/migrate.yml"), "utf8"),
  generator: await readFile(path.join(root, "scripts/generate-cloudflare-credentials-guide.mjs"), "utf8"),
  detector: await readFile(path.join(root, "scripts/detect-github-repository.mjs"), "utf8"),
};

const contracts = {
  guide: [
    "AI自動", "所有者のみ", "停止", "チーム用Cloudflareアカウント", "個人アカウント",
    "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "APP_URL", "Global API Key",
    "gh auth status", "gh repo view", "supportedArchitectures", "__INSTALL_COMMAND__",
    "wrangler whoami", "__WRANGLER__ login", "r2 bucket list", "r2 bucket create", "r2 bucket info",
    "r2 bucket dev-url get", "r2 bucket domain list", "Account API Tokens", "account-owned",
    "Account Settings", "Workers Scripts", "Workers R2 Storage", "D1", "Specific account",
    "Client IP Address Filtering", "Continue to summary", "cfat_", "cfut_", "cfk_",
    "gh secret list --env", "gh variable list", "deployment-branch-policies", "AUTH_PASSWORD",
    "SESSION_SECRET", "secret list", "bash .github/scripts/smoke.sh", "gh run rerun", "gh run watch", "deployments list", "IF_EXISTING", "EXISTING",
    "30秒", "90秒", "code 10000", "code 7003", "漏えい", "rollback", "最終チェックリスト",
  ],
  helper: [
    "readHidden", "tokens/verify", "probeGh", "HTTP 404", "deployment_branch_policy", "deployment-branch-policies", "EXISTING",
    "gh", "secret", "set", "--env", "variable", "set", "APP_URL", "secret", "list",
    "既存policyを削除せず停止", "--rotate-auth-password", "--rotate-session-secret", "randomBytes", "clipboard", "apiToken = null",
  ],
  skill: [
    "チーム用Accountを既定選択", "account-owned API Token", "Environment secret",
    "cloudflare-credentials-setup.md", "setup-production.mjs", "既存Worker secret",
    "required_status_checks[contexts][]=verify",
  ],
  ci: ["jobs:", "  verify:", "このジョブ名（verify）を、ブランチ保護の必須チェックに指定する", "uses: ./.github/actions/detect-pm"],
  detectPm: ["using: composite", "id: detect", "pnpm-lock.yaml", "yarn.lock", "npm ci", "pnpm/action-setup@v6", "actions/setup-node@v7"],
  deploy: [
    "workflow_run:", "github.event.workflow_run.head_sha", "environment: production",
    "github.event.workflow_run.conclusion == 'success'", "github.ref == 'refs/heads/main'",
    "テスト（手動実行時）", "sleep 30", "sleep 90", "uses: ./.github/actions/detect-pm",
  ],
  migrate: ["workflow_dispatch:", "environment: production", "inputs.confirm != 'APPLY'", "uses: ./.github/actions/detect-pm"],
  generator: ["--auto", "detect-github-repository.mjs", "--wrangler-config", "pnpm-lock.yaml", "yarn.lock", "package-lock.json", ".yarnrc.yml", "--frozen-lockfile", "--immutable", "--install-command-json", "variable", "get", "APP_URL", "自動検出を安全に完了できない", "existing", "installCommand", "--prefix", "--dir", "--cwd"],
  detector: ["single_github_remote", "multiple_github_remotes", "gh_auth_required", "question_required", "safe_question"],
};

const missing = [];
for (const [file, required] of Object.entries(contracts)) {
  for (const fragment of required) {
    if (!files[file].includes(fragment)) missing.push(`${file}: ${fragment}`);
  }
}

const unsafe = [];
for (const [name, content] of Object.entries({ guide: files.guide, skill: files.skill })) {
  if (content.includes("dash.cloudflare.com/profile/api-tokens")) unsafe.push(`${name}: user token URL`);
}
for (const line of files.skill.split(/\r?\n/)) {
  if (/gh secret set CLOUDFLARE_(?:API_TOKEN|ACCOUNT_ID)/.test(line) && !line.includes("--env production")) {
    unsafe.push(`skill: Environment指定なし: ${line.trim()}`);
  }
}
if (files.skill.includes("required_status_checks[contexts][]=ci")) {
  unsafe.push("skill: 実在しない必須チェック名ci");
}
const cfutLine = files.guide.split(/\r?\n/).find((line) => line.includes("cfut_"));
if (!cfutLine || !cfutLine.includes("停止")) {
  unsafe.push("guide: user-owned tokenで停止する指示がない");
}
for (const name of ["ci", "deploy", "migrate"]) {
  if (files[name].includes("if [ -f pnpm-lock.yaml ]")) {
    unsafe.push(`${name}: package manager判定が共通Actionと重複`);
  }
}

if (missing.length || unsafe.length) {
  if (missing.length) console.error(`不足項目:\n- ${missing.join("\n- ")}`);
  if (unsafe.length) console.error(`危険な退行:\n- ${unsafe.join("\n- ")}`);
  process.exit(1);
}

console.log("✓ Cloudflare資格情報ガイド: 11章相当の手順・新規team既定・既存existing・helper・workflow契約を確認しました");
