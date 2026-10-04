# /// script
# name: test-qa-supersession
# version: 0.1.0
# purpose: 凍結済み qa の置き換え (supersede-qa) の writer 契約と、compile での旧版・逐語の描き方の回帰ガード。修正前の実装では全て赤になる。
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
"""qa の置き換えと、その章への投影の回帰テスト。

背景 — qa_log は append-only で question/answer を凍結している。問の設計に欠陥
(推奨の印、片側だけの不利益) があると、同じ論点を中立に問い直して利用者の回答を
取り直しても、旧 entry は C06 の誘導性評価の対象に残り続け、検出を閉じる手段が
無かった。また compile は answer の逐語をそのまま章の markdown に流し込むため、
answer の行頭 ``###`` が章の見出しとして漏れ、旧版の本文が現行の構造と区別できなかった。

  1. writer: ``supersede-qa`` op で置き換え関係を 1 度だけ記録する。条件 (c)
     (利用者の回答が記録されている) は writer が決定論で検査する。
  2. compile: 構造を持つ逐語はフェンスで囲み、置き換え済みの entry は
     「旧版 (置き換え先: <qa_id>)」の印付きで描く。承認 id を名指ししているだけの
     qa を旧版と描かない。
"""
from __future__ import annotations

import copy
import importlib.util
import re
from pathlib import Path

import pytest

_TESTS = Path(__file__).resolve().parent
_PLUGIN = _TESTS.parent
COMPILE = _PLUGIN / "skills" / "run-system-spec-compile" / "scripts" / "compile-spec-doc.py"
WRITER = _PLUGIN / "skills" / "run-system-spec-elicit" / "scripts" / "apply-spec-transition.py"

PLATFORMS = ["web", "mobile", "tablet", "desktop-windows", "desktop-linux", "desktop-macos"]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


c = _load(COMPILE, "compile_spec_doc_supersession")
w = _load(WRITER, "apply_spec_transition_supersession")


# --------------------------------------------------------------------------- #
# 1. writer: supersede-qa                                                      #
# --------------------------------------------------------------------------- #
OLD_Q = "次のどれにしますか? A (推奨) / B"
NEW_Q = "次のどれにしますか? A: 利点… 不利な点… / B: 利点… 不利な点… / 決めない"


def _state() -> dict:
    return {
        "qa_log": [
            {
                "id": "qa-old",
                "question": OLD_Q,
                "answer": "A",
                "basis": "user-decision",
                "answered_at": "2020-01-01T00:00:00Z",
            },
            {
                "id": "qa-new",
                "question": NEW_Q,
                "answer": "A",
                "basis": "user-decision",
                "answered_at": "2020-01-02T00:00:00Z",
            },
        ],
        "approval_log": [],
        "categories": [{"id": "auth", "label": "認証"}],
        "matrix": {"auth": {pf: {"state": "対象外", "reason": "配信対象外"} for pf in PLATFORMS}},
    }


def _op(**extra) -> dict:
    op = {
        "action": "supersede-qa",
        "qa_id": "qa-old",
        "superseded_by": "qa-new",
        "superseded_at": "2020-01-03T00:00:00Z",
        "note": "旧問は A に推奨の印があった (N1 違反)。同じ論点を利点と不利な点を対称にして問い直した",
    }
    op.update(extra)
    return op


def _entry(state: dict, qa_id: str) -> dict:
    return next(e for e in state["qa_log"] if e["id"] == qa_id)


def test_supersede_records_the_relation_without_touching_the_frozen_body():
    """置き換えは旧 entry への追記であって、問答本文は凍結されたまま残る。"""
    state = _state()
    w.apply_cell_op(state, _op())
    old = _entry(state, "qa-old")
    assert old["superseded_by"] == "qa-new"
    assert old["superseded_at"] == "2020-01-03T00:00:00Z"
    assert "N1" in old["superseded_note"]
    # 欠陥のあった問を記録から消していない。
    assert old["question"] == OLD_Q and old["answer"] == "A"
    # 新 entry は置き換える側であって、置き換えられた印は付かない。
    assert "superseded_by" not in _entry(state, "qa-new")


