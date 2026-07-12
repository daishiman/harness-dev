"""Genuine functional tests (scripts4) for
plugins/harness-creator/skills/run-skill-create/scripts/validate-intake-publish-ready.py.

このスクリプトは run-skill-create の Gate 1。skill-intake が Notion publish 済みである
ことを **ローカルの証拠ファイル** (notion-publish-result.json / notion-log.json /
notion-url.txt / intake.json) だけで fail-closed 検証する。Notion を一切叩かない設計
なので network stub は不要 — tmp_path に合格 fixture と各違反 fixture を組み立てて純関数
(canonical_page_id / read_json) と main() の全 return 経路を genuine に網羅する。

他ディレクトリと同名にならないよう _r4 サフィックスを付す。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO / "plugins" / "harness-creator" / "skills" / "run-skill-create"
    / "scripts" / "validate-intake-publish-ready.py"
)

_SPEC = importlib.util.spec_from_file_location("validate_intake_publish_ready_r4", SCRIPT)
VIP = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(VIP)

# 32-hex canonical page id (UUID なしの compact 形) と対応 URL
PAGE_HEX = "a" * 32
DASHED = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
NOTION_URL = f"https://www.notion.so/{PAGE_HEX}"


# ============================================================
# canonical_page_id: 各入力形式 → 32-hex 正規化
# ============================================================

def test_canonical_none_and_empty():
    assert VIP.canonical_page_id(None) == ""
    assert VIP.canonical_page_id("") == ""


def test_canonical_compact_32hex_passthrough():
    assert VIP.canonical_page_id(PAGE_HEX) == PAGE_HEX


def test_canonical_dashed_uuid():
    assert VIP.canonical_page_id(DASHED) == PAGE_HEX


def test_canonical_url_with_trailing_slug_hyphen_id():
    # slug-<32hex> の最後トークンが id
    url = f"https://www.notion.so/My-Page-Title-{PAGE_HEX}"
    assert VIP.canonical_page_id(url) == PAGE_HEX


def test_canonical_url_with_p_query_param():
    url = f"https://www.notion.so/workspace?v=xyz&p={PAGE_HEX}"
    assert VIP.canonical_page_id(url) == PAGE_HEX


def test_canonical_url_with_page_id_query_param():
    url = f"https://www.notion.so/x?page_id={DASHED}"
    assert VIP.canonical_page_id(url) == PAGE_HEX


def test_canonical_url_strips_query_and_fragment_in_path():
    url = f"https://www.notion.so/{PAGE_HEX}?v=abc#section"
    assert VIP.canonical_page_id(url) == PAGE_HEX


def test_canonical_invalid_returns_empty():
    assert VIP.canonical_page_id("not-a-page") == ""
    assert VIP.canonical_page_id("https://example.com/page") == ""


def test_canonical_short_hex_not_32_returns_empty():
    assert VIP.canonical_page_id("deadbeef") == ""


def test_canonical_uppercase_normalized_to_lower():
    upper = "A" * 32
    assert VIP.canonical_page_id(upper) == PAGE_HEX


# ============================================================
# read_json: 正常 dict / 非 dict / 不正 JSON
# ============================================================

def test_read_json_dict(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert VIP.read_json(p) == {"a": 1}


def test_read_json_non_dict_raises(tmp_path):
    p = tmp_path / "list.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError):
        VIP.read_json(p)


def test_read_json_invalid_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        VIP.read_json(p)


# ============================================================
# main(): tmp_path に証拠ファイルを組み立てて全 return 経路を駆動
# ============================================================

def _make_evidence(
    out_dir: Path,
    *,
    intake=None,
    result=None,
    log=None,
    url=NOTION_URL,
    omit=(),
):
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "intake.json": intake if intake is not None else {"hint": "demo"},
        "notion-publish-result.json": result if result is not None else {"page_id": PAGE_HEX},
        "notion-log.json": log if log is not None else {"status": "published"},
    }
    for name, payload in files.items():
        if name in omit:
            continue
        (out_dir / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    if "notion-url.txt" not in omit:
        (out_dir / "notion-url.txt").write_text(url, encoding="utf-8")
    return out_dir


def _run(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["validate-intake-publish-ready.py", *args])
    return VIP.main()


def test_main_happy_path(tmp_path, monkeypatch, capsys):
    d = _make_evidence(tmp_path / "out")
    assert _run(monkeypatch, ["--dir", str(d)]) == 0
    out = capsys.readouterr().out
    assert "PASS" in out
    assert PAGE_HEX in out


def test_main_missing_evidence_file(tmp_path, monkeypatch, capsys):
    d = _make_evidence(tmp_path / "out", omit=("notion-log.json",))
    assert _run(monkeypatch, ["--dir", str(d)]) == 2
    err = capsys.readouterr().err
    assert "missing publish evidence" in err
    assert "notion-log.json" in err


def test_main_all_evidence_missing(tmp_path, monkeypatch, capsys):
    d = tmp_path / "empty"
    d.mkdir()
    assert _run(monkeypatch, ["--dir", str(d)]) == 2
    assert "missing publish evidence" in capsys.readouterr().err


def test_main_invalid_result_json(tmp_path, monkeypatch, capsys):
    d = _make_evidence(tmp_path / "out")
    (d / "notion-publish-result.json").write_text("{broken", encoding="utf-8")
    assert _run(monkeypatch, ["--dir", str(d)]) == 2
    assert "invalid publish evidence" in capsys.readouterr().err


def test_main_log_status_not_published(tmp_path, monkeypatch, capsys):
    d = _make_evidence(tmp_path / "out", log={"status": "draft"})
    assert _run(monkeypatch, ["--dir", str(d)]) == 2
    err = capsys.readouterr().err
    assert "expected 'published'" in err
    assert "draft" in err


def test_main_log_missing_status_key(tmp_path, monkeypatch, capsys):
    d = _make_evidence(tmp_path / "out", log={"other": 1})
    assert _run(monkeypatch, ["--dir", str(d)]) == 2
    assert "expected 'published'" in capsys.readouterr().err


def test_main_result_no_page_id(tmp_path, monkeypatch, capsys):
    d = _make_evidence(tmp_path / "out", result={"foo": "bar"})
    assert _run(monkeypatch, ["--dir", str(d)]) == 2
    assert "no page_id" in capsys.readouterr().err


def test_main_result_uses_id_fallback(tmp_path, monkeypatch):
    # page_id 無し → result.id をフォールバックで使用
    d = _make_evidence(tmp_path / "out", result={"id": DASHED})
    assert _run(monkeypatch, ["--dir", str(d)]) == 0


def test_main_result_uses_log_page_id_fallback(tmp_path, monkeypatch):
    # result に page_id/id 無し → log.page_id を使用
    d = _make_evidence(
        tmp_path / "out",
        result={"foo": "bar"},
        log={"status": "published", "page_id": PAGE_HEX},
    )
    assert _run(monkeypatch, ["--dir", str(d)]) == 0


def test_main_invalid_notion_url(tmp_path, monkeypatch, capsys):
    d = _make_evidence(tmp_path / "out", url="http://evil.example.com/x")
    assert _run(monkeypatch, ["--dir", str(d)]) == 2
    assert "invalid notion-url.txt" in capsys.readouterr().err


def test_main_url_whitespace_stripped(tmp_path, monkeypatch):
    d = _make_evidence(tmp_path / "out", url=f"  {NOTION_URL}\n  ")
    assert _run(monkeypatch, ["--dir", str(d)]) == 0


def test_main_expected_page_id_match(tmp_path, monkeypatch):
    d = _make_evidence(tmp_path / "out")
    assert _run(monkeypatch, ["--dir", str(d), "--page-id", DASHED]) == 0


def test_main_expected_page_id_mismatch(tmp_path, monkeypatch, capsys):
    d = _make_evidence(tmp_path / "out")
    other = "b" * 32
    assert _run(monkeypatch, ["--dir", str(d), "--page-id", other]) == 2
    err = capsys.readouterr().err
    assert "page_id mismatch" in err
    assert other in err


def test_main_expected_page_url_match(tmp_path, monkeypatch):
    d = _make_evidence(tmp_path / "out")
    assert _run(monkeypatch, ["--dir", str(d), "--page-url", NOTION_URL]) == 0


def test_main_expected_page_id_takes_precedence_over_url(tmp_path, monkeypatch):
    # script の expected = canonical(page_id) or canonical(page_url)。
    # --page-id が解決できれば or が短絡し --page-url は評価されない。
    # よって page-id が actual と一致する限り、別の page-url を渡しても 0。
    d = _make_evidence(tmp_path / "out")
    assert _run(monkeypatch, [
        "--dir", str(d), "--page-id", DASHED, "--page-url", "https://www.notion.so/" + "c" * 32,
    ]) == 0


def test_main_page_url_used_when_page_id_unresolvable(tmp_path, monkeypatch, capsys):
    # --page-id が無効 (解決不能) → page-url 側を expected に採用。
    # その page-url が actual と不一致なら mismatch (2)。
    d = _make_evidence(tmp_path / "out")
    assert _run(monkeypatch, [
        "--dir", str(d),
        "--page-id", "garbage",
        "--page-url", "https://www.notion.so/" + "c" * 32,
    ]) == 2
    assert "page_id mismatch" in capsys.readouterr().err


def test_main_invalid_intake_json(tmp_path, monkeypatch, capsys):
    d = _make_evidence(tmp_path / "out")
    (d / "intake.json").write_text("[not a dict", encoding="utf-8")
    assert _run(monkeypatch, ["--dir", str(d)]) == 2
    assert "invalid intake.json" in capsys.readouterr().err


def test_main_intake_non_dict_json(tmp_path, monkeypatch, capsys):
    d = _make_evidence(tmp_path / "out")
    (d / "intake.json").write_text(json.dumps([1, 2]), encoding="utf-8")
    assert _run(monkeypatch, ["--dir", str(d)]) == 2
    assert "invalid intake.json" in capsys.readouterr().err


# ----- intake.notion_target update mode checks -----

def test_main_intake_update_target_matches(tmp_path, monkeypatch):
    d = _make_evidence(
        tmp_path / "out",
        intake={"notion_target": {"mode": "update", "page_id": PAGE_HEX}},
    )
    assert _run(monkeypatch, ["--dir", str(d)]) == 0


def test_main_intake_update_target_uses_page_url(tmp_path, monkeypatch):
    d = _make_evidence(
        tmp_path / "out",
        intake={"notion_target": {"mode": "update", "page_url": NOTION_URL}},
    )
    assert _run(monkeypatch, ["--dir", str(d)]) == 0


def test_main_intake_update_target_no_page_id(tmp_path, monkeypatch, capsys):
    d = _make_evidence(
        tmp_path / "out",
        intake={"notion_target": {"mode": "update"}},
    )
    assert _run(monkeypatch, ["--dir", str(d)]) == 2
    assert "update mode lacks page_id" in capsys.readouterr().err


def test_main_intake_update_target_mismatch(tmp_path, monkeypatch, capsys):
    d = _make_evidence(
        tmp_path / "out",
        intake={"notion_target": {"mode": "update", "page_id": "d" * 32}},
    )
    assert _run(monkeypatch, ["--dir", str(d)]) == 2
    assert "does not match publish result" in capsys.readouterr().err


def test_main_intake_target_create_mode_ignored(tmp_path, monkeypatch):
    # mode != update → target チェックをスキップ (page_id 不要)
    d = _make_evidence(
        tmp_path / "out",
        intake={"notion_target": {"mode": "create"}},
    )
    assert _run(monkeypatch, ["--dir", str(d)]) == 0


def test_main_intake_target_not_dict_ignored(tmp_path, monkeypatch):
    d = _make_evidence(tmp_path / "out", intake={"notion_target": "string-value"})
    assert _run(monkeypatch, ["--dir", str(d)]) == 0


# ============================================================
# 実 CLI 起動 (subprocess) end-to-end: PASS と missing の 2 経路
# ============================================================

def test_cli_subprocess_pass(tmp_path):
    d = _make_evidence(tmp_path / "out")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--dir", str(d)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "PASS" in proc.stdout


def test_cli_subprocess_missing_exits_2(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--dir", str(d)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "missing publish evidence" in proc.stderr


def test_cli_subprocess_requires_dir_arg():
    # --dir 必須 → argparse が 2 で終了
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "required" in proc.stderr or "--dir" in proc.stderr
