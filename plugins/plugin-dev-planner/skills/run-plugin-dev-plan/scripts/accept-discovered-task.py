#!/usr/bin/env python3
# /// script
# name: accept-discovered-task
# purpose: build 進行中に発見された discovered-task form を producer 側で受理し、additive は即時 task-graph 反映・structural は --approved 二段受理 (fail-closed) で task-graph.json へ canonical 反映する (C5)。外ループ (spec-improvement loop) 入口として --inbox でディレクトリ一括ドレインし各 form へ status/resulting_graph_hash を書き戻す (FC-6 帰路)。
# inputs:
#   - argv (単一): --form <discovered-task.json> --graph <task-graph.json> [--approved] [-o OUT]
#   - argv (ドレイン): --inbox <discovered-tasks/ dir> --graph <task-graph.json> [--approved] [-o OUT]
# outputs:
#   - stdout: 受理サマリ JSON (単一: accepted 単発 / ドレイン: accepted[]/needs_approval[]/rejected[]/skipped[])
#   - stderr: 検証/受理エラー・structural 未承認拒否メッセージ
#   - exit: 0=OK (ドレインは needs_approval 残存でも 0=正常完了) / 1=単一 form の必須欠落|discovering_task_id 不在|structural 未承認 / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: <--out or --graph> task-graph.json (canonical 上書き) + --inbox 時は各 form の status/resulting_graph_hash 書き戻し
# dependencies: []
# requires-python: ">=3.10"
# ///
"""discovered-task form の producer 受理器 (C5・二段受理 + 外ループ inbox ドレイン)。

design: plugin-plans/plugin-dev-planner/phase-05-implementation.md (C5)。
additive = proposed_node を即時 task-graph へ追加し derive-task-graph.canonicalize() を
再適用して単一 writer の正準形を維持する (id 重複は冪等に無視)。structural (既存エッジ
張替え/component 追加) は approved=True (CLI --approved) でない限り fail-closed 拒否する。

外ループ (spec-improvement loop) の planner 側入口: `--inbox <dir>` は consumer C04 が emit した
discovered-task inbox を決定論順 (filename 昇順) で一括ドレインし、additive を自動受理して
task-graph を累積更新、各 form へ `status`/`resulting_graph_hash` を書き戻す。書き戻しにより
consumer C08 の完了ゲート (scan_pending_discovered が status in {accepted,rejected,superseded}
を処理済とみなす) が処理済 form を素通しでき、外ループが閉じる。structural 未承認は status を
pending 据置で block 継続 (二段受理)。emit(C04)→block(C08)→drain(本 script)→再消費 の一巡。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402,F401  (frontmatter 規約の共有ローダ; 兄弟 script と同一 boilerplate)


def _load_sibling(stem: str):
    """同一 scripts/ 配下のハイフン名 module を importlib で読み込む (canonicalize 共有 API)。"""
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_dtg = _load_sibling("derive-task-graph")
_vtg = _load_sibling("validate-task-graph")

REQUIRED_FIELDS = (
    "discovering_task_id",
    "reason",
    "discovered_at_artifact",
    "proposed_node",
    "change_level",
)
CHANGE_LEVELS = ("additive", "structural")
# 外ループ完了ゲート (consumer C08) が「処理済」とみなす status 集合。
# これ以外 (pending/未設定) の form が inbox に 1 件でも残ると C08 は completed を block する。
PROCESSED_STATUSES = ("accepted", "rejected", "superseded")


class UnknownDiscoveringTask(ValueError):
    """discovering_task_id が現時点の graph に不在 (同一 inbox 内の後続 form が産む可能性がある)。

    ドレインは filename 昇順で回すため、ある form の発見元が同じ inbox の別 form である場合
    (build 中に発見したタスクが、さらに別のタスクを発見する連鎖) 順序次第で発見元がまだ
    graph に居ない。これを恒久 rejected にすると、正当な form が並び順だけで永久に失われる
    (rejected は PROCESSED_STATUSES ゆえ再処理されない)。実測で P05-x-129 がこれに当たった。
    よって本例外は「まだ受理できない」であって「受理できない」ではなく、ドレインは進捗が
    止まるまで多重パスで再試行する。
    """


def _validation_marker(graph: dict) -> str:
    """Preserve the graph's producer shape when validating discovered additions.

    Target-shape graphs carry ``execution_kind`` on every node.  Treating those
    graphs as the legacy fixed shape would skip the executable-leaf contract and
    allow a discovered node without task_spec_ref/produces/phase parentage to be
    accepted.  A graph with no execution_kind remains the legacy shape for
    backward compatibility.
    """
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    if isinstance(nodes, list) and any(
        isinstance(node, dict) and "execution_kind" in node for node in nodes
    ):
        return "task-graph-derived"
    return "fixed-13-phase"


def _is_target_shape(graph: dict) -> bool:
    """graph が target shape (実行可能 leaf 契約を課す形) かを execution_kind 携帯で判定する。

    validate-task-graph の `_target_shape_adopted` と同じ述語 (marker 非依存)。fixed-13-phase
    bootstrap graph (execution_kind 皆無) では (k) が発火しないため配線も行わない。
    """
    return any(
        isinstance(n.get("execution_kind"), str) and n.get("execution_kind")
        for n in graph.get("nodes", [])
    )


def _wire_target_shape_edges(proposed: dict, updated: dict) -> None:
    """target shape の実行可能 leaf が (k) 契約を満たすよう parent_of / produces を配線する。

    accept は従来 depends_on しか張らず、(k) が要求する
      - phase root (`id == phase_ref` かつ execution_kind == "phase-gate") からの parent_of
      - leaf が産出する各成果物への produces
    を欠いたため、target shape graph では発見タスクが必ず validation_failed になっていた
    (外ループが構造的に収束不能)。ここを埋めて外ループの帰路を開通させる。

    `updated["edges"]` を in-place で伸ばす。重複エッジは張らない (canonicalize は重複を
    吸収しないため呼び出し前に自前で防ぐ)。phase root 不在・produces 不在はここで補わず、
    後段の validate ゲートに fail-closed で落とさせる (欠落を黙って捏造しない)。
    """
    proposed_id = proposed.get("id")
    phase_ref = proposed.get("phase_ref")
    existing = {(e.get("type"), e.get("from"), e.get("to")) for e in updated["edges"]}

    def _add(edge_type: str, src: str, dst: str) -> None:
        if (edge_type, src, dst) not in existing:
            updated["edges"].append({"type": edge_type, "from": src, "to": dst})
            existing.add((edge_type, src, dst))

    # parent_of: phase root の実在を確認してから張る。不在なら張らず (k) の
    # "not parented by phase root" で落とす — dangling な親エッジを作って orphan 検査を汚さない。
    root_exists = any(
        n.get("id") == phase_ref and n.get("execution_kind") == "phase-gate"
        for n in updated["nodes"]
    )
    if root_exists:
        _add("parent_of", phase_ref, proposed_id)
        # phase gate が新 leaf を完了集約対象に含める辺 (derive の rel["depends_on"] 同等)。
        # これが無いと P<nn> ゲートが新 leaf を待たずに done になれてしまう (完了判定の穴)。
        _add("depends_on", phase_ref, proposed_id)

    # produces: 宣言された成果物だけを張る。write_scope からの推測補完はしない
    # (成果物宣言のない leaf を通すと「何を作れば done か」が曖昧なまま下流が進む)。
    for artifact in proposed.get("produces") or []:
        if isinstance(artifact, str) and artifact.strip():
            _add("produces", proposed_id, artifact)

    # consumes は derive に合わせて向きが produces の逆 (from=成果物 / to=leaf)。
    # 揃えないと (e) consumes↔produces 突合が空振りする。
    for artifact in proposed.get("consumes") or []:
        if isinstance(artifact, str) and artifact.strip():
            _add("consumes", artifact, proposed_id)


# 発見タスクの成果物を置く plan dir 相対サブディレクトリ。node id で鍵付けする
# (write_scope で鍵付けしない理由は _derive_produces の docstring)。
DISCOVERED_ARTIFACT_SUBDIR = "discovered"
TASK_SPEC_SUBDIR = "task-specs"


def _yaml_scalar(value) -> str:
    """YAML の double-quoted scalar / flow sequence として安全な表現を返す。

    JSON の文字列・配列リテラルは YAML 1.2 の部分集合なので json.dumps をそのまま使える
    (専用 YAML writer を持たない本 scripts/ の規約に合わせる)。
    """
    return json.dumps(value, ensure_ascii=False)


def _plan_rel(plan_dir: Path) -> str:
    """produces に書く plan dir パスを repo 相対 posix 文字列へ正規化する。"""
    try:
        return plan_dir.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return plan_dir.as_posix()


def _derive_produces(node_id: str, plan_dir: Path) -> str:
    """発見 leaf が産出する成果物パスを node id から決定論導出する。

    write_scope から導出してはならない。write_scope は「どのファイルを編集してよいか」で
    多対一 (複数タスクが同じ config/script を編集するのは正常) だが、produces は
    validate-task-graph の producer 一意制約により一対一でなければならない。実測では
    inbox 136 件の file 形 write_scope 72 件が 34 個へ潰れ (goal-spec.json が 10 件で共有)、
    既存 produces エッジとも 35 件衝突した。一方 node id は form 間の重複 0・既存 node id
    との衝突 0 が実測で確認できているため、id 鍵付けだけが一意性を構造的に保証する。

    実体の編集先は write_scope のままで、この成果物は「その leaf が完了したことの記録」
    (完了トークン) として graph の完了判定に使う。task spec 本文へ両者の関係を明記する。
    """
    return f"{_plan_rel(plan_dir)}/{DISCOVERED_ARTIFACT_SUBDIR}/{node_id}.md"


PROVISIONAL_AC_PREFIX = "[要再定義]"


def _provisional_acceptance(node: dict, form: dict) -> str:
    """acceptance_criterion 欠落時の暫定受入条件を form の情報だけから組み立てる。

    emit 側で `--node-acceptance-criterion` が optional なため、実測 136 件のうち 12 件が
    空で来る。空のままでは規則 (k) に落ち、all-or-nothing で全 136 件が巻き添えになる。
    ここでは title と reason を根拠に暫定条件を作るが、**受入の水準を planner が発明した
    ことを隠さない** ため接頭辞 `[要再定義]` を必ず付ける。これにより後続の builder と
    レビュアは「これは発見時の記述から機械生成された仮の条件であり、着手前に本条件へ
    差し替える」と読める (空欄を黙って埋めて緑にするのが最も危険な失敗なので、
    埋めた事実を成果物側に残す)。
    """
    title = (node.get("title") or node.get("id") or "").strip()
    reason = (form.get("reason") or "").strip()
    return (
        f"{PROVISIONAL_AC_PREFIX} 発見時の記述から機械生成した暫定条件。着手前に実測可能な"
        f"条件へ差し替えること。暫定: 「{title}」を解消し、その根拠 (発見理由: {reason}) が"
        "再現しないことを実測で示す。"
    )


def _phase_index(phase_ref) -> int | None:
    """`P05` 形の phase id から番号を取り出す (非該当は None)。"""
    if isinstance(phase_ref, str):
        m = re.match(r"^P(\d{2})$", phase_ref)
        if m:
            return int(m.group(1))
    return None


def _normalize_phase_ref(phase_ref, graph: dict) -> tuple[str, bool]:
    """phase_ref を phase root の node id (P<nn>) へ正規化する。

    graph の phase root は id=phase_ref=`P<nn>` だが、emit 側 (emit-discovered-task.py) の
    `--node-phase-ref` には help 文字列すら無く書式の指示が存在しないため、実測 136 件のうち
    38 件が `phase-05-implementation.md` のようなファイル名形で来ている。しかも
    `phase-04-tests.md` / `phase-04-testing.md` のように実在しないファイル名も混じる
    (正本は phase-04-test-design.md)。よって末尾の題名部分は信用せず、先頭の 2 桁番号
    だけを根拠に写像する。写像先が phase-gate として実在しない場合は変換せず、後段の
    validate へ fail-closed で落とす (存在しない親を捏造しない)。
    """
    if not isinstance(phase_ref, str):
        return phase_ref, False
    roots = {
        n.get("id")
        for n in graph.get("nodes", [])
        if n.get("execution_kind") == "phase-gate"
    }
    if phase_ref in roots:
        return phase_ref, False
    match = re.match(r"^phase-(\d{2})\b", phase_ref)
    if match:
        candidate = f"P{match.group(1)}"
        if candidate in roots:
            return candidate, True
    return phase_ref, False


def render_task_spec(node: dict, form: dict) -> str:
    """発見 leaf の task spec を既存 task-specs/*.md と同一形状で描画する。

    frontmatter の key 順・型は plugin-plans/<slug>/task-specs/P05-x-01.md (derive 生成物) に
    合わせる。後続の builder が既存 spec と発見 spec を区別せず読めることが要件。
    """
    fields = [
        ("id", node["id"]),
        ("title", node.get("title") or node["id"]),
        ("phase_ref", node.get("phase_ref")),
        ("execution_kind", node.get("execution_kind")),
        ("write_scope", node.get("write_scope") or ""),
        ("acceptance_criterion", node.get("acceptance_criterion") or ""),
        ("objective", form.get("reason") or ""),
        ("verify", node.get("acceptance_criterion") or ""),
        ("depends_on", [form["discovering_task_id"]]),
        ("produces", list(node.get("produces") or [])),
        ("consumes", list(node.get("consumes") or [])),
    ]
    if node.get("route_ref"):
        fields.insert(4, ("route_ref", node["route_ref"]))
    head = "\n".join(f"{k}: {_yaml_scalar(v)}" for k, v in fields)
    produced = (node.get("produces") or [""])[0]
    body = f"""
# {node.get('title') or node['id']}

## 由来

build 実行中に `{form['discovering_task_id']}` が発見したタスク (change_level=
{form.get('change_level')})。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: {form.get('reason') or '(未記載)'}

**発見時の証跡**: `{form.get('discovered_at_artifact') or '(未記載)'}`

## 作業

`{node.get('write_scope') or '(未指定)'}` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `{produced}` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

{node.get('acceptance_criterion') or '(未記載)'}
"""
    return f"---\n{head}\n---\n{body}"


def materialize_leaf_contract(
    proposed: dict,
    form: dict,
    graph: dict,
    plan_dir: Path,
    spec_writes: list | None = None,
) -> tuple[dict, list[str]]:
    """実行可能 leaf 契約 (k) の欠落 field を決定論補完し task spec を実体化する。

    emit 側 (harness-creator の emit-discovered-task.py) は execution_kind / task_spec_ref /
    produces を optional として受けるのに対し、consumer 側の validate-task-graph 規則 (k) は
    実行可能 leaf にこれらを必須とする。生産側の必須集合が消費側の不変条件より狭いため、
    emit された form は原理的に 1 件も受理できない状態だった (実測 accepted=0 / 136 件)。
    その差分をここで埋める (欠落を捏造せず、form が持つ情報だけから導出する)。

    戻り値は (補完後 node, 補完した内容の説明 list)。spec_writes を渡すと task spec の
    書き出しを (path, content) として貯め、呼び出し側が validate 通過後に flush できる
    (all-or-nothing の rollback 時に spec ファイルだけ残す漏出を防ぐ)。
    """
    node = dict(proposed)
    notes: list[str] = []
    node_id = node.get("id")

    normalized, changed = _normalize_phase_ref(node.get("phase_ref"), graph)
    if changed:
        notes.append(f"phase_ref {node.get('phase_ref')!r} -> {normalized!r}")
        node["phase_ref"] = normalized

    # 発見タスクは発見元より前の phase へは置けない (規則 (i) future phase dependency)。
    # accept は depends_on を発見元へ張るため、発見元より若い phase に置くと必ず落ちる。
    # ファイル名形 phase_ref は emit 側が実在しない名前 (phase-04-testing.md 等) を渡して
    # くる実績があり番号自体も信用できないので、発見元の phase を下限として床を張る。
    discovering = next(
        (n for n in graph.get("nodes", []) if n.get("id") == form.get("discovering_task_id")),
        None,
    )
    own = _phase_index(node.get("phase_ref"))
    floor = _phase_index((discovering or {}).get("phase_ref"))
    if own is not None and floor is not None and own < floor:
        notes.append(
            f"phase_ref を発見元 {form['discovering_task_id']} の phase まで繰り下げ: "
            f"{node['phase_ref']} -> P{floor:02d}"
        )
        node["phase_ref"] = f"P{floor:02d}"

    if not (node.get("acceptance_criterion") or "").strip():
        node["acceptance_criterion"] = _provisional_acceptance(node, form)
        notes.append("acceptance_criterion を暫定生成 (要再定義)")

    if not node.get("execution_kind"):
        # route_ref を持つ node だけが component-build。実測で execution_kind 欠落 18 件は
        # 全て route_ref/entity_ref とも None であり direct-task が正しい。
        node["execution_kind"] = "component-build" if node.get("route_ref") else "direct-task"
        notes.append(f"execution_kind={node['execution_kind']}")

    if node["execution_kind"] == "phase-gate":
        return node, notes

    if not node.get("task_spec_ref"):
        node["task_spec_ref"] = f"{TASK_SPEC_SUBDIR}/{node_id}.md"
        notes.append(f"task_spec_ref={node['task_spec_ref']}")

    if not node.get("produces"):
        node["produces"] = [_derive_produces(node_id, plan_dir)]
        notes.append(f"produces={node['produces'][0]}")

    # (e) consumes↔produces 突合: graph 内に producer が居ない成果物を consumes に残すと
    # 全件 rollback を招く。落とした事実は notes と spec 本文へ残し、黙って消さない。
    produced_now = {
        e.get("to") for e in graph.get("edges", []) if e.get("type") == "produces"
    }
    keep, dropped = [], []
    for artifact in node.get("consumes") or []:
        (keep if artifact in produced_now else dropped).append(artifact)
    if dropped:
        node["consumes"] = keep
        notes.append(f"consumes から producer 不在の {len(dropped)} 件を除外: {dropped}")

    spec_path = plan_dir / TASK_SPEC_SUBDIR / f"{node_id}.md"
    content = render_task_spec(node, form)
    if spec_writes is None:
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(content, encoding="utf-8")
    else:
        spec_writes.append((spec_path, content))
    return node, notes


def accept(
    form: dict,
    graph: dict,
    approved: bool = False,
    plan_dir: Path | None = None,
    spec_writes: list | None = None,
    notes_sink: dict | None = None,
) -> dict:
    """discovered-task form を受理し、更新後の canonical task-graph を返す。

    - 必須フィールド欠落は ValueError。
    - discovering_task_id が graph.nodes に実在しなければ ValueError。
    - change_level=="additive": proposed_node を追加し即時反映 (id 既存なら冪等に無追加)。
    - change_level=="structural": approved=True でなければ PermissionError (二段受理)。
    """
    missing = [k for k in REQUIRED_FIELDS if k not in form or form[k] is None]
    if missing:
        raise ValueError(f"discovered-task 必須フィールド欠落: {missing}")

    level = form["change_level"]
    if level not in CHANGE_LEVELS:
        raise ValueError(f"change_level は {CHANGE_LEVELS} のいずれか (received={level!r})")

    node_ids = {n.get("id") for n in graph.get("nodes", [])}
    if form["discovering_task_id"] not in node_ids:
        raise UnknownDiscoveringTask(
            f"discovering_task_id={form['discovering_task_id']!r} が task-graph の nodes に不在"
        )

    if level == "structural" and not approved:
        raise PermissionError(
            "structural change (既存エッジ張替え/component 追加) は --approved 二段受理が必須"
        )

    # graph の浅いコピー上で proposed_node を追加 (入力 graph を破壊しない)。
    updated = {
        "schema_version": graph.get("schema_version", "1.0"),
        "nodes": list(graph.get("nodes", [])),
        "edges": list(graph.get("edges", [])),
    }
    proposed = form["proposed_node"]
    proposed_id = proposed.get("id")
    existing_ids = {n.get("id") for n in updated["nodes"]}
    # 実行可能 leaf 契約の欠落補完 (plan_dir 未指定なら従来どおり素通し=低レベル互換)。
    # id 既存 (冪等 skip) の場合は補完しない — derive 生成済みの task spec を再 emit された
    # form の内容で黙って上書きしてしまうため。
    if plan_dir is not None and proposed_id not in existing_ids and _is_target_shape(updated):
        proposed, notes = materialize_leaf_contract(
            proposed, form, updated, plan_dir, spec_writes=spec_writes
        )
        if notes_sink is not None and notes:
            notes_sink[proposed_id] = notes
    if proposed_id not in existing_ids:
        updated["nodes"].append(proposed)
        # 発見タスクを孤立ノードにしない (MD-2): 既定の連結辺として
        # 「発見された新タスクは、それを発見した discovering_task の後続 (depends_on)」を張る。
        # derive のエッジ方向 (from=下流/to=上流) に合わせ from=新ノード to=discovering_task。
        # これで producer validate-task-graph の orphan-0 不変条件を破らない
        # (新ノードは leaf dependent なので循環も生まない)。planner は structural 周回で張替え可。
        discovering = form["discovering_task_id"]
        # spec-gap 由来 (F4): proposed_id が discovering の *上流 producer* の場合
        # (= 既に {from=discovering, to=proposed_id} の depends_on/consumes エッジが存在し、
        # proposed_id 不在ゆえ dangling で spec-gap 停滞していた) は、逆向き
        # {from=proposed_id, to=discovering} を張ると 2-循環になり validate ゲートが rollback
        # → 自動受理不能で外ループが収束しない。この場合は既存の依存方向を尊重し auto-edge を
        # 張らない (追加した proposed_id により既存 dangling エッジがそのまま解決する)。
        proposed_is_upstream = any(
            e.get("type") in ("depends_on", "consumes")
            and e.get("from") == discovering and e.get("to") == proposed_id
            for e in updated["edges"]
        )
        if not proposed_is_upstream:
            dep_edge = {"type": "depends_on", "from": proposed_id, "to": discovering}
            if dep_edge not in updated["edges"]:
                updated["edges"].append(dep_edge)
        # 接合が密な既存兄弟との直列化 (proposed_node.couples_with・外ループ追記でも盲目並列を防ぐ)。
        # plan-time の derive は両兄弟未 build ゆえ id 昇順で対称に直列化するが、外ループの新タスクは
        # 既存兄弟が既に build 中/済ゆえ「新タスクは既存兄弟の *後*」(from=新ノード to=兄弟) が因果的に
        # 正しい (既存の統合面を観測してから新規を build)。新ノードは leaf dependent ゆえ cycle を作らず
        # additive のまま (既存ノードの依存は書き換えない)。同一 phase の兄弟のみ直列化する。
        couples = proposed.get("couples_with") or []
        proposed_phase = proposed.get("phase_ref")
        if isinstance(couples, list) and couples:
            existing_dep = {(e.get("from"), e.get("to")) for e in updated["edges"]
                            if e.get("type") == "depends_on"}
            for sib in updated["nodes"]:
                sid = sib.get("id")
                if sid == proposed_id:
                    continue
                if sib.get("entity_ref") in couples and sib.get("phase_ref") == proposed_phase:
                    if (sid, proposed_id) in existing_dep:
                        continue  # 逆向き (兄弟→新ノード) が既にあれば cycle 化するので張らない
                    if (proposed_id, sid) not in existing_dep:
                        updated["edges"].append({"type": "depends_on", "from": proposed_id, "to": sid})
                        existing_dep.add((proposed_id, sid))
        # target shape の leaf 契約 (k) を満たす構造エッジを張る (depends_on だけでは validate に落ちる)。
        if _is_target_shape(updated) and proposed.get("execution_kind") != "phase-gate":
            _wire_target_shape_edges(proposed, updated)
    return _dtg.canonicalize(updated)


def diff_proposed_vs_existing(proposed: dict, graph: dict) -> list[str] | None:
    """proposed_node と graph 内の同 id 既存 node の field 差分を返す (既存不在なら None)。

    冪等 skip (id 既存で無追加) の際、再 emit された form の field 変更 (title/acceptance_criterion
    等) が黙って落ちるのを可視化する材料 (B1)。graph は不変のまま、両 node の key 和集合に対する
    値不一致フィールド名を昇順 list で返す (差分なしは [])。
    """
    pid = proposed.get("id")
    existing = next(
        (n for n in graph.get("nodes", []) if isinstance(n, dict) and n.get("id") == pid), None)
    if existing is None:
        return None
    keys = set(proposed) | set(existing)
    return sorted(k for k in keys if proposed.get(k) != existing.get(k))


def drain_inbox(
    inbox_dir: Path,
    graph: dict,
    approved: bool = False,
    plan_dir: Path | None = None,
) -> tuple[dict, dict]:
    """discovered-task inbox を決定論順で一括ドレインし外ループ入口を閉じる (FC-6 帰路)。

    filename 昇順で各 *.json を走査し、status が処理済 (PROCESSED_STATUSES) の form は skip。
    未処理 form は accept() を試み:
      - 受理成功 (additive、または structural かつ approved) → graph を累積更新し form へ
        status=accepted + resulting_graph_hash を書き戻す。
      - PermissionError (structural 未承認) → status は pending 据置で書き戻さず needs_approval へ
        記録 (二段受理: 後続の --approved 周回で受理・それまで C08 が block し続ける)。
      - ValueError (必須欠落/discovering_task_id 不在等) → status=rejected + rejected_reason を
        書き戻し (恒久的に処理不能な form が block を永続化しないよう rejected 化)。

    graph は inbox 全体で 1 度だけ更新する累積更新 (form 間の id 依存は canonicalize が冪等吸収)。
    戻り値は (更新後 graph, 結果サマリ)。graph 自体の write は呼び出し側 (main) が担う。
    """
    results: dict = {"accepted": [], "needs_approval": [], "rejected": [], "skipped": []}
    original_graph = graph  # validate 失敗時に書き戻さない元 graph
    working = graph
    accepted_paths: list[tuple[Path, dict, str | None]] = []  # (path, form, node_id)
    # task spec の書き出しは validate ゲート通過後まで保留する。accept は all-or-nothing
    # rollback を持つため、途中で書くと graph 未更新のまま spec ファイルだけが残る。
    spec_writes: list[tuple[Path, str]] = []
    notes_sink: dict[str, list[str]] = {}
    queue: list[tuple[Path, dict]] = []
    for form_path in sorted(inbox_dir.glob("*.json")):
        try:
            form = json.loads(form_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            results["rejected"].append({"form": form_path.name, "reason": f"read/parse error: {exc}"})
            continue
        if form.get("status") in PROCESSED_STATUSES:
            results["skipped"].append({"form": form_path.name, "status": form.get("status")})
            continue
        queue.append((form_path, form))

    def _reject(form_path: Path, form: dict, node_id: str | None, reason: str) -> None:
        form["status"] = "rejected"
        form["rejected_reason"] = reason
        form_path.write_text(json.dumps(form, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results["rejected"].append({"form": form_path.name, "node": node_id, "reason": reason})

    # 多重パス化 (順序依存の恒久拒否を防ぐ): form は filename 昇順で並ぶが、ある form の
    # discovering_task_id を graph へ産むのは別 form でありうる。単一パスだと後者が先に来る
    # 並びで前者が UnknownDiscoveringTask → rejected となり、rejected は PROCESSED_STATUSES
    # ゆえ二度と再処理されない (正当な form が並び順だけで永久に失われる)。よって「まだ受理
    # できない」form は次パスへ繰り越し、1 パス丸ごと前進が無くなった時点で初めて rejected に
    # する。パス数は毎回 1 件以上減る前提なので高々 form 件数で停止する。
    deferred: list[tuple[Path, dict, str]] = [(p, f, "") for p, f in queue]
    while deferred:
        next_deferred: list[tuple[Path, dict, str]] = []
        progressed = False
        for form_path, form, _prev_reason in deferred:
            node_id = form.get("proposed_node", {}).get("id")
            # 冪等 skip の field 差分検出 (B1): accept 前の working graph と比較する
            # (id 既存なら accept は無追加=graph 不変で、proposed の field 変更は反映されない)。
            proposed = form.get("proposed_node") if isinstance(form.get("proposed_node"), dict) else {}
            diff_fields = diff_proposed_vs_existing(proposed, working)
            try:
                working = accept(
                    form,
                    working,
                    approved=approved,
                    plan_dir=plan_dir,
                    spec_writes=spec_writes,
                    notes_sink=notes_sink,
                )
            except UnknownDiscoveringTask as exc:
                next_deferred.append((form_path, form, str(exc)))
                continue
            except PermissionError:
                # structural 未承認: pending 据置 (書き戻さない) → C08 が block を継続し二段受理を強制。
                results["needs_approval"].append({"form": form_path.name, "node": node_id})
                progressed = True
                continue
            except ValueError as exc:
                _reject(form_path, form, node_id, str(exc))
                progressed = True
                continue
            form["status"] = "accepted"
            entry = {"form": form_path.name, "node": node_id}
            if diff_fields:
                # 冪等 skip で proposed の field 変更が graph へ反映されていない (partial 反映)。
                # graph は不変のまま form へ差分一覧を書き戻し、次周回 planner の判断材料にする (B1)。
                form["reflected"] = "partial"
                form["reflected_diff_fields"] = diff_fields
                entry["reflected"] = "partial"
                entry["diff_fields"] = diff_fields
            accepted_paths.append((form_path, form, node_id))
            results["accepted"].append(entry)
            progressed = True
        if not next_deferred:
            break
        if not progressed:
            # 1 パス丸ごと前進が無い = 残りの discovering_task_id を産む form は inbox に居ない。
            # 順序ではなく実体の欠落なので、ここで初めて恒久 rejected にする。
            for form_path, form, reason in next_deferred:
                node_id = form.get("proposed_node", {}).get("id")
                _reject(form_path, form, node_id, reason)
            break
        deferred = next_deferred
    # fail-closed validate ゲート (MD-2): 受理を全て適用した *最終* graph が producer 不変条件
    # (DAG 非循環 / orphan 0 / producer 一意 / consumes 実在 / canonical) を破るなら、graph も
    # form status も一切コミットせず元 graph を返す。C08 完了ゲートが block を継続し外ループが
    # 不正 graph を書き戻せない (accept の depends_on 自動配線で additive は通常 valid・
    # structural 承認済で循環を招くケース等をここで捕捉)。
    violations = (
        _vtg.validate(working, {}, marker=_validation_marker(working))
        if accepted_paths else []
    )
    if violations:
        results["accepted"] = []
        results["validation_failed"] = violations
        for form_path, form, node_id in accepted_paths:
            results["needs_approval"].append(
                {"form": form_path.name, "node": node_id, "reason": "graph validation failed"}
            )
        return original_graph, results
    # 全 form 受理後の *最終* graph_hash を全 accepted form へ統一して焼き戻す (MD-8)。
    # form 逐次の中間 hash でなく最終 hash を焼くことで、consumer C07 の再 pin 認可述語
    # (task-state pin を新 graph_hash へ更新してよいのは、その hash が accepted form の
    # resulting_graph_hash と一致するときのみ) が最終 graph と突合できる (SS-4 provenance-gated re-pin)。
    # validate 通過が確定してから task spec を flush する (rollback 時は 1 件も書かない)。
    for spec_path, content in spec_writes:
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(content, encoding="utf-8")
    results["materialized_task_specs"] = [str(p) for p, _ in spec_writes]
    results["materialization_notes"] = notes_sink
    # 暫定 AC は「planner が受入水準を発明した」箇所なので個別に名指しして返す
    # (materialization_notes に埋もれさせると人が気づかないまま build へ流れる)。
    results["provisional_acceptance_nodes"] = sorted(
        nid for nid, ns in notes_sink.items()
        if any("acceptance_criterion を暫定生成" in n for n in ns)
    )
    final_hash = _dtg.graph_hash(working)
    for form_path, form, _ in accepted_paths:
        form["resulting_graph_hash"] = final_hash
        form_path.write_text(json.dumps(form, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return working, results


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="accept-discovered-task.py",
        description="discovered-task form を producer 側で受理し task-graph へ canonical 反映する。",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--form", help="単一 discovered-task.json のパス")
    src.add_argument("--inbox", help="外ループ入口: discovered-tasks/ ディレクトリを一括ドレイン")
    parser.add_argument("--graph", required=True, help="task-graph.json のパス")
    parser.add_argument(
        "--approved",
        action="store_true",
        help="structural change を承認する (二段受理の第2段)",
    )
    parser.add_argument(
        "--plan-dir",
        default=None,
        help="task spec 実体化先の plan dir (既定は --graph の親)。leaf 契約の欠落補完に使う",
    )
    parser.add_argument("-o", "--out", default=None, help="出力先 (既定は --graph を上書き)")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse usage error / --help
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"read/parse error: {exc}", file=sys.stderr)
        return 2

    out_path = Path(args.out) if args.out else Path(args.graph)

    # 外ループ入口: inbox 一括ドレイン (needs_approval 残存でも exit0=ドレイン正常完了)。
    if args.inbox:
        inbox_dir = Path(args.inbox)
        if not inbox_dir.is_dir():
            print(f"inbox ディレクトリが存在しない: {inbox_dir}", file=sys.stderr)
            return 2
        plan_dir = Path(args.plan_dir) if args.plan_dir else Path(args.graph).parent
        updated, results = drain_inbox(
            inbox_dir, graph, approved=args.approved, plan_dir=plan_dir
        )
        out_path.write_text(_dtg.canonical_json(updated) + "\n", encoding="utf-8")
        summary = {
            "mode": "inbox",
            "accepted": results["accepted"],
            "needs_approval": results["needs_approval"],
            "rejected": results["rejected"],
            "skipped": results["skipped"],
            "graph_hash": _dtg.graph_hash(updated),
            "node_count": len(updated["nodes"]),
            "out": str(out_path),
        }
        # 全件 rollback の理由を stdout から落とさない。従来は validation_failed が results に
        # 入っていても summary が 7 key 固定だったため、呼び出し側 (planner E4・dispatcher) には
        # 「accepted=0 / needs_approval=N」しか見えず、二段承認待ちと構造違反が区別できなかった。
        if results.get("validation_failed"):
            summary["validation_failed"] = results["validation_failed"]
        for key in ("materialized_task_specs", "materialization_notes",
                    "provisional_acceptance_nodes"):
            if results.get(key):
                summary[key] = results[key]
        print(json.dumps(summary, ensure_ascii=False))
        return 0

    # 単一 form モード (低レベルプリミティブ・従来互換: form へ status 書き戻さない)。
    try:
        form = json.loads(Path(args.form).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"read/parse error: {exc}", file=sys.stderr)
        return 2

    try:
        updated = accept(form, graph, approved=args.approved)
    except PermissionError as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"invalid discovered-task: {exc}", file=sys.stderr)
        return 1

    out_path.write_text(_dtg.canonical_json(updated) + "\n", encoding="utf-8")
    summary = {
        "accepted": True,
        "change_level": form["change_level"],
        "added_node": form["proposed_node"].get("id"),
        "node_count": len(updated["nodes"]),
        "out": str(out_path),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