def test_supersede_is_write_once_and_idempotent():
    """同値の再適用は no-op、別の値への書換は拒否する。"""
    state = _state()
    w.apply_cell_op(state, _op())
    snapshot = copy.deepcopy(state)
    w.apply_cell_op(state, _op())
    assert state == snapshot, "同値の再適用で state が変わってはならない"

    state["qa_log"].append(
        {"id": "qa-newer", "question": "別の問", "answer": "B", "basis": "user-decision",
         "answered_at": "2020-01-04T00:00:00Z"}
    )
    with pytest.raises(w.TransitionError) as exc:
        w.apply_cell_op(state, _op(superseded_by="qa-newer", superseded_at="2020-01-05T00:00:00Z"))
    assert "書換不可" in str(exc.value)
    assert _entry(state, "qa-old")["superseded_by"] == "qa-new"


def test_supersede_rejects_malformed_input_by_field_name():
    """不正な欄を writer が名指しで報告する。

    例外型だけを見る検査は、この op を知らない実装でも緑になる (未知 action は同じ例外型で
    弾かれる)。正例が通ることと、誤りが欄の名前で報告されることの両方を要求する。
    """
    w.apply_cell_op(_state(), _op())
    for bad, expected in (
        ({"qa_id": ""}, "qa_id"),
        ({"qa_id": "存在しない"}, "存在しない"),
        ({"superseded_by": ""}, "superseded_by"),
        ({"superseded_by": "存在しない"}, "存在しない"),
        ({"superseded_by": "qa-old"}, "自分自身"),
        ({"note": "  "}, "note"),
        ({"superseded_at": "きのう"}, "superseded_at"),
        ({"superseded_at": "2099-01-01T00:00:00Z"}, "superseded_at"),
        ({"superseded_at": "2020-01-01T12:00:00Z"}, "superseded_at"),  # 新しい回答より前
    ):
        with pytest.raises(w.TransitionError) as exc:
            w.apply_cell_op(_state(), _op(**bad))
        assert expected in str(exc.value), (bad, str(exc.value))


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda e: e.update(answer=""), "answer"),
        (lambda e: e.update(basis="agent-inference"), "basis"),
        (lambda e: e.pop("basis"), "basis"),
        (lambda e: e.pop("answered_at"), "answered_at"),
        (lambda e: e.update(answered_at="2019-12-31T00:00:00Z"), "answered_at"),
    ],
)
def test_supersede_requires_a_recorded_user_answer_after_the_old_one(mutate, expected):
    """条件 (c): 置き換える側に、旧 entry より後に取った利用者の回答が記録されていること。

    推定 (agent-inference) や回答の無い問で置き換えられると、欠陥のある問を「問い直した」
    体裁だけ整えて検出を閉じられてしまう。
    """
    state = _state()
    mutate(_entry(state, "qa-new"))
    with pytest.raises(w.TransitionError) as exc:
        w.apply_cell_op(state, _op())
    assert expected in str(exc.value)
    assert "superseded_by" not in _entry(state, "qa-old"), "拒否した置き換えを部分適用してはならない"


def test_supersede_refuses_while_the_old_entry_grounds_a_confirmed_cell():
    """確定セルの主たる接地根拠のままでは置き換えられない。R4-reopen → 再確定が先。"""
    state = _state()
    state["matrix"]["auth"]["web"] = {"state": "確定", "qa_ref": "qa-old", "qa_refs": ["qa-old"]}
    with pytest.raises(w.TransitionError) as exc:
        w.apply_cell_op(state, _op())
    assert "auth/web" in str(exc.value) and "reopen" in str(exc.value)

    w.apply_cell_op(
        state,
        {"action": "reopen", "category": "auth", "platform": "web",
         "reason": "主根拠の問に推奨の印があった", "reopened_at": "2020-01-02T12:00:00Z"},
    )
    w.apply_cell_op(state, {"action": "confirm", "category": "auth", "platform": "web", "qa_ref": "qa-new"})
    w.apply_cell_op(state, _op())
    assert _entry(state, "qa-old")["superseded_by"] == "qa-new"


