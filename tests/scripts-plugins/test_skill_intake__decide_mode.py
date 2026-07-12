"""decide-mode.py の純関数 + main CLI 契約を network/LLM 無しで網羅する。

decide-mode.py は kickoff/purpose/options/summary の JSON から mode(A〜E)を
機械判定するだけの純ロジックであり、実通信は一切しない。さらに skill 生成へ
進む handoff を確定する前に「Notion 公開完了」を必須前提として検証する
precondition gate(逸脱B封鎖)を持つ。よって本テストは:

  - canonical_notion_id: 空 / 32hex compact / URL・token 抽出 / ハイフン入り / 失敗
  - check_publish_precondition: 全 OK 経路 + 各 NG 経路
    (result 欠落 / log 欠落 / log 不正JSON / status≠published / page_id 欠落 /
     log と result の page_id 不一致 / intake.notion_target 不一致 / intake 不正JSON /
     intake target が一致する OK 経路)
  - load_json_required: 欠落(exit3) / 不正JSON(exit3) は main 経由 subprocess で
  - main: precondition gate(BLOCK exit2)/ --allow-skip(env 無し BLOCK / env 有り続行)/
    mode 判定(P 徴候→P / verb 空→E / 連結語→D / 単一→kickoff.pattern 採用)/
    handoff マップ(references/mode-catalog.md 右列の逐語コピー)/ handoff_target /
    out 書き出し内容
  - detect_plugin_scale: plugin_scale 明示宣言 / component_requests 非 skill 種別 /
    skill 系 2 件以上 / 徴候なし

を tmp_path 上の実ファイルで genuine に assert する(repo 非汚染)。
handoff phase 文言は F-0313 で harness-creator 実在語彙 (Step 1 elicit 等) へ更新済み。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "skill-intake"
    / "skills"
    / "run-intake-next-action"
    / "scripts"
    / "decide-mode.py"
)

_SPEC = importlib.util.spec_from_file_location("decide_mode_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# 32 桁の有効な hex を 1 つ用意し、各種表記の入力を作る。
HEX32 = "0123456789abcdef0123456789abcdef"
DASHED = "01234567-89ab-cdef-0123-456789abcdef"


# --------------------------------------------------------------------------
# canonical_notion_id
# --------------------------------------------------------------------------

def test_canonical_empty_and_none():
    assert MOD.canonical_notion_id("") == ""
    assert MOD.canonical_notion_id(None) == ""


def test_canonical_from_compact_32hex():
    assert MOD.canonical_notion_id(HEX32) == DASHED


def test_canonical_from_dashed_is_idempotent():
    # 既にハイフン入りでも非 hex 文字を除去して 32 桁に戻し正規化する。
    assert MOD.canonical_notion_id(DASHED) == DASHED


def test_canonical_from_notion_url_token():
    # compact が 32 桁にならない URL は最終セグメントの 32hex token を抽出する。
    url = f"https://www.notion.so/workspace/Some-Page-Title-{HEX32}?pvs=4"
    assert MOD.canonical_notion_id(url) == DASHED


def test_canonical_returns_empty_when_no_hex():
    assert MOD.canonical_notion_id("not-an-id") == ""


def test_canonical_token_with_trailing_slash():
    url = f"https://notion.so/{HEX32}/"
    assert MOD.canonical_notion_id(url) == DASHED


# --------------------------------------------------------------------------
# check_publish_precondition — fixture helpers
# --------------------------------------------------------------------------

def _write_published(out_dir: Path, page_id: str = DASHED, log_page_id=None,
                     intake_target=None):
    """published 状態の最小 fixture を out_dir に書き、out_path を返す。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / MOD.PUBLISH_RESULT_NAME).write_text(
        json.dumps({"page_id": page_id}), encoding="utf-8"
    )
    log = {"status": "published"}
    if log_page_id is not None:
        log["page_id"] = log_page_id
    (out_dir / MOD.NOTION_LOG_NAME).write_text(json.dumps(log), encoding="utf-8")
    if intake_target is not None:
        (out_dir / MOD.INTAKE_JSON_NAME).write_text(
            json.dumps({"notion_target": intake_target}), encoding="utf-8"
        )
    return out_dir / "decision.json"


