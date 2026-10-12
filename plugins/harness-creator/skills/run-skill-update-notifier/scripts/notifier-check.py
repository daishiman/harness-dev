#!/usr/bin/env python3
"""Skill update notifier: changelog/version cache check.

比べるもの (Stage 1): 同じツリー (install 先またはチェックアウト) の中の plugin.json の
version (installed) と CHANGELOG.md 先頭の版 (latest)。配布元とは比べない。
非破壊原則: plugin manifest / marketplace.json / bundles.json は読み取りのみ。
書き込み先は CACHE_PATH (~/.cache/harness/version-snapshot.json) だけ
(置き換え用の一時ファイルは同じディレクトリに呼び出しごとの名前で作り、失敗したら消す)。
出力チャネル: 通知本体は stdout 1 行。hook (hook-notify-skill-end.py) がそれを systemMessage の
JSON に包んで利用者に表示させる。診断ログのみ stderr。
graceful degradation: 引数を解釈したあとの例外は握りつぶし、stderr に短文を出して exit 0。
引数の誤り (mode なし・未知の mode・notify の --plugin 欠落) だけは argparse が usage を出して
exit 2 (--help は exit 0)。
重複抑止: notify に --session-id が渡されたら、同じ session で同じ plugin を 2 度通知しない
(cache の notified.<plugin> に session_id と last_notified_at を残す)。ただし並行に呼ぶと
記録が消え、同じ通知がもう一度出ることがある (lost update。_save_cache を参照)。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "harness"
CACHE_PATH = CACHE_DIR / "version-snapshot.json"
TTL_HOURS = 24
SUPPRESS_ENV = "HARNESS_SKILLS_NOTIFY"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(data: dict) -> None:
    """CACHE_PATH を丸ごと置き換える。書けなければ stderr に短文を出して諦める。

    一時ファイルは CACHE_PATH と同じディレクトリに、呼び出しごとに違う名前で排他作成する
    (tempfile.mkstemp と同じ考え方。import を SKILL.md の stdlib 一覧から増やさないため自前)。
    固定名だと、同時に動いた 2 つが同じ一時ファイルを書き合い、片方の replace が一時ファイルを
    持ち去ったあとで、もう片方の replace が失敗して保存が飛ぶ (cache save skipped)。
    名前を分けて防ぐのは、この保存の失敗だけ。並行に呼んだときの lost update は防がない。
    _load_cache から _save_cache までに lock が無いので、後から保存したプロセスが、先に保存した
    プロセスの記録 (notified など) を上書きする。そのため並行時は重複抑止の記録が消え、同じ通知が
    もう一度出ることがある (通知が増える向きの誤り。lock は入れていない)。
    作った一時ファイルは失敗時に消す。作れなかった (名前が衝突した) ものは他人のなので消さない。
    """
    created = False
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(f".{os.getpid()}-{os.urandom(6).hex()}.tmp")
        with tmp.open("x", encoding="utf-8") as fh:
            created = True
            fh.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        tmp.replace(CACHE_PATH)
    except Exception as exc:
        if created:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        print(f"[notifier] cache save skipped: {exc}", file=sys.stderr)


def _is_fresh(cache: dict) -> bool:
    ts = cache.get("last_refreshed_at")
    if not ts:
        return False
    try:
        last = datetime.fromisoformat(ts)
    except Exception:
        return False
    return datetime.now(timezone.utc) - last < timedelta(hours=TTL_HOURS)


_VERSION_RE = re.compile(r"^##\s*\[?v?(\d+\.\d+\.\d+[^\]\s]*)", re.MULTILINE)


def _extract_latest_version(changelog_path: Path) -> str | None:
    """CHANGELOG 先頭の版数を返す共有正本。

    見出しの書式 (`## [1.2.3] - date` / `## v1.2.3` / `## 1.2.3 — date` など) に
    依存しない。repo 内で CHANGELOG 先頭の版数を見たい箇所は、別の正規表現を立てず
    ここを呼ぶ。書式を要求する形で書くと、その書式で書いた plugin だけが検査に当たり、
    当たらない書式へ逃げる圧力になる。
    """
    try:
        text = changelog_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    m = _VERSION_RE.search(text)
    return m.group(1) if m else None


def _read_manifest(plugin_dir: Path) -> dict:
    """<plugin_dir>/.claude-plugin/plugin.json。無い・読めない・object でなければ {}。"""
    pj = plugin_dir / ".claude-plugin" / "plugin.json"
    if not pj.exists():
        return {}
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _installed_version(plugin_dir: Path) -> str | None:
    return _read_manifest(plugin_dir).get("version")


def cmd_cache_status(_args) -> int:
    cache = _load_cache()
    if not cache:
        print("absent")
    elif _is_fresh(cache):
        print("fresh")
    else:
        print("stale")
    return 0


def _candidate_rank(plugin_dir: Path, installed: object, is_direct: bool) -> tuple:
    """同じ name のディレクトリが複数あるとき、大きい rank の 1 つを snapshot に採る。

    規則 (この順で比べる):
      1. `--plugin-root` で直接渡したディレクトリ (hook が渡す、いま動いている plugin)
      2. installed (plugin.json の version) が semver として読めるもの
      3. installed が semver で大きいもの (文字列順だと 1.4.9 が 1.4.43 より後になる)
      4. パスが辞書順で後ろのもの (ここまで同じでも結果を 1 つに決める)
    """
    key = _semver_key(installed) if isinstance(installed, str) else None
    return (is_direct, key is not None, key or (), str(plugin_dir))


def cmd_refresh(args) -> int:
    root = Path(args.plugins_root).resolve()
    plugin_dirs = list(sorted(root.glob("*/")))
    direct_plugin = getattr(args, "plugin_root", None)
    direct_path = Path(direct_plugin).resolve() if direct_plugin else None
    if direct_path is not None and direct_path.is_dir() and direct_path not in plugin_dirs:
        plugin_dirs.append(direct_path)
    # key は plugin.json の name (読めなければディレクトリ名)。hook は skill 名の
    # `<name>:` から plugin を引くので、key をディレクトリ名にすると install 先
    # (~/.claude/plugins/cache/<marketplace>/<name>/<version>/) の親を走査したとき
    # key が版名になり、notify が常に無出力になる。
    # 同じ name が複数出たら (install 先には版ディレクトリが並ぶ) _candidate_rank で 1 つに決める。
    chosen: dict[str, tuple[tuple, dict]] = {}
    for plugin_dir in plugin_dirs:
        manifest = _read_manifest(plugin_dir)
        name = manifest.get("name")
        if not isinstance(name, str) or not name:
            name = plugin_dir.name
        changelog = plugin_dir / "CHANGELOG.md"
        latest = _extract_latest_version(changelog) if changelog.exists() else None
        installed = manifest.get("version")
        rank = _candidate_rank(plugin_dir, installed, plugin_dir.resolve() == direct_path)
        if name not in chosen or rank > chosen[name][0]:
            chosen[name] = (rank, {"installed": installed, "latest": latest})
    data = {
        "last_refreshed_at": _now_iso(),
        "plugins": {name: entry for name, (_, entry) in sorted(chosen.items())},
    }
    # 通知済みの記録は refresh で消さない。消すと session の途中で 24h TTL を
    # 跨いだときに同じ通知がもう一度出る。
    notified = _load_cache().get("notified")
    if isinstance(notified, dict):
        data["notified"] = notified
    _save_cache(data)
    return 0


def _vprefix(version: str) -> str:
    """先頭 `v` を正規化 (既に付いていれば二重化しない。大文字 `V` も `v` に揃える)。"""
    v = version.strip()
    return f"v{v[1:]}" if v[:1] in ("v", "V") else f"v{v}"


_SEMVER_RE = re.compile(
    r"^[vV]?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


def _semver_key(version: str) -> tuple | None:
    """semver を比較可能な tuple へ。semver として読めなければ None。

    文字列の大小では版の前後が決まらない ("0.10.0" < "0.9.0" が真になる) ため、
    数値三つ組 + prerelease を semver 11 の優先順位で組み立てる。
    先頭の `v` / `V` は表記として読み飛ばす ("V1.0.0" と "1.0.0" は同じ版)。
    """
    m = _SEMVER_RE.match(version.strip())
    if not m:
        return None
    major, minor, patch, pre = m.groups()
    base = (int(major), int(minor), int(patch))
    if pre is None:
        # prerelease 無しは同じ三つ組の prerelease より後 (1.2.0 > 1.2.0-rc1)
        return base + ((1,),)
    ids: list[tuple[int, int, str]] = []
    for part in pre.split("."):
        # 数値識別子は常に英数識別子より前 (rc1 より 1 が先)
        ids.append((0, int(part), "") if part.isdigit() else (1, 0, part))
    return base + ((0, tuple(ids)),)


def _show(version: str) -> str:
    """表示用。semver として読める値は先頭を `v` に揃え、読めない値は書かれたまま出す
    (読めない値に `v` を付けると、版として読めたかのように見えるため)。"""
    return _vprefix(version) if _semver_key(version) is not None else version.strip()


def _format_line(installed: str | None, latest: str | None) -> str:
    """R2 notification-formatting: 版が食い違うときだけ 1 行の通知文字列を返す純関数。

    installed は plugin.json の version、latest は同じツリーの CHANGELOG 先頭の版で、
    どちらも作者が手で上げる。食い違いは作者の書き忘れなので、文言は作者に向けて
    向きごとに分ける (仕様の正本は references/output-format.md):
      - CHANGELOG の版が新しい: plugin.json の version の上げ忘れ
      - plugin.json の版が新しい: CHANGELOG の節の足し忘れ
      - どちらかが semver として読めない: 向きを決めず、版を比べられないとだけ言う
      - 片方欠落 / 版として等しい (表記差のみを含む) ときは空文字列
      - locale 切替や ANSI カラーは出さない (純テキスト・日本語固定)
    """
    if not installed or not latest:
        return ""
    if installed.strip() == latest.strip():
        return ""
    head = f"(plugin.json: {_show(installed)} / CHANGELOG: {_show(latest)} — "
    installed_key, latest_key = _semver_key(installed), _semver_key(latest)
    if installed_key is None or latest_key is None:
        return head + "版を比べられない)"
    if installed_key == latest_key:
        # "1.0.0" と "v1.0.0" のように表記だけが違う場合
        return ""
    if installed_key < latest_key:
        return head + "plugin.json の version が CHANGELOG より古い。version の上げ忘れの可能性)"
    return head + "CHANGELOG が plugin.json の version より古い。CHANGELOG の節の足し忘れの可能性)"


def _already_notified(cache: dict, plugin: str, session_id: str | None) -> bool:
    """同じ session で同じ plugin を通知済みなら True。session_id が無ければ判定しない。"""
    if not session_id:
        return False
    notified = cache.get("notified")
    record = notified.get(plugin) if isinstance(notified, dict) else None
    return isinstance(record, dict) and record.get("session_id") == session_id


def _record_notified(cache: dict, plugin: str, session_id: str) -> None:
    """通知した session を plugin ごとに 1 件だけ残す (古い session の記録は上書き)。

    1 件だけなので、2 つの session が同じ plugin を A→B→A と交互に使うと A に
    もう一度出る (通知が増える向きの制限。SKILL.md Gotchas に記載)。
    """
    notified = cache.get("notified")
    if not isinstance(notified, dict):
        notified = {}
    notified[plugin] = {"session_id": session_id, "last_notified_at": _now_iso()}
    cache["notified"] = notified
    _save_cache(cache)


def cmd_notify(args) -> int:
    if os.environ.get(SUPPRESS_ENV, "").lower() == "off":
        return 0
    cache = _load_cache()
    if not cache:
        return 0
    entry = cache.get("plugins", {}).get(args.plugin)
    if not entry:
        return 0
    try:
        line = _format_line(entry.get("installed"), entry.get("latest"))
    except Exception as exc:
        # R3 graceful-degradation: 整形失敗時も Skill 全体を壊さない
        print(f"[notifier] format skipped: {exc}", file=sys.stderr)
        return 0
    if not line:
        return 0
    session_id = getattr(args, "session_id", None)
    if _already_notified(cache, args.plugin, session_id):
        return 0
    # 出力チャネル = stdout (PostToolUse hook が拾い、systemMessage の JSON に包んで出す)
    print(line)
    if session_id:
        # 記録は表示の後。cache に書けなくても通知そのものは失わない
        _record_notified(cache, args.plugin, session_id)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="skill update notifier")
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("cache-status")
    p_refresh = sub.add_parser("refresh")
    p_refresh.add_argument("--plugins-root", default="plugins")
    p_refresh.add_argument(
        "--plugin-root",
        help="marketplace cache など collection 外の現在 plugin も snapshot に含める",
    )
    p_notify = sub.add_parser("notify")
    p_notify.add_argument("--plugin", required=True)
    p_notify.add_argument(
        "--session-id",
        help="同じ session で同じ plugin を 2 度通知しない。省略時は毎回通知する",
    )

    # 互換: --mode <name> 形式も受ける
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "--mode":
        argv = argv[1:]
    args = parser.parse_args(argv)
    dispatch = {
        "cache-status": cmd_cache_status,
        "refresh": cmd_refresh,
        "notify": cmd_notify,
    }
    try:
        return dispatch[args.mode](args)
    except Exception as exc:
        print(f"[notifier] no-op: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
