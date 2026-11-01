#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# name: aggregate-evals
# version: 0.3.0
# purpose: SessionEnd hook で 4 つの評価の記録を集計し、連続 FAIL・平均スコアの低下・苦戦の重なりを前回の観測と比べて、差分があるときだけ観測差分のドラフトを plugin の外の state に書く
# inputs:
#   - stdin: SessionEnd hook の payload（使わずに読み捨てる）
#   - argv: 無ければ SessionEnd hook の経路。--list-proposals（書かずに、自動ドラフトと手書きの提案の両方の置き場を一覧する。CLAUDE_PROJECT_DIR が無ければ cwd と git の作業ツリーの root を project とみなして読む）。ほかの引数は受けない（--help は usage を出す）
#   - files: plugins/harness-creator/EVALS.json、eval-log/**/*-score.jsonl、eval-log/**/content-review/*-verdict.json、eval-log/*/*/live-trial/*/verdict.json、書込先の既存ドラフト（<date>-rubric-update.md。前の日までの最新のものを前回の観測として読み、今日のものは上書きの要否を決めるのに読む。退避先に書くときだけ、より優先する置き場の履歴も読む）
#   - env: HC_ROOT・CLAUDE_PLUGIN_ROOT（plugin root）、HARNESS_CREATOR_PROPOSALS_DIR（書き込み先の明示）、CLAUDE_PROJECT_DIR（既定の書き込み先。--list-proposals では読む先）、XDG_STATE_HOME（書けないときの退避先）
# outputs:
#   - file: $CLAUDE_PROJECT_DIR/.claude/state/harness-creator/proposals/<date>-rubric-update.md（frontmatter の kind は rubric-anomaly-delta。前回の観測から new / changed / retired のどれかが出たときに書く。今日のドラフトが既にあれば、観測が変わったときだけ上書きする。marker の無い同名の手書きは上書きしない。書けなければ退避先へ、どこにも書けなければ書かない。plugin のツリーには書かない）
#   - file: OS の一時ディレクトリの harness-aggregate-<hash>.lock（書込先ごとの排他に使う空ファイル）
#   - stdout: --list-proposals のときだけ、置き場と提案の一覧の JSON（--help のときは usage）
#   - stderr: 書いた先 / 差分が無いこと / 読めなかった記録 / 入力が欠けて前回の観測を変えなかったこと / skill_md_sha256 の無い content-review の件数 / 書込先が使用中で飛ばしたこと / 書けなかった理由 / --list-proposals で project を推し量ったこと / 引数の誤り
#   - exit: 0（hook を止めない。差分が無いとき・入力が欠けたとき・書込先が使用中のとき・書けないときも 0）/ 2（--list-proposals 以外の引数。hook は引数を渡さないので、hook の経路では返さない）
# requires-python: ">=3.9"
# dependencies: []
# contexts: [D]
# network: false
# write-scope: output-dir（state の proposals/ の観測差分ドラフトと、OS の一時ディレクトリの lock ファイルだけ。plugin のツリーと git は触らない）
# ///
"""aggregate-evals.py

SessionEnd hook から発火し、4 つの入力源の評価の記録を集計する。
異常 (連続 FAIL / 平均スコア低下 / 苦戦の重なり) を前回の観測 (書込先にある、前の日までの最新の
ドラフトに埋めた anomaly-state) と比べ、new / changed / retired のどれかがあるときだけ
$CLAUDE_PROJECT_DIR/.claude/state/harness-creator/proposals/<date>-rubric-update.md に
観測差分のドラフト (kind: rubric-anomaly-delta) を書く。同じ日の 2 回目以降は、観測が今日のドラフトと
違うときだけ上書きする。これは rubric の改正案ではない。
改正するときは人が templates/proposal.json で起票する。

節:
    書込先  ... どこに書き、どこを読むか (plugin のツリーには書かない)
    model   ... 4 入力源の正規化、target の正準化、score の単位、episode の識別
    loader  ... 4 入力源の読み込みと health (どの入力源が欠けたか)
    anomaly ... episode 単位の異常検出と集計
    snapshot ... 前回の観測の選択、差分、排他、atomic write、描画
    main    ... hook の経路と --list-proposals

副作用境界:
    - state の proposals/ ディレクトリへの書き込みと、OS の一時ディレクトリの lock ファイルだけ。
      git は触らない。
    - plugin のツリー (run-skill-rubric-governance/proposals/) には書かない。そこは手書きの
      提案が tracked で残る置き場で、読むだけにする。書くと配布物に生成物が混ざり、
      session を終えるたびに plugin の fingerprint が動く。

止めない (SessionEnd hook の timeout は 3 秒):
    - 入力源のどれかが読めなければ health が incomplete になり、前回の観測を変えずに exit 0。
      欠けた入力で集計すると、消えていない異常を retired と書いてしまう。
    - 書込先の lock は待たない (短く試して取れなければ飛ばして exit 0)。別の session が
      同じ書込先を更新しているので、次の SessionEnd で追いつく。

exit_code 仕様 (Claude Code Hooks 準拠):
    0  非ブロック (正常 / 差分なし / 入力不足 / 使用中 / 書き込み成功 / 書けない)
    2  明示拒否 (hook の経路では使わない。手で流したときの引数の誤りに argparse が返す)
    その他 非ブロック警告

閾値 (どれも episode 単位。1 レビューを複数ファイルへ投影しても 1 件と数える):
    - 同一 target で直近 3 連続が負の verdict (FAIL / BLOCKED / DEGRADED / INCOMPLETE など)
    - 同一 target の平均スコア (0..1 に揃えた値) が直近窓で 0.1 以上低下
    - 同一 target で直近窓 (6 件) 中 2 episode 以上が苦戦シグナルを示す
      (iterations>=2 / negative_feedback>=2件 / findings>=3件 のいずれか)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import errno
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, NamedTuple

try:  # POSIX
    import fcntl as _fcntl
except ImportError:  # Windows では無い。msvcrt を使う
    _fcntl = None

try:  # Windows
    import msvcrt as _msvcrt
except ImportError:  # POSIX では無いのがふつう
    _msvcrt = None

_CONSECUTIVE_FAIL_THRESHOLD = 3
_SCORE_DROP_THRESHOLD = 0.1
_RECENT_WINDOW = 5  # 直近窓

# 苦戦密度 (friction_density) 閾値。
# CI は PASS verdict のみ commit を許すため、FAIL 系列に依存する上記 2 条件は
# 入力が構造的に空集合となり発火し得ない。committed PASS verdict に既に埋まる
# 摩擦データ (再評価 iterations / negative_feedback / findings 件数) を第 3 の
# 発火条件にする。単独レビューアの軽微な摩擦 (iterations=1 かつ negative 1 件)
# では発火せず、同一 skill の直近窓で複数 episode の摩擦が裏付け合う場合のみ
# 発火する (オオカミ少年回避を最優先した保守設計)。
_FRICTION_ITERATIONS_MIN = 2  # 再評価ループが必要だった (上限は max_iterations=3)
_FRICTION_NEGATIVE_MIN = 2  # 1 episode の negative_feedback が 2 件以上
_FRICTION_FINDINGS_MIN = 3  # 1 episode の findings が 3 件以上 (score.jsonl 系)
# 直近窓内で摩擦 episode 2 件以上 (相互裏付け)。この「裏付け」が成立するのは
# 1 レビュー = 1 episode が保証されている場合だけで、content-review の 2 ファイル投影を
# そのまま数えていた頃は自分自身のコピーで満たされ実質 >= 1 に退化していた。
# 畳み込みは _coalesce_episodes の責務。ここを上げて対処してはいけない
# (投影の数が変わればまた壊れる)。
_FRICTION_MIN_EPISODES = 2
_FRICTION_MIN_RECORDS = _FRICTION_MIN_EPISODES  # 旧名。数える単位は episode
_FRICTION_RECENT_WINDOW = 6  # 苦戦密度の直近窓

# 自動ドラフトの本文に必ず入る行。手書きの提案と分ける唯一の手がかりで、
# scripts/build-plugin-release.py の GENERATED_PROPOSAL_MARKER と同じ文字列にする。
# 前回の観測として読むのも、この行があるドラフトだけにする。
_GENERATED_MARKER = "aggregate-evals.py により自動生成された"

# 書込先の lock を待つ上限。SessionEnd hook の timeout (3 秒) に収めるため短くし、
# 取れなければ待たずに飛ばす。
_LOCK_WAIT_SECONDS = 0.5
_LOCK_POLL_SECONDS = 0.05


# ===========================================================================
# 書込先: どこに書き、どこを読むか (plugin のツリーには書かない)
# ===========================================================================


def _manifest_name(root: Path) -> str | None:
    """<root>/.claude-plugin/plugin.json の name。読めなければ None。"""
    try:
        manifest = json.loads(
            (root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    return manifest.get("name") if isinstance(manifest, dict) else None


def _self_plugin_name() -> str | None:
    """このファイル自身が属する plugin の manifest name。

    リテラル直書きは制御リテラル散在として禁止 (tests/test_dogfooding_boundary.py)、
    SSOT 定数は「SSOT を探すのに plugin root が要る」循環のため使えない。__file__ は
    循環せず改名にも自動追従する第三の出所。plugin は入れ子にならないので、上向きに
    最初に見つかる manifest が自 plugin のもので確定する。
    """
    for parent in Path(__file__).resolve().parents:
        name = _manifest_name(parent)
        if name:
            return name
    return None


def _hc_env_root() -> Path | None:
    """env から自 plugin root を得る。他 plugin を指す値は拒否する。

    他 repo が .claude 平置き projection で本 plugin を借用している場合、
    env CLAUDE_PLUGIN_ROOT は **別 plugin** を指していることがある
    (ObsidianMemo では ubm-goal-setting)。空ではなく「存在するが別物」なので
    `if env:` では弾けない。manifest の name で自 plugin か検証する。
    借用側は HC_ROOT を設定すれば明示指定できる。
    拒否するのは manifest が読めて **別 plugin と確認できた** 場合だけにする。
    判定材料が無い (manifest 不在) env は従来どおり採用し、既存挙動を後退
    させない。vendored コピー先 (company-master / skill-intake) でも同様。
    """
    expected = _self_plugin_name()
    if not expected:
        return None
    for _var in ("HC_ROOT", "CLAUDE_PLUGIN_ROOT"):
        raw = os.environ.get(_var)
        if not raw:
            continue
        root = Path(raw).expanduser()
        _name = _manifest_name(root)
        if _name is None or _name == expected:
            return root.resolve()
    return None


def _plugin_root() -> Path:
    # 本ファイル: plugins/harness-creator/skills/run-skill-rubric-governance/scripts/
    return _hc_env_root() or Path(__file__).resolve().parents[3]


def _project_state_root() -> Path | None:
    """自動ドラフトの既定の置き場 (project の state)。$CLAUDE_PROJECT_DIR が無ければ None。"""
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project:
        return Path(project) / ".claude" / "state" / "harness-creator"
    return None


def _inferred_project_state_roots() -> list[Path]:
    """$CLAUDE_PROJECT_DIR が無いときに、project の state を推し量る。読む側だけで使う。

    SessionEnd hook は $CLAUDE_PROJECT_DIR のある環境で動くので、自動ドラフトはその project の
    state に書かれる。一方、Bash から手で --list-proposals を流すときは $CLAUDE_PROJECT_DIR が無い。
    project は Claude Code を起動したディレクトリで、ふつうは cwd か、cwd を含む git の作業ツリーの
    root (.git のあるディレクトリ。`git rev-parse --show-toplevel` と同じ) なので、両方を候補にする。
    書く側には使わない。推し量った先に書くと、hook の書き先とずれたときに提案が散らばる。
    """
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return []
    try:
        cwd = Path.cwd()
    except OSError:
        return []
    toplevel = next((d for d in (cwd, *cwd.parents) if (d / ".git").exists()), None)
    projects = dict.fromkeys(d for d in (cwd, toplevel) if d is not None)
    return [d / ".claude" / "state" / "harness-creator" for d in projects]


def _state_fallback_root() -> Path:
    """project の state に書けないとき (CLAUDE_PROJECT_DIR 未設定・read-only) の退避先。

    手本: notifier-check.py の `Path.home()/.cache/harness` (user 領域退避)。
    優先順: $XDG_STATE_HOME → ~/.claude/state。
    """
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".claude" / "state"
    return base / "harness-creator"


def _dir_is_writable(d: Path) -> bool:
    """d (存在しなければ最寄りの既存祖先) が書込可能かを実 mkdir せず判定。"""
    probe = d
    while not probe.exists():
        if probe.parent == probe:
            return False
        probe = probe.parent
    return os.access(probe, os.W_OK)


def _repo_root() -> Path:
    # _plugin_root() == <repo>/plugins/harness-creator なので parent.parent が repo root。
    return _plugin_root().parent.parent


def _eval_log_dir() -> Path:
    # write-eval-log.py の sink 基底と一致: <repo>/eval-log/
    return _repo_root() / "eval-log"


def _evals_path() -> Path:
    return _plugin_root() / "EVALS.json"


def _legacy_proposals_dir() -> Path:
    """手書きの提案が tracked で残る従来の置き場 (plugin のツリーの中)。読むだけで書かない。"""
    return _plugin_root() / "skills" / "run-skill-rubric-governance" / "proposals"


def _proposals_dir() -> Path:
    """観測差分ドラフトの第一の書込先。env の明示 > project の state。

    $CLAUDE_PROJECT_DIR が無いときは user の state を返す。
    read-only のときの退避は呼び出し側 (_candidate_proposals_dirs / main) が担う。
    """
    override = os.environ.get("HARNESS_CREATOR_PROPOSALS_DIR")
    if override:
        return Path(override).resolve()
    return (_project_state_root() or _state_fallback_root()) / "proposals"


def _is_inside_plugin(d: Path) -> bool:
    plugin = _plugin_root().resolve()
    target = d.resolve()
    return target == plugin or plugin in target.parents


def _candidate_proposals_dirs() -> list[Path]:
    """書込先候補を優先順で返す。前回の観測もここから読む (worktree ごとの置き場)。

    (a) env HARNESS_CREATOR_PROPOSALS_DIR の明示。あればそれだけを使う
    (b) $CLAUDE_PROJECT_DIR/.claude/state/harness-creator/proposals
    (c) 書けなければ user の state ($XDG_STATE_HOME か ~/.claude/state) へ退避
    (b)(c) のうち plugin のツリーの中に落ちるものは外す。plugin のディレクトリを
    cwd にして session を回すと $CLAUDE_PROJECT_DIR が plugin 自身を指し、(b) が
    plugin の中になる。(a) は利用者の明示なので外さない。
    """
    if os.environ.get("HARNESS_CREATOR_PROPOSALS_DIR"):
        return [_proposals_dir()]
    candidates = dict.fromkeys([_proposals_dir(), _state_fallback_root() / "proposals"])
    return [d for d in candidates if not _is_inside_plugin(d)]


def _proposal_read_dirs() -> list[Path]:
    """提案を読む・数えるときに見る置き場。書込先の候補すべてと、従来の置き場。

    自動ドラフトは書込先の候補のどれかに、手書きの提案は従来の置き場にある。
    片方だけを見ると、もう片方の提案を見落とす。
    $CLAUDE_PROJECT_DIR が無いと書込先の候補に project の state が入らないので、推し量った
    project の state を先頭に足す。plugin のツリーの中に落ちるものは、書く側と同じく外す。
    """
    inferred = [r / "proposals" for r in _inferred_project_state_roots()]
    inferred = [d for d in inferred if not _is_inside_plugin(d)]
    return list(dict.fromkeys([*inferred, *_candidate_proposals_dirs(), _legacy_proposals_dir()]))


def _is_generated_proposal(path: Path) -> bool:
    """本文に生成器の marker 行があれば自動ドラフト。読めなければ手書き扱い。"""
    try:
        return _GENERATED_MARKER in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _list_proposals() -> dict[str, Any]:
    dirs = _proposal_read_dirs()
    proposals = [
        {"path": str(p), "generated": _is_generated_proposal(p)}
        for d in dirs
        if d.is_dir()
        for p in sorted(d.glob("*.md"))
    ]
    return {"dirs": [str(d) for d in dirs], "proposals": proposals}


# ===========================================================================
# model: 4 入力源の正規化、target の正準化、score の単位、episode の識別
# ===========================================================================

# 負の verdict。live-trial の BLOCKED / DEGRADED と content-review の INCOMPLETE も、
# 「自走して通らなかった」ので FAIL と同じ側に数える。
_NEGATIVE_VERDICTS = frozenset(
    {"BLOCKED", "DEGRADED", "FAIL", "FAILED", "INCOMPLETE", "REJECT", "REJECTED"}
)
_PASS_VERDICTS = frozenset({"PASS", "PASSED", "ACCEPT", "ACCEPTED"})
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SKILL_PATH_RE = re.compile(r"(?:^|/)plugins/([^/]+)/skills/([^/]+)/SKILL\.md$")
_PLUGIN_PATH_RE = re.compile(r"(?:^|/)plugins/([^/]+)(?:/|$)")
_TZ_BASIC_RE = re.compile(r"([+-]\d{2})(\d{2})$")
# live-trial の run-id。先頭 8 桁の日付だけが必須で、時刻 (HHMM か HHMMSS、末尾 Z は任意) と
# 接尾辞 (-pr12 / -r3 など) は任意。実データには 20261030T1234-pr12 と 20261030T123456-r9 が混在する。
_RUN_ID_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})?Z?)?")


def _short_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _valid_slug(value: Any) -> str | None:
    if isinstance(value, str) and _SLUG_RE.fullmatch(value.strip()):
        return value.strip()
    return None


def _target_from_skill_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = _SKILL_PATH_RE.search(value.strip().replace("\\", "/"))
    if not match:
        return None
    plugin = _valid_slug(match.group(1))
    skill = _valid_slug(match.group(2))
    return f"{plugin}:{skill}" if plugin and skill else None


def _canonical_target(value: Any, plugin: Any = None) -> str | None:
    """環境に依らない target (plugin:skill か skill) を返す。生のパスは出さない。

    SKILL.md への絶対パスは plugin:skill に直し、slug にならない値は target-<hash>、
    plugin がパスなら external-<hash> にする。ドラフトや anomaly-state に worktree の
    絶対パスが残ると、同じ異常が worktree ごとに別の id になり、利用者のパスも漏れる。
    """
    if isinstance(value, dict):
        for key in ("target_path", "skill_path", "path"):
            from_path = _target_from_skill_path(value.get(key))
            if from_path:
                return from_path
        return _canonical_target(value.get("skill"), value.get("plugin") or plugin)
    if not isinstance(value, str) or not value.strip():
        return None

    raw = value.strip().replace("\\", "/")
    from_path = _target_from_skill_path(raw)
    if from_path:
        return from_path

    if ":" in raw and "/" not in raw:
        raw_plugin, raw_skill = raw.rsplit(":", 1)
        valid_plugin = _valid_slug(raw_plugin)
        valid_skill = _valid_slug(raw_skill)
        if valid_plugin and valid_skill:
            return f"{valid_plugin}:{valid_skill}"

    valid_skill = _valid_slug(raw)
    if not valid_skill:
        valid_skill = f"target-{_short_hash(raw)}"

    valid_plugin = _valid_slug(plugin)
    if valid_plugin:
        return f"{valid_plugin}:{valid_skill}"
    if isinstance(plugin, str) and plugin:
        plugin_path = plugin.replace("\\", "/")
        match = _PLUGIN_PATH_RE.search(plugin_path)
        path_plugin = _valid_slug(match.group(1)) if match else None
        namespace = path_plugin or f"external-{_short_hash(plugin_path)}"
        return f"{namespace}:{valid_skill}"
    return valid_skill


def _normalize_score(value: Any, *, scale: str) -> float | None:
    """宣言された単位の score を内部の 0..1 に揃える。範囲外と bool は None。

    score.jsonl の実データは 0..100 (percent) で、旧 EVALS.json と手組みの記録は 0..1 が混ざる。
    単位を揃えずに平均すると、percent の 1 件で score_drop が誤って発火する。
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    score = float(value)
    if scale == "percent" and 0.0 <= score <= 100.0:
        return score / 100.0
    if scale == "ratio" and 0.0 <= score <= 1.0:
        return score
    return None


