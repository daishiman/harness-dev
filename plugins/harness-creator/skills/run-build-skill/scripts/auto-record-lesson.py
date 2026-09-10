#!/usr/bin/env python3
# /// script
# name: auto-record-lesson
# purpose: Claude Code / Codex PostToolUse ペイロードから再現可能な失敗観測だけを抽出し、build-external-intelligence.py の共通 project store へ非ブロックで渡す薄い hook adapter
# inputs:
#   - stdin: Claude Code / Codex hook JSON
#   - env: HARNESS_AGENT(optional), HARNESS_INTELLIGENCE_HOME(optional), plugin/runtime env
# outputs:
#   - stderr: 記録結果の有界診断
#   - write: build-external-intelligence.py が解決する plugin package 外 state のみ
#   - exit: 常に 0 (hook をブロックしない)
# contexts: [C, E]
# network: false
# write-scope: resolved external-intelligence state root only
# dependencies: [build-external-intelligence.py]
# requires-python: ">=3.10"
# ///
"""Fail-soft hook adapter for the shared external-intelligence engine.

This file deliberately contains no store implementation. The former behavior
that appended Markdown and indexes inside the installed plugin was removed:
marketplace upgrades can replace that directory, and two stores made promotion
and deduplication ambiguous.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


_FAILURE_PATTERNS = (
    re.compile(r"\bFAIL(?:ED|URE)?\b", re.IGNORECASE),
    re.compile(r"\bERROR\b", re.IGNORECASE),
    re.compile(r"\bTraceback\b"),
    re.compile(r"\bnon-?zero exit\b", re.IGNORECASE),
    re.compile(r"\bexit (?:code|status)\s*[:=]?\s*[1-9]\d*", re.IGNORECASE),
)
_SECRET_NAME = r"(?:token|secret|password|passwd|api[_-]?key|authorization)"
_JSON_SECRET = re.compile(
    rf"(?i)(?P<prefix>[\"']{_SECRET_NAME}[\"']\s*:\s*)"
    r"(?P<quote>[\"'])(?P<value>.*?)(?P=quote)"
)
_AUTHORIZATION_HEADER = re.compile(
    r"(?im)(\bauthorization\s*:\s*)(bearer|basic)\s+[^\s,;]+"
)
_CLI_SECRET = re.compile(
    rf"(?i)(--{_SECRET_NAME}(?:\s*=\s*|\s+))"
    r'(?:"[^"]*"|\'[^\']*\'|[^\s,;&]+)'
)
_SENSITIVE = re.compile(
    rf"(?i)(\b{_SECRET_NAME}\b\s*[:=]\s*)"
    r'(?:"[^"]*"|\'[^\']*\'|[^\s,;&]+)'
)
_BEARER = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:\\(?:[^\s:]+\\)*[^\s:]+")
_UNIX_PATH = re.compile(r"(?<![\w.-])/(?:[^\s/:]+/)*[^\s/:]+")
_LOCATION = re.compile(r"(?<=\w):\d+(?::\d+)?\b")
_UUID = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
)
_LONG_HEX = re.compile(r"(?i)\b(?:0x)?[0-9a-f]{12,}\b")
_LABELED_ID = re.compile(
    r"(?i)\b((?:request|trace|run|job|task|session|turn|tool(?:_use)?)\s*[-_ ]?id\s*[:=]\s*)"
    r"[^\s,;]+"
)
_TIMESTAMP = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?\b"
)
_STABLE_CODE = re.compile(
    r"(?i)\b((?:exit\s+(?:code|status)|status\s+code|http(?:\s+status)?|errno)\s*[:=]?\s*)(\d+)\b"
)
_NUMBER = re.compile(r"\b\d+\b")
_MAX_OBSERVATION = 240
_MAX_SIGNATURE = 160


def _read_input() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _flatten(value: Any) -> str:
    parts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            parts.append(str(node))
        elif isinstance(node, dict):
            for key, item in node.items():
                if key in {"exit_code", "exitCode", "status_code"} and isinstance(item, int) and item:
                    parts.append(f"exit code {item}")
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return "\n".join(parts)


def _failure_text(payload: dict[str, Any]) -> str:
    event = str(payload.get("hook_event_name") or "")
    candidates = [payload.get("tool_response"), payload.get("error"), payload.get("tool_error")]
    text = _flatten(candidates)
    if event == "PostToolUseFailure" and text.strip():
        return text
    response = payload.get("tool_response")
    explicit_failure = False
    if isinstance(response, dict):
        exit_code = response.get("exit_code", response.get("exitCode"))
        explicit_failure = (
            isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code != 0
        ) or response.get("success") is False or response.get("is_error") is True
        status = str(response.get("status") or "").lower()
        explicit_failure = explicit_failure or status in {"error", "failed", "failure"}
    if explicit_failure:
        return text
    # A Skill can report semantic validation failure while the outer tool call
    # itself succeeded. Other successful tools may merely read/write the word
    # "ERROR", so pattern-only detection there would create false memories.
    tool = str(payload.get("tool_name") or payload.get("tool") or "")
    if tool == "Skill" and any(pattern.search(text) for pattern in _FAILURE_PATTERNS):
        return text
    return ""


def _redact(value: str) -> str:
    text = _JSON_SECRET.sub(
        lambda match: f'{match.group("prefix")}{match.group("quote")}<redacted>{match.group("quote")}',
        value,
    )
    text = _AUTHORIZATION_HEADER.sub(
        lambda match: f"{match.group(1)}{match.group(2)} <redacted>", text
    )
    text = _CLI_SECRET.sub(lambda match: f"{match.group(1)}<redacted>", text)
    text = _SENSITIVE.sub(lambda match: f"{match.group(1)}<redacted>", text)
    text = _BEARER.sub("Bearer <redacted>", text)
    home = str(Path.home())
    if home and home != "/":
        text = text.replace(home, "~")
    return text


def _failure_line(text: str) -> str:
    for line in text.splitlines():
        if any(pattern.search(line) for pattern in _FAILURE_PATTERNS):
            return line.strip()
    fallback = next((line.strip() for line in text.splitlines() if line.strip()), "tool failure")
    return fallback


def _first_failure_line(text: str) -> str:
    return _redact(_failure_line(text))[:_MAX_OBSERVATION]


def _failure_signature(text: str) -> str:
    """Return a stable, non-secret failure class for cross-run identity.

    Instance-only details (paths, locations, IDs, timestamps and numbers) are
    placeholders. Error/exception names and surrounding words remain, so two
    distinct failure classes do not collapse merely because they used one tool.
    """
    signature = _ANSI_ESCAPE.sub("", _redact(_failure_line(text)))
    signature = _WINDOWS_PATH.sub("<path>", signature)
    signature = _UNIX_PATH.sub("<path>", signature)
    signature = _LOCATION.sub(":<line>", signature)
    signature = _UUID.sub("<id>", signature)
    signature = _LONG_HEX.sub("<id>", signature)
    signature = _LABELED_ID.sub(lambda match: f"{match.group(1)}<id>", signature)
    signature = _TIMESTAMP.sub("<time>", signature)
    stable_codes: list[tuple[str, str]] = []

    def preserve_code(match: re.Match[str]) -> str:
        marker = chr(0xE000 + len(stable_codes))
        stable_codes.append((marker, match.group(2)))
        return f"{match.group(1)}{marker}"

    signature = _STABLE_CODE.sub(preserve_code, signature)
    signature = _NUMBER.sub("<n>", signature)
    for marker, code in stable_codes:
        signature = signature.replace(marker, code)
    signature = re.sub(r"\s+", " ", signature).strip().casefold()
    return signature[:_MAX_SIGNATURE] or "tool failure"


def _evidence_source(tool: str, signature: str) -> str:
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
    normalized_tool = re.sub(r"[^a-z0-9_-]+", "-", tool.casefold()).strip("-") or "unknown"
    return f"hook-failure:{normalized_tool}:{digest}"


def _hint(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return "unknown-target"
    for key in ("skill", "file_path", "path", "command", "description"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            if key in {"file_path", "path"}:
                return Path(value).name[:80] or "path"
            return _redact(value.strip())[:80]
    return "unknown-target"


def _agent() -> str:
    explicit = os.environ.get("HARNESS_AGENT", "").strip().lower()
    if explicit in {"codex", "claude", "other"}:
        return explicit
    # Codex plugin hooks define PLUGIN_ROOT/PLUGIN_DATA and also compatibility
    # CLAUDE_* variables. Claude defines CLAUDE_* only.
    return "codex" if os.environ.get("PLUGIN_ROOT") or os.environ.get("PLUGIN_DATA") else "claude"


def _context_id(payload: dict[str, Any]) -> str:
    session = str(payload.get("session_id") or "unknown-session")
    return f"session:{session}"


def _evidence_ref(payload: dict[str, Any]) -> str:
    turn = str(payload.get("turn_id") or "unknown-turn")
    tool_use = str(payload.get("tool_use_id") or "unknown-tool")
    return f"hook:{turn}:{tool_use}"


def build_command(payload: dict[str, Any], failure: str) -> list[str]:
    engine = Path(__file__).resolve().with_name("build-external-intelligence.py")
    tool = str(payload.get("tool_name") or payload.get("tool") or "unknown")
    hint = _hint(payload)
    observation = _first_failure_line(failure)
    signature = _failure_signature(failure)
    command = [sys.executable, str(engine), "--agent", _agent()]
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        command.extend(["--project-root", cwd])
    command.extend(
        [
            "capture",
            "--title",
            f"Failure signature: {tool}:{signature}",
            "--summary",
            f"{observation} [target: {hint}]",
            "--rule",
            f"Prevent repeated {tool} failure matching '{signature}'; verify root cause before promotion.",
            "--context-id",
            _context_id(payload),
            "--evidence-ref",
            _evidence_ref(payload),
            "--evidence-source",
            _evidence_source(tool, signature),
            "--ambiguous-action",
            "quarantine",
            "--tags",
            f"failure,{tool},auto-observation",
            "--countercondition",
            "A different root cause produces the same surface error signature.",
        ]
    )
    return command


def main() -> int:
    payload = _read_input()
    failure = _failure_text(payload)
    tool = payload.get("tool_name") or payload.get("tool")
    if not failure or not isinstance(tool, str) or not tool.strip():
        return 0
    try:
        proc = subprocess.run(
            build_command(payload, failure),
            text=True,
            capture_output=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        sys.stderr.write(f"[auto-record-lesson] skipped: {str(exc)[:240]}\n")
        return 0
    try:
        result = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError):
        result = {}
    status = result.get("action") or result.get("status") or f"exit-{proc.returncode}"
    state_dir = result.get("state_dir", "unresolved")
    sys.stderr.write(f"[auto-record-lesson] {status} -> {state_dir}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
