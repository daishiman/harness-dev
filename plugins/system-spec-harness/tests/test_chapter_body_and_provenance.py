# /// script
# name: test-chapter-body-and-provenance
# version: 0.1.0
# purpose: 章本文の空洞化 (確定内容/To-Be/上流指針の未生成)・merge の孤児化と節順崩れ・qa_log provenance 欠落・未来時刻の素通り、という 4 系統の欠陥に対する回帰ガード。修正前の実装では全て赤になる。
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
"""章本文の実体化 (C03) と質疑録 provenance / 時刻検証 (C01) の回帰テスト。

背景 — 以下はいずれも決定論ゲート (coverage / source-citation / knowledge-graph) を
exit 0 で素通りしていた欠陥であり、意味層の評価でしか捕まらなかった。本テストは
それらを決定論側へ降ろす。

  1. 章本文の空洞化: `render_state_table` が「本章の『確定内容 (質疑録)』へ併記」、
     `render_design_refs` が「規範となる差分は本章の To-Be / Delta 節で管理する」と
     宣言しているのに、その 2 節を `render_chapter` が生成していなかった。
  2. 上流指針の未到達: doctrine-anchor-registry.json は「C03 が各章生成時に
     category→concern→authority を反映する」と自ら宣言するが、compile は
     resource-map の `.md` しか読まず registry を一度も参照していなかった。
  3. merge の孤児化: `_carry_prose` が「消える側は復元できない」として旧箇条書きを
     常に温存し、SSOT が取り下げた改訂前の制約が章に残って現行 SSOT と矛盾した。
  4. 時刻の素通り: `_is_rfc3339` は書式しか見ないため、未来の日時を書いても
     latest_checked_at / confirmed_at が受理された (起きていない照合・採択の記録)。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_TESTS = Path(__file__).resolve().parent
_PLUGIN = _TESTS.parent
COMPILE = _PLUGIN / "skills" / "run-system-spec-compile" / "scripts" / "compile-spec-doc.py"
WRITER = _PLUGIN / "skills" / "run-system-spec-elicit" / "scripts" / "apply-spec-transition.py"
REGISTRY = (
    _PLUGIN
    / "skills"
    / "ref-system-design-knowledge"
    / "references"
    / "doctrine-anchor-registry.json"
)

PLATFORMS = ["web", "mobile", "tablet", "desktop-windows", "desktop-linux", "desktop-macos"]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


c = _load(COMPILE, "compile_spec_doc_body")
w = _load(WRITER, "apply_spec_transition_body")
_REGISTRY = json.loads(REGISTRY.read_text(encoding="utf-8"))


def _spec(cat_id: str = "backend") -> dict:
    """web だけ確定、他 5 platform 対象外の 1 カテゴリ spec-state。"""
    matrix = {
        cat_id: {
            "web": {
                "state": "確定",
                "qa_ref": "qa-primary",
                "qa_refs": ["qa-primary", "qa-support"],
                "serves_goals": ["G1"],
            }
        }
    }
    for pf in PLATFORMS[1:]:
        matrix[cat_id][pf] = {"state": "対象外", "reason": "配信対象外"}
    return {
        "categories": [{"id": cat_id, "label": "テスト章"}],
        "platforms": PLATFORMS,
        "matrix": matrix,
        "qa_log": [
            {
                "id": "qa-primary",
                "question": "主質問の本文",
                "answer": "主回答の本文",
                "provenance": "AskUserQuestion / 選択肢提示あり",
                "answered_at": "2020-01-01T00:00:00Z",
            },
            {"id": "qa-support", "question": "裏付け質問の本文", "answer": "裏付け回答の本文"},
        ],
        "approval_log": [],
        "category_aggregate": {},
        "targets": [],
        "decisions": [
            {
                "id": "dec-x",
                "question": "決定の問い",
                "status": "confirmed",
                "serves_goals": ["G1"],
                "category": cat_id,
                "options": [{"id": "opt-a", "label": "採った案", "goal_fit": "G1 に直接資する"}],
                "user_decision": {"option_id": "opt-a", "confirmed_at": "2020-01-01T00:00:00Z"},
                "qa_ref": "qa-primary",
            }
        ],
        "requirements_foundation": {
            "goals": [{"id": "G1", "text": "ゴール本文"}],
            "objectives": [{"id": "O1", "text": "目標本文", "measure": "観測点本文", "serves": ["G1"]}],
            "concrete_intents": [{"id": "I1", "text": "やりたいこと本文", "serves": ["G1"]}],
            "confirmed": True,
        },
    }


# --------------------------------------------------------------------------- #
# 1. 章本文の実体化 — id 文字列でなく問答の逐語が章に出る                       #
# --------------------------------------------------------------------------- #
def test_chapter_emits_the_sections_its_own_prose_references():
    """状態表と設計知識節が本文で名指す 2 節が、実際に章へ存在する。

    修正前は「確定内容 (質疑録)」「To-Be / Delta」いずれも生成されず、章の本文が
    存在しない節を参照していた (宙に浮いた参照)。
    """
    chapter = c.render_chapter(_spec(), "backend", {})
    assert "## 確定内容 (質疑録)" in chapter
    assert "## To-Be / Delta" in chapter
    # 状態表・設計知識節の宣言文が名指す先と綴りが一致していること。
    assert "確定内容 (質疑録)" in c.render_state_table(_spec(), "backend")
    assert "To-Be / Delta" in c.render_design_refs("backend", _spec())


def test_confirmed_section_materializes_qa_text_not_just_ids():
    """qa_ref / qa_refs が指す問答の**本文**が章に展開される。"""
    body = c.render_confirmed_content(_spec(), "backend")
    assert "主質問の本文" in body and "主回答の本文" in body
    assert "裏付け質問の本文" in body and "裏付け回答の本文" in body
    # provenance を持つ entry は出所も章へ出す (出所不明の回答を確定根拠にしないため)。
    assert "AskUserQuestion / 選択肢提示あり" in body


def test_dangling_qa_ref_is_surfaced_not_hidden():
    """qa_log に無い qa_ref は、黙って省略せず欠落として本文へ出す。"""
    spec = _spec()
    spec["matrix"]["backend"]["web"]["qa_ref"] = "qa-missing"
    body = c.render_confirmed_content(spec, "backend")
    assert "qa-missing" in body and "存在しない" in body


def test_to_be_section_projects_goals_objectives_and_decisions():
    body = c.render_to_be_delta(_spec(), "backend")
    assert "ゴール本文" in body  # U3
    assert "観測点本文" in body  # U4 の measure = Delta の判定点
    assert "やりたいこと本文" in body  # U9
    assert "採った案" in body  # 確定 decision の採択
    assert "qa-primary" in body  # 採択の接地根拠


# --------------------------------------------------------------------------- #
# 2. 上流指針 — registry の 4 authority が全カテゴリの章本文へ到達する          #
# --------------------------------------------------------------------------- #
def test_every_canonical_category_receives_its_doctrine_authority():
    """category_concern_map の全カテゴリで authority が章本文に現れる。

    修正前は resource-map の read_when 経由の `.md` しか引かず、infrastructure など
    read_when に現れないカテゴリの章には doctrine authority が 1 つも出なかった。
    """
    by_id = {c_["concern_id"]: c_ for c_ in _REGISTRY["concerns"]}
    for cat_id, concern_ids in _REGISTRY["category_concern_map"].items():
        body = c.render_doctrine_anchors(cat_id)
        for cid in concern_ids:
            assert by_id[cid]["authority"] in body, f"{cat_id}: {cid} の authority が章に無い"


def test_unmapped_category_fails_closed():
    """registry に無いカテゴリは空節でごまかさず compile を止める。"""
    with pytest.raises(c.CompileError):
        c.render_doctrine_anchors("no-such-category")


# --------------------------------------------------------------------------- #
# 3. merge — 孤児化させない / 管轄節の並びは compile が権威                     #
# --------------------------------------------------------------------------- #
NEW_DOC = """---
status: confirmed
---

