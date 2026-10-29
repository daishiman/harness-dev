"""validate-generation-lineage.py (HarnessHub-6cv) の検証。

supersede 済み旧世代 directory は byte-for-byte 不変で残る一方、名前が最も発見しやすく
render 済み成果物も同居するため、pointer を辿らない読み手が旧世代を正本と誤読しうる。
本 gate はその誤読を成立させない不変条件 (V1..V7) を機械化する。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import test_runtime as fx

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate-generation-lineage.py"
SLUG = "feature-package-feat-x"
PACKAGE_ID = "feature-package/feat-x"
LEGACY_REL = f".dev-graph/plans/{SLUG}"


def _write_package(root: Path, rel: str, specs: dict[str, str]) -> str:
    package = root / rel
    package.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    for name, content in specs.items():
        target = package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        files[name] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode()); digest.update(b"\0")
        digest.update((package / name).read_bytes()); digest.update(b"\0")
    canonical = "sha256:" + digest.hexdigest()
    (package / "staging-manifest.json").write_text(
        json.dumps({"canonical_digest": canonical, "files": files}), encoding="utf-8")
    (package / "atomic-promotion-receipt.json").write_text(
        json.dumps({"status": "promoted", "staging_digest": canonical,
                    "evaluated_digest": canonical, "published_digest": canonical}), encoding="utf-8")
    (package / "dev-graph-registration-receipt.json").write_text(
        json.dumps({"status": "registered", "source_digest": canonical}), encoding="utf-8")
    return canonical


def build_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """現行世代 + supersede 済み旧世代 + current pointer を持つ最小 repository。"""
    # C09 (resolve-project-context.py) が受理する最小 repository を作る。
    # path 検査は script 側で C09 へ一元化されているため、fixture も同じ前提を満たす必要がある。
    root = (tmp_path / "repo").resolve()
    root.mkdir(parents=True)
    fx.make_repo(root)
    legacy = _write_package(root, LEGACY_REL, {"task-specs/phase-01.md": "OLD"})
    generation = _write_package(root, f".dev-graph/plans/generations/{SLUG}/gen1",
                                {"task-specs/phase-01.md": "NEW"})
    pointer_dir = root / ".dev-graph" / "state" / "current"
    pointer_dir.mkdir(parents=True)
    (pointer_dir / f"{SLUG}.json").write_text(json.dumps({
        "schema_version": "1.0.0", "feature_package_id": PACKAGE_ID, "generation_id": "gen1",
        "published_path": f".dev-graph/plans/generations/{SLUG}/gen1",
        "published_digest": generation,
        "receipt": f".dev-graph/plans/generations/{SLUG}/gen1/atomic-promotion-receipt.json",
        "supersedes": {"published_path": LEGACY_REL, "published_digest": legacy,
                       "receipt": f"{LEGACY_REL}/atomic-promotion-receipt.json"},
    }), encoding="utf-8")
    return root, legacy, generation


def run(root: Path, *extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
    return subprocess.run([sys.executable, str(SCRIPT), "--repo-root", str(root), *extra],
                          capture_output=True, text=True, check=False, env=env)


def test_missing_marker_fails_closed(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    proc = run(root)
    assert proc.returncode == 2
    checks = [v["check"] for v in json.loads(proc.stdout)["violations"]]
    assert checks == ["V7-supersession-marker"]


def test_write_markers_makes_lineage_pass(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    assert run(root, "--write-markers").returncode == 0
    assert run(root).returncode == 0


def test_marker_write_is_idempotent(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    run(root, "--write-markers")
    first = (root / LEGACY_REL / "SUPERSEDED.json").read_bytes()
    run(root, "--write-markers")
    assert (root / LEGACY_REL / "SUPERSEDED.json").read_bytes() == first


def test_marker_does_not_change_superseded_digest(tmp_path: Path) -> None:
    # marker は canonical digest の対象集合 (staging-manifest.json の files) の外側にある
    root, legacy, _ = build_repo(tmp_path)
    run(root, "--write-markers")
    proc = run(root)
    assert proc.returncode == 0
    pointer = json.loads((root / ".dev-graph/state/current" / f"{SLUG}.json").read_text())
    assert pointer["supersedes"]["published_digest"] == legacy


def test_marker_points_at_current_generation(tmp_path: Path) -> None:
    root, legacy, generation = build_repo(tmp_path)
    run(root, "--write-markers")
    marker = json.loads((root / LEGACY_REL / "SUPERSEDED.json").read_text(encoding="utf-8"))
    assert marker["status"] == "superseded"
    assert marker["published_digest"] == legacy
    assert marker["superseded_by"]["published_digest"] == generation
    assert marker["current_pointer"] == f".dev-graph/state/current/{SLUG}.json"
    assert marker["superseded_receipts"]["promotion"]["path"] == \
        f"{LEGACY_REL}/atomic-promotion-receipt.json"
    assert marker["superseded_receipts"]["registration"]["path"] == \
        f"{LEGACY_REL}/dev-graph-registration-receipt.json"


def test_tampered_marker_fails_closed(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    run(root, "--write-markers")
    marker_path = root / LEGACY_REL / "SUPERSEDED.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["superseded_by"]["published_path"] = ".dev-graph/plans/generations/other/gen9"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    proc = run(root)
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["violations"][0]["check"] == "V7-supersession-marker"


def test_mutated_superseded_generation_fails_closed(tmp_path: Path) -> None:
    # 旧世代を現行世代へ「追随」させる上書き是正は V6 で拒否される
    root, _, _ = build_repo(tmp_path)
    run(root, "--write-markers")
    (root / LEGACY_REL / "task-specs" / "phase-01.md").write_text("NEW", encoding="utf-8")
    proc = run(root)
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["violations"][0]["check"] == "V6-superseded-digest"


def test_mutated_current_generation_fails_closed(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    run(root, "--write-markers")
    (root / f".dev-graph/plans/generations/{SLUG}/gen1/task-specs/phase-01.md").write_text("X", encoding="utf-8")
    proc = run(root)
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["violations"][0]["check"] == "V3-current-digest"


def test_missing_current_generation_fails_closed(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    (root / f".dev-graph/plans/generations/{SLUG}/gen1/task-specs/phase-01.md").unlink()
    proc = run(root)
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["violations"][0]["check"] == "V2-current-generation"


def test_receipt_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    receipt = root / f".dev-graph/plans/generations/{SLUG}/gen1/atomic-promotion-receipt.json"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["evaluated_digest"] = "sha256:" + "0" * 64
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    proc = run(root)
    assert proc.returncode == 2
    assert "V4-current-receipt" in [v["check"] for v in json.loads(proc.stdout)["violations"]]


def test_mutated_superseded_promotion_receipt_fails_closed(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    assert run(root, "--write-markers").returncode == 0
    receipt = root / LEGACY_REL / "atomic-promotion-receipt.json"
    receipt.write_text('{"tampered": true}', encoding="utf-8")
    proc = run(root)
    assert proc.returncode == 2
    assert "V7-supersession-marker" in [v["check"] for v in json.loads(proc.stdout)["violations"]]


def test_mutated_superseded_registration_receipt_fails_closed(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    assert run(root, "--write-markers").returncode == 0
    receipt = root / LEGACY_REL / "dev-graph-registration-receipt.json"
    receipt.write_text('{"tampered": true}', encoding="utf-8")
    proc = run(root)
    assert proc.returncode == 2
    assert "V7-supersession-marker" in [v["check"] for v in json.loads(proc.stdout)["violations"]]


def test_legacy_registration_receipt_name_is_supported(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    canonical = root / LEGACY_REL / "dev-graph-registration-receipt.json"
    canonical.rename(root / LEGACY_REL / "registration-receipt.json")
    assert run(root, "--write-markers").returncode == 0
    marker = json.loads((root / LEGACY_REL / "SUPERSEDED.json").read_text(encoding="utf-8"))
    assert marker["superseded_receipts"]["registration"]["path"] == \
        f"{LEGACY_REL}/registration-receipt.json"


def test_ambiguous_registration_receipt_names_fail_closed(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    canonical = root / LEGACY_REL / "dev-graph-registration-receipt.json"
    (root / LEGACY_REL / "registration-receipt.json").write_bytes(canonical.read_bytes())
    proc = run(root, "--write-markers")
    assert proc.returncode == 2
    assert "authority が一意でない" in json.loads(proc.stdout)["violations"][0]["detail"]


def test_write_markers_does_not_rebaseline_tampered_receipt(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    assert run(root, "--write-markers").returncode == 0
    marker_path = root / LEGACY_REL / "SUPERSEDED.json"
    marker_before = marker_path.read_bytes()
    receipt = root / LEGACY_REL / "atomic-promotion-receipt.json"
    receipt.write_text('{"tampered": true}', encoding="utf-8")
    proc = run(root, "--write-markers")
    assert proc.returncode == 2
    assert marker_path.read_bytes() == marker_before
    assert run(root).returncode == 2


def test_package_filter_scopes_the_check(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    assert run(root, "--package", SLUG).returncode == 2
    assert run(root, "--package", "feature-package-feat-absent").returncode == 2
    assert json.loads(run(root, "--package", SLUG, "--write-markers").stdout)["checked"] == 1


def test_pointer_without_supersedes_is_accepted(tmp_path: Path) -> None:
    # 初回 promotion (旧世代なし) は marker を要求しない
    root, _, _ = build_repo(tmp_path)
    pointer_path = root / ".dev-graph/state/current" / f"{SLUG}.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    del pointer["supersedes"]
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    assert run(root).returncode == 0


def test_empty_pointer_set_fails_closed(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    (root / ".dev-graph/state/current" / f"{SLUG}.json").unlink()
    proc = run(root)
    assert proc.returncode == 2
    assert "current pointer が 0 件" in proc.stderr


def test_current_pointer_symlink_escape_fails_closed(tmp_path: Path) -> None:
    root, _, _ = build_repo(tmp_path)
    pointer = root / ".dev-graph/state/current" / f"{SLUG}.json"
    outside = tmp_path / "outside-pointer.json"
    outside.write_bytes(pointer.read_bytes())
    pointer.unlink()
    pointer.symlink_to(outside.resolve())
    proc = run(root)
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["violations"][0]["check"] == "V1-pointer-schema"


def test_manifest_entry_escaping_repo_fails_closed(tmp_path: Path) -> None:
    # 悪意ある manifest が `../` で repository 外の bytes を digest へ取り込む read escape を拒否
    root, _, generation = build_repo(tmp_path)
    outside = tmp_path / "outside" / "secret.txt"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("SECRET", encoding="utf-8")
    gen_manifest = root / f".dev-graph/plans/generations/{SLUG}/gen1" / "staging-manifest.json"
    payload = json.loads(gen_manifest.read_text(encoding="utf-8"))
    payload["files"]["../../../../outside/secret.txt"] = "0" * 64
    gen_manifest.write_text(json.dumps(payload), encoding="utf-8")
    proc = run(root)
    assert proc.returncode == 2
    assert any("repository 外" in v["detail"] for v in json.loads(proc.stdout)["violations"])


def test_manifest_file_symlink_escaping_repo_fails_closed(tmp_path: Path) -> None:
    # manifest 記載 file 自体が repository 外への symlink の場合も read escape を拒否
    root, _, _ = build_repo(tmp_path)
    outside = tmp_path / "outside" / "secret.txt"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("SECRET", encoding="utf-8")
    victim = root / f".dev-graph/plans/generations/{SLUG}/gen1/task-specs/phase-01.md"
    victim.unlink()
    victim.symlink_to(outside.resolve())
    proc = run(root)
    assert proc.returncode == 2