def test_a_superseded_entry_cannot_become_the_primary_ground_again():
    """置き換えた後に reopen → confirm で旧 entry を主根拠へ戻せない。

    戻せると「主たる接地根拠のままでは置き換えない」という条件が 2 手で抜けられ、C06 は
    置き換え済みとして判定から外した問を、確定の根拠として読むことになる。
    """
    state = _state()
    w.apply_cell_op(state, _op())
    state["matrix"]["auth"]["web"] = {"state": "未収集"}
    with pytest.raises(w.TransitionError) as exc:
        w.apply_cell_op(
            state, {"action": "confirm", "category": "auth", "platform": "web", "qa_ref": "qa-old"}
        )
    assert "置き換え済み" in str(exc.value) and "qa-new" in str(exc.value)
    assert state["matrix"]["auth"]["web"] == {"state": "未収集"}
    # 置き換え先なら確定できる (拒否の理由が置き換えに限られることの確認)。
    w.apply_cell_op(
        state, {"action": "confirm", "category": "auth", "platform": "web", "qa_ref": "qa-new"}
    )
    assert state["matrix"]["auth"]["web"]["qa_ref"] == "qa-new"


def test_supersede_cannot_point_to_a_retired_entry_or_form_a_cycle():
    state = _state()
    w.apply_cell_op(state, _op())
    # qa-old は置き換え済み。qa-new を qa-old で置き換え返すことはできない (循環)。
    with pytest.raises(w.TransitionError) as exc:
        w.apply_cell_op(
            state,
            _op(qa_id="qa-new", superseded_by="qa-old", superseded_at="2020-01-04T00:00:00Z"),
        )
    assert "置き換え済み" in str(exc.value)


def test_apply_turn_fills_superseded_by_from_the_turn_qa():
    """問い直した turn の qa が置き換える側。op.qa_id (旧 entry) は補完で上書きしない。"""
    state = _state()
    state["qa_log"] = state["qa_log"][:1]
    w.apply_turn(
        state,
        {
            "qa_id": "qa-new",
            "question": NEW_Q,
            "answer": "A",
            "basis": "user-decision",
            "answered_at": "2020-01-02T00:00:00Z",
            "ops": [{k: v for k, v in _op().items() if k != "superseded_by"}],
        },
    )
    assert _entry(state, "qa-old")["superseded_by"] == "qa-new"


def test_turn_cannot_write_supersession_keys_directly():
    """turn の未知キーは読み飛ばされるので、置き換え欄を書いたつもりで黙って失われる。"""
    state = _state()
    with pytest.raises(w.TransitionError) as exc:
        w._upsert_qa_entry(state, "qa-old", {"superseded_by": "qa-new"})
    assert "supersede-qa" in str(exc.value)


# --------------------------------------------------------------------------- #
# 2. compile: 逐語を章の構造にしない / 旧版の印 / 承認を名指しする質疑           #
# --------------------------------------------------------------------------- #
# 以下の検査は compile の内部関数 (_fence_mask など) を使わず、この検査専用の走査で
# 「フェンスの外にある行」を数える。実装の走査を使うと、実装が誤れば検査も同じく誤る。
_FENCE_OPEN_T = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_QA_HEAD_T = re.compile(r"^####\s+(主たる接地根拠|裏付け質疑|この承認を名指ししている質疑):\s+`([^`]+)`")
_ANY_HEAD_T = re.compile(r"^ {0,3}#{1,6}[ \t]+\S")


def _outside_fence(text: str) -> list[str]:
    """閉じたフェンスの外にある行を返す (閉じないフェンスはフェンスとみなさない)。"""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = _FENCE_OPEN_T.match(lines[i])
        if m:
            mark = m.group(1)
            close = re.compile(r"^ {0,3}" + re.escape(mark[0]) + "{" + str(len(mark)) + r",}[ \t]*$")
            end = next((k for k in range(i + 1, len(lines)) if close.match(lines[k])), None)
            if end is not None:
                i = end + 1
                continue
        out.append(lines[i])
        i += 1
    return out


