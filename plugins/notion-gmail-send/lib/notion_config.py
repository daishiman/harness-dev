#!/usr/bin/env python3
# /// script
# name: notion_config
# purpose: 作業フォルダ($CLAUDE_PROJECT_DIR 直下。clone は repo-root) の .notion-config.json (gitignore 対象) を SSOT として解決し、Notion DB ID / 送信元設定を返す。不在時は placeholder 雛形を生成する scaffold も提供。symlink 共有プラグインでも install パス非依存で動く。
# inputs:
#   - env: NOTION_GMAIL_CONFIG / NOTION_CONFIG_PATH (任意) / CLAUDE_PROJECT_DIR (任意)
#   - file: .notion-config.json
# outputs:
#   - load_config(): dict / get_db_id(name): str / get_sender(): dict
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""Notion 設定ローダー (per-repo config SSOT)。

DB ID や送信元ドメインなど環境依存の固有値は作業フォルダ($CLAUDE_PROJECT_DIR 直下。
clone 開発者は repo-root)の .notion-config.json に分離し、コードには直書きしない
(仕様書 §3 取得時の確定事項・abstraction_variables)。探索順は
明示パス(--config) > env(NOTION_GMAIL_CONFIG) > CLAUDE_PROJECT_DIR > __file__ から上位ディレクトリ走査 > CWD。

config 不在の初回は ConfigError で fail-closed する。前進手段として placeholder 雛形を
$CLAUDE_PROJECT_DIR 直下へ書き出す scaffold (write_skeleton / skeleton_json) を提供する。
placeholder 値 (<...>) は解決不能なので、生成直後でも実値を埋めるまで送信できない (fail-closed 維持)。
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

CONFIG_FILENAME = ".notion-config.json"

# placeholder config の唯一の真実源 (SSOT)。
# (1) .notion-config.example.json / (2) write_skeleton が生成する雛形 /
# (3) ConfigError が印字する貼り付け用 JSON は、すべてこの定数から導く。
# 実 DB ID・実送信元は決してここに置かない (git 追跡ファイルへの実値拡散を機構的に防ぐ)。
CONFIG_SKELETON: dict = {
    "_comment": (
        "作業フォルダ($CLAUDE_PROJECT_DIR 直下。clone 開発者は repo-root)に "
        ".notion-config.json として置き、<...> を実値で埋める (.notion-config.json は gitignore 対象)。"
        "db_id は Notion ページURL末尾の32桁。雛形を自動生成するには doctor --init を実行。"
    ),
    "databases": {
        "gmail-send-log": {
            "db_id": "<送信ログDBのid>",
            "_note": "送信ログDB。run-notion-gmail-sendlog-setup でプロパティを §9 schema に整える",
        }
    },
    "notion_gmail_send": {
        "source": {
            "body_db": "<メール本文DBのid>",
            "recipient_db": "<メール送信先_DBのid>",
            "_note": "body_db=メール本文_DB / recipient_db=メール送信先_DB",
        },
        "sender": {
            "impersonate": "<送信元アドレス @your-domain>",
            "sa_keychain": {"service": "google-sa.<keychain-prefix>", "account": "<keychain-prefix>"},
            "_note": (
                "impersonate=DWDで成りすます送信元(本文DB『メールの送り主』と一致 or sendAs alias)。"
                "実値は git に載せず config にのみ置く。"
                "sa_keychain=Google SA鍵JSONを格納した Keychain の service/account"
            ),
        },
    },
}


class ConfigError(Exception):
    """設定不在 / キー欠落 (G2 で fail-closed させる)。"""


def _candidate_paths(explicit_path: str | os.PathLike[str] | None = None) -> list[Path]:
    cands: list[Path] = []
    if explicit_path:
        cands.append(Path(explicit_path))
    env = os.environ.get("NOTION_GMAIL_CONFIG")
    if env:
        cands.append(Path(env))
    tenant_env = os.environ.get("NOTION_CONFIG_PATH")
    if tenant_env:
        cands.append(Path(tenant_env))
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        cands.append(Path(proj) / CONFIG_FILENAME)
    # __file__ から上位を走査 (repo-root を見つける)
    here = Path(__file__).resolve()
    for parent in here.parents:
        cands.append(parent / CONFIG_FILENAME)
    cands.append(Path.cwd() / CONFIG_FILENAME)
    # 重複排除 (順序保持)
    seen: set[str] = set()
    uniq: list[Path] = []
    for c in cands:
        s = str(c)
        if s not in seen:
            seen.add(s)
            uniq.append(c)
    return uniq


def find_config_path(explicit_path: str | os.PathLike[str] | None = None) -> Path | None:
    for c in _candidate_paths(explicit_path):
        if c.is_file():
            return c
    return None


def load_config(path: str | os.PathLike[str] | None = None) -> dict:
    """.notion-config.json を読み込む。不在なら ConfigError。"""
    resolved = find_config_path(path)
    if resolved is None:
        target = f"指定パス {path}" if path else CONFIG_FILENAME
        raise ConfigError(
            f"{target} が見つかりません。作業フォルダ($CLAUDE_PROJECT_DIR 直下。"
            f"clone 開発者は repo-root)に作成してください。雛形を自動生成するには "
            f"doctor --init を実行できます (例は .notion-config.example.json)。"
        )
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError(f"{resolved} の読み込みに失敗: {e}") from e


