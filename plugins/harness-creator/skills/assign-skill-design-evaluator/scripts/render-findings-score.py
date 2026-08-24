#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Score a skill against rubric.json. Emits JSON to stdout.

Usage:
  render-findings-score.py --rubric <path> --target <skill-dir-or-SKILL.md> [--emit-hash]

Implementation notes:
- stdlib only. Rubric files are JSON.
- Findings collected by simple textual checks; complex checks are TODO.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SEVERITY_WEIGHTS = {"high": -20, "medium": -10, "low": -3}
PREFIXES = ("run-", "ref-", "assign-", "wrap-", "delegate-")

# check_rule() が実際に判定する rule id。ここに無い id は「合格」ではなく
# 「未採点」として出力へ現れる。
#
# なぜ集合を別に持つか: check_rule() は if/elif 連鎖の末尾で bare `return None`
# を返す。None は「違反なし」を意味するので、綴りの違う id・まだ実装していない
# id・将来 rubric へ増える id が、すべて満点へ吸い込まれていた。TODO(human)
# rule は pending_human へ退避されるのに未実装 rule は退避されない非対称が
# あり、threshold 80 が「実装しなければ満たされる」へ静かに反転していた。
# 検査していないものを検査したことにしないため、実装済み集合を明示して
# 差分を unscored として申告する (2026-08-14)。
IMPLEMENTED_RULES = frozenset({
    "FM-001", "FM-002", "FM-003", "FM-004", "FM-005",
    "BD-001", "BD-002", "BD-003",
    "NM-001", "NM-002", "NM-003",
    "PD-001", "PD-002",
    "RG-001",
    "KL-001", "KL-002", "KL-003", "KL-004", "KL-005",
    "PG-001", "PG-002", "BND-001", "REG-001",
})

# 機械では判定できず LLM judge が要る rule。満点へ吸わせず pending_human へ出す。
LLM_JUDGE_RULES = {
    "BD-004": "description の trigger と body の手順の 1:1 対応は意味判断が要る (LLM judge)",
}

# rubric 記述が repo 実態と一致せず機械判定できないときの退避用。
# silent pass を避け、pending_human へ明示する。現在は該当 rule なし。
BLOCKED_ON_RUBRIC: dict[str, str] = {}


def rule_applies(rule: dict, kind: str) -> bool:
    """rubric の applies_to_kinds を評価する。

    これを見ないと「対象種別が違うので無関係」と「実装漏れ」が同じ None へ
    潰れる。kind=skill を採点するとき AG-* / HK-* / CM-* は非適用であって
    未採点ではない — 両者を混ぜると被覆率の数字が意味を失う。
    """
    kinds = rule.get("applies_to_kinds") or ["*"]
    return "*" in kinds or kind in kinds


def find_repo_root(start: Path) -> Path | None:
    """skill_dir から上へ辿って repo root を探す。

    BND-001 は .claude-plugin/bundles.json を、REG-001 は scripts/ を見るため、
    skill の外側の座標が要る。見つからなければ None を返し、呼び出し側は
    「判定できなかった」として扱う (repo 外の tmp_path で走るテストのため)。
    """
    for p in [start, *start.parents]:
        if (p / ".claude-plugin" / "bundles.json").is_file() or (p / ".git").exists():
            return p
    return None


def _plugin_dir(skill_dir: Path) -> Path | None:
    """skills/<name>/ の 2 つ上が plugin root。構造が違えば None。"""
    if skill_dir.parent.name == "skills":
        return skill_dir.parent.parent
    return None


def _plugin_name(skill_dir: Path) -> str:
    """eval-log の振り分け先 plugin 名。plugin 外なら 'core'。"""
    plugin = _plugin_dir(skill_dir)
    if plugin is None:
        return "core"
    manifest = _load_json(plugin / ".claude-plugin" / "plugin.json")
    if isinstance(manifest, dict) and manifest.get("name"):
        return str(manifest["name"])
    return plugin.name


def load_rubric(path: Path) -> dict:
    """Load a JSON rubric."""
    return json.loads(path.read_text(encoding="utf-8"))


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_raw = parts[1]
    body = parts[2]
    fm: dict = {}
    for line in fm_raw.splitlines():
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm, body