def _normalize_observed_at(value: Any) -> str | None:
    """時刻まで分かるときだけ UTC の "YYYY-MM-DDTHH:MM:SSZ" を返す。

    "Z" と "+0900" (コロン無し) も受ける。タイムゾーンが無ければ UTC とみなす。
    """
    if not isinstance(value, str) or "T" not in value:
        return None
    raw = value.strip()
    if raw[-1:] in ("Z", "z"):
        raw = raw[:-1] + "+00:00"
    raw = _TZ_BASIC_RE.sub(r"\1:\2", raw)
    try:
        parsed = _dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _date_of(value: Any) -> str | None:
    # "2026-06-06T19:59:43+0900" -> "2026-06-06" (時刻があれば UTC の日付) / "2026-06-01" -> そのまま
    observed_at = _normalize_observed_at(value)
    if observed_at:
        return observed_at[:10]
    if isinstance(value, str):
        match = re.match(r"(\d{4}-\d{2}-\d{2})", value)
        return match.group(1) if match else None
    return None


def _date_sort_key(record: dict[str, Any]) -> tuple[bool, str, str]:
    """古い順に並べるキー。時刻があれば時刻、無ければ日付。どちらも無いものは末尾。

    同じ時点の episode は episode_id で並べ、入力の順で結果が変わらないようにする。
    """
    point = _normalize_observed_at(record.get("observed_at")) or _date_of(record.get("date"))
    return (point is None, point or "", str(record.get("episode_id") or ""))


