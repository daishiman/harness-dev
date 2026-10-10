#!/usr/bin/env python3
# /// script
# name: re-evaluate-on-rubric-bump
# version: 0.3.0
# purpose: List skills that require re-evaluation after a rubric major bump.
# inputs:
#   - argv: --rubric PATH (optional), --eval-log-dir PATH (optional), --post-tool-use (optional)
#   - env: EVAL_LOG_DIR / PROJECT_ROOT (optional。write-eval-log.py と同じ置き場を読む)
#   - stdin: --post-tool-use のときだけ、Claude Code の PostToolUse hook の JSON
# outputs:
#   - stdout: re-evaluation target list (skill ごとに最新の版で1行)。--post-tool-use では
#             PostToolUse の JSON (hookSpecificOutput.additionalContext に一覧と警告を入れる)
#   - stderr: missing or unreadable upstream rubric, unreadable score records, best-effort で読み飛ばした過去評価ログ
# contexts: [E]
# requires-python: ">=3.9"
# network: false
# write-scope: none
# dependencies: [extract-plugin-root.py]
# ///
"""re-evaluate-on-rubric-bump.py — major bump 時の再評価対象リストアップ.

現 rubric_version（upstream = 兄弟 plugin harness-creator の
skills/ref-skill-design-rubric/references/rubric.json）と、eval-log/ 直下の
過去評価ログおよび eval-log/<plugin>/*-score.jsonl（score ログ）に記録された
rubric_version を比較し、**major bump** が発生している場合に再評価が必要な
スキル一覧を列挙する。

挙動:
  - 実行はせず、対象リストを stdout に出力するのみ。
  - upstream rubric は同梱の scripts/extract-plugin-root.py で harness-creator の
    root を解決して読む（install 先では親ディレクトリ経由で兄弟に届かないため）。
    ``--rubric`` で明示もできる。
  - eval-log の置き場は ``--eval-log-dir`` → 環境変数 ``EVAL_LOG_DIR`` →
    ``$PROJECT_ROOT/eval-log`` → 作業ディレクトリの ``eval-log/`` の順で決める。
    score ログを書く write-eval-log.py と同じ順で、書いた場所と読む場所をずらさない。
  - ``--post-tool-use``: Claude Code の PostToolUse hook として動く。stdin の
    tool_input.file_path が比べる相手の upstream rubric.json そのもののときだけ走査し、
    それ以外の編集（別の rubric.json を含む）では何も出さない（upstream を解決できない
    ときは、それを知らせるために走査する）。結果は stdout の JSON の
    hookSpecificOutput.additionalContext に入れて Claude の文脈に届ける（素の stdout は
    transcript にしか出ない）。hook は通知だけなので、走査の結果が exit 2 でも 0 を返す
    （編集を止めない）。
  - exit 0: 走査できた（対象あり / 無し / eval-log 不在・空を含む）。
  - exit 2: upstream rubric が見つからない・読めない・rubric_version を解釈できない。
    または score ログに版を読めない行がある（対象リストは出力したうえで 2）。
    eval-log の path がディレクトリでない・一覧できないときも 2。
    入力の欠落を成功に畳まない。score ログ以外の過去評価ログ（eval-log/ 直下の
    .json/.jsonl）は best-effort で、非 UTF-8・壊れた JSON の行やファイルは読み飛ばし、
    その数を stderr に出す（exit は 0 のまま）。.jsonl は行ごとに読むので、壊れた行の
    前後の有効な行は拾う。
  - score ログの版は rubric.rubric_version（入れ子）だけを見る。各行がこれを持つ契約
    なので、無い行は最上位の rubric_version などで補わず、読めない行として数える。
  - eval-log/ 直下の記録の版は rubric.rubric_version → rubric_version → current_version →
    target_version の順に見る。汎用の version キーは、rubric と関係の無い文書
    （handoff.json など）を拾うので見ない。
  - rubric_id（入れ子か最上位）が upstream の rubric_id と違う記録は、別の rubric の版
    なので比べない（数を stdout に出す）。rubric_id の無い記録は比べる。
  - 対象スキル: skill_name / target_skill / skill / proposal_id / proposer。同じスキルの
    記録が複数あれば、版の最も新しい記録だけで判定する（現行の major で評価し直した
    スキルは対象から外れる）。plugin が違えば、同じ名前のスキルでも別のスキルとして扱う
    （plugA の run-x を 1.x で、plugB の run-x を 2.x で評価していれば、plugA の run-x は
    対象に残る）。plugin は、値の中の plugins/<plugin>/skills/<skill>（絶対パスでも、
    どの checkout のパスでも同じスキルになる）→ 記録の plugin → score ログの置き場
    eval-log/<plugin>/ の順で決める。plugin の分からない記録（eval-log/ 直下の記録など）は、
    plugin の分かる記録とまとめない（安全側: 対象に多めに出る）。スキルを特定できない
    記録はファイルごとにまとめ、そのファイルの中で最も新しい版で判定する。
  - 一覧の (from ...) は、score ログなら <plugin の置き場>/<ファイル名>、eval-log/ 直下の
    記録ならファイル名を出す。
  - eval-log/ 直下の *.json / *.jsonl は種類の混ざった置き場なので best-effort に拾う。
    score ログは各行が版を持つ契約なので、壊れた行・版の無い行を数えて報告する。

stdlib only / Python 3.9+.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUBRIC_REL = Path("skills") / "ref-skill-design-rubric" / "references" / "rubric.json"
# None のときは実行時に解決する (rubric は harness-creator の root、eval-log は cwd)。
UPSTREAM_RUBRIC: Path | None = None
EVAL_LOG_DIR: Path | None = None

VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
SCORE_LOG_GLOB = "*/*-score.jsonl"


def parse_semver(s: str | None) -> tuple[int, int, int] | None:
    """Extract the first semver-like (X.Y.Z) triple from a string."""
    if not s:
        return None
    m = VERSION_RE.search(str(s))
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def iter_records(path: Path, skipped: list[str] | None = None) -> Iterable[dict]:
    """Yield JSON records from .json (object or array) and .jsonl files.

    best-effort: 非 UTF-8・壊れた JSON・深すぎる入れ子は読み飛ばす。.jsonl は行ごとに
    decode するので、1行が壊れていても他の行は拾う。skipped を渡すと、読み飛ばした
    ファイルや行を ``<name>`` / ``<name>:<行番号>`` で足す。
    """
    def skip(where: str) -> None:
        if skipped is not None:
            skipped.append(where)

    try:
        if path.suffix == ".jsonl":
            with path.open("rb") as f:
                for lineno, raw in enumerate(f, 1):
                    try:
                        line = raw.decode("utf-8").strip()
                        if not line:
                            continue
                        rec = json.loads(line)
                    except (ValueError, RecursionError):
                        skip(f"{path.name}:{lineno}")
                        continue
                    if isinstance(rec, dict):
                        yield rec
        else:
            with path.open("r", encoding="utf-8") as f:
                doc = json.load(f)
            if isinstance(doc, list):
                for rec in doc:
                    if isinstance(rec, dict):
                        yield rec
            elif isinstance(doc, dict):
                yield doc
    except (OSError, ValueError, RecursionError):
        skip(path.name)
        return


def extract_version(rec: dict, *, generic: bool = True) -> tuple[int, int, int] | None:
    """記録の rubric の版。generic=False なら汎用の version キーは見ない (eval-log/ 直下の走査)。"""
    nested = rec.get("rubric")
    if isinstance(nested, dict):
        v = parse_semver(nested.get("rubric_version"))
        if v is not None:
            return v
    keys = ("rubric_version", "current_version", "target_version") + (("version",) if generic else ())
    for key in keys:
        v = parse_semver(rec.get(key))
        if v is not None:
            return v
    return None


def score_log_version(rec: dict) -> tuple[int, int, int] | None:
    """score ログの版。契約は入れ子の rubric.rubric_version なので、ほかのキーで補わない。"""
    nested = rec.get("rubric")
    return parse_semver(nested.get("rubric_version")) if isinstance(nested, dict) else None


def extract_rubric_id(rec: dict) -> str | None:
    nested = rec.get("rubric")
    for value in ((nested.get("rubric_id") if isinstance(nested, dict) else None), rec.get("rubric_id")):
        if isinstance(value, str) and value:
            return value
    return None


def read_score_log(path: Path) -> tuple[list[dict], int]:
    """score ログを読み、(版を読めた記録, 読めなかった行の数) を返す。

    score ログは各行が rubric.rubric_version を持つ契約なので、壊れた行・object で
    ない行・版の無い行を黙って捨てず unreadable として数える。
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return [], 1
    records: list[dict] = []
    unreadable = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (ValueError, RecursionError):
            unreadable += 1
            continue
        if not isinstance(rec, dict) or score_log_version(rec) is None:
            unreadable += 1
            continue
        records.append(rec)
    return records, unreadable


