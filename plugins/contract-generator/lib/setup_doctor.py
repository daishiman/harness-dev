#!/usr/bin/env python3
# /// script
# name: setup_doctor
# purpose: セットアップ(cwd/Python/gcloud/環境変数/Keychain/config/Drive/Sheets/Slack到達)を一括点検し、未完了のREADME Stepを名指しする診断スクリプト(標準ライブラリのみ・pip不要)。
# inputs:
#   - google-config.json(正本 ~/.config/contract-generator/・旧 .google-config.json も後方互換) / Keychain(gdrive-service-account.<keychain-prefix>, slack-bot-token.<keychain-prefix>) / gcloud CLI / 環境変数
#   - argv: --config
# outputs:
#   - stdout: 各チェックのPASS/FAIL/WARNと未完了Step番号・サマリ
#   - exit: 0=全項目クリア / 1=要対応あり
# contexts: [C, E]
# network: true
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: setup-doctor — contract-generator のセットアップ総合診断。

README(plugin 直下)Step 0-8 の達成状況を機械点検し、失敗項目を「→ Step N」で
名指しする。診断ロジックは二重実装せず、config_auth.check / load_config / load_party_a と
keychain_get_secret.get_secret / slack_common を再利用する(SSOT)。機密値は表示しない。

途中段階の自己診断手段(初見ユーザーの切り分け負荷を下げる)。--check が最後の Step 6 に
しか効かないのに対し、本 doctor は前提(cwd/Python/gcloud/env/Keychain/config)を含めて
横断点検し、どの Step に戻ればよいかを一意に示す。
"""

import argparse
import json
import os
import shutil
import sys
import urllib.error
from datetime import datetime

# 起動方法に依存せず同じ lib/ 内モジュールを import できるよう自身のディレクトリを先頭追加。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config_auth  # noqa: E402
import keychain_get_secret as kc  # noqa: E402
import slack_common  # noqa: E402

UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
DRIVE = "https://www.googleapis.com/drive/v3/files"
_BOUNDARY = "===============contract-generator-doctor=="

_ICON = {"pass": "✅", "fail": "❌", "warn": "⚠️ ", "info": "ℹ️ "}


class Report:
    """点検結果を集計し、未完了 Step と要対応の有無を保持する。"""

    def __init__(self):
        self.failed_tasks = []  # 未完了として名指しする Step ラベル
        self.has_issue = False  # fail が 1 つでもあれば True

    def line(self, status, label, detail="", task=""):
        tail = f"  → {task} を実施" if task else ""
        sep = f": {detail}" if detail else ""
        print(f"{_ICON.get(status, '  ')} {label}{sep}{tail}")
        if status == "fail":
            self.has_issue = True
            if task and task not in self.failed_tasks:
                self.failed_tasks.append(task)


def _plugin_root():
    """setup_doctor.py(lib/ 配下)から plugin ルート(lib の親)を返す。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_environment(rep):
    """cwd / Python / gcloud の前提を点検(Step 1-2)。"""
    print("── 前提ツール ──")
    # cwd 非依存運用(対話駆動・$CLAUDE_PLUGIN_ROOT 経由・shim 経由)では cwd はどこでもよい。
    # 手動で `python3 lib/...` を cwd 相対起動する場合だけ cwd=plugin ルートが必要。
    if os.path.isfile(os.path.join(os.getcwd(), "lib", "engine.py")):
        rep.line("pass", "作業ディレクトリ", "plugin ルート(手動 cwd 相対起動も可)")
    else:
        rep.line("info", "作業ディレクトリ",
                 f"cwd={os.getcwd()} は plugin ルート外(対話駆動・$CLAUDE_PLUGIN_ROOT 経由なら問題なし。"
                 f"手動で cwd 相対の `python3 lib/...` を使う場合のみ `cd {_plugin_root()}`)")
    # Python 3.11+
    v = sys.version_info
    if (v.major, v.minor) >= (3, 11):
        rep.line("pass", "Python", f"{v.major}.{v.minor}.{v.micro}")
    else:
        rep.line("fail", "Python", f"{v.major}.{v.minor}(3.11 以上が必要)", task="Step 1")
    # gcloud CLI(認証トークン取得に必須)
    if shutil.which("gcloud"):
        rep.line("pass", "gcloud CLI", "検出")
    else:
        rep.line("fail", "gcloud CLI", "未検出(認証トークン取得に必須)", task="Step 2")


