#!/usr/bin/env python3
"""資料作成の大原則カタログの整合を検査する（fail-closed）。

principles.json は 177 原則の唯一の正本なので、欠番・参照切れ・値域外が
そのまま全 agent の判断へ流れる。ここで落とす。

  python3 scripts/validate-deck-principles.py
  python3 scripts/validate-deck-principles.py --vendor-target ../guide-doc-generator/assets/deck-principles/principles.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

CATALOG_RELPATH = Path("references") / "deck-principles" / "principles.json"
SCHEMA_RELPATH = Path("schemas") / "deck-principles.schema.json"
BINDING_RELPATH = Path("references") / "deck-principles" / "binding.json"
BINDING_SCHEMA_RELPATH = Path("schemas") / "deck-principles-binding.schema.json"
VENDOR_MANIFEST_RELPATH = Path("references") / "deck-principles" / "vendor-manifest.json"
TOOL_ADAPTERS_RELPATH = Path("references") / "deck-principles" / "tool-adapters.json"


def plugin_root() -> Path:
    for key in ("SRG_ROOT", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        value = os.environ.get(key)
        if value and (Path(value) / CATALOG_RELPATH).is_file():
            return Path(value)
    return Path(__file__).resolve().parent.parent


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def check(self, condition: bool, code: str, message: str) -> None:
        if not condition:
            self.errors.append(f"[{code}] {message}")

    def fail(self, code: str, message: str) -> None:
        self.errors.append(f"[{code}] {message}")


def validate_schema(instance: dict, schema_path: Path, label: str, report: Report) -> None:
    """versioned schema を検査する。検査器不在を PASS に畳まない。"""
    try:
        import jsonschema  # type: ignore
    except ImportError:
        report.fail("P0", f"{label} schema を検査できません: jsonschema が未導入です")
        return
    if not schema_path.is_file():
        report.fail("P0", f"{label} schema がありません: {schema_path}")
        return
    with schema_path.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    validator = jsonschema.Draft7Validator(schema)
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        location = "/".join(str(part) for part in error.path) or "(root)"
        report.fail("P0", f"{label} schema 違反 {location}: {error.message}")


def validate_numbering(catalog: dict, report: Report) -> None:
    """no が 1..N で欠番・重複なし、かつ id と一致すること。

    出典の通し番号との対応が崩れると『全部網羅した』という主張が検証不能になる。
    """
    principles = catalog["principles"]
    numbers = [p["no"] for p in principles]
    expected = list(range(1, len(principles) + 1))
    report.check(sorted(numbers) == expected, "P1",
                 f"no が 1..{len(principles)} の連番になっていません（欠番または重複）: "
                 f"欠={sorted(set(expected) - set(numbers))} 重複={sorted({n for n in numbers if numbers.count(n) > 1})}")
    for principle in principles:
        report.check(principle["id"] == f"DP-{principle['no']:03d}", "P2",
                     f"id と no が不整合: {principle['id']} ⇔ no={principle['no']}")
    ids = [p["id"] for p in principles]
    report.check(len(set(ids)) == len(ids), "P3", "id が重複しています")


def validate_taxonomy(catalog: dict, report: Report) -> None:
    """group → chapter の親子関係と、章が宣言する no 区間との一致。"""
    groups = {g["id"]: g for g in catalog["groups"]}
    chapters = {c["id"]: c for c in catalog["chapters"]}

    for group in catalog["groups"]:
        report.check(group["chapter"] in chapters, "P4",
                     f"{group['id']} の chapter {group['chapter']} が chapters に存在しません")

    used_groups = set()
    for principle in catalog["principles"]:
        group = groups.get(principle["group"])
        if group is None:
            report.fail("P5", f"{principle['id']} の group {principle['group']} が groups に存在しません")
            continue
        used_groups.add(group["id"])
        chapter = chapters.get(group["chapter"])
        if chapter is None:
            continue
        low, high = (int(part) for part in chapter["principles"].split("-"))
        report.check(low <= principle["no"] <= high, "P6",
                     f"{principle['id']} (no={principle['no']}) は {group['id']} 経由で {chapter['id']} に属しますが、"
                     f"{chapter['id']} の宣言区間 {chapter['principles']} の外です")

    orphan = set(groups) - used_groups
    report.check(not orphan, "P7", f"どの原則も属していない group: {', '.join(sorted(orphan))}")


def validate_axes(catalog: dict, report: Report) -> None:
    """applies_to / phase / enforcement が axes の値域内であること。"""
    axes = catalog["axes"]
    for principle in catalog["principles"]:
        for name in ("applies_to", "phase"):
            unknown = [v for v in principle[name] if v not in axes[name]]
            report.check(not unknown, "P8",
                         f"{principle['id']} の {name} に値域外の値: {', '.join(unknown)}")
        report.check(principle["enforcement"] in axes["enforcement"], "P9",
                     f"{principle['id']} の enforcement が値域外: {principle['enforcement']}")


def validate_xrefs(catalog: dict, selector, report: Report) -> None:
    """rule / checklist が名指しする DP-xxx が全て実在すること。

    相互参照が切れていると、抽出器の 1 段補完が黙って何も足さず、
    『字数上限を守れ』とだけ書かれた規範が上限の値なしで agent へ渡る。
    """
    ids = {p["id"] for p in catalog["principles"]}
    for principle in catalog["principles"]:
        refs = selector.extract_xrefs(principle["rule"])
        for ref in refs:
            report.check(ref in ids, "P10", f"{principle['id']} の rule が実在しない {ref} を参照しています")
        report.check(principle["id"] not in refs, "P11",
                     f"{principle['id']} の rule が自分自身を参照しています")

    seen_cl: set[str] = set()
    for item in catalog["checklist"]["items"]:
        report.check(item["id"] not in seen_cl, "P12", f"checklist id が重複: {item['id']}")
        seen_cl.add(item["id"])
        for ref in item["refs"]:
            report.check(ref in ids, "P13", f"{item['id']} が実在しない {ref} を参照しています")


def validate_thresholds_locality(root: Path, catalog: dict, report: Report) -> None:
    """閾値の正本が principles.json 1 箇所であること（prompt / SKILL への写しを検出）。

    数値そのものは一般的すぎて grep できないので、代わりに
    『原則本文をまるごと写した形跡』= 20 文字以上一致する rule を探す。
    """
    targets: list[Path] = []
    for pattern in ("skills/**/*.md", "agents/*.md", "references/*.md"):
        targets.extend(root.glob(pattern))

    probes = [(p["id"], p["rule"][:24]) for p in catalog["principles"] if len(p["rule"]) >= 24]
    for path in targets:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for principle_id, probe in probes:
            if probe in text:
                report.fail("P14",
                            f"{path.relative_to(root)} が {principle_id} の規範文を複製しています"
                            f"（原則本文の正本は principles.json のみ。抽出器経由で読み込んでください）")


def consumer_root(root: Path, plugin: str) -> Path:
    """consumer が属する plugin の root を返す。plugin 同士は兄弟ディレクトリに置かれる。"""
    return root if root.name == plugin else root.parent / plugin


def frontmatter_value(path: Path, key: str) -> str:
    """thin agent adapter の単純な top-level frontmatter 値を返す。"""
    prefix = f"{key}:"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def validate_consumer_scope(root: Path, binding: dict, report: Report) -> None:
    """owner skill 配下 agent を consumer または理由付き除外へ排他的に閉じる。

    binding に既に載った consumer だけを検査しても、agent 一体の登録忘れは永遠に
    見つからない。対象 owner skill を明示し、agent 実体との差集合を通常ゲートで落とす。
    """
    consumers = binding.get("consumers", [])
    plugins = {item.get("plugin") for item in consumers if item.get("plugin")}
    report.check(len(plugins) == 1, "P36",
                 f"1 binding は1 pluginだけを対象にします: {', '.join(sorted(plugins))}")
    if len(plugins) != 1:
        return
    plugin = next(iter(plugins))
    base = consumer_root(root, plugin)
    scope = binding.get("consumer_scope", {})
    owners = set(scope.get("owner_skills", []))
    excluded_entries = scope.get("excluded_agents", [])
    excluded = {item.get("id") for item in excluded_entries if item.get("id")}
    declared = {item.get("id") for item in consumers if item.get("id")}

    expected: set[str] = set()
    agents_dir = base / "agents"
    if not agents_dir.is_dir():
        report.fail("P36", f"consumer scope の agent directory がありません: {agents_dir}")
        return
    for path in sorted(agents_dir.glob("*.md")):
        if frontmatter_value(path, "owner_skill") in owners:
            expected.add(frontmatter_value(path, "name") or path.stem)

    report.check(bool(expected), "P36",
                 f"owner_skills に該当する agent がありません: {', '.join(sorted(owners))}")
    report.check(not (declared & excluded), "P36",
                 f"consumer と excluded_agents が重複: {', '.join(sorted(declared & excluded))}")
    classified = declared | excluded
    report.check(classified == expected, "P36",
                 "agent consumer 分類が閉包していません: "
                 f"未分類={', '.join(sorted(expected - classified)) or '-'} "
                 f"余分={', '.join(sorted(classified - expected)) or '-'}")
    for entry in excluded_entries:
        evidence = base / entry.get("evidence", "")
        report.check(evidence.is_file(), "P36",
                     f"excluded agent {entry.get('id')} の evidence が実在しません: {evidence}")


def validate_delivery(root: Path, consumer: dict, report: Report) -> None:
    """原則が「誰の手で引かれ、どこに書かれているか」を実体と突合する。

    カタログと抽出器が正しくても、agent の prompt 正本に一行も書かれていなければ
    原則は 1 件も適用されない。ここが緑なら配線が実在すると言い切れる。
    """
    cid = consumer["id"]
    base = consumer_root(root, consumer["plugin"])

    # P29: run_by は agent の tools から導出される値なので、実体とズレたら落とす。
    agent_md = base / "agents" / f"{cid}.md"
    if not agent_md.is_file():
        report.fail("P29", f"{cid} の agent 定義がありません: {agent_md}")
    else:
        tools = ""
        for line in agent_md.read_text(encoding="utf-8").splitlines():
            if line.startswith("tools:"):
                tools = line
                break
        has_bash = "Bash" in tools
        expected = "agent" if has_bash else "orchestrator"
        report.check(consumer.get("run_by") == expected, "P29",
                     f"{cid} の run_by={consumer.get('run_by')} が tools と矛盾します"
                     f"（Bash {'あり' if has_bash else 'なし'} なら {expected}）")

    # P30/P31: prompt 正本には機械可読な一行宣言だけを置く。共通説明の複製や
    # substring 推測ではなく、consumer id と実行主体を exact match で突合する。
    prompt = base / consumer["prompt"]
    if not prompt.is_file():
        report.fail("P30", f"{cid} の prompt 正本がありません: {prompt}")
        return
    body = prompt.read_text(encoding="utf-8")
    marker = f"<!-- deck-principles-consumer: {cid}; run-by: {consumer.get('run_by')} -->"
    report.check(body.count(marker) == 1, "P30",
                 f"{cid} の prompt 正本に宣言が1件必要です: {marker}")
    any_marker = re.findall(r"<!--\s*deck-principles-consumer:[^>]+-->", body)
    report.check(len(any_marker) == 1, "P31",
                 f"{cid} の prompt 正本に deck-principles consumer 宣言が複数または不正形式で存在します")


def validate_binding(root: Path, catalog: dict, binding: dict, selector, report: Report) -> None:
    """binding.json の写像が実際に成立するかを検査する。

    ここが本体。『177 原則を持っている』ことと『agent へ届いている』ことは別なので、
    各 consumer の select argv を実際に評価し、宣言した core_refs がその結果に
    含まれるかを確かめる。limit で落ちる core_ref も検出する（宣言と挙動の乖離）。
    """
    validate_consumer_scope(root, binding, report)
    ids = {p["id"] for p in catalog["principles"]}
    axes = catalog["axes"]
    mapped = set(binding.get("mapped_by_filter", {}).get("refs", []))
    enforced = {
        ref
        for entry in binding.get("already_enforced", {}).get("map", [])
        for ref in entry.get("refs", [])
    }
    out_of_scope = set(binding.get("out_of_scope", {}).get("refs", []))

    partitions = {
        "mapped_by_filter": mapped,
        "already_enforced": enforced,
        "out_of_scope": out_of_scope,
    }
    for name, refs in partitions.items():
        report.check(refs <= ids, "P17", f"{name} に実在しない原則: {', '.join(sorted(refs - ids))}")
    names = list(partitions)
    for index, left_name in enumerate(names):
        for right_name in names[index + 1:]:
            overlap = partitions[left_name] & partitions[right_name]
            report.check(not overlap, "P18",
                         f"{left_name} と {right_name} が排他的でありません: {', '.join(sorted(overlap))}")
    classified = mapped | enforced | out_of_scope
    report.check(classified == ids, "P19",
                 "原則分類が閉包していません: "
                 f"未分類={', '.join(sorted(ids - classified)) or '-'} "
                 f"余分={', '.join(sorted(classified - ids)) or '-'}")

    for ref in out_of_scope:
        report.check(ref in ids, "P20", f"out_of_scope に実在しない {ref}")

    for entry in binding.get("already_enforced", {}).get("map", []):
        for ref in entry["refs"]:
            report.check(ref in ids, "P21", f"already_enforced に実在しない {ref}")

    seen: set[str] = set()
    filter_reachable: set[str] = set()
    for consumer in binding["consumers"]:
        cid = consumer["id"]
        report.check(cid not in seen, "P21", f"consumer id が重複: {cid}")
        seen.add(cid)

        validate_delivery(root, consumer, report)

        for ref in consumer.get("core_refs", []):
            report.check(ref in ids, "P22", f"{cid} の core_refs に実在しない {ref}")
            report.check(ref not in out_of_scope, "P23",
                         f"{cid} が {ref} を core_refs に挙げていますが out_of_scope にも入っています")

        argv = consumer["select"]
        if "--checklist" in argv:
            filter_reachable.update(
                ref for item in catalog["checklist"]["items"] for ref in item["refs"]
            )
            continue

        applies_to = [argv[i + 1] for i, a in enumerate(argv) if a == "--applies-to"]
        phases = [argv[i + 1] for i, a in enumerate(argv) if a == "--phase"]
        enforcement = [argv[i + 1] for i, a in enumerate(argv) if a == "--enforcement"]
        limit = next((int(argv[i + 1]) for i, a in enumerate(argv) if a == "--limit"), 0)

        for name, values in (("applies_to", applies_to), ("phase", phases), ("enforcement", enforcement)):
            unknown = [v for v in values if v not in axes[name]]
            report.check(not unknown, "P24", f"{cid} の select が値域外の {name} を指定: {', '.join(unknown)}")
        if not applies_to and not phases:
            report.fail("P25", f"{cid} の select が --applies-to も --phase も持ちません（抽出器が拒否します）")
            continue

        matched = [p for p in catalog["principles"] if selector.matches(p, applies_to, phases)]
        if enforcement:
            matched = [p for p in matched if p["enforcement"] in enforcement]
        matched_ids = {p["id"] for p in matched}
        filter_reachable.update(matched_ids)

        missing = [r for r in consumer.get("core_refs", []) if r in ids and r not in matched_ids]
        report.check(not missing, "P26",
                     f"{cid} の select が core_refs を拾えていません: {', '.join(missing)}"
                     f"（applies_to={applies_to or '*'} phase={phases or '*'} enforcement={enforcement or '*'}）")

        # --consumer 経由では core_refs が pin されるので limit で落ちることはないが、
        # limit が pin 件数を下回ると抽出器が実行時に落ちる。宣言時点で検出する。
        pins = len([r for r in consumer.get("core_refs", []) if r in matched_ids])
        report.check(not limit or limit >= pins, "P27",
                     f"{cid} の --limit {limit} が pin される core_refs {pins} 件を下回ります"
                     f"（該当 {len(matched)} 件。limit を上げるか core_refs を絞る）")

        if limit and len(matched) > limit:
            pinned_ids = set(consumer.get("core_refs", []))
            pinned = [p for p in matched if p["id"] in pinned_ids]
            rest = [p for p in matched if p["id"] not in pinned_ids]
            rest.sort(key=lambda p: selector.rank(p, applies_to, phases))
            selected = pinned + rest[:max(0, limit - len(pinned))]
        else:
            selected = matched
        xrefs = selector.collect_xrefs(selected, catalog)
        xref_limit = next((int(argv[i + 1]) for i, a in enumerate(argv) if a == "--xref-limit"), 8)
        report.check(not xref_limit or len(xrefs) <= xref_limit, "P32",
                     f"{cid} の相互参照 {len(xrefs)} 件が xref budget {xref_limit} を超えます")

    unreachable = mapped - filter_reachable
    report.check(not unreachable, "P33",
                 "mapped_by_filter なのにどの consumer filter にも該当しない原則: "
                 f"{', '.join(sorted(unreachable))}")


def _load_selector(root: Path):
    """ハイフン入りファイル名なので importlib.util で直接読む。"""
    import importlib.util

    path = root / "scripts" / "select-deck-principles.py"
    spec = importlib.util.spec_from_file_location("srg_select_deck_principles", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_vendor_parity(source: Path, target: Path, report: Report) -> None:
    """vendoring 先とのバイト一致。ずれると 2 plugin で別の規範が動く。"""
    if not target.is_file():
        report.fail("P15", f"vendoring 先が存在しません: {target}")
        return
    src = hashlib.sha256(source.read_bytes()).hexdigest()
    dst = hashlib.sha256(target.read_bytes()).hexdigest()
    report.check(src == dst, "P16",
                 f"vendoring 先が正本と不一致です\n  正本 {src}\n  複製 {dst}\n"
                 f"  復旧: cp {source} {target}")


def validate_vendor_manifest(root: Path, report: Report) -> dict:
    """通常実行で canonical source → standalone vendor target を全件検査する。"""
    path = root / VENDOR_MANIFEST_RELPATH
    if not path.is_file():
        report.fail("P34", f"vendor manifest がありません: {path}")
        return {}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.fail("P34", f"vendor manifest を読めません: {exc}")
        return {}
    report.check(manifest.get("schema_version") == 1, "P34",
                 f"vendor manifest schema_version が未対応です: {manifest.get('schema_version')}")
    entries = manifest.get("entries", [])
    report.check(bool(entries), "P34", "vendor manifest entries が空です")
    seen_sources: set[str] = set()
    seen_targets: set[str] = set()
    for entry in entries:
        source_ref = entry.get("source", "")
        target_ref = entry.get("target", "")
        report.check(bool(source_ref and target_ref), "P34", f"vendor entry が不完全です: {entry}")
        report.check(source_ref not in seen_sources, "P34", f"vendor source が重複: {source_ref}")
        report.check(target_ref not in seen_targets, "P34", f"vendor target が重複: {target_ref}")
        seen_sources.add(source_ref)
        seen_targets.add(target_ref)
        source = (root / source_ref).resolve()
        target = (root / target_ref).resolve()
        if not source.is_file():
            report.fail("P34", f"canonical source が存在しません: {source}")
            continue
        validate_vendor_parity(source, target, report)

    excluded = manifest.get("excluded_overlays", [])
    excluded_sources = {entry.get("source") for entry in excluded}
    report.check(not (seen_sources & excluded_sources), "P34",
                 "同じ source が parity entry と excluded overlay の双方にあります: "
                 f"{', '.join(sorted(seen_sources & excluded_sources))}")
    for entry in excluded:
        report.check(bool(entry.get("reason")), "P34",
                     f"excluded overlay に reason がありません: {entry.get('source')}")
    return manifest


def validate_declared_overlays(
    root: Path,
    manifest: dict,
    catalog: dict,
    selector,
    report: Report,
) -> None:
    """byte parity 対象外のplugin-local overlayも、宣言した契約で通常検査する。"""
    for entry in manifest.get("excluded_overlays", []):
        validation = entry.get("validation")
        report.check(validation == "binding-overlay", "P37",
                     f"excluded overlay の validation が未対応です: {validation}")
        if validation != "binding-overlay":
            continue
        target = (root / entry.get("target", "")).resolve()
        if not target.is_file():
            report.fail("P37", f"binding overlay がありません: {target}")
            continue
        try:
            overlay = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            report.fail("P37", f"binding overlay を読めません: {exc}")
            continue
        validate_schema(overlay, root / BINDING_SCHEMA_RELPATH, "binding overlay", report)
        validate_binding(root, catalog, overlay, selector, report)


def validate_tool_adapters(root: Path, report: Report) -> None:
    path = root / TOOL_ADAPTERS_RELPATH
    if not path.is_file():
        report.fail("P35", f"tool adapter registry がありません: {path}")
        return
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.fail("P35", f"tool adapter registry を読めません: {exc}")
        return
    report.check(registry.get("schema_version") == 1, "P35", "tool adapter schema_version が未対応です")
    adapters = registry.get("adapters", {})
    expected = {"powerpoint", "google-slides", "html"}
    report.check(set(adapters) == expected, "P35",
                 f"tool adapter の値域がCLIと不一致です: {', '.join(sorted(adapters))}")
    required = {"label", "brief", "intent_prefix", "intent_suffix", "checklist_prompt"}
    for tool_id, adapter in adapters.items():
        missing = required - set(adapter)
        report.check(not missing, "P35", f"{tool_id} adapter の必須項目欠落: {', '.join(sorted(missing))}")
        extra = set(adapter) - required
        report.check(not extra, "P35", f"{tool_id} adapter の未知項目: {', '.join(sorted(extra))}")
        for field in required & set(adapter):
            report.check(isinstance(adapter[field], str) and bool(adapter[field].strip()), "P35",
                         f"{tool_id}.{field} は空でない文字列が必要です")


def main() -> int:
    parser = argparse.ArgumentParser(description="資料作成の大原則カタログの整合を検査する")
    parser.add_argument("--vendor-target", action="append", default=[],
                        help="バイト一致を検査する vendoring 先（plugin root からの相対 or 絶対）")
    parser.add_argument("--skip-duplication", action="store_true",
                        help="P14（規範文の複製検出）を省略する")
    args = parser.parse_args()

    root = plugin_root()
    catalog_path = root / CATALOG_RELPATH
    if not catalog_path.is_file():
        sys.stderr.write(f"[validate-deck-principles] カタログが見つかりません: {catalog_path}\n")
        return 2

    binding_path = root / BINDING_RELPATH
    if not binding_path.is_file():
        sys.stderr.write(f"[validate-deck-principles] binding が見つかりません: {binding_path}\n")
        return 2
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[validate-deck-principles] JSON を読めません: {exc}\n")
        return 2

    report = Report()
    validate_schema(catalog, root / SCHEMA_RELPATH, "catalog", report)
    validate_schema(binding, root / BINDING_SCHEMA_RELPATH, "binding", report)
    try:
        selector = _load_selector(root)
    except Exception as exc:  # pragma: no cover
        report.fail("P18", f"抽出器を読み込めません: {exc}")
        selector = None
    validate_numbering(catalog, report)
    validate_taxonomy(catalog, report)
    validate_axes(catalog, report)
    if selector is not None:
        validate_xrefs(catalog, selector, report)
        validate_binding(root, catalog, binding, selector, report)
    validate_tool_adapters(root, report)
    if not args.skip_duplication:
        validate_thresholds_locality(root, catalog, report)
    manifest = validate_vendor_manifest(root, report)
    if selector is not None:
        validate_declared_overlays(root, manifest, catalog, selector, report)
    for target in args.vendor_target:
        path = Path(target)
        resolved = (path if path.is_absolute() else root / path).resolve()
        source_refs = [
            entry.get("source", "")
            for entry in manifest.get("entries", [])
            if (root / entry.get("target", "")).resolve() == resolved
        ]
        if source_refs:
            source = (root / source_refs[0]).resolve()
        else:
            candidates = [catalog_path.parent / resolved.name, root / "scripts" / resolved.name]
            source = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])
        if not source.is_file():
            report.fail("P28", f"vendoring 先 {resolved.name} に対応する正本がありません: {source}")
            continue
        validate_vendor_parity(source, resolved, report)

    if report.errors:
        sys.stderr.write("[validate-deck-principles] FAIL\n")
        for error in report.errors:
            sys.stderr.write(f"  {error}\n")
        return 1

    print(f"[validate-deck-principles] PASS "
          f"principles={len(catalog['principles'])} groups={len(catalog['groups'])} "
          f"chapters={len(catalog['chapters'])} checklist={len(catalog['checklist']['items'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
