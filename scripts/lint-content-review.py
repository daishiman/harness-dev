#!/usr/bin/env python3
# /// script
# name: lint-content-review
# purpose: content-review の 2 verdict (elegance / rubric) が PASS で、今の SKILL.md の sha256・skill ディレクトリの digest・結び直しの連鎖に結び付いているかを offline で検査する (LLM は実行しない)
# inputs:
#   - argv: --all | --changed-only [--base <ref>] | --print-target <plugin>/<skill> のどれか 1 つ
#   - fs: plugins/*/skills/*/SKILL.md と skill ディレクトリ (digest の範囲は feedback_contract_ssot.CONTENT_REVIEW_DIGEST_EXCLUDE の外)
#   - fs: eval-log/<plugin>/<skill>/content-review/{elegance,rubric}-verdict.json と scoped-reviews/<to_sha>.json、後方互換の eval-log の skill-build-trace.json
#   - git: --changed-only のときだけ git diff --name-only -z <base>...HEAD
# outputs:
#   - stdout: [OK] / [FAIL] と違反の一覧。--print-target は新しい verdict に書く target の JSON
#   - stderr: --print-target と --changed-only の入力エラー
#   - exit: 0=違反なし (対象の skill が 0 件のときも) / 1=違反あり (形の崩れた verdict も違反に数える) / 2=usage・入力エラー (引数の誤り、--print-target の skill が無い・読めない、--changed-only の git diff の失敗)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""内容 adequacy 評価成果物の存在を機械検査する (offline, LLM 不実行)。

役割境界:
  - 機械層: SKILL.md が変更された skill について eval-log/<plugin>/<skill>/content-review/
            配下に elegance-verdict.json + rubric-verdict.json が存在し verdict=PASS であることを検査
  - LLM 層 (本 lint の対象外): 評価実行自体はローカル Claude Code で run-elegant-review +
            assign-skill-design-evaluator を SubAgent 起動して行う (リモート CI コスト回避)

ref kind は除外する。harness-creator 自身は自己改善(dogfooding)対象なので CI/pre-push では除外しない
(dogfooding 境界の SSOT = scripts/feedback_contract_ssot.py:is_content_review_exempt)。

verdict が古くないことの検査 (harness-g67):
  - target.skill_md_sha256 が現在の SKILL.md の sha256 と一致する (stale-sha)。
  - target.skill_dir_digest があれば、SKILL.md 以外でモデルが読む文書 (references/ など。
    範囲は FC.CONTENT_REVIEW_DIGEST_EXCLUDE) の digest と一致する (stale-dir-digest)。
  - sha_rebinds[] が連鎖している: 最初の from_sha が target.reviewed_skill_md_sha256
    (元のレビューの sha。無い古い verdict は連鎖の内側だけを見る)、各 from_sha が直前の
    to_sha、最後の to_sha が target.skill_md_sha256。各記録は指摘の id・登録済みの移行 id・
    範囲つき再レビュー (scoped_review) のどれか 1 つを持つ。elegance と rubric は同じ
    sha_rebinds を持ち、1 つの指摘は 1 回しか使えない (rebind-chain)。
  - scoped_review の記録は、content-review/scoped-reviews/ のレビューの写しが実在し、その
    sha256・from/to・節・reviewer が記録と一致し、写しが両 verdict PASS・指摘 0 件で、
    全体レビュー 1 回あたりの回数が上限以内であること (scoped-review)。上限は
    feedback_contract_ssot.SCOPED_REVIEW_*。節に入出力契約 (SCOPED_REVIEW_CONTRACT_SECTIONS)
    を名指す記録も違反にする。変わった行数 (SCOPED_REVIEW_MAX_CHANGED_LINES) は from_sha 時点の
    SKILL.md が無いと数えられないので、書く側 (sync-content-review-sha.py) だけが見る。

fail-closed:
  - 形の崩れた verdict (object でない・型の違うフィールド) は、落ちずにその skill の違反として
    数え、残りの skill の検査を続ける。予期しない例外も check-error の違反にする。
  - SKILL.md や skill ディレクトリが読めないときは期限切れ (stale-*) として扱う。
  - --changed-only の git diff が失敗したら (ref が無い・repo でない・git が無い)、「対象なし」に
    せず exit 2 で止める。

