"""run-prompt-creator-7layer の l5-contract v2.0.0 機械ガードの contract / parity / self-scan テスト。

対象 (elegant-review 20260702T065933 findings):
- A2-06 / A4-14: verify-completeness.py の固定手順検出強化
  (「推論手順/思考プロセス/手順/Steps」見出し配下の連番列挙を FAIL、
   5.4 実行方式 / 実行方式.ループ の 6 ステップ宣言は allowlist)
- A3-04: --layers (brief.layers_required サブセット) で宣言層のみ必須・宣言外は N/A skip
- A4-10: parse_known_args 黙殺の廃止 (未知引数は exit 2 で failfast)
- A4-07: 新層構成 (5.2 ゴール定義 / 5.3 完了チェックリスト / 5.4 実行方式) fixture が
  verify-completeness.py と skill-governance-lint/lint-agent-prompt-section.py の
  双方を PASS する parity (注入セクション名 Prompt Templates / Self-Evaluation 不変)
- A2-16 / A4-16: plugin 所有 prompts/*.md への self-scan (dogfooding ゲート)。
  Wave 3.5 で 6 prompts 全件の l5-contract v2.0.0 転換が完了したため、
  全件が強化版 verify-completeness.py / validate-prompt.py を exit 0 で通過する
  full PASS を assert する (Wave 4 委譲注記は解消済み)。

実行 cwd: repo root (Makefile `python3 -m pytest tests/ -q`)。cwd 非依存 (絶対パスのみ)。
network: false, keychain: なし, 実 repo 書換: なし (tmp_path / stdout/stderr のみ)。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEVEN_LAYER_SKILL = ROOT / "plugins" / "prompt-creator" / "skills" / "run-prompt-creator-7layer"
VERIFY = SEVEN_LAYER_SKILL / "scripts" / "verify-completeness.py"
VALIDATE_SHEET = SEVEN_LAYER_SKILL / "scripts" / "validate-sheet.py"
AGENT_LINT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-agent-prompt-section.py"
PROMPTS_GLOB = "plugins/prompt-creator/skills/*/prompts/*.md"


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def _layer_block(n: int, body: str) -> str:
    return f"## Layer {n}: テスト層{n}\n\n{body}\n"


def _seven_layers(layer5_body: str, tail: str = "") -> str:
    """決定論 fixture: 7 層 Markdown プロンプト (Layer 5 のみ差し替え可能)。"""
    parts = ["# Prompt: fixture\n"]
    for n in range(1, 8):
        if n == 5:
            parts.append(f"## Layer 5: エージェント層 (ゴール駆動の実行主体)\n\n{layer5_body}\n")
        else:
            parts.append(_layer_block(n, f"- 要素 {n}"))
    return "\n".join(parts) + tail


NEW_STYLE_L5 = """### 5.1 担当 agent
- fixture-agent

### 5.2 ゴール定義
- 目的: fixture の目的
- 背景: fixture の背景
- 達成ゴール: 成果物が検証済みの状態になっている

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 成果物が schema 検証を通過している
- [ ] 生成物に固定手順が含まれていない

### 5.4 実行方式
- 固定手順を持たない (l5-contract v2.0.0)。現状評価→手順を都度立案→実行→検証→中間成果物アンカー記録→全項目充足まで反復 (6 ステップ・Step 5=Anchor)。"""

OLD_STYLE_L5 = """### 5.1 担当 agent
- fixture-agent

### 5.2 推論手順 (再現可能)
1. 入力を検証する。
2. 雛形を生成する。
3. 本文を充填する。

### 5.3 自己検証 checklist
- [ ] 検証した"""

INJECT_SECTIONS_TAIL = """
## Prompt Templates

### Round 1: fixture

> 「これは fixture の実発話例です」

## Self-Evaluation

