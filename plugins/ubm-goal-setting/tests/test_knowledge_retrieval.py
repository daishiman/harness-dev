"""実ファイルで検索順位・不正入力停止・採用と反応の観測を検証する。"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

PLUGIN = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), PLUGIN / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S = load("search-knowledge")
U = load("record-knowledge-usage")


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def corpus(tmp_path):
    root = (tmp_path / "kb").resolve()
    root.mkdir()
    write(root / "router.json", {"categories": {"principles": {"files": ["principles-test.json"]}, "consultation": {"files": ["consultation-test.json"]}}})
    write(root / "principles-test.json", {"entries": [
        {"id": "PR-002", "tags": ["組織"], "content": "原文B", "source": {"file": "b.md"}},
        {"id": "PR-001", "tags": ["組織"], "content": "原文A", "source": {"file": "a.md"}},
        {"id": "PR-003", "content": "組織" * 100, "source": {"file": "c.md"}},
    ]})
    write(root / "consultation-test.json", {"entries": [
        {"id": "CP-001", "problem": "資金が足りない", "advice": "開催前に成立させる", "source": {"file": "legacy.md", "line": 42}},
    ]})
    # 未列挙の履歴やファイルを意味検索へ混ぜてはいけない。
    write(root / "unlisted.json", {"entries": [{"id": "PR-999", "tags": ["組織"]}]})
    write(root / "registry.json", {"content": "組織"})
    return root


def test_weighted_fields_beat_frequency_and_ties_are_stable(corpus):
    result = S.search(corpus, ["組織"])
    assert result["matched_ids"] == ["PR-001", "PR-002", "PR-003"]
    assert [m["score"] for m in result["matches"]] == [8, 8, 3]
    assert result["entries_scanned"] == 4 and result["total_hits"] == 3
    assert result == S.search(corpus, ["組織"])
    path = corpus / "principles-test.json"
    obj = json.loads(path.read_text())
    obj["entries"].reverse()
    write(path, obj)
    assert S.search(corpus, ["組織"])["matched_ids"] == result["matched_ids"]


def test_legacy_problem_advice_and_source_remain_intact(corpus):
    result = S.search(corpus, ["資金", "成立"], ["consultation"])
    hit = result["matches"][0]
    assert result["matched_ids"] == ["CP-001"] and hit["score"] == 9
    assert hit["entry"]["problem"] == "資金が足りない"
    assert hit["entry"]["advice"] == "開催前に成立させる"
    assert hit["source"] == {"file": "legacy.md", "line": 42}
    assert hit["source_ref"].endswith("consultation-test.json#entries[id=CP-001]")
    assert len(hit["file_sha256"]) == 64


def test_nfkc_dedup_exact_id_and_zero_hit(corpus):
    normalized = S.search(corpus, ["ＰＲ－００１", "pr-001"])
    assert normalized["matched_ids"] == ["PR-001"] and normalized["matches"][0]["score"] == 20
    result = S.search(corpus, ["存在しない言葉"])
    assert result["zero_hit"] is True and result["matched_ids"] == [] and result["matches"] == []
    assert result["total_hits"] == 0


@pytest.mark.parametrize("terms,limit,categories", [([], 20, None), ([""], 20, None), (["x" * 121], 20, None), (["x"] * 13, 20, None), (["x"], 0, None), (["x"], 51, None), (["x"], True, None), (["x"], 20, ["unknown"])])
def test_query_bounds_fail_closed(corpus, terms, limit, categories):
    with pytest.raises(ValueError):
        S.search(corpus, terms, categories, limit)


@pytest.mark.parametrize("bad", ["../escape.json", "registry.json", "principles-missing.json"])
def test_router_bad_paths_or_bookkeeping_are_not_searchable(corpus, bad):
    write(corpus / "router.json", {"categories": {"principles": {"files": [bad]}}})
    with pytest.raises((ValueError, OSError)):
        S.search(corpus, ["組織"])


def test_duplicate_ids_and_symlink_stop_search(corpus, tmp_path):
    file = corpus / "principles-test.json"
    data = json.loads(file.read_text())
    data["entries"].append(data["entries"][0])
    write(file, data)
    with pytest.raises(ValueError, match="duplicated"):
        S.search(corpus, ["組織"])
    file.unlink()
    external = tmp_path / "external.json"
    write(external, {"entries": []})
    file.symlink_to(external)
    with pytest.raises(ValueError, match="symlink"):
        S.search(corpus, ["組織"])


def test_size_entry_and_field_shape_bounds(corpus, monkeypatch):
    monkeypatch.setattr(S, "MAX_ENTRIES", 2)
    with pytest.raises(ValueError, match="entry count"):
        S.search(corpus, ["組織"])
    monkeypatch.setattr(S, "MAX_ENTRIES", 10000)
    monkeypatch.setattr(S, "MAX_FILE_BYTES", 10)
    with pytest.raises(ValueError, match="size"):
        S.search(corpus, ["組織"])
    monkeypatch.setattr(S, "MAX_FILE_BYTES", 4 * 1024 * 1024)
    data = json.loads((corpus / "principles-test.json").read_text())
    data["entries"][0]["tags"] = [True]
    write(corpus / "principles-test.json", data)
    with pytest.raises(ValueError, match="boolean/number"):
        S.search(corpus, ["組織"])


def test_cli_invalid_corpus_returns_2_without_stdout_or_traceback(corpus):
    (corpus / "principles-test.json").write_text("broken")
    result = subprocess.run([sys.executable, str(PLUGIN / "scripts/search-knowledge.py"), "--knowledge-dir", str(corpus), "--term", "組織"], text=True, capture_output=True)
    assert result.returncode == 2 and not result.stdout and "Traceback" not in result.stderr
    assert "error" in json.loads(result.stderr)


def observation(used=None):
    return {"usage_id": "session.phase.search1", "used_ids": used if used is not None else ["PR-001"], "satisfaction": None}


def test_actual_jsonl_records_matched_used_unused_and_unknown_feedback(corpus, tmp_path):
    before = {p.name: p.read_bytes() for p in corpus.iterdir()}
    candidate = S.search(corpus, ["組織"])
    result = U.record_usage(tmp_path, "run-ubm-goal-setting", candidate, observation())
    log = tmp_path / U.LOG_RELATIVE
    row = json.loads(log.read_text())
    assert result["status"] == "recorded" and result["path"] == str(log)
    assert row["matched_ids"] == ["PR-001", "PR-002", "PR-003"]
    assert row["used_ids"] == ["PR-001"] and row["unused_ids"] == ["PR-002", "PR-003"]
    assert row["satisfaction"] is None and len(row["search_result_sha256"]) == 64
    assert {p.name: p.read_bytes() for p in corpus.iterdir()} == before
    assert "組織" not in log.read_text() and "原文" not in log.read_text()


def test_usage_subset_missing_satisfaction_and_list_bounds_rejected(corpus, tmp_path):
    candidate = S.search(corpus, ["組織"])
    for usage in (observation(["PR-999"]), {"usage_id": "x", "used_ids": []}, observation(["PR-001"] * 2), observation([str(n) for n in range(51)])):
        with pytest.raises(ValueError):
            U.record_usage(tmp_path, "run-ubm-goal-setting", candidate, usage)
    assert not (tmp_path / "eval-log").exists()


def test_feedback_requires_unique_actual_user_turn(corpus, tmp_path):
    candidate = S.search(corpus, ["組織"])
    usage = {**observation(), "satisfaction": "positive", "satisfaction_source_turn_id": "turn-2"}
    actual = {"id": "turn-2", "role": "user", "content": "この見方で整理できました"}
    for transcript in (None, [{**actual, "role": "assistant"}], [{**actual, "content": ""}], [actual, actual]):
        with pytest.raises(ValueError):
            U.record_usage(tmp_path, "run-ubm-consult", candidate, usage, transcript)
    receipt = U.record_usage(tmp_path, "run-ubm-consult", candidate, usage, [actual])
    assert receipt["row"]["satisfaction"] == "positive"
    assert receipt["row"]["satisfaction_source_turn_id"] == "turn-2"
    assert actual["content"] not in (tmp_path / U.LOG_RELATIVE).read_text()


def test_consult_ephemeral_and_zero_hit_do_not_create_files(corpus, tmp_path):
    candidate = S.search(corpus, ["未一致"])
    result = U.record_usage(tmp_path, "run-ubm-consult", candidate, observation([]), ephemeral=True)
    assert result["status"] == "ephemeral" and result["path"] is None
    assert result["row"]["matched_ids"] == result["row"]["used_ids"] == []
    assert not (tmp_path / "eval-log").exists()


def test_official_knowledge_and_symlink_log_cannot_receive_usage(corpus, tmp_path, monkeypatch):
    candidate = S.search(corpus, ["組織"])
    monkeypatch.setattr(U, "OFFICIAL_KNOWLEDGE", corpus)
    with pytest.raises(ValueError, match="official knowledge"):
        U.record_usage(corpus, "run-ubm-goal-setting", candidate, observation())
    assert not (corpus / "eval-log").exists()
    external = tmp_path / "external"
    external.mkdir()
    (tmp_path / "eval-log").symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        U.record_usage(tmp_path, "run-ubm-goal-setting", candidate, observation())
    assert list(external.iterdir()) == []


def test_usage_id_retry_is_idempotent_and_conflict_does_not_append(corpus, tmp_path):
    candidate = S.search(corpus, ["組織"])
    U.record_usage(tmp_path, "run-ubm-goal-setting", candidate, observation())
    log = tmp_path / U.LOG_RELATIVE
    before = log.read_bytes()
    assert U.record_usage(tmp_path, "run-ubm-goal-setting", candidate, observation())["status"] == "already_recorded"
    with pytest.raises(ValueError, match="different observation"):
        U.record_usage(tmp_path, "run-ubm-goal-setting", candidate, observation([]))
    assert log.read_bytes() == before


@pytest.mark.parametrize("broken", ["{broken}\n", "{}", "{}\n", "[]\n"])
def test_incomplete_or_corrupt_log_is_not_extended(corpus, tmp_path, broken):
    log = tmp_path / U.LOG_RELATIVE
    log.parent.mkdir(parents=True)
    log.write_text(broken)
    before = log.read_bytes()
    with pytest.raises(ValueError):
        U.record_usage(tmp_path, "run-ubm-goal-setting", S.search(corpus, ["組織"]), observation())
    assert log.read_bytes() == before


def test_usage_cli_rejects_foreign_used_id_without_mutation(corpus, tmp_path):
    candidate = tmp_path / "candidate.json"
    usage = tmp_path / "usage.json"
    write(candidate, S.search(corpus, ["組織"]))
    write(usage, observation(["PR-999"]))
    result = subprocess.run([sys.executable, str(PLUGIN / "scripts/record-knowledge-usage.py"), "--project-root", str(tmp_path), "--entrypoint", "run-ubm-goal-setting", "--search-result", str(candidate), "--usage", str(usage)], text=True, capture_output=True)
    assert result.returncode == 2 and "subset" in json.loads(result.stderr)["error"]
    assert not (tmp_path / "eval-log").exists()


def test_actual_search_stdout_consumed_by_usage_cli_and_jsonl(corpus, tmp_path):
    query = [sys.executable, str(PLUGIN / "scripts/search-knowledge.py"), "--knowledge-dir", str(corpus), "--term", "組織", "--limit", "2"]
    searched = subprocess.run(query, text=True, capture_output=True, check=True)
    candidate = tmp_path / "observed-search.json"
    candidate.write_text(searched.stdout)
    usage = tmp_path / "actual-use.json"
    write(usage, observation(["PR-002"]))
    recorded = subprocess.run([sys.executable, str(PLUGIN / "scripts/record-knowledge-usage.py"), "--project-root", str(tmp_path), "--entrypoint", "run-ubm-journal", "--search-result", str(candidate), "--usage", str(usage)], text=True, capture_output=True, check=True)
    receipt = json.loads(recorded.stdout)
    rows = [json.loads(row) for row in (tmp_path / U.LOG_RELATIVE).read_text().splitlines()]
    assert len(rows) == 1 and receipt["status"] == "recorded"
    assert rows[0]["search_id"] == json.loads(searched.stdout)["search_id"]
    assert rows[0]["matched_ids"] == ["PR-001", "PR-002"]
    assert rows[0]["used_ids"] == ["PR-002"] and rows[0]["unused_ids"] == ["PR-001"]
    assert rows[0]["satisfaction"] is None


def test_bundled_router_real_domain_entries_are_searchable_without_writes():
    root = PLUGIN / "knowledge"
    before = (root / "router.json").read_bytes()
    result = S.search(root, ["組織"], limit=3)
    assert result["entries_scanned"] > 900 and len(result["matched_ids"]) == 3
    assert all(hit["source"] and hit["entry"]["id"] == hit["id"] for hit in result["matches"])
    assert (root / "router.json").read_bytes() == before