def check_env_vars(rep):
    """上書き用環境変数の現在値を表示(沈黙故障の予防・情報のみ)。"""
    print("── 環境変数(任意・上書き用) ──")
    names = [
        "GOOGLE_CONFIG_PATH",
        "XDG_CONFIG_HOME",  # 設定の正本 ~/.config/contract-generator の基準を上書きする
        "GDRIVE_KEYCHAIN_SERVICE",
        "GDRIVE_KEYCHAIN_ACCOUNT",
        "PARTY_A_JSON_PATH",
        "CONTRACT_TEMPLATE_MAPPING",
    ]
    any_set = False
    for n in names:
        val = os.environ.get(n)
        if val:
            any_set = True
            rep.line("warn", n, f"設定済み={val}(README 既定より優先される)")
    if not any_set:
        rep.line("info", "上書き env", "未設定(README の既定値を使用=正常)")


def check_keychain(rep):
    """SA 鍵 / Slack Bot Token の Keychain 登録を点検(Step 3 / 4)。値は表示しない。"""
    print("── Keychain(機密) ──")
    try:
        t = kc.get_secret()  # 既定 service/account(または env 上書き)
        if t.startswith("/"):
            rep.line(
                "fail",
                "SA 鍵(gdrive-service-account.<keychain-prefix>)",
                "JSON本文ではなくファイルパスが登録されています。Step 3-3 で再登録してください",
                task="Step 3",
            )
        else:
            data = json.loads(t)
            required = ("type", "project_id", "private_key_id", "private_key", "client_email", "token_uri")
            missing = [k for k in required if not data.get(k)]
            if data.get("type") != "service_account" or missing:
                rep.line(
                    "fail",
                    "SA 鍵(gdrive-service-account.<keychain-prefix>)",
                    f"Service Account JSON として不正です(missing={missing})",
                    task="Step 3",
                )
            else:
                rep.line("pass", "SA 鍵(gdrive-service-account.<keychain-prefix>)", f"{data['client_email']} / key={data['private_key_id'][:12]}... (JSON OK)")
    except json.JSONDecodeError:
        rep.line(
            "fail",
            "SA 鍵(gdrive-service-account.<keychain-prefix>)",
            "JSONとして読めません。JSON全体ではなく一部文字列が登録されている可能性があります",
            task="Step 3",
        )
    except kc.KeychainError as e:
        rep.line("fail", "SA 鍵(gdrive-service-account.<keychain-prefix>)", str(e).split(":", 1)[0], task="Step 3")
    try:
        # Empty Slack defaults must not be passed through kc.get_secret(),
        # where they mean "use the gdrive credential". Resolve the Slack
        # purpose through the tenant namespace instead.
        t = slack_common.slack_token({})
        rep.line("pass", "Slack Bot Token(slack-bot-token.<keychain-prefix>)", kc.mask(t))
    except kc.KeychainError as e:
        rep.line("warn", "Slack Bot Token(slack-bot-token.<keychain-prefix>)",
                 "未登録(draft/finalize では必須・template-sync のみなら不要)")


def check_config(rep, explicit):
    """google-config.json の存在・必須キー・未置換プレースホルダ・slack_channel を点検(Step 5)。

    正本は ~/.config/contract-generator/google-config.json(旧リポジトリルートの
    .google-config.json も後方互換で探索)。解決パスは検出した cfg["_path"] で示す。
    成功時は cfg を返し、後続の総合疎通で使う。失敗時は None。
    """
    print("── 設定ファイル(google-config.json) ──")
    try:
        cfg = config_auth.load_config(explicit)
    except config_auth.ConfigError as e:
        rep.line("fail", "config 読込", str(e).split("。")[0], task="Step 5")
        return None
    rep.line("pass", "config 読込", cfg["_path"])
    # 必須キーに未置換プレースホルダ(<...>)が残っていないか
    unresolved = [k for k in config_auth.REQUIRED_KEYS
                  if str(cfg.get(k, "")).startswith("<")]
    if unresolved:
        rep.line("fail", "環境依存ID", f"未置換のまま: {unresolved}", task="Step 5")
    else:
        rep.line("pass", "環境依存ID", "プレースホルダ置換済み")
    # slack_channel(draft/finalize で必須)
    if (cfg.get("slack_channel") or "").strip().startswith("C"):
        rep.line("pass", "slack_channel", "設定済み")
    else:
        rep.line("warn", "slack_channel",
                 "未設定/書式不正(draft/finalize では C で始まる channel ID が必須)")
    return cfg


