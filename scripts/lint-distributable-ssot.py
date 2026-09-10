#!/usr/bin/env python3
# /// script
# name: lint-distributable-ssot
# version: 0.2.0
# purpose: 配布メタデータ (distributable / bundle_targets / category / tags) の真偽が
#          sidecar (references/package-contract.json の distribution.*) と manifest
#          (.claude-plugin/plugin.json 直下) の 2箇所に分裂している状態を fail-closed 検査する。
#          harness_metadata() は sidecar-first で解決するため、manifest だけを編集しても
#          無音で無視され、「公開したはずなのに marketplace に載らない」事故が再発する。
# inputs:
#   - fs: plugins/*/.claude-plugin/plugin.json
#   - fs: plugins/*/references/package-contract.json
#   - fs: .claude-plugin/marketplace.json  (走査欠落の検出に使う。無ければその検査だけ省略)
# outputs:
#   - stdout: OK / 違反一覧
#   - exit: 0=OK / 1=違反あり / 2=読み込み不能・走査欠落 (fail-closed)
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""配布メタデータの SSOT 分裂検査。

`scripts/validate-plugin-completeness.py` の `harness_metadata()` は
sidecar の `distribution.<key>` を優先し、無ければ manifest 直下へ
後方互換 fallback する。この解決順は正しく動くが、**どちらに書くのが正か**
はコード上どこにも表明されていない。結果として同じ意味の値が2箇所に書かれ、
片方だけ更新されたときに sidecar が黙って勝つ。本 lint はその分裂状態を
可視化し、fail-closed で止める。

対象は distributable 1 キーではない。bundle_targets / category / tags も
まったく同じ sidecar-first fallback を持ち、しかも bundle_targets と tags は
manifest 側に別名 (bundles / keywords) の第2 fallback を持つ。よって
「manifest に bundles、sidecar に bundle_targets」という形の分裂も成立する。
この lint の前提である解決順そのものは
tests/scripts-root/test_root__harness_metadata_resolution.py が固定している。
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"

SENTINEL = object()  # 「キーそのものが無い」を False / [] と区別するための番兵

# harness_metadata() の解決規則をそのまま写したもの。
#   key      : sidecar (distribution.*) 側のキー名。sidecar は常に「キーの有無」で解決される。
#   aliases  : manifest 側で読まれるキーを優先順に並べたもの。
#   or_chain : manifest 側の fallback が `a or b or default` 形かどうか。
#              True のとき falsy 値 (空リスト等) は「宣言なし」として素通りするため、
#              lint も同じく truthy でなければ宣言とみなさない。ここを presence 判定に
#              揃えてしまうと、実装が読まない値を違反として報告することになる。
FIELDS = [
    {"key": "distributable", "aliases": ("distributable",), "or_chain": False},
    {"key": "bundle_targets", "aliases": ("bundle_targets", "bundles"), "or_chain": True},
    {"key": "category", "aliases": ("category",), "or_chain": False},
    {"key": "tags", "aliases": ("tags", "keywords"), "or_chain": True},
]


def manifest_declaration(manifest: dict, field: dict):
    """manifest 側の実効宣言を (キー名, 値) で返す。宣言が無ければ (None, SENTINEL)。

    or_chain のフィールドは falsy を読み飛ばす — harness_metadata() がそうするため。
    """
    for alias in field["aliases"]:
        if alias not in manifest:
            continue
        value = manifest[alias]
        if field["or_chain"] and not value:
            continue
        return alias, value
    return None, SENTINEL


def manifest_alias_duplicates(manifest: dict, field: dict) -> list[str]:
    """manifest 内で別名が二重宣言されているキー名。or_chain 以外は別名が無いので常に空。"""
    if not field["or_chain"]:
        return []
    return [a for a in field["aliases"] if a in manifest and manifest[a]]


def read_declarations(plugin_dir: pathlib.Path) -> dict:
    """1 plugin の manifest / sidecar 双方の配布メタデータ宣言を採取する。

    値が無いことと False / [] であることは意味が違うので、SENTINEL で区別する。
    """
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # top-level が dict でない manifest を .get() へ渡すと AttributeError が
    # 素通りして traceback + exit 1 になる。exit 1 は「違反あり」の意味なので、
    # 読み込み不能 (exit 2) と取り違えられる。ValueError にして呼び出し側の
    # JSON 破損ハンドラ (exit 2) と同じ経路へ寄せる。
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path}: top-level が object ではありません")

    sidecar_path = plugin_dir / "references" / "package-contract.json"
    distribution: dict = {}
    if sidecar_path.is_file():
        contract = json.loads(sidecar_path.read_text(encoding="utf-8"))
        if not isinstance(contract, dict):
            raise ValueError(f"{sidecar_path}: top-level が object ではありません")
        raw = contract.get("distribution")
        if isinstance(raw, dict):
            distribution = raw

    fields = {}
    for field in FIELDS:
        alias, manifest_value = manifest_declaration(manifest, field)
        key = field["key"]
        fields[key] = {
            "manifest_key": alias,
            "manifest": manifest_value,
            "sidecar": distribution[key] if key in distribution else SENTINEL,
            "manifest_aliases": manifest_alias_duplicates(manifest, field),
        }

    return {"name": plugin_dir.name, "fields": fields}


