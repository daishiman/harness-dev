"""bd-bridge の external_ref 冪等検索 (projection 再実行での二重起票) の回帰テスト。

二重起票が起きた機序:
  bd 1.1.0 の `bd search --external-contains <ref> --json` は positional query を欠くと
  JSON 行ではなくヘルプ文を stdout へ出す。`bd()` はそれを JSON として解せず
  {"text": ..., "returncode": ...} に退避するため、_find_external からは「既存なし」に化け、
  _create_one が毎回 create を打っていた。positional query を付けても search は title/ID しか
  引かないため、external_ref だけを持つ既存 issue はやはり search に現れない。

既存の test_c27_c28_projection_contract.py の fake_bd は `search` が external_ref で
一致する理想実装なので、この退行を構造的に検出できない。本ファイルは bd 1.1.0 の
実挙動 (search は title/ID しか引かない・引数次第でヘルプ文を返す) を忠実に模し、
list --status all フォールバックと show 再取得が load-bearing であることを固定する。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

NODE = "T07-projection-node"

# bd() が JSON パースに失敗したときに返す形。bd 1.1.0 のヘルプ文出力を再現する。
BD_110_SEARCH_HELP = {
    "text": "Search issues across title and ID (excludes closed issues by default).",
    "returncode": 0,
}
# bd list --json の行は external_ref を持つが issue_type/parent は持たない (実測 2026-07-20)。
LIST_ROW = {"id": "BD-B42", "title": "projected", "status": "open", "external_ref": f"dev-graph:{NODE}"}


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def module():
    return load(SCRIPTS / "bd-bridge.py", "bd_bridge_external_ref")


def wire(module, monkeypatch, *, search, listed, detail=None, created=None):
    """bd 1.1.0 を模した fake を注入し、実際に流れた argv を返す。"""
    calls: list[list[str]] = []

    def fake_bd(args, cwd, check=True):
        calls.append(list(args))
        if args[0] == "search":
            return search
        if args[0] == "list":
            return listed
        if args[0] == "show":
            return detail
        if args[0] == "create":
            return created if created is not None else {"id": "BD-NEW"}
        raise AssertionError(f"unexpected bd call: {args}")

    monkeypatch.setattr(module, "bd", fake_bd)
    return calls


@pytest.mark.parametrize(
    ("blind_search", "label"),
    [([], "search miss"), (BD_110_SEARCH_HELP, "search help text")],
)
def test_find_external_recovers_via_list_when_search_is_blind(module, monkeypatch, tmp_path, blind_search, label):
    """search が空でもヘルプ文でも、list --status all フォールバックが既存を必ず発見する。"""
    calls = wire(module, monkeypatch, search=blind_search, listed=[LIST_ROW])
    found = module._find_external(tmp_path, NODE)
    assert found is not None and found["id"] == LIST_ROW["id"], label
    fallback = next(args for args in calls if args[0] == "list")
    assert fallback[fallback.index("--status") + 1] == "all"
    # ヘルプ文を誘発する no-query 呼び出しへ退行していないこと (positional query が先頭に立つ)。
    assert calls[0][:2] == ["search", NODE]


def test_find_external_short_circuits_when_search_hits(module, monkeypatch, tmp_path):
    """search が当たれば list --limit 10000 を引かない。

    フォールバックだけを検査すると、search 呼び出しを消して常に全件 list する実装へ
    退化しても全テストが緑のまま通る。高速経路が生きていることを別途固定する。
    """
    calls = wire(module, monkeypatch, search=[LIST_ROW], listed=[])
    assert module._find_external(tmp_path, NODE)["id"] == LIST_ROW["id"]
    assert [args[0] for args in calls] == ["search"]


def test_find_external_requires_exact_external_ref_match(module, monkeypatch, tmp_path):
    """部分一致 (前方/後方) を既存扱いすると別ノードへ誤って冪等化するため、完全一致のみ採る。"""
    near = [
        {**LIST_ROW, "id": "BD-B43", "external_ref": f"dev-graph:{NODE}-legacy"},
        {**LIST_ROW, "id": "BD-B44", "external_ref": f"dev-graph:legacy-{NODE}"},
    ]
    wire(module, monkeypatch, search=near, listed=near)
    assert module._find_external(tmp_path, NODE) is None


def test_create_one_reuses_list_discovered_issue_instead_of_double_creating(module, monkeypatch, tmp_path):
    """冪等の核: search が盲目でも create を打たず idempotent を返す (二重起票の回帰ガード)。"""
    detail = {**LIST_ROW, "issue_type": "task", "parent": "BD-EPIC"}
    calls = wire(module, monkeypatch, search=BD_110_SEARCH_HELP, listed=[LIST_ROW], detail=detail)
    result = module._create_one(
        tmp_path,
        graph_node_id=NODE,
        title="projected",
        description="body",
        issue_type="task",
        parent="BD-EPIC",
    )
    assert result == {"id": LIST_ROW["id"], "external_ref": NODE, "idempotent": True}
    assert not any(args[0] == "create" for args in calls)


def test_create_one_refetches_detail_because_list_rows_omit_type_and_parent(module, monkeypatch, tmp_path):
    """list 行は issue_type/parent を持たないため show 再取得が必須。省くと不整合が素通りする。"""
    def run(detail):
        wire(module, monkeypatch, search=BD_110_SEARCH_HELP, listed=[LIST_ROW], detail=detail)
        return module._create_one(
            tmp_path, graph_node_id=NODE, title="projected", description="body",
            issue_type="task", parent="BD-EPIC",
        )

    with pytest.raises(module.ContractError, match="has type epic, expected task"):
        run({**LIST_ROW, "issue_type": "epic", "parent": "BD-EPIC"})
    with pytest.raises(module.ContractError, match="belongs to a different epic"):
        run({**LIST_ROW, "issue_type": "task", "parent": "BD-OTHER"})


def test_find_external_fails_closed_on_open_plus_closed_remnant(module, monkeypatch, tmp_path):
    """同一 external_ref を open+closed が併存したときの方針をテストで固定する。

    併存が実測 0 組でも、方針を機械強制しないと再発時に「どちらを正とするか」が
    実行時の運のみで決まる。

    確定方針は purge (fail-closed): closed 残骸は external_ref を剥離して運用し、
    併存を検出したら projection を止める。closed issue 自体は監査証跡として残す
    (剥離するのは external_ref のみ)。open 側を暗黙採用する fail-open は、
    重複検知を弱めて二重起票の再発を隠すため採らない。
    """
    remnant = [
        {**LIST_ROW, "id": "BD-OLD", "status": "closed"},
        {**LIST_ROW, "id": "BD-B42", "status": "open"},
    ]
    wire(module, monkeypatch, search=BD_110_SEARCH_HELP, listed=remnant)
    with pytest.raises(module.ContractError, match=f"duplicate beads external_ref for {NODE}"):
        module._find_external(tmp_path, NODE)
