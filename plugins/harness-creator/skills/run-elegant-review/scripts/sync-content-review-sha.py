#!/usr/bin/env python3
# /// script
# name: sync-content-review-sha
# purpose: content-review verdict の指摘を SKILL.md へ適用した直後に限り、elegance / rubric の 2 verdict の target.skill_md_sha256 を現在の SKILL.md に結び直し、sha_rebinds[] に監査記録を 1 件足す。条件を満たさない編集は結び直さず、scripts/lint-content-review.py の stale-sha のまま再レビューへ回す (lint 自体は変えない)。
# inputs:
#   - argv: --plugin <plugin> --skill <skill> --from-sha <適用前の SKILL.md sha256> --finding-ids <elegance:N,rubric:N,...> [--repo-root <path> (既定 .)] [--dry-run]
# outputs:
#   - stdout: 結果 1 行 JSON {"status": "rebound"|"dry-run"|"noop"|"already-bound", "plugin", "skill", "from_sha", "to_sha", "finding_ids", "verdicts"}
#   - stderr: 拒否理由 (REJECT: ...) と要再レビューの案内 / 引数・入出力のエラー
#   - exit: 0=結び直し・dry-run・noop・already-bound / 1=条件を満たさず拒否 (ファイルは変えない。要再レビュー) / 2=引数・入出力の誤り
# contexts: [A, B]
# network: false
# write-scope: <repo-root>/eval-log/<plugin>/<skill>/content-review/{elegance,rubric}-verdict.json の 2 ファイルだけ (target.skill_md_sha256 の更新と sha_rebinds[] への追記。ほかのキーは書き換えない)。--dry-run は書かない
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
  c. --finding-ids が空でなく、各 id が下の照合規則で verdict の指摘に解決でき、
     まだどの sha_rebinds[] にも使われていない (1 つの指摘で結び直せるのは 1 回だけ)。
     使用済みかは id と指摘本文の両方で見る。2 verdict に同じ本文の指摘が並ぶとき、
     片方の id で結び直した指摘をもう片方の id で再び使うことはできない
     (1 回の呼び出しで両方の id を並べるのはよい)。

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
      --from-sha <64 桁 hex> --finding-ids elegance:1,rubric:2 [--repo-root .] [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TOOL = "sync-content-review-sha"
VERDICT_FILES = (("elegance", "elegance-verdict.json"), ("rubric", "rubric-verdict.json"))
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
FINDING_ID_RE = re.compile(r"^(elegance|rubric):([1-9][0-9]*)$")
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
        if not FINDING_ID_RE.match(fid):
            raise UsageError(
                f"--finding-ids の {fid!r} は形式が違います。<elegance|rubric>:<1 始まりの番号> で書きます"
                " (例: elegance:2 = elegance-verdict.json の feedback_loop.negative_feedback の 2 番目)"
            )
        if fid not in ids:
            ids.append(fid)
    return ids


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise UsageError(f"SKILL.md を読めません: {path} ({exc})") from exc


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


def plan(repo_root: Path, plugin: str, skill: str, from_sha: str, finding_ids: list[str]) -> dict:
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

    # b. verdict が適用前の内容 (--from-sha) に対する判定であること
    for kind, sha in recorded.items():
        if sha != from_sha:
            raise Reject(
                f"{kind}-verdict.json: target.skill_md_sha256={sha} が --from-sha={from_sha} と一致しません。"
                "verdict が適用前の SKILL.md に対する判定だと示せない"
            )

    # c. 指摘の id が実在し、まだ使われていないこと
    if not finding_ids:
        raise Reject("--finding-ids が空です。適用した指摘を 1 件以上挙げないと結び直せない")
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

    entry = {
        "from_sha": from_sha,
        "to_sha": current,
        "finding_ids": finding_ids,
        "rebound_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": TOOL,
    }
    writes = []
    for path, text, data in verdicts.values():
        data["target"]["skill_md_sha256"] = current
        data.setdefault("sha_rebinds", []).append(entry)
        writes.append((path, text, _serialize(data, text)))
    return {**result, "status": "rebound", "entry": entry, "_writes": writes}


def _write_temp(path: Path, content: str) -> str:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
    except Exception:
        _unlink(temporary)
        raise
    return temporary


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def apply_writes(writes: list[tuple[Path, str, str]]) -> None:
    """全ファイルの一時ファイルを先に作り、os.replace で順に置き換える。途中で失敗したら戻す。"""
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
            os.replace(_write_temp(path, original), path)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--from-sha", required=True, help="適用前の SKILL.md の sha256 (64 桁 hex)")
    ap.add_argument("--finding-ids", required=True, help="適用した指摘の id。例: elegance:1,rubric:2")
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
        finding_ids = _parse_finding_ids(args.finding_ids)
        repo_root = Path(args.repo_root).resolve()
        if not repo_root.is_dir():
            raise UsageError(f"--repo-root {args.repo_root!r} がディレクトリではありません")

        result = plan(repo_root, args.plugin, args.skill, from_sha, finding_ids)
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
