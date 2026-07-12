#!/usr/bin/env python3
"""焼き込みconfig (baked-default config) の内容変更と plugin version の同期を機械強制する (fail-closed)。

なぜ (= 配布完全性ギャップの恒久封鎖):
  一部 plugin は DB id 等の共有既定値を `*-config.default.json` / `*-config.fixed.json`
  に焼き込んで配布し、導入者をゼロ設定で動かす。ところが Claude Code の plugin キャッシュは
  **version 名ディレクトリでキー付け**され、同一 version の再取得は no-op になる
  (設計書 36 章 PKG-012)。よって「config の中身を変えたのに version を上げ忘れる」と、
  修正が main にマージされても既存インストール先のキャッシュに永久に届かず、消費側は
  古い (例: DB id 空) config を読み続けて fail-closed し「毎回設定を聞かれる」状態が固定化する。
  実際に mf-kessai-invoice-check で 3 DB id を default.json へ焼き込んだ際に version bump が
  漏れ、この症状が発生した。本 lint はその一手 (version bump) の欠落を機械検知して再発を封じる。

不変条件 (working tree と lockfile config-version-lock.json の完全一致を強制):
  ① 焼き込みconfig の内容 (sha256) が変わったら、その plugin の version も必ず変わっている
     こと。sha 変化 × version 据え置き = `config_changed_no_bump` (真因・最重要違反)。
  ② plugin.json の version と marketplace.json の version が一致していること
     (bump がキャッシュ更新へ届くには両方が揃っている必要がある) = `marketplace_version_mismatch`。
  ③ 全ての焼き込みconfig が lockfile に登録済み = `missing_lock_entry`。
  ④ lockfile に実在しない config エントリが残っていない = `stale_lock_entry`。
  ⑤ 内容 or version が変わったら lockfile を再生成済み = `lockfile_stale`。

usage:
  python3 scripts/lint-config-version-sync.py            # 検査 (CI 既定)。違反で exit 1
  python3 scripts/lint-config-version-sync.py --write     # lockfile を現状から再生成。
                                                          #   ただし ① / ② は書込みを拒否 (papering over 防止)
  python3 scripts/lint-config-version-sync.py --root PATH # 検査対象 repo ルートを明示 (テスト用)

exit code:
  0 違反なし / 再生成成功    1 違反検出 / 再生成拒否

CONVENTIONS: stdlib only. base ref に依存しない決定論的検査 (CI/local で同一挙動)。
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_NAME = "config-version-lock.json"

# 焼き込みconfig の命名パターン (plugins/<name>/ 直下)。
# *.default.json (mf-kessai-config.default.json 等) / *.fixed.json (notion-config.fixed.json 等)。
# `.example.json` はマッチしない (上書き専用テンプレのため対象外)。
BAKED_CONFIG_GLOBS = ("plugins/*/*.default.json", "plugins/*/*.fixed.json")

# 再生成 (--write) を拒否すべき違反種別 (これらを lockfile 更新で塗り潰すと真因を隠蔽する)。
WRITE_BLOCKERS = frozenset({"config_changed_no_bump", "marketplace_version_mismatch"})


def discover_configs(root):
    """焼き込みconfig ファイルの相対パス一覧を決定的順序で返す。"""
    found = []
    for pat in BAKED_CONFIG_GLOBS:
        found.extend(root.glob(pat))
    return sorted(str(p.relative_to(root)) for p in found)


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_plugin_version(root, plugin):
    pj = root / "plugins" / plugin / ".claude-plugin" / "plugin.json"
    if not pj.exists():
        return None
    return json.loads(pj.read_text(encoding="utf-8")).get("version")


def read_marketplace_versions(root):
    """marketplace.json の {plugin name: version}。marketplace 非掲載 plugin は含まれない。"""
    mk = root / ".claude-plugin" / "marketplace.json"
    if not mk.exists():
        return {}
    data = json.loads(mk.read_text(encoding="utf-8"))
    return {p.get("name"): p.get("version") for p in data.get("plugins", [])}


def build_current_state(root):
    """{相対config path: {plugin, version, sha256}} を返す (version は plugin.json が SSOT)。"""
    state = {}
    for rel in discover_configs(root):
        plugin = Path(rel).parts[1]
        state[rel] = {
            "plugin": plugin,
            "version": read_plugin_version(root, plugin),
            "sha256": sha256_of(root / rel),
        }
    return state


def load_lock(root):
    lp = root / LOCK_NAME
    if not lp.exists():
        return {"configs": {}}
    return json.loads(lp.read_text(encoding="utf-8"))


def evaluate(current, lock, mkt_versions):
    """(kind, key, message) の違反リストを返す純関数 (副作用なし・テスト対象コア)。"""
    violations = []
    lock_configs = lock.get("configs", {})

    for rel, cur in sorted(current.items()):
        plugin = cur["plugin"]
        # ② plugin.json ↔ marketplace.json version 整合 (marketplace 掲載 plugin のみ検査)。
        if plugin in mkt_versions and mkt_versions[plugin] != cur["version"]:
            violations.append((
                "marketplace_version_mismatch", rel,
                f"{plugin}: plugin.json version={cur['version']} が "
                f"marketplace.json version={mkt_versions[plugin]} と不一致。"
                f"両ファイルの version を揃えてください (片方だけの bump はキャッシュ更新に届かない)。",
            ))

        locked = lock_configs.get(rel)
        if locked is None:
            # ③ 新規焼き込みconfig が未登録。
            violations.append((
                "missing_lock_entry", rel,
                f"{rel} が {LOCK_NAME} 未登録。`make config-version-lock` で登録してください。",
            ))
            continue

        sha_changed = locked.get("sha256") != cur["sha256"]
        ver_changed = locked.get("version") != cur["version"]
        if sha_changed and not ver_changed:
            # ① 真因: 内容変更 × version 据え置き。
            violations.append((
                "config_changed_no_bump", rel,
                f"{plugin}: 焼き込みconfig {rel} の内容が変わったのに version が "
                f"{cur['version']} のままです。plugin.json + marketplace.json の version を "
                f"bump し `make config-version-lock` を実行してください "
                f"(bump しないと version 名でキーされるキャッシュが更新されず、"
                f"修正が配布先に届かず消費側が古い config で fail-closed し続けます)。",
            ))
        elif sha_changed or ver_changed:
            # ⑤ 内容 or version が動いたが lockfile 未再生成。
            violations.append((
                "lockfile_stale", rel,
                f"{rel}: {LOCK_NAME} が最新ではありません "
                f"(sha_changed={sha_changed}, version_changed={ver_changed})。"
                f"`make config-version-lock` で再生成してください。",
            ))

    # ④ 実在しない config が lockfile に残存。
    for rel in sorted(lock_configs):
        if rel not in current:
            violations.append((
                "stale_lock_entry", rel,
                f"{rel} は存在しないのに {LOCK_NAME} に残っています。"
                f"`make config-version-lock` で除去してください。",
            ))

    return violations


def write_lock(root, current):
    payload = {
        "_comment": (
            "焼き込みconfig (*.default.json / *.fixed.json) の内容 sha256 と plugin version を "
            "対応づける lockfile。内容を変更したら version を bump し `make config-version-lock` で "
            "再生成すること。lint-config-version-sync.py が working tree との完全一致を CI で強制する "
            "(version bump 漏れによる配布キャッシュ未更新=毎回 fail-closed を封じるため)。"
        ),
        "configs": {
            rel: {
                "plugin": current[rel]["plugin"],
                "version": current[rel]["version"],
                "sha256": current[rel]["sha256"],
            }
            for rel in sorted(current)
        },
    }
    (root / LOCK_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help="lockfile を現状から再生成 (① config_changed_no_bump / ② version 不一致 は拒否)")
    ap.add_argument("--root", default=None, help="検査対象 repo ルート (既定=このスクリプトの親)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT

    current = build_current_state(root)
    lock = load_lock(root)
    mkt = read_marketplace_versions(root)
    violations = evaluate(current, lock, mkt)

    if a.write:
        blockers = [v for v in violations if v[0] in WRITE_BLOCKERS]
        if blockers:
            sys.stderr.write(
                "[config-version-lock] 再生成を中止しました "
                "(先に version を bump/整合させてから再実行してください):\n")
            for _kind, _key, msg in blockers:
                sys.stderr.write(f"  - {msg}\n")
            return 1
        write_lock(root, current)
        sys.stdout.write(
            f"[config-version-lock] {len(current)} 件の焼き込みconfigを記録しました → {LOCK_NAME}\n")
        return 0

    if violations:
        sys.stderr.write("[config-version-lock] 違反を検出しました (exit 1):\n")
        for kind, _key, msg in violations:
            sys.stderr.write(f"  - [{kind}] {msg}\n")
        return 1
    sys.stdout.write(
        f"[config-version-lock] OK: {len(current)} 件の焼き込みconfigが version と同期しています。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
