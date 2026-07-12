"""kind→必須 frontmatter キーの散文 (io-contract.md / R3-emit-specs.md) が
コード正本 `specfm.STRUCTURAL_REQUIRED` と一致することを機械強制する (kind-key ドリフト封止)。

2026-06-30 elegant-review (Phase 2 の論理/メタ/システム analyst が独立に収束) で、kind 別
必須キーが `specfm.STRUCTURAL_REQUIRED` (= 唯一 lint が強制する実行可能正本) を io-contract.md
§9 の表と R3-emit-specs.md §2.2 が散文で再掲しており、マトリクス全行 (test_matrix_doc_integrity
が守る) と違い parity ガードが無いため、specfm にキーを足して散文を忘れると無音で乖離する欠陥を
検出した。LLM は散文を読むため、この乖離は生成品質 (再現性) に直結する。

本テストは「specfm の各 required キーが各散文の kind 行に backtick トークンとして現れる」
(forward 方向 specfm ⊆ doc) を機械突合する。

射程の限界 (正直開示):
  - forward 方向のみ縛る。doc が specfm に無い任意キー (例 sub-agent の `(任意)evaluator_pair`)
    を列挙しても fail させない。
  - R3 §2.2 の skill 行は base required 14 を列挙せず `specfm.SKILL_BRIEF_FIELDS` を名指し参照
    する doc-points-to-SSOT 設計のため、R3 では skill のみ「specfm 参照の存在」を確認する
    (io-contract.md 側は 14 キーを全列挙するので forward 突合の対象にする)。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_SKILL_DIR = Path(__file__).resolve().parents[1]
_IO_CONTRACT = _SKILL_DIR / "references" / "io-contract.md"
_R3 = _SKILL_DIR / "prompts" / "R3-emit-specs.md"
_KINDS = ("skill", "sub-agent", "slash-command", "hook", "script")
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _normalize_key(token: str) -> str:
    """backtick トークンを frontmatter キー名へ正規化する (`独自: true` → `独自`)。"""
    return re.split(r"[:( ]", token.strip())[0].strip().lower()


def _kind_line(text: str, kind: str, prefixes: tuple[str, ...]) -> str | None:
    """`**{kind}**` を含み、指定 prefix (表行 '|' / 箇条 '-') で始まる行を返す。"""
    marker = f"**{kind}**"
    for line in text.splitlines():
        stripped = line.lstrip()
        if marker in line and stripped[:1] in prefixes:
            return line
    return None


def _backtick_keys(line: str) -> set[str]:
    return {_normalize_key(t) for t in _BACKTICK_RE.findall(line)}


@pytest.mark.parametrize("kind", _KINDS)
def test_io_contract_kind_keys_match_specfm(kind, specfm_mod):
    """io-contract.md §9 の kind 行が specfm.STRUCTURAL_REQUIRED の全キーを列挙する。"""
    if not _IO_CONTRACT.is_file():
        pytest.skip(f"io-contract.md 不在: {_IO_CONTRACT}")
    line = _kind_line(_IO_CONTRACT.read_text(encoding="utf-8"), kind, ("|",))
    assert line is not None, f"io-contract.md に kind={kind} の表行 (| **{kind}** |) が無い"
    tokens = _backtick_keys(line)
    required = set(specfm_mod.STRUCTURAL_REQUIRED[kind])
    missing = sorted(required - tokens)
    assert not missing, (
        f"io-contract.md §9 の {kind} 行が specfm.STRUCTURAL_REQUIRED のキーを欠落: {missing}\n"
        f"(specfm にキーを足したら io-contract.md §9 の表へ追記すること)"
    )


@pytest.mark.parametrize("kind", [k for k in _KINDS if k != "skill"])
def test_r3_nonskill_kind_keys_match_specfm(kind, specfm_mod):
    """R3-emit-specs.md §2.2 の非 skill kind 箇条が specfm の全キーを列挙する。"""
    if not _R3.is_file():
        pytest.skip(f"R3-emit-specs.md 不在: {_R3}")
    line = _kind_line(_R3.read_text(encoding="utf-8"), kind, ("-", "*"))
    assert line is not None, f"R3-emit-specs.md に kind={kind} の箇条 (- **{kind}**:) が無い"
    tokens = _backtick_keys(line)
    required = set(specfm_mod.STRUCTURAL_REQUIRED[kind])
    missing = sorted(required - tokens)
    assert not missing, (
        f"R3-emit-specs.md §2.2 の {kind} 箇条が specfm.STRUCTURAL_REQUIRED のキーを欠落: {missing}"
    )


def test_r3_skill_delegates_to_specfm():
    """R3 の skill 箇条は 14 キーを列挙せず specfm.SKILL_BRIEF_FIELDS を名指し参照する
    (doc-points-to-SSOT パターン=二重定義回避)。参照が消えたら検出する。"""
    if not _R3.is_file():
        pytest.skip(f"R3-emit-specs.md 不在: {_R3}")
    line = _kind_line(_R3.read_text(encoding="utf-8"), "skill", ("-", "*"))
    assert line is not None, "R3-emit-specs.md に skill 箇条が無い"
    assert "specfm.SKILL_BRIEF_FIELDS" in line, (
        "R3 の skill 箇条が specfm.SKILL_BRIEF_FIELDS への参照を失った "
        "(skill は 14 キー全列挙でなく specfm 名指し参照で SSOT 一本化する設計)"
    )


def test_io_contract_phase_keys_match_specfm(specfm_mod):
    """io-contract.md §9 の phase frontmatter 表が specfm.PHASE_REQUIRED を全キー列挙する。

    per-phase 転換で phase frontmatter 契約は specfm.PHASE_REQUIRED (実行可能正本) と、その
    人間可読 projection である io-contract.md の phase 表に持たれる。specfm にキーを足して散文を
    忘れる drift を forward 方向 (specfm ⊆ doc) で機械突合する。
    """
    if not _IO_CONTRACT.is_file():
        pytest.skip(f"io-contract.md 不在: {_IO_CONTRACT}")
    tokens = {_normalize_key(t) for t in _BACKTICK_RE.findall(_IO_CONTRACT.read_text(encoding="utf-8"))}
    required = set(specfm_mod.PHASE_REQUIRED)
    missing = sorted(required - tokens)
    assert not missing, (
        f"io-contract.md の phase frontmatter 表が specfm.PHASE_REQUIRED のキーを欠落: {missing}\n"
        f"(specfm.PHASE_REQUIRED にキーを足したら io-contract.md §9 の phase 表へ追記すること)"
    )


# ─────────────────── §5 節床 / index 床の doc-parity (島A 再発封鎖) ───────────────────
# 2026-07-02 elegant-review 島A: 機械正本 specfm.PHASE_BODY_SECTIONS は宣言型 8 節へ転換済 (2026-07-02 自足性強化: ドメイン知識/スコープ外を追加)
# なのに文書層 (io-contract §5 表 / R3 / SKILL.md) が旧 4 節のまま取り残される乖離を検出した。
# kind-key と同型の「specfm にだけ手を入れて散文を忘れる」ドリフトを節集合にも機械封鎖する。

_SKILL_MD = _SKILL_DIR / "SKILL.md"
_TOPSORT = _SKILL_DIR / "scripts" / "verify-index-topsort.py"
_SECTION_TOKEN_RE = re.compile(r"`(## [^`]+)`")


def test_io_contract_section5_table_matches_phase_body_sections(specfm_mod):
    """io-contract.md §5 表の節集合 == specfm.PHASE_BODY_SECTIONS (双方向一致)。

    §5 表は「specfm.PHASE_BODY_SECTIONS の人間可読 projection」を自称する完全列挙のため、
    forward (specfm ⊆ doc) だけでなく逆方向 (doc に余剰節が無い) も縛る。表行は行頭
    "| `## " で機械抽出する (表外の節名言及は対象外)。
    """
    if not _IO_CONTRACT.is_file():
        pytest.skip(f"io-contract.md 不在: {_IO_CONTRACT}")
    table_sections = {
        m
        for line in _IO_CONTRACT.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("| `## ")
        for m in _SECTION_TOKEN_RE.findall(line.split("|")[1])
    }
    expected = set(specfm_mod.PHASE_BODY_SECTIONS)
    assert table_sections == expected, (
        f"io-contract.md §5 表が specfm.PHASE_BODY_SECTIONS と乖離: "
        f"specfm-doc={sorted(expected - table_sections)} doc-specfm={sorted(table_sections - expected)}\n"
        "(節集合を変えたら specfm と §5 表を同一変更で更新すること)"
    )


def test_r3_phase_sections_cite_specfm():
    """R3 §2.2 は phase 本文節名を再列挙せず specfm.PHASE_BODY_SECTIONS を名指し参照する
    (引用形一本化=doc-points-to-SSOT。skill 行の SKILL_BRIEF_FIELDS 参照と同型)。参照が
    消えて節名の再列挙へ戻ると本テストでは検出できないため、参照存在そのものを固定する。"""
    if not _R3.is_file():
        pytest.skip(f"R3-emit-specs.md 不在: {_R3}")
    assert "specfm.PHASE_BODY_SECTIONS" in _R3.read_text(encoding="utf-8"), (
        "R3-emit-specs.md が specfm.PHASE_BODY_SECTIONS への参照を失った "
        "(§5 節床は節名再列挙でなく specfm 名指し参照で SSOT 一本化する設計)"
    )


def test_index_sections_enumerated_in_topsort_purpose(specfm_mod):
    """verify-index-topsort.py の purpose 行が INDEX_REQUIRED_SECTIONS を完全列挙する
    (完了チェックリスト追加=7 節化のような節集合変更で docstring が取り残されない)。"""
    assert _TOPSORT.is_file(), f"verify-index-topsort.py 不在: {_TOPSORT}"
    text = _TOPSORT.read_text(encoding="utf-8")
    m = re.search(r"specfm\.INDEX_REQUIRED_SECTIONS=([^)]+)\)", text)
    assert m, "verify-index-topsort.py の purpose 行に INDEX_REQUIRED_SECTIONS= の列挙が無い"
    enumerated = {s.strip() for s in m.group(1).split("/") if s.strip()}
    expected = {s.removeprefix("## ") for s in specfm_mod.INDEX_REQUIRED_SECTIONS}
    assert enumerated == expected, (
        f"verify-index-topsort purpose 行の index 節列挙が specfm と乖離: "
        f"specfm-doc={sorted(expected - enumerated)} doc-specfm={sorted(enumerated - expected)}"
    )


def test_doc_section_tokens_are_known_floor_sections(specfm_mod):
    """io-contract.md / SKILL.md 中の backtick 節名トークン (`## X`) が全て床節集合
    (PHASE_BODY_SECTIONS ∪ INDEX_REQUIRED_SECTIONS) の一員である (⊆ 検査)。

    index 床の完全列挙は文書層に無い (散文記述のみ) ため equality では縛れない — 代わりに
    「文書が言及する節名は必ず実在する床節」の床を敷き、旧節 (`## 実行タスク` / `## 完了条件`
    等) の言及が残存/再混入したら検出する (fail-open でなく語彙床で封鎖)。
    """
    known = set(specfm_mod.PHASE_BODY_SECTIONS) | set(specfm_mod.INDEX_REQUIRED_SECTIONS)
    offenders: list[str] = []
    for doc in (_IO_CONTRACT, _SKILL_MD):
        if not doc.is_file():
            continue
        for token in _SECTION_TOKEN_RE.findall(doc.read_text(encoding="utf-8")):
            if token not in known:
                offenders.append(f"{doc.name}: {token}")
    assert not offenders, (
        "文書が床節集合に無い節名を backtick 言及 (旧節の stale 残存?): " + ", ".join(offenders)
    )


# ─────────────────── GATE_SCRIPTS / BUILDER_STATUS の doc-parity (二重保持台帳の整合) ───────────────────
# specfm 冒頭の二重保持台帳が GATE_SCRIPTS / BUILDER_STATUS の parity test を本ファイルと宣言する。
# 台帳の宣言が虚偽にならないよう、両定数の io-contract projection をここで機械突合する。

_SCRIPT_NAME_RE = re.compile(r"`scripts/([a-z0-9-]+\.py)`")
_BUILDER_ROW_RE = re.compile(r"^\|\s*`([a-z-]+)`\s*\|\s*(executor-backed|contract-only)\s*\|")


def test_io_contract_s11_table_covers_gate_scripts(specfm_mod):
    """io-contract §11 表が specfm.GATE_SCRIPTS の全 script (core+extended) を行として持つ
    (forward: GATE_SCRIPTS ⊆ 表)。表は render/specfm 等の非ゲート同梱 script も併載する完全
    在庫のため equality でなく forward で縛る (総数の散文「検証 10 本」は invocation 数と別)。"""
    if not _IO_CONTRACT.is_file():
        pytest.skip(f"io-contract.md 不在: {_IO_CONTRACT}")
    parts = _IO_CONTRACT.read_text(encoding="utf-8").split("## §11", 1)
    assert len(parts) == 2, "io-contract.md に §11 見出しが無い (決定論検査スクリプト表の置き場)"
    table_scripts = set(_SCRIPT_NAME_RE.findall(parts[1]))
    gate_names = {
        name for group in specfm_mod.GATE_SCRIPTS.values() for name, _args in group
    }
    missing = sorted(gate_names - table_scripts)
    assert not missing, (
        f"io-contract.md §11 表が specfm.GATE_SCRIPTS の script 行を欠落: {missing}\n"
        "(GATE_SCRIPTS へ script を足したら §11 表へ行を追記すること)"
    )


def test_io_contract_builder_resolution_table_matches_builder_status(specfm_mod):
    """io-contract §9 build handoff 契約「builder → 実行手段の解決表」が specfm.BUILDER_STATUS
    と双方向一致する (builder 名と executor-backed/contract-only の status 両方)。島C の
    contract-only 可視化が文書層で取り残される drift を機械封鎖する。"""
    if not _IO_CONTRACT.is_file():
        pytest.skip(f"io-contract.md 不在: {_IO_CONTRACT}")
    doc_map = {
        m.group(1): m.group(2)
        for line in _IO_CONTRACT.read_text(encoding="utf-8").splitlines()
        if (m := _BUILDER_ROW_RE.match(line.strip()))
    }
    expected = dict(specfm_mod.BUILDER_STATUS)
    assert doc_map == expected, (
        f"io-contract.md builder 解決表が specfm.BUILDER_STATUS と乖離: "
        f"doc={doc_map} specfm={expected}\n"
        "(builder 語彙/実体性を変えたら specfm と解決表を同一変更で更新すること)"
    )


def test_parity_guard_catches_drift(specfm_mod):
    """本ガードが「specfm にキーを足して散文を忘れた」drift を確かに検出する回帰固定。"""
    required = set(specfm_mod.STRUCTURAL_REQUIRED["hook"])
    # 正例: 全キーが散文行に在る → 欠落なし
    good = "| **hook** | `event`/`matcher`/`exit_semantics`/`settings_wiring`/`fail_closed: true` |"
    assert not (required - _backtick_keys(good))
    # 負例: specfm に新キー `new_required` を足したのに散文が欠く → 検出される
    drifted = required | {"new_required"}
    assert sorted(drifted - _backtick_keys(good)) == ["new_required"]
