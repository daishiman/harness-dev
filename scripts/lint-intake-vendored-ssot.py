#!/usr/bin/env python3
"""[後方互換ラッパ] vendored SSOT byte 一致検証を lint-vendored-ssot.py へ委譲する。

歴史的経緯: 本 lint は skill-intake 単独 install 用の notion_config.py vendoring を検査する
専用 lint だった。その後 harness-creator の feedback_contract_ssot.py も同型の vendoring が
必要になり (単独 install で plugin 外 repo-root への import-time 依存が ImportError になる
回帰)、検査ロジックを汎用 scripts/lint-vendored-ssot.py に一般化した。

二重実装で drift しないよう、本ファイルは VENDORED_PAIRS を保持せず後継へ委譲するだけの
薄いシムにする。Makefile / CI / 既存テストが本パスを参照しているため互換のため残す。
新規 vendored ペアの追加は lint-vendored-ssot.py の VENDORED_PAIRS に行う。
"""
import sys
from pathlib import Path

# notion_config ペアは後継の VENDORED_PAIRS に統合済み。互換のため import して委譲する。
sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "lint_vendored_ssot", Path(__file__).resolve().parent / "lint-vendored-ssot.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]


def main():
    # notion_config の vendored ペアのみを抽出して検査 (本 lint の歴史的責務)。
    pairs = [p for p in _mod.VENDORED_PAIRS if p[0].name == "notion_config.py"]
    failures = _mod.check_pairs(pairs)
    if failures:
        sys.stderr.write("[lint-intake-vendored-ssot] FAIL\n")
        for f in failures:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print(
        f"[lint-intake-vendored-ssot] OK: vendored SSOT {len(pairs)} 件が正本と byte 一致 "
        "(検査は lint-vendored-ssot.py に一般化済み)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
