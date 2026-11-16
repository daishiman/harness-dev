#!/usr/bin/env python3
# /// script
# name: extract-harness-run-metrics
# purpose: Claude Code の transcript (JSONL) から、harness-creator の 1 回の実行 (既定は capability-build / run-skill-create の起動から完了レポートまで) について、利用者への質問の回数・AI の呼び出しと token (subagent は自分の transcript の累計)・読んだ bytes (yaml-spec-cache は別に)・検査 script を呼んだ回数・所要時間を数えて JSON で出す。区切りが見つからなければ推測で数えずに止める。
# inputs:
#   - argv: <transcript.jsonl> [--start-skill REGEX] [--end-marker TEXT ...] [--run N] [--subagents-dir DIR] [--out PATH]
#   - file: subagent の transcript (<transcript の stem>/subagents/agent-<id>.jsonl か、transcript と同じ dir の subagents/。--subagents-dir で上書き)
# outputs:
#   - stdout: 計測結果の JSON (--out を渡したときは書いたパスだけ)
#   - stderr: 区切りが見つからない・transcript が読めないときの理由
#   - exit: 0=計測できた / 2=区切りが見つからない・入力が不正・--out に書けない
# contexts: [C, E]
# network: false
# write-scope: --out で指定したファイルだけ (既定は書かない)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""1 回の実行を transcript から数える (harness-hxi)。

区切り:
  - 始まり: 指定した skill の起動 (Skill tool の呼び出し、または /<skill> の slash command)。
    所要時間はその起動を引き起こした利用者の依頼 (直前の利用者の発言) から測る。
  - 終わり: 始まりより後で、終わりの目印 (既定は完了レポートの項目名 gates_passed と
    build_lint_receipt) をすべて含む最初の assistant の本文。
  どちらかが見つからなければ exit 2 で止める。終わりの目印より前に同じ skill の次の起動が
  あるときも止める (目印の無い実行を次の実行と 1 本に合わせて数えないため)。

数えるもの:
  - questions: AskUserQuestion の呼び出し数と、その中の質問数。利用者の返答を待った turn
    (実行中に届いた利用者の発言。task-notification などの自動の通知は含めない)。
  - agents: Agent / Task の起動数と、fork された Skill の数。token の累計 (usage) は、結果に
    出る agentId から subagent の transcript を開き、assistant の usage を message.id ごとに
    1 回だけ足す。subagent がさらに起動した subagent も辿る。transcript が見つからない
    agent は transcripts.missing に数える。
    final_context_tokens は結果の totalTokens と background の通知の <subagent_tokens> の和。
    これは各 agent の最後の呼び出しの context の大きさで、累計ではない (比べるときは usage を使う)。
  - main_tokens: 親の会話の token (assistant の usage を message.id ごとに 1 回だけ足す)。
  - read: Read の結果の bytes と、Bash の出力の bytes (cat / sed で読んだ分も context に入るため)。
    yaml-spec-cache を読んだ分 (Read と、yaml-spec-cache を名指しした Bash の出力) は別に数える。
  - checkers: Bash の command の文の先頭で script として呼んだ validate-* / lint-* / check-*
    (.py) の名前ごとの回数。引数や grep の対象として名前が出ただけのものは数えない。loop の
    中の 1 文は 1 回に数え、make など別の command の中で呼ばれた分は見えない。
  - skills: 実行中の Skill の起動の名前ごとの回数 (入れ子の再入を見るため)。
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

DEFAULT_START = r"^(harness-creator:)?(capability-build|run-skill-create)$"
DEFAULT_END_MARKERS = ("gates_passed", "build_lint_receipt")
CHECKER_SCRIPT_RE = re.compile(r"(?:^|/)((?:validate|lint|check)-[A-Za-z0-9_-]+)\.py$")
PYTHON_RE = re.compile(r"(?:^|/)python(?:\d+(?:\.\d+)*)?$")
# 文の切れ目になる記号 (shlex の punctuation_chars。quote の中は切らない)
STATEMENT_PUNCT = "();<>|&`\n"
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
LEADING_WORDS = frozenset({"then", "do", "else", "elif", "if", "while", "until", "!", "{", "$",
                           "time", "env", "exec", "command", "nohup"})
