#!/usr/bin/env python3
# /// script
# name: notion_config
# version: 0.1.0
# purpose: Per-repository Notion 設定 (DB ID / API キー / parent page) を解決する
#          vendored 共有 loader。単独 install でも repo-root 非依存で動く多段フォールバック探索を持つ。
# inputs:
#   - env: NOTION_CONFIG_PATH (最優先) / CLAUDE_PLUGIN_ROOT
#   - files: .notion-config.json (repo-root or plugin-root) / notion-config.fixed.json
# outputs:
#   - return: config dict / DB ID / token を呼び出し側 module へ返す (stdout 出力なし)
#   - exit: なし (import して関数利用する library)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""Per-repository Notion configuration loader (SSOT, vendored into each plugin).

harness-creator / skill-intake に vendoring 実体として同梱され、各環境固有の
Notion DB ID / API キー指定を解決するための唯一の経路。単独 install (plugin 単体)
でも repo-root 非依存で動くよう plugin-root 起点のフォールバック探索を持つ。

解決順 (find_config_path):
  1. env `NOTION_CONFIG_PATH` が指すファイル (最優先・明示。不在なら fail-closed)
  2. repo-root (`.git` AND harness marker を持つ親) 直下の `.notion-config.json`
     (monorepo / 複数 repo 共有時)
  3. plugin-root (`$CLAUDE_PLUGIN_ROOT`、無ければ本ファイルの parents[1]) 直下の
     `.notion-config.json` (単独 install: repo-root marker 不在環境のフォールバック)
  4. plugin-root 直下の `notion-config.fixed.json`
     (単独 install: 固定 Notion ヒアリングシート DB への既定出力先)
  5. いずれも無ければ None を返す（呼び出し側で warn-and-skip / env 明示を促す）

config schema (JSON):
{
  "keychain_service": "notion-api-key.<keychain-prefix>",
  "keychain_account": "<keychain-prefix>",
  "parent_page": {
    "page_id": "11111111-d18c-80bf-9eff-c74aa736645c",
    "page_url": "https://app.notion.com/p/11111111d18c80bf9effc74aa736645c"
  },
  "databases": {
    "skill-list":          {"db_id": "..."},
    "hearing-sheet":       {"db_id": "..."},
    "improvement-request": {"db_id": "..."}
  },
  "schema_dir": "doc/notion-schema"
}

トークン本体は Keychain を正とする。CI / dry-run で `INTAKE_ALLOW_ENV_TOKEN=1`
を明示した場合のみ env `NOTION_TOKEN` を許可する。config には載せない。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Optional

from tenant_runtime import TenantConfigError, credential_ref

CONFIG_FILENAME = ".notion-config.json"
BUNDLED_CONFIG_FILENAME = "notion-config.fixed.json"
SETUP_DOC_REL = "references/notion-per-repo-setup.md (harness-creator or skill-intake plugin)"


REPO_MARKERS = (".notion-config.json", ".notion-config.example.json", "marketplace.json")


def find_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    """Repo-root 探索: .git を上向き走査するが、harness marker (.notion-config.* / marketplace.json)
    のいずれかを持つ root のみ採用。submodule の .git や別 repo の .git に誤ヒットしてグローバル
    config を盗み読むのを防ぐ。
    """
    p = (start or Path.cwd()).resolve()
    for d in [p, *p.parents]:
        if (d / ".git").exists() and any((d / m).exists() for m in REPO_MARKERS):
            return d
    return None


def plugin_root() -> Path:
    """単独 install 時の config 探索アンカー。`$CLAUDE_PLUGIN_ROOT` 優先、無ければ
    本ファイル (plugins/<plugin>/scripts/) の親 = plugin root。repo-root marker
    が存在しない単独 install 環境でも .notion-config.json を解決可能にする。"""
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    return Path(env) if env else Path(__file__).resolve().parents[1]


def find_config_path(start: Optional[Path] = None) -> Optional[Path]:
    # 1. 明示 env (最優先)
    env = os.environ.get("NOTION_CONFIG_PATH")
    if env:
        p = Path(env)
        if p.exists():
            return p
        raise FileNotFoundError(
            f"NOTION_CONFIG_PATH is set but file does not exist: {p}. "
            "Refusing to fall back to another config."
        )
    # 2. repo-root 直下 (monorepo / 複数 repo 共有時)
    root = find_repo_root(start)
    if root and (root / CONFIG_FILENAME).exists():
        return root / CONFIG_FILENAME
    # 3. plugin-root 直下 (単独 install: repo-root marker 不在環境のフォールバック)
    pr = plugin_root()
    if (pr / CONFIG_FILENAME).exists():
        return pr / CONFIG_FILENAME
    # 4. plugin-root 固定設定 (単独 install: ヒアリングシート DB の既定出力先)
    if (pr / BUNDLED_CONFIG_FILENAME).exists():
        return pr / BUNDLED_CONFIG_FILENAME
    return None


