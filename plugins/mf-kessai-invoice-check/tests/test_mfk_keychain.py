#!/usr/bin/env python3
"""mfk_keychain.py の鍵取得経路を subprocess/platform を mock して検証する (network 不要)。

守る契約: (1) service/account の解決順 env>config>default、(2) Keychain ヒット時は生値を返す、
(3) Keychain ミス時は MFK_API_KEY フォールバック、(4) 全滅時は KeychainError と正しい exit_code
(macOS=44 / 非macOS=9)、(5) mask が生値を出さない。生値の print 禁止を構造で固定する。
"""
import types

import pytest

import mfk_keychain as kc


# --- service/account 解決順 ---

def test_service_account_resolution_order(monkeypatch):
    monkeypatch.setenv("HARNESS_KEYCHAIN_PREFIX", "test-tenant")
    monkeypatch.delenv("MFK_KEYCHAIN_SERVICE", raising=False)
    monkeypatch.delenv("MFK_KEYCHAIN_ACCOUNT", raising=False)
    # active tenant から導出 (固定既定値は空)
    assert kc.DEFAULT_SERVICE == kc.DEFAULT_ACCOUNT == ""
    assert kc._service() == "mfkessai-api-key.test-tenant"
    assert kc._account() == "test-tenant"
    # config 上書き
    assert kc._service({"keychain_service": "svc-cfg"}) == "svc-cfg"
    assert kc._account({"keychain_account": "acc-cfg"}) == "acc-cfg"
    # env が最優先 (config より強い)
    monkeypatch.setenv("MFK_KEYCHAIN_SERVICE", "svc-env")
    monkeypatch.setenv("MFK_KEYCHAIN_ACCOUNT", "acc-env")
    assert kc._service({"keychain_service": "svc-cfg"}) == "svc-env"
    assert kc._account({"keychain_account": "acc-cfg"}) == "acc-env"


# --- 共通リゾルバ resolve_service (env > config > default) ---

def test_resolve_service_prefers_env_then_config_then_default(monkeypatch):
    """共通リゾルバが env > config > default の優先順を満たす (MF/Notion で共有する単一実装)。"""
    monkeypatch.delenv("SOME_ENV", raising=False)
    # default のみ
    assert kc.resolve_service("SOME_ENV", None, "dflt") == "dflt"
    # 空文字 config は未設定扱い → default
    assert kc.resolve_service("SOME_ENV", "", "dflt") == "dflt"
    # config 上書き
    assert kc.resolve_service("SOME_ENV", "cfg", "dflt") == "cfg"
    # env が最優先 (config より強い)
    monkeypatch.setenv("SOME_ENV", "env")
    assert kc.resolve_service("SOME_ENV", "cfg", "dflt") == "env"


def test_service_account_delegate_to_resolver(monkeypatch):
    """_service/_account はリファクタ後も共通リゾルバ経由で同じ既定/解決順を保つ。"""
    monkeypatch.delenv("MFK_KEYCHAIN_SERVICE", raising=False)
    monkeypatch.delenv("MFK_KEYCHAIN_ACCOUNT", raising=False)
    monkeypatch.setenv("HARNESS_KEYCHAIN_PREFIX", "test-tenant")
    assert kc.DEFAULT_SERVICE == kc.DEFAULT_ACCOUNT == ""
    assert kc._service() == "mfkessai-api-key.test-tenant"
    assert kc._account() == "test-tenant"


# --- 共通コア fetch_secret (旧 _from_keychain は委譲エイリアス) ---

def test_fetch_secret_returns_keychain_value(monkeypatch):
    monkeypatch.setattr(kc.sys, "platform", "darwin")
    monkeypatch.setattr(kc.subprocess, "run", _fake_run(returncode=0, stdout="raw\n"))
    assert kc.fetch_secret("svc", "acc") == "raw"           # 末尾改行を除く


def test_fetch_secret_none_on_failure_and_non_darwin(monkeypatch):
    monkeypatch.setattr(kc.sys, "platform", "darwin")
    monkeypatch.setattr(kc.subprocess, "run", _fake_run(returncode=1, stdout=""))
    assert kc.fetch_secret("svc", "acc") is None
    # 非macOS は security を呼ばずに None。
    monkeypatch.setattr(kc.sys, "platform", "linux")
    monkeypatch.setattr(kc.subprocess, "run",
                        lambda *a, **k: pytest.fail("非macOS で security を呼んではいけない"))
    assert kc.fetch_secret("svc", "acc") is None