def _heading_lines_of_spec(spec: dict) -> set[str]:
    texts: list[str] = []
    for e in spec.get("qa_log") or []:
        texts += [e[k] for k in ("question", "answer", "provenance") if isinstance(e.get(k), str)]
        texts += [x["note"] for x in e.get("corrections") or [] if isinstance(x.get("note"), str)]
    texts += [a["note"] for a in spec.get("approval_log") or [] if isinstance(a.get("note"), str)]
    return {line.strip() for t in texts for line in t.splitlines() if _ANY_HEAD_T.match(line)}


def _leaked(text: str, spec: dict) -> list[str]:
    """フェンスの外で見出しになっている、spec-state の逐語の行。"""
    verbatim = _heading_lines_of_spec(spec)
    return [line.strip() for line in _outside_fence(text) if line.strip() in verbatim]


def _duplicated_qa_headings(text: str) -> dict[str, int]:
    heads = [line.strip() for line in _outside_fence(text) if _QA_HEAD_T.match(line)]
    return {h: heads.count(h) for h in set(heads) if heads.count(h) > 1}


OLD_I7 = "再試行を、失敗した明細にだけ出す"
LEAKY_ANSWER = (
    "承認する。改めた後の文面は次のとおり。\n"
    "### U1 本質的な目的\n"
    "選んだ明細を一括で確定できるようにする。\n"
    "### U9 具体的にやりたいこと\n"
    f"- **I7** {OLD_I7}。"
)


def _chapter_spec(refs=("qa-main", "qa-leaky", "qa-after")) -> dict:
    """web だけ確定 (qa_ref=qa-main)、他 5 platform は理由付きの対象外。"""
    matrix = {
        "backend": {
            "web": {"state": "確定", "qa_ref": "qa-main", "qa_refs": list(refs), "serves_goals": ["G1"]}
        }
    }
    for pf in PLATFORMS[1:]:
        matrix["backend"][pf] = {"state": "対象外", "reason": "配信対象外"}
    return {
        "categories": [{"id": "backend", "label": "テスト章"}],
        "platforms": PLATFORMS,
        "matrix": matrix,
        "qa_log": [
            {"id": "qa-main", "question": "主の問の本文", "answer": "主の答の本文",
             "basis": "user-decision", "answered_at": "2020-01-01T00:00:00Z"},
            {"id": "qa-leaky", "question": "10 項目の文面を改めますか", "answer": LEAKY_ANSWER,
             "basis": "user-decision", "answered_at": "2020-01-02T00:00:00Z",
             "corrections": [{"corrected_at": "2020-01-03T00:00:00Z", "note": "I7 の文面は後の問で改めた"}]},
            {"id": "qa-after", "question": "後続の問の本文", "answer": "後続の答の本文",
             "basis": "user-decision", "answered_at": "2020-01-04T00:00:00Z"},
        ],
        "approval_log": [],
        "category_aggregate": {},
        "targets": [],
        "decisions": [],
        "requirements_foundation": {
            "goals": [{"id": "G1", "text": "ゴール本文"}],
            "objectives": [{"id": "O1", "text": "目標本文", "measure": "観測点本文", "serves": ["G1"]}],
            "concrete_intents": [{"id": "I1", "text": "やりたいこと本文", "serves": ["G1"]}],
            "confirmed": True,
        },
    }


def test_heading_lines_in_an_answer_stay_inside_a_fence():
    """answer の行頭 `###` を章の見出しにしない。逐語はエスケープせずそのまま残す。"""
    spec = _chapter_spec()
    chapter = c.render_chapter(spec, "backend", {})
    assert _leaked(chapter, spec) == [], "answer の見出し行が章の見出しとして漏れている"
    assert "### U1 本質的な目的" in chapter and OLD_I7 in chapter, "逐語を消す・書き換えることで漏れを防いではならない"


def test_a_fence_inside_the_verbatim_does_not_close_the_outer_fence():
    """逐語がフェンスを含んでも、逐語全体が 1 つのフェンスに収まる。

    外側のフェンスを 3 連のバッククォートで固定すると、逐語の中のフェンス行で先に閉じ、
    その後ろの行が章の本文 (見出しを含む) として出る。
    """
    answer = "### 前の見出し風\n```\nフェンス内のコード行\n```\n### 後ろの見出し風"
    spec = _chapter_spec()
    spec["qa_log"][1]["answer"] = answer
    outside = {line.strip() for line in _outside_fence(c.render_chapter(spec, "backend", {}))}
    for line in answer.splitlines():
        assert line not in outside, f"逐語の行がフェンスの外に出ている: {line!r}"


