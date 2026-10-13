"""lint-goal-seek.py のゴールシーク準拠検査を実入力で網羅検証する。

対象 script:
  plugins/harness-creator/skills/run-build-skill/scripts/lint-goal-seek.py

方針:
  - 純関数 (parse_frontmatter / is_execution_skill / body_after_frontmatter /
    skill_prefix / checklist_region / lint_file / collect_targets /
    _extract_defaults / check_default_drift) を実ファイルから importlib でロードして直接呼ぶ。
  - lint_file は tmp_path に「合格 fixture」と「各違反 fixture」を書いて実入力で
    findings / warnings を assert する。
  - main は in-process 呼び出し (capsys で stdout/stderr と return code) と
    subprocess(sys.executable) の双方で exit code / 出力を assert する。
  - check_default_drift / --self-test は repo 実ファイル (render-combinators.py /
    with-goal-seek.patch / 各 schema / run-goal-seek/SKILL.md) を読むため、
    現リポジトリ状態で drift なし=0 を期待する (SSOT 整合の回帰検出も兼ねる)。
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
    / "lint-goal-seek.py"
)


def _load():
    """coverage 計測下 (テスト実行フェーズ) で module を import する遅延ロード。"""
    spec = importlib.util.spec_from_file_location("lint_goal_seek_t", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def MOD():
    return _load()


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _json_deepcopy(obj):
    import copy
    return copy.deepcopy(obj)


# ---- 合格 SKILL.md (run loop 実行系: findings/warnings ともに 0) ----
CLEAN_RUN = """---
prefix: run
---

## ゴールシーク実行

ゴール達成までループする。

### 完了チェックリスト
- [ ] 出力ファイルが存在する
- [x] テストが全て通る

