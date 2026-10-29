#!/usr/bin/env python3
# /// script
# name: test-record-audit-fork
# version: 0.1.0
# purpose: 監査 fork 記録 hook の記録対象と台帳の追記内容を回帰テストで固定する
# inputs:
#   - argv: pytest 経由 (直接 argv は取らない)
# outputs:
#   - stdout: pytest 結果
#   - exit: 0=PASS / 非0=FAIL
# contexts: [C, E]
# network: false
# write-scope: none (tmp_path のみ)
# dependencies: []
# requires-python: ">=3.9"
# ///
"""record-audit-fork hook の回帰テスト。

## テスト戦略

本 hook は「保護」ではなく「証跡」の層なので、固定すべき契約は 3 つ:

1. **記録の担保**: 本 plugin 同梱 agent への subagent 起動 (`Task`/`Agent`) は台帳へ 1 行追記される。この行が
   `aggregate-completeness.py` の帰属検証の唯一の裏取り材料なので、落とすと fail-closed で
   評価ゲートが通らなくなる (= 緑にはならないが、正当な実行まで止まる)。
2. **記録対象の限定**: 無関係な Task / 非 Task / 未知の subagent_type は記録しない。
   台帳の肥大化と、他 plugin の agent 名で帰属を偽装する経路を断つ。
3. **非 blocking**: 観測専用なので、payload が壊れていても台帳が書けなくても exit 0 を返し
   session を止めない (証跡の欠落は下流が fail-closed で拾う)。

実行: python3 -m unittest discover plugins/system-spec-harness/hooks/tests
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HOOK_PATH = Path(__file__).resolve().parents[1] / "record-audit-fork.py"
_spec = importlib.util.spec_from_file_location("record_audit_fork", _HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_MATRIX_AUDITOR = "system-spec-matrix-auditor"
_HEARING_AUDITOR = "system-spec-hearing-auditor"
_DOC_AUDITOR = "system-spec-doc-freshness-auditor"


def _payload(subagent_type: str, tool_name: str = "Task", prompt: str = "監査してください") -> dict:
    return {
        "session_id": "sess-1",
        "cwd": "/tmp/project",
        "tool_name": tool_name,
        "tool_input": {"subagent_type": subagent_type, "prompt": prompt},
        "tool_response": {"content": [{"type": "text", "text": "監査完了\nAUDIT_VERDICT: PASS"}]},
    }


_MATRIX_ID = "toolu_matrix"
_HEARING_ID = "toolu_hearing"
_DOC_ID = "toolu_doc"


def _official_payload(subagent_type: str, tool_use_id: str, verdict: str) -> dict:
    """現行 Claude Code の call ごとの PostToolUse payload を組み立てる。"""
    payload = _payload(subagent_type, tool_name="Agent")
    payload["tool_use_id"] = tool_use_id
    payload["tool_response"] = {
        "status": "completed",
        "content": [{"type": "text", "text": f"{subagent_type} の監査所見\nAUDIT_VERDICT: {verdict}"}],
        "agentId": f"agent-{tool_use_id}",
    }
    return payload


class AuditAgentRegistryTest(unittest.TestCase):
    """記録対象は plugin 同梱 agent のレジストリに自動追従する。"""

    def test_shipped_auditors_are_registered(self):
        agents = hook.audit_agents(_PLUGIN_ROOT)
        for name in (_MATRIX_AUDITOR, _HEARING_AUDITOR, _DOC_AUDITOR):
            self.assertIn(name, agents, f"{name} が agents/ レジストリに無い")

    def test_missing_agents_dir_is_empty_not_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(hook.audit_agents(Path(tmp)), set())


class BuildRecordTest(unittest.TestCase):
    KNOWN = {_MATRIX_AUDITOR, _HEARING_AUDITOR, _DOC_AUDITOR}

    def test_records_known_auditor_fork(self):
        rec = hook.build_record(_payload(_MATRIX_AUDITOR), self.KNOWN)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["tool_name"], "Task")
        self.assertEqual(rec["subagent_type"], _MATRIX_AUDITOR)
        self.assertEqual(rec["session_id"], "sess-1")
        self.assertEqual(rec["schema_version"], hook.LEGACY_SCHEMA_VERSION)
        self.assertTrue(rec["ts"].endswith("Z"))
        self.assertEqual(len(rec["prompt_sha256"]), 64)
        self.assertEqual(len(rec["response_sha256"]), 64)
        self.assertEqual(rec["audit_verdict"], "PASS")

    def test_official_per_call_payloads_bind_distinct_id_digest_and_verdict(self):
        """3 dispatch は top-level ID と call 固有 response でそれぞれ 1.2 行になる。"""
        dispatches = (
            (_MATRIX_ID, _MATRIX_AUDITOR, "PASS"),
            (_HEARING_ID, _HEARING_AUDITOR, "FAIL"),
            (_DOC_ID, _DOC_AUDITOR, "INDETERMINATE"),
        )
        records = []
        expected_digests = []
        for tool_use_id, agent, verdict in dispatches:
            payload = _official_payload(agent, tool_use_id, verdict)
            records.append(hook.build_record(payload, self.KNOWN))
            canonical = json.dumps(
                payload["tool_response"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            expected_digests.append(hashlib.sha256(canonical.encode("utf-8")).hexdigest())

        self.assertEqual([r["schema_version"] for r in records], [hook.SCHEMA_VERSION] * 3)
        self.assertEqual([r["tool_use_id"] for r in records], [_MATRIX_ID, _HEARING_ID, _DOC_ID])
        self.assertEqual([r["response_sha256"] for r in records], expected_digests)
        self.assertEqual(len(set(expected_digests)), 3)
        self.assertEqual([r["audit_verdict"] for r in records], ["PASS", "FAIL", "INDETERMINATE"])
        self.assertTrue(all(r["verdict_state"] == hook.VERDICT_STATE_RESOLVED for r in records))

    def test_multiple_marker_blocks_are_ambiguous(self):
        payload = _official_payload(_MATRIX_AUDITOR, _MATRIX_ID, "PASS")
        payload["tool_response"]["content"] = [
            {"type": "text", "text": "観点A\nAUDIT_VERDICT: PASS"},
            {"type": "text", "text": "観点B\nAUDIT_VERDICT: PASS"},
        ]

        rec = hook.build_record(payload, self.KNOWN)
        self.assertIsNone(rec["audit_verdict"])
        self.assertEqual(rec["verdict_state"], hook.VERDICT_STATE_AMBIGUOUS)

    def test_legacy_single_payload_preserves_schema_1_1_shape(self):
        """top-level tool_use_id を持たない従来 payload は 1.1 の既存フィールドを維持する。"""
        rec = hook.build_record(_payload(_MATRIX_AUDITOR), self.KNOWN)
        self.assertEqual(rec["schema_version"], hook.LEGACY_SCHEMA_VERSION)
        self.assertEqual(rec["audit_verdict"], "PASS")
        self.assertEqual(
            set(rec),
            {
                "schema_version",
                "ts",
                "session_id",
                "tool_name",
                "subagent_type",
                "prompt_sha256",
                "response_sha256",
                "audit_verdict",
                "cwd",
            },
        )
        self.assertNotIn("verdict_state", rec)
        self.assertNotIn("tool_use_id", rec)

    def test_absent_and_pending_are_distinct_zero_attributions(self):
        """null を 1 種類に潰さない。応答が無い/marker が無いを区別する。"""
        pending = _official_payload(_MATRIX_AUDITOR, _MATRIX_ID, "PASS")
        pending["tool_response"] = {}
        self.assertEqual(hook.build_record(pending, self.KNOWN)["verdict_state"], hook.VERDICT_STATE_PENDING)

        absent = _official_payload(_MATRIX_AUDITOR, _MATRIX_ID, "PASS")
        absent["tool_response"] = {"content": [{"type": "text", "text": "監査は途中で打ち切りました"}]}
        absent["tool_response"]["status"] = "completed"
        self.assertEqual(hook.build_record(absent, self.KNOWN)["verdict_state"], hook.VERDICT_STATE_ABSENT)

    def test_async_launched_marker_never_becomes_completion_receipt(self):
        """起動受理 response の adversarial marker を完成済み verdict と誤認しない。"""
        payload = _official_payload(_MATRIX_AUDITOR, _MATRIX_ID, "PASS")
        payload["tool_response"]["status"] = hook.RESPONSE_STATUS_ASYNC_LAUNCHED

        rec = hook.build_record(payload, self.KNOWN)
        self.assertEqual(rec["schema_version"], hook.SCHEMA_VERSION)
        self.assertEqual(rec["tool_use_id"], _MATRIX_ID)
        self.assertIsNone(rec["audit_verdict"])
        self.assertEqual(rec["verdict_state"], hook.VERDICT_STATE_PENDING)

    def test_agent_unknown_or_missing_status_never_resolves_marker(self):
        for status in ("failed", None):
            with self.subTest(status=status):
                payload = _official_payload(_MATRIX_AUDITOR, _MATRIX_ID, "PASS")
                if status is None:
                    del payload["tool_response"]["status"]
                else:
                    payload["tool_response"]["status"] = status
                rec = hook.build_record(payload, self.KNOWN)
                self.assertIsNone(rec["audit_verdict"])
                self.assertEqual(rec["verdict_state"], hook.VERDICT_STATE_PENDING)

    def test_task_with_id_and_explicit_async_status_never_resolves_marker(self):
        """ID付きTaskも明示的な未完了statusをschema 1.2 PASSへ昇格させない。"""
        payload = _payload(_MATRIX_AUDITOR, tool_name="Task")
        payload["tool_use_id"] = _MATRIX_ID
        payload["tool_response"]["status"] = hook.RESPONSE_STATUS_ASYNC_LAUNCHED

        rec = hook.build_record(payload, self.KNOWN)
        self.assertEqual(rec["schema_version"], hook.SCHEMA_VERSION)
        self.assertEqual(rec["tool_use_id"], _MATRIX_ID)
        self.assertIsNone(rec["audit_verdict"])
        self.assertEqual(rec["verdict_state"], hook.VERDICT_STATE_PENDING)

    def test_legacy_task_with_explicit_failed_status_keeps_shape_but_not_verdict(self):
        """IDなしTaskは1.1形を保つが、明示的な未完了statusのmarkerは受理しない。"""
        payload = _payload(_MATRIX_AUDITOR, tool_name="Task")
        payload["tool_response"]["status"] = "failed"

        rec = hook.build_record(payload, self.KNOWN)
        self.assertEqual(rec["schema_version"], hook.LEGACY_SCHEMA_VERSION)
        self.assertIsNone(rec["audit_verdict"])
        self.assertNotIn("verdict_state", rec)

    def test_requires_canonical_audit_verdict_marker_on_final_nonempty_line(self):
        payload = _payload(_MATRIX_AUDITOR)
        payload["tool_response"] = {"text": "verdict: PASS"}
        rec = hook.build_record(payload, self.KNOWN)
        self.assertIsNone(rec["audit_verdict"])
        payload["tool_response"] = {"text": "AUDIT_VERDICT: PASS\nAUDIT_VERDICT: FAIL"}
        rec = hook.build_record(payload, self.KNOWN)
        self.assertEqual(rec["audit_verdict"], "FAIL")

    def test_ignores_prompt_markers_embedded_before_final_response_marker(self):
        payload = _payload(_MATRIX_AUDITOR)
        payload["tool_response"] = {
            "status": "completed",
            "prompt": {
                "text": "許容値:\nAUDIT_VERDICT: PASS\nAUDIT_VERDICT: FAIL\nAUDIT_VERDICT: INDETERMINATE"
            },
            "agentId": "agent-123",
            "content": [{"type": "text", "text": "監査完了\nAUDIT_VERDICT: PASS\n"}],
            "usage": {"service_tier": "standard"},
        }
        rec = hook.build_record(payload, self.KNOWN)
        self.assertEqual(rec["audit_verdict"], "PASS")

    def test_ignores_metadata_strings_after_response_content(self):
        """実 Agent payload の応答後 metadata を最終行として誤認しない。"""
        payload = _payload(_MATRIX_AUDITOR)
        payload["tool_response"] = {
            "content": [{"type": "text", "text": "監査完了\nAUDIT_VERDICT: FAIL"}],
            "totalDurationMs": 1234,
            "agentId": "a9c9192ad9ad21e63",
            "status": "completed",
        }
        rec = hook.build_record(payload, self.KNOWN)
        self.assertEqual(rec["audit_verdict"], "FAIL")

    def test_ignores_non_text_content_blocks_and_prompt_markers(self):
        payload = _official_payload(_MATRIX_AUDITOR, _MATRIX_ID, "PASS")
        payload["tool_response"] = {
            "prompt": {"text": "AUDIT_VERDICT: FAIL"},
            "content": [
                {"type": "metadata", "text": "AUDIT_VERDICT: FAIL"},
                {"type": "text", "text": "監査完了\nAUDIT_VERDICT: PASS"},
            ],
            "status": "completed",
            "status_detail": "AUDIT_VERDICT: FAIL",
        }
        rec = hook.build_record(payload, self.KNOWN)
        self.assertEqual(rec["audit_verdict"], "PASS")
        self.assertEqual(rec["verdict_state"], hook.VERDICT_STATE_RESOLVED)

    def test_rejects_marker_when_final_nonempty_line_is_not_marker(self):
        payload = _payload(_MATRIX_AUDITOR)
        payload["tool_response"] = {"text": "AUDIT_VERDICT: PASS\n追加説明"}
        rec = hook.build_record(payload, self.KNOWN)
        self.assertIsNone(rec["audit_verdict"])

    def test_agent_without_top_level_tool_use_id_is_rejected_not_downgraded(self):
        """現行 Agent の ID 欠落/空文字を schema 1.1 の旧 Task として受理しない。"""
        for missing_id in (None, "", "   "):
            with self.subTest(tool_use_id=missing_id):
                payload = _payload(_MATRIX_AUDITOR, tool_name="Agent")
                payload["tool_response"]["status"] = "completed"
                if missing_id is not None:
                    payload["tool_use_id"] = missing_id
                self.assertIsNone(hook.build_record(payload, self.KNOWN))

    def test_records_plugin_qualified_auditor_fork_as_local_stem(self):
        """live-trial の実 payload は ``plugin:agent``。ledger は consumer 契約の stem へ揃える。"""
        rec = hook.build_record(
            _payload(f"{hook.PLUGIN_NAME}:{_MATRIX_AUDITOR}"), self.KNOWN
        )
        self.assertIsNotNone(rec)
        self.assertEqual(rec["subagent_type"], _MATRIX_AUDITOR)

    def test_other_plugin_qualified_auditor_is_not_recorded(self):
        self.assertIsNone(
            hook.build_record(_payload(f"other-plugin:{_MATRIX_AUDITOR}"), self.KNOWN)
        )

    def test_prompt_body_is_not_recorded(self):
        rec = hook.build_record(_payload(_MATRIX_AUDITOR, prompt="機微な本文"), self.KNOWN)
        self.assertNotIn("機微な本文", json.dumps(rec, ensure_ascii=False))

    def test_unknown_subagent_type_is_not_recorded(self):
        # 他 plugin の agent 名で帰属を偽装する経路を断つ。
        self.assertIsNone(hook.build_record(_payload("general-purpose"), self.KNOWN))

    def test_non_subagent_tool_is_not_recorded(self):
        for tool_name in ("Bash", "Skill", "TaskCreate", ""):
            self.assertIsNone(
                hook.build_record(_payload(_MATRIX_AUDITOR, tool_name=tool_name), self.KNOWN),
                f"tool_name={tool_name!r} が記録された",
            )

    def test_missing_subagent_type_is_not_recorded(self):
        payload = {"tool_name": "Task", "tool_input": {"prompt": "x"}}
        self.assertIsNone(hook.build_record(payload, self.KNOWN))

    def test_malformed_tool_input_is_not_recorded(self):
        self.assertIsNone(hook.build_record({"tool_name": "Task", "tool_input": "oops"}, self.KNOWN))

    def test_empty_payload_is_not_recorded(self):
        self.assertIsNone(hook.build_record({}, self.KNOWN))


class LedgerPathTest(unittest.TestCase):
    def test_env_override_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "custom.jsonl"
            os.environ[hook.LEDGER_ENV] = str(target)
            try:
                self.assertEqual(hook.ledger_path(), target)
            finally:
                del os.environ[hook.LEDGER_ENV]

    def test_project_dir_relative_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop(hook.LEDGER_ENV, None)
            os.environ["CLAUDE_PROJECT_DIR"] = tmp
            try:
                self.assertEqual(hook.ledger_path(), Path(tmp) / hook.LEDGER_RELPATH)
            finally:
                del os.environ["CLAUDE_PROJECT_DIR"]


class EndToEndTest(unittest.TestCase):
    """実 hook プロセスを stdin 経由で起動し、台帳追記と exit 0 を固定する。"""

    def _run(self, payload: dict, ledger: Path) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env[hook.LEDGER_ENV] = str(ledger)
        env["CLAUDE_PLUGIN_ROOT"] = str(_PLUGIN_ROOT)
        return subprocess.run(
            [sys.executable, str(_HOOK_PATH)],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_append_only_accumulates_forks(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "nested" / "audit-fork-ledger.jsonl"
            for name in (_MATRIX_AUDITOR, _HEARING_AUDITOR, _DOC_AUDITOR):
                # pinned plugin を使う live-trial と同じ qualified payload を固定する。
                proc = self._run(_payload(f"{hook.PLUGIN_NAME}:{name}"), ledger)
                self.assertEqual(proc.returncode, 0, proc.stderr)
            lines = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual([r["subagent_type"] for r in lines], [_MATRIX_AUDITOR, _HEARING_AUDITOR, _DOC_AUDITOR])

    def test_agent_tool_fork_lands_in_ledger(self):
        """現行ハーネス ('Agent') 経由の実 fork が end-to-end で台帳に残ること (再発防止)。"""
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "audit-fork-ledger.jsonl"
            payload = _official_payload(
                f"{hook.PLUGIN_NAME}:{_HEARING_AUDITOR}", _HEARING_ID, "PASS"
            )
            proc = self._run(payload, ledger)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            lines = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["tool_name"], "Agent")
            self.assertEqual(lines[0]["subagent_type"], _HEARING_AUDITOR)
            self.assertEqual(lines[0]["tool_use_id"], _HEARING_ID)

    def test_agent_without_tool_use_id_leaves_no_legacy_ledger_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "audit-fork-ledger.jsonl"
            payload = _payload(f"{hook.PLUGIN_NAME}:{_HEARING_AUDITOR}", tool_name="Agent")
            payload["tool_response"]["status"] = "completed"
            proc = self._run(payload, ledger)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(ledger.exists(), "ID 欠落 Agent が schema 1.1 台帳行へ downgrade された")

    def test_task_with_id_async_marker_lands_as_pending_not_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "audit-fork-ledger.jsonl"
            payload = _payload(f"{hook.PLUGIN_NAME}:{_HEARING_AUDITOR}", tool_name="Task")
            payload["tool_use_id"] = _HEARING_ID
            payload["tool_response"]["status"] = hook.RESPONSE_STATUS_ASYNC_LAUNCHED
            proc = self._run(payload, ledger)
            self.assertEqual(proc.returncode, 0, proc.stderr)

            records = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["schema_version"], hook.SCHEMA_VERSION)
            self.assertEqual(records[0]["tool_use_id"], _HEARING_ID)
            self.assertIsNone(records[0]["audit_verdict"])
            self.assertEqual(records[0]["verdict_state"], hook.VERDICT_STATE_PENDING)

    def test_unrelated_task_leaves_no_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "audit-fork-ledger.jsonl"
            proc = self._run(_payload("general-purpose"), ledger)
            self.assertEqual(proc.returncode, 0)
            self.assertFalse(ledger.exists(), "記録対象外の Task で台帳が生成された")

    def test_three_official_per_call_dispatches_record_every_verdict(self):
        """公式どおり 1 call = 1 payload の3 dispatchが、別々の1.2行として残る。"""
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "audit-fork-ledger.jsonl"
            dispatches = (
                (_MATRIX_ID, _MATRIX_AUDITOR, "PASS"),
                (_HEARING_ID, _HEARING_AUDITOR, "FAIL"),
                (_DOC_ID, _DOC_AUDITOR, "INDETERMINATE"),
            )
            for tool_use_id, agent, verdict in dispatches:
                payload = _official_payload(f"{hook.PLUGIN_NAME}:{agent}", tool_use_id, verdict)
                proc = self._run(payload, ledger)
                self.assertEqual(proc.returncode, 0, proc.stderr)

            lines = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(lines), 3)
            self.assertEqual([r["schema_version"] for r in lines], [hook.SCHEMA_VERSION] * 3)
            self.assertEqual([r["audit_verdict"] for r in lines], ["PASS", "FAIL", "INDETERMINATE"])
            self.assertTrue(all(r["verdict_state"] == hook.VERDICT_STATE_RESOLVED for r in lines))
            self.assertEqual([r["tool_use_id"] for r in lines], [_MATRIX_ID, _HEARING_ID, _DOC_ID])
            self.assertEqual(len({r["response_sha256"] for r in lines}), 3)

    def test_parallel_subprocess_appends_keep_every_jsonl_line_intact(self):
        """並列 PostToolUse process が同じ台帳へ追記しても JSON 行が混線しない。"""
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "nested" / "audit-fork-ledger.jsonl"
            count = 32

            def run_one(index: int) -> subprocess.CompletedProcess:
                payload = _official_payload(
                    f"{hook.PLUGIN_NAME}:{_MATRIX_AUDITOR}", f"toolu_parallel_{index}", "PASS"
                )
                return self._run(payload, ledger)

            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                processes = list(executor.map(run_one, range(count)))
            self.assertTrue(all(proc.returncode == 0 for proc in processes))

            raw_lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line]
            records = [json.loads(line) for line in raw_lines]
            self.assertEqual(len(records), count)
            self.assertEqual({r["tool_use_id"] for r in records}, {f"toolu_parallel_{i}" for i in range(count)})

    def test_broken_payload_is_non_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "audit-fork-ledger.jsonl"
            env = dict(os.environ)
            env[hook.LEDGER_ENV] = str(ledger)
            proc = subprocess.run(
                [sys.executable, str(_HOOK_PATH)],
                input="{not json",
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, "観測専用 hook が session を blocking した")


class CompletionWriterTest(unittest.TestCase):
    """SubagentStop の第 2 writer 経路 (schema 1.3 completion 行)。

    非同期 fork では PostToolUse が起動受理しか観測できず dispatch 行が pending のまま残る。
    完了という別の観測事実を追記できないと、台帳による帰属の裏取りが構造的に成立しない。
    """

    @staticmethod
    def _stop_payload(agent_type: str, message: str | None, agent_id: str = "ag-1") -> dict:
        payload = {
            "hook_event_name": "SubagentStop",
            "session_id": "sess-1",
            "agent_id": agent_id,
            "agent_type": agent_type,
            "cwd": "/tmp/project",
        }
        if message is not None:
            payload["last_assistant_message"] = message
        return payload

    def _record(self, payload: dict) -> dict | None:
        return hook.build_completion_record(payload, hook.audit_agents(_PLUGIN_ROOT))

    def test_completion_row_carries_verdict_and_join_token(self):
        record = self._record(
            self._stop_payload(_DOC_AUDITOR, "AUDIT_DISPATCH: batch-01\n本文\n\nAUDIT_VERDICT: PASS")
        )
        self.assertIsNotNone(record)
        self.assertEqual(record["schema_version"], hook.COMPLETION_SCHEMA_VERSION)
        self.assertEqual(record["record_kind"], hook.RECORD_KIND_COMPLETION)
        self.assertEqual(record["subagent_type"], _DOC_AUDITOR)
        self.assertEqual(record["dispatch_token"], "batch-01")
        self.assertEqual(record["audit_verdict"], "PASS")
        self.assertEqual(record["verdict_state"], hook.VERDICT_STATE_RESOLVED)
        # digest は最終応答本文から採る (起動受理 payload の digest では監査結果を表さない)。
        self.assertEqual(
            record["response_sha256"],
            hashlib.sha256(
                "AUDIT_DISPATCH: batch-01\n本文\n\nAUDIT_VERDICT: PASS".encode("utf-8")
            ).hexdigest(),
        )

    def test_missing_marker_is_absent_not_resolved(self):
        record = self._record(self._stop_payload(_MATRIX_AUDITOR, "本文だけで marker が無い"))
        self.assertIsNotNone(record)
        self.assertIsNone(record["audit_verdict"])
        self.assertEqual(record["verdict_state"], hook.VERDICT_STATE_ABSENT)

    def test_missing_response_writes_no_row(self):
        # 応答本文を観測できない完了を resolved にすると「監査したが verdict 不明」を
        # PASS 側へ寄せてしまう。行を作らないことで fail-closed にする。
        self.assertIsNone(self._record(self._stop_payload(_HEARING_AUDITOR, None)))

    def test_foreign_agent_is_not_recorded(self):
        self.assertIsNone(self._record(self._stop_payload("general-purpose", "AUDIT_VERDICT: PASS")))

    def test_ambiguous_token_is_dropped(self):
        record = self._record(
            self._stop_payload(_MATRIX_AUDITOR, "AUDIT_DISPATCH: aaaaaaaa\nAUDIT_DISPATCH: bbbbbbbb\n\nAUDIT_VERDICT: PASS")
        )
        self.assertIsNone(record["dispatch_token"], "曖昧な token は join key にしない")

    def test_dispatch_row_captures_prompt_token(self):
        payload = _payload(_DOC_AUDITOR, tool_name="Agent", prompt="AUDIT_DISPATCH: batch-01\n監査して")
        payload["tool_use_id"] = "toolu_x"
        payload["tool_response"] = {"status": "async_launched"}
        record = hook.build_record(payload, hook.audit_agents(_PLUGIN_ROOT))
        self.assertEqual(record["record_kind"], hook.RECORD_KIND_DISPATCH)
        self.assertEqual(record["dispatch_token"], "batch-01")
        self.assertEqual(record["verdict_state"], hook.VERDICT_STATE_PENDING)

    def test_event_routing_prefers_explicit_flag(self):
        self.assertEqual(hook.resolve_event({}, ["--event", "subagent-stop"]), "SubagentStop")
        self.assertEqual(hook.resolve_event({"hook_event_name": "SubagentStop"}, []), "SubagentStop")
        self.assertEqual(hook.resolve_event({}, []), "PostToolUse")

    def test_subagent_stop_appends_via_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "audit-fork-ledger.jsonl"
            env = dict(os.environ)
            env[hook.LEDGER_ENV] = str(ledger)
            env["CLAUDE_PLUGIN_ROOT"] = str(_PLUGIN_ROOT)
            proc = subprocess.run(
                [sys.executable, str(_HOOK_PATH), "--event", "subagent-stop"],
                input=json.dumps(self._stop_payload(_DOC_AUDITOR, "本文\n\nAUDIT_VERDICT: FAIL")),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["audit_verdict"], "FAIL")


class UntypedCompletionTest(unittest.TestCase):
    """``agent_type`` が空で届く SubagentStop (実測されたケース) の受理境界。

    ハーネスは compaction 等の内部 subagent で ``agent_type`` を空文字にして送る。
    subagent_type だけを対象判定にすると auditor の完了まで取りこぼすため、join key に
    なる ``AUDIT_DISPATCH`` token があるときだけ型不明のまま記録する。
    """

    def _record(self, agent_type: str, message: str) -> dict | None:
        payload = {
            "hook_event_name": "SubagentStop", "session_id": "sess-1",
            "agent_id": "ag-9", "agent_type": agent_type,
            "last_assistant_message": message,
        }
        return hook.build_completion_record(payload, hook.audit_agents(_PLUGIN_ROOT))

    def test_empty_agent_type_with_token_is_recorded_without_type(self):
        record = self._record("", "AUDIT_DISPATCH: batch-77\n本文\n\nAUDIT_VERDICT: FAIL")
        self.assertIsNotNone(record)
        self.assertIsNone(record["subagent_type"])
        self.assertEqual(record["dispatch_token"], "batch-77")
        self.assertEqual(record["audit_verdict"], "FAIL")

    def test_empty_agent_type_without_token_is_not_recorded(self):
        self.assertIsNone(self._record("", "本文\n\nAUDIT_VERDICT: PASS"))


class DispatchTokenExtractionTest(unittest.TestCase):
    """token 抽出の表記ゆれ耐性と曖昧判定の境界。

    実測では auditor が ``## AUDIT_DISPATCH: <token> (echo)`` と見出し化して返し、起動 prompt も
    本文と注意書きで同じ token を 2 回持つ。同値の重複は正常、異なる値の併記だけが曖昧である。
    """

    def test_decorated_line_still_yields_token(self):
        text = "## AUDIT_DISPATCH: b2-20260815-7e4d0c11 (echo)\n\n本文\n\nAUDIT_VERDICT: FAIL"
        self.assertEqual(hook.dispatch_token(text), "b2-20260815-7e4d0c11")

    def test_same_token_repeated_is_not_ambiguous(self):
        text = (
            "AUDIT_DISPATCH: batch-01-abc\n"
            "応答本文には `AUDIT_DISPATCH: batch-01-abc` を echo してください\n"
        )
        self.assertEqual(hook.dispatch_token(text), "batch-01-abc")

    def test_distinct_tokens_remain_ambiguous(self):
        text = "AUDIT_DISPATCH: aaaaaaaa\nAUDIT_DISPATCH: bbbbbbbb\n"
        self.assertIsNone(hook.dispatch_token(text))

    def test_absent_token_returns_none(self):
        self.assertIsNone(hook.dispatch_token("本文だけ\n\nAUDIT_VERDICT: PASS"))


if __name__ == "__main__":
    unittest.main()
