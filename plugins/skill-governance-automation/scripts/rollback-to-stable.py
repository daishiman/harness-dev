#!/usr/bin/env python3
# /// script
# name: rollback-to-stable
# version: 0.4.3
# purpose: 現行の rubric と同じ rubric_id で、現行版より古く violation_rate_avg が ceiling (freeze.violation_rate_ceiling) 以下の最新の版への巻き戻し計画を出す（27章§9 の自動 rollback のうち計画の部分。hook にはつないでいない）
# inputs:
#   - --rubric: 現行の rubric.json のパス（必須。rubric_version を現行版、rubric_id を照合のキーとして読み、それより古い同じ rubric の版だけを候補にする）
#   - --versions-md: rubric-versions.md のパス（必須。各版の節に `- violation_rate_avg: <0〜1>` の行と、rubric_id のある rubric では `- rubric_id: <id>` の行が要る）
#   - --params: governance-params.json のパス（既定 references/governance-params.json。作業ディレクトリ基準）
#   - --dry-run: 互換のため受け付ける（この script は書き込まず、計画を出すだけ）
# outputs:
#   - stdout: 選定版 / 照合用の hash / 巻き戻しの手順（params_source に ceiling の出どころ、current_version と rubric_id に現行の rubric）
#   - stderr: 既定の ceiling を使うときの警告 / 候補にしない版とその理由 / 版の見出しとして読めない見出し
#   - exit: 0=OK / 1=候補なし・versions-md 不在 / 2=usage・params や rubric や versions-md を読めない・ファイルでない・rubric が無い・rubric_version を版として読めない・rubric_id が空でない文字列でない・ceiling が 0〜1 の有限数でない
# requires-python: ">=3.9"
# dependencies: []
# contexts: [E, C]
# network: false
# write-scope: none
# ///
"""安定版凍結条件を満たす、現行版より古い最新の rubric_version への巻き戻し計画を出力する。

この script は計画を出すだけで、rubric.json は書き換えない。巻き戻しは承認の後に、
対象の版を発効した commit の rubric.json と、それから派生した rubric.json（assign 側など）を
一組で戻し（版の名前だけを書き換えない）、その skill に templates/ があれば同じ commit の内容に
戻す（ref-skill-design-rubric には templates/ が無い）。戻した rubric.json に
compute-rubric-hash.py --dry-run を流して hash を計算し（書き込まない）、rubric-versions.md に
記録した hash と照合する。--dry-run を付けないと rubric.json に rubric_hash を書き込むので、
rubric_hash を持たない版を戻したときにファイルの sha256 が変わり、一組で戻した派生の rubric.json と
合わなくなる（check-rubric-sync.py が RUBRIC_DRIFT にする）。この script の --dry-run は互換の
ために残している。

ceiling（freeze.violation_rate_ceiling）は --params の governance-params.json から読む。
ファイルが無いときは既定の 0.05 を使うが、黙って使わず stderr に警告し、出力の
params_source を "default" にする。あるのに読めない・壊れているとき、ファイルでないとき、
ceiling が 0〜1 の有限数でないときは exit 2 で止める。

--rubric の rubric_version を現行版とし、それより古い版だけを候補にする（現行版や、それより
新しい版への「巻き戻し」を出さない）。rubric が無い・読めない・版を読めないときは exit 2。
プレリリース（1.3.0-rc.1 など）は安定版として選ばない。

rubric-versions.md には複数の rubric の版が並びうる（27章§8.3 のひな形は各節に
`- rubric_id: <id> / hash: ...` を書く）。--rubric の rubric.json に rubric_id があれば、同じ
rubric_id の節だけを候補にする。rubric_id の行が無い節は、どの rubric の版か確かめられないので
候補にしない（安全側。stderr に理由を出す）。rubric.json に rubric_id が無いときは、rubric_id の
行が無い節だけを候補にし、rubric_id のある節は照合できないので候補にしない。

rubric-versions.md は「## <版> (YYYY-MM-DD)」の節ごとに読む。# と ## の見出しは、書式が
少し違っても前の節を閉じる。### 以下は節の中の小見出しとして扱うが、今の節と違う版の番号らしい
もの（小数を含む）を含むもの（「### 1.2.0 (2026-01-01)」など）は前の節を閉じる（下の値を直前の
版に数えない）。今の節と同じ版の番号（1.3 と 1.3.0 は同じ。v が付いてもよい）は数えないので、
「## 1.3.0 …」の下の「### 1.3.0 の計測」は節の中に残る。版の見出しでない見出し（「# 付録」
「## 未リリース」「### 1.2.0 …」など）の後ろは、どの版にも数えない。版の番号らしいものを含むのに
書式が違う見出し（「## [1.3.0] - …」「### 1.2.0 …」など）は stderr に出す。コードブロックと
HTML コメントの中は読まない。

値の行は、行頭（`- ` の後）か ` / ` の後に `violation_rate_avg` のキーがあるものだけを読む
（`**violation_rate_avg**:` や `` `violation_rate_avg`: `` のように飾ったキーも読む。rubric_id と
hash も同じ）。1行に同じキーが2つあれば両方を読む。本文中の言及や `baseline_violation_rate_avg`
は読まない。値は 0〜1 の小数で、後ろに続いてよいのは行末・括弧・`#` や HTML のコメント・
` / <次のキー>:`・`, ` の後の注記（別の値に読める数で始まらないもの）だけ。「0,30」「0.01, 0.30」
「3%」「0.01→0.30」「0.0３」などは黙って読み違えず、stderr に理由を出して候補から外す。日付が
無い・暦に無い（2026-13-45 など）版、値や rubric_id が食い違う版、0〜1 の外の版、同じ rubric で
同じ版の見出しが2つある版（1.3 と 1.3.0 は同じ版）も同じ。

候補は日付（同じ日なら版。同じ番号なら正式版をプレリリースより新しいとみなす）が最も新しい
ものを選ぶ。27章§8.3 の rubric-versions.md のひな形には violation_rate_avg の行がまだ無く、
書く仕組みも無い。各版の節に手で書き足す必要がある。freeze.consecutive_runs（連続 run 数）は
rubric-versions.md に記録が無いので、ここでは確かめない。
"""
from __future__ import annotations
import argparse
import datetime
import json
import math
import re
import sys
from pathlib import Path

