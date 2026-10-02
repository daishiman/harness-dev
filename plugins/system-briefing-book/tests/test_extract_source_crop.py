"""extract-source-crop.mjs: 素材の PDF や写真から一部を PNG に切り出す。

画像は標準ライブラリ (zlib と struct) だけで作って読む。切り出しは Chrome / Edge を使うので、無ければ飛ばす。
"""
from __future__ import annotations

import shutil
import struct
import zlib
from pathlib import Path

import pytest

from conftest import codes, needs_browser, run_script

SCRIPT = "extract-source-crop"
WHITE, RED, BLUE = (255, 255, 255), (220, 30, 30), (30, 60, 220)
needs_poppler = pytest.mark.skipif(not (shutil.which("pdftoppm") and shutil.which("pdfinfo")), reason="poppler がない")


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_rect_png(path: Path, size: tuple[int, int], rect: tuple[int, int, int, int], color) -> Path:
    """白地に 1 つの四角 (x, y, w, h) を塗った RGB の PNG。"""
    width, height = size
    x, y, w, h = rect
    plain = b"\x00" + bytes(WHITE) * width
    marked = b"\x00" + bytes(WHITE) * x + bytes(color) * w + bytes(WHITE) * (width - x - w)
    raw = b"".join(marked if y <= row < y + h else plain for row in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b""))
    return path


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def center_color(path: Path) -> tuple[int, int, int]:
    """8 bit の RGB / RGBA の PNG を zlib で解き、真ん中の画素の色を返す。"""
    data = path.read_bytes()
    width, height, depth, ctype = struct.unpack(">IIBB", data[16:26])
    assert depth == 8 and ctype in (2, 6)
    bpp = 3 if ctype == 2 else 4
    idat, pos = b"", 8
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        if data[pos + 4:pos + 8] == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * bpp
    prev = bytearray(stride)
    for row in range(height // 2 + 1):
        start = row * (stride + 1)
        kind, line = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if kind == 1:
                line[i] = (line[i] + a) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + b) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 0xFF
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        prev = line
    x = (width // 2) * bpp
    return tuple(prev[x:x + 3])


def near(color, expected) -> bool:
    """PDF を描くときのにじみや縮めたときの混ざりは少しだけ許す。"""
    return all(abs(a - b) <= 8 for a, b in zip(color, expected))


def write_jpeg_header(path: Path, size: tuple[int, int], orientation: int) -> Path:
    """EXIF の向きと SOF0 だけを持つ JPEG の頭 (--info は頭しか読まない)。"""
    width, height = size
    ifd = struct.pack(">H", 1) + struct.pack(">HHIHH", 0x0112, 3, 1, orientation, 0) + struct.pack(">I", 0)
    exif = b"Exif\x00\x00" + b"MM\x00\x2a" + struct.pack(">I", 8) + ifd
    app1 = b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, height, width, 3) + b"\x01\x11\x00\x02\x11\x01\x03\x11\x01"
    path.write_bytes(b"\xff\xd8" + app1 + sof + b"\xff\xd9")
    return path


def write_pdf(path: Path, pages: list[tuple[tuple[int, int], tuple[int, int, int, int], tuple[int, int, int]]]) -> Path:
    """ページごとに (大きさ pt, 四角 (x, y, w, h) を上からの pt で, 色) を塗った PDF。72dpi で 1pt = 1px。"""
    count = len(pages)
    objects = ["<< /Type /Catalog /Pages 2 0 R >>",
               f"<< /Type /Pages /Kids [{' '.join(f'{3 + i * 2} 0 R' for i in range(count))}] /Count {count} >>"]
    for i, ((pw, ph), (x, y, w, h), color) in enumerate(pages):
        rgb = " ".join(f"{c / 255:.4f}" for c in color)
        stream = f"{rgb} rg {x} {ph - y - h} {w} {h} re f"
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pw} {ph}] /Contents {4 + i * 2} 0 R >>")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    body = b"%PDF-1.4\n"
    offsets = []
    for n, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body += f"{n} 0 obj\n{obj}\nendobj\n".encode("ascii")
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    body += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    body += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    path.write_bytes(body)
    return path


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    """800x400 の写真。左半分は白、右半分に赤い四角。"""
    return write_rect_png(tmp_path / "写真.png", (800, 400), (500, 100, 200, 200), RED)


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    """2 ページの PDF。1 ページ目は A4 縦に赤い四角、2 ページ目は A4 横に青い四角。"""
    return write_pdf(tmp_path / "記録票.pdf", [((595, 842), (100, 100, 200, 200), RED),
                                               ((842, 595), (400, 200, 200, 200), BLUE)])


