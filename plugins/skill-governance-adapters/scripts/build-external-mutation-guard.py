#!/usr/bin/env python3
# /// script
# name: build-external-mutation-guard
# purpose: Bind an external mutation to a preview receipt, an actual UserPromptSubmit confirmation or intent event, and an exact argv consumer.
# inputs:
#   - argv: preview | hook-confirm | authorize | authorize-intent | cancel | execute | pretool
#   - stdin: Claude hook JSON for hook-confirm/pretool
# outputs:
#   - stdout: sealed receipt metadata or official PreToolUse deny JSON
# contexts: [A, C, E]
# network: false
# write-scope: project/.artifact-delivery/external-mutation only; execute runs only the argv bound by receipts
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Executable preview -> user confirmation -> authorization -> mutation guard."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


CONTRACT_ID = "external-mutation-guard-v1"
SCHEMA_VERSION = 1
STATE_REL = Path(".artifact-delivery/external-mutation")
KEY_NAME = ".guard-key"
TTL_SECONDS = 900
CONFIRM_RE = re.compile(r"^CONFIRM EXTERNAL MUTATION ([0-9A-F]{24})$")
INTENT_KIND = "intent"
# 人間の自然文リクエストで自動承認してよい操作クラス。取り消し可能な範囲だけを列挙する。
AUTO_GRANT_CLASSES = frozenset({"github-pr-write", "github-issue-write", "beads-issue-write"})
GH_PR_AUTO_VERBS = frozenset({"create", "edit", "comment", "ready"})
GH_ISSUE_AUTO_VERBS = frozenset({"create", "edit", "comment", "close", "reopen"})
BD_AUTO_VERBS = frozenset({"create", "update", "close", "reopen"})
# 自然文の意図宣言。UserPromptSubmit の実イベントでのみ評価され、付与クラスを限定する。
INTENT_PATTERNS: tuple[tuple[re.Pattern[str], frozenset[str]], ...] = (
    (
        re.compile(
            # \bPR\b は使えない: Python の \w は CJK を含むため "PRを出して" で
            # 単語境界が成立せず落ちる。境界判定を ASCII 英字だけに限定する。
            r"(?:プルリク(?:エスト)?|プル\s*リクエスト|pull\s*request|(?<![A-Za-z])PR(?![A-Za-z]))"
            r"[^\n]{0,40}?"
            r"(?:出し|出す|出せ|作成|作って|作る|上げ|開い|投げ|送っ|create|open|raise|submit)",
            re.I,
        ),
        frozenset({"github-pr-write"}),
    ),
    (
        re.compile(
            r"(?:issue|イシュー|課題|チケット)"
            r"[^\n]{0,40}?"
            r"(?:立て|作成|作って|作る|閉じ|クローズ|更新|create|close|reopen|update)",
            re.I,
        ),
        frozenset({"github-issue-write", "beads-issue-write"}),
    ),
)
ENTRYPOINT_RE = re.compile(r"^plugin:[a-z0-9][a-z0-9-]*/skills/[a-z0-9][a-z0-9-]*/SKILL\.md$")
PYTHON_RE = re.compile(r"^python3(?:\.\d+)?$")
RUNNER_NAME = "build-external-mutation-guard.py"
SHELL_CONTROL_TOKENS = frozenset({";", "&", "&&", "|", "||", "<", ">", "<<", ">>", "(", ")"})
CANONICAL_ACTION_FLAGS = {
    "preview": frozenset(
        {
            "--project-root",
            "--entrypoint-ref",
            "--target-scope",
            "--diff-summary",
            "--side-effect-summary",
            "--command-json",
        }
    ),
    "authorize": frozenset(
        {"--project-root", "--preview-receipt", "--confirmation-receipt"}
    ),
    "authorize-intent": frozenset(
        {"--project-root", "--preview-receipt", "--intent-receipt"}
    ),
    "execute": frozenset(
        {"--project-root", "--authorization-receipt", "--command-json"}
    ),
    "cancel": frozenset({"--project-root", "--preview-receipt"}),
}
DIRECT_MUTATION_PATTERNS = (
    re.compile(r"\bcurl\b[^\n]*(?:-X|--request)\s*(?:POST|PUT|PATCH|DELETE)\b", re.I),
    re.compile(r"\bcurl\b[^\n]*(?:--data(?:-raw|-binary)?|-d)\s", re.I),
    re.compile(r"\bgh\s+(?:issue|pr)\s+(?:create|edit|close|reopen|merge|comment)\b", re.I),
    re.compile(r"\bgh\s+api\b[^\n]*(?:-X|--method)\s*(?:POST|PUT|PATCH|DELETE)\b", re.I),
    re.compile(r"\bbd\s+(?:create|update|close|reopen|delete|dep\s+add)\b", re.I),
    re.compile(r"\b(?:send-campaign|publish-notion-page|notion-submit-improvement)\.py\b", re.I),
    re.compile(r"\bgh-bridge\.py\b[^\n]*\bapply\b", re.I),
    re.compile(r"\bintake_publish_pipeline\.py\b", re.I),
    re.compile(r"\bsetup-send-log-db\.py\b[^\n]*--apply\b", re.I),
)


