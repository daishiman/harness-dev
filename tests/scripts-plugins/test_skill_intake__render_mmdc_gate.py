"""render_to_image.py / render_to_svg.py の mmdc 不在 fail-fast (exit 3, F-0102/F-0209/F-0303)
と --allow-placeholder (CI/テスト専用) 隔離、validate-notion-ready.py の mmdc preflight を検証する。

mmdc の実在有無に依存しないよう has_mmdc を monkeypatch で固定し、preflight は
PATH を最小化した subprocess で mmdc 不在を決定論的に再現する。
実 mmdc・実 Notion・実 keychain は呼ばない。全 I/O は tmp_path 配下に限定。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins" / "skill-intake" / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


IMG = _load("render_to_image_s3", SCRIPTS / "render_to_image.py")
SVG = _load("render_to_svg_s3", SCRIPTS / "render_to_svg.py")


def _mmd(tmp_path):
    p = tmp_path / "diagram.mmd"
    p.write_text("graph TD;A-->B;", encoding="utf-8")
    return p


# ===================== render_to_image.py =====================

def test_image_mmdc_missing_exits_3_dependency_error(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(IMG, "has_mmdc", lambda: False)
    rc = IMG.main([str(_mmd(tmp_path)), str(tmp_path / "d.png")])
    assert rc == 3
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["reason"] == "DEPENDENCY_ERROR"
    # 非エンジニア向け導入案内が stderr に出る
    assert "@mermaid-js/mermaid-cli" in captured.err
    assert "mmdc --version" in captured.err
    # fail-open 廃止: placeholder は生成されない
    assert not (tmp_path / "d.png.placeholder.txt").exists()


def test_image_allow_placeholder_flag_keeps_legacy_behavior(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(IMG, "has_mmdc", lambda: False)
    rc = IMG.main([str(_mmd(tmp_path)), str(tmp_path / "d.png"), "--allow-placeholder"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["mode"] == "placeholder"
    assert (tmp_path / "d.png.placeholder.txt").exists()


def test_image_input_missing_exits_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(IMG, "has_mmdc", lambda: False)
    rc = IMG.main([str(tmp_path / "nope.mmd"), str(tmp_path / "d.png")])
    assert rc == 2
    assert "input missing" in capsys.readouterr().err


# ===================== render_to_image.py: SVG 入力経路 =====================

def _svg(tmp_path, stem="cvis-sample"):
    p = tmp_path / f"{stem}.svg"
    # font-family はカタログ実資産 (assets/cvis-*.svg) と同形
    p.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"'
        ' font-family="-apple-system, \'Hiragino Sans\', sans-serif"/>',
        encoding="utf-8")
    return p


def test_image_svg_bundled_png_copies_without_external_deps(monkeypatch, tmp_path, capsys):
    # mmdc / cairosvg いずれも不在でも、同梱 PNG があればコピーで成立する (外部依存ゼロ)。
    monkeypatch.setattr(IMG, "has_mmdc", lambda: False)
    monkeypatch.setattr(IMG, "load_cairosvg", lambda: None)
    svg = _svg(tmp_path)
    (tmp_path / "cvis-sample.png").write_bytes(b"\x89PNG-fake-bundled")
    out = tmp_path / "visuals" / "s0-cvis-sample.png"
    rc = IMG.main([str(svg), str(out)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["mode"] == "bundled-copy"
    assert out.read_bytes() == b"\x89PNG-fake-bundled"


def test_image_svg_no_bundled_no_cairosvg_exits_3(monkeypatch, tmp_path, capsys):
    # 同梱 PNG 不在 + cairosvg 未導入を環境非依存でシミュレート → exit 3 DEPENDENCY_ERROR。
    monkeypatch.setattr(IMG, "load_cairosvg", lambda: None)
    svg = _svg(tmp_path)
    rc = IMG.main([str(svg), str(tmp_path / "d.png")])
    assert rc == 3
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["reason"] == "DEPENDENCY_ERROR"
    assert payload["mode"] == "svg"
    # 導入案内 (同梱 PNG 再取得 or pip install cairosvg) が stderr に出る
    assert "cairosvg" in captured.err
    assert "同梱 PNG" in captured.err
    assert not (tmp_path / "d.png").exists()


def test_image_svg_cairosvg_fallback_when_bundled_missing(monkeypatch, tmp_path, capsys):
    # 同梱 PNG 不在でも cairosvg があれば変換で成立する (stub で環境非依存)。
    class FakeCairosvg:
        @staticmethod
        def svg2png(bytestring, write_to, output_width):
            # -apple-system は cairosvg 非解決フォントとして前処理で除去される
            assert b"-apple-system" not in bytestring
            Path(write_to).write_bytes(b"\x89PNG-fake-cairosvg")

    monkeypatch.setattr(IMG, "load_cairosvg", lambda: FakeCairosvg)
    svg = _svg(tmp_path)
    out = tmp_path / "d.png"
    rc = IMG.main([str(svg), str(out)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "cairosvg"
    assert out.read_bytes() == b"\x89PNG-fake-cairosvg"


def test_bundled_pngs_exist_for_all_catalog_svgs():
    # カタログ静的 SVG 8 種に事前レンダリング PNG が同梱されている (bundled-copy 経路の前提)。
    assets = ROOT / "plugins" / "skill-intake" / "assets"
    svgs = sorted(assets.glob("cvis-*.svg"))
    assert len(svgs) == 8
    for svg in svgs:
        png = svg.with_suffix(".png")
        assert png.exists(), f"bundled PNG missing: {png.name}"
        assert png.stat().st_size > 1024, f"bundled PNG too small: {png.name}"


# ===================== render_to_svg.py =====================

def test_svg_mmdc_missing_exits_3_dependency_error(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(SVG, "has_mmdc", lambda: False)
    out = tmp_path / "d.svg"
    rc = SVG.main([str(_mmd(tmp_path)), str(out)])
    assert rc == 3
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["reason"] == "DEPENDENCY_ERROR"
    assert "@mermaid-js/mermaid-cli" in captured.err
    # fail-open 廃止: placeholder SVG は書かれない
    assert not out.exists()


def test_svg_allow_placeholder_flag_keeps_legacy_behavior(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(SVG, "has_mmdc", lambda: False)
    out = tmp_path / "d.svg"
    rc = SVG.main([str(_mmd(tmp_path)), str(out), "--allow-placeholder"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "placeholder"
    assert "mermaid placeholder" in out.read_text(encoding="utf-8")


# ===================== validate-notion-ready.py mmdc preflight =====================

def test_validate_notion_ready_mmdc_preflight_exits_3(tmp_path):
    # PATH を最小化して mmdc 不在を再現 (config/token 検査より前に fail-fast する)。
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "validate-notion-ready.py")],
        capture_output=True, text=True, env=env, cwd=str(tmp_path),
    )
    assert r.returncode == 3
    assert "mmdc" in r.stderr
    assert "@mermaid-js/mermaid-cli" in r.stderr
