"""system-briefing-book 設計ノートの可変な主張が正本とずれないことを保証する。

設計ノートは「なぜその形にしたか」を残す散文だが、その論拠として skill の一覧・
質問の数・H 番号の範囲・答えの出どころ・配色の名前といった正本側の事実を引用している。
引用は書いた時点では正しくても、正本が動けば静かに古くなる。ここでは散文のうち
**正本から導出できる主張だけ** を突き合わせ、乖離を落として気づけるようにする。

期待値はこのテストに直書きせず、hearing-catalog.json・hearing-guide.md・SKILL.md・
document-structure.md・schema から組み立てる。直書きすると正本とテストを一緒に直すだけで緑になり、
ノートだけが古いまま取り残される。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "system-briefing-book"
DOC = ROOT / "doc" / "system-briefing-book-設計ノート.md"
HEARING = PLUGIN / "skills" / "run-briefing-hearing"
CATALOG = PLUGIN / "assets" / "data" / "hearing-catalog.json"


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def _question_rows() -> list[dict[str, str]]:
    """質問の正本 hearing-catalog.json を読む (記号・番号・聞く回)。聞かない質問の回は空にする。"""
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = [
        {"id": q["key"], "h": q["id"], "round": "" if q["round"] is None else str(q["round"])}
        for q in catalog["questions"]
    ]
    assert rows, "hearing-catalog.json の questions が読み取れなかった (形が変わった可能性)"
    return rows


def test_skill_table_matches_skill_dirs() -> None:
    text = _doc_text()
    rows = set(re.findall(r"^\| `([a-z-]+)` \| .+ \|$", text, re.M))
    skills = {p.parent.name for p in (PLUGIN / "skills").glob("*/SKILL.md")}

    assert rows, "設計ノートの skill 表が読み取れなかった (表の書式が変わった可能性)"
    assert rows == skills, (
        "設計ノートの skill 表と plugin の skills/ がずれている。\n"
        f"  ノート側: {sorted(rows)}\n  実体側:   {sorted(skills)}"
    )
    assert f"## 2. {len(skills)} つの skill に割った理由" in text


def test_relative_links_resolve() -> None:
    text = _doc_text()
    links = [
        target.split("#", 1)[0]
        for target in re.findall(r"\]\(([^)]+)\)", text)
        if not target.startswith(("http://", "https://", "#"))
    ]
    assert links, "設計ノートが正本へのリンクを 1 つも持っていない (書式が変わった可能性)"
    missing = [t for t in links if not (DOC.parent / t).resolve().exists()]
    assert not missing, f"設計ノートのリンク先が実在しない: {missing}"


def test_question_counts_are_derived_from_hearing_guide() -> None:
    text = _doc_text()
    rows = _question_rows()
    asked = [r for r in rows if r["round"]]
    per_round = Counter(r["round"] for r in asked)
    total, n_asked = len(rows), len(asked)

    assert f"質問は {total} 問" in text
    assert f"聞くのは {n_asked} 問" in text
    assert f"1 回 {max(per_round.values())} 問 × {len(per_round)} 回" in text
    assert f"残りの {total - n_asked} 問は既定案" in text


def test_h_number_ranges_follow_hearing_guide() -> None:
    text = _doc_text()
    rows = _question_rows()
    guide = (HEARING / "references" / "hearing-guide.md").read_text(encoding="utf-8")
    total = len(rows)

    numbers = sorted(int(r["h"][1:]) for r in rows)
    assert numbers == list(range(1, total + 1)), "質問の H 番号が H01 から連番になっていない"

    # もとからの質問の範囲は hearing-guide.md の文から読む。足した質問の範囲と続きの番号は、
    # その範囲と質問の総数から導く。
    m = re.search(r"H01〜H(\d{2})を含む既存の番号", guide)
    assert m, "hearing-guide.md から、もとからの質問の H 番号の範囲が読み取れなかった"
    orig = int(m.group(1))
    assert f"H01〜H{orig:02d}" in text
    assert f"H{orig + 1:02d}〜H{total:02d}" in text
    assert f"H{total + 1:02d} から" in text


def test_core_questions_match_hearing_skill() -> None:
    text = _doc_text()
    skill = (HEARING / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"核心の (\d+) 問 \(([^)]+)\)", skill)
    assert m, "run-briefing-hearing の SKILL.md から核心の質問が読み取れなかった"
    n = int(m.group(1))
    assert n == len(m.group(2).split("・"))

    note = re.search(r"核心の (\d+) 問\s*\(([^)]+)\)", text)
    assert note, "設計ノートから核心の質問が読み取れなかった"
    assert int(note.group(1)) == n
    assert len(note.group(2).split("・")) == n, "設計ノートの核心の質問の数と、挙げた項目の数が合わない"


def test_answer_sources_match_document_structure() -> None:
    structure = (PLUGIN / "references" / "document-structure.md").read_text(encoding="utf-8")
    pattern = r"出どころは (`[^`]+`(?: / `[^`]+`)+)"
    canon = re.search(pattern, structure)
    note = re.search(pattern, _doc_text())
    assert canon and note, "答えの出どころの並びが読み取れなかった"
    assert note.group(1) == canon.group(1)
    assert f"の {canon.group(1).count('`') // 2} つ" in _doc_text()


def test_receiving_labels_exist_in_document_structure() -> None:
    structure = (PLUGIN / "references" / "document-structure.md").read_text(encoding="utf-8")
    labels = sorted(set(re.findall(r"`([^`\s]+:)`", _doc_text())))
    assert labels, "設計ノートが仕様書の記入欄を 1 つも挙げていない (書式が変わった可能性)"
    missing = [label for label in labels if f"`{label}`" not in structure]
    assert not missing, f"設計ノートが挙げる記入欄が document-structure.md に無い: {missing}"


def test_palette_name_matches_schema_and_thresholds() -> None:
    text = _doc_text()
    schema = json.loads((PLUGIN / "schemas" / "briefing.schema.json").read_text(encoding="utf-8"))
    consts = [c["const"] for c in schema["properties"]["palette"]["anyOf"] if "const" in c]
    thresholds = json.loads(
        (PLUGIN / "assets" / "data" / "quality-thresholds.json").read_text(encoding="utf-8")
    )

    # 名前つきの配色は 1 つだけで、既定もそれであること。旧名の読み替えを置かない
    # という判断は、schema が名前を 1 つしか受け付けないことと対応する。
    assert len(consts) == 1
    assert thresholds["palette_default"] == consts[0]
    assert f"`{consts[0]}`" in text
