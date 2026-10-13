"""配っている版が、版数を埋めた派生成果物すべてに届いていることを見る。

対象は 2 系統ある。どちらも**版数を入力にしながら bump の出力ではなかった**ために、
bump のたびに 1 版遅れるという同じ形の非対称だった。

  1. plugin 直下の CHANGELOG.md (CHANGELOG を持つ plugin 全件から導出)
  2. 版数と実数を本文へ埋めた doc (build-plugin-release の DERIVED_VERSION_SURFACES)

どちらの導出も 0 件へ落ちると空振りで緑になるため、下限 assert を置く。

この検査を x-longpost-creator の contract parity テストから切り出した理由。版数整合は
特定 plugin の契約ではなく repo 全体の不変条件だが、2026-10-10 22:26 の実測では
`tests/scripts-plugins/test_x_longpost_creator__contract_parity.py` の 1 本だけが
整合を見ており、**CHANGELOG を持つ 6 plugin が 6 件とも plugin.json とズレていた**のに
赤くなったのは 1 件だけだった。残り 5 件は検査が当たっていないので静かにズレ続けていた。
対象を plugin 側から導出すれば、新しい CHANGELOG が増えた時点で自動的に検査対象になる。

版数を取る口は repo 内に 1 つだけ置く (notifier-check.py の `_extract_latest_version`)。
ここで独自の正規表現を立てると、その書式で書いた plugin だけが検査に当たり、当たらない
書式へ逃げる圧力になる。
"""

import importlib.util
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGINS = ROOT / "plugins"

_NOTIFIER = (ROOT / "plugins" / "harness-creator" / "skills"
             / "run-skill-update-notifier" / "scripts" / "notifier-check.py")
_SPEC = importlib.util.spec_from_file_location("notifier_check_changelog_parity", _NOTIFIER)
NOTIFIER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(NOTIFIER)

# 実測した下限 (2026-10-10 22:30 時点で 6 件)。対象を plugin 側から導出する検査は、
# 導出が 0 件へ落ちると「全件 OK」の顔で緑になる。分母の下限を置いて空振りを潰す。
# plugin や CHANGELOG を意図的に減らしたときはこの数と測定時刻を一緒に更新する。
_MINIMUM_TARGETS = 6


def _targets() -> list[Path]:
    return sorted(
        d for d in PLUGINS.iterdir()
        if (d / "CHANGELOG.md").is_file()
        and (d / ".claude-plugin" / "plugin.json").is_file()
    )


