"""lint-knowledge-loop.py の genuine で網羅的な機能テスト (network 不要)。

対象: plugins/harness-creator/skills/run-build-skill/scripts/lint-knowledge-loop.py

このスクリプトは knowledge-loop capability の lint (KL-001..007):
  KL-001: index|router 存在 + >=3 エントリ
  KL-002: 各エントリの必須6フィールド
  KL-003/004/006: search_knowledge.py / record_usage.py / add_entry.py の存在
  KL-005: 分割閾値の記述/設定
  KL-007: consult_at 宣言・妥当性・物理位置(store_only)一致
さらに --self-test で schema↔定数 drift / lint↔CI 配線のメタ検査も行う。

方針:
  - 純関数 (find_knowledge_dir / collect_entries / load_json_safe / check_kl00X /
    run_lint / _extract_anyof_required) を tmp_path fixture で直接呼び戻り値を assert。
  - 合格 fixture を _good_skill() で組み、各 KL ルールを 1 つずつ壊して検出を確認。
  - main は subprocess(sys.executable) で exit code / JSON 出力を assert。
  - self_test / check_schema_drift / check_ci_wiring は実 repo の schema・CI を
    読むスクリプト挙動をそのまま使う (network/keychain/secret 一切なし)。
  - すべて tmp_path に閉じてリポジトリを汚染しない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "lint-knowledge-loop.py"
)

_SPEC = importlib.util.spec_from_file_location("lint_knowledge_loop_uut", SCRIPT)
KL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(KL)


# =====================================================================
# fixture builders
# =====================================================================

def _entry(i: int) -> dict:
    return {
        "id": f"t_{i:03d}",
        "title": f"タイトル{i}",
        "intent": f"意図{i}",
        "background": f"背景{i}",
        "keywords": [f"kw{i}"],
        "source": "test.md",
    }


def _good_skill(tmp_path, *, store_only=False, consult_at=None, n_entries=3) -> Path:
    """KL-001..007 すべて pass する skill ディレクトリを組む。"""
    skill_dir = tmp_path / "run-target"
    kdir = skill_dir / "knowledge"
    kdir.mkdir(parents=True)
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    for name in ("search_knowledge.py", "record_usage.py", "add_entry.py"):
        (scripts_dir / name).write_text("# stub", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "# テスト\n\n分割閾値: 500行/25エントリ\n", encoding="utf-8"
    )
    if consult_at is None:
        consult_at = ["build-time"] if store_only else ["runtime"]
    index = {
        "version": "1.0.0",
        "consult_at": consult_at,
        "categories": [
            {"id": "test", "label": "テスト", "file": "knowledge-test.json", "keywords": []}
        ],
        "global_keywords": {},
    }
    (kdir / "knowledge-index.json").write_text(json.dumps(index), encoding="utf-8")
    cat = {
        "category": "test",
        "label": "テスト",
        "version": "1.0.0",
        "items": [_entry(i) for i in range(1, n_entries + 1)],
    }
    (kdir / "knowledge-test.json").write_text(json.dumps(cat), encoding="utf-8")
    return skill_dir


# =====================================================================
# 純関数: find_knowledge_dir / load_json_safe / collect_entries
# =====================================================================

def test_find_knowledge_dir_present(tmp_path):
    (tmp_path / "knowledge").mkdir()
    assert KL.find_knowledge_dir(tmp_path) == tmp_path / "knowledge"


def test_find_knowledge_dir_absent(tmp_path):
    assert KL.find_knowledge_dir(tmp_path) is None


def test_load_json_safe_ok(tmp_path):
    p = tmp_path / "a.json"
    p.write_text('{"x": 1}', encoding="utf-8")
    data, err = KL.load_json_safe(p)
    assert err is None
    assert data == {"x": 1}


def test_load_json_safe_bad_json(tmp_path):
    p = tmp_path / "a.json"
    p.write_text("{bad", encoding="utf-8")
    data, err = KL.load_json_safe(p)
    assert data is None
    assert "JSON解析失敗" in err


def test_load_json_safe_missing_file(tmp_path):
    data, err = KL.load_json_safe(tmp_path / "absent.json")
    assert data is None
    assert "ファイル読み込みエラー" in err


def test_collect_entries_items_and_list(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    # items 形式
    (kdir / "a.json").write_text(
        json.dumps({"items": [_entry(1), _entry(2)]}), encoding="utf-8"
    )
    # 直接 list 形式
    (kdir / "b.json").write_text(json.dumps([_entry(3)]), encoding="utf-8")
    # 除外されるべきメタファイル
    (kdir / "knowledge-index.json").write_text("{}", encoding="utf-8")
    (kdir / "router.json").write_text("{}", encoding="utf-8")
    entries, errors = KL.collect_entries(kdir)
    assert errors == []
    assert len(entries) == 3


def test_collect_entries_reports_bad_json(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "broken.json").write_text("{not json", encoding="utf-8")
    entries, errors = KL.collect_entries(kdir)
    assert entries == []
    assert any("broken.json" in e for e in errors)


# =====================================================================
# run_lint: happy paths
# =====================================================================

def test_run_lint_skip_when_no_knowledge_dir(tmp_path):
    result = KL.run_lint(tmp_path, strict=False)
    assert result["status"] == "skip"
    assert "knowledge/" in result["message"]


def test_run_lint_all_pass(tmp_path):
    skill_dir = _good_skill(tmp_path)
    result = KL.run_lint(skill_dir, strict=True)
    errors = [f for f in result["findings"] if f["severity"] == "error"]
    assert errors == [], errors
    assert result["status"] == "pass"
    assert result["error_count"] == 0


def test_run_lint_store_only_pass(tmp_path):
    skill_dir = _good_skill(tmp_path, store_only=True)
    # store-only かつ build-time 宣言 → KL-003/004/006 を info に格下げし pass
    result = KL.run_lint(skill_dir, strict=True, store_only=True)
    assert result["status"] == "pass", result
    info = [f for f in result["findings"] if f["severity"] == "info"]
    assert any("store-only" in f["message"] for f in info)
    assert not [f for f in result["findings"] if f["rule"] == "KL-006"]


# =====================================================================
# KL-001
# =====================================================================

def test_kl001_no_index_or_router(tmp_path):
    skill_dir = _good_skill(tmp_path)
    (skill_dir / "knowledge" / "knowledge-index.json").unlink()
    findings = KL.check_kl001(skill_dir / "knowledge")
    assert any("見つからない" in f["message"] for f in findings)
    assert findings[0]["severity"] == "error"


def test_kl001_too_few_entries(tmp_path):
    skill_dir = _good_skill(tmp_path, n_entries=2)
    findings = KL.check_kl001(skill_dir / "knowledge")
    assert any("3件未満" in f["message"] for f in findings)


# =====================================================================
# KL-002
# =====================================================================

def test_kl002_missing_always_field(tmp_path):
    skill_dir = _good_skill(tmp_path)
    kdir = skill_dir / "knowledge"
    bad = _entry(1)
    del bad["source"]  # always-required field
    cat = {"items": [bad, _entry(2), _entry(3)]}
    (kdir / "knowledge-test.json").write_text(json.dumps(cat), encoding="utf-8")
    findings = KL.check_kl002(kdir)
    assert any("必須フィールドがない" in f["message"] and "source" in f["message"]
               for f in findings)


def test_kl002_missing_title_or_content(tmp_path):
    skill_dir = _good_skill(tmp_path)
    kdir = skill_dir / "knowledge"
    bad = _entry(1)
    del bad["title"]  # neither title nor content
    cat = {"items": [bad, _entry(2), _entry(3)]}
    (kdir / "knowledge-test.json").write_text(json.dumps(cat), encoding="utf-8")
    findings = KL.check_kl002(kdir)
    assert any("title または content がない" in f["message"] for f in findings)


def test_kl002_content_alias_accepted(tmp_path):
    """title の代わりに content / intent->purpose / keywords->tags でも合格。"""
    skill_dir = _good_skill(tmp_path)
    kdir = skill_dir / "knowledge"
    alias = {
        "id": "t_alias",
        "content": "本文",
        "purpose": "目的",
        "background": "背景",
        "tags": ["t"],
        "source": "s.md",
    }
    cat = {"items": [alias, _entry(2), _entry(3)]}
    (kdir / "knowledge-test.json").write_text(json.dumps(cat), encoding="utf-8")
    findings = KL.check_kl002(kdir)
    assert findings == []


def test_kl002_missing_intent(tmp_path):
    skill_dir = _good_skill(tmp_path)
    kdir = skill_dir / "knowledge"
    bad = _entry(1)
    del bad["intent"]
    cat = {"items": [bad, _entry(2), _entry(3)]}
    (kdir / "knowledge-test.json").write_text(json.dumps(cat), encoding="utf-8")
    findings = KL.check_kl002(kdir)
    assert any("intent または purpose がない" in f["message"] for f in findings)


def test_kl002_missing_keywords(tmp_path):
    skill_dir = _good_skill(tmp_path)
    kdir = skill_dir / "knowledge"
    bad = _entry(1)
    del bad["keywords"]
    cat = {"items": [bad, _entry(2), _entry(3)]}
    (kdir / "knowledge-test.json").write_text(json.dumps(cat), encoding="utf-8")
    findings = KL.check_kl002(kdir)
    assert any("keywords または tags がない" in f["message"] for f in findings)


# =====================================================================
# KL-003 / KL-004 / KL-006
# =====================================================================

def test_kl003_missing_search_script(tmp_path):
    skill_dir = _good_skill(tmp_path)
    (skill_dir / "scripts" / "search_knowledge.py").unlink()
    findings = KL.check_kl003(skill_dir)
    assert findings and findings[0]["rule"] == "KL-003"
    assert findings[0]["severity"] == "error"


def test_kl003_present(tmp_path):
    skill_dir = _good_skill(tmp_path)
    assert KL.check_kl003(skill_dir) == []


def test_kl004_missing_record_script(tmp_path):
    skill_dir = _good_skill(tmp_path)
    (skill_dir / "scripts" / "record_usage.py").unlink()
    findings = KL.check_kl004(skill_dir)
    assert findings and findings[0]["rule"] == "KL-004"


def test_kl006_missing_add_entry_is_warn(tmp_path):
    skill_dir = _good_skill(tmp_path)
    (skill_dir / "scripts" / "add_entry.py").unlink()
    findings = KL.check_kl006(skill_dir)
    assert findings and findings[0]["severity"] == "warn"


def test_kl006_present(tmp_path):
    skill_dir = _good_skill(tmp_path)
    assert KL.check_kl006(skill_dir) == []


# =====================================================================
# KL-005
# =====================================================================

def test_kl005_threshold_in_skill_md(tmp_path):
    skill_dir = _good_skill(tmp_path)
    findings = KL.check_kl005(skill_dir, skill_dir / "knowledge")
    assert findings == []


def test_kl005_threshold_in_index_lifecycle(tmp_path):
    skill_dir = _good_skill(tmp_path)
    # SKILL.md から閾値文言を消す
    (skill_dir / "SKILL.md").write_text("# テスト\n本文のみ\n", encoding="utf-8")
    kdir = skill_dir / "knowledge"
    idx, _ = KL.load_json_safe(kdir / "knowledge-index.json")
    idx["lifecycle"] = {"split_threshold_lines": 500, "split_threshold_entries": 25}
    (kdir / "knowledge-index.json").write_text(json.dumps(idx), encoding="utf-8")
    findings = KL.check_kl005(skill_dir, kdir)
    assert findings == []


def test_kl005_missing_threshold_is_warn(tmp_path):
    skill_dir = _good_skill(tmp_path)
    (skill_dir / "SKILL.md").write_text("# テスト\n本文のみ\n", encoding="utf-8")
    findings = KL.check_kl005(skill_dir, skill_dir / "knowledge")
    assert findings and findings[0]["rule"] == "KL-005"
    assert findings[0]["severity"] == "warn"


# =====================================================================
# KL-007: consult_at 宣言・妥当性・物理位置一致
# =====================================================================

def _write_index(skill_dir: Path, extra: dict) -> None:
    kdir = skill_dir / "knowledge"
    base = {
        "version": "1.0.0",
        "categories": [
            {"id": "test", "label": "テスト", "file": "knowledge-test.json", "keywords": []}
        ],
        "global_keywords": {},
    }
    (kdir / "knowledge-index.json").write_text(
        json.dumps({**base, **extra}), encoding="utf-8"
    )


def test_kl007_unset_consult_at(tmp_path):
    skill_dir = _good_skill(tmp_path)
    _write_index(skill_dir, {})
    findings = KL.check_kl007(skill_dir / "knowledge", store_only=False)
    assert findings and "未宣言" in findings[0]["message"]


def test_kl007_runtime_loop_a_ok(tmp_path):
    skill_dir = _good_skill(tmp_path)
    _write_index(skill_dir, {"consult_at": ["runtime"]})
    findings = KL.check_kl007(skill_dir / "knowledge", store_only=False)
    assert findings == []


def test_kl007_build_time_loop_b_ok(tmp_path):
    skill_dir = _good_skill(tmp_path)
    _write_index(skill_dir, {"consult_at": ["build-time"]})
    findings = KL.check_kl007(skill_dir / "knowledge", store_only=True)
    assert findings == []


def test_kl007_loop_a_with_build_time_mismatch(tmp_path):
    skill_dir = _good_skill(tmp_path)
    _write_index(skill_dir, {"consult_at": ["build-time"]})
    findings = KL.check_kl007(skill_dir / "knowledge", store_only=False)
    assert findings and "不一致" in findings[0]["message"]


def test_kl007_loop_b_with_runtime_mismatch(tmp_path):
    skill_dir = _good_skill(tmp_path)
    _write_index(skill_dir, {"consult_at": ["runtime"]})
    findings = KL.check_kl007(skill_dir / "knowledge", store_only=True)
    assert findings and "不一致" in findings[0]["message"]


def test_kl007_invalid_value(tmp_path):
    skill_dir = _good_skill(tmp_path)
    _write_index(skill_dir, {"consult_at": ["sometime"]})
    findings = KL.check_kl007(skill_dir / "knowledge", store_only=False)
    assert findings and "不正な値" in findings[0]["message"]


def test_kl007_not_a_list(tmp_path):
    skill_dir = _good_skill(tmp_path)
    _write_index(skill_dir, {"consult_at": "runtime"})  # string not list
    findings = KL.check_kl007(skill_dir / "knowledge", store_only=False)
    assert findings and "配列である必要" in findings[0]["message"]


def test_kl007_empty_list(tmp_path):
    skill_dir = _good_skill(tmp_path)
    _write_index(skill_dir, {"consult_at": []})
    findings = KL.check_kl007(skill_dir / "knowledge", store_only=False)
    assert findings and "未宣言または空" in findings[0]["message"]


def test_kl007_decl_file_absent_skips(tmp_path):
    """宣言ファイルが無ければ KL-007 は対象なしでスキップ (KL-001 が別途検出)。"""
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    findings = KL.check_kl007(kdir, store_only=False)
    assert findings == []


def test_kl007_router_fallback(tmp_path):
    """index が無く router.json があれば router を宣言ファイルとして使う。"""
    skill_dir = _good_skill(tmp_path)
    kdir = skill_dir / "knowledge"
    (kdir / "knowledge-index.json").unlink()
    (kdir / "router.json").write_text(
        json.dumps({"consult_at": ["runtime"]}), encoding="utf-8"
    )
    findings = KL.check_kl007(kdir, store_only=False)
    assert findings == []


def test_kl007_bad_json_in_decl(tmp_path):
    skill_dir = _good_skill(tmp_path)
    (skill_dir / "knowledge" / "knowledge-index.json").write_text(
        "{broken", encoding="utf-8"
    )
    findings = KL.check_kl007(skill_dir / "knowledge", store_only=False)
    assert findings and "JSON 解析に失敗" in findings[0]["message"]


# =====================================================================
# run_lint: status transitions (strict vs non-strict)
# =====================================================================

def test_run_lint_strict_fail_on_error(tmp_path):
    skill_dir = _good_skill(tmp_path)
    (skill_dir / "scripts" / "search_knowledge.py").unlink()  # KL-003 error
    result = KL.run_lint(skill_dir, strict=True)
    assert result["status"] == "fail"
    assert result["error_count"] >= 1


def test_run_lint_non_strict_warn_on_error(tmp_path):
    skill_dir = _good_skill(tmp_path)
    (skill_dir / "scripts" / "search_knowledge.py").unlink()
    result = KL.run_lint(skill_dir, strict=False)
    assert result["status"] == "warn"


def test_run_lint_warn_on_warning_only(tmp_path):
    skill_dir = _good_skill(tmp_path)
    (skill_dir / "scripts" / "add_entry.py").unlink()  # KL-006 warn only
    result = KL.run_lint(skill_dir, strict=True)
    assert result["status"] == "warn"
    assert result["error_count"] == 0
    assert result["warn_count"] >= 1


# =====================================================================
# _extract_anyof_required (schema 走査純関数)
# =====================================================================

def test_extract_anyof_required_nested():
    node = {
        "allOf": [
            {"anyOf": [{"required": ["a"]}, {"required": ["b"]}]},
            {"properties": {"x": {"anyOf": [{"required": ["c"]}]}}},
        ]
    }
    groups = KL._extract_anyof_required(node)
    assert {"a", "b"} in groups
    assert {"c"} in groups


def test_extract_anyof_required_empty():
    assert KL._extract_anyof_required({"x": 1}) == []


# =====================================================================
# main() via subprocess: exit code + JSON 出力契約
# =====================================================================

def test_subprocess_self_test():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "PASS" in r.stdout


def test_subprocess_pass(tmp_path):
    skill_dir = _good_skill(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(skill_dir)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["status"] == "pass"


def test_subprocess_strict_fail(tmp_path):
    skill_dir = _good_skill(tmp_path)
    (skill_dir / "scripts" / "search_knowledge.py").unlink()
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(skill_dir), "--strict"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 1
    payload = json.loads(r.stdout)
    assert payload["status"] == "fail"


def test_subprocess_store_only_flag(tmp_path):
    skill_dir = _good_skill(tmp_path, store_only=True)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(skill_dir), "--store-only", "--strict"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["status"] == "pass"


def test_subprocess_skip_when_no_knowledge(tmp_path):
    skill_dir = tmp_path / "run-empty"
    skill_dir.mkdir()
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(skill_dir)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert payload["status"] == "skip"


def test_subprocess_missing_skill_dir_arg():
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode != 0
    assert "skill_dir" in r.stderr


def test_subprocess_nonexistent_dir(tmp_path):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "absent")],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 1
    payload = json.loads(r.stderr)
    assert "存在しない" in payload["error"]