def _verdict_state(verdict: str) -> str:
    normalized = verdict.upper()
    if normalized in _NEGATIVE_VERDICTS:
        return "negative"
    if normalized in _PASS_VERDICTS:
        return "pass"
    return "unknown"


def _verdict_is_fail(verdict: str) -> bool:
    return _verdict_state(verdict) == "negative"


def _score_of(record: dict[str, Any]) -> float | None:
    """score を 0..1 で返す。単位 (score_unit か score_scale) の宣言が無ければ None。"""
    scale = record.get("score_unit") or record.get("score_scale")
    if scale not in {"percent", "ratio"}:
        return None
    for key in ("score", "overall", "mean_score", "average"):
        if key in record:
            return _normalize_score(record.get(key), scale=str(scale))
    return None


def _episode_identity(source_kind: str, target: str, *parts: Any) -> str:
    return f"{source_kind}:{_short_hash([source_kind, target, *parts])}"


def _review_identity(rec: dict[str, Any]) -> tuple[Any, ...]:
    """content-review の 1 レビューを指すキー。

    content-review 規約は 1 レビューを elegance / rubric の 2 ファイルへ投影し、どちらにも
    評価した SKILL.md の skill_md_sha256 を書く (content-review-verdict.schema.json で必須)。
    同じ版の SKILL.md を見た投影は、reviewed_at が数秒ずれていても同じレビューなので、
    (target, digest) で 1 つに畳む。target は plugin:skill なので plugin も含む。

    digest の無い古い記録は捨てずに (target, reviewed_at, date) で数える。reviewed_at は
    秒精度で、同一ラウンドの 2 ファイルには同じ値が書かれる。date (日付) まで丸めると、
    同じ日に 2 回別のレビューを回したケースまで畳んでしまい、本物の相互裏付けを消す。
    """
    digest = rec.get("skill_md_sha256")
    if isinstance(digest, str) and digest.strip():
        return ("digest", rec.get("skill"), digest.strip())
    return ("fallback", rec.get("skill"), rec.get("reviewed_at"), rec.get("date"))


