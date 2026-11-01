"""lib/orphan_external_ref.py の検査ロジック検証。

CLI 契約 (引数解釈・exit code・--json-out・baseline の入力解決) は
``test_lint_orphan_external_ref_cli.py`` が持つ。疑似 repo 構築は ``conftest.py`` の
``orphan_lint`` fixture 経由で共有する。

固定する不変条件は 6 つ。

1. **走査方向**: bd issue を起点に graph を引く。既存の同期系 (C03 `reconcile-github-lifecycle.py` /
   `lint-open-residue.py::lint` / `build-parity-manifest.py::_entries`) は例外なく
   graph の node を起点に走るため、graph から node が消えると、その node を指す bd issue は
   全ての検査の視界から同時に消える。逆方向の全数検査だけがこの盲点を塞ぐ。
2. **処分 owner の分離**: md 実体が残る orphan (C02 で復元) と、実体ごと消えた orphan
   (処分が必要) を同じ札にしない。混ぜると「復元すべきものを閉じる」誤処分が起きる。
3. **silent drop の禁止**: 違反にしない closed orphan も `orphans[]` から消さない。
   消すと「件数が減った = 直った」と読めてしまい、棚卸しの母数が失われる。
4. **shrink-only ratchet**: 既知 orphan は baseline で凍結し新規のみ遮断する。処分済みの
   baseline 行は `resolved_baseline_entries` で削除を促す (残すと再発時に検出できない穴になる)。
5. **仕組み/ナレッジ境界**: baseline は repo 側データを入力で受け取る。portable な
   plugins/ 側へ repo 固有の node id を焼き込むと、持ち出した先で意味を失う。
6. **並列 worktree 分離**: 他 ref に node が実在する参照は `merge_pending` として可視化し、
   現在 branch / upstream の削除前 commit で未コミット削除を隠さない。
"""
from __future__ import annotations

import json
from pathlib import Path


# --- 1. 走査方向: bd 起点で graph を引く ------------------------------------


def test_oe001_detects_orphan_whose_artifact_is_gone(tmp_path: Path, orphan_lint) -> None:
    """graph node も md 実体も無い非クローズ issue は真の orphan (処分が必要)。"""
    root, export = orphan_lint.repo(
        tmp_path,
        node_ids=["issue-alive"],
        beads=[orphan_lint.issue("BD-a", "issue-alive"),
               orphan_lint.issue("BD-b", "issue-vanished")],
    )
    code, result = orphan_lint.run(root, export)

    assert code == 2
    assert [row["bd_issue_id"] for row in result["violations"]] == ["BD-b"]
    violation = result["violations"][0]
    assert violation["rule"] == "OE-001"
    assert violation["disposition"] == "true_orphan"
    assert violation["external_ref"] == "issue-vanished"
    assert violation["path"] == ""
    # graph に実在する node を指す issue は orphan ではないので出てこない。
    assert all(row["bd_issue_id"] != "BD-a" for row in result["orphans"])


def test_oe002_separates_restorable_node_from_true_orphan(tmp_path: Path, orphan_lint) -> None:
    """md 実体が残る orphan は C02 で復元すべきで、処分 (bd close) してはならない。"""
    root, export = orphan_lint.repo(
        tmp_path,
        node_ids=[],
        beads=[orphan_lint.issue("BD-r", "issue-restorable"),
               orphan_lint.issue("BD-t", "issue-gone")],
        md_ids=["issue-restorable"],
    )
    code, result = orphan_lint.run(root, export)

    assert code == 2
    by_issue = {row["bd_issue_id"]: row for row in result["violations"]}
    assert by_issue["BD-r"]["rule"] == "OE-002"
    assert by_issue["BD-r"]["disposition"] == "node_restorable"
    assert by_issue["BD-r"]["path"] == "issues/issue-restorable.md"
    assert by_issue["BD-t"]["rule"] == "OE-001"
    assert by_issue["BD-t"]["disposition"] == "true_orphan"