def get_db_id(name: str, config: dict | None = None) -> str:
    """databases.<name>.db_id を返す。未解決なら ConfigError (G2 で送信中断)。"""
    cfg = config if config is not None else load_config()
    databases = cfg.get("databases") or {}
    if not isinstance(databases, dict):
        raise ConfigError("databases は {name: {db_id: ...}} 形式の dict である必要があります "
                          "(.notion-config.example.json 参照)。")
    db = databases.get(name) or {}
    db_id = db.get("db_id") if isinstance(db, dict) else None
    return require_resolved_value(db_id, f"databases.{name}.db_id")


def is_placeholder_value(value: object) -> bool:
    """`<...>` 形式の scaffold placeholder なら True。"""
    return isinstance(value, str) and value.strip().startswith("<") and value.strip().endswith(">")


def require_resolved_value(value: object, path: str) -> str:
    """必須 config 値を実値として返す。未設定/placeholder は ConfigError。"""
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{path} が .notion-config.json に未設定です。")
    if is_placeholder_value(value):
        raise ConfigError(f"{path} が placeholder ({value}) のままです。実値に置き換えてください。")
    return value.strip()


def get_source_db_ids(config: dict | None = None) -> tuple[str, str]:
    """notion_gmail_send.source の body_db / recipient_db を実値として返す。"""
    cfg = config if config is not None else load_config()
    source = (cfg.get("notion_gmail_send") or {}).get("source") or {}
    body_db = require_resolved_value(source.get("body_db"), "notion_gmail_send.source.body_db")
    recipient_db = require_resolved_value(source.get("recipient_db"), "notion_gmail_send.source.recipient_db")
    return body_db, recipient_db


def get_sender(config: dict | None = None) -> dict:
    """送信元設定 (notion_gmail_send.sender)。from_domain / impersonate などの固有値。"""
    cfg = config if config is not None else load_config()
    return (cfg.get("notion_gmail_send") or {}).get("sender") or {}


# ---- scaffold (config 不在時の前進手段。fail-closed を弱めない) ----

def skeleton_json() -> str:
    """貼り付け用の placeholder config JSON 文字列 (CONFIG_SKELETON の整形出力)。"""
    return json.dumps(CONFIG_SKELETON, ensure_ascii=False, indent=2)


# init 時に実値で埋めてよい非機密キー → config 上の設定先 (path)。
# DB ID は Notion ページURLの一部、impersonate はメールアドレスでいずれも非機密。
# API鍵 / SA鍵JSON は Keychain にのみ置き config には決して書かない (ここに含めない)。
FILLABLE_KEYS = ("body_db", "recipient_db", "log_db", "impersonate")


def build_config(values: dict | None = None) -> dict:
    """CONFIG_SKELETON を基に、与えられた実値(非機密)だけを上書きした config dict を返す。

    SSOT である CONFIG_SKELETON は決して変更しない(deepcopy)。example/skeleton(git 追跡) にも
    一切書かない。values で与えなかったキーは placeholder のまま残るため、部分指定でも未指定分は
    fail-closed を維持する(実値を埋めるまで解決不能)。受け付けるキー: FILLABLE_KEYS。
    書き出し先は呼び出し側(write_skeleton)が gitignored .notion-config.json に限定する。
    """
    cfg = copy.deepcopy(CONFIG_SKELETON)
    if not values:
        return cfg
    if values.get("log_db"):
        cfg["databases"]["gmail-send-log"]["db_id"] = values["log_db"]
    source = cfg["notion_gmail_send"]["source"]
    if values.get("body_db"):
        source["body_db"] = values["body_db"]
    if values.get("recipient_db"):
        source["recipient_db"] = values["recipient_db"]
    if values.get("impersonate"):
        cfg["notion_gmail_send"]["sender"]["impersonate"] = values["impersonate"]
    return cfg


def scaffold_target_path(explicit_path: str | os.PathLike[str] | None = None) -> Path:
    """init で書き出す config の宛先。明示パス > CLAUDE_PROJECT_DIR 直下 > CWD 直下。"""
    if explicit_path:
        return Path(explicit_path)
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    base = Path(proj) if proj else Path.cwd()
    return base / CONFIG_FILENAME


def write_skeleton(explicit_path: str | os.PathLike[str] | None = None, *, overwrite: bool = False,
                   values: dict | None = None) -> Path:
    """config を宛先(gitignored .notion-config.json)へ書き出し Path を返す。

    values=None なら全 placeholder。values(FILLABLE_KEYS の非機密実値)を渡すと該当キーだけを
    実値で埋め、残りは placeholder のまま(未指定分は fail-closed 維持)。実値は gitignored の
    宛先にのみ書き、example/skeleton(git 追跡) には決して書かない(build_config が deepcopy で SSOT を守る)。
    既存ファイルがあり overwrite=False なら ConfigError (実値を誤って潰さない)。
    """
    dest = scaffold_target_path(explicit_path)
    if dest.exists() and not overwrite:
        raise ConfigError(f"{dest} は既に存在します (上書きしません)。中身を編集してください。")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cfg = build_config(values)
    dest.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest
