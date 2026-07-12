#!/usr/bin/env python3
"""verdict 語彙 SSOT (schemas/verdict-mapping.json) と engine の配線 parity ガード。

engine (lib/mfk_reconcile.py) が emit しうる全 internal_verdict が SSOT に定義済みであること、
CHECK_VERDICTS (AI が ✓ を付けてよい集合) が ai_check:true から派生していること
(ハードコードでないこと) を機械的に保証する。新 verdict を engine に足して mapping へ
登録し忘れる配線漏れを fail-fast で検出する。
"""
import os
import re

import mfk_reconcile as R

ENGINE_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "lib", "mfk_reconcile.py")


def _engine_verdict_literals():
    """engine ソースから emit される verdict 文字列リテラルを静的抽出する。

    `rec["verdict"] = "XXX"` と orphan 等の `"verdict": "XXX"` の両形を拾う。
    """
    with open(ENGINE_SRC, encoding="utf-8") as fh:
        src = fh.read()
    found = set()
    found |= set(re.findall(r'\["verdict"\]\s*=\s*"([A-Z][A-Z_]+)"', src))
    found |= set(re.findall(r'"verdict":\s*"([A-Z][A-Z_]+)"', src))
    return found


def test_engine_emits_only_mapped_verdicts():
    """engine が emit する全 verdict ⊆ verdict-mapping.json の internal_verdict。"""
    mapping = R.load_verdict_mapping()
    assert mapping, "verdict-mapping.json が読めていない (SSOT 解決失敗)"
    emitted = _engine_verdict_literals()
    # 主要 verdict が実際に抽出できている (回帰で正規表現が空振りしないこと)
    assert {"MATCH_MONTHLY", "GAP", "ORPHAN", "REVIEW_METERED"} <= emitted
    missing = emitted - set(mapping.keys())
    assert not missing, f"mapping 未登録の engine verdict (配線漏れ): {sorted(missing)}"


def test_mapping_has_no_dead_spec_verdicts():
    """逆方向 parity: mapping の全 internal_verdict は engine が実際に emit する。

    『宣言したが engine が一切 emit しない』dead-spec (例: 単月では算出不能な STALE) を
    fail-fast で検出する。SUPPRESS_ONESHOT 等も静的抽出に現れるため、現状この差は空。
    新 verdict を mapping に足したが engine 配線を忘れた / 配線を消したが mapping に
    残した、の双方を前方 (test_engine_emits_only_mapped_verdicts) と対で封鎖する。
    """
    mapping = R.load_verdict_mapping()
    assert mapping, "verdict-mapping.json が読めていない (SSOT 解決失敗)"
    emitted = _engine_verdict_literals()
    dead = set(mapping.keys()) - emitted
    assert not dead, f"engine が emit しない mapping verdict (dead-spec): {sorted(dead)}"


def test_check_verdicts_derived_from_ai_check():
    """CHECK_VERDICTS は ai_check:true から派生し、別定義のハードコードでない。"""
    mapping = R.load_verdict_mapping()
    derived = {k for k, v in mapping.items() if v["ai_check"]}
    assert R.check_verdicts() == derived
    assert R.CHECK_VERDICTS == derived  # import 時定数も同一派生
    assert derived, "ai_check:true が 1 つも無い (SSOT 異常)"
    # 各メンバが本当に ai_check:true であること (逆向きの整合)
    for v in R.CHECK_VERDICTS:
        assert R.is_check_verdict(v) is True
    # 非メンバは ai_check:false
    for k, v in mapping.items():
        if not v["ai_check"]:
            assert R.is_check_verdict(k) is False


def test_judge_label_and_warning_class_lookup():
    """judge_label / warning_class が mapping を引く。未定義は verdict 文字列を返す fail-soft。"""
    assert R.judge_label("GAP") == "発行漏れ"
    assert R.warning_class("GAP") == "重大"
    assert R.judge_label("MATCH_MONTHLY") == "発行確認OK"
    assert R.warning_class("MATCH_MONTHLY") == "なし"
    assert R.judge_label("__UNKNOWN__") == "__UNKNOWN__"
    assert R.warning_class("__UNKNOWN__") == "なし"


