#!/usr/bin/env python3
# /// script
# name: extract-ci-workflow-steps
# purpose: pull_request で起動する GitHub Actions workflow から、ローカルで再現できる run 段を 1 段 1 ファイルの shell script として書き出す。run-ci-checks.sh が CI と同じ段を漏れなく実行するための抽出器。
# inputs:
#   - .github/workflows/*.yml / *.yaml (on に pull_request を持つもの)
# outputs:
#   - <out-dir>/NNN.sh: 1 段 1 ファイル (先頭 2 行に label と mode)
#   - <out-dir>/skipped.tsv: GitHub 上でしか評価できず書き出さなかった段・job と理由
#   - stdout: 書き出し件数のサマリ
#   - exit: 0=書き出し成功 / 1=対象 workflow の段が 1 つも無い / 2=usage・入力エラー (YAML 構文・型の不正を含む)
# contexts: [C]
# network: false
# write-scope: <out-dir> のみ
# dependencies: [PyYAML]
# requires-python: ">=3.10"
# ///
"""CI workflow の段を、ローカルの一括検査 (scripts/run-ci-checks.sh) 用に書き出す。

背景 (PR #83 / harness-o2m):
  run-ci-checks.sh は CI の段を手で写した一覧だったため、workflow 側にだけ段が増えて
  ずれていた (PR #83 の時点で 2 workflow の blocking な段の約 7 割がローカルに無かった)。
  validate-plugin-packages.py の PKG-007 (shebang 付き script の実行ビット欠落) を
  ローカルが持たず、push 後の CI で初めて落ちた。本 script は workflow を正本として
  段を書き出し、run-ci-checks.sh はそれをそのまま実行する。手写しの一覧を持たないので、
  workflow に段を足せばローカルにも自動で入る。

書き出しの規則:
  - 対象は on に pull_request を持つ workflow の全 job の run 段。schedule /
    workflow_dispatch だけの workflow は PR の合否に関わらないので対象外。
  - job か段に if がある段と、run / env / 実効 working-directory に GitHub 式を含む段は、
    ローカルで評価できないので書き出さず、理由を skipped.tsv に残す (黙って捨てない)。
  - job 単位の `uses:` (reusable workflow の呼び出し) は、呼び出し先の段を GitHub が展開する
    ので書き出さず、job ごと skipped.tsv に残す。
  - `pip install` の行 (`python3 -m pip install`・`pip3 install` など) は、行末が
    バックスラッシュの継続行ごと除く。ローカル環境を書き換えないため (依存は
    requirements-dev.txt を事前に入れておく前提)。同じ行の `&&` の先も一緒に消えるので、
    install と検査は別の行に書く。
  - continue-on-error: true の段は mode=soft、それ以外は mode=hard。
  - working-directory (段 / job の defaults / workflow の defaults) は cd に変換する。
  - literal env は workflow → job → 段の順で上書きし、shell quote した export に変換する。
  - shell は bash だけを再現し、ローカルでは常に `set -eo pipefail` で実行する。GitHub は
    shell 未指定の段を `bash -e {0}`、`shell: bash` の段を `bash --noprofile --norc -eo pipefail {0}`
    で動かすので、未指定の段はローカルの方が pipefail の分だけ厳しい (ローカルで通れば CI でも
    通る側に倒す)。bash 以外の shell の段は再現できないので skipped.tsv に残す。
  - YAML は GitHub と同じ 1.2 の真偽値 (true / false だけ) で読む。PyYAML 既定の 1.1 は
    yes / no / on / off も真偽値にするので、`FLAG: yes` が export FLAG=true に化ける。
  - YAML の構文エラー、root・jobs・job・steps・段の型の不正は exit 2 で止める (traceback にしない)。

Usage:
  extract-ci-workflow-steps.py --out-dir DIR [--workflows-dir DIR] [--skip-jobs "JOB ..."]

Exit 0 = 書き出し成功, 1 = 対象 workflow が 1 本も無い (検査が空振りするので止める),
2 = usage / 入力エラー。
"""
from __future__ import annotations

