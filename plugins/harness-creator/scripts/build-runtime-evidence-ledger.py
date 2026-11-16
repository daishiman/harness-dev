#!/usr/bin/env python3
# /// script
# name: build-runtime-evidence-ledger
# purpose: capability-build の dispatcher (TG-C06) が user-owned runtime node (install/enable/trust/new-session/uninstall/PR) を保留して終えるときの runtime-evidence-ledger.json 書き手。local 証跡 artifact の sha256・task-state の graph_hash pin・UTC 時刻・schema_version を機械で埋め、TG-C08 (record-task-graph-knowledge.py) と同じ validate_runtime_pending_ledger で検証してから同じ dir の一時ファイル経由で一括で書く。検証に落ちたら何も書かない。
# inputs:
#   - argv: --task-state P --artifact PURPOSE=PATH (local_build/native_parity/rollback を各1回)
#           --gates P|- [--plan-dir PLAN_DIR] [--out P] [--boundary TEXT] [--dry-run]
#   - file: <task-state> (graph_hash と、--plan-dir 省略時の node 列) / <PLAN_DIR>/task-graph.json /
#           --gates の JSON (install/enable/trust/new_session/uninstall/pr の 6 gate を
#           {state, task_ids, artifact_refs, reason} で全部書く) / --artifact が指す build dir 相対の証跡
# outputs:
#   - stdout: {"status": "written"|"dry_run"|"invalid"|"input_error", "path", "graph_hash",
#             "gates"{id: state}, "violations"[]} の JSON (input_error のときは violations に理由 1 件)
#   - stderr: usage / 入力の読込・parse 失敗の説明
#   - exit: 0=書いた (--dry-run は検証だけ通った) / 1=ledger が検証に落ちた (何も書かない) /
#           2=usage・入力の読込/parse 失敗・--out が build dir の外 (何も書かない)
#   - write-scope: <build_dir>/runtime-evidence-ledger.json。build_dir は --task-state の dir で、
#           --out は同じ build_dir の中の別名 .json だけを許す (一時ファイル→os.replace、0644 相当)
# contexts: [C, E]
# network: false
# write-scope: <build_dir>/runtime-evidence-ledger.json
# dependencies: []
# requires-python: ">=3.10"
# ///
"""runtime-evidence-ledger.json の書き手 (TG-C06 dispatcher が使う)。

TG-C08 (record-task-graph-knowledge.py) の完了ゲート第3段は、P13 の user-owned runtime node を
この ledger が task id 単位で列挙したときだけ保留を認める。ledger を手で書くと sha256 の写し間違い・
graph_hash の取り違え・UTC でない時刻が混ざり、TG-C08 が invalid で止まって初めて気づく。

本 script は判断の要る値 (gate ごとの state・task_ids・artifact_refs・reason) だけを --gates で受け、
機械で決まる値を自分で埋める:

- artifacts[].sha256: --artifact PURPOSE=PATH の実ファイル (ledger と同じ dir からの相対) から計算する
- graph_hash: --task-state の graph_hash をそのまま pin する
- generated_at: 書く時点の UTC (``YYYY-MM-DDTHH:MM:SSZ``)
- schema_version: runtime-evidence-ledger.schema.json の const

入力 (task-state と task-graph) の形は TG-C08 の _task_nodes_shape_error で、組み立てた ledger は
TG-C08 の validate_runtime_pending_ledger と select_ledger_graph_nodes で検証する (どれも sibling
import)。入力の形も ledger も読む側と同じ関数で確かめるので、書けた ledger は TG-C08 も受理する。
違反が 1 件でもあれば書かずに exit 1。通れば同じ dir の一時ファイルへ書いて os.replace で
置き換え、途中で落ちても壊れた ledger を残さない。dispatcher は build lease を解放する前に呼ぶ
(capability-build-runtime-contract.md の release 後書込禁止に従う)。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent

DEFAULT_BOUNDARY = (
    "local evidence (local_build / native_parity / rollback) は build dir の artifact と sha256 で示し、"
    "install / enable / trust / new_session / uninstall / pr は利用者が行う runtime 操作として"
    " gate ごとに分けて記録する"
)


def _load_sibling(stem: str):
    """同じ scripts/ のハイフン名 module を importlib で読み込む。"""
    path = _HERE / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_TG_C08 = _load_sibling("record-task-graph-knowledge")


class InputError(Exception):
    """usage・入力の読込/parse 失敗 (exit 2)。"""


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"{label} 読込/parse 失敗 ({path}): {exc}") from exc


def _read_gates(source: str) -> object:
    if source == "-":
        try:
            return json.loads(sys.stdin.buffer.read().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InputError(f"--gates (stdin) 読込/parse 失敗: {exc}") from exc
    return _read_json(Path(source), "--gates")


def resolve_out_path(out: str | None, task_state_path: Path) -> Path:
    """書く先を build dir (task-state の dir) の中に閉じる。

    artifact の path は ledger の dir からの相対で、TG-C08 も既定では task-state の隣を読む。
    別の dir へ書けると write-scope を外れるうえ、証跡の相対 path の意味も変わる。
    """
    build_dir = task_state_path.parent
    if out is None:
        return build_dir / _TG_C08._RUNTIME_LEDGER_NAME
    path = Path(out)
    if path.parent.resolve() != build_dir.resolve():
        raise InputError(f"--out は task-state と同じ build dir の中だけ: {out}")
    if path.suffix != ".json" or path.name.startswith("."):
        raise InputError(f"--out は .json で、. で始まらない名前にする: {out}")
    if path.is_symlink():
        raise InputError(f"--out が symlink: {out}")
    return build_dir / path.name


def _check_shapes(task_state: object, task_graph: object) -> None:
    """入力の形を TG-C08 と同じ関数で検査する。

    書く側だけ緩いと、TG-C08 が後で拒む入力 (id の重複・要素が object でない等) から
    ledger を書けてしまう。同じ関数を呼ぶので、受理する入力の範囲が両者で一致する。
    """
    error = _TG_C08._task_nodes_shape_error(task_state, "--task-state")
    if error is None and task_graph is not None:
        error = _TG_C08._task_nodes_shape_error(task_graph, "task-graph")
    if error is not None:
        raise InputError(error)


def parse_artifact_args(values: list[str], ledger_dir: Path) -> list[tuple[str, str]]:
    """--artifact PURPOSE=PATH を (purpose, ledger dir 相対 path) へ直す。

    絶対パスは ledger dir の中を指すときだけ相対へ直し、外を指すなら schema の confinement
    違反として検証に回す (そのまま残すと validate が path 違反として報告する)。
    """
    out: list[tuple[str, str]] = []
    for raw in values:
        purpose, sep, path_raw = raw.partition("=")
        if not sep or not purpose or not path_raw:
            raise InputError(f"--artifact は PURPOSE=PATH 形式: {raw!r}")
        path = Path(path_raw)
        if path.is_absolute():
            try:
                path_raw = path.resolve().relative_to(ledger_dir.resolve()).as_posix()
            except ValueError:
                pass
        out.append((purpose, path_raw))
    return out


def _artifact_sha256(ledger_dir: Path, path_raw: str) -> str | None:
    """証跡の sha256。path が confinement 違反か実在しなければ None (検証側が違反として報告する)。"""
    path = Path(path_raw)
    if path.is_absolute() or ".." in path.parts:
        return None
    actual = ledger_dir / path
    if not actual.is_file() or not _TG_C08._inside_dir(actual, ledger_dir):
        return None
    try:
        return hashlib.sha256(actual.read_bytes()).hexdigest()
    except OSError:
        return None  # 読めない証跡は validate が理由つきで報告する


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compose_ledger(*, task_state: object, artifacts: list[tuple[str, str]], gates: object,
                   ledger_dir: Path, boundary: str, generated_at: str | None = None) -> dict:
    """機械で決まる値を埋めた ledger を組む。検証はしない (validate_ledger の役割)。"""
    graph_hash = task_state.get("graph_hash") if isinstance(task_state, dict) else None
    return {
        "schema_version": _TG_C08._RUNTIME_LEDGER_VERSION,
        "graph_hash": graph_hash,
        "generated_at": generated_at or _utc_now(),
        "artifacts": [
            {"purpose": purpose, "path": path_raw,
             # 実ファイルが無いときは空文字を入れ、validate に「不在」と「64-hex でない」を報告させる。
             "sha256": _artifact_sha256(ledger_dir, path_raw) or ""}
            for purpose, path_raw in artifacts
        ],
        "gates": gates,
        "boundary": boundary,
    }


def validate_ledger(ledger: dict, *, ledger_path: Path, task_state: object,
                    task_graph: object) -> list[str]:
    """TG-C08 が読むときと同じ関数・同じ照合対象で検証する。"""
    return _TG_C08.validate_runtime_pending_ledger(
        ledger,
        ledger_path=ledger_path,
        expected_graph_hash=task_state.get("graph_hash") if isinstance(task_state, dict) else None,
        graph_nodes=_TG_C08.select_ledger_graph_nodes(task_state, task_graph),
    )


def write_ledger_atomic(path: Path, ledger: dict) -> None:
    """同じ dir の一時ファイルへ書いてから os.replace で置き換える。"""
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        # mkstemp は 0600 で作る。他の ledger 読み手 (別 user の CI など) が読めるよう、umask を効かせた 0644 にする。
        umask = os.umask(0)
        os.umask(umask)
        os.fchmod(fd, 0o644 & ~umask)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    # rename 自体を電源断から守るため、dir の entry も fsync する (対応しない FS では諦める)。
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="build-runtime-evidence-ledger.py",
        description="runtime-evidence-ledger.json を検証してから一括で書く (TG-C06 dispatcher 用)。",
    )
    p.add_argument("--task-state", required=True,
                   help="task-state.json (graph_hash を pin する。--out 省略時は同じ dir に書く)")
    p.add_argument("--plan-dir", default=None,
                   help="<PLAN_DIR>/task-graph.json で task id を照合する (TG-C08 に渡す --plan-dir と同じもの)。"
                        "省略時は task-state の node で照合する")
    p.add_argument("--artifact", action="append", default=[], metavar="PURPOSE=PATH",
                   help="local 証跡 (purpose は local_build / native_parity / rollback)。PATH は ledger と"
                        "同じ dir からの相対。sha256 は本 script が計算する")
    p.add_argument("--gates", required=True,
                   help="6 gate の JSON object ファイル (- で stdin)。各 gate は state/task_ids/artifact_refs/reason")
    p.add_argument("--out", default=None,
                   help=f"書く先 (省略時は <task-state の dir>/{_TG_C08._RUNTIME_LEDGER_NAME})。"
                        "task-state と同じ dir の中の .json だけ")
    p.add_argument("--boundary", default=DEFAULT_BOUNDARY,
                   help="local evidence と user-owned runtime state の境界の説明 (非空)")
    p.add_argument("--dry-run", action="store_true", help="検証だけして書かない")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    task_state_path = Path(args.task_state)
    out_path = task_state_path.parent / _TG_C08._RUNTIME_LEDGER_NAME
    try:
        out_path = resolve_out_path(args.out, task_state_path)
        task_state = _read_json(task_state_path, "--task-state")
        task_graph = (_read_json(Path(args.plan_dir) / "task-graph.json", "task-graph")
                      if args.plan_dir else None)
        _check_shapes(task_state, task_graph)
        gates = _read_gates(args.gates)
        artifacts = parse_artifact_args(args.artifact, out_path.parent)
    except InputError as exc:
        print(str(exc), file=sys.stderr)
        print(json.dumps({"status": "input_error", "path": str(out_path), "graph_hash": None,
                          "gates": {}, "violations": [str(exc)]}, ensure_ascii=False))
        return 2

    ledger = compose_ledger(task_state=task_state, artifacts=artifacts, gates=gates,
                            ledger_dir=out_path.parent, boundary=args.boundary)
    violations = validate_ledger(ledger, ledger_path=out_path, task_state=task_state,
                                 task_graph=task_graph)
    gate_states = ({gid: g.get("state") for gid, g in gates.items() if isinstance(g, dict)}
                   if isinstance(gates, dict) else {})
    report = {
        "status": "invalid" if violations else ("dry_run" if args.dry_run else "written"),
        "path": str(out_path),
        "graph_hash": ledger["graph_hash"],
        "gates": gate_states,
        "violations": violations,
    }
    if violations:
        print(json.dumps(report, ensure_ascii=False))
        return 1
    if not args.dry_run:
        try:
            write_ledger_atomic(out_path, ledger)
        except OSError as exc:
            message = f"ledger 書込失敗 ({out_path}): {exc}"
            print(message, file=sys.stderr)
            print(json.dumps({**report, "status": "input_error", "violations": [message]}, ensure_ascii=False))
            return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
