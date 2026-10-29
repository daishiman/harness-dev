#!/usr/bin/env python3
# /// script
# name: record-audit-fork
# version: 0.4.0
# purpose: 監査 sub-agent への Task fork が実際に完了したことと、その監査 verdict を
#          PostToolUse (dispatch) と SubagentStop (completion) の 2 経路で append-only 台帳へ
#          記録する (completeness-report の auditor 帰属と verdict を自己申告でなく
#          実 fork 証跡へ接地させるための証跡 writer)。
# inputs:
#   - stdin: PostToolUse hook JSON ({session_id, tool_name, tool_use_id,
#            tool_input{subagent_type, prompt}, tool_response})
#            または SubagentStop hook JSON ({session_id, agent_id, agent_type,
#            last_assistant_message})
#   - argv: --event post-tool-use|subagent-stop (省略時は payload の hook_event_name で判別)
#   - env: CLAUDE_PROJECT_DIR (台帳の書込起点。未設定時は cwd)
#          CLAUDE_PLUGIN_ROOT (監査 agent レジストリの探索起点。未設定時は本ファイルの親の親)
#          SYSTEM_SPEC_AUDIT_FORK_LEDGER (台帳パスの明示上書き。テスト・live-trial 用)
# outputs:
#   - file: <project>/eval-log/system-spec-harness/audit-fork-ledger.jsonl (1 fork = 1 行の追記)
#   - exit: 0 always (観測専用。session を blocking しない)
# contexts: [E]
# network: false
# write-scope: workspace
# dependencies: []
# requires-python: ">=3.9"
# ///
"""PostToolUse(Task|Agent) 監査 fork 台帳 writer。

## なぜ必要か (issue: completeness-report の auditor 帰属が実 fork 証跡に接地しない)

`assign-system-spec-completeness-evaluator` の評価レポートは観点ごとに `auditor`
(例 `matrix_coverage` → `system-spec-matrix-auditor`) を宣言するが、これは **評価者自身が書く
文字列** であり、実際に Task fork が起きたかを何も表していなかった。独立監査を 1 件も起動しない
実行でも「独立 auditor が PASS を出した」と名乗るレポートを生成でき、`aggregate-completeness.py
--report` は exit 0 で通っていた。レポート digest は graph node の
`confirmation_evidence.evaluated_digest` として confirmed の根拠になるため、fail-closed の証跡連鎖に
「帰属だけ検証されない」穴が残っていた。

監査 agent (`system-spec-{matrix,hearing,doc-freshness}-auditor`) は `tools: Read[, Bash]` のみで
**Write を持たない** ため、自力ではディスク上に「自分が走った」痕跡を残せない。そこで
「モデルが書けない層」である hook が fork の完了、response digest、最終 verdict marker を記録する。
台帳はモデルの出力ではなく harness の副作用なので、レポート側の宣言と独立した corroboration (裏取り) になる。

## 記録対象

本 plugin が同梱する agent (`<plugin_root>/agents/*.md` の stem) を `subagent_type` に持つ
subagent 起動 (tool_name が 'Task' または 'Agent') のみ。起動ツール名はハーネス世代で異なる
(旧ハーネス/Codex 系='Task', 現行 Claude Code='Agent') ため両方を受理し、台帳へは観測名をそのまま書く。
Claude Code が pinned plugin の agent を `system-spec-harness:<agent>` として渡す場合は、自 plugin の
qualifier だけを受理して stem へ正規化する。無関係な Task で台帳が膨らむのを避け、レジストリ追加に
自動追従する (agent を足せば記録対象になる)。

## 記録しないもの

prompt / tool_response 本文は記録せず sha256 のみ (機微情報を台帳へ持ち込まない)。response 本文の
text block の最終非空行に正規 marker が 1 件だけあれば、本文を保存せず enum として記録する。
tool_response が prompt を内包していても、prompt 内の説明用 marker は判定に数えない。

## dispatch の対応付け (schema 1.2)

現行 Claude Code の PostToolUse hook は **tool call ごとに 1 回** 呼ばれ、top-level の
`tool_use_id` と、その call 固有の `tool_response` を渡す。1.2 はこの公式 payload をそのまま
1 台帳行へ束縛し、response digest も `tool_response` 全体から採る。response 内に架空の
`tool_use_id` block を探したり、同一 message の全結果を分割したりしない。

verdict は完了状態を確認してから、応答本文の各 text block の最終非空行だけを候補にする。
`Agent` は `status=completed` が必須。旧 `Task` は status 欠落を互換受理するが、status が
明示された場合は `completed` のみ完成扱いにする。`async_launched` / `failed` など completed
以外は marker があっても `pending` とし、completion receipt に昇格させない。正規 marker 候補が
1 件なら `resolved`、0 件なら本文あり=`absent` / 本文なし=`pending`、2 件以上なら `ambiguous`
とする。prompt や metadata の文字列は応答本文ではないため候補に数えない。

top-level `tool_use_id` が無い **旧 `Task` payload に限り** schema 1.1 として既存フィールドを
維持する。現行 `Agent` の ID 欠落を 1.1 へ downgrade せず、台帳行を作らないことで fail-closed にする。

## 非同期 fork の完了記録 (schema 1.3 / 第 2 writer)

ハーネスが監査 subagent を **非同期** 起動すると、PostToolUse が観測できる `tool_response` は
起動受理 (`status=async_launched` 等) だけで、最終応答も `AUDIT_VERDICT` marker も含まない。
PostToolUse だけを writer にしていた 1.2 では、この経路の行が恒久的に
`verdict_state=pending` / `audit_verdict=null` のまま残り、台帳による帰属の裏取りが成立しなかった
(第 4 回 completeness evaluator の medium finding `attribution`)。

そこで **SubagentStop を第 2 writer** として配線し、fork 完了時に `record_kind="completion"` の
schema 1.3 行を **追記** する。台帳は append-only 契約なので、既存の pending 行は書き換えず、
読取側 (`audit_fork_attribution.py`) が同一 fork の dispatch 行と completion 行を
「pending は暫定・resolved は確定」という状態機械として畳み込む。これは last-write-wins の
暗黙解釈ではなく、行 kind による明示的な昇格である。

### dispatch 行と completion 行の対応付け (join key)

ハーネスは **親の `tool_use_id` と子の `agent_id` を繋ぐ鍵を提供しない**。PostToolUse は親で
発火して `tool_use_id` を持つが子を知らず、SubagentStop は子で発火して最終応答を持つが
`tool_use_id` を知らない。推測で対応付けると、並列 fork で verdict を取り違える。

そこで **dispatch token** を導入する。親が fork prompt へ

    AUDIT_DISPATCH: <token>

の 1 行を含め、auditor は最終応答の中 (最終行の `AUDIT_VERDICT` とは別行) に同じ 1 行を
echo する。hook は prompt 側の token を dispatch 行へ、応答側の token を completion 行へ
記録するので、読取側は token の完全一致で exact join できる。token は
`[A-Za-z0-9._-]{8,64}` で、prompt / 応答のいずれかに 2 個以上あれば曖昧として記録しない。

token が無い場合の fallback は読取側の責務とし、本 hook は観測した事実だけを書く。

## 既知の限界 (正直な境界)

- 台帳は同一 response digest の verdict を receipt が忠実に転記したことまで照合できる。監査 prompt が
  実質を伴うか、根拠が妥当かは機械層では判定できない (意味層 = content-review/human)。
- hook が無効化された環境では台帳が空になる。その場合 `aggregate-completeness.py` は
  fail-closed で「帰属未接地」の violation を出す (緑にはならない = 安全側)。
- dispatch token を含めずに起動した fork は exact join できない。読取側は (session, subagent_type)
  の pending dispatch と resolved completion が **ちょうど 1 対 1** のときだけ昇格を許し、
  並列起動で多対多になる場合は fail-closed のまま残す (取り違えを黙認しない)。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

SCHEMA_VERSION = "1.2"
LEGACY_SCHEMA_VERSION = "1.1"
COMPLETION_SCHEMA_VERSION = "1.3"
RECORD_KIND_DISPATCH = "dispatch"
RECORD_KIND_COMPLETION = "completion"
HOOK_EVENT_POST_TOOL_USE = "PostToolUse"
HOOK_EVENT_SUBAGENT_STOP = "SubagentStop"
# 親の tool_use_id と子の agent_id を繋ぐ鍵をハーネスが提供しないため、親が prompt へ埋め
# auditor が応答へ echo する token を join key にする (docstring「join key」節)。
# 実測では auditor が `## AUDIT_DISPATCH: <token> (echo)` のように見出し化・注記付きで echo し、
# 起動 prompt 側も本文と注意書きで同じ token を 2 回持つ。行全体を固定すると前者を取りこぼし、
# 単純な出現数判定では後者を曖昧扱いにしてしまうため、行内の出現をすべて拾って値の異同で判定する。
AUDIT_DISPATCH_TOKEN_RE = re.compile(r"AUDIT_DISPATCH:[ \t]*([A-Za-z0-9._-]{8,64})")
HOOK_NAME = "record-audit-fork"
PLUGIN_NAME = "system-spec-harness"
# subagent 起動ツール名はハーネス世代で異なる (旧/Codex 系='Task', 現行 Claude Code='Agent')。
# 台帳には観測名をそのまま書く (正規化しない)。証跡は harness の観測事実であるべきで、
# 書き換えると「自己申告でない裏取り」という台帳の存在意義と矛盾するため。
# 読取側 aggregate-completeness.py の LEDGER_TOOL_NAMES と整合を保つこと。
AUDIT_FORK_TOOL_NAMES = ("Task", "Agent")
LEDGER_RELPATH = Path("eval-log") / "system-spec-harness" / "audit-fork-ledger.jsonl"
LEDGER_ENV = "SYSTEM_SPEC_AUDIT_FORK_LEDGER"
AUDIT_VERDICTS = {"PASS", "FAIL", "INDETERMINATE"}
AUDIT_VERDICT_LINE_RE = re.compile(r"^AUDIT_VERDICT: (PASS|FAIL|INDETERMINATE)\s*$")
RESPONSE_STATUS_COMPLETED = "completed"
RESPONSE_STATUS_ASYNC_LAUNCHED = "async_launched"

# verdict が null になった理由の帰属 (schema 1.2)。
# null を 1 種類に潰すと「応答がまだ無い」「応答はあるが marker が無い」「marker が複数ある」が
# 同じ 0 に見え、下流が「監査を起動していない」と「監査は起動したが証跡が未確定」を区別できない。
# verdict_state は 1.2 行にだけ付け、既存の 1.1 行のフィールド契約は変えない。
VERDICT_STATE_RESOLVED = "resolved"  # 正規 marker 候補がちょうど 1 件
VERDICT_STATE_ABSENT = "absent"  # 応答本文はあるが正規 marker 候補が無い
VERDICT_STATE_PENDING = "pending"  # Agent が未完了、または応答本文がまだ無い
VERDICT_STATE_AMBIGUOUS = "ambiguous"  # 正規 marker 候補が複数あり 1 verdict に決められない


def plugin_root() -> Path:
    """hooks/record-audit-fork.py -> plugin root (parents[1])。env 指定があれば優先。"""
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1]


def audit_agents(root: Path | None = None) -> set[str]:
    """本 plugin が同梱する agent 名 (= 記録対象の subagent_type) を返す。"""
    agents_dir = (root or plugin_root()) / "agents"
    try:
        return {p.stem for p in agents_dir.glob("*.md")}
    except OSError:
        return set()


def ledger_path() -> Path:
    """台帳パス。env 上書き > CLAUDE_PROJECT_DIR 相対 > cwd 相対。"""
    env = os.environ.get(LEDGER_ENV)
    if env:
        return Path(env)
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    return root / LEDGER_RELPATH


def read_payload() -> dict:
    """hook は stdin で JSON を渡す。空・不正なら {} (観測専用なので落とさない)。"""
    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {}


def normalize_subagent_type(subagent_type: object, known_agents: set[str]) -> str | None:
    """Task payload の agent 名を plugin-local stem へ正規化する。

    Claude Code は plain agent を ``<agent>``、``--plugin-dir`` で pin した agent を
    ``<plugin>:<agent>`` として渡す。qualified 名は本 plugin の qualifier だけを受理し、
    他 plugin が同じ stem を名乗って台帳へ混入する経路を閉じる。
    """
    if not isinstance(subagent_type, str) or not subagent_type:
        return None
    if ":" in subagent_type:
        plugin, agent = subagent_type.split(":", 1)
        if plugin != PLUGIN_NAME:
            return None
    else:
        agent = subagent_type
    return agent if agent in known_agents else None


def _response_text_blocks(value: object):
    """tool_response の応答本文だけから text block を取り出す。

    Agent の PostToolUse payload には ``prompt`` や ``agentId``、status などの
    metadata も含まれる。任意の dict value を再帰走査すると、応答本文の最終 marker
    より後にある metadata 文字列を「最終行」と誤認するため、既知の応答本文 key だけを
    降りる。content block 自体は ``{"type": "text", "text": ...}`` なので direct
    ``text`` を採る。明示的に text 以外の type を持つ metadata block は除外する。
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _response_text_blocks(item)
    elif isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            if value.get("type") in (None, "text"):
                yield text
            return
        for key in ("content", "output", "result", "response", "message"):
            if key in value:
                yield from _response_text_blocks(value[key])


