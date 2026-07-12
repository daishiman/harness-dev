"""record_usage.py の純関数 + CLI 契約を network 無しで網羅する。

record_usage は §12 活用ログ (usage-log.jsonl) の記録と品質改善パターン検出を行う
ローカル決定論スクリプト (network: false)。よって全関数を実ファイル/実 JSONL で
genuine に検証できる:

  - find_log_file: 親ディレクトリ探索 + 不在時のカレント配下フォールバック
  - record_entry: JSONL 追記 + note 有無
  - load_log: 不在 / 空行 / 壊れた行スキップ
  - analyze_patterns: サンプル不足 + パターン 4 種 (hit_not_used / low_hit_rate /
    consecutive_unhelpful / entry_concentration) を実入力で発火
  - extract_brushup_queue / write_brushup_queue: ステージング行の抽出と JSONL 追記
  - mark_needs_update: status のみ付与・本文不変・冪等・壊れたカテゴリファイルのスキップ
  - resolve_index_path: --dir 指定 / knowledge サブディレクトリ / 自動探索 / 不在 None
  - self_test: 内蔵 8 テスト
  - main: --record / --analyze / --emit-queue / --mark-needs-update / 引数エラー経路

すべて tmp_path / monkeypatch.chdir で repo を汚さない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
          / "templates" / "knowledge-skeleton" / "scripts" / "record_usage.py")

_SPEC = importlib.util.spec_from_file_location("record_usage_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# find_log_file
# --------------------------------------------------------------------------

def test_find_log_file_finds_in_parent(tmp_path):
    (tmp_path / "usage-log.jsonl").write_text("", encoding="utf-8")
    child = tmp_path / "a" / "b"
    child.mkdir(parents=True)
    found = MOD.find_log_file(child, "usage-log.jsonl")
    assert found == tmp_path / "usage-log.jsonl"


def test_find_log_file_falls_back_to_start_dir(tmp_path):
    # どこにも無ければ start_dir 配下のパスを (作らずに) 返す。
    found = MOD.find_log_file(tmp_path, "usage-log.jsonl")
    assert found == tmp_path / "usage-log.jsonl"
    assert not found.exists()


# --------------------------------------------------------------------------
# record_entry
# --------------------------------------------------------------------------

def test_record_entry_appends_with_note(tmp_path):
    log = tmp_path / "usage-log.jsonl"
    entry = MOD.record_entry(log, "クエリ", ["id_1", "id_2"], ["id_1"], "helpful", "メモ")
    assert entry["query"] == "クエリ"
    assert entry["note"] == "メモ"
    assert "timestamp" in entry
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["matched_ids"] == ["id_1", "id_2"]


def test_record_entry_without_note_omits_field(tmp_path):
    log = tmp_path / "usage-log.jsonl"
    entry = MOD.record_entry(log, "q", [], [], "neutral", None)
    assert "note" not in entry


def test_record_entry_appends_multiple(tmp_path):
    log = tmp_path / "usage-log.jsonl"
    MOD.record_entry(log, "q1", ["a"], ["a"], "helpful", None)
    MOD.record_entry(log, "q2", ["b"], [], "neutral", None)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2


# --------------------------------------------------------------------------
# load_log
# --------------------------------------------------------------------------

def test_load_log_missing_returns_empty(tmp_path):
    assert MOD.load_log(tmp_path / "absent.jsonl") == []


def test_load_log_skips_blank_and_corrupt_lines(tmp_path):
    log = tmp_path / "usage-log.jsonl"
    log.write_text(
        json.dumps({"query": "ok1"}) + "\n"
        + "\n"  # 空行
        + "{ broken json\n"  # 壊れた行 → スキップ
        + "   \n"  # 空白のみ
        + json.dumps({"query": "ok2"}) + "\n",
        encoding="utf-8",
    )
    entries = MOD.load_log(log)
    assert [e["query"] for e in entries] == ["ok1", "ok2"]


# --------------------------------------------------------------------------
# analyze_patterns: サンプル不足 + 4 パターン
# --------------------------------------------------------------------------

def test_analyze_insufficient_samples():
    res = MOD.analyze_patterns([{"query": "q"}])
    assert res["findings"] == []
    assert "サンプル不足" in res["note"]
    assert res["analyzed_entries"] == 1


def _entry(q, matched, used, sat):
    return {"timestamp": "2026-01-01T00:00:00+00:00", "query": q,
            "matched_ids": matched, "used_ids": used, "satisfaction": sat}


def test_analyze_hit_not_used_pattern():
    entries = [_entry(f"q{i}", ["always_hit"], [], "neutral") for i in range(5)]
    res = MOD.analyze_patterns(entries)
    hnu = [f for f in res["findings"] if f["pattern"] == "hit_not_used"]
    assert hnu, res["findings"]
    assert hnu[0]["entry_id"] == "always_hit"
    assert hnu[0]["ratio"] == 1.0
    assert hnu[0]["hit_count"] == 5


def test_analyze_low_hit_rate_pattern():
    # 半数以上 used_ids 空 → low_hit_rate。matched は別々の id にして
    # hit_not_used / concentration が同時発火しない構成にする。
    entries = [_entry(f"q{i}", [f"m{i}"], [], "neutral") for i in range(4)]
    res = MOD.analyze_patterns(entries)
    lhr = [f for f in res["findings"] if f["pattern"] == "low_hit_rate"]
    assert lhr, res["findings"]
    assert lhr[0]["empty_used_count"] == 4
    assert lhr[0]["ratio"] == 1.0


def test_analyze_consecutive_unhelpful_pattern():
    entries = [_entry(f"q{i}", [f"m{i}"], [f"m{i}"], "unhelpful") for i in range(4)]
    res = MOD.analyze_patterns(entries)
    cu = [f for f in res["findings"] if f["pattern"] == "consecutive_unhelpful"]
    assert cu, res["findings"]
    assert cu[0]["max_consecutive"] >= 3


def test_analyze_consecutive_resets_on_non_unhelpful():
    # unhelpful が連続 2 で途切れる → consecutive_unhelpful は発火しない。
    entries = [
        _entry("q0", ["m0"], ["m0"], "unhelpful"),
        _entry("q1", ["m1"], ["m1"], "unhelpful"),
        _entry("q2", ["m2"], ["m2"], "helpful"),
        _entry("q3", ["m3"], ["m3"], "unhelpful"),
        _entry("q4", ["m4"], ["m4"], "helpful"),
    ]
    res = MOD.analyze_patterns(entries)
    cu = [f for f in res["findings"] if f["pattern"] == "consecutive_unhelpful"]
    assert not cu, res["findings"]


def test_analyze_entry_concentration_pattern():
    # 単一 id が全クエリにヒットし used されている (used されるので hit_not_used は不発)。
    entries = [_entry(f"q{i}", ["dominant"], ["dominant"], "helpful") for i in range(5)]
    res = MOD.analyze_patterns(entries)
    ec = [f for f in res["findings"] if f["pattern"] == "entry_concentration"]
    assert ec, res["findings"]
    assert ec[0]["entry_id"] == "dominant"
    assert ec[0]["ratio"] == 1.0


def test_analyze_summary_counts_satisfaction():
    entries = [
        _entry("q0", ["a"], ["a"], "helpful"),
        _entry("q1", ["b"], ["b"], "neutral"),
        _entry("q2", ["c"], ["c"], "unhelpful"),
    ]
    res = MOD.analyze_patterns(entries)
    sc = res["summary"]["satisfaction_counts"]
    assert sc == {"helpful": 1, "neutral": 1, "unhelpful": 1}
    assert res["summary"]["unique_matched_ids"] == 3


# --------------------------------------------------------------------------
# extract_brushup_queue / write_brushup_queue
# --------------------------------------------------------------------------

def test_extract_brushup_queue_maps_findings():
    analysis = {"findings": [
        {"pattern": "hit_not_used", "entry_id": "e1", "severity": "warn", "action": "fix"},
        {"pattern": "low_hit_rate", "action": "add keywords"},  # entry_id 無し
    ]}
    queue = MOD.extract_brushup_queue(analysis)
    assert len(queue) == 2
    assert queue[0]["entry_id"] == "e1"
    assert queue[1]["entry_id"] is None  # entry 単位でない finding は null
    assert all("detected_at" in q and "pattern" in q for q in queue)


def test_extract_brushup_queue_empty():
    assert MOD.extract_brushup_queue({"findings": []}) == []
    assert MOD.extract_brushup_queue({}) == []


def test_write_brushup_queue_appends_and_counts(tmp_path):
    qp = tmp_path / "brushup-queue.jsonl"
    rows = [{"pattern": "p1", "action": "a"}, {"pattern": "p2", "action": "b"}]
    n = MOD.write_brushup_queue(qp, rows)
    assert n == 2
    # 追記であること: 再呼び出しで 4 行。
    MOD.write_brushup_queue(qp, rows)
    assert len(qp.read_text(encoding="utf-8").splitlines()) == 4


# --------------------------------------------------------------------------
# mark_needs_update
# --------------------------------------------------------------------------

def _make_store(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    idx = kdir / "knowledge-index.json"
    idx.write_text(json.dumps({
        "version": "1.0.0",
        "categories": [{"id": "t", "label": "t", "file": "knowledge-t.json", "keywords": []}],
        "global_keywords": {},
    }), encoding="utf-8")
    item = {"id": "e1", "title": "原文", "intent": "意図", "background": "背景",
            "keywords": ["a", "b"], "source": {"file": "x.md"}}
    (kdir / "knowledge-t.json").write_text(json.dumps({
        "category": "t", "label": "t", "version": "1.0.0", "items": [item],
    }), encoding="utf-8")
    return idx, kdir


def test_mark_needs_update_sets_status_keeps_body(tmp_path):
    idx, kdir = _make_store(tmp_path)
    updated = MOD.mark_needs_update(idx, {"e1"})
    assert updated == ["e1"]
    after = json.loads((kdir / "knowledge-t.json").read_text(encoding="utf-8"))
    item = after["items"][0]
    assert item["status"] == "needs-update"
    assert item["title"] == "原文"  # 本文不変
    assert item["keywords"] == ["a", "b"]


def test_mark_needs_update_idempotent(tmp_path):
    idx, _ = _make_store(tmp_path)
    assert MOD.mark_needs_update(idx, {"e1"}) == ["e1"]
    assert MOD.mark_needs_update(idx, {"e1"}) == []  # 再付与されない


def test_mark_needs_update_empty_ids_or_missing_index(tmp_path):
    idx, _ = _make_store(tmp_path)
    assert MOD.mark_needs_update(idx, set()) == []
    assert MOD.mark_needs_update(tmp_path / "absent.json", {"e1"}) == []


def test_mark_needs_update_skips_corrupt_category_file(tmp_path):
    idx, kdir = _make_store(tmp_path)
    (kdir / "knowledge-t.json").write_text("{ broken", encoding="utf-8")
    # 壊れたカテゴリファイルは握りつぶしてスキップ (例外を投げない)。
    assert MOD.mark_needs_update(idx, {"e1"}) == []


def test_mark_needs_update_skips_missing_category_file(tmp_path):
    idx, kdir = _make_store(tmp_path)
    (kdir / "knowledge-t.json").unlink()  # カテゴリ実体が無い
    assert MOD.mark_needs_update(idx, {"e1"}) == []


# --------------------------------------------------------------------------
# resolve_index_path
# --------------------------------------------------------------------------

def test_resolve_index_path_dir_direct(tmp_path):
    (tmp_path / "knowledge-index.json").write_text("{}", encoding="utf-8")
    assert MOD.resolve_index_path(str(tmp_path)) == tmp_path / "knowledge-index.json"


def test_resolve_index_path_dir_knowledge_subdir(tmp_path):
    # base 直下に無ければ base/knowledge/knowledge-index.json を返す (存在問わず)。
    out = MOD.resolve_index_path(str(tmp_path))
    assert out == tmp_path / "knowledge" / "knowledge-index.json"


def test_resolve_index_path_autodiscover_knowledge_subdir(tmp_path, monkeypatch):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "knowledge-index.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert MOD.resolve_index_path(None) == kdir / "knowledge-index.json"


def test_resolve_index_path_autodiscover_flat(tmp_path, monkeypatch):
    (tmp_path / "knowledge-index.json").write_text("{}", encoding="utf-8")
    sub = tmp_path / "deep"
    sub.mkdir()
    monkeypatch.chdir(sub)
    assert MOD.resolve_index_path(None) == tmp_path / "knowledge-index.json"


def test_resolve_index_path_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert MOD.resolve_index_path(None) is None


# --------------------------------------------------------------------------
# self_test
# --------------------------------------------------------------------------

def test_self_test_passes(capsys):
    MOD.self_test()  # 例外を投げなければ全 8 アサート通過
    out = capsys.readouterr().out
    assert "PASS" in out


# --------------------------------------------------------------------------
# main CLI 契約 (subprocess)
# --------------------------------------------------------------------------

def _run(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_cli_no_mode_errors(tmp_path):
    proc = _run([], cwd=str(tmp_path))
    assert proc.returncode == 2  # argparse error
    assert "--record" in proc.stderr or "--analyze" in proc.stderr


def test_cli_record_requires_query(tmp_path):
    proc = _run(["--record"], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "--query" in proc.stderr


def test_cli_record_writes_entry(tmp_path):
    proc = _run(["--record", "--query", "地方採用", "--matched-ids", "a,b",
                 "--used-ids", "a", "--satisfaction", "helpful", "--note", "メモ",
                 "--dir", str(tmp_path)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["recorded"] is True
    assert out["entry"]["matched_ids"] == ["a", "b"]
    assert out["entry"]["used_ids"] == ["a"]
    log = tmp_path / "usage-log.jsonl"
    assert log.exists()
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[0])["query"] == "地方採用"


def test_cli_record_strips_empty_ids(tmp_path):
    proc = _run(["--record", "--query", "q", "--matched-ids", "a,,b, ",
                 "--dir", str(tmp_path)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["entry"]["matched_ids"] == ["a", "b"]


def test_cli_analyze_insufficient(tmp_path):
    (tmp_path / "usage-log.jsonl").write_text(
        json.dumps({"query": "q", "matched_ids": [], "used_ids": [],
                    "satisfaction": "neutral"}) + "\n", encoding="utf-8")
    proc = _run(["--analyze", "--dir", str(tmp_path)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "サンプル不足" in json.loads(proc.stdout)["note"]


def test_cli_analyze_detects_and_emits_queue(tmp_path):
    log = tmp_path / "usage-log.jsonl"
    log.write_text("".join(
        json.dumps(_entry(f"q{i}", ["always_hit"], [], "neutral")) + "\n"
        for i in range(5)), encoding="utf-8")
    proc = _run(["--analyze", "--emit-queue", "brushup-queue.jsonl",
                 "--dir", str(tmp_path)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    res = json.loads(proc.stdout)
    assert any(f["pattern"] == "hit_not_used" for f in res["findings"])
    assert res["brushup_queue"]["written"] >= 1
    # --dir 相対の emit パスは <dir>/brushup-queue.jsonl へ解決される。
    qp = tmp_path / "brushup-queue.jsonl"
    assert qp.exists()
    assert len(qp.read_text(encoding="utf-8").splitlines()) >= 1


def test_cli_analyze_emit_queue_default_path(tmp_path):
    # --emit-queue をパス無しで指定するとデフォルト brushup-queue.jsonl。
    log = tmp_path / "usage-log.jsonl"
    log.write_text("".join(
        json.dumps(_entry(f"q{i}", ["always_hit"], [], "neutral")) + "\n"
        for i in range(5)), encoding="utf-8")
    proc = _run(["--analyze", "--emit-queue", "--dir", str(tmp_path)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "brushup-queue.jsonl").exists()


def test_cli_analyze_mark_needs_update(tmp_path):
    idx, kdir = _make_store(tmp_path)
    # entry_id "e1" を hit_not_used で検出させる活用ログを作る。
    log = tmp_path / "usage-log.jsonl"
    log.write_text("".join(
        json.dumps(_entry(f"q{i}", ["e1"], [], "neutral")) + "\n"
        for i in range(5)), encoding="utf-8")
    proc = _run(["--analyze", "--mark-needs-update", "--dir", str(tmp_path)],
                cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    res = json.loads(proc.stdout)
    assert res["marked_needs_update"] == ["e1"]
    after = json.loads((kdir / "knowledge-t.json").read_text(encoding="utf-8"))
    assert after["items"][0]["status"] == "needs-update"


def test_cli_mark_needs_update_missing_index_exit1(tmp_path):
    # knowledge-index.json が無い空 dir → exit 1。
    log = tmp_path / "usage-log.jsonl"
    log.write_text("".join(
        json.dumps(_entry(f"q{i}", ["e1"], [], "neutral")) + "\n"
        for i in range(5)), encoding="utf-8")
    proc = _run(["--analyze", "--mark-needs-update", "--dir", str(tmp_path)],
                cwd=str(tmp_path))
    assert proc.returncode == 1
    assert "knowledge-index.json" in proc.stderr


def test_cli_self_test_exit0(tmp_path):
    proc = _run(["--self-test"], cwd=str(tmp_path))
    assert proc.returncode == 0
    assert "PASS" in proc.stdout


# --------------------------------------------------------------------------
# 書き込み失敗 (OSError / JSONDecodeError) のエラー経路
# --------------------------------------------------------------------------

def test_cli_record_write_failure_exit1(tmp_path):
    # --dir をファイルにすると <dir>/usage-log.jsonl の open が NotADirectoryError。
    notdir = tmp_path / "notdir"
    notdir.write_text("x", encoding="utf-8")
    proc = _run(["--record", "--query", "q", "--dir", str(notdir)], cwd=str(tmp_path))
    assert proc.returncode == 1
    # この経路の診断は ensure_ascii 既定 (=True) のため日本語は \uXXXX に escape される。
    err = json.loads(proc.stderr)
    assert "ファイル書き込み失敗" in err["error"]
    assert "Not a directory" in err["error"]


def test_cli_emit_queue_write_failure_exit1(tmp_path):
    # findings を出す活用ログを置き、emit-queue 先の親をファイルにして書き込み失敗。
    log = tmp_path / "usage-log.jsonl"
    log.write_text("".join(
        json.dumps(_entry(f"q{i}", ["always"], [], "neutral")) + "\n"
        for i in range(5)), encoding="utf-8")
    notdir = tmp_path / "notdir"
    notdir.write_text("x", encoding="utf-8")
    # 絶対パスで親がファイル → NotADirectoryError。
    proc = _run(["--analyze", "--emit-queue", str(notdir / "queue.jsonl"),
                 "--dir", str(tmp_path)], cwd=str(tmp_path))
    assert proc.returncode == 1
    assert "キュー書き込み失敗" in proc.stderr


def test_cli_mark_needs_update_corrupt_index_exit1(tmp_path):
    # 壊れた knowledge-index.json は mark_needs_update の json.loads(index) で
    # JSONDecodeError → main の except (OSError, json.JSONDecodeError) で exit 1。
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "knowledge-index.json").write_text("{ broken index", encoding="utf-8")
    log = tmp_path / "usage-log.jsonl"
    log.write_text("".join(
        json.dumps(_entry(f"q{i}", ["e1"], [], "neutral")) + "\n"
        for i in range(5)), encoding="utf-8")
    proc = _run(["--analyze", "--mark-needs-update", "--dir", str(tmp_path)],
                cwd=str(tmp_path))
    assert proc.returncode == 1
    assert "status 付与失敗" in proc.stderr


# --------------------------------------------------------------------------
# main() in-process 契約
#
# subprocess 経路は子プロセスの行カバレッジが (COVERAGE_PROCESS_START 未設定の
# 素の --cov では) 回収されないため、main() の本体分岐は同一プロセスで
# monkeypatch(sys.argv) して直接呼び、--cov に確実に計上させる。
# argparse の error()/SystemExit と sys.exit(...) は SystemExit として捕捉する。
# --------------------------------------------------------------------------

def _call_main(monkeypatch, tmp_path, argv):
    """record_usage.main() を tmp_path を CWD にして与えた argv で実行する。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["record_usage.py", *argv])
    return MOD.main()