class GuardError(ValueError):
    """Fail-closed receipt or execution contract violation."""


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _ordered_output(value: dict[str, Any]) -> str:
    """Preserve human-review field order; receipt canonicalization remains sorted."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _command(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise GuardError(f"command-json is invalid JSON: {exc}") from exc
    if (
        not isinstance(parsed, list)
        or not parsed
        or not all(isinstance(item, str) and item for item in parsed)
    ):
        raise GuardError("command-json must be a non-empty JSON string array")
    return parsed


def _command_sha256(argv: list[str]) -> str:
    return _sha256_bytes(_compact(argv).encode("utf-8"))


def _action_class(argv: list[str]) -> str | None:
    """Classify argv into an auto-grantable class; unknown or irreversible argv stays None."""
    program = Path(argv[0]).name
    rest = argv[1:]
    if program == "gh" and len(rest) >= 2:
        surface, verb = rest[0], rest[1]
        if surface == "pr" and verb in GH_PR_AUTO_VERBS:
            return "github-pr-write"
        if surface == "issue" and verb in GH_ISSUE_AUTO_VERBS:
            return "github-issue-write"
        return None
    if program == "bd" and rest:
        if rest[0] in BD_AUTO_VERBS:
            return "beads-issue-write"
        if rest[0] == "dep" and len(rest) >= 2 and rest[1] == "add":
            return "beads-issue-write"
    return None


def _intent_classes(prompt: str) -> frozenset[str]:
    granted: set[str] = set()
    for pattern, classes in INTENT_PATTERNS:
        if pattern.search(prompt):
            granted |= set(classes)
    return frozenset(granted & AUTO_GRANT_CLASSES)


def _review_text(value: str, *, name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise GuardError(f"{name} must be non-empty")
    if len(normalized.encode("utf-8")) > 2048:
        raise GuardError(f"{name} exceeds 2048 UTF-8 bytes")
    return normalized


def _project_root(value: str) -> Path:
    try:
        root = Path(value).expanduser().resolve(strict=True)
    except OSError as exc:
        raise GuardError(f"project root does not exist: {value}") from exc
    if not root.is_dir():
        raise GuardError(f"project root is not a directory: {root}")
    return root


def _state_dir(root: Path, *, create: bool) -> Path:
    state = root / STATE_REL
    if create:
        state.mkdir(parents=True, exist_ok=True)
        os.chmod(state, 0o700)
    try:
        resolved = state.resolve(strict=True)
    except OSError as exc:
        raise GuardError(f"guard state is unavailable: {state}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GuardError("guard state escapes project root") from exc
    return resolved


def _key(state: Path, *, create: bool) -> bytes:
    path = state / KEY_NAME
    if create and not path.exists():
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(secrets.token_bytes(32))
    try:
        value = path.read_bytes()
    except OSError as exc:
        raise GuardError("guard key is unavailable") from exc
    if len(value) != 32:
        raise GuardError("guard key is invalid")
    return value


def _seal(body: dict[str, Any], key: bytes) -> str:
    unsigned = {name: value for name, value in body.items() if name != "seal"}
    return hmac.new(key, _compact(unsigned).encode("utf-8"), hashlib.sha256).hexdigest()


def _write_receipt(state: Path, name: str, body: dict[str, Any], key: bytes) -> Path:
    destination = state / name
    if destination.exists():
        raise GuardError(f"receipt already exists: {destination.name}")
    document = {**body, "seal": _seal(body, key)}
    descriptor, temporary = tempfile.mkstemp(prefix=f".{name}.", dir=state)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def _write_once(state: Path, name: str, body: dict[str, Any], key: bytes) -> Path:
    """Atomically create a sealed claim; an existing claim is never replaced."""
    destination = state / name
    document = {**body, "seal": _seal(body, key)}
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise GuardError("preview and confirmation were already consumed by authorization") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        # A partially written O_EXCL claim remains fail-closed and cannot be replayed.
        raise
    return destination


def _receipt(state: Path, raw_path: str, expected_kind: str, key: bytes) -> tuple[Path, dict[str, Any]]:
    try:
        path = Path(raw_path).expanduser().resolve(strict=True)
        path.relative_to(state)
    except (OSError, ValueError) as exc:
        raise GuardError("receipt path is outside canonical guard state") from exc
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardError(f"receipt is unreadable: {path}") from exc
    if not isinstance(document, dict):
        raise GuardError("receipt root must be an object")
    if document.get("contract_id") != CONTRACT_ID or document.get("schema_version") != SCHEMA_VERSION:
        raise GuardError("receipt contract identity drift")
    if document.get("kind") != expected_kind:
        raise GuardError(f"expected {expected_kind} receipt")
    seal = document.get("seal")
    if not isinstance(seal, str) or not hmac.compare_digest(seal, _seal(document, key)):
        raise GuardError("receipt seal mismatch; receipt may be tampered")
    expires_at = document.get("expires_at")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        raise GuardError("receipt expired")
    return path, document


def _base(kind: str, receipt_id: str, *, now: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "kind": kind,
        "receipt_id": receipt_id,
        "issued_at": now,
        # Second resolution cannot order two receipts issued inside the same second.
        "issued_at_ns": time.time_ns(),
        "expires_at": now + TTL_SECONDS,
    }


def _issued_ns(receipt: dict[str, Any]) -> int:
    value = receipt.get("issued_at_ns")
    if isinstance(value, int):
        return value
    return int(receipt["issued_at"]) * 1_000_000_000


def preview(args: argparse.Namespace) -> dict[str, Any]:
    root = _project_root(args.project_root)
    state = _state_dir(root, create=True)
    key = _key(state, create=True)
    argv = _command(args.command_json)
    if not ENTRYPOINT_RE.fullmatch(args.entrypoint_ref):
        raise GuardError("entrypoint-ref must be a canonical plugin SKILL.md ref")
    target_scope = _review_text(args.target_scope, name="target-scope")
    diff_summary = _review_text(args.diff_summary, name="diff-summary")
    side_effect_summary = _review_text(args.side_effect_summary, name="side-effect-summary")
    now = int(time.time())
    receipt_id = uuid.uuid4().hex
    challenge = secrets.token_hex(12).upper()
    action_class = _action_class(argv)
    body = {
        **_base("preview", receipt_id, now=now),
        "entrypoint_ref": args.entrypoint_ref,
        "target_scope": target_scope,
        "command_argv": argv,
        "command_sha256": _command_sha256(argv),
        "action_class": action_class,
        "diff_summary": diff_summary,
        "side_effect_summary": side_effect_summary,
        "challenge_sha256": _sha256_bytes(challenge.encode("ascii")),
        "status": "pending-user-confirmation",
    }
    path = _write_receipt(state, f"preview-{receipt_id}.json", body, key)
    auto_grantable = action_class in AUTO_GRANT_CLASSES
    instruction = f"Reply exactly: CONFIRM EXTERNAL MUTATION {challenge}"
    if auto_grantable:
        instruction = (
            f"A live intent grant covering {action_class} authorizes this via authorize-intent; "
            f"otherwise reply exactly: CONFIRM EXTERNAL MUTATION {challenge}"
        )
    return {
        "contract_id": CONTRACT_ID,
        "status": "preview-created",
        "receipt_path": str(path),
        "receipt_sha256": _sha256_file(path),
        "target_scope": target_scope,
        "command_argv": argv,
        "action_class": action_class,
        "auto_grantable": auto_grantable,
        "diff_summary": diff_summary,
        "side_effect_summary": side_effect_summary,
        "challenge": challenge,
        "user_instruction": instruction,
    }


def _read_hook_payload() -> dict[str, Any]:
    try:
        value = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def hook_confirm() -> dict[str, Any] | None:
    payload = _read_hook_payload()
    if payload.get("hook_event_name") not in {None, "UserPromptSubmit"}:
        return None
    prompt = payload.get("prompt")
    cwd = payload.get("cwd")
    session_id = payload.get("session_id")
    if not isinstance(prompt, str) or not isinstance(cwd, str) or not isinstance(session_id, str):
        return None
    stripped = prompt.strip()
    root = _project_root(cwd)
    matched = CONFIRM_RE.fullmatch(stripped)
    if matched is not None:
        return _confirm_challenge(root, stripped, session_id, matched.group(1))
    granted = _intent_classes(stripped)
    if not granted:
        return None
    return _grant_intent(root, stripped, session_id, granted)


def _user_event_id(session_id: str, prompt: str) -> str:
    return _sha256_bytes(f"{session_id}\0{prompt}".encode("utf-8"))


def _confirm_challenge(
    root: Path, prompt: str, session_id: str, challenge: str
) -> dict[str, Any]:
    """Bind a typed challenge to its single live preview.

    A challenge that matches no live preview creates no receipt and does not block the
    prompt: refusing the user's message buys no safety and strands the session.
    """
    unmatched = {
        "contract_id": CONTRACT_ID,
        "status": "confirmation-unmatched",
        "detail": "no live preview matches this challenge; it may have expired or been consumed",
    }
    try:
        state = _state_dir(root, create=False)
        key = _key(state, create=False)
    except GuardError:
        return unmatched
    challenge_hash = _sha256_bytes(challenge.encode("ascii"))
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(state.glob("preview-*.json")):
        try:
            loaded_path, receipt = _receipt(state, str(path), "preview", key)
        except GuardError:
            continue
        if receipt.get("challenge_sha256") == challenge_hash:
            candidates.append((loaded_path, receipt))
    if len(candidates) != 1:
        return unmatched
    preview_path, preview_receipt = candidates[0]
    now = int(time.time())
    receipt_id = uuid.uuid4().hex
    body = {
        **_base("confirmation", receipt_id, now=now),
        "preview_receipt_id": preview_receipt["receipt_id"],
        "preview_receipt_sha256": _sha256_file(preview_path),
        "producer": "claude-code-user-prompt-submit",
        "user_event_id": _user_event_id(session_id, prompt),
        "decision": "confirm",
    }
    path = _write_receipt(state, f"confirmation-{receipt_id}.json", body, key)
    return {
        "contract_id": CONTRACT_ID,
        "status": "confirmation-created",
        "receipt_path": str(path),
        "receipt_sha256": _sha256_file(path),
    }


def _grant_intent(
    root: Path, prompt: str, session_id: str, granted: frozenset[str]
) -> dict[str, Any]:
    """Seal a single-use grant proving a human asked for this class of mutation."""
    state = _state_dir(root, create=True)
    key = _key(state, create=True)
    now = int(time.time())
    receipt_id = uuid.uuid4().hex
    body = {
        **_base(INTENT_KIND, receipt_id, now=now),
        "granted_classes": sorted(granted),
        "producer": "claude-code-user-prompt-submit",
        "user_event_id": _user_event_id(session_id, prompt),
        "prompt_excerpt": " ".join(prompt.split())[:200],
        "decision": "confirm-by-intent",
    }
    path = _write_receipt(state, f"{INTENT_KIND}-{receipt_id}.json", body, key)
    return {
        "contract_id": CONTRACT_ID,
        "status": "intent-granted",
        "receipt_path": str(path),
        "receipt_sha256": _sha256_file(path),
        "granted_classes": sorted(granted),
    }


def authorize(args: argparse.Namespace) -> dict[str, Any]:
    root = _project_root(args.project_root)
    state = _state_dir(root, create=False)
    key = _key(state, create=False)
    preview_path, preview_receipt = _receipt(state, args.preview_receipt, "preview", key)
    confirmation_path, confirmation_receipt = _receipt(
        state, args.confirmation_receipt, "confirmation", key
    )
    if (
        confirmation_receipt.get("preview_receipt_id") != preview_receipt["receipt_id"]
        or confirmation_receipt.get("preview_receipt_sha256") != _sha256_file(preview_path)
    ):
        raise GuardError("confirmation receipt is not bound to the supplied preview receipt")
    return _seal_authorization(
        state,
        key,
        preview_path,
        preview_receipt,
        confirmation_path,
        confirmation_receipt,
        confirmation_kind="confirmation",
    )


def authorize_intent(args: argparse.Namespace) -> dict[str, Any]:
    """Authorize an auto-grantable preview against a live human intent grant."""
    root = _project_root(args.project_root)
    state = _state_dir(root, create=False)
    key = _key(state, create=False)
    preview_path, preview_receipt = _receipt(state, args.preview_receipt, "preview", key)
    intent_path, intent_receipt = _receipt(state, args.intent_receipt, INTENT_KIND, key)
    action_class = preview_receipt.get("action_class")
    if action_class not in AUTO_GRANT_CLASSES:
        raise GuardError(
            "preview action class is not auto-grantable; use the typed confirmation flow"
        )
    granted = intent_receipt.get("granted_classes")
    if not isinstance(granted, list) or action_class not in granted:
        raise GuardError("intent grant does not cover the preview action class")
    if _issued_ns(intent_receipt) > _issued_ns(preview_receipt):
        raise GuardError("preview predates the intent grant; the user request must come first")
    _write_once(
        state,
        f"intent-claim-{intent_receipt['receipt_id']}.json",
        {
            "contract_id": CONTRACT_ID,
            "schema_version": SCHEMA_VERSION,
            "kind": "intent-claim",
            "intent_receipt_id": intent_receipt["receipt_id"],
            "intent_receipt_sha256": _sha256_file(intent_path),
            "preview_receipt_id": preview_receipt["receipt_id"],
            "claimed_at": int(time.time()),
        },
        key,
    )
    return _seal_authorization(
        state,
        key,
        preview_path,
        preview_receipt,
        intent_path,
        intent_receipt,
        confirmation_kind=INTENT_KIND,
    )


def _seal_authorization(
    state: Path,
    key: bytes,
    preview_path: Path,
    preview_receipt: dict[str, Any],
    confirmation_path: Path,
    confirmation_receipt: dict[str, Any],
    *,
    confirmation_kind: str,
) -> dict[str, Any]:
    now = int(time.time())
    preview_sha256 = _sha256_file(preview_path)
    confirmation_sha256 = _sha256_file(confirmation_path)
    _write_once(
        state,
        f"authorization-claim-preview-{preview_receipt['receipt_id']}.json",
        {
            "contract_id": CONTRACT_ID,
            "schema_version": SCHEMA_VERSION,
            "kind": "authorization-claim",
            "preview_receipt_id": preview_receipt["receipt_id"],
            "preview_receipt_sha256": preview_sha256,
            "confirmation_receipt_id": confirmation_receipt["receipt_id"],
            "confirmation_receipt_sha256": confirmation_sha256,
            "claimed_at": now,
        },
        key,
    )
    receipt_id = uuid.uuid4().hex
    body = {
        **_base("authorization", receipt_id, now=now),
        "preview_receipt_id": preview_receipt["receipt_id"],
        "preview_receipt_sha256": preview_sha256,
        "confirmation_receipt_id": confirmation_receipt["receipt_id"],
        "confirmation_receipt_sha256": confirmation_sha256,
        "confirmation_receipt_kind": confirmation_kind,
        "entrypoint_ref": preview_receipt["entrypoint_ref"],
        "target_scope": preview_receipt["target_scope"],
        "command_sha256": preview_receipt["command_sha256"],
        "status": "authorized-once",
    }
    path = _write_receipt(state, f"authorization-{receipt_id}.json", body, key)
    return {
        "contract_id": CONTRACT_ID,
        "status": "authorized",
        "receipt_path": str(path),
        "receipt_sha256": _sha256_file(path),
        "confirmation_receipt_kind": confirmation_kind,
    }


def cancel(args: argparse.Namespace) -> dict[str, Any]:
    """Resolve a preview without executing it so pending guard context stops blocking Bash."""
    root = _project_root(args.project_root)
    state = _state_dir(root, create=False)
    key = _key(state, create=False)
    preview_path, preview_receipt = _receipt(state, args.preview_receipt, "preview", key)
    now = int(time.time())
    receipt_id = uuid.uuid4().hex
    path = _write_receipt(
        state,
        f"cancellation-preview-{preview_receipt['receipt_id']}.json",
        {
            **_base("cancellation", receipt_id, now=now),
            "preview_receipt_id": preview_receipt["receipt_id"],
            "preview_receipt_sha256": _sha256_file(preview_path),
            "status": "cancelled",
        },
        key,
    )
    return {
        "contract_id": CONTRACT_ID,
        "status": "cancelled",
        "receipt_path": str(path),
        "receipt_sha256": _sha256_file(path),
    }


def execute(args: argparse.Namespace) -> int:
    root = _project_root(args.project_root)
    state = _state_dir(root, create=False)
    key = _key(state, create=False)
    authorization_path, authorization = _receipt(
        state, args.authorization_receipt, "authorization", key
    )
    argv = _command(args.command_json)
    if authorization.get("command_sha256") != _command_sha256(argv):
        raise GuardError("execute command digest differs from authorized preview")
    preview_path = state / f"preview-{authorization['preview_receipt_id']}.json"
    confirmation_kind = authorization.get("confirmation_receipt_kind", "confirmation")
    if confirmation_kind not in {"confirmation", INTENT_KIND}:
        raise GuardError("authorization names an unknown confirmation receipt kind")
    confirmation_path = (
        state / f"{confirmation_kind}-{authorization['confirmation_receipt_id']}.json"
    )
    if _sha256_file(preview_path) != authorization.get("preview_receipt_sha256"):
        raise GuardError("preview receipt changed after authorization")
    if _sha256_file(confirmation_path) != authorization.get("confirmation_receipt_sha256"):
        raise GuardError("confirmation receipt changed after authorization")
    consumed = state / f"consumed-{authorization['receipt_id']}.json"
    try:
        descriptor = os.open(consumed, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise GuardError("authorization receipt was already consumed") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "authorization_receipt_sha256": _sha256_file(authorization_path),
                "consumed_at": int(time.time()),
            },
            handle,
            sort_keys=True,
        )
        handle.write("\n")
    completed = subprocess.run(argv, cwd=root, text=True, capture_output=True, shell=False, check=False)
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    if completed.returncode == 0:
        now = int(time.time())
        completion_id = uuid.uuid4().hex
        _write_receipt(
            state,
            f"completion-preview-{authorization['preview_receipt_id']}.json",
            {
                **_base("completion", completion_id, now=now),
                "preview_receipt_id": authorization["preview_receipt_id"],
                "authorization_receipt_id": authorization["receipt_id"],
                "authorization_receipt_sha256": _sha256_file(authorization_path),
                "status": "executed-successfully",
            },
            key,
        )
    return completed.returncode


def _canonical_guard_action(command: str) -> str | None:
    """Return the action only when the entire shell command is one canonical guard call."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None
    if len(tokens) < 3 or any(token in SHELL_CONTROL_TOKENS for token in tokens):
        return None
    if not PYTHON_RE.fullmatch(Path(tokens[0]).name) or Path(tokens[1]).name != RUNNER_NAME:
        return None
    action = tokens[2]
    expected_flags = CANONICAL_ACTION_FLAGS.get(action)
    rest = tokens[3:]
    if expected_flags is None or len(rest) != 2 * len(expected_flags):
        return None
    supplied: dict[str, str] = {}
    for index in range(0, len(rest), 2):
        flag, value = rest[index : index + 2]
        if flag not in expected_flags or flag in supplied or not value:
            return None
        supplied[flag] = value
    return action if set(supplied) == expected_flags else None


