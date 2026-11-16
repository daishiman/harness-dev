#!/usr/bin/env python3
# /// script
# name: sync-content-review-sha
# purpose: content-review verdict の指摘を SKILL.md へ適用した直後 (変更が挙げた指摘の節に収まるとき)、登録済みの機械的な移行を当てた直後 (再生して bytes が一致するとき)、または変えた節だけを独立 reviewer が読み直して PASS を出した直後 (範囲つき再レビュー) に限り、elegance / rubric の 2 verdict の target.skill_md_sha256 を現在の SKILL.md に結び直し、sha_rebinds[] に監査記録を 1 件足す。条件を満たさない編集は結び直さず、scripts/lint-content-review.py の stale-sha のまま再レビューへ回す。
# inputs:
#   - argv: --plugin <plugin> --skill <skill> --from-sha <適用前の SKILL.md sha256> (--finding-ids <elegance:N,rubric:N,F-0003,...> | --replay <移行 id> | --scoped-review <範囲つき再レビュー JSON>) [--from-file <適用前の SKILL.md>] [--repo-root <path> (既定 .)] [--dry-run]
#   - git: --from-file が無いとき、適用前の SKILL.md を index → HEAD → 直近 64 commit の順に探す (sha256 が --from-sha と一致する版)
# outputs:
#   - stdout: 結果 1 行 JSON {"status": "rebound"|"dry-run"|"noop"|"already-bound", "plugin", "skill", "from_sha", "to_sha", "finding_ids", "replay", "scoped_review", "verdicts"}
#   - stderr: 拒否理由 (REJECT: ...) と要再レビューの案内 / 引数・入出力のエラー
#   - exit: 0=結び直し・dry-run・noop・already-bound / 1=条件を満たさず拒否 (ファイルは変えない。要再レビュー) / 2=引数・入出力の誤り
# contexts: [A, B]
# network: false
# write-scope: <repo-root>/eval-log/<plugin>/<skill>/content-review/{elegance,rubric}-verdict.json の 2 ファイル (target.skill_md_sha256 の更新、target.reviewed_skill_md_sha256 が無ければその記入、sha_rebinds[] への追記。ほかのキーは書き換えない) と、--scoped-review のときだけ同じ場所の scoped-reviews/<to_sha>.json (レビューの写し) 1 ファイル。--dry-run は書かない
# dependencies: []
# requires-python: ">=3.9"
# ///
"""レビュー由来の修正を適用した直後に、content-review verdict の sha を結び直す。

なぜ要るか:
  scripts/lint-content-review.py は verdict の target.skill_md_sha256 と現在の SKILL.md の
  sha256 の完全一致を求める。レビューが勧めた修正を当てただけでも sha が変わって stale-sha に
  なり、再レビュー → 新しい指摘 → 編集 → stale-sha と周回していた。根本原因は「レビュー由来の
  修正」と「審査なしの書き換え」を区別できないこと。本 script は lint を 1 行も変えず、
  前者に限って verdict を結び直す。後者はこれまでどおり stale-sha で FAIL する。

結び直す条件 (すべて満たすときだけ。1 つでも欠ければ理由を stderr に出して exit 1、ファイルは変えない):
  a. elegance-verdict.json と rubric-verdict.json が両方あり、どちらも verdict == "PASS"。
     FAIL / INCOMPLETE の verdict は修正を当てても PASS にならない (再レビューが要る)。
     target.plugin / target.skill が引数の skill と一致すること。
  b. 両 verdict の target.skill_md_sha256 が --from-sha と一致する
     (= verdict が適用前の内容に対する判定だと示せる)。
  c. (--finding-ids のとき) id が空でなく、各 id が下の照合規則で verdict の指摘に解決でき、
     まだどの sha_rebinds[] にも使われていない (1 つの指摘で結び直せるのは 1 回だけ)。
     使用済みかは id と指摘本文の両方で見る。2 verdict に同じ本文の指摘が並ぶとき、
     片方の id で結び直した指摘をもう片方の id で再び使うことはできない
     (1 回の呼び出しで両方の id を並べるのはよい)。
  d. (--finding-ids のとき) 変更が、挙げた指摘の節に収まっている (下の「変更箇所の照合」)。未使用の id を 1 つ
     挙げればどんな編集でも結び直せた穴 (fail-open) を塞ぐ (harness-g67)。
  e. verdict が target.skill_dir_digest を持つなら、それが現在の skill ディレクトリの digest
     (feedback_contract_ssot.content_review_dir_digest) と一致する。references/ などを
     変えたあとは結び直せない。

変更箇所の照合 (--finding-ids のとき):
  適用前の SKILL.md (--from-file か git から、sha256 が --from-sha と一致する版) と現在の
  SKILL.md を見出しで節に分けて比べる。次のどれかなら拒否する (要再レビュー)。
    - frontmatter が変わった。
    - 見出しが増えた・減った・変わった・並び替わった。
    - 最初の見出しより前が変わった。
    - 挙げた指摘に finding_locations の節が無い。節が適用前の SKILL.md に無い、一意に
      決まらない (「親 > 子」で書く)、または文書全体の見出し (#) である。
    - 変わった節が、挙げた指摘の節 (とその下位の節) のどれにも入らない。
    - 範囲つき再レビューと同じ上限と約束の保護に触れる: 変わった節が 3 を超える、変わった行が
      60 を超える、変わった節が入出力契約の中にある、または criteria が名指す節 (とその下位) にある。
      経路で境目が違うと、大きな変更ほど緩い経路で通せてしまうため。
  finding_locations は verdict の最上位にあり、"<review_kind>:<n>" ごとに
  {"sections": ["<見出し>" か "<親> > <子>", ...]} を持つ。レビューが指摘と一緒に書く。

範囲つき再レビューの結び直し (--scoped-review <JSON>):
  指摘を当てた後の追加の手直しなど、指摘の節に収まらない小さな変更を、全体レビューをやり直さずに
  結び直す (harness-g67 step 5)。変更した本人ではない reviewer が、変わった節だけを読み直して
  次の JSON を書く。
    {"kind": "scoped-content-review", "plugin", "skill", "from_sha", "to_sha",
     "sections": ["<見出し>" か "<親> > <子>", ...], "verdicts": {"elegance": "PASS", "rubric": "PASS"},
     "negative_feedback": [], "reviewer": "<独立 reviewer>", "reviewed_at": "YYYY-MM-DDTHH:MM:SSZ"}
  次のどれかなら拒否する (全体の再レビューが要る)。上限は feedback_contract_ssot.SCOPED_REVIEW_*。
    - kind / plugin / skill / from_sha / to_sha が今回の結び直しと合わない。
    - 両 verdict が PASS でない、negative_feedback が空でない (指摘があれば直してから全体レビュー)。
    - reviewer が無い、または root / self / elegant-improvement-executor (書いた本人と同じ context)。
    - frontmatter・見出し・最初の見出しより前が変わった。
    - 変わった節が sections の外にある、sections が 3 を超える、変わった行が 60 を超える。
    - sections のどれかが入出力契約 ("Purpose & Output Contract" / "入出力契約") を名指す
      (「親 > 子」のどの段でも。scripts/lint-content-review.py と同じ規則)。
    - 変わった節が入出力契約の中にある、または変わった節かその祖先 (# を除く) の見出しが
      frontmatter の feedback_contract (criteria) に書かれている。
    - 2 verdict の target.reviewed_skill_md_sha256・skill_dir_digest・sha_rebinds が食い違う
      (lint の pair-mismatch。どの経路でも書く前に止める)。
    - 前の全体レビューから数えて、範囲つき再レビューがすでに 2 回ある (3 回目は全体レビューへ)。
    - verdict が rebinds を持つのに target.reviewed_skill_md_sha256 が無い (起点の全体レビューが不明)。
  通ったら、レビューの写しを content-review/scoped-reviews/<to_sha>.json に置き、sha_rebinds[] に
  {from_sha, to_sha, scoped_review: {sections, reviewer, reviewed_at, review_ref, review_sha256},
  rebound_at, tool} を足す。scripts/lint-content-review.py は写しの sha256 と中身を照合する。

finding id の別名 (source id):
  レビューが finding_locations["<review_kind>:<n>"].source_id に元の id (例: F-0003, R5-01) を
  書いていれば、--finding-ids にその id を渡せる。2 verdict が同じ source_id を持てば、その id
  1 つで両方の指摘を使う。どの verdict にも無い source id は拒否する。sha_rebinds[] には
  解決後の <review_kind>:<n> を記録する。

機械的な移行の結び直し (--replay <移行 id>):
  REPLAYS に登録した決定的な変換を適用前の SKILL.md に当て直し、結果が現在の SKILL.md と
  bytes で一致するときだけ結び直す (指摘の id は使わない)。変換は内容の意味を変えないことを
  変換の持ち主が test で示したもの、または全 skill 共通の契約の定型語句だけを置き換え、表の外を
  1 文字も変えないことを test で示したものだけを登録する。いまは artifact-delivery-v1
  (契約の写しを契約 id の参照へ置き換える harness-vvd の移行) と diagnostic-choice-2way
  (初回の選択肢を 4 択から accept-as-is / diagnose の 2 択へ書き換える harness-znj の移行) である。

finding id の照合規則:
  実在の content-review verdict (eval-log/*/*/content-review/*.json。harness-creator の 38 本を含め
  全 plugin で findings[] 配列も指摘ごとの id も持たない) では、指摘は
  feedback_loop.negative_feedback[] の自由文で並ぶだけである。文中に "N2" "PKG-006" "IN1" の
  ような記号を含むものもあるが書式がそろわず、別の verdict と同じ記号がぶつかるので id に使えない。
  そこで id を「<review_kind>:<n>」と決める。
    - <review_kind> は verdict のファイル名で決まる elegance / rubric。
    - <n> はその verdict の feedback_loop.negative_feedback[] の 1 始まりの位置。
    例: elegance:2 = elegance-verdict.json の negative_feedback の 2 番目。
  negative_feedback は本 script も含め誰も書き換えず、再レビューは verdict ファイルごと
  置き換えるので、位置は 1 つの verdict が生きているあいだ変わらない。
  negative_feedback が空の verdict (指摘なしの PASS) には引ける id が無いので、その後の
  SKILL.md の編集は結び直せず、再レビューになる。

noop と冪等性:
  - 現在の SKILL.md の sha が --from-sha と同じなら何もしない (exit 0, status=noop)。
  - 両 verdict がすでに現在の sha に結ばれていれば何もしない (exit 0, status=already-bound)。
    同じ引数で 2 回呼んでも 2 件目の記録は足さない。

書き込み:
  両 verdict の target.skill_md_sha256 を現在の sha に変え、sha_rebinds[] に
  {from_sha, to_sha, finding_ids, rebound_at (UTC ISO8601), tool} を 1 件足す。
  verdict / reviewer / reviewed_at / iterations / feedback_loop は変えない。
  元ファイルの indent・ensure_ascii・末尾改行に合わせて書き、一時ファイル + os.replace で置き換える。
  2 本目の置き換えに失敗したら 1 本目を元の内容へ戻す。

Usage:
  python3 sync-content-review-sha.py --plugin harness-creator --skill run-foo \\
      --from-sha <64 桁 hex> --finding-ids elegance:1,rubric:2 [--from-file before.md] [--repo-root .] [--dry-run]
  python3 sync-content-review-sha.py --plugin harness-creator --skill run-foo \\
      --from-sha <64 桁 hex> --replay artifact-delivery-v1 [--repo-root .] [--dry-run]
  python3 sync-content-review-sha.py --plugin harness-creator --skill run-foo \\
      --from-sha <64 桁 hex> --scoped-review scoped-review.json [--from-file before.md] [--repo-root .] [--dry-run]
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TOOL = "sync-content-review-sha"
VERDICT_FILES = (("elegance", "elegance-verdict.json"), ("rubric", "rubric-verdict.json"))
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
FINDING_ID_RE = re.compile(r"^(elegance|rubric):([1-9][0-9]*)$")
# レビューが finding_locations[*].source_id に書く元の id (例: F-0003, R5-01)。
SOURCE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+$")
REVIEWED_AT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
GIT_HISTORY_DEPTH = 64
# 再生で確かめる機械的な移行。id -> (repo-root からの module の path, 変換関数の名前)。
# 変換は SKILL.md の全文を受けて新しい全文を返す (対象が無ければ None、当てられなければ例外)。
REPLAYS = {
    "artifact-delivery-v1": ("scripts/lint-entrypoint-artifact-first.py", "rewrite_copied_contract"),
    "diagnostic-choice-2way": ("scripts/lint-entrypoint-artifact-first.py", "rewrite_diagnostic_choices"),
}
SSOT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "feedback_contract_ssot.py"
RE_REVIEW_HINT = (
    "要再レビュー: verdict JSON を手で書き換えず、content-review をやり直してください "
    "(plugins/harness-creator/skills/run-build-skill/references/content-review-protocol.md"
    " の「レビュー由来の修正後の sha 結び直し」)。"
)


class Reject(Exception):
    """結び直しの条件を満たさない (exit 1)。"""


class UsageError(Exception):
    """引数・入出力の誤り (exit 2)。"""


def _parse_finding_ids(raw: str) -> list[str]:
    ids: list[str] = []
    for part in raw.split(","):
        fid = part.strip()
        if not fid:
            continue
        if not (FINDING_ID_RE.match(fid) or SOURCE_ID_RE.match(fid)):
            raise UsageError(
                f"--finding-ids の {fid!r} は形式が違います。<elegance|rubric>:<1 始まりの番号> で書きます"
                " (例: elegance:2 = elegance-verdict.json の feedback_loop.negative_feedback の 2 番目)。"
                "レビューが finding_locations に書いた source_id (例: F-0003) でもよい"
            )
        if fid not in ids:
            ids.append(fid)
    return ids


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise UsageError(f"SKILL.md を読めません: {path} ({exc})") from exc


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise UsageError(f"{path} を module として読めません")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (OSError, ImportError) as exc:
        raise UsageError(f"{path} を読み込めません ({exc})") from exc
    return module


def _git_blob(repo_root: Path, *args: str) -> bytes | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=repo_root, capture_output=True, check=True, timeout=60
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def _reviewed_bytes(repo_root: Path, md: Path, from_sha: str, from_file: Path | None) -> bytes:
    """verdict が判定した (sha256 が from_sha の) SKILL.md の bytes。見つからなければ Reject。"""
    if from_file is not None:
        try:
            data = from_file.read_bytes()
        except OSError as exc:
            raise UsageError(f"--from-file を読めません: {from_file} ({exc})") from exc
        if hashlib.sha256(data).hexdigest() != from_sha:
            raise UsageError(f"--from-file {from_file} の sha256 が --from-sha と一致しません")
        return data
    rel = md.relative_to(repo_root).as_posix()
    specs = [f":{rel}", f"HEAD:{rel}"]
    revs = _git_blob(repo_root, "rev-list", "-n", str(GIT_HISTORY_DEPTH), "HEAD", "--", rel)
    if revs:
        specs += [f"{commit}:{rel}" for commit in revs.decode("ascii", "replace").split()]
    for spec in specs:
        data = _git_blob(repo_root, "cat-file", "blob", spec)
        if data is not None and hashlib.sha256(data).hexdigest() == from_sha:
            return data
    raise Reject(
        "適用前の SKILL.md (sha256 が --from-sha の版) を git の index・HEAD・直近 "
        f"{GIT_HISTORY_DEPTH} commit に見つけられません。編集前に写しを取り --from-file で渡してください"
    )


def _split_frontmatter(text: str) -> tuple[str, list[str]]:
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return "".join(lines[: index + 1]), lines[index + 1:]
    return "", lines


def _outline(text: str) -> tuple[str, list[tuple[int, str, int | None]], list[str]]:
    """(frontmatter, 見出し [(level, 見出し文, 親の位置)], 節の本文) を返す。

    節の本文の 0 番目は最初の見出しより前、k+1 番目は k 番目の見出しの行から次の見出しの前まで。
    code fence の中の # 行は見出しとして数えない。
    """
    frontmatter, body = _split_frontmatter(text)
    headings: list[tuple[int, str, int | None]] = []
    segments: list[list[str]] = [[]]
    stack: list[int] = []
    fence: str | None = None
    for line in body:
        stripped = line.rstrip("\r\n")
        fence_match = FENCE_RE.match(stripped)
        if fence is not None:
            segments[-1].append(line)
            if (
                fence_match
                and fence_match.group(1)[0] == fence[0]
                and len(fence_match.group(1)) >= len(fence)
                and not stripped.strip()[len(fence_match.group(1)):].strip()
            ):
                fence = None
            continue
        if fence_match:
            fence = fence_match.group(1)
            segments[-1].append(line)
            continue
        heading = HEADING_RE.match(stripped)
        if heading:
            level = len(heading.group(1))
            while stack and headings[stack[-1]][0] >= level:
                stack.pop()
            headings.append((level, heading.group(2).strip(), stack[-1] if stack else None))
            stack.append(len(headings) - 1)
            segments.append([line])
        else:
            segments[-1].append(line)
    return frontmatter, headings, ["".join(segment) for segment in segments]


def _ancestry(headings: list[tuple[int, str, int | None]], index: int) -> list[int]:
    """index 自身から根までの見出しの位置。"""
    chain = []
    current: int | None = index
    while current is not None:
        chain.append(current)
        current = headings[current][2]
    return chain


def _section_label(headings: list[tuple[int, str, int | None]], index: int) -> str:
    return " > ".join(headings[i][1] for i in reversed(_ancestry(headings, index)))


def _resolve_section(headings: list[tuple[int, str, int | None]], location: str) -> list[int]:
    parts = [part.strip() for part in location.split(" > ")]
    if not all(parts):
        return []
    matches = []
    for index, (_, title, _) in enumerate(headings):
        if title != parts[-1]:
            continue
        ancestors = [headings[i][1] for i in reversed(_ancestry(headings, index)[1:])]
        if len(parts) > 1 and ancestors[-(len(parts) - 1):] != parts[:-1]:
            continue
        matches.append(index)
    return matches


def _changed_outline(before: str, after: str) -> tuple[list[tuple[int, str, int | None]], list[int], int]:
    """適用前後を見出しで節に分けて比べ、(見出し, 変わった節の位置, 変わった行数) を返す。

    frontmatter・見出しの並び・最初の見出しより前のどれかが変わったら、変更を節に結び付け
    られないので Reject。節の位置は _outline の見出しの位置 (segments の位置 - 1)。
    """
    front_before, headings, segments_before = _outline(before)
    front_after, headings_after, segments_after = _outline(after)
    if front_before != front_after:
        raise Reject("frontmatter が変わっています。frontmatter の変更は節に結び付けられない")
    if [(level, title) for level, title, _ in headings] != [(level, title) for level, title, _ in headings_after]:
        raise Reject("見出しが増えた・減った・変わった・並び替わったので、節の対応が取れない")
    changed: list[int] = []
    changed_lines = 0
    for position, (old, new) in enumerate(zip(segments_before, segments_after)):
        if old == new:
            continue
        if position == 0:
            raise Reject("最初の見出しより前が変わっています。節に結び付けられない")
        changed.append(position - 1)
        matcher = difflib.SequenceMatcher(a=old.splitlines(), b=new.splitlines(), autojunk=False)
        changed_lines += sum(
            max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"
        )
    return headings, changed, changed_lines


def _resolve_unique_section(headings: list[tuple[int, str, int | None]], section: str, owner: str) -> int:
    """section を適用前の見出しの位置 1 つに解く。無い・一意でない・# の見出しなら Reject。"""
    matches = _resolve_section(headings, section)
    if len(matches) != 1:
        where = "ありません" if not matches else f"{len(matches)} か所あります (「親 > 子」で一意に書く)"
        raise Reject(f"{owner}: 節 {section!r} が適用前の SKILL.md に{where}")
    if headings[matches[0]][0] == 1:
        raise Reject(f"{owner}: 節 {section!r} は文書全体の見出し (#) です。場所は ## 以下の節で挙げる")
    return matches[0]


