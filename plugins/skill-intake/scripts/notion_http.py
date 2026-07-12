#!/usr/bin/env python3
"""Notion REST API v1 への薄い wrapper。Notion-Version / Authorization を1箇所に閉じ込める。

token 解決順: 引数 > notion_config (per-repo .notion-config.json の
keychain_service/account 尊重) > keychain_get_secret 既定。
CI / dry-run で `INTAKE_ALLOW_ENV_TOKEN=1` を明示した場合のみ `NOTION_TOKEN` env を許容。
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notion_config  # config/token SSOT loader (本 plugin に同梱。harness-creator 版と byte 一致を lint 検証)
from keychain_get_secret import get_secret, KeychainError

NOTION_VERSION = os.environ.get('INTAKE_NOTION_VERSION', '2022-06-28')
BASE = 'https://api.notion.com/v1'


def _resolve_token():
    """per-repo config (Keychain via cfg.keychain_service/account) > legacy; env token only by opt-in."""
    if os.environ.get('NOTION_TOKEN') and os.environ.get('INTAKE_ALLOW_ENV_TOKEN') == '1':
        return os.environ['NOTION_TOKEN']
    cfg = notion_config.load_config()
    if cfg:
        tok = notion_config.get_token(cfg)
        if tok:
            return tok
    return get_secret()


class NotionHttpError(Exception):
    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


def notion_fetch(path, method='GET', body=None, token=None):
    t = token or _resolve_token()
    headers = {
        'Authorization': f'Bearer {t}',
        'Notion-Version': NOTION_VERSION,
    }
    data = None
    if body is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(f'{BASE}{path}', data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode('utf-8')
            status = resp.status
    except urllib.error.HTTPError as e:
        text = e.read().decode('utf-8', errors='replace') if hasattr(e, 'read') else ''
        status = e.code
        try:
            j = json.loads(text) if text else {}
        except Exception:
            j = {'raw': text}
        msg = f"Notion {method} {path} -> HTTP {status} {j.get('code', '')} {j.get('message', '')}".strip()
        raise NotionHttpError(msg, status=status, body=j)
    try:
        j = json.loads(text) if text else {}
    except Exception:
        j = {'raw': text}
    if status >= 400:
        msg = f"Notion {method} {path} -> HTTP {status}"
        raise NotionHttpError(msg, status=status, body=j)
    return j


def get_database(database_id, **opts):
    return notion_fetch(f'/databases/{database_id}', **opts)


def get_me(**opts):
    return notion_fetch('/users/me', **opts)