def test_issue_without_external_ref_is_out_of_scope(tmp_path: Path, orphan_lint) -> None:
    """graph 管理外の手起票 issue を orphan 扱いすると、母数が bd 全件になり検査が無意味になる。"""
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[], beads=[orphan_lint.issue("BD-native", None)],
    )
    code, result = orphan_lint.run(root, export)

    assert code == 0
    assert result["orphans"] == [] and result["violations"] == []
    assert result["scanned"] == 1  # 走査はしている (母数から黙って消していない)


def test_external_ref_is_read_from_description_fallback(tmp_path: Path, orphan_lint) -> None:
    """bd-bridge.py と同じ規則で description 内の `external_ref:` も拾う (取りこぼし防止)。"""
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[],
        beads=[{"id": "BD-d", "status": "open",
                "description": "detail\nexternal_ref:issue-in-body\nmore"}],
    )
    code, result = orphan_lint.run(root, export)

    assert code == 2
    assert result["violations"][0]["external_ref"] == "issue-in-body"


# --- 2/3. closed orphan は違反にしないが報告からは消さない -------------------


def test_closed_orphan_is_residue_not_a_violation(tmp_path: Path, orphan_lint) -> None:
    """closed 済みは可視化されず実害が無いので違反にしない。ただし件数は残す (silent drop 禁止)。"""
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[],
        beads=[orphan_lint.issue("BD-c", "issue-closed-orphan", status="closed")],
    )
    code, result = orphan_lint.run(root, export)

    assert code == 0
    assert result["violations"] == [] and result["violation_count"] == 0
    assert result["closed_residue_count"] == 1
    # 違反にしないことと報告から消すことは別。棚卸しの母数として残っていること。
    assert [row["disposition"] for row in result["orphans"]] == ["closed_residue"]
    assert result["orphans"][0]["rule"] is None


def test_in_progress_and_blocked_count_as_non_closed(tmp_path: Path, orphan_lint) -> None:
    """終了状態は closed のみ。in_progress/blocked を終了扱いすると生きた orphan を見逃す。"""
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[],
        beads=[orphan_lint.issue("BD-p", "issue-wip", status="in_progress"),
               orphan_lint.issue("BD-k", "issue-blocked", status="blocked")],
    )
    code, result = orphan_lint.run(root, export)

    assert code == 2
    assert {row["bd_issue_id"] for row in result["violations"]} == {"BD-p", "BD-k"}


def test_closed_wins_over_md_presence(tmp_path: Path, orphan_lint) -> None:
    """closed 済みは md 実体が残っていても復元要求へ昇格させない (分岐順の固定)。

    md 判定を先に置くと、処分済み 100 件のうち md が残るものが毎回 node_restorable として
    再燃し、shrink-only baseline が処分済み案件で膨らむ (= ratchet が意味を失う)。
    closed は既に処分済みという意思表示なので、実体の残存は復元理由にならない。
    """
    module = orphan_lint.module
    assert module.classify_orphan("closed", "issues/still-here.md") == ("closed_residue", None)
    assert module.classify_orphan("closed", None) == ("closed_residue", None)

    # e2e でも同じ: md があっても closed なら違反にならない。
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[],
        beads=[orphan_lint.issue("BD-c", "issue-closed-with-md", status="closed")],
        md_ids=("issue-closed-with-md",),
    )
    code, result = orphan_lint.run(root, export)
    assert code == 0 and result["violations"] == []
    assert result["orphans"][0]["disposition"] == "closed_residue"


def test_classify_orphan_maps_non_closed_states_to_owners(orphan_lint) -> None:
    """非クローズは md 実体の有無で処分 owner が分かれる。未知 status は非クローズ側 (fail-closed)。"""
    module = orphan_lint.module
    for status in ("open", "in_progress", "blocked", "", "some-future-status"):
        assert module.classify_orphan(status, "issues/x.md") == ("node_restorable", "OE-002"), status
        assert module.classify_orphan(status, None) == ("true_orphan", "OE-001"), status
    # 終了状態の語彙は closed のみ。広げると生きた orphan を見逃す。
    assert module._CLOSED_STATUSES == frozenset({"closed"})


