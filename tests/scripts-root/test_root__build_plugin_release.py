"""build-plugin-release.py の不変条件を固定する。

守りたいのは 3 点:
  1. 採番が「キャッシュディレクトリ名の衝突」を起こさないこと。version は
     ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/ の名前になり、
     `+` が `-` へ潰れる。潰れた結果が同名だと、新版を install したつもりで
     古い copy を見続ける無音故障になる。
  2. version 上げ忘れを --check が fail-closed で捕まえること。symlink projection を
     廃止した以上、上げ忘れ = 反映されない、が唯一の故障モードである。
  3. bump が plugin.json の整形を巻き添えにしないこと。整形差分は内容 hash を
     動かし、bump が次の bump を呼ぶ自己増殖になる。
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-plugin-release.py"
FINGERPRINTS = ROOT / "marketplaces" / "local" / "plugin-fingerprints.json"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("build_plugin_release", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── 採番 ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        ("0.2.0", "0.2.1"),
        ("1.3.0+codex.20260713-1", "1.3.1"),
        ("0.1.9", "0.1.10"),
        ("2.0.0-rc.1", "2.0.1"),
    ],
)
def test_next_version_bumps_patch_and_drops_metadata(mod, current, expected):
    assert mod.next_version(current) == expected


@pytest.mark.parametrize("bad", ["1.3", "latest", "v1.2.3", "1.2.x", ""])
def test_unparseable_version_stops_instead_of_guessing(mod, bad):
    """握り潰すと誤った version を plugin.json へ書き込み、対応が壊れる。"""
    with pytest.raises(SystemExit):
        mod.next_version(bad)


def test_bumped_version_never_collides_in_cache_dir_name(mod):
    """`+` -> `-` 正規化後も現 version と別名であること。"""
    for current in ("0.2.0", "1.3.0+codex.20260713-1", "2.0.0-rc.1"):
        assert mod.cache_dir_name(mod.next_version(current)) != mod.cache_dir_name(current)


def test_cache_dir_name_matches_observed_normalization(mod):
    """2026-08-11 実測のキャッシュ名と一致する。"""
    assert mod.cache_dir_name("1.3.0+codex.20260713-1") == "1.3.0-codex.20260713-1"


# ── 対応表 ─────────────────────────────────────────────────────────


def test_checked_in_state_has_no_drift(mod):
    """commit 済み対応表が現在の plugins/ と一致する (CI と同じ検査)。"""
    assert mod.main(["--check"]) == 0


def test_every_plugin_is_recorded(mod):
    """plugins/ 実体すべてが対応表に載る。新 plugin の無音欠落を防ぐ。"""
    recorded = set(json.loads(FINGERPRINTS.read_text(encoding="utf-8"))["plugins"])
    actual = {d.name for d in mod.iter_plugins()}
    assert recorded == actual


def test_recorded_versions_match_plugin_manifests(mod):
    """対応表の version は plugin.json が SSOT。"""
    recorded = json.loads(FINGERPRINTS.read_text(encoding="utf-8"))["plugins"]
    for plugin_dir in mod.iter_plugins():
        assert recorded[plugin_dir.name]["version"] == mod.read_version(plugin_dir)


# ── 変更検出 ───────────────────────────────────────────────────────


def test_content_change_without_version_bump_is_detected(mod, tmp_path, monkeypatch):
    """version 据え置きの内容変更 = 上げ忘れ。--check が exit 1 で落とす。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    assert mod.main([]) == 0  # 初回記録
    assert mod.main(["--check"]) == 0
    (plugin / "SKILL.md").write_text("changed", encoding="utf-8")
    assert mod.main(["--check"]) == 1


def test_bump_advances_version_and_clears_drift(mod, tmp_path, monkeypatch):
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    mod.main([])
    (plugin / "SKILL.md").write_text("changed", encoding="utf-8")
    assert mod.main([]) == 0
    assert mod.read_version(plugin) == "0.1.1"
    assert mod.main(["--check"]) == 0


def test_manual_version_bump_is_respected(mod, tmp_path, monkeypatch):
    """手で major/minor を上げた場合、script は採番せず記録だけ更新する。

    「破壊的変更かどうかは人間しか判断できない」ので、手動採番を patch へ
    上書きしてはならない。
    """
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    mod.main([])
    (plugin / "SKILL.md").write_text("breaking", encoding="utf-8")
    mod.write_version(plugin, "1.0.0")
    assert mod.main([]) == 0
    assert mod.read_version(plugin) == "1.0.0"