DEFAULT_CEILING = 0.05

# 版の数字は ASCII に限り、桁も抑える（全角数字や桁の大きい数で int が失敗しないように）
_VERSION_TEXT = r"[0-9]{1,9}(?:\.[0-9]{1,9})*(?:-[0-9A-Za-z.-]{1,40})?"
_VERSION_FULL = re.compile(rf"v?({_VERSION_TEXT})")
_SECTION_HEADING = re.compile(r"^#{1,2}(?:\s|$)")
_SUBHEADING = re.compile(r"^#{3,6}(?:\s|$)")
_VERSION_HEADING = re.compile(rf"^##\s+v?({_VERSION_TEXT})(?![\w.])(.*)$")
_VERSION_LIKE = re.compile(r"[0-9]+\.[0-9]+")
# 小見出しの中の版の番号（v が付いてもよい）。今の節と同じ版かを比べるために取り出す
_VERSION_TOKEN = re.compile(rf"(?<![0-9.])v?({_VERSION_TEXT})(?![0-9])")
_DATE = re.compile(r"(?<![0-9])([0-9]{4}-[0-9]{2}-[0-9]{2})(?![0-9])")
_FENCE = re.compile(r"^(`{3,}|~{3,})")
_KEY_START = r"(?:^(?:[-*+]\s+)?|\s/\s*)"
# **violation_rate_avg**: や `rubric_id`: のように飾ったキーは、飾りを外してから読む
_DECORATED_KEY = re.compile(r"(\*\*|__|`)(violation[_-]?rate[_-]?avg|rubric[_-]?id|hash)(\s*[:：]?)\1")
_RATE_KEY = re.compile(_KEY_START + r"violation[_-]?rate[_-]?avg(?![\w-])\s*[:：]?\s*")
_RATE_VALUE = re.compile(r"[0-9]+(?:\.[0-9]+)?")
# `, ` の後の注記は「3 runs」のような数で始まってよいが、「0.30」や行末までの数は別の値に読めるので外す
_RATE_TAIL = re.compile(r"[.。]?\s*(?:$|[(（#]|<!--)"
                        r"|[,、]\s+(?![0-9]*\.[0-9]|[0-9]+\s*(?:$|[,、/(（#]|<!--))"
                        r"|\s+/\s*[A-Za-z_][\w-]*\s*[:：]")
