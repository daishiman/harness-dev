"""notion-gmail-send 共有ライブラリ。

決定論的な処理 (Notion 取得・置換・MIME 組立・plan 生成・send_guard・冪等ログ・
preflight 検証) を提供する。LLM 判断・人間承認は各 skill (run-*) が担い、本パッケージは
副作用の安全装置 (send_guard / 事前予約つき冪等ログ) と純粋ロジックのみを持つ。
"""

__all__ = [
    "render_substitute",
    "message_assemble",
    "plan_build",
    "send_guard",
    "notion_config",
    "secrets",
    "notion_client",
    "idempotent_log",
    "gmail_client",
    "preflight",
]