def test_multiline_correction_note_stays_inside_the_quote():
    """訂正 note の 2 行目以降も引用の中に置く (引用の外へ出た `#` 行は章の見出しになる)。"""
    spec = _chapter_spec()
    spec["qa_log"][1]["corrections"] = [
        {"corrected_at": "2020-01-03T00:00:00Z", "note": "1 行目の訂正\n### 見出し風の訂正の 2 行目"}
    ]
    chapter = c.render_chapter(spec, "backend", {})
    outside = {line.strip() for line in _outside_fence(chapter)}
    assert "### 見出し風の訂正の 2 行目" not in outside, "訂正 note の 2 行目が引用の外で見出しになっている"
    assert "見出し風の訂正の 2 行目" in chapter


def test_structured_provenance_is_fenced_not_inlined_into_the_meta_line():
    spec = _chapter_spec()
    spec["qa_log"][1]["provenance"] = "AskUserQuestion\n### 提示した選択肢\n- A: 利点と不利な点\n- B: 利点と不利な点"
    chapter = c.render_chapter(spec, "backend", {})
    outside = {line.strip() for line in _outside_fence(chapter)}
    assert "### 提示した選択肢" not in outside, "出所の見出し行が章の見出しとして漏れている"
    assert "### 提示した選択肢" in chapter


def test_superseded_entry_is_rendered_as_an_old_version_with_its_replacement():
    """置き換え済みの qa は「旧版（置き換え先: <qa_id>）」の印付きで、問答をフェンスに入れて描く。"""
    spec = _chapter_spec(refs=("qa-main", "qa-old"))
    spec["qa_log"] += [
        {"id": "qa-old", "question": OLD_Q, "answer": "A", "basis": "user-decision",
         "answered_at": "2020-01-05T00:00:00Z",
         "superseded_by": "qa-new", "superseded_at": "2020-01-07T00:00:00Z",
         "superseded_note": "A に推奨の印があった (N1)。同じ論点を中立に問い直した"},
        {"id": "qa-new", "question": NEW_Q, "answer": "A", "basis": "user-decision",
         "answered_at": "2020-01-06T00:00:00Z"},
    ]
    chapter = c.render_chapter(spec, "backend", {})
    assert "#### 裏付け質疑: `qa-old` — 旧版（置き換え先: `qa-new`）" in chapter
    assert "A に推奨の印があった (N1)" in chapter, "置き換えの理由が章に無い"
    assert OLD_Q in chapter, "旧版の問を章から消してはならない (凍結された記録)"
    assert OLD_Q not in {line.strip() for line in _outside_fence(chapter)}, "旧版の問が現行の問と同じ見た目で出ている"


def _approval_chapter_spec(note: str = "範囲の承認") -> dict:
    """対象外 5 セルが appr-1 を引用し、どのセルからも参照されない qa-scope がそれを名指しする。"""
    spec = _chapter_spec(refs=("qa-main",))
    for pf in PLATFORMS[1:]:
        spec["matrix"]["backend"][pf]["approval_ref"] = "appr-1"
    spec["approval_log"] = [{"id": "appr-1", "note": note}]
    spec["qa_log"].append(
        {"id": "qa-scope", "question": "対象をどこまでにしますか", "answer": "web のみ",
         "basis": "user-decision", "answered_at": "2020-01-02T00:00:00Z",
         "provenance": "AskUserQuestion (appr-1 として記録)"}
    )
    return spec


def test_a_qa_that_only_names_the_approval_is_not_called_an_old_version():
    """セルから参照されていないだけの qa を「R4-reopen で差し替えられた旧版」と書かない。

    reopen_log は外した qa の id を持たないので、reopen で外れたのか初めから裏付けに
    入っていなかったのかを記録から区別できない。証明できない来歴を書かず、本文と
    「参照されていない」という事実を描く。
    """
    spec = _approval_chapter_spec()
    chapter = c.render_chapter(spec, "backend", {})
    assert "R4-reopen で差し替えられた旧版" not in chapter
    assert "対象をどこまでにしますか" in chapter, "承認の実体である問答の本文が章に無い"
    assert "参照状況" in chapter