# 章

## 管理節

- 新しい項目

## 後ろの管理節

本文
"""


def test_merge_drops_stale_bullets_of_managed_lists():
    """SSOT が取り下げた旧箇条書きを章へ残さない (現行 SSOT との矛盾を作らない)。"""
    old = NEW_DOC.replace("- 新しい項目", "- 改訂前の古い項目")
    merged = c.merge_preserving(NEW_DOC, old)
    assert "新しい項目" in merged
    assert "改訂前の古い項目" not in merged


def test_merge_keeps_handwritten_prose_in_managed_sections():
    """箇条書きでない手書き注記は従来どおり引き継ぐ (保護の意図を壊さない)。"""
    old = NEW_DOC.replace("- 新しい項目", "- 新しい項目\n\n運用上の但し書き。")
    merged = c.merge_preserving(NEW_DOC, old)
    assert "運用上の但し書き。" in merged


def test_merge_orders_managed_sections_by_compile_and_keeps_unmanaged():
    """管轄節の並びは再生成側が権威、章に溜まった管轄外節は位置関係ごと残す。

    修正前は old_text の並びを全面基準にしたため、compile が節を足すと規範節
    (確定内容 / To-Be) が参考資料節の後ろへ落ちて読み順が壊れた。
    """
    old = """---
status: confirmed
---

# 章

## 後ろの管理節

本文

## 章に溜まった節

人が書いた記録

## 管理節