新しい verdict の target は `--print-target <plugin>/<skill>` の出力をそのまま使う。

Usage:
  python3 scripts/lint-content-review.py --changed-only [--base origin/main]
  python3 scripts/lint-content-review.py --all
  python3 scripts/lint-content-review.py --print-target <plugin>/<skill>
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"
EVAL_LOG = ROOT / "eval-log"

sys.path.insert(0, str(ROOT / "scripts"))
import feedback_contract_ssot as FC  # noqa: E402
REQUIRED_VERDICTS = ("elegance-verdict.json", "rubric-verdict.json")
# dogfooding 除外境界は SSOT (FC.is_content_review_exempt) が単一正本。
# content-review は生成器自身も除外しない (常に False) ため集合は空のままだが、
# 判定は SSOT 述語へ委譲しリテラル散在を排除する。
EXEMPT_KINDS = {"ref"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
FINDING_ID_RE = re.compile(r"^(elegance|rubric):([1-9][0-9]*)$")
REBIND_TOOL = "sync-content-review-sha"
# sync-content-review-sha.py の REPLAYS と同じ集合 (test が食い違いを止める)。
REPLAY_IDS = frozenset({"artifact-delivery-v1", "diagnostic-choice-2way"})
SCOPED_REF_RE = re.compile(rf"^{re.escape(FC.SCOPED_REVIEW_DIR)}/[0-9a-f]{{64}}[.]json$")
SKILL_PATH_RE = re.compile(r"plugins/([^/]+)/skills/([^/]+)/(.+)", re.S)


class GitDiffError(Exception):
    """--changed-only の git diff が失敗した。対象なしとは区別して exit 2 にする。"""


def _git_changed_paths(base):
    """変わった skill ごとに、skill ディレクトリからの相対 path の集合を返す。

    -z で path を引用符なしの NUL 区切りで受け取る (既定の core.quotePath だと日本語の path が
    "..." で囲まれ、plugins/ に当たらず取りこぼす)。
    """
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", "-z", f"{base}...HEAD"],
            cwd=ROOT,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        raise GitDiffError(f"git diff {base}...HEAD failed ({type(exc).__name__}: {exc})") from exc
    changed = {}
    for path in diff.split("\0"):
        m = SKILL_PATH_RE.fullmatch(path)
        if m:
            changed.setdefault((m.group(1), m.group(2)), set()).add(m.group(3))
    return changed


def _git_changed_skills(base):
    """SKILL.md が変わった skill と、digest の範囲が変わり verdict が digest を持つ skill。"""
    skills = set()
    for (plugin, skill), paths in _git_changed_paths(base).items():
        if "SKILL.md" in paths:
            skills.add((plugin, skill))
            continue
        in_scope = any(not FC._is_excluded(path, FC.CONTENT_REVIEW_DIGEST_EXCLUDE) for path in paths)
        if in_scope and _has_dir_digest(plugin, skill):
            skills.add((plugin, skill))
    return skills


def _has_dir_digest(plugin, skill):
    """verdict が skill_dir_digest を持つか。在るのに読めない・形の崩れた verdict も検査に回す。"""
    review_dir = EVAL_LOG / plugin / skill / "content-review"
    for fname in REQUIRED_VERDICTS:
        path = review_dir / fname
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return True
        target = data.get("target") if isinstance(data, dict) else None
        if not isinstance(target, dict) or target.get("skill_dir_digest") is not None:
            return True
    return False


def _all_skills():
    skills = set()
    if not PLUGINS_DIR.exists():
        return skills
    for plugin_dir in PLUGINS_DIR.iterdir():
        if not plugin_dir.is_dir():
            continue
        sk_dir = plugin_dir / "skills"
        if not sk_dir.is_dir():
            continue
        for s in sk_dir.iterdir():
            if (s / "SKILL.md").is_file():
                # symlink / Codex 配布用の同一コピーは正本側で評価
                if s.is_symlink() or FC.is_vendored_feedback_skill(s, plugins_dir=PLUGINS_DIR):
                    continue
                skills.add((plugin_dir.name, s.name))
    return skills


def _read_kind(plugin, skill):
    md = PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md"
    if not md.is_file():
        return None
    try:
        text = md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None  # kind が分からない skill は除外せず検査に回す
    return FC.read_kind(text)  # kind 抽出は SSOT の単一実装に委譲 (lint 間の乖離を排除)


def _skill_sha256(plugin, skill):
    md = PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md"
    try:
        return hashlib.sha256(md.read_bytes()).hexdigest()
    except OSError:
        return None


def _skill_dir_digest(plugin, skill):
    return FC.content_review_dir_digest(PLUGINS_DIR / plugin / "skills" / skill)


def _check_rebind_chain(target, rebinds):
    """sha_rebinds[] が元のレビューの sha から現在の sha まで切れずにつながっているか。"""
    if rebinds is None:
        rebinds = []
    if not isinstance(rebinds, list):
        return "schema: sha_rebinds must be array"
    reviewed = target.get("reviewed_skill_md_sha256")
    if reviewed is not None and not (isinstance(reviewed, str) and SHA_RE.match(reviewed)):
        return "schema: target.reviewed_skill_md_sha256 must be a 64-hex sha256"
    previous = reviewed
    scoped_count = 0
    for number, entry in enumerate(rebinds, 1):
        where = f"rebind-chain: sha_rebinds[{number}]"
        if not isinstance(entry, dict):
            return f"{where} must be object"
        from_sha, to_sha = entry.get("from_sha"), entry.get("to_sha")
        if not all(isinstance(sha, str) and SHA_RE.match(sha) for sha in (from_sha, to_sha)):
            return f"{where} from_sha/to_sha must be 64-hex sha256"
        if from_sha == to_sha:
            return f"{where} from_sha == to_sha"
        if entry.get("tool") != REBIND_TOOL:
            return f"{where} tool must be {REBIND_TOOL}"
        ids, replay, scoped = entry.get("finding_ids"), entry.get("replay"), entry.get("scoped_review")
        if sum(value is not None for value in (ids, replay, scoped)) != 1:
            return f"{where} must hold exactly one of finding_ids, replay and scoped_review"
        if ids is not None and (
            not isinstance(ids, list)
            or not ids
            or not all(isinstance(fid, str) and FINDING_ID_RE.match(fid) for fid in ids)
            or len(ids) != len(set(ids))  # 要素が文字列だと確かめてから set にする
        ):
            return f"{where} finding_ids must be unique <elegance|rubric>:<n> ids"
        if replay is not None and (not isinstance(replay, str) or replay not in REPLAY_IDS):
            return f"{where} replay {replay!r} is not a registered migration"
        if scoped is not None:
            scoped_error = _check_scoped_entry(scoped)
            if scoped_error:
                return f"{where} {scoped_error}"
            scoped_count += 1
        if previous is not None and from_sha != previous:
            source = "target.reviewed_skill_md_sha256" if number == 1 else f"sha_rebinds[{number - 1}].to_sha"
            return f"{where}.from_sha {from_sha} != {source} {previous}"
        previous = to_sha
    if scoped_count > FC.SCOPED_REVIEW_MAX_PER_FULL_REVIEW:
        return (
            f"scoped-review: {scoped_count} scoped re-reviews since the full review"
            f" (limit {FC.SCOPED_REVIEW_MAX_PER_FULL_REVIEW}); run a full content review"
        )
    if scoped_count and reviewed is None:
        return "scoped-review: scoped re-review needs target.reviewed_skill_md_sha256 (the full review it extends)"
    if rebinds and previous != target.get("skill_md_sha256"):
        return "rebind-chain: last sha_rebinds.to_sha != target.skill_md_sha256"
    if not rebinds and reviewed is not None and reviewed != target.get("skill_md_sha256"):
        return "rebind-chain: target.reviewed_skill_md_sha256 != skill_md_sha256 without sha_rebinds"
    return None


def _check_scoped_entry(scoped):
    """sha_rebinds[].scoped_review の形 (中身の照合は _check_scoped_copy)。"""
    if not isinstance(scoped, dict):
        return "scoped_review must be object"
    keys = {"sections", "reviewer", "reviewed_at", "review_ref", "review_sha256"}
    if set(scoped) != keys:
        return f"scoped_review must hold exactly {sorted(keys)}"
    sections = scoped["sections"]
    if (
        not isinstance(sections, list)
        or not sections
        or len(sections) > FC.SCOPED_REVIEW_MAX_SECTIONS
        or len(set(map(str, sections))) != len(sections)
        or not all(isinstance(section, str) and section.strip() for section in sections)
    ):
        return f"scoped_review.sections must be 1-{FC.SCOPED_REVIEW_MAX_SECTIONS} unique non-empty strings"
    for section in sections:
        # 節は "<見出し>" か "<親> > <子>"。どの段でも入出力契約を名指すなら全体の再レビューへ。
        contract = next(
            (part.strip() for part in section.split(" > ") if part.strip() in FC.SCOPED_REVIEW_CONTRACT_SECTIONS),
            None,
        )
        if contract:
            return (
                f"scoped_review.sections {section!r} is inside the output contract ({contract});"
                " a contract change needs a full content review"
            )
    reviewer = scoped["reviewer"]
    if not isinstance(reviewer, str) or not reviewer.strip() or reviewer.strip() in FC.SCOPED_REVIEW_NON_INDEPENDENT:
        return f"scoped_review.reviewer {reviewer!r} is not an independent reviewer"
    if not isinstance(scoped["reviewed_at"], str) or not scoped["reviewed_at"].strip():
        return "scoped_review.reviewed_at must be a non-empty string"
    if not isinstance(scoped["review_sha256"], str) or not SHA_RE.match(scoped["review_sha256"]):
        return "scoped_review.review_sha256 must be a 64-hex sha256"
    ref = scoped["review_ref"]
    if not isinstance(ref, str) or not SCOPED_REF_RE.match(ref):
        return f"scoped_review.review_ref must be {FC.SCOPED_REVIEW_DIR}/<to_sha>.json"
    return None


def _check_scoped_copy(review_dir, plugin, skill, number, entry):
    """scoped_review の記録が、残したレビューの写しと一致するか。"""
    scoped = entry["scoped_review"]
    where = f"scoped-review: sha_rebinds[{number}]"
    if scoped["review_ref"] != f"{FC.SCOPED_REVIEW_DIR}/{entry['to_sha']}.json":
        return f"{where} review_ref does not name the copy for to_sha"
    copy = review_dir / scoped["review_ref"]
    try:
        raw = copy.read_bytes()
        review = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return f"{where} review copy {scoped['review_ref']} is missing or not JSON"
    if hashlib.sha256(raw).hexdigest() != scoped["review_sha256"]:
        return f"{where} review copy sha256 != review_sha256"
    expected = {
        "kind": FC.SCOPED_REVIEW_KIND, "plugin": plugin, "skill": skill,
        "from_sha": entry["from_sha"], "to_sha": entry["to_sha"],
        "sections": scoped["sections"], "reviewer": scoped["reviewer"], "reviewed_at": scoped["reviewed_at"],
        "verdicts": {"elegance": "PASS", "rubric": "PASS"}, "negative_feedback": [],
    }
    for key, value in expected.items():
        got = review.get(key) if isinstance(review, dict) else None
        if key == "reviewer" and isinstance(got, str):
            got = got.strip()
        if got != value:
            return f"{where} review copy {key}={got!r} != {value!r}"
    return None


def _check_finding_locations(data, review_kind):
    locations = data.get("finding_locations")
    if locations is None:
        return None
    if not isinstance(locations, dict):
        return "schema: finding_locations must be object"
    negative = data["feedback_loop"].get("negative_feedback") or []
    for fid, entry in locations.items():
        m = FINDING_ID_RE.match(fid) if isinstance(fid, str) else None
        if not m or m.group(1) != review_kind or int(m.group(2)) > len(negative):
            return f"schema: finding_locations key {fid!r} must name this verdict's negative_feedback"
        sections = entry.get("sections") if isinstance(entry, dict) else None
        if not isinstance(sections, list) or not sections or not all(
            isinstance(section, str) and section.strip() for section in sections
        ):
            return f"schema: finding_locations[{fid!r}].sections must be non-empty strings"
    return None


def _check_pair(review_dir):
    """elegance と rubric が同じ結び直しの記録を持ち、指摘を使い回していないか。"""
    loaded = {}
    for fname in REQUIRED_VERDICTS:
        loaded[_expected_review_kind(fname)] = json.loads((review_dir / fname).read_text(encoding="utf-8"))
    elegance, rubric = loaded["elegance"], loaded["rubric"]
    for key in ("reviewed_skill_md_sha256", "skill_dir_digest"):
        if elegance["target"].get(key) != rubric["target"].get(key):
            return f"pair-mismatch: target.{key} differs between elegance and rubric"
    rebinds = elegance.get("sha_rebinds") or []
    if rebinds != (rubric.get("sha_rebinds") or []):
        return "pair-mismatch: sha_rebinds differ between elegance and rubric"
    plugin, skill = elegance["target"].get("plugin"), elegance["target"].get("skill")
    used_ids, used_texts = set(), set()
    for number, entry in enumerate(rebinds, 1):
        if isinstance(entry, dict) and isinstance(entry.get("scoped_review"), dict):
            scoped_error = _check_scoped_copy(review_dir, plugin, skill, number, entry)
            if scoped_error:
                return scoped_error
        texts = set()
        for fid in entry.get("finding_ids") or []:
            kind, index = FINDING_ID_RE.match(fid).groups()
            negative = loaded[kind]["feedback_loop"].get("negative_feedback") or []
            if int(index) > len(negative) or not isinstance(negative[int(index) - 1], str):
                return f"rebind-chain: sha_rebinds[{number}] {fid} does not name a negative_feedback entry"
            text = " ".join(negative[int(index) - 1].split())
            if fid in used_ids or text in used_texts:
                return f"rebind-chain: sha_rebinds[{number}] reuses finding {fid}"
            texts.add(text)
        used_ids.update(entry.get("finding_ids") or [])
        used_texts.update(texts)
    return None


def print_target(spec):
    # 補完で付く末尾の / は落とす (残すと skill が "run-x/" になり、書いた verdict が target-mismatch になる)
    plugin, _, skill = spec.rstrip("/").partition("/")
    if (
        not plugin
        or not skill
        or "/" in skill
        or not (PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md").is_file()
    ):
        print(f"[FAIL] content-review lint: no SKILL.md for {spec!r}", file=sys.stderr)
        return 2
    sha = _skill_sha256(plugin, skill)
    digest = _skill_dir_digest(plugin, skill)
    if sha is None or digest is None:
        print(f"[FAIL] content-review lint: cannot read {spec}", file=sys.stderr)
        return 2
    target = {
        "plugin": plugin,
        "skill": skill,
        "skill_md_sha256": sha,
        "reviewed_skill_md_sha256": sha,
        "skill_dir_digest": digest,
    }
    print(json.dumps(target, ensure_ascii=False, indent=2))
    return 0


def _expected_review_kind(fname):
    if fname.startswith("elegance-"):
        return "elegance"
    if fname.startswith("rubric-"):
        return "rubric"
    return None


def _json_type(value):
    """違反の文に書く JSON の型の名前。"""
    if value is None:
        return "null"
    for python_type, name in ((bool, "boolean"), (dict, "object"), (list, "array"), (str, "string"), ((int, float), "number")):
        if isinstance(value, python_type):
            return name
    return type(value).__name__


def _check_verdict(path, plugin, skill, fname):
    if not path.is_file():
        return "missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"invalid-json: {exc}"
    if not isinstance(data, dict):
        return f"schema: verdict must be a JSON object, got {_json_type(data)}"
    for key in ("target", "review_kind", "verdict", "reviewer", "reviewed_at", "iterations", "feedback_loop"):
        if key not in data:
            return f"schema: missing {key}"
    target = data.get("target")
    if not isinstance(target, dict):
        return "schema: target must be object"
    if target.get("plugin") != plugin or target.get("skill") != skill:
        return (
            "target-mismatch: "
            f"expected {plugin}/{skill}, got {target.get('plugin')}/{target.get('skill')}"
        )
    expected_kind = _expected_review_kind(fname)
    if expected_kind and data.get("review_kind") != expected_kind:
        return f"review_kind={data.get('review_kind')} expected={expected_kind}"
    verdict = data.get("verdict")
    if verdict != "PASS":
        return f"verdict={verdict}"
    current_sha = _skill_sha256(plugin, skill)
    recorded_sha = target.get("skill_md_sha256")
    if not recorded_sha:
        return "schema: target.skill_md_sha256 missing"
    chain_error = _check_rebind_chain(target, data.get("sha_rebinds"))
    if chain_error:
        return chain_error
    if current_sha is None:
        return "stale-sha: cannot read SKILL.md"
    if recorded_sha != current_sha:
        return f"stale-sha: {recorded_sha} != current {current_sha}"
    recorded_digest = target.get("skill_dir_digest")
    if recorded_digest is not None:
        current_digest = _skill_dir_digest(plugin, skill)
        if current_digest is None:
            return "stale-dir-digest: cannot read the skill directory"
        if recorded_digest != current_digest:
            return f"stale-dir-digest: {recorded_digest} != current {current_digest}"
    if not isinstance(data.get("iterations"), int):
        return "schema: iterations must be integer"
    feedback_loop = data.get("feedback_loop")
    if not isinstance(feedback_loop, dict):
        return "schema: feedback_loop must be object"
    criteria = feedback_loop.get("criteria_evaluated")
    if not isinstance(criteria, list) or not criteria:
        return "schema: feedback_loop.criteria_evaluated must be non-empty array"
    for number, criterion in enumerate(criteria, 1):
        if not isinstance(criterion, str):
            return f"schema: feedback_loop.criteria_evaluated[{number}] must be string, got {_json_type(criterion)}"
    if len(criteria) != len(set(criteria)):
        return "schema: feedback_loop.criteria_evaluated has duplicates"
    if not isinstance(feedback_loop.get("iteration_limit"), int):
        return "schema: feedback_loop.iteration_limit must be integer"
    if not isinstance(feedback_loop.get("iteration"), int):
        return "schema: feedback_loop.iteration must be integer"
    # 列挙の照合は文字列だと確かめてから (配列や object は set の in で落ちる)
    loop_scope = feedback_loop.get("loop_scope")
    if not isinstance(loop_scope, str) or loop_scope not in {"inner", "outer", "both"}:
        return "schema: feedback_loop.loop_scope invalid"
    if not isinstance(feedback_loop.get("positive_feedback"), list):
        return "schema: feedback_loop.positive_feedback must be array"
    if not isinstance(feedback_loop.get("negative_feedback"), list):
        return "schema: feedback_loop.negative_feedback must be array"
    next_action = feedback_loop.get("next_action")
    if not isinstance(next_action, str) or next_action not in {"none", "improve", "re_evaluate", "human_review"}:
        return "schema: feedback_loop.next_action invalid"
    if not isinstance(feedback_loop.get("hook_trigger"), str) or not feedback_loop.get("hook_trigger").strip():
        return "schema: feedback_loop.hook_trigger missing"
    locations_error = _check_finding_locations(data, data.get("review_kind"))
    if locations_error:
        return locations_error
    expected = _expected_criteria_ids(plugin, skill)
    if expected:
        missing = expected - set(criteria)
        if missing:
            return f"criteria-missing: {sorted(missing)}"
    return None


def _expected_criteria_ids(plugin, skill):
    """期待される feedback_contract.criteria id 集合を返す。

    正本は **量産先 SKILL.md frontmatter の feedback_contract**(携帯する評価基準)。
    frontmatter に無い場合のみ後方互換で build trace(skill-local→global)を best-effort
    で読む。どこにも無ければ空集合を返す(verdict 自体の必須構造のみ検査)。
    """
    # 1) frontmatter 正本 (SSOT)
    md = PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md"
    try:
        fc = FC.extract_frontmatter_feedback_contract(md.read_text(encoding="utf-8"))
        ids = FC.criteria_ids(fc.get("criteria")) if isinstance(fc, dict) else set()
        if ids:
            return ids
    except OSError:
        pass

    # 2) 後方互換: build trace (世代差で skill-local→global)
    candidates = [
        EVAL_LOG / plugin / skill / "skill-build-trace.json",
        EVAL_LOG / "skill-build-trace.json",
    ]
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue  # 後方互換の best-effort 入力。JSON として読めないときと同じく読み飛ばす
        if path.name == "skill-build-trace.json" and data.get("skill_name") not in (None, skill):
            continue
        fc = data.get("feedback_contract")
        if not isinstance(fc, dict):
            continue
        ids = FC.criteria_ids(fc.get("criteria"))
        if ids:
            return ids
    return set()


def _guarded(check, *args):
    """検査を呼び、予期しない例外は落とさずその skill の違反の文にする (残りの skill も検査する)。"""
    try:
        return check(*args)
    except Exception as exc:  # 形の崩れた入力で traceback にせず、違反の側に倒す (fail-closed)
        return f"check-error: could not finish the check ({type(exc).__name__}: {exc})"


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--changed-only", action="store_true")
    g.add_argument("--all", action="store_true")
    g.add_argument("--print-target", metavar="PLUGIN/SKILL", help="新しい verdict に書く target を出す")
    ap.add_argument("--base", default="origin/main")
    args = ap.parse_args()
    if args.print_target:
        return print_target(args.print_target)

    try:
        targets = _git_changed_skills(args.base) if args.changed_only else _all_skills()
    except GitDiffError as exc:
        print(f"[FAIL] content-review lint: {exc}", file=sys.stderr)
        print("     存在する ref を --base に渡すか、--all で全 skill を検査してください。", file=sys.stderr)
        return 2
    targets = {
        (plugin, skill)
        for plugin, skill in targets
        if not FC.is_vendored_feedback_skill(
            PLUGINS_DIR / plugin / "skills" / skill, plugins_dir=PLUGINS_DIR
        )
    }
    # filter
    filtered = []
    for plugin, skill in sorted(targets):
        if FC.is_content_review_exempt(plugin):
            continue
        kind = _read_kind(plugin, skill)
        if kind in EXEMPT_KINDS:
            continue
        # SKILL.md が削除された変更も target に含まれるので存在チェック
        if not (PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md").is_file():
            continue
        filtered.append((plugin, skill))

    if not filtered:
        print("[OK] content-review lint: no target skill")
        return 0

    violations = []
    for plugin, skill in filtered:
        review_dir = EVAL_LOG / plugin / skill / "content-review"
        errors = []
        for fname in REQUIRED_VERDICTS:
            err = _guarded(_check_verdict, review_dir / fname, plugin, skill, fname)
            if err:
                errors.append(f"{plugin}/{skill}: {fname} {err}")
        if not errors:
            err = _guarded(_check_pair, review_dir)
            if err:
                errors.append(f"{plugin}/{skill}: {err}")
        violations.extend(errors)

    if violations:
        print(f"[FAIL] content-review lint: {len(violations)} violation(s)")
        for v in violations:
            print(f"  - {v}")
        print()
        print("Fix: ローカル Claude Code で assign-skill-design-evaluator の focused combined review を")
        print("     1 context 実行してください。4 条件は elegance-verdict.json に書き、rubric-verdict.json は")
        print("     render-findings-score.py --write-rubric-verdict <path> --judgments <判定> に書かせます。")
        print("     完全な run-elegant-review + rubric evaluator は exhaustive 明示時だけです。")
        print("     target は --print-target <plugin>/<skill> の出力を写し、指摘には finding_locations を書きます。")
        print("     指摘を当てただけの stale-sha は sync-content-review-sha.py --finding-ids で、節の外の小さな")
        print("     手直しは --scoped-review で結び直せます (rebind-chain は手で直さない)。")
        print("     手順詳細: plugins/harness-creator/skills/run-build-skill/references/content-review-protocol.md")
        return 1

    print(f"[OK] content-review lint: {len(filtered)} skill(s) verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