def test_superseded_qa_naming_the_approval_carries_the_old_version_mark():
    spec = _approval_chapter_spec()
    spec["qa_log"][-1].update(
        superseded_by="qa-scope-new", superseded_at="2020-01-09T00:00:00Z", superseded_note="片側だけの不利益 (N2)"
    )
    spec["qa_log"].append(
        {"id": "qa-scope-new", "question": "対象の範囲を選んでください (利点と不利な点を対称に提示)",
         "answer": "web のみ", "basis": "user-decision", "answered_at": "2020-01-08T00:00:00Z",
         "provenance": "AskUserQuestion (appr-1 の問い直し)"}
    )
    chapter = c.render_chapter(spec, "backend", {})
    assert "#### この承認を名指ししている質疑: `qa-scope` — 旧版（置き換え先: `qa-scope-new`）" in chapter
    assert "#### この承認を名指ししている質疑: `qa-scope-new`" in chapter


def test_structured_approval_note_is_fenced():
    spec = _approval_chapter_spec(note="範囲の承認\n### 承認した範囲\n- web のみ")
    chapter = c.render_chapter(spec, "backend", {})
    assert _leaked(chapter, spec) == []
    assert "### 承認した範囲" in chapter


def test_split_blocks_does_not_cut_inside_a_fence():
    """フェンスの中の `###` 行はブロックの境界にしない (保存則の分割単位を逐語で切らない)。"""
    body = "### 本物の見出し\n\n```text\n### フェンスの中\n```\n\n本文\n"
    blocks = c._split_blocks(body)
    assert [h for h, _ in blocks] == ["### 本物の見出し"]


# ── 移行: 旧 compile が章へ漏らした見出しと重複ブロックを片付ける ────────────────
# 旧 compile は answer を生で流し込んでいた。漏れた `### U1 …` が ### ブロックを途中で
# 切り、qa がセルの参照から外れた後の再生成で、漏れ見出し以降 (後続の質疑小節を含む) が
# 「見出しの違う既存ブロック」として _preserved_blocks に引き継がれ、同じ質疑が節内に
# 2 度出ていた。漏れ見出しを消失として数えないだけでも、フェンスで囲むだけでも片付かない。
MIGRATION_LEFTOVER = f"""### U1 本質的な目的

選んだ明細を一括で確定できるようにする。

### U9 具体的にやりたいこと

- **I7** {OLD_I7}。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 回答時刻: 2020-01-02T00:00:00Z)

#### 裏付け質疑: `qa-after`

**問**

後続の問の本文

**答**

後続の答の本文

### 手書きの補足

人が書いた補足の本文。

#### 人が書いた小節

人の小節の本文。

### U2 背景

人が書いた、逐語ではない U2 の節。
"""

HUMAN_SECTION = """## 運用メモ

#### 人の見出し

人が書いた運用メモ。
"""


def _write_inputs(tmp_path: Path, spec: dict, chapter: str) -> tuple[list[str], Path]:
    import json

    spec_path = tmp_path / "spec-state.json"
    refs_path = tmp_path / "fetched-references.json"
    out = tmp_path / "out"
    out.mkdir()
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    refs_path.write_text(json.dumps({"references": []}), encoding="utf-8")
    (out / "backend.md").write_text(chapter, encoding="utf-8")
    argv = ["compile", "--spec", str(spec_path), "--references", str(refs_path), "--out-dir", str(out)]
    return argv, out / "backend.md"


def _leaky_old_chapter(spec: dict) -> str:
    """旧 compile が出していた形の章: 確定内容節の末尾に漏れた残骸と人の節が溜まっている。"""
    fresh = c.render_chapter(spec, "backend", {})
    head, sep, tail = fresh.partition("\n## To-Be / Delta")
    assert sep, "確定内容節の次の節が見つからない (fixture の前提)"
    return head.rstrip("\n") + "\n\n" + MIGRATION_LEFTOVER + sep + tail.rstrip("\n") + "\n\n" + HUMAN_SECTION