| 次元 | 合格条件 |
|---|---|
| 完全性 | fixture が全項目を満たす |
"""


# ── A2-06 / A4-14: 固定手順検出の強化 ──────────────────────────────────────
def test_verify_new_style_l5_passes(tmp_path):
    p = tmp_path / "new.md"
    p.write_text(_seven_layers(NEW_STYLE_L5), encoding="utf-8")
    res = _run(VERIFY, "--input", str(p))
    assert res.returncode == 0, res.stderr
    assert "l5-contract v2.0.0" in res.stdout


def test_verify_old_style_numbered_reasoning_steps_fail(tmp_path):
    # 旧 R1-elicit 型: 「### 5.2 推論手順」見出し配下の連番列挙 → FAIL
    p = tmp_path / "old.md"
    p.write_text(_seven_layers(OLD_STYLE_L5), encoding="utf-8")
    res = _run(VERIFY, "--input", str(p))
    assert res.returncode == 1
    assert "固定手順" in res.stderr
    assert "推論手順" in res.stderr


def test_verify_legacy_thinking_process_detection_kept(tmp_path):
    # legacy 検出 (思考プロセス + ステップN 共起) は維持される
    l5 = (
        "ゴール定義: あり / 完了チェックリスト: あり / 達成ゴール: あり\n\n"
        "### 5.2 思考プロセス\n"
        "ステップ1: 何かする\n"
        "ステップ2: 続ける\n"
    )
    p = tmp_path / "legacy.md"
    p.write_text(_seven_layers(l5), encoding="utf-8")
    res = _run(VERIFY, "--input", str(p))
    assert res.returncode == 1
    assert "思考プロセスのステップ列挙" in res.stderr


def test_verify_goal_seek_loop_declaration_is_allowlisted(tmp_path):
    # 5.4 実行方式 / 実行方式.ループ の 6 ステップ宣言 (連番) は正当パターン
    l5 = """エージェント定義:
  エージェント:
    - 名前: "X"
      ゴール定義:
        目的: |
          fixture
        達成ゴール: |
          成果物が検証済みの状態
      完了チェックリスト:
        - 項目: "schema 検証を通過"
      実行方式:
        ループ:
          - "1. 現状評価: 未充足項目を特定する"
          - "2. 手順生成: 中間成果物を必須入力に手順を立案する"
          - "3. 実行: 手順を実行する"
          - "4. 検証: チェックリストで自己評価する"
          - "5. 中間成果物アンカー: original_goal 等を記録する"
          - "6. 反復: 全項目充足まで 1→5 を反復する"
