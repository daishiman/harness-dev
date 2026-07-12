#!/usr/bin/env python3
# /// script
# name: config_auth
# purpose: google-config.json 読込 + Keychain の SA 鍵から gcloud でアクセストークン取得 + REST用httpヘルパ提供(標準ライブラリのみ・pip不要)。
# inputs:
#   - google-config.json(正本 ~/.config/contract-generator/・旧 .google-config.json も後方互換) / Keychain(gdrive-service-account.<keychain-prefix>) / gcloud CLI
#   - argv: --config --check
# outputs:
#   - returns: access_token / gapi_get/gapi_send で Drive/Sheets REST / party_a(甲固定値 SSOT)
# contexts: [C, E]
# network: true
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: load-config-auth(標準ライブラリのみ・pip不要)。

google-config.json(環境依存IDのSSOT。正本=~/.config/contract-generator/・ホーム配下で
git管理外。旧リポジトリルートの .google-config.json も後方互換で読む) を読み、Keychain の
Service Account 鍵を gcloud CLI に一時 activate してアクセストークンを取得する。
Drive/Sheets は urllib で REST 直叩き。

SA認証のRS256署名は標準ライブラリに無いため gcloud CLI を使う(pip install は不要・README Task2でgcloud導入済)。
gcloud のグローバル設定を汚さないよう CLOUDSDK_CONFIG で一時ディレクトリを使い、鍵は即破棄する。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import warnings

import keychain_get_secret as kc

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

# 正本は XDG 準拠のホーム配下(プラグイン更新で消えない・誰が導入しても同一)。
# 開発リポジトリ時代の .google-config.json(リポジトリルート/cwd) は後方互換で探索を残す。
APP_DIR_NAME = "contract-generator"
GOOGLE_CONFIG_BASENAME = "google-config.json"

REQUIRED_KEYS = [
    "spreadsheet_id",
    "templates_folder_id",
    "individual_folder_id",
    "corporate_folder_id",
]


class ConfigError(Exception):
    pass


def xdg_config_dir():
    """設定の正本ディレクトリ ~/.config/contract-generator(XDG_CONFIG_HOME 優先)。"""
    base = os.environ.get("XDG_CONFIG_HOME", "").strip() or os.path.expanduser("~/.config")
    return os.path.join(base, APP_DIR_NAME)


def google_config_candidates(explicit=None):
    """google-config.json の探索候補を優先順で返す(実行時評価)。

    1. --config 明示指定
    2. $GOOGLE_CONFIG_PATH
    3. ~/.config/contract-generator/google-config.json (正本・XDG)
    4. 同ディレクトリの .google-config.json (後方互換・旧ドット名で XDG に置いた場合の救済)
    5. [後方互換] cwd 直下 → 親 6 階層の .google-config.json(旧リポジトリルート運用)
    """
    cands = [explicit] if explicit else []
    cands.append(os.environ.get("GOOGLE_CONFIG_PATH", ""))
    app_dir = xdg_config_dir()
    cands.append(os.path.join(app_dir, GOOGLE_CONFIG_BASENAME))
    cands.append(os.path.join(app_dir, "." + GOOGLE_CONFIG_BASENAME))
    # 後方互換: cwd(=ループ初回)から親 6 階層まで .google-config.json を遡る
    here = os.path.abspath(os.getcwd())
    for _ in range(6):
        cands.append(os.path.join(here, ".google-config.json"))
        here = os.path.dirname(here)
    return cands


def find_config(explicit=None):
    for c in google_config_candidates(explicit):
        if c and os.path.isfile(c):
            return c
    raise ConfigError(
        f"google-config.json が見つかりません。references/google-config.sample.json を "
        f"{xdg_config_dir()}/{GOOGLE_CONFIG_BASENAME} にコピーして自分の環境の値に編集してください"
        "(README Task 10)。$GOOGLE_CONFIG_PATH で別の場所を明示指定することもできます。"
    )


def load_config(explicit=None):
    path = find_config(explicit)
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    missing = [k for k in REQUIRED_KEYS if not cfg.get(k)]
    if missing:
        raise ConfigError(f"google-config.json に必須キー欠落: {missing} ({path})")
    cfg["_path"] = path
    return cfg


# ---------- 甲固定値(party_a) SSOT ----------

PARTY_A_REQUIRED_KEYS = ("name", "address", "representative", "title", "rep_name")


