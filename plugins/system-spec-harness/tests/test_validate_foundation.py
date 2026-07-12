# /// script
# name: test-validate-foundation
# version: 0.1.0
# purpose: C9 (上位概念 anchor) の anti-drift ゲート validate-coverage-matrix.py --require-foundation を、正例=OK・負例 (foundation 不在/U1-U5 空/goal 不備/serves_goals 無しの drift 候補/dangling serves_goals) で網羅検証する pytest。既存 C12 (--matrix/--require-complete) の後方互換 (foundation 検証は opt-in) も確認する。
# inputs:
#   - argv: pytest 経由 (直接 argv は取らない)
# outputs:
#   - stdout: pytest 結果
#   - exit: 0=all pass / 1=failure
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""C9 上位概念 anchor の validate_foundation() / --require-foundation を検証する。

正例=OK / 負例=各違反 / 後方互換 (opt-in) を網羅する。ハイフン名モジュールを importlib で
in-process ロードし validate_foundation()/main() を直接呼ぶ。既存 test_validate_scripts.py の
C12 検証は一切変更しない (本ファイルは foundation 検証の新規追加のみ)。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

PLATFORMS = ["web", "mobile", "tablet", "desktop-windows", "desktop-linux", "desktop-macos"]
CATEGORIES = ["database", "auth", "ui-ux", "security", "infrastructure", "backend", "frontend", "maintenance-ops"]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


c12 = _load("vcm_f", "validate-coverage-matrix.py")


def write(tmp_path: Path, name: str, obj: dict) -> str:
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


def _valid_foundation() -> dict:
    return {
        "essential_purpose": "請求と監査を単一 Web システムへ統合し二重管理をなくす",
        "background": "表計算と個別ツールが乱立し請求漏れが慢性化している",
        "goals": [
            {"id": "G1", "text": "データを単一の信頼できる情報源へ統合する"},
            {"id": "G2", "text": "主要動線を Web だけで完結できるようにする"},
        ],
        "objectives": [{"id": "O1", "text": "請求漏れ検知の自動化", "measure": "月次0件"}],
        "success_criteria": ["請求漏れ0件が3ヶ月継続"],
        "stakeholders": ["経理"],
        "scope": {"in": ["請求"], "out": ["給与"]},
        "constraints": ["社内 k8s"],
        "concrete_intents": [{"id": "I1", "text": "日次バックアップ", "serves": ["G1"]}],
        "confirmed": True,
        "approval_ref": "appr-foundation",
    }


def _valid_state() -> dict:
    """全確定セルが serves_goals で実在 goal へトレースされ、上位概念 U1-U5 が非空の状態。"""
    return {
        "matrix": {
            "database": {
                "web": {"state": "確定", "qa_ref": "q", "serves_goals": ["G1"]},
                "mobile": {"state": "対象外", "reason": "非対応"},
            },
            "frontend": {
                "web": {"state": "確定", "qa_ref": "q", "serves_goals": ["G2", "G1"]},
            },
        },
        "approval_log": [{"id": "appr-foundation", "note": "上位概念をユーザーと合意した"}],
        "requirements_foundation": _valid_foundation(),
        "decisions": [],
    }


# ── validate_foundation() 正例 ─────────────────────────────────────────────
def test_foundation_valid():
    assert c12.validate_foundation(_valid_state()) == []


# ── (a) requirements_foundation 不在 / U1-U5 空 ────────────────────────────
def test_foundation_missing_object():
    d = _valid_state()
    del d["requirements_foundation"]
    assert any("存在しない" in f for f in c12.validate_foundation(d))


def test_foundation_empty_essential_purpose():
    d = _valid_state()
    d["requirements_foundation"]["essential_purpose"] = "   "
    assert any("essential_purpose" in f for f in c12.validate_foundation(d))


def test_foundation_empty_background():
    d = _valid_state()
    d["requirements_foundation"]["background"] = ""
    assert any("background" in f for f in c12.validate_foundation(d))


def test_foundation_empty_goals():
    d = _valid_state()
    d["requirements_foundation"]["goals"] = []
    # goals 空 → U3 空 の finding (かつ確定セルは dangling になる)
    assert any("goals" in f for f in c12.validate_foundation(d))


def test_foundation_empty_objectives():
    d = _valid_state()
    d["requirements_foundation"]["objectives"] = []
    assert any("objectives" in f for f in c12.validate_foundation(d))


def test_foundation_empty_success_criteria():
    d = _valid_state()
    d["requirements_foundation"]["success_criteria"] = []
    assert any("success_criteria" in f for f in c12.validate_foundation(d))


def test_foundation_requires_u6_u9_or_explicit_na():
    for field, empty in (
        ("stakeholders", []),
        ("scope", {"in": [], "out": []}),
        ("constraints", []),
        ("concrete_intents", []),
    ):
        d = _valid_state()
        d["requirements_foundation"][field] = empty
        assert any(field in f for f in c12.validate_foundation(d))