def _normalize_score_record(
    rec: dict[str, Any], plugin: str | None = None
) -> dict[str, Any] | None:
    """write-eval-log.py の score.jsonl 1行を共通形へ。score は 0..100 (percent) として読む。

    sink schema: rubric{rubric_id,...} / score / passed / findings / skill_name / timestamp
    plugin は eval-log/<plugin>/ のディレクトリ名 (loader が渡す)。
    """
    if not isinstance(rec, dict):
        return None
    rubric = rec.get("rubric") if isinstance(rec.get("rubric"), dict) else {}
    target = _canonical_target(rec.get("skill_name") or rubric.get("rubric_id"), plugin)
    if not target:
        return None
    passed = rec.get("passed")
    if passed is True:
        verdict = "PASS"
    elif passed is False:
        verdict = "FAIL"
    else:
        verdict = str(rec.get("verdict", ""))
    observed_at = _normalize_observed_at(rec.get("timestamp"))
    return {
        "skill": target,
        "date": _date_of(rec.get("timestamp")),
        "observed_at": observed_at,
        "verdict": verdict,
        "verdict_state": _verdict_state(verdict),
        "score": _normalize_score(rec.get("score"), scale="percent"),
        "score_unit": "ratio",
        "source_score_scale": "percent",
        "findings": rec.get("findings", []) or [],
        "source_kind": "score",
        "episode_id": _episode_identity(
            "score", target, rec.get("evaluation_id") or rec.get("run_id") or observed_at, rec
        ),
    }


def _normalize_verdict_record(
    rec: dict[str, Any], source_view: str | None = None
) -> dict[str, Any] | None:
    """content-review verdict.json (1 投影) を共通形へ。

    verdict schema: target{plugin,skill,skill_md_sha256} / review_kind / verdict / reviewed_at
                    / iterations / feedback_loop{negative_feedback[]}
    iterations / negative_feedback は PASS verdict にも残る摩擦シグナルで、
    friction_density 検出の入力になる (PASS-only commit 制約下の唯一の負情報)。
    skill_md_sha256 が無ければ digest_missing を立てて fallback キーで数える (捨てない)。
    """
    if not isinstance(rec, dict):
        return None
    target_data = rec.get("target") if isinstance(rec.get("target"), dict) else {}
    target = _canonical_target(target_data)
    if not target:
        return None
    feedback = rec.get("feedback_loop") if isinstance(rec.get("feedback_loop"), dict) else {}
    negative = feedback.get("negative_feedback")
    reviewed_at = rec.get("reviewed_at")
    reviewed_at = reviewed_at if isinstance(reviewed_at, str) and reviewed_at else None
    digest = target_data.get("skill_md_sha256")
    digest = digest.strip() if isinstance(digest, str) and digest.strip() else None
    verdict = str(rec.get("verdict", ""))
    norm: dict[str, Any] = {
        "skill": target,
        "date": _date_of(reviewed_at),
        "observed_at": _normalize_observed_at(reviewed_at),
        "reviewed_at": reviewed_at,
        "skill_md_sha256": digest,
        "digest_missing": digest is None,
        "verdict": verdict,
        "verdict_state": _verdict_state(verdict),
        "score": None,  # verdict は数値スコアを持たない
        "score_unit": "ratio",
        "findings": [],
        "iterations": rec.get("iterations"),
        "negative_feedback_count": len(negative) if isinstance(negative, list) else 0,
        "source_kind": "content-review",
        "source_view": source_view or rec.get("review_kind") or "unknown",
    }
    identity = _review_identity(norm)
    norm["episode_id"] = _episode_identity("content-review", target, identity[0], *identity[2:])
    return norm


def _normalize_legacy_record(rec: dict[str, Any]) -> dict[str, Any] | None:
    """EVALS.json#/evaluations[] の旧形式を共通形へ。score の単位は score_scale (既定 percent)。"""
    if not isinstance(rec, dict):
        return None
    target = _canonical_target(rec.get("skill") or rec.get("rubric_id"), rec.get("plugin"))
    if not target:
        return None
    observed_at = _normalize_observed_at(rec.get("observed_at") or rec.get("timestamp"))
    source_scale = rec.get("score_scale") or "percent"
    if source_scale not in {"percent", "ratio"}:
        source_scale = "percent"
    raw_score = next(
        (rec.get(key) for key in ("score", "overall", "mean_score", "average") if key in rec),
        None,
    )
    normalized = dict(rec)
    normalized.update(
        {
            "skill": target,
            "date": _date_of(rec.get("date") or rec.get("timestamp")),
            "observed_at": observed_at,
            "verdict_state": _verdict_state(str(rec.get("verdict", ""))),
            "score": _normalize_score(raw_score, scale=str(source_scale)),
            "score_unit": "ratio",
            "source_score_scale": source_scale,
            "findings": rec.get("findings", []) or [],
            "source_kind": "evals",
        }
    )
    normalized["episode_id"] = str(
        rec.get("episode_id")
        or _episode_identity(
            "evals", target, rec.get("evaluation_id") or rec.get("run_id") or observed_at, rec
        )
    )
    return normalized


def _run_id_observed(run_id: Any) -> tuple[str | None, str | None]:
    """run-id から (date, observed_at) を返す。日付が読めなければ (None, None)。

    時刻があれば UTC とみなす (live-trial の run-id は UTC で振る)。時刻が無ければ observed_at は None。
    """
    match = _RUN_ID_RE.match(str(run_id))
    if not match:
        return None, None
    year, month, day, hour, minute, second = match.groups()
    try:
        date = _dt.date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None, None
    if hour is None:
        return date, None
    try:
        moment = _dt.datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second or 0),
            tzinfo=_dt.timezone.utc,
        )
    except ValueError:
        return date, None
    return date, moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_live_trial_record(rec: dict[str, Any], run_id: str = "") -> dict[str, Any] | None:
    """live-trial verdict.json (D10 runtime-evidence 契約) を共通形へ。

    verdict schema: target_skill("plugin:skill") / overall{verdict: PASS|DEGRADED|FAIL|BLOCKED}
                    / goal_verdict{blockers[]} / nudge_count / gate_response_count
    timestamp フィールドを持たないため date と時刻は run-id 先頭から復元する。
    score は構造的に存在しない (goal 判定は PASS|FAIL のみ・点数出力禁止)。
    nudge / gate 応答は「自走できず介入を要した」負シグナルなので
    negative_feedback_count へ合算し friction_density の入力に載せる。
    goal_verdict.blockers は findings として finding カテゴリ集計へ流す。
    """
    if not isinstance(rec, dict):
        return None
    target = _canonical_target(rec.get("target_skill"))
    if not target:
        return None
    overall = rec.get("overall") if isinstance(rec.get("overall"), dict) else {}
    goal = rec.get("goal_verdict") if isinstance(rec.get("goal_verdict"), dict) else {}
    blockers = goal.get("blockers")
    intervention = sum(
        value if isinstance(value, int) and not isinstance(value, bool) else 0
        for value in (rec.get("nudge_count"), rec.get("gate_response_count"))
    )
    date, observed_at = _run_id_observed(run_id)
    verdict = str(overall.get("verdict", ""))
    return {
        "skill": target,
        "date": date,
        "observed_at": observed_at,
        "verdict": verdict,
        "verdict_state": _verdict_state(verdict),
        "score": None,
        "score_unit": "ratio",
        "findings": [b for b in blockers if isinstance(b, str)] if isinstance(blockers, list) else [],
        "negative_feedback_count": intervention,
        "source_kind": "live-trial",
        "episode_id": _episode_identity("live-trial", target, str(run_id)),
    }


def _union_strings(views: list[dict[str, Any]], single: str, plural: str) -> list[str]:
    values: set[str] = set()
    for view in views:
        if view.get(single):
            values.add(str(view[single]))
        for value in view.get(plural) or []:
            values.add(str(value))
    return sorted(values)