def test_main_no_mode_raises_systemexit(tmp_path, monkeypatch):
    # --record も --analyze も無ければ parser.error → SystemExit(2)。
    with pytest.raises(SystemExit) as ei:
        _call_main(monkeypatch, tmp_path, [])
    assert ei.value.code == 2


def test_main_record_requires_query_systemexit(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as ei:
        _call_main(monkeypatch, tmp_path, ["--record"])
    assert ei.value.code == 2


def test_main_record_writes_entry_and_prints(tmp_path, monkeypatch, capsys):
    rc = _call_main(monkeypatch, tmp_path, [
        "--record", "--query", "地方採用", "--matched-ids", "a, ,b",
        "--used-ids", "a", "--satisfaction", "helpful", "--note", "メモ",
        "--dir", str(tmp_path),
    ])
    assert rc is None  # main は record 後 return しない (sys.exit しない)
    out = json.loads(capsys.readouterr().out)
    assert out["recorded"] is True
    assert out["entry"]["matched_ids"] == ["a", "b"]  # 空 id は除去
    assert out["entry"]["used_ids"] == ["a"]
    assert out["entry"]["note"] == "メモ"
    log = tmp_path / "usage-log.jsonl"
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[0])["query"] == "地方採用"


def test_main_record_no_dir_uses_find_log_file(tmp_path, monkeypatch, capsys):
    # --dir 無し: find_log_file(Path.cwd(), args.log) 経路 (else 枝) を踏む。
    rc = _call_main(monkeypatch, tmp_path, [
        "--record", "--query", "q", "--matched-ids", "x",
    ])
    assert rc is None
    out = json.loads(capsys.readouterr().out)
    assert out["recorded"] is True
    # デフォルトログファイルは cwd 配下に作られる。
    assert (tmp_path / "usage-log.jsonl").exists()