IDENTITY_KEYS = ("skill_name", "target_skill", "skill", "proposal_id", "proposer")


# 値の中の plugins/<plugin>/skills/<skill>。SKILL.md の絶対パスを skill_name に書く記録がある
_SKILL_DIR = re.compile(r"(?:^|/)plugins/([^/]+)/skills/([^/]+)")


def extract_skill_identity(rec: dict, source: Path, label: str | None = None) -> str:
    """一覧に出す表示名。label が無ければ source のファイル名を出す。"""
    shown = label or source.name
    for key in IDENTITY_KEYS:
        if rec.get(key):
            return f"{rec[key]} (from {shown})"
    return f"<unknown> (from {shown})"


def skill_key(rec: dict, source: Path, plugin_dir: str | None = None) -> tuple[str, ...]:
    """同じスキルの記録をまとめる key。plugin が違えば同じ名前でも別のスキルにする。

    plugin は、値の中の plugins/<plugin>/skills/<skill> → 記録の plugin → score ログの
    置き場 (plugin_dir) の順で決める。特定できない記録はファイルごとにまとめる。
    """
    for key in IDENTITY_KEYS:
        value = rec.get(key)
        if value:
            text = str(value).replace("\\", "/")
            found = list(_SKILL_DIR.finditer(text))
            if found:
                return ("skill", found[-1].group(1), found[-1].group(2))
            plugin = rec.get("plugin")
            if not isinstance(plugin, str) or not plugin:
                plugin = plugin_dir or ""
            return ("skill", plugin, text)
    return ("unknown", str(source))