def _party_a_candidate_paths():
    """優先順位: 環境変数 > ~/.config/contract-generator > [後方互換]~/.config/tenant > plugin 同梱 default。"""
    env_path = os.environ.get("PARTY_A_JSON_PATH", "").strip()
    legacy_env_path = os.environ.get("XL_PARTY_A_JSON_PATH", "").strip()
    if legacy_env_path and not env_path:
        warnings.warn(
            "XL_PARTY_A_JSON_PATH is deprecated; use PARTY_A_JSON_PATH",
            DeprecationWarning,
            stacklevel=2,
        )
        env_path = legacy_env_path
    app_path = os.path.join(xdg_config_dir(), "party_a.json")  # 正本(google-config と同居)
    # plugin 同梱: lib/ の親 = plugin ルート → references/party_a.default.json
    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_path = os.path.join(plugin_root, "references", "party_a.default.json")
    return [p for p in (env_path, app_path, default_path) if p]


def load_party_a():
    """甲固定値 dict を返す(SSOT)。優先順位 4 層で最初に見つかった JSON を採用。

    返却キー: name / address / representative / title / rep_name。
    どの層にも無ければ ConfigError を投げる(plugin 同梱の default が存在する想定)。
    """
    last_err = None
    for path in _party_a_candidate_paths():
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            last_err = e
            continue
        missing = [k for k in PARTY_A_REQUIRED_KEYS if not data.get(k)]
        if missing:
            raise ConfigError(f"party_a JSON に必須キー欠落: {missing} ({path})")
        data["_path"] = path
        return data
    raise ConfigError(
        "party_a JSON が見つかりません(優先順位: $PARTY_A_JSON_PATH / "
        f"{xdg_config_dir()}/party_a.json / "
        "references/party_a.default.json)"
        + (f" / 直近エラー: {last_err}" if last_err else "")
    )


def get_access_token(cfg):
    """Keychain の SA 鍵を gcloud に一時 activate してアクセストークンを返す。

    既存 gcloud 設定を汚さないよう CLOUDSDK_CONFIG=一時dir を使い、鍵ファイルは即削除する。
    """
    service = cfg.get("keychain_service") or kc.DEFAULT_SERVICE
    account = cfg.get("keychain_account") or kc.DEFAULT_ACCOUNT
    raw = kc.get_secret(service=service, account=account)  # SA 鍵 JSON
    tmpdir = tempfile.mkdtemp(prefix="cg-gcloud-")
    keypath = os.path.join(tmpdir, "sa.json")
    with open(keypath, "w", encoding="utf-8") as f:
        f.write(raw)
    env = {**os.environ, "CLOUDSDK_CONFIG": tmpdir}
    try:
        subprocess.run(
            ["gcloud", "auth", "activate-service-account", "--key-file", keypath],
            env=env, check=True, capture_output=True, text=True,
        )
        res = subprocess.run(
            ["gcloud", "auth", "print-access-token", "--scopes=" + ",".join(SCOPES)],
            env=env, check=True, capture_output=True, text=True,
        )
        return res.stdout.strip()
    except FileNotFoundError as e:
        raise ConfigError("gcloud CLI が見つかりません(README Task 2 で導入)") from e
    except subprocess.CalledProcessError as e:
        raise ConfigError(f"gcloud 認証失敗: {(e.stderr or '').strip()}") from e
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------- Google REST(urllib) 共通ヘルパ ----------

def gapi_get(url, token, params=None, raw=False):
    """GET。raw=True ならバイト列を返す(ファイルDL/export用)。それ以外は JSON。"""
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    return body if raw else json.loads(body.decode("utf-8"))


def gapi_send(url, token, method="POST", json_body=None, raw_body=None, content_type=None):
    """POST/PUT/PATCH/DELETE。json_body は JSON送信、raw_body はバイト送信(multipart等)。"""
    headers = {"Authorization": f"Bearer {token}"}
    if raw_body is not None:
        data = raw_body
        if content_type:
            headers["Content-Type"] = content_type
    elif json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    else:
        data = None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise ConfigError(f"Google API {method} failed HTTP {e.code}: {detail}") from e
    return json.loads(body.decode("utf-8")) if body else {}