def same_value(a, b) -> bool:
    """SSOT 判定用の同値比較。bool と int を同一視しない。

    Python では `True == 1` なので、素の == だと manifest に 1、sidecar に true と
    書かれた食い違い (DS-001) を「同値の重複」(DS-002) と誤分類する。JSON としては
    別の型であり、修正の指示内容も変わるため区別する。
    """
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return a == b


def check_distributable_ssot(records: list[dict]) -> list[str]:
    """宣言の一覧を検査し違反メッセージのリストを返す (純関数・I/O 非依存)。

    違反コード:
      DS-001 = manifest と sidecar で値が食い違う (sidecar が黙って勝つ)
      DS-002 = 同じ値が manifest と sidecar に重複記述されている
      DS-003 = manifest 内で別名が二重宣言されている (bundle_targets と bundles など)
    """
    violations: list[str] = []
    for rec in records:
        name = rec["name"]
        for field in FIELDS:
            key = field["key"]
            state = rec["fields"][key]
            manifest = state["manifest"]
            sidecar = state["sidecar"]

            aliases = state["manifest_aliases"]
            if len(aliases) > 1:
                head, *rest = field["aliases"]
                violations.append(
                    f"DS-003: {name}: manifest 内で {key} が別名重複しています "
                    f"({'/'.join(aliases)})。harness_metadata() は {head} を先に読むため "
                    f"{'/'.join(rest)} は読まれません。読まれない側を削除してください"
                )

            if manifest is SENTINEL or sidecar is SENTINEL:
                continue

            manifest_key = state["manifest_key"]
            if not same_value(manifest, sidecar):
                violations.append(
                    f"DS-001: {name}: {key} が食い違っています "
                    f"(manifest.{manifest_key}={manifest!r} / sidecar.{key}={sidecar!r})。"
                    f"harness_metadata() は sidecar を優先するため実効値は {sidecar!r} です。"
                    f"どちらか一方に寄せてください"
                )
                continue

            # 値が一致していても違反とする。今は同値でも、片方だけ更新された瞬間に
            # DS-001 (sidecar が黙って勝つ) へ変わる。重複記述はその事故の必要条件であり、
            # 「今は無害」は「明日も無害」を意味しない。実際 2026-08-17 に 5 plugin を
            # 配布化したとき、manifest と sidecar の両方を手で書き換える必要があった。
            #
            # 寄せ先は sidecar 固定にする。harness_metadata() が sidecar-first で解決する以上、
            # manifest 側の値は sidecar があるかぎり一度も読まれない死んだ宣言だからである。
            # 逆向き (manifest へ寄せる) を許すと解決順との齟齬が残り続ける。
            violations.append(
                f"DS-002: {name}: {key} が manifest と sidecar に重複記述されています "
                f"(どちらも {sidecar!r})。harness_metadata() は sidecar を先に見るため "
                f"manifest.{manifest_key} は読まれません。.claude-plugin/plugin.json の "
                f'"{manifest_key}" を削除し、references/package-contract.json の '
                f"distribution.{key} を唯一の正本にしてください"
            )

    return violations


def marketplace_plugin_names() -> set[str]:
    """marketplace.json が載せている plugin 名。読めない場合は空集合 (この検査だけ省略)。"""
    if not MARKETPLACE.is_file():
        return set()
    try:
        data = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(data, dict):
        return set()
    entries = data.get("plugins")
    if not isinstance(entries, list):
        return set()
    return {e["name"] for e in entries if isinstance(e, dict) and isinstance(e.get("name"), str)}


def main() -> int:
    if not PLUGINS.is_dir():
        sys.stderr.write(f"lint-distributable-ssot: plugins/ がありません: {PLUGINS}\n")
        return 2

    records: list[dict] = []
    for plugin_dir in sorted(PLUGINS.iterdir()):
        if not plugin_dir.is_dir():
            continue
        if not (plugin_dir / ".claude-plugin" / "plugin.json").is_file():
            continue
        try:
            records.append(read_declarations(plugin_dir))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            sys.stderr.write(f"lint-distributable-ssot: {plugin_dir.name}: 読み込み失敗: {exc}\n")
            return 2

    # 読める plugin が 1 件も無いのに OK を出すと、走査経路が壊れたときに
    # 「検査した結果みつからなかった」と区別がつかない (vacuous green)。
    if not records:
        sys.stderr.write(
            f"lint-distributable-ssot: {PLUGINS} 配下に manifest を持つ plugin が 1 件もありません\n"
        )
        return 2

    # 「1 件も無い」だけでなく「一部しか拾えていない」も緑にしない。走査が 22→1 に
    # 減っても違反が 0 なら OK と出てしまうため、独立した第2の名簿 (marketplace.json)
    # と突き合わせる。定数を埋めると台帳が増えるので、既存の on-disk 名簿を使う。
    scanned = {r["name"] for r in records}
    missing = sorted(marketplace_plugin_names() - scanned)
    if missing:
        sys.stderr.write(
            "lint-distributable-ssot: marketplace.json に載っているのに走査できなかった "
            f"plugin があります: {', '.join(missing)}\n"
        )
        return 2

    violations = check_distributable_ssot(records)
    if violations:
        print(f"FAIL: 配布メタデータの SSOT 違反 {len(violations)} 件")
        for v in violations:
            print(f"  - {v}")
        return 1

    keys = "/".join(f["key"] for f in FIELDS)
    print(f"OK: {len(records)} plugin の配布メタデータ ({keys}) が単一の正本に収まっています")
    return 0


if __name__ == "__main__":
    sys.exit(main())
