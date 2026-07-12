#!/usr/bin/env python3
# /// script
# name: slack_common
# purpose: Slack Bot Token を Keychain から取得する共通経路。slack_notify/slack_poll の重複_tokenを一本化(SSOT)。
# inputs:
#   - config(slack_keychain_service/slack_keychain_account)
# outputs:
#   - Slack Bot Token 文字列
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: Slack Bot Token 取得の単一経路(SSOT)。

slack_notify と slack_poll が各自で同一定義していた _token を一本化する。
"""

import keychain_get_secret as kc
from tenant_runtime import credential_ref

DEFAULT_SERVICE = ""
DEFAULT_ACCOUNT = ""


def slack_token(cfg):
    tenant_service, tenant_account = credential_ref("slack-bot-token")
    service = cfg.get("slack_keychain_service") or tenant_service
    account = cfg.get("slack_keychain_account") or tenant_account
    return kc.get_secret(service=service, account=account)