def _has_pending_guard_context(payload: dict[str, Any]) -> bool:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return False
    try:
        root = _project_root(cwd)
    except GuardError:
        return False
    if not (root / STATE_REL).exists():
        return False
    try:
        state = _state_dir(root, create=False)
        key = _key(state, create=False)
    except GuardError:
        # Existing but unreadable/non-canonical guard state cannot prove safety.
        return True
    for preview_path in sorted(state.glob("preview-*.json")):
        try:
            _, preview_receipt = _receipt(state, str(preview_path), "preview", key)
        except GuardError as exc:
            if "expired" in str(exc):
                continue
            # A malformed receipt inside canonical state cannot safely prove no pending mutation.
            return True
        resolution: tuple[str, Path, str] | None = None
        for kind, terminal_status in (
            ("completion", "executed-successfully"),
            ("cancellation", "cancelled"),
        ):
            candidate = state / f"{kind}-preview-{preview_receipt['receipt_id']}.json"
            if candidate.is_file():
                resolution = (kind, candidate, terminal_status)
                break
        if resolution is None:
            return True
        kind, resolution_path, terminal_status = resolution
        try:
            _, resolved = _receipt(state, str(resolution_path), kind, key)
        except GuardError:
            return True
        if (
            resolved.get("preview_receipt_id") != preview_receipt["receipt_id"]
            or resolved.get("status") != terminal_status
        ):
            return True
    return False


