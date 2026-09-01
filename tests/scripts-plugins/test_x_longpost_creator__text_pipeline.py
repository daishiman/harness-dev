"""X長文の A/B 表現契約と検証失敗時の出力原子性を CLI 境界で検査する。"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "x-longpost-creator"
SCRIPTS = PLUGIN / "scripts"
TEMPLATE = PLUGIN / "assets" / "output-template.md"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node が PATH に無い"
)

TITLE = "検証で壊れた成果物を公開しないための設計"
H2S = (
    "失敗した下書きを出力先に置かない",
    "同じ本文を二つの改行形式で保つ",
    "機械検証が合格した後だけ配置する",
)


def _run(script: str, *args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(SCRIPTS / script), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _short_bodies(*, drift=False, packed=False):
    sentences = ["一つ目の主張です。", "二つ目の主張です。", "三つ目の主張です。"]
    a = "\n\n".join(
        f"## {heading}\n\n{sentence}" for heading, sentence in zip(H2S, sentences)
    )
    b_sentences = list(sentences)
    if drift:
        b_sentences[-1] = "三つ目の内容を勝手に変えました。"
    if packed:
        b = f"{b_sentences[0]}{b_sentences[1]}\n\n{b_sentences[2]}"
    else:
        b = "\n\n".join(b_sentences)
    return a, b


def _vars(a_body: str, b_body: str):
    return {
        "タイトル": TITLE,
        "キャッチコピー": "壊れたファイルを公開しない",
        "投稿文_短文": "",
        "投稿文_長文A": a_body,
        "投稿文_長文B": b_body,
        "メモ": "検証用メモ",
        "文字起こし": "",
        "IdeaCompass": "",
        "ハッシュタグ": "",
    }


def _expanded_file(tmp_path: Path, a_body: str, b_body: str) -> Path:
    output = tmp_path / f"X長文投稿-prompt作成 - 2026-08-31_{TITLE}.md"
    vars_file = tmp_path / "vars.json"
    vars_file.write_text(
        json.dumps(_vars(a_body, b_body), ensure_ascii=False), encoding="utf-8"
    )
    proc = _run(
        "expand-template.js",
        "--template", str(TEMPLATE),
        "--vars-file", str(vars_file),
        "--output", str(output),
        "--json",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return output


def _check(path: Path) -> subprocess.CompletedProcess:
    return _run(
        "validate-headings.js",
        "--file", str(path),
        "--title", TITLE,
        "--strict-h2-count",
    )


def test_normalized_a_b_content_and_one_sentence_per_line_pass(tmp_path):
    a_body, b_body = _short_bodies()
    output = _expanded_file(tmp_path, a_body, b_body)

    proc = _check(output)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    checks = {item["id"]: item for item in json.loads(proc.stdout)["checks"]}
    assert checks["F4"]["ok"] is True
    assert checks["F5"]["ok"] is True


def test_normalized_a_b_drift_is_rejected(tmp_path):
    a_body, b_body = _short_bodies(drift=True)
    output = _expanded_file(tmp_path, a_body, b_body)

    proc = _check(output)

    assert proc.returncode == 1
    failed = json.loads(proc.stdout)["failed"]
    assert any(item.startswith("F4 ") for item in failed)


def test_two_sentences_on_one_b_line_are_rejected(tmp_path):
    a_body, b_body = _short_bodies(packed=True)
    output = _expanded_file(tmp_path, a_body, b_body)

    proc = _check(output)

    assert proc.returncode == 1
    failed = json.loads(proc.stdout)["failed"]
    assert any(item.startswith("F5 ") for item in failed)


def test_b_body_line_without_sentence_terminator_is_rejected(tmp_path):
    a_body, b_body = _short_bodies()
    b_body = b_body.replace("二つ目の主張です。", "二つ目の主張です")
    output = _expanded_file(tmp_path, a_body, b_body)

    proc = _check(output)

    assert proc.returncode == 1
    failed = json.loads(proc.stdout)["failed"]
    assert any(item.startswith("F5 ") for item in failed)


def test_decimal_point_inside_single_b_sentence_is_not_a_boundary(tmp_path):
    sentences = ["一つ目の主張です。", "バージョン1.2でも同じ主張です。", "三つ目の主張です。"]
    a_body = "\n\n".join(
        f"## {heading}\n\n{sentence}" for heading, sentence in zip(H2S, sentences)
    )
    b_body = "\n\n".join(sentences)
    output = _expanded_file(tmp_path, a_body, b_body)

    proc = _check(output)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    checks = {item["id"]: item for item in json.loads(proc.stdout)["checks"]}
    assert checks["F5"]["ok"] is True


def test_failed_integrated_pipeline_keeps_existing_destination_bytes(tmp_path):
    sentence = "これは中心パイプラインの失敗原子性を確かめる文章です。"
    sections = [sentence * 22 for _ in H2S]
    a_body = "\n\n".join(
        f"## {heading}\n\n{body}" for heading, body in zip(H2S, sections)
    )
    b_lines = [sentence for _ in range(65)] + ["本文を意図的に改変しました。"]
    b_body = "\n\n".join(b_lines)

    output_dir = tmp_path / "published"
    output_dir.mkdir()
    env = os.environ.copy()
    env["XLP_OUTPUT_DIR"] = str(output_dir)
    filename_proc = _run(
        "generate-filename.js",
        "--date", "2026-08-31",
        "--title", TITLE,
        env=env,
    )
    assert filename_proc.returncode == 0, filename_proc.stdout + filename_proc.stderr
    generated = json.loads(filename_proc.stdout)
    destination = Path(generated["fullPath"])
    destination.write_bytes(b"previous verified artifact\n")
    before = destination.read_bytes()

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    candidate = _expanded_file(scratch, a_body, b_body)
    assert candidate.name == generated["filename"]

    heading_check = _check(candidate)
    emoji_check = _run("check-no-emoji.js", "--file", str(candidate))
    count_check = _run(
        "count-chars.js",
        "--text", f"# {TITLE}\n\n{a_body}",
        "--min", "1800",
        "--max", "2200",
    )
    assert heading_check.returncode == 1
    assert emoji_check.returncode == 0
    assert count_check.returncode == 0, count_check.stdout + count_check.stderr

    if all(p.returncode == 0 for p in (heading_check, emoji_check, count_check)):
        candidate.replace(destination)

    assert destination.read_bytes() == before
    assert candidate.exists()