def crop(*args: str, env: dict | None = None):
    return run_script(SCRIPT, *args, env=env)


# --- 写真 -----------------------------------------------------------------

def test_image_info(photo: Path) -> None:
    rc, out, _ = crop("--src", str(photo), "--info")
    assert rc == 0
    assert out["kind"] == "image" and out["pages"] == 1 and out["sizes"] == [{"page": 1, "width": 800, "height": 400}]


@needs_browser
def test_image_box_and_rel_give_same_area(photo: Path, tmp_path: Path) -> None:
    rc, out, err = crop("--src", str(photo), "--box", "450,50,300,300", "--out", str(tmp_path / "a.png"))
    assert rc == 0, err
    assert out["box"] == [450, 50, 300, 300] and out["out_size"] == [300, 300] and out["warnings"] == []
    assert out["engine"] == "chrome" and out["source_size"] == [800, 400]
    rc, out, _ = crop("--src", str(photo), "--rel", "0.5625 0.125 0.375 0.75", "--out", str(tmp_path / "b.png"))
    assert rc == 0 and out["box"] == [450, 50, 300, 300]
    assert png_size(tmp_path / "a.png") == (300, 300)
    assert center_color(tmp_path / "a.png") == RED == center_color(tmp_path / "b.png")


@needs_browser
def test_image_warnings_do_not_fail(photo: Path, tmp_path: Path) -> None:
    rc, out, _ = crop("--src", str(photo), "--box", "10,10,20,20", "--out", str(tmp_path / "c.png"))
    assert rc == 0
    assert codes(out["warnings"]) == {"CROP-SMALL", "CROP-BLANK"}


@needs_browser
def test_image_max_width(photo: Path, tmp_path: Path) -> None:
    rc, out, _ = crop("--src", str(photo), "--rel", "0,0,1,1", "--max-width", "400", "--out", str(tmp_path / "d.png"))
    assert rc == 0 and out["scaled"] is True and out["out_size"] == [400, 200]
    assert png_size(tmp_path / "d.png") == (400, 200)
    rc, out, _ = crop("--src", str(photo), "--rel", "0,0,1,1", "--max-width", "0", "--out", str(tmp_path / "e.png"))
    assert rc == 0 and out["scaled"] is False and out["out_size"] == [800, 400]


def test_photo_orientation_is_applied(tmp_path: Path) -> None:
    path = write_jpeg_header(tmp_path / "縦の写真.jpg", (200, 100), orientation=6)  # 右に 90 度回して見る写真
    rc, out, _ = crop("--src", str(path), "--info")
    assert rc == 0 and out["sizes"][0]["width"] == 100 and out["sizes"][0]["height"] == 200


@pytest.mark.parametrize("extra", [
    ["--box", "700,0,200,100"],     # 右にはみ出す
    ["--rel", "0.5,0,0.6,1"],        # 割合が 1 を超える
    ["--box", "0,0,0,10"],           # 幅 0
    ["--box", "1,2,3"],              # 数が足りない
    ["--box", "a,0,10,10"],          # 数でない
    ["--box", "0,0,10,10", "--page", "2"],
    ["--box", "0,0,10,10", "--rel", "0,0,1,1"],
])
def test_image_usage_errors(photo: Path, tmp_path: Path, extra: list[str]) -> None:
    """範囲の誤りはブラウザを起こす前に止まる。"""
    rc, out, _ = crop("--src", str(photo), *extra, "--out", str(tmp_path / "x.png"))
    assert rc == 2 and out["status"] == "usage-error"
    assert not (tmp_path / "x.png").exists()


