#!/usr/bin/env python3
# /// script
# name: notion_config
# purpose: company-master 用に vendoring した Notion 設定ローダー(DB ID / token 解決の唯一経路, SSOT)。
# inputs:
#   - env: NOTION_CONFIG_PATH / NOTION_TOKEN(INTAKE_ALLOW_ENV_TOKEN=1 時) / *_DB_ID / COMPANY_MASTER_EGRESS_IP
#   - files: .notion-config.json / notion-config.fixed.json
#   - keychain: notion-api-key.<keychain-prefix> / gbizinfo-api-token.<keychain-prefix> / japanpost-da-api.<keychain-prefix>
# outputs:
#   - stdout: loaded config(__main__ 実行時)
#   - api: get_db_id / get_token / get_parent_page_id / get_japanpost_credentials / get_japanpost_egress_ip
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Per-repository Notion configuration loader (SSOT, company-master へ vendoring した実体).

company-master plugin に vendoring 実体として同梱され、企業マスタ DB の
Notion DB ID / API キー指定を解決するための唯一の経路。単独 install (plugin 単体)
でも repo-root 非依存で動くよう plugin-root 起点のフォールバック探索を持つ。
gBizINFO トークン解決 (get_gbizinfo_token) を含む company-master 向け拡張版。

解決順 (find_config_path):
  1. env `NOTION_CONFIG_PATH` が指すファイル (最優先・明示。不在なら fail-closed)
  2. repo-root (`.git` AND harness marker を持つ親) 直下の `.notion-config.json`
     (monorepo / 複数 repo 共有時)
  3. plugin-root (`$CLAUDE_PLUGIN_ROOT`、無ければ本ファイルの parents[1]) 直下の
     `.notion-config.json` (単独 install: repo-root marker 不在環境のフォールバック)
  4. plugin-root 直下の `notion-config.fixed.json`
     (単独 install: 固定の企業マスタ DB への既定出力先)
  5. いずれも無ければ None を返す（呼び出し側で warn-and-skip / env 明示を促す）