def check_rule(rule: dict, fm: dict, body: str, skill_dir: Path) -> dict | None:
    rid = rule["id"]
    sev = rule.get("severity", "low")
    name = fm.get("name", "")
    desc = fm.get("description", "")

    def fail(msg: str, loc: str = "") -> dict:
        return {"id": rid, "severity": sev, "area": rule.get("area", ""),
                "message": msg, "loc": loc}

    if rid == "FM-001":
        if not re.fullmatch(r"(run|ref|assign|wrap|delegate)-[a-z0-9][a-z0-9-]*", name) or len(name) > 60:
            return fail(f"name '{name}' violates prefix/kebab/len<=60", "frontmatter.name")
    elif rid == "FM-002":
        jp_triggers = ("とき", "場合", "際", "時に")
        has_en = ("Use when" in desc) or ("Read when" in desc)
        has_jp = any(t in desc for t in jp_triggers)
        if not (has_en or has_jp):
            return fail("description missing trigger phrase "
                        "(〜とき/〜場合/〜際/〜時 or 'Use when'/'Read when')",
                        "frontmatter.description")
    elif rid == "FM-003":
        jp_triggers = ("とき", "場合", "際", "時に")
        has_en = ("Use when" in desc) or ("Read when" in desc)
        if has_en:
            n_when = desc.count("when ")
            m = re.search(r"(Use when|Read when)\s+(.+?)\.\s*$", desc)
            n_clauses = 0
            if m:
                tail = m.group(2)
                parts = re.split(r",\s*|\s+or\s+", tail)
                n_clauses = len([p for p in parts if p.strip()])
            n = max(n_when, n_clauses)
        else:
            n_jp = sum(desc.count(t) for t in jp_triggers)
            m = re.search(r"([^。]*?)(とき|場合|際|時に)", desc)
            n_clauses = 0
            if m:
                head = m.group(1)
                parts = re.split(r"[、・/／]|\s+や\s*", head)
                n_clauses = len([p for p in parts if p.strip()])
            n = max(n_jp, n_clauses)
        if not (2 <= n <= 3):
            return fail(f"trigger count = {n} (expected 2..3)", "frontmatter.description")
    elif rid == "FM-004":
        bad = ["採点する", "JSONで返す", "sha256", "exit code"]
        hit = [b for b in bad if b in desc]
        if hit:
            return fail(f"description contains action detail: {hit}", "frontmatter.description")
    elif rid == "FM-005":
        en_verbs = ("Build", "Score", "Read", "Wrap", "Delegate", "Generate",
                    "Rubric", "Naming", "Claude")
        # 日本語: 冒頭〜句点までの最初の文に動詞語尾が現れれば可
        jp_verb_markers = ("する", "行う", "実行", "生成", "採点", "評価",
                            "構築", "参照", "読み取", "レビュー", "管理",
                            "監査", "集約", "委譲", "観察", "検出")
        first = desc.split(" ", 1)[0] if desc else ""
        starts_en = desc.startswith(en_verbs)
        # 日本語動詞: 最初の句点までに verb marker が含まれる
        head_jp = re.split(r"[。\.]", desc, 1)[0] if desc else ""
        has_jp_verb = any(m in head_jp for m in jp_verb_markers)
        if desc and not (starts_en or has_jp_verb):
            return fail(f"description first phrase '{first}' is not a verb",
                        "frontmatter.description")
    elif rid == "BD-001":
        if "## Purpose & Output Contract" not in body:
            return fail("missing '## Purpose & Output Contract'", "body")
    elif rid == "BD-002":
        if "## Gotchas" not in body:
            return fail("missing '## Gotchas'", "body")
    elif rid == "BD-003":
        n = len(body.splitlines())
        if n > 300:
            return fail(f"body line count {n} > 300", "body")
    elif rid == "BD-004":
        # human-pending; never deduct
        return None
    elif rid == "NM-001":
        if skill_dir.name != name:
            return fail(f"dirname '{skill_dir.name}' != name '{name}'", "naming")
    elif rid == "NM-002":
        if not any(name.startswith(p) for p in PREFIXES):
            return fail("name missing required prefix", "naming")
    elif rid == "NM-003":
        # basic check: scripts must be Python stdlib entrypoints.
        for p in skill_dir.glob("scripts/*"):
            if p.is_file() and p.suffix != ".py":
                return fail(f"scripts/ has non-py file: {p.name}", "naming")
    elif rid == "PD-001":
        n = len(body.splitlines())
        if n > 100:
            refs = skill_dir / "references"
            if not (refs.is_dir() and any(refs.iterdir())):
                return fail("body>100 lines but references/ empty", "progressive-disclosure")
    elif rid == "PD-002":
        # 本文冒頭 30 行に「何を出すか」と「何をしてはいけないか」が揃うか。
        # 読み手が最初の画面で契約と禁則の両方に当たれるかを見る rule なので、
        # 走査幅を 30 行に固定する (末尾にあっても救済しない)。
        head = "\n".join(body.strip().splitlines()[:30])
        has_heading = ("## Purpose" in head) or ("## Output Contract" in head)
        # rule 文の列挙は 'e.g.' 付きで例示であり網羅ではない。rule の名前その
        # ものである 'Key Rule' 見出しを禁則の記述と認めないと、'## Key Rules'
        # を持つ skill が語彙不一致だけで落ちる。逆に語彙を広げすぎると
        # 「それらしい単語を 1 語置けば通る」へ退化するので、rubric が名指しした
        # 語とその見出し形だけに留める。
        has_rule = any(k in head for k in
                       ("MUST", "NEVER", "禁止", "禁則", "必ず", "Key Rule"))
        if not has_heading:
            return fail("body head 30 lines lack '## Purpose' / '## Output Contract'",
                        "progressive-disclosure")
        if not has_rule:
            return fail("body head 30 lines lack a Key Rule / 禁則 "
                        "(MUST / NEVER / 禁止 / 必ず)", "progressive-disclosure")
    elif rid in ("KL-001", "KL-002", "KL-003", "KL-004", "KL-005"):
        declares = "knowledge_loop" in fm
        kdir = _knowledge_dir(skill_dir, allow_plugin_scope=declares)
        if kdir is None and not declares:
            return None  # rubric が明示する skip (knowledge loop を持たない skill)
        return _check_knowledge_loop(rid, kdir, skill_dir, fail)
    elif rid == "PG-002":
        return _check_prompt_anchors(skill_dir, fail)
    elif rid == "PG-001":
        return _check_required_prompts(skill_dir, fm, fail)
    elif rid == "BND-001":
        return _check_bundle_registration(skill_dir, fail)
    elif rid == "REG-001":
        return _check_registration_and_trace(skill_dir, fail)
    elif rid == "RG-001":
        # always satisfied since we emit hash
        return None
    return None