_RUBRIC_ID_KEY = re.compile(_KEY_START + r"rubric[_-]?id(?![\w-])\s*[:：]\s*")
_RUBRIC_ID_VALUE = re.compile(r"[\"'`]?([A-Za-z0-9][\w.-]*)")
_HASH = re.compile(r"(?<![\w-])hash\s*[:：]\s*(sha256:[0-9A-Fa-f]+)")


def _flag(row: dict, msg: str) -> None:
    row["issue"] = msg if row["issue"] is None else f"{row['issue']}; {msg}"


def _strip_comments(line: str, in_comment: bool) -> tuple[str, bool]:
    """行から HTML コメントを外す。(残りの文字列, 行末でコメントの中か) を返す。"""
    kept: list[str] = []
    rest = line
    while rest:
        if in_comment:
            end = rest.find("-->")
            if end < 0:
                return "".join(kept), True
            rest, in_comment = rest[end + 3:], False
        else:
            start = rest.find("<!--")
            if start < 0:
                kept.append(rest)
                break
            kept.append(rest[:start])
            rest, in_comment = rest[start + 4:], True
    return "".join(kept), in_comment


def _undecorate(line: str) -> str:
    return _DECORATED_KEY.sub(r"\2\3", line)


def _read_rubric_id(row: dict, value_text: str) -> None:
    m = _RUBRIC_ID_VALUE.match(value_text)
    if m is None:
        _flag(row, f"rubric_id を読めない: {value_text[:40]!r}")
        return
    prev = row["rubric_id"]
    if prev is not None and prev != m.group(1):
        _flag(row, f"rubric_id が食い違う: {prev} と {m.group(1)}")
        return
    row["rubric_id"] = m.group(1)


def _read_rate(row: dict, value_text: str) -> None:
    m = _RATE_VALUE.match(value_text)
    if m is None or _RATE_TAIL.match(value_text, m.end()) is None:
        _flag(row, f"violation_rate_avg を読めない（0〜1 の小数で書く）: {value_text[:40]!r}")
        return
    value = float(m.group(0))
    prev = row["violation_rate_avg"]
    if prev is not None and prev != value:
        _flag(row, f"violation_rate_avg が食い違う: {prev} と {value}")
    if not 0 <= value <= 1:
        _flag(row, f"violation_rate_avg が 0〜1 の外: {value}")
    row["violation_rate_avg"] = value


