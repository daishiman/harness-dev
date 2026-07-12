"""lint-knowledge-layout の規約検出を機械担保する。

knowledge/ (JSON ストア) と lessons-learned/ (散文ログ) の役割分担を fail-closed 検査する
lint が、実際に各違反 (K1 散文混入 / K2 dangling source.file / L1-L4 形式) を検出でき、
かつ 2 種の正当な lesson (人手記述 / 自動記録) を誤検出しないことを負テストで固定する。
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "lint_knowledge_layout", ROOT / "scripts" / "lint-knowledge-layout.py")
_M = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_M)


def _plugin(tmp_path: Path, name: str) -> Path:
    p = tmp_path / "plugins" / name
    p.mkdir(parents=True)
    return p


_GOOD_HUMAN = (
    "---\ndate: 2026-07-11\n---\n\n# t\n\n## 背景\nx\n\n## 知見\ny\n\n## 適用先\nz\n")
_GOOD_AUTO = (
    "---\ndate: 2026-07-11\ntrigger_event: PostToolUse\n---\n\n"
    "## observation\na\n\n## hypothesis\nb\n\n## proposed_action\nc\n")


def test_clean_layout_passes(tmp_path):
    pl = _plugin(tmp_path, "p")
    (pl / "knowledge").mkdir()
    (pl / "knowledge" / "knowledge-index.json").write_text("{}", encoding="utf-8")
    (pl / "knowledge" / "README.md").write_text("# k", encoding="utf-8")
    (pl / "lessons-learned").mkdir()
    (pl / "lessons-learned" / "2026-07-11-good-lesson.md").write_text(_GOOD_HUMAN, encoding="utf-8")
    assert _M.run(tmp_path / "plugins") == []


def test_auto_recorded_lesson_not_forced_to_human_sections(tmp_path):
    """auto-record 形式 (## observation 系) を人手形式へ誤強制しない (回帰の要)。"""
    pl = _plugin(tmp_path, "p")
    (pl / "lessons-learned").mkdir()
    (pl / "lessons-learned" / "2026-07-11-auto-fail.md").write_text(_GOOD_AUTO, encoding="utf-8")
    assert [v for v in _M.run(tmp_path / "plugins") if v["rule"] == "L3"] == []


def test_k1_prose_md_in_knowledge_detected(tmp_path):
    """knowledge/ 直下の散文 .md (README 以外) は K1 違反。"""
    pl = _plugin(tmp_path, "p")
    (pl / "knowledge").mkdir()
    (pl / "knowledge" / "lesson-foo.md").write_text("# stray", encoding="utf-8")
    rules = {v["rule"] for v in _M.run(tmp_path / "plugins")}
    assert "K1" in rules


def test_k1_allows_jsonl_and_readme(tmp_path):
    pl = _plugin(tmp_path, "p")
    (pl / "knowledge").mkdir()
    (pl / "knowledge" / "usage-log.jsonl").write_text("", encoding="utf-8")
    (pl / "knowledge" / "README.md").write_text("# k", encoding="utf-8")
    assert [v for v in _M.run(tmp_path / "plugins") if v["rule"] == "K1"] == []


def test_k2_dangling_source_file_detected(tmp_path):
    """lessons-index の source.file が実在しなければ K2 違反。"""
    pl = _plugin(tmp_path, "p")
    (pl / "knowledge").mkdir()
    idx = {"items": [{"id": "x", "source": {"file": "plugins/p/lessons-learned/missing.md"}}]}
    (pl / "knowledge" / "knowledge-lessons-index.json").write_text(
        json.dumps(idx), encoding="utf-8")
    rules = {v["rule"] for v in _M.run(tmp_path / "plugins")}
    assert "K2" in rules


def test_k2_existing_source_file_ok(tmp_path):
    pl = _plugin(tmp_path, "p")
    (pl / "knowledge").mkdir()
    (pl / "lessons-learned").mkdir()
    (pl / "lessons-learned" / "2026-07-11-real.md").write_text(_GOOD_HUMAN, encoding="utf-8")
    idx = {"items": [{"id": "x", "source": {"file": "plugins/p/lessons-learned/2026-07-11-real.md"}}]}
    (pl / "knowledge" / "knowledge-lessons-index.json").write_text(
        json.dumps(idx), encoding="utf-8")
    assert [v for v in _M.run(tmp_path / "plugins") if v["rule"] == "K2"] == []


def test_l1_bad_name_detected(tmp_path):
    pl = _plugin(tmp_path, "p")
    (pl / "lessons-learned").mkdir()
    (pl / "lessons-learned" / "no-date-prefix.md").write_text(_GOOD_HUMAN, encoding="utf-8")
    assert {v["rule"] for v in _M.run(tmp_path / "plugins")} >= {"L1"}


def test_l2_missing_frontmatter_date_detected(tmp_path):
    pl = _plugin(tmp_path, "p")
    (pl / "lessons-learned").mkdir()
    (pl / "lessons-learned" / "2026-07-11-nofm.md").write_text(
        "# t\n\n## 背景\nx\n\n## 知見\ny\n\n## 適用先\nz\n", encoding="utf-8")
    assert {v["rule"] for v in _M.run(tmp_path / "plugins")} >= {"L2"}


def test_l3_missing_human_section_detected(tmp_path):
    pl = _plugin(tmp_path, "p")
    (pl / "lessons-learned").mkdir()
    (pl / "lessons-learned" / "2026-07-11-partial.md").write_text(
        "---\ndate: 2026-07-11\n---\n\n## 背景\nx\n", encoding="utf-8")
    assert {v["rule"] for v in _M.run(tmp_path / "plugins")} >= {"L3"}


def test_l4_over_30_body_lines_detected(tmp_path):
    pl = _plugin(tmp_path, "p")
    (pl / "lessons-learned").mkdir()
    body = "\n".join(f"行 {i}" for i in range(40))
    (pl / "lessons-learned" / "2026-07-11-long.md").write_text(
        f"---\ndate: 2026-07-11\n---\n\n## 背景\n{body}\n\n## 知見\ny\n\n## 適用先\nz\n",
        encoding="utf-8")
    assert {v["rule"] for v in _M.run(tmp_path / "plugins")} >= {"L4"}


def test_readme_in_lessons_learned_skipped(tmp_path):
    pl = _plugin(tmp_path, "p")
    (pl / "lessons-learned").mkdir()
    (pl / "lessons-learned" / "README.md").write_text("# how to", encoding="utf-8")
    assert _M.run(tmp_path / "plugins") == []


def test_repo_tree_is_clean():
    """本 repo の現状ツリーが規約準拠であることを固定 (再発ガード)。"""
    assert _M.run(ROOT / "plugins") == []
