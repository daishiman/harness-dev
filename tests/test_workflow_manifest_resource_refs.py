"""workflow-manifest.json の phase が参照する resourceIds が resources[] に定義されていることを検査する。

phase の resourceIds は「その phase で読む資産」の索引で、未定義 id は読み手に解決できない。
run-build-skill で schema 2 件が参照だけ追加されて定義が漏れていたため、全 manifest を対象にする。
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = sorted(ROOT.glob("plugins/*/skills/*/workflow-manifest.json"))


def _with_resources(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data.get("resources"), list) else None


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: str(p.relative_to(ROOT)))
def test_phase_resource_ids_are_defined(path: Path) -> None:
    data = _with_resources(path)
    if data is None:
        pytest.skip("resources[] を持たない manifest")
    defined = {r.get("id") for r in data["resources"]}
    phase_ids = {ph.get("id") for ph in data.get("phases", [])}
    undefined = sorted(
        {rid for ph in data.get("phases", []) for rid in ph.get("resourceIds") or []} - defined
    )
    assert not undefined, f"resources[] に無い resourceIds: {undefined}"
    dangling = sorted(
        (r.get("id"), pid)
        for r in data["resources"]
        for pid in r.get("phaseIds") or []
        if pid not in phase_ids
    )
    assert not dangling, f"phases[] に無い phaseIds: {dangling}"
