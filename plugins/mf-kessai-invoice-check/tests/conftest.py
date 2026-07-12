"""plugin-local テスト共通フィクスチャ: tenant 文脈の hermetic 化。

tenant 依存コード (tenant_runtime 経由の keychain service 解決等) は
「HARNESS_TENANT または .notion-config.json symlink」で active tenant を要求する。
開発機では repo-root の gitignore 対象 symlink が偶然存在するためテストが通るが、
CI のクリーン checkout には無く TenantConfigError で落ちる。tracked な
tenants/xlocal/tenant.json を tmp へ複製し HARNESS_ROOT + HARNESS_TENANT で
明示選択することで、どの環境でも同一の tenant 文脈を保証する
(repo-root tests/conftest.py の xlocal_tenant_env と同型)。
"""
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _xlocal_tenant_env(monkeypatch, tmp_path):
    root = tmp_path / "harness-root"
    (root / "tenants" / "xlocal").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "tenants" / "xlocal" / "tenant.json",
                 root / "tenants" / "xlocal" / "tenant.json")
    monkeypatch.setenv("HARNESS_ROOT", str(root))
    monkeypatch.setenv("HARNESS_TENANT", "xlocal")