def test_main_record_oserror_exit1(tmp_path, monkeypatch, capsys):
    # <dir>/usage-log.jsonl の親をファイルにして open を NotADirectoryError に。
    notdir = tmp_path / "notdir"
    notdir.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        _call_main(monkeypatch, tmp_path, [
            "--record", "--query", "q", "--dir", str(notdir),
        ])
    assert ei.value.code == 1
    err = json.loads(capsys.readouterr().err)
    assert "ファイル書き込み失敗" in err["error"]


def test_main_analyze_insufficient_prints_note(tmp_path, monkeypatch, capsys):
    (tmp_path / "usage-log.jsonl").write_text(
        json.dumps(_entry("q", [], [], "neutral")) + "\n", encoding="utf-8")
    rc = _call_main(monkeypatch, tmp_path, ["--analyze", "--dir", str(tmp_path)])
    assert rc is None
    assert "サンプル不足" in json.loads(capsys.readouterr().out)["note"]


def test_main_analyze_emit_queue_relative_resolves_under_dir(tmp_path, monkeypatch, capsys):
    (tmp_path / "usage-log.jsonl").write_text("".join(
        json.dumps(_entry(f"q{i}", ["always"], [], "neutral")) + "\n"
        for i in range(5)), encoding="utf-8")
    rc = _call_main(monkeypatch, tmp_path, [
        "--analyze", "--emit-queue", "brushup-queue.jsonl", "--dir", str(tmp_path),
    ])
    assert rc is None
    res = json.loads(capsys.readouterr().out)
    assert any(f["pattern"] == "hit_not_used" for f in res["findings"])
    # --dir 相対パスは <dir>/brushup-queue.jsonl へ解決される。
    assert res["brushup_queue"]["path"] == str(tmp_path / "brushup-queue.jsonl")
    assert (tmp_path / "brushup-queue.jsonl").exists()


