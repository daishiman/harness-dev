"""run-dev-graph-schedule SKILL 本文が ready-json の生成手順を消費より前に書いていることを固定する。

`--ready-json` を消費する実行ブロックだけが文書化されていると、初回実行が古い receipt を
掴むか、生成手順を推測することになる。生成 (bd-bridge.py --op ready --parity-manifest) が
消費より前にあり、manifest の由来 (source_graph_digest) が本文で説明されていることを守る。
"""

from __future__ import annotations

import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
SKILL = PLUGIN / "skills" / "run-dev-graph-schedule" / "SKILL.md"
CONTRACT = PLUGIN / "references" / "schedule-graph-contract.md"


def _bash_blocks(text: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL)


def _is_generation(block: str) -> bool:
    # パスの逐語一致は固定しない。正当なパス変更でテストが割れないようにする。
    return "bd-bridge.py" in block and "--op ready" in block and "--parity-manifest" in block and ">" in block


def test_schedule_documents_ready_json_generation_before_consumption() -> None:
    text = SKILL.read_text(encoding="utf-8")
    blocks = _bash_blocks(text)
    consumers = [i for i, block in enumerate(blocks) if "--ready-json" in block and not _is_generation(block)]
    generators = [i for i, block in enumerate(blocks) if _is_generation(block)]

    assert consumers, "schedule SKILL must document a schedule-graph.py invocation consuming --ready-json"
    assert generators, "schedule SKILL must document bd-bridge.py --op ready --parity-manifest ... > <ready-json>"
    assert generators[0] < consumers[0], "ready-json generation must be documented before its consumption"
    assert all("python3 -B" in line for block in blocks[generators[0]:consumers[0] + 1]
               for line in block.splitlines() if ".py" in line)
    for term in ("parity_provenance", "source_graph_digest"):
        assert term in text, f"schedule SKILL must mention the provenance check: {term}"


def test_schedule_skill_links_the_c16_contract_it_cites() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "references/schedule-graph-contract.md" in text
    contract = CONTRACT.read_text(encoding="utf-8")
    # script が出す reason を source から集め、契約の表に無い reason が増えたら落とす。
    script = (PLUGIN / "scripts" / "schedule-graph.py").read_text(encoding="utf-8")
    reasons = set(re.findall(r'"reason": "([a-z_]+)"', script))
    assert {"dependency_unsatisfied", "ready_payload_entry_absent", "graph_node_missing"} <= reasons
    assert sorted(r for r in reasons if f"`{r}`" not in contract) == []
