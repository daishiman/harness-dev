#!/usr/bin/env python3
# /// script
# name: appendix
# purpose: 法人契約書の別紙(別紙1業務内容明細/別紙2業務委託料/別紙3個人情報処分方法)を台帳値から生成する。
# inputs:
#   - 法人契約書 docx Document + 法人台帳 row
# outputs:
#   - 契約書末尾に改ページして別紙を追記(AI記入箇所は黄色維持)
# contexts: [C]
# network: false
# write-scope: local-tmp
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: 法人契約書の別紙生成(標準ライブラリ docx_lib のみ・pip不要)。

法人①ひな形は成果物・納品・検収・遂行場所を本体でなく『別紙1に定める』へ委譲する設計のため、
本体差込だけでは成果物等が未定義のまま提出されてしまう。本モジュールが台帳の別紙列(別紙1_*/別紙2_*/別紙3_*)
から別紙1〜3を生成し、契約書末尾に改ページして追記する。AI記入値は黄色ハイライトで証跡化する。

呼び出しは法人(corporate)かつ『業務内容方式=別紙1に定める』または『料金方式=別紙2参照』または
『個人情報処分方法=別紙3に定める』のいずれかが選択された場合(generate_contracts が判定)。
"""

import re

import docx_lib


def needs_appendix(row):
    """別紙生成が必要か(いずれかの方式が別紙参照)。"""
    return (
        (row.get("業務内容方式", "") or "").strip() == "別紙1に定める"
        or (row.get("料金方式", "") or "").strip() == "別紙2参照"
        or (row.get("個人情報処分方法", "") or "").strip() == "別紙3に定める"
    )


def appendix_warnings(row):
    """別紙生成に必要なデータが空の場合の警告リスト(別紙仕様の検証は appendix の責務)。

    engine から抽出。needs_appendix と同じ判定軸を使うため appendix に集約する。
    """
    if not needs_appendix(row):
        return []
    warnings = []
    if (row.get("業務内容方式", "") or "").strip() == "別紙1に定める" and \
       not (row.get("別紙1_成果物内容") or row.get("業務内容①") or "").strip():
        warnings.append("別紙1を生成するが業務内容(別紙1_成果物内容/業務内容①)が空")
    if (row.get("別紙1_成果物有無", "") or "").strip() == "あり" and \
       not (row.get("別紙1_納品期限") or "").strip():
        warnings.append("別紙1の成果物=ありだが納品期限(別紙1_納品期限)が空")
    return warnings


def _add_page_break(doc):
    p = doc.add_paragraph()
    p.add_run().add_break(docx_lib.PAGE)


def _heading(doc, text):
    p = doc.add_paragraph()
    p.alignment = docx_lib.CENTER
    r = p.add_run(text)
    r.font.bold = True
    return p


def _kv(doc, label, value, highlight=True):
    """「label：value」段落。value は AI 記入として黄色維持(highlight=True)。"""
    p = doc.add_paragraph()
    p.add_run(f"{label}：")
    if value:
        r = p.add_run(str(value))
        if highlight:
            r.font.highlight_color = docx_lib.YELLOW
    return p


def append_appendices(doc, row):
    """法人契約書 doc の末尾に必要な別紙を追記。returns 生成した別紙番号リスト。"""
    made = []
    method = (row.get("業務内容方式", "") or "").strip()
    fee = (row.get("料金方式", "") or "").strip()
    priv = (row.get("個人情報処分方法", "") or "").strip()

    if method == "別紙1に定める":
        _add_page_break(doc)
        _heading(doc, "別紙１（業務内容明細）")
        _kv(doc, "１．業務内容", row.get("別紙1_成果物内容") or row.get("業務内容①", ""))
        _kv(doc, "２．業務遂行場所", row.get("別紙1_遂行場所", ""))
        has = (row.get("別紙1_成果物有無", "") or "").strip()
        _kv(doc, "３．成果物の有無", has)
        if has == "あり":
            _kv(doc, "４．成果物の内容", row.get("別紙1_成果物内容", ""))
            _kv(doc, "５．納品期限", row.get("別紙1_納品期限", ""))
            _kv(doc, "６．検収期間", _suffix(row.get("別紙1_検収期間", ""), "営業日以内"))
        made.append("別紙1")

    if fee == "別紙2参照":
        _add_page_break(doc)
        _heading(doc, "別紙２（業務委託料）")
        detail = row.get("別紙2_料金明細", "")
        if detail:
            _kv(doc, "業務委託料の内訳", detail)
        else:
            _kv(doc, "業務委託料", _yen(row.get("金額", "")))
        made.append("別紙2")

    if priv == "別紙3に定める":
        _add_page_break(doc)
        _heading(doc, "別紙３（個人情報の処分方法）")
        _kv(doc, "処分方法", row.get("別紙3_個人情報処分方法") or "甲の指示に従い返却又は廃棄する")
        made.append("別紙3")

    return made


def _suffix(v, suf):
    v = (v or "").strip()
    return f"{v}{suf}" if v and not v.endswith(suf) else v


def _yen(v):
    n = re.sub(r"[^\d]", "", str(v or ""))
    return f"金{int(n):,}円（消費税抜）" if n else ""