def parse_versions_md(text: str, warnings: list[str] | None = None) -> list[dict]:
    """版の節ごとに {version, date, rubric_id, violation_rate_avg, hash, issue} を返す。

    issue が None でない版は候補にしない。値の行が無い版は violation_rate_avg が None で、
    issue も None（未計測）。rubric_id の行が無い版は rubric_id が None。コードブロックと
    HTML コメントの中は見出しにも値にも数えない。
    warnings を渡すと、版の番号らしいものを含むのに版の見出しとして読めない見出しを足す。
    """
    out: list[dict] = []
    current: dict | None = None
    fence: str | None = None
    in_comment = False
    for ln in text.splitlines():
        if fence is None:
            ln, in_comment = _strip_comments(ln, in_comment)
        s = ln.strip()
        fm = _FENCE.match(s)
        if fence is not None:
            marker = fm.group(1) if fm else ""
            if marker[:1] == fence[:1] and len(marker) >= len(fence) and not s[len(marker):].strip():
                fence = None
            continue
        if fm:
            fence = fm.group(1)
            continue
        # ### 以下の小見出しは節の中に残すが、今の節と違う版らしいものは前の版の値に混ぜない
        if _SECTION_HEADING.match(s) or (_SUBHEADING.match(s) and _VERSION_LIKE.search(_drop_version(s, current))):
            m = _VERSION_HEADING.match(s)
            if m is None:
                enclosing, current = current, None
                if warnings is not None and _VERSION_LIKE.search(s):
                    if _SUBHEADING.match(s) and enclosing is not None:
                        v = enclosing["version"]
                        hint = (f"版の見出しなら `## <版> (YYYY-MM-DD)` で書く。{v} の節の小見出しなら、"
                                f"{v} のほかに版の番号や小数を入れない")
                    else:
                        hint = "`## <版> (YYYY-MM-DD)` で書く"
                    warnings.append(f"見出し {s!r} を版の見出しとして読めない（{hint}）。この節の値は使わない")
                continue
            d = _DATE.search(m.group(2))
            current = {"version": m.group(1), "date": d.group(1) if d else None, "rubric_id": None,
                       "violation_rate_avg": None, "hash": None, "issue": None}
            if d is None:
                _flag(current, "見出しに日付 (YYYY-MM-DD) が無い")
            else:
                try:
                    datetime.date.fromisoformat(d.group(1))
                except ValueError:
                    _flag(current, f"見出しの日付 {d.group(1)} が暦に無い")
            out.append(current)
            continue
        if current is None:
            continue
        s = _undecorate(s)
        h = _HASH.search(s)
        if h is not None and current["hash"] is None:
            current["hash"] = h.group(1)
        for k in _RUBRIC_ID_KEY.finditer(s):
            _read_rubric_id(current, s[k.end():])
        for k in _RATE_KEY.finditer(s):
            _read_rate(current, s[k.end():])
    seen: dict[tuple, int] = {}
    for row in out:
        seen[_same_version(row)] = seen.get(_same_version(row), 0) + 1
    for row in out:
        if seen[_same_version(row)] > 1:
            _flag(row, "同じ版の見出しが複数ある")
    return out


def _version_identity(version: str) -> tuple:
    """同じ版なら等しい（1.3 と 1.3.0 は同じ。プレリリースは名前ごと比べる）。"""
    return version_key(version)[0], version.partition("-")[2].lower()


def _same_version(row: dict) -> tuple:
    """同じ rubric の同じ版なら等しい。"""
    return (row["rubric_id"],) + _version_identity(row["version"])


def _drop_version(heading: str, current: dict | None) -> str:
    """見出しから、今の節と同じ版の番号を除く（今の節が無ければそのまま返す）。"""
    if current is None:
        return heading
    same = _version_identity(current["version"])
    return _VERSION_TOKEN.sub(lambda m: "" if _version_identity(m.group(1)) == same else m.group(0), heading)


def version_key(version: str) -> tuple:
    """版の順序。末尾の .0 は無視し（1.2 と 1.2.0 は同じ）、正式版をプレリリースより新しいとみなす。"""
    core, _, pre = version.partition("-")
    nums = [int(n) for n in core.split(".")]
    while len(nums) > 1 and nums[-1] == 0:
        nums.pop()
    return (tuple(nums), 0 if pre else 1, tuple(int(n) for n in re.findall(r"[0-9]+", pre)))


def recency(row: dict) -> tuple:
    """日付、同じ日なら版の番号、同じ番号なら正式版 > プレリリースの順で新しさを比べる。"""
    return (row["date"],) + version_key(row["version"])


def _kind(path: Path) -> str:
    """'file' / 'missing' / 'other'（ディレクトリや壊れた symlink）。stat できなければ OSError。"""
    if path.is_file():
        return "file"
    if path.exists() or path.is_symlink():
        return "other"
    return "missing"


def _shown(path: Path) -> str:
    try:
        return str(path.resolve())
    except (OSError, RuntimeError):  # symlink のループ
        return str(path)


