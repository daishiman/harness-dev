#!/usr/bin/env python3
# /// script
# name: render_substitute
# purpose: 本文コードブロックおよび件名の {{会社名}}/{{担当者様名}} を宛先DB値で置換し、未置換トークン残存とヘッダインジェクション危険値を fail-closed 検出する純粋ロジック。
# inputs:
#   - template: str (件名 or 本文テンプレート)
#   - values: dict[str,str] (宛先DB由来の差し込み値)
# outputs:
#   - substitute(): (置換後文字列, 未置換トークン名リスト)
#   - unsafe_value_keys(): 改行/制御文字を含む危険値のキー一覧
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""差し込み置換と安全検査 (仕様書 §5)。

置換は純粋関数。未置換 {{...}} 残存と危険値 (CR/LF/制御文字) は呼び出し側が
skipped_validation(reason=unresolved_token / unsafe_header) として送信前に除外する。
本モジュールは送信判断を持たず、検出結果だけを返す。
"""
from __future__ import annotations

import re

# 二重波括弧トークン。波括弧をネストしない最短一致で抽出する。
TOKEN_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

# ヘッダインジェクションに使われる制御文字。タブ(\x09)も差し込み値としては不正扱い。
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def find_unresolved_tokens(text: str) -> list[str]:
    """text 内に残存する {{...}} トークン名を出現順 (重複排除) で返す。"""
    seen: list[str] = []
    for m in TOKEN_RE.finditer(text or ""):
        name = m.group(1).strip()
        if name not in seen:
            seen.append(name)
    return seen


def is_safe_value(value: str) -> bool:
    """差し込み値が CR/LF/制御文字を含まないか。含めば False (ヘッダインジェクション risk)。"""
    if value is None:
        return True
    return _CONTROL_RE.search(value) is None


def unsafe_value_keys(values: dict) -> list[str]:
    """values のうち危険な (CR/LF/制御文字を含む) キーの一覧を返す。"""
    return [k for k, v in (values or {}).items() if isinstance(v, str) and not is_safe_value(v)]


def substitute(template: str, values: dict) -> tuple[str, list[str]]:
    """template 内の {{key}} を values[key] で置換する。

    空値 (None / "") のキーは置換せず {{key}} のまま残し、未置換トークンとして検出させる
    (仕様書 §5: 置換元が空値の場合も unresolved として送信を止める)。

    Returns:
        (置換後文字列, 置換後に残った未置換トークン名リスト)
    """
    if template is None:
        return "", []

    def _repl(m: re.Match) -> str:
        key = m.group(1).strip()
        v = values.get(key) if values else None
        if v is None or v == "":
            return m.group(0)  # 空値は残す → unresolved として検出される
        return str(v)

    result = TOKEN_RE.sub(_repl, template)
    return result, find_unresolved_tokens(result)