def _check_covered(
    headings: list[tuple[int, str, int | None]], changed: list[int], covered: set[int], whose: str
) -> None:
    """変わった節が、covered の節 (とその下位の節) のどれかに入ることを確かめる。"""
    for index in changed:
        if not covered.intersection(_ancestry(headings, index)):
            listed = ", ".join(sorted(_section_label(headings, i) for i in covered))
            raise Reject(
                f"節 {_section_label(headings, index)!r} の変更は、{whose} ({listed}) の外です。"
                "レビューが見ていない節の変更は結び直せない"
            )


def _check_change_size(ssot, changed: list[int], changed_lines: int) -> None:
    """変わった節と行が上限 (ssot.SCOPED_REVIEW_MAX_*) 以内であることを確かめる。

    指摘の id でも範囲つき再レビューでも同じ上限にする。経路で上限が違うと、
    大きな変更ほど緩い経路を選んで通せてしまう。
    """
    if len(changed) > ssot.SCOPED_REVIEW_MAX_SECTIONS:
        raise Reject(
            f"変わった節が {len(changed)} 個あります (上限 {ssot.SCOPED_REVIEW_MAX_SECTIONS})。広い変更は全体を再レビューする"
        )
    if changed_lines > ssot.SCOPED_REVIEW_MAX_CHANGED_LINES:
        raise Reject(
            f"変わった行が {changed_lines} 行あります (上限 {ssot.SCOPED_REVIEW_MAX_CHANGED_LINES})。"
            "大きな変更は全体を再レビューする"
        )