COMMAND_RE = re.compile(r"<command-name>/?([^<\s]+)</command-name>")
SUBAGENT_TOKENS_RE = re.compile(r"<subagent_tokens>(\d+)</subagent_tokens>")
NOTIFY_TOOL_ID_RE = re.compile(r"<tool-use-id>([^<]+)</tool-use-id>")
# 利用者の発言の形をしているが、利用者が打ったものではない (自動の通知・command の出力)
AUTO_USER_PREFIXES = ("<task-notification>", "<local-command-stdout>", "<local-command-stderr>",
                      "<local-command-caveat>", "<bash-stdout>", "<bash-stderr>")
YAML_SPEC = "yaml-spec-cache"
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


class BoundaryError(ValueError):
    """区切りが見つからない (推測で数えない)。"""


def _read_jsonl(path: Path) -> list:
    """1 行 1 event。U+2028 などで行を割らないよう、改行文字だけで分ける。"""
    events = []
    for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{n}: JSON として読めない ({exc.msg})") from None
    return events


def load_events(path: Path) -> list[dict]:
    return [e for e in _read_jsonl(path) if isinstance(e, dict) and not e.get("isSidechain")]


def _message(event: dict) -> dict:
    message = event.get("message")
    return message if isinstance(message, dict) else {}


def _content(event: dict) -> list | str:
    content = _message(event).get("content", [])
    return content if isinstance(content, (list, str)) else []


def _blocks(event: dict, kind: str) -> list[dict]:
    content = _content(event)
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == kind]


def _input(block: dict) -> dict:
    args = block.get("input")
    return args if isinstance(args, dict) else {}


def _user_text(event: dict) -> str | None:
    """利用者が打った発言なら本文を返す。tool の結果や自動の通知は None。"""
    if event.get("type") != "user" or event.get("isMeta") or event.get("isCompactSummary"):
        return None
    content = _content(event)
    if isinstance(content, str):
        text = content
    elif any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return None
    else:
        text = "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text")
    return text if text.strip() else None


def _started_skill(event: dict, start: re.Pattern) -> str | None:
    """始まりに当たる起動なら、plugin の prefix を除いた skill 名を返す。"""
    names = [str(_input(b).get("skill", "")) for b in _blocks(event, "tool_use") if b.get("name") == "Skill"]
    text = _user_text(event)
    if text:
        names += COMMAND_RE.findall(text)
    for name in names:
        if start.search(name):
            return name.rsplit(":", 1)[-1]
    return None


def _assistant_text(event: dict) -> str:
    if event.get("type") != "assistant":
        return ""
    return "\n".join(str(b.get("text", "")) for b in _blocks(event, "text"))


def find_runs(events: list[dict], start: re.Pattern, end_markers: tuple[str, ...]) -> list[tuple[int, int]]:
    runs, i = [], 0
    while i < len(events):
        name = _started_skill(events[i], start)
        if name is None:
            i += 1
            continue
        end = next((j for j in range(i, len(events))
                    if all(m in _assistant_text(events[j]) for m in end_markers)), None)
        if end is None:
            raise BoundaryError(f"event {i} で始まった実行の終わりの目印 {list(end_markers)} が見つからない")
        again = next((k for k in range(i + 1, end + 1) if _started_skill(events[k], start) == name), None)
        if again is not None:
            raise BoundaryError(
                f"event {i} で始まった実行の終わりの目印より前に、同じ skill ({name}) の次の起動 "
                f"(event {again}) がある。前の実行に終わりの目印が無いので、2 本を合わせて数えない")
        runs.append((i, end))
        i = end + 1
    return runs


def _ts(event: dict) -> datetime:
    raw = event.get("timestamp")
    if not isinstance(raw, str):
        raise BoundaryError("区切りの event に timestamp が無い")
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _request_index(events: list[dict], start: int) -> int:
    """起動を引き起こした利用者の依頼。slash command ならその発言、Skill tool なら直前の発言。"""
    for k in range(start, -1, -1):
        text = _user_text(events[k])
        if text and not text.lstrip().startswith(AUTO_USER_PREFIXES):
            return k
    return start


