"""C13 embed-assets.py の受入テスト共通ヘルパ (P04-C13-01)。

方針:
- 契約は `plugin-plans/guide-doc-generator/briefs/script-brief-C13.json` の
  argv / stdout / stderr / exit_codes / algorithm / acceptance_checks / failure_modes
  からだけ起こす。推測で新しい契約を発明しない。
- 実装が未存在でも import 例外にしない。require_script() が「実装が無い」という
  診断可能なアサーション失敗 (failures) として赤を出す。
- 素材は全てテスト実行時に生成する。repo 内へバイナリ fixture を置かない。
- 実 plugin ツリーへ 1 バイトも書かない。素材も構成データも tempdir に作る。

C13 の責務境界 (P03 Y-04):
  C13 は data URI 化だけを行い、出力ディレクトリへの原本コピーや
  handout-config.json の配置は C19 の責務。ここでは「置かないこと」も検査する。
"""

from __future__ import annotations

import io
import json
import os
import struct
import subprocess
import sys
import unittest
import zipfile
import zlib
from pathlib import Path

# tests/embed-assets.py/ -> tests -> guide-doc-generator -> plugins -> repo root
TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TESTS_DIR.parents[1]
REPO_ROOT = TESTS_DIR.parents[3]

SCRIPT = PLUGIN_ROOT / "scripts" / "embed-assets.py"

# argv 契約 (script-brief-C13.json argv)
DEFAULT_MAX_BYTES = 5242880

# AC-C13-2 が名指しする MIME (C13 自前対応表の期待値)。
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_ZIP = "application/zip"
MIME_PDF = "application/pdf"
MIME_PNG = "image/png"
MIME_OCTET = "application/octet-stream"

# algorithm 7 / 8 が定める素材オブジェクトの追加フィールド。
STATUS_EMBEDDED = "embedded"
STATUS_SKIPPED = "skipped-oversize"

# algorithm 9 が定める資料単位サマリ。
SUMMARY_KEY = "asset_embedding"
SUMMARY_FIELDS = (
    "max_bytes",
    "embedded_count",
    "skipped_count",
    "total_source_bytes",
    "total_encoded_chars",
    "warnings",
)

# stderr の warning 行形式 (stderr 契約): `WARN <asset_id>: <reason>; 代替手段: <hint>`
WARN_PREFIX = "WARN "
WARN_HINT_SEP = "; 代替手段: "


class MissingArtifact(AssertionError):
    """実装成果物がまだ存在しないことを示す (P04 では赤が正しい状態)。"""


def require_script(tc: unittest.TestCase) -> Path:
    if not SCRIPT.is_file():
        tc.fail(
            "実装が未存在: {} (P04 時点ではこの失敗が期待値。P05 で解消する)".format(SCRIPT)
        )
    return SCRIPT


def script_source(tc: unittest.TestCase) -> str:
    require_script(tc)
    return SCRIPT.read_text(encoding="utf-8")


def clean_env(**overrides) -> dict:
    env = dict(os.environ)
    for key in ("HB_ROOT", "CLAUDE_PLUGIN_ROOT"):
        env.pop(key, None)
    env["PYTHONIOENCODING"] = "utf-8"
    env.update({k: v for k, v in overrides.items() if v is not None})
    return env


def run(args, env=None, cwd=None, stdin_data: str | None = None):
    """script を subprocess で起動する。戻り値は CompletedProcess (bytes)。"""
    cmd = [sys.executable, str(SCRIPT), *[str(a) for a in args]]
    return subprocess.run(
        cmd,
        input=(stdin_data or "").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env if env is not None else clean_env(),
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        timeout=60,
    )


def run_embed(
    tc: unittest.TestCase,
    config_path,
    assets_dir,
    max_bytes=None,
    out=None,
    extra_args=(),
    stdin_data: str | None = None,
    cwd=None,
):
    require_script(tc)
    args = ["--config", config_path, "--assets-dir", assets_dir]
    if max_bytes is not None:
        args += ["--max-bytes", max_bytes]
    if out is not None:
        args += ["--out", out]
    args += list(extra_args)
    return run(args, stdin_data=stdin_data, cwd=cwd)


def out_text(proc) -> str:
    return proc.stdout.decode("utf-8")


def err_text(proc) -> str:
    return proc.stderr.decode("utf-8")


def describe(proc) -> str:
    return "exit={}\n--- stdout ---\n{}\n--- stderr ---\n{}".format(
        proc.returncode, out_text(proc)[:4000], err_text(proc)[:4000]
    )


def parse_stdout_json(tc: unittest.TestCase, proc):
    text = out_text(proc)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        tc.fail("stdout が構成データ JSON として読めない ({}):\n{}".format(exc, describe(proc)))


def load_json_file(tc: unittest.TestCase, path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        tc.fail("--out が書かれていない: {}".format(path))
    except json.JSONDecodeError as exc:
        tc.fail("--out の内容が JSON として読めない: {} ({})".format(path, exc))


# --------------------------------------------------------------------------
# 素材バイト列の生成 (実バイトのシグネチャを持つ最小ファイル)
# --------------------------------------------------------------------------


def png_bytes(payload_size: int = 0) -> bytes:
    """1x1 PNG。payload_size を与えると tEXt チャンクで嵩増しして総バイト数を増やす。"""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\xff\xff"
    body = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
    )
    if payload_size > 0:
        body += chunk(b"tEXt", b"pad\x00" + b"a" * payload_size)
    return body + chunk(b"IEND", b"")


def jpeg_bytes(payload_size: int = 0) -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * (16 + payload_size) + b"\xff\xd9"


