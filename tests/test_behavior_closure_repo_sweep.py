"""実 repo 全 skill の behavior closure が解決可能であることを固定する sweep テスト。

HarnessHub-c8m (issue-behavior-closure-unresolvable-20260721) の再発防止。

`behavior_closure_files()` は宣言された依存を fail-closed で解決し、解決できない ref が
1 つでもあると例外を投げる。その skill は `skill_dir_tree_sha` を計算できず、
`plan-live-trials.py` が plugin 全体で停止するか、あるいは検証対象から静かに外れる。
「赤くなる」のではなく「無くなる」形の被覆欠落なので、状態を見る検査では気づけない。

そのため本テストは合成 fixture ではなく **実 repo の全 SKILL.md** を走査し、
(a) 宣言 ref が全て解決できること、(b) package-contract を持つ全 plugin で
entry point の digest が計算できること、の 2 点を機械検査で固定する。

closure の解決規則そのものの単体テストは tests/test_live_trial_harness.py 側にある。
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
LIVE_TRIAL_SCRIPTS = (
    ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-live-trial" / "scripts"
)


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(
        stem.replace("-", "_"), LIVE_TRIAL_SCRIPTS / f"{stem}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


verdict_mod = _load("live-trial-verdict")
plan_mod = _load("plan-live-trials")


def _skill_dirs() -> list[Path]:
    """実 repo の skill dir 一覧 (symlink 配備の重複は実体で 1 件に畳む)。

    run-skill-feedback のように単一 SSOT を全 plugin へ symlink 配備するものがあり、
    resolve() せずに数えると同じ実体を 22 回検査することになる。
    """
    seen: dict[Path, Path] = {}
    for skill_md in sorted(PLUGINS.glob("*/skills/*/SKILL.md")):
        seen.setdefault(skill_md.resolve().parent, skill_md.parent)
    return sorted(seen.values())


def _contract_plugins() -> list[Path]:
    return sorted(
        path.parent.parent
        for path in PLUGINS.glob("*/references/package-contract.json")
    )


# entry_points 未宣言の既知 2 件 (mf-kessai-invoice-check / slide-report-generator) は
# HarnessHub-btn で是正済みのため allowlist を空にした。以後は例外なく全 plugin が
# 計画可能であることを要求する。宣言漏れそのものの検査は
# tests/test_package_contract_entry_points.py が担当する。
ENTRY_POINTS_UNDECLARED: set[str] = set()


def test_every_skill_resolves_its_declared_behavior_closure():
    """全 skill で宣言 ref が解決でき digest を計算できる (解決不能 0 件)。"""
    unresolvable: list[str] = []
    for skill_dir in _skill_dirs():
        try:
            verdict_mod.skill_dir_tree_sha(skill_dir)
        except ValueError as exc:
            unresolvable.append(f"{skill_dir.relative_to(ROOT)}: {exc}")
    assert not unresolvable, (
        "declared behavior dependency が解決できず digest を計算できない skill がある "
        "(該当 skill は live-trial 証跡を取得できず検証対象から静かに外れる):\n  "
        + "\n  ".join(unresolvable)
    )


def test_sweep_covers_every_plugin_skill_tree():
    """sweep が空振り (vacuous pass) していないことを固定する。

    _skill_dirs() の glob が壊れる / plugin dir 構成が変わる / symlink 畳み込みが
    行き過ぎる、のいずれでも上の sweep は「0 件を検査して PASS」してしまう。
    これは本テストが再発防止しようとしている欠陥そのもの (検査対象が静かに消える) と
    同じ形なので、走査の網羅性を別途固定する。

    下限件数の閾値では skill を減らす正当な変更で赤くなり閾値更新が形骸化するため、
    「自前の skill 実体を持つ plugin は必ず sweep に現れる」という構成追随型の不変条件で縛る。
    """
    swept = _skill_dirs()
    covered = {skill_dir.parent.parent.name for skill_dir in swept}

    # 自前の skill 実体 (非 symlink) を持つ plugin。symlink のみの plugin
    # (run-skill-feedback だけを配備した skill-governance-* 等) は畳み込みで
    # SSOT 側 plugin に代表されるため、網羅性の期待対象から外す。
    expected = {
        plugin.name
        for plugin in PLUGINS.iterdir()
        if (plugin / ".claude-plugin" / "plugin.json").is_file()
        and any(
            not skill_dir.is_symlink()
            for skill_dir in plugin.glob("skills/*")
            if (skill_dir / "SKILL.md").is_file()
        )
    }
    assert expected, "plugin を 1 件も検出できない (走査起点 PLUGINS が壊れている)"
    assert not expected - covered, (
        "skill 実体を持つのに sweep へ 1 件も現れない plugin がある "
        "(glob か plugin dir 構成が壊れており closure 検査が素通りしている): "
        f"{sorted(expected - covered)}"
    )

    # symlink 畳み込みが効いており、かつ効きすぎていないこと
    total = len(list(PLUGINS.glob("*/skills/*/SKILL.md")))
    assert 0 < len(swept) <= total, (
        f"sweep 対象数が不正 (swept={len(swept)} total={total})"
    )


@pytest.mark.parametrize(
    "plugin_dir", _contract_plugins(), ids=lambda p: p.name
)
def test_declared_entry_points_are_planable(plugin_dir: Path):
    """package-contract を持つ plugin は entry point 全ての digest を計算できる。

    plan-live-trials.py は entry_points.skills を列挙して digest を取るため、
    1 skill でも解決不能だと plugin 全体の計画が fail-closed で止まる。
    """
    if plugin_dir.name in ENTRY_POINTS_UNDECLARED:
        # allowlist が是正後も残り続けて検査を素通りさせないよう、未宣言の実在を確認する
        with pytest.raises(ValueError):
            plan_mod._entry_skills(plugin_dir)
        pytest.skip("package-contract が entry_points 未宣言 (既知・別課題で是正)")
    for skill in plan_mod._entry_skills(plugin_dir):
        skill_dir = plugin_dir / "skills" / skill
        assert (skill_dir / "SKILL.md").is_file(), (
            f"{plugin_dir.name}: entry point の実体が無い: {skill}"
        )
        verdict_mod.skill_dir_tree_sha(skill_dir)