def test_foundation_explicit_na_with_reason_is_valid():
    d = _valid_state()
    d["requirements_foundation"]["constraints"] = {
        "status": "not_applicable", "reason": "制約なしを確認済み"
    }
    assert c12.validate_foundation(d) == []


def test_foundation_requires_confirmed_true():
    d = _valid_state()
    d["requirements_foundation"]["confirmed"] = False
    assert any("confirmed=true" in f for f in c12.validate_foundation(d))


# F1: confirmed はユーザー合意の approval_ref (approval_log 実在) を必須にする (writer と同一契約)
def test_foundation_confirmed_requires_approval_ref():
    d = _valid_state()
    del d["requirements_foundation"]["approval_ref"]
    assert any("approval_ref" in f and "空" in f for f in c12.validate_foundation(d))


def test_foundation_dangling_approval_ref():
    d = _valid_state()
    d["requirements_foundation"]["approval_ref"] = "appr-nonexistent"
    assert any("approval_log に不在" in f for f in c12.validate_foundation(d))


# F2: U1-U3 (essential_purpose/background/goals) は N/A 不可 (値必須)。明示 N/A でも finding が立つ
def test_foundation_u1_u3_reject_explicit_na():
    for field in ("essential_purpose", "background", "goals"):
        d = _valid_state()
        d["requirements_foundation"][field] = {
            "status": "not_applicable", "reason": "N/A 不可のはず"
        }
        assert any(field in f for f in c12.validate_foundation(d))


def test_foundation_goal_missing_id():
    d = _valid_state()
    d["requirements_foundation"]["goals"] = [{"text": "id 無し"}]
    assert any("id 欠落" in f for f in c12.validate_foundation(d))


def test_foundation_goal_empty_text():
    d = _valid_state()
    d["requirements_foundation"]["goals"] = [{"id": "G1", "text": "  "}]
    d["matrix"]["frontend"]["web"]["serves_goals"] = ["G1"]  # G2 を消したので付け替え
    assert any("text が空" in f for f in c12.validate_foundation(d))


# ── (b)(c) serves_goals トレース (drift 候補 / dangling) ────────────────────
def test_foundation_confirmed_cell_without_serves_is_drift():
    d = _valid_state()
    del d["matrix"]["database"]["web"]["serves_goals"]  # 確定だがトレース無し
    findings = c12.validate_foundation(d)
    assert any("drift 候補" in f and "database.web" in f for f in findings)


def test_foundation_dangling_serves_goals():
    d = _valid_state()
    d["matrix"]["database"]["web"]["serves_goals"] = ["G9"]  # 実在しない goal
    assert any("dangling" in f and "G9" in f for f in c12.validate_foundation(d))


def test_foundation_excluded_cell_needs_no_serves():
    # 対象外セルは serves_goals 不要 (drift 対象は『確定』セルのみ)
    d = _valid_state()
    d["matrix"]["database"]["mobile"] = {"state": "対象外", "reason": "x"}
    assert c12.validate_foundation(d) == []


# ── main() CLI: --require-foundation ───────────────────────────────────────
def _full_valid_matrix() -> dict:
    """C12 の完全な合格マトリクス (8 カテゴリ×6 platform 全確定) + 上位概念。"""
    matrix = {
        c: {p: {"state": "確定", "qa_ref": "qa-001", "serves_goals": ["G1"]} for p in PLATFORMS}
        for c in CATEGORIES
    }
    return {
        "categories": [{"id": c, "label": c} for c in CATEGORIES],
        "platforms": PLATFORMS,
        "matrix": matrix,
        "qa_log": [{"id": "qa-001", "question": "q", "answer": "a"}],
        "approval_log": [{"id": "appr-001"}, {"id": "appr-foundation"}],
        "requirements_foundation": _valid_foundation(),
        "decisions": [],
    }


def _valid_decision() -> dict:
    return {
        "id": "D1", "question": "認証基盤をどれにするか",
        "status": "recommended_pending_confirmation",
        "options": [
            {
                "id": "managed", "label": "managed無料枠",
                "cost_model": {
                    "category": "free", "amount": 0, "currency": "JPY",
                    "billing_period": "month", "tco": "無料枠内は月額0円、超過後は従量課金",
                },
                "free_tier_limits": "1万MAU", "goal_fit": "G1に適合", "pros": ["運用容易"],
                "security_fit": "managed更新とMFAで要件を満たす",
                "cons": ["上限後課金"], "risks": ["価格改定"], "lock_in": "中",
                "ops_burden": "低", "evidence_refs": ["https://vendor.example/pricing"],
            },
            {
                "id": "oss", "label": "OSS",
                "cost_model": {
                    "category": "low-cost", "amount": 1000, "currency": "JPY",
                    "billing_period": "month", "tco": "月額基盤費に保守工数を加算",
                },
                "free_tier_limits": "制限なし", "goal_fit": "G1に適合", "pros": ["自由度"],
                "security_fit": "内製で脆弱性更新を期限内に適用する場合に適合",
                "cons": ["保守必要"], "risks": ["更新遅延"], "lock_in": "低",
                "ops_burden": "高", "evidence_refs": ["https://project.example/docs"],
            },
        ],
        "recommendation": {
            "option_id": "managed", "rationale": "総運用費が低い", "caveats": ["上限監視"],
            "confidence": "medium", "latest_checked_at": "2026-07-11T00:00:00Z",
            "comparison_basis": {
                "goal_fit": "短期導入目標に最も適合", "tco": "無料枠内の総費用が最小",
                "security": "managed更新とMFAを利用可能", "operations": "保守負荷が低い",
                "lock_in": "中程度の移行費を許容できる",
            },
        },
        "serves_goals": ["G1"], "user_decision": None,
    }