def test_cli_cleans_leaked_headings_and_duplicate_blocks_and_keeps_human_sections(tmp_path):
    """移行経路: 漏れ見出し 0・重複 0 にし、人が書き足した節はすべて残す。2 回目は固定点。"""
    spec = _chapter_spec(refs=("qa-main", "qa-after"))  # qa-leaky はもう参照されていない
    old = _leaky_old_chapter(spec)
    assert _leaked(old, spec) and _duplicated_qa_headings(old), "fixture が移行前の形になっていない"
    argv, chapter_path = _write_inputs(tmp_path, spec, old)

    assert c.main(argv) == 0
    merged = chapter_path.read_text(encoding="utf-8")
    assert _leaked(merged, spec) == [], "漏れた見出しが残っている"
    assert _duplicated_qa_headings(merged) == {}, "同じ質疑が節内に 2 度出ている"
    assert OLD_I7 not in merged, "参照から外れた qa の逐語 (の漏れた残骸) が章に残っている"
    for kept in ("### 手書きの補足", "人が書いた補足の本文。", "#### 人が書いた小節", "人の小節の本文。",
                 "### U2 背景", "人が書いた、逐語ではない U2 の節。", "## 運用メモ", "#### 人の見出し"):
        assert kept in merged, f"人が書き足した記述が消えた: {kept}"

    assert c.main(argv) == 0
    assert chapter_path.read_text(encoding="utf-8") == merged, "移行後の再実行が固定点になっていない"


def test_cli_keeps_a_still_referenced_leaky_answer_once_inside_its_fenced_block(tmp_path, monkeypatch):
    """参照されたままの qa は、逐語が 1 度だけ、その質疑小節 (訂正付き) のフェンスの中に残る。"""
    spec = _chapter_spec()
    with monkeypatch.context() as m:
        # 旧 compile の描き方 (逐語を生で流し込む) で既存章を作る。旧実装には _verbatim が無い。
        m.setattr(c, "_verbatim", lambda value, force_fence=False: [value], raising=False)
        old = c.render_chapter(spec, "backend", {})
    assert _leaked(old, spec), "fixture が漏れた章になっていない"
    argv, chapter_path = _write_inputs(tmp_path, spec, old)

    assert c.main(argv) == 0
    merged = chapter_path.read_text(encoding="utf-8")
    assert _leaked(merged, spec) == []
    assert merged.count(OLD_I7) == 1
    block = merged.split("#### 裏付け質疑: `qa-leaky`", 1)[1].split("\n#### ", 1)[0]
    assert OLD_I7 in block and "**訂正あり**" in block, "逐語が訂正付きの質疑小節の外にある"
    assert not any(OLD_I7 in line for line in _outside_fence(merged))


def _old_compile_chapter(spec: dict, monkeypatch) -> str:
    """旧 compile の描き方 (逐語も出所も、構造を見ずに生で流し込む) で章を作る。"""
    with monkeypatch.context() as m:
        m.setattr(c, "_has_structure", lambda value: False)
        return c.render_chapter(spec, "backend", {})


def test_cli_cleans_a_leak_whose_qa_has_a_multiline_provenance(tmp_path, monkeypatch):
    """出所が複数行の qa の漏れも片付ける (描いた要素は行に割ってから比べる)。

    旧 compile は出所を付帯行の括弧書きへそのまま埋め込んだので、出所が 2 行なら付帯行も
    2 行に割れて章に出る。描いた要素を割らずに比べると、2 行目が spec-state から導けない行に
    見え、漏れた見出しを人の節と取り違えて移行が止まる。
    """
    spec = _chapter_spec()  # qa-leaky を参照していた頃
    spec["qa_log"][1]["provenance"] = "会話ログ\n2 行目の補足"
    old = _old_compile_chapter(spec, monkeypatch)
    assert _leaked(old, spec), "fixture が漏れた章になっていない"
    spec["matrix"]["backend"]["web"]["qa_refs"] = ["qa-main", "qa-after"]  # 参照から外れた
    argv, chapter_path = _write_inputs(tmp_path, spec, old)

    assert c.main(argv) == 0
    assert _leaked(chapter_path.read_text(encoding="utf-8"), spec) == []


