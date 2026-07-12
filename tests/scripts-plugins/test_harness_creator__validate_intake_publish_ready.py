"""validate-intake-publish-ready.py の Gate1 (Notion publish 証跡検証) を実入力で検証する。

このスクリプトは Notion へ実通信せず、skill-intake が出力したローカル証跡
(intake.json / notion-publish-result.json / notion-log.json / notion-url.txt) を
file-based で検査し、fail-closed する。本テストは canonical_page_id / read_json の
純関数を実入力で検証し、main を subprocess で証跡を tmp_path に組み立てて全経路
(missing / 不正 JSON / status!=published / page_id 欠落 / url 不正 / page_id 不一致 /
notion_target update モード整合 / PASS) について exit code と出力を検証する。
ネットワーク・Keychain・Notion API には一切触れない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-skill-create"
    / "scripts"
    / "validate-intake-publish-ready.py"
)
SPEC = importlib.util.spec_from_file_location("validate_intake_publish_ready", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

# 32-hex page id とその dashed-UUID 表現
PAGE_HEX = "0123456789abcdef0123456789abcdef"
PAGE_UUID = "01234567-89ab-cdef-0123-456789abcdef"


# --- canonical_page_id(): 各種表現を 32-hex に正規化 ---

def test_canonical_page_id_from_plain_hex():
    assert MOD.canonical_page_id(PAGE_HEX) == PAGE_HEX


def test_canonical_page_id_from_dashed_uuid():
    assert MOD.canonical_page_id(PAGE_UUID) == PAGE_HEX


def test_canonical_page_id_from_notion_url_with_slug():
    url = f"https://www.notion.so/My-Page-Title-{PAGE_HEX}"
    assert MOD.canonical_page_id(url) == PAGE_HEX


def test_canonical_page_id_from_query_param_p():
    url = f"https://www.notion.so/workspace?v=abc&p={PAGE_HEX}"
    assert MOD.canonical_page_id(url) == PAGE_HEX


def test_canonical_page_id_uppercase_normalized_to_lower():
    assert MOD.canonical_page_id(PAGE_HEX.upper()) == PAGE_HEX


def test_canonical_page_id_empty_and_garbage():
    assert MOD.canonical_page_id(None) == ""
    assert MOD.canonical_page_id("") == ""
    assert MOD.canonical_page_id("not-a-page-id") == ""


# --- read_json() ---

def test_read_json_returns_dict(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    assert MOD.read_json(p) == {"a": 1}


def test_read_json_rejects_non_object(tmp_path):
    p = tmp_path / "arr.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    try:
        MOD.read_json(p)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "must contain a JSON object" in str(exc)


# --- main(): subprocess で証跡を組み立てて全経路を検証 ---

def _write_evidence(
    out: Path,
    *,
    log_status="published",
    result=None,
    url=f"https://www.notion.so/page-{PAGE_HEX}",
    intake=None,
    omit=(),
):
    """4 証跡ファイルを out に書く。omit に名前を入れるとそのファイルを書かない。"""
    out.mkdir(parents=True, exist_ok=True)
    if result is None:
        result = {"page_id": PAGE_HEX}
    if intake is None:
        intake = {"hint": "demo"}
    files = {
        "intake.json": json.dumps(intake),
        "notion-publish-result.json": json.dumps(result),
        "notion-log.json": json.dumps({"status": log_status, "page_id": PAGE_HEX}),
        "notion-url.txt": url,
    }
    for name, content in files.items():
        if name in omit:
            continue
        (out / name).write_text(content, encoding="utf-8")


def _run(out: Path, extra=()):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--dir", str(out), *extra],
        capture_output=True,
        text=True,
    )


def test_main_pass_with_valid_evidence(tmp_path):
    out = tmp_path / "out"
    _write_evidence(out)
    proc = _run(out)
    assert proc.returncode == 0
    assert "PASS" in proc.stdout
    assert PAGE_HEX in proc.stdout


def test_main_missing_evidence_returns_2(tmp_path):
    out = tmp_path / "out"
    _write_evidence(out, omit=("notion-url.txt",))
    proc = _run(out)
    assert proc.returncode == 2
    assert "missing publish evidence" in proc.stderr


def test_main_invalid_json_returns_2(tmp_path):
    out = tmp_path / "out"
    _write_evidence(out)
    (out / "notion-publish-result.json").write_text("{bad json", encoding="utf-8")
    proc = _run(out)
    assert proc.returncode == 2
    assert "invalid publish evidence" in proc.stderr


def test_main_status_not_published_returns_2(tmp_path):
    out = tmp_path / "out"
    _write_evidence(out, log_status="pending")
    proc = _run(out)
    assert proc.returncode == 2
    assert "expected 'published'" in proc.stderr


def test_main_no_page_id_returns_2(tmp_path):
    out = tmp_path / "out"
    # result/log のどこにも page_id が無い
    _write_evidence(out, result={"foo": "bar"})
    (out / "notion-log.json").write_text(
        json.dumps({"status": "published"}), encoding="utf-8"
    )
    proc = _run(out)
    assert proc.returncode == 2
    assert "no page_id" in proc.stderr


def test_main_invalid_url_returns_2(tmp_path):
    out = tmp_path / "out"
    _write_evidence(out, url="http://example.com/not-notion")
    proc = _run(out)
    assert proc.returncode == 2
    assert "invalid notion-url.txt" in proc.stderr


def test_main_page_id_mismatch_returns_2(tmp_path):
    out = tmp_path / "out"
    _write_evidence(out)
    other = "ffffffffffffffffffffffffffffffff"
    proc = _run(out, extra=["--page-id", other])
    assert proc.returncode == 2
    assert "page_id mismatch" in proc.stderr


def test_main_page_id_match_passes(tmp_path):
    out = tmp_path / "out"
    _write_evidence(out)
    proc = _run(out, extra=["--page-id", PAGE_UUID])  # dashed UUID -> 同一に正規化
    assert proc.returncode == 0
    assert "PASS" in proc.stdout


def test_main_invalid_intake_json_returns_2(tmp_path):
    # intake.json が JSON 配列 (オブジェクトでない) -> read_json が ValueError
    out = tmp_path / "out"
    _write_evidence(out)
    (out / "intake.json").write_text("[1, 2, 3]", encoding="utf-8")
    proc = _run(out)
    assert proc.returncode == 2
    assert "invalid intake.json" in proc.stderr


def test_main_passes_when_target_not_update_mode(tmp_path):
    # notion_target が create モードなら page_id 整合チェックをスキップして PASS
    out = tmp_path / "out"
    _write_evidence(
        out,
        intake={"hint": "demo", "notion_target": {"mode": "create"}},
    )
    proc = _run(out)
    assert proc.returncode == 0
    assert "PASS" in proc.stdout


def test_main_intake_target_update_match_passes(tmp_path):
    out = tmp_path / "out"
    _write_evidence(
        out,
        intake={
            "hint": "demo",
            "notion_target": {"mode": "update", "page_id": PAGE_UUID},
        },
    )
    proc = _run(out)
    assert proc.returncode == 0
    assert "PASS" in proc.stdout


def test_main_intake_target_update_mismatch_returns_2(tmp_path):
    out = tmp_path / "out"
    _write_evidence(
        out,
        intake={
            "hint": "demo",
            "notion_target": {
                "mode": "update",
                "page_id": "ffffffffffffffffffffffffffffffff",
            },
        },
    )
    proc = _run(out)
    assert proc.returncode == 2
    assert "does not match publish result" in proc.stderr


def test_main_intake_target_update_without_page_id_returns_2(tmp_path):
    out = tmp_path / "out"
    _write_evidence(
        out,
        intake={"hint": "demo", "notion_target": {"mode": "update"}},
    )
    proc = _run(out)
    assert proc.returncode == 2
    assert "update mode lacks page_id" in proc.stderr