def _check_contract_untouched(ssot, headings: list[tuple[int, str, int | None]], changed: list[int], after: str) -> None:
    """変わった節が、成果物の約束の中に無いことを確かめる。中にあれば Reject (全体の再レビューへ)。

    約束は 2 つ。入出力契約の節 (ssot.SCOPED_REVIEW_CONTRACT_SECTIONS) と、frontmatter の
    feedback_contract (criteria) が名指す節。どちらも下位の節の変更を含む。基準の判定が
    変わりうる変更は、指摘の id でも範囲つき再レビューでも結び直さない。
    文書全体の見出し (#) は criteria の照合に使わない (skill 名が criteria に出ても全体を止めない)。
    """
    criteria_block = _feedback_contract_block(after)
    for index in changed:
        for position in _ancestry(headings, index):
            level, title, _ = headings[position]
            if title in ssot.SCOPED_REVIEW_CONTRACT_SECTIONS:
                raise Reject(
                    f"節 {_section_label(headings, index)!r} は成果物の約束 ({title}) の中です。"
                    "契約を変えたときは全体を再レビューする"
                )
            if level > 1 and criteria_block and title in criteria_block:
                raise Reject(
                    f"節 {_section_label(headings, index)!r} は feedback_contract の criteria が名指す節 ({title}) の中です。"
                    "基準の判定が変わりうるので全体を再レビューする"
                )