def resolve_upstream_rubric() -> Path | None:
    """兄弟 plugin harness-creator を同梱の extract-plugin-root.py で解決し、L0 rubric の path を返す。"""
    resolver = PLUGIN_ROOT / "scripts" / "extract-plugin-root.py"
    # spec_from_file_location は実在しない path にも spec を返すので、先に実在を確かめる。
    spec = importlib.util.spec_from_file_location("_extract_plugin_root", resolver) if resolver.is_file() else None
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    found = module.resolve("harness-creator", PLUGIN_ROOT, Path.cwd())
    return None if found is None else found / RUBRIC_REL


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="rubric の major bump 後に再評価が必要なスキルを列挙する (書き込みなし)。"
    )
    parser.add_argument("--rubric", type=Path, help="upstream の L0 rubric.json (既定: harness-creator から解決)")
    parser.add_argument(
        "--eval-log-dir", type=Path,
        help="過去評価ログの置き場 (既定: $EVAL_LOG_DIR → $PROJECT_ROOT/eval-log → ./eval-log)",
    )
    parser.add_argument(
        "--post-tool-use", action="store_true",
        help="PostToolUse hook として動く: upstream の rubric.json の編集のときだけ走査し、常に exit 0",
    )
    return parser.parse_args(argv)


def default_eval_log_dir() -> Path:
    """write-eval-log.py が score ログを書く場所と同じ順で、eval-log の置き場を決める。"""
    if EVAL_LOG_DIR is not None:
        return EVAL_LOG_DIR
    base = os.environ.get("EVAL_LOG_DIR")
    if base:
        return Path(base)
    project_root = os.environ.get("PROJECT_ROOT")
    if project_root:
        return Path(project_root) / "eval-log"
    return Path.cwd() / "eval-log"


def edited_rubric_path(payload_text: str) -> str | None:
    """PostToolUse の payload から、編集されたのが rubric.json ならその path を返す。"""
    try:
        payload = json.loads(payload_text)
    except (ValueError, RecursionError):
        return None
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if isinstance(file_path, str) and Path(file_path).name == "rubric.json":
        return file_path
    return None