def test_other_usage_errors(photo: Path, tmp_path: Path) -> None:
    assert crop("--src", str(photo), "--box", "0,0,10,10", "--out", str(tmp_path / "x.jpg"))[0] == 2
    assert crop("--src", str(photo), "--box", "0,0,10,10", "--out", str(photo))[0] == 2
    assert crop("--src", str(photo), "--out", str(tmp_path / "x.png"))[0] == 2
    assert crop("--src", str(photo), "--box", "0,0,10,10")[0] == 2
    assert crop("--src", str(tmp_path / "なし.png"), "--info")[0] == 2
    assert crop("--src", str(photo), "--info", "--max-width", "-1")[0] == 2
    assert crop("--src", str(photo), "--info", "--engine", "auto")[0] == 2, "Python 版の --engine は無い"
    heic = tmp_path / "写真.heic"
    heic.write_bytes(b"x")
    rc, out, _ = crop("--src", str(heic), "--info")
    assert rc == 2 and "JPEG" in out["message"]
    broken = tmp_path / "壊れた.png"
    broken.write_bytes(b"not a png")
    assert crop("--src", str(broken), "--info")[0] == 2


def test_browser_not_found(photo: Path, tmp_path: Path) -> None:
    rc, out, _ = crop("--src", str(photo), "--box", "0,0,10,10", "--out", str(tmp_path / "x.png"),
                      "--browser", str(tmp_path / "chrome-なし"))
    assert rc == 3 and out["status"] == "tool-missing"


@needs_browser
def test_quiet_prints_one_line(photo: Path, tmp_path: Path) -> None:
    rc, out, _ = crop("--src", str(photo), "--box", "450,50,300,300", "--out", str(tmp_path / "q.png"), "--quiet")
    assert rc == 0 and out.startswith("crop: ok p1 (450,50,300,300)") and out.rstrip().endswith("300x300")


# --- PDF ------------------------------------------------------------------

@needs_poppler
def test_pdf_info(pdf: Path) -> None:
    rc, out, err = crop("--src", str(pdf), "--info", "--dpi", "144")
    assert rc == 0, err
    assert out["pages"] == 2 and out["engine"] == "pdfinfo"
    assert [(s["width"], s["height"]) for s in out["sizes"]] == [(1190, 1684), (1684, 1190)]
    assert out["sizes"][0]["width_pt"] == 595


@needs_poppler
@needs_browser
def test_pdf_crop_each_page(pdf: Path, tmp_path: Path) -> None:
    rc, out, err = crop("--src", str(pdf), "--dpi", "144", "--box", "150,150,500,500", "--out", str(tmp_path / "p1.png"))
    assert rc == 0, err
    assert out["source_size"] == [1190, 1684] and out["out_size"] == [500, 500] and out["dpi"] == 144
    assert near(center_color(tmp_path / "p1.png"), RED) and out["warnings"] == []
    rc, out, err = crop("--src", str(pdf), "--page", "2", "--dpi", "144", "--rel", "0.45,0.3,0.1,0.2",
                        "--out", str(tmp_path / "p2.png"))
    assert rc == 0, err
    assert out["source_size"] == [1684, 1190]
    assert near(center_color(tmp_path / "p2.png"), BLUE)


@needs_poppler
def test_pdf_missing_page(pdf: Path, tmp_path: Path) -> None:
    rc, out, _ = crop("--src", str(pdf), "--page", "3", "--rel", "0,0,1,1", "--out", str(tmp_path / "x.png"))
    assert rc == 2 and "3" in out["message"]


def test_pdf_dpi_range(pdf: Path) -> None:
    assert crop("--src", str(pdf), "--info", "--dpi", "601")[0] == 2
    assert crop("--src", str(pdf), "--info", "--dpi", "71")[0] == 2


def test_pdf_without_poppler(pdf: Path, tmp_path: Path) -> None:
    """pdftoppm が無ければ exit 3 で、PNG で保存して渡すよう案内する。--info は pdfinfo が無くても止めない。"""
    empty = tmp_path / "空の PATH"
    empty.mkdir()
    rc, out, _ = crop("--src", str(pdf), "--rel", "0,0,1,1", "--out", str(tmp_path / "x.png"), env={"PATH": str(empty)})
    assert rc == 3 and out["status"] == "tool-missing" and "PNG" in out["message"]
    rc, out, _ = crop("--src", str(pdf), "--info", env={"PATH": str(empty)})
    assert rc == 0 and out["pages"] is None and codes(out["warnings"]) == {"PDFINFO-MISSING"}