def test_beads_unresolvable_fails_closed_by_default(orphan_lint) -> None:
    """bd を引けないまま緑を返すと、検査軸が原理的に成立していないのに『問題なし』と読める。"""
    module = orphan_lint.module
    assert module.decide_exit_code([], "unavailable", require_beads=True) == 2
    assert module.decide_exit_code([], "unavailable", require_beads=False) == 0
    assert module.decide_exit_code([{"rule": "OE-001"}], "resolved", require_beads=True) == 2
    assert module.decide_exit_code([], "resolved", require_beads=True) == 0


def test_unavailable_beads_reports_not_evaluated_instead_of_a_clean_result(
    tmp_path: Path, orphan_lint,
) -> None:
    """beads 不可用時は「0 件だった」ではなく「未評価」と分かる JSON を出す。"""
    module = orphan_lint.module
    root, _ = orphan_lint.repo(tmp_path, node_ids=["issue-alive"], beads=[])
    result = module.lint(
        root / ".dev-graph" / "state" / "graph.json", root,
        None, "bd not found", None, require_beads=False,
    )
    assert result["beads_axis"] == "unavailable"
    assert result["scanned"] == 0 and result["exit_code"] == 0
    assert result["graph_node_count"] == 1


# --- 4. 並列 worktree / ref の分離 -----------------------------------------


def test_scan_refs_marks_other_branch_node_as_merge_pending(tmp_path: Path, orphan_lint) -> None:
    """共有 Beads DB で先に見える他 branch の node は orphan ではなくマージ待ち。"""
    node_id = "issue-on-parallel-branch"
    root, export = orphan_lint.repo(
        tmp_path,
        node_ids=[],
        beads=[orphan_lint.issue("BD-parallel", node_id, status="in_progress")],
    )
    orphan_lint.git(root, "init", "-b", "main")
    orphan_lint.git(root, "config", "user.email", "test@example.com")
    orphan_lint.git(root, "config", "user.name", "Test")
    orphan_lint.git(root, "add", ".dev-graph/state/graph.json")
    orphan_lint.git(root, "commit", "-m", "empty graph")
    orphan_lint.git(root, "switch", "-c", "parallel")
    (root / ".dev-graph" / "state" / "graph.json").write_text(
        json.dumps({
            "schema_version": "1",
            "nodes": [{"graph_node_id": node_id, "artifact_kind": "issue"}],
        }),
        encoding="utf-8",
    )
    orphan_lint.git(root, "add", ".dev-graph/state/graph.json")
    orphan_lint.git(root, "commit", "-m", "parallel node")
    orphan_lint.git(root, "switch", "main")

    code_without_scan, result_without_scan = orphan_lint.run(root, export)
    code_with_scan, result_with_scan = orphan_lint.run(root, export, "--scan-refs")

    assert code_without_scan == 2
    assert result_without_scan["violations"][0]["disposition"] == "true_orphan"
    assert code_with_scan == 0
    assert result_with_scan["violations"] == []
    assert result_with_scan["scanned_refs"] is True
    assert result_with_scan["orphans"][0]["disposition"] == "merge_pending"
    assert result_with_scan["orphans"][0]["node_in_refs"] == ["refs/heads/parallel"]


def test_scan_refs_does_not_hide_worktree_deletion_behind_current_branch(
    tmp_path: Path, orphan_lint,
) -> None:
    """現在 branch の削除前 commit を実在証拠にすると GC 削除を見逃すため除外する。"""
    node_id = "issue-deleted-in-worktree"
    root, export = orphan_lint.repo(
        tmp_path,
        node_ids=[node_id],
        beads=[orphan_lint.issue("BD-deleted", node_id)],
    )
    orphan_lint.git(root, "init", "-b", "main")
    orphan_lint.git(root, "config", "user.email", "test@example.com")
    orphan_lint.git(root, "config", "user.name", "Test")
    orphan_lint.git(root, "add", ".dev-graph/state/graph.json")
    orphan_lint.git(root, "commit", "-m", "graph before deletion")
    (root / ".dev-graph" / "state" / "graph.json").write_text(
        json.dumps({"schema_version": "1", "nodes": []}),
        encoding="utf-8",
    )

    code, result = orphan_lint.run(root, export, "--scan-refs")

    assert code == 2
    assert result["scanned_refs"] is True
    assert result["violations"][0]["disposition"] == "true_orphan"
    assert result["violations"][0]["node_in_refs"] == []


