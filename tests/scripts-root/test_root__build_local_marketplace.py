"""build-local-marketplace.py の不変条件を固定する。

守りたいのは 3 点:
  1. ローカル marketplace が公開側のガード (MK-004 / NEVER_DISTRIBUTE) を迂回する
     裏口にならないこと = --only-distributable が公開集合と厳密に一致する。
  2. 生成物が machine 非依存であること = source が相対パスで、かつ実在解決する。
     ここが崩れると git 管理できず、CI の drift 検出も別 clone での利用も成立しない。
  3. 新 plugin が無音で欠落しないこと = plugins/ 実体を起点に走査している。
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-local-marketplace.py"
GENERATED = ROOT / "marketplaces" / "local" / ".claude-plugin" / "marketplace.json"
PUBLIC = ROOT / ".claude-plugin" / "marketplace.json"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("build_local_marketplace", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generated() -> dict:
    assert GENERATED.exists(), (
        "marketplaces/local/.claude-plugin/marketplace.json が未生成。"
        "python3 scripts/build-local-marketplace.py を実行すること"
    )
    return json.loads(GENERATED.read_text(encoding="utf-8"))


def test_checked_in_output_has_no_drift(mod):
    """commit 済み生成物が現在の plugins/ と一致する (CI と同じ検査)。"""
    assert mod.main(["--check"]) == 0


def test_all_plugin_dirs_are_listed(generated):
    """plugins/ の実体すべてが載る。新 plugin の無音欠落を防ぐ。"""
    actual = {p["name"] for p in generated["plugins"]}
    expected = {
        d.name
        for d in (ROOT / "plugins").iterdir()
        if (d / ".claude-plugin" / "plugin.json").is_file()
    }
    assert actual == expected


def test_sources_stay_inside_marketplace_root(generated):
    """source は `./plugins/<name>` 形式で marketplace ルート配下に収まる。

    2026-08-11 実機再現: `../` で親へ遡ると Claude Code が
    `source: Invalid input` で install を拒否する。ローカル plugin catalog の
    255 エントリを調べても `../` と絶対パスの実例は 1 件も無い。
    ここが崩れると install が失敗するので、書式そのものを固定する。
    """
    for entry in generated["plugins"]:
        source = entry["source"]
        assert source == f"./plugins/{entry['name']}", f"{entry['name']}: {source}"
        assert ".." not in pathlib.PurePosixPath(source).parts, f"{entry['name']}: 親へ遡及"


def test_plugins_symlink_bridges_to_real_plugins(generated):
    """`<marketplace root>/plugins` symlink が実体へ橋渡ししている。

    marketplace.json と symlink は「両方揃って初めて install できる」一組。
    symlink だけ消えると marketplace.json は正しいまま install が失敗する。
    """
    market_root = GENERATED.parent.parent
    link = market_root / "plugins"
    assert link.is_symlink(), "plugins symlink が無い"
    # 相対 symlink であること = 別 clone でもそのまま動く条件。
    assert not pathlib.PurePosixPath(link.readlink()).is_absolute()
    assert link.resolve() == (ROOT / "plugins").resolve()
    for entry in generated["plugins"]:
        manifest = market_root / entry["source"] / ".claude-plugin" / "plugin.json"
        assert manifest.is_file(), f"{entry['name']}: source から plugin.json へ到達不能"


def test_entries_use_only_official_marketplace_keys(generated):
    """entry へ非公式キーを混ぜない (Claude Code 側の schema 検証で弾かれうる)。"""
    official = {"name", "source", "description", "version", "category", "tags"}
    for entry in generated["plugins"]:
        assert set(entry) <= official, f"{entry['name']}: 非公式キー {set(entry) - official}"


def test_marketplace_name_differs_from_public(generated):
    """`<plugin>@<marketplace>` の exact identity が公開側と衝突しない。"""
    public_name = json.loads(PUBLIC.read_text(encoding="utf-8"))["name"]
    assert generated["name"] != public_name


def test_versions_track_plugin_manifest(generated):
    """version は plugin.json が SSOT。公開 marketplace の drift に引きずられない。"""
    for entry in generated["plugins"]:
        manifest = json.loads(
            (ROOT / "plugins" / entry["name"] / ".claude-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        assert entry["version"] == manifest["version"], entry["name"]


def test_only_distributable_reproduces_public_set(mod, tmp_path):
    """--only-distributable が公開 marketplace の集合と厳密に一致する。

    should_include の判定式が validate-plugin-completeness.py の MK-004 逆ガードと
    同一であることの実証。片方だけ解釈が漂流したらここで落ちる。
    """
    out = tmp_path / "dist"
    assert mod.main(["--out", str(out), "--only-distributable"]) == 0
    produced = json.loads((out / ".claude-plugin" / "marketplace.json").read_text("utf-8"))
    public = json.loads(PUBLIC.read_text(encoding="utf-8"))
    assert {p["name"] for p in produced["plugins"]} == {p["name"] for p in public["plugins"]}


def test_non_distributable_plugins_are_included_locally(mod, generated):
    """非配布 plugin がローカル側には載る (この script の存在理由)。"""
    clone_local = generated["metadata"]["clone_local_plugins"]
    assert clone_local, "非配布 plugin が 1 件も載っていない"
    listed = {p["name"] for p in generated["plugins"]}
    assert set(clone_local) <= listed
    # NEVER_DISTRIBUTE (公開への混入を恒久禁止する固有名) こそローカルでは使いたい対象。
    completeness = mod._load_completeness_module()
    assert completeness.NEVER_DISTRIBUTE <= listed


def test_check_detects_missing_output(mod, tmp_path):
    """未生成を drift として検出する (fail-closed)。"""
    assert mod.main(["--out", str(tmp_path / "absent"), "--check"]) == 1


def test_check_detects_stale_output(mod, tmp_path):
    """内容が古い場合を drift として検出する。"""
    out = tmp_path / "stale"
    assert mod.main(["--out", str(out)]) == 0
    target = out / ".claude-plugin" / "marketplace.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    data["plugins"] = data["plugins"][:-1]
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert mod.main(["--out", str(out), "--check"]) == 1


def test_check_detects_missing_symlink(mod, tmp_path):
    """marketplace.json が正しくても symlink が無ければ drift 扱いにする。

    symlink 消失は install 時まで露見しない無音故障なので、生成物と同じ強度で
    検査することが fail-closed の条件。
    """
    out = tmp_path / "unlinked"
    assert mod.main(["--out", str(out)]) == 0
    assert mod.main(["--out", str(out), "--check"]) == 0
    (out / "plugins").unlink()
    assert mod.main(["--out", str(out), "--check"]) == 1


def test_regeneration_repairs_wrong_symlink(mod, tmp_path):
    """向き先が誤った symlink を張り直す (手で書き換えられても収束する)。"""
    out = tmp_path / "wrong"
    assert mod.main(["--out", str(out)]) == 0
    link = out / "plugins"
    link.unlink()
    link.symlink_to("/nonexistent", target_is_directory=True)
    assert mod.main(["--out", str(out), "--check"]) == 1
    assert mod.main(["--out", str(out)]) == 0
    assert link.resolve() == (ROOT / "plugins").resolve()


def test_real_file_at_link_path_is_refused(mod, tmp_path):
    """symlink 位置に実体ディレクトリがあれば黙って壊さず停止する。"""
    out = tmp_path / "occupied"
    (out / "plugins").mkdir(parents=True)
    (out / "plugins" / "keep.txt").write_text("do not delete", encoding="utf-8")
    with pytest.raises(SystemExit):
        mod.main(["--out", str(out)])
    assert (out / "plugins" / "keep.txt").exists()


def test_broken_public_marketplace_stops_with_input_exit_code(mod, tmp_path, monkeypatch):
    """公開 marketplace が壊れていたら握り潰さず exit 2 で止まる。

    握り潰して {} に落とすと description/category/tags の fallback が消えたまま
    「正常な生成物」が出てしまい、--check もその退化後の内容で緑になる。
    """
    broken = tmp_path / "marketplace.json"
    broken.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(mod, "PUBLIC_MARKETPLACE", broken)
    with pytest.raises(SystemExit) as excinfo:
        mod.load_public_entries()
    assert excinfo.value.code == 2

    broken.write_text(json.dumps({"plugins": {"oops": 1}}), encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        mod.load_public_entries()
    assert excinfo.value.code == 2


def test_missing_public_marketplace_is_tolerated(mod, tmp_path, monkeypatch):
    """未生成 (不在) は fallback 無しで続行してよい = 壊れているとは区別する。"""
    monkeypatch.setattr(mod, "PUBLIC_MARKETPLACE", tmp_path / "absent.json")
    assert mod.load_public_entries() == {}


def test_documented_cli_surface_matches_argparse(mod, capsys):
    """docstring / frontmatter が掲げる option だけを受理する (幽霊 option を作らない)。"""
    frontmatter = SCRIPT.read_text(encoding="utf-8").split("# ///")[1]
    declared = {tok.strip() for tok in frontmatter.split("argv:")[1].splitlines()[0].split(",")}
    assert declared == {"--out", "--check", "--name", "--only-distributable"}
    for flag in declared:
        assert f'"{flag}"' in SCRIPT.read_text(encoding="utf-8"), f"{flag} が argparse に無い"
    # 宣言に無い option は受理しない (幽霊 option を作らない)
    with pytest.raises(SystemExit) as excinfo:
        mod.main(["--source-style", "absolute"])
    assert excinfo.value.code == 2