def test_precondition_ok_minimal(tmp_path):
    out_path = _write_published(tmp_path / "h")
    ok, reason = MOD.check_publish_precondition(out_path)
    assert ok is True
    assert "公開完了を確認" in reason


def test_precondition_ok_with_matching_log_and_target(tmp_path):
    out_path = _write_published(
        tmp_path / "h", page_id=DASHED, log_page_id=HEX32,
        intake_target={"page_id": DASHED},
    )
    ok, reason = MOD.check_publish_precondition(out_path)
    assert ok is True


def test_precondition_ok_with_target_page_url(tmp_path):
    # notion_target に page_url 形式が与えられても canonical 化して一致判定される。
    url = f"https://notion.so/{HEX32}"
    out_path = _write_published(
        tmp_path / "h", page_id=DASHED, intake_target={"page_url": url},
    )
    ok, _ = MOD.check_publish_precondition(out_path)
    assert ok is True


def test_precondition_missing_result(tmp_path):
    out_dir = tmp_path / "h"
    out_dir.mkdir()
    ok, reason = MOD.check_publish_precondition(out_dir / "decision.json")
    assert ok is False
    assert "が存在しない" in reason and MOD.PUBLISH_RESULT_NAME in reason


def test_precondition_missing_log(tmp_path):
    out_dir = tmp_path / "h"
    out_dir.mkdir()
    (out_dir / MOD.PUBLISH_RESULT_NAME).write_text(json.dumps({"page_id": DASHED}))
    ok, reason = MOD.check_publish_precondition(out_dir / "decision.json")
    assert ok is False
    assert MOD.NOTION_LOG_NAME in reason


def test_precondition_log_invalid_json(tmp_path):
    out_dir = tmp_path / "h"
    out_dir.mkdir()
    (out_dir / MOD.PUBLISH_RESULT_NAME).write_text(json.dumps({"page_id": DASHED}))
    (out_dir / MOD.NOTION_LOG_NAME).write_text("{ broken json")
    ok, reason = MOD.check_publish_precondition(out_dir / "decision.json")
    assert ok is False
    assert "読込失敗" in reason


def test_precondition_status_not_published(tmp_path):
    out_dir = tmp_path / "h"
    out_dir.mkdir()
    (out_dir / MOD.PUBLISH_RESULT_NAME).write_text(json.dumps({"page_id": DASHED}))
    (out_dir / MOD.NOTION_LOG_NAME).write_text(json.dumps({"status": "draft"}))
    ok, reason = MOD.check_publish_precondition(out_dir / "decision.json")
    assert ok is False
    assert "status='draft'" in reason or "draft" in reason


def test_precondition_result_invalid_json(tmp_path):
    out_dir = tmp_path / "h"
    out_dir.mkdir()
    (out_dir / MOD.PUBLISH_RESULT_NAME).write_text("{ broken")
    (out_dir / MOD.NOTION_LOG_NAME).write_text(json.dumps({"status": "published"}))
    ok, reason = MOD.check_publish_precondition(out_dir / "decision.json")
    assert ok is False
    assert "読込失敗" in reason and MOD.PUBLISH_RESULT_NAME in reason


def test_precondition_result_missing_page_id(tmp_path):
    out_dir = tmp_path / "h"
    out_dir.mkdir()
    (out_dir / MOD.PUBLISH_RESULT_NAME).write_text(json.dumps({"foo": "bar"}))
    (out_dir / MOD.NOTION_LOG_NAME).write_text(json.dumps({"status": "published"}))
    ok, reason = MOD.check_publish_precondition(out_dir / "decision.json")
    assert ok is False
    assert "page_id が無い" in reason


def test_precondition_uses_id_fallback_for_page_id(tmp_path):
    # result が page_id でなく id を持つ場合も公開確定として扱う。
    out_dir = tmp_path / "h"
    out_dir.mkdir()
    (out_dir / MOD.PUBLISH_RESULT_NAME).write_text(json.dumps({"id": DASHED}))
    (out_dir / MOD.NOTION_LOG_NAME).write_text(json.dumps({"status": "published"}))
    ok, _ = MOD.check_publish_precondition(out_dir / "decision.json")
    assert ok is True