# --- 5. shrink-only ratchet -------------------------------------------------


def test_baselined_orphan_does_not_fail_but_new_one_does(tmp_path: Path, orphan_lint) -> None:
    """既知 orphan は凍結し新規のみ遮断する。凍結分も baselined_orphans として可視化する。"""
    baselined = orphan_lint.baselined
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[], beads=[orphan_lint.issue("BD-old", baselined)],
        baseline=(baselined,),
    )
    code, result = orphan_lint.run(root, export)
    assert code == 0
    assert result["violations"] == []
    assert [row["external_ref"] for row in result["baselined_orphans"]] == [baselined]

    root2, export2 = orphan_lint.repo(
        tmp_path / "second", node_ids=[],
        beads=[orphan_lint.issue("BD-old", baselined),
               orphan_lint.issue("BD-new", "issue-brand-new")],
        baseline=(baselined,),
    )
    code2, result2 = orphan_lint.run(root2, export2)
    assert code2 == 2
    assert [row["external_ref"] for row in result2["violations"]] == ["issue-brand-new"]


def test_resolved_baseline_entries_are_surfaced_for_deletion(tmp_path: Path, orphan_lint) -> None:
    """処分済み baseline 行を残すと、同じ external_ref が再発しても違反にならない穴になる。"""
    baselined = orphan_lint.baselined
    disposed = "issue-already-disposed-fixture"
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[], beads=[orphan_lint.issue("BD-old", baselined)],
        baseline=(baselined, disposed),
    )
    _, result = orphan_lint.run(root, export)

    resolved = set(result["resolved_baseline_entries"])
    assert baselined not in resolved  # 今回観測されたので削除候補ではない
    assert resolved == {disposed}


# --- 6. 検査母集団: dev-graph を指す参照だけ -------------------------------


def test_non_devgraph_external_ref_is_out_of_scope(tmp_path: Path, orphan_lint) -> None:
    """bd の external_ref は tracker 共通欄。GitHub URL を graph_node_id とみなすと、
    dev-graph 管理外の issue が全件 OE-001 に化ける (実測 541 行中 498 行が URL)。
    """
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[],
        beads=[
            orphan_lint.issue("BD-gh", "https://github.com/o/r/issues/1", prefix=""),
            orphan_lint.issue("BD-dg", "issue-really-gone"),
        ],
    )
    code, result = orphan_lint.run(root, export)

    assert code == 2
    assert [row["bd_issue_id"] for row in result["violations"]] == ["BD-dg"]
    # silent drop ではなく、母集団の広さを数字で示す。
    assert result["scanned"] == 2 and result["devgraph_ref_count"] == 1
    assert all(row["bd_issue_id"] != "BD-gh" for row in result["orphans"])


def test_legacy_devgraph_prefix_is_still_in_scope(tmp_path: Path, orphan_lint) -> None:
    """legacy- 形式は graph 導入前に書かれた旧表記で、指す先は同じく dev-graph。

    prefix を剥がし損ねると本文が graph_node_id と一致せず、生きた orphan を
    「無関係な参照」として黙って母集団から落とす。
    """
    root, export = orphan_lint.repo(
        tmp_path, node_ids=[],
        beads=[orphan_lint.issue("BD-lg", "issue-legacy-bound",
                                 prefix="legacy-dev-graph:")],
    )
    code, result = orphan_lint.run(root, export)

    assert code == 2 and result["devgraph_ref_count"] == 1
    assert result["violations"][0]["external_ref"] == "issue-legacy-bound"


# --- 7. 仕組み/ナレッジ境界 ---------------------------------------


def test_mechanism_holds_no_repo_specific_node_id(orphan_lint) -> None:
    """portable な plugins/ 側へ repo 固有 node id を焼き込むと持ち出した先で意味を失う。

    baseline は repo 側データを入力で受け取り、module には規約 path (repo-root 相対) しか置かない。
    """
    module = orphan_lint.module
    assert not hasattr(module, "_BASELINE_ORPHAN"), "baseline は repo 側データへ外出し済み"
    assert not Path(module._BASELINE_RELPATH).is_absolute()