def check_party_a(rep):
    """甲固定値(party_a)が 4 層フォールバックで解決できるか点検。

    優先順位: $PARTY_A_JSON_PATH > ~/.config/contract-generator/party_a.json
    > 同梱 references/party_a.default.json。
    """
    print("── 甲固定値(party_a) ──")
    try:
        pa = config_auth.load_party_a()
        rep.line("pass", "party_a", f"{pa.get('name')}({os.path.basename(pa.get('_path',''))})")
    except config_auth.ConfigError as e:
        rep.line("fail", "party_a", str(e).split("(")[0], task="references/party_a-readme.md 参照")


def _multipart(metadata, media_bytes, media_mime):
    head = (f"--{_BOUNDARY}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n").encode(
        "utf-8"
    ) + json.dumps(metadata).encode("utf-8")
    mid = (f"\r\n--{_BOUNDARY}\r\nContent-Type: {media_mime}\r\n\r\n").encode("utf-8")
    tail = (f"\r\n--{_BOUNDARY}--\r\n").encode("utf-8")
    return head + mid + media_bytes + tail, f"multipart/related; boundary={_BOUNDARY}"


def _drive_write_probe(token, folder_id):
    """Drive 出力フォルダに小さなテストファイルを作成し、即削除する。

    canAddChildren=true でも、Service Account が My Drive 配下で所有者になる場合は
    storageQuotaExceeded で実アップロードだけ失敗するため、本番前に検出する。
    """
    name = "_contract_generator_setup_doctor_probe_" + datetime.now().strftime("%Y%m%d%H%M%S")
    body, ct = _multipart(
        {"name": name, "parents": [folder_id]},
        b"contract-generator setup-doctor probe\n",
        "text/plain",
    )
    url = f"{UPLOAD}?uploadType=multipart&supportsAllDrives=true&fields=id"
    res = config_auth.gapi_send(url, token, method="POST", raw_body=body, content_type=ct)
    fid = res.get("id")
    if fid:
        # Shared Drive では files.delete が 404 を返す権限構成があるため、疎通判定では
        # 「作成できた」ことを重視し、片付けは trash への移動をベストエフォートで行う。
        try:
            config_auth.gapi_send(
                f"{DRIVE}/{fid}?supportsAllDrives=true",
                token,
                method="PATCH",
                json_body={"trashed": True},
            )
        except Exception:
            pass


