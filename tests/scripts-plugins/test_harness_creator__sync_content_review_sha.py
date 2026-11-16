"""Functional tests for run-elegant-review/scripts/sync-content-review-sha.py.

レビュー由来の修正を当てた直後に限り content-review verdict の sha を結び直す script。
CLI 契約 (exit 0/1/2・書く/書かない) は subprocess で、結び直し後の verdict が
scripts/lint-content-review.py の _check_verdict / _check_pair を通ることは lint の module を
tmp の repo へ向けて確かめる (repo の eval-log は触らない)。

harness-g67 で塞いだ穴:
  - 未使用の id を 1 つ挙げれば、どの節を書き換えても結び直せた (変更箇所の照合で止める)。
  - references/ などを変えても verdict が緑のままだった (skill_dir_digest で止める)。
  - sha_rebinds が元のレビューから現在までつながっているかを誰も見ていなかった (連鎖検査)。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = REPO_ROOT / "plugins" / "harness-creator"
SCRIPT = PLUGIN / "skills" / "run-elegant-review" / "scripts" / "sync-content-review-sha.py"
SCHEMA = PLUGIN / "skills" / "run-build-skill" / "schemas" / "content-review-verdict.schema.json"
LINT = REPO_ROOT / "scripts" / "lint-content-review.py"
ENTRYPOINT_LINT = REPO_ROOT / "scripts" / "lint-entrypoint-artifact-first.py"
SSOT = REPO_ROOT / "scripts" / "feedback_contract_ssot.py"
AGENT = PLUGIN / "agents" / "elegant-improvement-executor.md"
PROTOCOL = PLUGIN / "skills" / "run-build-skill" / "references" / "content-review-protocol.md"

PLUGIN_NAME, SKILL_NAME = "p1", "run-x"
FRONT = "---\nname: run-x\nkind: run\n---\n"
BEFORE = FRONT + "# run-x\n\n概要\n\n## 手順\n\n本文 (修正前)\n\n## Gotchas\n\n- 注意\n"
AFTER = FRONT + "# run-x\n\n概要\n\n## 手順\n\n本文 (指摘を当てた後)\n\n## Gotchas\n\n- 注意\n"
LOCATIONS = {
    "elegance": {"elegance:1": {"sections": ["手順"]}, "elegance:2": {"sections": ["手順"]}},
    "rubric": {"rubric:1": {"sections": ["手順"], "source_id": "R5-01"}},
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verdict(review_kind: str, sha: str, negative: list[str], verdict: str = "PASS") -> dict:
    return {
        "target": {"plugin": PLUGIN_NAME, "skill": SKILL_NAME, "skill_md_sha256": sha},
        "review_kind": review_kind,
        "verdict": verdict,
        "findings_summary": {"contradiction": 0, "omission": 0, "inconsistency": 0, "dependency_break": 0, "smell": len(negative)},
        "reviewer": "assign-skill-design-evaluator",
        "reviewed_at": "2026-11-13T00:00:00Z",
        "iterations": 1,
        "human_review_required": False,
        "feedback_loop": {
            "loop_scope": "both",
            "criteria_evaluated": ["IN1"],
            "positive_feedback": ["良い判断"],
            "negative_feedback": negative,
            "iteration": 1,
            "iteration_limit": 3,
            "hook_trigger": "manual",
            "next_action": "none",
        },
        "notes": "日本語のメモ",
        "finding_locations": LOCATIONS[review_kind],
    }


def _make_repo(root: Path, before: str, after: str) -> dict:
    md = root / "plugins" / PLUGIN_NAME / "skills" / SKILL_NAME / "SKILL.md"
    md.parent.mkdir(parents=True)
    md.write_text(before, encoding="utf-8")
    review_dir = root / "eval-log" / PLUGIN_NAME / SKILL_NAME / "content-review"
    review_dir.mkdir(parents=True)
    paths = {
        "elegance": review_dir / "elegance-verdict.json",
        "rubric": review_dir / "rubric-verdict.json",
    }
    sha_before = _sha(before)
    for kind, negative in (("elegance", ["[low] 指摘 A", "[low] 指摘 B"]), ("rubric", ["[low] 指摘 A'"])):
        text = json.dumps(_verdict(kind, sha_before, negative), ensure_ascii=False, indent=2) + "\n"
        paths[kind].write_text(text, encoding="utf-8")
    # 編集前に写しを取る (executor の手順と同じ)
    copy = root / "before.md"
    copy.write_text(before, encoding="utf-8")
    # レビューの勧めた修正を当てた状態 (SKILL.md が変わった)
    md.write_text(after, encoding="utf-8")
    return {"root": root, "md": md, "paths": paths, "before": sha_before, "after": _sha(after), "from_file": copy}


@pytest.fixture
def repo(tmp_path):
    return _make_repo(tmp_path, BEFORE, AFTER)


def _run(repo, *, from_sha=None, ids="elegance:1", replay=None, scoped=None, from_file="default", extra=()):
    cmd = [
        sys.executable, str(SCRIPT),
        "--plugin", PLUGIN_NAME, "--skill", SKILL_NAME,
        "--from-sha", from_sha if from_sha is not None else repo["before"],
        "--repo-root", str(repo["root"]),
    ]
    if replay is not None:
        cmd += ["--replay", replay]
    if scoped is not None:
        cmd += ["--scoped-review", str(scoped)]
    if ids is not None:
        cmd += ["--finding-ids", ids]
    if from_file == "default":
        from_file = repo["from_file"]
    if from_file is not None:
        cmd += ["--from-file", str(from_file)]
    return subprocess.run([*cmd, *extra], capture_output=True, text=True)


def _snapshot(repo) -> dict:
    return {kind: path.read_bytes() for kind, path in repo["paths"].items() if path.exists()}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _edit_verdicts(repo, change) -> None:
    for kind, path in repo["paths"].items():
        data = _load(path)
        change(kind, data)
        _dump(path, data)


def _save_copy(repo, name: str) -> Path:
    """いまの SKILL.md の写しを取る (次の修正の --from-file)。"""
    copy = repo["root"] / name
    copy.write_bytes(repo["md"].read_bytes())
    return copy


def _load_lint(repo, monkeypatch):
    lint = _load_module(LINT, "lint_content_review_for_sync")
    monkeypatch.setattr(lint, "ROOT", repo["root"])
    monkeypatch.setattr(lint, "PLUGINS_DIR", repo["root"] / "plugins")
    monkeypatch.setattr(lint, "EVAL_LOG", repo["root"] / "eval-log")
    return lint


def _assert_lint_passes(repo, monkeypatch):
    lint = _load_lint(repo, monkeypatch)
    review_dir = repo["paths"]["elegance"].parent
    for fname in ("elegance-verdict.json", "rubric-verdict.json"):
        assert lint._check_verdict(review_dir / fname, PLUGIN_NAME, SKILL_NAME, fname) is None
    assert lint._check_pair(review_dir) is None


def _expect_reject(repo, message, **kwargs):
    snapshot = _snapshot(repo)
    proc = _run(repo, **kwargs)
    assert proc.returncode == 1, proc.stderr
    assert message in proc.stderr
    assert "要再レビュー" in proc.stderr
    assert _snapshot(repo) == snapshot


# ---------- 結び直し (成功) ----------

def test_rebind_updates_both_verdicts_and_appends_audit_record(repo):
    originals = {kind: _load(path) for kind, path in repo["paths"].items()}
    proc = _run(repo, ids="elegance:2, rubric:1")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"] == "rebound"
    assert out["to_sha"] == repo["after"]

    for kind, path in repo["paths"].items():
        data = _load(path)
        assert data["target"]["skill_md_sha256"] == repo["after"]
        assert data["target"]["reviewed_skill_md_sha256"] == repo["before"]
        (entry,) = data["sha_rebinds"]
        assert entry["from_sha"] == repo["before"]
        assert entry["to_sha"] == repo["after"]
        assert entry["finding_ids"] == ["elegance:2", "rubric:1"]
        assert "replay" not in entry
        assert entry["tool"] == "sync-content-review-sha"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", entry["rebound_at"])
        # sha・起点の sha・監査記録のほかは変えない (verdict・reviewer・reviewed_at・iterations を含む)
        expected = dict(originals[kind])
        expected["target"] = {
            **expected["target"],
            "skill_md_sha256": repo["after"],
            "reviewed_skill_md_sha256": repo["before"],
        }
        expected["sha_rebinds"] = data["sha_rebinds"]
        assert data == expected
        Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(data)


def test_rebind_keeps_the_original_json_layout(repo):
    assert _run(repo).returncode == 0
    for path in repo["paths"].values():
        text = path.read_text(encoding="utf-8")
        assert text == json.dumps(_load(path), ensure_ascii=False, indent=2) + "\n"
        assert "日本語のメモ" in text  # ensure_ascii=False の元ファイルを \\u エスケープへ変えない


def test_rebound_verdicts_pass_lint_content_review(repo, monkeypatch):
    lint = _load_lint(repo, monkeypatch)
    review_dir = repo["paths"]["elegance"].parent
    for fname in ("elegance-verdict.json", "rubric-verdict.json"):
        before = lint._check_verdict(review_dir / fname, PLUGIN_NAME, SKILL_NAME, fname)
        assert before.startswith("stale-sha:")  # 修正を当てただけで stale になる (因果ループの起点)

    assert _run(repo).returncode == 0
    _assert_lint_passes(repo, monkeypatch)


def test_change_in_a_child_of_the_listed_section_is_covered(tmp_path, monkeypatch):
    before = FRONT + "# run-x\n\n## 手順\n\n前置き\n\n### 例\n\n- 古い例\n\n## Gotchas\n\n- 注意\n"
    after = before.replace("- 古い例", "- 新しい例")
    repo = _make_repo(tmp_path, before, after)
    proc = _run(repo)  # elegance:1 の節は「手順」。変わったのはその子の「手順 > 例」
    assert proc.returncode == 0, proc.stderr
    _assert_lint_passes(repo, monkeypatch)


def test_hash_lines_inside_a_code_fence_are_not_headings(tmp_path):
    before = FRONT + "# run-x\n\n## 手順\n\n```bash\n# 古いコメント\nmake test\n```\n\n## Gotchas\n\n- 注意\n"
    after = before.replace("# 古いコメント", "# 新しいコメント")
    repo = _make_repo(tmp_path, before, after)
    # fence の中の # 行を見出しと読むと、見出しが変わったとして拒否してしまう
    proc = _run(repo)
    assert proc.returncode == 0, proc.stderr


def test_parent_qualified_location_resolves_a_repeated_heading(tmp_path):
    before = FRONT + "# run-x\n\n## 手順\n\n### 例\n\n- a\n\n## Gotchas\n\n### 例\n\n- b\n"
    after = before.replace("- a", "- a2")
    repo = _make_repo(tmp_path, before, after)
    _edit_verdicts(repo, lambda kind, data: data["finding_locations"].update(
        {f"{kind}:1": {"sections": ["手順 > 例"]}}
    ))
    proc = _run(repo)
    assert proc.returncode == 0, proc.stderr


def test_the_skill_md_before_the_edit_is_found_in_git(repo):
    root = repo["root"]
    repo["md"].write_text(BEFORE, encoding="utf-8")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run([*git, "add", "plugins"], cwd=root, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "before"], cwd=root, check=True)
    repo["md"].write_text(AFTER, encoding="utf-8")
    proc = _run(repo, from_file=None)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "rebound"


# ---------- 変更箇所の照合で拒否 (harness-g67) ----------

def test_change_outside_the_listed_sections_is_rejected(repo):
    repo["md"].write_text(BEFORE.replace("- 注意", "- 審査されていない注意"), encoding="utf-8")
    _expect_reject(repo, "の外です")


def test_change_in_both_listed_and_unlisted_sections_is_rejected(repo):
    repo["md"].write_text(AFTER.replace("- 注意", "- 審査されていない注意"), encoding="utf-8")
    _expect_reject(repo, "'run-x > Gotchas' の変更は")


def test_change_to_the_document_intro_is_rejected(repo):
    repo["md"].write_text(BEFORE.replace("概要", "書き換えた概要"), encoding="utf-8")
    _expect_reject(repo, "'run-x' の変更は")


def test_text_before_the_first_heading_is_rejected(repo):
    repo["md"].write_text(BEFORE.replace("# run-x\n", "前置き\n\n# run-x\n"), encoding="utf-8")
    _expect_reject(repo, "最初の見出しより前")


def test_frontmatter_change_is_rejected(repo):
    repo["md"].write_text(AFTER.replace("kind: run", "kind: run\nextra: 1"), encoding="utf-8")
    _expect_reject(repo, "frontmatter")


@pytest.mark.parametrize("after", [
    BEFORE.replace("## 手順", "## 手順 (改)"),
    BEFORE.replace("## Gotchas", "## 追加\n\n- x\n\n## Gotchas"),
    BEFORE.replace("## 手順\n\n本文 (修正前)\n\n## Gotchas\n\n- 注意\n", "## Gotchas\n\n- 注意\n\n## 手順\n\n本文 (修正前)\n"),
    BEFORE.replace("## Gotchas", "### Gotchas"),
])
def test_heading_changes_are_rejected(repo, after):
    repo["md"].write_text(after, encoding="utf-8")
    _expect_reject(repo, "見出し")


def test_finding_without_locations_is_rejected(repo):
    _edit_verdicts(repo, lambda kind, data: data.pop("finding_locations"))
    _expect_reject(repo, "finding_locations に節がありません")


def test_location_naming_a_missing_section_is_rejected(repo):
    _edit_verdicts(repo, lambda kind, data: data["finding_locations"].update(
        {f"{kind}:1": {"sections": ["存在しない節"]}}
    ))
    _expect_reject(repo, "ありません")


def test_ambiguous_location_is_rejected(tmp_path):
    before = FRONT + "# run-x\n\n## 手順\n\n### 例\n\n- a\n\n## Gotchas\n\n### 例\n\n- b\n"
    repo = _make_repo(tmp_path, before, before.replace("- a", "- a2"))
    _edit_verdicts(repo, lambda kind, data: data["finding_locations"].update(
        {f"{kind}:1": {"sections": ["例"]}}
    ))
    _expect_reject(repo, "2 か所あります")


def test_document_heading_cannot_be_a_location(repo):
    _edit_verdicts(repo, lambda kind, data: data["finding_locations"].update(
        {f"{kind}:1": {"sections": ["run-x"]}}
    ))
    _expect_reject(repo, "文書全体の見出し")


# ---------- skill ディレクトリの digest と連鎖 (harness-g67) ----------

def test_reference_change_after_review_is_rejected_when_the_digest_is_recorded(repo, monkeypatch):
    ssot = _load_module(SSOT, "feedback_contract_ssot_for_sync_test")
    skill_dir = repo["md"].parent
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "guide.md").write_text("レビューした版\n", encoding="utf-8")
    digest = ssot.content_review_dir_digest(skill_dir)
    _edit_verdicts(repo, lambda kind, data: data["target"].update({"skill_dir_digest": digest}))
    # scripts/ は digest の外なので変えても結び直せる
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "x.py").write_text("print(1)\n", encoding="utf-8")
    assert ssot.content_review_dir_digest(skill_dir) == digest

    (skill_dir / "references" / "guide.md").write_text("レビューしていない版\n", encoding="utf-8")
    _expect_reject(repo, "skill_dir_digest")

    (skill_dir / "references" / "guide.md").write_text("レビューした版\n", encoding="utf-8")
    assert _run(repo).returncode == 0
    _assert_lint_passes(repo, monkeypatch)


def test_broken_chain_is_rejected(repo):
    def broken(kind, data):
        data["sha_rebinds"] = [{
            "from_sha": _sha("もっと前\n"),
            "to_sha": _sha("別の版\n"),
            "finding_ids": ["elegance:2"],
            "rebound_at": "2026-11-13T00:00:00Z",
            "tool": "sync-content-review-sha",
        }]
    _edit_verdicts(repo, broken)
    _expect_reject(repo, "連鎖が切れている")


def test_two_rebinds_chain_and_pass_lint(repo, monkeypatch):
    assert _run(repo, ids="elegance:1").returncode == 0
    copy = _save_copy(repo, "after.md")
    repo["md"].write_text(AFTER.replace("指摘を当てた後", "2 つ目の指摘も当てた後"), encoding="utf-8")
    proc = _run(repo, from_sha=repo["after"], ids="elegance:2", from_file=copy)
    assert proc.returncode == 0, proc.stderr
    data = _load(repo["paths"]["elegance"])
    first, second = data["sha_rebinds"]
    assert data["target"]["reviewed_skill_md_sha256"] == first["from_sha"] == repo["before"]
    assert second["from_sha"] == first["to_sha"] == repo["after"]
    assert second["to_sha"] == data["target"]["skill_md_sha256"]
    _assert_lint_passes(repo, monkeypatch)


# ---------- 機械的な移行の再生 (--replay) ----------

def _contract_skill(body_suffix: str = "") -> str:
    lint = _load_module(ENTRYPOINT_LINT, "entrypoint_lint_for_sync_test")
    block = yaml.safe_dump({"artifact_delivery": lint.COPIED_CONTRACT_V1}, allow_unicode=True, sort_keys=False)
    return "---\nname: run-x\n" + block + "kind: run\n---\n# run-x\n\n## 手順\n\n本文" + body_suffix + "\n"


@pytest.fixture
def replay_repo(tmp_path):
    lint = _load_module(ENTRYPOINT_LINT, "entrypoint_lint_for_sync_test")
    before = _contract_skill()
    after = lint.rewrite_copied_contract(before)
    assert after is not None and "artifact_delivery: artifact-delivery-v1\n" in after
    repo = _make_repo(tmp_path, before, after)
    (tmp_path / "scripts").mkdir()
    shutil.copy2(ENTRYPOINT_LINT, tmp_path / "scripts" / ENTRYPOINT_LINT.name)
    return repo


def test_replay_rebinds_a_mechanical_migration(replay_repo, monkeypatch):
    proc = _run(replay_repo, ids=None, replay="artifact-delivery-v1")
    assert proc.returncode == 0, proc.stderr
    for path in replay_repo["paths"].values():
        data = _load(path)
        (entry,) = data["sha_rebinds"]
        assert entry["replay"] == "artifact-delivery-v1"
        assert "finding_ids" not in entry
        assert data["target"]["reviewed_skill_md_sha256"] == replay_repo["before"]
        Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(data)
    _assert_lint_passes(replay_repo, monkeypatch)


def test_replay_with_an_extra_manual_edit_is_rejected(replay_repo):
    replay_repo["md"].write_text(replay_repo["md"].read_text(encoding="utf-8") + "審査されていない追記\n", encoding="utf-8")
    _expect_reject(replay_repo, "一致しません", ids=None, replay="artifact-delivery-v1")


def test_replay_on_a_skill_without_the_copy_is_rejected(repo):
    (repo["root"] / "scripts").mkdir()
    shutil.copy2(ENTRYPOINT_LINT, repo["root"] / "scripts" / ENTRYPOINT_LINT.name)
    _expect_reject(repo, "変換の対象がありません", ids=None, replay="artifact-delivery-v1")


def test_replay_and_finding_ids_are_mutually_exclusive(replay_repo):
    snapshot = _snapshot(replay_repo)
    proc = _run(replay_repo, ids="elegance:1", replay="artifact-delivery-v1")
    assert proc.returncode == 2
    assert _snapshot(replay_repo) == snapshot


def test_unknown_replay_id_exits_2(replay_repo):
    proc = _run(replay_repo, ids=None, replay="artifact-delivery-v0")
    assert proc.returncode == 2


def test_replay_rebinds_the_two_choice_migration_on_top_of_the_v1_migration(tmp_path, monkeypatch):
    """vvd の移行の後に 2 択化 (harness-znj) を当てても、結び直しは連鎖として 1 本につながる。"""
    lint = _load_module(ENTRYPOINT_LINT, "entrypoint_lint_for_sync_test")
    legacy = "\n\nPurpose & Output Contractの現物を提示してからaccept-as-is/light/standard/detailedを記録する。"
    before = _contract_skill(legacy)
    middle = lint.rewrite_copied_contract(before)
    after = lint.rewrite_diagnostic_choices(middle)
    assert after is not None and "accept-as-is/diagnoseを記録する" in after
    repo = _make_repo(tmp_path, before, middle)
    (tmp_path / "scripts").mkdir()
    shutil.copy2(ENTRYPOINT_LINT, tmp_path / "scripts" / ENTRYPOINT_LINT.name)
    assert _run(repo, ids=None, replay="artifact-delivery-v1").returncode == 0
    pre_image = tmp_path / "pre-2way.md"
    pre_image.write_text(middle, encoding="utf-8")
    repo["md"].write_text(after, encoding="utf-8")
    middle_sha = hashlib.sha256(middle.encode("utf-8")).hexdigest()
    proc = _run(repo, ids=None, replay="diagnostic-choice-2way", from_sha=middle_sha, from_file=pre_image)
    assert proc.returncode == 0, proc.stderr
    for path in repo["paths"].values():
        data = _load(path)
        first, second = data["sha_rebinds"]
        assert (first["replay"], second["replay"]) == ("artifact-delivery-v1", "diagnostic-choice-2way")
        assert second["from_sha"] == first["to_sha"] == middle_sha
        assert data["target"]["reviewed_skill_md_sha256"] == repo["before"]
        Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(data)


def test_replay_registry_matches_lint_and_schema():
    sync = _load_module(SCRIPT, "sync_content_review_sha_for_test")
    lint = _load_module(LINT, "lint_content_review_registry_test")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enum = schema["properties"]["sha_rebinds"]["items"]["properties"]["replay"]["enum"]
    assert set(sync.REPLAYS) == set(lint.REPLAY_IDS) == set(enum)
    for rel, function in sync.REPLAYS.values():
        assert callable(getattr(_load_module(REPO_ROOT / rel, "replay_target_for_test"), function))


# ---------- 拒否 (exit 1・ファイルは変えない) ----------

def test_fail_verdict_is_rejected(repo):
    path = repo["paths"]["rubric"]
    data = _load(path)
    data["verdict"] = "FAIL"
    _dump(path, data)
    _expect_reject(repo, "verdict='FAIL'")


def test_from_sha_mismatch_is_rejected(repo):
    _expect_reject(repo, "--from-sha", from_sha=_sha("別の内容\n"), from_file=None)


@pytest.mark.parametrize("ids", ["elegance:3", "rubric:2", "elegance:1,rubric:9"])
def test_unknown_finding_id_is_rejected(repo, ids):
    _expect_reject(repo, "negative_feedback", ids=ids)


def test_empty_finding_ids_are_rejected(repo):
    _expect_reject(repo, "--finding-ids が空", ids=" , ")


def test_verdict_without_negative_feedback_cannot_be_rebound(repo):
    path = repo["paths"]["elegance"]
    data = _load(path)
    data["feedback_loop"]["negative_feedback"] = []
    _dump(path, data)
    _expect_reject(repo, "negative_feedback", ids="elegance:1")


def test_missing_one_verdict_is_rejected(repo):
    repo["paths"]["rubric"].unlink()
    _expect_reject(repo, "rubric-verdict.json")


def test_missing_pre_image_is_rejected(repo):
    # git にも --from-file にも適用前の版が無い (tmp は git repo ではない)
    _expect_reject(repo, "--from-file で渡して", from_file=None)


def test_a_finding_rebinds_only_once(repo):
    assert _run(repo, ids="elegance:1").returncode == 0
    # 結び直した後にもう一度 手順 を書き換え、同じ指摘で通そうとする
    copy = _save_copy(repo, "after.md")
    repo["md"].write_text(AFTER.replace("指摘を当てた後", "審査されていない書き換え"), encoding="utf-8")
    _expect_reject(repo, "すでに sha_rebinds で使われた", from_sha=repo["after"], ids="elegance:1", from_file=copy)
    # まだ使っていない指摘なら結び直せる (記録は 2 件になる)
    assert _run(repo, from_sha=repo["after"], ids="elegance:2", from_file=copy).returncode == 0
    assert len(_load(repo["paths"]["rubric"])["sha_rebinds"]) == 2


def _share_text_between_verdicts(repo):
    """rubric の 1 番目を elegance の 1 番目と同じ本文にする (1 文脈が 2 verdict を書く実態)。"""
    path = repo["paths"]["rubric"]
    data = _load(path)
    data["feedback_loop"]["negative_feedback"] = ["[low]  指摘 A"]  # 空白の揺れも同じ指摘とみなす
    _dump(path, data)


def test_same_finding_cannot_be_reused_under_the_other_verdicts_id(repo):
    _share_text_between_verdicts(repo)
    assert _run(repo, ids="elegance:1").returncode == 0
    copy = _save_copy(repo, "after.md")
    repo["md"].write_text(AFTER.replace("指摘を当てた後", "審査されていない書き換え"), encoding="utf-8")
    _expect_reject(repo, "同じ本文の指摘", from_sha=repo["after"], ids="rubric:1", from_file=copy)


def test_both_ids_of_one_finding_may_be_listed_in_one_call(repo):
    _share_text_between_verdicts(repo)
    proc = _run(repo, ids="elegance:1,rubric:1")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "rebound"


# ---------- 元の id (source_id) で指摘を挙げる ----------

def test_source_id_resolves_to_the_finding_it_names(repo):
    proc = _run(repo, ids="R5-01")
    assert proc.returncode == 0, proc.stderr
    for path in repo["paths"].values():
        (entry,) = _load(path)["sha_rebinds"]
        assert entry["finding_ids"] == ["rubric:1"]  # 記録は位置の id (lint の照合と同じ形)


def test_a_shared_source_id_consumes_both_verdicts_findings(repo):
    _share_text_between_verdicts(repo)
    _edit_verdicts(repo, lambda kind, data: data["finding_locations"][f"{kind}:1"].update(source_id="F-0003"))
    proc = _run(repo, ids="F-0003")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["finding_ids"] == ["elegance:1", "rubric:1"]
    # 同じ指摘をもう片方の id で使い回せない
    copy = _save_copy(repo, "after.md")
    repo["md"].write_text(AFTER.replace("指摘を当てた後", "審査されていない書き換え"), encoding="utf-8")
    _expect_reject(repo, "すでに sha_rebinds で使われた", from_sha=repo["after"], ids="rubric:1", from_file=copy)


@pytest.mark.parametrize("ids", ["F-9999", "elegance:1,R5-02"])
def test_unknown_source_id_is_rejected(repo, ids):
    _expect_reject(repo, "source_id にもありません", ids=ids)


# ---------- 書かない成功 (noop / dry-run / already-bound) ----------

def test_noop_when_skill_md_is_unchanged(repo):
    repo["md"].write_text(BEFORE, encoding="utf-8")
    snapshot = _snapshot(repo)
    proc = _run(repo)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["status"] == "noop"
    assert _snapshot(repo) == snapshot


def test_dry_run_does_not_write(repo):
    snapshot = _snapshot(repo)
    proc = _run(repo, extra=("--dry-run",))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"] == "dry-run"
    assert out["entry"]["to_sha"] == repo["after"]
    assert _snapshot(repo) == snapshot
    assert not list(repo["paths"]["elegance"].parent.glob(".*"))  # 一時ファイルも残さない


def test_rerun_with_same_arguments_is_idempotent(repo):
    assert _run(repo).returncode == 0
    snapshot = _snapshot(repo)
    proc = _run(repo)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["status"] == "already-bound"
    assert _snapshot(repo) == snapshot


# ---------- 引数・入出力の誤り (exit 2) ----------

@pytest.mark.parametrize("args", [
    {"ids": "F 001"},
    {"ids": "elegance:x"},
    {"ids": "elegance:0"},
    {"from_sha": "abc"},
])
def test_malformed_arguments_exit_2(repo, args):
    snapshot = _snapshot(repo)
    proc = _run(repo, **args)
    assert proc.returncode == 2
    assert _snapshot(repo) == snapshot


def test_from_file_with_another_sha_exits_2(repo):
    other = repo["root"] / "other.md"
    other.write_text("別の内容\n", encoding="utf-8")
    snapshot = _snapshot(repo)
    proc = _run(repo, from_file=other)
    assert proc.returncode == 2
    assert "--from-file" in proc.stderr
    assert _snapshot(repo) == snapshot


def test_missing_skill_md_exits_2(repo):
    repo["md"].unlink()
    assert _run(repo).returncode == 2


def test_broken_verdict_json_exits_2(repo):
    repo["paths"]["elegance"].write_text("{not json", encoding="utf-8")
    assert _run(repo).returncode == 2


# ---------- 範囲つき再レビュー (--scoped-review) ----------
# 指摘の節の外を変えたときに、全体を読み直さず「変えた節だけを独立 reviewer が読み直した」
# 証拠で結び直す。読んでいない節が変わった・変更が大きい・約束に触れた・重ねすぎたときは
# 全体レビューへ戻す (harness-g67 step 5)。

GOTCHAS_AFTER = BEFORE.replace("- 注意\n", "- 注意 (例外の補足)\n")


@pytest.fixture
def scoped_repo(tmp_path):
    # 変更は Gotchas。指摘の節 (手順) の外なので --finding-ids では結び直せない
    return _make_repo(tmp_path, BEFORE, GOTCHAS_AFTER)


def _scoped_review(repo, name="scoped.json", **override) -> Path:
    review = {
        "kind": "scoped-content-review",
        "plugin": PLUGIN_NAME,
        "skill": SKILL_NAME,
        "from_sha": repo["before"],
        "to_sha": _sha(repo["md"].read_text(encoding="utf-8")),
        "sections": ["Gotchas"],
        "verdicts": {"elegance": "PASS", "rubric": "PASS"},
        "negative_feedback": [],
        "reviewer": "assign-skill-design-evaluator",
        "reviewed_at": "2026-11-14T00:00:00Z",
    }
    review.update(override)
    path = repo["root"] / name
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _expect_scoped_reject(repo, message, review=None, **kwargs):
    review = review if review is not None else _scoped_review(repo)
    _expect_reject(repo, message, ids=None, scoped=review, **kwargs)
    assert not (repo["paths"]["elegance"].parent / "scoped-reviews").exists()


def test_scoped_review_rebinds_a_change_outside_the_findings(scoped_repo, monkeypatch):
    repo = scoped_repo
    _expect_reject(repo, "の外です", ids="elegance:1")  # 指摘の id では通らない変更
    review = _scoped_review(repo)
    proc = _run(repo, ids=None, scoped=review)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "rebound"

    stored = repo["paths"]["elegance"].parent / "scoped-reviews" / f"{repo['after']}.json"
    assert stored.read_bytes() == review.read_bytes()  # 写しはレビューの bytes そのまま
    for path in repo["paths"].values():
        data = _load(path)
        assert data["target"]["skill_md_sha256"] == repo["after"]
        assert data["target"]["reviewed_skill_md_sha256"] == repo["before"]
        (entry,) = data["sha_rebinds"]
        assert "finding_ids" not in entry and "replay" not in entry
        assert entry["scoped_review"] == {
            "sections": ["Gotchas"],
            "reviewer": "assign-skill-design-evaluator",
            "reviewed_at": "2026-11-14T00:00:00Z",
            "review_ref": f"scoped-reviews/{repo['after']}.json",
            "review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
        }
        Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(data)
    _assert_lint_passes(repo, monkeypatch)


def test_scoped_review_that_did_not_read_the_changed_section_is_rejected(scoped_repo, monkeypatch):
    """肝: 変えた節を読んでいないレビューでは結び直さず、lint は stale-sha のまま。"""
    repo = scoped_repo
    _expect_scoped_reject(repo, "範囲つき再レビューが読んだ節", _scoped_review(repo, sections=["手順"]))
    lint = _load_lint(repo, monkeypatch)
    review_dir = repo["paths"]["elegance"].parent
    assert lint._check_verdict(review_dir / "elegance-verdict.json", PLUGIN_NAME, SKILL_NAME, "elegance-verdict.json").startswith("stale-sha:")


@pytest.mark.parametrize("override, message", [
    ({"negative_feedback": ["[low] まだ直っていない"]}, "件の指摘"),
    ({"verdicts": {"elegance": "PASS", "rubric": "FAIL"}}, "verdicts="),
    ({"kind": "content-review"}, "kind="),
    ({"plugin": "p2"}, "plugin="),
    ({"to_sha": "0" * 64}, "to_sha="),
    ({"reviewer": "elegant-improvement-executor"}, "reviewer="),
    ({"reviewer": " root "}, "reviewer="),
    ({"reviewer": ""}, "reviewer="),
    ({"reviewed_at": "2026-11-14"}, "reviewed_at"),
    ({"sections": []}, "sections"),
    ({"sections": ["Gotchas", "Gotchas"]}, "sections"),
    ({"sections": ["無い節"]}, "無い節"),
])
def test_scoped_review_that_does_not_vouch_for_this_change_is_rejected(scoped_repo, override, message):
    _expect_scoped_reject(scoped_repo, message, _scoped_review(scoped_repo, **override))


def _four_section_skill(body: str) -> str:
    return FRONT + "# run-x\n\n" + "".join(f"## 節{i}\n\n{body}{i}\n\n" for i in range(1, 5))


def test_scoped_review_of_more_than_three_sections_is_rejected(tmp_path):
    repo = _make_repo(tmp_path, _four_section_skill("旧"), _four_section_skill("新"))
    review = _scoped_review(repo, sections=["節1", "節2", "節3", "節4"])
    _expect_scoped_reject(repo, "上限 3", review)


def test_scoped_review_of_many_changed_subsections_is_rejected(tmp_path):
    def skill(body):
        return FRONT + "# run-x\n\n## 手順\n\n" + "".join(f"### 段{i}\n\n{body}\n\n" for i in range(1, 5))
    repo = _make_repo(tmp_path, skill("旧"), skill("新"))
    _expect_scoped_reject(repo, "変わった節が 4 個", _scoped_review(repo, sections=["手順"]))


def test_scoped_review_of_more_than_sixty_changed_lines_is_rejected(tmp_path):
    after = BEFORE.replace("- 注意\n", "- 注意\n" + "".join(f"- 追記 {i}\n" for i in range(61)))
    repo = _make_repo(tmp_path, BEFORE, after)
    _expect_scoped_reject(repo, "変わった行が 61 行")


def test_scoped_review_cannot_change_the_output_contract(tmp_path):
    def skill(item):
        return FRONT + f"# run-x\n\n## Purpose & Output Contract\n\n約束\n\n### 出力\n\n- {item}\n\n## 手順\n\n本文\n"
    repo = _make_repo(tmp_path, skill("report.md"), skill("report.md と summary.md"))
    review = _scoped_review(repo, sections=["Purpose & Output Contract > 出力"])
    _expect_scoped_reject(repo, "成果物の約束", review)


def test_scoped_review_cannot_change_a_section_the_criteria_name(tmp_path):
    front = "---\nname: run-x\nkind: run\nfeedback_contract:\n  criteria:\n    - id: IN1\n      text: Gotchas に落とし穴を 1 つ以上書く\n---\n"
    before = BEFORE.replace(FRONT, front)
    repo = _make_repo(tmp_path, before, before.replace("- 注意\n", "- 注意 (例外の補足)\n"))
    _expect_scoped_reject(repo, "criteria が名指す")


@pytest.mark.parametrize("after", [
    BEFORE.replace("## Gotchas", "## 落とし穴"),
    BEFORE.replace("kind: run", "kind: run\nversion: 2"),
])
def test_scoped_review_cannot_cover_heading_or_frontmatter_changes(tmp_path, after):
    repo = _make_repo(tmp_path, BEFORE, after)
    _expect_scoped_reject(repo, "変わって" if "version" in after else "見出し")


def test_scoped_reviews_are_capped_per_full_review(scoped_repo, monkeypatch):
    repo = scoped_repo
    from_sha = repo["before"]
    for round_ in (1, 2):
        copy = repo["from_file"]
        if round_ == 2:
            copy = _save_copy(repo, "before-2.md")
            repo["md"].write_text(GOTCHAS_AFTER.replace("例外の補足", "例外の補足 2"), encoding="utf-8")
        review = _scoped_review(repo, name=f"scoped-{round_}.json", from_sha=from_sha)
        proc = _run(repo, ids=None, scoped=review, from_sha=from_sha, from_file=copy)
        assert proc.returncode == 0, proc.stderr
        from_sha = _sha(repo["md"].read_text(encoding="utf-8"))
    _assert_lint_passes(repo, monkeypatch)
    copy = _save_copy(repo, "before-3.md")
    repo["md"].write_text(GOTCHAS_AFTER.replace("例外の補足", "例外の補足 3"), encoding="utf-8")
    review = _scoped_review(repo, name="scoped-3.json", from_sha=from_sha)
    snapshot = _snapshot(repo)
    proc = _run(repo, ids=None, scoped=review, from_sha=from_sha, from_file=copy)
    assert proc.returncode == 1 and "すでに 2 回" in proc.stderr
    assert _snapshot(repo) == snapshot
    assert len(list((repo["paths"]["elegance"].parent / "scoped-reviews").iterdir())) == 2


def test_legacy_verdict_without_its_full_review_sha_cannot_take_a_scoped_review(scoped_repo):
    def legacy(kind, data):
        data["sha_rebinds"] = [{
            "from_sha": _sha("もっと前\n"), "to_sha": scoped_repo["before"],
            "finding_ids": ["elegance:2"], "rebound_at": "2026-11-13T00:00:00Z", "tool": "sync-content-review-sha",
        }]
    _edit_verdicts(scoped_repo, legacy)
    _expect_scoped_reject(scoped_repo, "古い verdict")


def test_scoped_review_and_finding_ids_are_mutually_exclusive(scoped_repo):
    snapshot = _snapshot(scoped_repo)
    proc = _run(scoped_repo, ids="elegance:1", scoped=_scoped_review(scoped_repo))
    assert proc.returncode == 2
    assert _snapshot(scoped_repo) == snapshot


@pytest.mark.parametrize("content", ["{not json", "[]"])
def test_unreadable_scoped_review_exits_2(scoped_repo, content):
    review = scoped_repo["root"] / "broken.json"
    review.write_text(content, encoding="utf-8")
    assert _run(scoped_repo, ids=None, scoped=review).returncode == 2


# lint 側: sync を通さず手で書いた scoped_review の記録は、写しと照合して落ちる

def _rebind_scoped(repo):
    assert _run(repo, ids=None, scoped=_scoped_review(repo)).returncode == 0
    review_dir = repo["paths"]["elegance"].parent
    return review_dir, review_dir / "scoped-reviews" / f"{repo['after']}.json"


def test_lint_rejects_a_scoped_record_whose_copy_is_missing(scoped_repo, monkeypatch):
    review_dir, stored = _rebind_scoped(scoped_repo)
    stored.unlink()
    assert "missing" in _load_lint(scoped_repo, monkeypatch)._check_pair(review_dir)


def test_lint_rejects_a_scoped_record_whose_copy_was_edited(scoped_repo, monkeypatch):
    review_dir, stored = _rebind_scoped(scoped_repo)
    stored.write_text(stored.read_text(encoding="utf-8").replace("Gotchas", "手順"), encoding="utf-8")
    assert "sha256" in _load_lint(scoped_repo, monkeypatch)._check_pair(review_dir)


def test_lint_rejects_a_scoped_record_that_disagrees_with_its_copy(scoped_repo, monkeypatch):
    review_dir, stored = _rebind_scoped(scoped_repo)
    review = _load(stored)
    review["negative_feedback"] = ["[low] 指摘を消して PASS にした"]
    _dump(stored, review)
    digest = hashlib.sha256(stored.read_bytes()).hexdigest()
    _edit_verdicts(scoped_repo, lambda kind, data: data["sha_rebinds"][0]["scoped_review"].update(review_sha256=digest))
    assert "negative_feedback" in _load_lint(scoped_repo, monkeypatch)._check_pair(review_dir)


@pytest.mark.parametrize("change, message", [
    (lambda scoped: scoped.update(reviewer="self"), "independent"),
    (lambda scoped: scoped.update(sections=["a", "b", "c", "d"]), "sections"),
    (lambda scoped: scoped.update(review_ref="../elsewhere.json"), "review_ref"),
    (lambda scoped: scoped.pop("review_sha256"), "exactly"),
])
def test_lint_rejects_a_malformed_scoped_record(scoped_repo, monkeypatch, change, message):
    review_dir, _ = _rebind_scoped(scoped_repo)
    _edit_verdicts(scoped_repo, lambda kind, data: change(data["sha_rebinds"][0]["scoped_review"]))
    lint = _load_lint(scoped_repo, monkeypatch)
    error = lint._check_verdict(review_dir / "elegance-verdict.json", PLUGIN_NAME, SKILL_NAME, "elegance-verdict.json")
    assert error and message in error


def test_lint_caps_scoped_records_in_one_chain(scoped_repo, monkeypatch):
    review_dir, _ = _rebind_scoped(scoped_repo)
    middle = [_sha("中間 1\n"), _sha("中間 2\n")]

    def three_scoped(kind, data):
        (entry,) = data["sha_rebinds"]
        hops = [scoped_repo["before"], *middle, scoped_repo["after"]]
        data["sha_rebinds"] = [
            {**entry, "from_sha": a, "to_sha": b, "scoped_review": {**entry["scoped_review"], "review_ref": f"scoped-reviews/{b}.json"}}
            for a, b in zip(hops, hops[1:])
        ]
    _edit_verdicts(scoped_repo, three_scoped)
    lint = _load_lint(scoped_repo, monkeypatch)
    error = lint._check_verdict(review_dir / "elegance-verdict.json", PLUGIN_NAME, SKILL_NAME, "elegance-verdict.json")
    assert error and "3 scoped re-reviews" in error


def test_schema_rejects_a_record_with_two_kinds_of_evidence(scoped_repo):
    review_dir, _ = _rebind_scoped(scoped_repo)
    data = _load(scoped_repo["paths"]["elegance"])
    data["sha_rebinds"][0]["finding_ids"] = ["elegance:1"]
    validator = Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert list(validator.iter_errors(data))
    data["sha_rebinds"][0].pop("finding_ids")
    data["sha_rebinds"][0]["scoped_review"]["reviewer"] = "self"
    assert list(validator.iter_errors(data))


def test_scoped_review_limits_agree_between_sync_lint_and_schema():
    ssot = _load_module(SSOT, "fc_ssot_for_scoped_test")
    plugin_ssot = _load_module(PLUGIN / "scripts" / "feedback_contract_ssot.py", "fc_plugin_ssot_for_scoped_test")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    scoped = schema["properties"]["sha_rebinds"]["items"]["properties"]["scoped_review"]["properties"]
    for name in ("SCOPED_REVIEW_KIND", "SCOPED_REVIEW_DIR", "SCOPED_REVIEW_MAX_SECTIONS", "SCOPED_REVIEW_MAX_CHANGED_LINES",
                 "SCOPED_REVIEW_MAX_PER_FULL_REVIEW", "SCOPED_REVIEW_CONTRACT_SECTIONS", "SCOPED_REVIEW_NON_INDEPENDENT"):
        assert getattr(ssot, name) == getattr(plugin_ssot, name), name
    assert scoped["sections"]["maxItems"] == ssot.SCOPED_REVIEW_MAX_SECTIONS
    assert set(scoped["reviewer"]["not"]["enum"]) == set(ssot.SCOPED_REVIEW_NON_INDEPENDENT)
    assert scoped["review_ref"]["pattern"].startswith(f"^{ssot.SCOPED_REVIEW_DIR}/")


# ---------- 経路のあいだの食い違い (指摘の id と範囲つき再レビューで、通す変更の境目を同じにする) ----------

def _locate(repo, sections: list[str]) -> None:
    """elegance:1 の finding_locations を sections にする。"""
    path = repo["paths"]["elegance"]
    data = _load(path)
    data["finding_locations"]["elegance:1"] = {"sections": sections}
    _dump(path, data)


def _output_contract_skill(item: str) -> str:
    return FRONT + f"# run-x\n\n## Purpose & Output Contract\n\n約束\n\n### 出力\n\n- {item}\n\n## 手順\n\n本文\n"


def test_finding_id_cannot_change_the_output_contract(tmp_path):
    repo = _make_repo(tmp_path, _output_contract_skill("report.md"), _output_contract_skill("report.md と summary.md"))
    _locate(repo, ["Purpose & Output Contract"])
    _expect_reject(repo, "成果物の約束")


def test_finding_id_change_is_capped_like_a_scoped_review(tmp_path):
    def skill(body):
        return FRONT + "# run-x\n\n## 手順\n\n" + "".join(f"### 段{i}\n\n{body}\n\n" for i in range(1, 5))
    repo = _make_repo(tmp_path, skill("旧"), skill("新"))
    _locate(repo, ["手順"])
    _expect_reject(repo, "変わった節が 4 個")

    lines = _make_repo(tmp_path / "lines", BEFORE, BEFORE.replace("本文 (修正前)\n", "".join(f"- 行 {i}\n" for i in range(61))))
    _expect_reject(lines, "変わった行が 61 行")


@pytest.mark.parametrize("mode", ["finding-ids", "scoped"])
def test_change_under_a_section_the_criteria_name_is_rejected(tmp_path, mode):
    """criteria が親の節を名指すとき、子の節だけを変えても止める。"""
    front = "---\nname: run-x\nkind: run\nfeedback_contract:\n  criteria:\n    - id: IN1\n      text: 手順 を守る\n---\n"
    def skill(body):
        return front + f"# run-x\n\n概要\n\n## 手順\n\n### 段1\n\n{body}\n\n## Gotchas\n\n- 注意\n"
    repo = _make_repo(tmp_path, skill("旧"), skill("新"))
    if mode == "finding-ids":
        _locate(repo, ["手順 > 段1"])
        _expect_reject(repo, "criteria が名指す節 (手順)")
    else:
        _expect_scoped_reject(repo, "criteria が名指す節 (手順)", _scoped_review(repo, sections=["手順 > 段1"]))


def test_document_title_in_criteria_does_not_block_every_change(tmp_path):
    front = "---\nname: run-x\nkind: run\nfeedback_contract:\n  criteria:\n    - id: IN1\n      text: run-x の出力を表にする\n---\n"
    repo = _make_repo(tmp_path, BEFORE.replace(FRONT, front), AFTER.replace(FRONT, front))
    proc = _run(repo)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("section", ["Purpose & Output Contract", "Purpose & Output Contract > 出力", "入出力契約"])
def test_scoped_sections_naming_the_contract_are_rejected_like_the_lint(tmp_path, monkeypatch, section):
    """変更が契約の外でも、契約の節を名指す記録は lint が通さない。書く側も同じ規則で書く前に止める。"""
    def skill(note):
        return FRONT + f"# run-x\n\n## Purpose & Output Contract\n\n約束\n\n### 出力\n\n- report.md\n\n## 入出力契約\n\n入出力\n\n## 手順\n\n{note}\n"
    repo = _make_repo(tmp_path, skill("本文"), skill("本文 (直した)"))
    review = _scoped_review(repo, sections=["手順", section])
    _expect_scoped_reject(repo, "を名指しています", review)
    lint = _load_lint(repo, monkeypatch)
    entry = {"sections": ["手順", section], "reviewer": "assign-skill-design-evaluator",
             "reviewed_at": "2026-11-14T00:00:00Z", "review_ref": "scoped-reviews/" + "a" * 64 + ".json",
             "review_sha256": "b" * 64}
    assert "inside the output contract" in lint._check_scoped_entry(entry)


def test_mismatched_pair_is_not_extended(repo):
    data = _load(repo["paths"]["rubric"])
    data["target"]["reviewed_skill_md_sha256"] = "c" * 64
    _dump(repo["paths"]["rubric"], data)
    _expect_reject(repo, "pair が壊れている")


@pytest.mark.parametrize("breakage", [
    lambda d: d.update(target=["p1", "run-x"]),
    lambda d: d.update(target="p1/run-x"),
    lambda d: d.update(sha_rebinds={"0": {}}),
    lambda d: d.update(sha_rebinds=3),
    lambda d: d.update(sha_rebinds=[{"to_sha": d["target"]["skill_md_sha256"], "finding_ids": ["elegance:2"]}]),
])
def test_malformed_verdict_is_an_input_error_not_a_traceback(repo, breakage):
    for path in repo["paths"].values():
        data = _load(path)
        breakage(data)
        _dump(path, data)
    snapshot = _snapshot(repo)
    proc = _run(repo)
    assert proc.returncode == 2, proc.stderr
    assert "Traceback" not in proc.stderr
    assert _snapshot(repo) == snapshot


@pytest.mark.parametrize("replay", [None, "artifact-delivery-v1"])
def test_non_utf8_reviewed_copy_is_an_input_error(repo, replay):
    bad = b"---\nname: run-x\n---\n# run-x\n\n\xff\xfe\n"
    repo["from_file"].write_bytes(bad)
    sha = hashlib.sha256(bad).hexdigest()
    for path in repo["paths"].values():
        data = _load(path)
        data["target"]["skill_md_sha256"] = sha
        _dump(path, data)
    proc = _run(repo, from_sha=sha, ids=None if replay else "elegance:1", replay=replay)
    assert proc.returncode == 2, proc.stderr
    assert "UTF-8" in proc.stderr and "Traceback" not in proc.stderr


# ---------- 配線 ----------

def test_executor_and_protocol_point_to_the_script():
    agent = AGENT.read_text(encoding="utf-8")
    protocol = PROTOCOL.read_text(encoding="utf-8")
    for text in (agent, protocol):
        assert "sync-content-review-sha.py" in text
        assert "--finding-ids" in text
        assert "--from-file" in text
        assert "finding_locations" in text
    assert "要再レビュー" in agent
    assert "--replay" in protocol
    assert "--print-target" in protocol
