"""lint-marketplace-install-docs.py の検出ロジック回帰テスト。

README の install 導線が実体からズレる事故 (リポジトリ改名で
`manju/skills` が取り残された / plugin 改名で `skill-creator` が実体を失った)
を捕捉する lint 自身が腐らないよう、検出/許容の各分岐を機械保証する。

検証する不変条件:
  M1 リポジトリ名不一致 → 検出 / 一致・ローカル手順の絶対パス・プレースホルダ → 許容
  M2 実在しない marketplace 名 → 検出
  M3 marketplace 未登録の plugin を install 案内 → 検出 (非配布ならヒントを添える)
  M4 実在しない plugin のスラッシュコマンド → 検出
  実 repo の README が PASS すること (統合)

import 経路: dash 入り script のため importlib.util.spec_from_file_location
(test_lint_readme_plugin_root_portability.py のパターンに倣う)。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-marketplace-install-docs.py"
SPEC = importlib.util.spec_from_file_location("lint_marketplace_install_docs", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

REPO = "owner/repo"
CATALOGS = {
    "skills": {"alpha", "beta", "skills-full"},
    "harness-local": {"alpha", "beta", "internal-only"},
}
ON_DISK = {"alpha", "beta", "internal-only"}


def check(text: str) -> list[str]:
    return MOD.check_install_docs(text, REPO, CATALOGS, ON_DISK)


def codes(text: str) -> list[str]:
    """違反メッセージから M1..M4 のコードだけ取り出す。"""
    out = []
    for e in check(text):
        for c in ("M1", "M2", "M3", "M4"):
            if f" {c} " in e:
                out.append(c)
    return out


# --- M1: marketplace add のリポジトリ名 -----------------------------------


def test_m1_detects_stale_repository_name():
    assert codes("/plugin marketplace add manju/skills") == ["M1"]


def test_m1_allows_matching_repository_name():
    assert check(f"/plugin marketplace add {REPO}") == []


def test_m1_allows_marketplace_name_for_update_and_remove():
    # `marketplace update skills` は marketplace 名指定であってリポジトリ名ではない
    assert check("/plugin marketplace update skills\n/plugin marketplace remove skills") == []


def test_m1_ignores_local_marketplace_absolute_path_and_placeholder():
    text = (
        "/plugin marketplace add /Users/me/harness/marketplaces/local\n"
        "/plugin marketplace add <出力された絶対パス>\n"
        "/plugin marketplace add harness-local\n"
    )
    assert check(text) == []


def test_m1_strips_surrounding_backticks():
    assert codes("`/plugin marketplace add manju/skills`") == ["M1"]


# --- M2/M3: install 対象 ---------------------------------------------------


def test_m2_detects_unknown_marketplace_name():
    assert codes("/plugin install alpha@nosuchmarket") == ["M2"]


def test_m3_detects_plugin_not_registered_in_marketplace():
    assert codes("/plugin install nonexistent@skills") == ["M3"]


def test_m3_hints_local_route_for_non_distributable_plugin():
    """実体はあるが公開 marketplace に無い = 非配布。ローカル経路のヒントを出す。"""
    errs = check("/plugin install internal-only@skills")
    assert len(errs) == 1
    assert "ローカル marketplace 経由" in errs[0]


def test_m3_allows_bundle_name():
    assert check("/plugin install skills-full@skills") == []


def test_m3_allows_plugin_from_local_marketplace():
    assert check("/plugin install internal-only@harness-local") == []


def test_install_update_uninstall_are_all_checked():
    text = (
        "/plugin install nonexistent@skills\n"
        "/plugin update nonexistent@skills\n"
        "/plugin uninstall nonexistent@skills\n"
    )
    assert codes(text) == ["M3", "M3", "M3"]


# --- M4: スラッシュコマンドの plugin 名 -------------------------------------


def test_m4_detects_slash_command_for_missing_plugin():
    assert codes("/skill-creator:run-skill-create") == ["M4"]


def test_m4_allows_slash_command_for_existing_plugin():
    assert check("/alpha:run-something") == []


def test_m4_only_matches_line_start():
    # 散文中の `詳細は /alpha:run` のような途中出現は対象外 (行頭アンカー)
    assert check("詳細は /nosuch:run-x を参照") == []


# --- 統合: 実 repo の README -----------------------------------------------


def test_real_readme_passes():
    proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_repository_is_declared_in_marketplace_metadata():
    """SSOT である metadata.repository が欠けたら lint は exit 2 (入力不備) になる契約。"""
    import json

    mk = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    repository = mk.get("metadata", {}).get("repository")
    assert repository, "metadata.repository が install 導線の正本として必要"
    assert "/" in repository, f"<owner>/<repo> 形式であること: {repository!r}"
