"""lint-notion-relations.py の Notion 3DB リレーション不変条件 lint を網羅検証する (scripts4 系列)。

対象 script:
  scripts/lint-notion-relations.py

network / Notion / keychain は一切叩かない:
  - `curl()` (subprocess.check_output で実 curl を起動) は subprocess.check_output を
    monkeypatch でメモリ stub に差し替え、method/URL/header/body 組み立てと HTTP code /
    JSON パースを実値で検証する。
  - `query_all()` / `main()` は `curl` / `notion_config` を monkeypatch して、実通信なしで
    ページネーション・各不変条件 (Rule1/2/3) の合格・違反・SKIP・exit code を genuine に検証する。
  - すべての I/O は monkeypatch + tmp_path に限定し repo を汚さない。

他ディレクトリの同名衝突を避けるため _r4 サフィックス。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-notion-relations.py"

# lint-notion-relations.py は import 時に plugins/harness-creator/scripts を sys.path へ入れて
# `import notion_config` する。module body をそのまま exec すれば解決される。
_SPEC = importlib.util.spec_from_file_location("lint_notion_relations_r4", SCRIPT)
LNR = importlib.util.module_from_spec(_SPEC)
sys.modules["lint_notion_relations_r4"] = LNR
_SPEC.loader.exec_module(LNR)


# ============================================================
# curl(): subprocess.check_output stub で method/URL/header/body 組み立て & パース検証
# ============================================================

class _FakeCheckOutput:
    """subprocess.check_output の置き換え。最後に渡された argv / body を記録し固定出力を返す。"""

    def __init__(self, http_code=200, payload=None, payload_raw=None):
        self.http_code = http_code
        self.payload = payload if payload is not None else {}
        self.payload_raw = payload_raw
        self.calls = []

    def __call__(self, cmd, *a, **kw):
        body_text = None
        if "--data-binary" in cmd:
            ref = cmd[cmd.index("--data-binary") + 1]
            assert ref.startswith("@")
            body_text = Path(ref[1:]).read_text()
        self.calls.append({"argv": cmd, "body": body_text})
        tail = self.payload_raw if self.payload_raw is not None else json.dumps(self.payload)
        return (f"{tail}\n__HTTP__{self.http_code}").encode()


def test_curl_get_builds_headers_and_parses(monkeypatch):
    fake = _FakeCheckOutput(http_code=200, payload={"results": [], "has_more": False})
    monkeypatch.setattr(subprocess, "check_output", fake)
    code, data = LNR.curl("POST", "https://api.notion.com/v1/x", "tok-123")
    assert code == 200
    assert data == {"results": [], "has_more": False}
    argv = fake.calls[0]["argv"]
    assert argv[0] == "curl"
    assert "-X" in argv and argv[argv.index("-X") + 1] == "POST"
    assert any(a == "Authorization: Bearer tok-123" for a in argv)
    assert any(a == "Notion-Version: 2022-06-28" for a in argv)
    assert any(a == "Content-Type: application/json" for a in argv)
    # body 無し → --data-binary 不在
    assert "--data-binary" not in argv
    assert fake.calls[0]["body"] is None


def test_curl_post_writes_body_tempfile_and_cleans_up(monkeypatch):
    fake = _FakeCheckOutput(http_code=200, payload={"results": []})
    monkeypatch.setattr(subprocess, "check_output", fake)
    body = {"page_size": 100, "start_cursor": "C2"}
    code, data = LNR.curl("POST", "https://api.notion.com/v1/databases/db/query", "tok", body=body)
    assert code == 200
    # body が一時ファイル経由で渡り内容一致
    sent = json.loads(fake.calls[0]["body"])
    assert sent == body
    # 一時ファイルは os.unlink で削除済
    ref = fake.calls[0]["argv"][fake.calls[0]["argv"].index("--data-binary") + 1]
    assert not Path(ref[1:]).exists()


def test_curl_empty_payload_returns_empty_dict(monkeypatch):
    fake = _FakeCheckOutput(http_code=204, payload_raw="")
    monkeypatch.setattr(subprocess, "check_output", fake)
    code, data = LNR.curl("POST", "https://api.notion.com/v1/x", "tok")
    assert code == 204
    assert data == {}


# ============================================================
# query_all(): ページネーション / エラー終了
# ============================================================

def test_query_all_single_page(monkeypatch):
    calls = []

    def fake_curl(method, url, tk, body=None):
        calls.append((method, url, body))
        return 200, {"results": [{"id": "p1"}, {"id": "p2"}], "has_more": False}

    monkeypatch.setattr(LNR, "curl", fake_curl)
    pages = LNR.query_all("DBID", "tok")
    assert [p["id"] for p in pages] == ["p1", "p2"]
    # 1 ページのみ。初回 body には start_cursor 無し
    assert len(calls) == 1
    assert "databases/DBID/query" in calls[0][1]
    assert calls[0][2] == {"page_size": 100}


def test_query_all_pagination_follows_cursor(monkeypatch):
    state = {"n": 0}

    def fake_curl(method, url, tk, body=None):
        state["n"] += 1
        if state["n"] == 1:
            assert "start_cursor" not in body
            return 200, {"results": [{"id": "a"}], "has_more": True, "next_cursor": "CUR2"}
        # 2 回目は前回の next_cursor を引き継ぐ
        assert body["start_cursor"] == "CUR2"
        return 200, {"results": [{"id": "b"}], "has_more": False}

    monkeypatch.setattr(LNR, "curl", fake_curl)
    pages = LNR.query_all("DBID", "tok")
    assert [p["id"] for p in pages] == ["a", "b"]
    assert state["n"] == 2


def test_query_all_http_error_exits_2(monkeypatch, capsys):
    monkeypatch.setattr(LNR, "curl", lambda *a, **k: (400, {"message": "bad"}))
    with pytest.raises(SystemExit) as ei:
        LNR.query_all("DBID", "tok")
    assert ei.value.code == 2
    assert "[ERR] query DBID: 400" in capsys.readouterr().out


# ============================================================
# main(): notion_config 解決 / 各不変条件 (Rule1/2/3) / SKIP / 違反 exit
# ============================================================

def _page(props):
    return {"id": "pg-" + str(id(props))[-4:], "properties": props}


def _hearing(rel_count):
    return _page({"紐づくプラグイン": {"relation": [{"id": f"r{i}"} for i in range(rel_count)]}})


def _improvement(rel_count, title="改善A"):
    return _page({
        "対象プラグイン": {"relation": [{"id": f"r{i}"} for i in range(rel_count)]},
        "要望タイトル": {"title": [{"plain_text": title}]},
    })


def _skill(name):
    return _page({"プラグイン名": {"title": [{"plain_text": name}]}})


def _wire_config(monkeypatch, *, cfg=None, token="tok", db_ids=None):
    """notion_config.require_or_skip / get_db_id を stub する共通ヘルパ。"""
    cfg = {"__path__": "x"} if cfg is None else cfg
    monkeypatch.setattr(LNR.notion_config, "require_or_skip", lambda *a, **k: (cfg, token))
    ids = db_ids if db_ids is not None else {
        "hearing-sheet": "HS", "skill-list": "SL", "improvement-request": "IR",
    }
    monkeypatch.setattr(LNR.notion_config, "get_db_id", lambda k, *a, **kw: ids.get(k))


def _wire_query(monkeypatch, by_db):
    """db_id -> ページ配列 の dict を query_all stub として配線する。"""
    def fake_query_all(db_id, tk):
        return by_db.get(db_id, [])
    monkeypatch.setattr(LNR, "query_all", fake_query_all)


def test_main_config_missing_returns_none(monkeypatch):
    # require_or_skip が (None, None) → 早期 return 0 相当 (関数は return 0)
    monkeypatch.setattr(LNR.notion_config, "require_or_skip", lambda *a, **k: (None, None))
    assert LNR.main() == 0


def test_main_missing_db_id_skips(monkeypatch, capsys):
    # db_id のいずれかが None → [SKIP] 出力して return 0
    _wire_config(monkeypatch, db_ids={"hearing-sheet": "HS", "skill-list": None,
                                      "improvement-request": "IR"})
    assert LNR.main() == 0
    out = capsys.readouterr().out
    assert "[SKIP]" in out and "skill-list" in out


def test_main_all_invariants_satisfied(monkeypatch, capsys):
    _wire_config(monkeypatch)
    _wire_query(monkeypatch, {
        "HS": [_hearing(0), _hearing(1)],          # ≤1 → OK
        "IR": [_improvement(1), _improvement(1, "改善B")],  # ==1 → OK
        "SL": [_skill("plugin-a"), _skill("plugin-b")],     # 重複なし → OK
    })
    assert LNR.main() is None  # 正常時は明示 return なし
    assert "[OK] all relation invariants satisfied" in capsys.readouterr().out


def test_main_rule1_hearing_relation_over_one(monkeypatch, capsys):
    _wire_config(monkeypatch)
    _wire_query(monkeypatch, {
        "HS": [_hearing(2)],   # 2 件 → 違反 (max 1)
        "IR": [],
        "SL": [],
    })
    with pytest.raises(SystemExit) as ei:
        LNR.main()
    assert ei.value.code == 1
    out = capsys.readouterr().out
    assert "[FAIL] 1 violation(s)" in out
    assert "紐づくプラグインが 2 件 (max 1)" in out


def test_main_rule2_improvement_zero_relations(monkeypatch, capsys):
    _wire_config(monkeypatch)
    _wire_query(monkeypatch, {
        "HS": [],
        "IR": [_improvement(0, "孤児要望")],   # 0 件 → 違反 (must be 1)
        "SL": [],
    })
    with pytest.raises(SystemExit) as ei:
        LNR.main()
    assert ei.value.code == 1
    out = capsys.readouterr().out
    assert "improvement-request '孤児要望': 対象プラグインが 0 件 (must be 1)" in out


def test_main_rule2_improvement_two_relations(monkeypatch, capsys):
    _wire_config(monkeypatch)
    _wire_query(monkeypatch, {
        "HS": [],
        "IR": [_improvement(2, "多重要望")],   # 2 件 → 違反 (must be 1)
        "SL": [],
    })
    with pytest.raises(SystemExit) as ei:
        LNR.main()
    assert ei.value.code == 1
    assert "対象プラグインが 2 件 (must be 1)" in capsys.readouterr().out


def test_main_rule3_skill_name_duplicate(monkeypatch, capsys):
    _wire_config(monkeypatch)
    dup1, dup2 = _skill("dup-plugin"), _skill("dup-plugin")
    _wire_query(monkeypatch, {
        "HS": [],
        "IR": [],
        "SL": [dup1, dup2, _skill("unique")],   # dup-plugin 2 件 → 違反
    })
    with pytest.raises(SystemExit) as ei:
        LNR.main()
    assert ei.value.code == 1
    out = capsys.readouterr().out
    assert "プラグイン名 'dup-plugin' が 2 件重複" in out
    # unique は違反に出ない
    assert "'unique'" not in out


def test_main_rule3_empty_title_skipped(monkeypatch, capsys):
    # title 空のページは重複カウント対象外 (continue)
    _wire_config(monkeypatch)
    empty1 = _page({"プラグイン名": {"title": []}})
    empty2 = _page({"プラグイン名": {"title": []}})
    _wire_query(monkeypatch, {"HS": [], "IR": [], "SL": [empty1, empty2]})
    assert LNR.main() is None
    assert "[OK]" in capsys.readouterr().out


def test_main_multiple_violations_aggregate(monkeypatch, capsys):
    _wire_config(monkeypatch)
    _wire_query(monkeypatch, {
        "HS": [_hearing(3)],                       # Rule1 違反
        "IR": [_improvement(0, "x")],              # Rule2 違反
        "SL": [_skill("d"), _skill("d")],          # Rule3 違反
    })
    with pytest.raises(SystemExit) as ei:
        LNR.main()
    assert ei.value.code == 1
    out = capsys.readouterr().out
    assert "[FAIL] 3 violation(s)" in out


def test_main_improvement_missing_title_defaults_empty(monkeypatch, capsys):
    # 要望タイトル プロパティが欠落でも KeyError にならず空文字で出る
    _wire_config(monkeypatch)
    page = _page({"対象プラグイン": {"relation": []}})  # 要望タイトル 無し, rel 0 → 違反
    _wire_query(monkeypatch, {"HS": [], "IR": [page], "SL": []})
    with pytest.raises(SystemExit) as ei:
        LNR.main()
    assert ei.value.code == 1
    assert "improvement-request '': 対象プラグインが 0 件" in capsys.readouterr().out


# ============================================================
# subprocess 経由: __main__ ガード (config 不在で SKIP/return) を実バイナリで確認
# ============================================================

def test_subprocess_runs_without_network(tmp_path):
    """実行環境に .notion-config.json が無い (NOTION_CONFIG_PATH を不在ファイルへ向ける)
    → require_or_skip(allow_skip 既定 False) が fail-closed で exit 2、もしくは設定が
    在れば走る。network へは到達しないことだけを保証する (返り値で確認)。"""
    import os
    env = dict(os.environ)
    # 存在しない config を明示指定 → find_config_path が FileNotFoundError を投げる経路。
    env["NOTION_CONFIG_PATH"] = str(tmp_path / "no-such-config.json")
    env.pop("NOTION_TOKEN", None)
    env.pop("INTAKE_ALLOW_ENV_TOKEN", None)
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, env=env, timeout=30,
    )
    # config 解決で fail-closed (exit 2) もしくは FileNotFoundError traceback(!=0)。
    # いずれにせよ network 到達前に停止する = returncode != 0。
    assert r.returncode != 0
