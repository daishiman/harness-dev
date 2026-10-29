"""自由領域 field (priority/assignee/labels) の到達経路を三者一致で固定する。

背景:
  契約 §2 は priority/assignee/labels を「bd 側自由領域」= parity 突合対象外と定める。
  一方 C10 guard (`guard-graph-schema.py`) の BD_MUTATION は `bd update` をサブコマンド
  単位で全面遮断する。bridge が 3 field を転送しなければ、「bridge の管理外」と契約が言う
  field がどの経路からも更新不能になる。

採った方針:
  guard は緩めず、bridge の UPDATE_FIELDS を広げて到達経路を作る。guard を field 単位へ
  細分する案は、フラグの並び・短縮形・後続コマンド連結で fail-closed が破れるため採らない。

本 test が固定する三者一致:
  1. CONTRACT: 契約書が自由領域 3 field の書込経路として bd-bridge --op update を名指す。
  2. GUARD:    bd 直接実行はその 3 field でも遮断され、bridge 経由は遮断されない。
  3. BRIDGE:   3 field が bd update のフラグへ転送され、正規化と fail-closed が効く。
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
HOOKS = PLUGIN / "hooks"
SCRIPTS = PLUGIN / "scripts"
CONTRACT = PLUGIN / "references" / "execution-tracker-contract.md"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# 契約 §2 が parity 突合対象外と定め、かつ bridge 経由でしか到達できない field。
FREE_FIELDS = ("priority", "assignee", "labels")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bridge(monkeypatch):
    module = load(SCRIPTS / "bd-bridge.py", "bd_bridge_free_field_route")
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
        return {"id": args[1] if len(args) > 1 else None, "ok": True}

    monkeypatch.setattr(bridge, "bd", fake_bd)
    return recorded


@pytest.fixture
def guard(monkeypatch):
    module = load(HOOKS / "guard-graph-schema.py", "guard_free_field_route")
    # context_ok は「遮断対象ではない入力」にだけ走る後段。ここでの subprocess は
    # 判定に無関係なので固定し、遮断/許可の差だけを観測する。
    monkeypatch.setattr(module, "context_ok", lambda _root: (True, "{}"))
    return module


def call_bridge(module, monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", [str(module.__file__), *map(str, argv)])
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    code = module.main()
    output = capsys.readouterr().out
    return code, json.loads(output) if output else None


def call_guard(module, monkeypatch, capsys, tmp_path, command: str):
    # guard は所有 marker (.dev-graph/config.json) を持つ repository でだけ判定する。
    marker = tmp_path / ".dev-graph" / "config.json"
    marker.parent.mkdir(exist_ok=True)
    marker.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [module.__file__, "--repo-root", str(tmp_path)])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command}}
    )))
    code = module.main()
    return code, capsys.readouterr().err


def _update_call(calls: list[list[str]]) -> list[str]:
    matching = [args for args in calls if args and args[0] == "update"]
    assert len(matching) == 1, calls
    return matching[0]


def _flag_value(argv: list[str], flag: str) -> str:
    assert flag in argv, argv
    return argv[argv.index(flag) + 1]


# 一致 1: 契約書 ↔ bridge。
def test_contract_names_the_bridge_route_for_every_free_field(bridge):
    """契約が 3 field の書込経路を名指し、それが UPDATE_FIELDS の宣言と一致する。

    契約だけを直しても、bridge だけを直しても、この assertion は落ちる。「突合対象外」を
    「bridge 迂回可」と読み替える退行を文書側から締める。
    """
    clauses = [line for line in CONTRACT.read_text(encoding="utf-8").splitlines()
               if "bd-bridge.py --op update" in line]
    assert clauses, "契約 §2 が自由領域 field の書込経路を明示していること"
    text = "\n".join(clauses)
    declared = dict(sys.modules["bd_bridge_contracts"].UPDATE_FIELDS)
    for field in FREE_FIELDS:
        assert f"`--{field}`" in text, f"契約が --{field} の経路を名指していない"
        assert field in declared, f"bridge が {field} を転送しない"


# 一致 2: guard。field を問わず bd 直接実行は遮断され、bridge 経由は通る。
@pytest.mark.parametrize("command", [
    "bd update BD-1 --priority 1",
    "bd update BD-1 --assignee daishiman",
    "bd update BD-1 --set-labels dev-graph,guard",
    "bd update BD-1 -p 1",
    # 無害な read の後ろへ連結した mutation。field 単位で guard を緩めると、この形が
    # 「自由領域だけの update」を装って通り抜ける。
    "bd show BD-1 | cat && bd update BD-1 --priority 0",
])
def test_guard_blocks_direct_bd_mutation_for_free_fields(guard, monkeypatch, capsys, tmp_path, command):
    code, err = call_guard(guard, monkeypatch, capsys, tmp_path, command)
    assert code == 2, command
    # 遮断理由は既存の正規チョークポイントを示すこと。
    assert "bd-bridge.py" in err


def test_guard_allows_the_bridge_route_and_read_only_bd(guard, monkeypatch, capsys, tmp_path):
    for command in (
        "python3 plugins/dev-graph/scripts/bd-bridge.py --op update --bd-issue-id BD-1 --priority 1",
        "python3 plugins/dev-graph/scripts/bd-bridge.py --op update --bd-issue-id BD-1 --labels a,b",
        "bd show BD-1 --json",
        "bd help update",
    ):
        code, _ = call_guard(guard, monkeypatch, capsys, tmp_path, command)
        assert code == 0, command


# 一致 3: bridge。転送・正規化・fail-closed。
@pytest.mark.parametrize("flag,dest,value,forwarded_flag,forwarded_value", [
    ("--priority", "priority", "high", "--priority", "1"),
    ("--priority", "priority", "P3", "--priority", "3"),
    ("--assignee", "assignee", "daishiman", "--assignee", "daishiman"),
    ("--labels", "labels", "dev-graph, guard", "--set-labels", "dev-graph,guard"),
])
def test_free_field_is_forwarded_with_normalization(
    bridge, calls, monkeypatch, capsys, tmp_path, flag, dest, value, forwarded_flag, forwarded_value,
):
    code, receipt = call_bridge(
        bridge, monkeypatch, capsys,
        "--op", "update", "--repo-root", tmp_path, "--bd-issue-id", "B1", flag, value,
    )
    assert code == 0
    assert _flag_value(_update_call(calls), forwarded_flag) == forwarded_value
    assert receipt["applied_fields"] == [dest]


def test_dry_run_preview_shows_the_normalized_value(bridge, calls, monkeypatch, capsys, tmp_path):
    """preview は転送値を見せる。生値のままだと apply 時の畳み込みが観測できない。"""
    code, receipt = call_bridge(
        bridge, monkeypatch, capsys,
        "--op", "update", "--repo-root", tmp_path, "--bd-issue-id", "B1",
        "--priority", "critical", "--labels", "a, b", "--dry-run",
    )
    assert code == 0
    preview = receipt["dry_run_preview"]
    assert preview["priority"] == "0"
    assert preview["labels"] == "a,b"
    assert preview["applied_fields"] == ["priority", "labels"]
    # HD の dry-run は apply と同じ read (bd show) まで進むが、書込 (bd update) は起動しない。
    assert not [args for args in calls if args[0] == "update"]


@pytest.mark.parametrize("labels", ["", "a,,b", "a, ,b", ","])
def test_labels_rejects_empty_entries_before_write(bridge, calls, monkeypatch, capsys, tmp_path, labels):
    """空 label は書込前に落とす。bd の strings フラグは空値の意味論を公開していない。"""
    from _common import ContractError

    with pytest.raises(ContractError, match="non-empty"):
        call_bridge(
            bridge, monkeypatch, capsys,
            "--op", "update", "--repo-root", tmp_path, "--bd-issue-id", "B1", "--labels", labels,
        )
    assert calls == []


def test_update_priority_rejects_unknown_vocabulary_before_write(bridge, calls, monkeypatch, capsys, tmp_path):
    """update の priority 語彙は create と同じ関数で判定する (op で解釈が割れない)。"""
    from _common import ContractError

    with pytest.raises(ContractError, match="priority must be"):
        call_bridge(
            bridge, monkeypatch, capsys,
            "--op", "update", "--repo-root", tmp_path, "--bd-issue-id", "B1", "--priority", "urgent",
        )
    assert calls == []


@pytest.mark.parametrize("flag,value", [("--assignee", "daishiman"), ("--labels", "a,b")])
def test_update_only_fields_are_rejected_on_other_ops(bridge, calls, monkeypatch, capsys, tmp_path, flag, value):
    """update 専用 field を別 op へ渡す要求は落とす (成功 receipt を返す silent drop の防止)。"""
    from _common import ContractError

    with pytest.raises(ContractError, match="only by --op update"):
        call_bridge(
            bridge, monkeypatch, capsys,
            "--op", "close", "--repo-root", tmp_path, "--bd-issue-id", "B1", flag, value,
        )
    assert calls == []


def test_priority_is_rejected_outside_create_or_update(bridge, calls, monkeypatch, capsys, tmp_path):
    """create と update 以外の priority は silent drop せず、書込前に拒否する。"""
    from _common import ContractError

    with pytest.raises(ContractError, match="create or --op update"):
        call_bridge(
            bridge, monkeypatch, capsys,
            "--op", "close", "--repo-root", tmp_path, "--bd-issue-id", "B1", "--priority", "high",
        )
    assert calls == []
