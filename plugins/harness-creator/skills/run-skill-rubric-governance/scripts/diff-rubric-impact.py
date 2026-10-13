#!/usr/bin/env python3
# /// script
# name: diff-rubric-impact
# version: 0.5.1
# purpose: rubric 改正の提案を過去の score ログに当て、提案の向き（緩和か厳格化か）に応じて、合否が変わるレコードの割合（flip_rate）と必要な bump を出す（27章§6 の影響評価。厳格化は常に major、緩和は最低 minor。flip_rate が 30% を超えたかは、猶予期間と board 招集の根拠として別のキーに出す）
# inputs:
#   - --proposal: 改正提案の JSON（templates/proposal.json の形。change.type・change.direction・change.severity と bump（最上位か change.bump）を読む）
#   - --logs: score ログを探すディレクトリ（配下の *-score.jsonl を再帰で読む。例 eval-log、eval-log/<plugin>）
#   - --threshold: 合格点（既定 80）
#   - 引数なし: PostToolUse hook からの起動とみなし、何もせず exit 0
# outputs:
#   - stdout: JSON {total, would_flip, flip_rate, flip_rate_limit, exceeds_flip_rate_limit, proposed_bump, required_bump, change_type, direction, direction_source, severity_weight, severity_source, impact_model, score_logs, skipped_no_score, skipped_invalid, unreadable_logs}（severity_weight は厳格化の見積もりに使った重み、severity_source は change.severity どおりなら declared・分からず一番重い重みにしたなら assumed。緩和は重みを使わないのでどちらも null）
#   - stderr: 止めた理由 / 向きを仮定したこと / 厳格化で severity が high・medium・low のどれでもなく一番重い重みで見積もったこと / 提案の bump が required_bump に届かないこと / 数えなかったレコードと読めなかったファイル
#   - exit: 0=OK / 2=usage・proposal が無い・読めない・change.type や change.direction の値が不正・bump が無いか major・minor・patch 以外・最上位と change.bump の値が違う・--logs がディレクトリでない・score を持つレコードが 0 件
# requires-python: ">=3.10"
# dependencies: []
# contexts: [A, C]
# network: false
# write-scope: none
# ///
"""rubric 改正の提案が過去の評価の合否をどれだけ変えるかを見積もる。

Usage:
  diff-rubric-impact.py --proposal <json> --logs <dir> [--threshold 80]

--logs の配下にある score ログ（write-eval-log.py が書く eval-log/<plugin>/<date>-score.jsonl）を
再帰で読む。score ログでない jsonl（run-skill-rubric-governance/log の governance log など）は読まない。

数えるのは数値の score を持つレコードだけ。score の無いレコードを 100 点とみなすと、合否が
変わらないレコードとして分母に入り、flip_rate が実際より小さく出る（30% 超の判定が働かない）。
そこで score の無いレコードは数えず、件数を skipped_no_score に出す。JSON の
object として読めない行は skipped_invalid に、読めないファイルは unreadable_logs に数える。
score を持つレコードが 1 件も無いときは影響を評価できないので、結果を出さずに exit 2 で止める。

見積もりの模型は提案の向きで選ぶ（出力の impact_model）。
- 厳格化（worst_case_tightening）: 提案した rule が全レコードで違反になったとして、severity の重み
  （high -20 / medium -10 / low -3）を score に足し、合格点を下回るようになるレコードを数える。
  change.severity が無いときや、この 3 つのどれでもないとき（critical・High・error・warn など）は、
  重みが分からないので一番重い重みで見積もり、stderr に出す。止めはしない（ほかの rubric の severity を
  書いた提案も見積もれるように）。使った重みは出力の severity_weight に、その出どころは severity_source
  に出す（change.severity どおりなら declared、推し量ったなら assumed。direction_source と同じ流儀）。
  緩和は重みを使わないので、どちらも null。
- 緩和（relaxation_no_new_failures）: 緩和は「合格とする値の集合を広げるだけで、今まで合格したものが
  すべて合格のままである変更」なので、合格から不合格に変わるレコードは定義上 0 件。would_flip は 0。

必要な bump（required_bump）は向きで決める（SKILL.md の Key Rule 2）。厳格化は flip_rate に
関わらず major。緩和は提案の bump と minor の大きい方で、patch の緩和は minor に引き上げる
（semver 規約: 閾値や severity を変えるなら最低 minor。patch は文言だけ）。required_bump を
下回ってよいのは、判定を変えない文言だけの patch と、緊急パッチ（emergency: true）だけ。道具は
それを見分けないので、下回った提案は stderr に出し、例外に当たるかは承認者が rubric.json の差分で
確かめる。厳格化の flip_rate が flip_rate_limit（0.30）を超えたかは exceeds_flip_rate_limit に
出す。これは bump を決めず、猶予期間と board 招集の根拠にする。

提案の bump は最上位か change.bump に書き、major・minor・patch のどれかでなければならない。
両方に書くなら、どちらも正しい値で、同じ値でなければならない。無いとき、どちらかの値が不正なとき、
両方の値が違うときは、required_bump と比べられないので exit 2 で止める。

向きは提案の JSON で決める（出力の direction と direction_source）。
- change.type が add なら厳格化、remove なら緩和（direction_source: type）。
- modify は change.direction（relax か tighten）で宣言する（direction_source: declared）。
  change.type が無く change.direction があるときも、その宣言に従う（declared）。
- change.type も change.direction も無いとき、または modify で direction が無いときは、
  向きが分からないので厳格化とみなして最悪の場合で見積もる（direction_source: assumed。
  stderr にも出す）。黙って緩和として扱うことはしない。
- change.type や change.direction の値が不正なとき、add・remove と食い違う direction を
  書いたときは、見積もれないので exit 2 で止める。
宣言が緩和の定義を満たしているかは確かめない（道具は宣言を信じる）。その判断の責任は
提案者と承認者にある。
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path

SEVERITY_WEIGHTS = {"high": -20, "medium": -10, "low": -3}
# severity が無いか SEVERITY_WEIGHTS に無い値のときの重み。最悪の場合の見積もりなので一番重いもの
UNKNOWN_SEVERITY_WEIGHT = min(SEVERITY_WEIGHTS.values())
SCORE_LOG_GLOB = "*-score.jsonl"

RELAX = "relax"
TIGHTEN = "tighten"
# change.type ごとの向き。modify は change.direction で宣言する。
TYPE_DIRECTION = {"add": TIGHTEN, "remove": RELAX, "modify": None}
IMPACT_MODELS = {TIGHTEN: "worst_case_tightening", RELAX: "relaxation_no_new_failures"}
# 厳格化の flip_rate がこれを超えたら、猶予期間と board 招集の根拠にする（bump は決めない）
FLIP_RATE_LIMIT = 0.30
# 小さい順。required_bump と提案の bump の大小はこの並びで比べる
BUMPS = ("patch", "minor", "major")
# 緩和の required_bump の下限。閾値や severity を変えるなら最低 minor（patch は文言だけ）
RELAX_MIN_BUMP = "minor"


def parse_proposal(p: Path) -> tuple[dict, dict]:
    """提案の JSON を読み、(最上位, change) を返す。"""
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("proposal の最上位が object でない")
    change = data.get("change", {})
    if not isinstance(change, dict):
        raise ValueError("proposal の change が object でない")
    return data, change


def resolve_direction(change: dict) -> tuple[str, str]:
    """提案の向きと、その出どころ（type / declared / assumed）を返す。値が不正なら ValueError。"""
    ctype = change.get("type")
    if ctype is not None and not (isinstance(ctype, str) and ctype in TYPE_DIRECTION):
        raise ValueError(f"change.type が add・modify・remove のどれでもない: {ctype!r}")
    declared = change.get("direction")
    if declared is not None and not (isinstance(declared, str) and declared in IMPACT_MODELS):
        raise ValueError(f"change.direction が relax・tighten のどちらでもない: {declared!r}")
    implied = TYPE_DIRECTION.get(ctype)
    if implied is not None:
        if declared is not None and declared != implied:
            raise ValueError(f"change.type {ctype} は {implied} なのに change.direction が {declared}")
        return implied, "type"
    if declared is not None:
        return declared, "declared"
    return TIGHTEN, "assumed"


def resolve_bump(proposal: dict, change: dict) -> str:
    """提案の bump を返す。最上位と change.bump のどちらに書いてもよい。

    無いとき、書いた値が major・minor・patch 以外のとき、両方に書いて値が違うときは ValueError。
    片方を黙って選ぶと、提案者が意図しない方の bump で required_bump と比べてしまう。
    """
    written = {where: src["bump"] for where, src in (("最上位の bump", proposal), ("change.bump", change))
               if "bump" in src}
    if not written:
        raise ValueError("最上位にも change.bump にも bump が無い")
    for where, bump in written.items():
        if not (isinstance(bump, str) and bump in BUMPS):
            raise ValueError(f"{where} が major・minor・patch のどれでもない: {bump!r}")
    if len(set(written.values())) > 1:
        raise ValueError("・".join(f"{where} は {bump}" for where, bump in written.items()) + "で、値が違う")
    return next(iter(written.values()))


def required_bump(direction: str, bump: str) -> str:
    """向きと提案の bump から、必要な bump を返す（SKILL.md の Key Rule 2）。

    厳格化は flip_rate に関わらず major。緩和は提案の bump と RELAX_MIN_BUMP の大きい方。
    """
    if direction == TIGHTEN:
        return "major"
    return max(bump, RELAX_MIN_BUMP, key=BUMPS.index)


def record_score(rec: object) -> float | None:
    """数値の score を返す。score を持たない（bool・文字列・NaN を含む）レコードは None。"""
    if not isinstance(rec, dict):
        return None
    score = rec.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None
    if isinstance(score, float) and not math.isfinite(score):
        return None
    return score


def load_scores(log_dir: Path) -> tuple[list[float], dict]:
    """log_dir 配下の score ログから score を集める。(scores, 数えなかった内訳) を返す。"""
    scores: list[float] = []
    stats = {"score_logs": 0, "skipped_no_score": 0, "skipped_invalid": 0, "unreadable_logs": []}
    for f in sorted(p for p in log_dir.rglob(SCORE_LOG_GLOB) if p.is_file()):
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            stats["unreadable_logs"].append(f"{f} ({type(exc).__name__})")
            continue
        stats["score_logs"] += 1
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                stats["skipped_invalid"] += 1
                continue
            if not isinstance(rec, dict):
                stats["skipped_invalid"] += 1
                continue
            score = record_score(rec)
            if score is None:
                stats["skipped_no_score"] += 1
                continue
            scores.append(score)
    return scores, stats


def main() -> int:
    # PostToolUse:Edit の hook は引数を付けずに呼ぶ。そのときは何もしない。
    # 引数があれば提案の評価として扱い、--proposal が無ければ argparse が exit 2 で止める。
    if len(sys.argv) == 1:
        return 0
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument("--proposal", required=True)
    ap.add_argument("--logs", required=True,
                    help="score ログ（*-score.jsonl）を再帰で探すディレクトリ。例: eval-log")
    ap.add_argument("--threshold", type=int, default=80)
    args = ap.parse_args()

    pf = Path(args.proposal)
    if not pf.is_file():
        print(f"error: proposal missing: {pf}", file=sys.stderr)
        return 2
    try:
        proposal, change = parse_proposal(pf)
    except (OSError, ValueError) as exc:
        print(f"error: proposal を読めない: {pf} ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 2
    try:
        direction, direction_source = resolve_direction(change)
    except ValueError as exc:
        print(f"error: 提案の向きを決められない: {pf} ({exc})。change.type は add・modify・remove、"
              "modify の change.direction は relax・tighten のどちらかを書く", file=sys.stderr)
        return 2
    try:
        bump = resolve_bump(proposal, change)
    except ValueError as exc:
        print(f"error: 提案の bump を読めない: {pf} ({exc})。bump は最上位か change.bump に major・minor・patch の"
              "どれかを書く（両方に書くなら同じ値）", file=sys.stderr)
        return 2

    log_dir = Path(args.logs)
    if not log_dir.is_dir():
        print(f"error: --logs がディレクトリでない: {log_dir}。影響を評価できない", file=sys.stderr)
        return 2

    scores, stats = load_scores(log_dir)
    for bad in stats["unreadable_logs"]:
        print(f"warning: score ログを読めない: {bad}", file=sys.stderr)
    skipped = stats["skipped_no_score"] + stats["skipped_invalid"]
    if skipped:
        print(f"warning: 数えなかったレコード {skipped} 件（score なし {stats['skipped_no_score']}・"
              f"JSON の object でない {stats['skipped_invalid']}）", file=sys.stderr)
    if not scores:
        print(f"error: {log_dir} の配下に score を持つレコードが無い（{SCORE_LOG_GLOB} {stats['score_logs']} 件を"
              "読んだ）。影響を評価できないので止める。--logs には score ログのある場所（例: eval-log）を渡す",
              file=sys.stderr)
        return 2

    if direction_source == "assumed":
        print("warning: 提案の向きが分からない（change.type も change.direction も無いか、modify に "
              "change.direction が無い）ので、"
              "厳格化とみなして最悪の場合で見積もった（direction_source: assumed）。緩和の提案なら "
              'change.direction に "relax" を書いて流し直す', file=sys.stderr)

    would_flip = 0
    severity_weight = severity_source = None  # 緩和は重みを使わないので、どちらも null のまま
    if direction == TIGHTEN:
        sev = change.get("severity")
        severity_weight = SEVERITY_WEIGHTS.get(sev) if isinstance(sev, str) else None
        severity_source = "declared"
        if severity_weight is None:
            severity_weight, severity_source = UNKNOWN_SEVERITY_WEIGHT, "assumed"
            print(f"warning: change.severity（{sev!r}）が無いか high・medium・low のどれでもないので、重みが"
                  f"分からない。最悪の場合として一番重い {severity_weight} で見積もった（severity_source: assumed）",
                  file=sys.stderr)
        for old_score in scores:
            # 最悪の場合: 改正した rule がこのレコードで新たに発火する
            new_score = max(0, old_score + severity_weight)
            if old_score >= args.threshold and new_score < args.threshold:
                would_flip += 1
    # 緩和では、合格から不合格に変わるレコードは定義上 0 件（would_flip は 0 のまま）

    flip_rate = would_flip / len(scores)
    bump_required = required_bump(direction, bump)
    if BUMPS.index(bump) < BUMPS.index(bump_required):
        print(f"warning: 提案の bump {bump} が required_bump {bump_required} に届かない（厳格化は major、"
              "緩和は最低 minor）。下回って通せるのは文言だけの patch と緊急パッチ（emergency: true）だけで、"
              "承認者が rubric.json の差分で確かめる", file=sys.stderr)
    out = {
        "total": len(scores),
        "would_flip": would_flip,
        "flip_rate": round(flip_rate, 4),
        "flip_rate_limit": FLIP_RATE_LIMIT,
        "exceeds_flip_rate_limit": flip_rate > FLIP_RATE_LIMIT,
        "proposed_bump": bump,
        "required_bump": bump_required,
        "change_type": change.get("type"),
        "direction": direction,
        "direction_source": direction_source,
        "severity_weight": severity_weight,
        "severity_source": severity_source,
        "impact_model": IMPACT_MODELS[direction],
        "score_logs": stats["score_logs"],
        "skipped_no_score": stats["skipped_no_score"],
        "skipped_invalid": stats["skipped_invalid"],
        "unreadable_logs": len(stats["unreadable_logs"]),
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
