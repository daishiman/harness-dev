#!/usr/bin/env python3
# /// script
# name: render-c1-c4-section
# purpose: run-build-skill の初稿診断 receipt から、run-skill-create の完了レポートに貼る C1-C4 節を日本語 Markdown で描画する（評価はしない。読むだけで書かない）
# inputs:
#   - argv: --plugin NAME --skill NAME [--repo-root DIR] [--receipt-root DIR] [--fingerprint SHA256]
#   - files: eval-log/<plugin>/build/initial-draft-review/<artifact-fingerprint>/{review.json,improvement-validation.json,improvement-result.json,post-target-manifest.json}, eval-log/<plugin>/build/diagnostic-choice.json, receipt が記録した対象ファイル
# outputs:
#   - stdout: 完了レポートの build_evaluation_receipt (C1-C4) 節（Markdown）
#   - stderr: 引数エラーの説明
#   - exit: 0=描画した（未診断も含む） / 2=引数エラー（名前が不正・repo root や skill ディレクトリが無い・fingerprint が 64 桁 hex でない）か、receipt の置き場や skill ディレクトリを読めない（OSError）
# contexts: [C, E]
# network: false
# write-scope: なし
# dependencies: []
# requires-python: ">=3.9"
# ///
"""run-skill-create 完了レポートの C1-C4 節を初稿診断 receipt から描画する。

C1-C4 の正本は run-build-skill Step 12.6-12.8 の receipt で、run-skill-create は
それを評価し直さない。この script は receipt を読んで決まった文面へ写すだけで、
receipt が無い・壊れている・今の成果物と合わない場合は「未診断」と出す。

receipt の置き場所と中身:
  eval-log/<plugin>/build/initial-draft-review/<artifact-fingerprint>/
    review.json                  Step 12.6 (initial-draft-review.schema.json)
    improvement-result.json      Step 12.7 (improvement-result.schema.json)
    post-target-manifest.json    Step 12.7
    improvement-validation.json  Step 12.8 (validate-improvement-result.py --out)

<artifact-fingerprint> は build-improvement-gate.py の baseline fingerprint で、
review.json の baseline_fingerprint_sha256 に記録される。verification plan などが
無いと計算し直せず、改善後は中身も変わるので、この script は計算し直さずに
ディレクトリ名と記録値の一致だけを確かめる。

receipt が今の成果物の診断かどうかは、build-improvement-gate.py が target manifest を
作り直して完全一致を求めるのと同じ考え方で決める。manifest に載ったファイルの
sha256 に加え、skill ディレクトリを今数え直して manifest に無いファイル (診断後に
足したもの) があれば、その receipt は使わない。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONDITION_LABELS = {
    "C1": "矛盾なし",
    "C2": "漏れなし",
    "C3": "整合性あり",
    "C4": "依存関係整合",
}
VERDICTS = {"PASS", "FAIL", "PARTIAL"}
SEVERITIES = ("critical", "high", "medium", "low")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FINDING_ID_RE = re.compile(r"^IDR-[0-9]{3}$")  # initial-draft-review.schema.json の findings[].id と同じ
OLDEST = datetime.min.replace(tzinfo=timezone.utc)
# build_target_manifest はこれらも hash するが、実行するだけで変わるので鮮度判定から外す。
IGNORED_PARTS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
IGNORED_NAMES = {".DS_Store"}

HEADING = "## build_evaluation_receipt (C1-C4)"
PREAMBLE = (
    "> run-build-skill の初稿診断 receipt から `render-c1-c4-section.py` が生成した節。"
    "run-skill-create では評価し直していない。"
)
UNDIAGNOSED_LINE = "- C1-C4: 未診断 (run-skill-create では評価していない)"


class ReceiptError(Exception):
    """receipt が壊れている理由 (1 行)。"""


@dataclass
class Receipt:
    directory: Path
    review_path: Path
    review: dict[str, Any]
    validation_path: Path | None = None
    validation: dict[str, Any] | None = None
    result_path: Path | None = None
    result: dict[str, Any] | None = None
    changed: list[str] = field(default_factory=list)

    @property
    def improved(self) -> bool:
        return self.validation is not None


@dataclass
class Broken:
    directory: Path
    reason: str
    # review.json が読めず、どの skill の receipt か判定できなかったときは False。
    attributed: bool = True


def _one_line(value: Any) -> str:
    return " ".join(str(value).split())


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReceiptError(f"{label} を読めない ({exc.__class__.__name__})") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"{label} が JSON として読めない ({exc.__class__.__name__})") from exc


def _read_object(path: Path, label: str) -> dict[str, Any]:
    value = _read_json(path, label)
    if not isinstance(value, dict):
        raise ReceiptError(f"{label} が JSON object ではない")
    return value


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_ignored(relative: str) -> bool:
    path = Path(relative)
    return (
        bool(IGNORED_PARTS & set(path.parts))
        or path.suffix in IGNORED_SUFFIXES
        or path.name in IGNORED_NAMES
    )


def _is_safe_relative(value: str) -> bool:
    """repo root からの相対 path で、外へ出ない (絶対 path・`..`・空の段・`\\` を含まない) もの。"""
    return not value.startswith("/") and "\\" not in value and all(part not in ("", ".", "..") for part in value.split("/"))


def _check_manifest(manifest: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(manifest, list) or not manifest:
        raise ReceiptError(f"{label} が path の配列ではない")
    for item in manifest:
        if not isinstance(item, dict) or not _non_empty_str(item.get("path")):
            raise ReceiptError(f"{label} が path の配列ではない")
        if not _is_safe_relative(item["path"]):
            raise ReceiptError(f"{label} に repo 外を指す path がある")
    return manifest


def _belongs_to_skill(review: dict[str, Any], *, subject: str) -> bool:
    # target_manifest は複数 component をまとめることがあるので、帰属は subject だけで決める。
    return review.get("subject") == subject


def _check_conditions(doc: dict[str, Any], label: str, refs_key: str, finding_ids: set[str] | None = None) -> None:
    conditions = doc.get("four_conditions")
    if not isinstance(conditions, dict):
        raise ReceiptError(f"{label} に four_conditions が無い")
    for key in CONDITION_LABELS:
        condition = conditions.get(key)
        if not isinstance(condition, dict):
            raise ReceiptError(f"{label} の four_conditions.{key} が無い")
        if condition.get("verdict") not in VERDICTS:
            raise ReceiptError(f"{label} の four_conditions.{key}.verdict が PASS/FAIL/PARTIAL ではない")
        if not _non_empty_str(condition.get("summary")):
            raise ReceiptError(f"{label} の four_conditions.{key}.summary が空")
        refs = condition.get(refs_key)
        if not isinstance(refs, list):
            raise ReceiptError(f"{label} の four_conditions.{key}.{refs_key} が配列ではない")
        if finding_ids is not None and any(not isinstance(ref, str) or ref not in finding_ids for ref in refs):
            raise ReceiptError(f"{label} の four_conditions.{key}.{refs_key} に findings に無い ID がある")


def _check_review(review: dict[str, Any], directory: Path) -> None:
    if review.get("schema_version") != 1:
        raise ReceiptError("review.json の schema_version が 1 ではない")
    for key in ("run_id", "subject", "recommended_level"):
        if not _non_empty_str(review.get(key)):
            raise ReceiptError(f"review.json の {key} が無い")
    if review.get("baseline_fingerprint_sha256") != directory.name:
        raise ReceiptError("review.json の baseline_fingerprint_sha256 がディレクトリ名と一致しない")
    evaluator = review.get("evaluator")
    if not isinstance(evaluator, dict) or evaluator.get("id") != "elegant-initial-draft-evaluator":
        raise ReceiptError("review.json の evaluator が elegant-initial-draft-evaluator ではない")
    _check_manifest(review.get("target_manifest"), "review.json の target_manifest")
    findings = review.get("findings")
    if not isinstance(findings, list) or any(
        not isinstance(item, dict)
        or item.get("severity") not in SEVERITIES
        or not isinstance(item.get("id"), str)
        or not FINDING_ID_RE.match(item["id"])
        for item in findings
    ):
        raise ReceiptError("review.json の findings に id か severity が不正なものがある")
    finding_ids = {item["id"] for item in findings}
    if len(finding_ids) != len(findings):
        raise ReceiptError("review.json の findings の id が重複している")
    _check_conditions(review, "review.json", "finding_refs", finding_ids)


def _check_improvement(receipt: Receipt, directory: Path) -> list[dict[str, Any]]:
    """改善 receipt (Step 12.7-12.8) を確かめ、鮮度判定に使う manifest を返す。"""
    review = receipt.review
    validation = receipt.validation or {}
    if validation.get("schema_version") != 1 or validation.get("status") != "pass":
        raise ReceiptError("improvement-validation.json の status が pass ではない")
    if validation.get("run_id") != review.get("run_id") or validation.get("subject") != review.get("subject"):
        raise ReceiptError("improvement-validation.json の run_id/subject が review.json と一致しない")

    result_path = directory / "improvement-result.json"
    if not result_path.is_file():
        raise ReceiptError("improvement-validation.json はあるが improvement-result.json が無い")
    result = _read_object(result_path, "improvement-result.json")
    if result.get("run_id") != review.get("run_id") or result.get("subject") != review.get("subject"):
        raise ReceiptError("improvement-result.json の run_id/subject が review.json と一致しない")
    if result.get("review_sha256") != _file_sha(receipt.review_path):
        raise ReceiptError("improvement-result.json の review_sha256 が review.json と一致しない")
    for key in ("completion_status", "rounds_used"):
        if result.get(key) != validation.get(key):
            raise ReceiptError(f"improvement-result.json の {key} が improvement-validation.json と一致しない")
    outcomes = result.get("finding_outcomes")
    if not isinstance(outcomes, dict) or any(
        not isinstance(outcomes.get(key), list) for key in ("resolved", "residual", "regressed")
    ):
        raise ReceiptError("improvement-result.json の finding_outcomes が不正")
    _check_conditions(result, "improvement-result.json", "evidence_refs")

    post_path = directory / "post-target-manifest.json"
    if not post_path.is_file():
        raise ReceiptError("improvement-validation.json はあるが post-target-manifest.json が無い")
    post = _check_manifest(_read_json(post_path, "post-target-manifest.json"), "post-target-manifest.json")
    if result.get("post_target_manifest_sha256") != _canonical_sha(post):
        raise ReceiptError("improvement-result.json の post_target_manifest_sha256 が post-target-manifest.json と一致しない")
    receipt.result_path = result_path
    receipt.result = result
    return post


def current_skill_files(repo_root: Path, skill_rel: str) -> set[str]:
    """skill ディレクトリにいま在るファイル (鮮度判定から外すものを除く) の repo 相対 path。"""
    files = set()
    for path in (repo_root / skill_rel).rglob("*"):
        if path.is_file():
            relative = path.relative_to(repo_root).as_posix()
            if not _is_ignored(relative):
                files.add(relative)
    return files


def _matches(repo_root: Path, relative: str, sha256: Any) -> bool:
    current = repo_root / relative
    try:
        # symlink で repo の外を指すものは、中身が同じでも今の成果物とは数えない。
        current.resolve(strict=True).relative_to(repo_root)
        return current.is_file() and _file_sha(current) == sha256
    except (OSError, ValueError):
        return False


def _changed_files(manifest: list[dict[str, Any]], repo_root: Path, current: set[str]) -> list[str]:
    recorded = {item["path"]: item.get("sha256") for item in manifest if not _is_ignored(item["path"])}
    changed = [relative for relative, sha256 in recorded.items() if not _matches(repo_root, relative, sha256)]
    changed += [f"{relative} (診断後に追加)" for relative in sorted(current - recorded.keys())]
    return changed


def load_receipt(
    directory: Path, *, repo_root: Path, subject: str, current: set[str], explicit: bool, skill_rel: str
) -> Receipt | Broken | None:
    """1 つの receipt ディレクトリを読む。この skill のものでなければ None。"""
    review_path = directory / "review.json"
    if not review_path.is_file():
        return Broken(directory, "review.json が無い") if explicit else None
    try:
        review = _read_object(review_path, "review.json")
    except ReceiptError as exc:
        # 読めない review.json はどの skill のものか判定できないので、呼び出し側で扱いを分ける。
        return Broken(directory, str(exc), attributed=explicit)
    if not _belongs_to_skill(review, subject=subject):
        return Broken(directory, f"review.json が {skill_rel} の receipt ではない") if explicit else None
    receipt = Receipt(directory=directory, review_path=review_path, review=review)
    try:
        _check_review(review, directory)
        validation_path = directory / "improvement-validation.json"
        if validation_path.is_file():
            receipt.validation_path = validation_path
            receipt.validation = _read_object(validation_path, "improvement-validation.json")
            manifest = _check_improvement(receipt, directory)
        elif (directory / "improvement-result.json").is_file():
            raise ReceiptError("improvement-result.json はあるが improvement-validation.json が無い (Step 12.8 の検証を通っていない)")
        else:
            manifest = review["target_manifest"]
    except ReceiptError as exc:
        return Broken(directory, str(exc))
    except OSError as exc:
        return Broken(directory, f"receipt を読めない ({exc.__class__.__name__})")
    receipt.changed = _changed_files(manifest, repo_root, current)
    return receipt


def _display(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _diagnostic_choice(repo_root: Path, plugin: str, *, skill_rel: str, subject: str) -> tuple[str, str] | None:
    """この skill に対する現状で試すか診断するかの選択 (Step 12.5) があれば (level, path) を返す。"""
    path = repo_root / "eval-log" / plugin / "build" / "diagnostic-choice.json"
    try:
        choice = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(choice, dict) or not _non_empty_str(choice.get("selected_level")):
        return None
    artifact = choice.get("artifact_path")
    matches = choice.get("subject") == subject or (
        isinstance(artifact, str) and (artifact == skill_rel or artifact.startswith(skill_rel + "/"))
    )
    return (choice["selected_level"], _display(path, repo_root)) if matches else None


def _undiagnosed(reason: str, location: str | None, notes: list[str]) -> list[str]:
    lines = ["- 状態: 未診断", f"- 理由: {reason}"]
    if location:
        lines.append(f"- receipt: {location}")
    lines.extend(notes)
    lines.append(UNDIAGNOSED_LINE)
    return lines


def _finding_counts(findings: list[dict[str, Any]]) -> str:
    counts = {severity: 0 for severity in SEVERITIES}
    for item in findings:
        counts[item["severity"]] += 1
    detail = " / ".join(f"{severity} {counts[severity]}" for severity in SEVERITIES)
    return f"{len(findings)} 件 ({detail})"


def _refs(values: list[Any]) -> str:
    return ", ".join(_one_line(value) for value in values) if values else "なし"


def _render_receipt(receipt: Receipt, repo_root: Path, notes: list[str]) -> list[str]:
    review = receipt.review
    evaluator = review["evaluator"]
    files = [receipt.review_path]
    if receipt.improved:
        files += [receipt.result_path, receipt.validation_path]
    lines = [
        "- 状態: 診断済み・改善済み" if receipt.improved else "- 状態: 診断済み (改善なし)",
        "- receipt: " + ", ".join(_display(path, repo_root) for path in files if path is not None),
        f"- subject: {_one_line(review['subject'])} (run_id {_one_line(review['run_id'])})",
        f"- 診断者: {evaluator.get('id')} ({_one_line(evaluator.get('runtime', '不明'))})",
        f"- 推奨 level: {_one_line(review['recommended_level'])}",
        f"- 所見: {_finding_counts(review['findings'])}",
    ]
    initial = review["four_conditions"]
    if not receipt.improved:
        lines.extend(notes)
        for key, label in CONDITION_LABELS.items():
            condition = initial[key]
            lines.append(
                f"- {key} {label}: {condition['verdict']} — {_one_line(condition['summary'])}"
                f" (所見: {_refs(condition['finding_refs'])})"
            )
        return lines

    validation = receipt.validation or {}
    result = receipt.result or {}
    outcomes = result["finding_outcomes"]
    lines += [
        f"- 改善: level {_one_line(result.get('selected_level', '不明'))}、"
        f"選んだ所見 {_refs(validation.get('selected_finding_ids') or [])}、"
        f"round {_one_line(validation.get('rounds_used'))}/{_one_line(validation.get('max_rounds'))}、"
        f"completion_status {_one_line(validation.get('completion_status'))}",
        f"- 所見の結果: resolved {len(outcomes['resolved'])} / residual {len(outcomes['residual'])}"
        f" / regressed {len(outcomes['regressed'])}",
    ]
    lines.extend(notes)
    final = result["four_conditions"]
    for key, label in CONDITION_LABELS.items():
        before, after = initial[key], final[key]
        lines += [
            f"- {key} {label}: {before['verdict']} → {after['verdict']}",
            f"  - 初稿: {_one_line(before['summary'])} (所見: {_refs(before['finding_refs'])})",
            f"  - 改善後: {_one_line(after['summary'])}",
        ]
    return lines


def _produced_at(receipt: Receipt) -> datetime:
    """produced_at を時刻として読む (文字列のままだとタイムゾーン違いで新旧が逆転する)。読めなければ最も古い扱い。"""
    value = receipt.review.get("produced_at")
    if not isinstance(value, str):
        return OLDEST
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value)
    except ValueError:
        return OLDEST
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def render(*, repo_root: Path, plugin: str, skill: str, receipt_root: Path, fingerprint: str | None) -> str:
    skill_rel = f"plugins/{plugin}/skills/{skill}"
    subject = f"{plugin}:{skill}"
    root_label = _display(receipt_root, repo_root) + "/"

    if fingerprint:
        directories = [receipt_root / fingerprint]
    elif receipt_root.is_dir():
        directories = sorted(path for path in receipt_root.iterdir() if path.is_dir() and SHA256_RE.match(path.name))
    else:
        directories = []

    current = current_skill_files(repo_root, skill_rel)
    receipts: list[Receipt] = []
    broken: list[Broken] = []
    for directory in directories:
        if fingerprint and not directory.is_dir():
            continue
        try:
            loaded = load_receipt(
                directory, repo_root=repo_root, subject=subject, current=current, explicit=bool(fingerprint), skill_rel=skill_rel
            )
        except OSError as exc:
            loaded = Broken(directory, f"receipt を読めない ({exc.__class__.__name__})", attributed=bool(fingerprint))
        if isinstance(loaded, Receipt):
            receipts.append(loaded)
        elif isinstance(loaded, Broken):
            broken.append(loaded)

    fresh = sorted((item for item in receipts if not item.changed), key=lambda item: (_produced_at(item), item.directory.name))
    stale = sorted((item for item in receipts if item.changed), key=lambda item: (_produced_at(item), item.directory.name))

    attributed = [item for item in broken if item.attributed]
    unattributed = [item for item in broken if not item.attributed]
    unattributed_note = (
        [f"- 注記: どの skill のものか判定できない壊れた receipt が {len(unattributed)} 件ある (例: "
         f"{_display(unattributed[0].directory, repo_root)}/: {unattributed[0].reason})"]
        if unattributed
        else []
    )

    body: list[str]
    if fresh:
        chosen = fresh[-1]
        notes = []
        if len(fresh) > 1:
            notes.append(f"- 注記: 今の成果物と一致する receipt が {len(fresh)} 件あり、produced_at が最新のものを使った")
        if attributed or stale:
            notes.append(f"- 注記: 使わなかった receipt (壊れている {len(attributed)} 件 / 診断後に成果物が変わった {len(stale)} 件)")
        notes.extend(unattributed_note)
        body = _render_receipt(chosen, repo_root, notes)
    elif attributed:
        item = attributed[0]
        notes = [f"- 注記: 壊れている receipt が {len(attributed)} 件ある"] if len(attributed) > 1 else []
        body = _undiagnosed(f"receipt が壊れている。{item.reason}", _display(item.directory, repo_root) + "/", notes)
    elif stale:
        item = stale[-1]
        body = _undiagnosed(
            f"診断後に成果物が変わっている ({len(item.changed)} 件。例: {item.changed[0]})。"
            "この receipt は今の成果物の診断ではない",
            _display(item.directory, repo_root) + "/",
            unattributed_note,
        )
    elif unattributed:
        item = unattributed[0]
        body = _undiagnosed(
            f"receipt が壊れていて、この skill のものか判定できない。{item.reason}",
            _display(item.directory, repo_root) + "/",
            [f"- 注記: 判定できない壊れた receipt が {len(unattributed)} 件ある"] if len(unattributed) > 1 else [],
        )
    else:
        choice = _diagnostic_choice(repo_root, plugin, skill_rel=skill_rel, subject=subject)
        if fingerprint:
            reason = f"指定した fingerprint の receipt が無い ({root_label}{fingerprint}/)"
        elif choice and choice[0] == "accept-as-is":
            reason = "初稿診断 receipt が無い。run-build-skill の現状で試すか診断するかの選択で accept-as-is が選ばれている"
        elif choice:
            reason = f"現状で試すか診断するかの選択で {choice[0]} が選ばれているが、初稿診断 receipt が無い"
        else:
            reason = "初稿診断 receipt が無い。run-build-skill の現状で試すか診断するかの選択で accept-as-is を選んだか、診断を行っていない"
        notes = [f"- 探した場所: {root_label}"]
        if choice:
            notes.append(f"- 現状で試すか診断するかの選択: {choice[0]} ({choice[1]})")
        body = _undiagnosed(reason, None, notes)

    return "\n".join([HEADING, "", PREAMBLE, "", *body]) + "\n"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plugin", required=True, help="成果物の plugin 名")
    parser.add_argument("--skill", required=True, help="成果物の skill 名")
    parser.add_argument("--repo-root", default=".", help="生成対象 repo の root (既定: cwd)")
    parser.add_argument(
        "--receipt-root",
        help="receipt を探すディレクトリ (既定: <repo-root>/eval-log/<plugin>/build/initial-draft-review)",
    )
    parser.add_argument("--fingerprint", help="使う receipt の artifact fingerprint (64 桁 hex)。省くと skill に合うものを探す")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    for label, value in (("--plugin", args.plugin), ("--skill", args.skill)):
        if not NAME_RE.match(value) or ".." in value:
            print(f"error: {label} が不正: {value!r}", file=sys.stderr)
            return 2
    if args.fingerprint and not SHA256_RE.match(args.fingerprint):
        print("error: --fingerprint は 64 桁の小文字 hex で指定する", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root).resolve()
    if not repo_root.is_dir():
        print(f"error: --repo-root が無い: {args.repo_root}", file=sys.stderr)
        return 2
    if not (repo_root / "plugins" / args.plugin / "skills" / args.skill).is_dir():
        print(f"error: skill ディレクトリが無い: plugins/{args.plugin}/skills/{args.skill}", file=sys.stderr)
        return 2
    if args.receipt_root:
        raw = Path(args.receipt_root)
        receipt_root = (raw if raw.is_absolute() else repo_root / raw).resolve()
    else:
        receipt_root = repo_root / "eval-log" / args.plugin / "build" / "initial-draft-review"
    try:
        section = render(
            repo_root=repo_root,
            plugin=args.plugin,
            skill=args.skill,
            receipt_root=receipt_root,
            fingerprint=args.fingerprint,
        )
    except OSError as exc:
        print(f"error: receipt の置き場か skill ディレクトリを読めない ({exc.__class__.__name__}: {exc.filename})", file=sys.stderr)
        return 2
    sys.stdout.write(section)
    return 0


if __name__ == "__main__":
    sys.exit(main())
