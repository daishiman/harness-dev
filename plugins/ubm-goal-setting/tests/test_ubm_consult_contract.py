"""run-ubm-consult (C09) の契約を決定論で検証する。

コーチング型相談 orchestrator の骨格が仕様どおり配線されているかを、実行時対話に
依存しない範囲で機械確認する:
  - SKILL.md frontmatter の feedback_contract(IN1 inner/test・OUT1 outer/test)存在
  - goal_seek(engine:inline / fork:inline / max_loops:5)と combinators
  - responsibility_refs が prompts R1-R4 を列挙し実在
  - スタンス不変条件(非処方/引き出し/ユーザー言語化/ゴール指向/責務境界)の文言が SKILL.md に存在
  - prompts R1-R4 が 7 層アンカー(Layer 1..7 + 出力指示)を持つ
  - prompt の入出力契約表が workflow-manifest input と parity(痩せ drift の再発検出)
  - workflow-manifest の phase(r1-r4)と resourceIds prompt の整合・実在
  - references(consult-frames.md / session-record-format.md / resource-map.yaml)実在
  - OUT1/IN1 の検出ロジック(正本= scripts/validate-consult-session.py)を正例/負例 fixture で検証
実 knowledge/ や vault には一切触れない。
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PLUGIN_ROOT / "skills/run-ubm-consult"
SKILL_MD = SKILL_DIR / "SKILL.md"
MANIFEST = SKILL_DIR / "workflow-manifest.json"
PROMPTS = ["R1-intake-issue", "R2-elicit", "R3-frame-consult", "R4-cocreate-converge"]
REFERENCES = ["consult-frames.md", "session-record-format.md", "resource-map.yaml"]

# IN1/OUT1 の検出ロジックは validator が正本 (二重定義 drift 防止のため import 一本化)
_VALIDATOR = PLUGIN_ROOT / "scripts/validate-consult-session.py"
_SPEC = importlib.util.spec_from_file_location("validate_consult_session_for_contract", _VALIDATOR)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_MOD)
detect_transcript_elements = _MOD.detect_transcript_elements
detect_prescription_stance = _MOD.detect_prescription_stance


def _frontmatter(text: str) -> str:
    assert text.startswith("---"), "frontmatter が --- で始まっていない"
    parts = text.split("---", 2)
    assert len(parts) >= 3, "frontmatter ブロックが閉じていない"
    return parts[1]


def _body(text: str) -> str:
    return text.split("---", 2)[2]


# --------------------------------------------------------------------------- #
# 骨格の実在
# --------------------------------------------------------------------------- #
def test_skill_and_supports_exist():
    assert SKILL_MD.is_file(), f"SKILL.md 不在: {SKILL_MD}"
    assert MANIFEST.is_file(), f"workflow-manifest.json 不在: {MANIFEST}"
    for slug in PROMPTS:
        p = SKILL_DIR / "prompts" / f"{slug}.md"
        assert p.is_file(), f"prompt 不在: {p}"
    for ref in REFERENCES:
        r = SKILL_DIR / "references" / ref
        assert r.is_file(), f"reference 不在: {r}"


# --------------------------------------------------------------------------- #
# frontmatter: feedback_contract / goal_seek / combinators / refs
# --------------------------------------------------------------------------- #
def test_frontmatter_core_fields():
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    assert re.search(r"^name:\s*run-ubm-consult\s*$", fm, re.M)
    assert re.search(r"^kind:\s*run\s*$", fm, re.M)
    assert re.search(r"^prefix:\s*run\s*$", fm, re.M)
    # run kind は Step 7-4 で disable-model-invocation: true が必須
    assert re.search(r"^disable-model-invocation:\s*true\s*$", fm, re.M)
    assert re.search(r"^effect:\s*local-artifact\s*$", fm, re.M)


def test_frontmatter_goal_seek():
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    assert re.search(r"engine:\s*inline", fm)
    assert re.search(r"fork:\s*inline", fm)
    assert re.search(r"max_loops:\s*5", fm)


def test_frontmatter_combinators():
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    assert "with-goal-seek" in fm
    assert "with-feedback-contract" in fm


def test_feedback_contract_in1_out1():
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    assert "feedback_contract:" in fm
    # IN1 = inner / OUT1 = outer、双方 verify_by: test
    assert re.search(r"id:\s*IN1", fm), "IN1 が feedback_contract に無い"
    assert re.search(r"id:\s*OUT1", fm), "OUT1 が feedback_contract に無い"
    # IN1 ブロックに inner、OUT1 ブロックに outer が並ぶ
    m_in = re.search(r"id:\s*IN1.*?verify_by:\s*(\w+)", fm, re.S)
    m_out = re.search(r"id:\s*OUT1.*?verify_by:\s*(\w+)", fm, re.S)
    assert m_in and m_in.group(1) == "test"
    assert m_out and m_out.group(1) == "test"
    assert "loop_scope: inner" in fm
    assert "loop_scope: outer" in fm


def test_responsibility_refs_list_all_prompts():
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    for slug in PROMPTS:
        assert f"prompts/{slug}.md" in fm, f"responsibility_refs に {slug} 未列挙"


def test_reference_and_script_refs_resolve():
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    # reference_refs はローカル解決、script_refs は plugin scripts へ解決
    for ref in REFERENCES:
        assert f"references/{ref}" in fm
        assert (SKILL_DIR / "references" / ref).is_file()
    for script in ("consult-harness-artifact-graph.py", "validate-consult-session.py"):
        assert f"../../scripts/{script}" in fm
        assert (PLUGIN_ROOT / "scripts" / script).is_file(), f"script 不在: {script}"


def test_adaptive_collaboration_and_safety_contract_present():
    body = _body(SKILL_MD.read_text(encoding="utf-8"))
    for marker in ("question-led", "framework-led", "hypothesis-example", "reflect-only", "安全分岐", "保存は同意制"):
        assert marker in body


# --------------------------------------------------------------------------- #
# スタンス不変条件の文言が SKILL.md 本文に存在
# --------------------------------------------------------------------------- #
STANCE_MARKERS = [
    "具体解の押し付けゼロ",          # (1) 非処方
    "引き出し質問",                   # (2) 各ターン引き出し
    "ユーザーの発話",                 # (3) 解決策の言語化はユーザー主導
    "現状→ゴール→ギャップ→次の一歩",  # (4) ゴール指向の締め
    "run-ubm-goal-setting へ誘導",    # (5) 責務境界
]


@pytest.mark.parametrize("marker", STANCE_MARKERS)
def test_stance_invariants_present(marker):
    body = _body(SKILL_MD.read_text(encoding="utf-8"))
    assert marker in body, f"スタンス不変条件の文言が SKILL.md に無い: {marker}"


# --------------------------------------------------------------------------- #
# prompts: 7 層アンカー
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("slug", PROMPTS)
def test_prompt_seven_layer_anchors(slug):
    text = (SKILL_DIR / "prompts" / f"{slug}.md").read_text(encoding="utf-8")
    for n in range(1, 8):
        assert re.search(rf"##\s*Layer\s*{n}:", text), f"{slug}: Layer {n} 見出し欠落"
    assert "## 出力指示" in text, f"{slug}: 出力指示 節欠落"
    assert re.search(r"responsibility\s*\|\s*" + re.escape(slug), text), (
        f"{slug}: メタ responsibility が一致しない"
    )


# --------------------------------------------------------------------------- #
# workflow-manifest 整合
# --------------------------------------------------------------------------- #
def test_manifest_phases_align_with_prompts():
    import json

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["workflowId"] == "run-ubm-consult"
    assert data["skill"] == "run-ubm-consult"
    phase_ids = [p["id"] for p in data["phases"]]
    assert phase_ids == ["r1-intake-issue", "r2-elicit", "r3-frame-consult", "r4-cocreate-converge"]
    # 各 phase の prompt resourceId が実在
    for phase in data["phases"]:
        prompt_refs = [r for r in phase["resourceIds"] if r.startswith("prompts/")]
        assert prompt_refs, f"{phase['id']}: prompt resourceId が無い"
        for r in prompt_refs:
            assert (SKILL_DIR / r).is_file(), f"{phase['id']}: resource 不在 {r}"
    # dependsOn が直列 (R1<-R2<-R3<-R4)
    dep = {p["id"]: p["dependsOn"] for p in data["phases"]}
    assert dep["r1-intake-issue"] == []
    assert dep["r2-elicit"] == ["r1-intake-issue"]
    assert dep["r3-frame-consult"] == ["r2-elicit"]
    assert dep["r4-cocreate-converge"] == ["r3-frame-consult"]


def test_manifest_r3_consult_graceful_fallback():
    import json

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    r3 = next(p for p in data["phases"] if p["id"] == "r3-frame-consult")
    consults = r3.get("consults")
    assert consults, "R3 に consults ブロックが無い"
    assert "consult-harness-artifact-graph.py" in consults["script"]
    # グラフ未生成時の graceful fallback が note に明記されている
    assert "フォールバック" in consults["note"] or "fallback" in consults["note"]


# --------------------------------------------------------------------------- #
# prompt 入出力契約表と workflow-manifest input の parity (系統的痩せ drift の再発検出)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "slug,section,field",
    [
        ("R1-intake-issue", "2.4", "consult_type"),
        ("R2-elicit", "2.3", "collaboration_mode"),
        ("R3-frame-consult", "2.3", "collaboration_mode"),
        ("R4-cocreate-converge", "2.3", "persistence_consent"),
    ],
)
def test_prompt_io_tables_carry_manifest_fields(slug, section, field):
    text = (SKILL_DIR / "prompts" / f"{slug}.md").read_text(encoding="utf-8")
    m = re.search(rf"###\s*{re.escape(section)}[^\n]*\n(.*?)(?=\n###|\n## )", text, re.S)
    assert m, f"{slug}: {section} 契約表の節が無い"
    assert re.search(rf"^\|\s*{field}\s*\|", m.group(1), re.M), (
        f"{slug} の {section} 表に {field} が無い (workflow-manifest input との parity 違反)"
    )


# --------------------------------------------------------------------------- #
# OUT1: transcript 4 要素検出 (正本= validator) + fixture 検証
# --------------------------------------------------------------------------- #
def test_out1_detector_positive_fixture():
    # fixture は role 付き turns (validator 一本化に伴い「ユーザー:」前置の平文から移行)
    transcript = [
        {"id": "a1", "role": "assistant", "content": "今回の論点はどこにありそうですか？（引き出し）"},
        {"id": "u1", "role": "user", "content": "新規のお客さんとの最初の接点をどう作るかで迷っています。"},
        {
            "id": "a2",
            "role": "assistant",
            "content": "いくつかの見方（考え方）を並べますね。A: 関係構築ファースト、B: 逆算。あなたの場合はどちらが当てはまりそうですか？",
        },
        {"id": "u2", "role": "user", "content": "Aで、まず既存客に紹介をお願いする、と自分の言葉で決めました。"},
        {
            "id": "a3",
            "role": "assistant",
            "content": "では現状→ゴール→ギャップ→次の一歩で整理します。次の一歩: 今週中に既存客3名へ紹介依頼のメッセージを送る。",
        },
    ]
    result = detect_transcript_elements(transcript)
    assert all(result.values()), f"正例で未検出要素: {result}"


def test_out1_detector_negative_prescriptive():
    # 処方的で引き出しもユーザー言語化も無い transcript は不合格
    transcript = [
        {"id": "a1", "role": "assistant", "content": "あなたは値上げをすべきです。以下を実行してください。"},
        {"id": "a2", "role": "assistant", "content": "1. 価格を20%上げる 2. 広告を出す。以上が正解です。"},
    ]
    result = detect_transcript_elements(transcript)
    assert not all(result.values()), "負例(処方的)が全要素 True になっている"
    assert result["user_verbalized"] is False
    assert result["next_step"] is False


def test_out1_user_verbalized_ignores_assistant_impersonation():
    # assistant 発話内の「ユーザー: ...」文字列は user_verbalized の根拠にならない
    transcript = [
        {"id": "a1", "role": "assistant", "content": "ユーザー: 自分でやると決めました、とのことでした。"},
    ]
    assert detect_transcript_elements(transcript)["user_verbalized"] is False


# --------------------------------------------------------------------------- #
# IN1: 非処方スタンス(具体解押し付けゼロ)検出 (正本= validator) + fixture 検証
# --------------------------------------------------------------------------- #
def in1_pass(response: str) -> bool:
    s = detect_prescription_stance(response)
    return s["frame_presented"] and s["no_prescription"]


def test_in1_non_prescriptive_fixture_passes():
    # OK 例: 具体解を処方せず、考え方(見方)を選択肢で提示し、選択をユーザーに委ねる
    response = (
        "いくつかの見方（考え方）を並べますね。\n"
        "見方A: ゴール指向分解 — 現状とありたい姿の差はどこにありそうですか？\n"
        "見方B: 前提検証 — 「できない」の前提を1つ外すと何が変わりそうですか？\n"
        "どちらが今のあなたに当てはまりそうですか？ 選ぶのはあなたです。\n"
    )
    s = detect_prescription_stance(response)
    assert s["frame_presented"] is True, f"考え方/フレーム未提示: {s}"
    assert s["no_prescription"] is True, f"処方マーカーを誤検出/含有: {s}"
    assert in1_pass(response) is True


def test_in1_prescriptive_fixture_fails():
    # NG 例: 単一解を押し付ける処方的応答は IN1 不合格
    response = (
        "あなたは値上げをすべきです。以下を実行してください。\n"
        "1. 価格を20%上げる 2. 広告を出す。以上が正解です。\n"
    )
    s = detect_prescription_stance(response)
    assert s["no_prescription"] is False, "処方マーカーを検出できていない"
    assert in1_pass(response) is False, "処方的応答が IN1 合格になっている"


def test_in1_detector_separates_ok_from_ng():
    ok = (
        "こういう見方（考え方）があります。あなたの場合はどう当てはまりますか？\n"
    )
    ng = "あなたは今すぐ撤退すべきです。従ってください。"
    assert in1_pass(ok) is True
    assert in1_pass(ng) is False
