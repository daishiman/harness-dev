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

import argparse
import fnmatch
import importlib.util
import json
import pathlib
import re
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
    """commit 済み対応表が現在の plugins/ と一致する (CI と同じ検査)。

    **このテストは作業ツリーの現在の状態を見るので、plugins/ を編集している最中は
    構造的に赤くなる。** test_untracked_but_unignored_files_are_content のとおり
    未 commit の新規ファイルも内容に数えられるため、誰かが plugins/ に 1 ファイル
    置いた瞬間に rc=1 へ変わる。実測 (2026-10-10) でも、別の作業が新規ファイルを
    作った瞬間に緑から赤へ戻った。

    これは検査の欠陥ではなく、fingerprint が「作業ツリーの内容」を基準にすることの
    裏側である (基準を commit にすると未 commit の編集を install が copy する事実と
    食い違う。module docstring の「なぜ git commit hash を使わないのか」)。だから
    **ここを緩めてはいけない**。緩めると本来の上げ忘れを見逃す。

    赤を見たときの読み分け:
      - plugins/ を自分 (または同時に走っている別の作業) が編集中 → それが原因。
        異常ではない
      - 編集していないのに赤 → 本物の drift

    運用: **commit 前の最後の工程として `build-plugin-release.py` を再実行する**。
    編集が止まった状態で台帳を合わせ直せば緑になる。
    """
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


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_version_of_new_plugin_is_rejected_with_exit_2(mod, tmp_path, monkeypatch, capsys, blank):
    """採番を通らない new の行は version をそのまま書く。空なら書く前に exit 2 で止める。"""
    plugin = _fake_plugin(tmp_path, "probe", blank)
    _isolate(mod, monkeypatch, tmp_path)
    manifest = plugin / ".claude-plugin" / "plugin.json"
    before = manifest.read_bytes()
    assert mod.main(["--check"]) == 2
    assert mod.main([]) == 2
    assert "probe: version が空" in capsys.readouterr().err
    assert manifest.read_bytes() == before
    assert not (tmp_path / "fingerprints.json").exists()
    assert not (tmp_path / "marketplace.json").exists()


def test_blank_version_of_released_plugin_is_rejected_with_exit_2(mod, tmp_path, monkeypatch, capsys):
    """記録済みの plugin の version を手で空にした (released) 場合も記録・同期しない。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    assert mod.main([]) == 0
    recorded = (tmp_path / "fingerprints.json").read_bytes()
    manifest = plugin / ".claude-plugin" / "plugin.json"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace('"0.1.0"', '"  "'), encoding="utf-8")
    assert mod.main([]) == 2
    assert "version が空" in capsys.readouterr().err
    assert (tmp_path / "fingerprints.json").read_bytes() == recorded
    assert mod.read_version(plugin) == "  "


def test_blank_version_blocks_the_whole_run(mod, tmp_path, monkeypatch):
    """1 件でも空の version があれば、正しい plugin も含めて何も書かない (部分書き込みを作らない)。"""
    good = _fake_plugin(tmp_path, "good", "0.1.0")
    _fake_plugin(tmp_path, "blank", "")
    _isolate(mod, monkeypatch, tmp_path)
    before = (good / ".claude-plugin" / "plugin.json").read_bytes()
    assert mod.main([]) == 2
    assert (good / ".claude-plugin" / "plugin.json").read_bytes() == before
    assert not (tmp_path / "fingerprints.json").exists()


@pytest.mark.parametrize("blank", ["", "  ", None])
def test_write_version_refuses_blank_version(mod, tmp_path, monkeypatch, capsys, blank):
    """write_version を直接呼んでも、空の版を plugin.json と派生面へ広げない。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    manifest = plugin / ".claude-plugin" / "plugin.json"
    before = manifest.read_bytes()
    with pytest.raises(SystemExit) as excinfo:
        mod.write_version(plugin, blank)
    assert excinfo.value.code == 2
    assert "version が空" in capsys.readouterr().err
    assert manifest.read_bytes() == before
    assert not (tmp_path / "marketplace.json").exists()