def test_from_keychain_is_alias_of_fetch_secret(monkeypatch):
    """後方互換: _from_keychain は fetch_secret へ委譲する (既存呼出/テストを壊さない)。"""
    monkeypatch.setattr(kc.sys, "platform", "darwin")
    monkeypatch.setattr(kc.subprocess, "run", _fake_run(returncode=0, stdout="v\n"))
    assert kc._from_keychain("svc", "acc") == kc.fetch_secret("svc", "acc") == "v"


def test_default_notion_service_is_ssot():
    """Notion service 既定が mfk_keychain に SSOT 化されている (命名規約の一元管理)。"""
    assert kc.DEFAULT_NOTION_SERVICE == ""


# --- mask は生値を出さない ---

def test_mask_never_leaks_full_secret():
    assert kc.mask("") == "(empty)"
    assert kc.mask(None) == "(empty)"
    assert kc.mask("short6") == "(len=6)"          # <=6 は中身を出さない
    masked = kc.mask("abcdefghij")                  # 10 文字
    assert masked == "abcd...ij (len=10)"
    assert "efgh" not in masked                     # 中間は伏せられる


# --- Keychain ヒット ---

def _fake_run(returncode=0, stdout=""):
    def run(*args, **kwargs):
        return types.SimpleNamespace(returncode=returncode, stdout=stdout)
    return run


def test_get_api_key_returns_keychain_value(monkeypatch):
    monkeypatch.setattr(kc.sys, "platform", "darwin")
    monkeypatch.setattr(kc.subprocess, "run", _fake_run(returncode=0, stdout="s3cr3t\n"))
    # 末尾改行を除いた生値を返す。
    assert kc.get_api_key() == "s3cr3t"


def test_from_keychain_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr(kc.sys, "platform", "darwin")
    monkeypatch.setattr(kc.subprocess, "run", _fake_run(returncode=44, stdout=""))
    assert kc._from_keychain("svc", "acc") is None


def test_from_keychain_returns_none_on_non_darwin(monkeypatch):
    monkeypatch.setattr(kc.sys, "platform", "linux")
    # subprocess を呼ばずに None (security コマンドは macOS のみ)。
    monkeypatch.setattr(kc.subprocess, "run",
                        lambda *a, **k: pytest.fail("非macOS で security を呼んではいけない"))
    assert kc._from_keychain("svc", "acc") is None


# --- フォールバックとエラー ---

def test_keychain_miss_falls_back_to_env_key(monkeypatch):
    monkeypatch.setattr(kc.sys, "platform", "darwin")
    monkeypatch.setattr(kc.subprocess, "run", _fake_run(returncode=1, stdout=""))
    monkeypatch.setenv("MFK_API_KEY", "  env-key  ")
    assert kc.get_api_key() == "env-key"            # strip される


def test_all_sources_fail_on_darwin_raises_44(monkeypatch):
    monkeypatch.setattr(kc.sys, "platform", "darwin")
    monkeypatch.setattr(kc.subprocess, "run", _fake_run(returncode=1, stdout=""))
    monkeypatch.delenv("MFK_API_KEY", raising=False)
    with pytest.raises(kc.KeychainError) as ei:
        kc.get_api_key()
    assert ei.value.exit_code == 44


def test_non_darwin_without_env_raises_9(monkeypatch):
    monkeypatch.setattr(kc.sys, "platform", "linux")
    monkeypatch.delenv("MFK_API_KEY", raising=False)
    with pytest.raises(kc.KeychainError) as ei:
        kc.get_api_key()
    assert ei.value.exit_code == 9


def test_non_darwin_with_env_returns_key(monkeypatch):
    monkeypatch.setattr(kc.sys, "platform", "linux")
    monkeypatch.setenv("MFK_API_KEY", "ci-key")
    assert kc.get_api_key() == "ci-key"


# --- CLI main ---

def test_main_check_ok_masks_value(monkeypatch, capsys):
    monkeypatch.setattr(kc, "get_api_key", lambda service=None, account=None: "abcdefghij")
    monkeypatch.setattr(kc.sys, "argv", ["mfk_keychain.py", "--check"])
    assert kc.main() == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "abcdefghij" not in out                  # 生値は表示しない
    assert "(len=10)" in out


def test_main_returns_keychain_error_exit_code(monkeypatch):
    def boom(service=None, account=None):
        raise kc.KeychainError("missing", exit_code=44)
    monkeypatch.setattr(kc, "get_api_key", boom)
    monkeypatch.setattr(kc.sys, "argv", ["mfk_keychain.py", "--check"])
    assert kc.main() == 44
