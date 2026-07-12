#!/usr/bin/env python3
# /// script
# name: confirm_url
# purpose: confirm-url-template.md(確認用URLページ本文の唯一の正本)をパースし source_by_field/source_urls から Notion children ブロック/プレビューテキストを決定論生成し、既存本文とのURL非減少マージを提供する(文言をコードに二重定義しない)。
# inputs:
#   - file: references/confirm-url-template.md の「template_key → 要素マッピング」「origin → 表示由来マッピング」表
#   - api: load_template() / load_origin_labels() / build_entries(source) / parse_bullet(text) / merge_entries(new, existing) / render_blocks(source) / render_text(source)
# outputs:
#   - api: Notion children blocks(list[dict]) / プレビュー用プレーンテキスト(str) / マージ済み entries(list[dict])
#   - exit: 0=OK (CLI 自己検査: source_by_field 有り/全未確定 両方の render_text を表示)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""確認用URL ページ本文テンプレート展開器 (SSOT 維持・fail-closed)。

文言の唯一の正本は references/confirm-url-template.md の markdown 表 (md 単一正本)。本モジュールは
その表をパースして 5 要素 (heading / intro / bullet_with_url / bullet_no_url / body_no_fields) と
origin enum 5値 → 表示由来ラベルの対応へ展開するだけで、文言をコードに二重定義しない
(remarks.py と同型)。既定値フォールバックは持たない: md が不在/破損して要素を抽出できなければ
ValueError を送出する (fail-closed)。

入力の正本は record の `source_by_field` (= {field: {origin, url}})。origin enum は
{gbizinfo, japanpost, web, user_input, none}。各 field 値 dict は拡張可能 (後続のフォールバック
多段化が attempts 等を併設しても本モジュールは origin/url のみ読む)。旧形式の `source_urls`
(= {attribute, url} リスト / str リスト) も後方互換で受理する (由来不明 URL は web 扱い)。

本文同期 (notion_upsert.sync_confirm_url_body) は既存本文 bullet を parse_bullet でパースし、
merge_entries で **URL 非減少マージ** (今回取得した出典のみ差し替え・既存の出典 URL は保持)
してから再レンダリングする。レンダリングは決定論で、同一入力 → byte 一致 (冪等)。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# references/confirm-url-template.md (scripts/ から見て ../references/)
TEMPLATE_MD = Path(__file__).resolve().parent.parent / "references" / "confirm-url-template.md"

# 表行: | `key` | `値` |  (バッククォートは任意許容)
_ROW_RE = re.compile(r"^\|\s*`?([a-z_]+)`?\s*\|\s*`?(.+?)`?\s*\|\s*$")
_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")
_HEADER_KEYS = {"template_key", "origin"}

TEMPLATE_KEYS = ("heading", "intro", "bullet_with_url", "bullet_no_url", "body_no_fields")
# origin enum 5値 (source_by_field[field].origin の値域。columns.md per-field 出典規則と一致)。
ORIGIN_KEYS = ("gbizinfo", "japanpost", "web", "user_input", "none")

# 本文 bullet の属性と順序 (columns.md 列定義と一致。列順 = 本文 bullet 順)。正式名称は独立
# bullet を廃し会社名へ統合 (R5/D2) したため本文属性は 5 つ。会社名 bullet は official_name(登記名)
# の検証 URL を統合し、official_name が無く会社名が user_input(URLなし) のときのみ抑止する (R5)。
ATTRIBUTE_FIELDS = (
    "company_name", "address",
    "postal_code", "hojin_bango", "phone_number",
)
# 属性表示名。official_name は本文では会社名へ統合され独立 bullet を持たないが、enrich の
# 派生 source_urls (列順導出) が正式名称ラベルを参照するため定義は残す (provenance ラベル)。
FIELD_LABELS = {
    "company_name": "会社名",
    "official_name": "正式名称",
    "address": "住所",
    "postal_code": "郵便番号",
    "hojin_bango": "法人番号",
    "phone_number": "電話番号",
}

