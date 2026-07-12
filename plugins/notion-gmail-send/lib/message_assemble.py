#!/usr/bin/env python3
# /// script
# name: message_assemble
# purpose: From=本文DB送り主/To=対象者DBメール/CC=本文DB CC をカンマ分割し1通に並列、RFC822/MIME 組立して Gmail API 用 base64url raw 化する。アドレス形式を検証する。
# inputs:
#   - subject/body: str (置換後)
#   - from_addr: str / to_raw: str / cc_raw: str (カンマ区切り可)
# outputs:
#   - assemble(): {raw, to_list, cc_list, multi_to_visible, invalid_addrs}
#   - parse_comma_addrs(): list[str] / validate_email(): bool
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""メッセージ組立 (仕様書 §6)。

To/CC のカンマ区切りは分割し1通に並列する。同一宛先行内 To が複数なら multi_to_visible=True
を立て、呼び出し側が dry-run 警告と承認 echo に含める。不正アドレスを含む組立は invalid_addrs
を返し、呼び出し側が skipped_validation(reason=invalid_to/invalid_cc) として除外する。
"""
from __future__ import annotations

import base64
import re
from email.message import EmailMessage

# 実用的なメールアドレス検証。RFC5322 完全準拠ではなく、ヘッダ安全 + 単一 @ + ドメインに dot。
_EMAIL_RE = re.compile(r"^[^@\s,;:<>\"\\]+@[^@\s,;:<>\"\\]+\.[^@\s,;:<>\"\\]+$")


def parse_comma_addrs(raw: str) -> list[str]:
    """カンマ区切りアドレス文字列を分割し、空要素を除いた list を返す。"""
    if not raw:
        return []
    return [a.strip() for a in raw.split(",") if a.strip()]


def validate_email(addr: str) -> bool:
    """アドレスがヘッダ安全かつ形式的に妥当か。"""
    return bool(_EMAIL_RE.match(addr or ""))


def normalize_cc(cc_list: list[str], to_list: list[str]) -> list[str]:
    """CC を正規化する (本文CC + 秘書CC の結合後に1通のヘッダへ整える。仕様書 §6)。

    - To と重複する CC を除外 (大小無視。同一人物が To と CC に二重で載るのを防ぐ)
    - CC 内の重複を除外 (本文CC と 秘書CC が同一アドレスのケース)
    - 出現順は保持 (content_hash は plan_build 側で sorted 済みのため順序非依存)
    """
    to_lower = {a.lower() for a in to_list}
    seen: set[str] = set()
    out: list[str] = []
    for a in cc_list:
        al = a.lower()
        if al in to_lower or al in seen:
            continue
        seen.add(al)
        out.append(a)
    return out


def cc_suppressed_by_to(cc_list: list[str], to_list: list[str]) -> list[str]:
    """CC のうち To と重複して除外されたアドレスを返す (観測専用・除外挙動は変えない)。

    normalize_cc の安全側除外 (同一人物を To と CC に二重に載せない) を可視化するための純関数。
    秘書addr がプロ人材To と同一の場合、CC からは消えるが沈黙すると運用者が「秘書に届かない」と
    誤解しうるため、dry-run で `cc_suppressed_due_to_to_overlap` 警告として明示する (要件3整合)。
    """
    to_lower = {a.lower() for a in to_list}
    out: list[str] = []
    seen: set[str] = set()
    for a in cc_list:
        al = a.lower()
        if al in to_lower and al not in seen:
            seen.add(al)
            out.append(a)
    return out


def assemble(subject: str, body: str, from_addr: str, to_raw: str, cc_raw: str = "") -> dict:
    """1送信単位の MIME を組み立て、Gmail API 用 base64url raw を返す。

    Returns dict:
        raw: str | None            base64url (invalid_addrs があれば None)
        to_list / cc_list: list[str]
        multi_to_visible: bool     To が複数 = 受信者が互いを見られる
        invalid_addrs: list[str]   不正アドレス (空なら組立成功)
    """
    to_list = parse_comma_addrs(to_raw)
    # CC は本文CC + 秘書CC を結合した文字列で渡される。To と重複/CC内重複を正規化で畳む。
    cc_list = normalize_cc(parse_comma_addrs(cc_raw), to_list)

    invalid: list[str] = []
    if not from_addr or not validate_email(from_addr):
        invalid.append(f"from:{from_addr}")
    if not to_list:
        invalid.append("to:(empty)")
    invalid += [f"to:{a}" for a in to_list if not validate_email(a)]
    invalid += [f"cc:{a}" for a in cc_list if not validate_email(a)]

    multi_to_visible = len(to_list) > 1

    if invalid:
        return {
            "raw": None,
            "to_list": to_list,
            "cc_list": cc_list,
            "multi_to_visible": multi_to_visible,
            "invalid_addrs": invalid,
        }

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject or ""
    msg.set_content(body or "", subtype="plain", charset="utf-8")

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    return {
        "raw": raw,
        "to_list": to_list,
        "cc_list": cc_list,
        "multi_to_visible": multi_to_visible,
        "invalid_addrs": [],
    }