def test_main_analyze_emit_queue_absolute_path(tmp_path, monkeypatch, capsys):
    # 絶対パスの emit-queue は --dir で前置されず、そのまま使われる。
    (tmp_path / "usage-log.jsonl").write_text("".join(
        json.dumps(_entry(f"q{i}", ["always"], [], "neutral")) + "\n"
        for i in range(5)), encoding="utf-8")
    abs_queue = tmp_path / "out" / "q.jsonl"
    abs_queue.parent.mkdir()
    rc = _call_main(monkeypatch, tmp_path, [
        "--analyze", "--emit-queue", str(abs_queue), "--dir", str(tmp_path),
    ])
    assert rc is None
    res = json.loads(capsys.readouterr().out)
    assert res["brushup_queue"]["path"] == str(abs_queue)
    assert abs_queue.exists()


def test_main_analyze_emit_queue_oserror_exit1(tmp_path, monkeypatch, capsys):
    (tmp_path / "usage-log.jsonl").write_text("".join(
        json.dumps(_entry(f"q{i}", ["always"], [], "neutral")) + "\n"
        for i in range(5)), encoding="utf-8")
    notdir = tmp_path / "notdir"
    notdir.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        _call_main(monkeypatch, tmp_path, [
            "--analyze", "--emit-queue", str(notdir / "q.jsonl"), "--dir", str(tmp_path),
        ])
    assert ei.value.code == 1
    assert "キュー書き込み失敗" in capsys.readouterr().err