def test_manual_version_record_repairs_release_surfaces(mod, tmp_path, monkeypatch):
    """manifest だけ先に進んだ record 状態でも派生面を旧版のまま固定しない。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    (tmp_path / "marketplace.json").write_text(
        '{"plugins": [{"name": "probe", "version": "0.1.0"}]}\n',
        encoding="utf-8",
    )
    assert mod.main([]) == 0

    manifest = plugin / ".claude-plugin" / "plugin.json"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace('"0.1.0"', '"1.0.0"', 1),
        encoding="utf-8",
    )
    assert mod.main([]) == 0

    assert mod.read_version(plugin) == "1.0.0"
    marketplace = json.loads((tmp_path / "marketplace.json").read_text(encoding="utf-8"))
    assert marketplace["plugins"][0]["version"] == "1.0.0"
    recorded = json.loads((tmp_path / "fingerprints.json").read_text(encoding="utf-8"))["plugins"]
    assert recorded["probe"]["version"] == "1.0.0"
    assert recorded["probe"]["fingerprint"] == mod.fingerprint(plugin)


@pytest.mark.parametrize("failed_step", ["marketplace", "config_lock"])
@pytest.mark.parametrize("release_state", ["changed", "new", "released"])
def test_downstream_failure_keeps_release_pending_and_retry_repairs(
    mod, tmp_path, monkeypatch, failed_step, release_state
):
    # This exercises release state transitions without requiring or touching Git.
    plugin = tmp_path / "plugins" / "probe"
    manifest = plugin / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "probe", "version": "0.1.0"}))
    (plugin / "SKILL.md").write_text("original")
    _isolate(mod, monkeypatch, tmp_path)
    monkeypatch.setattr(mod, "content_paths", lambda root: sorted(root.rglob("*")))
    if release_state != "new":
        assert mod.main([]) == 0
        (plugin / "SKILL.md").write_text("changed")
        if release_state == "released":
            mod.write_version(plugin, "1.0.0")
    ledger_before = mod.load_fingerprints()
    calls = []
    fail_next = True

    def regenerate(step):
        nonlocal fail_next
        calls.append(step)
        if step == failed_step and fail_next:
            fail_next = False
            raise SystemExit("injected downstream failure")

    monkeypatch.setattr(mod, "regenerate_local_marketplace", lambda: regenerate("marketplace"))
    monkeypatch.setattr(mod, "regenerate_config_version_lock", lambda: regenerate("config_lock"))
    with pytest.raises(SystemExit, match="injected downstream failure"):
        mod.main([])
    version_after_failure = mod.read_version(plugin)
    assert mod.load_fingerprints() == ledger_before
    assert mod.main(["--check"]) == 1

    calls.clear()
    assert mod.main([]) == 0
    assert calls == ["marketplace", "config_lock"]
    assert mod.read_version(plugin) == version_after_failure
    assert mod.main(["--check"]) == 0


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


def test_root_changelog_is_not_content_but_everything_else_still_is(mod, tmp_path, monkeypatch):
    """plugin 直下の CHANGELOG.md だけを fingerprint から外す。

    外す理由は副産物だからではなく、**採番の入力でありながら出力でないため不動点が
    存在しなくなる**ことである (script 側 EXCLUDED_ROOT_FILE_NAMES のコメント)。

    除外が検査を殺していないことを同じテストの中で対照する。CHANGELOG 以外の内容
    変更は従来どおり bump を要求し、全階層での名前一致にはしない (skill が
    reference として読む `.../references/CHANGELOG.md` が実在し、それは内容である)。
    """
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    (plugin / "CHANGELOG.md").write_text("# Changelog\n\n## 0.1.0 - 2026-10-10\n", encoding="utf-8")
    assert mod.main([]) == 0  # 初回記録
    assert mod.main(["--check"]) == 0

    # 1. 直下 CHANGELOG のみの変更は bump を要求しない (今回入れた除外)
    (plugin / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 0.2.0 - 2026-10-11\n\n新しい節。\n", encoding="utf-8"
    )
    assert mod.main(["--check"]) == 0
    assert mod.read_version(plugin) == "0.1.0"

    # 2. 除外は直下だけ。入れ子の CHANGELOG.md は依然として内容
    (plugin / "references").mkdir()
    (plugin / "references" / "CHANGELOG.md").write_text("rubric history", encoding="utf-8")
    assert mod.main(["--check"]) == 1
    assert mod.main([]) == 0
    assert mod.read_version(plugin) == "0.1.1"

    # 3. CHANGELOG 以外の内容変更は従来どおり bump を要求する (対照)
    (plugin / "SKILL.md").write_text("changed", encoding="utf-8")
    assert mod.main(["--check"]) == 1


def test_bump_adds_the_changelog_section_for_the_version_it_distributes(
    mod, tmp_path, monkeypatch
):
    """bump が CHANGELOG へ節を足し、版数整合が遅れないこと。

    fingerprint から除外しているのは「節を足した書き込み自体が次の bump を呼ぶ」
    不動点の不在を避けるためで、CHANGELOG を採番の出力から外すためではない。除外した
    うえで write_version() が節を書くことで、除外と追従が両立する。

    以前はここで「bump した直後の CHANGELOG 見出しは必ず 1 つ古い」を副作用として
    固定していた。実測 (2026-10-10 22:26) でその副作用が CHANGELOG を持つ 6 plugin
    全件のズレとして現れていたため、追従させる側へ不変条件を入れ替えた。

    既存の履歴の穴は埋めない (script 側 sync_changelog_section の docstring)。ここで
    見るのは「配っている版の節が在る」ことだけで、全履歴の網羅ではない。
    """
    def changelog_head_version(plugin_dir: pathlib.Path) -> str | None:
        text = (plugin_dir / "CHANGELOG.md").read_text(encoding="utf-8")
        match = re.search(r"^##\s*\[?v?(\d+\.\d+\.\d+[^\]\s]*)", text, re.MULTILINE)
        return match.group(1) if match else None

    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    (plugin / "CHANGELOG.md").write_text("# Changelog\n\n## 0.1.0 - 2026-10-10\n", encoding="utf-8")
    assert mod.main([]) == 0
    assert changelog_head_version(plugin) == mod.read_version(plugin)

    # 本体を変えて bump させると CHANGELOG も同じ工程で追従する
    (plugin / "SKILL.md").write_text("changed", encoding="utf-8")
    assert mod.main([]) == 0
    assert mod.read_version(plugin) == "0.1.1"
    assert changelog_head_version(plugin) == "0.1.1"
    # 既存の節は残る (履歴を書き換えない)
    assert "## 0.1.0 - 2026-10-10" in (plugin / "CHANGELOG.md").read_text(encoding="utf-8")
    # 書式を踏襲する (fixture は角括弧なし・半角ハイフン)
    assert re.search(r"^## 0\.1\.1 - \d{4}-\d{2}-\d{2}$",
                     (plugin / "CHANGELOG.md").read_text(encoding="utf-8"), re.MULTILINE)

    # 追従しても fingerprint は動かない (除外が効いている)。動くと次回が
    # 「上げ忘れ」になり、解消の bump がまた節を足して落ち着かない。
    assert mod.main(["--check"]) == 0

    # 検出器は無力化されていない: 手で見出しを戻すとズレを掴む
    text = (plugin / "CHANGELOG.md").read_text(encoding="utf-8")
    (plugin / "CHANGELOG.md").write_text(
        text.replace("## 0.1.1 -", "## 0.0.9 -", 1), encoding="utf-8"
    )
    assert changelog_head_version(plugin) != mod.read_version(plugin)


def test_changelog_section_is_written_below_an_unreleased_heading(mod, tmp_path, monkeypatch):
    """`## [Unreleased]` がある CHANGELOG では、新しい節をその下へ入れる。

    Keep a Changelog の通例であると同時に、読む側 (notifier-check の
    `_extract_latest_version`) が版の形をしていない見出しを飛ばして次へ進むため、
    下へ入れても版数整合検査は通る (2026-10-10 22:26 実測)。飛ばすのは先頭の 1 つ
    だけにする — Unreleased を全部飛ばすと、2 つ以上ある CHANGELOG (実測:
    prompt-creator) で新しい節が古い節より下へ回って新旧の順序が壊れる。
    """
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    (plugin / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n- 未リリース分\n\n"
        "## [Unreleased] - 2026-05-24\n\n- 版へ昇格しなかった古い節\n",
        encoding="utf-8",
    )
    mod.write_version(plugin, "0.2.0")

    headings = [
        line for line in (plugin / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]
    assert headings == [
        "## [Unreleased]",
        "## [0.2.0] - " + __import__("datetime").date.today().isoformat(),
        "## [Unreleased] - 2026-05-24",
    ]
    # 冪等: 同じ版で二度呼んでも節は増えない
    before = (plugin / "CHANGELOG.md").read_bytes()
    mod.sync_changelog_section(plugin, "0.2.0")
    assert (plugin / "CHANGELOG.md").read_bytes() == before


def _declare_derived(mod, monkeypatch, tmp_path, plugin_name="probe"):
    """宣言テーブルを tmp 側の成果物へ差し替え、実 doc を触らずに追従を見る。"""
    doc = tmp_path / "doc" / "derived.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(
        mod,
        "DERIVED_VERSION_SURFACES",
        (
            (
                plugin_name,
                "doc/derived.md",
                r"version \S+ / skills \d+ \+ agents \d+ \+ commands \d+",
                "version {version} / skills {skills} + agents {agents} + commands {commands}",
            ),
        ),
    )
    return doc


def test_bump_rewrites_declared_derived_surfaces(mod, tmp_path, monkeypatch):
    """宣言した派生成果物が、bump の工程で版数と実数へ書き直されること。

    ソーステキスト検査 (write_version の本文に呼び出しが在るか) は、呼び出し行を
    コメントへ落とす改変で騙される — 文字列がコメントの中に残るため。実測
    (2026-10-10 22:47) で `pass  # MUTATION: sync_derived_version_surfaces(...)` は
    rc=0 / 51 passed のまま通った。呼び出しを実際に走らせて結果を見るのはここだけ。
    """
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    for name in ("alpha", "beta", "gamma"):
        (plugin / "skills" / name).mkdir(parents=True)
        (plugin / "skills" / name / "SKILL.md").write_text("x", encoding="utf-8")
    (plugin / "agents").mkdir()
    (plugin / "agents" / "one.md").write_text("x", encoding="utf-8")
    (plugin / "commands").mkdir()
    for name in ("a.md", "b.md"):
        (plugin / "commands" / name).write_text("x", encoding="utf-8")
    doc = _declare_derived(mod, monkeypatch, tmp_path)
    doc.write_text(
        "> 対象: probe (version 0.0.1 / skills 1 + agents 1 + commands 1)\n",
        encoding="utf-8",
    )

    mod.write_version(plugin, "0.2.0")

    assert doc.read_text(encoding="utf-8") == (
        "> 対象: probe (version 0.2.0 / skills 3 + agents 1 + commands 2)\n"
    )
    # 冪等: 同じ版で二度呼んでも文面は動かない
    before = doc.read_bytes()
    mod.sync_derived_version_surfaces(plugin, "0.2.0")
    assert doc.read_bytes() == before


def test_derived_surface_sync_fails_loudly_on_a_broken_declaration(mod, tmp_path, monkeypatch):
    """宣言と文面が食い違ったら黙って通さない。

    通すと「追従の仕組みが在るのに効いていない」状態になり、版数は静かに遅れ始める。
    """
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    doc = _declare_derived(mod, monkeypatch, tmp_path)

    # 1. 宣言した path が無い
    with pytest.raises(SystemExit):
        mod.sync_derived_version_surfaces(plugin, "0.2.0")

    # 2. path は在るが正規表現が 1 件も当たらない (文面の書き換えで切れた場合)
    doc.write_text("version の記述を言い換えて消した本文\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        mod.sync_derived_version_surfaces(plugin, "0.2.0")

    # 3. 対象外 plugin の bump では何も要求しない (宣言の plugin 名で絞る)
    other = _fake_plugin(tmp_path, "other", "0.1.0")
    mod.sync_derived_version_surfaces(other, "0.2.0")


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


_GOV_PROPOSALS = "skills/run-skill-rubric-governance/proposals"
_GENERATED_BODY = (
    "---\nkind: rubric-update-proposal\n---\n\n"
    "本ドラフトは aggregate-evals.py により自動生成された。PR 起票は別工程。\n"
)
_HANDWRITTEN_BODY = (
    "---\nkind: rubric-update-proposal\n---\n\n"
    "BD-001 の見出し別名を追加する。承認者は利用者。\n"
)


def _write_proposal(plugin: pathlib.Path, name: str, body: str) -> pathlib.Path:
    d = plugin / _GOV_PROPOSALS
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(body, encoding="utf-8")
    return p


def test_generated_rubric_proposals_do_not_trigger_bumps(mod, tmp_path, monkeypatch):
    """SessionEnd hook (aggregate-evals.py) は以前 session を終えるたびに
    proposals/<today>-rubric-update.md を書いていた。今の書き先は plugin の外だが、
    手元に残った旧生成物や古い版の hook が書いたもので version が上がると、
    「セッションを終えた」だけで誰も待っていない版が日ごとに増える。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    mod.main([])
    _write_proposal(plugin, "2026-10-11-rubric-update.md", _GENERATED_BODY)
    assert mod.main(["--check"]) == 0


