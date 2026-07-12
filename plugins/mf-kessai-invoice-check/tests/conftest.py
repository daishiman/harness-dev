"""plugin-local テスト共通フィクスチャ: tenant 文脈の hermetic 化。

tenant 依存コード (tenant_runtime 経由の keychain service 解決等) は
「HARNESS_TENANT または .notion-config.json symlink」で active tenant を要求する。
開発機では repo-root の gitignore 対象 symlink が偶然存在するためテストが通るが、
CI のクリーン checkout には無く TenantConfigError で落ちる。企業非依存の合成
tenant を tmp に生成し HARNESS_ROOT + HARNESS_TENANT で明示選択することで、
どの環境でも同一の tenant 文脈を保証する (tenant-isolation 規約により
plugins/ 配下では実企業 slug を参照しない)。
"""
import json

import pytest

_TEST_TENANT = {
    "schema_version": 1,
    "slug": "test-tenant",
    "display_name": "Test Tenant",
    "keychain_prefix": "test-tenant",
    "credentials": {},
}


@pytest.fixture(autouse=True)
def _synthetic_tenant_env(monkeypatch, tmp_path):
    root = tmp_path / "harness-root"
    tenant_dir = root / "tenants" / "test-tenant"
    tenant_dir.mkdir(parents=True)
    (tenant_dir / "tenant.json").write_text(
        json.dumps(_TEST_TENANT), encoding="utf-8")
    monkeypatch.setenv("HARNESS_ROOT", str(root))
    monkeypatch.setenv("HARNESS_TENANT", "test-tenant")
