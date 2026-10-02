#!/usr/bin/env node
import { execFileSync } from "node:child_process";

function option(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : null;
}

function run(command, args, cwd) {
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

function emit(payload) {
  process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
}

function safeRemoteName(value) {
  return typeof value === "string" && /^[A-Za-z0-9._-]+$/.test(value);
}

function githubRemote(value) {
  if (!value) return null;
  let host;
  let pathname;

  const scp = value.match(/^(?:[^@/:]+@)?([^/:]+):(.+)$/);
  if (scp && !value.includes("://")) {
    [, host, pathname] = scp;
  } else {
    try {
      const url = new URL(value);
      host = url.hostname;
      pathname = url.pathname;
    } catch {
      return null;
    }
  }

  if (!host || !/(^|\.)github\.com$/i.test(host)) return null;
  const parts = pathname.replace(/^\/+|\/+$/g, "").replace(/\.git$/i, "").split("/");
  if (parts.length !== 2 || parts.some((part) => !/^[A-Za-z0-9_.-]+$/.test(part))) return null;
  const [owner, repositoryName] = parts;
  return {
    host: host.toLowerCase(),
    owner,
    repository: `${owner}/${repositoryName}`,
    web_url: `https://${host.toLowerCase()}/${owner}/${repositoryName}`,
  };
}

function ghView(cwd, repository = null) {
  const args = ["repo", "view"];
  if (repository) args.push(repository);
  args.push("--json", "nameWithOwner,url,defaultBranchRef,isPrivate");
  const output = run("gh", args, cwd);
  if (!output) return null;
  try {
    const parsed = JSON.parse(output);
    if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(parsed.nameWithOwner || "")) return null;
    return parsed;
  } catch {
    return null;
  }
}

const cwd = option("--cwd") || process.cwd();
const root = run("git", ["rev-parse", "--show-toplevel"], cwd);
if (!root) {
  emit({
    status: "unconfigured",
    question_required: true,
    reason: "git_repository_not_found",
    safe_question: "対象のGitリポジトリがあるフォルダを指定してください。",
  });
  process.exit(0);
}

const remoteNames = (run("git", ["remote"], root) || "")
  .split(/\r?\n/)
  .filter(safeRemoteName);
const candidates = [];
for (const remote of remoteNames) {
  const rawUrl = run("git", ["remote", "get-url", remote], root);
  const parsed = githubRemote(rawUrl);
  if (parsed) candidates.push({ remote, ...parsed });
}

const requestedRemote = option("--remote");
if (requestedRemote && !safeRemoteName(requestedRemote)) {
  emit({
    status: "invalid_selection",
    question_required: true,
    reason: "unsafe_remote_name",
    safe_question: "候補一覧に表示されたremote名をそのまま選んでください。",
  });
  process.exit(0);
}

const currentBranch = run("git", ["branch", "--show-current"], root);
const trackingRemote = currentBranch
  ? run("git", ["config", "--get", `branch.${currentBranch}.remote`], root)
  : null;
const currentGh = ghView(root);
let selected = null;

if (requestedRemote) {
  selected = candidates.find((candidate) => candidate.remote === requestedRemote) || null;
  if (!selected) {
    emit({
      status: "invalid_selection",
      question_required: true,
      reason: "remote_is_missing_or_not_github",
      candidates,
      safe_question: "候補一覧からGitHubのremoteを1つ選んでください。",
    });
    process.exit(0);
  }
} else if (candidates.length === 1) {
  [selected] = candidates;
} else if (candidates.length > 1) {
  selected = candidates.find((candidate) => candidate.remote === trackingRemote) || null;
  if (!selected && currentGh) {
    const matches = candidates.filter((candidate) => (
      candidate.repository.toLowerCase() === currentGh.nameWithOwner.toLowerCase()
    ));
    if (matches.length === 1) [selected] = matches;
  }
  if (!selected) {
    emit({
      status: "multiple",
      question_required: true,
      reason: "multiple_github_remotes",
      candidates,
      safe_question: "操作対象にするremoteを候補から1つ選んでください。認証情報を含むURLは貼らないでください。",
    });
    process.exit(0);
  }
}

if (!selected) {
  emit({
    status: "unconfigured",
    question_required: true,
    reason: "github_remote_not_found",
    detected_by_gh: currentGh?.nameWithOwner || null,
    safe_question: currentGh
      ? `ghでは${currentGh.nameWithOwner}を検出しました。どのremote名で接続するか確認してください。`
      : "既存のGitHubリポジトリへ接続するか、新規作成するかを選んでください。認証情報を含むURLは貼らないでください。",
  });
  process.exit(0);
}

const repositoryView = ghView(root, selected.repository);
if (!repositoryView) {
  emit({
    status: "gh_auth_required",
    question_required: true,
    reason: "gh_cannot_read_selected_repository",
    candidate: selected,
    safe_question: "リポジトリ所有者が `gh auth login` を完了してから再実行してください。認証コードやトークンは共有しないでください。",
  });
  process.exit(0);
}

const [owner, repositoryName] = repositoryView.nameWithOwner.split("/");
emit({
  status: "ok",
  question_required: false,
  recommended: {
    repository: repositoryView.nameWithOwner,
    owner,
    name: repositoryName,
    remote: selected.remote,
    remote_url: repositoryView.url,
    default_branch: repositoryView.defaultBranchRef?.name || null,
    is_private: repositoryView.isPrivate,
  },
  evidence: {
    git_root: root,
    current_branch: currentBranch || null,
    tracking_remote: trackingRemote || null,
    selection: requestedRemote
      ? "explicit_safe_remote"
      : candidates.length === 1
        ? "single_github_remote"
        : trackingRemote === selected.remote
          ? "current_branch_tracking_remote"
          : "gh_current_repository_match",
  },
});