def _contract_part(ssot, section: str) -> str | None:
    """節の書き方 ("<見出し>" か "<親> > <子>") のどれかの段が入出力契約なら、その名前。

    scripts/lint-content-review.py の _check_scoped_entry と同じ規則。lint が通さない記録を書かない。
    """
    return next(
        (part.strip() for part in section.split(" > ") if part.strip() in ssot.SCOPED_REVIEW_CONTRACT_SECTIONS),
        None,
    )


def _check_locations(
    before: str, after: str, verdicts: dict[str, tuple[Path, str, dict]], finding_ids: list[str]
) -> tuple[list[tuple[int, str, int | None]], list[int], int]:
    """変更が、挙げた指摘の finding_locations の節に収まることを確かめる。収まらなければ Reject。

    返り値は _changed_outline と同じ (見出し, 変わった節の位置, 変わった行数)。
    """
    headings, changed, changed_lines = _changed_outline(before, after)
    covered: set[int] = set()
    for fid in finding_ids:
        kind = fid.split(":", 1)[0]
        path, _, data = verdicts[kind]
        locations = data.get("finding_locations")
        entry = locations.get(fid) if isinstance(locations, dict) else None
        sections = entry.get("sections") if isinstance(entry, dict) else None
        if not isinstance(sections, list) or not sections or not all(
            isinstance(section, str) and section.strip() for section in sections
        ):
            raise Reject(
                f"{fid}: {path.name} の finding_locations に節がありません。"
                "どの節を直す指摘か分からないので、変更を指摘に結び付けられない"
            )
        for section in sections:
            covered.add(_resolve_unique_section(headings, section, fid))
    _check_covered(headings, changed, covered, "挙げた指摘の節")
    return headings, changed, changed_lines