# 既存本文 bullet のパース正規表現。bullet_with_url / bullet_no_url の 2 形式 + 旧形式
# (`属性: URL`) に対応する。形式の正本はテンプレ md だが、レンダリング済み本文の逆変換
# (URL 非減少マージ用) はここで行う。round-trip (parse(render(e)) == e) はテストで機械保証する。
_BULLET_WITH_URL_RE = re.compile(r"^(?P<attribute>.*?)（(?P<origin_label>[^（）]+)）:\s*(?P<url>\S+)$")
_BULLET_LEGACY_RE = re.compile(r"^(?P<attribute>.*?):\s*(?P<url>https?://\S+)$")
_BULLET_NO_URL_RE = re.compile(r"^(?P<attribute>.*?):\s*(?P<origin_label>.+?)（URLなし）$")


def _parse_table(text: str, heading_markers: tuple[str, ...]) -> dict[str, str]:
    """指定見出し配下の md 表行を {key: 値} へパースする。"""
    out: dict[str, str] = {}
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            in_section = any(m in stripped for m in heading_markers)
            continue
        if not in_section or _SEP_RE.match(stripped):
            continue
        m = _ROW_RE.match(stripped)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip().strip("`")
        if key in _HEADER_KEYS:
            continue
        out[key] = value
    return out


def _read_template_md(md_path: Path | None) -> str:
    path = md_path or TEMPLATE_MD
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(
            f"confirm-url-template.md が読めません: {path} ({e}). "
            "文言の唯一の正本 (SSOT) が不在のため fail-closed で停止します。"
        ) from e


def load_template(md_path: Path | None = None) -> dict[str, str]:
    """confirm-url-template.md の表をパースして {template_key: 値} を返す (fail-closed)。

    「template_key → 要素マッピング」見出し配下の表行のみを採用する。文言の正本は md 単一で、
    既定値フォールバックは持たない (二重定義しない・remarks.load_templates と同型)。md が不在
    (OSError) または 5 要素 (TEMPLATE_KEYS) のいずれかが欠落していれば ValueError を送出する。
    呼び出し側 (notion_upsert.sync_confirm_url_body) がこの例外を best-effort で握り、本文同期
    失敗で全体を落とさず縮退する。
    """
    path = md_path or TEMPLATE_MD
    out = _parse_table(_read_template_md(md_path), ("template_key", "要素マッピング"))
    missing = [k for k in TEMPLATE_KEYS if k not in out]
    if missing:
        raise ValueError(
            f"confirm-url-template.md からテンプレートを抽出できません: {path} "
            f"(欠落キー: {', '.join(missing)}. 「template_key → 要素マッピング」表の形式を確認してください)"
        )
    return {k: out[k] for k in TEMPLATE_KEYS}


def load_origin_labels(md_path: Path | None = None) -> dict[str, str]:
    """「origin → 表示由来マッピング」表をパースして {origin: 表示由来} を返す (fail-closed)。"""
    path = md_path or TEMPLATE_MD
    out = _parse_table(_read_template_md(md_path), ("表示由来",))
    missing = [k for k in ORIGIN_KEYS if k not in out]
    if missing:
        raise ValueError(
            f"confirm-url-template.md から origin 表示由来を抽出できません: {path} "
            f"(欠落 origin: {', '.join(missing)}. 「origin → 表示由来マッピング」表の形式を確認してください)"
        )
    return {k: out[k] for k in ORIGIN_KEYS}


def _normalize_source_urls(source_urls: list | None) -> list[dict]:
    """旧形式 source_urls を [{attribute, origin, url}] へ正規化する (後方互換で str 要素も許容)。

    由来 (origin) を持たない旧形式エントリは web 扱い (歴史的に source_urls はネット検索由来のみ)。
    """
    items: list[dict] = []
    for entry in source_urls or []:
        if isinstance(entry, dict):
            url = (entry.get("url") or "").strip()
            attribute = (entry.get("attribute") or "").strip()
            if attribute == FIELD_LABELS["official_name"]:
                attribute = FIELD_LABELS["company_name"]
            origin = (entry.get("origin") or "web").strip()
            if url:
                items.append({"attribute": attribute, "origin": origin, "url": url})
        elif isinstance(entry, str):
            url = entry.strip()
            if url:
                items.append({"attribute": "", "origin": "web", "url": url})
    return items


