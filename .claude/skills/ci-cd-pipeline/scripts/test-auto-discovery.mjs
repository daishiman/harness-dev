#!/usr/bin/env node
import { execFileSync, spawnSync } from "node:child_process";
import { chmod, mkdir, mkdtemp, readFile, unlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

function check(condition, message) {
  if (!condition) throw new Error(message);
}

const scripts = path.dirname(fileURLToPath(import.meta.url));
const generator = path.join(scripts, "generate-cloudflare-credentials-guide.mjs");
const fixture = await mkdtemp(path.join(os.tmpdir(), "aidd-cicd-auto-"));
const bin = path.join(fixture, "bin");
const api = path.join(fixture, "packages", "api worker");
await mkdir(bin, { recursive: true });
await mkdir(api, { recursive: true });

const ghStub = `#!/bin/sh
if [ "$1 $2" = "repo view" ]; then
  printf '%s\\n' '{"nameWithOwner":"example-owner/example-repo","url":"https://github.com/example-owner/example-repo","defaultBranchRef":{"name":"trunk"},"isPrivate":false}'
  exit 0
fi
if [ "$1 $2 $3" = "variable get APP_URL" ]; then
  printf '%s\\n' 'https://example-repo.example.workers.dev'
  exit 0
fi
exit 1
`;
await writeFile(path.join(bin, "gh"), ghStub, "utf8");
await chmod(path.join(bin, "gh"), 0o755);
await writeFile(path.join(fixture, "pnpm-lock.yaml"), "lockfileVersion: '9.0'\n", "utf8");
await writeFile(path.join(fixture, "package.json"), '{"name":"example-app"}\n', "utf8");
await writeFile(path.join(api, "wrangler.jsonc"), `{
  "name": "example-worker",
  "vars": { "APP_URL": "https://example-repo.example.workers.dev" },
  "d1_databases": [{ "binding": "DB", "database_name": "example-db" }],
  "r2_buckets": [{ "binding": "BUCKET", "bucket_name": "example-bucket" }]
}\n`, "utf8");
execFileSync("git", ["init", "-q"], { cwd: fixture });
execFileSync("git", ["remote", "add", "upstream", "https://credential:must-not-leak@github.com/example-owner/example-repo.git"], { cwd: fixture });

const env = { ...process.env, PATH: `${bin}${path.delimiter}${process.env.PATH || ""}` };
const noArgs = spawnSync(process.execPath, [generator], { cwd: fixture, env, encoding: "utf8" });
check(noArgs.status === 2, "無引数時に不足Account名で停止しませんでした");
check(noArgs.stderr.includes("--account-name"), "無引数時の診断に次の操作がありません");
check(!`${noArgs.stdout}${noArgs.stderr}`.includes("must-not-leak"), "remoteの認証情報が診断へ漏れました");

const guide = path.join(fixture, "out", "guide.md");
const helper = path.join(fixture, "out", "setup.mjs");
const generated = execFileSync(process.execPath, [
  generator,
  "--auto",
  "--account-name", "Example Team's Account",
  "--output", guide,
  "--helper-output", helper,
], { cwd: fixture, env, encoding: "utf8" });
const guideText = await readFile(guide, "utf8");
const helperText = await readFile(helper, "utf8");
execFileSync(process.execPath, ["--check", helper], { cwd: fixture, env });
for (const expected of [
  "example-owner/example-repo", "trunk", "example-worker", "example-db", "example-bucket",
  "https://example-repo.example.workers.dev", "pnpm --dir 'packages/api worker' exec wrangler",
  "pnpm install --force --frozen-lockfile", "TEAM",
]) check(guideText.includes(expected), `生成ガイドに自動検出値がありません: ${expected}`);
check(helperText.includes("['pnpm', '--dir', 'packages/api worker', 'exec', 'wrangler']"), "nested pnpm用Wranglerコマンドを検出できませんでした");
check(helperText.includes("Example Team\\'s Account"), "apostropheを含むAccount名を安全に埋め込めませんでした");
check(helperText.includes("const ACCOUNT_MODE = 'team'"), "新規構築のteam既定が適用されませんでした");
check(generated.includes("✓ 自動検出"), "自動検出の成功表示がありません");
check(!`${guideText}${helperText}${generated}`.includes("must-not-leak"), "生成物へremoteの認証情報が漏れました");
const dryRun = execFileSync(process.execPath, [helper, "--dry-run"], { cwd: fixture, env, encoding: "utf8" });
check(dryRun.includes("外部設定とsecretは変更していません"), "生成helperのdry-runに失敗しました");

const existingGuide = path.join(fixture, "out", "existing-guide.md");
const existingHelper = path.join(fixture, "out", "existing-helper.mjs");
execFileSync(process.execPath, [
  generator,
  "--auto",
  "--account-name", "Existing Account",
  "--account-mode", "existing",
  "--output", existingGuide,
  "--helper-output", existingHelper,
], { cwd: fixture, env });
check((await readFile(existingGuide, "utf8")).includes("EXISTING"), "確認済み既存所有先のexisting modeを生成できませんでした");
check((await readFile(existingHelper, "utf8")).includes("const ACCOUNT_MODE = 'existing'"), "existing modeがhelperへ渡りませんでした");

await unlink(path.join(fixture, "pnpm-lock.yaml"));
await writeFile(path.join(fixture, "package-lock.json"), "{}\n", "utf8");
const npmGuide = path.join(fixture, "out", "npm-guide.md");
const npmHelper = path.join(fixture, "out", "npm-helper.mjs");
execFileSync(process.execPath, [generator, "--auto", "--account-name", "Example Team", "--output", npmGuide, "--helper-output", npmHelper], { cwd: fixture, env });
check((await readFile(npmGuide, "utf8")).includes("npm ci"), "npm lockfile位置のinstall commandを検出できませんでした");
check((await readFile(npmHelper, "utf8")).includes("['npm', '--prefix', 'packages/api worker', 'exec', '--', 'wrangler']"), "nested npm Wrangler commandを検出できませんでした");

await unlink(path.join(fixture, "package-lock.json"));
await writeFile(path.join(fixture, "yarn.lock"), "# yarn lockfile v1\n", "utf8");
const yarnGuide = path.join(fixture, "out", "yarn-guide.md");
const yarnHelper = path.join(fixture, "out", "yarn-helper.mjs");
execFileSync(process.execPath, [generator, "--auto", "--account-name", "Example Team", "--output", yarnGuide, "--helper-output", yarnHelper], { cwd: fixture, env });
check((await readFile(yarnGuide, "utf8")).includes("yarn install --frozen-lockfile"), "Yarn Classic用install commandを検出できませんでした");
check((await readFile(yarnHelper, "utf8")).includes("['yarn', '--cwd', 'packages/api worker', 'exec', 'wrangler']"), "nested yarn Wrangler commandを検出できませんでした");

await writeFile(path.join(fixture, ".yarnrc.yml"), "nodeLinker: node-modules\n", "utf8");
const berryGuide = path.join(fixture, "out", "berry-guide.md");
const berryHelper = path.join(fixture, "out", "berry-helper.mjs");
execFileSync(process.execPath, [generator, "--auto", "--account-name", "Example Team", "--output", berryGuide, "--helper-output", berryHelper], { cwd: fixture, env });
check((await readFile(berryGuide, "utf8")).includes("yarn install --immutable"), "Yarn Berry用install commandを検出できませんでした");

await mkdir(path.join(fixture, "packages", "other"), { recursive: true });
await writeFile(path.join(fixture, "packages", "other", "wrangler.toml"), 'name = "other-worker"\n', "utf8");
const ambiguous = spawnSync(process.execPath, [
  generator,
  "--auto",
  "--account-name", "Example Team",
  "--output", path.join(fixture, "out", "other-guide.md"),
  "--helper-output", path.join(fixture, "out", "other-helper.mjs"),
], { cwd: fixture, env, encoding: "utf8" });
check(ambiguous.status === 2, "複数Wrangler設定で停止しませんでした");
check(ambiguous.stderr.includes("Wrangler設定が複数"), "複数候補の停止理由が明確ではありません");
check(ambiguous.stderr.includes("--wrangler-config"), "複数候補の解決方法がありません");

console.log("✓ auto discovery: 無引数診断・pnpm/npm/yarn nested path・helper dry-run・複数候補停止・認証情報非表示を確認しました");
