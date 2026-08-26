#!/usr/bin/env python3
"""資料作成の大原則カタログから、いま必要な分だけを抽出する。

実行中 plugin の deck-principles/principles.json が原則本文の唯一の正本で、
本 script は解決済みカタログから applies_to × phase で絞り込んだ部分集合を返すだけ。
規範文・閾値をこの script 内へ持たない（持った瞬間に正本が 2 つになる）。

  python3 select-deck-principles.py --applies-to report --phase story
  python3 select-deck-principles.py --applies-to diagram --phase diagram --limit 12
  python3 select-deck-principles.py --checklist
  python3 select-deck-principles.py --id DP-034 --id DP-108
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

FULL_XREF = re.compile(r"DP-(\d{3})")
RANGE_XREF = re.compile(r"DP-(\d{3})\s*[〜～~–—-]\s*(?:DP-)?(\d{3})")
SLASH_XREF = re.compile(r"DP-\d{3}(?:(?:/|／)(?:DP-)?\d{3})+")

# 本 script は slide-report-generator が正本で、guide-doc-generator へは
# バイト複製で vendoring される。どちらでも同じバイトが動くよう、plugin root の
# env 名と配置先 (references/ か assets/) の両方を候補として探索する。
ROOT_ENV_KEYS = ("SRG_ROOT", "HB_ROOT", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")
DIR_CANDIDATES = (
    Path("references") / "deck-principles",
    Path("assets") / "deck-principles",
)


def catalog_dir() -> Path:
    """principles.json と binding.json を含むディレクトリを解決する。

    絶対パスを焼き込むと worktree / marketplace 配置で壊れる。明示 override の
    DECK_PRINCIPLES_DIR、実行中 script の __file__ 相対、汎用 plugin root env の順で見る。
    vendored script が sibling plugin の環境変数へ吸われず standalone で閉じるためである。
    """
    direct = os.environ.get("DECK_PRINCIPLES_DIR")
    if direct and (Path(direct) / "principles.json").is_file():
        return Path(direct)

    # vendored script は sibling plugin の env が同時に立っていても cross-read しない。
    # 明示的な DECK_PRINCIPLES_DIR の次は、必ず実行中 script 自身の plugin を優先する。
    roots: list[Path] = [Path(__file__).resolve().parent.parent]
    for key in ROOT_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            roots.append(Path(value))
    for root in roots:
        for relative in DIR_CANDIDATES:
            if (root / relative / "principles.json").is_file():
                return root / relative

    sys.stderr.write("[select-deck-principles] 原則カタログが見つかりません。"
                     f"探索した root: {', '.join(str(r) for r in roots)}\n"
                     f"  候補の配置: {', '.join(str(c) for c in DIR_CANDIDATES)}\n")
    raise SystemExit(2)


def load_catalog(root: Path) -> dict:
    with (root / "principles.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def load_binding(root: Path) -> dict:
    path = root / "binding.json"
    if not path.is_file():
        sys.stderr.write(f"[select-deck-principles] 写像表が見つかりません: {path}\n")
        raise SystemExit(2)
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_tool_adapter(root: Path, tool_id: str | None) -> dict | None:
    """ツール中立 rule を薄い実行 brief へ投影する adapter を返す。"""
    if not tool_id:
        return None
    path = root / "tool-adapters.json"
    if not path.is_file():
        sys.stderr.write(f"[select-deck-principles] tool adapter が見つかりません: {path}\n")
        raise SystemExit(2)
    with path.open(encoding="utf-8") as handle:
        registry = json.load(handle)
    adapter = registry.get("adapters", {}).get(tool_id)
    if adapter is None:
        known = ", ".join(sorted(registry.get("adapters", {})))
        sys.stderr.write(f"[select-deck-principles] 未知の tool: {tool_id}\n  既知: {known}\n")
        raise SystemExit(2)
    return {"id": tool_id, **adapter}


def resolve_consumer(root: Path, consumer_id: str) -> tuple[list[str], list[str]]:
    """binding.json の consumer 定義を (select argv, pin する原則 id) へ展開する。

    agent prompt には --consumer <id> だけを書かせる。絞り込み条件を prompt 側へ
    書き写すと、条件が 2 箇所に散って必ず片方が腐る。
    """
    binding = load_binding(root)
    for consumer in binding["consumers"]:
        if consumer["id"] == consumer_id:
            return list(consumer["select"]), list(consumer.get("core_refs", []))
    known = ", ".join(c["id"] for c in binding["consumers"])
    sys.stderr.write(f"[select-deck-principles] 未知の consumer: {consumer_id}\n  既知: {known}\n")
    raise SystemExit(2)


def matches(principle: dict, applies_to: list[str], phases: list[str]) -> bool:
    """指定された applies_to と phase の両方に交差する原則だけを通す。

    どちらの指定も OR（複数指定はいずれかに当たればよい）だが、
    軸をまたぐ関係は AND。「report の story 局面」は
    「report に効く」かつ「story で効く」の両方を満たす必要がある。
    """
    if applies_to and not (set(principle["applies_to"]) & set(applies_to)):
        return False
    if phases and not (set(principle["phase"]) & set(phases)):
        return False
    return True


ENFORCEMENT_ORDER = {"machine": 0, "reviewer": 1, "human": 2}


def rank(principle: dict, applies_to: list[str], phases: list[str]) -> tuple:
    """--limit で溢れたときに、どの原則を優先して残すかの順序キーを返す。昇順で小さいほど残る。

    第 1 軸は「問い合わせに対する特異度」。原則が持つ applies_to / phase のうち、
    問い合わせに含まれない値が何個あるかを数える。0 ならその局面専用の助言、
    大きいほど「どこでも言われる一般論」なので先に落とす。局面固有の知見の方が、
    その場の判断を実際に変える。

    第 2 軸は thresholds の有無。数値を持つ原則は後段の検査器と直接噛み合う。
    第 3 軸は enforcement（machine → reviewer → human）。
    最後に no で安定化させ、同じ引数なら常に同じ部分集合が出るようにする。
    """
    query_applies = set(applies_to) or set(principle["applies_to"])
    query_phases = set(phases) or set(principle["phase"])
    off_target = (len(set(principle["applies_to"]) - query_applies)
                  + len(set(principle["phase"]) - query_phases))
    return (
        off_target,
        0 if "thresholds" in principle else 1,
        ENFORCEMENT_ORDER.get(principle["enforcement"], 9),
        principle["no"],
    )


def extract_xrefs(text: str) -> list[str]:
    """完全形・範囲・slash短縮形を同じ DP-xxx 列へ正規化する。"""
    refs = {f"DP-{number}" for number in FULL_XREF.findall(text)}
    for start_text, end_text in RANGE_XREF.findall(text):
        start, end = int(start_text), int(end_text)
        step = 1 if end >= start else -1
        refs.update(f"DP-{number:03d}" for number in range(start, end + step, step))
    for match in SLASH_XREF.finditer(text):
        refs.update(f"DP-{number}" for number in re.findall(r"\d{3}", match.group(0)))
    return sorted(refs)


def collect_xrefs(selected: list[dict], catalog: dict) -> list[dict]:
    """選ばれた原則の rule が名指ししている DP-xxx を補完する。

    「DP-076 の字数を守れ」とだけ書かれた原則が選ばれても、
    DP-076 本体が手元に無ければ適用できない。相互参照は 1 段だけ辿る
    （多段で辿ると結局カタログ全体に膨らむ）。
    """
    by_id = {p["id"]: p for p in catalog["principles"]}
    have = {p["id"] for p in selected}
    extra: dict[str, dict] = {}
    for principle in selected:
        for ref in extract_xrefs(principle["rule"]):
            if ref not in have and ref in by_id:
                extra[ref] = by_id[ref]
    return sorted(extra.values(), key=lambda p: p["no"])


def render_markdown(
    selected: list[dict],
    xrefs: list[dict],
    catalog: dict,
    *,
    consumer: str | None,
    catalog_digest: str,
    tool_adapter: dict | None,
    base_limit: int,
    xref_limit: int,
) -> str:
    groups = {g["id"]: g["title_ja"] for g in catalog["groups"]}
    lines = ["# 適用する原則", ""]
    lines.append(f"基本 {len(selected)} 件 + 相互参照 {len(xrefs)} 件。"
                 "本文の正本は解決済み deck-principles/principles.json。ここに書かれていない規範を足さない。")
    lines.append(f"- selection: consumer={consumer or '-'} / catalog={catalog_digest} "
                 f"/ base_limit={base_limit or 'unbounded'} / xref_limit={xref_limit or 'unbounded'}")
    if tool_adapter:
        lines.append(f"- ツール投影: {tool_adapter['label']} — {tool_adapter['brief']}")
    lines.append("")
    for principle in selected + xrefs:
        lines.append(f"## {principle['id']} {principle['title_ja']}")
        lines.append(f"- 分類: {groups.get(principle['group'], principle['group'])}"
                     f" / 適用: {'・'.join(principle['applies_to'])}"
                     f" / 局面: {'・'.join(principle['phase'])}"
                     f" / 判定: {principle['enforcement']}")
        lines.append(f"- 規範: {principle['rule']}")
        if "thresholds" in principle:
            lines.append(f"- 閾値: {json.dumps(principle['thresholds'], ensure_ascii=False)}")
        if "antipattern" in principle:
            lines.append(f"- 反例: {principle['antipattern']}")
        if "tool_intent" in principle:
            lines.append(f"- 操作意図: {principle['tool_intent']}")
            if tool_adapter:
                lines.append(f"- {tool_adapter['label']}での確認: "
                             f"{tool_adapter['intent_prefix']}{principle['tool_intent']}{tool_adapter['intent_suffix']}")
        lines.append("")
    return "\n".join(lines)


def render_checklist(catalog: dict, tool_adapter: dict | None) -> str:
    by_id = {p["id"]: p for p in catalog["principles"]}
    lines = ["# 出力直前チェックリスト", ""]
    if tool_adapter:
        lines.extend([
            f"ツール投影: {tool_adapter['label']} — {tool_adapter['brief']}",
            f"確認方法: {tool_adapter['checklist_prompt']}",
            "",
        ])
    for item in catalog["checklist"]["items"]:
        lines.append(f"- [ ] **{item['id']}** {item['text']}")
        for ref in item["refs"]:
            principle = by_id.get(ref)
            if principle:
                lines.append(f"    - {ref}: {principle['rule']}")
        lines.append("")
    return "\n".join(lines)


def digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def selection_envelope(
    *,
    consumer: str | None,
    catalog_digest: str,
    selected_ids: list[str],
    xref_ids: list[str],
    tool_adapter: dict | None,
    base_limit: int,
    xref_limit: int,
) -> dict:
    return {
        "consumer": consumer,
        "catalog_digest": catalog_digest,
        "selected_ids": selected_ids,
        "xref_ids": xref_ids,
        "tool_adapter": tool_adapter,
        "budgets": {
            "base_limit": base_limit,
            "xref_limit": xref_limit,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="資料作成の大原則からいま必要な分だけを抽出する")
    parser.add_argument("--applies-to", action="append", default=[],
                        help="slide / report / doc / diagram / chart / delivery / meta（複数可・OR）")
    parser.add_argument("--phase", action="append", default=[],
                        help="purpose / story / research / skeleton / rule / write / diagram / chart / flow / deliver / review / env / ai（複数可・OR）")
    parser.add_argument("--id", action="append", default=[], help="原則 id を直接指定（他の絞り込みを無視する）")
    parser.add_argument("--enforcement", action="append", default=[], help="machine / reviewer / human で更に絞る")
    parser.add_argument("--limit", type=int, default=0,
                        help="基本選択の上限件数。相互参照は含めない。0 で無制限")
    parser.add_argument("--xref-limit", type=int, default=8,
                        help="相互参照補完の別予算。超過は欠落させず exit 2。0 で無制限")
    parser.add_argument("--no-xref", action="store_true", help="rule が名指しする原則の自動補完を止める")
    parser.add_argument("--pin", action="append", default=[],
                        help="--limit で溢れても必ず残す原則 id")
    parser.add_argument("--consumer", help="binding.json の consumer id。絞り込み条件と pin をそこから引く")
    parser.add_argument("--checklist", action="store_true", help="チェックリスト 20 項目を出力して終了")
    parser.add_argument("--tool", choices=["powerpoint", "google-slides", "html"],
                        help="ツール中立 rule を指定ツール向けの薄い brief/checklist へ投影")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    root = catalog_dir()
    consumer_id = args.consumer
    requested_format = args.format
    requested_tool = args.tool

    if args.consumer:
        argv, pins = resolve_consumer(root, args.consumer)
        if "--checklist" in argv:
            args.checklist = True
        else:
            projected_args = argv + ["--format", requested_format]
            if requested_tool:
                projected_args += ["--tool", requested_tool]
            args = parser.parse_args(projected_args)
            args.pin = pins
            args.consumer = consumer_id

    catalog = load_catalog(root)
    catalog_digest = digest_file(root / "principles.json")
    tool_adapter = load_tool_adapter(root, args.tool)

    if args.checklist:
        selected_ids = sorted({ref for item in catalog["checklist"]["items"] for ref in item["refs"]})
        envelope = selection_envelope(
            consumer=consumer_id,
            catalog_digest=catalog_digest,
            selected_ids=selected_ids,
            xref_ids=[],
            tool_adapter=tool_adapter,
            base_limit=0,
            xref_limit=args.xref_limit,
        )
        if args.format == "json":
            print(json.dumps({"selection": envelope, "checklist": catalog["checklist"]},
                             ensure_ascii=False, indent=2))
        else:
            print(render_checklist(catalog, tool_adapter))
        return 0

    axes = catalog["axes"]
    for name, values in (("applies_to", args.applies_to), ("phase", args.phase), ("enforcement", args.enforcement)):
        unknown = [v for v in values if v not in axes[name]]
        if unknown:
            sys.stderr.write(f"[select-deck-principles] {name} に未知の値: {', '.join(unknown)}\n"
                             f"  取りうる値: {', '.join(axes[name])}\n")
            return 2

    if args.id:
        wanted = set(args.id)
        selected = [p for p in catalog["principles"] if p["id"] in wanted]
        missing = wanted - {p["id"] for p in selected}
        if missing:
            sys.stderr.write(f"[select-deck-principles] 存在しない id: {', '.join(sorted(missing))}\n")
            return 2
    else:
        if not args.applies_to and not args.phase:
            sys.stderr.write("[select-deck-principles] --applies-to か --phase を最低 1 つ指定してください"
                             "（全件出力は context を食い潰すため許可しない）\n")
            return 2
        selected = [p for p in catalog["principles"] if matches(p, args.applies_to, args.phase)]

    if args.enforcement:
        selected = [p for p in selected if p["enforcement"] in args.enforcement]

    if args.limit and len(selected) > args.limit:
        # pin されたものは rank に関係なく残す。limit は残り枠にだけ効く。
        # こうしないと「その局面で必ず要る原則」が一般論だという理由で落ちる。
        pinned = [p for p in selected if p["id"] in set(args.pin)]
        if len(pinned) > args.limit:
            sys.stderr.write(f"[select-deck-principles] --limit {args.limit} が pin 件数 {len(pinned)} を下回っています\n")
            return 2
        rest = [p for p in selected if p["id"] not in set(args.pin)]
        rest.sort(key=lambda p: rank(p, args.applies_to, args.phase))
        selected = pinned + rest[:args.limit - len(pinned)]

    selected.sort(key=lambda p: p["no"])
    xrefs = [] if (args.no_xref or args.id) else collect_xrefs(selected, catalog)
    if args.xref_limit and len(xrefs) > args.xref_limit:
        sys.stderr.write(f"[select-deck-principles] 相互参照 {len(xrefs)} 件が --xref-limit "
                         f"{args.xref_limit} を超えました（依存を黙って欠落させないため中止）\n")
        return 2

    envelope = selection_envelope(
        consumer=consumer_id,
        catalog_digest=catalog_digest,
        selected_ids=[p["id"] for p in selected],
        xref_ids=[p["id"] for p in xrefs],
        tool_adapter=tool_adapter,
        base_limit=args.limit,
        xref_limit=args.xref_limit,
    )

    if args.format == "json":
        print(json.dumps({"selection": envelope, "selected": selected, "xrefs": xrefs},
                         ensure_ascii=False, indent=2))
    else:
        print(render_markdown(
            selected,
            xrefs,
            catalog,
            consumer=consumer_id,
            catalog_digest=catalog_digest,
            tool_adapter=tool_adapter,
            base_limit=args.limit,
            xref_limit=args.xref_limit,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