def _company_bullet_suppressed(origin: str, url: str) -> bool:
    """会社名 bullet を本文に出さない条件 (R5) の唯一の述語 (forward/backward 共有 SSOT)。

    URL が無く origin が none/user_input のとき True。新規生成 (build_entries dict 経路) でも
    既存本文の再同期 (build_entries list 経路) でも同一規律で適用し、『会社名: ユーザー入力（URLなし）』
    『会社名: 未確定（URLなし）』を二度と出力しない。official_name の検証 URL や非自明 origin
    (gbizinfo 等) があれば url 有無に関わらず会社名 bullet として残す (登記名 URL を失わない)。
    """
    return not (url or "").strip() and (origin or "none").strip() in ("none", "user_input")


def _merged_company_entry(source: dict, labels: dict) -> dict | None:
    """会社名 bullet を official_name(登記名) 優先で 1 エントリに統合する (R5/D2)。

    official_name に検証 URL か非自明 origin (gbizinfo 等) があれば、その出典を会社名ラベルで
    出す (登記名の gBizINFO 検証 URL を会社名 bullet へ統合し失わない)。無ければ会社名(通称) へ
    フォールバックするが、_company_bullet_suppressed が真の会社名 bullet は本文に出さない
    (R5: 『会社名: ユーザー入力（URLなし）』を二度と出さない → None)。
    """
    official = source.get("official_name") if isinstance(source.get("official_name"), dict) else {}
    company = source.get("company_name") if isinstance(source.get("company_name"), dict) else {}
    for spec in (official, company):
        origin = (spec.get("origin") or "none").strip()
        url = (spec.get("url") or "").strip()
        if not _company_bullet_suppressed(origin, url):
            o = origin if origin in labels else "none"
            return {"attribute": FIELD_LABELS["company_name"], "origin": o,
                    "origin_label": labels.get(o, labels["none"]), "url": url}
    return None


def build_entries(source, md_path: Path | None = None) -> list[dict]:
    """source_by_field(dict) / source_urls(list) を本文 entries へ正規化する。

    entries の各要素は {attribute, origin, origin_label, url}。
      - dict 入力 (source_by_field): 会社名(official_name 統合)+住所/郵便番号/法人番号/電話番号 を
        columns.md 列順で出力する (会社名は R5 で抑止され得るため最大 5・最小 4 件)。
      - list 入力 (旧 source_urls / マージ済み entries): 要素順を保持する。
    """
    labels = load_origin_labels(md_path)
    entries: list[dict] = []
    if isinstance(source, dict):
        company_entry = _merged_company_entry(source, labels)
        if company_entry is not None:
            entries.append(company_entry)
        for field in ATTRIBUTE_FIELDS:
            if field == "company_name":
                continue  # 会社名は official_name 統合済み (_merged_company_entry で処理)
            spec = source.get(field) or {}
            origin = (spec.get("origin") or "none").strip() if isinstance(spec, dict) else "none"
            url = (spec.get("url") or "").strip() if isinstance(spec, dict) else ""
            entries.append({
                "attribute": FIELD_LABELS[field],
                "origin": origin if origin in labels else "none",
                "origin_label": labels.get(origin, labels["none"]),
                "url": url,
            })
        return entries
    legacy_entries: list[dict] = []
    for item in source or []:
        if isinstance(item, dict) and "origin_label" in item:
            attribute = (item.get("attribute") or "").strip()
            if attribute == FIELD_LABELS["official_name"]:
                attribute = FIELD_LABELS["company_name"]
            legacy_entries.append({
                "attribute": attribute,
                "origin": (item.get("origin") or ("web" if item.get("url") else "none")).strip(),
                "origin_label": item["origin_label"],
                "url": (item.get("url") or "").strip(),
            })
            continue
        for norm in _normalize_source_urls([item]):
            origin = norm["origin"] if norm["origin"] in labels else "web"
            legacy_entries.append({
                "attribute": norm["attribute"],
                "origin": origin,
                "origin_label": labels[origin],
                "url": norm["url"],
            })
    # R5 (backward 辺): 再同期/legacy 経路でも会社名 bullet 抑止を forward と同一述語で適用し、
    # 既存本文の『会社名: ユーザー入力（URLなし）』『会社名: 未確定（URLなし）』を復活させない。
    legacy_entries = [
        e for e in legacy_entries
        if not (e["attribute"] == FIELD_LABELS["company_name"]
                and _company_bullet_suppressed(e["origin"], e["url"]))
    ]
    return merge_entries(legacy_entries, [])