def test_handwritten_rubric_proposals_are_still_content(mod, tmp_path, monkeypatch):
    """除外は marker を持つ機械生成ドラフトだけ。同じディレクトリの手書き提案は
    rubric 採番の根拠として governance-log から参照される監査記録なので、
    追加・書き換えが黙って通ってはいけない。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    mod.main([])
    _write_proposal(plugin, "2026-10-09-ja-heading-alias.md", _HANDWRITTEN_BODY)
    assert mod.main(["--check"]) == 1


def test_generated_proposal_exclusion_is_anchored_to_the_governance_dir(
    mod, tmp_path, monkeypatch
):
    """marker 行だけを根拠に全階層で消すと、その語を引用した実コンテンツを
    取りこぼす。除外はこの proposals/ 配下に限る。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    mod.main([])
    (plugin / "skills" / "run-skill-rubric-governance").mkdir(parents=True, exist_ok=True)
    (plugin / "skills" / "run-skill-rubric-governance" / "SKILL.md").write_text(
        _GENERATED_BODY, encoding="utf-8"
    )
    assert mod.main(["--check"]) == 1


_GENERATED_NAME_GLOB = "*-rubric-update.md"


def test_real_proposals_dir_keeps_handwritten_and_ignores_generated(mod):
    """自動ドラフトの書き先は plugin の外 ($CLAUDE_PROJECT_DIR/.claude/state/...) へ
    移したので、clean clone の proposals/ には手書きしか無い (機械生成 0 件は正常)。
    手元に旧書き先の生成物が残っていても、.gitignore のファイル名パターンが
    生成物だけに当たり、手書きの監査記録には当たらないことを実 repo で押さえる。
    手書きが 0 件になったら、パターンか marker 判定が手書きまで飲み込んでいる。"""
    d = ROOT / "plugins" / "harness-creator" / _GOV_PROPOSALS
    assert d.is_dir()
    files = sorted(d.glob("*.md"))
    generated = [p.name for p in files if mod._is_generated_proposal(p)]
    handwritten = [p.name for p in files if not mod._is_generated_proposal(p)]
    assert len(handwritten) >= 2, f"手書きが少なすぎる: {handwritten}"
    assert not [n for n in handwritten if fnmatch.fnmatch(n, _GENERATED_NAME_GLOB)]
    assert all(fnmatch.fnmatch(n, _GENERATED_NAME_GLOB) for n in generated), generated
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert f"plugins/harness-creator/{_GOV_PROPOSALS}/{_GENERATED_NAME_GLOB}" in ignore


