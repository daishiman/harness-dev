"""C28 bd-bridge: create/update の field 転送契約。

背景:
  guard-graph-schema.py が beads mutation を bd-bridge.py の単一チョークポイントへ限定する。
  したがって bridge が転送しない field は運用上「存在しない」。update 分岐が --status/--title
  しか転送しないと、(a) --notes/--design の正規経路が無く、(b) 受理した --description が
  黙って捨てられる (成功 receipt を返しながら何も変わらない silent drop)。

本 test が固定する契約:
  1. PASSTHROUGH: UPDATE_FIELDS の exact-set が bd update のフラグへ 1:1 で転送される。
  2. NO SILENT DROP: 受理した field は receipt の applied_fields に必ず現れる。
  3. FAIL-CLOSED: field 皆無の update / notes 置換と追記の同時指定は書込前に拒否する。
  4. CREATE PRIORITY: dev-graph priority を Beads の 0-4 へ正規化して転送する。

fake bd は bridge の ``bd`` を差し替え、preflight も固定するため本物の bd もネットワークも使わない。
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

PROMOTED = {"confirmation_status": "confirmed", "evaluation_status": "pass",
            "implementation_readiness": {"status": "complete"}}


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_main(module, monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", [str(module.__file__), *map(str, argv)])
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    code = module.main()
    output = capsys.readouterr().out
    return code, json.loads(output) if output else None


@pytest.fixture
def bridge(monkeypatch):
    module = load(SCRIPTS / "bd-bridge.py", "bd_bridge_update_passthrough")
    monkeypatch.setattr(
        module, "preflight",
        lambda root, expected=None: {"version": "1.1.0", "workspace_identity": {"workspace_id": "bdw_fixture"}},
    )
    return module


@pytest.fixture
def calls(bridge, monkeypatch):
    recorded: list[list[str]] = []

    def fake_bd(args, *, cwd, check=True):
        recorded.append(list(args))
        if args[0] == "show":
            return {"id": args[1], "status": "open", "dependencies": []}
        if args[0] in {"search", "list"}:
            return []
        if args[0] == "create":
            return {"id": "B9", "status": "open"}
        return {"id": args[1] if len(args) > 1 else None, "ok": True}

    monkeypatch.setattr(bridge, "bd", fake_bd)
    return recorded


def register_graph(root: Path, *node_ids: str) -> None:
    """create の promotion gate が読む graph を fixture root に置く (全 node を昇格済みにする)。"""
    state = root / ".dev-graph"
    state.mkdir(exist_ok=True)
    (state / "config.json").write_text(json.dumps({"local_state": {"graph": ".dev-graph/graph.json"}}))
    (state / "graph.json").write_text(json.dumps({"nodes": [{"graph_node_id": node_id, **PROMOTED} for node_id in node_ids]}))


def _writes(calls: list[list[str]], verb: str) -> list[list[str]]:
    return [args for args in calls if args and args[0] == verb]


def _update_call(calls: list[list[str]]) -> list[str]:
    matching = _writes(calls, "update")
    assert len(matching) == 1, calls
    return matching[0]


def _flag_value(argv: list[str], flag: str) -> str:
    assert flag in argv, argv
    return argv[argv.index(flag) + 1]


# 契約 1/2: 受理 field は bd update へ転送され、receipt にも現れる。
FORWARDED = [
    ("--notes", "notes", "進捗: P03 完了"),
    ("--append-notes", "append_notes", "追記: レビュー指摘 2 件"),
    ("--design", "design", "決定: fail-closed を採用"),
    ("--description", "description", "本文を差し替える"),
    ("--status", "status", "in_progress"),
    ("--title", "title", "新しいタイトル"),
    ("--assignee", "assignee", "daishiman"),
]


@pytest.mark.parametrize("flag,dest,value", FORWARDED)
def test_update_field_is_forwarded_and_reported(bridge, calls, monkeypatch, capsys, tmp_path, flag, dest, value):
    code, receipt = call_main(
        bridge, monkeypatch, capsys,
        "--op", "update", "--repo-root", tmp_path, "--bd-issue-id", "B1", flag, value,
    )
    assert code == 0
    assert _flag_value(_update_call(calls), flag) == value
    assert receipt["applied_fields"] == [dest]


def test_update_forwards_multiple_fields_in_declared_order(bridge, calls, monkeypatch, capsys, tmp_path):
    code, receipt = call_main(
        bridge, monkeypatch, capsys,
        "--op", "update", "--repo-root", tmp_path, "--bd-issue-id", "B1",
        "--notes", "n", "--design", "d", "--status", "in_progress",
    )
    assert code == 0
    argv = _update_call(calls)
    assert argv[:2] == ["update", "B1"] and argv[-1] == "--json"
    # UPDATE_FIELDS の宣言順 = 転送順。呼び出し順に依存しない決定論的な argv を保証する。
    assert receipt["applied_fields"] == ["status", "notes", "design"]
    for flag, value in (("--notes", "n"), ("--design", "d"), ("--status", "in_progress")):
        assert _flag_value(argv, flag) == value


def test_empty_value_is_forwarded_as_explicit_clear(bridge, calls, monkeypatch, capsys, tmp_path):
    """`--notes ""` は「消去の明示指定」。truthiness 判定で黙って落とさない。"""
    code, receipt = call_main(
        bridge, monkeypatch, capsys,
        "--op", "update", "--repo-root", tmp_path, "--bd-issue-id", "B1", "--notes", "",
    )
    assert code == 0
    assert _flag_value(_update_call(calls), "--notes") == ""
    assert receipt["applied_fields"] == ["notes"]


def test_update_fields_cover_every_declared_flag(bridge):
    """UPDATE_FIELDS が exact-set であること (宣言漏れ = 運用上の機能欠落) を固定する。

    priority/assignee/labels は契約 §2 の parity 突合対象外だが、C10 guard が bd 直接実行を
    field で選り分けず遮断する以上、ここに載っていない field は到達経路を持たない。
    labels の写像先が `--set-labels` (置換) であることも併せて固定する。
    """
    contracts = sys.modules["bd_bridge_contracts"]
    assert dict(contracts.UPDATE_FIELDS) == {
        "status": "--status",
        "title": "--title",
        "description": "--description",
        "notes": "--notes",
        "append_notes": "--append-notes",
        "design": "--design",
        "priority": "--priority",
        "assignee": "--assignee",
        "labels": "--set-labels",
    }


# 契約 3: fail-closed。HD の bridge は受理判定 (_require) を preflight と bd show より前に置くため、
# 拒否時は bd を 1 度も起動しない。
def test_update_without_any_field_is_rejected_before_write(bridge, calls, monkeypatch, capsys, tmp_path):
    from _common import ContractError

    with pytest.raises(ContractError, match="at least one of"):
        call_main(bridge, monkeypatch, capsys, "--op", "update", "--repo-root", tmp_path, "--bd-issue-id", "B1")
    assert calls == []


def test_notes_and_append_notes_together_are_rejected(bridge, calls, monkeypatch, capsys, tmp_path):
    from _common import ContractError

    with pytest.raises(ContractError, match="not both"):
        call_main(
            bridge, monkeypatch, capsys,
            "--op", "update", "--repo-root", tmp_path, "--bd-issue-id", "B1",
            "--notes", "replace", "--append-notes", "append",
        )
    assert calls == []


def test_dry_run_previews_fields_without_writing(bridge, calls, monkeypatch, capsys, tmp_path):
    """HD の dry-run は apply と同じ read (bd show) まで進み、書込の argv を返して止まる。"""
    code, receipt = call_main(
        bridge, monkeypatch, capsys,
        "--op", "update", "--repo-root", tmp_path, "--bd-issue-id", "B1",
        "--notes", "n", "--dry-run",
    )
    assert code == 0
    preview = receipt["dry_run_preview"]
    assert preview["applied_fields"] == ["notes"]
    assert preview["notes"] == "n"
    assert preview["result"] == {"planned_bd_args": ["update", "B1", "--notes", "n", "--json"], "write_count": 0}
    assert _writes(calls, "update") == []


def test_dry_run_applies_the_same_acceptance_rules(bridge, calls, monkeypatch, capsys, tmp_path):
    """preview は書込前の最後の砦。受理判定を素通りさせない。"""
    from _common import ContractError

    with pytest.raises(ContractError, match="at least one of"):
        call_main(bridge, monkeypatch, capsys, "--op", "update", "--repo-root", tmp_path, "--bd-issue-id", "B1", "--dry-run")
    assert calls == []


@pytest.mark.parametrize(
    "priority,expected",
    [("critical", "0"), ("high", "1"), ("medium", "2"), ("low", "3"), ("backlog", "4"), ("P3", "3")],
)
def test_create_priority_is_normalized_and_forwarded(bridge, calls, monkeypatch, capsys, tmp_path, priority, expected):
    register_graph(tmp_path, f"G-{priority}")
    code, _ = call_main(
        bridge, monkeypatch, capsys,
        "--op", "create", "--repo-root", tmp_path,
        "--graph-node-id", f"G-{priority}", "--title", "Task", "--priority", priority,
    )
    assert code == 0
    create = _writes(calls, "create")
    assert len(create) == 1
    assert _flag_value(create[0], "--priority") == expected


def test_create_rejects_unknown_priority_before_write(bridge, calls, monkeypatch, capsys, tmp_path):
    from _common import ContractError

    register_graph(tmp_path, "G1")
    with pytest.raises(ContractError, match="priority must be"):
        call_main(
            bridge, monkeypatch, capsys,
            "--op", "create", "--repo-root", tmp_path,
            "--graph-node-id", "G1", "--title", "Task", "--priority", "urgent",
        )
    assert calls == []


def test_create_priority_dry_run_normalizes_without_writing(bridge, calls, monkeypatch, capsys, tmp_path):
    register_graph(tmp_path, "G1")
    code, receipt = call_main(
        bridge, monkeypatch, capsys,
        "--op", "create", "--repo-root", tmp_path,
        "--graph-node-id", "G1", "--title", "Task", "--priority", "low", "--dry-run",
    )
    assert code == 0
    assert receipt["dry_run_preview"]["priority"] == "3"
    assert calls == []


def test_create_priority_rejects_projection_silent_drop(bridge, calls, monkeypatch, capsys, tmp_path):
    from _common import ContractError

    with pytest.raises(ContractError, match="cannot be combined"):
        call_main(
            bridge, monkeypatch, capsys,
            "--op", "create", "--repo-root", tmp_path,
            "--projection-manifest", "projection.json", "--priority", "low", "--dry-run",
        )
    assert calls == []