def _strip_heredocs(command: str) -> str:
    """heredoc の本文は shell の文ではない (python のコードなど) ので除く。"""
    kept, pending = [], []
    for line in command.split("\n"):
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        kept.append(line)
        pending += [m.group(2) for m in HEREDOC_RE.finditer(line)]
    return "\n".join(kept)


def _statements(command: str) -> list[list[str]]:
    """quote を守って、演算子・括弧・改行で文に分けた単語の列。"""
    lexer = shlex.shlex(_strip_heredocs(command), posix=True, punctuation_chars=STATEMENT_PUNCT)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    statements, current = [], []
    try:
        for token in lexer:
            if token and set(token) <= set(STATEMENT_PUNCT):
                statements.append(current)
                current = []
            else:
                current.append(token)
    except ValueError:
        # quote が閉じていない。quote を見ずに記号で切る (quote の中の記号でも切れるので、少し多めに数えうる)
        return [part.split() for part in re.split(r"[;|&\n()`]", command)]
    return statements + [current]


def invoked_checkers(command: str) -> list[str]:
    """command の文の先頭で script として呼んだ検査 script の名前。"""
    found = []
    for words in _statements(command):
        while words and (words[0] in LEADING_WORDS or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])):
            words.pop(0)
        if words and PYTHON_RE.search(words[0]):
            words.pop(0)
            while words and words[0].startswith("-"):
                if words.pop(0) in ("-c", "-m"):
                    words = []
        elif len(words) >= 2 and words[0] == "uv" and words[1] == "run":
            words = [w for w in words[2:] if not w.startswith("-")]
        if words:
            match = CHECKER_SCRIPT_RE.search(words[0])
            if match:
                found.append(match.group(1))
    return found


def _sum_usage(usages) -> Counter:
    total = Counter()
    for usage in usages:
        for key in USAGE_KEYS:
            if isinstance(usage.get(key), int):
                total[key] += usage[key]
    return total


def _subagent_usage(path: Path) -> tuple[Counter, list[str]]:
    """subagent の transcript の usage の累計と、その中で起動された subagent の agentId。"""
    usage_by_message, children = {}, []
    for event in _read_jsonl(path):
        if not isinstance(event, dict):
            continue
        message = _message(event)
        if event.get("type") == "assistant" and isinstance(message.get("usage"), dict):
            usage_by_message[str(message.get("id") or f"#{len(usage_by_message)}")] = message["usage"]
        extra = event.get("toolUseResult")
        if isinstance(extra, dict) and isinstance(extra.get("agentId"), str):
            children.append(extra["agentId"])
    return _sum_usage(usage_by_message.values()), children


def _children_by_meta(subagents_dir: Path | None) -> dict[str, list[str]]:
    """`agent-<id>.meta.json` の parentAgentId から、親ごとの子の agentId を集める。

    subagent が起動した subagent は、親の transcript に toolUseResult (agentId) が
    残らないことがある。meta の parentAgentId はそのときも残るので、こちらでも辿る。
    読めない meta は飛ばす (usage は transcript の側にあるので、数え漏れは missing に出ない)。
    """
    children: dict[str, list[str]] = {}
    if subagents_dir is None:
        return children
    for meta in sorted(subagents_dir.glob("agent-*.meta.json")):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        parent = data.get("parentAgentId") if isinstance(data, dict) else None
        if isinstance(parent, str) and parent:
            children.setdefault(parent, []).append(meta.name[len("agent-"):-len(".meta.json")])
    return children


def subagent_totals(agent_ids: list[str | None], subagents_dir: Path | None) -> dict:
    usage, found, missing, nested = Counter(), 0, 0, 0
    by_meta = _children_by_meta(subagents_dir)
    queue = [(a, False) for a in agent_ids]
    seen: set[str] = set()
    while queue:
        agent_id, is_nested = queue.pop(0)
        if agent_id in seen:
            continue
        if agent_id:
            seen.add(agent_id)
        path = subagents_dir / f"agent-{agent_id}.jsonl" if subagents_dir and agent_id else None
        if path is None or not path.is_file():
            missing += 1
            continue
        found += 1
        nested += is_nested
        sub_usage, children = _subagent_usage(path)
        usage.update(sub_usage)
        queue += [(c, True) for c in children + by_meta.get(agent_id, [])]
    return {"transcripts": {"found": found, "missing": missing, "nested": nested},
            "usage": dict(sorted(usage.items()))}