def audited_response_metadata(tool_response: object) -> tuple[str, str | None, str]:
    """非機微な response digest、厳密な最終 verdict marker、その帰属状態を返す。

    auditor は最終行を ``AUDIT_VERDICT: <PASS|FAIL|INDETERMINATE>`` と返す契約である。
    hook payload の tool_response は fork prompt と応答後 metadata を含む場合があるため、
    prompt/metadata の文字列は判定材料にしない。応答本文の **text block ごと** に最終非空行を
    1 行だけ取り、正規 marker に一致する候補がちょうど 1 件のときだけ verdict を確定する。
    digest は PostToolUse が当該 call に渡した ``tool_response`` 全体から採る。
    """
    canonical = json.dumps(tool_response, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    candidates = []
    saw_nonempty_text = False
    for text in _response_text_blocks(tool_response):
        final_line = None
        for line in text.splitlines():
            if line.strip():
                saw_nonempty_text = True
                final_line = line.strip()
        match = AUDIT_VERDICT_LINE_RE.fullmatch(final_line or "")
        if match and match.group(1) in AUDIT_VERDICTS:
            candidates.append(match.group(1))
    if len(candidates) == 1:
        return digest, candidates[0], VERDICT_STATE_RESOLVED
    if len(candidates) > 1:
        return digest, None, VERDICT_STATE_AMBIGUOUS
    return digest, None, VERDICT_STATE_ABSENT if saw_nonempty_text else VERDICT_STATE_PENDING


def response_is_complete(tool_name: str, tool_response: object) -> bool:
    """completion receipt を作れる response かを tool 世代別に判定する。

    現行 Agent は status が必須。旧 Task は status 自体が無い payload を互換受理するが、
    status を明示した新しい payload が未完了を名乗る場合は legacy へ逃がさない。
    """
    if tool_name == "Agent":
        return (
            isinstance(tool_response, dict)
            and tool_response.get("status") == RESPONSE_STATUS_COMPLETED
        )
    if tool_name == "Task" and isinstance(tool_response, dict) and "status" in tool_response:
        return tool_response.get("status") == RESPONSE_STATUS_COMPLETED
    return True


def dispatch_token(text: object) -> str | None:
    """``AUDIT_DISPATCH: <token>`` の記述から join key を取り出す。

    同じ token が複数回現れるのは正常 (起動 prompt は本文と注意書きで 2 回持ち、auditor は
    見出しや注記を添えて echo する) なので、**値が 1 種類なら** その値を返す。0 件 (未使用) と
    2 種類以上 (曖昧) はいずれも None。曖昧な token を書くと読取側が誤った dispatch へ
    completion を接合するため、書かないことで fail-closed にする。
    """
    if not isinstance(text, str) or not text:
        return None
    found = set(AUDIT_DISPATCH_TOKEN_RE.findall(text))
    return found.pop() if len(found) == 1 else None


def completion_response_text(payload: dict) -> str | None:
    """SubagentStop payload から subagent の最終応答本文を取り出す。

    公式 payload は ``last_assistant_message`` を持つ。transcript は非同期書込みで最新 turn を
    含まない場合があるため読まない (公式ドキュメントの指示)。取れなければ None にして
    ``verdict_state=pending`` のまま残す (推測で resolved へ昇格させない)。
    """
    for key in ("last_assistant_message", "lastAssistantMessage", "final_message", "response"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, dict):
            blocks = [t for t in _response_text_blocks(value) if t.strip()]
            if blocks:
                return "\n".join(blocks)
    return None


def build_completion_record(payload: dict, known_agents: set[str]) -> dict | None:
    """SubagentStop payload から completion 行 (schema 1.3) を組み立てる。対象外なら None。

    dispatch 行 (PostToolUse) を書き換えず、完了という新しい観測事実を追記する。

    実測 payload では ``agent_type`` が空文字で届く SubagentStop がある (compaction 等の
    内部 subagent)。そのため subagent_type だけを対象判定にすると、auditor の完了まで
    取りこぼしうる。応答本文に ``AUDIT_DISPATCH`` token があれば ``subagent_type=None``
    のまま行を書き、読取側は token join 専用の completion として扱う (1 対 1 fallback の
    対象にはしない)。token も subagent_type も無い完了だけを対象外にする。
    """
    text = completion_response_text(payload)
    if text is None:
        # 応答本文を観測できない完了は verdict の根拠にならない。行を作らず fail-closed にする
        # (空の resolved 行を作ると「監査は完了したが verdict 不明」を PASS 側へ寄せてしまう)。
        return None
    subagent_type = normalize_subagent_type(
        payload.get("agent_type") or payload.get("subagent_type"), known_agents
    )
    token = dispatch_token(text)
    if subagent_type is None and token is None:
        return None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    candidates = []
    final_line = None
    for line in text.splitlines():
        if line.strip():
            final_line = line.strip()
    match = AUDIT_VERDICT_LINE_RE.fullmatch(final_line or "")
    if match:
        candidates.append(match.group(1))
    if len(candidates) == 1:
        audit_verdict, verdict_state = candidates[0], VERDICT_STATE_RESOLVED
    else:
        audit_verdict, verdict_state = None, VERDICT_STATE_ABSENT
    return {
        "schema_version": COMPLETION_SCHEMA_VERSION,
        "record_kind": RECORD_KIND_COMPLETION,
        "ts": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "session_id": payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "unknown",
        # 読取側 LEDGER_TOOL_NAMES と整合させる。completion は Agent 世代でのみ発火する。
        "tool_name": "Agent",
        "subagent_type": subagent_type,
        "agent_id": payload.get("agent_id"),
        "dispatch_token": token,
        "prompt_sha256": None,
        "response_sha256": digest,
        "audit_verdict": audit_verdict,
        "verdict_state": verdict_state,
        "cwd": payload.get("cwd") or str(Path.cwd()),
    }


def build_record(payload: dict, known_agents: set[str]) -> dict | None:
    """記録対象なら台帳 1 行を組み立てる。対象外なら None。

    subagent 起動ツール名はハーネス世代で異なる: 旧ハーネス/Codex 系は 'Task'、
    現行 Claude Code は 'Agent' を tool_name として渡す。
    """
    ledger_tool_name = payload.get("tool_name")
    if ledger_tool_name not in AUDIT_FORK_TOOL_NAMES:
        return None
    tin = payload.get("tool_input")
    if not isinstance(tin, dict):
        return None
    subagent_type = normalize_subagent_type(tin.get("subagent_type"), known_agents)
    if subagent_type is None:
        return None
    prompt = tin.get("prompt")
    prompt_sha256 = (
        hashlib.sha256(prompt.encode("utf-8")).hexdigest() if isinstance(prompt, str) and prompt else None
    )
    tool_use_id = payload.get("tool_use_id")
    has_tool_use_id = isinstance(tool_use_id, str) and bool(tool_use_id.strip())
    if ledger_tool_name == "Agent" and not has_tool_use_id:
        # 現行 Agent の call identity 欠落を legacy Task と誤認すると、1.2 の必須照合を迂回できる。
        return None

    tool_response = payload.get("tool_response")
    response_sha256, audit_verdict, verdict_state = audited_response_metadata(tool_response)
    if not response_is_complete(ledger_tool_name, tool_response):
        # async_launched は起動受理であって最終応答ではない。本文に marker が注入されていても
        # completion receipt にしない。Agent の未知/欠落 status と、Task の明示的な未完了 status
        # も同じく安全側へ倒す。
        audit_verdict = None
        verdict_state = VERDICT_STATE_PENDING

    is_current_schema = has_tool_use_id
    record = {
        "schema_version": SCHEMA_VERSION if is_current_schema else LEGACY_SCHEMA_VERSION,
        "ts": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "session_id": payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "unknown",
        "tool_name": ledger_tool_name,
        "subagent_type": subagent_type,
        "prompt_sha256": prompt_sha256,
        "response_sha256": response_sha256,
        "audit_verdict": audit_verdict,
        "cwd": payload.get("cwd") or str(Path.cwd()),
    }
    if is_current_schema:
        # 1.2 は公式 PostToolUse payload の top-level call identity を必須フィールドとして保持する。
        record["tool_use_id"] = tool_use_id
        record["verdict_state"] = verdict_state
        # 1.3 で導入した join key。既存 1.2 の必須フィールド契約は変えず、追加フィールドとして
        # 持たせる (token を使わない起動でも既存読取側はそのまま通る)。
        record["record_kind"] = RECORD_KIND_DISPATCH
        record["dispatch_token"] = dispatch_token(prompt)
    return record


def append_record(record: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    # PostToolUse は並列 tool call ごとに別 process で走りうる。O_APPEND + 1 os.write にして、
    # TextIO の分割 write による JSONL 行の混線を避ける。
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o666)
    try:
        written = os.write(fd, line)
        if written != len(line):
            raise OSError(f"short append: {written}/{len(line)} bytes")
    finally:
        os.close(fd)


def resolve_event(payload: dict, argv: list) -> str:
    """観測する hook event を決める。--event 明示 > payload の hook_event_name > PostToolUse。"""
    if "--event" in argv:
        index = argv.index("--event")
        if index + 1 < len(argv):
            value = argv[index + 1]
            if value == "subagent-stop":
                return HOOK_EVENT_SUBAGENT_STOP
            if value == "post-tool-use":
                return HOOK_EVENT_POST_TOOL_USE
    if payload.get("hook_event_name") == HOOK_EVENT_SUBAGENT_STOP:
        return HOOK_EVENT_SUBAGENT_STOP
    return HOOK_EVENT_POST_TOOL_USE


def main(argv: list | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    payload = read_payload()
    try:
        event = resolve_event(payload, argv)
        if event == HOOK_EVENT_SUBAGENT_STOP:
            record = build_completion_record(payload, audit_agents())
        else:
            record = build_record(payload, audit_agents())
        if record is not None:
            append_record(record, ledger_path())
    except OSError as exc:  # 台帳が書けなくても session は止めない (証跡欠落は下流が fail-closed で拾う)
        print(f"WARN {HOOK_NAME}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