def _canon_attribute(attribute: str) -> str:
    """旧『正式名称』属性ラベルを会社名へ正規化する (会社名統合・R5/D2)。

    _normalize_source_urls / build_entries(legacy 経路) と同一規律。既存ページ本文に旧
    『正式名称: URL』bullet が残る行を再同期するとき、parse_bullet 経由の逆変換でも会社名へ
    寄せ、merge_entries が会社名 entry へ dedup できるようにする (廃止した正式名称 bullet を
    復活させず、official_name URL を会社名・正式名称の 2 bullet へ重複させない)。
    """
    return FIELD_LABELS["company_name"] if attribute == FIELD_LABELS["official_name"] else attribute


def parse_bullet(text: str, md_path: Path | None = None) -> dict | None:
    """レンダリング済み bullet テキスト 1 行を entry へ逆変換する (マージ用)。

    bullet_with_url / 旧形式 (`属性: URL`) / bullet_no_url の順に試行し、いずれにも
    一致しなければ None (本文の非テンプレ行はマージ対象外として無視する)。属性ラベルは
    _canon_attribute で会社名へ正規化する (旧『正式名称』bullet を会社名へ統合・R5/D2)。
    """
    labels = load_origin_labels(md_path)
    reverse = {v: k for k, v in labels.items()}
    s = (text or "").strip()
    if s.startswith("- "):
        s = s[2:]
    if not s:
        return None
    m = _BULLET_WITH_URL_RE.match(s)
    if m:
        label = m.group("origin_label").strip()
        return {"attribute": _canon_attribute(m.group("attribute").strip()),
                "origin": reverse.get(label, "web"),
                "origin_label": label, "url": m.group("url").strip()}
    m = _BULLET_LEGACY_RE.match(s)
    if m:
        return {"attribute": _canon_attribute(m.group("attribute").strip()), "origin": "web",
                "origin_label": labels["web"], "url": m.group("url").strip()}
    m = _BULLET_NO_URL_RE.match(s)
    if m:
        label = m.group("origin_label").strip()
        return {"attribute": _canon_attribute(m.group("attribute").strip()),
                "origin": reverse.get(label, "none"),
                "origin_label": label, "url": ""}
    return None


def merge_entries(new_entries: list[dict], existing_entries: list[dict]) -> list[dict]:
    """URL 非減少マージ: 今回の出典で差し替えつつ、既存本文の出典 URL を喪失させない。

    属性ごとに: 今回 entry が URL を持てば今回を採用 (出典差し替え)、今回が URL 無しで
    既存が URL を持てば既存を保持 (URL 非減少)、どちらも URL 無しなら今回を採用。
    順序は columns.md 列順 (FIELD_LABELS 順) → それ以外は出現順。
    """
    by_new = {e["attribute"]: e for e in new_entries if e.get("attribute")}
    by_old: dict[str, dict] = {}
    for e in existing_entries:
        if e.get("attribute"):
            by_old.setdefault(e["attribute"], e)
    order: list[str] = []
    for field in ATTRIBUTE_FIELDS:
        label = FIELD_LABELS[field]
        if label in by_new or label in by_old:
            order.append(label)
    for e in list(new_entries) + list(existing_entries):
        attr = e.get("attribute") or ""
        if attr and attr not in order:
            order.append(attr)
    merged: list[dict] = []
    for attr in order:
        n, o = by_new.get(attr), by_old.get(attr)
        if n and (n.get("url") or not (o and o.get("url"))):
            merged.append(dict(n))
        elif o:
            merged.append(dict(o))
    # 属性名を持たない旧形式エントリ (URL のみ) は今回分だけ末尾へ保持する。
    merged.extend(dict(e) for e in new_entries if not e.get("attribute"))
    return merged