def test_cli_cleans_a_heading_leaked_from_a_structured_provenance(tmp_path, monkeypatch):
    """出所そのものの見出しが旧 compile で漏れた章も、人の節と取り違えずに片付ける。

    旧 compile は構造を持つ出所も付帯行へ埋め込んだので、漏れた見出しの直下には
    「最終行 / 回答時刻: …)」という旧書式の付帯行の断片が並ぶ。今の compile は出所を
    フェンスへ出すのでこの行を描かない。旧書式も導ける行に含めないと移行が止まる。
    """
    spec = _chapter_spec(refs=("qa-main", "qa-after"))
    spec["qa_log"][0]["provenance"] = "利用者回答の要約\n### 出所の見出し\n会話ログの 3 行目"
    old = _old_compile_chapter(spec, monkeypatch)
    assert "\n### 出所の見出し\n" in old, "fixture が漏れた章になっていない"
    argv, chapter_path = _write_inputs(tmp_path, spec, old)

    assert c.main(argv) == 0
    assert _leaked(chapter_path.read_text(encoding="utf-8"), spec) == []


def test_duplicate_qa_subblock_is_dropped_even_without_spec():
    """管轄節と同じ (役割, qa id) の質疑小節は、spec が無くても重複として引き継がない。

    人が書いた #### 小節と ### ブロックは残す (compile が出す質疑見出しの形だけが対象)。
    """
    new = NEW_DOC_QA
    old = NEW_DOC_QA.replace(
        "## 後ろの節",
        "### 残骸の見出し\n\n#### 裏付け質疑: `qa-after`\n\n**問**\n\n後続の問\n\n"
        "#### 人の小節\n\n人の本文\n\n## 後ろの節",
    )
    merged = c.merge_preserving(new, old)
    assert _duplicated_qa_headings(merged) == {}
    assert "#### 人の小節" in merged and "人の本文" in merged and "### 残骸の見出し" in merged


NEW_DOC_QA = """---
status: confirmed
---

# 章

## 確定内容 (質疑録)

### Web (web)

#### 裏付け質疑: `qa-after`

**問**

後続の問

## 後ろの節

本文
"""


def test_human_block_sharing_a_heading_with_the_verbatim_still_fails_closed(tmp_path):
    """逐語と同じ字面の見出しでも、人が書いた本文を伴う節は漏れとして片付けない。

    qa の答に `### 補足` の行があるとき、章に人が書いた `### 補足` ブロックを字面だけで
    漏れと判定すると、本文ごと黙って消える (終了コード 0)。見出しの直下に spec-state から
    導けない行があれば人の節なので、消失として止める (書き込まない)。
    """
    spec = _chapter_spec(refs=("qa-main", "qa-after"))
    spec["qa_log"][0]["answer"] = "主の答の本文\n### 補足\n逐語の補足"
    fresh = c.render_chapter(spec, "backend", {})
    head, sep, tail = fresh.partition("\n## To-Be / Delta")
    assert sep, "確定内容節の次の節が見つからない (fixture の前提)"
    old = head.rstrip("\n") + "\n\n### 補足\n\n人が書いた補足の本文。\n" + sep + tail
    argv, chapter_path = _write_inputs(tmp_path, spec, old)
    assert c.main(argv) == 1
    assert chapter_path.read_text(encoding="utf-8") == old, "人の節を消す再生成を書き込んでいる"


def test_removing_a_human_heading_still_fails_closed(tmp_path):
    """逐語の漏れを消失に数えない例外が、人の見出しの消失まで通さないこと (新旧で同じ)。

    再生成される ### ブロックの中に人が書いた #### は引き継がれないので、消失として止まる。
    """
    spec = _chapter_spec(refs=("qa-main", "qa-after"))
    fresh = c.render_chapter(spec, "backend", {})
    old = fresh.replace("#### 裏付け質疑: `qa-after`", "#### 人の注記\n\n人の本文\n\n#### 裏付け質疑: `qa-after`", 1)
    argv, chapter_path = _write_inputs(tmp_path, spec, old)
    assert c.main(argv) == 1
    assert chapter_path.read_text(encoding="utf-8") == old, "消失を伴う再生成を書き込んでいる"
