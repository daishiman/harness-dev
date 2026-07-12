#!/usr/bin/env python3
"""PreToolUse hook `guard-mfk-readonly.py` の参照専用ガード回帰テスト。

このテストは guard の **現行の実挙動** を忠実に固定する (理想化しない)。守るべき不変条件:
  - MF掛け払いホスト(api.mfkessai.co.jp / sandbox-api.mfkessai.co.jp)宛ての Bash 変更系
    (POST/PUT/PATCH/DELETE / --data 系) は exit 2 で遮断される (参照専用の第1層)。
  - MF への GET(参照)は exit 0 で許可される。
  - Notion(api.notion.com)宛ての書き込みは guard 対象外で exit 0 (MFは読むだけ・
    Notionは書く の一方向設計)。
  - 別ホスト宛ての変更系が同一行に共起しても、MF への変更系でなければ誤遮断しない
    (CL5-A4-005 精度改善)。ただしホスト不明な変更系断片は fail-closed で遮断する
    (遮断を弱めない)。

guard はファイル名にハイフンを含むため通常 import できない。importlib の
SourceFileLoader でモジュールとしてロードし `main()` を直接呼ぶ経路と、実 hook を
subprocess で起動して exit code を見る経路の両方で境界を固定する。manifest の実配線は
Bash matcher だが、module-level の汎用 payload 判定も退行防止として固定する。
"""
import importlib.util
import io
import json
import os
import subprocess
import sys

import pytest


_HOOK_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "hooks", "guard-mfk-readonly.py")
)


def _load_guard():
    """ハイフン入りファイル名の hook を module として動的ロードする。"""
    spec = importlib.util.spec_from_file_location("guard_mfk_readonly", _HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = _load_guard()


def _run_main(payload, monkeypatch):
    """guard.main() を payload を stdin に差し込んで実行し戻り値(exit code相当)を返す。"""
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps(payload, ensure_ascii=False))
    )
    # main() は stderr に書くことがあるので捨て先を確保 (アサーションには使わない)。
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    return guard.main()


