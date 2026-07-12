"""skeleton 生成器の出力が自 plugin の決定論ゲートを通ることを固定する (HIGH-1 回帰ガード)。

SKILL は「手書き穴埋め skeleton を置かず、render-spec-skeleton.py が正本 (specfm) から
実行可能ひな形を生成する」と skeleton を前面に据える。その生成物 (render_minimal_index /
render_minimal_phase) が check-spec-gates / check-spec-frontmatter を exit0 で通らなければ
「ひな形」の約束が破れる。

本 test は **production 生成器の出力そのもの** をゲートへ流す。従来は golden / 負例テストが
生成器ではなく test fixture (conftest.valid_plugin_meta) で index を組んでおり、両者が別実装で
あるため「生成器が plugin_meta.distribution を落としてもゲート通過側 fixture だけがテストされる」
二重実装 drift (このプラグインが lint-ssot-duplication で他所に禁じる「両方残し」) が無音化していた。
この parity が両実装を機械的に縛る。
"""
from __future__ import annotations


def test_skeleton_index_passes_spec_gates(tmp_path, specfm_mod, gates):
    """render_minimal_index の出力が check-spec-gates を exit0 で通る (plugin_meta 値域=F3 distribution 含む)。"""
    index = tmp_path / "index.md"
    index.write_text(specfm_mod.render_minimal_index(plugin_slug="demo"), encoding="utf-8")
    assert gates.main([str(index)]) == 0, (
        "render_minimal_index 出力が check-spec-gates を通らない (生成器↔ゲートの plugin_meta 契約 drift)"
    )


def test_skeleton_phases_pass_spec_frontmatter(tmp_path, specfm_mod, specfm):
    """render_minimal_phase の出力が check-spec-frontmatter を exit0 で通る (frontmatter 契約 + phase 連鎖)。"""
    for n in (1, 5, 8, 10, 13):
        phase = tmp_path / f"phase-{n:02d}-{specfm_mod.PHASE_NAMES[n - 1]}.md"
        phase.write_text(specfm_mod.render_minimal_phase(n), encoding="utf-8")
        assert specfm.main([str(phase)]) == 0, (
            f"render_minimal_phase({n}) 出力が check-spec-frontmatter を通らない (生成器↔ゲート drift)"
        )


def test_skeleton_index_plugin_meta_matches_fixture_shape(specfm_mod):
    """生成器 (render_minimal_index) と test fixture (conftest.valid_plugin_meta) の plugin_meta
    トップレベルキー集合が一致する (二重実装が別々のキーを持つ drift を集合で検出)。

    値 (distributable 等) は用途で異なってよいが、キー集合が食い違うと「片方だけゲートを通る」
    穴が再発する。conftest を fixture 経由でなく直接ロードし、両者を突合する。
    """
    import importlib.util
    from pathlib import Path

    conftest_path = Path(__file__).resolve().parent / "conftest.py"
    spec = importlib.util.spec_from_file_location("conftest_for_parity", conftest_path)
    assert spec and spec.loader
    conftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conftest)

    gen_meta = specfm_mod.parse_frontmatter(specfm_mod.render_minimal_index(plugin_slug="demo"))["plugin_meta"]
    fixture_meta = conftest.valid_plugin_meta(distributable=False)
    missing = sorted(set(fixture_meta) - set(gen_meta))
    extra = sorted(set(gen_meta) - set(fixture_meta))
    assert not missing and not extra, (
        f"生成器と fixture の plugin_meta キー集合が drift: 生成器欠落={missing} 生成器余剰={extra}"
    )