def test_changelog_head_version_matches_the_distributed_version():
    targets = _targets()
    assert len(targets) >= _MINIMUM_TARGETS, (
        f"CHANGELOG を持つ plugin が {len(targets)} 件しか見つからない "
        f"(下限 {_MINIMUM_TARGETS})。検査が空振りしている可能性がある"
    )

    mismatched = []
    for plugin in targets:
        manifest = json.loads(
            (plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        changelog_version = NOTIFIER._extract_latest_version(plugin / "CHANGELOG.md")
        if changelog_version != manifest["version"]:
            mismatched.append(
                f"{plugin.name}: plugin.json={manifest['version']} "
                f"CHANGELOG={changelog_version}"
            )

    assert not mismatched, (
        "配っている版の節が CHANGELOG に無い plugin がある。\n"
        "python3 scripts/build-plugin-release.py が採番と同じ工程で節を足すので、"
        "手で直す前にそれを回す。\n  " + "\n  ".join(mismatched)
    )


def test_release_script_writes_the_changelog_it_also_reads():
    """CHANGELOG を採番の出力として扱う実装が在ることを見る。

    上のテストは「今ズレていない」ことしか言わない。追記ロジックを外しても、その場では
    緑のまま次の bump で初めて赤くなる — 壊れたことが分かるのが遅すぎる。採番工程
    (write_version) が CHANGELOG へ書く経路そのものを固定する。
    """
    script = (ROOT / "scripts" / "build-plugin-release.py").read_text(encoding="utf-8")
    assert "def sync_changelog_section(" in script
    write_version_body = script.split("def write_version(", 1)[1].split("\ndef ", 1)[0]
    assert "sync_changelog_section(" in write_version_body, (
        "write_version() が CHANGELOG を書いていない。4 面だけ更新して CHANGELOG を"
        "置き去りにすると、bump のたびに版数整合が 1 版遅れる"
    )

    # 読む側と書く側で版見出しの形が違うと、書いた節が読まれないという最も静かな
    # 壊れ方をする。両者の正規表現が同一であることを突き合わせる。
    notifier_src = _NOTIFIER.read_text(encoding="utf-8")
    pattern = r"\^##\\s\*\\\[\?v\?\(\\d\+\\\.\\d\+\\\.\\d\+\[\^\\\]\\s\]\*\)"
    assert re.search(pattern, notifier_src), "notifier 側の版見出し正規表現が変わった"
    assert re.search(pattern, script), (
        "build-plugin-release 側の版見出し正規表現が notifier 側と揃っていない"
    )


# ── 版数を埋めた派生成果物 ─────────────────────────────────────────

# 実測した下限 (2026-10-10 22:40 時点で 2 件: doc/harness-creator-完全解剖.md の
# version/inventory 行と skill 数の行)。宣言テーブルを走る検査は、宣言が 0 件へ
# 落ちると「全件 OK」の顔で緑になる。下限を置いて空振りを潰す。宣言を意図的に
# 減らしたときはこの数と測定時刻を一緒に更新する。
_MINIMUM_DERIVED_SURFACES = 2


def _release_module():
    spec = importlib.util.spec_from_file_location(
        "build_plugin_release_for_derived", ROOT / "scripts" / "build-plugin-release.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_declared_derived_surfaces_hold_the_distributed_facts():
    """宣言された派生成果物が、今配っている版数と実数を書いていること。

    CHANGELOG と同じ非対称 (版数を入力にしながら bump の出力ではない) が
    doc/harness-creator-完全解剖.md にもあり、2026-10-10 22:19 の bump 後に 1.4.45 の
    まま残って tests/test_harness_creator_dissection_doc.py が落ちた。宣言テーブルを
    走ることで、同じ形の成果物が増えても宣言 1 行で同じ検査に乗る。
    """
    mod = _release_module()
    declared = mod.DERIVED_VERSION_SURFACES
    assert len(declared) >= _MINIMUM_DERIVED_SURFACES, (
        f"派生成果物の宣言が {len(declared)} 件しかない "
        f"(下限 {_MINIMUM_DERIVED_SURFACES})。検査が空振りしている可能性がある"
    )

    stale = []
    for name, relative, pattern, template in declared:
        plugin = PLUGINS / name
        assert (plugin / ".claude-plugin" / "plugin.json").is_file(), (
            f"宣言の plugin 名 {name} が実在しない"
        )
        path = ROOT / relative
        assert path.is_file(), f"宣言された派生成果物 {relative} が無い"
        text = path.read_text(encoding="utf-8")
        version = json.loads(
            (plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )["version"]
        expected = template.format(**mod._plugin_facts(plugin, version))
        found = re.findall(pattern, text)
        # 1 件も当たらないのは「古い」ではなく「宣言と文面が食い違っている」で、
        # 追従の仕組みが在るのに効かない状態。古い値と同じ重さで落とす。
        assert found, f"{relative}: {pattern!r} が 1 件も当たらない"
        for actual in found:
            if actual != expected:
                stale.append(f"{relative}: {actual!r} (期待 {expected!r})")

    assert not stale, (
        "版数を埋めた派生成果物が実数と食い違っている。\n"
        "python3 scripts/build-plugin-release.py が採番と同じ工程で書き直すので、"
        "手で直す前にそれを回す。\n  " + "\n  ".join(stale)
    )


def test_release_script_writes_the_derived_surfaces_it_also_checks():
    """採番工程が派生成果物へ書く経路そのものを固定する。

    上のテストは「今ズレていない」ことしか言わない。追従を外しても、その場では緑の
    まま次の bump で初めて赤くなる。
    """
    script = (ROOT / "scripts" / "build-plugin-release.py").read_text(encoding="utf-8")
    assert "def sync_derived_version_surfaces(" in script
    write_version_body = script.split("def write_version(", 1)[1].split("\ndef ", 1)[0]
    assert "sync_derived_version_surfaces(" in write_version_body, (
        "write_version() が派生成果物を書き直していない。版数を埋めた doc は bump の"
        "たびに 1 版遅れる"
    )
