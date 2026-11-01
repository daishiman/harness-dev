"""published task spec の再実行コマンド解決 (HarnessHub-cc6) の検証。

content-addressed generation の task spec 本文は byte-for-byte 不変で、そこに書かれた
`validate-system-plan.py --repo-root . --staging .` は repository root から解決できない。
generation path を直書きすると再計画のたびに stale になるため、
(1) validator 側に feature 別 current pointer から現行世代を解決する世代非依存経路を持たせ、
(2) executor が読む mutable な task projection へその形のコマンドを冪等配線する。
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import test_runtime as fx

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SYNC_SCRIPT = SCRIPTS / "build-task-projection-rerun.py"
SLUG = "feature-package-feat-x"
PACKAGE_ID = "feature-package/feat-x"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load("test_cc6_validator", "validate-system-plan.py")


def _pointer_repo(tmp_path: Path, *, package_id: str = PACKAGE_ID) -> Path:
    root = tmp_path / "repo"
    pointer_dir = root / ".dev-graph" / "state" / "current"
    pointer_dir.mkdir(parents=True)
    (pointer_dir / f"{SLUG}.json").write_text(json.dumps({
        "feature_package_id": package_id, "generation_id": "gen1",
        "published_path": f".dev-graph/plans/generations/{SLUG}/gen1",
        "published_digest": "sha256:" + "1" * 64,
        "receipt": f".dev-graph/plans/generations/{SLUG}/gen1/atomic-promotion-receipt.json",
    }), encoding="utf-8")
    return root


CONTEXT = {"plan_roots": {"state": {"relative": ".dev-graph/state"}}}


def test_package_slug_matches_promoter_rule() -> None:
    # promote-system-plan.py と同じ規則でなければ pointer を引けない
    assert VALIDATOR._package_slug(PACKAGE_ID) == SLUG


def test_current_pointer_resolves_published_generation(tmp_path: Path) -> None:
    root = _pointer_repo(tmp_path)
    assert VALIDATOR._current_generation(VALIDATOR._resolver(), root, CONTEXT, PACKAGE_ID) == \
        f".dev-graph/plans/generations/{SLUG}/gen1"


def test_pointer_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    root = _pointer_repo(tmp_path, package_id="feature-package/feat-other")
    try:
        VALIDATOR._current_generation(VALIDATOR._resolver(), root, CONTEXT, PACKAGE_ID)
    except ValueError as exc:
        assert "identity mismatch" in str(exc)
    else:
        raise AssertionError("package identity mismatch を拒否していない")


def test_missing_pointer_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / ".dev-graph" / "state" / "current").mkdir(parents=True)
    try:
        VALIDATOR._current_generation(VALIDATOR._resolver(), root, CONTEXT, PACKAGE_ID)
    except ValueError as exc:
        assert "current pointer が無い" in str(exc)
    else:
        raise AssertionError("pointer 不在を拒否していない")


def test_staging_and_feature_package_are_mutually_exclusive() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "validate-system-plan.py"), "--repo-root", ".",
         "--staging", "x", "--feature-package", PACKAGE_ID],
        capture_output=True, text=True, check=False)
    assert proc.returncode == 2
    assert "not allowed with argument" in proc.stderr


def test_one_source_is_required() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "validate-system-plan.py"), "--repo-root", "."],
        capture_output=True, text=True, check=False)
    assert proc.returncode == 2
    assert "one of the arguments" in proc.stderr


def test_current_pointer_symlink_escape_is_rejected(tmp_path: Path) -> None:
    root = _pointer_repo(tmp_path)
    pointer = root / ".dev-graph" / "state" / "current" / f"{SLUG}.json"
    outside = tmp_path / "outside-pointer.json"
    outside.write_bytes(pointer.read_bytes())
    pointer.unlink()
    pointer.symlink_to(outside.resolve())
    c09 = VALIDATOR._resolver()
    try:
        VALIDATOR._current_generation(c09, root, CONTEXT, PACKAGE_ID)
    except c09.PolicyError as exc:
        assert "realpath containment" in str(exc)
    else:
        raise AssertionError("repository 外の current pointer を拒否していない")


# --- projection への rerun 行配線 -------------------------------------------

PROJECTION = """---
graph_node_id: "T1"
feature_package_id: "feature-package/feat-x"
phase_ref: "P01"
---