def measure(events: list[dict], start_idx: int, end_idx: int, subagents_dir: Path | None = None) -> dict:
    window = events[start_idx:end_idx + 1]
    request_idx = _request_index(events, start_idx)
    uses: dict[str, dict] = {}
    results: dict[str, dict] = {}
    asks = ask_questions = user_turns = queued_prompts = 0
    skills: Counter = Counter()
    checkers: Counter = Counter()
    usage_by_message: dict[str, dict] = {}
    notified_tokens: dict[str, int] = {}

    for event in window:
        if event.get("type") == "assistant":
            message = _message(event)
            if isinstance(message.get("usage"), dict):
                usage_by_message[str(message.get("id") or f"#{len(usage_by_message)}")] = message["usage"]
            for block in _blocks(event, "tool_use"):
                uses[str(block.get("id", ""))] = block
                name, args = block.get("name"), _input(block)
                if name == "AskUserQuestion":
                    questions = args.get("questions")
                    asks += 1
                    ask_questions += len(questions) if isinstance(questions, list) else 0
                elif name == "Skill":
                    skills[str(args.get("skill", ""))] += 1
                elif name == "Bash":
                    checkers.update(invoked_checkers(str(args.get("command", ""))))
        elif event.get("type") == "user":
            for block in _blocks(event, "tool_result"):
                results[str(block.get("tool_use_id", ""))] = {"block": block, "extra": event.get("toolUseResult")}
            text = _user_text(event)
            if text and text.lstrip().startswith("<task-notification>"):
                _record_notification(text, notified_tokens)
            elif text and not text.lstrip().startswith(AUTO_USER_PREFIXES) and event is not window[0]:
                user_turns += 1
        elif event.get("type") == "attachment":
            # 作業中に届いたもの: background agent の完了通知と、利用者が途中で打った発言
            attachment = event.get("attachment") if isinstance(event.get("attachment"), dict) else {}
            if attachment.get("type") == "queued_command":
                if attachment.get("commandMode") == "task-notification":
                    _record_notification(str(attachment.get("prompt", "")), notified_tokens)
                elif attachment.get("commandMode") == "prompt":
                    queued_prompts += 1

    agent_count = forked_skills = final_context = final_unknown = 0
    agent_ids: list[str | None] = []
    read_calls = read_bytes = yaml_bytes = bash_calls = bash_bytes = 0
    for tool_id, use in uses.items():
        name, args = use.get("name"), _input(use)
        result = results.get(tool_id, {})
        extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
        agent_id = extra.get("agentId") if isinstance(extra.get("agentId"), str) else None
        if name in ("Agent", "Task"):
            agent_count += 1
            agent_ids.append(agent_id)
            if isinstance(extra.get("totalTokens"), int):
                final_context += extra["totalTokens"]
            elif tool_id in notified_tokens:
                final_context += notified_tokens[tool_id]
            else:
                final_unknown += 1
        elif name == "Skill" and extra.get("status") == "forked":
            forked_skills += 1
            agent_ids.append(agent_id)
        elif name == "Read":
            read_calls += 1
            size = len(_result_text(result, extra).encode("utf-8"))
            read_bytes += size
            if YAML_SPEC in str(args.get("file_path", "")):
                yaml_bytes += size
        elif name == "Bash":
            # cat / sed で読んだ分も context に入る。Read だけ数えると Bash で読む実行が軽く見える
            size = len(_result_text(result, extra).encode("utf-8"))
            bash_calls += 1
            bash_bytes += size
            if YAML_SPEC in str(args.get("command", "")):
                yaml_bytes += size

    started, ended = _ts(events[request_idx]), _ts(events[end_idx])
    return {
        "boundaries": {
            "request_event": request_idx, "start_event": start_idx, "end_event": end_idx,
            "request_at": events[request_idx]["timestamp"], "end_at": events[end_idx]["timestamp"],
        },
        "wall_seconds": round((ended - started).total_seconds(), 3),
        # round_trips は利用者の返答を待った回数。途中で打たれた発言 (queued_prompts) は待っていないので含めない
        "questions": {"ask_user_question_calls": asks, "ask_user_question_items": ask_questions,
                      "user_turns": user_turns, "round_trips": asks + user_turns,
                      "queued_prompts": queued_prompts},
        "agents": {"launched": agent_count, "forked_skills": forked_skills,
                   **subagent_totals(agent_ids, subagents_dir),
                   "final_context_tokens": final_context, "final_context_unknown": final_unknown},
        "main_tokens": dict(sorted(_sum_usage(usage_by_message.values()).items())),
        "read": {"calls": read_calls, "bytes": read_bytes, "yaml_spec_cache_bytes": yaml_bytes,
                 "bash_calls": bash_calls, "bash_output_bytes": bash_bytes},
        "checkers": dict(sorted(checkers.items())),
        "skills": dict(sorted(skills.items())),
    }


