from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


VALIDATOR = load_module("test_sdp_validator_qa", "validate-system-plan.py")


class QaSemanticCoverageTest(unittest.TestCase):
    """qa_semantic_violations: tag/lineage 一致だけの PASS (HarnessHub-p73) を遮断する 3 軸検査。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.staging = Path(self._tmp.name) / "staging"
        (self.repo / "features").mkdir(parents=True)
        (self.staging / "task-specs").mkdir(parents=True)
        self.parent = "feat-demo"

    def tearDown(self):
        self._tmp.cleanup()

    def _feature(self, tags):
        body = "---\n" + f"tags: {json.dumps(tags)}\n" + "---\n\n# demo\n"
        (self.repo / "features" / f"{self.parent}.md").write_text(body, encoding="utf-8")

    def _spec_state(self, qa_ids, answers=None):
        answers = answers or {}
        path = self.repo / "system-spec" / "spec-state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"qa_log": [
                {"id": q, "question": "q", "answer": answers.get(q, "a")}
                for q in qa_ids
            ]},
            ensure_ascii=False), encoding="utf-8")

    def _goal_spec(self, text, semantic_qa=None):
        constraints = []
        if semantic_qa:
            constraints.append({
                "id": VALIDATOR.SEMANTIC_COVERAGE_CONSTRAINT_ID,
                "summary": f"{semantic_qa} の意味内容を検証する",
            })
        (self.staging / "goal-spec.json").write_text(json.dumps(
            {
                "purpose": text,
                "goal": "",
                "scope_in": [],
                "scope_out": [],
                "acceptance": [],
                "quality_constraints": constraints,
            },
            ensure_ascii=False), encoding="utf-8")

    def _task_spec(self, text, index=0):
        (self.staging / VALIDATOR.TASK_PATHS[index]).write_text(text, encoding="utf-8")

    def _all_task_specs(self, text):
        for index in range(len(VALIDATOR.TASK_PATHS)):
            self._task_spec(text, index)

    def _codes(self):
        return [c for c, _p, _d in VALIDATOR.qa_semantic_violations(
            self.staging, self.repo, self.parent)]

    def test_missing_feature_md_is_out_of_scope(self):
        self.assertEqual(self._codes(), [])

    def test_feature_without_qa_tags_is_vacuous(self):
        self._feature(["macro-feature", "governance"])
        self.assertEqual(self._codes(), [])

    def test_unregistered_qa_tag_fails_closed(self):
        self._feature(["qa-071"])
        self._spec_state(["qa-067"])
        self._goal_spec("qa-071 を伝播する")
        self._task_spec("qa-071")
        self.assertIn("qa-ref-unregistered", self._codes())

    def test_registered_but_goal_spec_silent_fails(self):
        self._feature(["qa-071"])
        self._spec_state(["qa-067", "qa-071"])
        self._goal_spec("qa-067 の運用改善のみ")
        self._task_spec("qa-071 trace あり")
        codes = self._codes()
        self.assertIn("qa-semantic-coverage", codes)
        self.assertNotIn("qa-ref-unregistered", codes)

    def test_registered_and_covered_but_tasks_silent_fails(self):
        self._feature(["qa-071"])
        self._spec_state(["qa-071"])
        self._goal_spec("qa-071 の方法論要件を実装する")
        self._all_task_specs("qa 言及なしの task 本文")
        self.assertEqual(self._codes(), ["qa-task-trace"])

    def test_fully_covered_passes(self):
        self._feature(["qa-067", "qa-071"])
        self._spec_state(["qa-067", "qa-071"])
        self._goal_spec("qa-067 と qa-071 の要件を保持する")
        self._all_task_specs("参照情報: qa-067 / qa-071")
        self.assertEqual(self._codes(), [])

    def test_declared_tags_without_goal_spec_fail(self):
        self._feature(["qa-071"])
        self._spec_state(["qa-071"])
        self._all_task_specs("qa-071")
        self.assertIn("qa-semantic-coverage", self._codes())

    def test_goal_spec_dangling_qa_reference_fails(self):
        self._feature(["qa-071"])
        self._spec_state(["qa-071"])
        self._goal_spec("qa-071 と qa-099 に基づく")
        self._all_task_specs("qa-071")
        codes = self._codes()
        self.assertIn("qa-ref-unregistered", codes)

    def test_partial_exact13_trace_fails(self):
        self._feature(["qa-071"])
        self._spec_state(["qa-071"])
        self._goal_spec("qa-071 を伝播する")
        self._task_spec("qa-071")
        self.assertIn("qa-task-trace", self._codes())

    def test_semantic_marker_missing_from_goal_spec_fails(self):
        answer = "【1. 外側ループ (outer loop)】x\n【2. 内側ループ (inner loop)】y"
        self._feature(["qa-071"])
        self._spec_state(["qa-071"], {"qa-071": answer})
        self._goal_spec("qa-071 外側ループ", semantic_qa="qa-071")
        self._all_task_specs("qa-071 外側ループ 内側ループ")
        self.assertIn("qa-semantic-coverage", self._codes())

    def test_semantic_marker_missing_from_one_task_fails(self):
        answer = "【1. 外側ループ (outer loop)】x\n【2. 内側ループ (inner loop)】y"
        self._feature(["qa-071"])
        self._spec_state(["qa-071"], {"qa-071": answer})
        self._goal_spec("qa-071 外側ループ 内側ループ", semantic_qa="qa-071")
        self._all_task_specs("qa-071 外側ループ 内側ループ")
        self._task_spec("qa-071 外側ループ", index=12)
        self.assertIn("qa-task-trace", self._codes())

    def test_semantic_markers_cover_goal_and_all_tasks(self):
        answer = "【1. 外側ループ (outer loop)】x\n【2. 内側ループ (inner loop)】y"
        self._feature(["qa-071"])
        self._spec_state(["qa-071"], {"qa-071": answer})
        self._goal_spec("qa-071 外側ループ 内側ループ", semantic_qa="qa-071")
        self._all_task_specs("qa-071 外側ループ 内側ループ")
        self.assertEqual(self._codes(), [])

    def test_spec_state_root_must_be_object(self):
        self._feature(["qa-071"])
        path = self.repo / "system-spec" / "spec-state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]", encoding="utf-8")
        self._goal_spec("qa-071")
        self._all_task_specs("qa-071")
        self.assertIn("qa-ref-unregistered", self._codes())

    def test_spec_state_qa_log_must_be_array(self):
        self._feature(["qa-071"])
        path = self.repo / "system-spec" / "spec-state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"qa_log": {}}', encoding="utf-8")
        self._goal_spec("qa-071")
        self._all_task_specs("qa-071")
        self.assertIn("qa-ref-unregistered", self._codes())

    def test_semantic_constraint_without_explicit_qa_applies_to_declared_tags(self):
        answer = "【1. 外側ループ (outer loop)】x"
        self._feature(["qa-071"])
        self._spec_state(["qa-071"], {"qa-071": answer})
        self._goal_spec("qa-071", semantic_qa=None)
        goal_path = self.staging / "goal-spec.json"
        goal = json.loads(goal_path.read_text(encoding="utf-8"))
        goal["quality_constraints"] = [{
            "id": VALIDATOR.SEMANTIC_COVERAGE_CONSTRAINT_ID,
            "summary": "tag だけでなく意味を検証する",
        }]
        goal_path.write_text(json.dumps(goal, ensure_ascii=False), encoding="utf-8")
        self._all_task_specs("qa-071 外側ループ")
        self.assertIn("qa-semantic-coverage", self._codes())

    def test_body_tags_line_does_not_act_as_frontmatter(self):
        path = self.repo / "features" / f"{self.parent}.md"
        path.write_text("# demo\n\ntags: [\"qa-071\"]\n", encoding="utf-8")
        self.assertEqual(self._codes(), [])


if __name__ == "__main__":
    unittest.main()
