"""package-contract.json 構文正本 (36章 §schema) の fail-closed 回帰テスト。

HarnessHub-2ih / HarnessHub-65z (2026-07-21 検出):
  36章のインライン schema 例が `^PKG-(00[1-9]|01[0-5]|01[3][a-d])$` という古い pattern を
  抱えており (選択肢 `01[0-5]` が 013 を含むため無印 PKG-013 を受理してしまう)、構文正本
  `ref-pkg-contract/schemas/package-contract.schema.json` の pattern と乖離していた。その結果
  plugins/mf-kessai-invoice-check/references/package-contract.json が無印 PKG-013 を pkg_checks
  キーとして記録し、Draft 2020-12 検証で additionalProperties 違反になっていた。
  `make plugin-package-check` は advisory ラッパー経由で赤化しないため、この乖離は無言で残存した。

本テストが fail-closed で固定する不変条件:
  - 実 repo の全 plugin の package-contract.json が構文正本で PASS する (advisory を待たない)
  - 無印 PKG-013 は pkg_checks キーとして REJECT される (集約表示専用ラベルであり記録 ID ではない)
  - PKG-013a〜d の 4 sub-check は ACCEPT される
  - pkg-id-catalog.yaml の PKG ID 集合と構文正本 pattern の受理集合が完全一致する
  - 予約 ID (PKG-016/017) が catalog 上で `reserved: true` として区別されている

実 repo の plugins は一切書き換えず、否定ケースは全て in-memory の最小 contract で構築する。
"""
import json
import re
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
REF_PKG_CONTRACT = ROOT / "plugins" / "harness-creator" / "skills" / "ref-pkg-contract"
SCHEMA_PATH = REF_PKG_CONTRACT / "schemas" / "package-contract.schema.json"
CATALOG_PATH = REF_PKG_CONTRACT / "references" / "pkg-id-catalog.yaml"

UMBRELLA_ID = "PKG-013"
SUB_CHECK_IDS = ("PKG-013a", "PKG-013b", "PKG-013c", "PKG-013d")


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> "jsonschema.Draft202012Validator":
    return jsonschema.Draft202012Validator(_schema())


def _pkg_checks_pattern(schema: dict) -> str:
    """構文正本の pkg_checks patternProperties キー (受理 ID の正規表現) を 1 本だけ返す。"""
    patterns = list(schema["properties"]["pkg_checks"]["patternProperties"])
    assert len(patterns) == 1, f"pkg_checks の受理 pattern は 1 本であること: {patterns}"
    return patterns[0]


def _minimal_contract(pkg_ids) -> dict:
    """指定 PKG ID だけを pass で持つ最小 contract を組む (実 repo 非依存の判定用)。

    schema の必須キーは空の値で埋め、pkg_checks のキー以外で違反が出ないようにする。
    """
    return {
        "package_mode": "bundle",
        "plugin_name": "demo",
        "entry_points": {"skills": [], "agents": [], "commands": [], "hooks": []},
        "distribution": {},
        "depends_on": [],
        "runtime_dependencies": [],
        "codex_alternatives": {"commands": {}, "agents": {}, "hook_omissions": {}},
        "pkg_checks": {
            pkg_id: {"status": "pass", "last_run_at": "2026-06-19T00:00:00Z"}
            for pkg_id in pkg_ids
        },
    }


def _catalog_pkg_ids() -> set:
    return set(_catalog_entries())


def _catalog_entries() -> dict:
    return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))["pkg_ids"]


def _repo_contracts():
    return sorted(ROOT.glob("plugins/*/references/package-contract.json"))


# --- 実 repo 側の適合 (65z 受け入れ条件) ---------------------------------------

def test_repo_has_package_contracts():
    """glob が 0 件でも緑になる空振りを防ぐ。"""
    assert len(_repo_contracts()) >= 7


@pytest.mark.parametrize("contract_path", _repo_contracts(), ids=lambda p: p.parent.parent.name)
def test_repo_contract_validates_against_schema(contract_path):
    """全 plugin の package-contract.json が構文正本の Draft 2020-12 検証を PASS する。"""
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    errors = sorted(_validator().iter_errors(data), key=lambda e: list(e.path))
    assert not errors, "\n".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )


def test_no_repo_contract_records_umbrella_pkg013():
    """無印 PKG-013 を pkg_checks キーとして持つ plugin が 1 つも無い。"""
    offenders = [
        p.parent.parent.name
        for p in _repo_contracts()
        if UMBRELLA_ID in json.loads(p.read_text(encoding="utf-8")).get("pkg_checks", {})
    ]
    assert offenders == [], f"無印 {UMBRELLA_ID} は記録軸では不可 (36章 §無印 PKG-013 の扱い): {offenders}"


# --- PKG-013 の正本上の扱い (2ih / 65z 共通の pin) -----------------------------

def test_umbrella_pkg013_is_rejected_as_record_key():
    """無印 PKG-013 は集約表示専用ラベルであり pkg_checks キーとして受理されない。"""
    errors = list(_validator().iter_errors(_minimal_contract([UMBRELLA_ID])))
    assert errors, f"{UMBRELLA_ID} が pkg_checks キーとして受理されている (schema が広すぎる)"
    assert any(UMBRELLA_ID in e.message for e in errors)


@pytest.mark.parametrize("sub_id", SUB_CHECK_IDS)
def test_pkg013_sub_checks_are_accepted(sub_id):
    """PKG-013a〜d の 4 sub-check は記録軸で受理される。"""
    assert not list(_validator().iter_errors(_minimal_contract([sub_id])))


def test_umbrella_pkg013_absent_from_catalog():
    """一次情報カタログにも無印 PKG-013 は存在しない (schema と catalog の判断が一致)。"""
    ids = _catalog_pkg_ids()
    assert UMBRELLA_ID not in ids
    assert set(SUB_CHECK_IDS) <= ids


# --- catalog と schema の関係 --------------------------------------------------

# 受理 pattern の被検査母集団。PKG-001〜017 の無印と PKG-013a〜d を並べる。
CANDIDATE_IDS = [f"PKG-{n:03d}" for n in range(1, 18)] + list(SUB_CHECK_IDS)
RESERVED_IDS = {"PKG-016", "PKG-017"}


def _accepted_ids() -> set:
    """構文正本 pattern が受理する PKG ID 集合を候補母集団から求める。"""
    pattern = re.compile(_pkg_checks_pattern(_schema()))
    return {pkg_id for pkg_id in CANDIDATE_IDS if pattern.fullmatch(pkg_id)}


def test_catalog_and_schema_id_sets_match_exactly():
    """catalog の PKG ID 集合と構文正本 pattern の受理集合が完全一致する。

    予約 ID (PKG-016/017) も catalog に `reserved: true` エントリとして実在するため、
    両者は部分集合ではなく厳密一致で固定できる。片方だけ更新すると必ず赤くなる。
    """
    accepted = _accepted_ids()
    catalog = _catalog_pkg_ids()
    assert catalog - accepted == set(), f"catalog にあるが schema が受理しない ID: {sorted(catalog - accepted)}"
    assert accepted - catalog == set(), f"schema が受理するが catalog 未定義の ID: {sorted(accepted - catalog)}"


def test_reserved_ids_are_flagged_in_catalog():
    """予約 ID は catalog 上で `reserved: true` として区別される。

    予約 ID を実装して flag を落とした時点で本 assert が赤くなり、36章 §予約 ID 表と
    27章 §4.1 governance の同時更新を強制する (静かに通さない)。
    """
    entries = _catalog_entries()
    flagged = {pkg_id for pkg_id, spec in entries.items() if spec.get("reserved") is True}
    assert flagged == RESERVED_IDS, (
        f"catalog の予約 ID 集合が 36章 §予約 ID (PKG-016〜017) と不一致: {sorted(flagged)}"
    )
    # 予約中の ID は実装 script を持たない (持っていれば予約状態の解除漏れ)
    assert all(entries[pkg_id].get("script") is None for pkg_id in flagged)