def _slack_check(cfg):
    """Slack 設定をソフト検証する。

    返り値 (status, detail):
      - ("unset", "...")  : slack_channel 未設定。draft/finalize では必須だが、Slack 不使用
                            スキル(template-sync 等)の疎通は壊さないため致命的失敗にしない。
      - ("ok", "")        : auth.test 成功(token 有効)。可能なら channel 到達性も確認。
      - ("ng", "<理由>")  : token 無効 / channel 到達不可 / token 取得失敗 等。

    機微情報(token 値・channel 名)は detail に含めない。
    """
    channel = (cfg.get("slack_channel") or "").strip()
    if not channel:
        return ("unset", "Slack 未設定(draft/finalize では必須)")
    try:
        from slack_common import slack_token  # lib 同居・遅延 import
        token = slack_token(cfg)
    except Exception as e:  # noqa: BLE001  Keychain 取得失敗等
        return ("ng", f"Slack Bot Token 取得失敗: {type(e).__name__}")
    body = _slack_api_get("https://slack.com/api/auth.test", token)
    if isinstance(body, str):
        return ("ng", body)  # HTTP/JSON レベルの失敗理由
    if not body.get("ok"):
        return ("ng", f"auth.test エラー: {body.get('error')}")
    team = body.get("team") or "(unknown workspace)"
    team_id = body.get("team_id") or "(unknown team_id)"
    # token 有効。channel 到達性を軽く確認(失敗しても token OK は活かす)。
    ch = _slack_api_get(
        "https://slack.com/api/conversations.info", token, params={"channel": channel}
    )
    if isinstance(ch, dict) and not ch.get("ok"):
        if ch.get("error") == "missing_scope":
            needed = ch.get("needed") or "(unknown)"
            provided = ch.get("provided") or "(unknown)"
            return (
                "ng",
                "channel 到達不可: missing_scope "
                f"(needed={needed}; provided={provided})。"
                "publicチャンネルは channels:read、privateチャンネルは groups:read を追加して再インストール",
            )
        if ch.get("error") == "channel_not_found":
            return (
                "ng",
                f"channel 到達不可: channel_not_found (slack_channel={channel})。"
                f"現在のBot Tokenは workspace={team} / team_id={team_id} のものです。"
                "チャンネルIDが正しい場合は、Bot Tokenが別workspaceのもの、またはprivateチャンネルにBotが未招待の可能性があります",
            )
        return ("ng", f"channel 到達不可: {ch.get('error')}")
    return ("ok", "")


def _slack_api_get(url, token, params=None):
    """Slack Web API を GET で叩く(Authorization: Bearer)。

    成功時は JSON(dict)、urllib/JSON レベルの失敗時は理由文字列を返す。標準ライブラリのみ。
    """
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return f"Slack 接続失敗: {getattr(e, 'reason', e)}"
    except (json.JSONDecodeError, ValueError) as e:
        return f"Slack 応答解析失敗: {type(e).__name__}"


def check(cfg):
    """疎通確認: Google トークン取得 + 台帳/各フォルダ到達 + Slack ソフト検証。

    返り値: (True, slack_status, slack_detail)
      - slack_status は "ok" / "unset" / "ng" のいずれか(_slack_check 参照)。
    Google 側の失敗は従来どおり例外送出(致命的)。Slack 側は致命化せず status で返す
    (Slack 不使用スキルの疎通を壊さないため)。
    後方互換: 既存呼び出し元は main() のみで戻り値を tuple 受けに更新済み。
    """
    token = get_access_token(cfg)
    gapi_get(f"https://sheets.googleapis.com/v4/spreadsheets/{cfg['spreadsheet_id']}",
             token, params={"fields": "spreadsheetId"})
    for key in ("templates_folder_id", "individual_folder_id", "corporate_folder_id"):
        gapi_get(f"https://www.googleapis.com/drive/v3/files/{cfg[key]}",
                 token, params={"fields": "id,name", "supportsAllDrives": "true"})
    slack_status, slack_detail = _slack_check(cfg)
    return (True, slack_status, slack_detail)


def build_services(cfg):
    """REST 化に伴う互換ヘルパ。

    旧 google-api-python-client 時代の (drive_service, sheets_service) を返す API の
    後継。本実装は単一 access_token を Drive/Sheets 共通スコープで取得し、dict で返す。
    gapi_get/gapi_send は token を引数に取るため、呼び出し側は dict["sheets_token"]
    または dict["drive_token"] を渡す(実体は同一トークン)。

    返却: {"sheets_token": token, "drive_token": token, "cfg": cfg}
    """
    token = get_access_token(cfg)
    return {"sheets_token": token, "drive_token": token, "cfg": cfg}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config")
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    try:
        cfg = load_config(a.config)
    except ConfigError as e:
        sys.stderr.write(f"[config_auth] {e}\n")
        return 2
    if a.check:
        try:
            _ok, slack_status, slack_detail = check(cfg)
        except Exception as e:  # noqa: BLE001  Google 側は致命的失敗
            sys.stderr.write(f"[config_auth] 疎通NG: {e}\n")
            return 3
        slack_line = {
            "ok": "Slack: OK(auth.test 成功)",
            "unset": "Slack: 未設定(draft/finalize では必須)",
        }.get(slack_status, f"Slack: NG({slack_detail})")
        print(f"OK config={cfg['_path']}")
        print("gcloudトークン取得・Sheets台帳/個人/法人フォルダ到達OK(REST)")
        print(slack_line)
        # Slack 設定ミス(ng)は総合テストとして検出する(unset は致命化しない)。
        if slack_status == "ng":
            return 4
    else:
        print(f"OK config={cfg['_path']} (--check で疎通確認)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
