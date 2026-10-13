"""lint-matrix.json の所在宣言 (owner_plugin / script_path) ↔ 実体ファイルの照合テスト。

lint-matrix.json は harness-creator に置かれた台帳だが、lint 実体は harness-creator
配下に限らない (skill-governance-lint / repo-root scripts/ にもある)。台帳が所在を
宣言していても実体が動けばズレるので、ズレたら赤くなる口をここに置く。

検査:
  (1) 全 lint が owner_plugin / script_path を宣言している (分母 = lints 件数)
  (2) script_path が実在する
  (3) script_path の basename が script フィールドと一致する
  (4) owner_plugin が script_path の配置と整合する
  (5) 検査対象が 0 件でない (floor guard: 台帳が空でも緑にならないようにする)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = REPO_ROOT / "plugins/harness-creator/references/lint-matrix.json"

# owner_plugin → script_path が満たすべき接頭辞
OWNER_PREFIX = {
    "harness-creator": "plugins/harness-creator/",
    "skill-governance-lint": "plugins/skill-governance-lint/",
    "repo-root": "scripts/",
}


def _lints() -> list[dict]:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    return matrix["lints"]


def test_matrix_has_lints() -> None:
    """floor guard: lints が空なら以降の parametrize が 0 件で緑になるため先に止める。"""
    lints = _lints()
    assert len(lints) >= 1, f"lints が空: {MATRIX_PATH}"


@pytest.mark.parametrize("lint", _lints(), ids=lambda l: l["id"])
def test_script_path_declared_and_exists(lint: dict) -> None:
    lint_id = lint["id"]
    owner = lint.get("owner_plugin")
    rel = lint.get("script_path")

    assert owner, f"{lint_id}: owner_plugin が未宣言 (実体の所有単位が台帳から読めない)"
    assert rel, f"{lint_id}: script_path が未宣言 (実体の所在が台帳から読めない)"
    assert owner in OWNER_PREFIX, (
        f"{lint_id}: 未知の owner_plugin={owner!r} (既知: {sorted(OWNER_PREFIX)})"
    )

    path = REPO_ROOT / rel
    assert path.is_file(), f"{lint_id}: script_path の実体が不在: {rel}"

    assert path.name == lint["script"], (
        f"{lint_id}: script_path の basename ({path.name}) が script ({lint['script']}) と不一致"
    )

    prefix = OWNER_PREFIX[owner]
    assert rel.startswith(prefix), (
        f"{lint_id}: owner_plugin={owner} なのに script_path が {prefix} 配下でない: {rel}"
    )
