from __future__ import annotations

import re
import unittest
from pathlib import Path

import test_runtime as fx


VALIDATOR = fx.VALIDATOR
PROMOTER = fx.PROMOTER
PLUGIN = fx.PLUGIN
REFERENCE = PLUGIN / "references" / "system-plan-phase-names.md"

# The reference table declares itself the SSOT (正本) for the generation-side
# 13 phase names. `validate-system-plan.py` / `promote-system-plan.py` restate
# those phases as independent Python constants (PHASES / TASK_PATHS) with no
# mechanism that reconciles them against the reference. These parity tests are
# that missing mechanism: they detect drift, they do not repair it. The
# reference file is the fixed expectation; a failure means a constant fell out
# of sync with the SSOT and must be brought back to it.

EXPECTED_PHASE_REFS = [f"P{i:02d}" for i in range(1, 14)]

# A data row looks like: `| P01 | requirements | requirements baseline | required |`
# The first cell is the phase_ref (P01..P13), the second is the phase id
# (確定呼称). Header (`| phase_ref | ... |`) and separator (`|---|...|`) rows do
# not start with a P## cell and are skipped.
_ROW = re.compile(r"^\|\s*(P\d{2})\s*\|\s*([^|]+?)\s*\|")


def parse_reference_rows() -> list[tuple[str, str]]:
    """Deterministically extract (phase_ref, phase_id) pairs from the SSOT table."""
    rows: list[tuple[str, str]] = []
    for line in REFERENCE.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line.strip())
        if match:
            rows.append((match.group(1), match.group(2)))
    return rows


def drift_message(label: str, actual: list[str], expected: list[str]) -> str:
    """Point at exactly which phase index drifted between a constant and the SSOT."""
    diffs = []
    for index in range(max(len(actual), len(expected))):
        got = actual[index] if index < len(actual) else "<missing>"
        want = expected[index] if index < len(expected) else "<missing>"
        if got != want:
            diffs.append(f"  index {index}: {label}={got!r} reference={want!r}")
    return (
        f"{label} drifted from reference SSOT ({REFERENCE.name}); "
        f"reference is authoritative:\n" + "\n".join(diffs)
    )


class PhaseNameParityTests(unittest.TestCase):
    def test_reference_declares_exact_13_ordered_unique_phases(self):
        rows = parse_reference_rows()
        refs = [ref for ref, _ in rows]
        names = [name for _, name in rows]
        self.assertEqual(
            len(rows), 13,
            f"SSOT must declare exactly 13 phases, got {len(rows)}: {refs}",
        )
        self.assertEqual(
            refs, EXPECTED_PHASE_REFS,
            f"SSOT phase_ref column must be ordered P01..P13, got {refs}",
        )
        self.assertEqual(
            len(set(names)), 13,
            f"SSOT phase names must be unique, got {names}",
        )

    def test_validator_phases_match_reference(self):
        refs = [ref for ref, _ in parse_reference_rows()]
        self.assertEqual(
            list(VALIDATOR.PHASES), refs,
            drift_message("validate-system-plan.py PHASES", list(VALIDATOR.PHASES), refs),
        )

    def test_promoter_phases_match_reference(self):
        refs = [ref for ref, _ in parse_reference_rows()]
        self.assertEqual(
            list(PROMOTER.PHASES), refs,
            drift_message("promote-system-plan.py PHASES", list(PROMOTER.PHASES), refs),
        )

    def test_validator_task_paths_encode_reference_phase_names(self):
        # TASK_PATHS is where the human-readable phase names actually live in the
        # constants (PHASES only carries the P## refs). A rename of any phase id
        # in the SSOT must be mirrored here or this fails.
        rows = parse_reference_rows()
        expected = [
            f"task-specs/phase-{ref[1:]}-{name}.md" for ref, name in rows
        ]
        self.assertEqual(
            list(VALIDATOR.TASK_PATHS), expected,
            drift_message(
                "validate-system-plan.py TASK_PATHS", list(VALIDATOR.TASK_PATHS), expected
            ),
        )

    def test_validator_and_promoter_phases_are_consistent(self):
        # Both scripts hardcode PHASES independently; they must agree with each
        # other as well as with the SSOT.
        self.assertEqual(
            list(VALIDATOR.PHASES), list(PROMOTER.PHASES),
            drift_message(
                "promote-system-plan.py PHASES",
                list(PROMOTER.PHASES),
                list(VALIDATOR.PHASES),
            ),
        )


if __name__ == "__main__":
    unittest.main()