def _tolerate_unencodable_output() -> None:
    """PYTHONIOENCODING=ascii などでも、非 ASCII の skill 名で UnicodeEncodeError にしない。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="backslashreplace")
            except (ValueError, OSError):
                pass


def upstream_rubric_path(args: argparse.Namespace) -> Path | None:
    return args.rubric or UPSTREAM_RUBRIC or resolve_upstream_rubric()


def _same_file(edited: str, upstream: Path | None) -> bool:
    if upstream is None:
        return False
    try:
        return Path(edited).resolve() == upstream.resolve()
    except (OSError, RuntimeError, ValueError):
        return False


def main(argv: list[str] | None = None) -> int:
    _tolerate_unencodable_output()
    args = parse_args([] if argv is None else argv)
    if not args.post_tool_use:
        return scan(args)
    try:
        payload = "" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read()
        edited = edited_rubric_path(payload)
        if edited is None:
            return 0
        # 比べる相手は upstream の L0 だけなので、別の rubric.json の編集では走査しない。
        # upstream を解決できないときは、そのこと自体を知らせるために走査する。
        upstream = upstream_rubric_path(args)
        if upstream is not None and not _same_file(edited, upstream):
            return 0
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = scan(args)
        parts = [f"# rubric edited: {edited}", out.getvalue().rstrip(), err.getvalue().rstrip()]
        if code != 0:
            parts.append("# re-evaluate scan exited 2 (see above); hook mode only notifies")
        # 素の stdout は transcript にしか出ない。additionalContext に入れて Claude の文脈に届ける
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(part for part in parts if part),
        }}, ensure_ascii=False))
    except Exception as exc:  # hook は通知だけ。どんな失敗でも編集を止めない (常に exit 0)
        print(f"# re-evaluate hook skipped: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 0


def scan(args: argparse.Namespace) -> int:
    rubric = upstream_rubric_path(args)
    eval_log_dir = args.eval_log_dir or default_eval_log_dir()
    if rubric is None:
        print("# upstream rubric not found: harness-creator plugin is not resolvable", file=sys.stderr)
        return 2
    if not rubric.is_file():
        print(f"# upstream rubric not found: {rubric}", file=sys.stderr)
        return 2

    try:
        with rubric.open("r", encoding="utf-8") as f:
            upstream = json.load(f)
    except (OSError, ValueError, RecursionError) as exc:
        print(f"# could not read upstream rubric {rubric}: {exc}", file=sys.stderr)
        return 2
    current = parse_semver(upstream.get("rubric_version")) if isinstance(upstream, dict) else None
    upstream_id = extract_rubric_id(upstream) if isinstance(upstream, dict) else None
    if current is None:
        print(
            f"# could not parse upstream rubric_version in {rubric}; aborting",
            file=sys.stderr,
        )
        return 2

    if not eval_log_dir.exists():
        print(f"# no eval-log directory at {eval_log_dir}; nothing to do")
        return 0
    if not eval_log_dir.is_dir():
        print(f"# eval-log path is not a directory: {eval_log_dir}", file=sys.stderr)
        return 2

    try:
        log_files = sorted(
            [p for p in eval_log_dir.iterdir() if p.suffix in (".json", ".jsonl")]
        )
        score_logs = sorted(eval_log_dir.glob(SCORE_LOG_GLOB))
    except OSError as exc:
        print(f"# could not list eval-log directory {eval_log_dir}: {exc}", file=sys.stderr)
        return 2
    if not log_files and not score_logs:
        print("# eval-log/ is empty; nothing to re-evaluate")
        return 0

    # skill ごとに、版の最も新しい記録 (表示名, 版) を残す
    latest: dict[tuple[str, str], tuple[str, tuple[int, int, int]]] = {}
    other_rubric = 0

    def consider(rec: dict, path: Path, past: tuple[int, int, int] | None, plugin_dir: str | None = None) -> None:
        nonlocal other_rubric
        if past is None:
            return
        rubric_id = extract_rubric_id(rec)
        if upstream_id is not None and rubric_id is not None and rubric_id != upstream_id:
            other_rubric += 1
            return
        key = skill_key(rec, path, plugin_dir)
        if key not in latest or past > latest[key][1]:
            label = f"{plugin_dir}/{path.name}" if plugin_dir else path.name
            latest[key] = (extract_skill_identity(rec, path, label), past)

    skipped: list[str] = []
    for path in log_files:
        for rec in iter_records(path, skipped):
            consider(rec, path, extract_version(rec, generic=False))
    if skipped:
        print(f"# best-effort: skipped {len(skipped)} unreadable log file(s)/line(s): {', '.join(skipped)}",
              file=sys.stderr)
    unreadable = 0
    for path in score_logs:
        records, bad = read_score_log(path)
        if bad:
            print(f"# unreadable score records: {path} ({bad})", file=sys.stderr)
            unreadable += bad
        for rec in records:
            # SCORE_LOG_GLOB は */*-score.jsonl なので、親ディレクトリが plugin の置き場
            consider(rec, path, score_log_version(rec), path.parent.name)
    # major bump = upstream major > そのスキルの最新の記録の major
    targets = [(ident, past) for ident, past in latest.values() if current[0] > past[0]]

    current_str = ".".join(map(str, current))
    print(f"# upstream rubric_version: {current_str}")
    print(f"# eval-log files scanned: {len(log_files) + len(score_logs)}")
    if other_rubric:
        print(f"# records of another rubric_id (not compared with {upstream_id}): {other_rubric}")
    print(f"# re-evaluation targets (major bump detected): {len(targets)}")
    print("")
    if not targets:
        if unreadable:
            print("# no major bump detected among readable records.")
        else:
            print("# no major bump detected against any logged evaluation. OK.")
    else:
        print("# target list (skill / past_version -> current_version):")
        for ident, past in targets:
            past_str = ".".join(map(str, past))
            print(f"- {ident}\tpast={past_str}\tcurrent={current_str}")
    if unreadable:
        print(
            f"# {unreadable} score record(s) had no readable rubric_version; "
            "the target list may be incomplete",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
