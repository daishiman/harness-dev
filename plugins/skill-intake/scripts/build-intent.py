#!/usr/bin/env python3
# /// script
# name: build-intent
# purpose: interview 回答を probe-pattern-table と intent-contract.schema に基づき決定論的に
#          intent_contract の各 slot へ機械マッピングする。LLM 非依存・冪等。
# inputs:
#   - answers.json (位置引数): 回答ログ {qa_log:[{slot|target_slot|probe_id, answer}]} または
#                              {answers:{<slot_path>: <text>}} 形式
#   - --table: references/probe-pattern-table.json (発火条件と normalize_hint の正本)
#   - --schema: references/intent-contract.schema.json (slot 定義と enum の正本, 任意)
# outputs:
#   - stdout: JSON {intent_contract:{input_spec,output_spec,slot_status}, pending_probes:[probe_id]}
#   - exit 0: 全 slot filled / exit 1: pending_probes あり / exit 2: 入力エラー
# contexts: [interview phase / phase3 決定論チェーン]
# network: false
# write-scope: none
# requires-python: ">=3.8"
# ///
"""回答 -> intent_contract 正規化 (決定論・冪等)。

本質: ヒアリングの本質は『入力->出力インテント抽出』。ユーザーは言語化できないので
probe で引き出す。本 script はその回答を probe-pattern-table.json の normalize_hint と
enum に従い intent_contract の slot へ機械写像する。写像不能な slot は filled=false のまま
残し、発火すべき probe_id を pending_probes に列挙する(=次に手を差し伸べるべき点の決定論的提示)。

冪等性: 同一入力 -> 同一出力。Date/random 一切不使用。dict は sort_keys で安定シリアライズ。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import _jsonschema_compat as jsonschema
except Exception:  # pragma: no cover - optional until --schema is used
    jsonschema = None

# ---------------------------------------------------------------------------
# enum 写像テーブル (script 冒頭に定数化。日本語表現を広めにカバー)
# 正本の enum 値は intent-contract.schema.json 側。ここは日本語->enum の写像のみ担う。
# ---------------------------------------------------------------------------

# frequency / cadence 共通 enum: realtime|daily|weekly|monthly|event|ondemand
FREQUENCY_MAP = {
    "realtime": "realtime", "常時": "realtime", "リアルタイム": "realtime",
    "随時更新": "realtime", "つねに": "realtime", "常に": "realtime",
    "daily": "daily", "毎日": "daily", "日次": "daily", "毎朝": "daily",
    "毎晩": "daily", "1日1回": "daily", "一日一回": "daily", "デイリー": "daily",
    "weekly": "weekly", "毎週": "weekly", "週次": "weekly", "週1": "weekly",
    "週一": "weekly", "毎週月曜": "weekly", "ウィークリー": "weekly",
    "monthly": "monthly", "毎月": "monthly", "月次": "monthly", "月1": "monthly",
    "月一": "monthly", "マンスリー": "monthly",
    "event": "event", "イベント": "event", "イベント時": "event",
    "特定イベント": "event", "きっかけ": "event", "都度イベント": "event",
    "ondemand": "ondemand", "必要な時": "ondemand", "必要になった時": "ondemand",
    "必要なとき": "ondemand", "都度": "ondemand", "オンデマンド": "ondemand",
    "手動": "ondemand", "任意": "ondemand", "適宜": "ondemand",
}
# cadence は frequency と同一 enum 集合。別名で参照可能にする。
CADENCE_MAP = dict(FREQUENCY_MAP)

# format enum: bullet|table|prose|document|message|dashboard|other
FORMAT_MAP = {
    "bullet": "bullet", "箇条書き": "bullet", "箇条書": "bullet", "リスト": "bullet",
    "リスト形式": "bullet", "ポイント": "bullet",
    "table": "table", "表": "table", "テーブル": "table", "一覧表": "table",
    "スプレッドシート": "table", "表形式": "table",
    "prose": "prose", "文章": "prose", "文": "prose", "散文": "prose",
    "地の文": "prose", "説明文": "prose",
    "document": "document", "文書": "document", "ドキュメント": "document",
    "レポート": "document", "報告書": "document", "資料": "document",
    "message": "message", "メッセージ": "message", "通知文": "message",
    "チャット": "message", "短文": "message", "一言": "message",
    "dashboard": "dashboard", "ダッシュボード": "dashboard", "画面": "dashboard",
    "ボード": "dashboard", "パネル": "dashboard",
    "other": "other", "その他": "other", "それ以外": "other",
}

# 未充足とみなす placeholder 表現 (fire_condition の決定論判定に用いる)
PLACEHOLDER_TOKENS = {
    "", "未定", "未定義", "不明", "わからない", "分からない", "わからん",
    "tbd", "todo", "未回答", "なし", "-", "ー", "null", "none", "?", "？",
    "未入力", "後で", "あとで", "保留",
}

# slot -> 写像方式の分類 (enum 写像 or 自由文字列)
ENUM_SLOTS = {
    "input_spec.frequency": FREQUENCY_MAP,
    "output_spec.format": FORMAT_MAP,
    "output_spec.cadence": CADENCE_MAP,
}
ARRAY_SLOTS = {"input_spec.sources", "input_spec.raw_materials"}
FREE_SLOTS = {
    "input_spec.trigger",
    "output_spec.sink",
    "output_spec.granularity",
    "output_spec.audience",
}

ALL_SLOTS = [
    "input_spec.sources",
    "input_spec.trigger",
    "input_spec.frequency",
    "input_spec.raw_materials",
    "output_spec.sink",
    "output_spec.format",
    "output_spec.granularity",
    "output_spec.audience",
    "output_spec.cadence",
]


def _is_placeholder(text: str) -> bool:
    return text.strip().lower() in PLACEHOLDER_TOKENS


def _map_enum(text: str, table: dict) -> str | None:
    """テキスト中に写像キーが含まれれば対応 enum を返す (最長キー優先で決定論)。"""
    t = text.strip().lower()
    if not t:
        return None
    # 完全一致優先
    for key in sorted(table.keys(), key=len, reverse=True):
        if key.lower() == t:
            return table[key]
    # 部分一致 (長いキー優先で衝突回避)
    for key in sorted(table.keys(), key=len, reverse=True):
        if key.lower() in t:
            return table[key]
    return None


def _load_answers(obj: dict, probe_by_id: dict[str, str] | None = None) -> tuple[dict, dict]:
    """回答 JSON を {slot_path: answer_text} の正規形へ変換する。

    受理形式:
      A. {"answers": {"output_spec.format": "箇条書き", ...}}
      B. {"qa_log": [{"target_slot"|"slot": "...", "answer": "..."}, ...]}
      C. B の要素が {"probe_id": "PB-OUT-FORMAT", "answer": "..."} でも
         table 経由で target_slot を解決する (呼び出し側で解決済み前提の簡易対応)。
    """
    result: dict[str, str] = {}
    provenance: dict[str, dict] = {}
    probe_by_id = probe_by_id or {}
    if isinstance(obj.get("answers"), dict):
        for k, v in obj["answers"].items():
            slot = str(k)
            result[slot] = "" if v is None else str(v)
            provenance.setdefault(slot, {"source": "direct_answer", "probe_ids": []})
    log = obj.get("qa_log") or obj.get("answers_log") or []
    if isinstance(log, list):
        for entry in log:
            if not isinstance(entry, dict):
                continue
            probe_id = entry.get("probe_id")
            slot = entry.get("target_slot") or entry.get("slot")
            if slot is None and probe_id:
                slot = probe_by_id.get(str(probe_id))
            ans = entry.get("answer")
            if ans is None:
                ans = entry.get("raw_answer")
            if slot is not None:
                slot = str(slot)
                result.setdefault(slot, "" if ans is None else str(ans))
                source = "probe" if probe_id else "direct_answer"
                probe_ids = [str(probe_id)] if probe_id else []
                provenance.setdefault(slot, {"source": source, "probe_ids": probe_ids})
    return result, provenance


def _resolve_probe_ids(table: dict) -> dict:
    """target_slot -> probe_id の逆引き表 (最初に定義された probe を採用)。"""
    m: dict[str, str] = {}
    for p in table.get("probes", []):
        slot = p.get("target_slot")
        pid = p.get("probe_id")
        if slot and pid and slot not in m:
            m[slot] = pid
    return m


def _resolve_probe_targets(table: dict) -> dict:
    """probe_id -> target_slot の逆引き表。"""
    m: dict[str, str] = {}
    for p in table.get("probes", []):
        pid = p.get("probe_id")
        slot = p.get("target_slot")
        if pid and slot:
            m[str(pid)] = str(slot)
    return m


def normalize(answers: dict, table: dict, provenance: dict | None = None) -> dict:
    """回答 -> intent_contract + pending_probes (決定論)。"""
    probe_by_slot = _resolve_probe_ids(table)
    probe_order = table.get("probe_order", [])

    input_spec = {"sources": [], "trigger": "", "frequency": "", "raw_materials": []}
    output_spec = {"sink": "", "format": "", "granularity": "", "audience": "", "cadence": ""}
    slot_status: dict[str, dict] = {}
    pending: list[str] = []
    provenance = provenance or {}

    for slot in ALL_SLOTS:
        section, field = slot.split(".", 1)
        target = input_spec if section == "input_spec" else output_spec
        raw = answers.get(slot, "")
        text = raw.strip() if isinstance(raw, str) else str(raw)

        filled = False
        value = None

        if _is_placeholder(text):
            filled = False
        elif slot in ENUM_SLOTS:
            mapped = _map_enum(text, ENUM_SLOTS[slot])
            if mapped is not None:
                value, filled = mapped, True
        elif slot in ARRAY_SLOTS:
            # 区切り(、,/・ 改行)で分割し placeholder を除いて配列化
            parts = [
                seg.strip()
                for seg in _split_multi(text)
                if seg.strip() and not _is_placeholder(seg)
            ]
            if parts:
                value, filled = parts, True
        elif slot in FREE_SLOTS:
            value, filled = text, True

        if filled:
            target[field] = value
            src = provenance.get(slot, {})
            slot_status[slot] = {
                "filled": True,
                "source": src.get("source") or "direct_answer",
                "probe_ids": src.get("probe_ids") or [],
            }
        else:
            pid = probe_by_slot.get(slot)
            slot_status[slot] = {
                "filled": False,
                "source": "probe",
                "probe_ids": [pid] if pid else [],
            }
            if pid:
                pending.append(pid)

    # pending を probe_order の決定論順に整列
    order_index = {pid: i for i, pid in enumerate(probe_order)}
    pending.sort(key=lambda pid: order_index.get(pid, len(order_index)))

    return {
        "intent_contract": {
            "input_spec": input_spec,
            "output_spec": output_spec,
            "slot_status": slot_status,
        },
        "pending_probes": pending,
    }


def _validate_schema(result: dict, schema_path: str | None) -> list[str]:
    if not schema_path:
        return []
    if jsonschema is None:
        return ["jsonschema validator unavailable"]
    try:
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        validator_cls = jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema)
        errors = sorted(
            validator.iter_errors({"intent_contract": result["intent_contract"]}),
            key=lambda e: list(e.absolute_path),
        )
    except Exception as exc:
        return [f"schema validation setup failed: {exc}"]
    messages = []
    for err in errors:
        loc = ".".join(str(p) for p in err.absolute_path) or "<root>"
        messages.append(f"{loc}: {err.message}")
    return messages


def _split_multi(text: str) -> list[str]:
    seps = ["、", ",", "，", "/", "／", "・", "\n", ";", "；"]
    parts = [text]
    for sep in seps:
        nxt: list[str] = []
        for p in parts:
            nxt.extend(p.split(sep))
        parts = nxt
    return parts


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="回答 -> intent_contract 正規化 (決定論)")
    ap.add_argument("answers", help="回答 JSON パス (qa_log または answers 形式)")
    ap.add_argument(
        "--table",
        default="references/probe-pattern-table.json",
        help="probe-pattern-table.json パス",
    )
    ap.add_argument(
        "--schema",
        default=None,
        help="intent-contract.schema.json パス (任意・参照のみ)",
    )
    args = ap.parse_args(argv)

    try:
        answers_obj = json.loads(Path(args.answers).read_text(encoding="utf-8"))
    except Exception as e:
        sys.stderr.write(f"error: 回答 JSON 読込失敗: {e}\n")
        return 2
    if not isinstance(answers_obj, dict):
        sys.stderr.write("error: 回答 JSON は object である必要があります\n")
        return 2

    try:
        table = json.loads(Path(args.table).read_text(encoding="utf-8"))
    except Exception as e:
        sys.stderr.write(f"error: probe-pattern-table 読込失敗: {e}\n")
        return 2
    if not isinstance(table.get("probes"), list):
        sys.stderr.write("error: probe-pattern-table に probes[] がありません\n")
        return 2

    answers, provenance = _load_answers(answers_obj, _resolve_probe_targets(table))
    result = normalize(answers, table, provenance)
    schema_errors = [] if result["pending_probes"] else _validate_schema(result, args.schema)
    if schema_errors:
        for msg in schema_errors:
            sys.stderr.write(f"error: intent_contract schema mismatch: {msg}\n")
        return 2

    # sort_keys=True で冪等な安定シリアライズ (sha256 安定)
    sys.stdout.write(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    return 1 if result["pending_probes"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
