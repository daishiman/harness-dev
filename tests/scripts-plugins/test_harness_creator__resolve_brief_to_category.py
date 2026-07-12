"""plugins/harness-creator/skills/run-skill-create/scripts/resolve-brief-to-category.py の genuine 機能テスト。

skill-brief.json の field 値を resource-map category へ決定論的に写像する純関数群と
main(CLI) の全分岐を tmp_path fixture + 実ファイルロードで網羅する。

カバー分岐:
- _parse_scalar: 空文字 / list literal / 数字 / true / false / クォート付き文字列 / 素の文字列
- load_resource_map: resources: skip / "- category:" 新規 entry / "- key:" current None 補完 /
    list item 追記 / 空行・コメント除去 / トップキー scalar / トップキー list 開始 /
    current None かつ ":" 無し行の skip / category 欠落 entry の除外
- load_brief: JSON 読込
- resolve: kind 写像 / 未知 kind / conditional flag / troubleshooting trigger /
    head-middle-tail ordering / budget cutoff(末尾 drop, HEAD は保護) / hierarchy_level 既定 /
    read_first dedup
- main: 正常系(stdout JSON) / brief 欠落(argparse error) / 不正 JSON brief(例外)

network: false, keychain: なし, 実 repo 書換: なし(全 tmp_path)。
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
    / "run-skill-create"
    / "scripts"
    / "resolve-brief-to-category.py"
)

SPEC = importlib.util.spec_from_file_location("resolve_brief_to_category_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# ── 合格 fixture ヘルパ ───────────────────────────────────────────────────────
def _full_resource_map(tmp_path: Path) -> Path:
    """resolve が参照する全 category を含む resource-map.yaml を tmp に書く。

    各種パース分岐(scalar / list / コメント / 空行)も同時に踏ませる。
    """
    cats = [
        "baseline-skill-build",
        "naming-classification",
        "progressive-disclosure",
        "reproducible-skill-writing",
        "complete-examples",
        "layering-placement",
        "evaluator-orchestration",
        "template-rendering",
        "checklist-gates",
        "subagent-hook-integration",
        "agent-teams",
        "troubleshooting",
    ]
    lines = ["resources:  # top-level list", ""]
    for c in cats:
        lines.append(f"  - category: {c}")
        lines.append("    max_docs: 1")
        lines.append("    read_first:")
        lines.append(f"      - {c}/intro.md")
    text = "\n".join(lines) + "\n"
    p = tmp_path / "resource-map.yaml"
    p.write_text(text, encoding="utf-8")
    return p


# ── _parse_scalar ────────────────────────────────────────────────────────────
def test_parse_scalar_empty():
    assert MOD._parse_scalar("   ") == ""


def test_parse_scalar_list_literal():
    assert MOD._parse_scalar("['a', 'b']") == ["a", "b"]


def test_parse_scalar_digit_to_int():
    assert MOD._parse_scalar("42") == 42
    assert isinstance(MOD._parse_scalar("42"), int)


def test_parse_scalar_true_false():
    assert MOD._parse_scalar("true") is True
    assert MOD._parse_scalar("false") is False


def test_parse_scalar_quoted_string_stripped():
    assert MOD._parse_scalar('"hello"') == "hello"
    assert MOD._parse_scalar("'world'") == "world"


def test_parse_scalar_plain_string():
    assert MOD._parse_scalar("plain-value") == "plain-value"


# ── load_brief ───────────────────────────────────────────────────────────────
def test_load_brief_reads_json(tmp_path):
    p = tmp_path / "brief.json"
    p.write_text(json.dumps({"kind": "run", "hierarchy_level": "L1"}), encoding="utf-8")
    brief = MOD.load_brief(p)
    assert brief["kind"] == "run"


# ── load_resource_map ────────────────────────────────────────────────────────
def test_load_resource_map_basic_shapes(tmp_path):
    p = tmp_path / "rm.yaml"
    p.write_text(
        "resources:\n"
        "  - category: baseline-skill-build  # head\n"
        "    max_docs: 2\n"
        "    read_first:\n"
        "      - base/a.md\n"
        "      - base/b.md\n"
        "\n"  # 空行
        "  - category: naming-classification\n"
        "    max_docs: 1\n",
        encoding="utf-8",
    )
    rm = MOD.load_resource_map(p)
    assert set(rm.keys()) == {"baseline-skill-build", "naming-classification"}
    assert rm["baseline-skill-build"]["max_docs"] == 2
    assert rm["baseline-skill-build"]["read_first"] == ["base/a.md", "base/b.md"]


def test_load_resource_map_dash_key_without_category_extends_current(tmp_path):
    # "- key: value" で current が既存なら同じ entry に追記される分岐
    p = tmp_path / "rm.yaml"
    p.write_text(
        "resources:\n"
        "  - category: c1\n"
        "  - max_docs: 3\n",  # category で始まらない "- " 行 → current(c1)へ
        encoding="utf-8",
    )
    rm = MOD.load_resource_map(p)
    assert rm["c1"]["max_docs"] == 3


def test_load_resource_map_dash_key_when_current_none_starts_new(tmp_path):
    # current が None の状態で "- key:" → 新 entry を起こす分岐(current is None)
    p = tmp_path / "rm.yaml"
    p.write_text(
        "resources:\n"
        "  - max_docs: 9\n"
        "    category: orphan\n",
        encoding="utf-8",
    )
    rm = MOD.load_resource_map(p)
    assert rm["orphan"]["max_docs"] == 9


def test_load_resource_map_skips_lines_before_any_entry(tmp_path):
    # current None かつ ":" 無し / "resources:" 以外のトップ行は skip
    p = tmp_path / "rm.yaml"
    p.write_text(
        "# pure comment\n"
        "resources:\n"
        "stray-line-no-colon\n"  # current None, ":" 無し → continue
        "  - category: only\n"
        "    max_docs: 1\n",
        encoding="utf-8",
    )
    rm = MOD.load_resource_map(p)
    assert list(rm.keys()) == ["only"]


def test_load_resource_map_entry_without_category_excluded(tmp_path):
    # category キーを持たない entry は最終 dict から除外される
    p = tmp_path / "rm.yaml"
    p.write_text(
        "resources:\n"
        "  - max_docs: 5\n"  # category 無し entry
        "  - category: kept\n"
        "    max_docs: 1\n",
        encoding="utf-8",
    )
    rm = MOD.load_resource_map(p)
    assert "kept" in rm
    # max_docs:5 の entry は category 無しなので除外
    assert all("category" in v for v in rm.values())


def test_load_resource_map_top_level_scalar_after_entry(tmp_path):
    # entry 内で value 付きトップキー(scalar)が来る分岐
    p = tmp_path / "rm.yaml"
    p.write_text(
        "resources:\n"
        "  - category: c\n"
        "    note: hello\n"  # スペース字下げの key: value → current[key]
        "    read_first:\n"
        "      - x.md\n",
        encoding="utf-8",
    )
    rm = MOD.load_resource_map(p)
    assert rm["c"]["note"] == "hello"
    assert rm["c"]["read_first"] == ["x.md"]


# ── resolve: kind 写像 ───────────────────────────────────────────────────────
def test_resolve_run_kind_maps_required_categories(tmp_path):
    rm = MOD.load_resource_map(_full_resource_map(tmp_path))
    res = MOD.resolve({"kind": "run", "hierarchy_level": "L2"}, rm)
    # run の必須 category が全て含まれ、baseline が先頭
    assert res["categories"][0] == "baseline-skill-build"
    for cat in MOD.KIND_TO_REQUIRED_CATEGORIES["run"]:
        assert cat in res["categories"]
    assert res["rationale"]["naming-classification"].startswith("kind=run requires")


def test_resolve_unknown_kind_no_required(tmp_path):
    rm = MOD.load_resource_map(_full_resource_map(tmp_path))
    res = MOD.resolve({"kind": "totally-unknown", "hierarchy_level": "L2"}, rm)
    # 未知 kind → KIND 写像なし。conditional/trigger も無いので空
    assert res["categories"] == []
    assert res["brief_fields_used"]["kind"] == "totally-unknown"


def test_resolve_category_missing_from_map_skipped(tmp_path):
    # resource_map に存在しない category は categories に入らない
    p = tmp_path / "rm.yaml"
    p.write_text(
        "resources:\n"
        "  - category: baseline-skill-build\n"
        "    max_docs: 1\n",
        encoding="utf-8",
    )
    rm = MOD.load_resource_map(p)
    res = MOD.resolve({"kind": "run", "hierarchy_level": "L2"}, rm)
    # map に baseline しか無いので run 必須でも baseline のみ
    assert res["categories"] == ["baseline-skill-build"]


# ── resolve: conditional flag ────────────────────────────────────────────────
def test_resolve_conditional_flags_trigger_categories(tmp_path):
    rm = MOD.load_resource_map(_full_resource_map(tmp_path))
    res = MOD.resolve(
        {
            "kind": "ref",  # ref には agent-teams/subagent-hook-integration は無い
            "hierarchy_level": "L2",
            "needs_independent_context": True,
            "needs_lifecycle_enforcement": True,
        },
        rm,
    )
    assert "agent-teams" in res["categories"]
    assert "subagent-hook-integration" in res["categories"]
    assert "true triggers agent-teams" in res["rationale"]["agent-teams"]


def test_resolve_conditional_flag_already_present_not_duplicated(tmp_path):
    rm = MOD.load_resource_map(_full_resource_map(tmp_path))
    # delegate kind は agent-teams を必須に持つ。with_subagent_hint=True でも重複しない
    res = MOD.resolve(
        {"kind": "delegate", "hierarchy_level": "L2", "with_subagent_hint": True},
        rm,
    )
    assert res["categories"].count("agent-teams") == 1


# ── resolve: troubleshooting trigger ─────────────────────────────────────────
def test_resolve_troubleshooting_trigger_appends_tail(tmp_path):
    rm = MOD.load_resource_map(_full_resource_map(tmp_path))
    res = MOD.resolve(
        {"kind": "run", "hierarchy_level": "L2", "resume_from": "step-3"}, rm
    )
    assert "troubleshooting" in res["categories"]
    # 末尾に来ること
    assert res["categories"][-1] == "troubleshooting"
    assert res["rationale"]["troubleshooting"].startswith("resume/fast/loop")


# ── resolve: budget cutoff ───────────────────────────────────────────────────
def test_resolve_l0_budget_drops_tail(tmp_path):
    # L0=4 docs。run は 7 category(各 max_docs=1)→ budget で末尾側が drop される
    rm = MOD.load_resource_map(_full_resource_map(tmp_path))
    res = MOD.resolve({"kind": "run", "hierarchy_level": "L0"}, rm)
    assert len(res["categories"]) == 4  # budget=4
    assert res["categories"][0] == "baseline-skill-build"  # HEAD は必ず残る
    # drop された category の rationale に注記
    dropped = [c for c in MOD.KIND_TO_REQUIRED_CATEGORIES["run"] if c not in res["categories"]]
    assert dropped, "L0 では一部 drop されるはず"
    for c in dropped:
        assert "[dropped: budget=4 exceeded]" in res["rationale"][c]
    assert "budget=4" in res["rationale"]["_budget"]


def test_resolve_invalid_hierarchy_level_defaults_to_7(tmp_path):
    rm = MOD.load_resource_map(_full_resource_map(tmp_path))
    res = MOD.resolve({"kind": "run", "hierarchy_level": "L99"}, rm)
    assert "budget=7" in res["rationale"]["_budget"]


def test_resolve_head_protected_even_when_budget_zero(tmp_path):
    # max_docs を大きくして budget を即超過させても HEAD は残ることを確認
    p = tmp_path / "rm.yaml"
    p.write_text(
        "resources:\n"
        "  - category: baseline-skill-build\n"
        "    max_docs: 100\n"
        "    read_first:\n"
        "      - base.md\n"
        "  - category: naming-classification\n"
        "    max_docs: 100\n"
        "    read_first:\n"
        "      - name.md\n",
        encoding="utf-8",
    )
    rm = MOD.load_resource_map(p)
    res = MOD.resolve({"kind": "run", "hierarchy_level": "L0"}, rm)
    # HEAD は cost 超過でも保護される。naming は drop。
    assert "baseline-skill-build" in res["categories"]
    assert "naming-classification" not in res["categories"]


# ── resolve: read_first dedup ────────────────────────────────────────────────
def test_resolve_read_first_dedup(tmp_path):
    p = tmp_path / "rm.yaml"
    p.write_text(
        "resources:\n"
        "  - category: baseline-skill-build\n"
        "    max_docs: 1\n"
        "    read_first:\n"
        "      - shared.md\n"
        "  - category: naming-classification\n"
        "    max_docs: 1\n"
        "    read_first:\n"
        "      - shared.md\n"  # 重複
        "      - unique.md\n",
        encoding="utf-8",
    )
    rm = MOD.load_resource_map(p)
    res = MOD.resolve({"kind": "run", "hierarchy_level": "L2"}, rm)
    assert res["read_first"] == ["shared.md", "unique.md"]


def test_resolve_max_docs_falsy_treated_as_one(tmp_path):
    # max_docs が 0 / None のとき or 1 で cost=1 になる分岐
    p = tmp_path / "rm.yaml"
    p.write_text(
        "resources:\n"
        "  - category: baseline-skill-build\n"
        "    max_docs: 0\n",
        encoding="utf-8",
    )
    rm = MOD.load_resource_map(p)
    res = MOD.resolve({"kind": "run", "hierarchy_level": "L1"}, rm)
    # used_docs が 1 として計上される
    assert "used=1" in res["rationale"]["_budget"]


# ── main (subprocess) ────────────────────────────────────────────────────────
def test_main_subprocess_emits_json(tmp_path):
    rm = _full_resource_map(tmp_path)
    brief = tmp_path / "brief.json"
    brief.write_text(
        json.dumps({"kind": "assign", "hierarchy_level": "L2"}), encoding="utf-8"
    )
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--brief", str(brief), "--resource-map", str(rm)],
        text=True,
        capture_output=True,
    )
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["categories"][0] == "baseline-skill-build"
    assert "evaluator-orchestration" in out["categories"]


def test_main_subprocess_missing_arg_errors(tmp_path):
    rm = _full_resource_map(tmp_path)
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--resource-map", str(rm)],
        text=True,
        capture_output=True,
    )
    assert res.returncode != 0
    assert "--brief" in res.stderr


def test_main_subprocess_invalid_brief_json_raises(tmp_path):
    rm = _full_resource_map(tmp_path)
    brief = tmp_path / "brief.json"
    brief.write_text("{not valid json", encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--brief", str(brief), "--resource-map", str(rm)],
        text=True,
        capture_output=True,
    )
    assert res.returncode != 0
    assert "JSONDecodeError" in res.stderr or "Expecting" in res.stderr


# ── main (in-process) で return 0 / stdout 経路を確実に踏む ───────────────────
def test_main_in_process_returns_zero(tmp_path, monkeypatch, capsys):
    rm = _full_resource_map(tmp_path)
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"kind": "wrap", "hierarchy_level": "L2"}), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["resolve-brief-to-category.py", "--brief", str(brief), "--resource-map", str(rm)],
    )
    rc = MOD.main()
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["brief_fields_used"]["kind"] == "wrap"