def _coalesce_episodes(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同じ episode (target と episode_id が同じ) の記録を 1 件に畳む。何度畳んでも同じ結果になる。

    代表は時点が最新の記録。verdict は負が 1 つでもあれば負、時点は最新、iterations と
    negative_feedback_count は大きい方、findings は和集合。片方だけ更新された中途半端な投影でも
    摩擦の情報を捨てない (落とした情報は復元できないが、過大な 1 episode は裏付け不足で発火しない)。
    episode_id の無い生の記録は、それぞれ別の episode として数える。
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for index, record in enumerate(records):
        target = _canonical_target(record.get("skill") or record.get("rubric_id"), record.get("plugin"))
        episode_id = record.get("episode_id")
        key = (
            json.dumps([target, str(episode_id)], ensure_ascii=False)
            if episode_id
            else f"unidentified:{index}"
        )
        grouped.setdefault(key, []).append(record)

    merged: list[dict[str, Any]] = []
    for group_key, views in grouped.items():
        dated = [view for view in views if not _date_sort_key(view)[0]]
        latest = max(dated, key=_date_sort_key) if dated else views[0]
        item = dict(latest)
        item["episode_id"] = latest.get("episode_id") or group_key
        item["source_kinds"] = _union_strings(views, "source_kind", "source_kinds")
        item["source_views"] = _union_strings(views, "source_view", "source_views")
        verdicts = [str(view.get("verdict", "")) for view in views]
        item["verdict"] = next(
            (verdict for verdict in verdicts if _verdict_is_fail(verdict)),
            str(latest.get("verdict", "")),
        )
        item["verdict_state"] = _verdict_state(item["verdict"])
        observed = sorted(
            value
            for value in (_normalize_observed_at(view.get("observed_at")) for view in views)
            if value
        )
        item["observed_at"] = observed[-1] if observed else None
        dates = sorted(value for value in (_date_of(view.get("date")) for view in views) if value)
        item["date"] = item["observed_at"][:10] if item["observed_at"] else (dates[-1] if dates else None)
        scores = [score for score in (_score_of(view) for view in views) if score is not None]
        item["score"] = scores[0] if scores else None
        item["score_unit"] = "ratio"
        for field in ("iterations", "negative_feedback_count"):
            values = [
                view.get(field)
                for view in views
                if isinstance(view.get(field), int) and not isinstance(view.get(field), bool)
            ]
            if values:
                item[field] = max(values)
        findings: list[Any] = []
        seen: set[str] = set()
        for view in views:
            for finding in view.get("findings", []) or []:
                marker = json.dumps(finding, ensure_ascii=False, sort_keys=True, default=str)
                if marker not in seen:
                    seen.add(marker)
                    findings.append(finding)
        item["findings"] = findings
        merged.append(item)
    return merged


# ===========================================================================
# loader: 4 入力源の読み込みと health
# ===========================================================================
# 入力源が無いのは「空の入力」で健全 (absent)。有るのに読めない・形が違う記録があれば
# incomplete にし、main は前回の観測を変えずに終える。


def _diagnostics(value: dict[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {"present": False, "errors": []}
    value.setdefault("present", False)
    value.setdefault("errors", [])
    return value


def _record_error(diagnostics: dict[str, Any], message: str) -> None:
    diagnostics["errors"].append(message)


def _load_score_jsonl(diagnostics: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """eval-log/<plugin>/<date>-score.jsonl (write-eval-log の実 sink) を全件読む。"""
    diag = _diagnostics(diagnostics)
    base = _eval_log_dir()
    if not base.exists():
        return []
    try:
        paths = sorted(base.glob("**/*-score.jsonl"))
    except OSError as exc:
        _record_error(diag, f"scan failed: {exc}")
        return []
    diag["present"] = bool(paths)

    out: list[dict[str, Any]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _record_error(diag, f"{path}: unreadable: {exc}")
            continue
        try:
            plugin: str | None = path.relative_to(base).parts[0]
        except (ValueError, IndexError):
            plugin = None
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                _record_error(diag, f"{path}:{line_number}: invalid JSON: {exc}")
                continue
            norm = _normalize_score_record(rec, plugin=plugin)
            if norm is None:
                _record_error(diag, f"{path}:{line_number}: invalid score record")
            else:
                out.append(norm)
    return out


def _load_content_review_verdicts(
    diagnostics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """eval-log/<plugin>/<skill>/content-review/*-verdict.json を全件読み、1 レビュー 1 件に畳む。

    content-review 規約は同一レビューを elegance-verdict.json と rubric-verdict.json の
    2 ファイルへ投影する。glob の結果をそのまま返すと 1 回のレビューが常に 2 件になり、
    friction_density の「相互裏付け」が自分自身のコピーで満たされる。投影の数は将来増えうる
    ので、閾値側ではなくここで畳む。skill_md_sha256 の無いレビューの件数を digest_missing に数える。
    """
    diag = _diagnostics(diagnostics)
    base = _eval_log_dir()
    if not base.exists():
        return []
    try:
        paths = sorted(base.glob("**/content-review/*-verdict.json"))
    except OSError as exc:
        _record_error(diag, f"scan failed: {exc}")
        return []
    diag["present"] = bool(paths)

    views: list[dict[str, Any]] = []
    for path in paths:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _record_error(diag, f"{path}: unreadable or invalid JSON: {exc}")
            continue
        view = path.name[: -len("-verdict.json")]
        norm = _normalize_verdict_record(rec, source_view=view)
        if norm is None:
            _record_error(diag, f"{path}: invalid content-review record")
        else:
            views.append(norm)
    episodes = _coalesce_episodes(views)
    diag["digest_missing"] = sum(1 for episode in episodes if episode.get("digest_missing"))
    return episodes


def _load_live_trial_verdicts(
    diagnostics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """eval-log/<plugin>/<skill>/live-trial/<run-id>/verdict.json (Gate D 実走証拠) を全件読む。"""
    diag = _diagnostics(diagnostics)
    base = _eval_log_dir()
    if not base.exists():
        return []
    try:
        paths = sorted(base.glob("*/*/live-trial/*/verdict.json"))
    except OSError as exc:
        _record_error(diag, f"scan failed: {exc}")
        return []
    diag["present"] = bool(paths)

    out: list[dict[str, Any]] = []
    for path in paths:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _record_error(diag, f"{path}: unreadable or invalid JSON: {exc}")
            continue
        norm = _normalize_live_trial_record(rec, run_id=path.parent.name)
        if norm is None:
            _record_error(diag, f"{path}: invalid live-trial record")
        elif norm["date"] is None:
            _record_error(diag, f"{path}: run-id has no leading YYYYMMDD date")
        else:
            out.append(norm)
    return out


def _source_status(diag: dict[str, Any], count: int) -> dict[str, Any]:
    errors = [str(error) for error in diag.get("errors", [])]
    if errors:
        status = "incomplete"
    elif diag.get("present"):
        status = "ok"
    else:
        status = "absent"
    result: dict[str, Any] = {"status": status, "records": count, "errors": errors}
    if "digest_missing" in diag:
        result["digest_missing"] = diag["digest_missing"]
    return result


def _load_evals() -> dict[str, Any]:
    """評価レコードを 4 ソースから集約し、ソースごとの health を付けて返す。

    1) EVALS.json#/evaluations[]   (旧経路。読取互換だけ残す)
    2) eval-log/<plugin>/<date>-score.jsonl       (write-eval-log の実 sink)
    3) eval-log/<plugin>/<skill>/content-review/*-verdict.json  (content-review verdict)
    4) eval-log/<plugin>/<skill>/live-trial/<run-id>/verdict.json  (live-trial 実走証拠, D10)

    新 writer は作らず既存 writer の出力を読むだけ (重複writer回避)。
    health.complete が False なら、どれかの入力源が欠けている。
    """
    evaluations: list[dict[str, Any]] = []
    sources: dict[str, dict[str, Any]] = {}

    evals_diag = _diagnostics(None)
    path = _evals_path()
    evals_diag["present"] = path.exists()
    legacy_count = 0
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            rows = raw.get("evaluations", []) if isinstance(raw, dict) else None
            if not isinstance(rows, list):
                _record_error(evals_diag, f"{path}: evaluations must be an array")
            else:
                for index, row in enumerate(rows):
                    norm = _normalize_legacy_record(row)
                    if norm is None:
                        _record_error(evals_diag, f"{path}: evaluations[{index}] invalid")
                    else:
                        evaluations.append(norm)
                        legacy_count += 1
        except (OSError, ValueError) as exc:
            _record_error(evals_diag, f"{path}: load failed: {exc}")
    sources["EVALS.json"] = _source_status(evals_diag, legacy_count)

    loaders: tuple[tuple[str, Callable[..., list[dict[str, Any]]]], ...] = (
        ("score.jsonl", _load_score_jsonl),
        ("content-review", _load_content_review_verdicts),
        ("live-trial", _load_live_trial_verdicts),
    )
    for source_name, loader in loaders:
        diag = _diagnostics(None)
        try:
            loaded = loader(diag)
        except Exception as exc:  # 非ブロック (SessionEnd 流儀)。欠けた入力源として数える
            loaded = []
            _record_error(diag, f"loader failed: {exc}")
        evaluations.extend(loaded)
        sources[source_name] = _source_status(diag, len(loaded))

    errors = [
        f"{source}: {error}"
        for source, health in sources.items()
        for error in health["errors"]
    ]
    for error in errors:
        sys.stderr.write(f"[aggregate-evals] source load failed: {error}\n")
    digest_missing = int(sources["content-review"].get("digest_missing", 0) or 0)
    if digest_missing:
        sys.stderr.write(
            f"[aggregate-evals] content-review without skill_md_sha256: {digest_missing} "
            "(reviewed_at と日付で数えた)\n"
        )
    return {
        "evaluations": evaluations,
        "health": {
            "complete": not errors,
            "sources": sources,
            "errors": errors,
            "digest_missing": digest_missing,
        },
    }


# ===========================================================================
# anomaly: episode 単位の異常検出と集計
# ===========================================================================


def _is_friction(ev: dict[str, Any]) -> bool:
    """1 episode が苦戦シグナルを含むか (EVALS.json 旧形式はフィールド欠落 = 非該当)。"""
    iterations = ev.get("iterations")
    if isinstance(iterations, int) and iterations >= _FRICTION_ITERATIONS_MIN:
        return True
    negative = ev.get("negative_feedback_count")
    if isinstance(negative, int) and negative >= _FRICTION_NEGATIVE_MIN:
        return True
    findings = ev.get("findings")
    return isinstance(findings, list) and len(findings) >= _FRICTION_FINDINGS_MIN


def _detect_anomalies(evals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """target (plugin:skill) 単位で、episode に畳んでから異常を検出する。

    日付も時刻も無い episode は「直近」と言えないので窓から外す。
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in evals:
        target = _canonical_target(ev.get("skill") or ev.get("rubric_id"), ev.get("plugin"))
        if target:
            grouped[target].append(ev)

    anomalies: list[dict[str, Any]] = []
    for rubric_id, items in sorted(grouped.items()):
        episodes = [e for e in _coalesce_episodes(items) if not _date_sort_key(e)[0]]
        ordered = sorted(episodes, key=_date_sort_key)

        # 1) 連続 FAIL
        tail = ordered[-_CONSECUTIVE_FAIL_THRESHOLD:]
        if len(tail) == _CONSECUTIVE_FAIL_THRESHOLD and all(
            _verdict_is_fail(str(x.get("verdict", ""))) for x in tail
        ):
            anomalies.append(
                {
                    "rubric_id": rubric_id,
                    "kind": "consecutive_fail",
                    "count": _CONSECUTIVE_FAIL_THRESHOLD,
                    "evidence_dates": [x.get("date") for x in tail],
                    "evidence_observed_at": [x.get("observed_at") for x in tail],
                }
            )

        # 2) 平均スコア低下 (直近窓 vs それ以前)。score は 0..1 に揃えた値で比べる。
        scored = [score for x in ordered if (score := _score_of(x)) is not None]
        if len(scored) >= _RECENT_WINDOW + 1:
            recent = scored[-_RECENT_WINDOW:]
            prior = scored[:-_RECENT_WINDOW]
            drop = (sum(prior) / len(prior)) - (sum(recent) / len(recent))
            if drop >= _SCORE_DROP_THRESHOLD:
                anomalies.append(
                    {
                        "rubric_id": rubric_id,
                        "kind": "score_drop",
                        "drop": round(drop, 3),
                        "recent_mean": round(sum(recent) / len(recent), 3),
                        "prior_mean": round(sum(prior) / len(prior), 3),
                    }
                )

        # 3) 苦戦密度 (PASS verdict 内の摩擦シグナル。FAIL 非依存の第 3 条件)。
        recent_episodes = ordered[-_FRICTION_RECENT_WINDOW:]
        friction = [x for x in recent_episodes if _is_friction(x)]
        if len(friction) >= _FRICTION_MIN_EPISODES:
            anomalies.append(
                {
                    "rubric_id": rubric_id,
                    "kind": "friction_density",
                    "friction_episodes": len(friction),
                    "window": len(recent_episodes),
                    "evidence": [
                        {
                            "date": x.get("date"),
                            "observed_at": x.get("observed_at"),
                            "episode_id": x.get("episode_id"),
                            "source_kinds": x.get("source_kinds", []),
                            "iterations": x.get("iterations"),
                            "negative_feedback_count": x.get("negative_feedback_count"),
                            "findings_count": len(x.get("findings") or []),
                        }
                        for x in friction
                    ],
                }
            )
    return anomalies


def _top_finding_categories(evals: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for ev in evals:
        for f in ev.get("findings", []) or []:
            cat = None
            if isinstance(f, dict):
                cat = f.get("category") or f.get("rule") or f.get("kind")
            elif isinstance(f, str):
                cat = f
            if cat:
                counter[str(cat)] += 1
    return counter.most_common(5)


def _compute_summary(evals: list[dict[str, Any]]) -> dict[str, Any]:
    """episode 単位の件数・負の verdict の率・平均スコア (0..1)・digest の無いレビュー数。"""
    episodes = _coalesce_episodes(evals)
    total = len(episodes)
    negatives = sum(1 for e in episodes if _verdict_is_fail(str(e.get("verdict", ""))))
    scores = [s for s in (_score_of(e) for e in episodes) if s is not None]
    return {
        "total": total,
        "negative_rate": (negatives / total) if total else 0.0,
        "mean_score": round(sum(scores) / len(scores), 3) if scores else "n/a",
        "digest_missing": sum(1 for e in episodes if e.get("digest_missing")),
    }


# ===========================================================================
# snapshot: 前回の観測の選択、差分、排他、atomic write、描画
# ===========================================================================
# 前回の観測 (snapshot) は、書込先にある marker 付きの <date>-rubric-update.md のうち、今日より前で
# 最新のもの。本文の <!-- anomaly-state: {...} --> に {anomaly_id: fingerprint} を埋めておき、次の回は
# それと比べて new / changed / retired / ongoing に分ける。ongoing だけなら書かない。今日のドラフトは
# 「その日の、前の日に対する差分」で、同じ日の 2 回目以降は観測が変わったときだけ書き直す。

_SNAPSHOT_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-rubric-update\.md$")
_STATE_COMMENT_RE = re.compile(r"<!-- anomaly-state: (\{.*\}) -->")
# 0.2.x までのドラフトの異常の行。anomaly-state を持たない旧ドラフトも前回の観測として読む。
_LEGACY_ANOMALY_RE = re.compile(r"^- \*\*(.+?)\*\*: ([a-z_]+) — (\{.*\})$")


class Snapshot(NamedTuple):
    """前回の観測。error があれば読めなかった (呼び出し側は前回の観測を変えずに終える)。

    dataclass にしないのは、テストや shim が sys.modules に登録せずに読み込むため
    (dataclass は定義時に sys.modules から自分の module を引く)。
    """

    date: str
    path: Path
    state: dict[str, str]
    error: str | None = None


class _SinkBusy(Exception):
    """書込先の lock を待ち時間内に取れなかった。別の session が同じ書込先を更新している。"""


def _report_name(today: str) -> str:
    return f"{today}-rubric-update.md"


@contextmanager
def _sink_lock(directory: Path, wait: float | None = None) -> Iterator[None]:
    """書込先ごとに排他する。待つのは wait 秒 (既定 _LOCK_WAIT_SECONDS) まで。

    取れなければ _SinkBusy。lock ファイルは OS の一時ディレクトリに置き、repo と state には作らない。
    POSIX は flock、Windows は msvcrt.locking を、どちらも非ブロックで試す。
    """
    identity = hashlib.sha256(str(directory.resolve()).encode("utf-8")).hexdigest()[:20]
    lock_path = Path(tempfile.gettempdir()) / f"harness-aggregate-{identity}.lock"
    budget = _LOCK_WAIT_SECONDS if wait is None else wait
    with lock_path.open("a+b") as lock_file:
        if _fcntl is not None:
            backend = _fcntl

            def try_lock() -> bool:
                try:
                    backend.flock(lock_file.fileno(), backend.LOCK_EX | backend.LOCK_NB)
                except OSError as exc:
                    if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES):
                        return False
                    raise
                return True

            def unlock() -> None:
                backend.flock(lock_file.fileno(), backend.LOCK_UN)

        elif _msvcrt is not None:
            win = _msvcrt
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()

            def try_lock() -> bool:
                lock_file.seek(0)
                try:
                    win.locking(lock_file.fileno(), win.LK_NBLCK, 1)
                except OSError:
                    return False
                return True

            def unlock() -> None:
                lock_file.seek(0)
                win.locking(lock_file.fileno(), win.LK_UNLCK, 1)

        else:
            raise OSError("no supported advisory-lock backend")

        deadline = time.monotonic() + budget
        while not try_lock():
            if time.monotonic() >= deadline:
                raise _SinkBusy(str(directory))
            time.sleep(_LOCK_POLL_SECONDS)
        try:
            yield
        finally:
            unlock()


def _atomic_write_text(path: Path, text: str) -> None:
    """同じディレクトリの一時ファイルに書いて fsync し、os.replace で置き換える。

    途中で落ちても、読み手は古い版か新しい版のどちらかを丸ごと見る (半端な snapshot を残さない)。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s or "rubric"


def _anomaly_id(anomaly: dict[str, Any]) -> str:
    target = _canonical_target(anomaly.get("rubric_id")) or "unknown-target"
    return f"{target}#{_slugify(str(anomaly.get('kind', 'anomaly')))}"


def _anomaly_payload(anomaly: dict[str, Any]) -> dict[str, Any]:
    return {
        "target": _canonical_target(anomaly.get("rubric_id")) or "unknown-target",
        "kind": str(anomaly.get("kind", "anomaly")),
        **{key: value for key, value in anomaly.items() if key not in {"rubric_id", "kind"}},
    }


def _fingerprint_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _anomaly_fingerprint(anomaly: dict[str, Any]) -> str:
    return _fingerprint_payload(_anomaly_payload(anomaly))


def _snapshot_state(text: str) -> dict[str, str]:
    """ドラフトの本文から {anomaly_id: fingerprint} を読む。旧ドラフトは異常の行から組み直す。"""
    state_match = _STATE_COMMENT_RE.search(text)
    if state_match:
        try:
            state = json.loads(state_match.group(1))
        except json.JSONDecodeError:
            state = None
        if isinstance(state, dict):
            return {
                str(key): str(value)
                for key, value in state.items()
                if isinstance(key, str) and isinstance(value, str)
            }

    legacy: dict[str, str] = {}
    for line in text.splitlines():
        match = _LEGACY_ANOMALY_RE.match(line)
        if not match:
            continue
        target, kind, raw_details = match.groups()
        try:
            details = json.loads(raw_details)
        except json.JSONDecodeError:
            details = {}
        anomaly = {
            "rubric_id": _canonical_target(target) or target,
            "kind": kind,
            **(details if isinstance(details, dict) else {}),
        }
        legacy[_anomaly_id(anomaly)] = _anomaly_fingerprint(anomaly)
    return legacy


def _select_snapshot(directories: list[Path], before_date: str) -> Snapshot | None:
    """履歴のある最初の置き場から、before_date より前で最新の自動ドラフトを選ぶ。

    before_date の当日のドラフトは含めない (今日のドラフトは上書きされる側で、前回の観測ではない)。
    marker の無い同名ファイル (手書き) は前回の観測にしない。読めなければ error 付きで返し、
    呼び出し側は前回の観測を変えずに終える。
    """
    for directory in directories:
        if not directory.is_dir():
            continue
        try:
            candidates = sorted(
                (
                    (match.group(1), path)
                    for path in directory.iterdir()
                    if (match := _SNAPSHOT_NAME_RE.match(path.name))
                    and match.group(1) < before_date
                    and path.is_file()
                ),
                reverse=True,
            )
        except OSError:
            continue
        for date, path in candidates:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                return Snapshot(date, path, {}, str(exc))
            if _GENERATED_MARKER not in text:
                continue
            return Snapshot(date, path, _snapshot_state(text))
    return None


def _read_todays_draft(target: Path) -> Snapshot | None:
    """今日のドラフト (上書きする側) を読む。無ければ None。

    手書き (marker 無し) と読めないものは error 付きで返し、呼び出し側は書かずに終える。
    """
    if not target.exists():
        return None
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Snapshot("", target, {}, f"unreadable ({exc})")
    if _GENERATED_MARKER not in text:
        return Snapshot("", target, {}, "has no generated marker (hand-written)")
    return Snapshot("", target, _snapshot_state(text))


def _latest_snapshot(directories: list[Path], before_date: str) -> tuple[str | None, dict[str, str]]:
    snapshot = _select_snapshot(directories, before_date)
    return (snapshot.date, snapshot.state) if snapshot else (None, {})


def _align_legacy_state(baseline: dict[str, str], current: dict[str, str]) -> dict[str, str]:
    """plugin の無い旧 id (skill#kind) を、一意に決まる今回の plugin:skill#kind へ寄せる。"""
    aligned: dict[str, str] = {}
    for old_id, fingerprint in baseline.items():
        target, separator, kind = old_id.rpartition("#")
        if separator and ":" not in target:
            matches = [cid for cid in current if cid.endswith(f":{target}#{kind}")]
            if len(matches) == 1:
                aligned[matches[0]] = fingerprint
                continue
        aligned[old_id] = fingerprint
    return aligned


def _compute_delta(anomalies: list[dict[str, Any]], baseline: dict[str, str]) -> dict[str, Any]:
    """今回の異常を前回の観測と比べ、new / changed / resolved (retired) / ongoing に分ける。"""
    details = {_anomaly_id(anomaly): _anomaly_payload(anomaly) for anomaly in anomalies}
    current = {anomaly_id: _fingerprint_payload(payload) for anomaly_id, payload in details.items()}
    aligned_baseline = _align_legacy_state(baseline, current)
    current_ids = set(current)
    baseline_ids = set(aligned_baseline)
    new = sorted(current_ids - baseline_ids)
    retired = sorted(baseline_ids - current_ids)
    changed = sorted(
        anomaly_id
        for anomaly_id in current_ids & baseline_ids
        if current[anomaly_id] != aligned_baseline[anomaly_id]
    )
    ongoing = sorted((current_ids & baseline_ids) - set(changed))
    return {
        "state": current,
        "details": details,
        "new": new,
        "changed": changed,
        # 互換のキー名。表示では「解決した」とは言わない (観測されなくなっただけ)。
        "resolved": retired,
        "ongoing": ongoing,
        "actionable": bool(new or changed or retired),
    }


def _render_anomaly_delta(
    delta: dict[str, Any],
    summary: dict[str, Any],
    baseline_date: str | None,
    top_findings: list[tuple[str, int]] | None = None,
) -> str:
    today = _dt.date.today().isoformat()
    state_json = json.dumps(delta["state"], ensure_ascii=False, sort_keys=True)
    lines = [
        "---",
        f"date: {today}",
        "kind: rubric-anomaly-delta",
        "status: draft",
        "trigger: aggregate-evals (SessionEnd)",
        f"baseline: {baseline_date or 'none'}",
        "---",
        "",
        f"<!-- anomaly-state: {state_json} -->",
        "",
        "# rubric の異常の観測差分 (自動生成ドラフト)",
        "",
        "これは rubric 改正案ではなく、正式な提案の前に見る観測差分です。",
        "改正するときは `templates/proposal.json` で別に起票します。",
        "",
        "## 差分サマリ",
        "",
        f"- baseline: {baseline_date or 'なし'}",
        f"- new: {len(delta['new'])}",
        f"- changed: {len(delta['changed'])}",
        f"- retired / not reproduced: {len(delta['resolved'])}",
        f"- ongoing: {len(delta['ongoing'])}",
        f"- 評価 episode 件数: {summary.get('total', 0)}",
        f"- 負の verdict の率: {summary.get('negative_rate', 0.0):.2%}",
        f"- 平均スコア (0..1): {summary.get('mean_score', 'n/a')}",
        f"- skill_md_sha256 の無い content-review: {summary.get('digest_missing', 0)} 件"
        " (reviewed_at と日付で数えた)",
        "",
    ]
    for section, label, include_details in (
        ("new", "New", True),
        ("changed", "Changed", True),
        ("resolved", "Retired / not reproduced", False),
        ("ongoing", "Ongoing", False),
    ):
        lines.extend([f"## {label}", ""])
        identifiers = delta[section]
        if not identifiers:
            lines.append("- (なし)")
        elif include_details:
            for anomaly_id in identifiers:
                lines.append(
                    f"- **{anomaly_id}** — "
                    + json.dumps(
                        delta["details"][anomaly_id], ensure_ascii=False, sort_keys=True, default=str
                    )
                )
        else:
            lines.extend(f"- {anomaly_id}" for anomaly_id in identifiers)
        lines.append("")
    lines += ["## 主要 finding カテゴリ (top5)", ""]
    if not top_findings:
        lines.append("- (なし)")
    else:
        for cat, n in top_findings:
            lines.append(f"- {cat}: {n} 件")
    lines += [
        "",
        "## 次の手順 (要 human review)",
        "",
        "- New / Changed の target について、閾値や観点を見直すかを人が決める",
        "- 見直すなら `templates/proposal.json` で正式な改正提案を起票する",
        "- Retired / not reproduced は観測されなくなっただけで、解決の確認ではない",
        "",
        "## 備考",
        "",
        f"本ドラフトは {_GENERATED_MARKER}。PR 起票は別工程。",
        "",
    ]
    return "\n".join(lines)


def _render_proposal(
    anomalies: list[dict[str, Any]],
    top_findings: list[tuple[str, int]],
    summary: dict[str, Any],
) -> str:
    """前回の観測なしで描く薄いラッパ (全件 new)。既存の呼び出し側との互換のために残す。"""
    return _render_anomaly_delta(_compute_delta(anomalies, {}), summary, None, top_findings)


# ===========================================================================
# main: hook の経路と --list-proposals
# ===========================================================================


def main(argv: list[str] | None = None) -> int:
    # SessionEnd hook は引数を付けずに呼ぶ（hooks/hooks.json）。引数があれば手で流したとみなして argparse に渡す。
    # 知らない引数や綴りの誤りは exit 2 で止める。hook の経路へ落とすと、一覧のつもりで提案を書いてしまう。
    if argv:
        ap = argparse.ArgumentParser(
            allow_abbrev=False,
            description="引数なしでは SessionEnd hook として評価を集計し、前回の観測から差分があれば観測差分のドラフトを書く。",
        )
        ap.add_argument("--list-proposals", action="store_true", required=True,
                        help="書かずに、自動ドラフトと手書きの提案の両方の置き場を一覧する（JSON）")
        ap.parse_args(argv)
        listing = _list_proposals()
        if not os.environ.get("CLAUDE_PROJECT_DIR"):
            print("[aggregate-evals] CLAUDE_PROJECT_DIR が無いので、cwd と git の作業ツリーの root を "
                  "project とみなして読んだ。見た置き場は dirs にある", file=sys.stderr)
        print(json.dumps(listing, ensure_ascii=False, indent=2))
        return 0

    # stdin は SessionEnd hook payload。本 script では使わないが drain しておく。
    try:
        sys.stdin.read()
    except Exception:  # 捨てる payload なので、stdin が None・閉じている・decode できないのどれでも集計へ進む
        pass

    data = _load_evals()
    health = data["health"]
    if not health["complete"]:
        # 欠けた入力で比べると、消えていない異常を retired と書いてしまう。前回の観測は変えない。
        sys.stderr.write(
            "[aggregate-evals] incomplete source; snapshot unchanged: "
            + "; ".join(health["errors"])
            + "\n"
        )
        return 0

    evals = data.get("evaluations", []) or []
    if not evals:
        return 0

    anomalies = _detect_anomalies(evals)
    summary = _compute_summary(evals)
    top_findings = _top_finding_categories(evals)
    today = _dt.date.today().isoformat()
    filename = _report_name(today)

    # 書込可能な最初の候補へ (_candidate_proposals_dirs の順)。全滅なら silent no-op exit 0。
    # 前回の観測の選択と書き込みは同じ lock の中で行う。
    directories = _candidate_proposals_dirs()
    last_exc: OSError | None = None
    for out_dir in directories:
        if not _dir_is_writable(out_dir):
            continue
        try:
            with _sink_lock(out_dir):
                # 前回の観測は、前の日までの最新の自動ドラフト。今日のドラフトを前回にすると、
                # 同じ日の 2 回目の上書きで 1 回目の New が根拠の無い Ongoing に下がる。
                # 退避先に書くときだけ、それより優先する置き場の履歴を借りる。後ろの置き場
                # (全 project が共有する ~/.claude/state など) は読まない。別の project の観測が混ざる。
                history = [out_dir, *directories[: directories.index(out_dir)]]
                snapshot = _select_snapshot(history, today)
                if snapshot is not None and snapshot.error:
                    sys.stderr.write(
                        "[aggregate-evals] unreadable snapshot; snapshot unchanged: "
                        f"{snapshot.path}: {snapshot.error}\n"
                    )
                    return 0
                target = out_dir / filename
                todays = _read_todays_draft(target)
                if todays is not None and todays.error:
                    sys.stderr.write(f"[aggregate-evals] {target}: {todays.error}; left unchanged\n")
                    return 0
                delta = _compute_delta(anomalies, snapshot.state if snapshot else {})
                # 今日のドラフトがあれば、観測が変わったときだけ上書きする (前の日との差分が
                # 消えた場合も、古い New を残さないよう書き直す)。無ければ差分があるときだけ書く。
                up_to_date = (
                    todays.state == delta["state"] if todays is not None else not delta["actionable"]
                )
                if up_to_date:
                    if delta["state"]:
                        sys.stderr.write(
                            f"[aggregate-evals] no anomaly delta (ongoing {len(delta['state'])}); "
                            "snapshot unchanged\n"
                        )
                    return 0
                report = _render_anomaly_delta(
                    delta, summary, snapshot.date if snapshot else None, top_findings
                )
                _atomic_write_text(target, report)
            sys.stderr.write(
                f"[aggregate-evals] proposal -> {target} (new {len(delta['new'])} / "
                f"changed {len(delta['changed'])} / retired {len(delta['resolved'])} / "
                f"ongoing {len(delta['ongoing'])})\n"
            )
            return 0
        except _SinkBusy:
            # 別の session が同じ書込先を更新している。待たずに飛ばし、次の SessionEnd で追いつく。
            # 退避先へ書くと前回の観測が 2 か所に分かれるので、退避もしない。
            sys.stderr.write(f"[aggregate-evals] sink busy, skipped: {out_dir}\n")
            return 0
        except OSError as exc:
            last_exc = exc
            continue
    # どこにも書けない (read-only install 等): クラッシュさせず no-op で握る。
    if last_exc is not None:
        sys.stderr.write(f"[aggregate-evals] no writable sink, skipped: {last_exc}\n")
    else:
        sys.stderr.write("[aggregate-evals] no writable sink, skipped\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