def _is_blank(entries: list[dict]) -> bool:
    """記録すべき由来が 1 件も無い (全 entry が none かつ URL 無し / entries 空) か。"""
    return all(e.get("origin") == "none" and not e.get("url") for e in entries) if entries else True


def _bullet_text(tpl: dict[str, str], entry: dict) -> str:
    if entry.get("url"):
        return tpl["bullet_with_url"].format(
            attribute=entry.get("attribute", ""),
            origin_label=entry.get("origin_label", ""), url=entry["url"])
    return tpl["bullet_no_url"].format(
        attribute=entry.get("attribute", ""), origin_label=entry.get("origin_label", ""))


def _rich_text(content: str) -> list[dict]:
    return [{"type": "text", "text": {"content": content}}]


def render_blocks(source, md_path: Path | None = None) -> list[dict]:
    """source_by_field/source_urls/マージ済み entries から Notion children ブロック配列を決定論生成する。

    由来あり: heading_2 + paragraph(intro) + bulleted_list_item×N (会社名統合後の属性 or エントリ数)。
    全未確定: heading_2 + paragraph(body_no_fields)。
    """
    tpl = load_template(md_path)
    entries = build_entries(source, md_path)
    blocks: list[dict] = [
        {"object": "block", "type": "heading_2",
         "heading_2": {"rich_text": _rich_text(tpl["heading"])}},
    ]
    if _is_blank(entries):
        blocks.append({"object": "block", "type": "paragraph",
                       "paragraph": {"rich_text": _rich_text(tpl["body_no_fields"])}})
        return blocks
    blocks.append({"object": "block", "type": "paragraph",
                   "paragraph": {"rich_text": _rich_text(tpl["intro"])}})
    for e in entries:
        blocks.append({"object": "block", "type": "bulleted_list_item",
                       "bulleted_list_item": {"rich_text": _rich_text(_bullet_text(tpl, e))}})
    return blocks


def render_text(source, md_path: Path | None = None) -> str:
    """検証/プレビュー用にテンプレ展開済みプレーンテキストを返す (byte 一致確認用)。

    レンダリング規約 (confirm-url-template.md) と同一の本文を再現する:
      由来あり: '## heading' + 空行 + intro + 空行 + '- bullet'×N
      全未確定: '## heading' + 空行 + body_no_fields
    """
    tpl = load_template(md_path)
    entries = build_entries(source, md_path)
    lines: list[str] = [f"## {tpl['heading']}", ""]
    if _is_blank(entries):
        lines.append(tpl["body_no_fields"])
        return "\n".join(lines)
    lines.append(tpl["intro"])
    lines.append("")
    for e in entries:
        lines.append("- " + _bullet_text(tpl, e))
    return "\n".join(lines)


def main() -> int:
    """CLI 自己検査: source_by_field 有り/全未確定 両方の render_text を表示し parse 健全性を確認する。"""
    sample = {
        "company_name": {"origin": "user_input", "url": ""},
        "official_name": {"origin": "gbizinfo",
                          "url": "https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1234567890123"},
        "address": {"origin": "gbizinfo",
                    "url": "https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1234567890123"},
        "postal_code": {"origin": "japanpost", "url": "https://www.post.japanpost.jp/"},
        "hojin_bango": {"origin": "gbizinfo",
                        "url": "https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1234567890123"},
        "phone_number": {"origin": "web", "url": "https://www.google.com/search?q=%2203-1234-5678%22"},
    }
    print("=== source_by_field ===")
    print(render_text(sample))
    print("\n=== all unresolved ===")
    print(render_text([]))
    tpl = load_template()
    labels = load_origin_labels()
    print(f"\n# loaded {len(tpl)} template keys / {len(labels)} origin labels from {TEMPLATE_MD}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
