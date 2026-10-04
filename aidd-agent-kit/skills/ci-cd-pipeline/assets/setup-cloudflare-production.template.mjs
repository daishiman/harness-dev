#!/usr/bin/env node
import { spawn, spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { stdin as input, stdout as output } from 'node:process';
import { createInterface } from 'node:readline/promises';

const REPO = __REPO_JSON__;
const ENVIRONMENT = __ENVIRONMENT_JSON__;
const BRANCH = __BRANCH_JSON__;
const ACCOUNT_NAME = __ACCOUNT_NAME_JSON__;
const ACCOUNT_MODE = __ACCOUNT_MODE_JSON__;
const APP_URL = __APP_URL_JSON__;
const WRANGLER_COMMAND = __WRANGLER_COMMAND_JSON__;
const AUTH_PASSWORD = __AUTH_PASSWORD_JSON__;
const SESSION_SECRET = __SESSION_SECRET_JSON__;
const DRY_RUN = process.argv.includes('--dry-run');
const ROTATE_AUTH_PASSWORD = process.argv.includes('--rotate-auth-password');
const ROTATE_SESSION_SECRET = process.argv.includes('--rotate-session-secret');

function executable(command) {
  return process.platform === 'win32' && ['gh', 'pnpm', 'npm', 'npx', 'yarn'].includes(command)
    ? `${command}.cmd`
    : command;
}

function run(command, args, options = {}) {
  const result = spawnSync(executable(command), args, {
    encoding: 'utf8',
    input: options.input,
    stdio: options.capture ? [options.input === undefined ? 'ignore' : 'pipe', 'pipe', 'pipe'] : 'inherit',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    if (options.capture && result.stderr) process.stderr.write(result.stderr);
    throw new Error(`${command} ${args.join(' ')} に失敗しました。`);
  }
  return result.stdout || '';
}

function runGh(args, options = {}) {
  return run('gh', args, options);
}

function probeGh(args) {
  const result = spawnSync(executable('gh'), args, {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  if (result.error) throw result.error;
  return result;
}

function runWrangler(args, options = {}) {
  const [command, ...baseArgs] = WRANGLER_COMMAND;
  return run(command, [...baseArgs, ...args], options);
}

function putStdin(command, args, value) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable(command), args, { stdio: ['pipe', 'inherit', 'inherit'] });
    child.once('error', reject);
    child.once('exit', (code) =>
      code === 0 ? resolve() : reject(new Error(`${command}の登録処理に失敗しました。`)),
    );
    child.stdin.end(`${value}\n`);
  });
}

function putGithubSecret(name, value) {
  return putStdin('gh', ['secret', 'set', name, '--env', ENVIRONMENT, '--repo', REPO], value);
}

function putWorkerSecret(name, value) {
  const [command, ...baseArgs] = WRANGLER_COMMAND;
  return putStdin(command, [...baseArgs, 'secret', 'put', name], value);
}

async function readHidden(label) {
  if (!process.stdin.isTTY || typeof process.stdin.setRawMode !== 'function') {
    throw new Error('VS Code等の対話Terminalから実行してください。');
  }
  process.stdout.write(`${label}（入力内容は表示されません）: `);
  const wasRaw = Boolean(process.stdin.isRaw);
  process.stdin.setEncoding('utf8');
  process.stdin.setRawMode(true);
  process.stdin.resume();
  return new Promise((resolve, reject) => {
    let value = '';
    const finish = (error) => {
      process.stdin.off('data', onData);
      process.stdin.setRawMode(wasRaw);
      process.stdin.pause();
      process.stdout.write('\n');
      error ? reject(error) : resolve(value.trim());
    };
    const onData = (chunk) => {
      for (const character of chunk) {
        if (character === '\u0003') return finish(new Error('中止しました。'));
        if (character === '\r' || character === '\n') return finish();
        if (character === '\u007f' || character === '\b') value = value.slice(0, -1);
        else value += character;
      }
    };
    process.stdin.on('data', onData);
  });
}

function clipboard(inputValue) {
  const attempts =
    process.platform === 'darwin'
      ? [['pbcopy', []]]
      : process.platform === 'win32'
        ? [['clip', []]]
        : [
            ['wl-copy', []],
            ['xclip', ['-selection', 'clipboard']],
          ];
  for (const [command, args] of attempts) {
    const result = spawnSync(executable(command), args, { input: inputValue, encoding: 'utf8' });
    if (!result.error && result.status === 0) return;
  }
  throw new Error(
    'クリップボードへ安全にコピーできません。macOSはpbcopy、Windowsはclip、Linuxはwl-copyを使える状態にしてください。',
  );
}

async function confirmTeamAccount() {
  const rl = createInterface({ input, output });
  const expected = ACCOUNT_MODE === 'team' ? 'TEAM' : ACCOUNT_MODE === 'personal' ? 'PERSONAL' : 'EXISTING';
  const answer = await rl.question(`Cloudflareの対象は「${ACCOUNT_NAME}」です。${expected} と入力して続行: `);
  rl.close();
  if (answer.trim() !== expected) throw new Error('対象Accountの確認が一致しないため停止しました。');
}