def _load_ceiling(params_path: Path) -> tuple[float, str] | None:
    """(ceiling, params_source) を返す。exit 2 にすべきときは stderr に書いて None。"""
    try:
        kind = _kind(params_path)
        if kind == "file":
            params = json.loads(params_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, RecursionError) as exc:
        print(f"error: params を読めない: {params_path} ({type(exc).__name__}: {exc})", file=sys.stderr)
        return None
    if kind == "other":
        print(f"error: params がファイルでない: {params_path}", file=sys.stderr)
        return None
    if kind == "missing":
        print(f"warning: params が無い ({_shown(params_path)})。既定の ceiling {DEFAULT_CEILING} を使う",
              file=sys.stderr)
        return DEFAULT_CEILING, "default"
    freeze = params.get("freeze") if isinstance(params, dict) else None
    ceiling = freeze.get("violation_rate_ceiling") if isinstance(freeze, dict) else None
    if isinstance(ceiling, bool) or not isinstance(ceiling, (int, float)):
        print(f"error: {params_path} に数値の freeze.violation_rate_ceiling が無い", file=sys.stderr)
        return None
    # int は math.isfinite に渡さない（桁が大きいと float に直せず OverflowError になる）
    if (isinstance(ceiling, float) and not math.isfinite(ceiling)) or not 0 <= ceiling <= 1:
        print(f"error: {params_path} の freeze.violation_rate_ceiling は 0〜1 の有限数にする: {ceiling}",
              file=sys.stderr)
        return None
    return ceiling, str(params_path)


def _load_current(rubric_path: Path) -> tuple[str, str | None] | None:
    """現行の (rubric_version, rubric_id)。版の先頭の v は外し、rubric_id が無ければ None。

    exit 2 にすべきときは stderr に書いて None を返す。
    """
    try:
        kind = _kind(rubric_path)
        if kind == "file":
            rubric = json.loads(rubric_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, RecursionError) as exc:
        print(f"error: rubric を読めない: {rubric_path} ({type(exc).__name__}: {exc})", file=sys.stderr)
        return None
    if kind == "other":
        print(f"error: rubric がファイルでない: {rubric_path}", file=sys.stderr)
        return None
    if kind == "missing":
        # 現行版が分からないと、現行版やそれより新しい版を巻き戻し先に選んでしまう
        print(f"error: rubric が無い: {rubric_path}（--rubric に現行の rubric.json を渡す）", file=sys.stderr)
        return None
    version = rubric.get("rubric_version") if isinstance(rubric, dict) else None
    if not isinstance(version, str) or not version.strip():
        print(f"error: {rubric_path} に文字列の rubric_version が無い", file=sys.stderr)
        return None
    m = _VERSION_FULL.fullmatch(version.strip())
    if m is None:
        print(f"error: {rubric_path} の rubric_version を版として読めない: {version!r}", file=sys.stderr)
        return None
    rubric_id = rubric.get("rubric_id")
    if rubric_id is not None and (not isinstance(rubric_id, str) or not rubric_id.strip()):
        # 照合のキーが読めないまま進むと、別の rubric の版を巻き戻し先に選びうる
        print(f"error: {rubric_path} の rubric_id が空でない文字列でない: {rubric_id!r}", file=sys.stderr)
        return None
    return m.group(1), rubric_id.strip() if rubric_id is not None else None


def _exclusion(row: dict, current_version: str, current_id: str | None) -> str | None:
    """候補にしない理由。None なら候補にしてよい（値の有無と ceiling は別に見る）。"""
    if current_id is not None and row["rubric_id"] is None:
        return f"rubric_id の行が無く、現行の rubric ({current_id}) の版か確かめられない"
    if row["rubric_id"] != current_id:
        if current_id is None:
            return f"rubric_id {row['rubric_id']} を、rubric_id の無い現行の rubric と照合できない"
        return f"rubric_id {row['rubric_id']} は現行の rubric ({current_id}) と違う"
    if row["issue"] is not None:
        return row["issue"]
    key, current_key = version_key(row["version"]), version_key(current_version)
    if key > current_key:
        return f"現行版 {current_version} より新しい"
    if key[1] == 0 and key != current_key:
        return "プレリリースは安定版として選ばない"
    return None


