"""log_usage.js (CJS) と log_usage.mjs (ESM) の等価性を機械保証する parity テスト。

背景 (elegant-review 2026-08-31):
  x-longpost-creator は Claude Code (CJS) と Codex (ESM) の両方で同じ記録処理を
  動かすため、log_usage を 2 実装で持っている。mjs のヘッダには
  「変更は両方へ同時に入れる」と書かれているが、これは散文の約束にすぎず、
  片方だけに引数を足しても何も落ちない状態だった (= 未強制の申告)。
  本テストは CLI 契約・stdout/stderr・exit code・追記されるログ本文の 4 点で
  両実装が一致することを実行して確かめ、片肺改修を fail-closed で止める。

正規化するのは 2 点だけ:
  - ISO8601 タイムスタンプ (実行時刻ゆえ必ず異なる)
  - 実装ごとに異なる出力先 tmp ディレクトリと自身のファイル名 (log_usage.js / .mjs)
これ以外の差分はすべて等価性の破れとして検出する。
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
# scripts は plugin ルート直下にある (lint-skill-tree 第10条: skills/*/scripts/ は .py/.sh のみ)
SCRIPTS = ROOT / "plugins" / "x-longpost-creator" / "scripts"

# 両実装とも node で起動する。node の無い環境 (CI ランナー) では等価性を確かめようが
# ないので skip する。ここが無いと FileNotFoundError('node') が「等価性の破れ」と
# 区別なく failure として出る。visual_pipeline 側と同じ前提を明示する。
pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node が PATH に無い"
)

# 両実装へ同一に与える CLI ケース。成功系・失敗系・引数エラー系・ヘルプ系を網羅する。
CASES = [
    pytest.param(["--result", "success", "--phase", "Phase 4"], id="success-minimal"),
    pytest.param(
        [
            "--result", "success",
            "--phase", "Phase 4",
            "--agent", "x-longpost-output-file",
            "--notes", "検証メモ",
        ],
        id="success-full",
    ),
    pytest.param(
        ["--result", "failure", "--phase", "Phase 3", "--error", "ValidationError"],
        id="failure-with-error",
    ),
    pytest.param(["--phase", "Phase 1"], id="missing-required-result"),
    pytest.param(["--result", "invalid"], id="invalid-result-value"),
    pytest.param(["--help"], id="help"),
]

TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z")

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node 未インストール環境では parity を実行できない"
)


def _normalize(text: str, out_dir: Path) -> str:
    text = TIMESTAMP_RE.sub("<TS>", text)
    text = text.replace(str(out_dir), "<OUT>")
    # 自身のファイル名 (usage 行に出る) は実装ごとに異なるのが正しい
    text = text.replace("log_usage.mjs", "<SELF>").replace("log_usage.js", "<SELF>")
    return text


def _run(ext: str, args: list[str], tmp_path: Path) -> dict:
    out_dir = tmp_path / ext
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["node", str(SCRIPTS / f"log_usage.{ext}"), *args],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "XLP_OUTPUT_DIR": str(out_dir)},
    )
    log = out_dir / "x-longpost-usage-log.md"
    return {
        "returncode": proc.returncode,
        "stdout": _normalize(proc.stdout, out_dir),
        "stderr": _normalize(proc.stderr, out_dir),
        "log": _normalize(log.read_text(encoding="utf-8"), out_dir) if log.exists() else None,
    }


def test_both_implementations_exist():
    assert (SCRIPTS / "log_usage.js").is_file()
    assert (SCRIPTS / "log_usage.mjs").is_file()


@pytest.mark.parametrize("args", CASES)
def test_cjs_and_esm_behave_identically(args, tmp_path):
    cjs = _run("js", args, tmp_path)
    esm = _run("mjs", args, tmp_path)
    assert cjs == esm, (
        f"log_usage.js と log_usage.mjs の挙動が args={args} で分岐した。\n"
        f"CJS: {cjs}\nESM: {esm}\n"
        "片方だけを変更した場合はもう片方へ同じ変更を入れること。"
    )