"""
    p = tmp_path / "loop.yaml"
    p.write_text(_seven_layers(l5), encoding="utf-8")
    res = _run(VERIFY, "--input", str(p))
    assert res.returncode == 0, res.stderr


def test_verify_negation_guard_does_not_flag_prohibition_notes(tmp_path):
    # 「固定手順（ステップ列挙）は持たせない」等の注意書きは検出しない
    l5 = NEW_STYLE_L5 + "\n# 固定手順（ステップ列挙）は持たせない。手順は書かない。\n"
    p = tmp_path / "note.md"
    p.write_text(_seven_layers(l5), encoding="utf-8")
    res = _run(VERIFY, "--input", str(p))
    assert res.returncode == 0, res.stderr


# ── A3-04: --layers サブセット ───────────────────────────────────────────────
def _subset_prompt() -> str:
    return (
        "# Prompt: subset fixture\n\n"
        + _layer_block(1, "- 要素 1")
        + "\n"
        + _layer_block(2, "- 要素 2")
        + "\n"
        + f"## Layer 5: エージェント層\n\n{NEW_STYLE_L5}\n"
    )


def test_verify_full_seven_required_without_layers_option(tmp_path):
    # 互換維持: --layers 未指定はフル 7 層必須 (欠落 Layer は FAIL)
    p = tmp_path / "subset.md"
    p.write_text(_subset_prompt(), encoding="utf-8")
    res = _run(VERIFY, "--input", str(p))
    assert res.returncode == 1
    assert "Layer 3: section missing" in res.stderr


def test_verify_layers_subset_passes_with_na_skip(tmp_path):
    p = tmp_path / "subset.md"
    p.write_text(_subset_prompt(), encoding="utf-8")
    res = _run(VERIFY, "--input", str(p), "--layers", "L1,L2,L5")
    assert res.returncode == 0, res.stderr
    assert "SKIP Layer 3: N/A skip" in res.stdout
    assert "L1,L2,L5" in res.stdout


def test_verify_layers_subset_still_enforces_declared_layers(tmp_path):
    # 宣言層が欠落していれば FAIL (サブセットでもゲートは効く)
    p = tmp_path / "subset.md"
    p.write_text(_subset_prompt(), encoding="utf-8")
    res = _run(VERIFY, "--input", str(p), "--layers", "L1,L4")
    assert res.returncode == 1
    assert "Layer 4: section missing" in res.stderr


def test_verify_layers_invalid_token_exit_2(tmp_path):
    p = tmp_path / "subset.md"
    p.write_text(_subset_prompt(), encoding="utf-8")
    res = _run(VERIFY, "--input", str(p), "--layers", "L9")
    assert res.returncode == 2


def test_verify_layers_subset_still_detects_fixed_procedure(tmp_path):
    # L5 が宣言層でも固定手順検出は有効
    p = tmp_path / "subset-old.md"
    p.write_text(
        "# Prompt: fixture\n\n"
        + _layer_block(1, "- 要素 1")
        + "\n"
        + f"## Layer 5: エージェント層\n\n{OLD_STYLE_L5}\n",
        encoding="utf-8",
    )
    res = _run(VERIFY, "--input", str(p), "--layers", "L1,L5")
    assert res.returncode == 1
    assert "固定手順" in res.stderr


# ── A4-10: 未知引数 failfast ─────────────────────────────────────────────────
def test_verify_unknown_arg_failfast_exit_2(tmp_path):
    p = tmp_path / "new.md"
    p.write_text(_seven_layers(NEW_STYLE_L5), encoding="utf-8")
    res = _run(VERIFY, "--input", str(p), "--bogus", "1")
    assert res.returncode == 2


def test_verify_missing_input_usage_exit_2():
    res = _run(VERIFY)
    assert res.returncode == 2


# ── A4-07: verify-completeness × lint-agent-prompt-section の parity ────────
def test_new_layer_structure_parity_with_agent_prompt_section_lint(tmp_path):
    """新層構成 fixture が両 lint を PASS = 注入セクション名不変の双方向互換を機械保証。"""
    p = tmp_path / "agent-with-7layer.md"
    p.write_text(_seven_layers(NEW_STYLE_L5, tail=INJECT_SECTIONS_TAIL), encoding="utf-8")
    res_verify = _run(VERIFY, "--input", str(p))
    assert res_verify.returncode == 0, res_verify.stderr
    res_lint = _run(AGENT_LINT, str(p))
    assert res_lint.returncode == 0, res_lint.stderr


def test_inject_section_names_are_stable_contract():
    """lint 側の必須見出しが Prompt Templates / Self-Evaluation のまま (A4-03 不変契約)。"""
    text = AGENT_LINT.read_text(encoding="utf-8")
    assert '"## Prompt Templates"' in text
    assert '"## Self-Evaluation"' in text


# ── validate-sheet: goals の手順列挙検出 (docstring と実装の一致) ────────────
def test_validate_sheet_flags_step_enumeration_goal(tmp_path):
    data = {
        "prompt_name": "x",
        "target_user": "u",
        "purpose": "p",
        "background": "b",
        "success_criteria": "s",
        "goals": ["ステップ1: 入力を検証し、ステップ2 で変換する"],
        "challenges": ["c"],
    }
    p = tmp_path / "hearing.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    res = _run(VALIDATE_SHEET, str(p))
    assert res.returncode == 4
    assert "手順列挙の疑い" in res.stdout


def test_validate_sheet_accepts_outcome_state_goal(tmp_path):
    data = {
        "prompt_name": "x",
        "target_user": "u",
        "purpose": "p",
        "background": "b",
        "success_criteria": "s",
        "goals": ["検証済み成果物が出力された状態になっている"],
        "challenges": ["c"],
    }
    p = tmp_path / "hearing.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    res = _run(VALIDATE_SHEET, str(p))
    assert res.returncode == 0, res.stdout


# ── A2-16 / A4-16: plugin 所有 prompts の self-scan (dogfooding ゲート) ──────
def test_self_scan_plugin_prompts_exist_and_have_layer5():
    """plugin 所有 prompts/*.md の存在+構造検査 (full PASS 検査の前提ガード)。"""
    prompts = sorted(ROOT.glob(PROMPTS_GLOB))
    assert len(prompts) >= 6, f"expected >= 6 plugin prompts, found {len(prompts)}: {PROMPTS_GLOB}"
    layer5_re = re.compile(r"#+\s*Layer\s*5\s*[:：]")
    for p in prompts:
        text = p.read_text(encoding="utf-8")
        assert text.strip(), f"{p}: empty prompt"
        assert layer5_re.search(text), f"{p}: Layer 5 section missing"


def test_self_scan_all_plugin_prompts_pass_strengthened_gate():
    """plugin 所有 prompts 全件が強化版 verify-completeness.py を full PASS する (自己適用)。

    Wave 3.5 で全 6 prompts の l5-contract v2.0.0 転換が完了した状態を固定する
    dogfooding ゲート。新規追加 prompt も glob で自動的に検査対象へ入る。
    """
    prompts = sorted(ROOT.glob(PROMPTS_GLOB))
    assert len(prompts) >= 6
    failures = []
    for p in prompts:
        res = _run(VERIFY, "--input", str(p))
        if res.returncode != 0:
            failures.append(f"{p.relative_to(ROOT)}:\n{res.stderr}")
    assert not failures, "verify-completeness FAIL:\n" + "\n".join(failures)


def test_self_scan_all_plugin_prompts_pass_validate_prompt():
    """plugin 所有 prompts 全件が validate-prompt.py --phase prompt を PASS する
    (7 層マーカー / placeholder / TODO 残存の回帰防止)。"""
    validate = SEVEN_LAYER_SKILL / "scripts" / "validate-prompt.py"
    prompts = sorted(ROOT.glob(PROMPTS_GLOB))
    assert len(prompts) >= 6
    failures = []
    for p in prompts:
        res = _run(validate, "--input", str(p), "--phase", "prompt")
        if res.returncode != 0:
            failures.append(f"{p.relative_to(ROOT)}:\n{res.stdout}{res.stderr}")
    assert not failures, "validate-prompt FAIL:\n" + "\n".join(failures)
