#!/usr/bin/env python3
"""AC-C14-1 の golden SVG を 9 パターン分だけ記録する補助 script。

テストではない (discover の pattern test_*.py に一致しない)。

使い方 (実装が入ったあと 1 回だけ):

    python3 plugins/guide-doc-generator/tests/render-diagram-svg.py/record_goldens.py

記録の前に、golden に依存しない構造検査 (test_svg_contract / test_patterns /
test_determinism の GoldenSvgTest 以外) が全て緑であることを確認すること。
構造検査が赤のまま golden を記録すると、誤った出力を正としてしまう。
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _harness as H  # noqa: E402


def main():
    H.require_script()
    H.GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    failed = 0
    for pattern in H.PATTERNS:
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.spec_for(pattern))
        if res.returncode != 0:
            sys.stderr.write("FAIL %s exit=%d\n%s\n" % (pattern, res.returncode, res.stderr))
            failed += 1
            continue
        target = H.GOLDEN_DIR / ("%s.svg" % pattern)
        target.write_bytes(res.stdout_bytes)
        sys.stdout.write("recorded %s (%d bytes)\n" % (target, len(res.stdout_bytes)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