config schema (JSON):
{
  "keychain_service": "notion-api-key.<keychain-prefix>",
  "keychain_account": "<keychain-prefix>",
  "databases": {
    "company-master": {"db_id": "..."}
  }
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
SETUP_DOC_REL = "references/README-setup.md (company-master plugin)"


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
    本ファイルから上向きに `.claude-plugin` / `.codex-plugin` を持つ plugin root を探す。
    repo-root marker が存在しない単独 install 環境でも .notion-config.json を解決可能にする。"""
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".claude-plugin").exists() or (parent / ".codex-plugin").exists():
            return parent
    return here.parents[3]


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
    # 4. plugin-root 固定設定 (単独 install: 企業マスタ DB の既定出力先)
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
    "company-master": "COMPANY_MASTER_NOTION_DATABASE_ID",
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


def get_gbizinfo_token(cfg: Optional[dict] = None) -> Optional[str]:
    """gBizINFO API トークン解決: Keychain('gbizinfo-api-token.<keychain-prefix>') のみ。

    リクエストヘッダ X-hojinInfo-api-token で送る。env への平文保持は許可しない
    (Notion token と異なり開発緩和経路を設けない: 公的 API キーの取り扱い厳格化)。
    """
    try:
        service, account = credential_ref("gbizinfo-api-token")
    except TenantConfigError:
        return None
    cmd = [
        "security", "find-generic-password",
        "-s", service,
        "-a", account, "-w",
    ]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        if out.strip():
            return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


# ── 日本郵便 addresszip API 認証 (postal_api の SSOT) ─────────────────────────
JAPANPOST_CLIENT_ID_ACCOUNT = "client_id"
JAPANPOST_SECRET_KEY_ACCOUNT = "secret_key"
JAPANPOST_EGRESS_IP_ACCOUNT = "egress_ip"
JAPANPOST_PROXY_URL_ACCOUNT = "proxy_url"
JAPANPOST_PROXY_TOKEN_ACCOUNT = "proxy_token"
JAPANPOST_BASE_URL_ACCOUNT = "base_url"
JAPANPOST_CLIENT_ID_ENV = "COMPANY_MASTER_JAPANPOST_CLIENT_ID"
JAPANPOST_SECRET_KEY_ENV = "COMPANY_MASTER_JAPANPOST_SECRET_KEY"
COMPANY_MASTER_EGRESS_IP_ENV = "COMPANY_MASTER_EGRESS_IP"
POSTAL_PROXY_URL_ENV = "COMPANY_MASTER_POSTAL_PROXY_URL"
POSTAL_PROXY_TOKEN_ENV = "COMPANY_MASTER_POSTAL_PROXY_TOKEN"
JAPANPOST_BASE_URL_ENV = "COMPANY_MASTER_JAPANPOST_BASE_URL"


def _keychain_password(service: str, account: str) -> Optional[str]:
    """Keychain から generic-password を 1 件読み出す (不在/security 不在は None)。"""
    cmd = ["security", "find-generic-password", "-s", service, "-a", account, "-w"]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        return out.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _japanpost_service() -> Optional[str]:
    try:
        service, _ = credential_ref("japanpost-da-api")
        return service
    except TenantConfigError:
        return None


def get_japanpost_credentials() -> tuple[str, str]:
    """日本郵便 addresszip API の client_id / secret_key を解決する。

    解決順: Keychain service `japanpost-da-api.<keychain-prefix>`、account `client_id` / `secret_key` (優先) →
    env `COMPANY_MASTER_JAPANPOST_CLIENT_ID` / `COMPANY_MASTER_JAPANPOST_SECRET_KEY` (低優先)。
    Keychain を優先するが、Keychain 不在環境 (Linux/コンテナのプロキシ運用: 中央 postal_proxy が
    固定IPで鍵を保持し addresszip を代行する) 向けに env フォールバックを許容する。
    return: (client_id, secret_key)。各値は不在なら ""。
    """
    service = _japanpost_service()
    cid = ((_keychain_password(service, JAPANPOST_CLIENT_ID_ACCOUNT) if service else None)
           or (os.environ.get(JAPANPOST_CLIENT_ID_ENV) or "").strip() or "")
    sec = ((_keychain_password(service, JAPANPOST_SECRET_KEY_ACCOUNT) if service else None)
           or (os.environ.get(JAPANPOST_SECRET_KEY_ENV) or "").strip() or "")
    return (cid, sec)


def has_japanpost_credentials() -> bool:
    cid, sec = get_japanpost_credentials()
    return bool(cid and sec)


def get_japanpost_egress_ip() -> Optional[str]:
    """日本郵便にシステム登録した送信元IP (x-forwarded-for 用) の明示 pin を返す。

    解決順: Keychain `japanpost-da-api.<keychain-prefix>`/`egress_ip` (推奨・env ファイル不使用) →
    env `COMPANY_MASTER_EGRESS_IP` (CI/後方互換の低優先フォールバック)。
    どちらも無ければ None を返し、呼び出し側 (postal_api.resolve_egress_ip) が自動検出へフォールバックする。
    IP 認証のため、pin する場合は API ゲートウェイに登録済みの IP と一致している必要がある。
    """
    service = _japanpost_service()
    kc = _keychain_password(service, JAPANPOST_EGRESS_IP_ACCOUNT) if service else None
    if kc:
        return kc
    return (os.environ.get(COMPANY_MASTER_EGRESS_IP_ENV) or "").strip() or None


def has_egress_ip() -> bool:
    return bool(get_japanpost_egress_ip())


def get_postal_proxy_url() -> Optional[str]:
    """郵便番号取得を中継する中央プロキシの URL。Keychain `japanpost-da-api.<keychain-prefix>`/`proxy_url` → env。

    設定されていれば postal_api はこの URL 経由で検索し、ローカルに日本郵便鍵/送信元IP は不要になる
    (不特定多数・多拠点配布向け: 鍵と IP 登録はプロキシ側=固定IP 1件に集約する)。未設定なら従来の直叩き。
    """
    service = _japanpost_service()
    return ((_keychain_password(service, JAPANPOST_PROXY_URL_ACCOUNT) if service else None)
            or (os.environ.get(POSTAL_PROXY_URL_ENV) or "").strip() or None)


def get_postal_proxy_token() -> Optional[str]:
    """中央プロキシの Bearer トークン (任意・プロキシが通行認証する場合)。Keychain → env。"""
    service = _japanpost_service()
    return ((_keychain_password(service, JAPANPOST_PROXY_TOKEN_ACCOUNT) if service else None)
            or (os.environ.get(POSTAL_PROXY_TOKEN_ENV) or "").strip() or None)


def get_japanpost_base_url() -> Optional[str]:
    """日本郵便 API の接続先ホスト上書き (テスト/stub 環境用)。Keychain `japanpost-da-api.<keychain-prefix>`/`base_url` → env。

    未設定なら postal_api の本番既定 (https://api.da.pf.japanpost.jp) を使う。テスト用 API は別ホスト
    (例 https://stub-...da.pf.japanpost.jp) かつ東京都千代田区のみのため、配線検証時のみ上書きする。
    """
    service = _japanpost_service()
    return ((_keychain_password(service, JAPANPOST_BASE_URL_ACCOUNT) if service else None)
            or (os.environ.get(JAPANPOST_BASE_URL_ENV) or "").strip() or None)


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
    企業マスタへの upsert/backfill が黙ってスキップされる逸脱を封じる。

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
    # 認証情報の有無のみ診断する (値は表示しない)。
    print(f"# japanpost credentials (tenant credential reference): "
          f"{'set' if has_japanpost_credentials() else 'MISSING'}")
    print(f"# egress IP (env {COMPANY_MASTER_EGRESS_IP_ENV}): "
          f"{'set' if has_egress_ip() else 'MISSING'}")
