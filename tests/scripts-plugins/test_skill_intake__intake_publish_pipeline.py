"""Genuine functional tests for plugins/skill-intake/scripts/intake_publish_pipeline.py.

カバレッジ計測方針: orchestrator の本体ロジック (target 解決 / fail-closed 早期 exit /
render→fidelity→gate→publish の段階配線 / log・url・result 書き出し) を **in-process** で
`main()` を駆動して網羅する。subprocess 起動の子プロセスは別プロセスのため
`python3 -m pytest --cov` (COVERAGE_PROCESS_START 無し) では計上されないので、

- `run()` ヘルパ (実 subprocess.run を stub) を直接呼んで段階起動の戻り値分岐を検査
- `main()` 内で各ステージを起動するヘルパ `run` と直接 `subprocess.run` を monkeypatch で
  差し替え、network/Notion を一切叩かずに段階遷移・成否ハンドリングを genuine に検証

全ファイル I/O は tmp_path 配下に限定し repo を汚さない。実通信・実 keychain は呼ばない。
"""
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "intake_publish_pipeline.py"

_SPEC = importlib.util.spec_from_file_location("intake_publish_pipeline_s3", SCRIPT)
IPP = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(IPP)


# ===================== 純関数 =====================

def test_canonical_id_dashed_and_compact_equal():
    dashed = IPP._canonical_id("12345678-1234-1234-1234-123456789abc")
    compact = IPP._canonical_id("12345678123412341234123456789abc")
    assert dashed == compact and dashed != ""


def test_canonical_id_invalid_and_none():
    assert IPP._canonical_id("zzzz") == ""
    assert IPP._canonical_id(None) == ""


def test_read_json_roundtrip(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"k": [1, 2]}), encoding="utf-8")
    assert IPP._read_json(p) == {"k": [1, 2]}


