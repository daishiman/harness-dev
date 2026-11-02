#!/usr/bin/env python3
# /// script
# name: live-trial-verdict
# purpose: trial 成果 (transcript/成果物/判定入力) を回収し、schema 自己検証済みの live-trial verdict.json を生成する。
# inputs:
#   - argv: --workdir --target-skill --skill-dir --launch --completion --goal-result --scenario-id --scenario-file --observation ほか (下記 usage)
#   - env: CLAUDE_PROJECTS_DIR ($HOME/.claude/projects)
# outputs:
#   - stdout: verdict 要約 + 書出パス
#   - exit: 0=生成成功 / 1=schema 不適合・回収失敗 / 2=usage・denylist
# contexts: [C, E]
# network: false
# write-scope: --workdir 配下のみ (transcript.jsonl / verdict.json)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""live-trial の runtime-evidence 契約 (D10) を機械生成する。

- transcript 回収: ~/.claude/projects/*/<session-id>.jsonl → workdir/transcript.jsonl
- actual_model 抽出: transcript を json.loads ループで走査 (旧 AG 版の jq 代替) し
  assistant.message.model の unique 集合を得る。proof trial の唯一の実走 model 証明。
- skill_dir_tree_sha: 被験 skill の挙動閉包 (SKILL/scripts/prompts/宣言 refs と
  plugin manifest/hooks) の複合 sha256 (repo 相対パス + 内容)。
- 生成した verdict は同梱 schemas/live-trial-verdict.schema.json で自己検証してから
  書き出す (required / enum / additionalProperties false / pattern)。
- scenario 契約: --scenario-id を名乗る trial は --scenario-file (required_observations の
  正本) を必須とし、--observation N=<evidence ref> で回収を宣言する。未回収項目と
  task_args_template との乖離は scenario_contract へ機械的に列挙され、未回収があれば
  goal_verdict は FAIL になる。scenario_id 一致だけの verdict は契約充足を意味しない。
- 被験 skill denylist (再帰遮断) は backend.deny_target_skill が正本。
"""
from __future__ import annotations

import argparse
import csv
import glob as globmod
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _load_sibling(stem: str):
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas" / "live-trial-verdict.schema.json"


def find_transcript(projects_dir: str, session_id: str) -> Path | None:
    for p in globmod.glob(os.path.join(projects_dir, "*", f"{session_id}.jsonl")):
        if Path(p).is_file():
            return Path(p)
    return None


def iter_transcript(path: Path):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            yield obj


def extract_models(path: Path, runtime: str = "claude") -> list[str]:
    if runtime == "codex":
        return _load_sibling("extract-codex-transcript").extract_models(path)
    if runtime != "claude":
        raise ValueError(f"unsupported live-trial runtime: {runtime}")
    models: set[str] = set()
    for obj in iter_transcript(path):
        if obj.get("type") == "assistant":
            model = (obj.get("message") or {}).get("model")
            if isinstance(model, str) and model:
                models.add(model)
    return sorted(models)


def extract_skill_invocations(path: Path, runtime: str = "claude", *,
                              skill_dir: Path | None = None,
                              target_skill: str | None = None) -> list[str]:
    """transcript に残る Skill ツール呼出しの skill 名を返す (重複なし・昇順)。

    「被験 skill を起動せず、その中で使われる script を Bash から直接叩く」実走は、
    成果物が出ても skill の受け入れ検証になっていない (2026-07-21 live-trial r14 の C05)。
    起動の有無を orchestrator の自己申告ではなく transcript から機械判定する。
    """
    if runtime == "codex":
        return _load_sibling("extract-codex-transcript").extract_skill_invocations(
            path, skill_dir=skill_dir, target_skill=target_skill
        )
    if runtime != "claude":
        raise ValueError(f"unsupported live-trial runtime: {runtime}")
    skills: set[str] = set()
    for obj in iter_transcript(path):
        content = (obj.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") != "Skill":
                continue
            name = (block.get("input") or {}).get("skill")
            if isinstance(name, str) and name:
                skills.add(name)
    return sorted(skills)


GOAL_SEEK_ARTIFACTS = ("goal-spec.json", "progress.json", "intermediate.jsonl")


def validate_goal_seek_evidence(skill_dir: Path, eval_root: Path | None) -> dict:
    """goal_seek 成果物の実体と内容を独立 validator で検証する。

    transcript の command/file_path 文字列だけでは、ファイル名を言及しただけの run や
    空のダミー成果物を PASS にできる。宣言済み skill は eval root 未指定も fail-closed にする。
    """
    validator = _load_sibling("validate-goal-seek-evidence")
    if not validator.declares_goal_seek(skill_dir / "SKILL.md"):
        return {
            "valid": True,
            "goal_seek_declared": False,
            "violations": [],
            "checked": {"skipped": "frontmatter に goal_seek 宣言なし"},
        }
    if eval_root is None:
        return {
            "valid": False,
            "goal_seek_declared": True,
            "violations": [
                "eval-root-missing: goal_seek 宣言 skill は --goal-seek-eval-root が必須"
            ],
            "checked": {},
        }
    return validator.verify(skill_dir, eval_root)


def extract_claude_version(path: Path) -> str | None:
    for obj in iter_transcript(path):
        ver = obj.get("version")
        if isinstance(ver, str) and ver:
            return ver
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def validate_runtime_evidence(doc: dict, transcript_path: Path | None,
                              skill_dir: Path | None = None) -> list[str]:
    """Check native-runtime identity independently of the caller's PASS fields."""
    if not isinstance(doc, dict) or not isinstance(doc.get("environment"), dict):
        return ["runtime-environment-invalid"]
    environment = doc["environment"]
    overall = doc.get("overall", {})
    if not isinstance(overall, dict):
        return ["runtime-overall-invalid"]
    runtime = environment.get("runtime", "claude")
    if runtime not in {"claude", "codex"}:
        return [f"runtime-unsupported:{runtime}"]
    errors = []
    if runtime == "claude":
        if environment.get("codex_version") is not None:
            errors.append("runtime-mismatch:Claude evidence declares Codex version")
        if environment.get("native_transcript_format") not in {None, "claude-transcript-jsonl"}:
            errors.append("runtime-mismatch:Claude evidence declares non-Claude transcript")
        if transcript_path is not None:
            for obj in iter_transcript(transcript_path):
                if obj.get("type") in {"session_meta", "turn_context", "response_item", "event_msg"}:
                    errors.append("runtime-mismatch:Codex native records in Claude evidence")
                    break
        return errors
    if environment.get("claude_version") is not None:
        errors.append("runtime-mismatch:Codex evidence declares Claude version")
    if environment.get("native_transcript_format") != "codex-rollout-jsonl":
        errors.append("runtime-mismatch:Codex native transcript format is required")
    if environment.get("tmux") is not False:
        errors.append("runtime-mismatch:Codex native exec evidence is not a tmux trial")
    blocked = overall.get("verdict") == "BLOCKED"
    if transcript_path is None or not transcript_path.is_file():
        return errors + ([] if blocked else ["native-transcript-missing"])
    info = _load_sibling("extract-codex-transcript").inspect_transcript(
        transcript_path, skill_dir=skill_dir, target_skill=doc.get("target_skill")
    )
    if environment.get("codex_version") != info["cli_version"]:
        errors.append("native-cli-version-mismatch")
    if doc.get("actual_model") != info["models"]:
        errors.append("native-actual-model-mismatch")
    if environment.get("native_sandbox_contexts") != info["sandbox_contexts"]:
        errors.append("native-sandbox-context-mismatch")
    state_ref = environment.get("native_run_state_ref")
    if state_ref is not None:
        if not isinstance(state_ref, str):
            errors.append("native-run-state-ref-invalid")
        else:
            metadata, metadata_errors = native_run_metadata(
                transcript_path.parent, transcript_path.parent / state_ref, info,
                nudge=doc.get("nudge_count", 0), gate=doc.get("gate_response_count", 0),
            )
            errors.extend(metadata_errors)
            if any(environment.get(key) != value for key, value in metadata.items()):
                errors.append("native-run-state-metadata-mismatch")
    elif environment.get("single_input_autonomous") is True or environment.get("native_operation_turns") is not None:
        errors.append("native-run-state-missing-for-autonomy-claim")
    if not blocked:
        errors.extend(info["format_errors"])
        errors.extend(info["activation_errors"])
        if not info["cli_version"]:
            errors.append("native-cli-version-unmeasured")
        if not info["models"]:
            errors.append("native-actual-model-unmeasured")
        if skill_dir is not None and doc.get("target_skill") not in info["invoked_skills"]:
            errors.append("native-skill-activation-unproven")
        if overall.get("completion") == "PASS" and not info["completed"]:
            errors.append("native-completion-unproven")
        if not info["usage"]["measured"]:
            errors.append("native-tokens-unmeasured")
        contexts = info["sandbox_contexts"]
        if not contexts or any(context["mode"] != environment.get("permissions_mode") for context in contexts):
            errors.append("native-sandbox-mode-unproven")
        for context in contexts:
            if context["mode"] == "workspace-write" and (
                context["network_access"] is not False or not context["profile_restricted"]
                or not context["writable_roots"] or any(not Path(root).is_absolute() for root in context["writable_roots"])
                or context["exclude_tmpdir_env_var"] is not True or context["exclude_slash_tmp"] is not True
                or context["special_write_roots"]
            ):
                errors.append("native-workspace-sandbox-unproven")
    return sorted(set(errors))


def external_confirmation_proof_errors(workdir: Path, state: dict, entry: dict, user: dict) -> list[str]:
    """Recheck public native event/receipt/source bindings without exposing the guard key.

    Public CI cannot recheck the private HMAC. It checks the original hook input and
    stdout, native user turn, canonical receipt bytes, source and adapter digests.
    The fresh independent goal evaluator remains required.
    """
    try:
        def contained(ref):
            path = (workdir / ref).resolve(strict=True)
            path.relative_to(workdir.resolve(strict=True))
            return path
        def sha(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()
        def encoded(document):
            return (json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
        proof_path = contained(entry["proof_ref"])
        if sha(proof_path) != entry["proof_sha256"] or entry.get("hook_verified") is not True:
            raise ValueError("proof digest/verification missing")
        proof = json.loads(proof_path.read_text())
        pin, policy = state["external_fixture_pin"], state["external_fixture_policy"]
        if proof.get("fixture_pin") != pin or proof.get("allowed_commands") != policy["allowed_commands"] or proof.get("target_scopes") != policy["target_scopes"]:
            raise ValueError("fixture policy/pin mismatch")
        for ref, key in (("guard_source_ref", "guard_script_sha256"), ("hook_wrapper_ref", "hook_wrapper_sha256"), ("fake_adapter_ref", "fake_adapter_sha256")):
            if sha(contained(policy[ref])) != pin[key]:
                raise ValueError("source/adapter digest mismatch")
        canonical_guard = Path(__file__).resolve().parents[4] / "skill-governance-adapters/scripts/build-external-mutation-guard.py"
        if not canonical_guard.is_file() or sha(canonical_guard) != pin["guard_script_sha256"]:
            raise ValueError("guard source differs from the current canonical dependency")
        rows = [json.loads(line) for line in contained(policy["hook_events_ref"]).read_text().splitlines()]
        index = entry["hook_event_index"]
        if isinstance(index, bool) or not isinstance(index, int) or index < entry["hook_records_before"] or rows[index] != proof["native_hook_record"]:
            raise ValueError("original hook log record mismatch")
        row = proof["native_hook_record"]
        payload, output = json.loads(row["input_raw"]), json.loads(row["output_raw"])
        prompt = payload["prompt"].strip()
        match = re.fullmatch(r"CONFIRM EXTERNAL MUTATION ([0-9A-F]{24})", prompt)
        if (not match or hashlib.sha256(prompt.encode()).hexdigest() != user["normalized_text_sha256"]
                or hashlib.sha256(match.group(1).encode()).hexdigest() != entry["challenge_sha256"]):
            raise ValueError("hook challenge/native user input mismatch")
        if (row.get("runtime") != "codex" or row.get("returncode") != 0
                or row.get("guard_script_sha256") != pin["guard_script_sha256"]
                or payload.get("hook_event_name") != "UserPromptSubmit"
                or payload.get("session_id") != state["session_id"]
                or payload.get("cwd") != entry["project_root"]
                or entry["project_root"] != state["writable_roots"][0]):
            raise ValueError("native hook source/identity mismatch")
        specific = output["hookSpecificOutput"]
        if specific.get("hookEventName") != "UserPromptSubmit" or not specific["additionalContext"].startswith("[external-mutation-confirmation]\n"):
            raise ValueError("canonical native hook output missing")
        result = json.loads(specific["additionalContext"].split("\n", 1)[1])
        preview, confirmation = proof["preview"], proof["confirmation"]
        preview_sha = hashlib.sha256(encoded(preview)).hexdigest()
        confirmation_sha = hashlib.sha256(encoded(confirmation)).hexdigest()
        prior = entry["sent_after_turn"]
        if isinstance(prior, bool) or not isinstance(prior, int) or prior < 1 or entry["native_turn"] != prior + 1:
            raise ValueError("external confirmation response turn order mismatch")
        events = [json.loads(line) for line in contained(f"native-exec/turn-{prior:03d}.jsonl").read_text().splitlines()]
        texts = [row["item"].get("text", "") for row in events if row.get("type") == "item.completed" and row.get("item", {}).get("type") == "agent_message"]
        text = texts[-1] if texts else ""
        preview_path = str(Path(entry["project_root"]) / ".artifact-delivery/external-mutation" / f"preview-{preview['receipt_id']}.json")
        if (hashlib.sha256(text.encode()).hexdigest() != entry["presentation_sha256"]
                or f"GATE-CHALLENGE: {match.group(1)}" not in text or preview_path not in text
                or preview_sha not in text or preview.get("target_scope", "") not in text
                or not all(arg in text for arg in preview.get("command_argv", []))):
            raise ValueError("original assistant did not present the exact preview before confirmation")
        command_sha = hashlib.sha256(json.dumps(preview.get("command_argv"), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if preview.get("command_sha256") != command_sha or entry["command_sha256"] != command_sha:
            raise ValueError("external command digest mismatch")
        if (result.get("status") != "confirmation-created" or result.get("receipt_sha256") != confirmation_sha
                or confirmation_sha != entry["confirmation_receipt_sha256"] or preview_sha != entry["preview_sha256"]
                or confirmation.get("producer") != "codex-user-prompt-submit"
                or confirmation.get("kind") != "confirmation" or confirmation.get("decision") != "confirm"
                or confirmation.get("preview_receipt_sha256") != preview_sha
                or confirmation.get("preview_receipt_id") != entry["preview_receipt_id"]
                or confirmation.get("user_event_id") != hashlib.sha256(f"{state['session_id']}\0{prompt}".encode()).hexdigest()):
            raise ValueError("receipt producer/preview/user binding mismatch")
        if (preview.get("kind") != "preview" or preview.get("receipt_id") != entry["preview_receipt_id"]
                or preview.get("challenge_sha256") != entry["challenge_sha256"]
                or preview.get("entrypoint_ref") != "plugin:" + entry["target_skill"].replace(":", "/skills/", 1) + "/SKILL.md"
                or preview.get("command_argv") not in policy["allowed_commands"]
                or preview.get("target_scope") not in policy["target_scopes"]
                or not preview["issued_at"] <= confirmation["issued_at"] <= preview["expires_at"]):
            raise ValueError("predeclared preview/validity mismatch")
        for document, name in ((preview, f"preview-{preview['receipt_id']}.json"), (confirmation, f"confirmation-{confirmation['receipt_id']}.json")):
            path = contained("fixture-final/.artifact-delivery/external-mutation/" + name)
            if path.read_bytes() != encoded(document):
                raise ValueError("collected receipt bytes mismatch")
        if proof.get("private_seal_verified") is not True or not proof.get("public_hmac_recheck", "").startswith("not_available:"):
            raise ValueError("private/public verification boundary missing")
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        return [f"native-external-confirmation-invalid:{exc}"]
    return []


def native_run_metadata(workdir: Path, state_path: Path | None, info: dict | None,
                        *, nudge: int, gate: int) -> tuple[dict, list[str]]:
    """Bind the disclosure ledger to actual native user turns; it never grants PASS."""
    result = {"native_operation_turns": None, "single_input_autonomous": False}
    if state_path is None or info is None:
        return result, []
    try:
        resolved = state_path.resolve(strict=True)
        reference = str(resolved.relative_to(workdir.resolve()))
        raw = resolved.read_bytes()
        state = json.loads(raw)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return result, [f"native-run-state-invalid:{exc}"]
    errors = []
    if not isinstance(state, dict) or state.get("runtime") != "codex" or state.get("session_id") != info["session_id"] or state.get("collected") is not True:
        return result, ["native-run-state-identity-or-freeze-mismatch"]
    operations, responses = state.get("native_operation_turns"), state.get("responses")
    if not isinstance(operations, list) or not isinstance(responses, list):
        return result, ["native-run-state-turns-invalid"]
    roots = state.get("writable_roots")
    if not isinstance(roots, list) or not roots or not all(isinstance(root, str) and Path(root).is_absolute() for root in roots):
        errors.append("native-run-state-write-roots-invalid")
    else:
        for context in info["sandbox_contexts"]:
            for actual in context["writable_roots"]:
                actual_path = Path(os.path.normpath(actual))
                if not any(actual_path == Path(os.path.normpath(root)) or Path(os.path.normpath(root)) in actual_path.parents for root in roots):
                    errors.append("native-sandbox-write-root-outside-ledger")
    turns = state.get("turns")
    if not isinstance(turns, list) or len(turns) != len(info["user_turns"]):
        errors.append("native-run-state-execution-count-mismatch")
    else:
        for number, (turn, user) in enumerate(zip(turns, info["user_turns"]), 1):
            if not isinstance(turn, dict) or turn.get("number") != number or turn.get("stdin_sha256") != user["text_sha256"]:
                errors.append("native-run-state-execution-prompt-mismatch")
    matched, count = {1}, 0
    turns_by_number = {
        turn.get("number"): turn
        for turn in turns
        if isinstance(turn, dict) and isinstance(turn.get("number"), int) and not isinstance(turn.get("number"), bool)
    } if isinstance(turns, list) else {}
    for entry in [*operations, *responses]:
        if not isinstance(entry, dict):
            errors.append("native-run-state-entry-invalid")
            continue
        number = entry.get("native_turn")
        if not entry.get("submitted"):
            # 打切りで submitted にならない turn は、台帳に無い隠し入力ではない。
            # 完了していない終端 turn として分類し、提出済み operation には数えない。
            turn = turns_by_number.get(number)
            user = info["user_turns"][number - 1] if isinstance(number, int) and not isinstance(number, bool) and 1 <= number <= len(info["user_turns"]) else None
            if (isinstance(turn, dict) and user is not None and turn.get("terminated")
                    and turn.get("native_turn_complete") is False
                    and turn.get("stdin_sha256") == user["text_sha256"]):
                if number in matched:
                    errors.append("native-run-state-user-turn-duplicate")
                matched.add(number)
                if entry.get("prompt_sha256") != user["text_sha256"]:
                    errors.append("native-run-state-prompt-mismatch")
            continue
        if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= len(info["user_turns"]):
            errors.append("native-run-state-user-turn-missing")
            continue
        if number in matched:
            errors.append("native-run-state-user-turn-duplicate")
        matched.add(number)
        user = info["user_turns"][number - 1]
        if entry.get("prompt_sha256") != user["text_sha256"]:
            errors.append("native-run-state-prompt-mismatch")
        if entry.get("kind") == "external-mutation-confirmation":
            errors.extend(external_confirmation_proof_errors(workdir, state, entry, user))
        if entry in operations:
            target, args = entry.get("target_skill"), entry.get("args")
            if not isinstance(target, str) or not isinstance(args, str):
                errors.append("native-run-state-operation-invalid")
            else:
                expected = f"${target} {args}\n"
                if user["normalized_text_sha256"] != hashlib.sha256(expected.strip().encode()).hexdigest():
                    errors.append("native-run-state-operation-prompt-mismatch")
            count += 1
    if set(range(1, len(info["user_turns"]) + 1)) != matched:
        errors.append("native-run-state-unclassified-user-turns")
    result.update({"native_operation_turns": count,
                   "single_input_autonomous": len(info["user_turns"]) == 1 and info["completed"] and count == 0 and nudge == 0 and gate == 0 and not errors,
                   "native_run_state_ref": reference, "native_run_state_sha256": hashlib.sha256(raw).hexdigest()})
    return result, errors


def load_goal_evaluation(
    workdir: Path, evaluation_path: Path | None, transcript_sha: str | None
) -> tuple[dict | None, list[str]]:
    """Bind a fresh evaluator artifact to the exact collected transcript."""
    if evaluation_path is None:
        return None, ["fresh evaluator artifact missing (--goal-evaluation required)"]
    try:
        resolved = evaluation_path.resolve(strict=True)
        resolved.relative_to(workdir.resolve())
    except (OSError, ValueError):
        return None, ["goal evaluation must be an existing file inside workdir"]
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"goal evaluation unreadable: {exc}"]
    expected = {"result", "blockers", "evaluator", "transcript_sha256", "evidence_refs"}
    errors: list[str] = []
    if not isinstance(raw, dict) or set(raw) != expected:
        return None, ["goal evaluation must contain exactly result/blockers/evaluator/"
                      "transcript_sha256/evidence_refs"]
    if raw.get("result") not in {"PASS", "FAIL"}:
        errors.append("goal evaluation result must be PASS|FAIL")
    blockers = raw.get("blockers")
    if not isinstance(blockers, list) or any(
        not isinstance(value, str) or not value.strip() for value in blockers
    ):
        errors.append("goal evaluation blockers must be a string array")
    evaluator = raw.get("evaluator")
    if (
        not isinstance(evaluator, dict)
        or set(evaluator) != {"mode", "id"}
        or evaluator.get("mode") != "fresh-independent-context"
        or not isinstance(evaluator.get("id"), str)
        or not evaluator["id"].strip()
    ):
        errors.append("goal evaluation evaluator must identify a fresh-independent-context")
    if transcript_sha is None or raw.get("transcript_sha256") != transcript_sha:
        errors.append("goal evaluation transcript_sha256 does not match collected transcript")
    refs = raw.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        errors.append("goal evaluation evidence_refs must be a non-empty array")
    else:
        for ref in refs:
            if not isinstance(ref, str) or not ref:
                errors.append("goal evaluation evidence_ref must be a non-empty string")
                continue
            target = (workdir / ref.partition("#")[0]).resolve()
            try:
                target.relative_to(workdir.resolve())
            except ValueError:
                errors.append(f"goal evaluation evidence_ref escapes workdir: {ref}")
                continue
            if not target.is_file():
                errors.append(f"goal evaluation evidence_ref missing: {ref}")
    if errors:
        return None, errors
    return {
        "evidence_ref": str(resolved.relative_to(workdir.resolve())),
        "sha256": sha256_file(resolved),
        "result": raw["result"],
        "blockers": blockers,
        "evaluator": evaluator,
        "transcript_sha256": raw["transcript_sha256"],
        "evidence_refs": refs,
    }, []


_BEHAVIOR_REF_KEYS = (
    "script_refs",
    "reference_refs",
    "responsibility_refs",
    "schema_refs",
)


def _frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:index])
    raise ValueError("SKILL.md frontmatter is not terminated")


def _clean_yaml_scalar(value: str) -> str:
    value = value.split(" #", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()


def _frontmatter_refs(skill_md: Path) -> list[str]:
    """Extract path-like *_refs without adding a PyYAML runtime dependency."""
    lines = _frontmatter(skill_md.read_text(encoding="utf-8")).splitlines()
    refs: list[str] = []
    for index, line in enumerate(lines):
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match or match.group(1) not in _BEHAVIOR_REF_KEYS:
            continue
        value = match.group(2).strip()
        if value.startswith("["):
            if not value.endswith("]"):
                raise ValueError(f"unsupported multiline flow list: {match.group(1)}")
            body = value[1:-1].strip()
            if body:
                refs.extend(
                    _clean_yaml_scalar(item)
                    for item in next(csv.reader([body], skipinitialspace=True))
                    if _clean_yaml_scalar(item)
                )
            continue
        if value:
            refs.append(_clean_yaml_scalar(value))
            continue
        for child in lines[index + 1:]:
            if child and not child[0].isspace():
                break
            item = re.match(r"^\s+-\s+(.+?)\s*$", child)
            if item:
                cleaned = _clean_yaml_scalar(item.group(1))
                if cleaned:
                    refs.append(cleaned)
    return refs


# live-trial-status.GATE_TOOLS と同一。gate を上げる能力の frontmatter 宣言。
CONTRACT_GATE_TOOLS = ("AskUserQuestion", "ExitPlanMode")


def contract_gate_evidence(skill_md: Path) -> list[str]:
    """被験 skill が契約上の確認 gate を宣言している決定論的根拠を返す。

    ``--gate-kind contractual`` は「この gate 応答は受け入れ条件そのものだから
    降格根拠にならない」という主張だが、申告するのは trial を回す当人である。
    無検証で信じると、実際は stall 救済だった介入を contractual と言い換える
    だけで DEGRADED を PASS へ反転できる (受け入れ基準の自己申告による緩和)。
    そこで主張を被験 skill 側の宣言へ接地させ、根拠が 1 つも無い contractual は
    fail-closed で拒否する。

    根拠として認めるのは frontmatter の機械可読な宣言 2 種だけ:
    - ``external_mutation_guard``: 外部 mutation の人間確認 flow を宣言している
    - ``allowed-tools`` の ``AskUserQuestion`` / ``ExitPlanMode``

    本文の散文は根拠にしない。書き足すだけで主張が通るなら接地にならない。
    """
    lines = _frontmatter(skill_md.read_text(encoding="utf-8")).splitlines()
    evidence: list[str] = []
    for index, line in enumerate(lines):
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.group(1), match.group(2)
        if key == "external_mutation_guard" and value.strip():
            evidence.append("frontmatter.external_mutation_guard")
            continue
        if key != "allowed-tools":
            continue
        block = [value]
        for child in lines[index + 1:]:
            if child and not child[0].isspace():
                break
            block.append(child)
        joined = "\n".join(block)
        evidence.extend(
            f"frontmatter.allowed-tools:{tool}"
            for tool in CONTRACT_GATE_TOOLS
            if re.search(rf"\b{tool}\b", joined)
        )
    return sorted(set(evidence))


def _plugin_context(skill_dir: Path) -> tuple[Path, Path] | None:
    """Return (repo root, plugin root) only for a canonical plugins/<name>/skills path."""
    for candidate in (skill_dir, *skill_dir.parents):
        if candidate.parent.name != "plugins":
            continue
        manifest = candidate / ".claude-plugin" / "plugin.json"
        if manifest.is_file():
            return candidate.parent.parent.resolve(), candidate.resolve()
    return None


def _read_package_contract(
    plugin_root: Path, skill_name: str,
) -> tuple[Path | None, tuple[str, ...]]:
    """Read and validate package dependencies, narrowed for one target skill.

    The package-level ``depends_on`` list is an allow-list.  If
    ``skill_dependencies`` is present, only the mapped subset participates in
    this skill's behavior closure.  Without the map, legacy all-dependency
    behavior is retained.
    """
    path = plugin_root / "references" / "package-contract.json"
    if not path.is_file():
        return None, ()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"package contract read/parse error: {path}: {exc}") from exc
    depends = doc.get("depends_on", []) if isinstance(doc, dict) else None
    if not isinstance(depends, list) or not all(
        isinstance(item, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", item)
        for item in depends
    ):
        raise ValueError(f"package contract depends_on must be plugin slug strings: {path}")
    if len(depends) != len(set(depends)):
        raise ValueError(f"package contract depends_on contains duplicates: {path}")
    scoped = doc.get("skill_dependencies")
    if scoped is None:
        return path, tuple(depends)
    if not isinstance(scoped, dict):
        raise ValueError(f"package contract skill_dependencies must be an object: {path}")
    entries = doc.get("entry_points", {})
    known_skills = set(entries.get("skills", [])) if isinstance(entries, dict) else set()
    for declared_skill, dependencies in scoped.items():
        if not isinstance(declared_skill, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9-]*", declared_skill
        ):
            raise ValueError(
                f"package contract skill_dependencies has invalid skill: {declared_skill!r}"
            )
        if known_skills and declared_skill not in known_skills:
            raise ValueError(
                "package contract skill_dependencies references an undeclared entry point: "
                f"{declared_skill}"
            )
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", item)
            for item in dependencies
        ):
            raise ValueError(
                "package contract skill_dependencies values must be plugin slug arrays: "
                f"{declared_skill}"
            )
        if len(dependencies) != len(set(dependencies)):
            raise ValueError(
                f"package contract skill_dependencies contains duplicates: {declared_skill}"
            )
        undeclared = sorted(set(dependencies) - set(depends))
        if undeclared:
            raise ValueError(
                "package contract skill_dependencies must be a subset of depends_on: "
                f"{declared_skill} -> {undeclared}"
            )
    return path, tuple(scoped.get(skill_name, []))


def _contained(path: Path, root: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"declared behavior dependency missing: {label}: {path}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"declared behavior dependency escapes repository: {label}: {resolved}") from exc
    return resolved


def _manifest_name(plugin_root: Path, expected: str) -> Path:
    manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"plugin manifest read/parse error: {manifest_path}: {exc}") from exc
    actual = manifest.get("name") if isinstance(manifest, dict) else None
    if actual != expected:
        raise ValueError(
            f"plugin manifest name mismatch: expected={expected} actual={actual}"
        )
    return manifest_path.resolve()


def _manifest_dependency_slugs(plugin_root: Path, expected: str) -> tuple[str, ...]:
    """Return the manifest ``dependencies`` boot pins into argv.

    ホストは未解決依存を持つ plugin を登録しないため、この集合は skill 単位へ
    narrowing できず、live-trial-boot は必ず ``--plugin-dir`` へ載せる
    (``_merge_dependency_slugs`` の union)。closure がこれを外すと、trial に
    実在して挙動へ効く plugin (hooks を出荷する dependency を含む) の変更が
    verdict を stale にせず、変更後も古い PASS が再利用される。
    「load される集合」と「digest される集合」は同一でなければならない。
    """
    manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"plugin manifest read/parse error: {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("name") != expected:
        actual = manifest.get("name") if isinstance(manifest, dict) else None
        raise ValueError(
            f"plugin manifest name mismatch: expected={expected} actual={actual}"
        )
    dependencies = manifest.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(
        isinstance(item, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", item)
        for item in dependencies
    ):
        raise ValueError(
            f"plugin manifest dependencies must be plugin slug strings: {manifest_path}"
        )
    if len(dependencies) != len(set(dependencies)):
        raise ValueError(f"plugin manifest dependencies contains duplicates: {manifest_path}")
    if expected in dependencies:
        raise ValueError(f"plugin manifest dependencies contains self: {manifest_path}")
    return tuple(sorted(dependencies))


def _dependency_behavior_contract(plugin_root: Path, expected: str) -> tuple[Path, dict]:
    """Load the harness sidecar that identifies a dependency's behavior surface."""
    path = plugin_root / "references" / "package-contract.json"
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"dependency package contract read/parse error: {path}: {exc}"
        ) from exc
    if not isinstance(contract, dict) or contract.get("plugin_name") != expected:
        actual = contract.get("plugin_name") if isinstance(contract, dict) else None
        raise ValueError(
            "dependency package contract plugin_name mismatch: "
            f"expected={expected} actual={actual}"
        )
    entry_points = contract.get("entry_points")
    if not isinstance(entry_points, dict):
        raise ValueError(f"dependency package contract entry_points missing: {path}")
    for kind in ("skills", "agents", "commands", "hooks"):
        values = entry_points.get(kind, [])
        if not isinstance(values, list) or not all(
            isinstance(item, str) and item for item in values
        ):
            raise ValueError(
                f"dependency package contract entry_points.{kind} must be strings: {path}"
            )
    return path.resolve(), entry_points


# closure は「host が load する出荷バイト列」を digest する。ローカルのツール実行が
# 残す一時 cache は load されず出荷もされないが、tree 走査には引っかかる。除外しないと
# 依存 plugin で一度 pytest を回すだけで digest が動き、stale 判定が「テストを実行したか」
# に依存してしまう (CI は clone 直後なので再現せず、ローカルだけ落ちる非対称になる)。
# 除外は deny-list 方式にする。git 問い合わせに落とすと git 非在の runtime で digest が
# 変わり、決定性という closure の存在意義そのものを崩すため。
_EPHEMERAL_DIR_NAMES = frozenset({
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".benchmarks",
})
_EPHEMERAL_SUFFIXES = frozenset({".pyc", ".pyo"})
_EPHEMERAL_FILE_NAMES = frozenset({".DS_Store"})


def _is_ephemeral_artifact(path: Path) -> bool:
    """True for tool-generated files that are neither loaded nor shipped."""
    if _EPHEMERAL_DIR_NAMES & set(path.parts):
        return True
    return path.suffix in _EPHEMERAL_SUFFIXES or path.name in _EPHEMERAL_FILE_NAMES


def behavior_closure_files(skill_dir: Path, runtime: str = "claude") -> list[tuple[str, Path]]:
    """Resolve the declared behavior closure, fail-closed on missing/unsafe refs."""
    if runtime not in {"claude", "codex"}:
        raise ValueError(f"unsupported live-trial runtime: {runtime}")
    skill_dir = Path(skill_dir).resolve()
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise ValueError(f"skill dir has no SKILL.md: {skill_dir}")

    context = _plugin_context(skill_dir)
    repo_root, plugin_root = context or (skill_dir, skill_dir)
    files: dict[Path, str] = {}

    def add_file(path: Path, source: str) -> None:
        resolved = _contained(path, repo_root, source)
        if not resolved.is_file():
            raise ValueError(f"behavior dependency is not a file: {source}: {resolved}")
        label = (
            resolved.relative_to(repo_root).as_posix()
            if context else resolved.relative_to(skill_dir).as_posix()
        )
        files.setdefault(resolved, label)

    def add_tree(path: Path, source: str) -> None:
        resolved = _contained(path, repo_root, source)
        if not resolved.is_dir():
            raise ValueError(f"behavior dependency is not a directory: {source}: {resolved}")
        for child in sorted(resolved.rglob("*")):
            child_resolved = _contained(child, repo_root, source)
            if child_resolved.is_dir():
                if child.is_symlink():
                    raise ValueError(
                        f"behavior dependency directory symlink is not allowed: "
                        f"{source}: {child} -> {child_resolved}"
                    )
                continue
            if _is_ephemeral_artifact(child):
                continue
            add_file(child, source)

    add_file(skill_md, "SKILL.md")
    for dirname in ("scripts", "prompts"):
        directory = skill_dir / dirname
        if directory.is_dir():
            add_tree(directory, dirname)

    contract_path: Path | None = None
    declared_dependencies: tuple[str, ...] = ()
    if context:
        plugin_slug = plugin_root.name
        add_file(_manifest_name(plugin_root, plugin_slug), "native plugin manifest")
        hooks = plugin_root / "hooks"
        if hooks.is_dir():
            add_tree(hooks, "native plugin hooks")
        _contract_path, contract_dependencies = _read_package_contract(
            plugin_root, skill_dir.name
        )
        # Do not hash the raw target package contract.  The selected dependency
        # set below is the behavior-relevant projection; hashing unrelated
        # entry points or another skill's dependency map would invalidate every
        # trial in the plugin.
        # Bind exactly the dependency plugins boot loads for this skill.  A
        # package without skill_dependencies keeps the legacy all-dependency
        # closure; a scoped package avoids unrelated invalidation.
        # manifest dependencies は skill 単位へ narrowing できず boot が必ず
        # load するため、live-trial-boot._merge_dependency_slugs と同じ union を
        # 取る。closure が load 集合より狭いと、trial に実在する plugin の変更が
        # digest に出ず PASS が stale にならない (検査の素通り)。
        declared_dependencies = tuple(sorted(
            set(_manifest_dependency_slugs(plugin_root, plugin_slug))
            | set(contract_dependencies)
        ))
        for dependency in declared_dependencies:
            dep_root = _contained(
                repo_root / "plugins" / dependency, repo_root,
                f"declared plugin dependency {dependency}",
            )
            try:
                dep_root.relative_to(repo_root / "plugins")
            except ValueError as exc:
                raise ValueError(
                    f"declared plugin dependency escapes plugins root: {dependency}"
                ) from exc
            add_file(_manifest_name(dep_root, dependency), f"dependency manifest {dependency}")
            dep_contract, dep_entries = _dependency_behavior_contract(dep_root, dependency)
            add_file(dep_contract, f"dependency package contract {dependency}")
            dep_hooks = dep_root / "hooks"
            if dep_hooks.is_dir():
                add_tree(dep_hooks, f"dependency hooks {dependency}")
            for skill_name in dep_entries.get("skills", []):
                add_tree(
                    dep_root / "skills" / skill_name,
                    f"dependency skill {dependency}:{skill_name}",
                )
            for agent_name in dep_entries.get("agents", []):
                add_file(
                    dep_root / "agents" / f"{agent_name}.md",
                    f"dependency agent {dependency}:{agent_name}",
                )
            for command_name in dep_entries.get("commands", []):
                add_file(
                    dep_root / "commands" / f"{command_name}.md",
                    f"dependency command {dependency}:{command_name}",
                )
            # Shared runtime assets referenced by dependency entry points commonly
            # live at plugin root. Keep tests/docs outside the closure.
            for dirname in ("scripts", "schemas"):
                directory = dep_root / dirname
                if directory.is_dir():
                    add_tree(directory, f"dependency {dirname} {dependency}")

    if runtime == "codex" and context:
        # Preserve Claude's existing digest exactly. Codex additionally binds the
        # native manifests and hook delivery source actually used by its runner.
        for slug in (plugin_root.name, *declared_dependencies):
            native_root = repo_root / "plugins" / slug
            manifest_path = native_root / ".codex-plugin" / "plugin.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"Codex manifest read/parse error: {manifest_path}: {exc}") from exc
            if not isinstance(manifest, dict) or manifest.get("name") != slug:
                raise ValueError(f"Codex manifest name mismatch: {manifest_path}")
            add_file(manifest_path, f"Codex manifest {slug}")
            native_hooks = manifest.get("hooks")
            if native_hooks is not None:
                if not isinstance(native_hooks, str) or Path(native_hooks).is_absolute():
                    raise ValueError(f"Codex hooks must be a relative path: {manifest_path}")
                hook_path = _contained(native_root / native_hooks, native_root, "Codex hooks")
                add_file(hook_path, f"Codex hooks {slug}")
            native_assets = native_root / "codex"
            if native_assets.is_dir():
                add_tree(native_assets, f"Codex runtime surface {slug}")

    declared_set = set(declared_dependencies)
    for ref in _frontmatter_refs(skill_md):
        raw = Path(ref)
        if raw.is_absolute():
            raise ValueError(f"declared behavior dependency must be relative: {ref}")
        if ref.startswith("plugins/"):
            candidate = repo_root / ref
        else:
            candidate = skill_dir / ref
        if not candidate.exists() and "/" not in ref and "." not in ref:
            candidate = plugin_root / "skills" / ref / "SKILL.md"
        if not candidate.exists() and context and not ref.startswith("plugins/"):
            # repo-root 配置の共有資産 (doc/notion-schema/*.schema.json など) を
            # skill 相対で書いた ref。run-skill-feedback は SKILL.md 本文で
            # 「repo-bundled 前提」と宣言済みだが、resolver が skill 相対しか
            # 試さないため missing 扱いになり、その 1 件で plan-live-trials が
            # plugin 全体に対して落ちていた。repo_root 内に収まることは
            # _contained() が引き続き保証する。
            repo_candidate = repo_root / ref
            if repo_candidate.exists():
                candidate = repo_candidate
        resolved = _contained(candidate, repo_root, ref)
        if context:
            try:
                relative_plugins = resolved.relative_to(repo_root / "plugins")
            except ValueError:
                relative_plugins = None
            if relative_plugins and relative_plugins.parts:
                referenced_plugin = relative_plugins.parts[0]
                if referenced_plugin not in {plugin_root.name, *declared_set}:
                    raise ValueError(
                        "cross-plugin behavior dependency is not declared in "
                        f"package-contract.depends_on: {referenced_plugin} ({ref})"
                    )
        if resolved.is_dir():
            add_tree(resolved, ref)
        elif resolved.is_file():
            add_file(resolved, ref)
        else:
            raise ValueError(f"unsupported behavior dependency: {ref}: {resolved}")

    return sorted(((label, path) for path, label in files.items()), key=lambda item: item[0])


_MANIFEST_SUFFIXES = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json")

# native plugin manifest のうち、被験 skill の挙動に一切効かないと言い切れるキー。
# ここに挙げたキーだけを digest から落とし、未知のキーは残す (fail-closed: 知らない
# キーは挙動かもしれない)。allowlist にすると新しいキーが digest に出ず、検査が
# 静かに素通りする。
#
# なぜ必要か: manifest は closure に生で入っている一方、build-plugin-release は
# plugin に内容変更があれば必ず version を bump する。よって「どんな変更でも
# version が動く」→「その plugin の全 skill の verdict が一斉に stale」になり、
# 再 trial の要求が挙動変更の signal ではなく release 作業の副作用として出ていた。
# 巻き添えで stale になった verdict は、本当に挙動が変わった verdict と区別が
# つかないので、検査としての意味が薄れる。
# 実在キーは name / version / description / author / dependencies / repository の 6 種。
# 落とすのは version だけに絞る。dependencies は boot が load する plugin 集合そのもの、
# name は manifest 検証と依存解決の鍵、description は plugin 選択の手掛かりであり、
# いずれも挙動に効く。author / repository は効かないが、動かないので巻き添えの原因に
# ならず、除外する実益が無い。denylist は短いほど素通りの余地が小さい。
_MANIFEST_NON_BEHAVIOR_KEYS: frozenset[str] = frozenset({"version"})


def behavior_projection(label: str, raw: bytes) -> bytes:
    """digest と差分一覧が共有するバイト列。manifest は挙動に効くキーだけを残す。

    壊れた manifest は raw に戻さず失敗する。未知のバイト列を黙って digest すると、
    読めない manifest の変更が stale に出なくなる。
    """
    if not label.endswith(_MANIFEST_SUFFIXES):
        return raw
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"plugin manifest read/parse error: {label}: {exc}") from exc
    if not isinstance(manifest, dict):
        return raw
    projected = {k: v for k, v in manifest.items() if k not in _MANIFEST_NON_BEHAVIOR_KEYS}
    return json.dumps(
        projected, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _behavior_bytes(label: str, path: Path) -> bytes:
    """digest へ与えるバイト列。manifest だけは挙動に効く投影へ正規化する。"""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        if label.endswith(_MANIFEST_SUFFIXES):
            raise ValueError(f"plugin manifest read/parse error: {path}: {exc}") from exc
        raise
    return behavior_projection(label, raw)


def changed_behavior_labels(
    skill_dir: Path,
    baseline_raw: dict[str, bytes | None],
    runtime: str = "claude",
) -> list[str]:
    """現在の閉包のうち、受領時の挙動投影と違う label を返す。

    ``baseline_raw`` の値 ``None`` は、その label が受領時に無かったことを表す。
    manifest の version だけが変わった label は返さない。受領時にあって現在の
    閉包から消えたファイルは、この関数には見えない。
    """
    drifted: list[str] = []
    for label, path in behavior_closure_files(skill_dir, runtime=runtime):
        if label not in baseline_raw:
            continue
        old = baseline_raw[label]
        new = path.read_bytes()
        if old is None or behavior_projection(label, old) != behavior_projection(label, new):
            drifted.append(label)
    return drifted


def git_baseline_bytes(repo: Path, commit: str, labels: list[str]) -> dict[str, bytes | None] | None:
    """``commit`` の blob を label ごとに読む。git が読めないときは None。"""
    if not labels:
        return {}
    proc = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=repo,
        input="".join(f"{commit}:{label}\n" for label in labels).encode(),
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    data = proc.stdout
    offset = 0
    found: dict[str, bytes | None] = {}
    for label in labels:
        newline = data.find(b"\n", offset)
        if newline < 0:
            return None
        header = data[offset:newline]
        offset = newline + 1
        if header.endswith(b" missing"):
            found[label] = None
            continue
        parts = header.split()
        if len(parts) != 3 or parts[1] != b"blob":
            return None
        try:
            size = int(parts[2])
        except ValueError:
            return None
        if offset + size > len(data):
            return None
        found[label] = data[offset:offset + size]
        offset += size + 1
    return found


def verdict_baseline_commit(repo: Path, verdict_path: Path) -> str | None:
    """verdict ファイルを最後に commit した revision。未追跡なら None。"""
    try:
        relative = verdict_path.resolve().relative_to(repo.resolve())
    except ValueError:
        return None
    proc = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", relative.as_posix()],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    commit = proc.stdout.strip()
    return commit or None


def closure_drift_labels(
    repo: Path, skill_dir: Path, commit: str, runtime: str = "claude",
) -> list[str] | None:
    """受領 commit のツリーと現在の挙動閉包の差分 label。git 不能なら None。"""
    labels = [
        label for label, _path in behavior_closure_files(skill_dir, runtime=runtime)
    ]
    baseline = git_baseline_bytes(repo, commit, labels)
    if baseline is None:
        return None
    return changed_behavior_labels(skill_dir, baseline, runtime=runtime)


def format_closure_drift(labels: list[str] | None, *, limit: int = 30) -> str:
    """差分 label の1行。空なら空文字。"""
    if not labels:
        return ""
    shown = labels[:limit]
    text = "挙動差分: " + ", ".join(shown)
    if len(labels) > limit:
        text += f" ほか{len(labels) - limit}件"
    return text


def format_stale_sha(recorded: object, current: str, labels: list[str] | None) -> str:
    """stale-sha 違反。label があるときだけ挙動ファイル名を足す。"""
    text = (
        f"stale-sha: 記録 {recorded} != 現在 {current} "
        "(被験 skill の挙動面が verdict 後に変更された — 再 trial 要)"
    )
    drift = format_closure_drift(labels)
    if drift:
        text += "。" + drift
    return text


def skill_dir_tree_sha(skill_dir: Path, runtime: str = "claude") -> str:
    """Declared behavior closure digest (legacy field name retained for compatibility)."""
    h = hashlib.sha256()
    for label, path in behavior_closure_files(skill_dir, runtime=runtime):
        h.update(label.encode("utf-8"))
        h.update(b"\0")
        h.update(_behavior_bytes(label, path))
        h.update(b"\0")
    return h.hexdigest()


_SCENARIO = _load_sibling("validate-live-trial-scenario-contract")
_BUDGET = _load_sibling("validate-live-trial-resource-budget")
_FLAG_PATTERN = _SCENARIO._FLAG_PATTERN
load_scenario = _SCENARIO.load_scenario
parse_observation_claims = _SCENARIO.parse_observation_claims
validate_evidence_claims = _SCENARIO.validate_evidence_claims
repo_relative_scenario_file = _SCENARIO.repo_relative_scenario_file
observation_coverage = _SCENARIO.observation_coverage
args_divergence = _SCENARIO.args_divergence
validate_task_contract = _SCENARIO.validate_task_contract
validate_invocation_contract = _SCENARIO.validate_invocation_contract
scenario_contract_blockers = _SCENARIO.scenario_contract_blockers
resource_budget = _BUDGET.resource_budget
transcript_token_usage = _BUDGET.transcript_token_usage
budget_violations = _BUDGET.budget_violations
poll_wall_usage = _BUDGET.poll_wall_usage


def blocked_cause_for(*, poll_exit: str | None, resource_violations: list[str]) -> str | None:
    """打切り原因を分ける。原因が特定できないときだけ呼出側が tmux 不在の文言を使う。"""
    causes: list[str] = []
    token = any(item.startswith("token-budget-exceeded:") for item in resource_violations)
    wall = any(item.startswith("wall-clock-exceeded:") for item in resource_violations)
    if poll_exit == "TOKEN_CAP" or token:
        causes.append("TOKEN_CAP: scenario の token 予算到達")
    if poll_exit == "HARD_CAP" or wall:
        causes.append("HARD_CAP: scenario の wall-clock 到達")
    if poll_exit == "TOKEN_UNMEASURED":
        causes.append("TOKEN_UNMEASURED: assistant usage が欠落/不正")
    if poll_exit == "STATE_CORRUPT":
        causes.append("STATE_CORRUPT: poll state が壊れて経過を保持できない")
    if poll_exit == "STALL":
        causes.append("STALL: 進捗停止で打ち切り")
    if not causes:
        return None
    return " / ".join(causes) + " (fail-closed)"


def derive_overall(*, launch: str, completion: str, goal_result: str | None,
                   nudge: int, gate: int, gate_kind: str, proof: bool,
                   requested_model: str, actual_model: list[str],
                   blocked: bool, blocked_cause: str | None = None) -> tuple[str, str, str | None]:
    """判定ロジック表 (SKILL.md) の機械実装。returns (goal_fit, verdict, downgrade_reason)。"""
    goal_fit = goal_result if goal_result else "NOT_EVALUATED"
    if blocked:
        return goal_fit, "BLOCKED", blocked_cause or "tmux 不在 / HARD_CAP 超過等の fail-closed"
    if launch == "FAIL":
        return goal_fit, "FAIL", None
    if completion == "FAIL":
        return goal_fit, "FAIL", None
    if proof and actual_model != [requested_model]:
        return goal_fit, "FAIL", (
            f"proof trial: actual_model {actual_model} != requested_model "
            f"[{requested_model}] (transcript 機械 gate)"
        )
    degrade: list[str] = []
    if goal_fit == "FAIL":
        degrade.append("goal-proxy 乖離 (完走するが目的を果たさない)")
    if nudge > 0:
        degrade.append(f"自走未達 (nudge={nudge} — 自動送信でも介入)")
    # gate 応答は 2 種ある。stall を解くための救済介入 (rescue) は自走未達だが、
    # 被験 skill が契約上要求する確認 gate (external mutation の人間確認等) への正規応答
    # (contractual) は、gate を通ること自体が受け入れ条件なので降格根拠にならない。
    # 契約上 gate を必須とする skill を rescue と同じ規則で裁くと、その skill は永久に PASS を
    # 取れない (gate 応答 0 での完走は guard が破れていることを意味する)。
    # ただし proof trial は「人手介入なし PASS」が受け入れ条件なので kind を問わず介入扱い。
    if gate > 0 and (proof or gate_kind != "contractual"):
        note = ("契約 gate だが proof trial は人手介入なしが受け入れ条件"
                if gate_kind == "contractual" else "自動送信でも介入")
        degrade.append(f"自走未達 (gate応答={gate}/{gate_kind} — {note})")
    if degrade:
        reason = " / ".join(degrade)
        # proof trial は「人手介入なし PASS」が受け入れ条件 — ⚠️ 相当も不合格
        return goal_fit, ("FAIL" if proof else "DEGRADED"), reason
    if goal_fit == "NOT_EVALUATED":
        return goal_fit, "DEGRADED", "goal 判定未実施 (fresh evaluator 未起動)"
    return goal_fit, "PASS", None


def validate_schema(doc, schema, path: str = "$") -> list[str]:
    """同梱 schema 用の最小 validator。

    type/enum/required/properties/additionalProperties/items/uniqueItems/
    pattern/minimum/minLength を扱う。
    """
    errs: list[str] = []
    types = schema.get("type")
    if types is not None:
        allowed = types if isinstance(types, list) else [types]
        ok = False
        for t in allowed:
            if (
                (t == "object" and isinstance(doc, dict))
                or (t == "array" and isinstance(doc, list))
                or (t == "string" and isinstance(doc, str))
                or (t == "integer" and isinstance(doc, int) and not isinstance(doc, bool))
                or (t == "number" and isinstance(doc, (int, float)) and not isinstance(doc, bool))
                or (t == "boolean" and isinstance(doc, bool))
                or (t == "null" and doc is None)
            ):
                ok = True
        if not ok:
            return [f"{path}: type {allowed} 不一致 (got {type(doc).__name__})"]
    if "enum" in schema and doc not in schema["enum"]:
        return [f"{path}: enum {schema['enum']} 外の値 {doc!r}"]
    if isinstance(doc, str):
        if "pattern" in schema and not re.search(schema["pattern"], doc):
            errs.append(f"{path}: pattern {schema['pattern']} 不一致")
        if "minLength" in schema and len(doc) < schema["minLength"]:
            errs.append(f"{path}: minLength {schema['minLength']} 未満")
    if isinstance(doc, int) and not isinstance(doc, bool) and "minimum" in schema:
        if doc < schema["minimum"]:
            errs.append(f"{path}: minimum {schema['minimum']} 未満")
    if isinstance(doc, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in doc:
                errs.append(f"{path}: required key '{key}' 欠落")
        if schema.get("additionalProperties") is False:
            for key in doc:
                if key not in props:
                    errs.append(f"{path}: additionalProperties false 違反 '{key}'")
        for key, sub in props.items():
            if key in doc:
                errs.extend(validate_schema(doc[key], sub, f"{path}.{key}"))
    if isinstance(doc, list):
        if schema.get("uniqueItems"):
            seen: set[str] = set()
            for item in doc:
                identity = json.dumps(
                    item,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                if identity in seen:
                    errs.append(f"{path}: uniqueItems 違反 {item!r}")
                    break
                seen.add(identity)
        if "items" in schema:
            for i, item in enumerate(doc):
                errs.extend(validate_schema(item, schema["items"], f"{path}[{i}]"))
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workdir", required=True, help="eval-log/<plugin>/<skill>/live-trial/<run-id>/")
    ap.add_argument("--target-skill", required=True, help="plugin:skill")
    ap.add_argument("--skill-dir", required=True, help="被験 skill のディレクトリ (tree sha 対象)")
    ap.add_argument("--runtime", choices=["claude", "codex"], default="claude")
    ap.add_argument("--native-run-state", default="", help="Codex controllerの収集済みturn台帳（workdir内）")
    ap.add_argument("--args", default="", dest="trial_args")
    ap.add_argument("--requested-model", default="")
    ap.add_argument("--session-id", default="", help="transcript 回収用 UUID")
    ap.add_argument("--transcript", default="", help="回収済み transcript のパス (session-id 探索より優先)")
    ap.add_argument(
        "--goal-seek-eval-root",
        default="",
        help="被験 skill が goal_seek 成果物を書いた eval-log directory",
    )
    ap.add_argument("--launch", required=True, choices=["PASS", "FAIL"])
    ap.add_argument("--completion", required=True, choices=["PASS", "FAIL"])
    ap.add_argument("--goal-result", default="", choices=["", "PASS", "FAIL"],
                    help="fresh evaluator の達成判定。未実施は省略 (--no-goal-eval 相当)")
    ap.add_argument(
        "--goal-evaluation",
        default="",
        help="fresh evaluator の JSON artifact (workdir 内・transcript digest 束縛)",
    )
    ap.add_argument("--blocker", action="append", default=[], help="goal 未達点 (複数可)")
    ap.add_argument("--nudge-count", type=int, default=0)
    ap.add_argument("--gate-response-count", type=int, default=0)
    ap.add_argument("--gate-kind", default="rescue", choices=["rescue", "contractual"],
                    help="gate 応答の種別。rescue=stall を解くための救済介入 (既定・降格対象)。"
                         "contractual=被験 skill が契約上要求する確認 gate への正規応答 "
                         "(例: external mutation の人間確認)。未指定は fail-closed に rescue 扱い")
    ap.add_argument("--proof", action="store_true", help="proof trial (model 一致の機械 gate を厳格適用)")
    ap.add_argument("--blocked", action="store_true", help="tmux 不在 / HARD_CAP 超過等の fail-closed 記録")
    ap.add_argument("--scenario-origin", default="synthetic", choices=["synthetic", "replay"])
    ap.add_argument("--scenario-id", default="",
                    help="criteria receipt と実走を束縛する stable scenario id (任意。指定時は --scenario-file 必須)")
    ap.add_argument("--scenario-file", default="",
                    help="required_observations の正本 (scenarios[] を持つ JSON)")
    ap.add_argument("--observation", action="append", default=[],
                    help="回収済み required_observation を N=<evidence ref> で指定 (複数可)")
    ap.add_argument("--tier", default="live", choices=["static", "fork", "live"])
    ap.add_argument("--downgrade-reason", default="")
    ap.add_argument("--permissions-mode", default=None)
    ap.add_argument("--boot-s", type=float, default=None)
    ap.add_argument("--poll-exit", default="")
    ap.add_argument("--poll-state", default="", help="scenario wall time の正本 poll-state.json")
    ap.add_argument("--wall-clock-s", type=float, default=None)
    ns = ap.parse_args(argv)

    backend = _load_sibling("live-trial-backend")
    if backend.deny_target_skill(ns.target_skill):
        print(f"[ERROR] DENYLIST: 被験 skill {ns.target_skill} は再帰遮断対象 "
              f"({sorted(backend.DENY_TARGET_SKILLS)})", file=sys.stderr)
        return 2

    workdir = Path(ns.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    skill_dir = Path(ns.skill_dir)
    if not (skill_dir / "SKILL.md").is_file():
        print(f"[ERROR] skill dir に SKILL.md がない: {skill_dir}", file=sys.stderr)
        return 1

    # contractual の申告を被験 skill 側の宣言へ接地させる。gate 応答が 0 なら区分に
    # 意味が無いので rescue へ正規化し、gate 応答があるのに根拠が無い contractual は
    # 受け入れ基準の自己申告による緩和なので fail-closed で拒否する。
    gate_kind = ns.gate_kind
    gate_evidence: list[str] = []
    if ns.gate_response_count == 0:
        gate_kind = "rescue"
    elif gate_kind == "contractual":
        gate_evidence = contract_gate_evidence(skill_dir / "SKILL.md")
        if not gate_evidence:
            print(
                f"[ERROR] --gate-kind contractual だが被験 skill {ns.target_skill} の "
                f"frontmatter に契約 gate の宣言が無い "
                f"(external_mutation_guard / allowed-tools の "
                f"{'|'.join(CONTRACT_GATE_TOOLS)})。"
                "宣言なき contractual は降格回避の自己申告になるため拒否する",
                file=sys.stderr,
            )
            return 2

    # transcript 回収 (一次証拠)
    projects_dir = os.environ.get(
        "CLAUDE_PROJECTS_DIR", str(Path.home() / ".claude" / "projects")
    )
    src: Path | None = Path(ns.transcript) if ns.transcript else None
    if src is None and ns.session_id and ns.runtime == "claude":
        src = find_transcript(projects_dir, ns.session_id)
    transcript_dst: Path | None = None
    if src is not None and src.is_file():
        transcript_dst = workdir / "transcript.jsonl"
        if src.resolve() != transcript_dst.resolve():
            shutil.copyfile(src, transcript_dst)

    actual_model = extract_models(transcript_dst, runtime=ns.runtime) if transcript_dst else []
    claude_version = extract_claude_version(transcript_dst) if transcript_dst and ns.runtime == "claude" else None
    codex_info = (
        _load_sibling("extract-codex-transcript").inspect_transcript(
            transcript_dst, skill_dir=skill_dir, target_skill=ns.target_skill
        ) if transcript_dst and ns.runtime == "codex" else None
    )
    native_metadata, native_metadata_errors = native_run_metadata(
        workdir, Path(ns.native_run_state) if ns.native_run_state else None,
        codex_info, nudge=ns.nudge_count, gate=ns.gate_response_count,
    ) if ns.runtime == "codex" else ({}, [])
    transcript_sha = sha256_file(transcript_dst) if transcript_dst else None
    transcript_layer = "jsonl" if transcript_dst else "tui"

    invoked_skills = extract_skill_invocations(
        transcript_dst, runtime=ns.runtime, skill_dir=skill_dir, target_skill=ns.target_skill
    ) if transcript_dst else []

    goal_result = ns.goal_result or None
    blockers = list(ns.blocker)
    goal_evaluation, goal_evaluation_errors = load_goal_evaluation(
        workdir,
        Path(ns.goal_evaluation) if ns.goal_evaluation else None,
        transcript_sha,
    )
    if goal_evaluation is not None:
        if goal_result is not None and goal_result != goal_evaluation["result"]:
            goal_evaluation_errors.append(
                "--goal-result does not match bound goal evaluation artifact"
            )
        goal_result = goal_evaluation["result"]
        blockers.extend(goal_evaluation["blockers"])
    if goal_evaluation_errors and not ns.blocked:
        goal_result = "FAIL"
        blockers.extend(goal_evaluation_errors)
    elif goal_result is None and not blockers:
        blockers = ["goal 判定未実施 (trial が完走せず fresh evaluator を起動できない)"]

    # 起動の機械 gate: transcript が取れているのに被験 skill の Skill 呼出しが1件も無ければ
    # launch は PASS になりえない。orchestrator の --launch PASS 自己申告を上書きする。
    launch = ns.launch
    if transcript_dst and not ns.blocked and ns.target_skill not in invoked_skills:
        launch = "FAIL"
        invocation_label = "native skill適用と本文Read" if ns.runtime == "codex" else "Skill 呼出し"
        blockers.append(
            f"被験 skill {ns.target_skill} の {invocation_label}が transcript に0件 "
            f"(実行された Skill: {invoked_skills or 'なし'})。skill を起動せず script を"
            "直接実行した実走は受け入れ検証にならない"
        )
    if ns.runtime == "codex" and not ns.blocked:
        if codex_info is None or codex_info["format_errors"] or codex_info["activation_errors"] or not actual_model or not codex_info["cli_version"]:
            launch = "FAIL"
            blockers.append("Codex native transcript/model/CLI-versionの実測が不足または形式不一致")
        if codex_info is None or not codex_info["completed"]:
            ns.completion = "FAIL"
            blockers.append("Codex native実turnまたは子agentが未完了")
        if native_metadata_errors:
            goal_result = "FAIL"
            blockers.extend(native_metadata_errors)

    # 配線の機械 gate: ファイル名の transcript 言及ではなく、成果物の実体・必須キー・
    # original_goal/hash の整合を検証する。fresh evaluator の PASS より機械判定を優先する。
    goal_seek_evidence = validate_goal_seek_evidence(
        skill_dir,
        Path(ns.goal_seek_eval_root) if ns.goal_seek_eval_root else None,
    )
    wiring_violations = list(goal_seek_evidence.get("violations") or [])
    missing_labels = {
        "goal-spec.json": "goal-spec-missing",
        "progress.json": "progress-missing",
        "intermediate.jsonl": "intermediate-missing",
    }
    missing_wiring = [
        artifact
        for artifact in GOAL_SEEK_ARTIFACTS
        if any(missing_labels[artifact] in value for value in wiring_violations)
    ]
    if wiring_violations and not ns.blocked:
        goal_result = "FAIL"
        blockers.append(
            "ゴールシーク配線の実体検証に失敗: " + " | ".join(wiring_violations)
        )

    # scenario 契約の機械 gate: scenario_id を名乗る trial は required_observations の
    # 回収状況を開示する。scenario_id の一致だけでは「契約が要求する観測を一つも
    # 取っていない run」も PASS になる (HarnessHub-dyxr)。
    scenario_contract: dict | None = None
    resource_violations: list[str] = []
    if ns.scenario_id and not ns.scenario_file:
        print(
            "[ERROR] --scenario-id を名乗る trial は --scenario-file が必須 "
            "(required_observations の回収を検査できないため)",
            file=sys.stderr,
        )
        return 2
    if ns.scenario_file:
        if not ns.scenario_id:
            print("[ERROR] --scenario-file には --scenario-id が必須", file=sys.stderr)
            return 2
        try:
            scenario = load_scenario(Path(ns.scenario_file), ns.scenario_id)
            recorded_scenario_file = repo_relative_scenario_file(ns.scenario_file)
            required_observations = list(scenario["required_observations"])
            claims = parse_observation_claims(ns.observation, len(required_observations))
            claims = validate_evidence_claims(workdir, claims)
        except ValueError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 2
        observed, unobserved = observation_coverage(required_observations, claims)
        budget = resource_budget(scenario)
        token_usage = transcript_token_usage(transcript_dst, runtime=ns.runtime)
        try:
            wall_usage = poll_wall_usage(
                workdir, Path(ns.poll_state) if ns.poll_state else None
            )
            measured_wall_clock_s = wall_usage["wall_clock_s"]
        except ValueError as exc:
            wall_usage = {
                "wall_clock_s": None,
                "poll_state_ref": None,
                "poll_state_sha256": None,
            }
            measured_wall_clock_s = None
            blockers.append(f"poll-state-invalid:{exc}")
        resource_violations = budget_violations(
            budget, wall_clock_s=measured_wall_clock_s, token_usage=token_usage
        )
        scenario_contract = {
            "scenario_file": recorded_scenario_file,
            "scenario_id": ns.scenario_id,
            "required_observations": required_observations,
            "observed": observed,
            "unobserved": unobserved,
            "args_divergence": args_divergence(
                scenario.get("task_args_template", ""), ns.trial_args
            ),
            "task_contract": validate_task_contract(scenario, workdir / "task.md"),
            "invocation_contract": validate_invocation_contract(scenario, invoked_skills),
            "resource_budget": budget,
            "resource_usage": {
                **wall_usage,
                "tokens": token_usage,
                "violations": resource_violations,
            },
        }
        contract_blockers = scenario_contract_blockers(scenario_contract)
        if contract_blockers and not ns.blocked:
            goal_result = "FAIL"
            blockers.extend(contract_blockers)

        if resource_violations and not ns.blocked:
            ns.completion = "FAIL"

    goal_fit, verdict, auto_reason = derive_overall(
        launch=launch, completion=ns.completion, goal_result=goal_result,
        nudge=ns.nudge_count, gate=ns.gate_response_count,
        gate_kind=gate_kind, proof=ns.proof,
        requested_model=ns.requested_model, actual_model=actual_model,
        blocked=ns.blocked,
        blocked_cause=blocked_cause_for(
            poll_exit=ns.poll_exit or None, resource_violations=resource_violations,
        ) if ns.blocked else None,
    )
    doc = {
        "target_skill": ns.target_skill,
        "args": ns.trial_args,
        "requested_model": ns.requested_model,
        "actual_model": actual_model,
        "nudge_count": ns.nudge_count,
        "gate_response_count": ns.gate_response_count,
        "gate_kind": gate_kind,
        # 免除の根拠を verdict へ焼き付ける。lint と後続 reviewer が「誰の宣言に
        # 接地した contractual か」を verdict 単体で辿れる。
        **({"gate_contract_evidence": gate_evidence} if gate_evidence else {}),
        "goal_verdict": {
            "result": goal_result or "FAIL",
            "blockers": blockers,
        },
        "goal_evaluation": goal_evaluation,
        "invoked_skills": invoked_skills,
        "missing_goal_seek_artifacts": missing_wiring,
        "goal_seek_evidence_violations": wiring_violations,
        "overall": {
            "launch": launch,
            "completion": ns.completion,
            "goal_fit": goal_fit,
            "verdict": verdict,
        },
        "skill_dir_tree_sha": skill_dir_tree_sha(skill_dir, runtime=ns.runtime),
        "transcript_sha256": transcript_sha,
        "scenario_origin": ns.scenario_origin,
        "environment": {
            "claude_version": claude_version,
            "tmux": backend.tmux_available() if ns.runtime == "claude" else False,
            "transcript_layer": transcript_layer,
            "permissions_mode": ns.permissions_mode or ("workspace-write" if ns.runtime == "codex" else "bypassPermissions"),
            **({"runtime": "codex", "codex_version": codex_info["cli_version"] if codex_info else None,
                "native_transcript_format": "codex-rollout-jsonl",
                "native_sandbox_contexts": codex_info["sandbox_contexts"] if codex_info else [],
                **native_metadata} if ns.runtime == "codex" else {}),
        },
        "tier": ns.tier,
        "downgrade_reason": ns.downgrade_reason or auto_reason,
        "timeline": {
            "boot_s": ns.boot_s,
            "poll_exit": ns.poll_exit or None,
            "wall_clock_s": (
                scenario_contract["resource_usage"]["wall_clock_s"]
                if scenario_contract is not None else ns.wall_clock_s
            ),
        },
    }
    if ns.scenario_id:
        doc["scenario_id"] = ns.scenario_id
    if scenario_contract is not None:
        doc["scenario_contract"] = scenario_contract

    schema = json.loads(_schema_path().read_text(encoding="utf-8"))
    errs = validate_schema(doc, schema)
    # These cross-field checks are explicit because the small validator does not
    # implement JSON Schema if/then. Preserve a truthful FAIL/BLOCKED artifact,
    # while forbidding an inconsistent runtime record from claiming PASS.
    runtime_errors = validate_runtime_evidence(doc, transcript_dst, skill_dir)
    if runtime_errors and doc["overall"]["verdict"] == "PASS":
        errs.extend(runtime_errors)
    if errs:
        print("[ERROR] verdict が schema 不適合 (書き出し中止):", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1

    out = workdir / "verdict.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"VERDICT: {doc['overall']['verdict']} (launch={doc['overall']['launch']} completion={ns.completion} "
          f"goal_fit={goal_fit} nudge={ns.nudge_count} "
          f"gate={ns.gate_response_count}/{gate_kind})")
    print(f"WROTE: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