def _run_subprocess(payload):
    """実 hook を subprocess で起動し returncode を返す (本番の起動経路を再現)。"""
    proc = subprocess.run(
        [sys.executable, _HOOK_PATH],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stderr


def _bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# --- (block=遮断 exit 2) MF 宛ての変更系: 参照専用担保の中核 ---------------------
BLOCK_CASES = [
    ("mf_curl_x_post", _bash("curl -X POST https://api.mfkessai.co.jp/v3/billings")),
    ("mf_uppercase_host_post", _bash("curl -X POST https://API.MFKESSAI.CO.JP/v3/billings")),
    ("mf_curl_x_put", _bash("curl -X PUT https://api.mfkessai.co.jp/v3/x")),
    ("mf_curl_x_patch", _bash("curl -X PATCH https://api.mfkessai.co.jp/v3/x")),
    ("mf_curl_x_delete", _bash("curl -X DELETE https://api.mfkessai.co.jp/v3/x")),
    ("mf_request_post", _bash("curl --request POST https://api.mfkessai.co.jp/v3/x")),
    ("mf_curl_data", _bash("curl --data foo https://api.mfkessai.co.jp/v3/billings")),
    ("mf_curl_data_short", _bash("curl -d foo https://api.mfkessai.co.jp/v3/x")),
    ("mf_curl_form", _bash("curl --form a=b https://api.mfkessai.co.jp/v3/x")),
    (
        "sandbox_mf_post",
        _bash("curl -X POST https://sandbox-api.mfkessai.co.jp/v3/billings"),
    ),
    (
        "mf_list_form_post",
        _bash('subprocess.run(["curl","-X","POST","https://api.mfkessai.co.jp/x"])'),
    ),
    (
        "mf_python_method_kwarg",
        _bash("requests.post('https://api.mfkessai.co.jp/x', json={})"),
    ),
    # 非 Bash tool の tool_input JSON 経路: method:"POST" を取りこぼさない (遮断強化)。
    (
        "webfetch_method_post",
        {
            "tool_name": "WebFetch",
            "tool_input": {
                "url": "https://api.mfkessai.co.jp/v3/billings",
                "method": "POST",
            },
        },
    ),
    # MF GET と MF POST が同一行: MF への変更系があるので遮断。
    (
        "mf_get_then_mf_post",
        _bash(
            "curl https://api.mfkessai.co.jp/a && curl -X POST https://api.mfkessai.co.jp/b"
        ),
    ),
    # 別ホスト GET と MF POST が共起: MF への変更系断片があるので遮断。
    (
        "notion_get_then_mf_post",
        _bash(
            "curl https://api.notion.com/x ; curl -X POST https://api.mfkessai.co.jp/y"
        ),
    ),
    # 変数間接で MF URL を $U に逃がし別所で -X POST: ホスト不明断片は fail-closed で遮断。
    (
        "mf_url_var_then_post",
        _bash('U=https://api.mfkessai.co.jp/a ; curl -X POST "$U"'),
    ),
]


# --- (allow=許可 exit 0) ---------------------------------------------------------
ALLOW_CASES = [
    # MF への GET(参照)は許可。
    ("mf_curl_get_implicit", _bash("curl https://api.mfkessai.co.jp/v3/billings")),
    ("mf_curl_get_explicit", _bash("curl -X GET https://api.mfkessai.co.jp/v3/billings")),
    # Notion 書き込みは guard 対象外 (mfkessai host を含まない)。
    ("notion_post_only", _bash("curl -X POST https://api.notion.com/v1/pages")),
    # mfkessai を一切含まない任意コマンド。
    ("unrelated_post", _bash("curl -X POST https://example.com/x")),
    # MF GET と Notion POST の同一行共起: MF への変更系ではないので誤遮断しない。
    (
        "mf_get_and_notion_post_cooccur",
        _bash(
            "curl https://api.mfkessai.co.jp/v3/billings && "
            "curl -X POST https://api.notion.com/v1/pages"
        ),
    ),
    # MF GET と Notion --data の別断片共起: 別ホスト宛て変更系は無視。
    (
        "mf_get_and_notion_data_segment",
        _bash(
            "curl https://api.mfkessai.co.jp/a ; curl -d @b.json https://api.notion.com/c"
        ),
    ),
]


@pytest.mark.parametrize("name,payload", BLOCK_CASES, ids=[c[0] for c in BLOCK_CASES])
def test_main_blocks_mf_mutations(name, payload, monkeypatch):
    """MF 宛ての変更系は guard.main() が 2 を返す (遮断)。"""
    assert _run_main(payload, monkeypatch) == 2


@pytest.mark.parametrize("name,payload", ALLOW_CASES, ids=[c[0] for c in ALLOW_CASES])
def test_main_allows_reads_and_offhost_writes(name, payload, monkeypatch):
    """MF GET / Notion 書き込み / 無関係コマンドは guard.main() が 0 を返す (許可)。"""
    assert _run_main(payload, monkeypatch) == 0


def test_subprocess_blocks_mf_post_with_exit_2_and_message():
    """本番の起動経路(subprocess)でも MF POST は exit 2 で、理由を stderr に出す。"""
    rc, stderr = _run_subprocess(
        _bash("curl -X POST https://api.mfkessai.co.jp/v3/billings")
    )
    assert rc == 2
    assert "guard-mfk-readonly" in stderr
    assert "変更系" in stderr


def test_subprocess_allows_mf_get_with_exit_0():
    """本番の起動経路(subprocess)で MF GET は exit 0 で通過し stderr は空。"""
    rc, stderr = _run_subprocess(_bash("curl https://api.mfkessai.co.jp/v3/billings"))
    assert rc == 0
    assert stderr == ""


def test_invalid_json_stdin_is_fail_open_to_zero():
    """stdin が JSON でないとき guard は 0 を返す (現行挙動: hook を素通りさせる)。

    これは「hook 自身のクラッシュで全 Bash をブロックしない」現行設計の固定。
    遮断対象の検出は host 文字列 in text を前提とするため、解釈不能入力は通す。
    """
    proc = subprocess.run(
        [sys.executable, _HOOK_PATH],
        input="this-is-not-json",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0


def test_missing_tool_input_does_not_crash():
    """tool_input 欠落でも例外を投げず 0 (host を含まないので許可)。"""
    proc = subprocess.run(
        [sys.executable, _HOOK_PATH],
        input=json.dumps({"tool_name": "Bash"}),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0


def test_non_bash_tool_dumps_tool_input_json_for_scan():
    """非 Bash tool は tool_input 全体を JSON 化して走査する (host が JSON 内にある経路)。

    mfkessai host を含むが変更系の痕跡が無ければ許可される (GET 相当)。
    """
    payload = {
        "tool_name": "WebFetch",
        "tool_input": {"url": "https://api.mfkessai.co.jp/v3/billings"},
    }
    rc, _ = _run_subprocess(payload)
    assert rc == 0


def test_host_constant_covers_both_production_and_sandbox():
    """_HOST が production/sandbox 両ホストの部分文字列であることを構造的に固定。"""
    assert guard._HOST == "mfkessai.co.jp"
    assert guard._HOST in "api.mfkessai.co.jp"
    assert guard._HOST in "sandbox-api.mfkessai.co.jp"


def test_is_mutation_helper_returns_false_when_host_absent():
    """`_is_mutation_for_mfkessai` 単体: host を含まないテキストは即 False。

    main() は host チェックを先に通すため、この早期 return をヘルパ直叩きで固定する。
    """
    assert guard._is_mutation_for_mfkessai("curl -X POST https://api.notion.com") is False


def test_main_returns_zero_on_unparsable_stdin(monkeypatch):
    """stdin が JSON でないとき main() は例外を握りつぶして 0 を返す (in-process 固定)。"""
    monkeypatch.setattr(sys, "stdin", io.StringIO("not-json-at-all"))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    assert guard.main() == 0


def test_helper_fail_closed_on_unknown_host_segment():
    """ホスト不明断片(URL リテラル無し)は『別ホストと断定』しない = 判定対象に残す。

    遮断を弱めない安全側 (fail-closed) の中核ロジックを直接固定する。
    """
    # URL リテラルが無い断片 -> 安全に別ホストと断定できない -> False。
    assert guard._segment_is_safely_non_mfkessai('curl -X POST "$U"') is False
    # 明示的に別ホスト URL のみの断片 -> 別ホストと断定できる -> True。
    assert (
        guard._segment_is_safely_non_mfkessai("curl -X POST https://api.notion.com/x")
        is True
    )
    # mfkessai URL を含む断片 -> 別ホストではない -> False (判定対象に残す)。
    assert (
        guard._segment_is_safely_non_mfkessai(
            "curl -X POST https://api.mfkessai.co.jp/x"
        )
        is False
    )