def test_generated_marker_matches_the_writer(mod):
    """除外の根拠は生成器が本文へ書く marker 行。書く側の文言が変わると、
    旧書き先に残った生成物が手書き扱いになり fingerprint を揺らす。"""
    script = (
        ROOT / "plugins" / "harness-creator" / "skills"
        / "run-skill-rubric-governance" / "scripts" / "aggregate-evals.py"
    )
    spec = importlib.util.spec_from_file_location("aggregate_evals_for_marker", script)
    writer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(writer)
    assert writer._GENERATED_MARKER == mod.GENERATED_PROPOSAL_MARKER
    assert mod.GENERATED_PROPOSAL_MARKER in writer._render_proposal([], [], {})


def test_tests_dir_is_part_of_fingerprint(mod, tmp_path, monkeypatch):
    """install は tests/ ごと copy する。除外すると対応表が copy 内容とずれる。"""
    plugin = _fake_plugin(tmp_path, "probe", "0.1.0")
    _isolate(mod, monkeypatch, tmp_path)
    mod.main([])
    (plugin / "tests").mkdir()
    (plugin / "tests" / "test_x.py").write_text("assert True", encoding="utf-8")
    assert mod.main(["--check"]) == 1


def _write_installed(home: pathlib.Path, plugins: dict) -> None:
    (home / ".claude" / "plugins").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"plugins": plugins}), encoding="utf-8"
    )