### ゴールシーク配線
goal-spec を intermediate.jsonl に original_goal と merged_directive_for_next で記録。
検証 bash: required_keys と original_goal_hash を hashlib.sha256 で照合。
"""


def _write(tmp_path, body, name="SKILL.md"):
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# --- parse_frontmatter ---


def test_parse_frontmatter_flat(MOD):
    fm = MOD.parse_frontmatter('---\nprefix: run\nname: "run-x"\n---\nbody\n')
    assert fm["prefix"] == "run"
    assert fm["name"] == '"run-x"'


def test_parse_frontmatter_no_frontmatter(MOD):
    assert MOD.parse_frontmatter("no leading dashes\n") == {}


def test_parse_frontmatter_unterminated(MOD):
    # 先頭 --- だが閉じ --- が無い -> {}
    assert MOD.parse_frontmatter("---\nprefix: run\nstill open\n") == {}


def test_parse_frontmatter_skips_non_kv_lines(MOD):
    fm = MOD.parse_frontmatter("---\nprefix: run\n# a comment\n- list item\n---\nbody")
    assert fm == {"prefix": "run"}


# --- is_execution_skill / skill_prefix ---


def test_is_execution_skill_by_prefix_and_kind(MOD):
    assert MOD.is_execution_skill({"prefix": "run"}) is True
    assert MOD.is_execution_skill({"kind": "wrap"}) is True
    assert MOD.is_execution_skill({"prefix": "delegate"}) is True
    assert MOD.is_execution_skill({"prefix": "assign"}) is True
    assert MOD.is_execution_skill({"prefix": "ref"}) is False
    assert MOD.is_execution_skill({}) is False


def test_skill_prefix_strips_quotes_and_falls_back_to_kind(MOD):
    assert MOD.skill_prefix({"prefix": '"run"'}) == "run"
    assert MOD.skill_prefix({"kind": "wrap"}) == "wrap"
    assert MOD.skill_prefix({}) == ""


# --- body_after_frontmatter ---


def test_body_after_frontmatter_strips_block(MOD):
    body = MOD.body_after_frontmatter("---\nprefix: run\n---\nHELLO\n")
    assert body.strip() == "HELLO"


def test_body_after_frontmatter_no_block_returns_input(MOD):
    assert MOD.body_after_frontmatter("HELLO") == "HELLO"


def test_body_after_frontmatter_open_only_returns_input(MOD):
    txt = "---\nprefix: run\nno close"
    assert MOD.body_after_frontmatter(txt) == txt


# --- checklist_region ---


def test_checklist_region_found_and_bounded(MOD):
    body = "### 完了チェックリスト\n- [ ] A\n- [x] B\n## 次セクション\nignore\n"
    region = MOD.checklist_region(body)
    assert "- [ ] A" in region
    assert "- [x] B" in region
    assert "次セクション" not in region


def test_checklist_region_to_eof_when_no_next_heading(MOD):
    body = "### 完了チェックリスト\n- [ ] only\n"
    region = MOD.checklist_region(body)
    assert "- [ ] only" in region


def test_checklist_region_absent(MOD):
    assert MOD.checklist_region("no checklist heading here\n") is None


# --- lint_file: 合格系 ---


def test_lint_file_clean_run_no_findings(MOD, tmp_path):
    p = _write(tmp_path, CLEAN_RUN)
    findings, warnings = MOD.lint_file(p)
    assert findings == []
    assert warnings == []


def test_lint_file_ref_is_skipped(MOD, tmp_path):
    # ref-* は実行系外 -> 検査スキップ (空 findings/warnings)
    p = _write(tmp_path, "---\nprefix: ref\n---\n固定手順だらけでも対象外\n## 手順\n")
    findings, warnings = MOD.lint_file(p)
    assert findings == []
    assert warnings == []


def test_lint_file_assign_not_loop_no_checklist_required(MOD, tmp_path):
    # assign は EXECUTION だが LOOP ではない -> goal-seek 見出しのみ必須、
    # checklist/配線 warning は出ない。
    body = "---\nprefix: assign\n---\n## ゴールシーク実行\n採点する。\n"
    p = _write(tmp_path, body)
    findings, warnings = MOD.lint_file(p)
    assert findings == []
    assert warnings == []


# --- lint_file: 違反系 (findings=exit1) ---


def test_lint_file_missing_goal_seek_heading(MOD, tmp_path):
    p = _write(tmp_path, "---\nprefix: run\n---\nゴールシーク見出しが無い本文\n")
    findings, _ = MOD.lint_file(p)
    assert any("ゴールシーク実行' 見出しがない" in f for f in findings)


def test_lint_file_fixed_procedure_heading(MOD, tmp_path):
    body = CLEAN_RUN + "\n## 手順\n1. やる\n"
    p = _write(tmp_path, body)
    findings, _ = MOD.lint_file(p)
    assert any("固定 '## 手順' セクションが残存" in f for f in findings)


def test_lint_file_step_enumeration_violation(MOD, tmp_path):
    body = CLEAN_RUN + "\n### Step 1: 準備\n### Step 2: 実行\n"
    p = _write(tmp_path, body)
    findings, _ = MOD.lint_file(p)
    assert any("固定手順の連番 (### Step N:)" in f and "2 件" in f for f in findings)


def test_lint_file_step_allowed_under_catalog_heading(MOD, tmp_path):
    # 局面カタログ「見出し」セクション配下の ### Step 連番は許容 (violation にならない)
    body = CLEAN_RUN + "\n## 局面カタログ (順序は都度判断)\n### Step 1: A\n### Step 2: B\n"
    p = _write(tmp_path, body)
    findings, _ = MOD.lint_file(p)
    assert not any("固定手順の連番" in f for f in findings)


def test_lint_file_step_violation_when_marker_only_quoted_in_body(MOD, tmp_path):
    # 本文引用 (見出しでない行) のラベル出現では免除しない -> violation (escape 封鎖)
    body = (
        CLEAN_RUN
        + "\n備考: 「局面カタログ (順序は都度判断)」として書くべきという引用。\n"
        + "### Step 1: A\n### Step 2: B\n"
    )
    p = _write(tmp_path, body)
    findings, _ = MOD.lint_file(p)
    assert any("固定手順の連番 (### Step N:)" in f and "2 件" in f for f in findings)


def test_lint_file_step_outside_catalog_section_violation(MOD, tmp_path):
    # カタログ見出しセクションは次の ## 見出しで終端。以降の Step 連番は violation
    body = (
        CLEAN_RUN
        + "\n## 局面カタログ (順序は都度判断)\n### Step 1: 中は許容\n"
        + "## 別セクション\n### Step 2: 外A\n### Step 3: 外B\n"
    )
    p = _write(tmp_path, body)
    findings, _ = MOD.lint_file(p)
    assert any("固定手順の連番 (### Step N:)" in f and "2 件" in f for f in findings)


def test_lint_file_catalog_marker_embedded_in_heading_text(MOD, tmp_path):
    # 見出しテキスト内包型 (### 採点フロー（局面カタログ・順序は都度判断）) も有効
    body = (
        CLEAN_RUN
        + "\n### 採点フロー（局面カタログ・順序は都度判断）\n"
        + "### Step 1: A\n### Step 2: B\n"
    )
    p = _write(tmp_path, body)
    findings, _ = MOD.lint_file(p)
    assert not any("固定手順の連番" in f for f in findings)


def test_lint_file_level4_heading_marker_not_a_catalog_declaration(MOD, tmp_path):
    # カタログ宣言は ##/### 見出しのみ。#### レベルのラベル出現では免除しない
    body = (
        CLEAN_RUN
        + "\n#### 局面カタログ (順序は都度判断)\n### Step 1: A\n### Step 2: B\n"
    )
    p = _write(tmp_path, body)
    findings, _ = MOD.lint_file(p)
    assert any("固定手順の連番" in f for f in findings)


def test_lint_file_single_step_outside_catalog_below_threshold(MOD, tmp_path):
    # カタログ内 1 件 + 外 1 件 -> 外は 1 件のみで閾値 (2 連) 未満 -> 許容
    body = (
        CLEAN_RUN
        + "\n## 局面カタログ (順序は都度判断)\n### Step 1: 中\n"
        + "## 別セクション\n### Step 2: 外の単発\n"
    )
    p = _write(tmp_path, body)
    findings, _ = MOD.lint_file(p)
    assert not any("固定手順の連番" in f for f in findings)


def test_lint_file_single_step_not_violation(MOD, tmp_path):
    # 1 件のみは閾値 (2 連) 未満 -> violation にならない
    body = CLEAN_RUN + "\n### Step 1: 単発\n"
    p = _write(tmp_path, body)
    findings, _ = MOD.lint_file(p)
    assert not any("固定手順の連番" in f for f in findings)


def test_lint_file_checklist_missing_binary_items(MOD, tmp_path):
    body = (
        "---\nprefix: run\n---\n## ゴールシーク実行\n"
        "### 完了チェックリスト\n本文のみで二値項目が無い\n"
        "### ゴールシーク配線\n"
        "intermediate.jsonl original_goal merged_directive_for_next "
        "required_keys original_goal_hash hashlib.sha256\n"
    )
    p = _write(tmp_path, body)
    findings, _ = MOD.lint_file(p)
    assert any("二値チェックリスト項目" in f for f in findings)


def test_lint_file_checklist_vague_term(MOD, tmp_path):
    body = (
        "---\nprefix: run\n---\n## ゴールシーク実行\n"
        "### 完了チェックリスト\n- [ ] 適切に処理する\n"
        "### ゴールシーク配線\n"
        "intermediate.jsonl original_goal merged_directive_for_next "
        "required_keys original_goal_hash hashlib.sha256\n"
    )
    p = _write(tmp_path, body)
    findings, _ = MOD.lint_file(p)
    assert any("曖昧語" in f and "適切に" in f for f in findings)


def test_lint_file_checklist_placeholder_skips_binary_check(MOD, tmp_path):
    # 未展開 {{ }} を含む region は二値検査スキップ -> 二値欠落 finding が出ない
    body = (
        "---\nprefix: run\n---\n## ゴールシーク実行\n"
        "### 完了チェックリスト\n{{checklist}}\n"
        "### ゴールシーク配線\n"
        "intermediate.jsonl original_goal merged_directive_for_next "
        "required_keys original_goal_hash hashlib.sha256\n"
    )
    p = _write(tmp_path, body)
    findings, _ = MOD.lint_file(p)
    assert not any("二値チェックリスト項目" in f for f in findings)


# --- lint_file: warning 系 (exit0 助言) ---


def test_lint_file_missing_wiring_section_warns(MOD, tmp_path):
    # 配線サブセクションが無い -> warning (findings ではない)
    body = (
        "---\nprefix: run\n---\n## ゴールシーク実行\n"
        "### 完了チェックリスト\n- [ ] done\n"
    )
    p = _write(tmp_path, body)
    findings, warnings = MOD.lint_file(p)
    assert any("ゴールシーク配線' が無い" in w for w in warnings)
    # 配線が無いと中間成果物 / 機械検証トークンも全欠落 warning が付く
    assert any("中間成果物アンカー必須トークン" in w for w in warnings)
    assert any("機械検証 bash 必須トークン" in w for w in warnings)


def test_lint_file_partial_intermediate_tokens_warns(MOD, tmp_path):
    # 配線はあるが中間成果物トークンを 1 つ欠落 -> warning に欠落トークンが列挙される
    body = (
        "---\nprefix: run\n---\n## ゴールシーク実行\n"
        "### 完了チェックリスト\n- [ ] done\n"
        "### ゴールシーク配線\n"
        "intermediate.jsonl original_goal だけで merged 欠落 "
        "required_keys original_goal_hash hashlib.sha256\n"
    )
    p = _write(tmp_path, body)
    _, warnings = MOD.lint_file(p)
    assert any("merged_directive_for_next" in w for w in warnings)


def test_lint_file_partial_verify_tokens_warns(MOD, tmp_path):
    body = (
        "---\nprefix: run\n---\n## ゴールシーク実行\n"
        "### 完了チェックリスト\n- [ ] done\n"
        "### ゴールシーク配線\n"
        "intermediate.jsonl original_goal merged_directive_for_next "
        "required_keys のみで hash 欠落\n"
    )
    p = _write(tmp_path, body)
    _, warnings = MOD.lint_file(p)
    assert any("機械検証 bash 必須トークン" in w for w in warnings)
    assert any("hashlib.sha256" in w for w in warnings)


def test_lint_file_read_error_returns_finding(MOD, tmp_path):
    # 存在しないパス -> read error finding
    missing = tmp_path / "nope" / "SKILL.md"
    findings, warnings = MOD.lint_file(missing)
    # frontmatter parse 前に read 失敗するため findings に read error が入る
    assert findings and "read error" in findings[0]


# --- collect_targets ---


def test_collect_targets_empty(MOD):
    assert MOD.collect_targets([]) == []


def test_collect_targets_explicit_paths(MOD):
    out = MOD.collect_targets(["a/SKILL.md", "b/SKILL.md"])
    assert [str(p) for p in out] == ["a/SKILL.md", "b/SKILL.md"]


def test_collect_targets_skills_dir_globs(MOD, tmp_path):
    (tmp_path / "run-a").mkdir()
    (tmp_path / "run-a" / "SKILL.md").write_text(CLEAN_RUN, encoding="utf-8")
    (tmp_path / "run-b").mkdir()
    (tmp_path / "run-b" / "SKILL.md").write_text(CLEAN_RUN, encoding="utf-8")
    out = MOD.collect_targets(["--skills-dir", str(tmp_path)])
    assert len(out) == 2
    assert all(p.name == "SKILL.md" for p in out)


def test_collect_targets_skills_dir_missing_arg(MOD):
    assert MOD.collect_targets(["--skills-dir"]) == []


def test_collect_targets_skills_dir_not_a_dir(MOD, tmp_path):
    nonexist = tmp_path / "no_such_dir"
    assert MOD.collect_targets(["--skills-dir", str(nonexist)]) == []


# --- _extract_defaults ---


def test_extract_defaults_parses_tokens(MOD):
    txt = (
        'goal_seek.engine | default("run-goal-seek")\n'
        'goal_seek.fork | default("team")\n'
        "goal_seek.max_loops | default(8)\n"
    )
    d = MOD._extract_defaults(txt)
    assert d == {"engine": "run-goal-seek", "fork": "team", "max_loops": "8"}


def test_extract_defaults_handles_escaped_quotes(MOD):
    txt = 'goal_seek.engine | default(\\"run-goal-seek\\")\n'
    d = MOD._extract_defaults(txt)
    assert d["engine"] == "run-goal-seek"


def test_extract_defaults_missing_returns_none(MOD):
    d = MOD._extract_defaults("nothing relevant here")
    assert d == {"engine": None, "fork": None, "max_loops": None}


# --- check_default_drift (repo 実ファイル: 現状態で整合=空) ---


def test_check_default_drift_clean_repo(MOD):
    drift = MOD.check_default_drift()
    assert drift == [], f"unexpected SSOT drift: {drift}"


# --- check_default_drift: 故障注入 (各 drift 分岐を実入力で踏む) ---
# render定数 / patch / 各 schema / run-goal-seek を tmp_path の壊れた fixture に差し替え、
# 既定値乖離 / 中間成果物欠落 / enum drift / 検証 bash トークン欠落の findings を実発火させる。

# render-combinators 相当: engine/fork/max_loops 既定 + intermediate.jsonl + 全 required キー +
# drift_signal enum 全値 + 検証 bash トークンを内包する「整合テキスト」。
_GOOD_RENDER = (
    'engine: {{goal_seek.engine | default("inline")}}\n'
    'fork: {{goal_seek.fork | default("subagent")}}\n'
    "max_loops: {{goal_seek.max_loops | default(5)}}\n"
    "eval-log/{{skill_name}}-intermediate.jsonl\n"
    "iteration original_goal current_goal_snapshot delta_from_original "
    "merged_directive_for_next drift_signal\n"
    "initial aligned compressing stagnant widening oscillating\n"
    "required_keys original_goal_hash hashlib.sha256\n"
    # engine:task-graph 変種 (C04 check_task_graph_variant) の consumption verifier /
    # dependency graph knowledge consult トークン。整合 fixture は task-graph 配線も携帯する。
    "task-graph extract-ready-set-from-checklist.py build-self-reflection-entry.py ready_set selected_item "
    "依存順消費 self-reflect 完了 gate extract-capability-dependency-graph.py "
    "build-capability-graph-knowledge-entry.py dependency graph knowledge\n"
)
_GOOD_PATCH = _GOOD_RENDER  # patch 側も同型で逐語一致させる
_GOOD_RGS = "required_keys original_goal_hash hashlib.sha256\n"
_GOOD_BUILD_FLAGS = {
    "properties": {
        "with_goal_seek": {
            "properties": {
                # engine enum は task-graph を含む (check_task_graph_variant (a))。
                "engine": {"default": "inline", "enum": ["inline", "run-goal-seek", "task-graph"]},
                "max_loops": {"default": 5},
            }
        }
    }
}
_GOOD_LOOP_SCHEMA = {
    "properties": {
        "fork_context": {"default": "subagent"},
        "max_loops": {"default": 5},
        # checklist item に depends_on additive フィールド (check_task_graph_variant (b))。
        "checklist": {
            "items": {
                "properties": {
                    "depends_on": {"type": "array", "default": []},
                }
            }
        },
        "intermediate_artifacts": {
            "items": {
                "required": [
                    "iteration",
                    "original_goal",
                    "current_goal_snapshot",
                    "delta_from_original",
                    "merged_directive_for_next",
                    "drift_signal",
                ],
                "properties": {
                    "drift_signal": {
                        "enum": [
                            "initial",
                            "aligned",
                            "compressing",
                            "stagnant",
                            "widening",
                            "oscillating",
                        ]
                    }
                },
            }
        },
    }
}


def _install_drift_fixtures(MOD, tmp_path, monkeypatch, *,
                            render=_GOOD_RENDER, patch=_GOOD_PATCH,
                            build_flags=None, loop_schema=None, rgs=_GOOD_RGS):
    import json as _json

    render_p = tmp_path / "render-combinators.py"
    patch_p = tmp_path / "with-goal-seek.patch"
    bf_p = tmp_path / "build-flags.schema.json"
    ls_p = tmp_path / "goal-seek-loop.schema.json"
    rgs_dir = tmp_path / "run-goal-seek"
    rgs_dir.mkdir()
    rgs_p = rgs_dir / "SKILL.md"
    render_p.write_text(render, encoding="utf-8")
    patch_p.write_text(patch, encoding="utf-8")
    bf_p.write_text(_json.dumps(build_flags or _GOOD_BUILD_FLAGS), encoding="utf-8")
    ls_p.write_text(_json.dumps(loop_schema or _GOOD_LOOP_SCHEMA), encoding="utf-8")
    rgs_p.write_text(rgs, encoding="utf-8")
    monkeypatch.setattr(MOD, "_RENDER", render_p)
    monkeypatch.setattr(MOD, "_PATCH", patch_p)
    monkeypatch.setattr(MOD, "_BUILD_FLAGS", bf_p)
    monkeypatch.setattr(MOD, "_LOOP_SCHEMA", ls_p)
    # run-goal-seek は parents[2] / "run-goal-seek" / "SKILL.md" で解決される。
    # __file__ の探索を tmp 化するのは難しいため、check_default_drift 内の
    # Path(...).exists() を満たすよう run-goal-seek を直接差し替えできない。
    # → run-goal-seek パスは monkeypatch できないので、整合 fixture では本物の
    #   run-goal-seek/SKILL.md (トークン保持) を使い、検証 bash トークン分岐のみ
    #   render/patch 側欠落で踏む。
    return {"render": render_p, "patch": patch_p}


def test_drift_fixtures_all_consistent_no_findings(MOD, tmp_path, monkeypatch):
    # 整合 fixture では (run-goal-seek は本物を使うため) findings は空であること。
    _install_drift_fixtures(MOD, tmp_path, monkeypatch)
    assert MOD.check_default_drift() == []


def test_drift_render_extract_failure(MOD, tmp_path, monkeypatch):
    # render から engine/fork/max_loops を抽出不能 -> "抽出できない" findings
    bad = "no goal_seek tokens at all\nintermediate.jsonl original_goal\n"
    _install_drift_fixtures(MOD, tmp_path, monkeypatch, render=bad, patch=bad)
    drift = MOD.check_default_drift()
    assert any("render-combinators.py から goal_seek." in d for d in drift)
    assert any("with-goal-seek.patch から goal_seek." in d for d in drift)


def test_drift_render_patch_mismatch(MOD, tmp_path, monkeypatch):
    patch = _GOOD_PATCH.replace('default("inline")', 'default("run-goal-seek")')
    _install_drift_fixtures(MOD, tmp_path, monkeypatch, patch=patch)
    drift = MOD.check_default_drift()
    assert any("render定数" in d and "patch" in d for d in drift)


def test_drift_engine_vs_build_flags(MOD, tmp_path, monkeypatch):
    bf = {
        "properties": {
            "with_goal_seek": {
                "properties": {
                    "engine": {"default": "run-goal-seek"},  # render は inline -> drift
                    "max_loops": {"default": 5},
                }
            }
        }
    }
    _install_drift_fixtures(MOD, tmp_path, monkeypatch, build_flags=bf)
    drift = MOD.check_default_drift()
    assert any("engine 既定 drift" in d for d in drift)


def test_drift_fork_and_maxloops_vs_loop_schema(MOD, tmp_path, monkeypatch):
    ls = _json_deepcopy(_GOOD_LOOP_SCHEMA)
    ls["properties"]["fork_context"]["default"] = "agent-team"  # render は subagent
    ls["properties"]["max_loops"]["default"] = 9  # render は 5
    _install_drift_fixtures(MOD, tmp_path, monkeypatch, loop_schema=ls)
    drift = MOD.check_default_drift()
    assert any("fork 既定 drift" in d for d in drift)
    assert any("max_loops 既定 drift" in d and "goal-seek-loop.schema" in d for d in drift)


def test_drift_maxloops_vs_build_flags(MOD, tmp_path, monkeypatch):
    bf = _json_deepcopy(_GOOD_BUILD_FLAGS)
    bf["properties"]["with_goal_seek"]["properties"]["max_loops"]["default"] = 7
    _install_drift_fixtures(MOD, tmp_path, monkeypatch, build_flags=bf)
    drift = MOD.check_default_drift()
    assert any("max_loops 既定 drift" in d and "build-flags.schema" in d for d in drift)


def test_drift_intermediate_path_missing(MOD, tmp_path, monkeypatch):
    # render/patch から intermediate.jsonl 行を除去 -> 配線欠落 findings
    render = _GOOD_RENDER.replace("eval-log/{{skill_name}}-intermediate.jsonl\n", "")
    _install_drift_fixtures(MOD, tmp_path, monkeypatch, render=render, patch=render)
    drift = MOD.check_default_drift()
    assert any("render-combinators.py から intermediate.jsonl 配線が欠落" in d for d in drift)
    assert any("with-goal-seek.patch から intermediate.jsonl 配線が欠落" in d for d in drift)


def test_drift_schema_missing_intermediate_artifacts(MOD, tmp_path, monkeypatch):
    ls = {"properties": {"fork_context": {"default": "subagent"},
                         "max_loops": {"default": 5}}}
    _install_drift_fixtures(MOD, tmp_path, monkeypatch, loop_schema=ls)
    drift = MOD.check_default_drift()
    assert any("intermediate_artifacts プロパティが欠落" in d for d in drift)


def test_drift_required_key_absent_from_render_patch(MOD, tmp_path, monkeypatch):
    # render/patch から required キー "current_goal_snapshot" を抜く
    render = _GOOD_RENDER.replace("current_goal_snapshot ", "")
    _install_drift_fixtures(MOD, tmp_path, monkeypatch, render=render, patch=render)
    drift = MOD.check_default_drift()
    assert any("current_goal_snapshot が render-combinators.py" in d for d in drift)
    assert any("current_goal_snapshot が with-goal-seek.patch" in d for d in drift)


def test_drift_enum_value_absent(MOD, tmp_path, monkeypatch):
    # render/patch どちらからも enum 値 "oscillating" を抜く
    render = _GOOD_RENDER.replace(" oscillating", "")
    _install_drift_fixtures(MOD, tmp_path, monkeypatch, render=render, patch=render)
    drift = MOD.check_default_drift()
    assert any("drift_signal enum 'oscillating'" in d for d in drift)


def test_drift_verify_token_absent_from_render_patch(MOD, tmp_path, monkeypatch):
    # render/patch から検証 bash トークン hashlib.sha256 を抜く (run-goal-seek は本物=保持)
    render = _GOOD_RENDER.replace("hashlib.sha256", "")
    _install_drift_fixtures(MOD, tmp_path, monkeypatch, render=render, patch=render)
    drift = MOD.check_default_drift()
    assert any("hashlib.sha256' が render-combinators.py に不在" in d for d in drift)
    assert any("hashlib.sha256' が with-goal-seek.patch に不在" in d for d in drift)


def test_drift_source_read_error(MOD, tmp_path, monkeypatch):
    # _RENDER を存在しないパスにして read error 経路 (early return) を踏む
    monkeypatch.setattr(MOD, "_RENDER", tmp_path / "nope.py")
    drift = MOD.check_default_drift()
    assert drift and "source read error" in drift[0]


# --- main: in-process ---


def test_main_self_test_ok(MOD, capsys):
    rc = MOD.main(["--self-test"])
    assert rc == 0
    assert "OK: goal-seek 既定値 SSOT 整合" in capsys.readouterr().out


def test_main_self_test_failure_returns_1(MOD, monkeypatch, capsys):
    # drift 検出時は exit1 + stderr に各 finding を吐く
    monkeypatch.setattr(MOD, "check_default_drift", lambda: ["self-test: 故障注入"])
    rc = MOD.main(["--self-test"])
    assert rc == 1
    assert "故障注入" in capsys.readouterr().err


def test_main_usage_error_no_args(MOD, capsys):
    rc = MOD.main([])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


def test_main_ok_with_clean_file(MOD, tmp_path, capsys):
    p = _write(tmp_path, CLEAN_RUN)
    rc = MOD.main([str(p)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK:" in out
    assert "passed goal-seek lint" in out


def test_main_violation_returns_1(MOD, tmp_path, capsys):
    p = _write(tmp_path, "---\nprefix: run\n---\nゴールシーク見出し無し\n")
    rc = MOD.main([str(p)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "見出しがない" in err


def test_main_ok_with_warning_suffix(MOD, tmp_path, capsys):
    # 配線欠落 warning は出るが finding は無い -> exit0 + warning suffix
    body = "---\nprefix: run\n---\n## ゴールシーク実行\n### 完了チェックリスト\n- [ ] done\n"
    p = _write(tmp_path, body)
    rc = MOD.main([str(p)])
    assert rc == 0
    cap = capsys.readouterr()
    assert "WARN:" in cap.err
    assert "warning(s)" in cap.out


# --- main: subprocess (exit code 契約) ---


def test_subprocess_self_test_exits_0(tmp_path):
    proc = _run(["--self-test"])
    assert proc.returncode == 0
    assert "SSOT 整合" in proc.stdout


def test_subprocess_usage_exits_2():
    proc = _run([])
    assert proc.returncode == 2
    assert "usage:" in proc.stderr


def test_subprocess_violation_exits_1(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\nprefix: run\n---\nゴールシーク無し\n", encoding="utf-8")
    proc = _run([str(p)])
    assert proc.returncode == 1
    assert "見出しがない" in proc.stderr


def test_subprocess_clean_exits_0(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(CLEAN_RUN, encoding="utf-8")
    proc = _run([str(p)])
    assert proc.returncode == 0
    assert "passed goal-seek lint" in proc.stdout


# A canonical local reference supplies shared tokens, but cannot replace execution.
# validator は検査契約をコードとして持つ最小形 (コメントの語だけでは通らない)。
VALIDATOR_CODE = (
    "import hashlib\n"
    "REQUIRED_KEYS = {'iteration'}\n"
    "def check(progress, encoded):\n"
    "    return progress.get('original_goal_hash') == hashlib.sha256(encoded).hexdigest()\n"
)


def _canonical_plugin(tmp_path, *, reference_text=None, command=None):
    plugin = tmp_path / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin/plugin.json").write_text('{}')
    (plugin / "references").mkdir()
    (plugin / "scripts").mkdir()
    skill = plugin / "skills/run-test"
    skill.mkdir(parents=True)
    contract = plugin / "references/goal-seek-anchor-contract.md"
    contract.write_text(reference_text if reference_text is not None else
                        "intermediate.jsonl original_goal merged_directive_for_next required_keys original_goal_hash hashlib.sha256 "
                        "iteration current_goal_snapshot delta_from_original drift_signal UTF-8 validate-inline-goal-seek-anchor.py")
    (plugin / "scripts/validate-inline-goal-seek-anchor.py").write_text(VALIDATOR_CODE)
    body = CLEAN_RUN.split("### ゴールシーク配線")[0] + "### ゴールシーク配線\n"
    body += "`../../references/goal-seek-anchor-contract.md` が正本。\n```bash\n"
    body += command if command is not None else 'python3 "$PLUGIN_ROOT/scripts/validate-inline-goal-seek-anchor.py" "$progress_path" "$intermediate_path"'
    body += "\n```\n"
    path = skill / "SKILL.md"
    path.write_text(body)
    return path, contract


def test_canonical_local_anchor_reference_is_resolved_and_executed(MOD, tmp_path):
    path, _ = _canonical_plugin(tmp_path)
    assert MOD.lint_file(path) == ([], [])


@pytest.mark.parametrize("reference_text", ["", "required_keys original_goal_hash"])
def test_empty_or_incomplete_canonical_reference_is_not_an_escape(MOD, tmp_path, reference_text):
    path, _ = _canonical_plugin(tmp_path, reference_text=reference_text)
    findings, warnings = MOD.lint_file(path)
    assert any("必須契約が不足" in finding for finding in findings)
    assert warnings


@pytest.mark.parametrize("command", ["# python3 $PLUGIN_ROOT/scripts/validate-inline-goal-seek-anchor.py progress intermediate",
                                     'python3 "$PLUGIN_ROOT/scripts/validate-inline-goal-seek-anchor.py" "$progress_path"'])
def test_reference_needs_real_command_and_both_arguments(MOD, tmp_path, command):
    path, _ = _canonical_plugin(tmp_path, command=command)
    findings, _ = MOD.lint_file(path)
    assert any("両引数が無い" in finding for finding in findings)


def test_missing_reference_is_a_violation(MOD, tmp_path):
    path, contract = _canonical_plugin(tmp_path)
    contract.unlink()
    findings, _ = MOD.lint_file(path)
    assert any("不在" in finding for finding in findings)


def test_symlink_reference_outside_plugin_is_rejected(MOD, tmp_path):
    path, contract = _canonical_plugin(tmp_path)
    outside = tmp_path / "foreign-contract.md"
    outside.write_text(contract.read_text())
    contract.unlink()
    contract.symlink_to(outside)
    findings, _ = MOD.lint_file(path)
    assert any("root 外" in finding for finding in findings)


def test_absolute_foreign_contract_reference_is_rejected(MOD, tmp_path):
    path, _ = _canonical_plugin(tmp_path)
    path.write_text(path.read_text().replace("../../references/goal-seek-anchor-contract.md",
                                           "/foreign/goal-seek-anchor-contract.md"))
    findings, _ = MOD.lint_file(path)
    assert any("正規パス" in finding for finding in findings)


def test_missing_validator_is_a_violation(MOD, tmp_path):
    path, _ = _canonical_plugin(tmp_path)
    (path.parents[2] / "scripts/validate-inline-goal-seek-anchor.py").unlink()
    findings, _ = MOD.lint_file(path)
    assert any("validator が不在" in finding for finding in findings)


# ---- 配線 warning の ratchet (grace 未登録は violation / 返済済み登録も violation) ----
# 検出はされるが rc に出ない warning は誰も見ない。登録 (path, kind) 以外を rc へ出す。
UNWIRED_RUN = """---
prefix: run
---