def test_warning_classes_within_declared_enum():
    """全 warning_class が宣言済み 4 段 (なし/情報/警告/重大) の範囲内。"""
    import json
    with open(R.VERDICT_MAPPING_PATH, encoding="utf-8") as fh:
        doc = json.load(fh)
    allowed = set(doc["warning_classes"])
    for m in doc["mappings"]:
        assert m.get("warning_class", "なし") in allowed


def test_sheet_label_projection_complete_and_within_5values():
    """シート『判定』5値投影が全 emit verdict で解決できる (ORPHAN のみ None=シート行なし)。"""
    import json
    with open(R.VERDICT_MAPPING_PATH, encoding="utf-8") as fh:
        doc = json.load(fh)
    allowed = set(doc["sheet_labels"])  # 未照合/AIの確認OK/対象外/要確認/発行漏れ
    emitted = _engine_verdict_literals()
    for v in emitted:
        label = R.sheet_label(v)
        if v == "ORPHAN":
            assert label is None, "ORPHAN はシート行が無いため投影しない"
        else:
            assert label in allowed, f"{v} の sheet_label が 5 値外/未定義: {label!r}"
    # 5値の網羅 (未照合は engine 非emit の空状態・残り4値は実 verdict から到達可能)
    assert allowed == {"未照合", "AIの確認OK", "対象外", "要確認", "発行漏れ"}
    reachable = {R.sheet_label(v) for v in emitted if R.sheet_label(v)}
    assert reachable == {"AIの確認OK", "対象外", "要確認", "発行漏れ"}


def test_action_hint_present_for_actionable_verdicts():
    """確認ポイント(action_hint): 『AIの確認OK』のみ空・それ以外(対象外/要確認/発行漏れ/ORPHAN)は非空。

    決定2: 全対象外(SUPPRESS_*)にも『なぜ対象外か』の理由を出す。確認不要で空にするのは
    緑(AIの確認OK=MATCH_*)だけ。これを sheet_label を軸に機械強制する(以前は対象外も空だった)。
    """
    mapping = R.load_verdict_mapping()
    for v, m in mapping.items():
        hint = R.action_hint(v)
        if m["sheet_label"] == "AIの確認OK":
            # 緑(確認OK)だけは確認不要のため確認ポイントは空。
            assert hint == "", f"{v} は確認不要なのに action_hint がある: {hint!r}"
        else:
            # 対象外(なぜ対象外か)・要確認・発行漏れ・ORPHAN(要マスタ登録) は理由/対応を必ず示す。
            assert hint, f"{v} に action_hint(確認ポイント)が無い (sheet_label={m['sheet_label']!r})"


def test_monthly_schema_judge_options_match_mapping():
    """DB2 schema の判定 options は verdict-mapping.json の judge_label distinct と一致する。"""
    import json
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "skills", "run-mf-invoice-reconcile",
                               "schemas", "monthly-check-db.schema.json")
    with open(R.VERDICT_MAPPING_PATH, encoding="utf-8") as fh:
        mapping_doc = json.load(fh)
    with open(schema_path, encoding="utf-8") as fh:
        schema_doc = json.load(fh)
    expected = {m["judge_label"] for m in mapping_doc["mappings"]}
    actual = set(schema_doc["properties"]["判定"]["options"])
    assert actual == expected


def test_load_verdict_mapping_failsoft(tmp_path):
    """存在しないパスは空 dict を返す (import を落とさない fail-soft)。"""
    assert R.load_verdict_mapping(str(tmp_path / "nope.json")) == {}
    # 明示 path 指定はキャッシュしない (既定 path のキャッシュを汚さない)
    assert R.load_verdict_mapping(), "既定 path はキャッシュから有効な mapping を返す"


def test_mapping_keys_unique():
    """internal_verdict キーに重複が無い (SSOT 一意)。"""
    import json
    with open(R.VERDICT_MAPPING_PATH, encoding="utf-8") as fh:
        doc = json.load(fh)
    keys = [m["internal_verdict"] for m in doc["mappings"]]
    assert len(keys) == len(set(keys))
