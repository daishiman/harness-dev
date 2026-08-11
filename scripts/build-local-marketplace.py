#!/usr/bin/env python3
# /// script
# name: build-local-marketplace
# purpose: Generate a clone-local Claude Code marketplace covering non-distributable plugins.
# inputs:
#   - argv: --out, --check, --name, --source-style, --only-distributable
#   - fs: plugins/*/.claude-plugin/plugin.json, .claude-plugin/marketplace.json
# outputs:
#   - fs: <out>/.claude-plugin/marketplace.json
#   - stdout: summary / drift report
# contexts: [A]
# network: false
# write-scope: <out>
# dependencies: []
# requires-python: ">=3.10"
# ///
"""clone 済み harness を `/plugins` → Add Marketplace へ登録するためのローカル
marketplace を生成する。

なぜ公開 `.claude-plugin/marketplace.json` に足さないのか
--------------------------------------------------------
公開 marketplace には `distributable: false` の plugin を載せられない。
`validate-plugin-completeness.py` が MK-004 (非配布なのに marketplace 登録残存) と
`NEVER_DISTRIBUTE` 固有名 denylist の二層で fail-closed に拒否するためで、これは
「社内専用 plugin が意図せず配布される」ことを防ぐ意図的なガードである。

一方 harness-creator / slide-report-generator のような非配布 plugin も、**手元に
clone 済みの実体を指す** ローカル marketplace 経由でなら安全に install できる。
配布 (第三者への公開) ではなく、自分の clone を Claude Code へ束ねて見せるだけで、
性質は symlink projection (sync-harness.sh) と同じだからである。

そこで marketplace を 2 枚に分ける:

  - 公開 (GitHub パターン): `.claude-plugin/marketplace.json`
      `owner/repo` 指定で解決される。配布可 plugin のみ。本 script は触らない。
  - ローカル (パス指定パターン): `marketplaces/local/.claude-plugin/marketplace.json`
      本 script の生成物。非配布 plugin を含む全 plugin を載せる。

既存 lint は全て `.claude-plugin/marketplace.json` と `plugins/*` の固定パスだけを
見るため、別ディレクトリへ出力する限り公開側のガードには一切干渉しない。

なぜ `plugins` symlink を置くのか (source 形式の制約)
----------------------------------------------------
`source` の文字列形式は **marketplace ルート配下を指す `./` 相対パス** しか受け付け
ない。`../` で親へ遡ると Claude Code が

    Failed to install: This plugin's marketplace entry is invalid: source: Invalid input

で拒否する (2026-08-11 に実機で確認)。ローカル plugin catalog 255 エントリを調べても
`./plugins/<name>` 形式が 51 件あるだけで、`../` も絶対パスも実例が 1 件も無い
(残りは url / git-subdir / github のオブジェクト形式)。

したがってパスの書き方で解決してはいけない。**plugin 実体の見え方**を変える:

  marketplaces/local/.claude-plugin/marketplace.json   ← marketplace ルート
  marketplaces/local/plugins -> ../../plugins          ← 相対 symlink (git 管理下)
  source: "./plugins/harness-creator"                  ← 公式カタログと完全同形

symlink なので plugin 実体は 1 つのまま (harness を編集すれば即反映される)。相対
symlink なので machine 非依存で commit でき、別 clone でもそのまま動く。git 管理
できることは飾りではなく、CI が「新 plugin を足したのに再生成していない」を検出
できる前提条件である。

絶対パス出力は用意しない。カタログに実例が 1 件も無く動作を確認できないため、
逃げ道として残すと「検証していない安心」を売ることになる。

新しい plugin を作ったときの自動反映
------------------------------------
`run-skill-create` の workflow-manifest が `validate-plugin-completeness.py --fix`
の直後に本 script を呼ぶ。加えて `run-ci-checks.sh` が `--check` を実行するので、
手動で plugin を追加した場合も pre-push / CI で drift が fail-closed 検出される。

usage:
  python3 scripts/build-local-marketplace.py            # 生成 (既定 marketplaces/local)
  python3 scripts/build-local-marketplace.py --check    # drift 検出のみ (書き込まない)
  python3 scripts/build-local-marketplace.py --out /tmp/mk --source-style absolute

exit code:
  0 成功 / drift なし
  1 drift あり (--check) または生成失敗

CONVENTIONS: stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGINS_DIR = ROOT / "plugins"
PUBLIC_MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
DEFAULT_OUT = ROOT / "marketplaces" / "local"

# 公開 marketplace と同名にすると、両方登録したとき Claude Code 側で
# `<plugin>@<marketplace>` の exact identity が衝突する。別名で固定する。
DEFAULT_MARKETPLACE_NAME = "harness-local"

DEFAULT_CATEGORY = "development-tools"


def _load_completeness_module():
    """`validate-plugin-completeness.py` を SSOT として import する。

    distributable の解決規則 (sidecar `references/package-contract.json` の
    `distribution.distributable` を優先し、無ければ manifest 直下へ後方互換
    fallback、未宣言は True) を再実装すると、規則が変わったとき本 script だけが
    無音で古い解釈のまま残る。ハイフンを含む file 名は通常の import 文で読めない
    ため importlib で読み込む。
    """
    path = ROOT / "scripts" / "validate-plugin-completeness.py"
    spec = importlib.util.spec_from_file_location("_completeness_for_local_marketplace", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_public_entries() -> dict[str, dict]:
    """公開 marketplace の plugins[] を {name: entry} で返す。

    description / category / tags は人手で整えられているので、ローカル側でも
    fallback として流用し表示の一貫性を保つ。
    """
    if not PUBLIC_MARKETPLACE.exists():
        return {}
    try:
        data = json.loads(PUBLIC_MARKETPLACE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries = data.get("plugins") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return {}
    return {e["name"]: e for e in entries if isinstance(e, dict) and e.get("name")}


def discover_plugins(completeness) -> list[dict]:
    """plugins/ 配下の実体を走査して plugin メタデータを返す。

    marketplace.json ではなく実体ディレクトリを起点にするのは、未登録 plugin こそ
    ローカル marketplace が拾いたい対象だからである。
    """
    found: list[dict] = []
    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SystemExit(f"[build-local-marketplace] {manifest_path}: {exc}")
        contract, err = completeness.load_package_contract(plugin_dir)
        if err:
            raise SystemExit(f"[build-local-marketplace] {err}")
        metadata = completeness.harness_metadata(manifest, contract)
        found.append(
            {
                "dir": plugin_dir,
                "name": manifest.get("name") or plugin_dir.name,
                "manifest": manifest,
                "metadata": metadata,
            }
        )
    return found


def should_include(plugin: dict, include_internal: bool) -> bool:
    """この plugin をローカル marketplace に載せるか。

    判定式 `is not False` は `validate-plugin-completeness.py` の MK-004 逆ガードと
    同一にしてある。両者が同じ式を使うことで「公開に載る集合」と
    「--only-distributable で載る集合」が定義上一致し、片方だけ解釈が漂流しない。

    非配布 plugin (`distributable: false`) は clone-local 用途のときだけ載せる。
    NEVER_DISTRIBUTE 固有名の追加判定は置かない。あの denylist は「配布物へ混入
    させない」ための守りであり、ローカル marketplace は配布物ではないうえ、
    harness-creator 自身がそこに含まれる = 除外したら本 script の目的が消える。
    公開側への混入は MK-004 が独立に守り続ける。
    """
    if plugin["metadata"].get("distributable") is not False:
        return True
    return include_internal


PLUGINS_LINK_NAME = "plugins"


def plugins_link_target(out_dir: pathlib.Path) -> str:
    """`<out>/plugins` symlink が指すべき相対パス。

    相対にするのは生成物を machine 非依存に保つため。`--out` を repo 外へ向けた
    場合 (test) でも relpath が正しく遡る。
    """
    return os.path.relpath(PLUGINS_DIR.resolve(), out_dir.resolve())


def ensure_plugins_link(out_dir: pathlib.Path) -> bool:
    """`<out>/plugins` -> `<repo>/plugins` の相対 symlink を張る。既に正しければ no-op。

    この symlink が無いと `source: "./plugins/<name>"` が解決できず install が
    静かに失敗する。marketplace.json と同じ強度で生成・検証する対象。
    """
    link = out_dir / PLUGINS_LINK_NAME
    want = plugins_link_target(out_dir)
    if link.is_symlink():
        if os.readlink(link) == want:
            return False
        link.unlink()
    elif link.exists():
        raise SystemExit(
            f"[build-local-marketplace] {link} が symlink ではない実体。手動で退避すること"
        )
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(want, target_is_directory=True)
    return True


def check_plugins_link(out_dir: pathlib.Path) -> str | None:
    """symlink の状態を検査し、問題があれば理由を返す。"""
    link = out_dir / PLUGINS_LINK_NAME
    if not link.is_symlink():
        return f"{link} が未作成" if not link.exists() else f"{link} が symlink ではない"
    want = plugins_link_target(out_dir)
    actual = os.readlink(link)
    if actual != want:
        return f"{link} の向き先が {actual} (期待: {want})"
    if not link.resolve().is_dir():
        return f"{link} が解決できない (向き先 {actual} が存在しない)"
    return None


def build_entry(plugin: dict, public: dict[str, dict]) -> dict:
    """1 plugin 分の marketplace エントリを組み立てる。"""
    name = plugin["name"]
    manifest = plugin["manifest"]
    metadata = plugin["metadata"]
    base = public.get(name, {})
    return {
        "name": name,
        # marketplace ルート配下を指す `./` 相対パス。`../` で遡ると Claude Code が
        # `source: Invalid input` で拒否する。`plugins` symlink がこの形を成立させる。
        "source": f"./{PLUGINS_LINK_NAME}/{name}",
        "description": manifest.get("description") or base.get("description") or name,
        # version は manifest が SSOT。公開 marketplace 側の drift に引きずられない。
        "version": manifest.get("version") or base.get("version") or "0.0.0",
        "category": metadata.get("category") or base.get("category") or DEFAULT_CATEGORY,
        "tags": list(metadata.get("tags") or base.get("tags") or []),
    }


def build_document(entries: list[dict], name: str, clone_local: list[str]) -> dict:
    # clone_local は entry 内ではなくトップ metadata に置く。marketplace entry の
    # schema は Claude Code 側が検証するため、非公式キーを混ぜると将来の版で
    # 弾かれうる。metadata は元々自由記述の領域なので安全side。
    return {
        "name": name,
        "description": (
            "Local-clone marketplace for the harness repository. "
            "Sources point at this working copy, so edits take effect without re-publishing."
        ),
        "version": "1.0.0",
        "metadata": {
            "generated_by": "scripts/build-local-marketplace.py",
            "regenerate": "python3 scripts/build-local-marketplace.py",
            # source は ./plugins/<name>。この symlink が実体へ橋渡しする。
            "plugins_link": f"{PLUGINS_LINK_NAME} -> <repo>/plugins (相対 symlink)",
            # 公開 marketplace に載らない = clone 実体を前提とする plugin。
            "clone_local_plugins": clone_local,
        },
        "owner": {"name": "harness maintainers"},
        "plugins": entries,
    }


def render(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def generate(name: str, include_internal: bool) -> tuple[str, list[dict], list[str]]:
    completeness = _load_completeness_module()
    public = load_public_entries()
    selected = [p for p in discover_plugins(completeness) if should_include(p, include_internal)]
    entries = [build_entry(p, public) for p in selected]
    clone_local = sorted(
        p["name"] for p in selected if p["metadata"].get("distributable") is False
    )
    return render(build_document(entries, name, clone_local)), entries, clone_local


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ローカル clone 用 marketplace を生成する")
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help=f"marketplace ルートの出力先ディレクトリ (既定: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_MARKETPLACE_NAME,
        help=f"marketplace 名 (既定: {DEFAULT_MARKETPLACE_NAME})",
    )
    parser.add_argument(
        "--only-distributable",
        action="store_true",
        help="非配布 plugin を除外する (公開 marketplace と同じ集合を再現する検証用)",
    )
    parser.add_argument("--check", action="store_true", help="書き込まず drift のみ報告する")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out).expanduser().resolve()
    text, entries, internal = generate(args.name, not args.only_distributable)
    target = out_dir / ".claude-plugin" / "marketplace.json"

    if args.check:
        # marketplace.json と symlink は「両方揃って初めて install できる」一組。
        # 片方だけ検査すると symlink 消失を無音で見逃し、install 時に初めて露見する。
        problems = []
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current is None:
            problems.append(f"{target} が未生成")
        elif current != text:
            problems.append(f"{target} の内容が古い")
        link_problem = check_plugins_link(out_dir)
        if link_problem:
            problems.append(link_problem)
        if not problems:
            print(f"[build-local-marketplace] OK: {len(entries)} plugin(s), no drift")
            return 0
        print("[build-local-marketplace] DRIFT:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("  再生成: python3 scripts/build-local-marketplace.py", file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    linked = ensure_plugins_link(out_dir)
    shown = target.relative_to(ROOT) if target.is_relative_to(ROOT) else target
    print(f"[build-local-marketplace] wrote {shown}")
    print(f"  marketplace: {args.name}")
    print(f"  plugins:     {len(entries)} (clone-local only: {len(internal)})")
    print(
        f"  plugins link: {out_dir / PLUGINS_LINK_NAME} -> {plugins_link_target(out_dir)}"
        f"{' (作成)' if linked else ''}"
    )
    if internal:
        print(f"  local-only:  {', '.join(internal)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
