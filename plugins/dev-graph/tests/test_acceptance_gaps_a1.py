"""受入条件のうち、まだ実行で示していなかった挙動を script の実起動で確かめる (A1 担当分)。

- run-dev-graph-decompose OUT6/OUT7: system-dev-planner の promote と C02 register を、自動起動2回と手動経路で起動する。
- run-dev-graph-requirements IN1/OUT2: validate-readiness-binding.py が validate-system-plan・C02 保存 state・
  C11 を通した graph を同じ digest で照合することと、guard-requirements-handoff.py が incomplete な参照 node の
  混ざった closure で全件の missing_sections と remediation owner を返し handoff を0件にすることを見る。
- run-dev-graph-init OUT3: 同じ symlink harness を repo A/B から起動し、validate-harness-link.py が link の切断を
  起動前・write 前に検出して修復導線を返すことを見る。

Skill や slash command の起動そのものは Claude Code 本体の挙動なので、ここではそれらが呼ぶ script の連鎖だけを
起動する。fixture はすべて tmp_path に作り、bd/gh は PATH の spy に差し替える。
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
SDP = PLUGIN.parent / "system-dev-planner"
PHASES = [f"P{i:02d}" for i in range(1, 14)]
FEATURE = "FEATURE-1"
ARCHITECTURE = "architecture-system"
PUBLISHED = ".dev-graph/plans/feature-package-feat"
GRAPH = ".dev-graph/state/graph.json"
RECEIPTS = ".dev-graph/state/registration-receipts"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# system-dev-planner の staging fixture と、dev-graph の canonical feature node をそのまま使う。
RT = _load(SDP / "tests" / "test_runtime.py", "dev_graph_a1_sdp_runtime")
TRP = _load(PLUGIN / "tests" / "test_register_package.py", "dev_graph_a1_register_fixtures")
RP = _load(SCRIPTS / "register-package.py", "dev_graph_a1_register_package")


def write_artifact(root: Path, node: dict) -> None:
    """C11 の artifact 検査が読む形 (`key: json` の frontmatter と本文)。"""
    path = root / node["file_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", *(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in node.items()),
             "---", "", "# Overview", "", "Substantive content.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def architecture_node() -> dict:
    node = TRP.feature_node()
    node.update(graph_node_id=ARCHITECTURE, artifact_kind="architecture", artifact_subtypes=["backend"],
                title="System architecture", file_path="architecture/system.md", template_id="architecture",
                purpose=None, goal=None, scope_in=[], scope_out=[], acceptance=[], architecture_refs=[])
    return node


def feature_node(node_id: str = FEATURE) -> dict:
    node = TRP.feature_node()
    node.update(graph_node_id=node_id, file_path=f"features/{node_id}.md", architecture_refs=[ARCHITECTURE])
    return node


def git_init(root: Path) -> None:
    """C24 (resolve-repo-context.py) は git の toplevel で root を固定するので、C24 を通す script の fixture は git repo にする。"""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "commit", "-q", "--allow-empty", "-m", "init"], check=True)


def tree_bytes(root: Path) -> dict[str, bytes | str]:
    """root 以下の全 entry の中身 (symlink は link 先の文字列)。書込み 0 件の比較に使う。"""
    result: dict[str, bytes | str] = {}
    for path in sorted(root.rglob("*")):
        key = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[key] = "->" + os.readlink(path)
        elif path.is_file():
            result[key] = path.read_bytes()
        else:
            result[key] = "<dir>"
    return result


class PlanRepo:
    """1 feature を持つ一時 repo。promote と C02 register を subprocess で起動し、bd/gh の呼出しを記録する。"""

    def __init__(self, root: Path, *, git: bool = False) -> None:
        root.mkdir(parents=True)
        self.root = root.resolve()
        if git:
            git_init(self.root)
        self.rid = RT.make_repo(self.root)
        RT.dump(self.root / ".dev-graph/state/readiness.json", RT.valid_readiness(self.root, self.rid))
        (self.root / RECEIPTS).mkdir(parents=True)
        self.calls = self.root.parent / "tracker-calls.log"
        bin_dir = self.root.parent / "spy-bin"
        bin_dir.mkdir()
        for name in ("bd", "gh"):
            spy = bin_dir / name
            spy.write_text(f'#!/bin/sh\necho "{name} $*" >> "{self.calls}"\n', encoding="utf-8")
            spy.chmod(0o755)
        self.env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.root),
                    "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
        architecture, feature = architecture_node(), feature_node()
        for node in (architecture, feature):
            write_artifact(self.root, node)
        RT.dump(self.root / GRAPH, {"schema_version": "1.0.0", "graph_revision": 1, "nodes": [architecture, feature]})

    def run(self, script: Path, *argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(script), *argv], text=True, capture_output=True,
                              env=self.env, cwd=str(self.root), check=False)

    def promote(self, run_id: str, *, replace: dict[str, str] | None = None) -> tuple[subprocess.CompletedProcess[str], str]:
        """run_id ごとに staging・lock・findings・validation を作り、promote-system-plan.py を起動する。"""
        rel = f".dev-graph/staging/{run_id}"
        staging, digest = RT.make_fixture(self.root, self.rid, rel, include_handoff=replace is None)
        if replace:
            for path in sorted(p for p in staging.rglob("*") if p.is_file() and p.name != "staging-manifest.json"):
                text = path.read_text(encoding="utf-8")
                for old, new in replace.items():
                    text = text.replace(old, new)
                path.write_text(text, encoding="utf-8")
            RT.refresh_manifest(staging)
            sources = RT.HANDOFF._validate_sources(repo_root=self.root, staging=staging.resolve(),
                                                   repository_id=self.rid, validator=RT.VALIDATOR)
            package, inventory, graph, contents, manifest, source_manifest = sources
            handoff = RT.HANDOFF._build_handoff(package, inventory, graph, contents, source_manifest)
            RT.HANDOFF._schema_check(handoff, RT.VALIDATOR)
            digest = RT.HANDOFF._commit(staging, manifest, handoff, contents)["canonical_digest"]
        session = f"session-{run_id}"
        lock = self.root / RT.LOCK.LOCK_ROOT_REL / RT.LOCK.LOCK_NAME
        RT.dump(lock, {**json.loads(lock.read_text(encoding="utf-8")), "run_id": run_id, "session_owner": session})
        findings = RT.valid_findings(staging, digest)
        findings["plan_dir"] = rel
        findings["gate_results"][0]["command"][-1] = rel
        RT.dump(self.root / f".dev-graph/state/findings-{run_id}.json", findings)
        RT.dump(self.root / f".dev-graph/state/validation-{run_id}.json", {"status": "pass", "validated_digest": digest})
        cp = self.run(SDP / "scripts" / "promote-system-plan.py", "--repo-root", str(self.root),
                      "--feature-id", FEATURE, "--feature-context", "features/feature.json",
                      "--run-id", run_id, "--session-owner", session, "--staging", rel,
                      "--findings", f".dev-graph/state/findings-{run_id}.json",
                      "--readiness", ".dev-graph/state/readiness.json",
                      "--validation", f".dev-graph/state/validation-{run_id}.json")
        return cp, digest

    def register(self, published: str = PUBLISHED, receipt: str = "feat.json") -> subprocess.CompletedProcess[str]:
        return self.run(SCRIPTS / "register-package.py", "register", "--repo-root", str(self.root),
                        "--package", f"{published}/feature-package.json",
                        "--graph", f"{published}/dev-graph-registration.json",
                        "--output", GRAPH, "--receipt", f"{RECEIPTS}/{receipt}",
                        "--system-planner-root", str(SDP))

    def c11(self) -> tuple[int, dict]:
        cp = self.run(SCRIPTS / "validate-graph-schema.py", "--graph", GRAPH, "--repo-root", str(self.root))
        return cp.returncode, json.loads(cp.stdout)

    def graph(self) -> dict:
        return json.loads((self.root / GRAPH).read_text(encoding="utf-8"))

    def children(self) -> list[dict]:
        return [node for node in self.graph()["nodes"] if node.get("parent_feature") == FEATURE]

    def materialize_task_artifacts(self) -> None:
        """task artifact の書出しは C02 register の責務外なので、C11 の artifact 検査用に node から作る。
        task node は macro 欄 (purpose..architecture_refs) を持たないので、frontmatter では空値で埋める。"""
        macro = {"purpose": None, "goal": None, "scope_in": [], "scope_out": [], "acceptance": [], "architecture_refs": []}
        for node in self.children():
            write_artifact(self.root, {**macro, **node})

    def tracker_calls(self) -> str:
        return self.calls.read_text(encoding="utf-8") if self.calls.exists() else ""


@pytest.fixture
def plan(tmp_path: Path) -> PlanRepo:
    return PlanRepo(tmp_path / "repo")


@pytest.fixture
def git_plan(tmp_path: Path) -> PlanRepo:
    return PlanRepo(tmp_path / "repo", git=True)


def register_first(plan: PlanRepo) -> tuple[str, dict]:
    cp, digest = plan.promote("run-1")
    assert cp.returncode == 0, cp.stderr
    cp = plan.register()
    assert cp.returncode == 0, cp.stderr
    return digest, json.loads(cp.stdout)


def refused(cp: subprocess.CompletedProcess[str]) -> str:
    """C02 register の拒否 (exit 2・適用 0 件) を確かめ、理由の文を返す。"""
    report = json.loads(cp.stdout)
    assert (cp.returncode, report["valid"], report["applied_count"]) == (2, False, 0), cp.stdout
    return report["error"]


def assert_one_exact13_set(plan: PlanRepo) -> None:
    children = plan.children()
    assert len(children) == 13
    assert sorted(node["phase_ref"] for node in children) == PHASES
    assert {node["feature_package_id"] for node in children} == {"feature-package/feat"}
    code, report = plan.c11()
    assert not [item for item in report["violations"] if item["code"] == "feature_package_not_exact_13"], report


# --- run-dev-graph-decompose OUT6 ------------------------------------------------------------------


def test_decompose_out6_second_auto_dispatch_keeps_one_exact13_set(plan: PlanRepo) -> None:
    """同じ ready feature への2回目の自動起動は同じ published に収束し、C02 register は graph も receipt も変えない。"""
    digest, first = register_first(plan)
    assert first["idempotent"] is False and first["node_ids"] == [n["graph_node_id"] for n in plan.children()]
    graph_before = (plan.root / GRAPH).read_bytes()
    receipt_before = (plan.root / RECEIPTS / "feat.json").read_bytes()

    cp, again = plan.promote("run-2")
    assert cp.returncode == 0, cp.stderr
    assert again == digest
    cp = plan.register()
    assert cp.returncode == 0, cp.stderr
    report = json.loads(cp.stdout)
    assert report["idempotent"] is True and report["source_digest"] == first["source_digest"]
    assert (plan.root / GRAPH).read_bytes() == graph_before
    assert (plan.root / RECEIPTS / "feat.json").read_bytes() == receipt_before
    assert_one_exact13_set(plan)
    assert {node["parent_feature"] for node in plan.children()} == {FEATURE}
    assert plan.tracker_calls() == ""


def test_decompose_out6_second_dispatch_under_a_new_package_identity_is_refused(plan: PlanRepo) -> None:
    """2回目の起動が別の package id と task id を作っても、同じ feature に2組目の 13 task は登録されない。"""
    register_first(plan)
    graph_before = (plan.root / GRAPH).read_bytes()
    cp, _ = plan.promote("run-3", replace={"feature-package/feat": "feature-package/feat-rerun", "SYS-P": "SYS-RERUN-P"})
    assert cp.returncode == 0, cp.stderr
    rerun = ".dev-graph/plans/feature-package-feat-rerun"
    assert (plan.root / rerun / "dev-graph-registration.json").is_file()

    assert f"parent feature {FEATURE} already has tasks outside this package" in refused(plan.register(rerun, "feat-rerun.json"))
    assert (plan.root / GRAPH).read_bytes() == graph_before
    assert not (plan.root / RECEIPTS / "feat-rerun.json").exists()
    assert_one_exact13_set(plan)
    assert plan.tracker_calls() == ""


def test_decompose_out6_second_dispatch_with_changed_content_stops_at_the_promoter(plan: PlanRepo) -> None:
    """同じ package id で中身が違う2回目は、promote が published を上書きせずに止める (digest が別になる)。"""
    digest, _ = register_first(plan)
    published_before = tree_bytes(plan.root / PUBLISHED)
    graph_before = (plan.root / GRAPH).read_bytes()

    cp, changed = plan.promote("run-2", replace={"- Rollback: revert": "- Rollback: undo"})
    assert changed != digest
    assert cp.returncode == 2, cp.stdout
    assert "published generation bytes do not match promotion intent digest" in cp.stderr
    assert tree_bytes(plan.root / PUBLISHED) == published_before
    assert (plan.root / GRAPH).read_bytes() == graph_before
    assert_one_exact13_set(plan)


# --- run-dev-graph-decompose OUT7 ------------------------------------------------------------------


def test_decompose_out7_manual_route_converges_on_the_auto_registration(plan: PlanRepo) -> None:
    """`/system-dev-plan plan` は同じ Skill へ引数をそのまま渡すので、別 session の手動 run も同じ published と receipt に収束する。"""
    command = (SDP / "commands" / "system-dev-plan.md").read_text(encoding="utf-8")
    assert "entrypoint: run-system-dev-plan" in command
    assert "`run-system-dev-plan` Skill へそのまま渡す" in command
    digest, auto = register_first(plan)
    graph_before = (plan.root / GRAPH).read_bytes()

    cp, manual = plan.promote("manual-1")
    assert cp.returncode == 0, cp.stderr
    assert manual == digest
    cp = plan.register()
    assert cp.returncode == 0, cp.stderr
    report = json.loads(cp.stdout)
    assert report["idempotent"] is True
    assert (report["parent_feature"], report["node_ids"]) == (auto["parent_feature"], auto["node_ids"])
    assert (plan.root / GRAPH).read_bytes() == graph_before
    assert_one_exact13_set(plan)


def test_decompose_out7_manual_route_cannot_add_a_second_registration(plan: PlanRepo) -> None:
    """手動経路が別 package を作った場合も、経路ごとに別 receipt を渡した場合も、二重登録にならない。"""
    register_first(plan)
    graph_before = (plan.root / GRAPH).read_bytes()

    # 同じ package を手動経路専用の receipt で登録しようとすると、既存 node に receipt が無いので止まる。
    assert "registered nodes exist without immutable receipt" in refused(plan.register(receipt="feat-manual.json"))
    assert not (plan.root / RECEIPTS / "feat-manual.json").exists()

    cp, _ = plan.promote("manual-1", replace={"feature-package/feat": "feature-package/feat-manual", "SYS-P": "SYS-MANUAL-P"})
    assert cp.returncode == 0, cp.stderr
    manual = plan.register(".dev-graph/plans/feature-package-feat-manual", "feat-manual.json")
    assert "already has tasks outside this package" in refused(manual)
    assert not (plan.root / RECEIPTS / "feat-manual.json").exists()
    assert (plan.root / GRAPH).read_bytes() == graph_before
    assert_one_exact13_set(plan)
    assert plan.tracker_calls() == ""


# --- run-dev-graph-requirements IN1 ----------------------------------------------------------------


def binding(plan: PlanRepo, published: str = PUBLISHED, receipt: str = f"{RECEIPTS}/feat.json") -> tuple[int, dict]:
    """R2b の照合は validate-readiness-binding.py が行う。test は起動して report と exit を受け取るだけ。"""
    cp = plan.run(SCRIPTS / "validate-readiness-binding.py", "--repo-root", str(plan.root), "--package-dir", published,
                  "--receipt", receipt, "--system-planner-root", str(SDP))
    assert cp.returncode in (0, 1), cp.stderr
    return cp.returncode, json.loads(cp.stdout)


def violation_codes(report: dict) -> set[tuple[str, str | None]]:
    return {(item["code"], item.get("node")) for item in report["violations"]}


def node_id_of(plan: PlanRepo, phase: str) -> str:
    return next(node["graph_node_id"] for node in plan.children() if node["phase_ref"] == phase)


def test_requirements_in1_three_gates_bind_to_one_digest(git_plan: PlanRepo) -> None:
    plan = git_plan
    digest, registered = register_first(plan)
    plan.materialize_task_artifacts()
    before = tree_bytes(plan.root)

    code, report = binding(plan)
    assert (code, report["status"], report["violations"]) == (0, "pass", []), report["violations"]
    assert report["validated_digest"] == digest == registered["source_digest"]
    assert (report["feature_package_id"], report["parent_feature"]) == ("feature-package/feat", FEATURE)
    # C11 は同じ bytes を PASS し、その bytes が C02 の封じた登録時点の graph である。
    assert (report["c11"]["status"], report["graph"]["relation"]) == ("pass", "registered_snapshot")
    assert report["graph"]["digest"] == RP._canonical_digest(plan.graph()) == registered["graph_digest_after"]
    assert report["readiness_digest"]["c11"] == report["readiness_digest"]["c02"]
    # member は P01..P13 の 13 件で、全件が active/confirmed/pass/complete、digest は validated_digest に pin される。
    hex_digest = digest.removeprefix("sha256:")
    assert [member["phase_ref"] for member in report["members"]] == PHASES
    assert {(m["status"], m["confirmation_status"], m["evaluation_status"], m["implementation_readiness"]["status"],
             tuple(m["implementation_readiness"]["missing_sections"]), m["source_digest"], m["evaluated_digest"])
            for m in report["members"]} == {("active", "confirmed", "pass", "complete", (), hex_digest, hex_digest)}
    assert (report["write_count"], tree_bytes(plan.root)) == (0, before)

    # validate-system-plan は published の exact-13・共通 parent/package・機能内前方 dependency を見て PASS する。
    cp = plan.run(SDP / "scripts" / "validate-system-plan.py", "--repo-root", str(plan.root), "--staging", PUBLISHED)
    report = json.loads(cp.stdout)
    assert (report["feature_package_id"], report["parent_feature"], report["phase_refs"]) == \
        ("feature-package/feat", FEATURE, PHASES)


def test_requirements_in1_stale_digest_or_drifted_c02_state_breaks_the_binding(git_plan: PlanRepo) -> None:
    plan = git_plan
    register_first(plan)
    plan.materialize_task_artifacts()
    graph_path = plan.root / GRAPH
    clean = graph_path.read_bytes()
    p05, p07 = node_id_of(plan, "P05"), node_id_of(plan, "P07")

    # C02 保存 state の source_digest だけが revision を上げずにずれた: C11 は通るが、binding が止める。
    graph = plan.graph()
    next(node for node in graph["nodes"] if node["graph_node_id"] == p05)["source_lineage"]["source_digest"] = "b" * 64
    RT.dump(graph_path, graph)
    assert plan.c11()[0] == 0
    code, report = binding(plan)
    assert code == 1 and report["status"] == "fail"
    assert violation_codes(report) == {("stale_source_digest", p05), ("graph_snapshot_mismatch", None),
                                       ("readiness_digest_mismatch", None)}
    assert report["readiness_digest"]["c11"] != report["readiness_digest"]["c02"]
    stale_bytes = graph_path.read_bytes()
    assert "duplicate node ids exist with different content" in refused(plan.register())
    assert graph_path.read_bytes() == stale_bytes

    # 同じずれを後の writer revision に載せても、member の readiness view が C02 の保存値と違うので止まる。
    graph["graph_revision"] += 1
    RT.dump(graph_path, graph)
    code, report = binding(plan)
    assert (code, report["graph"]["relation"]) == (1, "later_revision")
    assert violation_codes(report) == {("stale_source_digest", p05), ("readiness_digest_mismatch", None)}

    # readiness だけが incomplete に戻った: C11 が active_not_ready を返し、binding は P07 の不足 section を名指しする。
    graph = json.loads(clean)
    regressed = next(node for node in graph["nodes"] if node["graph_node_id"] == p07)
    regressed["implementation_readiness"] = {"status": "incomplete", "missing_sections": ["Verification and evidence"],
                                             "checked_at": "2026-07-13T00:00:00Z"}
    RT.dump(graph_path, graph)
    code, report = binding(plan)
    assert code == 1
    assert violation_codes(report) == {("c11_failed", None), ("node_not_ready", p07), ("graph_snapshot_mismatch", None),
                                       ("readiness_digest_mismatch", None)}
    assert {"node": p07, "code": "active_not_ready", "detail": "active requires confirmed/pass/complete"} in report["c11"]["violations"]
    assert next(m for m in report["members"] if m["graph_node_id"] == p07)["implementation_readiness"] == {
        "status": "incomplete", "missing_sections": ["Verification and evidence"]}

    # C02 receipt が別の digest を指す: receipt と validated_digest の不一致として止まる。
    graph_path.write_bytes(clean)
    stale_receipt = json.loads((plan.root / RECEIPTS / "feat.json").read_text(encoding="utf-8"))
    stale_receipt["source_digest"] = "sha256:" + "c" * 64
    RT.dump(plan.root / RECEIPTS / "feat-stale.json", stale_receipt)
    code, report = binding(plan, receipt=f"{RECEIPTS}/feat-stale.json")
    assert (code, violation_codes(report)) == (1, {("receipt_digest_mismatch", None)})

    # published の task spec が評価後に変わった: validate-system-plan が fail し、binding も fail する。
    spec = plan.root / PUBLISHED / RT.VALIDATOR.TASK_PATHS[0]
    spec.write_text(spec.read_text(encoding="utf-8") + "\nedited after evaluation\n", encoding="utf-8")
    cp = plan.run(SDP / "scripts" / "validate-system-plan.py", "--repo-root", str(plan.root), "--staging", PUBLISHED)
    assert cp.returncode == 2 and json.loads(cp.stdout)["status"] == "fail"
    code, report = binding(plan)
    assert code == 1 and ("system_plan_failed", None) in violation_codes(report)
    assert report["system_plan"]["exit"] == 2


# --- run-dev-graph-requirements OUT2 ---------------------------------------------------------------


def incomplete(node: dict, missing: list[str]) -> dict:
    node.update(status="draft", confirmation_status="draft", evaluation_status="pending",
                confirmation_evidence={"evaluator": None, "evidence_ref": None, "evaluated_digest": None},
                implementation_readiness={"status": "incomplete", "missing_sections": missing, "checked_at": None})
    return node


def handoff_guard(root: Path, *nodes: str, env: dict | None = None, expect: str | None = None) -> tuple[int, dict]:
    """R3 の handoff 可否は guard-requirements-handoff.py が決める。expect は binding の graph.digest。"""
    argv = [arg for node in nodes for arg in ("--node", node)]
    argv += ["--expect-graph-digest", expect] if expect is not None else []
    cp = subprocess.run([sys.executable, str(SCRIPTS / "guard-requirements-handoff.py"), "--repo-root", str(root), *argv],
                        text=True, capture_output=True, check=False, cwd=str(root),
                        env=env or {**os.environ, "CLAUDE_PROJECT_DIR": str(root)})
    # exit 2 で report を返すのは snapshot の不一致だけ (usage・C24・IO の exit 2 は stdout が空)。
    assert cp.returncode in (0, 1) or (cp.returncode == 2 and expect is not None and cp.stdout), cp.stderr
    return cp.returncode, json.loads(cp.stdout)


def test_requirements_out2_mixed_incomplete_references_surface_every_missing_section_and_are_withheld(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    git_init(root)
    ready = feature_node("feature-ready")
    gap_a = incomplete(feature_node("feature-gap-a"), ["acceptance", "architecture_refs", "scope_out"])
    gap_b = incomplete(architecture_node(), ["## Security", "## Deploy unit"])
    gap_b.update(graph_node_id="architecture-gap-b", file_path="architecture/gap-b.md")
    ready["related_nodes"] = [gap_a["graph_node_id"], gap_b["graph_node_id"]]
    nodes = [architecture_node(), ready, gap_a, gap_b]
    for node in nodes:
        write_artifact(root, node)
    graph = root / GRAPH
    RT.dump(graph, {"schema_version": "1.0.0", "graph_revision": 1, "nodes": nodes})

    cp = subprocess.run([sys.executable, str(SCRIPTS / "validate-graph-schema.py"), "--graph", str(graph),
                         "--repo-root", str(root)], text=True, capture_output=True, check=False)
    report = json.loads(cp.stdout)
    # graph としては valid でも、node の着手準備は別に surface される。missing_sections は1件も落ちない。
    assert (cp.returncode, report["valid"]) == (0, True), report["violations"]
    assert report["node_readiness"]["complete"] == 2 and report["node_readiness"]["incomplete"] == 2

    # schedule の ready_set は依存の準備だけを見るので feature-ready を ready に入れる。handoff はここで決めない。
    cp = subprocess.run([sys.executable, str(SCRIPTS / "schedule-graph.py"), "--graph", str(graph)],
                        text=True, capture_output=True, check=False)
    assert cp.returncode == 0, cp.stderr
    assert json.loads(cp.stdout)["ready_set"]["features"] == ["feature-ready"]

    before = tree_bytes(root)
    code, report = handoff_guard(root, "feature-ready")
    assert (code, report["status"], report["handoff_count"], report["handoff"]) == (1, "withheld", 0, [])
    assert report["missing_sections"] == [
        {"graph_node_id": "architecture-gap-b", "missing_sections": ["## Security", "## Deploy unit"]},
        {"graph_node_id": "feature-gap-a", "missing_sections": ["acceptance", "architecture_refs", "scope_out"]},
    ]
    blocked = {item["graph_node_id"]: item for item in report["blocked"]}
    for node_id in ("architecture-gap-b", "feature-gap-a"):
        assert blocked[node_id]["reasons"] == ["readiness_incomplete", "evaluation_pending", "confirmation_draft"]
        assert blocked[node_id]["remediation"] == {"owner": "run-dev-graph-node", "upstream": None, "origin_kind": "manual",
                                                   "owners": ["team"], "referenced_by": ["feature-ready"]}
    assert {row["graph_node_id"]: row["verdict"] for row in report["closure"]} == {
        "feature-ready": "ready", ARCHITECTURE: "ready", "feature-gap-a": "blocked", "architecture-gap-b": "blocked"}

    # 対象に ready な node を足しても、一部だけを handoff しない。
    code, report = handoff_guard(root, "feature-ready", ARCHITECTURE)
    assert (code, report["handoff_count"], len(report["missing_sections"])) == (1, 0, 2)
    # 参照 closure が全件 ready なら handoff する (guard は常に保留するわけではない)。
    code, report = handoff_guard(root, ARCHITECTURE)
    assert (code, report["status"], report["handoff"], report["blocked"]) == (0, "handoff", [ARCHITECTURE], [])
    assert tree_bytes(root) == before


def test_requirements_out2_incomplete_node_in_a_package_handoff_is_refused_without_writes(plan: PlanRepo) -> None:
    cp, _ = plan.promote("run-1")
    assert cp.returncode == 0, cp.stderr
    registration_path = plan.root / PUBLISHED / "dev-graph-registration.json"
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    registration["nodes"][6]["implementation_readiness"] = {
        "status": "incomplete", "missing_sections": ["Verification and evidence"], "checked_at": "2026-07-13T00:00:00Z"}
    RT.dump(registration_path, registration)
    graph_before = (plan.root / GRAPH).read_bytes()

    # evaluation_status=pass の node は schema の条件で readiness=complete に固定されているので、そこで止まる。
    assert "nodes[6].implementation_readiness.status: expected const 'complete'" in refused(plan.register())
    assert (plan.root / GRAPH).read_bytes() == graph_before
    assert not (plan.root / RECEIPTS / "feat.json").exists()
    assert plan.tracker_calls() == ""


def test_requirements_out2_one_regressed_package_member_withholds_the_whole_feature_handoff(git_plan: PlanRepo) -> None:
    plan = git_plan
    register_first(plan)
    plan.materialize_task_artifacts()
    p07 = node_id_of(plan, "P07")
    code, report = handoff_guard(plan.root, FEATURE, env=plan.env)
    assert (code, report["handoff"]) == (0, [FEATURE])
    assert len([row for row in report["closure"] if row["artifact_kind"] == "task"]) == 13

    graph = plan.graph()
    incomplete(next(node for node in graph["nodes"] if node["graph_node_id"] == p07), ["Verification and evidence"])
    RT.dump(plan.root / GRAPH, graph)
    before = tree_bytes(plan.root)
    code, report = handoff_guard(plan.root, FEATURE, env=plan.env)
    assert (code, report["handoff_count"]) == (1, 0)
    assert report["missing_sections"] == [{"graph_node_id": p07, "missing_sections": ["Verification and evidence"]}]
    (item,) = report["blocked"]
    assert item["remediation"]["owner"] == "system-dev-planner:run-system-dev-plan"
    assert item["remediation"]["referenced_by"] == sorted([FEATURE, node_id_of(plan, "P08")])
    assert tree_bytes(plan.root) == before
    assert plan.tracker_calls() == ""


def test_requirements_handoff_guard_is_pinned_to_the_binding_graph_snapshot(git_plan: PlanRepo) -> None:
    """R3 は binding の graph.digest を guard へ渡す。2つの script の間に graph が変わると handoff は0件で止まる。"""
    plan = git_plan
    register_first(plan)
    plan.materialize_task_artifacts()
    code, bound = binding(plan)
    assert (code, bound["status"]) == (0, "pass"), bound["violations"]
    snapshot = bound["graph"]["digest"]

    # guard は binding と同じ定義 (C02 の canonical digest) で、自分が読んだ graph の snapshot を返す。
    code, report = handoff_guard(plan.root, FEATURE, env=plan.env, expect=snapshot)
    assert (code, report["status"], report["handoff"]) == (0, "handoff", [FEATURE])
    assert report["graph"]["digest"] == snapshot == RP._canonical_digest(plan.graph())
    assert report["graph"]["graph_revision"] == bound["graph"]["graph_revision"]
    assert (report["graph"]["expected_digest"], report["graph"]["digest_match"]) == (snapshot, True)

    # binding の後に graph が変わった。closure は全件 ready のままなので、snapshot を照合しなければ handoff してしまう。
    graph = plan.graph()
    graph["graph_revision"] += 1
    RT.dump(plan.root / GRAPH, graph)
    code, report = handoff_guard(plan.root, FEATURE, env=plan.env)
    assert (code, report["status"], report["blocked"]) == (0, "handoff", [])
    assert report["graph"]["digest"] != snapshot and report["graph"]["digest_match"] is None
    before = tree_bytes(plan.root)
    code, report = handoff_guard(plan.root, FEATURE, env=plan.env, expect=snapshot)
    assert (code, report["status"], report["handoff_count"], report["handoff"]) == (2, "snapshot_mismatch", 0, [])
    assert report["graph"]["digest"] == RP._canonical_digest(graph)
    assert report["graph"]["graph_revision"] == bound["graph"]["graph_revision"] + 1
    assert (report["graph"]["expected_digest"], report["graph"]["digest_match"]) == (snapshot, False)
    assert tree_bytes(plan.root) == before

    # binding を取り直して、その digest を渡せば同じ graph で handoff できる (guard は常に止めるわけではない)。
    code, rebound = binding(plan)
    assert code == 0 and rebound["graph"]["digest"] == report["graph"]["digest"]
    code, report = handoff_guard(plan.root, FEATURE, env=plan.env, expect=rebound["graph"]["digest"])
    assert (code, report["handoff"]) == (0, [FEATURE])
    assert plan.tracker_calls() == ""


# --- run-dev-graph-init OUT3 -----------------------------------------------------------------------


class Harness:
    """repo A/B から同じ symlink harness 経由で init と hook fallback を起動する。

    source を渡すと harness はその複製を指す (harness 側の bytes が変わらないかを見るため)。bytecode cache は
    interpreter が書くものなので PYTHONDONTWRITEBYTECODE で止め、dev-graph 自身の write だけを比べる。"""

    def __init__(self, base: Path, source: Path = PLUGIN) -> None:
        self.base = base.resolve()
        self.source = source.resolve()
        self.link = self.base / "harness"
        self.link.symlink_to(self.source)
        self.repos = {name: self._repo(name) for name in ("A", "B")}
        self.user = self.base / "user-settings.json"
        self.managed = self.base / "managed-settings.json"

    def _repo(self, name: str) -> Path:
        root = self.base / name
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        return root

    def run(self, name: str, script: str, *argv: str, project_dir: str | None = None,
            via: Path | None = None) -> tuple[int, dict | str]:
        root = self.repos[name]
        env = {**os.environ, "CLAUDE_PROJECT_DIR": project_dir or str(root), "PYTHONDONTWRITEBYTECODE": "1"}
        cp = subprocess.run([sys.executable, str((via or self.link) / "scripts" / script), "--repo-root", str(root), *argv],
                            text=True, capture_output=True, env=env, cwd=str(root), check=False)
        try:
            return cp.returncode, json.loads(cp.stdout)
        except json.JSONDecodeError:
            return cp.returncode, cp.stdout + cp.stderr

    def hook(self, name: str, *argv: str, via: Path | None = None) -> tuple[int, dict | str]:
        return self.run(name, "build-project-hook-fallback.py", "--user-settings", str(self.user),
                        "--managed-settings", str(self.managed), *argv, via=via)

    def preflight(self, name: str, *argv: str) -> tuple[int, dict | str]:
        """preflight は plugin 実体から起動する (link が切れていても届く)。"""
        return self.run(name, "validate-harness-link.py", *argv, via=self.source)

    def link_repo(self, name: str) -> Path:
        link = self.repos[name] / ".claude" / "dev-graph-plugin"
        link.parent.mkdir(exist_ok=True)
        link.symlink_to(self.link)
        return link

    def sealed(self, name: str):
        """相手 repo を読めなくする。cross-read が1件でもあればその起動は失敗する。"""
        return _Sealed(self.repos[name])


class _Sealed:
    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> None:
        self.path.chmod(0)

    def __exit__(self, *_: object) -> None:
        self.path.chmod(0o755)


def frozen_plugin(tmp_path: Path) -> Path:
    copy = tmp_path / "plugin-copy" / "dev-graph"
    shutil.copytree(PLUGIN, copy, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    return copy


def repair(report: dict, option: str, root: Path) -> None:
    """preflight が返した修復導線の argv をそのまま実行する (最後の step は preflight の再実行で、pass に戻る)。"""
    steps = next(item["steps"] for item in report["remediation"] if item["option"] == option)
    for argv in steps[:-1]:
        subprocess.run(argv, check=True, capture_output=True)
    assert steps[-1][:1] == ["python3"] and steps[-1][1].endswith("/validate-harness-link.py")
    rerun = subprocess.run([sys.executable, *steps[-1][1:]], text=True, capture_output=True, check=False,
                           env={**os.environ, "CLAUDE_PROJECT_DIR": str(root), "PYTHONDONTWRITEBYTECODE": "1"})
    assert rerun.returncode == 0 and json.loads(rerun.stdout)["status"] == "pass", rerun.stdout + rerun.stderr


def stored_strings(value: object) -> list[str]:
    if isinstance(value, dict):
        return [text for item in value.values() for text in stored_strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in stored_strings(item)]
    return [value] if isinstance(value, str) else []


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions enforced for a non-root user")
def test_init_out3_shared_symlink_harness_keeps_repo_a_and_b_isolated(tmp_path: Path) -> None:
    harness = Harness(tmp_path, frozen_plugin(tmp_path))
    plugin_before = tree_bytes(harness.source)
    for name, other in (("A", "B"), ("B", "A")):
        before = tree_bytes(harness.repos[other])
        with harness.sealed(other):
            code, report = harness.preflight(name)
            assert (code, report["status"], report["link_state"], report["write_count"]) == (0, "pass", "absent", 0), report
            code, report = harness.run(name, "build-init-scaffold.py")
            assert (code, report["status"]) == (0, "applied"), report
            harness.link_repo(name)
            code, report = harness.preflight(name, "--hook-source", "project-fallback")
            assert (code, report["status"], report["link_state"], report["in_use"]) == (0, "pass", "ok", True), report
            code, hooked = harness.hook(name, "--mode", "apply")
            assert (code, hooked["status"]) == (0, "applied"), hooked
        assert tree_bytes(harness.repos[other]) == before
    # A と B のどちらから起動しても、共有 harness の中身は1 byte も変わらない (repo の path も書かれない)。
    assert tree_bytes(harness.source) == plugin_before

    absolute = (str(tmp_path), str(harness.base), str(PLUGIN), str(harness.source), os.path.expanduser("~"),
                "/private/", "/var/", "/Users/", "/home/")
    for name, root in harness.repos.items():
        config = json.loads((root / ".dev-graph" / "config.json").read_text(encoding="utf-8"))
        assert config["repository_id"].startswith("local:sha256:")
        # repo に保存された全 file (git の内部と、利用者が張った link を除く)。JSON は値の文字列、ほかは本文を見る。
        stored = [path for path in sorted(root.rglob("*"))
                  if path.is_file() and not path.is_symlink() and ".git" not in path.relative_to(root).parts]
        kinds = {path.relative_to(root).parts[0] for path in stored}
        assert {".dev-graph", ".claude"} <= kinds, kinds
        leaked = []
        for path in stored:
            text = path.read_bytes().decode("utf-8", "replace")
            strings = stored_strings(json.loads(text)) if path.suffix == ".json" else [text]
            leaked += [(path.relative_to(root).as_posix(), item[:80]) for item in strings
                       if (path.suffix == ".json" and item.startswith("/")) or any(marker in item for marker in absolute)]
        assert leaked == [], (name, leaked)
        settings = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        commands = [hook["command"] for groups in settings["hooks"].values() for group in groups for hook in group["hooks"]]
        assert commands and all('"${CLAUDE_PROJECT_DIR}/.claude/dev-graph-plugin/hooks/' in command for command in commands)
        # 2回目は noop で、相手 repo の state は読まずに済む。
        with harness.sealed("B" if name == "A" else "A"):
            code, again = harness.run(name, "build-init-scaffold.py")
            assert harness.preflight(name)[1]["status"] == "pass"
        assert (code, again["status"], again["write_count"]) == (0, "noop", 0), again
    assert tree_bytes(harness.source) == plugin_before


def test_init_out3_root_mismatch_and_broken_content_links_fail_closed(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    a, b = harness.repos["A"], harness.repos["B"]
    assert harness.run("A", "build-init-scaffold.py")[0] == 0
    assert harness.run("B", "build-init-scaffold.py")[0] == 0
    snapshot = {name: tree_bytes(root) for name, root in harness.repos.items()}

    def rejected(expected: str, **kwargs: str) -> None:
        code, report = harness.run("A", "build-init-scaffold.py", **kwargs)
        assert (code, report["status"], report["code"], report["write_count"]) == (1, "rejected", "c24_context_failed", 0)
        assert expected in report["error"], report
        code, context = harness.run("A", "resolve-repo-context.py", "--mode", "write", **kwargs)
        assert code == 1 and expected in str(context)

    # session の project root と --repo-root が食い違う。
    rejected("--repo-root and CLAUDE_PROJECT_DIR disagree", project_dir=str(b))
    assert {name: tree_bytes(root) for name, root in harness.repos.items()} == snapshot

    # content root が壊れた link / repo 内 link / 相手 repo への link になった。
    issues = a / "issues"
    issues.rmdir()
    for target, expected in ((a / "missing-issues", "broken content symlink for content_roots.issues"),
                             (a / "docs", "content root path must not traverse a symlink: content_roots.issues"),
                             (b / "issues", "path escapes authority root")):
        issues.symlink_to(target)
        rejected(expected)
        assert tree_bytes(b) == snapshot["B"]
        assert not (a / "missing-issues").exists()
        issues.unlink()


def test_init_out3_preflight_names_the_severed_or_retargeted_harness_hop_and_its_repair_restores_the_link(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    a = harness.repos["A"]
    assert harness.run("A", "build-init-scaffold.py")[0] == 0
    link = harness.link_repo("A")
    assert harness.hook("A", "--mode", "apply")[1]["status"] == "applied"
    code, report = harness.preflight("A")
    assert (code, report["status"], report["link_state"]) == (0, "pass", "ok"), report
    assert report["in_use_by"] == ["settings:.claude/settings.json", "config:claude_hooks.source=project"]
    assert report["entrypoints"] == {"checked": 2, "missing": []}  # guard-graph-schema.py と reconcile-task-lifecycle.py
    snapshot = tree_bytes(a)

    # 共有 harness の link を外す。repo の link は残るので、link 経由の hook は次の起動で entrypoint に届かない。
    harness.link.rename(tmp_path / "harness.severed")
    assert not (link / "hooks" / "reconcile-task-lifecycle.py").exists()
    code, report = harness.preflight("A")
    assert (code, report["status"], report["code"], report["link_state"], report["write_count"]) == (
        1, "rejected", "harness_link_broken", "broken", 0), report
    assert (report["broken_hop"], report["missing_target"]) == (str(link), str(harness.link))
    assert [item["option"] for item in report["remediation"]] == ["relink-shared-harness", "relink-this-repo"]
    assert report["remediation"][0]["steps"][0] == ["ln", "-sfn", str(PLUGIN), str(harness.link)]
    # init 側の書込み script も、plugin 実体から起動して書込み 0 で止まる。
    code, hooked = harness.hook("A", "--mode", "apply", via=PLUGIN)
    assert (code, hooked["status"], hooked["code"], hooked["write_count"]) == (1, "rejected", "plugin_link_broken", 0), hooked
    assert tree_bytes(a) == snapshot
    repair(report, "relink-shared-harness", a)
    assert (link / "hooks" / "reconcile-task-lifecycle.py").is_file()
    assert tree_bytes(a) == snapshot  # 直したのは repo の外の harness link だけ

    # harness link を、hooks だけを持つ別の directory へ張り替えた。
    elsewhere = tmp_path / "other-plugin"
    shutil.copytree(PLUGIN / "hooks", elsewhere / "hooks")
    harness.link.rename(tmp_path / "harness.repaired")
    harness.link.symlink_to(elsewhere)
    code, report = harness.preflight("A")
    assert (code, report["code"], report["link_state"], report["write_count"]) == (1, "harness_link_mismatch", "mismatch", 0), report
    assert [item["option"] for item in report["remediation"]] == ["relink-shared-harness", "relink-this-repo"]
    code, hooked = harness.hook("A", "--mode", "apply", via=PLUGIN)
    assert (code, hooked["status"], hooked["code"], hooked["write_count"]) == (1, "rejected", "plugin_link_mismatch", 0), hooked
    assert tree_bytes(a) == snapshot
    # この repo の link だけを plugin 実体へ向ける。共有 harness は張り替えられたまま残る。
    repair(report, "relink-this-repo", a)
    assert os.readlink(link) == str(PLUGIN) and harness.link.resolve() == elsewhere.resolve()


def test_init_out3_preflight_rejects_an_in_use_missing_link_a_plain_directory_a_loop_and_a_retired_entrypoint(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    a, b = harness.repos["A"], harness.repos["B"]
    for name in ("A", "B"):
        assert harness.run(name, "build-init-scaffold.py")[0] == 0

    # 使っていない link が無いのは pass。project fallback を選ぶなら、無い link は拒否して張り方を返す。
    code, report = harness.preflight("B")
    assert (code, report["status"], report["in_use"], report["link_state"]) == (0, "pass", False, "absent"), report
    snapshot = tree_bytes(b)
    code, report = harness.preflight("B", "--hook-source", "project-fallback")
    assert (code, report["code"], report["in_use_by"], report["write_count"]) == (
        1, "harness_link_missing", ["argv:--hook-source project-fallback"], 0), report
    assert tree_bytes(b) == snapshot
    repair(report, "relink-this-repo", b)
    assert os.readlink(b / ".claude" / "dev-graph-plugin") == str(PLUGIN)

    # symlink でない directory が link の位置にある。
    (b / ".claude" / "dev-graph-plugin").rename(tmp_path / "b-link")
    (b / ".claude" / "dev-graph-plugin").mkdir()
    code, report = harness.preflight("B")
    assert (code, report["code"], report["link_state"]) == (1, "harness_link_not_symlink", "not_symlink"), report

    # 共有 harness が自分へ戻る loop になった。
    link = harness.link_repo("A")
    harness.link.rename(tmp_path / "harness.saved")
    harness.link.symlink_to(tmp_path / "loop")
    (tmp_path / "loop").symlink_to(harness.link)
    code, report = harness.preflight("A")
    assert (code, report["code"], report["link_state"]) == (1, "harness_link_loop", "loop"), report
    assert [item["option"] for item in report["remediation"]] == ["relink-this-repo"]
    harness.link.rename(tmp_path / "harness.loop")
    (tmp_path / "harness.saved").rename(harness.link)

    # settings が、今の plugin に無い hook を link 経由で参照している。
    assert harness.hook("A", "--mode", "apply")[1]["status"] == "applied"
    settings_path = a / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["hooks"]["Stop"] = [{"hooks": [{"type": "command",
                                             "command": 'python3 "${CLAUDE_PROJECT_DIR}/.claude/dev-graph-plugin/hooks/retired-hook.py"'}]}]
    settings_path.write_text(json.dumps(settings), encoding="utf-8")
    snapshot = tree_bytes(a)
    code, report = harness.preflight("A")
    assert (code, report["code"], report["link_state"], report["entrypoints"]["missing"]) == (
        1, "harness_entrypoint_missing", "ok", ["hooks/retired-hook.py"]), report
    steps = report["remediation"][0]["steps"]
    assert report["remediation"][0]["option"] == "reapply-hook-fallback"
    assert steps[0][-4:-1] == ["--mode", "rollback", "--manifest"] and steps[0][-1].startswith(".dev-graph/state/receipts/hook-fallback-")
    assert all(step[4:6] == ["--config", ".dev-graph/config.json"] for step in steps[:-1]), steps
    assert steps[-1][-2:] == ["--config", ".dev-graph/config.json"], steps[-1]
    assert tree_bytes(a) == snapshot and link.is_symlink()


def test_init_out3_preflight_rerun_reads_the_same_non_default_config(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    b = harness.repos["B"]
    assert harness.run("B", "build-init-scaffold.py")[0] == 0
    # 既定の config は link を使わない。別の config だけが、別の名前の link を hook source に選ぶ。
    alt = ".dev-graph/alt-config.json"
    config = json.loads((b / ".dev-graph" / "config.json").read_text(encoding="utf-8"))
    config["claude_hooks"] = {"source": "project", "project_plugin_link": ".claude/alt-plugin"}
    (b / alt).write_text(json.dumps(config), encoding="utf-8")
    code, report = harness.preflight("B", "--config", alt)
    assert (code, report["code"], report["plugin_link"], report["in_use_by"]) == (
        1, "harness_link_missing", ".claude/alt-plugin", ["config:claude_hooks.source=project"]), report
    steps = report["remediation"][0]["steps"]
    assert steps[-1][-2:] == ["--config", alt], steps[-1]
    for argv in steps[:-1]:
        subprocess.run(argv, check=True, capture_output=True)
    # rerun は、直した link (alt の config が指すもの) を見て pass に戻る。既定の config を読み直すと別の link を見る。
    rerun = subprocess.run([sys.executable, *steps[-1][1:]], text=True, capture_output=True, check=False,
                           env={**os.environ, "CLAUDE_PROJECT_DIR": str(b), "PYTHONDONTWRITEBYTECODE": "1"})
    again = json.loads(rerun.stdout)
    assert (rerun.returncode, again["status"], again["plugin_link"], again["link_state"]) == (
        0, "pass", ".claude/alt-plugin", "ok"), again
    assert os.readlink(b / ".claude" / "alt-plugin") == str(PLUGIN)


def test_init_out3_skill_runs_the_preflight_before_every_init_write() -> None:
    skill = (PLUGIN / "skills" / "run-dev-graph-init" / "SKILL.md").read_text(encoding="utf-8")
    refs = next(line for line in skill.splitlines() if line.startswith("script_refs:"))
    assert "../../scripts/validate-harness-link.py" in refs
    contract = skill[skill.index("\n## Execution contract\n"):skill.index("\n## ゴールシーク実行\n")]
    order = [contract.index(name) for name in ("validate-harness-link.py", "build-init-scaffold.py", "build-project-hook-fallback.py")]
    assert order == sorted(order), order
