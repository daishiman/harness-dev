#!/usr/bin/env python3
# /// script
# name: ledger
# purpose: 個人/法人2シートのヘッダ整備(非破壊) + 対象行抽出 + 生成結果の書き戻し。
# inputs:
#   - Google Sheets(管理台帳) / argv: --ensure-schema --list --dry-run
# outputs:
#   - sheets 書込(ヘッダ/行更新) / 対象行一覧
# contexts: [C, E]
# network: true
# write-scope: google-sheets
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: ensure-ledger-schema + 行抽出 + writeback-ledger。

同一スプレッドシート内の「個人」「法人」2シートのヘッダ整備(非破壊・既存行保持)、
作成指示◯ かつ ステータス≠completed 行の抽出(冪等キー)、生成結果の書き戻しを担う。

ヘッダ定義はコード内 SSOT(HEADERS)。差込列名は template-mapping.json の column と一致させる。
"""

import argparse
import hashlib
import sys
import urllib.parse

import config_auth

SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"


def _enc_range(title, suffix=""):
    """'個人'!A1:B1 等の range を URL エンコード。"""
    rng = f"'{title}'" + (f"!{suffix}" if suffix else "")
    return urllib.parse.quote(rng, safe="")

# --- ヘッダ SSOT(列順は新規作成時のみ使用。既存シートは header 名で解決し順序非依存) ---
HEADERS = {
    "個人": [
        "No", "ステータス", "作成指示（◯で発火）", "冪等キー（自動生成）",
        "乙氏名・名称", "乙住所・連絡先",
        "振込先_銀行名", "振込先_支店名", "振込先_口座種類", "振込先_口座番号", "振込先_口座名義（フリガナ）",
        "第1条_目的", "業務内容①", "業務内容②（任意）", "遂行場所", "業務内容方式",
        "成果物有無", "成果物番号", "納品期限", "検収期間", "料金方式", "金額", "個人情報処分方法",
        "契約開始日", "契約終了日", "契約期間_年数", "更新拒絶通知_月数", "中途解約通知_月数", "締結日",
        "ファイル名（自動記入）", "契約書URL（自動記入）", "PDF_URL（自動記入）",
        "Slack_メッセージTS（自動）", "Slack_通知日時（自動）", "承認者（自動）", "承認日時（自動）", "再生成フラグ",
        "作成日時（自動記入）", "更新日時（自動記入）", "備考（任意）",
    ],
    "法人": [
        "No", "ステータス", "作成指示（◯で発火）", "冪等キー（自動生成）",
        "乙法人名・名称", "乙代表者役職・氏名", "乙本店所在地・連絡先",
        "振込先_銀行名", "振込先_支店名", "振込先_口座種類", "振込先_口座番号", "振込先_口座名義（フリガナ）",
        "第1条_目的", "業務内容①", "業務内容②（任意）", "業務内容方式", "料金方式", "金額", "個人情報処分方法",
        "契約開始日", "契約終了日", "契約期間_年数", "更新拒絶通知_月数", "中途解約通知_月数", "締結日",
        "別紙1_遂行場所", "別紙1_成果物有無", "別紙1_成果物内容", "別紙1_納品期限", "別紙1_検収期間",
        "別紙2_料金明細", "別紙3_個人情報処分方法",
        "ファイル名（自動記入）", "契約書URL（自動・Docs黄色版）", "PDF_URL（自動・黄色除去版）",
        "別紙URL（自動記入）",
        "Slack_メッセージTS（自動）", "Slack_通知日時（自動）", "承認者（自動）", "承認日時（自動）", "再生成フラグ",
        "作成日時（自動記入）", "更新日時（自動記入）", "備考（任意）",
    ],
}

# 状態マシン(SSOT): 未作成/空 → draft → approved → completed (再生成フラグで未作成へ差し戻し)
STATUS_VALUES = ["", "未作成", "draft", "approved", "completed"]

# phase → select_target_rows の status_filter(状態遷移知識の正本)。engine等はこれを参照する。
# None(legacy)=従来の completed以外。各 phase は次に処理すべき入力状態の集合。
# 既定運用は pull 型: 発火条件は「Claude Code での finalize 実行」のみ。Slack承認は必須ゲートではない。
# そのため finalize は draft 行を直接受理する(= Claude Code 実行が人間の承認ゲート)。
# "approved" も残し、任意で poll(Slack承認)を挟む二者承認フローにも後方互換。
_PHASE_STATUS_FILTER = {
    None: None,
    "draft": {"", "未作成"},
    "poll": {"draft"},          # 任意: Slack ✅/OK を承認記録として approved 化(必須ではない)
    "finalize": {"draft", "approved"},  # draft を直接確定可(Claude Code 実行が発火条件)
}


def phase_filter(phase):
    """phase に対応する status_filter を返す(未知phaseは None=legacy)。状態遷移知識のSSOT。"""
    return _PHASE_STATUS_FILTER.get(phase)


SHEET_BY_TYPE = {"individual": "個人", "corporate": "法人"}

VALIDATION_CHOICES = {
    "個人": {
        "作成指示（◯で発火）": ["◯", ""],
        "ステータス": ["", "未作成", "draft", "approved", "completed"],
        "業務内容方式": ["する", "別紙1に定める"],
        "成果物有無": ["あり", "なし"],
        "料金方式": ["固定金額", "別紙2参照"],
        "個人情報処分方法": ["別途定める", "別紙3に定める"],
    },
    "法人": {
        "作成指示（◯で発火）": ["◯", ""],
        "ステータス": ["", "未作成", "draft", "approved", "completed"],
        "業務内容方式": ["する", "別紙1に定める"],
        "料金方式": ["固定金額", "別紙2参照"],
        "個人情報処分方法": ["別途定める", "別紙3に定める"],
        "別紙1_成果物有無": ["あり", "なし"],
    },
}


def get_party_a():
    """甲固定値の単一引当口(SSOT)。config_auth.load_party_a() に委譲する。

    差込時に template-mapping.json の {{party_a.*}} 変数を解決する用途。
    既存 API は触らず、薄い読み取り経路としてのみ追加。
    """
    return config_auth.load_party_a()


def _col_letter(idx0):
    """0-based 列番号 → A1 列記号。"""
    s = ""
    n = idx0 + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _sheet_properties(token, spreadsheet_id):
    meta = config_auth.gapi_get(f"{SHEETS_API}/{spreadsheet_id}", token,
                                params={"fields": "sheets.properties(title,sheetId)"})
    return {s["properties"]["title"]: s["properties"] for s in meta.get("sheets", [])}


def _existing_sheets(token, spreadsheet_id):
    return set(_sheet_properties(token, spreadsheet_id))


def _apply_data_validations(token, spreadsheet_id, title, headers, dry_run):
    if dry_run:
        return
    props = _sheet_properties(token, spreadsheet_id).get(title)
    if not props:
        return
    requests = []
    for col, choices in VALIDATION_CHOICES.get(title, {}).items():
        if col not in headers:
            continue
        idx = headers.index(col)
        requests.append({
            "setDataValidation": {
                "range": {
                    "sheetId": props["sheetId"],
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": idx,
                    "endColumnIndex": idx + 1,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": v} for v in choices],
                    },
                    "strict": True,
                    "showCustomUi": True,
                },
            }
        })
    if requests:
        config_auth.gapi_send(
            f"{SHEETS_API}/{spreadsheet_id}:batchUpdate",
            token,
            json_body={"requests": requests},
        )


def ensure_schema(token, spreadsheet_id, dry_run=False):
    """個人/法人シートを用意し、欠落ヘッダを末尾に追記(既存データ非破壊)。"""
    titles = _existing_sheets(token, spreadsheet_id)
    report = {}
    for title, headers in HEADERS.items():
        if title not in titles:
            if dry_run:
                report[title] = "would-create"
                continue
            config_auth.gapi_send(f"{SHEETS_API}/{spreadsheet_id}:batchUpdate", token,
                                  json_body={"requests": [{"addSheet": {"properties": {"title": title}}}]})
            _write_header_row(token, spreadsheet_id, title, headers, dry_run)
            _apply_data_validations(token, spreadsheet_id, title, headers, dry_run)
            report[title] = "created"
            continue
        cur = _read_header_row(token, spreadsheet_id, title)
        missing = [h for h in headers if h not in cur]
        if missing and not dry_run:
            _write_header_row(token, spreadsheet_id, title, cur + missing, dry_run)
            cur = cur + missing
        _apply_data_validations(token, spreadsheet_id, title, cur, dry_run)
        report[title] = f"ok(+{len(missing)}列追加)" if missing else "ok"
    return report


def _read_header_row(token, spreadsheet_id, title):
    url = f"{SHEETS_API}/{spreadsheet_id}/values/{_enc_range(title, '1:1')}"
    res = config_auth.gapi_get(url, token)
    vals = res.get("values", [[]])
    return vals[0] if vals else []


def _write_header_row(token, spreadsheet_id, title, headers, dry_run):
    if dry_run:
        return
    suffix = f"A1:{_col_letter(len(headers) - 1)}1"
    url = (f"{SHEETS_API}/{spreadsheet_id}/values/{_enc_range(title, suffix)}"
           "?valueInputOption=RAW")
    config_auth.gapi_send(url, token, method="PUT", json_body={"values": [headers]})


def idempotency_key(row):
    """乙名+目的+開始日+金額 から安定ハッシュ。台帳に既存値があればそれを優先。"""
    existing = row.get("冪等キー（自動生成）", "").strip()
    if existing:
        return existing
    name = row.get("乙氏名・名称") or row.get("乙法人名・名称") or ""
    basis = "|".join([name, row.get("第1条_目的", ""), row.get("契約開始日", ""), row.get("金額", "")])
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def read_rows(token, spreadsheet_id, title):
    """ヘッダ付きで全行を dict 化。row_number(1-based, ヘッダ=1)を付与。"""
    url = f"{SHEETS_API}/{spreadsheet_id}/values/{_enc_range(title)}"
    res = config_auth.gapi_get(url, token)
    values = res.get("values", [])
    if not values:
        return [], []
    header = values[0]
    rows = []
    for i, raw in enumerate(values[1:], start=2):
        d = {header[j]: (raw[j] if j < len(raw) else "") for j in range(len(header))}
        d["_row_number"] = i
        rows.append(d)
    return header, rows


FLAG_TRUE = ("◯", "○", "o", "O", "✓", "true", "TRUE")


def _flag_on(r):
    return (r.get("作成指示（◯で発火）", "") or "").strip() in FLAG_TRUE


def select_target_rows(rows, status_filter=None):
    """対象行を返す。

    status_filter=None(既定): 作成指示◯ かつ ステータス≠completed(従来挙動・後方互換)。
    status_filter=set/list: 作成指示◯ かつ ステータス∈status_filter の行(状態マシン用)。
      例: フェーズdraft → {"","未作成"} / フェーズfinalize → {"approved"}。
    """
    out = []
    for r in rows:
        if not _flag_on(r):
            continue
        status = (r.get("ステータス", "") or "").strip()
        if status_filter is None:
            if status.lower() != "completed":
                out.append(r)
        elif status in status_filter:
            out.append(r)
    return out


def writeback(token, spreadsheet_id, title, row_number, updates, dry_run=False):
    """updates: {ヘッダ名 or 接頭辞: 値}。接頭辞一致で実列を解決し該当セルのみ更新。"""
    header = _read_header_row(token, spreadsheet_id, title)
    data = []
    for key, val in updates.items():
        col = _resolve_col(header, key)
        if col is None:
            continue
        cell = f"'{title}'!{_col_letter(col)}{row_number}"
        data.append({"range": cell, "values": [[val]]})
    if dry_run or not data:
        return [d["range"] for d in data]
    config_auth.gapi_send(f"{SHEETS_API}/{spreadsheet_id}/values:batchUpdate", token,
                          json_body={"valueInputOption": "RAW", "data": data})
    return [d["range"] for d in data]


def _resolve_col(header, key):
    if key in header:
        return header.index(key)
    for i, h in enumerate(header):
        if h.startswith(key):
            return i
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config")
    p.add_argument("--ensure-schema", action="store_true")
    p.add_argument("--list", choices=["individual", "corporate"])
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    cfg = config_auth.load_config(a.config)
    token = config_auth.get_access_token(cfg)
    if a.ensure_schema:
        print(ensure_schema(token, cfg["spreadsheet_id"], a.dry_run))
    if a.list:
        title = SHEET_BY_TYPE[a.list]
        _, rows = read_rows(token, cfg["spreadsheet_id"], title)
        tgt = select_target_rows(rows)
        print(f"{title}: 全{len(rows)}行 / 対象{len(tgt)}行")
        for r in tgt:
            print(f"  row{r['_row_number']}: {r.get('乙氏名・名称') or r.get('乙法人名・名称')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