def check_connectivity(rep, cfg):
    """gcloud トークン取得 + Drive/Sheets 到達 + Slack 疎通の総合点検(Step 6 相当)。"""
    print("── 総合疎通(gcloud / Drive / Sheets / Slack) ──")
    if cfg is None:
        rep.line("warn", "総合疎通", "config 未解決のためスキップ(先に Step 5 を完了)")
        return
    try:
        token = config_auth.get_access_token(cfg)
    except Exception as e:  # noqa: BLE001
        rep.line("fail", "gcloud 認証", str(e), task="Step 2")
        return

    google_ok = True
    checks = [
        ("Sheets 台帳", "spreadsheet_id", f"https://sheets.googleapis.com/v4/spreadsheets/{cfg['spreadsheet_id']}", {"fields": "spreadsheetId,properties.title"}, "edit"),
        ("Drive ひな形フォルダ", "templates_folder_id", f"https://www.googleapis.com/drive/v3/files/{cfg['templates_folder_id']}", {"fields": "id,name,capabilities(canAddChildren,canEdit)", "supportsAllDrives": "true"}, "read"),
        ("Drive 個人フォルダ", "individual_folder_id", f"https://www.googleapis.com/drive/v3/files/{cfg['individual_folder_id']}", {"fields": "id,name,capabilities(canAddChildren,canEdit)", "supportsAllDrives": "true"}, "add_children"),
        ("Drive 法人フォルダ", "corporate_folder_id", f"https://www.googleapis.com/drive/v3/files/{cfg['corporate_folder_id']}", {"fields": "id,name,capabilities(canAddChildren,canEdit)", "supportsAllDrives": "true"}, "add_children"),
    ]
    for label, key, url, params, required_perm in checks:
        try:
            data = config_auth.gapi_get(url, token, params=params)
            name = data.get("name") or data.get("properties", {}).get("title") or data.get("id")
            caps = data.get("capabilities") or {}
            if required_perm == "add_children" and not caps.get("canAddChildren"):
                google_ok = False
                rep.line(
                    "fail",
                    label,
                    f"{name}: SAは閲覧できますがファイル追加できません(id={cfg[key]})。README 前提条件の Drive 共有で編集者に設定してください",
                    task="前提条件(Drive共有)",
                )
                continue
            rep.line("pass", label, name)
        except urllib.error.HTTPError as e:
            google_ok = False
            if e.code in (403, 404) and key.endswith("_folder_id"):
                rep.line("fail", label, f"SAから見えません(id={cfg[key]})。README 前提条件の Drive 共有を実施してください", task="前提条件(Drive共有)")
            elif e.code in (403, 404) and key == "spreadsheet_id":
                rep.line("fail", label, f"SAから見えません(id={cfg[key]})。README 前提条件の Drive 共有を実施してください", task="前提条件(Drive共有)")
            else:
                rep.line("fail", label, f"HTTP {e.code}", task="Step 2")
        except Exception as e:  # noqa: BLE001
            google_ok = False
            rep.line("fail", label, str(e), task="Step 2")
    if not google_ok:
        return

    for label, key in (
        ("Drive 個人フォルダ 書込テスト", "individual_folder_id"),
        ("Drive 法人フォルダ 書込テスト", "corporate_folder_id"),
    ):
        try:
            _drive_write_probe(token, cfg[key])
            rep.line("pass", label, "小さなテストファイルの作成・削除OK")
        except config_auth.ConfigError as e:
            google_ok = False
            detail = str(e)
            if "storageQuotaExceeded" in detail:
                rep.line(
                    "fail",
                    label,
                    "Drive storage quota exceeded。Service Account が My Drive 配下で所有者になれないため、出力先を共有ドライブに移すか、ユーザーOAuth/委任方式に切り替えてください",
                    task="前提条件(Drive共有)",
                )
            else:
                rep.line("fail", label, detail, task="前提条件(Drive共有)")
        except Exception as e:  # noqa: BLE001
            google_ok = False
            rep.line("fail", label, str(e), task="前提条件(Drive共有)")
    if not google_ok:
        return

    slack_status, slack_detail = config_auth._slack_check(cfg)
    rep.line("pass", "gcloud/Drive/Sheets 疎通", "トークン取得・台帳/個人/法人フォルダ到達OK(REST)")
    if slack_status == "ok":
        rep.line("pass", "Slack 疎通", "auth.test 成功")
    elif slack_status == "unset":
        rep.line("warn", "Slack 疎通", "未設定(draft/finalize では必須)")
    else:
        rep.line("fail", "Slack 疎通", slack_detail, task="Step 4")


def main():
    p = argparse.ArgumentParser(description="contract-generator セットアップ総合診断")
    p.add_argument("--config", help="google-config.json のパス(未指定は自動探索)")
    a = p.parse_args()

    print("contract-generator setup-doctor — セットアップ点検")
    print("=" * 56)
    rep = Report()
    check_environment(rep)
    check_env_vars(rep)
    check_keychain(rep)
    cfg = check_config(rep, a.config)
    check_party_a(rep)
    check_connectivity(rep, cfg)

    print("=" * 56)
    if rep.failed_tasks:
        print("要対応:", " / ".join(rep.failed_tasks))
        print("→ plugin 直下 README.md の該当 Step に戻って実施してください。")
    elif rep.has_issue:
        print("要対応あり(上記 ❌ を参照)。")
    else:
        print("✅ セットアップは整っています(draft 実行可能)。")
        print("   次: python3 lib/engine.py --phase draft --type all --dry-run")
    return 1 if rep.has_issue else 0


if __name__ == "__main__":
    sys.exit(main())