def load_config(start: Optional[Path] = None) -> Optional[dict]:
    path = find_config_path(start)
    if not path:
        return None
    with path.open(encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["__path__"] = str(path)
    return cfg


DB_ENV_NAMES = {
    "hearing-sheet": "INTAKE_NOTION_DATABASE_ID",
    "skill-list": "NOTION_DB_SKILL_LIST",
    "improvement-request": "NOTION_DB_IMPROVEMENT_REQUEST",
}

PAGE_ID_ENV_NAME = "INTAKE_NOTION_PARENT_PAGE_ID"


def canonical_notion_id(value: str | None) -> Optional[str]:
    """Notion ID / URL を 8-4-4-4-12 の UUID 形式へ正規化する。

    app.notion.com の database view URL は path 側に view/container ID、query `p` 側に
    page ID を持つ場合があるため、query の `p` / `page_id` を path より優先する。
    """
    if not value:
        return None
    raw = str(value).strip()
    parsed = urlparse(raw)
    if parsed.query:
        query = parse_qs(parsed.query)
        for key in ("p", "page_id"):
            for candidate in query.get(key, []):
                compact = re.sub(r"[^0-9a-fA-F]", "", str(candidate)).lower()
                if len(compact) == 32:
                    return f"{compact[0:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:32]}"
    segment = (parsed.path or raw.split("?")[0].split("#")[0]).rstrip("/").split("/")[-1]
    uuid_match = re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        segment,
    )
    if uuid_match:
        compact = re.sub(r"[^0-9a-fA-F]", "", uuid_match.group(0)).lower()
        return f"{compact[0:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:32]}"
    token = segment.split("-")[-1]
    if re.fullmatch(r"[0-9a-fA-F]{32}", token):
        compact = token.lower()
        return f"{compact[0:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:32]}"
    if re.fullmatch(r"[0-9a-fA-F]{32}", raw):
        compact = raw.lower()
        return f"{compact[0:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:32]}"
    return None


def get_db_id(key: str, start: Optional[Path] = None) -> Optional[str]:
    """DB ID 統一解決: env (key-specific) → .notion-config.json → None。

    全 callsite はこの関数を経由することで、setup-doc が宣言する解決順を全 script で一致させる。
    """
    env_name = DB_ENV_NAMES.get(key)
    if env_name and os.environ.get(env_name):
        return os.environ[env_name]
    cfg = load_config(start)
    if not cfg:
        return None
    return (cfg.get("databases") or {}).get(key, {}).get("db_id")


def get_parent_page_id(start: Optional[Path] = None) -> Optional[str]:
    """親ページ ID 解決: env → .notion-config.json#parent_page → legacy parent_page_id → None。"""
    if os.environ.get(PAGE_ID_ENV_NAME):
        return canonical_notion_id(os.environ[PAGE_ID_ENV_NAME])
    cfg = load_config(start)
    if not cfg:
        return None
    parent = cfg.get("parent_page") or {}
    return (
        canonical_notion_id(parent.get("page_id"))
        or canonical_notion_id(parent.get("page_url"))
        or canonical_notion_id(cfg.get("parent_page_id"))
    )


def get_token(cfg: Optional[dict] = None) -> Optional[str]:
    """Token 解決: Keychain → 明示許可された env NOTION_TOKEN."""
    tok = os.environ.get("NOTION_TOKEN") if os.environ.get("INTAKE_ALLOW_ENV_TOKEN") == "1" else None
    if tok:
        return tok
    service = str((cfg or {}).get("keychain_service") or "").strip()
    account = str((cfg or {}).get("keychain_account") or "").strip()
    if not service or not account:
        try:
            service, account = credential_ref("notion-api-key")
        except TenantConfigError:
            return None
    cmd = ["security", "find-generic-password", "-s", service, "-w"]
    if account:
        cmd[2:2] = ["-a", account]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def warn_missing(stream=sys.stderr) -> None:
    stream.write(
        f"[notion_config] WARN: {CONFIG_FILENAME} not found "
        f"(searched: env NOTION_CONFIG_PATH / repo-root / plugin-root={plugin_root()} / "
        f"bundled {BUNDLED_CONFIG_FILENAME}). "
        f"Notion sync cannot proceed. 単独 install 時は env NOTION_CONFIG_PATH を指すか "
        f"plugin-root 直下に {CONFIG_FILENAME} または {BUNDLED_CONFIG_FILENAME} を用意してください。"
        f"詳細は {SETUP_DOC_REL}。\n"
    )


def require_or_skip(key: str = "", allow_skip: bool = False) -> tuple[Optional[dict], Optional[str]]:
    """便利関数: (cfg, token) を返す。

    fail-closed (デフォルト): config / token / db_id のいずれかが欠ければ stderr に理由を出し
    **exit 2 で停止**する (silent-skip 禁止 / 「出力しない条件を厳格化」)。これにより未設定のまま
    publish が黙ってスキップされ、ヒアリング→skill 生成へ横流れする逸脱を封じる。

    fail-open (明示緩和): `allow_skip=True` (CI smoke / 開発者の dry-run 用) の時のみ、欠落時に
    警告して (None, None) を返す。呼び出し側は緩和時のみ `if not cfg: return 0` でスキップする。
    """
    def _missing(reason: str) -> tuple[Optional[dict], Optional[str]]:
        if allow_skip:
            sys.stderr.write(f"[notion_config] WARN (allow-skip): {reason}. Skipped.\n")
            return None, None
        sys.stderr.write(
            f"[notion_config] FATAL: {reason}. "
            f"必須 Notion 設定が不在のため停止します (緩和には allow_skip=True が必要)。\n"
        )
        sys.exit(2)

    cfg = load_config()
    if not cfg:
        warn_missing()
        return _missing(
            f"{CONFIG_FILENAME} / {BUNDLED_CONFIG_FILENAME} not found "
            "(env NOTION_CONFIG_PATH / repo-root / plugin-root のいずれにも不在)"
        )
    tok = get_token(cfg)
    if not tok:
        return _missing("Notion token unavailable (Keychain, or env NOTION_TOKEN with INTAKE_ALLOW_ENV_TOKEN=1)")
    if key and not get_db_id(key):
        return _missing(f"databases.{key}.db_id missing in {cfg['__path__']}")
    return cfg, tok


if __name__ == "__main__":
    cfg = load_config()
    if not cfg:
        warn_missing()
        sys.exit(0)
    print(json.dumps({k: v for k, v in cfg.items() if k != "__path__"}, indent=2, ensure_ascii=False))
    print(f"# loaded from: {cfg['__path__']}")
