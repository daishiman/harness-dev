"""SKILL.md の見出しを名前で指す参照が、参照先に実在するかを検査する。

SKILL.md を日本語化したとき `## Key Rules` を `## 守ること` に訳し、見出し名で正本を指していた
プロンプトの参照が切れたまま CI を通った。見出し名の参照はどこからも実行されないため、ここで検査する。
"""
from __future__ import annotations

import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
# 対象はプラグイン内の .md。CHANGELOG.md は履歴なので除く。
DOCS = [p for p in PLUGIN_ROOT.rglob("*.md") if p.name not in {"CHANGELOG.md", "version-history.md"}]
# run-skill-feedback は正本の配布コピーなので表示言語を維持する。
SHARED_TEMPLATE = PLUGIN_ROOT / "skills/run-skill-feedback"
FILE_RX = r"[\w./-]+\.md"
REF_RX = re.compile(r"(?P<file>" + FILE_RX + r")`?\s*[（(の]?\s*(?P<headings>(?:`#{1,6} [^`]+`\s*[/／]?\s*)+)")
HEADING_RX = re.compile(r"`#{1,6} ([^`]+)`")
NAMED_REF_RX = re.compile(r"(?P<file>" + FILE_RX + r")`?\s*の\s*「(?P<heading>[^」]+)」")
LINK_RX = re.compile(r"\[[^\]]*\]\((?P<file>[^()\s]*\.md)#(?P<anchor>[^()\s]+)\)")


def active_text(text: str) -> str:
    """Examples inside fenced blocks are not live heading references."""
    output, fence = [], None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)[0]
            if fence is None:
                fence = token
            elif fence == token:
                fence = None
            continue
        if fence is None:
            output.append(line)
    return "\n".join(output)


def resolve_document(doc: Path, name: str, root: Path) -> Path:
    if name.startswith(("/skills/", "/agents/")):
        name = name.lstrip("/")  # suffix of a documented ${PLUGIN_ROOT}/... path
    if name == "SKILL.md":
        for parent in [doc.parent, *doc.parents]:
            if parent == root.parent:
                break
            candidate = parent / name
            if candidate.is_file():
                return candidate
    parents = [p for p in [doc.parent, *doc.parents] if p == root or root in p.parents]
    for candidate in (p / name for p in parents):
        if candidate.is_file():
            return candidate
    matches = list(root.rglob(name)) if "/" not in name else []
    return matches[0] if len(matches) == 1 else doc.parent / name


def document_headings(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    text = active_text(path.read_text(encoding="utf-8"))
    return {h.replace("`", "") for h in re.findall(r"^#{1,6} (.+?)\s*#*\s*$", text, re.M)}


def heading_reference_errors(doc: Path, root: Path) -> tuple[int, list[str]]:
    from urllib.parse import unquote
    text = active_text(doc.read_text(encoding="utf-8"))
    count, errors = 0, []
    refs = [(m["file"], h, False) for m in REF_RX.finditer(text)
            for h in HEADING_RX.findall(m["headings"])]
    refs += [(m["file"], m["heading"], False) for m in NAMED_REF_RX.finditer(text)]
    refs += [(m["file"], unquote(m["anchor"]), True) for m in LINK_RX.finditer(text)
             if "://" not in m["file"]]
    for name, heading, anchor in refs:
        heading = heading.replace("`", "")
        target = resolve_document(doc, name, root)
        headings = document_headings(target)
        if anchor:
            headings = {re.sub(r"[^\w\s-]", "", h.lower()).replace(" ", "-") for h in headings}
        count += 1
        if heading not in headings:
            errors.append(f"{doc.relative_to(root)}: {name} に見出し {heading!r} が無い")
    return count, errors


def test_all_document_heading_references_resolve():
    # README/RUNBOOK/references/agents に加え、実行スクリプトのコメントも対象。
    documents = DOCS + [p for p in PLUGIN_ROOT.rglob("*.py") if "tests" not in p.parts]
    checked, broken = 0, []
    for doc in documents:
        count, errors = heading_reference_errors(doc, PLUGIN_ROOT)
        checked += count
        broken.extend(errors)
    assert checked, "見出し参照を1件も拾えていない"
    assert not broken, "\n".join(broken)


def test_heading_references_cover_files_and_levels(tmp_path):
    target = tmp_path / "RUNBOOK.md"
    target.write_text("# 実行手順\n### 保存の契約\n", encoding="utf-8")
    source = tmp_path / "agent.md"
    source.write_text("`RUNBOOK.md`（`### 保存の契約`）\n[参照](RUNBOOK.md#保存の契約)\nRUNBOOK.md の「実行手順」\n", encoding="utf-8")
    assert heading_reference_errors(source, tmp_path) == (3, [])
    target.write_text("# 改名した見出し\n", encoding="utf-8")
    assert len(heading_reference_errors(source, tmp_path)[1]) == 3


def test_heading_examples_do_not_create_false_references(tmp_path):
    source = tmp_path / "example.md"
    source.write_text("```markdown\nmissing.md `## example`\n```\n", encoding="utf-8")
    assert heading_reference_errors(source, tmp_path) == (0, [])

def test_no_untranslated_key_rules():
    left = [
        f"{doc.relative_to(PLUGIN_ROOT)}:{i}"
        for doc in DOCS if SHARED_TEMPLATE not in doc.parents
        for i, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), start=1)
        if "Key Rules" in line  # 「## Key Rules」もこれで拾う
    ]
    assert not left, "訳す前の見出し名 Key Rules が残っている:\n" + "\n".join(left)