def _feedback_contract_block(text: str) -> str:
    """frontmatter のうち feedback_contract: の block (criteria の text を含む) の文字列。"""
    frontmatter, _ = _split_frontmatter(text)
    block: list[str] = []
    inside = False
    for line in frontmatter.splitlines():
        if re.match(r"^feedback_contract\s*:", line):
            inside = True
        elif inside and line and not line[0].isspace():
            break
        if inside:
            block.append(line)
    return "\n".join(block)


def _load_scoped_review(path: Path) -> tuple[bytes, dict]:
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise UsageError(f"--scoped-review {path} を JSON として読めません ({exc})") from exc
    if not isinstance(data, dict):
        raise UsageError(f"--scoped-review {path} の最上位が object ではありません")
    return raw, data


def _check_scoped_review(
    ssot,
    review: dict,
    *,
    plugin: str,
    skill: str,
    from_sha: str,
    to_sha: str,
    before: str,
    after: str,
    verdicts: dict[str, tuple[Path, str, dict]],
) -> list[str]:
    """範囲つき再レビューで結び直してよいかを確かめ、レビューした節の一覧を返す。

    範囲つき再レビューは変えた節だけを読む。読んでいない節が変わった・変更が大きい・
    成果物の約束 (契約の節・criteria が名指す節) に触れた・何度も重なったときは、
    部分の判定で全体の PASS を名乗れないので Reject (全体の再レビューへ)。
    """
    expected = {"kind": ssot.SCOPED_REVIEW_KIND, "plugin": plugin, "skill": skill,
                "from_sha": from_sha, "to_sha": to_sha}
    for key, value in expected.items():
        if review.get(key) != value:
            raise Reject(
                f"範囲つき再レビューの {key}={review.get(key)!r} が {value!r} ではありません。"
                "いまの変更 (適用前 → 現在の SKILL.md) を見たレビューだと示せない"
            )
    if review.get("verdicts") != {"elegance": "PASS", "rubric": "PASS"}:
        raise Reject(f"範囲つき再レビューの verdicts={review.get('verdicts')!r}。elegance と rubric の両方が PASS でない")
    negative = review.get("negative_feedback")
    if not isinstance(negative, list):
        raise Reject("範囲つき再レビューに negative_feedback (配列) がありません")
    if negative:
        raise Reject(
            f"範囲つき再レビューが {len(negative)} 件の指摘を返しています。指摘を直してから"
            "もう一度範囲つき再レビューを受けるか、全体を再レビューする"
        )
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip() or reviewer.strip() in ssot.SCOPED_REVIEW_NON_INDEPENDENT:
        raise Reject(
            f"範囲つき再レビューの reviewer={reviewer!r} は使えません。変更した本人や親 context ではない"
            " reviewer (assign-skill-design-evaluator など) が書く"
        )
    if not isinstance(review.get("reviewed_at"), str) or not REVIEWED_AT_RE.match(review["reviewed_at"]):
        raise Reject("範囲つき再レビューの reviewed_at が UTC の ISO8601 (YYYY-MM-DDTHH:MM:SSZ) ではありません")

    for kind, (path, _, data) in verdicts.items():
        rebinds = data.get("sha_rebinds") or []
        if rebinds and "reviewed_skill_md_sha256" not in data["target"]:
            raise Reject(
                f"{path.name}: target.reviewed_skill_md_sha256 の無い古い verdict に結び直しが重なっています。"
                "元の全体レビューが分からないので、範囲つき再レビューは重ねられない"
            )
        scoped = sum(1 for entry in rebinds if isinstance(entry, dict) and "scoped_review" in entry)
        if scoped >= ssot.SCOPED_REVIEW_MAX_PER_FULL_REVIEW:
            raise Reject(
                f"{path.name}: 全体レビューのあとの範囲つき再レビューがすでに {scoped} 回あります"
                f" (上限 {ssot.SCOPED_REVIEW_MAX_PER_FULL_REVIEW})。部分の判定を重ねすぎたので全体を再レビューする"
            )

    sections = review.get("sections")
    if not isinstance(sections, list) or not sections or not all(
        isinstance(section, str) and section.strip() for section in sections
    ) or len(set(sections)) != len(sections):
        raise Reject("範囲つき再レビューの sections が、重複の無い空でない節の一覧ではありません")
    if len(sections) > ssot.SCOPED_REVIEW_MAX_SECTIONS:
        raise Reject(
            f"範囲つき再レビューの節が {len(sections)} 個あります (上限 {ssot.SCOPED_REVIEW_MAX_SECTIONS})。"
            "広い変更は全体を再レビューする"
        )
    for section in sections:
        contract = _contract_part(ssot, section)
        if contract:
            raise Reject(
                f"範囲つき再レビューの節 {section!r} は成果物の約束 ({contract}) を名指しています。"
                "契約の節は全体を再レビューする (scripts/lint-content-review.py もこの記録を通さない)"
            )
    headings, changed, changed_lines = _changed_outline(before, after)
    covered = {_resolve_unique_section(headings, section, "範囲つき再レビュー") for section in sections}
    _check_covered(headings, changed, covered, "範囲つき再レビューが読んだ節")
    _check_change_size(ssot, changed, changed_lines)
    _check_contract_untouched(ssot, headings, changed, after)
    return list(sections)