def test_main_analyze_mark_needs_update_success(tmp_path, monkeypatch, capsys):
    idx, kdir = _make_store(tmp_path)
    (tmp_path / "usage-log.jsonl").write_text("".join(
        json.dumps(_entry(f"q{i}", ["e1"], [], "neutral")) + "\n"
        for i in range(5)), encoding="utf-8")
    rc = _call_main(monkeypatch, tmp_path, [
        "--analyze", "--mark-needs-update", "--dir", str(tmp_path),
    ])
    assert rc is None
    res = json.loads(capsys.readouterr().out)
    assert res["marked_needs_update"] == ["e1"]
    after = json.loads((kdir / "knowledge-t.json").read_text(encoding="utf-8"))
    assert after["items"][0]["status"] == "needs-update"


def test_main_analyze_mark_needs_update_missing_index_exit1(tmp_path, monkeypatch, capsys):
    (tmp_path / "usage-log.jsonl").write_text("".join(
        json.dumps(_entry(f"q{i}", ["e1"], [], "neutral")) + "\n"
        for i in range(5)), encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        _call_main(monkeypatch, tmp_path, [
            "--analyze", "--mark-needs-update", "--dir", str(tmp_path),
        ])
    assert ei.value.code == 1
    assert "knowledge-index.json" in capsys.readouterr().err


def test_main_analyze_mark_needs_update_corrupt_index_exit1(tmp_path, monkeypatch, capsys):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "knowledge-index.json").write_text("{ broken", encoding="utf-8")
    (tmp_path / "usage-log.jsonl").write_text("".join(
        json.dumps(_entry(f"q{i}", ["e1"], [], "neutral")) + "\n"
        for i in range(5)), encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        _call_main(monkeypatch, tmp_path, [
            "--analyze", "--mark-needs-update", "--dir", str(tmp_path),
        ])
    assert ei.value.code == 1
    assert "status 付与失敗" in capsys.readouterr().err


def test_main_self_test_exit0(tmp_path, monkeypatch, capsys):
    with pytest.raises(SystemExit) as ei:
        _call_main(monkeypatch, tmp_path, ["--self-test"])
    assert ei.value.code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_record_and_analyze_both(tmp_path, monkeypatch, capsys):
    # --record と --analyze を同時指定 → 両ブロックが走る (record 後 analyze)。
    rc = _call_main(monkeypatch, tmp_path, [
        "--record", "--query", "q", "--matched-ids", "z",
        "--analyze", "--dir", str(tmp_path),
    ])
    assert rc is None
    out = capsys.readouterr().out
    # record の JSON と analyze の JSON が両方 stdout に出る。
    assert "recorded" in out and ("findings" in out or "サンプル不足" in out)


def test_module_guard_runs_main_via_runpy(tmp_path, monkeypatch):
    # if __name__ == "__main__": main() のガード行 (末尾) を踏むため runpy 実行。
    import runpy
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["record_usage.py", "--self-test"])
    with pytest.raises(SystemExit) as ei:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert ei.value.code == 0