- 新しい項目
"""
    merged = c.merge_preserving(NEW_DOC, old)
    order = [line[3:].strip() for line in merged.splitlines() if line.startswith("## ")]
    assert order.index("管理節") < order.index("後ろの管理節"), order
    assert "章に溜まった節" in order
    assert "人が書いた記録" in merged
    # 管轄外節は old_text で直前に来ていた管轄節 (後ろの管理節) の後ろに留まる。
    assert order.index("章に溜まった節") == order.index("後ろの管理節") + 1, order


# --------------------------------------------------------------------------- #
# 4. writer — qa_log provenance と未来時刻の拒否                               #
# --------------------------------------------------------------------------- #
def _state_with_qa() -> dict:
    return {"qa_log": [{"id": "qa-1", "question": "q", "answer": "a"}], "approval_log": []}


def test_provenance_can_be_attached_to_an_existing_qa_entry():
    """既存 entry へ後から出所を足せる (従来は既存 id を丸ごと読み飛ばしていた)。"""
    state = _state_with_qa()
    w._upsert_qa_entry(state, "qa-1", {"provenance": "利用者への直接質問", "answered_at": "2020-01-01T00:00:00Z"})
    entry = state["qa_log"][0]
    assert entry["provenance"] == "利用者への直接質問"
    assert entry["answered_at"] == "2020-01-01T00:00:00Z"
    assert entry["question"] == "q" and entry["answer"] == "a"
    # 冪等 — 同値の再適用で entry は増えない・変わらない。
    w._upsert_qa_entry(state, "qa-1", {"provenance": "利用者への直接質問"})
    assert len(state["qa_log"]) == 1


def test_existing_question_and_answer_cannot_be_rewritten():
    """問答本文の事後書換は拒否する (記録の改竄防止)。"""
    state = _state_with_qa()
    with pytest.raises(w.TransitionError):
        w._upsert_qa_entry(state, "qa-1", {"answer": "都合よく書き換えた回答"})


def test_recorded_provenance_cannot_be_silently_replaced():
    state = _state_with_qa()
    w._upsert_qa_entry(state, "qa-1", {"provenance": "出所A"})
    with pytest.raises(w.TransitionError):
        w._upsert_qa_entry(state, "qa-1", {"provenance": "出所B"})


def test_future_timestamps_are_rejected():
    """まだ起きていない照合・採択を記録済みとして書けない。"""
    with pytest.raises(w.TransitionError) as exc:
        w._require_past_rfc3339("2099-01-01T00:00:00Z", "test.checked_at")
    assert "未来" in str(exc.value)
    # 過去の実測値は通る。
    w._require_past_rfc3339("2020-01-01T00:00:00Z", "test.checked_at")


# ── qa_log ↔ required-info item_id の機械可読な紐付け ───────────────────────
# 従来 qa entry は `{id, question, answer}`(+出所) しか持たず、どの必須情報を満たした
# 回答なのかは qa_id の命名規約と qa_ref 文字列からの目視推測でしか辿れなかった。
def test_required_info_items_can_be_declared_on_a_qa_entry():
    state = {"qa_log": []}
    w._upsert_qa_entry(
        state, "qa-1", {"question": "q", "answer": "a", "required_info_items": ["product-goal"]}
    )
    assert state["qa_log"][0]["required_info_items"] == ["product-goal"]


def test_required_info_items_are_added_not_replaced():
    """列挙漏れのある turn が既存の紐付けを落とさない (追記のみ・和集合)。"""
    state = _state_with_qa()
    w._upsert_qa_entry(state, "qa-1", {"required_info_items": ["product-goal"]})
    w._upsert_qa_entry(state, "qa-1", {"required_info_items": ["auth-model"]})
    assert state["qa_log"][0]["required_info_items"] == ["auth-model", "product-goal"]


def test_malformed_required_info_items_are_rejected():
    state = _state_with_qa()
    with pytest.raises(w.TransitionError):
        w._upsert_qa_entry(state, "qa-1", {"required_info_items": "product-goal"})
    with pytest.raises(w.TransitionError):
        w._upsert_qa_entry(state, "qa-1", {"required_info_items": ["", "x"]})


# ── 除外セルの根拠質疑 ───────────────────────────────────────────────────────
def _matrix_state() -> dict:
    return {
        "qa_log": [{"id": "qa-1", "question": "q", "answer": "a"}],
        "approval_log": [{"id": "appr-1"}],
        "categories": [{"id": "auth", "label": "認証"}],
        "matrix": {"auth": {"tablet": {"state": "未収集"}}},
    }


def test_exclude_records_the_qa_that_justified_it():
    """従来は reason の散文だけが残り、どの質疑で外したのかを機械で辿れなかった。"""
    state = _matrix_state()
    w.apply_cell_op(
        state,
        {"action": "exclude", "category": "auth", "platform": "tablet",
         "reason": "専用アプリを持たない", "qa_ref": "qa-1"},
    )
    assert state["matrix"]["auth"]["tablet"]["qa_ref"] == "qa-1"


def test_exclude_turn_fills_qa_ref_from_the_turn_id():
    """confirm と同じく、turn の qa_id を exclude op へも補完する。"""
    state = _matrix_state()
    w.apply_turn(
        state,
        {"qa_id": "qa-1",
         "ops": [{"action": "exclude", "category": "auth", "platform": "tablet",
                  "reason": "専用アプリを持たない"}]},
    )
    assert state["matrix"]["auth"]["tablet"]["qa_ref"] == "qa-1"


# ── 根拠の差し替えを「節の消失」と取り違えない ────────────────────────────────
# 根拠付き R4-reopen で確定セルの第一根拠を差し替えると、章の
# `#### 主たる接地根拠: <qa_id>` の値が変わる。これを消失として拒むと、正規経路で
# reopen した章を二度と再生成できない (保存則が正規経路を詰ませる)。
def test_lost_headings_allows_same_label_different_value():
    old = "## 確定内容\n\n#### 主たる接地根拠: `qa-old-001`\n\n本文\n"
    new = "## 確定内容\n\n#### 主たる接地根拠: `qa-new-002`\n\n本文\n"
    assert c._lost_headings(new, old) == []


def test_lost_headings_still_rejects_outright_removal():
    # 差し替えの許容が、節そのものの削除まで通してしまわないこと。
    old = "## 確定内容\n\n#### 主たる接地根拠: `qa-old-001`\n\n本文\n"
    new = "## 確定内容\n\n本文\n"
    assert c._lost_headings(new, old) == ["#### 主たる接地根拠: `qa-old-001`"]


def test_lost_headings_rejects_removal_of_a_different_label():
    # ラベルが違えば、別のラベルが存在しても消失として扱う。
    old = "## 確定内容\n\n#### 主たる接地根拠: `qa-a`\n\n#### 補足: `x`\n\n本文\n"
    new = "## 確定内容\n\n#### 主たる接地根拠: `qa-b`\n\n本文\n"
    assert c._lost_headings(new, old) == ["#### 補足: `x`"]


# ── reopen の実施時刻 ────────────────────────────────────────────────────────
# reopen は確定を巻き戻せる唯一の正規経路であり、いちばん時刻が要る操作である。
# 時刻が無いと「差し替え後の主根拠がこの reopen より後に取り直された回答か」を検査
# できず、先に確定を壊してから既存の回答を主根拠に流用した場合と、正当に取り直した
# 場合が同じ見た目になる。
def _confirmed_state() -> dict:
    return {
        "qa_log": [{"id": "qa-1", "question": "q", "answer": "a"}],
        "approval_log": [],
        "categories": [{"id": "auth", "label": "認証"}],
        "matrix": {"auth": {"web": {"state": "確定", "qa_ref": "qa-1"}}},
    }


def _reopen_op(**extra) -> dict:
    op = {"action": "reopen", "category": "auth", "platform": "web", "reason": "根拠の差し替え"}
    op.update(extra)
    return op


def test_reopen_records_when_it_happened():
    state = _confirmed_state()
    w.apply_cell_op(state, _reopen_op(reopened_at="2020-01-01T00:00:00Z"))
    assert state["reopen_log"][0]["reopened_at"] == "2020-01-01T00:00:00Z"
    assert state["matrix"]["auth"]["web"]["state"] == "未収集"


def test_reopen_without_a_timestamp_is_rejected():
    """時刻の無い reopen は、実施順を復元できない記録を残すので受け付けない。"""
    state = _confirmed_state()
    with pytest.raises(w.TransitionError):
        w.apply_cell_op(state, _reopen_op())
    # 拒否された reopen は確定を壊していない (部分適用を残さない)。
    assert state["matrix"]["auth"]["web"]["state"] == "確定"
    assert not state.get("reopen_log")


def test_reopen_timestamp_cannot_be_in_the_future():
    """他の時刻と同じく、まだ起きていない reopen を記録済みとして書けない。"""
    state = _confirmed_state()
    with pytest.raises(w.TransitionError) as exc:
        w.apply_cell_op(state, _reopen_op(reopened_at="2099-01-01T00:00:00Z"))
    assert "未来" in str(exc.value)


# ── 凍結された問答本文に残る誤りの訂正 ────────────────────────────────────────
# question / answer は改竄防止で凍結されている。しかし本文の散文へ誤った値を書くと、
# その凍結がそのまま「訂正できない誤り」になる。corrections は本文を書き換えずに
# 「この記録は後に訂正された」という事実だけを append-only で残す。
def _corr(**extra) -> dict:
    c = {"corrected_at": "2020-01-01T00:00:00Z", "note": "旧値 14:52:00Z は誤り。正は 21:27:59Z"}
    c.update(extra)
    return c


def test_correction_can_be_attached_without_touching_the_frozen_body():
    state = _state_with_qa()
    w._upsert_qa_entry(state, "qa-1", {"corrections": [_corr()]})
    entry = state["qa_log"][0]
    assert entry["corrections"] == [_corr()]
    # 本文は凍結されたまま。
    assert entry["question"] == "q" and entry["answer"] == "a"


def test_corrections_are_append_only_and_idempotent():
    state = _state_with_qa()
    w._upsert_qa_entry(state, "qa-1", {"corrections": [_corr()]})
    w._upsert_qa_entry(state, "qa-1", {"corrections": [_corr()]})
    assert len(state["qa_log"][0]["corrections"]) == 1, "同値の再適用で増えてはならない"
    w._upsert_qa_entry(state, "qa-1", {"corrections": [_corr(note="別の訂正")]})
    assert len(state["qa_log"][0]["corrections"]) == 2, "既存の訂正を落としてはならない"


def test_correction_without_a_real_timestamp_is_rejected():
    """まだ起きていない訂正を記録済みとして書けない。"""
    state = _state_with_qa()
    with pytest.raises(w.TransitionError):
        w._upsert_qa_entry(state, "qa-1", {"corrections": [_corr(corrected_at="2099-01-01T00:00:00Z")]})
    with pytest.raises(w.TransitionError):
        w._upsert_qa_entry(state, "qa-1", {"corrections": [{"note": "時刻なし"}]})


def test_correction_without_substance_is_rejected():
    """訂正した体裁だけを整えて中身が無い記録を弾く。"""
    state = _state_with_qa()
    with pytest.raises(w.TransitionError):
        w._upsert_qa_entry(state, "qa-1", {"corrections": [_corr(note="   ")]})


def test_correction_with_an_unknown_key_is_rejected():
    """typo を黙って捨てると『書いたつもりの訂正』が消える。"""
    state = _state_with_qa()
    with pytest.raises(w.TransitionError) as exc:
        w._upsert_qa_entry(state, "qa-1", {"corrections": [dict(_corr(), corrected_by="me")]})
    assert "corrected_by" in str(exc.value)


def test_malformed_corrections_container_is_rejected():
    state = _state_with_qa()
    for bad in ("文字列", [], [None]):
        with pytest.raises(w.TransitionError):
            w._upsert_qa_entry(state, "qa-1", {"corrections": bad})


# ── 章固有の設計知識適用 ─────────────────────────────────────────────────────
# card 本文は共有資産の逐語なので、同じ card を引く章どうしは byte 一致する。
# 章固有性を担えるのは spec-state 側の適用記述だけで、従来その置き場が無かった。
def _cat_state() -> dict:
    return {
        "qa_log": [], "approval_log": [],
        "categories": [{"id": "backend", "label": "バックエンド"}],
        "matrix": {"backend": {"web": {"state": "未収集"}}},
    }


def _app_op(**extra) -> dict:
    op = {"action": "set-design-application", "category": "backend",
          "text": "月次集計を要求時導出にしたため、境界は読み取りモデル側に置いた",
          "recorded_at": "2020-01-01T00:00:00Z"}
    op.update(extra)
    return op


def test_design_application_is_recorded_per_category():
    state = _cat_state()
    w.apply_cell_op(state, _app_op(basis="agent-inference"))
    rec = state["design_applications"]["backend"]
    assert rec["basis"] == "agent-inference" and rec["recorded_at"] == "2020-01-01T00:00:00Z"


def test_design_application_rejects_empty_or_unknown_category():
    state = _cat_state()
    with pytest.raises(w.TransitionError):
        w.apply_cell_op(state, _app_op(text="   "))
    with pytest.raises(w.TransitionError):
        w.apply_cell_op(state, _app_op(category="存在しない"))
    with pytest.raises(w.TransitionError):
        w.apply_cell_op(state, _app_op(recorded_at="2099-01-01T00:00:00Z"))


def test_compile_marks_the_section_hollow_when_no_application_is_recorded():
    """未記入を黙って通すと、card を並べただけの節が『適用した』証拠を騙る。"""
    out = c._render_design_application({"design_applications": {}}, "backend")
    assert any("未記入" in line for line in out)
    assert any("「適用した」証拠ではない" in line for line in out)


def test_compile_renders_the_recorded_application():
    spec = {"design_applications": {"backend": {
        "text": "境界は読み取りモデル側に置いた", "basis": "agent-inference",
        "recorded_at": "2020-01-01T00:00:00Z"}}}
    out = "\n".join(c._render_design_application(spec, "backend"))
    assert "境界は読み取りモデル側に置いた" in out
    assert "未記入" not in out
    assert "アシスタントの推定" in out


# ── 訂正マーカーの章への投影 ─────────────────────────────────────────────────
def test_corrections_are_projected_next_to_the_frozen_answer():
    """章だけを読む利用者が、反証済みの値を唯一の事実として受け取らないこと。"""
    entry = {"id": "qa-1", "question": "q", "answer": "採択時刻は 14:52:00Z",
             "corrections": [{"corrected_at": "2020-01-01T00:00:00Z",
                              "note": "14:52:00Z は書込時刻より後で発生し得ない。正は 21:27:59Z"}]}
    out = "\n".join(c._render_qa_entry(entry, "qa-1", role="主たる接地根拠"))
    assert "訂正あり" in out and "21:27:59Z" in out
    # 訂正は答の本文より後、かつ次の見出しより前に出る。
    assert out.index("採択時刻は 14:52:00Z") < out.index("訂正あり")


def test_basis_is_projected_so_readers_can_tell_who_decided():
    entry = {"id": "qa-1", "question": "q", "answer": "a", "basis": "agent-inference"}
    out = "\n".join(c._render_qa_entry(entry, "qa-1", role="主たる接地根拠"))
    assert "アシスタントの推定" in out


# ── doctrine レベルの適用記述 ────────────────────────────────────────────────
# card レベル (design_applications) で塞いだ空洞が doctrine レベルにも残っていた。
# registry の転記表に authority 名が現れることは「適用した」証拠にならない
# (機械注入したものを自分で証拠に数える自己循環)。章固有の反映はここにしか書けない。
def _doc_state() -> dict:
    return {
        "qa_log": [], "approval_log": [],
        "categories": [{"id": "backend"}, {"id": "database"}],
        "matrix": {"backend": {"web": {"state": "未収集"}},
                   "database": {"web": {"state": "未収集"}}},
    }


def _doc_op(**extra) -> dict:
    op = {"action": "set-doctrine-application", "category": "backend",
          "concern_id": "data-access",
          "text": "月次集計は要求時に canonical から毎回導出し、D1 側に集計表を持たない",
          "recorded_at": "2020-01-01T00:00:00Z"}
    op.update(extra)
    return op


def test_doctrine_application_is_recorded_per_category_and_concern():
    """concern は複数章から引かれるので、category だけでは置き場が足りない。"""
    state = _doc_state()
    w.apply_cell_op(state, _doc_op(basis="agent-inference"))
    w.apply_cell_op(state, _doc_op(concern_id="application-architecture", text="別の反映"))
    rec = state["doctrine_applications"]["backend"]
    assert set(rec) == {"data-access", "application-architecture"}
    assert rec["data-access"]["basis"] == "agent-inference"
    assert rec["data-access"]["recorded_at"] == "2020-01-01T00:00:00Z"


def test_doctrine_application_rejects_the_same_text_reused_in_another_chapter():
    """章が違えば確定セルも違う。一致するのは上流の要約を写しただけの疑いが強い。"""
    state = _doc_state()
    w.apply_cell_op(state, _doc_op())
    with pytest.raises(w.TransitionError) as exc:
        w.apply_cell_op(state, _doc_op(category="database"))
    assert "backend" in str(exc.value)


def test_doctrine_reuse_check_sees_through_cosmetic_edits():
    """句読点や空白を足しただけの複製が転記でなくなるわけではない。"""
    state = _doc_state()
    base = _doc_op()["text"]
    w.apply_cell_op(state, _doc_op())
    for cosmetic in (base.replace("。", "．"), base.replace("月次", " 月次 "), base + "  "):
        with pytest.raises(w.TransitionError):
            w.apply_cell_op(state, _doc_op(category="database", text=cosmetic))


def test_doctrine_reuse_check_allows_different_content_and_self_overwrite():
    """弾きすぎれば回避目的の無意味な言い換えを強いる。正当な 2 例は通す。"""
    state = _doc_state()
    w.apply_cell_op(state, _doc_op())
    w.apply_cell_op(state, _doc_op(category="database", text="端末側に複製を持たない"))
    w.apply_cell_op(state, _doc_op(text="同じ章への再適用は上書きであって重複ではない"))
    assert state["doctrine_applications"]["backend"]["data-access"]["text"].startswith("同じ章")


def test_doctrine_application_rejects_malformed_input():
    """例外が出たことではなく、どの欄が不正かを writer が名指ししていることを見る。

    「TransitionError が上がる」だけを見る検査は、この op を一切知らない実装でも緑になる
    (未知 action として同じ例外型で弾かれるため)。それでは 0 件の違反と 0 件しか
    調べていないことが区別できないので、正しい op が通ることと、誤りが不正な欄の名前で
    報告されることの両方を要求する。
    """
    state = _doc_state()
    w.apply_cell_op(state, _doc_op())  # 正例が通らない実装では以降の負例に意味がない
    for bad, expected in (({"text": "   "}, "text"), ({"concern_id": ""}, "concern_id"),
                          ({"category": "存在しない"}, "存在しない"),
                          ({"recorded_at": "2099-01-01T00:00:00Z"}, "recorded_at"),
                          ({"basis": "なんとなく"}, "basis")):
        with pytest.raises(w.TransitionError) as exc:
            w.apply_cell_op(state, _doc_op(**bad))
        assert expected in str(exc.value), (bad, str(exc.value))


def test_compile_marks_the_doctrine_column_unfilled_when_absent():
    out = c.render_doctrine_anchors("backend", {"doctrine_applications": {}})
    assert "本章の確定セルへの反映" in out and "未記入" in out


def test_compile_renders_the_recorded_doctrine_application():
    spec = {"doctrine_applications": {"backend": {
        "data-access": {"text": "集計表を D1 に持たない", "recorded_at": "2020-01-01T00:00:00Z"}}}}
    out = c.render_doctrine_anchors("backend", spec)
    assert "集計表を D1 に持たない" in out


# ── reopen_log への補記 ──────────────────────────────────────────────────────
# 既存キーは不可侵のまま、事後に判明した事実だけを追記する。append-only の下では
# 「訂正 (既存事実の修正)」と「補記 (新しい事実の追加)」は別物である。
def _reopen_state() -> dict:
    return {"reopen_log": [
        {"category": "auth", "platform": "web", "reason": "前提が変わった"},
        {"category": "backend", "platform": "web", "reason": "別の理由",
         "reopened_at": "2020-01-01T00:00:00Z"},
    ]}


def _rc_op(**extra) -> dict:
    op = {"action": "add-reopen-correction", "index": 0,
          "match_category": "auth", "match_platform": "web",
          "note": "適用時刻をトランスクリプトから復元した",
          "recovered_at": "2020-02-01T00:00:00Z",
          "observed_reopened_at": "2019-12-31T23:59:00Z"}
    op.update(extra)
    return op


def test_reopen_correction_is_appended_without_touching_existing_keys():
    state = _reopen_state()
    before = dict(state["reopen_log"][0])
    w.apply_cell_op(state, _rc_op())
    entry = state["reopen_log"][0]
    assert all(entry[k] == v for k, v in before.items())
    assert entry["corrections"][0]["observed_reopened_at"] == "2019-12-31T23:59:00Z"


def test_reopen_correction_never_writes_the_original_timestamp_key():
    """復元値は state 反映時刻であって reopen を決めた瞬間ではない。同名キーへ置かない。"""
    state = _reopen_state()
    w.apply_cell_op(state, _rc_op())
    assert "reopened_at" not in state["reopen_log"][0]
    w.apply_cell_op(state, _rc_op(index=1, match_category="backend"))
    assert state["reopen_log"][1]["reopened_at"] == "2020-01-01T00:00:00Z"


def test_reopen_correction_is_idempotent():
    state = _reopen_state()
    w.apply_cell_op(state, _rc_op())
    w.apply_cell_op(state, _rc_op())
    assert len(state["reopen_log"][0]["corrections"]) == 1


def test_reopen_correction_requires_identity_match_not_just_an_index():
    """index の取り違えは、別の reopen に他人の時刻を付ける汚染そのものになる。"""
    state = _reopen_state()
    with pytest.raises(w.TransitionError):
        w.apply_cell_op(state, _rc_op(match_category="backend"))
    with pytest.raises(w.TransitionError):
        w.apply_cell_op(state, _rc_op(match_platform=None))


def test_reopen_correction_rejects_malformed_input():
    state = _reopen_state()
    for bad in ({"index": 5}, {"index": "0"}, {"index": True}, {"note": "  "},
                {"recovered_at": "2099-01-01T00:00:00Z"},
                {"observed_reopened_at": "2099-01-01T00:00:00Z"}):
        with pytest.raises(w.TransitionError):
            w.apply_cell_op(state, _rc_op(**bad))


# --------------------------------------------------------------------------- #
# 4. 承認の実体化 — 承認 id ではなく承認範囲が章に出る                          #
# --------------------------------------------------------------------------- #
APPR_NOTE = "対象を web のみとする範囲について、代替案 2 件を併記した上で利用者の承認を得た"


def _appr_spec() -> dict:
    """対象外セルが承認を引用し、その承認を名指しする質疑を持つ spec-state。"""
    spec = _spec()
    for pf in PLATFORMS[1:]:
        spec["matrix"]["backend"][pf]["approval_ref"] = "appr-scope-001"
    spec["approval_log"] = [{"id": "appr-scope-001", "note": APPR_NOTE}]
    spec["qa_log"].append(
        {
            "id": "qa-scope-001",
            "question": "対象プラットフォームをどこまでにしますか",
            "answer": "web のみとする",
            "basis": "user-decision",
            "answered_at": "2020-01-02T00:00:00Z",
            "provenance": "AskUserQuestion による明示選択 (appr-scope-001 として記録)",
            "corrections": [{"corrected_at": "2020-01-03T00:00:00Z", "note": "回答時刻の訂正"}],
        }
    )
    spec["requirements_foundation"]["approval_ref"] = "appr-scope-001"
    return spec


def test_chapter_materializes_the_approval_behind_an_excluded_cell():
    """対象外セルの「承認: <id>」に対応する承認範囲が、同じ章の本文に出る。

    id だけでは、その承認が何をどこまで認めたものかを章から辿れない。確定セルに対する
    「確定内容 (質疑録)」と同じ実体化を、対象外セルの承認にも要求する。
    """
    chapter = c.render_chapter(_appr_spec(), "backend", {})
    assert "## 対象外の承認範囲" in chapter
    assert APPR_NOTE in chapter, "承認 note の逐語が章に無い"
    assert chapter.count("### 承認: `appr-scope-001`") == 1, "5 セルが引用する承認を重複展開している"


def test_chapter_shows_the_qa_that_names_the_approval():
    """承認を名指しする質疑の逐語と、その訂正が章に出る。

    approval_log の entry は {id, note} だけで質疑への参照キーを持たない。名指しという
    検証可能な関係だけを根拠に、承認の実体である問答を同じ節へ引き込む。
    """
    chapter = c.render_chapter(_appr_spec(), "backend", {})
    assert "この承認を名指ししている質疑" in chapter
    assert "対象プラットフォームをどこまでにしますか" in chapter
    assert "回答時刻の訂正" in chapter, "qa の corrections が章へ投影されていない"


def test_requirements_chapter_names_the_approval_that_confirmed_it():
    """憲法章の status: confirmed が、どの承認に接地しているかを章から辿れる。

    修正前は「確定マーカー: status: confirmed」という自己申告だけで、承認 id も承認範囲も
    章のどこにも現れなかった。章だけを読む人にとって、利用者が全文を見た上で確定させた
    のか、確定フラグが立っているだけなのかが区別できない状態だった。
    """
    doc = c.render_requirements_definition(_appr_spec())
    assert "## 確定の接地根拠 (承認)" in doc
    assert "appr-scope-001" in doc
    assert APPR_NOTE in doc


def test_requirements_chapter_reports_a_missing_or_absent_approval_instead_of_hiding_it():
    """承認 ref が無い/壊れている場合に、確定根拠ありと読める体裁で黙らない。"""
    spec = _appr_spec()
    spec["requirements_foundation"]["approval_ref"] = "appr-does-not-exist"
    doc = c.render_requirements_definition(spec)
    assert "approval_log に存在しない" in doc

    spec2 = _appr_spec()
    spec2["requirements_foundation"].pop("approval_ref")
    doc2 = c.render_requirements_definition(spec2)
    assert "## 確定の接地根拠 (承認)" in doc2
    assert "引用している承認記録なし" in doc2


def test_reason_only_chapter_gets_no_empty_approval_section():
    """理由文で対象外にした章に、空の承認節を足さない。

    その章の対象外根拠は状態表に逐語で出ており空洞ではない。空洞になるのは状態表が
    「承認: <id>」としか言えないときだけなので、節の有無は approval_ref の有無に一致させる。
    節が無いことが根拠の隠蔽になっていないことを、理由の逐語が章にあることで併せて確かめる。
    """
    chapter = c.render_chapter(_spec(), "backend", {})
    assert "## 対象外の承認範囲" not in chapter
    assert "配信対象外" in chapter


# --------------------------------------------------------------------------- #
# 5. 計測値時刻の訂正 — 誤値を機械可読な位置に残さない                          #
# --------------------------------------------------------------------------- #
def _ts_state() -> dict:
    return {
        "qa_log": [
            {
                "id": "qa-income",
                "question": "収入側の判断効果は",
                "answer": "支出と同じ考え方に揃える",
                "basis": "user-decision",
                "answered_at": "2020-01-05T01:54:36Z",
            }
        ]
    }


def _ts_op(**extra) -> dict:
    op = {
        "action": "correct-qa-timestamp",
        "qa_id": "qa-income",
        "key": "answered_at",
        "expected_current": "2020-01-05T01:54:36Z",
        "value": "2020-01-05T00:26:23Z",
        "note": "記録値は書込時刻で、実際の回答時刻はトランスクリプト実測の 00:26:23Z",
        "corrected_at": "2020-01-06T00:00:00Z",
    }
    op.update(extra)
    return op


def test_measured_timestamp_is_corrected_in_place_and_the_old_value_is_kept():
    """誤った計測値時刻はフィールド自体が正しくなり、誤っていた事実も残る。

    answered_at は散文ではなく計測値なので、凍結したまま corrections[] の日本語文にだけ
    正しい値を置くと、このキーを読む機械は誤値を読み続ける。決定論ゲートは全て緑のまま
    誤りが残るので、どちらか一方ではなく両方 (正しい値と訂正の履歴) を要求する。
    """
    state = _ts_state()
    w.apply_cell_op(state, _ts_op())
    entry = state["qa_log"][0]
    assert entry["answered_at"] == "2020-01-05T00:26:23Z"
    rec = entry["corrections"][0]
    assert rec["previous_value"] == "2020-01-05T01:54:36Z"
    assert rec["corrected_value"] == "2020-01-05T00:26:23Z"
    assert rec["corrected_field"] == "answered_at"
    assert "00:26:23Z" in rec["note"]
    # 本文は訂正の対象外のまま。
    assert entry["answer"] == "支出と同じ考え方に揃える"


def test_timestamp_correction_is_idempotent_and_refuses_a_blind_overwrite():
    """同値の再適用では増えず、現在値を取り違えた訂正は拒否される。"""
    state = _ts_state()
    w.apply_cell_op(state, _ts_op())
    w.apply_cell_op(state, _ts_op())  # 2 回目は no-op
    assert len(state["qa_log"][0]["corrections"]) == 1

    # 既に訂正済みの entry を、古い現在値のまま別の値へ塗り替えることはできない。
    with pytest.raises(w.TransitionError) as exc:
        w.apply_cell_op(state, _ts_op(value="2020-01-05T12:00:00Z"))
    assert "expected_current" in str(exc.value)


def test_timestamp_correction_rejects_malformed_input():
    """不正な欄を writer が名指しで報告する。

    例外型だけを見る検査は、この op を一切知らない実装でも緑になる (未知 action が同じ
    例外型で弾かれるため)。正例が通ることと、誤りが不正な欄の名前で報告されることの
    両方を要求する。
    """
    w.apply_cell_op(_ts_state(), _ts_op())
    for bad, expected in (
        ({"qa_id": "存在しない"}, "存在しない"),
        ({"key": "answer"}, "key"),
        ({"key": "provenance"}, "key"),
        ({"value": "2099-01-01T00:00:00Z"}, "value"),
        ({"value": "きのう"}, "value"),
        ({"note": "   "}, "note"),
        ({"corrected_at": "2099-01-01T00:00:00Z"}, "corrected_at"),
        ({"expected_current": "2020-01-05T09:99:99Z"}, "expected_current"),
    ):
        with pytest.raises(w.TransitionError) as exc:
            w.apply_cell_op(_ts_state(), _ts_op(**bad))
        assert expected in str(exc.value), (bad, str(exc.value))


def test_chapter_shows_what_the_timestamp_correction_changed():
    """訂正が何をどう変えたかを、散文任せにせず旧値と新値で章に出す。"""
    spec = _spec()
    qa = spec["qa_log"][0]
    qa["answered_at"] = "2020-01-05T01:54:36Z"
    ts_state = {"qa_log": [qa]}
    w.apply_cell_op(ts_state, _ts_op(qa_id=qa["id"]))
    chapter = c.render_chapter(spec, "backend", {})
    assert "変更: `answered_at`" in chapter
    assert "2020-01-05T01:54:36Z" in chapter  # 旧値が消えていない
    assert "2020-01-05T00:26:23Z" in chapter  # 新値が出ている