def _load_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _knowledge_entries(kdir: Path) -> list[dict]:
    """カテゴリファイル群から entry を平坦に集める。

    index/router 本体 (knowledge-index.json / router.json / registry.json) は
    目録であって entry ではないので数に入れない。
    """
    meta = {"knowledge-index.json", "router.json", "registry.json"}
    entries: list[dict] = []
    for p in sorted(kdir.glob("*.json")):
        if p.name in meta:
            continue
        data = _load_json(p)
        if isinstance(data, list):
            entries.extend(x for x in data if isinstance(x, dict))
        elif isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    entries.extend(x for x in v if isinstance(x, dict))
    return entries


def _knowledge_dir(skill_dir: Path, allow_plugin_scope: bool) -> Path | None:
    """knowledge/ の実在位置。skill 直下を見て、宣言があるときだけ plugin 直下へ。

    ubm-goal-setting のように複数 skill が 1 つの knowledge base を共有する構成
    では knowledge/ は plugin 直下に置かれるので、そこまで辿れないと共有型が
    まるごと採点対象外になる。一方で plugin 直下を無条件に見ると、harness-creator
    のように plugin knowledge base を持つだけの plugin で、それを使っていない
    30 個の sibling skill まで KL-* の対象へ引きずり込まれる。
    frontmatter の knowledge_loop 宣言を opt-in の境界にして、この skill が
    その loop の担い手だと自ら言っている場合だけ plugin scope を許す。
    """
    local = skill_dir / "knowledge"
    if local.is_dir():
        return local
    if allow_plugin_scope:
        plugin = _plugin_dir(skill_dir)
        if plugin is not None and (plugin / "knowledge").is_dir():
            return plugin / "knowledge"
    return None


def _find_script(skill_dir: Path, name: str) -> Path | None:
    """scripts/<name> を skill 直下 → plugin 直下 の順で探す。"""
    for base in [skill_dir, _plugin_dir(skill_dir)]:
        if base is not None and (base / "scripts" / name).is_file():
            return base / "scripts" / name
    return None


