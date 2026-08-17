#!/usr/bin/env python3
# /// script
# name: lint-distributable-ssot
# version: 0.1.0
# purpose: distributable 判定の真偽が sidecar (references/package-contract.json の
#          distribution.distributable) と manifest (.claude-plugin/plugin.json 直下) の
#          2箇所に分裂している状態を fail-closed 検査する。harness_metadata() は
#          sidecar-first で解決するため、manifest だけを編集しても無音で無視され、
#          「公開したはずなのに marketplace に載らない」事故が再発する。
# inputs:
#   - fs: plugins/*/.claude-plugin/plugin.json
#   - fs: plugins/*/references/package-contract.json
# outputs:
#   - stdout: OK / 違反一覧
#   - exit: 0=OK / 1=違反あり / 2=読み込み不能 (fail-closed)
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""distributable の SSOT 分裂検査。

`scripts/validate-plugin-completeness.py` の `harness_metadata()` は
sidecar の `distribution.distributable` を優先し、無ければ manifest 直下へ
後方互換 fallback する (未宣言は True)。この解決順は正しく動くが、
**どちらに書くのが正か** はコード上どこにも表明されていない。結果として
同じ意味の値が2箇所に書かれ、片方だけ更新されたときに sidecar が黙って
勝つ。本 lint はその分裂状態を可視化し、fail-closed で止める。
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"

SENTINEL = object()  # 「キーそのものが無い」を False と区別するための番兵


def read_declarations(plugin_dir: pathlib.Path) -> dict:
    """1 plugin の manifest / sidecar 双方の distributable 宣言を採取する。

    値が無いことと False であることは意味が違うので、SENTINEL で区別する。
    """
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    sidecar_path = plugin_dir / "references" / "package-contract.json"
    sidecar_value = SENTINEL
    if sidecar_path.is_file():
        contract = json.loads(sidecar_path.read_text(encoding="utf-8"))
        distribution = contract.get("distribution")
        if isinstance(distribution, dict) and "distributable" in distribution:
            sidecar_value = distribution["distributable"]

    return {
        "name": plugin_dir.name,
        "manifest": manifest.get("distributable", SENTINEL),
        "sidecar": sidecar_value,
        "has_sidecar_file": sidecar_path.is_file(),
    }


def check_distributable_ssot(records: list[dict]) -> list[str]:
    """宣言の一覧を検査し違反メッセージのリストを返す (純関数・I/O 非依存)。

    違反コード:
      DS-001 = manifest と sidecar で値が食い違う (sidecar が黙って勝つ)
      DS-002 = 同じ値が2箇所に重複記述されている
    """
    violations: list[str] = []
    for rec in records:
        name = rec["name"]
        manifest = rec["manifest"]
        sidecar = rec["sidecar"]

        both_declared = manifest is not SENTINEL and sidecar is not SENTINEL
        if not both_declared:
            continue

        if manifest != sidecar:
            violations.append(
                f"DS-001: {name}: distributable が食い違っています "
                f"(manifest={manifest!r} / sidecar={sidecar!r})。"
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
            f"DS-002: {name}: distributable が manifest と sidecar に重複記述されています "
            f"(どちらも {sidecar!r})。harness_metadata() は sidecar を先に見るため "
            f"manifest 側は読まれません。.claude-plugin/plugin.json の "
            f'"distributable" を削除し、references/package-contract.json の '
            f"distribution.distributable を唯一の正本にしてください"
        )

    return violations


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
        except (OSError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"lint-distributable-ssot: {plugin_dir.name}: 読み込み失敗: {exc}\n")
            return 2

    violations = check_distributable_ssot(records)
    if violations:
        print(f"FAIL: distributable SSOT 違反 {len(violations)} 件")
        for v in violations:
            print(f"  - {v}")
        return 1

    print(f"OK: {len(records)} plugin の distributable 宣言が単一の正本に収まっています")
    return 0


if __name__ == "__main__":
    sys.exit(main())
