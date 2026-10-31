"""bd issue の external_ref から graph node を逆引きする orphan 検査の決定論ロジック。

正本契約: references/execution-tracker-contract.md §10 (unmapped 分類)。

## なぜ逆方向の突合が要るか (本検査の存在理由)

dev-graph の同期系は例外なく graph を起点に走査する。

- C03 sync (`reconcile-github-lifecycle.py`) は graph の node を引いてから tracker を読む。
- `lint-open-residue.py::lint()` も同じく `graph["nodes"]` から beads 束縛 node を選ぶ。
- `build-parity-manifest.py::_entries()` も graph の投影しか作らない。

したがって **graph から node が消えると、その node が指していた bd issue は全ての検査の
視界から同時に消える**。issue は `external_ref: dev-graph:<消えた node>` を抱えたまま
open で残り、誰も気づかない。C28 `--op ready` は ready 候補に上がった orphan だけを
`graph_node_missing` として可視化するが、ready に上がらない orphan (closed 済み・依存で
blocked 等) は原理的に捕まらない。

本検査は唯一 **bd を起点に graph を引く**方向の突合で、この盲点を塞ぐ。

## 検出 rule

  OE-001  非クローズ bd issue の external_ref が graph node を指さず、対応する md 実体も
          repo に無い (= 真の orphan。node 化するか bd 側を閉じる処分が必要)
  OE-002  非クローズ bd issue の external_ref が graph node を指さないが、md 実体は repo に
          ある (= node 登録漏れ / GC 削除。C02 build-graph-node.py で復元すべき)

closed 済み bd issue の orphan は履歴の残骸であり、可視化されないため実害が無い。違反に
せず `closed_residue` として件数だけ残す (silent drop を避けつつ ratchet を汚さない)。

## beads 状態の解決順序

lint-open-residue.py と同一:

  1. --beads-export FILE
  2. PATH 上の bd による `bd export` (Dolt DB の live 状態)
  3. いずれも不可なら --require-beads (既定) で exit 2

`.beads/issues.jsonl` は受動エクスポートであり状態判定の正本ではないため暗黙には読まない。

## 並列 worktree の扱い

bd の DB は worktree 間で共有されるが `.dev-graph/state/graph.json` は worktree ごとに
別実体である。並列 worktree で issue と node を同時に作ると、その node は自分の graph には
まだ現れないため、作業ツリーだけの検査では OE-001 に化ける。`scan_refs` は他 branch /
remote ref の canonical graph を読み、node が実在するものを `merge_pending` として可視化しつつ
違反から除外する。現在 branch と upstream は、未コミットの node 削除を過去の commit で
隠さないよう走査対象から除外する。ローカル品質ゲートは並列開発中にも使えるよう
`--scan-refs` を有効にし、単一 graph だけを厳密に検査したい呼び出しでは省略できる。

## baseline (shrink-only ratchet)

既知 orphan の baseline は repo 側データを入力で受け取る。仕組み (plugins/) は portable で
あり repo 固有の node id を保持しないため (仕組み/ナレッジ境界)。既定は repo-root 相対の
規約 path で、無ければ免除ゼロとして扱う。

Exit codes:
  0  違反 0 件
  1  一般エラー
  2  違反検出 / beads 解決不能 (fail-closed)

CLI と出力処理は ``scripts/lint-orphan-external-ref.py`` に分離する。この module は入力解決と
突合・分類だけを担い、単一責務を維持する。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

LINT_NAME = "lint-orphan-external-ref"

# bd 側が終了状態とみなせる status。ここに入る orphan は履歴の残骸として扱う。
_CLOSED_STATUSES = frozenset({"closed"})

# external_ref が dev-graph を指すと判定できる prefix。dev-graph 以外の紐付け
# (GitHub Issue URL 等) と同じ欄を共有するため、prefix が唯一の識別子になる。
# legacy- は graph 導入前に書かれた旧形式で、指す先は同じく dev-graph。
_DEVGRAPH_REF_PREFIXES = ("dev-graph:", "legacy-dev-graph:", "external_ref:")

# 既知の未処分 orphan (shrink-only baseline) の解決先。ここに載る external_ref の残置は
# 違反ではなく baselined_orphans として報告し exit に寄与しない。新規発生のみを遮断する。
#
# 一覧を本 module に直書きしないのは仕組み/ナレッジ境界による。plugins/ は
# 他 repo へ持ち出せる portable mechanism であり、特定 repo の node id を焼き込むと
# 持ち出した先で意味を失う。既知 orphan は repo 固有ナレッジなので repo 側データを入力で
# 受け取る。
#
# baseline は縮小のみが正。増やす変更は本検査の目的「orphan を生み続ける経路を塞ぐ」を
# 無効化するため、レビューで拒否すること (規律の正本はデータ側 _comment に置く)。
_BASELINE_RELPATH = "scripts/dev-graph-orphan-baseline.json"
_BASELINE_KEY = "baselined_external_refs"

# md 実体の走査から外す領域。試行ログ・雛形・外部依存は「node の実体」ではないため、
# ここを含めると OE-001 と OE-002 の判別 (処分すべきか復元すべきか) が壊れる。
_EXCLUDED_DIRS = frozenset({
    ".git", ".dev-graph", ".worktrees", ".venv", "__pycache__",
    "node_modules", "eval-log", "vendor", "dist", "build",
})

# artifact md の frontmatter から graph_node_id を読む。build-graph-node.py は JSON 値で書くが、
# 手書きの frontmatter も拾えるよう引用の有無を両方許容する。
_FRONTMATTER_NODE_ID = re.compile(r'^graph_node_id:\s*"?([^"\n]+?)"?\s*$', re.MULTILINE)


class LintError(Exception):
    """検査を続行できない一般エラー (exit 1)。"""


def _graph_node_ids(graph_path: Path) -> set[str]:
    """canonical graph に実在する graph_node_id の集合を返す。"""
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        nodes = graph["nodes"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise LintError(f"graph を読めません: {graph_path}: {exc}") from exc
    if not isinstance(nodes, list):
        raise LintError("graph の nodes[] が配列ではありません")
    result: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("graph_node_id") or node.get("id")
        if isinstance(node_id, str) and node_id:
            result.add(node_id)
    return result


def _md_node_ids(root: Path) -> dict[str, str]:
    """repo 上の artifact md を走査し graph_node_id -> 相対 path の写像を返す。

    graph に無い node の実体を探す用途なので、graph の file_path は使えない (消えた node の
    file_path はどこにも残っていない)。frontmatter を直接引くしかない。
    """
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*.md")):
        if any(part in _EXCLUDED_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        try:
            head = path.read_text(encoding="utf-8")[:4096]
        except (OSError, UnicodeDecodeError):
            continue
        if not head.startswith("---\n"):
            continue
        match = _FRONTMATTER_NODE_ID.search(head)
        if match:
            result.setdefault(match.group(1).strip(), path.relative_to(root).as_posix())
    return result


def _git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """read-only git を非対話で実行する。ref が無い等の通常欠損は caller が判定する。"""
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _refs_with_node(
    root: Path,
    graph_path: Path,
    node_ids: set[str],
) -> dict[str, list[str]]:
    """他 ref の graph に実在する node_id → ref[] を返す。

    現在 branch と upstream を除外するのは、作業ツリーで node を削除した直後に、削除前の
    commit / remote tracking ref が同じ node を持つことを `merge_pending` と誤認しないため。
    それ以外の ref は並列 worktree で先に作られた node の実在証拠になる。
    """
    if not node_ids:
        return {}
    try:
        graph_relative = graph_path.resolve(strict=True).relative_to(root.resolve(strict=True)).as_posix()
    except (OSError, ValueError) as exc:
        raise LintError("--scan-refs requires --graph to be inside --repo-root") from exc

    listed = _git(
        root,
        ["for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"],
    )
    if listed.returncode != 0:
        raise LintError(f"git refs を列挙できません: {listed.stderr.strip()}")

    excluded: set[str] = set()
    current = _git(root, ["symbolic-ref", "-q", "HEAD"])
    if current.returncode == 0 and current.stdout.strip():
        excluded.add(current.stdout.strip())
    upstream = _git(root, ["rev-parse", "--symbolic-full-name", "@{upstream}"])
    if upstream.returncode == 0 and upstream.stdout.strip():
        excluded.add(upstream.stdout.strip())

    found: dict[str, list[str]] = {}
    for ref in sorted(set(listed.stdout.split()) - excluded):
        shown = _git(root, ["show", f"{ref}:{graph_relative}"])
        if shown.returncode != 0 or not shown.stdout:
            continue
        try:
            value = json.loads(shown.stdout)
            nodes = value.get("nodes") if isinstance(value, dict) else None
        except json.JSONDecodeError:
            continue
        if not isinstance(nodes, list):
            continue
        present = {
            node.get("graph_node_id") or node.get("id")
            for node in nodes
            if isinstance(node, dict)
        }
        for node_id in sorted(node_ids & present):
            found.setdefault(node_id, []).append(ref)
    return found


def _load_baseline(root: Path, explicit: Path | None) -> tuple[frozenset[str], str]:
    """既知 orphan の baseline を repo 側データとして解決する。(集合, 由来) を返す。

    欠損時の方針は「免除を黙って与えない / 黙って握り潰さない」の 2 点で決める:

      既定 path が無い          -> 空集合 + 由来 "absent"。免除ゼロは最も厳しい側であり
                                   安全。ただし由来を出力に残し、暗黙に 0 件へ落ちない。
      --baseline 明示で読めない -> LintError (exit 1)。利用者の指定ミスを免除ゼロと
                                   区別できないまま続行すると、意図した免除が消える。
      JSON が壊れている / 形違い -> LintError (exit 1)。免除の有無を判定できない。
    """
    path = explicit if explicit is not None else root / _BASELINE_RELPATH
    if not path.exists():
        if explicit is not None:
            raise LintError(f"baseline が存在しません: {path}")
        return frozenset(), "absent"

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LintError(f"baseline を読めません: {path}: {exc}") from exc

    entries = payload.get(_BASELINE_KEY) if isinstance(payload, dict) else None
    if not isinstance(entries, list) or not all(
        isinstance(entry, str) and entry for entry in entries
    ):
        raise LintError(f"baseline の {_BASELINE_KEY}[] が非空文字列の配列ではありません: {path}")
    return frozenset(entries), str(path) if explicit is not None else _BASELINE_RELPATH


def _external_ref(row: dict) -> str | None:
    """bd issue 行から dev-graph の graph_node_id を取り出す。指していなければ None。

    bd の `external_ref` は tracker 共通の紐付け欄で、dev-graph 以外の参照 (GitHub Issue
    URL 等) も同じ欄に入る。prefix が唯一の識別子であり、prefix 無しの値を graph_node_id
    とみなすと逆方向突合の母集団が壊れる。

    bd-bridge.py の同名関数は graph_node_id から bd 行を探す **順方向**で使われるため、
    非 dev-graph 値が混ざっても完全一致で落ちて実害が無い。逆方向の本検査では同じ扱いが
    そのまま誤検出になる (URL は graph に在るはずが無く、全件が OE-001 に化ける)。
    """
    direct = row.get("external_ref") or row.get("externalRef")
    if isinstance(direct, str) and direct:
        for prefix in _DEVGRAPH_REF_PREFIXES:
            if direct.startswith(prefix):
                return direct[len(prefix):]
        return None
    match = re.search(r"(?:^|\s)external_ref:([^\s]+)", str(row.get("description", "")))
    return match.group(1) if match else None


def _parse_beads_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if isinstance(record, dict) and isinstance(record.get("id"), str):
            rows.append(record)
    return rows


def _resolve_beads(root: Path, explicit: Path | None) -> tuple[list[dict] | None, str]:
    """bd issue 行の一覧を解決する。(行, 由来) を返す。解決不能なら (None, 理由)。"""
    if explicit is not None:
        try:
            return _parse_beads_jsonl(explicit), f"--beads-export {explicit}"
        except (OSError, json.JSONDecodeError) as exc:
            raise LintError(f"beads export を読めません: {explicit}: {exc}") from exc

    if shutil.which("bd"):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "issues.jsonl"
            try:
                subprocess.run(
                    ["bd", "export", "-o", str(out)],
                    cwd=str(root), capture_output=True, check=True, timeout=120,
                )
                return _parse_beads_jsonl(out), "bd export"
            except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
                return None, "bd export に失敗"

    return None, "beads export が見つからず bd も PATH 上にありません"


def classify_orphan(
    bd_status: str,
    md_path: str | None,
    node_in_refs: list[str] | None = None,
) -> tuple[str, str | None]:
    """orphan 1 件の disposition と違反 rule を決める。

    Args:
        bd_status: bd issue の status ("open" / "in_progress" / "blocked" / "closed" 等)。
        md_path: 同じ graph_node_id を frontmatter に持つ md の相対 path。無ければ None。
        node_in_refs: 同じ node が実在する他 ref の一覧。scan_refs 無効時は空。

    Returns:
        (disposition, rule): disposition は下流が対処 owner を判別するための札
        ("closed_residue" / "merge_pending" / "node_restorable" / "true_orphan")。
        rule は違反として exit code に寄与させる場合の rule 名 ("OE-001" / "OE-002")、
        違反でなければ None。
    """
    # closed を最初に見る。closed は既に処分済みという意思表示なので、md 実体が残っていても
    # 復元要求へ昇格させない。順序を入れ替えると、処分済みのうち md が残るものが毎回
    # node_restorable として再燃し、shrink-only baseline が処分済み案件で膨らむ。
    if bd_status in _CLOSED_STATUSES:
        return "closed_residue", None

    # 他 ref に node が実在するなら参照は壊れていない。現在 graph へのマージ待ちとして
    # 可視化だけを残す。md が現在 worktree にもある場合でも、先回りの C02 登録は将来の
    # branch merge と衝突するため merge_pending を優先する。
    if node_in_refs:
        return "merge_pending", None

    # 以降は非クローズ (open / in_progress / blocked / 未知の status)。_CLOSED_STATUSES を
    # closed だけに絞ってあるのは、in_progress や blocked を終了扱いすると「生きている
    # orphan」を見逃すため。未知の status も非クローズ側へ倒すのが fail-closed な既定。
    if md_path:
        # 実体が repo に残っている = node 登録漏れ / GC 削除。捨てずに C02 で graph へ戻す。
        return "node_restorable", "OE-002"

    # graph node も md 実体も無い。復元先が存在しないので、bd 側を閉じるか再起票する。
    return "true_orphan", "OE-001"


def _orphans(
    beads_rows: list[dict],
    node_ids: set[str],
    md_ids: dict[str, str],
    refs_by_node: dict[str, list[str]] | None = None,
) -> list[dict]:
    """bd 起点で graph を引き、参照先が実在しない issue を分類して返す。"""
    records: list[dict] = []
    for row in beads_rows:
        external_ref = _external_ref(row)
        if not external_ref or external_ref in node_ids:
            continue
        bd_status = str(row.get("status") or "")
        md_path = md_ids.get(external_ref)
        node_in_refs = (refs_by_node or {}).get(external_ref, [])
        disposition, rule = classify_orphan(bd_status, md_path, node_in_refs)
        records.append({
            "rule": rule,
            "disposition": disposition,
            "bd_issue_id": str(row.get("id")),
            "bd_status": bd_status,
            "external_ref": external_ref,
            "path": md_path or "",
            "node_in_refs": node_in_refs,
            "title": str(row.get("title") or ""),
        })
    records.sort(key=lambda record: (record["external_ref"], record["bd_issue_id"]))
    return records


def decide_exit_code(violations: list[dict], beads_axis: str, require_beads: bool) -> int:
    """検出結果から exit code を決める fail-closed 判定。

    Args:
        violations: baseline を除いた違反のリスト。
        beads_axis: "resolved" (突合済み) または "unavailable" (未評価)。
        require_beads: --require-beads が有効かどうか (既定 True)。

    Returns:
        exit code (0 または 2)。
    """
    if violations:
        return 2
    # bd を要求したのに解決できなければ、JSON 証跡を出した上で遮断する。graph 単独では
    # 本検査の検査軸 (bd → graph の逆引き) が原理的に成立しないため。
    if beads_axis == "unavailable" and require_beads:
        return 2
    return 0


def lint(
    graph_path: Path,
    root: Path,
    beads_rows: list[dict] | None,
    beads_source: str,
    issue_ids: set[str] | None,
    require_beads: bool,
    baseline: frozenset[str] = frozenset(),
    baseline_source: str = "absent",
    scan_refs: bool = False,
) -> dict:
    node_ids = _graph_node_ids(graph_path)
    if beads_rows is None:
        return {
            "lint": LINT_NAME,
            "repo_root": ".",
            "beads_axis": "unavailable",
            "beads_source": beads_source,
            "baseline_source": baseline_source,
            "scanned": 0,
            "devgraph_ref_count": 0,
            "graph_node_count": len(node_ids),
            "scanned_refs": scan_refs,
            "orphans": [],
            "violations": [],
            "violation_count": 0,
            "closed_residue_count": 0,
            "baselined_orphans": [],
            "resolved_baseline_entries": sorted(baseline),
            "exit_code": decide_exit_code([], "unavailable", require_beads),
        }

    rows = [row for row in beads_rows if not issue_ids or str(row.get("id")) in issue_ids]
    orphan_node_ids = {
        external_ref
        for row in rows
        if (external_ref := _external_ref(row)) and external_ref not in node_ids
    }
    refs_by_node = (
        _refs_with_node(root, graph_path, orphan_node_ids) if scan_refs else {}
    )
    records = _orphans(rows, node_ids, _md_node_ids(root), refs_by_node)
    # 実際に突合できた母集団。scanned (bd 全行) との差が「dev-graph 管理外の issue」であり、
    # 両方出さないと「540 行検査した」という数字が検査軸の広さを過大に見せる。
    devgraph_ref_count = sum(1 for row in rows if _external_ref(row))

    violations: list[dict] = []
    baselined: list[dict] = []
    for record in records:
        if record["rule"] is None:
            continue
        if record["external_ref"] in baseline:
            baselined.append(record)
        else:
            violations.append(record)

    # 実在しなくなった baseline は削除を促す (shrink-only ratchet)。処分済みの行を残すと
    # 同じ external_ref が再発したとき違反として検出されない穴になる。
    seen_baseline = {record["external_ref"] for record in baselined}
    return {
        "lint": LINT_NAME,
        "repo_root": ".",
        "beads_axis": "resolved",
        "beads_source": beads_source,
        "baseline_source": baseline_source,
        "scanned": len(rows),
        "devgraph_ref_count": devgraph_ref_count,
        "graph_node_count": len(node_ids),
        "scanned_refs": scan_refs,
        "orphans": records,
        "violations": violations,
        "violation_count": len(violations),
        "closed_residue_count": sum(1 for record in records if record["disposition"] == "closed_residue"),
        "baselined_orphans": baselined,
        "resolved_baseline_entries": sorted(baseline - seen_baseline),
        "exit_code": decide_exit_code(violations, "resolved", require_beads),
    }