def _record_notification(text: str, notified_tokens: dict[str, int]) -> None:
    tool_id, tokens = NOTIFY_TOOL_ID_RE.search(text), SUBAGENT_TOKENS_RE.search(text)
    if tool_id and tokens:
        notified_tokens[tool_id.group(1)] = int(tokens.group(1))


def _result_text(result: dict, extra: dict) -> str:
    file_info = extra.get("file")
    if isinstance(file_info, dict) and isinstance(file_info.get("content"), str):
        return file_info["content"]
    if isinstance(extra.get("stdout"), str):
        return extra["stdout"]
    block = result.get("block") if isinstance(result.get("block"), dict) else {}
    content = block.get("content", "")
    if isinstance(content, list):
        return "".join(str(c.get("text", "")) for c in content if isinstance(c, dict))
    return content if isinstance(content, str) else ""


def default_subagents_dir(transcript: Path) -> Path | None:
    for candidate in (transcript.with_suffix("") / "subagents", transcript.parent / "subagents"):
        if candidate.is_dir():
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("transcript", type=Path)
    ap.add_argument("--start-skill", default=DEFAULT_START, help="始まりとみなす skill 名の正規表現")
    ap.add_argument("--end-marker", action="append", help="終わりの目印 (すべてを含む本文で終わる。繰り返し可)")
    ap.add_argument("--run", type=int, default=1, help="transcript 内の何回目の実行か (1 始まり)")
    ap.add_argument("--subagents-dir", type=Path, help="subagent の transcript の dir (既定は transcript の隣を探す)")
    ap.add_argument("--out", type=Path)
    ns = ap.parse_args(argv)
    markers = tuple(ns.end_marker or DEFAULT_END_MARKERS)
    try:
        start = re.compile(ns.start_skill)
        events = load_events(ns.transcript)
        runs = find_runs(events, start, markers)
        if not runs:
            raise BoundaryError(f"始まりの skill ({ns.start_skill}) の起動が見つからない")
        if not 1 <= ns.run <= len(runs):
            raise BoundaryError(f"--run {ns.run} に当たる実行が無い (見つかった実行は {len(runs)} 回)")
        if ns.subagents_dir is not None and not ns.subagents_dir.is_dir():
            raise ValueError(f"--subagents-dir {ns.subagents_dir} が dir ではない")
        subagents_dir = ns.subagents_dir or default_subagents_dir(ns.transcript)
        start_idx, end_idx = runs[ns.run - 1]
        report = {"schema_version": 2, "transcript": str(ns.transcript), "run": ns.run,
                  "runs_found": len(runs), "subagents_dir": str(subagents_dir) if subagents_dir else None,
                  **measure(events, start_idx, end_idx, subagents_dir)}
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if ns.out:
            ns.out.write_text(text, encoding="utf-8")
    except (OSError, ValueError, re.error) as exc:
        print(f"[extract-harness-run-metrics] ERROR: {exc}", file=sys.stderr)
        return 2
    if ns.out:
        print(ns.out)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
