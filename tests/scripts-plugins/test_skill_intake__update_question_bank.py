"""plugins/skill-intake/scripts/update_question_bank.py の genuine 機能テスト。

共有 question-bank.md へ新規質問を dedup / snapshot / rollback 付きで追記するスクリプトの純関数と
main(argv) の全分岐を tmp_path fixture で網羅する。network: false / keychain: なし。

snapshot_path() は `output/{hint}/question-bank.snapshot.md` を cwd 相対で resolve するため、
全テストで monkeypatch.chdir(tmp_path) して repo を汚染しない。スクリプトは importlib で実ファイル
パスから直接ロードし純関数を呼ぶ。main は in-process(MOD.main(argv))と subprocess(sys.executable)
の両方で exit code / stdout JSON / 副作用(ファイル書込)を assert。

カバー分岐:
- load_bank: 不在→'' / 存在→内容
- count_lines: 空→0 / 改行数
- normalize: 空白圧縮・小文字化・strip / None
- dedup: 既存と重複除去 / 候補内重複 / dict {text} / dict {} / 非 str/dict / 空テキスト skip
- append: str 質問 / dict(text+tags list)/ dict(text のみ)/ dict(text 無→json)/ 非 dict→json / 末尾空白除去
- snapshot_path / ensure_dir / save_snapshot(hint 有/無)
- rollback: snapshot 無→exit2 / 有→復元 exit0
- parse_args: 各フラグ / positional
- main:
    引数不足(diff 無)→exit2 / 入力 JSON 不正→exit2
    rollback 経路 / dry-run(apply 無)→exit0
    capacity halt(既存が MAX_LINES 超)→exit3
    apply 追記→exit0(書込・dedup・MAX_PER_SESSION 上限)
    apply 後 capacity halt(would_lines 超)→exit3
    session_id / hint / candidates キー揺れの解決
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "update_question_bank.py"

SPEC = importlib.util.spec_from_file_location("update_question_bank_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# ── load_bank ────────────────────────────────────────────────────────────────
def test_load_bank_missing_returns_empty(tmp_path):
    assert MOD.load_bank(tmp_path / "nope.md") == ""


def test_load_bank_reads_content(tmp_path):
    p = tmp_path / "bank.md"
    p.write_text("# Bank\n- q1\n", encoding="utf-8")
    assert MOD.load_bank(p) == "# Bank\n- q1\n"


# ── count_lines ──────────────────────────────────────────────────────────────
def test_count_lines_empty():
    assert MOD.count_lines("") == 0


def test_count_lines_counts_newlines():
    assert MOD.count_lines("a\nb\nc") == 3
    assert MOD.count_lines("a\n") == 2


# ── normalize ────────────────────────────────────────────────────────────────
def test_normalize_collapses_whitespace_and_lowers():
    assert MOD.normalize("  Hello   World  ") == "hello world"


def test_normalize_none():
    assert MOD.normalize(None) == ""


def test_normalize_non_string():
    assert MOD.normalize(123) == "123"


# ── dedup ────────────────────────────────────────────────────────────────────
def test_dedup_removes_existing_duplicate():
    existing = "## Session s\n- What is your goal?\n"
    out = MOD.dedup(existing, ["What is your goal?", "New question"])
    assert out == ["New question"]


def test_dedup_removes_in_candidate_duplicates():
    out = MOD.dedup("", ["Same Q", "same q", "Other"])
    assert out == ["Same Q", "Other"]


def test_dedup_dict_text_field():
    out = MOD.dedup("", [{"text": "Q one"}, {"text": "Q one"}, {"text": "Q two"}])
    assert out == [{"text": "Q one"}, {"text": "Q two"}]


def test_dedup_dict_without_text_skipped():
    # dict に text が無ければ '' → 空テキストとして skip
    out = MOD.dedup("", [{"foo": "bar"}])
    assert out == []


def test_dedup_non_str_non_dict_skipped():
    out = MOD.dedup("", [123, None])
    assert out == []


def test_dedup_empty_text_skipped():
    out = MOD.dedup("", ["", "   "])
    assert out == []


# ── append ───────────────────────────────────────────────────────────────────
def test_append_string_question():
    out = MOD.append("# Bank\n", "sess1", ["plain question"])
    assert "## Session sess1" in out
    assert "- plain question" in out
    assert out.endswith("\n")


def test_append_dict_with_tags():
    out = MOD.append("", "s", [{"text": "tagged q", "tags": ["a", "b"]}])
    assert "- tagged q <!-- a,b -->" in out


def test_append_dict_text_only():
    out = MOD.append("", "s", [{"text": "just text"}])
    assert "- just text" in out
    assert "<!--" not in out


def test_append_dict_without_text_serializes_json():
    out = MOD.append("", "s", [{"k": "v"}])
    assert '- {"k": "v"}' in out


def test_append_non_dict_non_str_serializes_json():
    out = MOD.append("", "s", [[1, 2]])
    assert "- [1, 2]" in out


def test_append_strips_trailing_whitespace_of_bank():
    out = MOD.append("# Bank\n\n   \n", "s", ["q"])
    # 既存末尾の連続空白(改行含む)は re.sub(r'\s*$','') で全て削られてから
    # session ヘッダが連結される(末尾は "# Bank" 直後に \n## Session)
    assert out.startswith("# Bank\n## Session s")
    assert "\n\n" not in out.split("## Session")[0]


# ── snapshot_path / ensure_dir / save_snapshot ───────────────────────────────
def test_snapshot_path_shape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = MOD.snapshot_path("myhint")
    assert p == (tmp_path / "output" / "myhint" / "question-bank.snapshot.md").resolve()


def test_ensure_dir_creates_parents(tmp_path):
    target = tmp_path / "a" / "b" / "c.md"
    MOD.ensure_dir(target)
    assert target.parent.is_dir()


def test_save_snapshot_no_hint_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    bank.write_text("data", encoding="utf-8")
    assert MOD.save_snapshot(bank, None) is None


def test_save_snapshot_writes_copy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    bank.write_text("original\n", encoding="utf-8")
    snap = MOD.save_snapshot(bank, "h1")
    assert snap is not None
    assert snap.read_text(encoding="utf-8") == "original\n"


def test_save_snapshot_missing_bank_writes_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    snap = MOD.save_snapshot(tmp_path / "absent.md", "h2")
    assert snap.read_text(encoding="utf-8") == ""


# ── rollback ─────────────────────────────────────────────────────────────────
def test_rollback_missing_snapshot_exit2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = MOD.rollback(tmp_path / "bank.md", "nohint")
    assert rc == 2
    assert "snapshot not found" in capsys.readouterr().err


def test_rollback_restores_and_exit0(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    bank.write_text("current\n", encoding="utf-8")
    snap = MOD.snapshot_path("h")
    MOD.ensure_dir(snap)
    snap.write_text("snapshotted\n", encoding="utf-8")
    rc = MOD.rollback(bank, "h")
    assert rc == 0
    assert bank.read_text(encoding="utf-8") == "snapshotted\n"
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": True, "rolled_back": True, "hint": "h", "from": str(snap)}


# ── parse_args ───────────────────────────────────────────────────────────────
def test_parse_args_all_flags():
    args = MOD.parse_args(
        ["--bank", "b.md", "--diff", "s.json", "--apply", "--hint", "h", "pos1"]
    )
    assert args["bank"] == "b.md"
    assert args["diff"] == "s.json"
    assert args["apply"] is True
    assert args["hint"] == "h"
    assert args["positional"] == ["pos1"]


def test_parse_args_rollback():
    args = MOD.parse_args(["--rollback", "h"])
    assert args["rollback"] == "h"


def test_parse_args_positional_only():
    args = MOD.parse_args(["bank.md", "session.json"])
    assert args["positional"] == ["bank.md", "session.json"]
    assert "apply" not in args


# ── main: in-process ─────────────────────────────────────────────────────────
def _session(tmp_path, data) -> Path:
    p = tmp_path / "session.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_main_missing_diff_exit2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["--bank", str(tmp_path / "bank.md")])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


def test_main_bad_json_exit2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    rc = MOD.main(["--bank", str(tmp_path / "bank.md"), "--diff", str(bad)])
    assert rc == 2
    assert "input error" in capsys.readouterr().err


def test_main_dry_run_exit0(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    bank.write_text("# Bank\n- existing q\n", encoding="utf-8")
    sess = _session(tmp_path, {"session_id": "S1", "questions": ["existing q", "fresh q"]})
    rc = MOD.main(["--bank", str(bank), "--diff", str(sess)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True
    assert out["to_append"] == 1  # "existing q" は dedup
    assert out["skipped_duplicates"] == 1
    # dry-run なので bank は不変
    assert bank.read_text(encoding="utf-8") == "# Bank\n- existing q\n"


def test_main_apply_appends_and_writes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    bank.write_text("# Bank\n", encoding="utf-8")
    sess = _session(tmp_path, {"session_id": "S2", "questions": ["q a", "q b"]})
    rc = MOD.main(["--bank", str(bank), "--diff", str(sess), "--apply"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["appended"] == 2
    assert out["session_id"] == "S2"
    body = bank.read_text(encoding="utf-8")
    assert "## Session S2" in body
    assert "- q a" in body and "- q b" in body
    # snapshot も作られている(hint=session_id)
    assert MOD.snapshot_path("S2").exists()


def test_main_apply_respects_max_per_session(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    bank.write_text("", encoding="utf-8")
    qs = [f"unique q {i}" for i in range(MOD.MAX_PER_SESSION + 3)]
    sess = _session(tmp_path, {"session_id": "S3", "questions": qs})
    rc = MOD.main(["--bank", str(bank), "--diff", str(sess), "--apply"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["appended"] == MOD.MAX_PER_SESSION


def test_main_capacity_halt_existing_too_big(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    bank.write_text("\n".join(["x"] * (MOD.MAX_LINES + 5)), encoding="utf-8")
    sess = _session(tmp_path, {"session_id": "S4", "questions": ["new"]})
    rc = MOD.main(["--bank", str(bank), "--diff", str(sess), "--apply"])
    assert rc == 3
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "halted_capacity"
    assert out["max"] == MOD.MAX_LINES


def test_main_capacity_halt_after_append(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    # 既存は MAX_LINES 以下だが追記で超過する境界
    bank.write_text("\n".join(["x"] * (MOD.MAX_LINES - 1)), encoding="utf-8")
    qs = [f"new q {i}" for i in range(MOD.MAX_PER_SESSION)]
    sess = _session(tmp_path, {"session_id": "S5", "questions": qs})
    rc = MOD.main(["--bank", str(bank), "--diff", str(sess), "--apply"])
    assert rc == 3
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "halted_capacity"
    assert "would_lines" in out


def test_main_rollback_path(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    bank.write_text("changed\n", encoding="utf-8")
    snap = MOD.snapshot_path("rb")
    MOD.ensure_dir(snap)
    snap.write_text("restored\n", encoding="utf-8")
    rc = MOD.main(["--bank", str(bank), "--rollback", "rb"])
    assert rc == 0
    assert bank.read_text(encoding="utf-8") == "restored\n"


def test_main_resolves_alt_keys(tmp_path, monkeypatch, capsys):
    # session_id 不在→id、questions 不在→used_questions、hint は --hint 優先
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    bank.write_text("", encoding="utf-8")
    sess = _session(tmp_path, {"id": "ALT", "used_questions": ["from used"]})
    rc = MOD.main(["--bank", str(bank), "--diff", str(sess), "--apply", "--hint", "custom"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["session_id"] == "ALT"
    assert out["hint"] == "custom"
    assert out["appended"] == 1
    assert MOD.snapshot_path("custom").exists()


def test_main_candidates_key_fallback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    bank.write_text("", encoding="utf-8")
    sess = _session(tmp_path, {"session_id": "C1", "candidates": ["cand q"]})
    rc = MOD.main(["--bank", str(bank), "--diff", str(sess)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["to_append"] == 1


def test_main_positional_bank_and_diff(tmp_path, monkeypatch, capsys):
    # positional[0]=bank, positional[1]=diff の経路
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    bank.write_text("", encoding="utf-8")
    sess = _session(tmp_path, {"session_id": "P1", "questions": ["pos q"]})
    rc = MOD.main([str(bank), str(sess), "--apply"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["appended"] == 1


def test_main_generates_session_id_when_absent(tmp_path, monkeypatch, capsys):
    # session_id / id / hint いずれも無い → s-<ms> 生成、hint=session_id
    monkeypatch.chdir(tmp_path)
    bank = tmp_path / "bank.md"
    bank.write_text("", encoding="utf-8")
    sess = _session(tmp_path, {"questions": ["q"]})
    rc = MOD.main(["--bank", str(bank), "--diff", str(sess), "--apply"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["session_id"].startswith("s-")
    assert out["hint"] == out["session_id"]


# ── main: subprocess CLI(実 main 起動。cwd=tmp_path で repo 非汚染) ──────────
def test_cli_subprocess_apply(tmp_path):
    bank = tmp_path / "bank.md"
    bank.write_text("# Bank\n", encoding="utf-8")
    sess = tmp_path / "s.json"
    sess.write_text(json.dumps({"session_id": "CLI1", "questions": ["cli q"]}), encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--bank", str(bank), "--diff", str(sess), "--apply"],
        text=True,
        capture_output=True,
        cwd=tmp_path,
    )
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["appended"] == 1
    assert "cli q" in bank.read_text(encoding="utf-8")


def test_cli_subprocess_usage_exit2(tmp_path):
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--bank", str(tmp_path / "b.md")],
        text=True,
        capture_output=True,
        cwd=tmp_path,
    )
    assert res.returncode == 2
    assert "usage:" in res.stderr