def test_precondition_log_result_page_id_mismatch(tmp_path):
    other = "ffffffffffffffffffffffffffffffff"
    out_path = _write_published(tmp_path / "h", page_id=DASHED, log_page_id=other)
    ok, reason = MOD.check_publish_precondition(out_path)
    assert ok is False
    assert "一致しない" in reason


def test_precondition_intake_target_mismatch(tmp_path):
    other_dashed = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    out_path = _write_published(
        tmp_path / "h", page_id=DASHED, intake_target={"page_id": other_dashed},
    )
    ok, reason = MOD.check_publish_precondition(out_path)
    assert ok is False
    assert "notion_target.page_id" in reason


def test_precondition_intake_invalid_json(tmp_path):
    out_dir = tmp_path / "h"
    out_dir.mkdir()
    (out_dir / MOD.PUBLISH_RESULT_NAME).write_text(json.dumps({"page_id": DASHED}))
    (out_dir / MOD.NOTION_LOG_NAME).write_text(json.dumps({"status": "published"}))
    (out_dir / MOD.INTAKE_JSON_NAME).write_text("{ broken")
    ok, reason = MOD.check_publish_precondition(out_dir / "decision.json")
    assert ok is False
    assert "読込失敗" in reason and MOD.INTAKE_JSON_NAME in reason


def test_precondition_intake_present_but_no_target_is_ok(tmp_path):
    # intake.json はあるが notion_target が無ければ一致チェックはスキップされ OK。
    out_path = _write_published(tmp_path / "h", page_id=DASHED, intake_target={})
    ok, _ = MOD.check_publish_precondition(out_path)
    assert ok is True


# --------------------------------------------------------------------------
# main CLI 契約 (subprocess)
# --------------------------------------------------------------------------

def _inputs(tmp_path, kickoff=None, purpose=None, options=None, summary=None):
    """4 入力 JSON を tmp_path に書き、パス dict を返す。"""
    kickoff = {"pattern": "A"} if kickoff is None else kickoff
    purpose = {"true_purpose": {"verb_object": "請求書を生成する"}} if purpose is None else purpose
    options = {} if options is None else options
    summary = {} if summary is None else summary
    paths = {}
    for name, data in (("kickoff", kickoff), ("purpose", purpose),
                       ("options", options), ("summary", summary)):
        p = tmp_path / f"{name}.json"
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        paths[name] = p
    return paths


def _run(args, cwd, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd, env=env,
    )


def _argv(paths, out, *extra):
    return [
        "--kickoff", str(paths["kickoff"]),
        "--purpose", str(paths["purpose"]),
        "--options", str(paths["options"]),
        "--summary", str(paths["summary"]),
        "--out", str(out),
        *extra,
    ]


def test_cli_help_exit0(tmp_path):
    proc = _run(["--help"], cwd=str(tmp_path))
    assert proc.returncode == 0
    assert "--kickoff" in proc.stdout and "--allow-skip" in proc.stdout