def _check_replay(repo_root: Path, replay: str, before: str, current: bytes) -> None:
    rel, function = REPLAYS[replay]
    module = _load_module(repo_root / rel, f"content_review_replay_{replay.replace('-', '_')}")
    try:
        rewritten = getattr(module, function)(before)
    except Exception as exc:  # noqa: BLE001 - 変換が当てられない理由をそのまま返す
        raise Reject(f"--replay {replay}: 適用前の SKILL.md に変換を当てられません ({exc})") from exc
    if rewritten is None:
        raise Reject(f"--replay {replay}: 適用前の SKILL.md に変換の対象がありません")
    if rewritten.encode("utf-8") != current:
        raise Reject(
            f"--replay {replay}: 変換を当て直した結果が現在の SKILL.md と一致しません。"
            "変換のほかに変えた箇所があります"
        )


def _check_dir_digest(repo_root: Path, plugin: str, skill: str, verdicts: dict[str, tuple[Path, str, dict]]) -> None:
    recorded = {
        kind: data["target"].get("skill_dir_digest")
        for kind, (_, _, data) in verdicts.items()
        if data["target"].get("skill_dir_digest") is not None
    }
    if not recorded:
        return
    ssot = _load_module(SSOT_PATH, "feedback_contract_ssot_for_sync")
    current = ssot.content_review_dir_digest(repo_root / "plugins" / plugin / "skills" / skill)
    for kind, digest in recorded.items():
        if digest != current:
            raise Reject(
                f"{kind}-verdict.json: target.skill_dir_digest が現在の skill ディレクトリと一致しません"
                " (references/ などが変わった)。SKILL.md 以外の変更は結び直せない"
            )


def _detect_format(text: str) -> tuple[int | str | None, bool, bool]:
    """元ファイルの indent・ensure_ascii・末尾改行を推定する。"""
    indent: int | str | None = None
    for line in text.splitlines()[1:]:
        m = re.match(r"^( +|\t+)\S", line)
        if m:
            ws = m.group(1)
            indent = "\t" if ws.startswith("\t") else len(ws)
            break
    ensure_ascii = "\\u" in text and all(ord(ch) < 128 for ch in text)
    return indent, ensure_ascii, text.endswith("\n")


def _serialize(data: dict, text: str) -> str:
    indent, ensure_ascii, newline = _detect_format(text)
    out = json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)
    return out + ("\n" if newline else "")


def _load_verdicts(review_dir: Path) -> dict[str, tuple[Path, str, dict]]:
    verdicts: dict[str, tuple[Path, str, dict]] = {}
    missing = [fname for _, fname in VERDICT_FILES if not (review_dir / fname).is_file()]
    if missing:
        raise Reject(
            f"{review_dir} に {', '.join(missing)} がありません。2 verdict がそろわないと結び直せません"
        )
    for kind, fname in VERDICT_FILES:
        path = review_dir / fname
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, ValueError) as exc:
            raise UsageError(f"{path} を JSON として読めません ({exc})") from exc
        if not isinstance(data, dict):
            raise UsageError(f"{path} の最上位が object ではありません")
        # 形の崩れた verdict は拒否 (exit 1 = 要再レビュー) ではなく入力の誤り (exit 2)。traceback にもしない
        if not isinstance(data.get("target"), dict):
            raise UsageError(f"{path} の target が object ではありません")
        rebinds = data.get("sha_rebinds")
        if rebinds is not None and not isinstance(rebinds, list):
            raise UsageError(f"{path} の sha_rebinds が配列ではありません")
        for number, entry in enumerate(rebinds or [], 1):
            if not isinstance(entry, dict) or not all(
                isinstance(entry.get(key), str) for key in ("from_sha", "to_sha")
            ):
                raise UsageError(f"{path} の sha_rebinds[{number}] が from_sha と to_sha (文字列) を持つ object ではありません")
        verdicts[kind] = (path, text, data)
    return verdicts


def _negative_feedback(data: dict) -> list:
    loop = data.get("feedback_loop")
    neg = loop.get("negative_feedback") if isinstance(loop, dict) else None
    return neg if isinstance(neg, list) else []


def _finding_text(verdicts: dict[str, tuple[Path, str, dict]], fid: str) -> str | None:
    """id が指す指摘の本文 (空白を詰めたもの)。解決できなければ None。"""
    m = FINDING_ID_RE.match(fid) if isinstance(fid, str) else None
    if not m:
        return None
    kind, number = m.groups()
    neg = _negative_feedback(verdicts[kind][2])
    idx = int(number)
    if idx > len(neg) or not isinstance(neg[idx - 1], str) or not neg[idx - 1].strip():
        return None
    return " ".join(neg[idx - 1].split())


def _consumed(verdicts: dict[str, tuple[Path, str, dict]]) -> tuple[set[str], set[str]]:
    """過去の sha_rebinds が使った id と、その id が指す指摘本文の集合。

    1 つの文脈が 2 verdict を書くので、同じ指摘が elegance:n と rubric:m の両方に並ぶことがある。
    id だけで使用済みを判定すると、片方で結び直したあと同じ指摘をもう片方の id で再利用できてしまう。
    """
    ids: set[str] = set()
    texts: set[str] = set()
    for path, _, data in verdicts.values():
        rebinds = data.get("sha_rebinds", [])
        if not isinstance(rebinds, list):
            raise UsageError(f"{path} の sha_rebinds が配列ではありません")
        for entry in rebinds:
            if isinstance(entry, dict) and isinstance(entry.get("finding_ids"), list):
                for fid in entry["finding_ids"]:
                    if isinstance(fid, str):
                        ids.add(fid)
                        text = _finding_text(verdicts, fid)
                        if text:
                            texts.add(text)
    return ids, texts