## 実行契約

- claim: Beads issueをatomic claimする。
- verification: published task spec の Automated commands と Required evidence を全件実行・保存する。
- completion: linked PR merge authority を満たす。
"""


def _projection_repo(tmp_path: Path, body: str = PROJECTION) -> Path:
    # 書込先の containment 検査を C09 へ委ねているため、fixture も C09 が受理する形にする。
    root = (tmp_path / "repo").resolve()
    root.mkdir(parents=True)
    fx.make_repo(root)
    target = root / "tasks" / "feat-x" / "sys-x-p01.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    for number in range(2, 14):
        phase = f"P{number:02d}"
        sibling = target.with_name(f"sys-x-p{number:02d}.md")
        sibling.write_text(
            PROJECTION.replace('graph_node_id: "T1"', f'graph_node_id: "T{number}"')
            .replace('phase_ref: "P01"', f'phase_ref: "{phase}"'),
            encoding="utf-8",
        )
    return root


def _sync(root: Path, *extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
    return subprocess.run([sys.executable, str(SYNC_SCRIPT), "--repo-root", str(root), *extra],
                          capture_output=True, text=True, check=False, env=env)


def test_check_reports_unwired_projection(tmp_path: Path) -> None:
    root = _projection_repo(tmp_path)
    proc = _sync(root, "--check")
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["missing"][0]["reason"] == "世代非依存の rerun 行が未配線"


def test_sync_wires_generation_independent_command(tmp_path: Path) -> None:
    root = _projection_repo(tmp_path)
    assert _sync(root).returncode == 0
    text = (root / "tasks" / "feat-x" / "sys-x-p01.md").read_text(encoding="utf-8")
    assert f"--feature-package {PACKAGE_ID}" in text
    # generation id を直書きしない (再計画で stale にならない)
    assert "gen1" not in text
    lines = text.splitlines()
    assert lines[lines.index(next(l for l in lines if l.startswith("- rerun:"))) - 1].startswith("- verification:")
    assert _sync(root, "--check").returncode == 0


def test_sync_is_idempotent(tmp_path: Path) -> None:
    root = _projection_repo(tmp_path)
    _sync(root)
    first = (root / "tasks" / "feat-x" / "sys-x-p01.md").read_bytes()
    assert json.loads(_sync(root).stdout)["updated"] == []
    assert (root / "tasks" / "feat-x" / "sys-x-p01.md").read_bytes() == first


def test_stale_rerun_line_is_replaced(tmp_path: Path) -> None:
    root = _projection_repo(tmp_path)
    target = root / "tasks" / "feat-x" / "sys-x-p01.md"
    target.write_text(PROJECTION.replace(
        "- completion:", "- rerun: 旧世代 path を直書きした古い指示\n- completion:"), encoding="utf-8")
    assert _sync(root, "--check").returncode == 2
    assert _sync(root).returncode == 0
    text = target.read_text(encoding="utf-8")
    assert "旧世代 path を直書き" not in text
    assert text.count("- rerun:") == 1


def test_projection_without_anchor_fails_closed(tmp_path: Path) -> None:
    root = _projection_repo(tmp_path, body=PROJECTION.replace("- verification:", "- verify:"))
    proc = _sync(root)
    assert proc.returncode == 2
    assert "verification 行が見つからない" in json.loads(proc.stdout)["missing"][0]["reason"]


def test_projection_without_package_id_fails_closed(tmp_path: Path) -> None:
    root = _projection_repo(tmp_path, body=PROJECTION.replace('feature_package_id: "feature-package/feat-x"', ""))
    proc = _sync(root)
    assert proc.returncode == 2
    assert "feature_package_id" in json.loads(proc.stdout)["missing"][0]["reason"]


def test_feature_package_scope_updates_only_the_requested_feature(tmp_path: Path) -> None:
    root = _projection_repo(tmp_path)
    other = root / "tasks" / "feat-y" / "sys-y-p01.md"
    other.parent.mkdir(parents=True)
    other.write_text(PROJECTION.replace(PACKAGE_ID, "feature-package/feat-y"), encoding="utf-8")
    assert _sync(root, "--feature-package", PACKAGE_ID).returncode == 0
    assert "- rerun:" in (root / "tasks" / "feat-x" / "sys-x-p01.md").read_text(encoding="utf-8")
    assert "- rerun:" not in other.read_text(encoding="utf-8")
    report = json.loads(_sync(root, "--feature-package", PACKAGE_ID, "--check").stdout)
    assert report["checked"] == 13
    assert report["missing"] == []


def test_feature_package_scope_with_no_projection_fails_closed(tmp_path: Path) -> None:
    root = _projection_repo(tmp_path)
    proc = _sync(root, "--feature-package", "feature-package/absent", "--check")
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["checked"] == 0


def test_feature_package_scope_requires_exact_13_projections(tmp_path: Path) -> None:
    root = _projection_repo(tmp_path)
    assert _sync(root, "--feature-package", PACKAGE_ID).returncode == 0
    (root / "tasks" / "feat-x" / "sys-x-p13.md").unlink()
    proc = _sync(root, "--feature-package", PACKAGE_ID, "--check")
    assert proc.returncode == 2
    report = json.loads(proc.stdout)
    assert report["checked"] == 12
    assert "exact 13/P01..P13" in report["missing"][0]["reason"]


def test_incomplete_feature_write_fails_without_partial_updates(tmp_path: Path) -> None:
    root = _projection_repo(tmp_path)
    (root / "tasks" / "feat-x" / "sys-x-p13.md").unlink()
    target = root / "tasks" / "feat-x" / "sys-x-p01.md"
    before = target.read_bytes()
    proc = _sync(root, "--feature-package", PACKAGE_ID)
    assert proc.returncode == 2
    report = json.loads(proc.stdout)
    assert report["updated"] == []
    assert target.read_bytes() == before


def test_feature_package_scope_requires_p01_through_p13_exact_set(tmp_path: Path) -> None:
    root = _projection_repo(tmp_path)
    assert _sync(root, "--feature-package", PACKAGE_ID).returncode == 0
    target = root / "tasks" / "feat-x" / "sys-x-p13.md"
    target.write_text(target.read_text(encoding="utf-8").replace('phase_ref: "P13"', 'phase_ref: "P12"'),
                      encoding="utf-8")
    proc = _sync(root, "--feature-package", PACKAGE_ID, "--check")
    assert proc.returncode == 2
    assert "missing=['P13']" in json.loads(proc.stdout)["missing"][0]["reason"]


def test_rerun_outside_execution_contract_is_not_rewritten_or_accepted(tmp_path: Path) -> None:
    body = PROJECTION.replace(
        "## 実行契約",
        "## Notes\n\n- rerun: unrelated note\n\n## 実行契約",
    )
    root = _projection_repo(tmp_path, body=body)
    target = root / "tasks" / "feat-x" / "sys-x-p01.md"
    assert _sync(root, "--feature-package", PACKAGE_ID, "--check").returncode == 2
    assert _sync(root, "--feature-package", PACKAGE_ID).returncode == 0
    text = target.read_text(encoding="utf-8")
    assert "- rerun: unrelated note" in text
    execution_contract = text.split("## 実行契約", 1)[1]
    assert f"--feature-package {PACKAGE_ID}" in execution_contract
    assert _sync(root, "--feature-package", PACKAGE_ID, "--check").returncode == 0


# --- 書込先の containment (独立レビュー指摘の回帰固定) ----------------------
#
# tasks root は repo-local config 由来なので、config が repository 外を指した場合に
# 書込モードが repository 外の file を書き換えないことを固定する。path 検査は
# C09 (resolve-project-context.py) へ一元化しており、独自実装を持たない。


def _repo_with_tasks_root(tmp_path: Path, tasks_value: str) -> tuple[Path, Path]:
    root = (tmp_path / "repo").resolve()
    root.mkdir(parents=True)
    fx.make_repo(root)
    config_path = root / ".dev-graph" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["content_roots"]["tasks"] = tasks_value
    config_path.write_text(json.dumps(config), encoding="utf-8")
    victim = (tmp_path / "outside" / "feat-victim" / "sys-victim-p01.md")
    victim.parent.mkdir(parents=True)
    victim.write_text(PROJECTION, encoding="utf-8")
    return root, victim


def test_traversal_tasks_root_is_rejected_without_writing(tmp_path: Path) -> None:
    root, victim = _repo_with_tasks_root(tmp_path, "../outside")
    before = victim.read_bytes()
    proc = _sync(root)
    assert proc.returncode == 2
    assert ".. traversal" in proc.stderr
    assert victim.read_bytes() == before


def test_absolute_tasks_root_is_rejected_without_writing(tmp_path: Path) -> None:
    root, victim = _repo_with_tasks_root(tmp_path, str((tmp_path / "outside").resolve()))
    before = victim.read_bytes()
    proc = _sync(root)
    assert proc.returncode == 2
    assert "absolute path を拒否" in proc.stderr
    assert victim.read_bytes() == before


def test_symlink_escape_tasks_root_is_rejected_without_writing(tmp_path: Path) -> None:
    root, victim = _repo_with_tasks_root(tmp_path, "tasks")
    tasks = root / "tasks"
    if tasks.exists():
        for child in sorted(tasks.rglob("*"), reverse=True):
            child.unlink() if child.is_file() else child.rmdir()
        tasks.rmdir()
    tasks.symlink_to((tmp_path / "outside").resolve(), target_is_directory=True)
    before = victim.read_bytes()
    proc = _sync(root)
    assert proc.returncode == 2
    assert victim.read_bytes() == before


def test_lineage_gate_also_routes_paths_through_c09(tmp_path: Path) -> None:
    # validate-generation-lineage.py も同じ一元化を持つ (plan_roots.state が repo 外)
    root = (tmp_path / "repo").resolve()
    root.mkdir(parents=True)
    fx.make_repo(root)
    config_path = root / ".dev-graph" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["plan_roots"]["state"] = "../outside"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "validate-generation-lineage.py"), "--repo-root", str(root)],
        capture_output=True, text=True, check=False,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})
    assert proc.returncode == 2


def test_symlinked_subdirectory_under_tasks_root_is_rejected(tmp_path: Path) -> None:
    # tasks root 自体は正当でも、その配下が repo 外への symlink なら書込みは越境する
    root, victim = _repo_with_tasks_root(tmp_path, "tasks")
    (root / "tasks" / "evil").symlink_to(victim.parent.resolve(), target_is_directory=True)
    before = victim.read_bytes()
    proc = _sync(root)
    assert proc.returncode == 2
    assert victim.read_bytes() == before
    assert any("repository 外" in row["reason"] for row in json.loads(proc.stdout)["missing"])


def test_symlinked_projection_file_is_rejected(tmp_path: Path) -> None:
    # 書込先 file 自体が repo 外への symlink の場合も拒否する
    root, victim = _repo_with_tasks_root(tmp_path, "tasks")
    link = root / "tasks" / "feat-x" / "sys-linked-p02.md"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(victim.resolve())
    before = victim.read_bytes()
    proc = _sync(root)
    assert proc.returncode == 2
    assert victim.read_bytes() == before


def test_symlinked_marker_is_rejected(tmp_path: Path) -> None:
    # validate-generation-lineage.py の marker 書込先が repo 外 symlink の場合も拒否する
    import test_generation_lineage as gl

    root, _, _ = gl.build_repo(tmp_path)
    outside = tmp_path / "outside" / "victim.json"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text('{"keep": true}\n', encoding="utf-8")
    (root / gl.LEGACY_REL / "SUPERSEDED.json").symlink_to(outside.resolve())
    before = outside.read_bytes()
    proc = gl.run(root, "--write-markers")
    assert proc.returncode == 2
    assert outside.read_bytes() == before