import argparse
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOWS_DIR = ROOT / ".github" / "workflows"
GITHUB_EXPR = "${{"
PIP_INSTALL_RE = re.compile(r"\s*(?:python(?:3(?:\.\d+)?)?\s+-m\s+)?pip3?\s+install\b")
ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class Step:
    label: str
    mode: str  # "hard" | "soft"
    working_directory: str | None
    body: str
    env: dict[str, str] = field(default_factory=dict)


def _triggers(data: dict) -> set[str]:
    # _yaml12_loader で読むので `on:` キーは文字列 "on" のまま (1.1 の True に化けない)。
    on = data.get("on")
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return {str(t) for t in on}
    if isinstance(on, dict):
        return {str(t) for t in on}
    return set()


def _yaml12_loader():
    """真偽値を YAML 1.2 (GitHub と同じ) の true / false だけにした SafeLoader を返す。"""
    import yaml

    bool_tag = "tag:yaml.org,2002:bool"

    class Loader(yaml.SafeLoader):
        pass

    Loader.yaml_implicit_resolvers = {
        first: [(tag, regexp) for tag, regexp in resolvers if tag != bool_tag]
        for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    Loader.add_implicit_resolver(
        bool_tag, re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
    )
    return Loader


def iter_pr_workflows(workflows_dir: Path):
    import yaml

    loader = _yaml12_loader()
    paths = sorted([*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")])
    for path in paths:
        try:
            data = yaml.load(path.read_text(encoding="utf-8"), Loader=loader)
        except (OSError, UnicodeDecodeError, RecursionError, yaml.YAMLError) as exc:
            raise ValueError(f"{path.name}: workflow を読めない: {exc}") from exc
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError(f"{path.name}: workflow の root が mapping でない ({type(data).__name__})")
        if "pull_request" in _triggers(data):
            yield path, data


def _mapping(value, what: str) -> dict:
    """省略 (None) は空の mapping、mapping 以外は入力エラーにする。"""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{what} が mapping でない ({type(value).__name__})")
    return value


def _github_only_reason(job: dict, step: dict) -> str | None:
    if "if" in job:
        return f"job の if 条件 ({job['if']}) は GitHub 上でのみ評価できる"
    if "if" in step:
        return f"段の if 条件 ({step['if']}) は GitHub 上でのみ評価できる"
    for scope, env in (("job", job.get("env")), ("段", step.get("env"))):
        if env and GITHUB_EXPR in str(env):
            return f"{scope}の env が GitHub 式 (${{{{ }}}}) に依存する"
    if GITHUB_EXPR in str(step.get("run", "")):
        return "run が GitHub 式 (${{ }}) に依存する"
    return None


def _strip_local_only(body: str) -> str:
    kept = []
    continuing = False
    for line in body.splitlines():
        if continuing or PIP_INSTALL_RE.match(line):
            # 行末の `\` は次の行も同じ pip install の引数であることを示す。
            continuing = line.rstrip().endswith("\\")
            continue
        kept.append(line)
    return "\n".join(kept).strip("\n")


def _effective_env(*scopes: dict | None) -> dict[str, str]:
    env: dict[str, str] = {}
    for scope in scopes:
        if scope is None:
            continue
        if not isinstance(scope, dict):
            raise ValueError("env must be a mapping")
        for name, value in scope.items():
            if not isinstance(name, str) or not ENV_NAME_RE.fullmatch(name):
                raise ValueError(f"invalid env name: {name!r}")
            if isinstance(value, (dict, list)) or value is None:
                raise ValueError(f"env value must be a scalar: {name}")
            # YAML boolean/numeric scalars become the strings passed to the shell.
            env[name] = str(value).lower() if isinstance(value, bool) else str(value)
    return env


def build_steps(
    workflows_dir: Path, skip_jobs: frozenset[str] = frozenset()
) -> tuple[list[Step], list[tuple[str, str]]]:
    steps: list[Step] = []
    skipped: list[tuple[str, str]] = []
    for path, data in iter_pr_workflows(workflows_dir):
        where = path.name
        wf_run = _mapping(_mapping(data.get("defaults"), f"{where}: defaults").get("run"),
                          f"{where}: defaults.run")
        if data.get("env") and GITHUB_EXPR in str(data["env"]):
            wf_reason = "workflow の env が GitHub 式 (${{ }}) に依存する"
        else:
            wf_reason = None
        for job_id, job in _mapping(data.get("jobs"), f"{where}: jobs").items():
            job = _mapping(job, f"{where}: jobs.{job_id}")
            if "uses" in job:
                skipped.append((
                    f"{path.name}:{job_id}: (reusable workflow)",
                    f"reusable workflow の job (uses: {job['uses']}) は呼び出し先の段を"
                    " GitHub 上で展開するので、ローカルでは再現しない",
                ))
                continue
            job_run = _mapping(_mapping(job.get("defaults"), f"{where}: jobs.{job_id}.defaults")
                               .get("run"), f"{where}: jobs.{job_id}.defaults.run")
            job_steps = job.get("steps") or []
            if not isinstance(job_steps, list):
                raise ValueError(f"{where}: jobs.{job_id}.steps が list でない")
            for idx, step in enumerate(job_steps, start=1):
                step = _mapping(step, f"{where}: jobs.{job_id}.steps[{idx}]")
                if "run" not in step:
                    continue
                label = f"{path.name}:{job_id}: {step.get('name') or f'step {idx}'}"
                working_directory = (
                    step.get("working-directory")
                    or job_run.get("working-directory")
                    or wf_run.get("working-directory")
                )
                shell = step.get("shell") or job_run.get("shell") or wf_run.get("shell") or "bash"
                if job_id in skip_jobs:
                    reason = "CI_CHECKS_SKIP_JOBS で利用者が除外した"
                elif shell != "bash":
                    reason = f"shell={shell} はローカルで再現しない"
                else:
                    reason = wf_reason or _github_only_reason(job, step)
                    if not reason and GITHUB_EXPR in str(working_directory or ""):
                        reason = "working-directory が GitHub 式 (${{ }}) に依存する"
                if reason:
                    skipped.append((label, reason))
                    continue
                steps.append(Step(
                    label=label,
                    mode="soft" if step.get("continue-on-error") is True else "hard",
                    working_directory=working_directory,
                    body=_strip_local_only(str(step["run"])),
                    env=_effective_env(data.get("env"), job.get("env"), step.get("env")),
                ))
    return steps, skipped


def render_step(step: Step) -> str:
    lines = [
        f"# label: {step.label}",
        f"# mode: {step.mode}",
        "set -eo pipefail",
    ]
    for name, value in step.env.items():
        if not ENV_NAME_RE.fullmatch(name):
            raise ValueError(f"invalid env name: {name!r}")
        lines.append(f"export {name}={shlex.quote(value)}")
    if step.working_directory:
        lines.append(f"cd {shlex.quote(step.working_directory)}")
    lines.append(step.body)
    return "\n".join(lines) + "\n"


def write_steps(out_dir: Path, steps: list[Step], skipped: list[tuple[str, str]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    width = max(3, len(str(len(steps))))
    for n, step in enumerate(steps, start=1):
        (out_dir / f"{n:0{width}d}.sh").write_text(render_step(step), encoding="utf-8")
    (out_dir / "skipped.tsv").write_text(
        "".join(f"{label}\t{reason}\n" for label, reason in skipped), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--workflows-dir", type=Path, default=DEFAULT_WORKFLOWS_DIR)
    ap.add_argument("--skip-jobs", default="", help="除外する job id を空白区切りで渡す")
    args = ap.parse_args(argv)

    if not args.workflows_dir.is_dir():
        print(f"[ERROR] workflows dir が無い: {args.workflows_dir}", file=sys.stderr)
        return 2
    if args.out_dir.exists() and any(args.out_dir.glob("*.sh")):
        print(f"[ERROR] out-dir に既存の段がある (混ざるので空の dir を渡す): {args.out_dir}",
              file=sys.stderr)
        return 2
    try:
        steps, skipped = build_steps(args.workflows_dir, frozenset(args.skip_jobs.split()))
    except ImportError:
        print("[ERROR] PyYAML が無い (pip install -r requirements-dev.txt)", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"[ERROR] invalid workflow input: {exc}", file=sys.stderr)
        return 2
    if not steps:
        print("[ERROR] pull_request で起動する workflow の段が 1 つも無い (検査が空振りする)",
              file=sys.stderr)
        return 1
    write_steps(args.out_dir, steps, skipped)
    print(f"extract-ci-workflow-steps: {len(steps)} steps, {len(skipped)} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
