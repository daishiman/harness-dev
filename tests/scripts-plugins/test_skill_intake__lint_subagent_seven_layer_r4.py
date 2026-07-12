"""lint_subagent_seven_layer.py の 7-layer 準拠 lint を独立に網羅する (scripts4 系列)。

対象 script:
  plugins/skill-intake/scripts/lint_subagent_seven_layer.py

lint_file の各ルール (SE-FM-required / SE-L1-L7-ordered / SE-L5-rubric-min5 /
SE-L5-goalseek / SE-meta-r-id / SE-L2-io-schema / SE-no-todo[TODO/placeholder]) と
main の verdict 決定・findings JSON 構造・exit code 契約をゼロから被覆する。
Layer 5 は l5-contract v2.0.0 (宣言型): 完了チェックリストは本文末尾 `## Self-Evaluation`、
{{var}} は `## Prompt Templates` 節内のみ許容 (フェンス内の見出し風行は節境界と見なさない)。

純ローカル lint (network=false, write-scope=none) のため stub 不要。
REPO は module load 時に __file__ から固定されるため in-process は monkeypatch.setattr(MOD,'REPO',tmp_path)
で差し替え、lint_file が tmp_path 配下のファイルを relative_to(REPO) できるようにし repo を一切汚染しない。
main は in-process と subprocess(__main__ ガード + exit code) 双方で確認する。
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "lint_subagent_seven_layer.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_subagent_seven_layer_r4_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def MOD():
    return _load()


def _layer_body(i: int, h: str) -> str:
    if i == 4:  # Layer 5 は l5-contract v2.0.0 の宣言型骨格 (5.2/5.3 必須)
        return (
            f"{h}\n\n"
            "### 5.1 context_fork 要否\n- false (理由: 親 context 不要)\n\n"
            "### 5.2 ゴール定義 (固定手順を持たない)\n- 達成ゴール: 出力 schema validate PASS。\n\n"
            "### 5.3 実行方式\n固定手順を持たない。チェックリスト充足まで反復。"
        )
    return f"{h}\n\n本文 for layer {i+1}."


def _good_doc(extra_meta: str = "", io_schema_line: str = "(なし)") -> str:
    """SE-* 全ルールを満たす最小合格 SubAgent 本文を組み立てる。"""
    layers = "\n\n".join(
        _layer_body(i, h) for i, h in enumerate(
            [
                "## Layer 1: 基本定義層",
                "## Layer 2: ドメイン層",
                "## Layer 3: インフラ層",
                "## Layer 4: 共通ポリシー層",
                "## Layer 5: エージェント層",
                "## Layer 6: オーケストレーション層",
                "## Layer 7: UI / 提示層",
            ]
        )
    )
    rubric = (
        "\n\n## Self-Evaluation\n\n"
        "- [ ] item 1\n- [ ] item 2\n- [ ] item 3\n- [ ] item 4\n- [ ] item 5\n"
    )
    meta = (
        "## メタ\n\n"
        "| key | value |\n|---|---|\n"
        "| responsibility_id | R2-assumption-challenge |\n"
        f"| input_schema | {io_schema_line} |\n"
        f"{extra_meta}"
    )
    return (
        "---\n"
        "name: skill-intake-x\n"
        "description: desc\n"
        "tools: Read, Write\n"
        "model: sonnet\n"
        "---\n\n"
        f"{meta}\n\n"
        f"{layers}"
        f"{rubric}\n"
    )


def _write(d: Path, name: str, content: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# lint_file — 合格パス
# ---------------------------------------------------------------------------
def test_lint_file_clean_passes(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    p = _write(tmp_path, "skill-intake-x.md", _good_doc())
    assert MOD.lint_file(p) == []


# ---------------------------------------------------------------------------
# lint_file — SE-FM-required
# ---------------------------------------------------------------------------
def test_lint_file_missing_frontmatter(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc().replace("tools: Read, Write\n", "")  # tools 行を削除し FM 正規表現を壊す
    p = _write(tmp_path, "skill-intake-x.md", doc)
    rules = {i["rule_id"] for i in MOD.lint_file(p)}
    assert "SE-FM-required" in rules


# ---------------------------------------------------------------------------
# lint_file — SE-L1-L7-ordered
# ---------------------------------------------------------------------------
def test_lint_file_missing_layer(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc().replace("## Layer 4: 共通ポリシー層", "## なにか別の見出し")
    p = _write(tmp_path, "skill-intake-x.md", doc)
    item = next(i for i in MOD.lint_file(p) if i["rule_id"] == "SE-L1-L7-ordered")
    assert "Layer 4" in item["message"]


def test_lint_file_layers_out_of_order(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    # Layer 7 を Layer 1 より前に置いて順序違反を起こす (全見出しは存在するが順序が崩れる)
    doc = _good_doc()
    seven = "## Layer 7: UI / 提示層\n\n本文 for layer 7."
    doc = doc.replace(seven, "")  # 末尾の Layer7 を除去
    doc = doc.replace(
        "## Layer 1: 基本定義層",
        "## Layer 7: UI / 提示層\n\n早すぎる7.\n\n## Layer 1: 基本定義層",
        1,
    )
    p = _write(tmp_path, "skill-intake-x.md", doc)
    rules = {i["rule_id"] for i in MOD.lint_file(p)}
    assert "SE-L1-L7-ordered" in rules


# ---------------------------------------------------------------------------
# lint_file — SE-L5-rubric-min5
# ---------------------------------------------------------------------------
def test_lint_file_rubric_section_absent(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc().replace("## Self-Evaluation", "## 別物")
    p = _write(tmp_path, "skill-intake-x.md", doc)
    item = next(i for i in MOD.lint_file(p) if i["rule_id"] == "SE-L5-rubric-min5")
    assert "欠落" in item["message"]


def test_lint_file_rubric_too_few_items(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    # checklist を 3 件に減らす (min5 未満)
    full = (
        "## Self-Evaluation\n\n"
        "- [ ] item 1\n- [ ] item 2\n- [ ] item 3\n- [ ] item 4\n- [ ] item 5\n"
    )
    few = "## Self-Evaluation\n\n- [ ] a\n- [ ] b\n- [ ] c\n"
    doc = _good_doc().replace(full, few)
    p = _write(tmp_path, "skill-intake-x.md", doc)
    item = next(i for i in MOD.lint_file(p) if i["rule_id"] == "SE-L5-rubric-min5")
    assert "3/5" in item["message"]


def test_lint_file_rubric_section_followed_by_next_heading(MOD, tmp_path, monkeypatch):
    # rubric セクションの後ろに "\n##" がある場合の body スライス分岐 (nxt > 0) を踏む
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc()
    # rubric の後ろに追加見出しを足す
    doc = doc + "\n## 付録\n- [ ] noise\n"
    p = _write(tmp_path, "skill-intake-x.md", doc)
    # rubric 本体は 5 件のままなので min5 違反は出ない
    rules = {i["rule_id"] for i in MOD.lint_file(p)}
    assert "SE-L5-rubric-min5" not in rules


# ---------------------------------------------------------------------------
# lint_file — SE-L5-goalseek (l5-contract v2.0.0)
# ---------------------------------------------------------------------------
def test_lint_file_goalseek_missing_goal_heading(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc().replace("### 5.2 ゴール定義 (固定手順を持たない)", "### 5.2 別物")
    p = _write(tmp_path, "skill-intake-x.md", doc)
    items = [i for i in MOD.lint_file(p) if i["rule_id"] == "SE-L5-goalseek"]
    assert any("ゴール定義" in i["message"] for i in items)


def test_lint_file_goalseek_missing_exec_heading(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc().replace("### 5.3 実行方式", "### 5.3 別物")
    p = _write(tmp_path, "skill-intake-x.md", doc)
    items = [i for i in MOD.lint_file(p) if i["rule_id"] == "SE-L5-goalseek"]
    assert any("実行方式" in i["message"] for i in items)


def test_lint_file_goalseek_fixed_steps_flagged(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc().replace(
        "### 5.3 実行方式\n固定手順を持たない。チェックリスト充足まで反復。",
        "### 5.3 実行方式\n固定手順を持たない。チェックリスト充足まで反復。\n\n"
        "### 5.4 推論手順 (再現可能, 番号付き)\n1. step",
    )
    p = _write(tmp_path, "skill-intake-x.md", doc)
    items = [i for i in MOD.lint_file(p) if i["rule_id"] == "SE-L5-goalseek"]
    assert any("固定手順" in i["message"] for i in items)
    # 固定手順見出しは行番号付き location を持つ
    assert any(":" in i.get("location", "") for i in items)


# ---------------------------------------------------------------------------
# lint_file — SE-meta-r-id
# ---------------------------------------------------------------------------
def test_lint_file_missing_responsibility_id(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc().replace(
        "| responsibility_id | R2-assumption-challenge |",
        "| responsibility_id | invalid-form |",
    )
    p = _write(tmp_path, "skill-intake-x.md", doc)
    rules = {i["rule_id"] for i in MOD.lint_file(p)}
    assert "SE-meta-r-id" in rules


# ---------------------------------------------------------------------------
# lint_file — SE-L2-io-schema
# ---------------------------------------------------------------------------
def test_lint_file_schema_ref_missing_file(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc(io_schema_line="plugins/skill-intake/schemas/ghost.schema.json")
    p = _write(tmp_path, "skill-intake-x.md", doc)
    item = next(i for i in MOD.lint_file(p) if i["rule_id"] == "SE-L2-io-schema")
    assert "ghost.schema.json" in item["message"]


def test_lint_file_schema_ref_existing_file_ok(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    # 実在する schema を tmp REPO 配下に作れば SE-L2-io-schema は出ない
    schema_rel = "plugins/skill-intake/schemas/real.schema.json"
    sp = tmp_path / schema_rel
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text("{}", encoding="utf-8")
    doc = _good_doc(io_schema_line=schema_rel)
    p = _write(tmp_path, "skill-intake-x.md", doc)
    rules = {i["rule_id"] for i in MOD.lint_file(p)}
    assert "SE-L2-io-schema" not in rules


def test_lint_file_schema_ref_unmaintained_marker_skipped(MOD, tmp_path, monkeypatch):
    # "未整備" を含む ref は存在チェックを免除される
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc(io_schema_line="path/未整備.schema.json")
    p = _write(tmp_path, "skill-intake-x.md", doc)
    rules = {i["rule_id"] for i in MOD.lint_file(p)}
    assert "SE-L2-io-schema" not in rules


# ---------------------------------------------------------------------------
# lint_file — SE-no-todo (TODO / placeholder)
# ---------------------------------------------------------------------------
def test_lint_file_bad_todo_flagged(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc() + "\nTODO: あとでやる\n"
    p = _write(tmp_path, "skill-intake-x.md", doc)
    todos = [i for i in MOD.lint_file(p) if i["rule_id"] == "SE-no-todo"]
    assert any("TODO" in i["message"] for i in todos)
    # location に行番号が付く
    assert any(":" in i["location"] for i in todos)


def test_lint_file_todo_human_allowed(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc() + "\nTODO(human): 人間判断待ち\n"
    p = _write(tmp_path, "skill-intake-x.md", doc)
    rules = {i["rule_id"] for i in MOD.lint_file(p)}
    assert "SE-no-todo" not in rules


def test_lint_file_placeholder_flagged(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc() + "\n出力例: {{unexpanded}}\n"
    p = _write(tmp_path, "skill-intake-x.md", doc)
    items = [i for i in MOD.lint_file(p) if i["rule_id"] == "SE-no-todo"]
    assert any("{{unexpanded}}" in i["message"] for i in items)


def test_lint_file_placeholder_in_prompt_templates_allowed(MOD, tmp_path, monkeypatch):
    # Prompt Templates 節内の {{var}} は置換変数として許容。フェンス内の見出し風行
    # (## ...) を節境界と誤認せず、フェンス内 {{var}} も許容されることを併せて確認。
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc() + (
        "\n## Prompt Templates\n\n"
        "> 「{{user_input}} ですか?」\n\n"
        "```markdown\n## 見出し風\n{{fenced_var}}\n```\n\n"
        "## 付録\n本文のみ\n"
    )
    p = _write(tmp_path, "skill-intake-x.md", doc)
    rules = {i["rule_id"] for i in MOD.lint_file(p)}
    assert "SE-no-todo" not in rules


def test_lint_file_placeholder_after_prompt_templates_flagged(MOD, tmp_path, monkeypatch):
    # Prompt Templates 節が終わった後 (次の ## 節) の {{var}} は許容されない
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    doc = _good_doc() + (
        "\n## Prompt Templates\n\n> 「{{ok_var}}」\n\n"
        "## Handoff\n{{leaked_var}}\n"
    )
    p = _write(tmp_path, "skill-intake-x.md", doc)
    items = [i for i in MOD.lint_file(p) if i["rule_id"] == "SE-no-todo"]
    assert any("{{leaked_var}}" in i["message"] for i in items)
    assert not any("{{ok_var}}" in i["message"] for i in items)


# ---------------------------------------------------------------------------
# emit_item
# ---------------------------------------------------------------------------
def test_emit_item_optional_fields(MOD):
    bare = MOD.emit_item("R", "error", "msg")
    assert bare == {"rule_id": "R", "severity": "error", "message": "msg"}
    full = MOD.emit_item("R", "warn", "m", location="f:1", suggestion="fix it")
    assert full["location"] == "f:1"
    assert full["suggestion"] == "fix it"


# ---------------------------------------------------------------------------
# main (in-process)
# ---------------------------------------------------------------------------
def test_main_inproc_pass_clean(MOD, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    p = _write(tmp_path, "skill-intake-x.md", _good_doc())
    rc = MOD.main(["prog", str(p)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "pass"
    assert out["summary"]["errors"] == 0
    assert out["summary"]["files_checked"] == 1
    assert out["produced_by"] == "lint_subagent_seven_layer.py"


def test_main_inproc_fail_returns_1(MOD, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    p = _write(tmp_path, "skill-intake-x.md", "no frontmatter and no layers\n")
    rc = MOD.main(["prog", str(p)])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "fail"
    assert out["summary"]["errors"] > 0
    # per_file_counts にカウントが反映される
    rel = str(p.relative_to(tmp_path))
    assert out["summary"]["per_file_counts"][rel] > 0


def test_main_inproc_default_glob(MOD, tmp_path, monkeypatch, capsys):
    # 引数省略 → 既定 glob (plugins/skill-intake/agents/skill-intake-*.md)
    monkeypatch.setattr(MOD, "REPO", tmp_path)
    agents = tmp_path / "plugins" / "skill-intake" / "agents"
    _write(agents, "skill-intake-a.md", _good_doc())
    rc = MOD.main(["prog"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["summary"]["files_checked"] == 1


# ---------------------------------------------------------------------------
# main (subprocess) — __main__ ガード + exit code 契約
# ---------------------------------------------------------------------------
def test_main_subprocess_real_agents_pass(tmp_path):
    # 実 agents (リポジトリ同梱) を default glob で走らせ、7-layer 準拠が保たれていることを
    # fail-closed で強制する (agents / lint / template のドリフトを CI で検出するゲート)。
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=dict(os.environ),
    )
    payload = json.loads(r.stdout)
    assert payload["produced_by"] == "lint_subagent_seven_layer.py"
    assert r.returncode == 0, r.stdout
    assert payload["verdict"] == "pass"
    assert payload["summary"]["errors"] == 0


def test_main_subprocess_accepts_repo_relative_path():
    target = "plugins/skill-intake/agents/skill-intake-assumption-challenger.md"
    r = subprocess.run(
        [sys.executable, str(SCRIPT), target],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=dict(os.environ),
    )
    payload = json.loads(r.stdout)
    assert r.returncode == 0, r.stderr
    assert payload["verdict"] == "pass"
    assert payload["summary"]["per_file_counts"][target] == 0