def test_install_targets_only_installed_plugins(mod, tmp_path, monkeypatch):
    """install していない plugin へ update をかけてもエラーになるだけ。"""
    home = tmp_path / "home"
    _write_installed(
        home,
        {
            "a@harness-local": [{"scope": "user"}],
            "b@xl-skills": [{"scope": "user"}],
            "c@harness-local": [{"scope": "user"}],
        },
    )
    monkeypatch.setattr(pathlib.Path, "home", staticmethod(lambda: home))
    assert mod.installed_plugin_scopes(str(tmp_path)) == {"a": "user", "c": "user"}


def test_install_follows_the_scope_the_copy_actually_lives_in(mod, tmp_path, monkeypatch):
    """既定では install 済み copy が実際に居る scope へ update をかける。

    実測 (2026-08-26) では harness-local の全 plugin が user scope なのに --scope の既定が
    project だった。全件が「project に入っていない」で exit 1 になり、`--install` は
    一度も成功しない状態が続いていた。既定を実態追随にしてその退行を塞ぐ。
    """
    home = tmp_path / "home"
    _write_installed(home, {"a@harness-local": [{"scope": "user"}]})
    monkeypatch.setattr(pathlib.Path, "home", staticmethod(lambda: home))
    calls: list[list[str]] = []
    monkeypatch.setattr(mod, "run_install", lambda t, d, p: calls.append(t) or 0)
    args = argparse.Namespace(
        project_dir=str(tmp_path), scope=None, dry_run=False
    )
    assert mod.drive_install(args, []) == 0
    assert calls == [{"a": "user"}]