def test_removed_plugin_is_pruned_from_fingerprint_state(mod, tmp_path, monkeypatch):
    plugin = _fake_plugin(tmp_path, "retired", "0.1.0")
    keep = _fake_plugin(tmp_path, "keep", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    assert mod.main([]) == 0
    plugin.rename(tmp_path / "retired-outside-plugins")

    assert mod.main(["--check"]) == 1
    assert mod.main([]) == 0
    recorded = json.loads((tmp_path / "fingerprints.json").read_text())["plugins"]
    assert set(recorded) == {keep.name}


def test_bump_touches_only_the_version_line(mod, tmp_path, monkeypatch):
    """json 往復での再整形を禁じる。整形差分は内容 hash を動かし bump を自己増殖させる。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    manifest = plugin / ".claude-plugin" / "plugin.json"
    manifest.write_text(
        '{\n  "name": "probe",\n  "version": "0.1.0",\n'
        '  "author": {"name": "someone"}\n}\n',
        encoding="utf-8",
    )
    before = manifest.read_text(encoding="utf-8").splitlines()
    _isolate(mod, monkeypatch, tmp_path)
    mod.write_version(plugin, "0.1.1")
    after = manifest.read_text(encoding="utf-8").splitlines()
    assert len(before) == len(after)
    assert [i for i, (a, b) in enumerate(zip(before, after)) if a != b] == [2]
    assert '"author": {"name": "someone"}' in after[3]


def test_bump_keeps_plugin_composition_version_in_the_same_atomic_release(mod, tmp_path, monkeypatch):
    """自己記述 bundle のversion同期が次回bumpを自己誘発しない。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    composition = plugin / "plugin-composition.yaml"
    composition.write_text(
        "name: probe\nkind: plugin-composition\nversion: 0.1.0\n",
        encoding="utf-8",
    )
    _isolate(mod, monkeypatch, tmp_path)
    assert mod.main([]) == 0
    (plugin / "SKILL.md").write_text("changed", encoding="utf-8")
    assert mod.main([]) == 0
    assert mod.read_version(plugin) == "0.1.1"
    assert "version: 0.1.1" in composition.read_text(encoding="utf-8")
    assert mod.main(["--check"]) == 0


def test_build_artifacts_do_not_trigger_bumps(mod, tmp_path, monkeypatch):
    """__pycache__ 等の副産物は fingerprint に入れない (pytest を回すだけで
    version が上がるノイズを防ぐ)。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    mod.main([])
    (plugin / "__pycache__").mkdir()
    (plugin / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    (plugin / ".DS_Store").write_bytes(b"\x00")
    assert mod.main(["--check"]) == 0


def test_bump_syncs_public_marketplace_version(mod, tmp_path, monkeypatch):
    """公開 marketplace も version を二重に持つ。片方だけ動かすと
    lint-config-version-sync が落ち、bump のたびに CI が赤くなる。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    (tmp_path / "marketplace.json").write_text(
        '{\n  "plugins": [\n'
        '    {\n      "name": "other",\n      "version": "9.9.9",\n'
        '      "tags": ["a", "b"]\n    },\n'
        '    {\n      "name": "probe",\n      "version": "0.1.0",\n'
        '      "tags": ["c", "d"]\n    }\n  ]\n}\n',
        encoding="utf-8",
    )
    mod.write_version(plugin, "0.1.1")
    after = (tmp_path / "marketplace.json").read_text(encoding="utf-8")
    assert '"name": "probe",\n      "version": "0.1.1"' in after
    assert '"version": "9.9.9"' in after  # 隣の plugin を巻き込まない
    assert '"tags": ["c", "d"]' in after  # 1 行記法を展開しない


def test_public_marketplace_sync_skips_unlisted_plugins(mod, tmp_path, monkeypatch):
    """distributable: false の plugin は公開側に載らない。無いことは異常ではない。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    (tmp_path / "marketplace.json").write_text(
        '{"plugins": [{"name": "other", "version": "9.9.9"}]}\n', encoding="utf-8"
    )
    mod.write_version(plugin, "0.1.1")
    assert '"version": "9.9.9"' in (tmp_path / "marketplace.json").read_text(encoding="utf-8")


def test_bump_syncs_codex_manifest_version(mod, tmp_path, monkeypatch):
    """.codex-plugin を持つ plugin は check-native-surface-parity が
    .claude-plugin との version 一致を要求する。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    (plugin / ".codex-plugin").mkdir()
    (plugin / ".codex-plugin" / "plugin.json").write_text(
        '{\n  "name": "probe",\n  "version": "0.1.0"\n}\n', encoding="utf-8"
    )
    mod.write_version(plugin, "0.1.1")
    codex = json.loads((plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert codex["version"] == "0.1.1"


def test_gitignored_artifacts_are_not_content(mod, tmp_path, monkeypatch):
    """機械ローカルの生成物を数えると fingerprint が machine 依存になる。

    実際に踏んだ: playwright のブラウザ実体と .coverage が手元にだけ存在し、
    手元 --check OK / CI DRIFT という再現しない食い違いを起こした。
    """
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    # パターンは .gitignore の位置を起点に解釈される。repo 直下に置くので
    # plugin からの相対ではなく repo からの相対で書く (実 repo と同じ書き方)。
    (tmp_path / ".gitignore").write_text(
        "plugins/probe/vendor/browsers/\n.coverage\n", encoding="utf-8"
    )
    _isolate(mod, monkeypatch, tmp_path)
    mod.main([])
    (plugin / "vendor" / "browsers").mkdir(parents=True)
    (plugin / "vendor" / "browsers" / "chromium").write_bytes(b"\x00" * 64)
    (plugin / ".coverage").write_bytes(b"\x00")
    assert mod.main(["--check"]) == 0


def test_untracked_but_unignored_files_are_content(mod, tmp_path, monkeypatch):
    """まだ commit していない新規ファイルも install されれば copy される。
    ここを落とすと「新 skill を足したのに反映されない」を検出できない。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    mod.main([])
    (plugin / "skills" / "run-new").mkdir(parents=True)
    (plugin / "skills" / "run-new" / "SKILL.md").write_text("new", encoding="utf-8")
    assert mod.main(["--check"]) == 1


def test_non_git_tree_fails_loudly(mod, tmp_path):
    """全走査へ黙って落とすと、環境で答えが変わる状態が無音で復活する。"""
    plugin = tmp_path / "plugins" / "probe"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text('{"version": "0.1.0"}', encoding="utf-8")
    with pytest.raises(SystemExit):
        mod.fingerprint(plugin)


def test_session_handoff_notes_do_not_trigger_bumps(mod, tmp_path, monkeypatch):
    """plugin ディレクトリを cwd にしてセッションを回すと .claude/handoff/ が書かれる。
    これで version が上がると、定時実行が「作業した」だけで空の版を量産する。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    mod.main([])
    (plugin / ".claude" / "handoff").mkdir(parents=True)
    (plugin / ".claude" / "handoff" / "20260811T003326.md").write_text("memo", encoding="utf-8")
    assert mod.main(["--check"]) == 0


def test_handoff_exclusion_is_anchored_to_dot_claude(mod, tmp_path, monkeypatch):
    """除外は相対パスの前方一致。"handoff" という一般名を全階層で
    消してしまうと、plugin の実コンテンツを取りこぼす。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    mod.main([])
    (plugin / "skills" / "handoff").mkdir(parents=True)
    (plugin / "skills" / "handoff" / "SKILL.md").write_text("real content", encoding="utf-8")
    assert mod.main(["--check"]) == 1


def test_tests_dir_is_part_of_fingerprint(mod, tmp_path, monkeypatch):
    """install は tests/ ごと copy する。除外すると対応表が copy 内容とずれる。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    mod.main([])
    (plugin / "tests").mkdir()
    (plugin / "tests" / "test_x.py").write_text("assert True", encoding="utf-8")
    assert mod.main(["--check"]) == 1


def test_install_targets_only_installed_plugins(mod, tmp_path, monkeypatch):
    """install していない plugin へ update をかけてもエラーになるだけ。"""
    home = tmp_path / "home"
    (home / ".claude" / "plugins").mkdir(parents=True)
    (home / ".claude" / "plugins" / "installed_plugins.json").write_text(
        json.dumps(
            {"plugins": {"a@harness-local": [], "b@xl-skills": [], "c@harness-local": []}}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pathlib.Path, "home", staticmethod(lambda: home))
    assert mod.installed_plugin_names() == ["a", "c"]


# ── ヘルパ ─────────────────────────────────────────────────────────


def _fake_plugin(tmp_path: pathlib.Path, name: str, version: str) -> pathlib.Path:
    # fingerprint は git に「何が内容か」を尋ねるので work tree が要る。
    if not (tmp_path / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    plugin = tmp_path / "plugins" / name
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": name, "version": version, "description": "Fixture plugin"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (plugin / "SKILL.md").write_text("original", encoding="utf-8")
    return plugin


def _isolate(mod, monkeypatch, tmp_path: pathlib.Path) -> None:
    """本物の plugins/ と対応表を触らせない。marketplace 再生成も止める
    (ここで検証したいのは採番と検出であって、生成物の内容ではない)。"""
    monkeypatch.setattr(mod, "PLUGINS_DIR", tmp_path / "plugins")
    monkeypatch.setattr(mod, "FINGERPRINTS", tmp_path / "fingerprints.json")
    monkeypatch.setattr(mod, "PUBLIC_MARKETPLACE", tmp_path / "marketplace.json")
    monkeypatch.setattr(mod, "regenerate_local_marketplace", lambda: None)
    # 実 repo の config-version-lock.json へ --write するのを止める。
    monkeypatch.setattr(mod, "regenerate_config_version_lock", lambda: None)
