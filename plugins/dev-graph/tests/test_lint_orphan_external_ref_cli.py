"""scripts/lint-orphan-external-ref.py の CLI 契約検証。

検査ロジックそのもの (OE-001 / OE-002 の判定・分類・ratchet 適用) は
``test_lint_orphan_external_ref.py`` が lib に対して固定する。本ファイルは CLI 境界、
すなわち **argv の解釈・入力欠損時の落ち方・出力先** だけを見る。

分けている理由は、ここで守る不変条件がロジックではなく「運用時の壊れ方」だから。
baseline を指定し損ねたときに黙って免除ゼロへ落ちる、bd を引けないのに緑を返す —
いずれもロジックが正しくても起きる。

baseline の実データと品質ゲートへの配線は、本 lint を使う repository 側の資産であり
portable な plugin では固定しない。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


# --- baseline の入力解決: 欠損を免除と取り違えない -------------------------


def test_absent_default_baseline_grants_no_exemption(tmp_path: Path, orphan_lint) -> None:
    """baseline 欠損は免除ゼロ (最も厳しい側)。ただし由来を残し暗黙に落ちない。"""
    baselined = orphan_lint.baselined
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[], beads=[orphan_lint.issue("BD-old", baselined)],
        baseline=None,
    )
    code, result = orphan_lint.run(root, export)
    assert code == 2
    assert result["baseline_source"] == "absent"
    assert [row["external_ref"] for row in result["violations"]] == [baselined]


def test_explicit_baseline_that_cannot_be_read_fails_instead_of_silently_empty(
    tmp_path: Path, orphan_lint,
) -> None:
    """指定ミスを免除ゼロと区別できないまま続行すると、意図した免除が黙って消える。"""
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[],
        beads=[orphan_lint.issue("BD-old", orphan_lint.baselined)],
    )
    missing = tmp_path / "nowhere.json"
    proc = subprocess.run(
        [sys.executable, "-B", str(orphan_lint.script), "--repo-root", str(root),
         "--beads-export", str(export), "--baseline", str(missing)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 1 and "baseline" in proc.stderr

    broken = tmp_path / "broken.json"
    broken.write_text('{"baselined_external_refs": "not-a-list"}', encoding="utf-8")
    proc2 = subprocess.run(
        [sys.executable, "-B", str(orphan_lint.script), "--repo-root", str(root),
         "--beads-export", str(export), "--baseline", str(broken)],
        capture_output=True, text=True, check=False,
    )
    assert proc2.returncode == 1 and "baseline" in proc2.stderr


def test_explicit_baseline_outside_the_convention_path_is_honoured(tmp_path: Path, orphan_lint) -> None:
    """repo 側データの置き場所は repository が決める。規約 path 以外も --baseline で渡せる。"""
    baselined = orphan_lint.baselined
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[], beads=[orphan_lint.issue("BD-old", baselined)], baseline=None,
    )
    elsewhere = tmp_path / "data" / "orphan-baseline.json"
    elsewhere.parent.mkdir()
    elsewhere.write_text(json.dumps({"baselined_external_refs": [baselined]}), encoding="utf-8")

    code, result = orphan_lint.run(root, export, "--baseline", str(elsewhere))
    assert code == 0
    assert result["baseline_source"] == str(elsewhere)
    assert [row["external_ref"] for row in result["baselined_orphans"]] == [baselined]


def test_unresolvable_beads_fails_closed_unless_explicitly_relaxed(
    tmp_path: Path, orphan_lint, monkeypatch,
) -> None:
    """bd を引けないのに緑を返すと、検査軸が成立していないのに『問題なし』と読める。"""
    root, _ = orphan_lint.repo(tmp_path, node_ids=["issue-alive"], beads=[])
    # PATH から bd を外し、export も渡さない = beads 解決不能。
    env = {"PATH": "/nonexistent", "PYTHONDONTWRITEBYTECODE": "1"}
    base = [sys.executable, "-B", str(orphan_lint.script), "--repo-root", str(root)]

    strict = subprocess.run(base, capture_output=True, text=True, check=False, env=env)
    assert strict.returncode == 2
    assert json.loads(strict.stdout)["beads_axis"] == "unavailable"
    assert "FAIL" in strict.stderr

    relaxed = subprocess.run([*base, "--no-require-beads"], capture_output=True, text=True, check=False, env=env)
    assert relaxed.returncode == 0
    assert json.loads(relaxed.stdout)["beads_axis"] == "unavailable"
    assert "NOTE" in relaxed.stderr


# --- argv と出力先 ---------------------------------------------------------


def test_issue_id_filter_narrows_the_scan(tmp_path: Path, orphan_lint) -> None:
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[],
        beads=[orphan_lint.issue("BD-a", "issue-x"),
               orphan_lint.issue("BD-b", "issue-y")],
    )
    code, result = orphan_lint.run(root, export, "--issue-id", "BD-b")
    assert code == 2 and result["scanned"] == 1
    assert [row["bd_issue_id"] for row in result["violations"]] == ["BD-b"]


def test_json_out_writes_the_same_payload(tmp_path: Path, orphan_lint) -> None:
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[], beads=[orphan_lint.issue("BD-a", "issue-x")],
    )
    out = tmp_path / "receipt" / "orphan.json"
    code, result = orphan_lint.run(root, export, "--json-out", str(out))
    assert code == 2
    assert json.loads(out.read_text(encoding="utf-8")) == result