def _check_knowledge_loop(rid: str, kdir: Path | None, skill_dir: Path, fail) -> dict | None:
    """KL-001..005 の決定論部分。

    KL-002 の「quality rubric level>=2」だけは意味判断なので、ここでは 6 フィールド
    の実在までを見る。残余は main() が pending_human へ出す — 機械が見た範囲と
    見ていない範囲を出力上で分ける。
    """
    if rid == "KL-001":
        if kdir is None:
            return fail("knowledge_loop 宣言があるが knowledge/ が無い", "knowledge-loop")
        has_index = (kdir / "knowledge-index.json").is_file() or (kdir / "router.json").is_file()
        if not has_index:
            return fail("knowledge/ に knowledge-index.json も router.json も無い",
                        "knowledge-loop")
        entries = _knowledge_entries(kdir)
        if len(entries) < 3:
            return fail(f"カテゴリファイルの entry 合計 {len(entries)} < 3", "knowledge-loop")
        return None

    if kdir is None:
        # KL-001 が既に「宣言はあるが実体が無い」を high で報告済み。
        # 同じ 1 つの欠落で KL-002..005 まで重ねて減点しない。
        return None

    if rid == "KL-002":
        # 6 required fields。| 区切りはどちらか一方あれば可。
        groups = [("id",), ("title", "content"), ("intent", "purpose"),
                  ("background",), ("keywords", "tags"), ("source",)]
        entries = _knowledge_entries(kdir)
        violations: list[tuple[str, list[str]]] = []
        for e in entries:
            missing = ["|".join(g) for g in groups if not any(k in e for k in g)]
            if missing:
                violations.append((str(e.get("id", "?")), missing))
        if violations:
            # 1 件目で打ち切ると「1 entry の綴り誤り」と「schema がそもそも違う」が
            # 同じ見た目になる。規模と代表例を出して、直し方の判断材料にする。
            fields = sorted({f for _, ms in violations for f in ms})
            ids = ", ".join(i for i, _ in violations[:5])
            return fail(f"必須フィールド欠落 {len(violations)}/{len(entries)} entry "
                        f"(欠落フィールド: {fields} / 例: {ids}"
                        f"{' ほか' if len(violations) > 5 else ''})",
                        "knowledge-loop")
        return None

    if rid == "KL-003":
        # rule が挙げる search_knowledge.py は knowledge-skeleton の参照実装名。
        # ファイル名で縛ると「名前を合わせれば通る」になるので、決定論 stage を
        # 名乗る script のどれかが実際にフィールド重み付けを持つかを見る。
        script = _find_script(skill_dir, "search_knowledge.py")
        candidates = [script] if script else [
            p for base in [skill_dir, _plugin_dir(skill_dir)] if base
            for p in sorted((base / "scripts").glob("*.py")) if "search" in p.name
        ]
        if not candidates:
            return fail("決定論的な検索 stage の script が無い "
                        "(scripts/search_knowledge.py 相当)。AI 意味検索のみは FAIL",
                        "knowledge-loop")
        for p in candidates:
            src = p.read_text(encoding="utf-8", errors="replace")
            if re.search(r"weight", src, re.I):
                return None
        return fail(f"{[p.name for p in candidates]} にフィールド重み付け (weight) が "
                    "見えない — 全文一致のみの検索は FAIL", "knowledge-loop")

    if rid == "KL-004":
        script = _find_script(skill_dir, "record_usage.py")
        if script is None:
            # usage 記録は script でなく別経路の場合もあるので、痕跡を広く探す。
            bases = [b for b in [skill_dir, _plugin_dir(skill_dir)] if b]
            # templates/ は「これから作る skill の雛形」であって、この skill 自身の
            # 配線ではない。除かないと knowledge-skeleton の record_usage.py を
            # 自分の実装として数えてしまう。
            traces = [p for b in bases for p in b.rglob("*.py")
                      if "templates" not in p.parts and "__pycache__" not in p.parts
                      and "usage-log" in p.read_text(encoding="utf-8", errors="replace")]
            if not traces:
                return fail("§12 feedback loop 未配線 (record_usage.py / usage-log.jsonl "
                            "への記録経路が無い)。使われ方が計測されず品質改善が回らない",
                            "knowledge-loop")
            script = traces[0]
        src = script.read_text(encoding="utf-8", errors="replace")
        missing = [k for k in ("matched_ids", "used_ids", "satisfaction", "usage-log.jsonl")
                   if k not in src]
        if missing:
            return fail(f"{script.name} が記録しない項目: {missing}", "knowledge-loop")
        return None

    if rid == "KL-005":
        bases = [b for b in [skill_dir, _plugin_dir(skill_dir)] if b]
        sources = [p for b in bases
                   for p in [b / "SKILL.md", *b.glob("references/*.md"), *b.glob("*.md")]
                   if p.is_file()]
        docs = " ".join(p.read_text(encoding="utf-8", errors="replace") for p in sources)
        # 閾値は knowledge base 側の growth_rules に書かれることもある。
        for meta_name in ("router.json", "knowledge-index.json", "registry.json"):
            meta = kdir / meta_name
            if meta.is_file():
                docs += " " + meta.read_text(encoding="utf-8", errors="replace")
        if not ("500" in docs and "25" in docs):
            return fail("分割閾値 (500行 / 25エントリ) が文書化されていない", "knowledge-loop")
        reg = _load_json(kdir / "registry.json")
        has_lifecycle = False
        if reg is not None:
            blob = json.dumps(reg, ensure_ascii=False)
            has_lifecycle = "status" in blob or "version" in blob
        if not has_lifecycle:
            has_lifecycle = any("deprecated" in e or "status" in e
                                for e in _knowledge_entries(kdir))
        if not has_lifecycle:
            return fail("lifecycle 追跡 (registry status 遷移 / version + 廃棄ルール) が無い",
                        "knowledge-loop")
        return None
    return None


