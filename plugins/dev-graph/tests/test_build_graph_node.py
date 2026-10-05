from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "scripts" / "build-graph-node.py"
VALIDATOR = PLUGIN / "scripts" / "validate-graph-schema.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("dev_graph_build_graph_node", SCRIPT)
assert SPEC and SPEC.loader
BGN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BGN
SPEC.loader.exec_module(BGN)
CONTRACT = json.loads((PLUGIN / "templates" / "template-contract.json").read_text(encoding="utf-8"))
ROOTS = {"issues": "issues", "tasks": "tasks", "specifications": "specs", "architecture": "architecture",
         "features": "features", "documents": "docs", "system_spec": "system-spec"}


BASE = {"project_id": "web", "domain": "auth", "tracker_binding": "none"}


def candidates(kind: str, confidence: float = 0.95, runner_up: float = 0.05) -> dict:
    other = "document" if kind != "document" else "issue"
    return {"reason": f"explicit {kind} request", "decision": "auto",
            "candidates": [{"artifact_kind": kind, "confidence": confidence},
                           {"artifact_kind": other, "confidence": runner_up}]}


def filled(kind: str) -> dict[str, str]:
    return {name: f"{name} の確定内容。" for name in CONTRACT["artifacts"][kind]["required_sections"]}


class BuildGraphNodeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        state = self.root / ".dev-graph" / "state"
        state.mkdir(parents=True)
        (self.root / ".dev-graph" / "cache" / "inputs").mkdir(parents=True)
        (self.root / ".dev-graph" / "config.json").write_text(json.dumps({
            "schema_version": "1.0.0", "content_roots": ROOTS,
            "local_state": {"graph": ".dev-graph/state/graph.json", "cache": ".dev-graph/cache",
                            "locks": ".dev-graph/locks"},
            "execution_tracker": {"mode": "beads"},
        }), encoding="utf-8")
        self.graph = state / "graph.json"
        self.graph.write_text(json.dumps({"graph_revision": 0, "nodes": [], "schema_version": "1.0.0"}), encoding="utf-8")
        for directory in ROOTS.values():
            (self.root / directory).mkdir()
        self.env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
        self.counter = 0

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_input(self, payload: dict) -> Path:
        self.counter += 1
        path = self.root / ".dev-graph" / "cache" / "inputs" / f"input-{self.counter}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def pinned(self, payload: dict, extra: tuple[str, ...] = ()) -> dict:
        """Apply the way R3 does: pin the CAS to the current revision unless the test sets it or previews."""
        if "--dry-run" in extra or "expected_graph_revision" in payload:
            return payload
        return {"expected_graph_revision": self.graph_state()["graph_revision"], **payload}

    def run_cli(self, command: str, payload: dict | Path, *extra: str, pin: bool = True) -> tuple[int, dict]:
        if isinstance(payload, Path):
            path = payload
        else:
            path = self.write_input(self.pinned(payload, extra) if pin else payload)
        cp = subprocess.run([sys.executable, str(SCRIPT), command, "--repo-root", str(self.root), "--input", str(path), *extra],
                            text=True, capture_output=True, env=self.env, cwd=self.root, check=False)
        return cp.returncode, json.loads(cp.stdout)

    def run_in_process(self, command: str, payload: dict) -> tuple[int, dict]:
        path = self.write_input(self.pinned(payload))
        stream = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=False), redirect_stdout(stream):
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
            code = BGN.main([command, "--repo-root", str(self.root), "--input", str(path)])
        return code, json.loads(stream.getvalue())

    def graph_state(self) -> dict:
        return json.loads(self.graph.read_text(encoding="utf-8"))

    def validate(self) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(VALIDATOR), "--graph", str(self.graph), "--repo-root", str(self.root)],
                              text=True, capture_output=True, env=self.env, check=False)

    def headings(self, relative: str) -> list[tuple[int, str]]:
        lines = (self.root / relative).read_text(encoding="utf-8").splitlines(keepends=True)
        return [(head["level"], head["title"]) for head in BGN._headings(lines)]

    def add_five(self) -> dict:
        artifacts = [
            {**BASE, "title": "T", "artifact_kind": "issue", "slug": "login-timeout", "title": "Login timeout", "tracker_binding": "none",
             "classification": candidates("issue"), "sections": filled("issue")},
            {**BASE, "title": "T", "artifact_kind": "task", "slug": "fix-timeout", "title": "Fix timeout", "tracker_binding": "repo-config-default",
             "classification": candidates("task")},
            {**BASE, "title": "T", "artifact_kind": "document", "slug": "runbook", "title": "Runbook", "tracker_binding": "none",
             "classification": candidates("document")},
            {**BASE, "title": "T", "artifact_kind": "architecture", "slug": "web", "title": "Web", "tracker_binding": "none",
             "artifact_subtypes": ["backend", "frontend"], "classification": candidates("architecture"),
             "subtype_sections": {"frontend": {"Routes, screens and navigation": "ログイン画面とセッション失効画面。"}}},
            {**BASE, "title": "T", "artifact_kind": "specification", "slug": "session-api", "title": "Session API", "tracker_binding": "none",
             "artifact_subtypes": ["api"], "classification": candidates("specification"),
             "api_contracts": [{"operation": "POST /sessions", "sections": {"Request": "email と password を受け取る。"}}]},
        ]
        code, report = self.run_cli("add", {"expected_graph_revision": 0, "artifacts": artifacts})
        self.assertEqual(code, 0, report)
        return report

    def test_add_five_kinds_composes_every_required_heading_and_passes_validator(self) -> None:
        report = self.add_five()
        self.assertEqual((report["status"], report["applied_count"], report["graph_revision_after"]), ("applied", 5, 1))
        graph = self.graph_state()
        self.assertEqual(graph["graph_revision"], 1)
        by_id = {node["graph_node_id"]: node for node in graph["nodes"]}
        self.assertEqual(set(by_id), {"issue-login-timeout", "task-fix-timeout", "doc-runbook", "arch-web", "spec-session-api"})
        self.assertEqual(by_id["task-fix-timeout"]["tracker_binding"], "beads")
        self.assertEqual(by_id["arch-web"]["artifact_subtypes"], ["frontend", "backend"])
        for node in graph["nodes"]:
            titles = {title for _, title in self.headings(node["file_path"])}
            required = CONTRACT["artifacts"][node["artifact_kind"]]["required_sections"]
            self.assertEqual([name for name in required if name not in titles], [], node["graph_node_id"])
        arch = self.headings("architecture/web.md")
        self.assertIn((3, "Frontend architecture"), arch)
        self.assertIn((3, "Backend architecture"), arch)
        self.assertNotIn((3, "Data architecture"), arch)
        spec = self.headings("specs/session-api.md")
        self.assertIn((3, "API: POST /sessions"), spec)
        self.assertIn((4, "Error contract"), spec)
        self.assertEqual(by_id["issue-login-timeout"]["implementation_readiness"]["status"], "complete")
        self.assertEqual(by_id["task-fix-timeout"]["implementation_readiness"]["status"], "incomplete")
        receipt = self.root / report["receipt_path"]
        self.assertTrue(receipt.is_file())
        self.assertEqual(json.loads(receipt.read_text(encoding="utf-8"))["graph_digest_after"], report["graph_digest_after"])
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_update_replaces_one_section_and_keeps_identity_and_other_bytes(self) -> None:
        self.add_five()
        issue = self.root / "issues" / "login-timeout.md"
        before = issue.read_text(encoding="utf-8")
        others = {path: path.read_bytes() for path in (self.root / "docs" / "runbook.md", self.root / "specs" / "session-api.md")}
        code, report = self.run_cli("update", {"expected_graph_revision": 1, "updates": [{
            "graph_node_id": "issue-login-timeout",
            "set_sections": {"現在の挙動": "30 秒でセッションが切れる。"},
            "append_sections": {"調査メモ": "ログイン API の TTL 設定を確認した。"},
        }]})
        self.assertEqual(code, 0, report)
        after = issue.read_text(encoding="utf-8")
        self.assertIn("30 秒でセッションが切れる。", after)
        self.assertTrue(after.rstrip().endswith("ログイン API の TTL 設定を確認した。"))
        untouched = before.split("## 期待する挙動", 1)[1]
        self.assertTrue(after.split("## 期待する挙動", 1)[1].startswith(untouched.rstrip()[:200]))
        node = next(item for item in self.graph_state()["nodes"] if item["graph_node_id"] == "issue-login-timeout")
        self.assertEqual((node["graph_node_id"], node["file_path"]), ("issue-login-timeout", "issues/login-timeout.md"))
        self.assertEqual(self.graph_state()["graph_revision"], 2)
        self.assertEqual(report["artifacts"][0]["sections_replaced"], ["現在の挙動"])
        self.assertEqual(report["artifacts"][0]["sections_appended"], ["調査メモ"])
        for path, data in others.items():
            self.assertEqual(path.read_bytes(), data)
        self.assertTrue((self.root / report["receipt_path"]).is_file())
        self.assertEqual(self.validate().returncode, 0)

    def test_update_adds_architecture_subtype_without_rewriting_existing_blocks(self) -> None:
        self.add_five()
        path = self.root / "architecture" / "web.md"
        frontend_before = path.read_text(encoding="utf-8").split("### Frontend architecture", 1)[1].split("### Backend architecture", 1)[0]
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "arch-web", "add_subtypes": ["security"]}]})
        self.assertEqual(code, 0, report)
        text = path.read_text(encoding="utf-8")
        self.assertIn("### Security architecture", text)
        self.assertIn(frontend_before, text)
        node = next(item for item in self.graph_state()["nodes"] if item["graph_node_id"] == "arch-web")
        self.assertEqual(node["artifact_subtypes"], ["frontend", "backend", "security"])
        self.assertEqual(self.validate().returncode, 0)

    def test_feature_is_rejected_before_any_write(self) -> None:
        before = self.graph.read_bytes()
        code, report = self.run_cli("add", {"artifacts": [{**BASE, "title": "T", "artifact_kind": "feature", "slug": "checkout",
                                                           "tracker_binding": "none", "classification": candidates("issue")}]})
        self.assertEqual((code, report["code"], report["applied_count"], report["write_count"]),
                         (1, "feature_requires_c14_macro_contract", 0, 0))
        self.assertEqual(list((self.root / "features").iterdir()), [])
        self.assertEqual(self.graph.read_bytes(), before)
        code, report = self.run_cli("add", {"artifacts": [{**BASE, "title": "T", "artifact_kind": "issue", "slug": "x", "tracker_binding": "none",
                                                           "classification": {"reason": "r", "candidates": [
                                                               {"artifact_kind": "issue", "confidence": 0.5},
                                                               {"artifact_kind": "feature", "confidence": 0.5}]}}]})
        self.assertEqual(report["code"], "feature_requires_c14_macro_contract")

    def test_package_member_fields_are_routed_to_register_package(self) -> None:
        code, report = self.run_cli("add", {"artifacts": [{**BASE, "title": "T", "artifact_kind": "task", "slug": "p01", "tracker_binding": "none",
                                                           "parent_feature": "feature-1", "classification": candidates("task")}]})
        self.assertEqual((code, report["code"]), (1, "package_member_requires_register_package"))

    def test_revision_conflict_and_dry_run_write_nothing(self) -> None:
        before = self.graph.read_bytes()
        entry = {**BASE, "title": "T", "artifact_kind": "issue", "slug": "a", "tracker_binding": "none", "classification": candidates("issue")}
        code, report = self.run_cli("add", {"expected_graph_revision": 3, "artifacts": [entry]})
        self.assertEqual((code, report["code"]), (1, "graph_revision_conflict"))
        code, report = self.run_cli("add", {"artifacts": [entry]}, "--dry-run")
        self.assertEqual((code, report["status"], report["write_count"], report["planned_count"]), (0, "preview", 0, 1))
        self.assertEqual(self.graph.read_bytes(), before)
        self.assertFalse((self.root / "issues" / "a.md").exists())
        self.assertFalse((self.root / report["receipt_path"]).exists())

    def test_receipt_failure_rolls_back_graph_and_content(self) -> None:
        before = self.graph.read_bytes()
        entry = {**BASE, "title": "T", "artifact_kind": "issue", "slug": "rollback", "tracker_binding": "none", "classification": candidates("issue")}
        with mock.patch.object(BGN, "_create_receipt", side_effect=OSError("disk full")):
            code, report = self.run_in_process("add", {"artifacts": [entry]})
        self.assertEqual((code, report["status"]), (2, "error"))
        self.assertEqual(self.graph.read_bytes(), before)
        self.assertFalse((self.root / "issues" / "rollback.md").exists())

    def test_low_confidence_needs_user_confirmation(self) -> None:
        entry = {**BASE, "title": "T", "artifact_kind": "issue", "slug": "ambiguous", "tracker_binding": "none",
                 "classification": candidates("issue", confidence=0.70, runner_up=0.60)}
        code, report = self.run_cli("add", {"artifacts": [entry]})
        self.assertEqual((code, report["code"]), (1, "classification_requires_user_confirmation"))
        entry["classification"]["decision"] = "user_confirmed"
        code, report = self.run_cli("add", {"artifacts": [entry]})
        self.assertEqual(code, 0, report)
        self.assertEqual(report["artifacts"][0]["classification"]["decision"], "user_confirmed")

    def test_input_outside_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / "input.json"
            path.write_text(json.dumps({"artifacts": []}), encoding="utf-8")
            code, report = self.run_cli("add", path)
        self.assertEqual(code, 2)
        self.assertFalse(report["valid"])

    def test_heading_injection_and_secrets_are_rejected(self) -> None:
        entry = {**BASE, "title": "T", "artifact_kind": "issue", "slug": "inject", "tracker_binding": "none", "classification": candidates("issue"),
                 "sections": {"概要": "要約\n## 偽の見出し"}}
        self.assertEqual(self.run_cli("add", {"artifacts": [entry]})[1]["code"], "section_contains_heading")
        entry["sections"] = {"概要": "token ghp_" + "a" * 30}
        self.assertEqual(self.run_cli("add", {"artifacts": [entry]})[1]["code"], "secret_like_content")

    def test_unchanged_update_is_noop(self) -> None:
        self.add_five()
        before = self.graph.read_bytes()
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "doc-runbook"}]})
        self.assertEqual((code, report["status"], report["write_count"]), (0, "noop", 0))
        self.assertEqual(self.graph.read_bytes(), before)

    # ------------------------------------------------------------ C14 macro feature (M1)

    def feature_entry(self, slug: str, **extra: object) -> dict:
        macro = {"purpose": "購入者が迷わず決済を終えられるようにする。", "goal": "カートから 3 画面以内で決済が完了する。",
                 "scope_in": ["カート確認", "決済確定"], "scope_out": ["ポイント付与"],
                 "acceptance": ["決済完了画面が表示される"], "architecture_refs": ["arch-web"]}
        return {**BASE, "title": f"Feature {slug}", "artifact_kind": "feature", "slug": slug, "macro": macro, **extra}

    def test_feature_registers_through_macro_contract_with_projected_body(self) -> None:
        self.add_five()
        code, report = self.run_cli("add", {"expected_graph_revision": 1, "artifacts": [
            self.feature_entry("cart"), self.feature_entry("checkout", depends_on=["feature-cart"])]})
        self.assertEqual(code, 0, report)
        self.assertEqual(report["artifacts"][1]["classification"]["decision"], "c14_macro_contract")
        node = next(item for item in self.graph_state()["nodes"] if item["graph_node_id"] == "feature-checkout")
        self.assertEqual((node["file_path"], node["purpose"], node["architecture_refs"], node["depends_on"]),
                         ("features/checkout.md", "購入者が迷わず決済を終えられるようにする。", ["arch-web"], ["feature-cart"]))
        self.assertEqual(node["source_lineage"]["origin_kind"], "generated")
        self.assertEqual(node["implementation_readiness"]["status"], "complete")
        text = (self.root / "features" / "checkout.md").read_text(encoding="utf-8")
        for line in ("- スコープ内: カート確認", "- スコープ外: ポイント付与", "- [ ] 決済完了画面が表示される",
                     "- `arch-web`", "- `feature-cart`", "parent_feature=`feature-checkout`"):
            self.assertIn(line, text)
        self.assertEqual(self.validate().returncode, 0, self.validate().stdout)

    def test_feature_contract_violations_are_rejected_without_writes(self) -> None:
        self.add_five()
        before = self.graph.read_bytes()
        cases = [
            (self.feature_entry("a", classification=candidates("issue")), "invalid_input"),
            ({**self.feature_entry("b"), "macro": {"purpose": "p"}}, "invalid_macro"),
            ({**self.feature_entry("c"), "macro": {**self.feature_entry("c")["macro"], "scope_in": []}}, "invalid_macro"),
            ({**self.feature_entry("d"), "macro": {**self.feature_entry("d")["macro"], "architecture_refs": ["doc-runbook"]}},
             "invalid_macro_reference"),
            (self.feature_entry("e", depends_on=["task-fix-timeout"]), "invalid_macro_reference"),
            (self.feature_entry("f", sections={"目的": "本文で上書き"}), "macro_section_is_projection"),
            ({**BASE, "title": "I", "artifact_kind": "issue", "slug": "g", "classification": candidates("issue"),
              "macro": self.feature_entry("g")["macro"]}, "invalid_input"),
        ]
        for entry, expected in cases:
            code, report = self.run_cli("add", {"artifacts": [entry]})
            self.assertEqual((code, report["code"], report["write_count"]), (1, expected, 0), entry["slug"])
        self.assertEqual(self.graph.read_bytes(), before)
        self.assertEqual(list((self.root / "features").iterdir()), [])

    def test_feature_update_regenerates_projection_from_macro_patch(self) -> None:
        self.add_five()
        self.assertEqual(self.run_cli("add", {"artifacts": [self.feature_entry("cart"), self.feature_entry("checkout")]})[0], 0)
        path = self.root / "features" / "checkout.md"
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "feature-checkout",
                                                            "macro_patch": {"scope_out": ["ポイント付与", "返品"]},
                                                            "node_patch": {"depends_on": ["feature-cart"]}}]})
        self.assertEqual(code, 0, report)
        self.assertEqual(report["artifacts"][0]["sections_regenerated"], ["スコープ", "機能間依存"])
        text = path.read_text(encoding="utf-8")
        self.assertIn("- スコープ外: 返品", text)
        self.assertIn("- `feature-cart`", text)
        self.assertNotIn("先行 feature なし", text)
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "feature-checkout", "set_sections": {"目的": "x"}}]})
        self.assertEqual((code, report["code"]), (1, "macro_section_is_projection"))
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "doc-runbook", "macro_patch": {"goal": "g"}}]})
        self.assertEqual((code, report["code"]), (1, "invalid_input"))
        self.assertEqual(self.validate().returncode, 0)

    # ------------------------------------------------------------ generated sections and order (M2)

    def test_added_subtypes_regenerate_listing_and_keep_canonical_block_order(self) -> None:
        self.add_five()
        path = self.root / "architecture" / "web.md"
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "arch-web", "add_subtypes": ["security", "data"]}]})
        self.assertEqual(code, 0, report)
        self.assertEqual(report["artifacts"][0]["sections_regenerated"], ["Subtype architecture"])
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "arch-web", "add_subtypes": ["infrastructure"]}]})
        self.assertEqual(code, 0, report)
        text = path.read_text(encoding="utf-8")
        for subtype in ("Frontend", "Backend", "Infrastructure", "Data", "Security"):
            self.assertIn(f"- {subtype}: 合成済み", text)
        self.assertNotIn("N/A: subtype 非選択", text)
        blocks = [title for level, title in self.headings("architecture/web.md") if level == 3]
        self.assertEqual(blocks, ["Frontend architecture", "Backend architecture", "Infrastructure architecture",
                                  "Data architecture", "Security architecture"])
        self.assertEqual(self.validate().returncode, 0)

    def test_hand_edited_generated_section_is_not_overwritten(self) -> None:
        self.add_five()
        code, _ = self.run_cli("update", {"updates": [{"graph_node_id": "arch-web",
                                                       "set_sections": {"Subtype architecture": "手で書いた subtype 一覧。"}}]})
        self.assertEqual(code, 0)
        before = self.graph.read_bytes()
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "arch-web", "add_subtypes": ["data"]}]})
        self.assertEqual((code, report["code"]), (1, "generated_section_diverged"))
        self.assertEqual(self.graph.read_bytes(), before)
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "arch-web", "add_subtypes": ["data"],
                                                            "set_sections": {"Subtype architecture": "Data を追加した一覧。"}}]})
        self.assertEqual(code, 0, report)
        self.assertIn("Data を追加した一覧。", (self.root / "architecture" / "web.md").read_text(encoding="utf-8"))

    def test_first_api_contract_regenerates_api_section_and_api_subtype(self) -> None:
        entry = {**BASE, "title": "Profile", "artifact_kind": "specification", "slug": "profile", "classification": candidates("specification")}
        self.assertEqual(self.run_cli("add", {"artifacts": [entry]})[0], 0)
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "spec-profile",
                                                            "add_api_contracts": [{"operation": "GET /profile"}]}]})
        self.assertEqual(code, 0, report)
        self.assertEqual(report["artifacts"][0]["sections_regenerated"], ["API契約"])
        node = next(item for item in self.graph_state()["nodes"] if item["graph_node_id"] == "spec-profile")
        self.assertEqual(node["artifact_subtypes"], ["api"])
        self.assertIn("endpoint ごとの契約を以下に合成する", (self.root / "specs" / "profile.md").read_text(encoding="utf-8"))

    # ------------------------------------------------------------ heading keys and text (M3)

    def test_section_keys_and_text_cannot_smuggle_structure(self) -> None:
        self.add_five()
        entry = {**BASE, "title": "I", "artifact_kind": "issue", "slug": "keys", "classification": candidates("issue")}
        for key in ("メモ\u2028## 偽", "# 偽", "A > B", " 前後空白", "x" * 121, "token ghp_" + "a" * 30):
            code, report = self.run_cli("add", {"artifacts": [{**entry, "sections": {key: "本文"}}]})
            self.assertEqual(code, 1)
            self.assertIn(report["code"], {"invalid_section_key", "secret_like_content"}, repr(key))
        for key in ("新規\n## 偽", "# 偽"):
            code, report = self.run_cli("update", {"updates": [{"graph_node_id": "doc-runbook", "append_sections": {key: "本文"}}]})
            self.assertEqual((code, report["code"]), (1, "invalid_section_key"), repr(key))
        code, report = self.run_cli("add", {"artifacts": [{**entry, "sections": {"概要": "要約\u2028## 偽の見出し"}}]})
        self.assertEqual(report["code"], "section_contains_heading")
        code, report = self.run_cli("add", {"artifacts": [{**entry, "sections": {"概要": "```\nopen fence"}}]})
        self.assertEqual(report["code"], "section_unbalanced_fence")
        code, report = self.run_cli("add", {"artifacts": [{**entry, "sections": {"概要": "```\n## inside fence\n```"}}]})
        self.assertEqual(code, 0, report)

    # ------------------------------------------------------------ tracker and subtypes (M4/M5)

    def set_tracker_mode(self, mode: str) -> None:
        config = self.root / ".dev-graph" / "config.json"
        data = json.loads(config.read_text(encoding="utf-8"))
        data["execution_tracker"] = {"mode": mode}
        config.write_text(json.dumps(data), encoding="utf-8")

    def test_github_binding_is_refused_at_the_entrance(self) -> None:
        self.set_tracker_mode("github")
        entry = {**BASE, "title": "I", "artifact_kind": "issue", "slug": "gh", "classification": candidates("issue")}
        for binding in ("github", "repo-config-default"):
            code, report = self.run_cli("add", {"artifacts": [{**entry, "tracker_binding": binding}]})
            self.assertEqual((code, report["code"], report["write_count"]), (1, "github_binding_requires_confirmed_node", 0), binding)

    def test_explicit_binding_must_be_allowed_by_tracker_mode(self) -> None:
        # Same rule as register-package._resolve_binding: none always, beads/github only where the mode allows.
        entry = {**BASE, "title": "I", "artifact_kind": "issue", "classification": candidates("issue")}
        # none は repo-config の mode ではない (beads/github/both)。binding none へ黙って倒さず、repo-config-default を解決不能にする。
        cases = [("none", "beads", "tracker_binding_not_allowed"), ("github", "beads", "tracker_binding_not_allowed"),
                 ("beads", "github", "tracker_binding_not_allowed"), ("both", "repo-config-default", "tracker_binding_unresolved"),
                 ("none", "repo-config-default", "tracker_binding_unresolved")]
        for index, (mode, binding, expected) in enumerate(cases):
            self.set_tracker_mode(mode)
            code, report = self.run_cli("add", {"artifacts": [{**entry, "slug": f"m{index}", "tracker_binding": binding}]})
            self.assertEqual((code, report["code"], report["write_count"]), (1, expected, 0), (mode, binding))
        self.assertEqual(self.graph_state()["nodes"], [])
        for index, (mode, binding) in enumerate([("both", "beads"), ("none", "none"), ("github", "none")]):
            self.set_tracker_mode(mode)
            code, report = self.run_cli("add", {"artifacts": [{**entry, "slug": f"ok{index}", "tracker_binding": binding}]})
            self.assertEqual(code, 0, (mode, binding, report))
        self.assertEqual([node["tracker_binding"] for node in self.graph_state()["nodes"]], ["beads", "none", "none"])

    def test_bind_github_switches_a_passed_issue_and_keeps_the_body(self) -> None:
        self.set_tracker_mode("github")
        issue = {**BASE, "title": "I", "artifact_kind": "issue", "slug": "pub", "classification": candidates("issue"),
                 "sections": filled("issue")}
        doc = {**BASE, "title": "D", "artifact_kind": "document", "slug": "pub-doc", "classification": candidates("document")}
        self.assertEqual(self.run_cli("add", {"artifacts": [issue, doc]})[0], 0)
        bind = {"bindings": [{"graph_node_id": "issue-pub"}]}
        code, report = self.run_cli("bind-github", bind)
        self.assertEqual((code, report["code"], report["write_count"]), (1, "github_binding_requires_confirmed_node", 0))
        self.mark_passed("issue-pub")
        code, report = self.run_cli("bind-github", {"bindings": [{"graph_node_id": "doc-pub-doc"}]})
        self.assertEqual((code, report["code"]), (1, "bind_github_requires_issue_or_task"))
        code, report = self.run_cli("bind-github", {**bind, "extra": True})
        self.assertEqual((code, report["code"]), (1, "invalid_input"))
        path = self.root / "issues" / "pub.md"
        body = BGN._split_frontmatter(path.read_text(encoding="utf-8"), "issues/pub.md")[1]
        code, report = self.run_cli("bind-github", bind)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["artifacts"][0]["tracker_binding"], {"before": "none", "after": "github"})
        node = next(item for item in self.graph_state()["nodes"] if item["graph_node_id"] == "issue-pub")
        self.assertEqual((node["tracker_binding"], node["github_publication"]["mode"], node["beads_linkage"], node["evaluation_status"]),
                         ("github", "issue", None, "pass"))
        self.assertEqual(BGN.VGS.frontmatter_of(path)["tracker_binding"], "github")
        self.assertEqual(BGN._split_frontmatter(path.read_text(encoding="utf-8"), "issues/pub.md")[1], body)
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        code, report = self.run_cli("bind-github", bind)
        self.assertEqual((code, report["status"], report["write_count"]), (0, "noop", 0))
        self.set_tracker_mode("beads")
        code, report = self.run_cli("bind-github", bind)
        self.assertEqual((code, report["code"]), (1, "tracker_binding_not_allowed"))

    def test_github_mirrored_fields_import_into_an_active_published_node_without_going_stale(self) -> None:
        # C03 imports a remote Issue title / Project field through update; the schema keeps a published or active node
        # at pass, so only a body change (which needs re-evaluation) may be refused.
        self.set_tracker_mode("github")
        issue = {**BASE, "title": "I", "artifact_kind": "issue", "slug": "pub", "classification": candidates("issue"),
                 "sections": filled("issue")}
        self.assertEqual(self.run_cli("add", {"artifacts": [issue]})[0], 0)
        self.mark_passed("issue-pub")
        self.assertEqual(self.run_cli("bind-github", {"bindings": [{"graph_node_id": "issue-pub"}]})[0], 0)
        update = {"graph_node_id": "issue-pub", "node_patch": {"status": "active"}}
        self.assertEqual(self.run_cli("update", {"updates": [update]})[0], 0)
        imported = {"title": "I (remote revision 2)", "priority": "high", "target_date": "2026-11-30"}
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "issue-pub", "node_patch": imported}]})
        self.assertEqual(code, 0, report)
        node = next(item for item in self.graph_state()["nodes"] if item["graph_node_id"] == "issue-pub")
        self.assertEqual((node["status"], node["evaluation_status"], node["title"]), ("active", "pass", imported["title"]))
        self.assertEqual(BGN.VGS.frontmatter_of(self.root / "issues" / "pub.md")["title"], imported["title"])
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        before = (self.root / "issues" / "pub.md").read_bytes()
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "issue-pub", "set_sections": {"背景と問題": "remote body"}}]})
        self.assertEqual((code, report["code"], report["write_count"]), (1, "pre_write_validation_failed", 0))
        self.assertIn("active_not_ready", {finding["code"] for finding in report["findings"]})
        self.assertEqual((self.root / "issues" / "pub.md").read_bytes(), before)

    def test_system_spec_lineage_must_resolve_before_add(self) -> None:
        source = self.root / "system-spec" / "auth.md"
        source.write_text("# 認証仕様\n", encoding="utf-8")
        lineage = {"origin_kind": "system-spec-harness", "source_plugin": "system-spec-harness", "source_path": "system-spec/auth.md",
                   "source_version": "1.0.0", "source_digest": hashlib.sha256(source.read_bytes()).hexdigest(),
                   "imported_at": "2026-10-01T00:00:00Z"}
        entry = {**BASE, "title": "S", "artifact_kind": "specification", "classification": candidates("specification")}
        rejected = [({**lineage, "source_digest": "0" * 64}, "lineage_digest_mismatch"),
                    ({**lineage, "source_path": "system-spec/gone.md"}, "lineage_source_missing")]
        for index, (bad, expected) in enumerate(rejected):
            code, report = self.run_cli("add", {"artifacts": [{**entry, "slug": f"bad-{index}", "source_lineage": bad}]})
            self.assertEqual((code, report["code"], report["write_count"]), (1, "source_lineage_unverified", 0), expected)
            self.assertEqual([item["code"] for item in report["findings"]], [expected])
        self.assertEqual(self.graph_state()["nodes"], [])
        code, report = self.run_cli("add", {"artifacts": [{**entry, "slug": "auth", "source_lineage": lineage}]})
        self.assertEqual(code, 0, report)
        self.assertEqual(self.validate().returncode, 0)

    def test_system_spec_import_confirms_only_with_pass_evidence(self) -> None:
        source = self.root / "system-spec" / "index.md"
        source.write_text("# 仕様書\n", encoding="utf-8")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        lineage = {"origin_kind": "system-spec-harness", "source_plugin": "system-spec-harness", "source_path": "system-spec/index.md",
                   "source_version": "0.1.0", "source_digest": digest, "imported_at": "2026-10-01T00:00:00Z"}
        (self.root / "eval-log").mkdir()
        (self.root / "eval-log" / "pass.json").write_text(json.dumps({"verdict": "PASS", "spec_dir": "system-spec"}), encoding="utf-8")
        (self.root / "eval-log" / "fail.json").write_text(json.dumps({"verdict": "FAIL", "spec_dir": "system-spec"}), encoding="utf-8")
        (self.root / "eval-log" / "other.json").write_text(json.dumps({"verdict": "PASS", "spec_dir": "docs"}), encoding="utf-8")
        evidence = {"evaluator": BGN.SPEC_EVALUATOR, "evidence_ref": "eval-log/pass.json", "evaluated_digest": digest}
        entry = {**BASE, "title": "S", "artifact_kind": "specification", "classification": candidates("specification"),
                 "sections": filled("specification"), "source_lineage": lineage}
        rejected = [
            ({**evidence, "evidence_ref": "eval-log/fail.json"}, entry, "confirmation_evidence_not_pass"),
            ({**evidence, "evidence_ref": "eval-log/other.json"}, entry, "invalid_confirmation_evidence"),
            ({**evidence, "evaluated_digest": "0" * 64}, entry, "invalid_confirmation_evidence"),
            ({**evidence, "evaluator": "someone-else"}, entry, "invalid_confirmation_evidence"),
            (evidence, {**entry, "sections": {}}, "confirmed_import_requires_complete_readiness"),
            (evidence, {k: v for k, v in entry.items() if k != "source_lineage"}, "confirmation_requires_spec_import"),
        ]
        for index, (bad, base, expected) in enumerate(rejected):
            code, report = self.run_cli("add", {"artifacts": [{**base, "slug": f"bad-{index}", "confirmation_evidence": bad}]})
            self.assertEqual((code, report["code"], report["write_count"]), (1, expected, 0), report)
        self.assertEqual(self.graph_state()["nodes"], [])
        code, report = self.run_cli("add", {"artifacts": [{**entry, "slug": "system", "confirmation_evidence": evidence}]})
        self.assertEqual(code, 0, report)
        node = self.graph_state()["nodes"][0]
        self.assertEqual((node["status"], node["confirmation_status"], node["evaluation_status"]), ("done", "confirmed", "pass"))
        self.assertEqual(node["confirmation_evidence"], evidence)
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # ------------------------------------------------------------ readiness fill, CAS, C14 architecture, frontmatter bytes

    def test_readiness_fill_completes_node_via_named_updates(self) -> None:
        report = self.add_five()
        fills = {item["graph_node_id"]: item["readiness_fill"] for item in report["artifacts"]}
        updates = []
        for node_id in ("arch-web", "spec-session-api"):
            self.assertTrue(fills[node_id], node_id)
            self.assertTrue(all(entry["via"] in {"set_sections", "append_sections"} for entry in fills[node_id]), fills[node_id])
            update: dict = {"graph_node_id": node_id}
            for entry in fills[node_id]:
                update.setdefault(entry["via"], {})[entry["key"]] = f"{entry['item']} を確定した。"
            updates.append(update)
        leaf = next(entry["item"] for entry in fills["arch-web"] if entry["item"].startswith("backend:"))
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "arch-web", "append_sections": {leaf: "本文"}}]})
        self.assertEqual((code, report["code"]), (1, "readiness_item_is_not_a_heading"))
        code, report = self.run_cli("update", {"updates": updates})
        self.assertEqual(code, 0, report)
        self.assertEqual([item["readiness_fill"] for item in report["artifacts"]], [[], []])
        statuses = {node["graph_node_id"]: node["implementation_readiness"]["status"] for node in self.graph_state()["nodes"]}
        self.assertEqual((statuses["arch-web"], statuses["spec-session-api"]), ("complete", "complete"))
        arch = self.headings("architecture/web.md")
        self.assertIn((3, "Frontend architecture"), arch)
        self.assertIn((3, "Backend architecture"), arch)
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # A top heading removed by hand comes back through append_sections even though the API block repeats its title.
        path = self.root / "specs" / "session-api.md"
        head, rest = path.read_text(encoding="utf-8").split("\n## 認証・認可\n", 1)
        path.write_text(head + "\n## " + rest.split("\n## ", 1)[1], encoding="utf-8")
        lines = BGN._split_frontmatter(path.read_text(encoding="utf-8"), "specs/session-api.md")[1]
        self.assertEqual(BGN.Composer(self.root, CONTRACT).readiness("specification", ["api"], lines),
                         [{"item": "認証・認可", "via": "append_sections", "key": "認証・認可"}])
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "spec-session-api",
                                                            "append_sections": {"認証・認可": "セッション cookie で認証する。"}}]})
        self.assertEqual((code, report.get("artifacts", [{}])[0].get("readiness_fill")), (0, []), report)

    def test_only_placeholder_only_sections_stay_unfilled(self) -> None:
        # template-contract placeholder_only_section: prose that merely mentions `<` or 未定 is filled.
        names = CONTRACT["artifacts"]["issue"]["required_sections"]
        prose = ["応答は p95 < 300ms に収める。", "`Authorization: Bearer <token>` を必須にする。", "保存期間は未定だが 30 日を上限にする。"]
        sections = {name: prose[index % len(prose)] for index, name in enumerate(names)}
        entry = {**BASE, "title": "I", "artifact_kind": "issue", "classification": candidates("issue")}
        code, report = self.run_cli("add", {"artifacts": [{**entry, "slug": "prose", "sections": sections}]})
        self.assertEqual((code, report["artifacts"][0]["readiness_fill"]), (0, []), report)
        # A template line kept as is, or nothing but placeholders, leaves the section unfilled; one real line fills it.
        partial = {**{name: text for name, text in sections.items() if name != "影響と優先度"},
                   "スコープ": "- In: <対象>\n- Out: 決済は対象外", "受入条件": "- [ ] <未記入> <TBD>",
                   "検証証跡": "- コマンド/テスト: TODO\n- 証跡 path: <path-or-url>"}
        code, report = self.run_cli("add", {"artifacts": [{**entry, "slug": "partial", "sections": partial}]})
        self.assertEqual(code, 0, report)
        self.assertEqual(report["artifacts"][0]["readiness_fill"],
                         [{"item": name, "via": "set_sections", "key": name} for name in ("影響と優先度", "受入条件", "検証証跡")])

    def test_autolink_fills_a_section_but_label_or_na_placeholders_do_not(self) -> None:
        names = CONTRACT["artifacts"]["issue"]["required_sections"]
        entry = {**BASE, "title": "I", "artifact_kind": "issue", "classification": candidates("issue")}
        sections = {**filled("issue"), names[0]: "<https://example.com/spec/42>", names[1]: "N/A: <reason>", names[2]: "- メモ: <TBD>"}
        code, report = self.run_cli("add", {"artifacts": [{**entry, "slug": "links", "sections": sections}]})
        self.assertEqual(code, 0, report)
        self.assertEqual([item["item"] for item in report["artifacts"][0]["readiness_fill"]], [names[1], names[2]])
        # 理由や中身を 1 行書けば、同じ形の行でも充足する。
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "issue-links", "set_sections": {
            names[1]: "N/A: 社内ツールのため外部影響なし", names[2]: "- メモ: Safari でだけ再現する"}}]})
        self.assertEqual((code, report["artifacts"][0]["readiness_fill"]), (0, []), report)

    def test_all_architecture_subtypes_compose_in_canonical_order_and_spec_without_api_has_no_api_block(self) -> None:
        arch = {**BASE, "title": "A", "artifact_kind": "architecture", "slug": "all",
                "artifact_subtypes": list(reversed(BGN.ARCH_SUBTYPES)), "classification": candidates("architecture")}
        spec = {**BASE, "title": "S", "artifact_kind": "specification", "slug": "plain", "artifact_subtypes": [],
                "classification": candidates("specification")}
        code, report = self.run_cli("add", {"artifacts": [arch, spec]})
        self.assertEqual(code, 0, report)
        nodes = {node["graph_node_id"]: node for node in self.graph_state()["nodes"]}
        self.assertEqual((nodes["arch-all"]["artifact_subtypes"], nodes["spec-plain"]["artifact_subtypes"]), (BGN.ARCH_SUBTYPES, []))
        blocks = [f"{subtype.capitalize()} architecture" for subtype in BGN.ARCH_SUBTYPES]
        self.assertEqual([title for level, title in self.headings("architecture/all.md") if level == 3 and title in blocks], blocks)
        spec_titles = [title for _, title in self.headings("specs/plain.md")]
        self.assertFalse([title for title in spec_titles if title.startswith("API: ")], spec_titles)
        self.assertNotIn("api-contract", nodes["spec-plain"]["implementation_readiness"]["missing_sections"])
        self.assertEqual(self.validate().returncode, 0)

    def test_update_of_a_node_missing_required_keys_names_the_keys(self) -> None:
        self.add_five()
        graph = self.graph_state()
        node = next(item for item in graph["nodes"] if item["graph_node_id"] == "doc-runbook")
        del node["tags"], node["resource_scope"]
        self.graph.write_text(json.dumps(graph), encoding="utf-8")
        before = (self.graph.read_bytes(), (self.root / "docs" / "runbook.md").read_bytes())
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "doc-runbook", "set_sections": {"要約": "更新。"}}]})
        self.assertEqual((code, report["status"], report["code"], report["write_count"]), (1, "rejected", "node_missing_required_keys", 0))
        self.assertEqual({(item["node"], item["code"], item["detail"]) for item in report["findings"]},
                         {("doc-runbook", "missing_required_key", "tags"), ("doc-runbook", "missing_required_key", "resource_scope")})
        self.assertIn("tags", report["error"])
        self.assertEqual((self.graph.read_bytes(), (self.root / "docs" / "runbook.md").read_bytes()), before)

    def test_validator_reports_graph_validation_apart_from_node_readiness(self) -> None:
        self.add_five()
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["graph_validation"], {"status": "pass", "violation_count": 0})
        # 互換キーは graph 全体の結果のまま残す。node 単位の未完了は node_readiness に出る。
        self.assertEqual((report["valid"], report["implementation_readiness"]), (True, "complete"))
        readiness = report["node_readiness"]
        self.assertEqual(sum(readiness[key] for key in ("complete", "incomplete", "not_applicable", "unknown")), 5)
        incomplete = {item["graph_node_id"]: item for item in readiness["incomplete_nodes"]}
        self.assertIn("task-fix-timeout", incomplete)
        self.assertNotIn("issue-login-timeout", incomplete)
        self.assertEqual(incomplete["task-fix-timeout"]["status"], "incomplete")
        self.assertTrue(incomplete["task-fix-timeout"]["missing_sections"])
        self.assertEqual(readiness["incomplete"], len(incomplete))

    def test_feature_projection_is_filled_and_restored_from_macro(self) -> None:
        self.add_five()
        entry = self.feature_entry("pay")
        entry["macro"] = {**entry["macro"], "purpose": "<TBD>", "acceptance": ["<受入条件>"]}
        code, report = self.run_cli("add", {"artifacts": [entry]})
        self.assertEqual(code, 0, report)
        self.assertEqual(report["artifacts"][0]["readiness_fill"], [{"item": "目的", "via": "macro_patch", "key": "purpose"},
                                                                    {"item": "受入", "via": "macro_patch", "key": "acceptance"}])
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "feature-pay", "append_sections": {"受入": "- [ ] x"}}]})
        self.assertEqual((code, report["code"]), (1, "macro_section_is_projection"))
        # A hand-edited body and a removed heading are put back from frontmatter even when those fields do not move.
        path = self.root / "features" / "pay.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("## 受入\n\n- [ ] <受入条件>\n\n", text)
        path.write_text(text.replace("<TBD>", "手で書いた目的").replace("## 受入\n\n- [ ] <受入条件>\n\n", ""), encoding="utf-8")
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "feature-pay", "macro_patch": {"goal": "1 画面で決済が完了する。"}}]})
        self.assertEqual(code, 0, report)
        self.assertEqual(report["artifacts"][0]["sections_regenerated"], ["目的", "到達状態", "受入"])
        self.assertEqual([title for _, title in self.headings("features/pay.md")], CONTRACT["artifacts"]["feature"]["required_sections"])
        self.assertNotIn("手で書いた目的", path.read_text(encoding="utf-8"))
        self.assertEqual([item["item"] for item in report["artifacts"][0]["readiness_fill"]], ["目的", "受入"])
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "feature-pay", "macro_patch": {
            "purpose": "購入者が 1 画面で決済を終えられるようにする。", "acceptance": ["決済が 1 画面で完了する"]}}]})
        self.assertEqual((code, report["artifacts"][0]["readiness_fill"]), (0, []), report)
        node = next(item for item in self.graph_state()["nodes"] if item["graph_node_id"] == "feature-pay")
        self.assertEqual(node["implementation_readiness"]["status"], "complete")
        self.assertEqual(self.validate().returncode, 0)

    def test_apply_requires_expected_graph_revision(self) -> None:
        entry = {**BASE, "title": "I", "artifact_kind": "issue", "slug": "cas", "classification": candidates("issue")}
        code, report = self.run_cli("add", {"artifacts": [entry]}, pin=False)
        self.assertEqual((code, report["code"], report["write_count"]), (1, "missing_expected_graph_revision", 0))
        for value in (True, "0", 0.0):
            code, report = self.run_cli("add", {"expected_graph_revision": value, "artifacts": [entry]})
            self.assertEqual((code, report["code"]), (1, "invalid_input"), repr(value))
        code, report = self.run_cli("add", {"artifacts": [entry]}, "--dry-run", pin=False)
        self.assertEqual((code, report["status"], report["write_count"]), (0, "preview", 0))
        self.assertEqual(self.graph_state()["graph_revision"], 0)

    def test_c14_declared_architecture_needs_a_citing_feature_in_the_same_batch(self) -> None:
        declared = {"reason": "C14 macro contract names this architecture", "decision": "c14_macro_contract"}
        core = {**BASE, "title": "Core", "artifact_kind": "architecture", "slug": "core", "artifact_subtypes": ["backend"],
                "classification": declared}
        feature = self.feature_entry("pay")
        feature["macro"] = {**feature["macro"], "architecture_refs": ["arch-core"]}
        rejected = [
            ([core], "invalid_classification"),
            ([{**core, "classification": {**declared, "candidates": [{"artifact_kind": "architecture", "confidence": 1.0}]}}, feature],
             "invalid_classification"),
            ([{**BASE, "title": "I", "artifact_kind": "issue", "slug": "core-issue", "classification": declared}, feature],
             "invalid_classification"),
        ]
        for artifacts, expected in rejected:
            code, report = self.run_cli("add", {"artifacts": artifacts})
            self.assertEqual((code, report["code"], report["write_count"]), (1, expected, 0), artifacts[0]["slug"])
        self.assertEqual(self.graph_state()["nodes"], [])
        code, report = self.run_cli("add", {"artifacts": [core, feature]})
        self.assertEqual(code, 0, report)
        self.assertEqual([item["classification"]["decision"] for item in report["artifacts"]], ["c14_macro_contract"] * 2)
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # 既存 feature へ後から architecture を足す 2 段手順: candidates で分類して add し、macro_patch で参照を足す。
        late = {**BASE, "title": "Late", "artifact_kind": "architecture", "slug": "late", "artifact_subtypes": ["data"],
                "classification": candidates("architecture")}
        self.assertEqual(self.run_cli("add", {"artifacts": [late]})[0], 0)
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "feature-pay",
                                                            "macro_patch": {"architecture_refs": ["arch-core", "arch-late"]}}]})
        self.assertEqual(code, 0, report)
        node = next(item for item in self.graph_state()["nodes"] if item["graph_node_id"] == "feature-pay")
        self.assertEqual(node["architecture_refs"], ["arch-core", "arch-late"])
        self.assertEqual(self.validate().returncode, 0)

    def test_frontmatter_objects_serialize_independent_of_key_order(self) -> None:
        self.add_five()
        keys = list(CONTRACT["common_frontmatter"]["required"])
        for node in self.graph_state()["nodes"]:
            shuffled = {key: dict(reversed(list(value.items()))) if isinstance(value, dict) else value
                        for key, value in reversed(list(node.items()))}
            self.assertEqual(BGN._frontmatter(shuffled, keys), BGN._frontmatter(node, keys), node["graph_node_id"])

    def test_specification_api_subtype_follows_contracts_on_add(self) -> None:
        entry = {**BASE, "title": "S", "artifact_kind": "specification", "slug": "auto-api", "classification": candidates("specification"),
                 "api_contracts": [{"operation": "GET /a"}]}
        code, report = self.run_cli("add", {"artifacts": [entry]})
        self.assertEqual(code, 0, report)
        self.assertEqual(self.graph_state()["nodes"][0]["artifact_subtypes"], ["api"])
        bare = {**entry, "slug": "no-api", "artifact_subtypes": ["api"], "api_contracts": []}
        self.assertEqual(self.run_cli("add", {"artifacts": [bare]})[1]["code"], "invalid_subtypes")
        twice = {**entry, "slug": "twice", "api_contracts": [{"operation": "GET /a"}, {"operation": "GET /a"}]}
        self.assertEqual(self.run_cli("add", {"artifacts": [twice]})[1]["code"], "duplicate_section")

    # ------------------------------------------------------------ classification thresholds

    def test_auto_classification_threshold_boundaries(self) -> None:
        cases = [((0.80, 0.65), 0), ((0.79, 0.10), 1), ((0.90, 0.751), 1)]
        for index, ((confidence, runner_up), expected) in enumerate(cases):
            entry = {**BASE, "title": "I", "artifact_kind": "issue", "slug": f"edge-{index}",
                     "classification": candidates("issue", confidence=confidence, runner_up=runner_up)}
            code, report = self.run_cli("add", {"artifacts": [entry]})
            self.assertEqual(code, expected, (confidence, runner_up, report))
            if expected:
                self.assertEqual(report["code"], "classification_requires_user_confirmation")

    # ------------------------------------------------------------ section addressing

    def test_ambiguous_and_overlapping_section_keys_are_rejected(self) -> None:
        self.add_five()
        self.assertEqual(self.run_cli("update", {"updates": [{"graph_node_id": "spec-session-api",
                                                              "add_api_contracts": [{"operation": "DELETE /sessions"}]}]})[0], 0)
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "spec-session-api", "set_sections": {"Request": "r"}}]})
        self.assertEqual((code, report["code"]), (1, "section_ambiguous"))
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "spec-session-api", "set_sections": {
            "API: POST /sessions > Request": "r1", "API契約 > API: POST /sessions > Request": "r2"}}]})
        self.assertEqual((code, report["code"]), (1, "overlapping_edits"))
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "spec-session-api", "set_sections": {
            "API: DELETE /sessions > Request": "session id を path で受け取る。"}}]})
        self.assertEqual(code, 0, report)

    # ------------------------------------------------------------ validation baseline and evaluation status

    def test_pre_write_validation_reports_findings_of_changed_nodes_only(self) -> None:
        self.add_five()
        graph = self.graph_state()
        next(node for node in graph["nodes"] if node["graph_node_id"] == "doc-runbook")["depends_on"] = ["missing-node"]
        self.graph.write_text(json.dumps(graph), encoding="utf-8")
        entry = {**BASE, "title": "I", "artifact_kind": "issue", "slug": "unrelated", "classification": candidates("issue")}
        code, report = self.run_cli("add", {"artifacts": [entry]})
        self.assertEqual(code, 0, report)
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "issue-unrelated", "node_patch": {"depends_on": ["ghost"]}}]})
        self.assertEqual((code, report["code"]), (1, "pre_write_validation_failed"))
        self.assertTrue(report["findings"])
        self.assertTrue(all(item["node"] == "issue-unrelated" for item in report["findings"]), report["findings"])

    def mark_passed(self, graph_node_id: str) -> None:
        graph = self.graph_state()
        node = next(item for item in graph["nodes"] if item["graph_node_id"] == graph_node_id)
        node.update({"confirmation_status": "confirmed", "evaluation_status": "pass",
                     "confirmation_evidence": {"evaluator": "reviewer", "evidence_ref": "eval-log/x.json", "evaluated_digest": "a" * 64}})
        self.graph.write_text(json.dumps(graph), encoding="utf-8")
        path = self.root / node["file_path"]
        _, body = BGN._split_frontmatter(path.read_text(encoding="utf-8"), node["file_path"])
        path.write_text(BGN._frontmatter(node, list(CONTRACT["common_frontmatter"]["required"])) + "".join(body), encoding="utf-8")

    def test_content_patch_makes_passed_evaluation_stale_but_status_patch_does_not(self) -> None:
        self.add_five()
        self.mark_passed("issue-login-timeout")
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "issue-login-timeout", "node_patch": {"status": "active"}}]})
        self.assertEqual(code, 0, report)
        node = next(item for item in self.graph_state()["nodes"] if item["graph_node_id"] == "issue-login-timeout")
        self.assertEqual((node["status"], node["evaluation_status"]), ("active", "pass"))
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "issue-login-timeout",
                                                            "node_patch": {"status": "blocked", "title": "Login timeout v2"}}]})
        self.assertEqual(code, 0, report)
        node = next(item for item in self.graph_state()["nodes"] if item["graph_node_id"] == "issue-login-timeout")
        self.assertEqual(node["evaluation_status"], "stale")

    def test_unmanaged_frontmatter_keys_survive_update(self) -> None:
        self.add_five()
        path = self.root / "docs" / "runbook.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("---\n", "---\nreviewer_note: \"keep me\"\n", 1), encoding="utf-8")
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "doc-runbook", "set_sections": {"要約": "手順の要約。"}}]})
        self.assertEqual(code, 0, report)
        self.assertEqual(report["artifacts"][0]["unmanaged_frontmatter_kept"], ["reviewer_note"])
        self.assertIn('reviewer_note: "keep me"\n', path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------ paths, lock, receipt, rollback

    def test_relative_input_resolves_against_repo_root_not_cwd(self) -> None:
        entry = {**BASE, "title": "I", "artifact_kind": "issue", "slug": "relative", "classification": candidates("issue")}
        absolute = self.write_input(self.pinned({"artifacts": [entry]}))
        relative = absolute.relative_to(self.root).as_posix()
        with tempfile.TemporaryDirectory() as elsewhere:
            cp = subprocess.run([sys.executable, str(SCRIPT), "add", "--repo-root", str(self.root), "--input", relative],
                                text=True, capture_output=True, env=self.env, cwd=elsewhere, check=False)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

    def test_concurrent_writer_is_refused(self) -> None:
        import fcntl
        entry = {**BASE, "title": "I", "artifact_kind": "issue", "slug": "busy", "classification": candidates("issue")}
        with (self.graph.with_name(f".{self.graph.name}.register.lock")).open("a+") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, report = self.run_cli("add", {"artifacts": [entry]})
        self.assertEqual((code, report["code"], report["write_count"]), (1, "writer_busy", 0))
        self.assertFalse((self.root / "issues" / "busy.md").exists())

    def test_existing_receipt_rolls_back_the_whole_write(self) -> None:
        before = self.graph.read_bytes()
        receipts = self.graph.parent / "receipts"
        receipts.mkdir()
        (receipts / "node-r000001-add.json").write_text("{}", encoding="utf-8")
        entry = {**BASE, "title": "I", "artifact_kind": "issue", "slug": "receipt", "classification": candidates("issue")}
        code, report = self.run_cli("add", {"artifacts": [entry]})
        self.assertEqual((code, report["code"]), (1, "immutable_receipt_exists"))
        self.assertEqual(self.graph.read_bytes(), before)
        self.assertFalse((self.root / "issues" / "receipt.md").exists())

    def test_artifact_changed_during_write_is_detected(self) -> None:
        self.add_five()
        path = self.root / "docs" / "runbook.md"
        real = BGN._findings

        def concurrent_edit(*args: object, **kwargs: object) -> list:
            path.write_text(path.read_text(encoding="utf-8") + "\n外部編集\n", encoding="utf-8")
            return real(*args, **kwargs)

        with mock.patch.object(BGN, "_findings", side_effect=concurrent_edit):
            code, report = self.run_in_process("update", {"updates": [{"graph_node_id": "doc-runbook",
                                                                       "set_sections": {"要約": "更新。"}}]})
        self.assertEqual((code, report["code"]), (1, "artifact_changed_during_write"))
        self.assertTrue(path.read_text(encoding="utf-8").endswith("外部編集\n"))
        self.assertEqual(self.graph_state()["graph_revision"], 1)

    def test_failed_restore_is_reported_as_rollback_incomplete(self) -> None:
        entry = {**BASE, "title": "I", "artifact_kind": "issue", "slug": "stuck", "classification": candidates("issue")}
        with mock.patch.object(BGN, "_create_receipt", side_effect=OSError("disk full")), \
                mock.patch.object(Path, "unlink", side_effect=OSError("read-only")):
            code, report = self.run_in_process("add", {"artifacts": [entry]})
        self.assertEqual((code, report["status"], report["code"]), (2, "error", "rollback_incomplete"))
        self.assertEqual([item["node"] for item in report["findings"]], ["issues/stuck.md"])
        self.assertEqual(report["findings"][0]["detail"], "remove created file: read-only")
        self.assertIsNone(report["write_count"])
        self.assertEqual(self.graph_state()["graph_revision"], 0)


if __name__ == "__main__":
    unittest.main()
