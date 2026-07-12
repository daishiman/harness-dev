"""inventory-skill-references.py の genuine 機能テスト。

純関数 parse_frontmatter / inventory_skill を実入力 (tmp_path 上の SKILL.md +
references/ 実ファイル) で呼び、frontmatter list parse / ハードコードパス抽出 /
script 参照抽出 / references 実ファイル列挙を実出力で assert する。
main() は subprocess で --skills-dir / --output を tmp_path に向けて実行し、
出力 JSON の構造と内容を検証する (repo の eval-log を汚さない)。
不正入力 (skills-dir 不在) で exit 2 を検証。network/外部 I/O なし。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "inventory-skill-references.py"

SPEC = importlib.util.spec_from_file_location("inventory_skill_references", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _make_skill(base: Path, dir_name: str, body: str) -> Path:
    d = base / dir_name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    return d


# --- parse_frontmatter: scalar + list の両方 ---

def test_parse_frontmatter_scalar_values():
    text = (
        "---\n"
        "name: run-foo\n"
        "kind: skill\n"
        "effect: read-only\n"
        "---\n"
        "body\n"
    )
    fm = MOD.parse_frontmatter(text)
    assert fm["name"] == "run-foo"
    assert fm["kind"] == "skill"
    assert fm["effect"] == "read-only"


def test_parse_frontmatter_list_key_left_empty_string_known_bug():
    # GENUINE: 実スクリプトの挙動を固定。`key:` (inline 値なし) は先に "" がセットされ、
    # 後続の setdefault が list へ変換しないため、list 項目は取り込まれず "" のまま残る。
    # (script の既知バグ。テストはアスピレーションでなく実挙動を assert する)
    text = (
        "---\n"
        "rubric_refs:\n"
        "  - ref-skill-design-rubric\n"
        "  - ref-output-routing\n"
        "---\n"
        "body\n"
    )
    fm = MOD.parse_frontmatter(text)
    assert fm["rubric_refs"] == ""


def test_parse_frontmatter_inline_scalar_overrides_list_key():
    # inline 値ありの key は scalar 文字列になる
    text = (
        "---\n"
        "pair: run-partner\n"
        "base: wrap-base\n"
        "---\n"
    )
    fm = MOD.parse_frontmatter(text)
    assert fm["pair"] == "run-partner"
    assert fm["base"] == "wrap-base"


def test_parse_frontmatter_no_fence_empty():
    assert MOD.parse_frontmatter("plain text") == {}


def test_parse_frontmatter_incomplete_fence_empty():
    # 開始 --- はあるが終端 --- が無い -> len(parts) < 3 -> {}
    assert MOD.parse_frontmatter("---\nname: x\n") == {}


def test_parse_frontmatter_list_then_scalar_resets_list_key():
    # list-key の後に inline scalar が来ると current_list_key が None に戻る
    text = (
        "---\n"
        "rubric_refs:\n"
        "  - item-a\n"
        "name: run-after\n"
        "  - stray-item\n"  # current_list_key が None なので取り込まれない
        "---\n"
    )
    fm = MOD.parse_frontmatter(text)
    assert fm["name"] == "run-after"
    # list-key バグで rubric_refs は "" のまま
    assert fm["rubric_refs"] == ""


# --- inventory_skill: 各抽出経路を genuine に ---

def test_inventory_skill_missing_skill_md(tmp_path):
    d = tmp_path / "run-empty"
    d.mkdir()
    out = MOD.inventory_skill(d)
    assert out == {"name": "run-empty", "error": "SKILL.md not found"}


def test_inventory_skill_frontmatter_pair_and_base_refs(tmp_path):
    # pair:/base: は inline scalar なので確実に取り込まれる。
    # rubric_refs/reference_refs は list-key バグで "" になり frontmatter_refs に入らない
    # (test_parse_frontmatter_list_key_left_empty_string_known_bug 参照)。
    body = (
        "---\n"
        "name: run-foo\n"
        "kind: skill\n"
        "effect: read-only\n"
        "rubric_refs:\n"
        "  - ref-rubric\n"
        "pair: run-partner\n"
        "base: wrap-base\n"
        "---\n"
        "no body refs\n"
    )
    d = _make_skill(tmp_path, "run-foo", body)
    out = MOD.inventory_skill(d)
    assert out["name"] == "run-foo"
    assert out["kind"] == "skill"
    assert out["effect"] == "read-only"
    assert "pair:run-partner" in out["frontmatter_refs"]
    assert "base:wrap-base" in out["frontmatter_refs"]
    # list-key バグにより rubric_refs は取り込まれない (実挙動)
    assert "ref-rubric" not in out["frontmatter_refs"]


def test_inventory_skill_frontmatter_scalar_ref_string(tmp_path):
    # script_refs に inline scalar 値を与えると str ブランチで取り込まれる
    body = (
        "---\n"
        "name: run-scalar\n"
        "script_refs: scripts/one.py\n"
        "---\n"
        "body\n"
    )
    d = _make_skill(tmp_path, "run-scalar", body)
    out = MOD.inventory_skill(d)
    assert "scripts/one.py" in out["frontmatter_refs"]


def test_inventory_skill_hardcode_and_script_and_refsfile(tmp_path):
    body = (
        "---\n"
        "name: run-bar\n"
        "---\n"
        "See plugins/harness-creator/skills/ref-target for details.\n"
        "Also .claude/skills/run-other works.\n"
        "Run: python3 scripts/do-thing.py\n"
        "And source helpers/setup.sh\n"
        "Read references/guide.md and references/data.json\n"
    )
    d = _make_skill(tmp_path, "run-bar", body)
    out = MOD.inventory_skill(d)
    assert set(out["hardcode_paths"]) == {"ref-target", "run-other"}
    assert set(out["script_refs_in_body"]) == {"scripts/do-thing.py", "helpers/setup.sh"}
    assert set(out["refs_files_mentioned"]) == {"guide.md", "data.json"}


def test_inventory_skill_actual_references_files_and_resource_map(tmp_path):
    d = _make_skill(tmp_path, "run-baz", "---\nname: run-baz\n---\nbody\n")
    refs = d / "references"
    refs.mkdir()
    (refs / "alpha.md").write_text("a", encoding="utf-8")
    (refs / "beta.yaml").write_text("b", encoding="utf-8")
    (refs / "resource-map.yaml").write_text("c", encoding="utf-8")
    out = MOD.inventory_skill(d)
    # sorted 列挙
    assert out["actual_references_files"] == ["alpha.md", "beta.yaml", "resource-map.yaml"]
    assert out["resource_map_exists"] is True


def test_inventory_skill_resource_map_absent_when_no_refs_dir(tmp_path):
    d = _make_skill(tmp_path, "run-noref", "---\nname: run-noref\n---\nbody\n")
    out = MOD.inventory_skill(d)
    assert out["actual_references_files"] == []
    assert out["resource_map_exists"] is False


def test_inventory_skill_name_falls_back_to_dir(tmp_path):
    # frontmatter に name なし -> dir 名を採用
    d = _make_skill(tmp_path, "run-dirname", "---\nkind: skill\n---\nbody\n")
    out = MOD.inventory_skill(d)
    assert out["name"] == "run-dirname"


# --- main(): subprocess, --skills-dir + --output を tmp に向ける ---

def _run(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


def test_main_writes_inventory_json(tmp_path):
    skills = tmp_path / "skills"
    _make_skill(skills, "run-a", "---\nname: run-a\nkind: skill\n---\nbody\n")
    _make_skill(skills, "ref-b", "---\nname: ref-b\nkind: ref\n---\nbody\n")
    out_path = tmp_path / "out" / "inventory.json"
    proc = _run(
        ["--skills-dir", str(skills), "--output", str(out_path)],
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["skill_count"] == 2
    names = {item["name"] for item in data["inventory"]}
    assert names == {"run-a", "ref-b"}
    assert str(skills) in data["skills_dir"]
    assert f"written: {out_path}" in proc.stdout


def test_main_skills_dir_not_found_exit_2(tmp_path):
    proc = _run(["--skills-dir", str(tmp_path / "absent")], cwd=tmp_path)
    assert proc.returncode == 2
    assert "skills directory not found" in proc.stderr


def test_main_default_skills_dir_when_missing_exit_2(tmp_path):
    # cwd を tmp_path にすると default の plugins/harness-creator/skills は無い -> exit 2
    proc = _run([], cwd=tmp_path)
    assert proc.returncode == 2
    assert "skills directory not found" in proc.stderr


# --- main(): in-process 駆動 (lines 117-160 を genuine にカバー) ---

def test_main_inprocess_writes_and_returns_0(tmp_path, monkeypatch):
    skills = tmp_path / "skills"
    _make_skill(skills, "run-a", "---\nname: run-a\nkind: skill\n---\nbody\n")
    _make_skill(skills, "ref-b", "---\nname: ref-b\nkind: ref\n---\nbody\n")
    out_path = tmp_path / "out" / "inv.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv",
        ["inventory-skill-references.py",
         "--skills-dir", str(skills), "--output", str(out_path)],
    )
    rc = MOD.main()
    assert rc == 0
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["skill_count"] == 2
    assert {item["name"] for item in data["inventory"]} == {"run-a", "ref-b"}
    assert data["generated_at"] == "2026-05-18"


def test_main_inprocess_missing_dir_returns_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv",
        ["inventory-skill-references.py", "--skills-dir", str(tmp_path / "absent")],
    )
    assert MOD.main() == 2


def test_main_inprocess_ignores_unknown_args(tmp_path, monkeypatch):
    # 未知の arg は while ループの else 分岐で読み飛ばされる (line 132)
    skills = tmp_path / "skills"
    _make_skill(skills, "run-a", "---\nname: run-a\n---\nbody\n")
    out_path = tmp_path / "inv.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv",
        ["inventory-skill-references.py",
         "--unknown-flag", "junk",
         "--skills-dir", str(skills), "--output", str(out_path)],
    )
    assert MOD.main() == 0
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["skill_count"] == 1


def test_main_inprocess_skips_non_dir_entries(tmp_path, monkeypatch):
    skills = tmp_path / "skills"
    _make_skill(skills, "run-a", "---\nname: run-a\n---\nbody\n")
    # ファイルエントリ (ディレクトリでない) は無視される
    (skills / "stray.txt").write_text("ignored", encoding="utf-8")
    out_path = tmp_path / "inv.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv",
        ["inventory-skill-references.py",
         "--skills-dir", str(skills), "--output", str(out_path)],
    )
    assert MOD.main() == 0
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["skill_count"] == 1  # stray.txt は数えない