def _check_prompt_anchors(skill_dir: Path, fail) -> dict | None:
    """PG-002: prompts/R<n>-agent-<name>.md ↔ agents/<name>.md の責務アンカー一致。

    prompts/ を持たない skill は対象外。アンカーは agent 側にしか書けないので、
    prompts が指す agent が実在し、かつ同じ R 番号を名乗っているかを見る。
    """
    pdir = skill_dir / "prompts"
    if not pdir.is_dir():
        return None
    plugin = _plugin_dir(skill_dir)
    if plugin is None:
        return None
    for p in sorted(pdir.glob("R*-agent-*.md")):
        m = re.match(r"^(R\d+)-agent-(.+)\.md$", p.name)
        if not m:
            continue
        rid_num, agent_name = m.group(1), m.group(2)
        agent_md = plugin / "agents" / f"{agent_name}.md"
        if not agent_md.is_file():
            return fail(f"{p.name} に対応する agents/{agent_name}.md が無い",
                        "prompt-governance")
        text = agent_md.read_text(encoding="utf-8", errors="replace")
        # rubric の最小形は '<!-- responsibility: R1 -->'。repo の実運用は
        # prompt ファイル stem をそのまま書く '<!-- responsibility:
        # R1-agent-hearing-facilitator -->' で、こちらは R 番号だけでなく
        # 担当 agent まで固定するぶん強い。両形を受けたうえで、stem 形なら
        # prompt ファイル名との完全一致を要求する — 番号だけ合っていて別 agent
        # の stem が書かれている交差配線を素通しさせない。
        anchors = re.findall(r"<!--\s*responsibility:\s*(\S+?)\s*-->", text)
        if not anchors:
            return fail(f"agents/{agent_name}.md に responsibility アンカーが無い",
                        "prompt-governance")
        if not any(a == rid_num or a == p.stem for a in anchors):
            return fail(f"agents/{agent_name}.md の responsibility アンカー {anchors} が "
                        f"'{rid_num}' / '{p.stem}' のどちらとも一致しない",
                        "prompt-governance")
    return None


def _required_responsibilities(skill_md: Path) -> list[tuple[str, str | None]]:
    """frontmatter responsibilities[] の prompt_required=true だけを読む。

    evaluator を PyYAML 必須にしないため、frontmatter の対象 block
    だけを厳密な縮小パーサで扱う。返値は (id, name)。
    """
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return []
    parts = text.split("---", 2)
    if len(parts) < 3:
        return []
    in_block = False
    rows: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in parts[1].splitlines():
        if not in_block:
            if re.fullmatch(r"responsibilities:\s*", line):
                in_block = True
            continue
        if line and not line[0].isspace():
            break
        item = re.match(r"^\s*-\s+id:\s*['\"]?([^'\"\s#]+)", line)
        if item:
            if current is not None:
                rows.append(current)
            current = {"id": item.group(1), "name": None, "prompt_required": False}
            continue
        if current is None:
            continue
        name = re.match(r"^\s+name:\s*['\"]?(.+?)['\"]?\s*$", line)
        if name:
            current["name"] = name.group(1).strip().strip("'\"")
            continue
        required = re.match(r"^\s+prompt_required:\s*(true|false)\s*$", line, re.I)
        if required:
            current["prompt_required"] = required.group(1).lower() == "true"
    if current is not None:
        rows.append(current)
    return [
        (str(row["id"]), str(row["name"]) if row.get("name") else None)
        for row in rows if row.get("prompt_required") is True
    ]


def _responsibility_ref_paths(skill_md: Path) -> list[str]:
    """frontmatter responsibility_refs[] の明示 path だけを返す。"""
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return []
    parts = text.split("---", 2)
    if len(parts) < 3:
        return []
    in_block = False
    refs: list[str] = []
    for line in parts[1].splitlines():
        if not in_block:
            if re.fullmatch(r"responsibility_refs:\s*", line):
                in_block = True
            continue
        if line and not line[0].isspace():
            break
        item = re.match(r"^\s*-\s*['\"]?([^'\"#]+?)['\"]?\s*$", line)
        if item:
            refs.append(item.group(1).strip())
    return refs


