"""PostToolUse 事後監査: C10 が遮断できない経路の drift 検出 (HarnessHub-kzth)。

背景:
  C10 PreToolUse は「interpreter 起動 x 書込み動詞 x authority path」の共起をコマンド文字列
  から読んで遮断する。書込みを別 script file へ移した間接起動 (`python3 tools/writer.py`) は
  この 3 条件が文字列上で 1 つも成立しないため、PreToolUse では原理的に遮断できない。script の
  中身を読めば遮断できるが、それは HarnessHub-6in4 で実測した fail-open 窓 (Bash 枝 39.79s) を
  再び開く。

本 test が固定する契約:
  1. 判定は「誰が書いたか」ではなく「書かれた結果が正規 writer の残す形か」に置く。中核は
     graph_revision の +1 不変条件 (C02 writer は 1 回の書込みにつき必ず +1 する)。
  2. confirmed (正規 writer では成立し得ない形 / exit 2) と advisory (正規運用でも起こり得る
     弱い痕跡 / exit 0) を混ぜない。VCS 操作に伴う revision 後退を confirmed にすると日常操作が
     毎回赤くなり、監査そのものが無視される。
  3. confirmed drift は破損状態を新しい基準へ採用せず、正規 writer による修復まで再通知する。
     PostToolUse は既に行われた変更を巻き戻せないため、1 回だけの警告では fail-closed にならない。
  4. 未変更時に digest を計算しない (全 Bash 実行後に走るため、監査コストが常時課金される)。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
HOOK = PLUGIN / "hooks" / "audit-graph-authority-drift.py"
GRAPH_RELATIVE = ".dev-graph/state/graph.json"
CONFIG_RELATIVE = ".dev-graph/config.json"
LEDGER_RELATIVE = ".dev-graph/tmp/authority-audit.json"


def run(root: Path, command: str) -> tuple[int, dict, str]:
    """hook を実プロセスとして起動し (exit code, stdout receipt, stderr) を返す。"""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(
        [sys.executable, "-B", str(HOOK), "--repo-root", str(root)],
        input=payload, capture_output=True, text=True, check=False,
    )
    receipt = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, receipt, proc.stderr


def codes(exit_code: int, receipt: dict, stderr: str) -> set[str]:
    found = {f"{item['code']}/{item['severity']}" for item in receipt.get("findings", [])}
    for line in stderr.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and ": " in stripped:
            found.add(stripped.split(": ", 2)[1] + "/confirmed")
    return found


def write_graph(root: Path, revision: int, *, nodes=None, extra=None) -> None:
    document = {
        "schema_version": "1.0.0",
        "repository_id": "probe-repo",
        "graph_revision": revision,
        "nodes": [] if nodes is None else nodes,
    }
    if extra:
        document.update(extra)
    path = root / GRAPH_RELATIVE
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    _advance_mtime(path)


def _advance_mtime(path: Path) -> None:
    """mtime を確実に進める。

    同一 tick 内の書換えは size/mtime 早期打ち切りに吸収され、test が測りたい digest 比較へ
    到達しない。実運用では書込み間隔が tick より長いのが通常なので、ここは test 環境の
    時間解像度を補正しているだけで、監査ロジックの緩和ではない。
    """
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns + 10**9, stat.st_mtime_ns + 10**9))


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".dev-graph" / "state").mkdir(parents=True)
    (root / CONFIG_RELATIVE).write_text(
        json.dumps({"repository_id": "probe-repo"}), encoding="utf-8"
    )
    write_graph(root, 5)
    # baseline 採用 (初回は必ず無警告)。
    assert run(root, "echo bootstrap")[0] == 0
    return root


def test_first_run_adopts_canonical_baseline_without_reporting_drift(tmp_path: Path) -> None:
    """台帳が無い状態を「全部 drift」にしない。

    clone 直後や台帳削除のたびに confirmed が出ると、監査の出力が信用されなくなり、
    本物の drift も読み飛ばされる。
    """
    root = tmp_path / "repo"
    (root / ".dev-graph" / "state").mkdir(parents=True)
    (root / CONFIG_RELATIVE).write_text(json.dumps({"repository_id": "r"}), encoding="utf-8")
    write_graph(root, 0)

    exit_code, receipt, stderr = run(root, "echo first")
    assert exit_code == 0, stderr
    assert codes(exit_code, receipt, stderr) == set()

    ledger = json.loads((root / LEDGER_RELATIVE).read_text(encoding="utf-8"))
    baseline = ledger["baselines"][GRAPH_RELATIVE]
    assert baseline["graph_revision"] == 0
    assert baseline["digest"].startswith("sha256:")


@pytest.mark.parametrize(
    "raw",
    ["{broken", json.dumps({"nodes": [], "backdoor": True})],
)
def test_first_run_rejects_broken_authority_instead_of_blessing_it(
    tmp_path: Path, raw: str
) -> None:
    """台帳削除と authority 破損を同じ command で行っても初回採用へ逃がさない。"""
    root = tmp_path / "repo"
    (root / ".dev-graph" / "state").mkdir(parents=True)
    (root / CONFIG_RELATIVE).write_text(json.dumps({"repository_id": "r"}), encoding="utf-8")
    (root / GRAPH_RELATIVE).write_text(raw, encoding="utf-8")

    exit_code, receipt, stderr = run(root, "python3 tools/indirect.py")
    assert exit_code == 2, receipt
    assert codes(exit_code, receipt, stderr) & {
        "unparsable_authority/confirmed",
        "envelope_violation/confirmed",
    }
    ledger = json.loads((root / LEDGER_RELATIVE).read_text(encoding="utf-8"))
    assert ledger["baselines"][GRAPH_RELATIVE] == {}


def test_content_change_without_revision_advance_is_confirmed_drift(repo: Path) -> None:
    """内容が変わって graph_revision が進まない形は C02 writer では成立しない。

    これが事後検出の中核。script file 経由の素朴な書込みは revision を触らないため、
    ここで必ず現れる。
    """
    write_graph(repo, 5, nodes=[{"id": "injected"}])
    exit_code, receipt, stderr = run(repo, "python3 tools/writer.py")

    assert exit_code == 2, receipt
    assert "revision_not_advanced/confirmed" in codes(exit_code, receipt, stderr)
    assert "build-graph-node.py" in stderr, "是正手順 (C02 writer) が案内されていない"


def test_sanctioned_writer_with_advanced_revision_is_silent(repo: Path) -> None:
    """正規経路は無警告。ここが鳴ると監査が日常運用のノイズになる。"""
    write_graph(repo, 6, nodes=[{"id": "legit"}])
    exit_code, receipt, stderr = run(
        repo, "python3 plugins/dev-graph/scripts/build-graph-node.py update --repo-root . --input .dev-graph/tmp/update.json"
    )
    assert exit_code == 0, stderr
    assert codes(exit_code, receipt, stderr) == set()


def test_advanced_revision_without_writer_name_is_advisory_only(repo: Path) -> None:
    """writer 名の不在は弱い証拠に留める。

    正規 writer を wrapper script から呼ぶ運用と、迂回書込みが revision まで正しく +1 した
    場合は、コマンド文字列上では区別できない。confirmed にすると前者を毎回誤検出する。
    """
    write_graph(repo, 6, nodes=[{"id": "legit"}])
    exit_code, receipt, stderr = run(repo, "python3 tools/indirect.py")

    assert exit_code == 0, stderr
    assert codes(exit_code, receipt, stderr) == {"writer_not_observed/advisory"}


def test_noncanonical_envelope_is_confirmed_drift(repo: Path) -> None:
    """revision を正しく進めても、未知 key の混入は正規 writer が書かない形として残る。"""
    write_graph(repo, 6, extra={"backdoor": True})
    exit_code, receipt, stderr = run(repo, "python3 tools/indirect.py")

    assert exit_code == 2
    assert "envelope_violation/confirmed" in codes(exit_code, receipt, stderr)


def test_vcs_transition_downgrades_revision_rollback_to_advisory(repo: Path) -> None:
    """checkout/merge は履歴移動なので revision は後退し得る。"""
    write_graph(repo, 3, nodes=[{"id": "old"}])
    exit_code, receipt, stderr = run(repo, "git checkout main")

    assert exit_code == 0, stderr
    assert codes(exit_code, receipt, stderr) == {"revision_not_advanced/advisory"}


def test_vcs_transition_with_read_only_git_suffix_stays_advisory(repo: Path) -> None:
    """履歴移動と read-only git command の連結は通常の VCS 操作として扱う。"""
    write_graph(repo, 3, nodes=[{"id": "old"}])
    exit_code, receipt, stderr = run(repo, "git merge main && git status")

    assert exit_code == 0, stderr
    assert codes(exit_code, receipt, stderr) == {"revision_not_advanced/advisory"}


def test_vcs_transition_mixed_with_non_git_command_stays_confirmed(repo: Path) -> None:
    """git 文字列の混在だけで、後続の迂回 writer を VCS 操作へ偽装できない。"""
    write_graph(repo, 3, nodes=[{"id": "old"}])
    exit_code, receipt, stderr = run(
        repo, "git checkout main && python3 tools/indirect.py"
    )

    assert exit_code == 2
    assert "revision_not_advanced/confirmed" in codes(exit_code, receipt, stderr)


def test_plain_rollback_without_vcs_stays_confirmed(repo: Path) -> None:
    """VCS 操作を伴わない revision 後退は緩めない (advisory 化の適用範囲を固定する)。"""
    write_graph(repo, 3, nodes=[{"id": "old"}])
    exit_code, receipt, stderr = run(repo, "python3 tools/indirect.py")

    assert exit_code == 2
    assert "revision_not_advanced/confirmed" in codes(exit_code, receipt, stderr)


def test_authority_removal_and_corruption_are_confirmed(repo: Path) -> None:
    (repo / GRAPH_RELATIVE).unlink()
    exit_code, receipt, stderr = run(repo, "rm -f graph")
    assert exit_code == 2
    assert "authority_removed/confirmed" in codes(exit_code, receipt, stderr)

    (repo / GRAPH_RELATIVE).write_text("{broken", encoding="utf-8")
    _advance_mtime(repo / GRAPH_RELATIVE)
    exit_code, receipt, stderr = run(repo, "python3 tools/indirect.py")
    assert exit_code == 2
    assert "unparsable_authority/confirmed" in codes(exit_code, receipt, stderr)


def test_identical_rewrite_is_not_drift(repo: Path) -> None:
    """mtime だけ動いた同一内容の再書込みは drift ではない (digest が最終判定)。"""
    write_graph(repo, 5)
    exit_code, receipt, stderr = run(repo, "python3 tools/indirect.py")
    assert exit_code == 0, stderr
    assert codes(exit_code, receipt, stderr) == set()


def test_config_authority_is_audited_too(repo: Path) -> None:
    config = repo / CONFIG_RELATIVE
    config.write_text(
        json.dumps({"repository_id": "probe-repo", "tampered": 1}), encoding="utf-8"
    )
    _advance_mtime(config)
    exit_code, receipt, stderr = run(repo, "python3 tools/indirect.py")

    # config には graph_revision が無いため、判定材料は writer 名だけになる。
    assert exit_code == 0
    assert codes(exit_code, receipt, stderr) == {"writer_not_observed/advisory"}
    assert receipt["findings"][0]["path"] == CONFIG_RELATIVE


def test_confirmed_drift_repeats_until_a_sanctioned_writer_repairs_it(repo: Path) -> None:
    write_graph(repo, 5, nodes=[{"id": "injected"}])
    first = run(repo, "python3 tools/writer.py")
    assert first[0] == 2

    second = run(repo, "echo unrelated")
    assert second[0] == 2
    assert "revision_not_advanced/confirmed" in codes(*second)

    ledger = json.loads((repo / LEDGER_RELATIVE).read_text(encoding="utf-8"))
    assert ledger["baselines"][GRAPH_RELATIVE]["graph_revision"] == 5
    assert ledger["last_findings"]

    write_graph(repo, 6, nodes=[{"id": "repaired"}])
    repaired = run(repo, "python3 plugins/dev-graph/scripts/build-graph-node.py update --repo-root . --input .dev-graph/tmp/update.json")
    assert repaired[0] == 0, repaired[2]
    assert codes(*repaired) == set()

    stable = run(repo, "echo unrelated")
    assert stable[0] == 0, stable[2]
    assert codes(*stable) == set()


def test_same_size_rewrite_with_restored_mtime_still_reaches_digest_check(repo: Path) -> None:
    """mtime は戻せるため、ctime を含めない早期判定では同サイズ改竄を見逃す。"""
    path = repo / GRAPH_RELATIVE
    before = path.stat()
    original = path.read_text(encoding="utf-8")
    changed = original.replace('"repository_id": "probe-repo"', '"repository_id": "probe-rep0"')
    assert len(changed.encode()) == len(original.encode())
    path.write_text(changed, encoding="utf-8")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))

    exit_code, receipt, stderr = run(repo, "python3 tools/indirect.py")
    # envelope としては canonical でも byte digest は変わっているため、revision 判定まで進む。
    assert exit_code == 2, receipt
    assert "revision_not_advanced/confirmed" in codes(exit_code, receipt, stderr)


def test_unchanged_authority_is_decided_without_reading_the_file(repo: Path, monkeypatch) -> None:
    """未変更判定は stat だけで閉じる。

    この hook は全ての Bash 実行後に走るため、2MB の store を毎回 parse すると監査コストが
    常時課金される。in-process で hook を読み込み、open() が呼ばれないことで確認する。
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("audit_drift_cost", HOOK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_drift_cost"] = module
    spec.loader.exec_module(module)

    ledger = json.loads((repo / LEDGER_RELATIVE).read_text(encoding="utf-8"))
    baseline = ledger["baselines"][GRAPH_RELATIVE]

    def fail_on_read(*args, **kwargs):  # pragma: no cover - 呼ばれたら test 失敗
        raise AssertionError("未変更の authority を開いてはならない")

    monkeypatch.setattr(module, "_digest_of", fail_on_read)
    record, findings = module.audit_path(
        GRAPH_RELATIVE, repo / GRAPH_RELATIVE, baseline, "echo nothing"
    )
    assert findings == []
    assert record["digest"] == baseline["digest"], "前回 digest が持ち越されていない"


def test_repository_without_dev_graph_is_untouched(tmp_path: Path) -> None:
    """dev-graph を使わない repo に台帳ディレクトリを作らない。"""
    exit_code, _, stderr = run(tmp_path, "echo hi")
    assert exit_code == 0, stderr
    assert not (tmp_path / ".dev-graph").exists()


def test_ledger_lives_outside_the_guarded_authority() -> None:
    """台帳の置き場を契約として固定する。

    `state/` や `config.json` へ置くと、監査自身の書込みが C10 の保護対象を叩き、監査を回す
    たびに guard の判定材料を汚す。`.dev-graph/tmp/` は再生成可能で保護対象外である。
    """
    body = HOOK.read_text(encoding="utf-8")
    assert 'LEDGER_RELATIVE = Path(".dev-graph") / "tmp" / "authority-audit.json"' in body

    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    post = [
        entry
        for group in hooks["hooks"]["PostToolUse"]
        for entry in group["hooks"]
        if "audit-graph-authority-drift.py" in entry["command"]
    ]
    assert len(post) == 1, "PostToolUse への配線が 1 件でない"
    assert not post[0].get("async"), (
        "confirmed drift の stderr を agent へ返すため同期実行である必要がある"
    )