def _deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def pretool() -> dict[str, Any] | None:
    payload = _read_hook_payload()
    if payload.get("hook_event_name") not in {None, "PreToolUse"}:
        return None
    if payload.get("tool_name") != "Bash":
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return None
    if _canonical_guard_action(command) is not None:
        return None
    if RUNNER_NAME in command:
        return _deny(
            "Malformed central guard invocation is blocked: the full Bash command must be "
            "exactly one canonical preview, authorize, or execute call with no shell operators."
        )
    if _has_pending_guard_context(payload):
        return _deny(
            "A pending guard context blocks non-canonical Bash execution until its exact "
            "preview -> confirmation -> authorize -> execute flow completes or expires."
        )
    if not any(pattern.search(command) for pattern in DIRECT_MUTATION_PATTERNS):
        return None
    return _deny(
        "Direct external mutation is blocked. Use build-external-mutation-guard.py "
        "preview -> user confirmation -> authorize -> execute."
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    preview_parser = commands.add_parser("preview")
    preview_parser.add_argument("--project-root", required=True)
    preview_parser.add_argument("--entrypoint-ref", required=True)
    preview_parser.add_argument("--target-scope", required=True)
    preview_parser.add_argument("--diff-summary", required=True)
    preview_parser.add_argument("--side-effect-summary", required=True)
    preview_parser.add_argument("--command-json", required=True)
    commands.add_parser("hook-confirm")
    authorize_parser = commands.add_parser("authorize")
    authorize_parser.add_argument("--project-root", required=True)
    authorize_parser.add_argument("--preview-receipt", required=True)
    authorize_parser.add_argument("--confirmation-receipt", required=True)
    authorize_intent_parser = commands.add_parser("authorize-intent")
    authorize_intent_parser.add_argument("--project-root", required=True)
    authorize_intent_parser.add_argument("--preview-receipt", required=True)
    authorize_intent_parser.add_argument("--intent-receipt", required=True)
    cancel_parser = commands.add_parser("cancel")
    cancel_parser.add_argument("--project-root", required=True)
    cancel_parser.add_argument("--preview-receipt", required=True)
    execute_parser = commands.add_parser("execute")
    execute_parser.add_argument("--project-root", required=True)
    execute_parser.add_argument("--authorization-receipt", required=True)
    execute_parser.add_argument("--command-json", required=True)
    commands.add_parser("pretool")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.action == "preview":
            print(_ordered_output(preview(args)))
            return 0
        if args.action == "hook-confirm":
            result = hook_confirm()
            if result is not None:
                print(
                    _compact(
                        {
                            "continue": True,
                            "suppressOutput": True,
                            "hookSpecificOutput": {
                                "hookEventName": "UserPromptSubmit",
                                "additionalContext": "[external-mutation-confirmation]\n"
                                + _compact(result),
                            },
                        }
                    )
                )
            return 0
        if args.action == "authorize":
            print(_compact(authorize(args)))
            return 0
        if args.action == "authorize-intent":
            print(_compact(authorize_intent(args)))
            return 0
        if args.action == "cancel":
            print(_compact(cancel(args)))
            return 0
        if args.action == "execute":
            return execute(args)
        result = pretool()
        if result is not None:
            print(_compact(result))
        return 0
    except (GuardError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print(f"EXTERNAL_MUTATION_GUARD_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
