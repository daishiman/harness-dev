"""verify_notion_assets.py を genuine に網羅する。

名前に notion を含むが network/Notion API は一切叩かず、manifest(JSON)に列挙された
items の *ローカルファイル存在* と *sha256_16 ハッシュ照合* を行う純粋なオフライン検証器。
よって実通信 stub は不要で、tmp_path に合格 fixture / 各違反 fixture を作って検証する:

  - hash_file: 65536 byte chunk 読みで sha256 先頭16桁を返す。
  - verify: invalid_manifest 系 (読めない/非object/items欠落/items非list/items空/item非dict),
    missing (path/absolute 解決後に不在), corrupted (sha256_16 不一致), ok=True を網羅。
    dest による base_dir 上書き、absolute 優先、path↔absolute フォールバックも確認。
  - main: argv 不足 (2)/manifest 欠落 (2)/invalid_manifest (2)/ok (0)/不一致 (1) の exit code、
    stdout の JSON 形, stderr メッセージを assert。importlib in-process と subprocess 双方。

tests/scripts3 等と衝突しない _r4 名で in-process ロードする。
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "verify_notion_assets.py"

_SPEC = importlib.util.spec_from_file_location("verify_notion_assets_r4", SCRIPT)
VNA = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(VNA)


def _sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


# --------------------------------------------------------------------------
# hash_file
# --------------------------------------------------------------------------

def test_hash_file_small(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello world")
    assert VNA.hash_file(str(f)) == _sha16(b"hello world")


def test_hash_file_multi_chunk(tmp_path):
    # 65536 byte chunk 境界を跨ぐ大きさで iter ループを実走させる。
    data = b"x" * (65536 * 2 + 17)
    f = tmp_path / "big.bin"
    f.write_bytes(data)
    assert VNA.hash_file(str(f)) == _sha16(data)


def test_hash_file_empty(tmp_path):
    f = tmp_path / "empty.bin"
    f.write_bytes(b"")
    assert VNA.hash_file(str(f)) == _sha16(b"")


# --------------------------------------------------------------------------
# verify: invalid_manifest 系
# --------------------------------------------------------------------------

def _write_manifest(tmp_path, obj):
    p = tmp_path / "manifest.json"
    if isinstance(obj, str):
        p.write_text(obj, encoding="utf-8")
    else:
        p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def test_verify_unreadable_json(tmp_path):
    mp = _write_manifest(tmp_path, "{not valid json")
    r = VNA.verify(mp)
    assert r["ok"] is False
    assert r["invalid_manifest"]
    assert r["total"] == 0


def test_verify_root_not_object(tmp_path):
    mp = _write_manifest(tmp_path, [1, 2, 3])
    r = VNA.verify(mp)
    assert r["ok"] is False
    assert r["invalid_manifest"] == "manifest root must be an object"


def test_verify_items_missing(tmp_path):
    mp = _write_manifest(tmp_path, {"dest": str(tmp_path)})
    r = VNA.verify(mp)
    assert r["invalid_manifest"] == "manifest.items is required"


def test_verify_items_not_list(tmp_path):
    mp = _write_manifest(tmp_path, {"items": {"path": "x"}})
    r = VNA.verify(mp)
    assert r["invalid_manifest"] == "manifest.items must be an array"


def test_verify_items_empty(tmp_path):
    mp = _write_manifest(tmp_path, {"items": []})
    r = VNA.verify(mp)
    assert r["invalid_manifest"] == "manifest.items must not be empty"


# --------------------------------------------------------------------------
# verify: item レベル
# --------------------------------------------------------------------------

def test_verify_item_not_dict_is_corrupted(tmp_path):
    mp = _write_manifest(tmp_path, {"items": ["a string item"]})
    r = VNA.verify(mp)
    assert r["ok"] is False
    assert r["corrupted"] == [{"path": "", "reason": "manifest item must be an object"}]
    assert r["total"] == 1


def test_verify_missing_file_via_path_and_dest(tmp_path):
    # dest を base_dir に、path 相対で解決 → 不在なら missing に rel_path。
    mp = _write_manifest(tmp_path, {"dest": str(tmp_path), "items": [{"path": "ghost.txt"}]})
    r = VNA.verify(mp)
    assert r["ok"] is False
    assert r["missing"] == ["ghost.txt"]
    assert r["corrupted"] == []


def test_verify_missing_without_dest_uses_manifest_dir(tmp_path):
    # dest 無し → manifest.json の dirname が base_dir。存在する隣接ファイルは OK。
    (tmp_path / "present.txt").write_bytes(b"data")
    mp = _write_manifest(tmp_path, {"items": [{"path": "present.txt"}]})
    r = VNA.verify(mp)
    assert r["ok"] is True
    assert r["missing"] == []
    assert r["total"] == 1


def test_verify_absolute_overrides_path(tmp_path):
    # absolute 指定があれば dest/path を無視して absolute を使う。
    target = tmp_path / "sub" / "file.txt"
    target.parent.mkdir()
    target.write_bytes(b"abc")
    mp = _write_manifest(
        tmp_path,
        {"dest": "/nonexistent-base", "items": [{"path": "ignored.txt", "absolute": str(target)}]},
    )
    r = VNA.verify(mp)
    assert r["ok"] is True


def test_verify_rel_path_falls_back_to_absolute_when_no_path(tmp_path):
    # path 無し・absolute あり → rel_path は absolute を使う。存在すれば OK。
    target = tmp_path / "only_abs.txt"
    target.write_bytes(b"z")
    mp = _write_manifest(tmp_path, {"items": [{"absolute": str(target)}]})
    r = VNA.verify(mp)
    assert r["ok"] is True


def test_verify_sha_match_ok(tmp_path):
    f = tmp_path / "good.txt"
    f.write_bytes(b"content-A")
    mp = _write_manifest(
        tmp_path,
        {"items": [{"path": "good.txt", "sha256_16": _sha16(b"content-A")}]},
    )
    r = VNA.verify(mp)
    assert r["ok"] is True
    assert r["corrupted"] == [] and r["missing"] == []
    assert r["total"] == 1


def test_verify_sha_mismatch_corrupted(tmp_path):
    f = tmp_path / "bad.txt"
    f.write_bytes(b"content-B")
    mp = _write_manifest(
        tmp_path,
        {"items": [{"path": "bad.txt", "sha256_16": "0000000000000000"}]},
    )
    r = VNA.verify(mp)
    assert r["ok"] is False
    assert len(r["corrupted"]) == 1
    c = r["corrupted"][0]
    assert c["path"] == "bad.txt"
    assert c["expected"] == "0000000000000000"
    assert c["actual"] == _sha16(b"content-B")


def test_verify_no_sha_skips_hash_check(tmp_path):
    # sha256_16 が無ければ存在のみ確認しハッシュ照合しない。
    f = tmp_path / "nohash.txt"
    f.write_bytes(b"whatever")
    mp = _write_manifest(tmp_path, {"items": [{"path": "nohash.txt"}]})
    r = VNA.verify(mp)
    assert r["ok"] is True


def test_verify_mixed_missing_and_corrupted(tmp_path):
    present = tmp_path / "p.txt"
    present.write_bytes(b"P")
    mp = _write_manifest(
        tmp_path,
        {
            "items": [
                {"path": "p.txt", "sha256_16": "deadbeefdeadbeef"},  # corrupted
                {"path": "absent.txt"},  # missing
            ]
        },
    )
    r = VNA.verify(mp)
    assert r["ok"] is False
    assert r["missing"] == ["absent.txt"]
    assert len(r["corrupted"]) == 1
    assert r["total"] == 2


# --------------------------------------------------------------------------
# main: CLI exit codes / stdout / stderr (in-process)
# --------------------------------------------------------------------------

def test_main_usage_when_no_arg(capsys):
    rc = VNA.main(["prog"])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


def test_main_manifest_missing(capsys, tmp_path):
    rc = VNA.main(["prog", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "manifest missing" in capsys.readouterr().err


def test_main_invalid_manifest_returns_2(capsys, tmp_path):
    mp = _write_manifest(tmp_path, "{broken")
    rc = VNA.main(["prog", mp])
    assert rc == 2
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["ok"] is False
    assert payload["invalid_manifest"]


def test_main_ok_returns_0(capsys, tmp_path):
    f = tmp_path / "ok.txt"
    f.write_bytes(b"OK")
    mp = _write_manifest(
        tmp_path, {"items": [{"path": "ok.txt", "sha256_16": _sha16(b"OK")}]}
    )
    rc = VNA.main(["prog", mp])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["total"] == 1


def test_main_verification_failure_returns_1(capsys, tmp_path):
    f = tmp_path / "f.txt"
    f.write_bytes(b"data")
    mp = _write_manifest(
        tmp_path, {"items": [{"path": "f.txt", "sha256_16": "1111111111111111"}]}
    )
    rc = VNA.main(["prog", mp])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert len(payload["corrupted"]) == 1


# --------------------------------------------------------------------------
# CLI: subprocess で __main__ 経路を実行 (exit code 実証)
# --------------------------------------------------------------------------

def test_cli_subprocess_ok(tmp_path):
    f = tmp_path / "c.txt"
    f.write_bytes(b"cli")
    mp = tmp_path / "m.json"
    mp.write_text(
        json.dumps({"items": [{"path": "c.txt", "sha256_16": _sha16(b"cli")}]}),
        encoding="utf-8",
    )
    proc = __import__("subprocess").run(
        [sys.executable, str(SCRIPT), str(mp)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=30,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["ok"] is True


def test_cli_subprocess_missing_manifest():
    proc = __import__("subprocess").run(
        [sys.executable, str(SCRIPT), "/definitely/not/here.json"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=30,
    )
    assert proc.returncode == 2
    assert "manifest missing" in proc.stderr