def test_project_scope_entries_of_other_projects_are_ignored(mod, tmp_path, monkeypatch):
    """project scope の entry は projectPath がこの repo を指すものだけ拾う。

    拾わないと、別 project へ入れた同名 plugin を掴んで無関係な install 先を更新する。
    """
    home = tmp_path / "home"
    _write_installed(
        home,
        {
            "a@harness-local": [
                {"scope": "project", "projectPath": str(tmp_path / "elsewhere")}
            ],
            "b@harness-local": [{"scope": "project", "projectPath": str(tmp_path)}],
        },
    )
    monkeypatch.setattr(pathlib.Path, "home", staticmethod(lambda: home))
    assert mod.installed_plugin_scopes(str(tmp_path)) == {"b": "project"}


def test_install_fails_loudly_when_nothing_is_installed(mod, tmp_path, monkeypatch, capsys):
    """対象 0 件を成功にしない。

    exit 0 にすると、bump した新版がどこにも届いていないのに成功として通り、
    「新しい版を install したのに古い copy を見続ける」無音故障になる。
    """
    home = tmp_path / "home"
    _write_installed(home, {})
    monkeypatch.setattr(pathlib.Path, "home", staticmethod(lambda: home))
    args = argparse.Namespace(project_dir=str(tmp_path), scope=None, dry_run=False)
    assert mod.drive_install(args, []) == 1
    assert "install 済み plugin がありません" in capsys.readouterr().err


def test_install_respects_only_on_the_no_change_path(mod, tmp_path, monkeypatch):
    """変更なし経路でも --only を尊重する (以前は無視して全件へ update していた)。"""
    home = tmp_path / "home"
    _write_installed(
        home, {"a@harness-local": [{"scope": "user"}], "c@harness-local": [{"scope": "user"}]}
    )
    monkeypatch.setattr(pathlib.Path, "home", staticmethod(lambda: home))
    calls: list[dict] = []
    monkeypatch.setattr(mod, "run_install", lambda t, d, p: calls.append(t) or 0)
    args = argparse.Namespace(project_dir=str(tmp_path), scope=None, dry_run=False)
    assert mod.drive_install(args, ["c"]) == 0
    assert calls == [{"c": "user"}]


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