## ゴールシーク実行

### 完了チェックリスト

- [ ] 出力ファイルが存在する
"""


def _unwired_skill(tmp_path, name="run-newcomer"):
    """配線 3 warning (wiring-section / intermediate / verification) を出す loop skill。"""
    skill = tmp_path / "plugins/demo/skills" / name
    skill.mkdir(parents=True)
    path = skill / "SKILL.md"
    path.write_text(UNWIRED_RUN, encoding="utf-8")
    return path


def test_unregistered_wiring_warning_fails(MOD, tmp_path, monkeypatch, capsys):
    """grace 未登録の配線 warning は rc=1 になる (以前は 37 件が rc=0 のまま残っていた)。"""
    path = _unwired_skill(tmp_path)
    monkeypatch.setattr(MOD, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(MOD, "GRANDFATHERED_WARNINGS", frozenset())

    rc = MOD.main(["--skills-dir", str(tmp_path / "plugins/demo/skills")])

    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err.count("grace 未登録") == 3
    for kind in MOD.WARNING_KINDS:
        assert f"kind={kind}" in captured.err
    assert "OK:" not in captured.out

    # 対照: 同じ 3 件を登録すると warning のまま rc=0 に戻る。
    rel = str(path.resolve().relative_to(tmp_path))
    monkeypatch.setattr(
        MOD,
        "GRANDFATHERED_WARNINGS",
        frozenset({(rel, kind) for kind in MOD.WARNING_KINDS}),
    )
    assert MOD.main(["--skills-dir", str(tmp_path / "plugins/demo/skills")]) == 0


def test_repaid_and_vanished_grace_registrations_fail(MOD, tmp_path, monkeypatch, capsys):
    """返済済み (走査したが warning を出さない) / 消滅済みの登録も rc=1 で削除を強制する。"""
    path = _unwired_skill(tmp_path)
    rel = str(path.resolve().relative_to(tmp_path))
    monkeypatch.setattr(MOD, "_REPO_ROOT", tmp_path)
    # wiring-section だけ返済したとみなす登録 (実際には 3 件出るので unlisted 側で落ちないよう全件登録)
    # + 実在しない path の登録を混ぜる。
    monkeypatch.setattr(
        MOD,
        "GRANDFATHERED_WARNINGS",
        frozenset(
            {(rel, kind) for kind in MOD.WARNING_KINDS}
            | {("plugins/demo/skills/run-gone/SKILL.md", "wiring-section")}
        ),
    )

    rc = MOD.main(["--skills-dir", str(tmp_path / "plugins/demo/skills")])

    captured = capsys.readouterr()
    assert rc == 1
    assert "run-gone/SKILL.md [登録 path が走査範囲内に実在しない]" in captured.err


def test_warning_ratchet_skips_paths_outside_repo(MOD, tmp_path, monkeypatch):
    """repo 外 ($OUT_BASE 生成物・tmp fixture) は登録できる同一性が無いので対象外。"""
    path = _unwired_skill(tmp_path)
    monkeypatch.setattr(MOD, "GRANDFATHERED_WARNINGS", frozenset())
    # _REPO_ROOT は実 repo のまま = path は repo 外。
    assert MOD.repo_relative(path) is None
    assert MOD.check_warning_ratchet([(path, "'### ゴールシーク配線' が無い")], set(), None) == []


# ---- 全 plugin の既知違反 baseline (載った違反は猶予 / 新規と stale は violation) ----
# 構造違反は kind を持たず GRANDFATHERED_WARNINGS で猶予できない。CI scope 外の plugin に
# 残る違反を (path, 規則) で固定し、固定外だけを rc=1 にする。
NO_HEADING_ASSIGN = """---
prefix: assign
---