def test_cli_missing_required_arg_exit2(tmp_path):
    proc = _run([], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "usage:" in proc.stderr


def test_cli_precondition_block_without_publish(tmp_path):
    # publish result が無い → gate BLOCK exit 2。
    paths = _inputs(tmp_path)
    out = tmp_path / "decision.json"
    proc = _run(_argv(paths, out), cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "BLOCK" in proc.stderr and "Notion 公開完了" in proc.stderr
    assert not out.exists()


def test_cli_allow_skip_without_env_blocks(tmp_path):
    paths = _inputs(tmp_path)
    out = tmp_path / "decision.json"
    proc = _run(_argv(paths, out, "--allow-skip"), cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "INTAKE_ALLOW_SKIP_PUBLISH_GATE=1" in proc.stderr


def test_cli_allow_skip_with_env_continues(tmp_path):
    import os
    paths = _inputs(tmp_path)
    out = tmp_path / "decision.json"
    env = dict(os.environ)
    env["INTAKE_ALLOW_SKIP_PUBLISH_GATE"] = "1"
    proc = _run(_argv(paths, out, "--allow-skip"), cwd=str(tmp_path), env=env)
    assert proc.returncode == 0, proc.stderr
    assert "WARN" in proc.stderr
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    # kickoff.pattern=A を採用、verb 非空・連結語無しなので A のまま。
    assert data["mode"] == "A"
    assert data["harness_creator_handoff_phase"] == "Step 1 (elicit)"
    assert data["handoff_target"] == "harness-creator"
    assert data["confirmed_with_user"] is False


def _published_inputs(tmp_path, **kw):
    """published fixture を out 親に置きつつ 4 入力も用意し、(paths, out) を返す。"""
    out_dir = tmp_path / "h"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / MOD.PUBLISH_RESULT_NAME).write_text(json.dumps({"page_id": DASHED}))
    (out_dir / MOD.NOTION_LOG_NAME).write_text(json.dumps({"status": "published"}))
    paths = _inputs(out_dir, **kw)
    return paths, out_dir / "decision.json"


def test_cli_published_mode_d_for_concatenated_verb(tmp_path):
    paths, out = _published_inputs(
        tmp_path,
        kickoff={"pattern": "A"},
        purpose={"true_purpose": {"verb_object": "請求書を生成 と 送付する"}},
    )
    proc = _run(_argv(paths, out), cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "mode=D" in proc.stdout
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["mode"] == "D"
    assert data["multi_skill_suspicion"] is True
    assert data["harness_creator_handoff_phase"] == "Step 1 (elicit, split first)"


def test_cli_published_mode_d_for_plus_verb(tmp_path):
    paths, out = _published_inputs(
        tmp_path,
        kickoff={"pattern": "B"},
        purpose={"true_purpose": {"verb_object": "集計+出力"}},
    )
    proc = _run(_argv(paths, out), cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out.read_text())["mode"] == "D"


def test_cli_published_mode_e_for_empty_verb(tmp_path):
    paths, out = _published_inputs(
        tmp_path,
        kickoff={"pattern": "B"},
        purpose={"true_purpose": {"verb_object": "   "}},
    )
    proc = _run(_argv(paths, out), cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text())
    assert data["mode"] == "E"
    assert "判定不能" in data["reason"]
    assert data["harness_creator_handoff_phase"] == "P1-kickoff (re-intake)"


def test_cli_published_preserves_kickoff_pattern_b(tmp_path):
    # 単一責務 verb・連結語無し → kickoff.pattern=B を採用し handoff も B。
    paths, out = _published_inputs(
        tmp_path,
        kickoff={"pattern": "B"},
        purpose={"true_purpose": {"verb_object": "既存skillを再利用"}},
    )
    proc = _run(_argv(paths, out), cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text())
    assert data["mode"] == "B"
    assert data["harness_creator_handoff_phase"] == "Step 1 (elicit --mode update)"


def test_cli_published_default_pattern_e_when_missing(tmp_path):
    # kickoff.pattern 欠落時のデフォルトは E。
    paths, out = _published_inputs(
        tmp_path,
        kickoff={},
        purpose={"true_purpose": {"verb_object": "なにかを作る"}},
    )
    proc = _run(_argv(paths, out), cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out.read_text())["mode"] == "E"


def test_cli_published_mode_p_plugin_scale_flag(tmp_path):
    # summary.plugin_scale=true → mode P (plugin-dev-planner 行き)。既存 A-E 判定より優先。
    paths, out = _published_inputs(
        tmp_path,
        kickoff={"pattern": "A"},
        purpose={"true_purpose": {"verb_object": "請求書を生成する"}},
        summary={"plugin_scale": True},
    )
    proc = _run(_argv(paths, out), cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "mode=P" in proc.stdout
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["mode"] == "P"
    assert data["handoff_target"] == "plugin-dev-planner"
    assert data["harness_creator_handoff_phase"] == "R1 (elicit-goal)"
    assert data["multi_skill_suspicion"] is True
    assert "plugin_scale" in data["reason"]


def test_cli_published_mode_p_wins_over_d(tmp_path):
    # P 徴候 (component_requests に hook) は連結語 D 判定より優先される。
    paths, out = _published_inputs(
        tmp_path,
        kickoff={"pattern": "A"},
        purpose={"true_purpose": {"verb_object": "集計 と 出力"}},
        options={"component_requests": ["skill", "hook"]},
    )
    proc = _run(_argv(paths, out), cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["mode"] == "P"
    assert data["handoff_target"] == "plugin-dev-planner"
    assert "hook" in data["reason"]


def test_cli_input_missing_exit3(tmp_path):
    # gate を通した後、入力ファイルの 1 つが欠落していれば exit 3。
    paths, out = _published_inputs(tmp_path)
    paths["summary"].unlink()
    proc = _run(_argv(paths, out), cwd=str(tmp_path))
    assert proc.returncode == 3
    assert "input missing" in proc.stderr and "summary" in proc.stderr


def test_cli_input_invalid_json_exit3(tmp_path):
    paths, out = _published_inputs(tmp_path)
    paths["purpose"].write_text("{ broken json", encoding="utf-8")
    proc = _run(_argv(paths, out), cwd=str(tmp_path))
    assert proc.returncode == 3
    assert "input invalid" in proc.stderr and "purpose" in proc.stderr


# --------------------------------------------------------------------------
# detect_plugin_scale: 純関数 (mode P 判定表の正本 = references/mode-catalog.md)
# --------------------------------------------------------------------------

def test_detect_plugin_scale_explicit_flag_each_source():
    for src_kwargs in (
        {"kick": {"plugin_scale": True}, "opts": {}, "summ": {}},
        {"kick": {}, "opts": {"plugin_scale": True}, "summ": {}},
        {"kick": {}, "opts": {}, "summ": {"plugin_scale": True}},
    ):
        is_p, reason = MOD.detect_plugin_scale(**src_kwargs)
        assert is_p is True
        assert "plugin_scale=true" in reason


def test_detect_plugin_scale_non_skill_component_kinds():
    is_p, reason = MOD.detect_plugin_scale(
        {}, {"component_requests": ["skill", "command"]}, {},
    )
    assert is_p is True
    assert "command" in reason


def test_detect_plugin_scale_two_or_more_skills():
    is_p, reason = MOD.detect_plugin_scale(
        {}, {}, {"component_requests": ["skill-a", "skill-b"]},
    )
    assert is_p is True
    assert "2 件" in reason


def test_detect_plugin_scale_negative_paths():
    # 徴候なし / 単一 skill 要望 / plugin_scale が truthy でも True 以外は徴候にしない。
    assert MOD.detect_plugin_scale({}, {}, {})[0] is False
    assert MOD.detect_plugin_scale({}, {"component_requests": ["skill"]}, {})[0] is False
    assert MOD.detect_plugin_scale({"plugin_scale": "yes"}, {}, {})[0] is False


# --------------------------------------------------------------------------
# load_json_required: in-process (exit3 経路を計測対象に乗せる)
# --------------------------------------------------------------------------

def test_load_json_required_reads_valid(tmp_path):
    p = tmp_path / "ok.json"
    p.write_text(json.dumps({"k": "v"}), encoding="utf-8")
    assert MOD.load_json_required(str(p), "ok") == {"k": "v"}


def test_load_json_required_missing_exits3(tmp_path, capsys):
    with pytest.raises(SystemExit) as ei:
        MOD.load_json_required(str(tmp_path / "nope.json"), "kickoff")
    assert ei.value.code == 3
    assert "input missing" in capsys.readouterr().err


def test_load_json_required_invalid_exits3(tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text("{ broken", encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        MOD.load_json_required(str(p), "purpose")
    assert ei.value.code == 3
    assert "input invalid" in capsys.readouterr().err


# --------------------------------------------------------------------------
# main: in-process (sys.argv 差し替え)。subprocess では計測されない
# main() 本体の分岐を coverage に乗せる。
# --------------------------------------------------------------------------

def _run_main(monkeypatch, argv):
    """main() を sys.argv 差し替えで in-process 実行。SystemExit は再送出。"""
    monkeypatch.setattr(sys, "argv", ["decide-mode.py", *argv])
    return MOD.main()


def test_main_inprocess_published_mode_a(tmp_path, monkeypatch, capsys):
    paths, out = _published_inputs(tmp_path)
    _run_main(monkeypatch, _argv(paths, out))
    captured = capsys.readouterr()
    assert "mode=A" in captured.out
    data = json.loads(out.read_text())
    assert data["mode"] == "A"
    assert data["harness_creator_handoff_phase"] == "Step 1 (elicit)"


def test_main_inprocess_mode_d_concatenated(tmp_path, monkeypatch, capsys):
    paths, out = _published_inputs(
        tmp_path,
        kickoff={"pattern": "A"},
        purpose={"true_purpose": {"verb_object": "集計 と 出力"}},
    )
    _run_main(monkeypatch, _argv(paths, out))
    assert "mode=D" in capsys.readouterr().out
    data = json.loads(out.read_text())
    assert data["mode"] == "D" and data["multi_skill_suspicion"] is True


def test_main_inprocess_mode_e_empty_verb(tmp_path, monkeypatch, capsys):
    paths, out = _published_inputs(
        tmp_path,
        kickoff={"pattern": "B"},
        purpose={"true_purpose": {"verb_object": ""}},
    )
    _run_main(monkeypatch, _argv(paths, out))
    assert "mode=E" in capsys.readouterr().out
    assert json.loads(out.read_text())["mode"] == "E"


def test_main_inprocess_each_handoff_phase(tmp_path, monkeypatch, capsys):
    # pattern C → Step 1 (elicit --mode update, prompt-only) を踏む(handoff マップの C 経路)。
    paths, out = _published_inputs(
        tmp_path,
        kickoff={"pattern": "C"},
        purpose={"true_purpose": {"verb_object": "プロンプトだけ更新"}},
    )
    _run_main(monkeypatch, _argv(paths, out))
    assert capsys.readouterr().out.strip() == "mode=C"
    assert json.loads(out.read_text())["harness_creator_handoff_phase"] == "Step 1 (elicit --mode update, prompt-only)"


def test_main_inprocess_mode_p_component_requests(tmp_path, monkeypatch, capsys):
    paths, out = _published_inputs(
        tmp_path,
        kickoff={"pattern": "A"},
        purpose={"true_purpose": {"verb_object": "タスクを同期する"}},
        summary={"component_requests": ["skill", "hook", "command"]},
    )
    _run_main(monkeypatch, _argv(paths, out))
    assert "mode=P" in capsys.readouterr().out
    data = json.loads(out.read_text())
    assert data["mode"] == "P"
    assert data["handoff_target"] == "plugin-dev-planner"
    assert data["harness_creator_handoff_phase"] == "R1 (elicit-goal)"


def test_main_inprocess_block_without_publish_exit2(tmp_path, monkeypatch, capsys):
    paths = _inputs(tmp_path)
    out = tmp_path / "decision.json"
    with pytest.raises(SystemExit) as ei:
        _run_main(monkeypatch, _argv(paths, out))
    assert ei.value.code == 2
    assert "BLOCK" in capsys.readouterr().err
    assert not out.exists()


def test_main_inprocess_allow_skip_without_env_exit2(tmp_path, monkeypatch, capsys):
    paths = _inputs(tmp_path)
    out = tmp_path / "decision.json"
    monkeypatch.delenv("INTAKE_ALLOW_SKIP_PUBLISH_GATE", raising=False)
    with pytest.raises(SystemExit) as ei:
        _run_main(monkeypatch, _argv(paths, out, "--allow-skip"))
    assert ei.value.code == 2
    assert "INTAKE_ALLOW_SKIP_PUBLISH_GATE=1" in capsys.readouterr().err


def test_main_inprocess_allow_skip_with_env_warns_and_continues(tmp_path, monkeypatch, capsys):
    paths = _inputs(tmp_path)
    out = tmp_path / "decision.json"
    monkeypatch.setenv("INTAKE_ALLOW_SKIP_PUBLISH_GATE", "1")
    _run_main(monkeypatch, _argv(paths, out, "--allow-skip"))
    captured = capsys.readouterr()
    assert "WARN" in captured.err
    assert "mode=" in captured.out
    assert out.exists()


def test_main_inprocess_input_missing_exit3(tmp_path, monkeypatch, capsys):
    paths, out = _published_inputs(tmp_path)
    paths["options"].unlink()
    with pytest.raises(SystemExit) as ei:
        _run_main(monkeypatch, _argv(paths, out))
    assert ei.value.code == 3
    assert "input missing" in capsys.readouterr().err