def _prompt_declares_responsibility(path: Path, rid: str) -> bool:
    """explicit ref の内容が同じ responsibility id に束縛されるか。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    escaped = re.escape(rid)
    patterns = (
        rf"`responsibility_id`\s*:\s*`{escaped}`",
        rf"\|\s*responsibility\s*\|\s*`?{escaped}`?(?:\s|\(|\|)",
        rf"責務\s*id\s*は\s*`{escaped}`",
        rf"<!--\s*responsibility:\s*{escaped}\s*-->",
    )
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def _check_required_prompts(skill_dir: Path, fm: dict, fail) -> dict | None:
    """PG-001: required responsibility と canonical Markdown prompt の 1:1 結合。"""
    if fm.get("kind") not in {"run", "assign"}:
        return None
    required = _required_responsibilities(skill_dir / "SKILL.md")
    if not required:
        # 条件は responsibilities[] が明示された target だけ。旧 target へ
        # 実在しない responsibility を推測で生やさない。
        return None
    pdir = skill_dir / "prompts"
    explicit_refs: list[Path] = []
    invalid_refs: list[str] = []
    skill_real = skill_dir.resolve()
    for raw in _responsibility_ref_paths(skill_dir / "SKILL.md"):
        candidate = (skill_dir / raw).resolve()
        try:
            candidate.relative_to(skill_real)
        except ValueError:
            invalid_refs.append(raw)
            continue
        if candidate.parent != (skill_real / "prompts") or candidate.suffix != ".md":
            invalid_refs.append(raw)
            continue
        if candidate.is_file():
            explicit_refs.append(candidate)
    if invalid_refs:
        return fail(f"responsibility_refs が skill-local prompts/*.md 外を指す: {invalid_refs}",
                    "prompt-governance")
    missing: list[str] = []
    ambiguous: list[str] = []
    used: dict[Path, str] = {}
    for rid, name in required:
        candidates = [pdir / f"{rid}.md"]
        # 現行 generator の id=R1 + name=elicit → R1-elicit.md も正準射影。
        # id 自体が R1-elicit なら exact path のみを許す。
        if re.fullmatch(r"R[0-9]+[a-z]?", rid) and name:
            slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
            if slug:
                candidates.append(pdir / f"{rid}-{slug}.md")
        existing = {path.resolve() for path in candidates if path.is_file()}
        existing.update(
            path for path in explicit_refs if _prompt_declares_responsibility(path, rid)
        )
        if not existing:
            missing.append(
                f"{rid}=>expected={[path.name for path in candidates]}, "
                f"explicit_refs={[path.name for path in explicit_refs]}"
            )
        elif len(existing) > 1:
            ambiguous.append(f"{rid}=>{sorted(path.name for path in existing)}")
        else:
            path = next(iter(existing))
            if path in used:
                ambiguous.append(f"{rid}/{used[path]}=>{path.name}")
            used[path] = rid
    if missing:
        return fail(f"prompt_required=true の Markdown prompt が欠落: {missing}",
                    "prompt-governance")
    if ambiguous:
        return fail(f"1 responsibility に複数の canonical prompt が競合: {ambiguous}",
                    "prompt-governance")
    return None


def _check_registration_and_trace(skill_dir: Path, fail) -> dict | None:
    """REG-001: plugin completeness + 存在する per-skill trace の正本検証。"""
    root = find_repo_root(skill_dir)
    plugin = _plugin_dir(skill_dir)
    if root is None or plugin is None:
        return fail("repository/plugin root を解決できない", "governance")
    completeness = root / "scripts" / "validate-plugin-completeness.py"
    validator = (
        root / "plugins" / "harness-creator" / "skills" / "run-build-skill"
        / "scripts" / "validate-build-trace.py"
    )
    for path, label in ((completeness, "plugin completeness validator"),
                        (validator, "canonical build-trace validator")):
        if not path.is_file():
            return fail(f"{label} not found: {path}", "governance")
    try:
        complete = subprocess.run(
            [sys.executable, str(completeness)], cwd=root,
            capture_output=True, text=True, check=False, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return fail(f"validate-plugin-completeness.py を実行できない: {exc}",
                    "governance")
    if complete.returncode != 0:
        detail = complete.stderr.strip() or complete.stdout.strip()
        return fail(f"validate-plugin-completeness.py exit={complete.returncode}: {detail}",
                    "governance")

    trace = root / "eval-log" / plugin.name / skill_dir.name / "skill-build-trace.json"
    if not trace.is_file():
        # per-skill trace 導入前の target は trace 部分のみ N/A。completeness
        # は常に検査し、存在する trace の失敗を N/A に降格しない。
        return None
    try:
        checked = subprocess.run(
            [sys.executable, str(validator), str(trace)], cwd=root,
            capture_output=True, text=True, check=False, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return fail(f"canonical validate-build-trace.py を実行できない: {exc}",
                    "governance")
    if checked.returncode != 0:
        detail = checked.stderr.strip() or checked.stdout.strip()
        return fail(f"canonical validate-build-trace.py exit={checked.returncode}: {detail}",
                    "governance")
    return None


def _is_distributable(plugin: Path, manifest: dict) -> bool:
    """配布対象か。解決規則の SSOT は scripts/build-local-marketplace.py。

    sidecar references/package-contract.json の distribution.distributable を
    優先し、無ければ manifest 直下へ後方互換で落ち、どちらも無ければ配布対象。
    ここで manifest だけを見ると dev-graph / system-dev-planner のように
    sidecar でだけ false を宣言している plugin を配布対象と誤認し、BND-001 が
    偽陽性を出す。判定の置き場所が 2 つある以上、順序ごと写す。
    """
    sidecar = _load_json(plugin / "references" / "package-contract.json")
    if isinstance(sidecar, dict):
        dist = sidecar.get("distribution")
        if isinstance(dist, dict) and "distributable" in dist:
            return dist["distributable"] is not False
    return manifest.get("distributable") is not False


def _check_bundle_registration(skill_dir: Path, fail) -> dict | None:
    """BND-001: plugin が bundles.json のいずれかに登録されているか。

    distributable: false の plugin は配布経路を持たないので対象外。ここを
    見落として『bundles.json へ足す』で緑にすると、配布しない plugin を
    配布物に混ぜる本末転倒になる。
    """
    plugin = _plugin_dir(skill_dir)
    if plugin is None:
        return None
    manifest = _load_json(plugin / ".claude-plugin" / "plugin.json")
    if not isinstance(manifest, dict):
        return None  # plugin 外の skill (repo 直下など) は対象外
    if not _is_distributable(plugin, manifest):
        return None
    root = find_repo_root(skill_dir)
    if root is None:
        return None
    bundles = _load_json(root / ".claude-plugin" / "bundles.json")
    if bundles is None:
        return None
    name = manifest.get("name") or plugin.name
    if name not in json.dumps(bundles, ensure_ascii=False):
        return fail(f"plugin '{name}' が .claude-plugin/bundles.json のどの bundle にも無い",
                    "bundle")
    return None


def compose_rubrics(refs: list[Path], strategy: str, policy: str) -> dict:
    script = Path(__file__).resolve().parents[3] / "scripts" / "compose-rubrics.py"
    if not script.exists():
        script = Path("plugins/skill-governance-automation/scripts/compose-rubrics.py")
    cmd = [
        sys.executable,
        str(script),
        "--rubric-refs",
        *[str(p) for p in refs],
        "--merge-strategy",
        strategy,
        "--conflict-policy",
        policy,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip() or result.stdout.strip(), file=sys.stderr)
        raise SystemExit(2)
    return json.loads(result.stdout)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubric", required=False,
                    help="single rubric (legacy); ignored if --rubric-refs given")
    ap.add_argument("--rubric-refs", nargs="+", default=None,
                    help="ordered list L0..Ln of rubric.json paths to deep-merge")
    ap.add_argument("--conflict-policy", default="most-specific-wins",
                    choices=["most-specific-wins", "error", "warn-and-merge"])
    ap.add_argument("--merge-strategy", default="deep-merge",
                    choices=["deep-merge", "strict", "override", "layered"])
    ap.add_argument("--target", required=True)
    ap.add_argument("--emit-hash", action="store_true")
    ap.add_argument("--kind", default="skill",
                    help="採点対象の capability kind。rubric の applies_to_kinds と "
                         "突き合わせて非適用 rule を被覆率の分母から外す")
    args = ap.parse_args()

    refs: list[Path]
    if args.rubric_refs:
        refs = [Path(p).resolve() for p in args.rubric_refs]
    elif args.rubric:
        print(
            "DEPRECATION: --rubric is legacy single-rubric mode; "
            "use --rubric-refs <L0> [<L1> ...] <L2> (設計書29 §7)",
            file=sys.stderr,
        )
        refs = [Path(args.rubric).resolve()]
    else:
        print("either --rubric or --rubric-refs required", file=sys.stderr)
        return 2

    for rp in refs:
        if not rp.exists():
            print(f"rubric not found: {rp}", file=sys.stderr)
            return 2

    if args.rubric_refs:
        # refs[0] は L0 正本 (ref-skill-design-rubric/references/rubric.json) 必須。
        # 非 L0 先頭は合成順序 (L0→L1→L2) 契約違反として fail-fast する。
        first_layer = load_rubric(refs[0]).get("layer")
        if first_layer != "L0":
            print(
                f"ERROR: --rubric-refs[0] must be the L0 canonical rubric "
                f"(layer=='L0'); got layer={first_layer!r} from {refs[0]}",
                file=sys.stderr,
            )
            return 1
    rubric = compose_rubrics(refs, args.merge_strategy, args.conflict_policy)
    composition_hash = rubric.get("_composition_hash", "")
    # primary rubric hash = first (upstream) layer or only layer
    rubric_path = refs[0]
    rhash = hashlib.sha256(rubric_path.read_bytes()).hexdigest()

    target = Path(args.target).resolve()
    if target.is_dir():
        skill_dir = target
        skill_md = target / "SKILL.md"
    else:
        skill_md = target
        skill_dir = target.parent
    if not skill_md.exists():
        print(f"SKILL.md not found: {skill_md}", file=sys.stderr)
        return 2
    text = skill_md.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)

    kind = args.kind
    has_knowledge = (skill_dir / "knowledge").is_dir() or "knowledge_loop" in fm

    findings: list[dict] = []
    pending_human: list[dict] = []
    not_applicable: list[dict] = []
    unscored: list[dict] = []
    scored_ids: list[str] = []
    for rule in rubric["rules"]:
        rid = rule["id"]
        check_expr = rule.get("check", "")
        if not rule_applies(rule, kind):
            # 対象種別が違う。未採点ではないので被覆率の分母から外す。
            not_applicable.append({
                "id": rid,
                "applies_to_kinds": rule.get("applies_to_kinds") or ["*"],
                "target_kind": kind,
            })
            continue
        if "TODO(human)" in check_expr:
            pending_human.append({"id": rid, "reason": "rubric has TODO(human) marker"})
            continue
        if rid in LLM_JUDGE_RULES:
            pending_human.append({"id": rid, "reason": LLM_JUDGE_RULES[rid]})
            continue
        if rid in BLOCKED_ON_RUBRIC:
            pending_human.append({"id": rid, "reason": BLOCKED_ON_RUBRIC[rid],
                                  "blocked_on": "rubric-text"})
            continue
        if rid not in IMPLEMENTED_RULES:
            # 「検査していない」を「合格」と言わない。severity を保ったまま
            # 申告し、high なら下の passed を落とす。
            unscored.append({"id": rid, "severity": rule.get("severity", "low"),
                             "area": rule.get("area", ""),
                             "reason": "check_rule() に判定実装が無い"})
            continue
        scored_ids.append(rid)
        f = check_rule(rule, fm, body, skill_dir)
        if f:
            findings.append(f)

    if has_knowledge and "KL-002" in scored_ids:
        pending_human.append({
            "id": "KL-002",
            "reason": "6 フィールドの実在は機械判定済み。各値が knowledge-construction.md "
                      "§4.3 の quality level>=2 かどうかは意味判断 (LLM judge)",
        })

    score = 100
    for f in findings:
        score += SEVERITY_WEIGHTS.get(f["severity"], 0)
    score = max(0, min(100, score))
    threshold = int(rubric.get("threshold", "80"))

    applicable = len(scored_ids) + len(pending_human) + len(unscored)
    coverage = {
        "applicable_rules": applicable,
        "scored": len(scored_ids),
        "pending_human": len(pending_human),
        "unscored": len(unscored),
        "not_applicable": len(not_applicable),
        "scored_ratio": round(len(scored_ids) / applicable, 3) if applicable else 1.0,
    }
    # fail-closed: 適用対象なのに判定実装が無い high severity rule が 1 つでも
    # あれば、score が満点でも合格とは言えない。未実装が加点になる経路を塞ぐ。
    unscored_high = [u["id"] for u in unscored if u["severity"] == "high"]

    out = {
        "rubric_id": rubric.get("rubric_id", "skill-design"),
        "rubric_version": rubric.get("rubric_version", "1.0.0"),
        "rubric_hash": f"sha256:{rhash}",
        "composition_hash": composition_hash,
        "rubric_refs": [str(p) for p in refs],
        "target": str(skill_md),
        # eval-log の振り分けキー。write-eval-log.py は record['plugin'] で
        # eval-log/<plugin>/ を決めるので、ここで出さないと全件が core/ へ落ちる。
        "plugin": _plugin_name(skill_dir),
        "skill": skill_dir.name,
        "score": score,
        "threshold": threshold,
        "target_kind": kind,
        "passed": (
            score >= threshold
            and not any(f["severity"] == "high" for f in findings)
            and not unscored_high
        ),
        "coverage": coverage,
        "machine_checks": [],
        "findings": findings,
        "required_fixes": [f for f in findings if f.get("severity") == "high"],
        "pending_human": pending_human,
        "unscored": unscored,
        "not_applicable": not_applicable,
    }
    if unscored_high:
        out["blocking_reason"] = (
            "applicable high-severity rules without a checker implementation: "
            + ", ".join(unscored_high)
        )
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