def _resolve_finding_ids(verdicts: dict[str, tuple[Path, str, dict]], requested: list[str]) -> list[str]:
    """source_id (例: F-0003) を finding_locations で <review_kind>:<n> に解く。

    1 つの source_id が 2 verdict の両方の指摘を指すときは両方の id になる (同じ指摘なので、
    片方だけ使って残りをあとで再利用されないよう一緒に消費する)。解けない source_id は Reject。
    """
    resolved: list[str] = []
    for fid in requested:
        if FINDING_ID_RE.match(fid):
            keys = [fid]
        else:
            keys = []
            for kind, _ in VERDICT_FILES:
                locations = verdicts[kind][2].get("finding_locations")
                if not isinstance(locations, dict):
                    continue
                for key, entry in locations.items():
                    match = FINDING_ID_RE.match(key) if isinstance(key, str) else None
                    if match and match.group(1) == kind and isinstance(entry, dict) and entry.get("source_id") == fid:
                        keys.append(key)
            keys.sort(key=lambda key: (key.split(":")[0], int(key.split(":")[1])))
            if not keys:
                raise Reject(f"{fid}: どの verdict の finding_locations[*].source_id にもありません")
        for key in keys:
            if key not in resolved:
                resolved.append(key)
    return resolved


def plan(
    repo_root: Path,
    plugin: str,
    skill: str,
    from_sha: str,
    finding_ids: list[str],
    *,
    replay: str | None = None,
    from_file: Path | None = None,
    scoped_review: tuple[Path, bytes, dict] | None = None,
) -> dict:
    """条件を検査し、結果 (status と書き込む内容) を返す。条件違反は Reject を投げる。"""
    md = repo_root / "plugins" / plugin / "skills" / skill / "SKILL.md"
    if not md.is_file():
        raise UsageError(f"SKILL.md がありません: {md}")
    current = _sha256(md)
    result = {
        "plugin": plugin,
        "skill": skill,
        "from_sha": from_sha,
        "to_sha": current,
        "finding_ids": finding_ids,
        "replay": replay,
        "scoped_review": None,
        "verdicts": [],
    }
    if current == from_sha:
        return {**result, "status": "noop"}

    review_dir = repo_root / "eval-log" / plugin / skill / "content-review"
    verdicts = _load_verdicts(review_dir)
    result["verdicts"] = [path.relative_to(repo_root).as_posix() for path, _, _ in verdicts.values()]

    # a. 両 verdict が PASS で、対象 skill の verdict であること
    for kind, (path, _, data) in verdicts.items():
        if data.get("verdict") != "PASS":
            raise Reject(
                f"{path.name}: verdict={data.get('verdict')!r}。PASS でない verdict は修正を当てても PASS にならない"
            )
        target = data.get("target")
        if not isinstance(target, dict) or target.get("plugin") != plugin or target.get("skill") != skill:
            got = (target or {}).get("plugin"), (target or {}).get("skill")
            raise Reject(f"{path.name}: target が {plugin}/{skill} ではありません (got {got[0]}/{got[1]})")

    recorded = {kind: data["target"].get("skill_md_sha256") for kind, (_, _, data) in verdicts.items()}
    if all(sha == current for sha in recorded.values()):
        return {**result, "status": "already-bound"}

    # 2 verdict は同じ連鎖を持つ (lint の pair-mismatch)。食い違った pair に足すと lint が落とすので、書く前に止める
    elegance, rubric = verdicts["elegance"][2], verdicts["rubric"][2]
    for key in ("reviewed_skill_md_sha256", "skill_dir_digest"):
        if elegance["target"].get(key) != rubric["target"].get(key):
            raise Reject(f"elegance と rubric の target.{key} が食い違っています。2 verdict の pair が壊れている")
    if (elegance.get("sha_rebinds") or []) != (rubric.get("sha_rebinds") or []):
        raise Reject("elegance と rubric の sha_rebinds が食い違っています。2 verdict の pair が壊れている")

    # b. verdict が適用前の内容 (--from-sha) に対する判定であること
    for kind, sha in recorded.items():
        if sha != from_sha:
            raise Reject(
                f"{kind}-verdict.json: target.skill_md_sha256={sha} が --from-sha={from_sha} と一致しません。"
                "verdict が適用前の SKILL.md に対する判定だと示せない"
            )

    for kind, (path, _, data) in verdicts.items():
        rebinds = data.get("sha_rebinds") or []
        if rebinds and (not isinstance(rebinds[-1], dict) or rebinds[-1].get("to_sha") != recorded[kind]):
            raise Reject(f"{path.name}: sha_rebinds の最後の to_sha が target.skill_md_sha256 と一致しません (連鎖が切れている)")

    # e. SKILL.md 以外 (references/ など) が変わっていないこと
    _check_dir_digest(repo_root, plugin, skill, verdicts)
    before = _reviewed_bytes(repo_root, md, from_sha, from_file)
    after = md.read_bytes()

    try:
        before_text, after_text = before.decode("utf-8"), after.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UsageError(f"SKILL.md (適用前か現在) を UTF-8 として読めません ({exc})") from exc

    if replay is not None:
        _check_replay(repo_root, replay, before_text, after)
        return _rebind(verdicts, result, {"from_sha": from_sha, "to_sha": current, "replay": replay})

    if scoped_review is not None:
        review_path, review_raw, review = scoped_review
        ssot = _load_module(SSOT_PATH, "feedback_contract_ssot_for_sync")
        sections = _check_scoped_review(
            ssot, review, plugin=plugin, skill=skill, from_sha=from_sha, to_sha=current,
            before=before_text, after=after_text, verdicts=verdicts,
        )
        review_sha = hashlib.sha256(review_raw).hexdigest()
        stored = review_dir / ssot.SCOPED_REVIEW_DIR / f"{current}.json"
        result["scoped_review"] = stored.relative_to(repo_root).as_posix()
        fields = {
            "from_sha": from_sha,
            "to_sha": current,
            "scoped_review": {
                "sections": sections,
                "reviewer": review["reviewer"].strip(),
                "reviewed_at": review["reviewed_at"],
                "review_ref": stored.relative_to(review_dir).as_posix(),
                "review_sha256": review_sha,
            },
        }
        # レビューの写しを verdict の隣に残し、lint が review_sha256 で中身を確かめられるようにする。
        return _rebind(verdicts, result, fields, extra_writes=[(stored, None, review_raw.decode("utf-8"))])

    # c. 指摘の id が実在し、まだ使われていないこと
    if not finding_ids:
        raise Reject("--finding-ids が空です。適用した指摘を 1 件以上挙げないと結び直せない")
    finding_ids = _resolve_finding_ids(verdicts, finding_ids)
    result["finding_ids"] = finding_ids
    consumed_ids, consumed_texts = _consumed(verdicts)
    for fid in finding_ids:
        kind, number = FINDING_ID_RE.match(fid).groups()
        path, _, data = verdicts[kind]
        text = _finding_text(verdicts, fid)
        if text is None:
            raise Reject(
                f"{fid}: {path.name} の feedback_loop.negative_feedback に {number} 番目の指摘がありません"
                f" (指摘は {len(_negative_feedback(data))} 件)"
            )
        if fid in consumed_ids or text in consumed_texts:
            raise Reject(
                f"{fid}: すでに sha_rebinds で使われた指摘です (同じ本文の指摘を別の id で使った場合を含む)。"
                "1 つの指摘で結び直せるのは 1 回だけ"
            )

    # d. 変更が挙げた指摘の節に収まり、範囲つき再レビューと同じ上限と約束の保護を満たすこと
    headings, changed, changed_lines = _check_locations(before_text, after_text, verdicts, finding_ids)
    ssot = _load_module(SSOT_PATH, "feedback_contract_ssot_for_sync")
    _check_change_size(ssot, changed, changed_lines)
    _check_contract_untouched(ssot, headings, changed, after_text)
    return _rebind(verdicts, result, {"from_sha": from_sha, "to_sha": current, "finding_ids": finding_ids})


