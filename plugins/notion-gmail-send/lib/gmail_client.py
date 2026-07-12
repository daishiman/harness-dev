#!/usr/bin/env python3
# /// script
# name: gmail_client
# purpose: Google SA鍵で DWD impersonate し、send_guard を内部で必ず通してから Gmail API で1通ずつ送信する。sendAs alias を実APIで検証し、quota/レート制御 (1通1秒+指数バックオフ) と安全停止を行う。
# inputs:
#   - sa_key: dict (service_account) / impersonate_subject: str / 送信単位 + send_guard 引数
# outputs:
#   - GmailClient.verify_sendas()/send_unit() / 例外: GmailUnavailable/QuotaStopped/SendGuardError
# contexts: [C, E]
# network: true   # gmail.googleapis.com への HTTPS のみ
# write-scope: external-email   # 不可逆な外部副作用 (送信)。send_guard 通過時のみ
# dependencies: ["google-auth"]
# requires-python: ">=3.9"
# ///
"""Gmail 送信クライアント (仕様書 §6/§10/§11)。

安全の正本である send_guard を本クライアント内部で必ず呼ぶため、orchestrator が guard を
呼び忘れても送信に到達しない。google-auth 未導入時は GmailUnavailable を上げ、preflight G1 が
fail-closed で GCP 手順へ誘導する (build は外部依存に静的依存しない)。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

try:  # 外部依存。未導入なら preflight G1 が案内する。
    from google.oauth2 import service_account
    import google.auth.transport.requests as _gtr
    _GOOGLE_AVAILABLE = True
except Exception:  # ImportError ほか環境差異
    _GOOGLE_AVAILABLE = False

# send_guard は本パッケージ内 (相対 import と直接 import の双方に耐える)
try:
    from . import send_guard as _sg
except ImportError:  # スクリプトから lib を sys.path 追加して import する場合
    import send_guard as _sg  # type: ignore

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.settings.basic",  # sendAs 検証用
]
# users.messages.send(userId=me=impersonate subject) は送信メールを **その送信者の「送信済み」**
# に自動格納する (Gmail API 仕様)。よって送信履歴は送信者メールボックスに残る (仕様書 §6・D6)。
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
SENDAS_URL = "https://gmail.googleapis.com/gmail/v1/users/me/settings/sendAs"

SendGuardError = _sg.SendGuardError


class GmailUnavailable(Exception):
    """google-auth 未導入 / 認証不能 (G1 で fail-closed)。"""


class QuotaStopped(Exception):
    """quota 枯渇 / レート上限超過による安全停止。サーバ拒否=未送信確定なので残件は再開対象。"""


class SendOutcomeUnknown(Exception):
    """送信成否が不明 (接続/timeout、2xx 受理後のレスポンス処理失敗)。

    Gmail messages.send はクライアント冪等トークンを持たず、リトライは本質的に at-least-once。
    成否不明を rateLimit (=未送信確定) と同様に自動再送すると二重送信になるため、本例外は
    **自動再送せず** unknown_needs_reconcile として手動照合へ回す (§11)。
    """


class GmailClient:
    def __init__(self, sa_key: dict, impersonate_subject: str,
                 rate_delay: float = 1.0, max_retry: int = 3,
                 backoff_initial: float = 2.0, backoff_cap: float = 60.0):
        if not _GOOGLE_AVAILABLE:
            raise GmailUnavailable(
                "google-auth が未導入です。`pip install google-auth` 後に再実行してください "
                "(認証基盤の設定は doc/GCP-Gmail送信設定手順.md 参照)。"
            )
        self._subject = impersonate_subject
        self._rate_delay = rate_delay
        self._max_retry = max_retry
        self._backoff_initial = backoff_initial
        self._backoff_cap = backoff_cap
        try:
            creds = service_account.Credentials.from_service_account_info(
                sa_key, scopes=GMAIL_SCOPES, subject=impersonate_subject)
            creds.refresh(_gtr.Request())
        except Exception as e:  # DWD 未承認 / scope 不許可 / 鍵不正
            raise GmailUnavailable(f"Gmail 認証失敗 (DWD/scope/鍵を確認): {type(e).__name__}") from None
        self._creds = creds

    @property
    def _token(self) -> str:
        if not self._creds.valid:
            self._creds.refresh(_gtr.Request())
        return self._creds.token

    def _get(self, url: str) -> dict:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {self._token}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def verify_sendas(self, from_addr: str) -> bool:
        """From が impersonate 対象自身、または accepted な sendAs alias か検証する。"""
        if from_addr and from_addr.lower() == (self._subject or "").lower():
            return True
        try:
            data = self._get(SENDAS_URL)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            return False
        for s in data.get("sendAs", []):
            if (s.get("sendAsEmail", "").lower() == (from_addr or "").lower()
                    and (s.get("isPrimary") or s.get("verificationStatus") == "accepted")):
                return True
        return False

    def _post_send(self, raw: str) -> str:
        """送信し messageId を返す。

        retry を許すのは **送信前にサーバが拒否したと確定する rateLimit/quota (403/429+rate body) のみ**。
        接続/timeout や 2xx 受理後のレスポンス処理失敗は送信成否が不明なので retry せず
        SendOutcomeUnknown を上げ、自動再送を防ぐ (§11・二重送信防止)。
        """
        body = json.dumps({"raw": raw}).encode("utf-8")
        backoff = self._backoff_initial
        for attempt in range(self._max_retry + 1):
            req = urllib.request.Request(SEND_URL, data=body, method="POST")
            req.add_header("Authorization", f"Bearer {self._token}")
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    payload = resp.read()
            except urllib.error.HTTPError as e:
                detail = ""
                try:
                    detail = e.read().decode("utf-8")
                except Exception:
                    pass
                is_rate = e.code in (403, 429) and ("rateLimit" in detail or "quota" in detail.lower())
                if is_rate and attempt < self._max_retry:
                    time.sleep(min(backoff, self._backoff_cap))
                    backoff *= 2
                    continue
                if is_rate:  # サーバ拒否=未送信確定 → 安全停止 (再開可)
                    raise QuotaStopped(f"quota/レート上限で安全停止 (HTTP {e.code})") from None
                # その他 HTTP エラー: ヘッダ受信前の 4xx/5xx は通常未送信だが、断定できないため
                # クライアント起因(4xx 非rate)のみ未送信扱いの RuntimeError、5xx は成否不明とする
                if 400 <= e.code < 500:
                    raise RuntimeError(f"Gmail send 失敗 HTTP {e.code}: {detail[:200]}") from None
                raise SendOutcomeUnknown(f"Gmail send 応答不明 HTTP {e.code}: {detail[:120]}") from None
            except (urllib.error.URLError, TimeoutError) as e:
                # 接続/timeout = リクエストがサーバに届き処理されたか不明 → 自動再送禁止
                raise SendOutcomeUnknown(f"Gmail send 接続/timeout で成否不明: {type(e).__name__}") from None
            # 2xx 受理。ここからの read/parse 失敗は「送信は成功・messageId 不明」扱い
            try:
                return json.loads(payload.decode("utf-8")).get("id", "")
            except Exception as e:
                raise SendOutcomeUnknown(f"送信受理後のレスポンス解析失敗 (messageId不明): {type(e).__name__}") from None
        raise QuotaStopped("送信リトライ上限超過で安全停止")

    def send_unit(self, raw: str, *, approved_plan_hash: str, plan_hash: str,
                  approved_count: int, actual_count: int,
                  approved_first_to: str, actual_first_to: str,
                  reserved_log_id: str | None, unresolved_tokens: list,
                  from_verified: bool, approved_nonce: str = "", actual_nonce: str = "") -> str:
        """send_guard を必ず通過させてから1通送信する。guard 違反は SendGuardError。

        送信後は呼び出し側がレート間隔を空ける (本メソッドは送信後に rate_delay を sleep)。
        呼び出し側が事前に guard を通していても、本メソッドは送信直前に再度 guard を通す (多層防御)。
        """
        _sg.check(
            approved_plan_hash=approved_plan_hash, plan_hash=plan_hash,
            approved_count=approved_count, actual_count=actual_count,
            approved_first_to=approved_first_to, actual_first_to=actual_first_to,
            reserved_log_id=reserved_log_id, unresolved_tokens=unresolved_tokens,
            from_verified=from_verified, approved_nonce=approved_nonce, actual_nonce=actual_nonce,
        )
        message_id = self._post_send(raw)
        if self._rate_delay > 0:
            time.sleep(self._rate_delay)
        return message_id