## 採点
"""


def _demo_repo(MOD, tmp_path, monkeypatch, skills):
    """tmp_path を repo root とみなし、plugins/demo/skills/<name>/SKILL.md を並べる。"""
    monkeypatch.setattr(MOD, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(MOD, "GRANDFATHERED_WARNINGS", frozenset())
    for name, body in skills.items():
        skill = tmp_path / "plugins/demo/skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(body, encoding="utf-8")
    return tmp_path / "plugins/demo/skills"


def _baseline(tmp_path, debt):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"debt": debt}, ensure_ascii=False), encoding="utf-8")
    return str(path)


_OLD_DEBT = {
    "plugins/demo/skills/run-old/SKILL.md": [
        "wiring-section", "intermediate-tokens", "verification-tokens"],
    "plugins/demo/skills/assign-old/SKILL.md": ["goal-seek-heading"],
}


def test_baseline_suppresses_listed_violations(MOD, tmp_path, monkeypatch, capsys):
    skills_dir = _demo_repo(MOD, tmp_path, monkeypatch,
                            {"run-old": UNWIRED_RUN, "assign-old": NO_HEADING_ASSIGN})
    # 対照: baseline 無しでは構造違反 1 件と grace 未登録 3 件で rc=1。
    assert MOD.main(["--skills-dir", str(skills_dir)]) == 1
    capsys.readouterr()

    rc = MOD.main(["--skills-dir", str(skills_dir), "--baseline", _baseline(tmp_path, _OLD_DEBT)])

    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert "baseline で猶予した既知違反 4 件" in captured.out


def test_baseline_new_violation_fails(MOD, tmp_path, monkeypatch, capsys):
    skills_dir = _demo_repo(MOD, tmp_path, monkeypatch, {
        "run-old": UNWIRED_RUN, "assign-old": NO_HEADING_ASSIGN, "assign-new": NO_HEADING_ASSIGN})

    rc = MOD.main(["--skills-dir", str(skills_dir), "--baseline", _baseline(tmp_path, _OLD_DEBT)])

    err = [line for line in capsys.readouterr().err.splitlines() if not line.startswith("WARN:")]
    assert rc == 1
    assert len(err) == 1 and "assign-new/SKILL.md" in err[0] and "見出しがない" in err[0]


def test_baseline_same_path_new_rule_fails(MOD, tmp_path, monkeypatch, capsys):
    """path が載っていても、載っていない規則の違反は猶予しない (組で照合する)。"""
    skills_dir = _demo_repo(MOD, tmp_path, monkeypatch,
                            {"run-old": UNWIRED_RUN, "assign-old": NO_HEADING_ASSIGN})
    debt = dict(_OLD_DEBT)
    debt["plugins/demo/skills/run-old/SKILL.md"] = ["wiring-section", "intermediate-tokens"]

    rc = MOD.main(["--skills-dir", str(skills_dir), "--baseline", _baseline(tmp_path, debt)])

    assert rc == 1
    assert "kind=verification-tokens" in capsys.readouterr().err


def test_baseline_repaid_and_vanished_entries_fail(MOD, tmp_path, monkeypatch, capsys):
    skills_dir = _demo_repo(MOD, tmp_path, monkeypatch,
                            {"run-old": UNWIRED_RUN, "assign-old": CLEAN_RUN})
    debt = dict(_OLD_DEBT)  # assign-old は返済済み (CLEAN_RUN は違反を出さない)
    debt["plugins/demo/skills/run-gone/SKILL.md"] = ["fixed-procedure"]

    rc = MOD.main(["--skills-dir", str(skills_dir), "--baseline", _baseline(tmp_path, debt)])

    err = capsys.readouterr().err
    assert rc == 1
    assert "baseline の登録が返済済み/消滅済み" in err
    assert "assign-old/SKILL.md [goal-seek-heading]" in err
    assert "run-gone/SKILL.md [登録 path が走査範囲内に実在しない]" in err


def test_baseline_entries_outside_narrowed_scope_are_not_stale(MOD, tmp_path, monkeypatch, capsys):
    """全 plugin 用の台帳を 1 plugin に絞った実行で使っても、範囲外の登録は stale にしない。"""
    skills_dir = _demo_repo(MOD, tmp_path, monkeypatch,
                            {"run-old": UNWIRED_RUN, "assign-old": NO_HEADING_ASSIGN})
    debt = dict(_OLD_DEBT)
    debt["plugins/other/skills/run-x/SKILL.md"] = ["goal-seek-heading"]

    rc = MOD.main(["--skills-dir", str(skills_dir), "--baseline", _baseline(tmp_path, debt)])

    assert rc == 0, capsys.readouterr().err


def test_baseline_does_not_cover_rules_outside_baseline_rules(MOD, tmp_path, monkeypatch):
    """BASELINE_RULES の外の違反 (今ある負債でない規則) は baseline_rule が None で常に落ちる。"""
    assert MOD.baseline_rule("x/SKILL.md: 共通アンカー参照が正規パスでない・root 外・不在: y") is None
    assert MOD.baseline_rule("x/SKILL.md: チェックリスト項目に曖昧語 ['適切に'] があり") is None


@pytest.mark.parametrize("payload, needle", [
    ({"debt": {"plugins/a/skills/run-a/SKILL.md": ["anchor-reference"]}}, "載せられない規則"),
    ({"debt": {"plugins/a/skills/run-a/SKILL.md": []}}, "空でない配列"),
    ({"debt": {"plugins/a/skills/run-a/SKILL.md": ["goal-seek-heading", "goal-seek-heading"]}},
     "重複"),
    ({"debt": {"/abs/skills/run-a/SKILL.md": ["goal-seek-heading"]}}, "repo 相対"),
    ({"debt": {"plugins/../x/SKILL.md": ["goal-seek-heading"]}}, "repo 相対"),
    ({"entries": []}, "debt オブジェクトが無い"),
])
def test_malformed_baseline_exits_2(MOD, tmp_path, capsys, payload, needle):
    p = tmp_path / "baseline.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    assert MOD.main(["--skills-dir", str(tmp_path), "--baseline", str(p)]) == 2
    assert needle in capsys.readouterr().err


@pytest.mark.parametrize("args", [["--baseline"], ["--baseline", "--skills-dir", "."]])
def test_subprocess_baseline_without_value_exits_2(tmp_path, args):
    proc = _run(["--skills-dir", str(tmp_path), *args])
    assert proc.returncode == 2
    assert "--baseline には JSON の path が要る" in proc.stderr


def test_subprocess_missing_baseline_file_exits_2(tmp_path):
    proc = _run(["--skills-dir", str(tmp_path), "--baseline", str(tmp_path / "none.json")])
    assert proc.returncode == 2
    assert "baseline を読めない" in proc.stderr


def test_collect_targets_skips_fixtures_under_scanned_dir(MOD, tmp_path):
    """tests/**/fixtures の SKILL.md は他テストの見本で、配布スキルではないので拾わない。"""
    real = tmp_path / "plugins/demo/skills/run-a/SKILL.md"
    fixture = tmp_path / "plugins/demo/tests/run-a/fixtures/accept/skills/run-a/SKILL.md"
    for p in (real, fixture):
        p.parent.mkdir(parents=True)
        p.write_text(CLEAN_RUN, encoding="utf-8")

    assert MOD.collect_targets(["--skills-dir", str(tmp_path / "plugins")]) == [real]
    # fixtures ディレクトリ自体を指せば、見本を検査できる。
    fixtures_dir = tmp_path / "plugins/demo/tests/run-a/fixtures"
    assert MOD.collect_targets(["--skills-dir", str(fixtures_dir)]) == [fixture]


def test_repo_scan_excludes_real_fixture_skill_files(MOD):
    targets = MOD.collect_targets(["--skills-dir", str(ROOT / "plugins")])
    assert targets
    assert not [p for p in targets if "fixtures" in p.relative_to(ROOT).parts]


def test_repo_all_plugins_pass_with_checked_in_baseline():
    """CI と同じ呼び出し。新しい違反と、返済したのに台帳に残った組の両方で落ちる。"""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--skills-dir", "plugins",
         "--baseline", "scripts/goal-seek-lint-baseline.json"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "baseline で猶予した既知違反" in proc.stdout


# --- 再レビュー B の [低] 指摘の再発防止 ---


def test_validator_with_contract_words_only_in_comment_is_rejected(MOD, tmp_path):
    path, _ = _canonical_plugin(tmp_path)
    (path.parents[2] / "scripts/validate-inline-goal-seek-anchor.py").write_text(
        "# REQUIRED_KEYS original_goal_hash sha256\n")
    findings, _ = MOD.lint_file(path)
    assert any("validator の検査契約が不足" in finding for finding in findings)


def test_validator_symlink_outside_plugin_is_rejected(MOD, tmp_path):
    path, _ = _canonical_plugin(tmp_path)
    validator = path.parents[2] / "scripts/validate-inline-goal-seek-anchor.py"
    outside = tmp_path / "foreign-validator.py"
    outside.write_text(validator.read_text())
    validator.unlink()
    validator.symlink_to(outside)
    findings, _ = MOD.lint_file(path)
    assert any("validator が不在・root 外" in finding for finding in findings)


def test_bare_filename_mention_in_wiring_is_not_a_declaration(MOD, tmp_path):
    path, _ = _canonical_plugin(tmp_path)
    path.write_text(path.read_text().replace(
        "が正本。\n", "が正本。`goal-seek-anchor-contract.md` は別の plugin の話。\n"))
    assert MOD.lint_file(path) == ([], [])


def test_lint_file_non_utf8_is_read_error_finding(MOD, tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_bytes(b"---\nprefix: run\n---\n\xff\xfe\n")
    findings, _ = MOD.lint_file(p)
    assert findings and "read error" in findings[0]


@pytest.mark.parametrize("kind", ["non_utf8", "directory", "missing"])
def test_subprocess_unreadable_input_exits_2_without_traceback(tmp_path, kind):
    p = tmp_path / "SKILL.md"
    if kind == "non_utf8":
        p.write_bytes(b"---\nprefix: run\n---\n\xff\xfe\n")
    elif kind == "directory":
        p.mkdir()
    proc = _run([str(p)])
    assert proc.returncode == 2
    assert "入力を読めない" in proc.stderr
    assert "Traceback" not in proc.stderr


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_subprocess_help_exits_0(flag):
    proc = _run([flag])
    assert proc.returncode == 0
    assert "usage:" in proc.stdout