def _rebind(
    verdicts: dict[str, tuple[Path, str, dict]],
    result: dict,
    fields: dict,
    *,
    extra_writes: list[tuple[Path, str | None, str]] = (),
) -> dict:
    entry = {
        **fields,
        "rebound_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": TOOL,
    }
    writes = []
    for path, text, data in verdicts.values():
        target = data["target"]
        if "reviewed_skill_md_sha256" not in target:
            rebinds = data.get("sha_rebinds") or []
            target["reviewed_skill_md_sha256"] = rebinds[0]["from_sha"] if rebinds else target["skill_md_sha256"]
        target["skill_md_sha256"] = entry["to_sha"]
        data.setdefault("sha_rebinds", []).append(entry)
        writes.append((path, text, _serialize(data, text)))
    for path, _, content in extra_writes:
        original = path.read_text(encoding="utf-8") if path.is_file() else None
        writes.append((path, original, content))
    return {**result, "status": "rebound", "entry": entry, "_writes": writes}


def _write_temp(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644)
    except Exception:
        _unlink(temporary)
        raise
    return temporary


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def apply_writes(writes: list[tuple[Path, str | None, str]]) -> None:
    """全ファイルの一時ファイルを先に作り、os.replace で順に置き換える。途中で失敗したら戻す。

    元の内容が None のファイルは新しく作るもので、戻すときは消す。
    """
    temps: list[str] = []
    try:
        for path, _, content in writes:
            temps.append(_write_temp(path, content))
    except Exception:
        for temporary in temps:
            _unlink(temporary)
        raise
    replaced: list[tuple[Path, str]] = []
    try:
        for (path, original, _), temporary in zip(writes, temps):
            os.replace(temporary, path)
            replaced.append((path, original))
    except Exception:
        for temporary in temps[len(replaced):]:
            _unlink(temporary)
        for path, original in replaced:
            if original is None:
                _unlink(str(path))
            else:
                os.replace(_write_temp(path, original), path)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--from-sha", required=True, help="適用前の SKILL.md の sha256 (64 桁 hex)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--finding-ids", help="適用した指摘の id。例: elegance:1,rubric:2")
    mode.add_argument("--replay", choices=sorted(REPLAYS), help="当てた機械的な移行の id")
    mode.add_argument(
        "--scoped-review", type=Path,
        help="変えた節だけを読んだ独立レビューの結果 (kind=scoped-content-review の JSON)",
    )
    ap.add_argument("--from-file", type=Path, help="適用前の SKILL.md の写し (無ければ git から探す)")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--dry-run", action="store_true", help="条件を検査して結果を出すだけで書かない")
    args = ap.parse_args(argv)

    try:
        for label, value in (("--plugin", args.plugin), ("--skill", args.skill)):
            if not NAME_RE.match(value):
                raise UsageError(f"{label} {value!r} は名前として使えません")
        from_sha = args.from_sha.strip().lower()
        if not SHA_RE.match(from_sha):
            raise UsageError(f"--from-sha {args.from_sha!r} は 64 桁の sha256 hex ではありません")
        finding_ids = _parse_finding_ids(args.finding_ids) if args.finding_ids is not None else []
        scoped_review = None
        if args.scoped_review is not None:
            scoped_review = (args.scoped_review, *_load_scoped_review(args.scoped_review))
        repo_root = Path(args.repo_root).resolve()
        if not repo_root.is_dir():
            raise UsageError(f"--repo-root {args.repo_root!r} がディレクトリではありません")

        result = plan(
            repo_root,
            args.plugin,
            args.skill,
            from_sha,
            finding_ids,
            replay=args.replay,
            from_file=args.from_file,
            scoped_review=scoped_review,
        )
        writes = result.pop("_writes", [])
        if result["status"] == "rebound":
            if args.dry_run:
                result["status"] = "dry-run"
            else:
                apply_writes(writes)
    except Reject as exc:
        print(f"REJECT: {exc}", file=sys.stderr)
        print(RE_REVIEW_HINT, file=sys.stderr)
        return 1
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: verdict を書けません ({exc})", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
