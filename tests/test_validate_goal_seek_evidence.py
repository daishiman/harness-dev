"""verify-goal-seek-evidence: goal_seek 実行契約の履行証跡検査のテスト。

背景: live-trial の trial は skill をロードしながらゴールシーク配線を飛ばし、下位 script を
直叩きして成果物だけ出せる。HarnessHub-s7b の初回再 trial では 2 件とも該当した。
成果物 (out/status.json) だけを見る検査では正常な実走と区別できないため、契約履行の証跡を
直接検査する必要がある。SKILL.md の「ゴールシーク検証」ブロックと同じ判定をここで固定する。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-live-trial"
          / "scripts" / "validate-goal-seek-evidence.py")
SPEC = importlib.util.spec_from_file_location("validate_goal_seek_evidence", SCRIPT)
assert SPEC and SPEC.loader
VG = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VG
SPEC.loader.exec_module(VG)

GOAL = "fixture repo の canonical graph を read-only で集計して status summary を出す"
GOAL_HASH = hashlib.sha256(GOAL.encode("utf-8")).hexdigest()
SKILL = "run-demo"


def row(**overrides) -> dict:
    base = {
        "original_goal": GOAL,
        "original_goal_hash": GOAL_HASH,
        "current_goal_snapshot": GOAL,
        "delta_from_original": "none",
        "merged_directive_for_next": "continue",
        "drift_signal": "none",
    }
    base.update(overrides)
    return base


class GoalSeekEvidenceTest(unittest.TestCase):
    def _build(self, tmp: Path, *, declared=True, goal_spec=True, progress=True,
               intermediate: list[dict] | None = ...):
        skill_dir = tmp / "skills" / SKILL
        skill_dir.mkdir(parents=True)
        fm = "---\nname: run-demo\n"
        if declared:
            fm += "goal_seek:\n  engine: inline\n  fork: subagent\n  max_loops: 5\n"
        (skill_dir / "SKILL.md").write_text(fm + "---\nbody\n", encoding="utf-8")

        eval_root = tmp / "eval-log"
        eval_root.mkdir()
        if goal_spec:
            (eval_root / f"{SKILL}-goal-spec.json").write_text(
                json.dumps({"original_goal": GOAL}, ensure_ascii=False), encoding="utf-8")
        if progress:
            (eval_root / f"{SKILL}-progress.json").write_text(
                json.dumps({"checklist": []}, ensure_ascii=False), encoding="utf-8")
        if intermediate is not ...:
            lines = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in (intermediate or []))
            (eval_root / f"{SKILL}-intermediate.jsonl").write_text(lines, encoding="utf-8")
        return skill_dir, eval_root

    def _verify(self, **kw):
        with tempfile.TemporaryDirectory() as td:
            skill_dir, eval_root = self._build(Path(td), **kw)
            return VG.verify(skill_dir, eval_root)

    def test_full_compliance_passes(self):
        result = self._verify(intermediate=[row()])
        self.assertTrue(result["valid"], result["violations"])
        self.assertEqual(result["checked"]["intermediate_rows"], 1)

    def test_missing_all_artifacts_is_rejected(self):
        """s7b の r5 が実際に該当した形: skill をロードしたが配線を一切実行していない。"""
        result = self._verify(goal_spec=False, progress=False, intermediate=...)
        self.assertFalse(result["valid"])
        codes = " ".join(result["violations"])
        for label in ("goal-spec-missing", "progress-missing", "intermediate-missing"):
            self.assertIn(label, codes)

    def test_skill_without_goal_seek_is_skipped(self):
        """goal_seek を宣言しない skill には契約が存在しないので対象外。"""
        result = self._verify(declared=False, goal_spec=False, progress=False, intermediate=...)
        self.assertTrue(result["valid"])
        self.assertFalse(result["goal_seek_declared"])
        self.assertIn("skipped", result["checked"])

    def test_empty_intermediate_is_rejected(self):
        """ファイルは置いたが中身が無い = 周回記録なし。"""
        result = self._verify(intermediate=[])
        self.assertFalse(result["valid"])
        self.assertTrue(any("intermediate-empty" in v for v in result["violations"]))

    def test_missing_required_keys_is_rejected(self):
        bad = row()
        del bad["drift_signal"]
        result = self._verify(intermediate=[bad])
        self.assertFalse(result["valid"])
        self.assertTrue(any("intermediate-keys" in v for v in result["violations"]))

    def test_goal_drift_is_rejected(self):
        """周回中にゴールがすり替わるのを検出する。"""
        result = self._verify(intermediate=[row(original_goal="別のゴール")])
        self.assertFalse(result["valid"])
        self.assertTrue(any("goal-drift" in v for v in result["violations"]))

    def test_hash_mismatch_is_rejected(self):
        """hash だけ書き換えて整合を装う経路を塞ぐ。"""
        result = self._verify(intermediate=[row(original_goal_hash="0" * 64)])
        self.assertFalse(result["valid"])
        self.assertTrue(any("goal-hash-mismatch" in v for v in result["violations"]))

    def test_empty_goal_spec_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            skill_dir, eval_root = self._build(tmp, intermediate=[row()])
            (eval_root / f"{SKILL}-goal-spec.json").write_text(
                json.dumps({"original_goal": "   "}), encoding="utf-8")
            result = VG.verify(skill_dir, eval_root)
        self.assertFalse(result["valid"])
        self.assertTrue(any("goal-spec-empty" in v for v in result["violations"]))

    def test_multi_row_all_checked(self):
        """複数周回のうち 1 行だけ壊れていても検出する。"""
        result = self._verify(intermediate=[row(), row(original_goal_hash="1" * 64), row()])
        self.assertFalse(result["valid"])
        self.assertEqual(sum("goal-hash-mismatch" in v for v in result["violations"]), 1)


if __name__ == "__main__":
    unittest.main()