def test_read_json_raises_on_bad(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{nope", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        IPP._read_json(p)


def test_write_repaired_result(tmp_path):
    p = tmp_path / "result.json"
    IPP._write_repaired_result(p, "pid-1", "https://x/p")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["page_id"] == "pid-1"
    assert d["url"] == "https://x/p"
    assert d["mode"] == "update"
    assert d["repaired_from_explicit_target"] is True
    assert "published_at" in d


def test_write_repaired_result_empty_url(tmp_path):
    p = tmp_path / "result.json"
    IPP._write_repaired_result(p, "pid-1", None)
    assert json.loads(p.read_text(encoding="utf-8"))["url"] == ""


def test_write_log_full(tmp_path):
    log = tmp_path / "sub" / "notion-log.json"
    url = tmp_path / "notion-url.txt"
    IPP._write_log(str(log), str(url), "published", 0, "publish",
                   page_id="pid", url="https://u", mode="update")
    assert url.read_text(encoding="utf-8") == "https://u\n"
    d = json.loads(log.read_text(encoding="utf-8"))
    assert d["status"] == "published"
    assert d["exit_code"] == 0
    assert d["stage"] == "publish"
    assert d["mode"] == "update"


def test_write_log_empty_url_does_not_write_url_file(tmp_path):
    # 失敗時 (url 空) は notion-url.txt を書かない (成功 URL 確定時のみ)。
    # 空ファイル残置は初回翻訳ゲートを恒久 False 化し retry デッドエンドになるため。
    log = tmp_path / "notion-log.json"
    url = tmp_path / "notion-url.txt"
    IPP._write_log(str(log), str(url), "failed", 51, "target_resolution")
    assert not url.exists()
    assert json.loads(log.read_text(encoding="utf-8"))["exit_code"] == 51


def test_write_log_empty_url_keeps_existing_url_file(tmp_path):
    # 前回成功 URL が既にある状態での失敗は notion-url.txt を破壊しない (truncate しない)。
    log = tmp_path / "notion-log.json"
    url = tmp_path / "notion-url.txt"
    url.write_text("https://www.notion.so/prev\n", encoding="utf-8")
    IPP._write_log(str(log), str(url), "failed", 8, "publish")
    assert url.read_text(encoding="utf-8") == "https://www.notion.so/prev\n"


def test_write_log_swallows_errors(tmp_path, capsys):
    # 書き込み不能パスでも例外を上げず stderr へ。
    # url_path を「ディレクトリ」にして open(url_path, 'w') を IsADirectoryError にする
    # (url 非空でのみ url 書き込みが走るため url を渡す)。
    bad_dir = tmp_path / "asdir"
    bad_dir.mkdir()
    IPP._write_log(str(tmp_path / "log.json"), str(bad_dir), "failed", 2, "x",
                   url="https://u")
    err = capsys.readouterr().err
    assert "notion-url/log write error" in err


# ===================== _has_publish_artifact (初回翻訳ゲートの内容ベース判定) =====================

def test_has_publish_artifact_none(tmp_path):
    assert IPP._has_publish_artifact(
        str(tmp_path / "notion-publish-result.json"), str(tmp_path / "notion-url.txt")) is False


def test_has_publish_artifact_empty_leftovers_ignored(tmp_path):
    # 失敗残置 (空 url / page_id 無し result) は痕跡とみなさない → 初回経路が回復する。
    url = tmp_path / "notion-url.txt"
    url.write_text("", encoding="utf-8")
    result = tmp_path / "notion-publish-result.json"
    result.write_text("{}", encoding="utf-8")
    assert IPP._has_publish_artifact(str(result), str(url)) is False


def test_has_publish_artifact_url_content(tmp_path):
    url = tmp_path / "notion-url.txt"
    url.write_text("https://www.notion.so/x\n", encoding="utf-8")
    assert IPP._has_publish_artifact(str(tmp_path / "r.json"), str(url)) is True


def test_has_publish_artifact_result_page_id(tmp_path):
    result = tmp_path / "notion-publish-result.json"
    result.write_text(json.dumps({"page_id": "pid"}), encoding="utf-8")
    assert IPP._has_publish_artifact(str(result), str(tmp_path / "u.txt")) is True


def test_has_publish_artifact_unreadable_result_fail_closed(tmp_path):
    # 破損 result は不明状態 → True (create 翻訳を無効化する fail-closed)。
    result = tmp_path / "notion-publish-result.json"
    result.write_text("{broken", encoding="utf-8")
    assert IPP._has_publish_artifact(str(result), str(tmp_path / "u.txt")) is True


# ===================== run() ヘルパ (subprocess を stub) =====================

class _FakeProc:
    def __init__(self, returncode=0, stdout=b""):
        self.returncode = returncode
        self.stdout = stdout


def test_run_simple_returns_returncode(monkeypatch, tmp_path):
    calls = {}

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        return _FakeProc(returncode=0)

    monkeypatch.setattr(IPP.subprocess, "run", fake_run)
    rc = IPP.run("label", tmp_path / "script.py", ["--a", "1"])
    assert rc == 0
    assert calls["cmd"][0] == sys.executable
    assert str(tmp_path / "script.py") in calls["cmd"]


def test_run_none_returncode_maps_to_1(monkeypatch, tmp_path):
    monkeypatch.setattr(IPP.subprocess, "run", lambda cmd, **kw: _FakeProc(returncode=None))
    assert IPP.run("l", tmp_path / "s.py", []) == 1


def test_run_capture_stdout_success(monkeypatch, tmp_path):
    out = tmp_path / "blocks.json"
    monkeypatch.setattr(IPP.subprocess, "run",
                        lambda cmd, **kw: _FakeProc(returncode=0, stdout=b'{"blocks":[]}'))
    rc = IPP.run("render", tmp_path / "s.py", [], capture_stdout_to=str(out))
    assert rc == 0
    assert out.read_bytes() == b'{"blocks":[]}'


def test_run_capture_stdout_write_error_returns_2(monkeypatch, tmp_path):
    # capture_stdout_to を既存ディレクトリにして open(...,'wb') を失敗させる
    bad = tmp_path / "adir"
    bad.mkdir()
    monkeypatch.setattr(IPP.subprocess, "run",
                        lambda cmd, **kw: _FakeProc(returncode=0, stdout=b"x"))
    rc = IPP.run("render", tmp_path / "s.py", [], capture_stdout_to=str(bad))
    assert rc == 2


def test_run_capture_stdout_nonzero_echoes(monkeypatch, tmp_path, capsysbinary):
    monkeypatch.setattr(IPP.subprocess, "run",
                        lambda cmd, **kw: _FakeProc(returncode=3, stdout=b"errbytes"))
    rc = IPP.run("render", tmp_path / "s.py", [], capture_stdout_to=str(tmp_path / "o.json"))
    assert rc == 3
    # 非ゼロ時は stdout を stderr.buffer へエコーし result は書かない
    assert not (tmp_path / "o.json").exists()


# ===================== main() in-process =====================

def _intake(tmp_path, payload="{}", name="intake.json", manifest=True):
    p = tmp_path / name
    p.write_text(payload, encoding="utf-8")
    if manifest:
        # All-or-Nothing 常時実行化 (F-0110) に伴い、out_dir 既定の notion-manifest.json を
        # 配置する (verify_assets 段は _stub_stages が rc を返す)。manifest=False で不在を模す。
        (tmp_path / "notion-manifest.json").write_text("{}", encoding="utf-8")
    return p


def _set_argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["intake_publish_pipeline.py", *args])


def test_main_intake_required(monkeypatch, capsys):
    _set_argv(monkeypatch)
    assert IPP.main() == 2
    assert "--intake is required" in capsys.readouterr().err


def test_main_intake_not_found(monkeypatch, capsys, tmp_path):
    _set_argv(monkeypatch, "--intake", str(tmp_path / "nope.json"))
    assert IPP.main() == 2
    assert "intake not found" in capsys.readouterr().err


def test_main_default_rejects_missing_target(monkeypatch, capsys, tmp_path):
    intake = _intake(tmp_path)
    _set_argv(monkeypatch, "--intake", str(intake))
    assert IPP.main() == 51
    assert "create fallback is disabled by default" in capsys.readouterr().err
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["stage"] == "target_resolution"
    assert log["exit_code"] == 51


def test_main_revise_no_pageid_no_result(monkeypatch, capsys, tmp_path):
    intake = _intake(tmp_path)
    _set_argv(monkeypatch, "--intake", str(intake), "--revise")
    assert IPP.main() == 51
    assert "page_id を解決できない" in capsys.readouterr().err


def test_main_revise_page_id_mismatch(monkeypatch, capsys, tmp_path):
    intake = _intake(tmp_path)
    (tmp_path / "notion-publish-result.json").write_text(
        json.dumps({"page_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}), encoding="utf-8")
    _set_argv(monkeypatch, "--intake", str(intake), "--revise",
              "--page-id", "12345678-1234-1234-1234-123456789abc")
    assert IPP.main() == 51
    assert "page_id mismatch" in capsys.readouterr().err
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["stage"] == "target_mismatch"


def test_main_revise_repairs_unreadable_result(monkeypatch, tmp_path):
    # 破損 result + 明示 page_id → 復旧してから後続へ進む。
    # render を即失敗させて render stage で止め、復旧が行われたことを result で確認。
    intake = _intake(tmp_path)
    pid = "12345678-1234-1234-1234-123456789abc"
    (tmp_path / "notion-publish-result.json").write_text("{broken", encoding="utf-8")
    _stub_stages(monkeypatch, render_rc=7)
    _set_argv(monkeypatch, "--intake", str(intake), "--revise", "--page-id", pid)
    rc = IPP.main()
    assert rc == 7  # render の戻り値で停止
    repaired = json.loads((tmp_path / "notion-publish-result.json").read_text(encoding="utf-8"))
    assert repaired["repaired_from_explicit_target"] is True
    assert repaired["page_id"].replace("-", "") == pid.replace("-", "")


def test_main_manifest_not_found(monkeypatch, capsys, tmp_path):
    intake = _intake(tmp_path)
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create",
              "--manifest", str(tmp_path / "nope-manifest.json"))
    assert IPP.main() == 2
    assert "manifest not found" in capsys.readouterr().err
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["stage"] == "manifest_missing"


# ----- main() の段階配線を in-process で網羅するための stage stub -----

def _stub_stages(monkeypatch, *, assets_rc=0, render_rc=0, fidelity_rc=0, gate_rc=0,
                 publish_rc=0, publish_stdout=b"", record=None):
    """IPP.run (verify_assets/render/fidelity/gate) と直接 subprocess.run (publish) を差し替える。

    script 名で段階を見分け、指定 returncode を返す。render は --out のファイルを生成して
    後続ステップが参照可能にする (確からしい副作用)。
    """
    rec = record if record is not None else []

    def fake_run(label, script, args, capture_stdout_to=None):
        rec.append((label, [str(a) for a in args]))
        name = script.name if hasattr(script, "name") else str(script)
        if "verify_notion_assets" in name:
            return assets_rc
        if "render_notion_page" in name:
            # --out 引数のファイルを作る (render 成果物の存在を模す)
            if "--out" in args:
                out = args[args.index("--out") + 1]
                Path(out).write_text('{"children": []}', encoding="utf-8")
            return render_rc
        if "validate-notion-fidelity" in name:
            return fidelity_rc
        if "quality_gate" in name:
            return gate_rc
        return 0

    monkeypatch.setattr(IPP, "run", fake_run)

    class _Proc:
        def __init__(self):
            self.returncode = publish_rc
            self.stdout = publish_stdout

    def fake_subprocess_run(cmd, **kw):
        rec.append(("publish_proc", [str(c) for c in cmd]))
        return _Proc()

    monkeypatch.setattr(IPP.subprocess, "run", fake_subprocess_run)
    return rec


def test_main_render_failure_stops(monkeypatch, capsys, tmp_path):
    intake = _intake(tmp_path)
    _stub_stages(monkeypatch, render_rc=9)
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create")
    assert IPP.main() == 9
    assert "render failed" in capsys.readouterr().err
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["stage"] == "render"


def test_main_fidelity_failure_stops(monkeypatch, capsys, tmp_path):
    intake = _intake(tmp_path)
    _stub_stages(monkeypatch, fidelity_rc=4)
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create")
    assert IPP.main() == 2  # fidelity 失敗は常に 2 にマップ
    assert "fidelity_guard failed" in capsys.readouterr().err
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["stage"] == "fidelity_guard"


def test_main_gate_failure_stops(monkeypatch, capsys, tmp_path):
    intake = _intake(tmp_path)
    _stub_stages(monkeypatch, gate_rc=5)
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create")
    assert IPP.main() == 5
    assert "quality_gate failed" in capsys.readouterr().err
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["stage"] == "quality_gate"


def test_main_assets_failure_stops(monkeypatch, capsys, tmp_path):
    intake = _intake(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    _stub_stages(monkeypatch, assets_rc=6)
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create",
              "--manifest", str(manifest))
    assert IPP.main() == 6
    assert "verify_assets failed" in capsys.readouterr().err
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["stage"] == "verify_assets"


def test_main_publish_success_writes_log_and_url(monkeypatch, capsys, tmp_path):
    intake = _intake(tmp_path)
    pub_out = json.dumps({"id": "pid-9", "url": "https://notion/p9", "mode": "create"}).encode()
    rec = _stub_stages(monkeypatch, publish_rc=0, publish_stdout=pub_out)
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create",
              "--database-id", "db-abc")
    assert IPP.main() == 0
    # url / log が書かれている
    assert (tmp_path / "notion-url.txt").read_text(encoding="utf-8") == "https://notion/p9\n"
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["status"] == "published"
    assert log["page_id"] == "pid-9"
    assert log["mode"] == "create"
    # database-id が render と publish の両方へ伝搬している (publish cmd を確認)
    pub_cmd = [r for r in rec if r[0] == "publish_proc"][0][1]
    assert "db-abc" in pub_cmd
    assert "--allow-create" in pub_cmd


def test_main_publish_failure_returns_code(monkeypatch, capsys, tmp_path):
    intake = _intake(tmp_path)
    rec = _stub_stages(monkeypatch, publish_rc=8, publish_stdout=b"")
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create")
    assert IPP.main() == 8
    err = capsys.readouterr().err
    assert "publish failed" in err
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["status"] == "failed"


def test_main_dry_run_skips_log(monkeypatch, capsys, tmp_path):
    intake = _intake(tmp_path)
    pub_out = json.dumps({"id": "p", "url": "https://u", "mode": "dry"}).encode()
    rec = _stub_stages(monkeypatch, publish_rc=0, publish_stdout=pub_out)
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create", "--dry-run")
    assert IPP.main() == 0
    # dry-run では notion-log.json を書かない
    assert not (tmp_path / "notion-log.json").exists()
    pub_cmd = [r for r in rec if r[0] == "publish_proc"][0][1]
    assert "--dry-run" in pub_cmd


def test_main_revise_consistent_page_id_passes_result_to_gate(monkeypatch, capsys, tmp_path):
    intake = _intake(tmp_path)
    pid = "12345678-1234-1234-1234-123456789abc"
    result_path = tmp_path / "notion-publish-result.json"
    result_path.write_text(json.dumps({"page_id": pid}), encoding="utf-8")
    pub_out = json.dumps({"id": pid, "url": "https://u", "mode": "update"}).encode()
    rec = _stub_stages(monkeypatch, publish_rc=0, publish_stdout=pub_out)
    _set_argv(monkeypatch, "--intake", str(intake), "--revise", "--page-id", pid)
    assert IPP.main() == 0
    # gate に --result-path / --prev-page-id が伝搬している
    gate_args = [r for r in rec if r[0] == "quality_gate"][0][1]
    assert "--result-path" in gate_args
    assert "--prev-page-id" in gate_args
    # publish に --require-update (revise) が付く
    pub_cmd = [r for r in rec if r[0] == "publish_proc"][0][1]
    assert "--require-update" in pub_cmd
    assert "--page-id" in pub_cmd


def test_main_revise_page_url_resolves_target(monkeypatch, capsys, tmp_path):
    # --page-url から page_id を抽出して target 解決し publish へ伝搬する。
    intake = _intake(tmp_path)
    url = "https://www.notion.so/Title-12345678123412341234123456789abc"
    pub_out = json.dumps({"id": "12345678-1234-1234-1234-123456789abc",
                          "url": url, "mode": "update"}).encode()
    rec = _stub_stages(monkeypatch, publish_rc=0, publish_stdout=pub_out)
    _set_argv(monkeypatch, "--intake", str(intake), "--revise", "--page-url", url)
    assert IPP.main() == 0
    pub_cmd = [r for r in rec if r[0] == "publish_proc"][0][1]
    assert "--page-url" in pub_cmd
    assert "--require-update" in pub_cmd


def test_main_manifest_and_gate_out_args_propagate(monkeypatch, capsys, tmp_path):
    # 有効 manifest を渡すと render に --manifest が、--gate-out を渡すと gate に --out が乗る。
    intake = _intake(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    gate_out = tmp_path / "gate.json"
    pub_out = json.dumps({"id": "p", "url": "https://u", "mode": "create"}).encode()
    rec = _stub_stages(monkeypatch, publish_rc=0, publish_stdout=pub_out)
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create",
              "--manifest", str(manifest), "--gate-out", str(gate_out))
    assert IPP.main() == 0
    render_args = [r for r in rec if r[0] == "render"][0][1]
    assert "--manifest" in render_args
    gate_args = [r for r in rec if r[0] == "quality_gate"][0][1]
    assert "--out" in gate_args
    # verify_assets が manifest 付きで起動された
    assert any(r[0] == "verify_assets" for r in rec)


def test_main_revise_result_repair_failure_returns_2(monkeypatch, capsys, tmp_path):
    # 破損 result の復旧書き込み自体が失敗する経路 (160-163)。
    # _write_repaired_result を例外で失敗させ、exit 2 / result_repair stage を検証。
    intake = _intake(tmp_path)
    pid = "12345678-1234-1234-1234-123456789abc"
    (tmp_path / "notion-publish-result.json").write_text("{broken", encoding="utf-8")

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(IPP, "_write_repaired_result", boom)
    _set_argv(monkeypatch, "--intake", str(intake), "--revise", "--page-id", pid)
    assert IPP.main() == 2
    assert "result repair failed" in capsys.readouterr().err
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["stage"] == "result_repair"


def test_main_blocks_out_override(monkeypatch, capsys, tmp_path):
    # --blocks-out を明示すると render の --out がそのパスになる。
    intake = _intake(tmp_path)
    blocks = tmp_path / "custom-blocks.json"
    pub_out = json.dumps({"id": "p", "url": "https://u", "mode": "create"}).encode()
    rec = _stub_stages(monkeypatch, publish_rc=0, publish_stdout=pub_out)
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create",
              "--blocks-out", str(blocks))
    assert IPP.main() == 0
    render_args = [r for r in rec if r[0] == "render"][0][1]
    assert str(blocks) in render_args


def test_main_default_manifest_missing_exits_2(monkeypatch, capsys, tmp_path):
    # F-0110: --manifest 未指定でも out_dir 既定 notion-manifest.json を検査し、不在なら exit 2。
    intake = _intake(tmp_path, manifest=False)
    _stub_stages(monkeypatch)
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create")
    assert IPP.main() == 2
    assert "notion-manifest.json" in capsys.readouterr().err
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["stage"] == "manifest_missing"


def test_main_skip_assets_flag_skips_verification(monkeypatch, capsys, tmp_path):
    # F-0110: 明示 --skip-assets (CI/テスト専用) のみ verify_assets を skip できる。
    intake = _intake(tmp_path, manifest=False)
    pub_out = json.dumps({"id": "p", "url": "https://u", "mode": "create"}).encode()
    rec = _stub_stages(monkeypatch, publish_rc=0, publish_stdout=pub_out)
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create", "--skip-assets")
    assert IPP.main() == 0
    assert not any(r[0] == "verify_assets" for r in rec)


def test_main_default_manifest_autoresolved_runs_assets(monkeypatch, capsys, tmp_path):
    # F-0110: --manifest 未指定でも out_dir 既定パスを自動解決して verify_assets が常時実行される。
    intake = _intake(tmp_path)
    pub_out = json.dumps({"id": "p", "url": "https://u", "mode": "create"}).encode()
    rec = _stub_stages(monkeypatch, publish_rc=0, publish_stdout=pub_out)
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create")
    assert IPP.main() == 0
    assets = [r for r in rec if r[0] == "verify_assets"]
    assert len(assets) == 1
    assert assets[0][1] == [str(tmp_path / "notion-manifest.json")]


def test_main_first_publish_translates_notion_target(monkeypatch, capsys, tmp_path):
    # F-0109: 初回 (url/result 不在, --revise/--allow-create 無し) は intake.json の
    # notion_target (mode=create-explicit, allow_create=true) を --allow-create へ翻訳する。
    payload = json.dumps({"notion_target": {"mode": "create-explicit", "allow_create": True}})
    intake = _intake(tmp_path, payload=payload)
    pub_out = json.dumps({"id": "p", "url": "https://u", "mode": "create"}).encode()
    rec = _stub_stages(monkeypatch, publish_rc=0, publish_stdout=pub_out)
    _set_argv(monkeypatch, "--intake", str(intake))
    assert IPP.main() == 0
    pub_cmd = [r for r in rec if r[0] == "publish_proc"][0][1]
    assert "--allow-create" in pub_cmd


def test_main_first_publish_translation_requires_allow_create_true(monkeypatch, capsys, tmp_path):
    # F-0109: notion_target.allow_create が true でなければ翻訳せず fail-closed (exit 51)。
    payload = json.dumps({"notion_target": {"mode": "create-explicit", "allow_create": False}})
    intake = _intake(tmp_path, payload=payload)
    _set_argv(monkeypatch, "--intake", str(intake))
    assert IPP.main() == 51


def test_main_first_publish_translation_skipped_when_republish_artifacts_exist(monkeypatch, capsys, tmp_path):
    # F-0109: notion-url.txt が既存 (=再公開局面) なら初回翻訳を発動しない → 既定 fail-closed 51。
    payload = json.dumps({"notion_target": {"mode": "create-explicit", "allow_create": True}})
    intake = _intake(tmp_path, payload=payload)
    (tmp_path / "notion-url.txt").write_text("https://www.notion.so/x\n", encoding="utf-8")
    _set_argv(monkeypatch, "--intake", str(intake))
    assert IPP.main() == 51


def test_main_first_publish_translation_skipped_when_result_has_page_id(monkeypatch, capsys, tmp_path):
    # notion-publish-result.json に page_id が実在すれば再公開局面 → 初回翻訳を発動しない (51)。
    payload = json.dumps({"notion_target": {"mode": "create-explicit", "allow_create": True}})
    intake = _intake(tmp_path, payload=payload)
    (tmp_path / "notion-publish-result.json").write_text(
        json.dumps({"page_id": "12345678-1234-1234-1234-123456789abc"}), encoding="utf-8")
    _set_argv(monkeypatch, "--intake", str(intake))
    assert IPP.main() == 51


def test_main_first_publish_stage_failure_then_retry_recovers(monkeypatch, capsys, tmp_path):
    # リトライ・デッドエンド regression: 初回 publish が stage 失敗 (assets 欠落 exit 2) しても
    # notion-url.txt を残さず、再実行で初回翻訳経路が再度有効になり --allow-create が伝搬する。
    payload = json.dumps({"notion_target": {"mode": "create-explicit", "allow_create": True}})
    intake = _intake(tmp_path, payload=payload)

    # 1回目: verify_assets 失敗 → exit 2。空 notion-url.txt を残さない (log は書く)。
    _stub_stages(monkeypatch, assets_rc=2)
    _set_argv(monkeypatch, "--intake", str(intake))
    assert IPP.main() == 2
    assert not (tmp_path / "notion-url.txt").exists()
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["stage"] == "verify_assets"

    # 2回目 (原因解消後の再実行): 初回翻訳ゲートが再度有効 → --allow-create が publish へ伝搬。
    pub_out = json.dumps({"id": "p", "url": "https://u", "mode": "create"}).encode()
    rec = _stub_stages(monkeypatch, publish_rc=0, publish_stdout=pub_out)
    _set_argv(monkeypatch, "--intake", str(intake))
    assert IPP.main() == 0
    pub_cmd = [r for r in rec if r[0] == "publish_proc"][0][1]
    assert "--allow-create" in pub_cmd
    assert (tmp_path / "notion-url.txt").read_text(encoding="utf-8") == "https://u\n"


def test_main_first_publish_translation_survives_legacy_empty_url_file(monkeypatch, capsys, tmp_path):
    # 旧実装が残した空 notion-url.txt (失敗残置) があっても内容ベース判定で初回経路が有効。
    payload = json.dumps({"notion_target": {"mode": "create-explicit", "allow_create": True}})
    intake = _intake(tmp_path, payload=payload)
    (tmp_path / "notion-url.txt").write_text("", encoding="utf-8")
    pub_out = json.dumps({"id": "p", "url": "https://u", "mode": "create"}).encode()
    rec = _stub_stages(monkeypatch, publish_rc=0, publish_stdout=pub_out)
    _set_argv(monkeypatch, "--intake", str(intake))
    assert IPP.main() == 0
    pub_cmd = [r for r in rec if r[0] == "publish_proc"][0][1]
    assert "--allow-create" in pub_cmd


def test_main_publish_invalid_stdout_json_treated_failed(monkeypatch, capsys, tmp_path):
    # publish が exit 0 だが stdout が壊れた JSON → url 取れず status=failed だが
    # pub_status==0 なので 0 を返す (silent-fail 検知は log の status で表現)。
    intake = _intake(tmp_path)
    _stub_stages(monkeypatch, publish_rc=0, publish_stdout=b"not-json")
    _set_argv(monkeypatch, "--intake", str(intake), "--allow-create")
    assert IPP.main() == 0
    log = json.loads((tmp_path / "notion-log.json").read_text(encoding="utf-8"))
    assert log["status"] == "failed"  # url 不在のため