def test_decision_pending_recommendation_is_valid_and_not_auto_confirmed():
    d = _valid_state()
    d["decisions"] = [_valid_decision()]
    assert c12.validate_foundation(d) == []


def test_decision_confirmed_requires_user_confirmation():
    d = _valid_state()
    decision = _valid_decision()
    decision["status"] = "confirmed"
    d["decisions"] = [decision]
    assert any("user_decision" in f for f in c12.validate_foundation(d))


def test_decision_requires_two_options_and_non_dangling_goal():
    d = _valid_state()
    decision = _valid_decision()
    decision["options"] = decision["options"][:1]
    decision["serves_goals"] = ["G9"]
    d["decisions"] = [decision]
    findings = c12.validate_foundation(d)
    assert any("2-3件" in f for f in findings)
    assert any("dangling" in f for f in findings)


def test_decision_rejects_all_paid_options():
    d = _valid_state()
    decision = _valid_decision()
    for option in decision["options"]:
        option["cost_model"]["category"] = "paid"
        option["cost_model"]["amount"] = 5000
    d["decisions"] = [decision]
    assert any("free または low-cost" in f for f in c12.validate_foundation(d))


def test_decision_rejects_invalid_evidence_and_latest_timestamp():
    d = _valid_state()
    decision = _valid_decision()
    decision["options"][0]["evidence_refs"] = ["not-a-url"]
    decision["recommendation"]["latest_checked_at"] = "not-a-date"
    d["decisions"] = [decision]
    findings = c12.validate_foundation(d)
    assert any("https URL" in f for f in findings)
    assert any("latest_checked_at は RFC3339" in f for f in findings)


def test_decision_rejects_missing_comparison_axis_and_security_fit():
    d = _valid_state()
    decision = _valid_decision()
    decision["options"][0].pop("security_fit")
    decision["recommendation"]["comparison_basis"].pop("operations")
    d["decisions"] = [decision]
    findings = c12.validate_foundation(d)
    assert any("option.security_fit" in f for f in findings)
    assert any("comparison_basis.operations" in f for f in findings)


def test_decision_confirmed_rejects_non_rfc3339_confirmation_time():
    d = _valid_state()
    decision = _valid_decision()
    decision["status"] = "confirmed"
    decision["user_decision"] = {"option_id": "managed", "confirmed_at": "2026-07-11"}
    d["decisions"] = [decision]
    assert any("confirmed_at は RFC3339" in f for f in c12.validate_foundation(d))


def test_main_require_foundation_ok(tmp_path, capsys):
    m = write(tmp_path, "m.json", _full_valid_matrix())
    assert c12.main(["--matrix", m, "--require-complete", "--require-foundation"]) == 0
    assert "foundation" in capsys.readouterr().out


def test_main_require_foundation_drift_fails(tmp_path):
    d = _full_valid_matrix()
    del d["matrix"]["database"]["web"]["serves_goals"]  # drift 候補
    m = write(tmp_path, "m.json", d)
    assert c12.main(["--matrix", m, "--require-foundation"]) == 1


def test_main_require_foundation_missing_foundation_fails(tmp_path):
    d = _full_valid_matrix()
    del d["requirements_foundation"]
    m = write(tmp_path, "m.json", d)
    assert c12.main(["--matrix", m, "--require-foundation"]) == 1


# ── 後方互換: foundation 検証は opt-in (既定は C12 挙動不変) ─────────────────
def test_backward_compat_default_ignores_foundation(tmp_path, capsys):
    # requirements_foundation 不在でも、--require-foundation 無しなら従来どおり OK。
    d = _full_valid_matrix()
    del d["requirements_foundation"]
    for row in d["matrix"].values():
        for cell in row.values():
            cell.pop("serves_goals", None)  # serves_goals も無い純粋な C12 形状
    m = write(tmp_path, "m.json", d)
    assert c12.main(["--matrix", m, "--require-complete"]) == 0
    assert "foundation" not in capsys.readouterr().out


def test_validate_unchanged_ignores_serves_goals():
    # validate() (C12 本体) は serves_goals / requirements_foundation を無視し従来判定のまま。
    d = _full_valid_matrix()
    assert c12.validate(d, require_complete=True) == []