def _steps(rubric: str, target: dict) -> list[str]:
    verify = (f"rubric-versions.md に記録した hash ({target['hash']}) と一致することを確かめる"
              if target["hash"] else
              f"rubric-versions.md に hash の記録が無いので照合できない。git diff <commit> -- {rubric} が空"
              "（戻した内容が発効時の commit と同じ）ことを確かめる")
    return [
        f"git log で {target['version']} を発効した commit を探し、{rubric} と、それから派生した rubric.json"
        "（assign 側など）を一組でその commit の内容に戻す。その skill に templates/ があれば同じ commit に戻す"
        "（rubric_version だけを書き換えない。23章: rubric と templates は同時に凍結する）",
        f"compute-rubric-hash.py --dry-run --rubric {rubric} で hash を計算し（書き込まない。--dry-run を外すと"
        f" rubric_hash を書き込み、派生の rubric.json と合わなくなる）、{verify}",
        "check-rubric-sync.py で派生の rubric の同期を確かめ、governance log に巻き戻しを記録する",
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubric", required=True)
    ap.add_argument("--versions-md", required=True)
    ap.add_argument("--params", default="references/governance-params.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    loaded = _load_ceiling(Path(args.params))
    if loaded is None:
        return 2
    ceiling, params_source = loaded
    current = _load_current(Path(args.rubric))
    if current is None:
        return 2
    current_version, current_id = current
    current_key = version_key(current_version)

    vm = Path(args.versions_md)
    heading_warnings: list[str] = []
    try:
        kind = _kind(vm)
        if kind == "file":
            versions = parse_versions_md(vm.read_text(encoding="utf-8-sig"), heading_warnings)
    except (OSError, ValueError) as exc:
        print(f"error: versions-md を読めない: {vm} ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 2
    if kind == "missing":
        print(f"error: versions-md not found: {vm}", file=sys.stderr)
        return 1
    if kind == "other":
        print(f"error: versions-md がファイルでない: {vm}", file=sys.stderr)
        return 2

    for msg in heading_warnings:
        print(f"warning: {msg}", file=sys.stderr)
    readable = []
    for row in versions:
        reason = _exclusion(row, current_version, current_id)
        if reason is not None:
            print(f"warning: {row['version']}: {reason}。この版は候補にしない", file=sys.stderr)
        elif row["violation_rate_avg"] is not None and version_key(row["version"]) < current_key:
            readable.append(row)
    candidates = [v for v in readable if v["violation_rate_avg"] <= ceiling]
    if not candidates:
        msg = (f"no stable candidate found: 現行版 {current_version} より古く violation_rate_avg を読めた版 "
               f"{len(readable)} 件のうち、ceiling {ceiling} 以下は0件")
        if current_id is not None and not any(v["rubric_id"] == current_id for v in versions):
            msg += f"（rubric_id {current_id} の節が無い。各版の節に `- rubric_id: {current_id}` の行が要る）"
        if not readable:
            msg += "（rubric-versions.md の各版の節に `- violation_rate_avg: <0〜1>` の行が要る。27章§8.3 のひな形には無い）"
        print(msg, file=sys.stderr)
        return 1

    target = max(candidates, key=recency)
    print(json.dumps({
        "target_version": target["version"],
        "target_date": target["date"],
        "target_hash": target["hash"],
        "violation_rate_avg": target["violation_rate_avg"],
        "ceiling": ceiling,
        "params_source": params_source,
        "current_version": current_version,
        "rubric_id": current_id,
        "rubric": args.rubric,
        "dry_run": args.dry_run,
        "plan": (f"{args.rubric} を {target['version']} の内容に巻き戻す（版の名前だけでなく中身を戻し、"
                 "派生した rubric.json と、あれば templates/ も同じ commit に戻す）"),
        "steps": _steps(args.rubric, target),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