async function verifyToken(accountId, apiToken) {
  const response = await fetch(`https://api.cloudflare.com/client/v4/accounts/${accountId}/tokens/verify`, {
    headers: { Authorization: `Bearer ${apiToken}` },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.success !== true || body?.result?.status !== 'active') {
    throw new Error('API Tokenがactiveではないか、選択したAccountのTokenではありません。');
  }
}

function ensureGitHubEnvironment() {
  const environmentEndpoint = `repos/${REPO}/environments/${ENVIRONMENT}`;
  const currentResult = probeGh(['api', environmentEndpoint]);
  if (currentResult.status === 0) {
    const current = JSON.parse(currentResult.stdout || '{}');
    const policy = current.deployment_branch_policy;
    if (policy?.protected_branches !== false || policy?.custom_branch_policies !== true) {
      throw new Error(
        `既存${ENVIRONMENT} Environmentのbranch policyが想定外です。既存のreviewer等を上書きしないため停止しました。AIへ設定名だけを伝えてください。`,
      );
    }
  } else if (/HTTP 404|Not Found/i.test(currentResult.stderr || '')) {
    runGh(['api', '--method', 'PUT', environmentEndpoint, '--input', '-'], {
      input: JSON.stringify({
        deployment_branch_policy: { protected_branches: false, custom_branch_policies: true },
      }),
      capture: true,
    });
  } else {
    if (currentResult.stderr) process.stderr.write(currentResult.stderr);
    throw new Error(`${ENVIRONMENT} Environmentの確認に失敗しました。`);
  }

  const policiesText = runGh(
    ['api', `repos/${REPO}/environments/${ENVIRONMENT}/deployment-branch-policies`],
    { capture: true },
  );
  const policies = JSON.parse(policiesText || '{}').branch_policies || [];
  const names = policies.map((policy) => policy.name);
  const unexpected = names.filter((name) => name !== BRANCH);
  if (unexpected.length) {
    throw new Error(
      `${ENVIRONMENT}が${BRANCH}以外も許可しています。既存policyを削除せず停止しました。AIへ許可ブランチ名だけを伝えてください。`,
    );
  }
  if (!names.includes(BRANCH)) {
    runGh(
      [
        'api',
        '--method',
        'POST',
        `repos/${REPO}/environments/${ENVIRONMENT}/deployment-branch-policies`,
        '-f',
        `name=${BRANCH}`,
        '-f',
        'type=branch',
      ],
      { capture: true },
    );
  }
}

function listWorkerSecrets() {
  try {
    return runWrangler(['secret', 'list', '--format', 'json'], { capture: true });
  } catch {
    return runWrangler(['secret', 'list'], { capture: true });
  }
}

async function configureWorkerSecrets() {
  const current = listWorkerSecrets();
  if (AUTH_PASSWORD) {
    if (current.includes(AUTH_PASSWORD) && !ROTATE_AUTH_PASSWORD) {
      console.log(`✓ ${AUTH_PASSWORD}: 登録済みのため変更しません`);
    } else {
      const password = randomBytes(24).toString('hex');
      clipboard(password);
      const rl = createInterface({ input, output });
      await rl.question(
        `パスワードマネージャーへ「${ACCOUNT_NAME} ${AUTH_PASSWORD}」として貼り付けて保存し、Enter: `,
      );
      rl.close();
      await putWorkerSecret(AUTH_PASSWORD, password);
      clipboard('');
      console.log(`✓ ${AUTH_PASSWORD}: 値を表示せず登録し、クリップボードを消去しました`);
    }
  }
  if (SESSION_SECRET) {
    if (current.includes(SESSION_SECRET) && !ROTATE_SESSION_SECRET) {
      console.log(`✓ ${SESSION_SECRET}: 登録済みのため変更しません`);
    } else {
      await putWorkerSecret(SESSION_SECRET, randomBytes(32).toString('hex'));
      console.log(`✓ ${SESSION_SECRET}: 値を表示せず登録しました`);
    }
  }
}

async function main() {
  if (DRY_RUN) {
    console.log('✓ helperの構文と生成値を確認しました。外部設定とsecretは変更していません。');
    return;
  }

  runGh(['auth', 'status'], { capture: true });
  const actualRepo = runGh(['repo', 'view', REPO, '--json', 'nameWithOwner', '-q', '.nameWithOwner'], {
    capture: true,
  }).trim();
  if (actualRepo !== REPO) throw new Error(`対象リポジトリが違います（期待: ${REPO}）。`);
  await confirmTeamAccount();

  const accountId = await readHidden('Cloudflare Account IDを貼り付けてEnter');
  if (!/^[a-f0-9]{32}$/i.test(accountId))
    throw new Error('Account IDの形式が正しくありません。Zone IDと取り違えていないか確認してください。');
  let apiToken = await readHidden('Cloudflare Account API Tokenを貼り付けてEnter');
  if (apiToken.startsWith('cfut_') || apiToken.startsWith('cfk_')) {
    throw new Error('user-owned tokenまたはGlobal API Keyです。Account API Tokenを作り直してください。');
  }
  await verifyToken(accountId, apiToken);
  console.log('✓ Cloudflare Account API Token: active');

  const whoami = runWrangler(['whoami'], { capture: true });
  if (!whoami.includes(accountId)) {
    throw new Error(
      'Wranglerのログイン先と選択したCloudflare Accountが一致しません。wrangler login後にやり直してください。',
    );
  }

  ensureGitHubEnvironment();
  await putGithubSecret('CLOUDFLARE_ACCOUNT_ID', accountId);
  await putGithubSecret('CLOUDFLARE_API_TOKEN', apiToken);
  apiToken = null;
  runGh(['variable', 'set', 'APP_URL', '--body', APP_URL, '--repo', REPO], { capture: true });
  console.log(`✓ GitHub ${ENVIRONMENT}: Environment secretsとAPP_URLを登録しました`);

  await configureWorkerSecrets();
  console.log('完了しました。secret値は表示・保存・送信していません。');
  console.log('このTerminalの完了メッセージだけをAIへ伝えてください。');
}

main().catch((error) => {
  try {
    clipboard('');
  } catch {}
  console.error(`エラー: ${error.message}`);
  console.error('secret値ではなく、このエラー文だけをAIへ伝えてください。');
  process.exitCode = 1;
});
