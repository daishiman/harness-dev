#!/usr/bin/env python3
"""UBM目標設定 一本筋（売上目標 → 成果目標 → 行動目標）の両方向照合.

行動目標は支える成果目標ごとの `### → {成果目標名}：{要約}（{金額}円）` 見出しで
グループ化する（記法の正本は `references/output-formats.md`「表記仕様」）。所属は
このグループ見出しから読む。見出しの無い旧ファイルだけ、行内の
`→ 支える成果目標：XXX` へフォールバックする。

**照合規則は `validate-goal-output.py` から読み込んで共用する。** 成果目標の項目の
束ね方・参照キーの切り出し（`_outcome_key`）・一致判定（`_ref_matches_key`：空白を
落とした完全一致）・グループ見出しの解釈（`_current_action_groups`）を二重に実装しない。
validator の C4（所属不明）・C5（参照先の実在）と同じ述語で数えるので、両者の判定が
食い違うことはない。このスクリプトが上乗せするのは次の5点だけである。

- 支える行動の無い成果目標を**未解決（rc=1）**として数える（validator の C6 は WARN）
- 括弧名の免除を `（土台）`／`（関係維持）` の2つに限る（C5 は括弧で始まる名前を
  すべて免除する。免除名を1つ足すだけで検査が通る経路を塞ぐ）
- 1つの行動が複数の成果目標を指す `・` 区切りを FAIL にする（OUTPUT_012。C5 は各参照の
  実在だけを見る）
- 月報の `# 北原さん提出用…` グループを照合対象から外し、`# 管理用…` グループだけを
  照合する。グループ見出しのラベルずれも FAIL にする
- 両方向の分母を印字し、分母0を rc=3 として PASS と区別する。末尾に測定時刻と引数を残す

exit code:

- 0 : 未解決0件（かつ照合を実施したグループが1つ以上あり、両方向の分母が1件以上あった）
- 1 : 未解決あり（参照の切れ／所属不明／複数参照／許容外の括弧名／グループ見出しのラベル不一致）
- 2 : 引数・ファイルの誤り
- 3 : 分母0（照合対象が1件も無い。「検査して0件」ではなく「数えていない」）

rc=0 と rc=3 は画面上で似て見えるので、必ず分母を印字する。
`MEASURED_AT` / `ARGS` は rc=2 で早期終了する場合も印字する（何を測って失敗したのかを
後から決められるようにするため）。

月報は1ファイルの中が `# 北原さん提出用（シンプル）` と `# 管理用（詳細）` に分かれ、
提出用セクションの見出しには「（提出）」が付く。グループ見出しがある場合は
**グループ単位で独立に照合**し、worst rc を返す（連結すると提出用の成果目標が
管理用の行動で支えられたことになり、片方だけ切れていても PASS になる）。
提出用の行動目標はグループ見出しを持たない1行1行動の規定なので照合しない。
ただし**提出用を外した結果として照合が1件も行われなかった場合は rc=3** を返す。
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import re
import sys
from pathlib import Path

_VALIDATOR_PATH = Path(__file__).resolve().parent / "validate-goal-output.py"


def _load_validator():
    """照合規則の正本（validate-goal-output.py の Validator）を読み込む。"""
    spec = importlib.util.spec_from_file_location("ubm_validate_goal_output", _VALIDATOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.Validator


Validator = _load_validator()

# 成果への紐づけを免除するグループ名。この2つだけ（半角括弧も同じ扱い）。
EXEMPT_REFS = ("（土台）", "（関係維持）")

# 行内の参照（グループ見出しの無い旧ファイル向けのフォールバック）。
_REF_INLINE = re.compile(r"→\s*支える成果目標\s*[：:]\s*(.+?)\s*$")
# ローカル版 0.4.0〜0.5.0 のカギ括弧記法。受理しない（グループ見出しへ書き換える）。
_REF_BRACKET = re.compile(r"→\s*支える成果目標\s*「")

# 1ファイル2セクション構成のグループ見出し（H1）。
_GROUP_HEAD = re.compile(r"^# (北原さん提出用|管理用)")
# 照合対象から外すグループ（提出用）。
_SUBMISSION_GROUP = re.compile(r"^北原さん提出用")
# グループ見出しのつもりで書かれた H1（`提出` / `管理` を含む）。_GROUP_HEAD に当たらない
# ものはラベルのずれで、当たらないと提出用グループが EOF まで伸びて全体が対象外になる。
_GROUP_HEAD_HINT = re.compile(r"^# .*(?:提出|管理)")


def _detect_kind(text: str) -> str:
    """本文から期間の種別（week / month / period）を決める。

    下位の層は上位の期アンカー（週報の `【今期の売上目標】` など）を持つが、
    上位の層が下位の見出しを持つことは無い。だから最も狭い期間語から順に探し、
    成果目標か行動目標の見出しが最初に見つかった種別を採る。
    """
    for kind, word in Validator.KIND_PERIOD_WORD.items():
        if re.search(rf"^## 【{word}の(?:売上以外の成果目標|行動目標)", text, re.M):
            return kind
    return "week"


def _normalize_paren(ref: str) -> str:
    return ref.replace("(", "（").replace(")", "）")


def _head(block: list[str]) -> str:
    return re.sub(r"^([*-] |・)\s*(\[[ xX]\]\s*)?", "", block[0]).strip()


def split_groups(text: str) -> list[tuple[str, str]]:
    """1ファイル2セクション構成を (ラベル, 本文) へ分ける。

    グループ見出しが1つも無い（週報・期報）場合は、ファイル全体を1グループとして返す。
    ラベルのずれ（`# 詳細（管理用）` など）は `group_label_issues` が別に検出する。
    """
    lines = text.split("\n")
    starts = [i for i, l in enumerate(lines) if _GROUP_HEAD.match(l)]
    if not starts:
        return [("", text)]
    groups: list[tuple[str, str]] = []
    bounds = starts + [len(lines)]
    for k, i in enumerate(starts):
        label = lines[i].lstrip("# ").strip()
        groups.append((label, "\n".join(lines[i:bounds[k + 1]])))
    return groups


def group_label_issues(text: str) -> list[str]:
    """グループ見出しのつもりで書かれた H1 のうち、ラベルが規約と違うものを返す。"""
    return [
        line.strip() for line in text.split("\n")
        if _GROUP_HEAD_HINT.match(line) and not _GROUP_HEAD.match(line)
    ]


def verify(text: str) -> tuple[int, list[str]]:
    """照合して (exit_code, 出力行) を返す。"""
    v = Validator(text, "", _detect_kind(text))
    out: list[str] = []

    keys = [k for k in (Validator._outcome_key(i) for i in v._current_outcome_items()) if k]
    groups = v._current_action_groups()

    by_group = by_inline = exempt = 0
    refs: list[tuple[str, str]] = []  # (参照名, 行動目標の見出し)
    unlinked: list[str] = []
    legacy_bracket: list[str] = []
    bad_paren: list[tuple[str, str]] = []
    multi_ref: list[tuple[str, int]] = []

    for group_ref, _amount, blocks in groups:
        for block in blocks:
            head = _head(block)
            if group_ref:
                value = group_ref
                by_group += 1
            else:
                inline = next((m for m in map(_REF_INLINE.search, block) if m), None)
                if inline is None:
                    if any(_REF_BRACKET.search(l) for l in block):
                        legacy_bracket.append(head)
                    else:
                        unlinked.append(head)
                    continue
                value = inline.group(1)
                by_inline += 1
            parts = [r.strip() for r in value.split("・") if r.strip()]
            if len(parts) > 1:
                multi_ref.append((head, len(parts)))
            for ref in parts:
                if ref.startswith(("（", "(")):
                    if _normalize_paren(ref) in EXEMPT_REFS:
                        exempt += 1
                    else:
                        bad_paren.append((ref, head))
                    continue
                refs.append((ref, head))

    # forward: 参照が成果目標のキーと一致するか（validator の C5 と同じ述語）
    forward_missing: dict[str, int] = {}
    linked: set[str] = set()
    for ref, _head_text in refs:
        matched = [k for k in keys if Validator._ref_matches_key(ref, k)]
        if matched:
            linked.update(matched)
        else:
            forward_missing[ref] = forward_missing.get(ref, 0) + 1

    # backward: 支える行動の無い成果目標（validator の C6 と同じ集合。こちらは FAIL）
    backward_missing = [k for k in keys if k not in linked]

    action_total = by_group + by_inline + len(unlinked) + len(legacy_bracket)
    out.append(
        f"行動目標の項目数: {action_total}（グループ見出し {by_group} / 行内注記 {by_inline} / "
        f"所属不明 {len(unlinked) + len(legacy_bracket)}）"
    )
    out.append(f"免除グループの行動: {exempt} 件（{'／'.join(EXEMPT_REFS)}）")
    out.append(f"成果目標の項目数: {len(keys)}")
    if by_inline:
        out.append(
            f"WARN: 行内注記「→ 支える成果目標：XXX」で所属を書いた行動目標が {by_inline} 件あります"
            "（読み取りのみ受理。新規は `### → 成果目標名：要約（金額円）` のグループ見出しで書く）"
        )

    out.append("")
    out.append("--- forward（行動目標 → 成果目標） ---")
    out.append(f"照合対象 {len(refs)} 件中 未解決 {sum(forward_missing.values())} 件")
    for ref, n in forward_missing.items():
        out.append(
            f"FAIL: 参照「{ref}」と項目名が一致する成果目標がありません（行動目標 {n} 件。"
            "空白を落とした完全一致で照合）"
        )
    for h in unlinked:
        out.append(
            "FAIL: 行動目標がどの成果目標に属するか分かりません"
            f"（`### → 成果目標名：要約（金額円）` の見出しでグループ化する）: {h}"
        )
    for h in legacy_bracket:
        out.append(
            "FAIL: カギ括弧の行内注記「→ 支える成果目標「XXX」」は受理しません"
            f"（`### → XXX：要約（金額円）` のグループ見出しへ書き換える）: {h}"
        )
    for ref, h in bad_paren:
        out.append(
            f"FAIL: 括弧名「{ref}」は免除されません（許容されるのは {'／'.join(EXEMPT_REFS)} だけ。"
            f"相手の側に起きる事実を数で取れる行動は成果目標を立てる）: {h}"
        )
    for h, n in multi_ref:
        out.append(
            f"FAIL: 1つの行動目標が成果目標を {n} 件参照しています"
            f"（成果目標1件につきグループを分ける）: {h}"
        )

    out.append("")
    out.append("--- backward（成果目標 → 行動目標） ---")
    out.append(f"照合対象 {len(keys)} 件中 支える行動なし {len(backward_missing)} 件")
    for k in backward_missing:
        out.append(f"FAIL: 成果目標「{k}」を支える行動目標が1件もありません（達成手段が無い）")

    out.append("")
    out.append("=== 結果 ===")
    unresolved = (
        sum(forward_missing.values()) + len(backward_missing) + len(unlinked)
        + len(legacy_bracket) + len(bad_paren) + len(multi_ref)
    )
    out.append(f"未解決: {unresolved} 件")

    if not refs and not keys and not unresolved:
        out.append(
            "STATUS: NO_TARGET"
            "（照合対象が1件も無い。未解決0件は検査結果ではありません。"
            "見出し「## 【今(週|月|期)の売上以外の成果目標】」「## 【今(週|月|期)の行動目標…】」"
            "が本文にあるか確認してください）"
        )
        return 3, out

    if unresolved:
        out.append("STATUS: FAIL")
        return 1, out
    out.append("STATUS: PASS")
    return 0, out


def _print_trailer(measured_at: str, argv: list[str]) -> None:
    """測定時刻と実行引数。rc=2 の早期終了でも必ず通す。"""
    print(f"MEASURED_AT: {measured_at}")
    print(f"ARGS: {' '.join(argv)}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="UBM目標設定 一本筋（売上→成果→行動）の両方向照合", add_help=True
    )
    ap.add_argument("--file", required=True, action="append", metavar="PATH",
                    help="検証対象の Markdown ファイル（複数指定可）")
    measured_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        # --help は argparse が SystemExit(0) を投げる。usage が正常に出たのに
        # 異常終了にすると、rc で成否を見る側が誤判定する。
        if e.code == 0:
            return 0
        _print_trailer(measured_at, argv)
        return 2

    worst = 0

    def _worst(current: int, rc: int) -> int:
        # 1（未解決あり）を最優先、次に 3（分母0）。
        if rc == 1 or (rc == 3 and current != 1):
            return rc
        return current

    for raw in args.file:
        path = Path(raw)
        print(f"=== {path.name} ===")
        if not path.is_file():
            print(f"ERROR: ファイルが見つかりません: {path}", file=sys.stderr)
            _print_trailer(measured_at, argv)
            return 2
        text = path.read_text(encoding="utf-8")

        for bad in group_label_issues(text):
            print(
                "FAIL: グループ見出しのラベルが規約と違います"
                "（`# 北原さん提出用…` / `# 管理用…` が正。1字ずれると提出用グループが"
                f"末尾まで伸び、ファイル全体が照合対象外になります）: {bad}"
            )
            worst = _worst(worst, 1)

        groups = split_groups(text)
        if len(groups) > 1:
            print(f"（1ファイル2セクション構成: {len(groups)} グループを独立に照合）")
        verified = 0
        for label, body in groups:
            if label:
                print(f"--- グループ: {label} ---")
            if _SUBMISSION_GROUP.match(label):
                print("SKIP: 提出用セクションは照合対象外（所属は管理用セクションのグループ見出しで担保）")
                print("")
                continue
            rc, lines = verify(body)
            for l in lines:
                print(l)
            print("")
            verified += 1
            worst = _worst(worst, rc)

        if verified == 0:
            print(
                f"STATUS: NO_TARGET（照合を実施したグループ 0 件 / 全 {len(groups)} グループ。"
                "提出用セクションしか無いファイルは一本筋を担保できません。"
                "管理用セクション（`# 管理用…`）が本文にあるか確認してください）"
            )
            print("")
            worst = _worst(worst, 3)

    _print_trailer(measured_at, argv)
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
