#!/usr/bin/env python3
# /// script
# name: build-plugin-release
# purpose: Detect changed plugins by content fingerprint, bump versions, regenerate the local marketplace, and drive `claude plugin update`.
# inputs:
#   - argv: --check, --install, --only, --dry-run, --project-dir, --scope, --quiet-period, --lock
#   - fs: plugins/*/**, marketplaces/local/plugin-fingerprints.json
# outputs:
#   - fs: plugins/*/.claude-plugin/plugin.json (version), marketplaces/local/**
#   - stdout: 変更検出 / bump / install の要約
# contexts: [A]
# network: false  (--install 時のみ claude CLI がローカル marketplace を読む。外部通信はしない)
# write-scope: plugins/*/.claude-plugin/plugin.json, marketplaces/local, --lock で指定した lock file
# dependencies: []
# requires-python: ">=3.10"
# ///
"""harness の編集を install 済み plugin へ届けるための release 駆動 script。

解こうとしている問題
--------------------
marketplace install は **version 単位の copy** である。実測 (2026-08-11):

  ~/.claude/plugins/cache/harness-local/<name>/<version>/  に実ファイル 539 件、symlink 0 件
  installed_plugins.json に gitCommitSha が固定される

つまりキャッシュのディレクトリ名が version そのものなので、**version を据え置いたまま
中身だけ直しても Claude Code には「同じ版」に見え、取り直す理由が無い**。
「harness を直したのに挙動が変わらない」の唯一の原因はこれである。

symlink projection (実体参照ゆえ即反映) を廃止して install へ一本化した以上、
version を上げ忘れることが即「反映されない」に直結する。人間の規律に頼ると必ず
漏れるので、**内容が変わったこと自体を機械が検出して version を進める**。

三つの状態を一致させ続ける
--------------------------
    plugins/<name>/**            内容 (真の SSOT)
    plugin.json の version       内容に対する識別子
    ~/.claude/plugins/cache/**   version で引かれた copy

`plugin-fingerprints.json` は 1 番目と 2 番目の対応表である。内容の hash と、その
hash が記録されたときの version を持つ。内容 hash が変わったのに version が同じなら
「上げ忘れ」であり、`--check` が exit 1 で落とす (CI ゲート)。引数なしで実行すれば
version を進めて対応表を書き直し、ローカル marketplace まで再生成する。

3 番目は `claude plugin update` が担う。`--install` はそれを CLI で駆動する:

    claude plugin marketplace update harness-local   # カタログ再読込
    claude plugin update <name> --scope project      # 新 version を copy

なぜ git commit hash を使わないのか
-----------------------------------
未 commit の作業ツリーでも成立させたいため。install が見るのは作業ツリーの実体
(`marketplaces/local/plugins -> ../../plugins` 経由) であって commit ではないので、
判定基準も作業ツリーの内容でなければ嘘になる。

fingerprint から除外するもの
----------------------------
`__pycache__` / `.pytest_cache` / `.DS_Store` / `.build` / `node_modules`。
いずれも実行の副産物で、内容が変わっても plugin の振る舞いは変わらない。ここを
含めると「pytest を回しただけで version が上がる」ノイズになる。
逆に `tests/` は **含める**。install は tests/ ごと copy しており、除外すると
「copy される内容」と fingerprint がずれて対応表としての意味が消えるためである。
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGINS_DIR = ROOT / "plugins"
LOCAL_MARKETPLACE_DIR = ROOT / "marketplaces" / "local"
FINGERPRINTS = LOCAL_MARKETPLACE_DIR / "plugin-fingerprints.json"
MARKETPLACE_NAME = "harness-local"

EXCLUDED_DIR_NAMES = frozenset(
    {"__pycache__", ".pytest_cache", ".build", "node_modules", ".git"}
)
EXCLUDED_FILE_NAMES = frozenset({".DS_Store"})

# plugin ツリーの中に落ちてくるが plugin の中身ではないもの。plugin ディレクトリを
# cwd にしてセッションを回すと .claude/handoff/<timestamp>.md が書かれる。これを
# 内容に数えると「作業した」だけで version が上がり、誰も待っていない版が
# 1 時間ごとに増える。ディレクトリ名だけの除外 (EXCLUDED_DIR_NAMES) では
# "handoff" という一般名を全階層で消してしまうため、相対パスの前方一致で絞る。
EXCLUDED_RELPATH_PREFIXES = (".claude/handoff/",)


def is_excluded(plugin_dir: pathlib.Path, path: pathlib.Path) -> bool:
    rel = path.relative_to(plugin_dir)
    if any(part in EXCLUDED_DIR_NAMES for part in rel.parts):
        return True
    if path.name in EXCLUDED_FILE_NAMES:
        return True
    return rel.as_posix().startswith(EXCLUDED_RELPATH_PREFIXES)


# ── plugin 走査 ────────────────────────────────────────────────────


def iter_plugins() -> list[pathlib.Path]:
    """plugins/ 実体を起点に走査する。marketplace.json を起点にすると、
    まだ載っていない新 plugin を無音で取りこぼす。"""
    return sorted(
        d
        for d in PLUGINS_DIR.iterdir()
        if (d / ".claude-plugin" / "plugin.json").is_file()
    )


def manifest_path(plugin_dir: pathlib.Path) -> pathlib.Path:
    return plugin_dir / ".claude-plugin" / "plugin.json"


def read_version(plugin_dir: pathlib.Path) -> str:
    return json.loads(manifest_path(plugin_dir).read_text(encoding="utf-8"))["version"]


def write_version(plugin_dir: pathlib.Path, version: str) -> None:
    """version の値だけを原文置換する。

    json.loads → json.dumps で往復させると整形が正規化され、`"author": {"name": ...}`
    のような 1 行記法が展開されて無関係な行まで差分に乗る (実測で確認)。
    fingerprint は内容 hash なので、その巻き添え整形自体が「変更」として次回の
    bump を誘発し、bump が bump を呼ぶ。だから原文には触らず値だけ差し替える。
    """
    path = manifest_path(plugin_dir)
    text = path.read_text(encoding="utf-8")
    current = json.loads(text)["version"]
    pattern = re.compile(
        r'("version"\s*:\s*)"' + re.escape(current) + r'"'
    )
    replaced, count = pattern.subn(lambda m: f'{m.group(1)}{json.dumps(version)}', text, count=1)
    if count != 1:
        raise SystemExit(
            f"[build-plugin-release] {path} の version 行を一意に特定できない"
        )
    path.write_text(replaced, encoding="utf-8")


def fingerprint(plugin_dir: pathlib.Path) -> str:
    """plugin ツリー全体の内容 hash。パスも hash に混ぜることで、内容が同じ
    ファイルの rename も変更として検出する。"""
    digest = hashlib.sha256()
    for path in sorted(plugin_dir.rglob("*")):
        if is_excluded(plugin_dir, path):
            continue
        rel = path.relative_to(plugin_dir).as_posix()
        if path.is_symlink():
            digest.update(f"L:{rel}:{path.readlink()}\n".encode())
        elif path.is_file():
            digest.update(f"F:{rel}:".encode())
            digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
            digest.update(b"\n")
    return digest.hexdigest()


# ── version 採番 ───────────────────────────────────────────────────


def cache_dir_name(version: str) -> str:
    """Claude Code がキャッシュディレクトリ名に使う正規化形。

    実測 (2026-08-11): plugin.json の "1.3.0+codex.20260713-1" が
    ~/.claude/plugins/cache/harness-local/harness-creator/1.3.0-codex.20260713-1/
    になっていた。`+` が `-` へ潰れる。異なる version が同じ名前へ潰れると
    「新しい版を install したのに古い copy を見続ける」無音故障になるため、
    採番後にこの形で衝突を検査する。
    """
    return version.replace("+", "-")


def next_version(current: str) -> str:
    """内容が変わった plugin の次の version を決める。

    harness の version には 2 系統が実在する:
        "0.2.0"                    素の semver
        "1.3.0+codex.20260713-1"   build metadata 付き

    採番規則は **core の patch を 1 進め、prerelease と build metadata は捨てる**。

    patch 固定にする理由: この script が知っているのは「内容が変わった」ことだけで、
    破壊的変更かどうかは判定できない。分からないものを minor/major と名乗るのは
    嘘なので、最小の主張である patch に倒す。major/minor を上げたいときは
    plugin.json を手で編集すればよい (status が released になり、bump されずに
    対応表だけ更新される — 手動採番を尊重する経路が既にある)。

    build metadata を捨てる理由は 2 つ。
      1. `1.3.1+codex.20260713-1` は「2026-07-13 の Codex ビルド」という嘘になる。
         由来を示す値を、由来が変わった後も引きずるのは誤情報。
      2. semver では build metadata は版の優先順位に参加しない。つまり
         `1.3.1+a` と `1.3.1+b` は同一版と解釈されうる。version が copy の
         同一性キーである以上、優先順位に参加しない情報を識別子へ混ぜると
         更新判定が曖昧になる。

    パースできない形式は握り潰さず止める。ここで黙って通すと、後段が誤った
    version を plugin.json へ書き込み、install 済み copy との対応が壊れる。
    """
    core = current.split("+", 1)[0].split("-", 1)[0]
    parts = core.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise SystemExit(
            f"[build-plugin-release] version {current!r} を解釈できない。"
            "major.minor.patch 形式へ手で直すこと"
        )
    major, minor, patch = (int(p) for p in parts)
    bumped = f"{major}.{minor}.{patch + 1}"
    if cache_dir_name(bumped) == cache_dir_name(current):
        raise SystemExit(
            f"[build-plugin-release] {current!r} -> {bumped!r} がキャッシュ名として同一"
        )
    return bumped


# ── 状態の突き合わせ ───────────────────────────────────────────────


def load_fingerprints() -> dict:
    if not FINGERPRINTS.exists():
        return {}
    return json.loads(FINGERPRINTS.read_text(encoding="utf-8")).get("plugins", {})


def save_fingerprints(state: dict) -> None:
    FINGERPRINTS.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "$comment": (
            "build-plugin-release.py の生成物。内容 hash と、その hash が記録された "
            "時点の version の対応表。手で編集しない。"
        ),
        "marketplace": MARKETPLACE_NAME,
        "plugins": dict(sorted(state.items())),
    }
    FINGERPRINTS.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def seconds_since_last_touch(plugin_dir: pathlib.Path) -> float:
    """plugin ツリー内で最後にファイルが変更されてからの経過秒。

    定時実行では「編集の途中」に出くわす。半分書いたファイルで version を進めると、
    その版が install 済み copy として固定され、直後の続きの編集がまた次の版を作る。
    バージョン列が編集の中間状態で埋まるのを避けるため、静穏期間を設ける。
    """
    newest = 0.0
    for path in plugin_dir.rglob("*"):
        if is_excluded(plugin_dir, path) or not path.is_file():
            continue
        newest = max(newest, path.stat().st_mtime)
    return max(0.0, time.time() - newest) if newest else float("inf")


class Lock:
    """多重起動を防ぐ。定時実行と手動実行が重なると、同じ plugin を二重に bump して
    誰も install していない版が生まれる。取得できなければ何もせず退く。"""

    def __init__(self, path: pathlib.Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("w")
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            self.handle = None
            return False
        return True

    def __exit__(self, *_exc):
        if self.handle:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
            self.handle.close()


def survey(only: set[str] | None = None) -> list[dict]:
    """各 plugin の (現 version, 現 hash, 記録) を突き合わせて状態を判定する。

    status:
      new       — 対応表に無い (新 plugin)
      changed   — 内容が変わったのに version が据え置き = 上げ忘れ
      released  — 内容が変わり version も上がっている (記録の更新だけ必要)
      clean     — 一致
    """
    recorded = load_fingerprints()
    rows = []
    for plugin_dir in iter_plugins():
        name = plugin_dir.name
        if only and name not in only:
            continue
        version = read_version(plugin_dir)
        digest = fingerprint(plugin_dir)
        prev = recorded.get(name)
        if prev is None:
            status = "new"
        elif prev.get("fingerprint") == digest and prev.get("version") == version:
            status = "clean"
        elif prev.get("version") != version:
            status = "released"
        else:
            status = "changed"
        rows.append(
            {
                "name": name,
                "dir": plugin_dir,
                "version": version,
                "fingerprint": digest,
                "recorded": prev,
                "status": status,
            }
        )
    return rows


# ── 下流工程 ───────────────────────────────────────────────────────


def regenerate_local_marketplace() -> None:
    """build-local-marketplace.py を SSOT として import する (subprocess にすると
    exit code しか受け取れず、失敗理由が握り潰される)。"""
    path = ROOT / "scripts" / "build-local-marketplace.py"
    spec = importlib.util.spec_from_file_location("_local_marketplace_for_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.main([]) != 0:
        raise SystemExit("[build-plugin-release] ローカル marketplace の再生成に失敗")


def installed_plugin_names() -> list[str]:
    """harness-local から install 済みの plugin 名。install していないものへ
    update をかけてもエラーになるだけなので、対象を実態に絞る。"""
    path = pathlib.Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8")).get("plugins", {})
    suffix = f"@{MARKETPLACE_NAME}"
    return sorted(k[: -len(suffix)] for k in data if k.endswith(suffix))


def run_install(names: list[str], dry_run: bool, project_dir: str, scope: str) -> int:
    """`claude plugin` CLI を駆動する。

    実測 (2026-08-11) で確かめた 2 つの必須条件:
      - plugin は `<name>@<marketplace>` 形式で指す。裸の名前は
        `Plugin "harness-creator" not found` になる。
      - `--scope project` は **cwd の project** を対象にする。project dir を渡す
        option が無いため、cwd を移して実行するしかない。
    """
    commands = [["claude", "plugin", "marketplace", "update", MARKETPLACE_NAME]]
    commands += [
        ["claude", "plugin", "update", f"{name}@{MARKETPLACE_NAME}", "--scope", scope]
        for name in names
    ]
    failed = 0
    for command in commands:
        print(f"  $ {' '.join(command)}")
        if dry_run:
            continue
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, cwd=project_dir, timeout=300
            )
        except subprocess.TimeoutExpired:
            # 定時実行では、応答しない CLI が次回起動まで lock を握り続けると
            # 以後の実行が全て空振りする。待たずに失敗として次へ進む。
            failed += 1
            print("    ! timeout (300s)")
            continue
        if result.returncode != 0:
            failed += 1
            print(f"    ! exit {result.returncode}: {result.stderr.strip()[:200]}")
        else:
            tail = [ln for ln in result.stdout.splitlines() if ln.strip()]
            if tail:
                print(f"    {tail[-1].strip()}")
    return failed


# ── CLI ────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="内容変更を検出して plugin version を進め、install 済み copy へ届ける"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="書き込まず、version 上げ忘れがあれば exit 1 (CI ゲート)",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="bump 後に claude CLI で marketplace / plugin を update する",
    )
    parser.add_argument("--only", action="append", default=[], help="対象 plugin 名を限定")
    parser.add_argument("--dry-run", action="store_true", help="実行内容だけ表示する")
    parser.add_argument(
        "--project-dir",
        default=str(pathlib.Path.cwd()),
        help="--install の実行 cwd。--scope project は cwd の project を対象にするため必須",
    )
    parser.add_argument(
        "--scope", default="project", choices=["user", "project", "local", "managed"]
    )
    parser.add_argument(
        "--quiet-period",
        type=float,
        default=0.0,
        metavar="MINUTES",
        help="直近 N 分以内に更新された plugin は編集中とみなし今回は触らない (定時実行用)",
    )
    parser.add_argument(
        "--lock",
        metavar="PATH",
        help="多重起動を防ぐ lock file。取得できなければ何もせず exit 0",
    )
    args = parser.parse_args(argv)

    if args.lock:
        lock = Lock(pathlib.Path(args.lock))
        if not lock.__enter__():
            print("[build-plugin-release] 別プロセスが実行中のため退出")
            return 0
        try:
            return _run(args)
        finally:
            lock.__exit__()
    return _run(args)


def _run(args) -> int:
    only = set(args.only) or None
    rows = survey(only)
    pending = [r for r in rows if r["status"] in ("changed", "new", "released")]

    if args.quiet_period > 0:
        threshold = args.quiet_period * 60
        editing = [r for r in pending if seconds_since_last_touch(r["dir"]) < threshold]
        for row in editing:
            print(f"  skip  {row['name']}: 直近 {args.quiet_period:g} 分以内に更新 (編集中とみなす)")
        pending = [r for r in pending if r not in editing]

    if args.check:
        stale = [r for r in pending if r["status"] == "changed"]
        for row in pending:
            print(f"[{row['status']:8}] {row['name']} {row['version']}")
        if stale:
            print(
                f"\n[build-plugin-release] version 上げ忘れ {len(stale)} 件。"
                "python3 scripts/build-plugin-release.py で解消する",
                file=sys.stderr,
            )
            return 1
        if pending:
            print(
                f"\n[build-plugin-release] 対応表が未更新 {len(pending)} 件。"
                "python3 scripts/build-plugin-release.py で解消する",
                file=sys.stderr,
            )
            return 1
        print(f"[build-plugin-release] OK ({len(rows)} plugins)")
        return 0

    if not pending:
        print(f"[build-plugin-release] 変更なし ({len(rows)} plugins)")
        if args.install:
            return (
                1
                if run_install(
                    installed_plugin_names(), args.dry_run, args.project_dir, args.scope
                )
                else 0
            )
        return 0

    state = load_fingerprints()
    bumped = []
    for row in pending:
        version = row["version"]
        digest = row["fingerprint"]
        if row["status"] == "changed":
            version = next_version(version)
            if not args.dry_run:
                write_version(row["dir"], version)
                # version を書いた瞬間 plugin.json が変わるので hash を取り直す。
                # 書き込み前の hash を記録すると、次の --check が自分自身の書き込みを
                # 「未記録の変更」と見なして永久に落ち続ける。
                digest = fingerprint(row["dir"])
            bumped.append(row["name"])
            print(f"  bump  {row['name']}: {row['version']} -> {version}")
        else:
            print(f"  record {row['name']}: {version} ({row['status']})")
        state[row["name"]] = {"version": version, "fingerprint": digest}

    if args.dry_run:
        print("[build-plugin-release] --dry-run のため書き込みなし")
        return 0

    save_fingerprints(state)
    regenerate_local_marketplace()
    print(f"[build-plugin-release] {len(bumped)} 件 bump / marketplace 再生成 完了")

    if args.install:
        targets = [n for n in installed_plugin_names() if not only or n in only]
        return 1 if run_install(targets, args.dry_run, args.project_dir, args.scope) else 0
    if bumped:
        print("  反映するには: python3 scripts/build-plugin-release.py --install")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