def gif_bytes() -> bytes:
    return b"GIF89a" + b"\x01\x00\x01\x00\x80\x00\x00" + b"\x00" * 8 + b";"


def webp_bytes() -> bytes:
    payload = b"VP8 " + b"\x00" * 16
    return b"RIFF" + struct.pack("<I", len(payload) + 4) + b"WEBP" + payload


def svg_bytes() -> bytes:
    return (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1">'
        b"<rect width=\"1\" height=\"1\"/></svg>"
    )


def pdf_bytes(payload_size: int = 0) -> bytes:
    return b"%PDF-1.4\n" + b"% pad " + b"p" * payload_size + b"\n%%EOF\n"


def zip_bytes(entry: str = "note.txt", payload: bytes = b"hello", extra: int = 0) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr(entry, payload + b"x" * extra)
    return buf.getvalue()


def xlsx_bytes(extra: int = 0) -> bytes:
    """xlsx は実体が zip。中身は最小の OOXML 風エントリで足りる (C13 は解釈しない)。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>" + " " * extra)
        zf.writestr("xl/workbook.xml", "<workbook/>")
    return buf.getvalue()


def bin_bytes(size: int = 32) -> bytes:
    """MIME 対応表に無い拡張子で使う中身 (シグネチャを持たない)。"""
    return bytes(range(min(size, 256))) * max(1, size // 256)


# --------------------------------------------------------------------------
# fixture の組み立て
# --------------------------------------------------------------------------


def write_asset(assets_dir: Path, relpath: str, data: bytes) -> Path:
    path = Path(assets_dir) / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def image_asset(asset_id: str, src: str, role: str = "screenshot", alt: str = "画面の説明") -> dict:
    """C12 正規化済み構成データの assets[] 要素 (script-brief-C12.json の assets 制約)。"""
    return {
        "id": asset_id,
        "kind": "image",
        "src": src,
        "alt": alt,
        "caption": None,
        "role": role,
    }


def attachment(att_id: str, filename: str, mime: str, src: str, hint: str = "同梱の素材ディレクトリを参照") -> dict:
    """C12 正規化済み構成データの attachments[] 要素。"""
    return {
        "id": att_id,
        "filename": filename,
        "mime": mime,
        "src": src,
        "fallback_hint": hint,
    }


def make_config(assets=None, attachments=None, title: str = "研修ハンドアウト") -> dict:
    """最小の正規化済み構成データ。キー順は挿入順 = 出力でも保存される契約 (stdout 契約)。"""
    return {
        "schema_version": 1,
        "title": title,
        "presentation_order": "demo_first",
        "assets": list(assets or []),
        "attachments": list(attachments or []),
        "sections": [],
    }


def write_config(tmp: Path, config, name: str = "handout-config.json") -> Path:
    path = Path(tmp) / name
    if isinstance(config, (dict, list)):
        text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    else:
        text = str(config)
    path.write_text(text, encoding="utf-8")
    return path


def make_workspace(tc: unittest.TestCase, tmp: Path) -> tuple[Path, Path]:
    """(assets_dir, work_dir) を作る。assets_dir は read-only 契約の検査対象。"""
    assets_dir = Path(tmp) / "assets-src"
    work_dir = Path(tmp) / "work"
    assets_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    return assets_dir, work_dir


# --------------------------------------------------------------------------
# 出力の読み取り
# --------------------------------------------------------------------------


def find_entry(tc: unittest.TestCase, config: dict, collection: str, entry_id: str) -> dict:
    for item in config.get(collection) or []:
        if isinstance(item, dict) and item.get("id") == entry_id:
            return item
    tc.fail("出力の {} に id={} が無い: {}".format(collection, entry_id, json.dumps(config, ensure_ascii=False)[:2000]))


def data_uri_of(tc: unittest.TestCase, entry: dict) -> str:
    uri = entry.get("data_uri")
    if not isinstance(uri, str) or not uri:
        tc.fail("data_uri が無い/文字列でない: {}".format(json.dumps(entry, ensure_ascii=False)))
    return uri


def data_uri_mime(tc: unittest.TestCase, uri: str) -> str:
    if not uri.startswith("data:"):
        tc.fail("data URI が data: で始まらない: {}".format(uri[:80]))
    head, sep, _payload = uri.partition(",")
    if not sep:
        tc.fail("data URI に ',' が無い: {}".format(uri[:80]))
    if not head.endswith(";base64"):
        tc.fail("data URI が ;base64 でない: {}".format(head[:120]))
    return head[len("data:") : -len(";base64")]


def data_uri_payload(tc: unittest.TestCase, uri: str) -> str:
    _head, sep, payload = uri.partition(",")
    if not sep:
        tc.fail("data URI に ',' が無い: {}".format(uri[:80]))
    return payload


def warn_lines(proc) -> list[str]:
    return [ln for ln in err_text(proc).splitlines() if ln.startswith(WARN_PREFIX)]


def summary_of(tc: unittest.TestCase, config: dict) -> dict:
    summary = config.get(SUMMARY_KEY)
    if not isinstance(summary, dict):
        tc.fail(
            "構成データ直下に {} サマリが無い (algorithm 9): keys={}".format(
                SUMMARY_KEY, sorted(config.keys())
            )
        )
    return summary


def tree_snapshot(root: Path) -> dict:
    """ディレクトリ配下の相対パス -> バイト列。read-only 契約の検査に使う。"""
    snap = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file() and not path.is_symlink():
            snap[str(path.relative_to(root))] = path.read_bytes()
        elif path.is_symlink():
            snap[str(path.relative_to(root))] = b"<symlink>" + os.readlink(path).encode("utf-8")
    return snap
