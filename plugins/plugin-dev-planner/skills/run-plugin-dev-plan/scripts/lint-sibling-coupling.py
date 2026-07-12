#!/usr/bin/env python3
# /// script
# name: lint-sibling-coupling
# purpose: 未宣言の密結合な同一 phase 兄弟ペア候補を advisory 検出する (record-only・盲目並列の再発防止安全網)。derive-task-graph は consumes edge を出さずグラフから密結合を推論できないため、inventory のテキスト参照 (B の inputs/purpose が A の出力ファイル名を参照=producer→consumer データ流) を唯一の決定論シグナルにして、couples_with 宣言も depends_on 順序も持たない兄弟ペアを候補として提示する。architect が couples_with を宣言すべきだったが忘れたケースを機械的に漏らさず拾う (判断は architect・機構は候補提示)。
# inputs:
#   - argv: <PLAN_DIR> [--strict] (<PLAN_DIR>/component-inventory.json + phase-*.md を読む)
# outputs:
#   - stdout: {"candidates":[{"a","b","phase","signal"},...]} JSON (a<b・昇順決定論)
#   - stderr: 読込/parse エラー
#   - exit: 0=候補0 または advisory (既定・record-only) / 1=--strict 指定かつ候補>0 / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: none (read-only)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""未宣言の密結合な同一 phase 兄弟ペアの advisory 検出器 (盲目並列の再発防止安全網)。

背景: couples_with (接合が密な兄弟ペアの直列化宣言) は architect の判断で付与するが、
宣言忘れがあると盲目並列の代償 (統合 finding の先送り) が再発する。本 lint は「宣言し
忘れたが直列化すべき候補」を機械的に拾う安全網。derive-task-graph は consumes edge を
焼かないためグラフからは密結合を推論できず、唯一の決定論シグナルは inventory のテキスト
参照になる:

  候補条件 (全て満たすペア A/B を候補とする):
    (1) 同一 phase の兄弟: A と B が同じ phase ファイルの entities_covered に共出現。
    (2) 未順序: どちらも depends_on にも couples_with にも相手を持たない (既宣言/既順序は除外)。
    (3) データ流シグナル: 片方 (例 B) の inputs / outputs / purpose テキストが他方 (A) の
        script_name / build_target basename を参照する (B が A の出力を読む=producer→consumer)。

判断は architect に残す (record-only・既定 exit0)。CI で強制したい場合のみ --strict で
候補>0 を exit1 にする。テキスト参照はヒューリスティックゆえ false-positive があり得るため
ハード 12 ゲートには含めない advisory。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402


def _load_inventory(plan_dir: Path) -> dict:
    inv_path = plan_dir / "component-inventory.json"
    return json.loads(inv_path.read_text(encoding="utf-8"))


def _same_phase_siblings(plan_dir: Path) -> dict[str, set[str]]:
    """phase_ref -> その phase の entities_covered に共出現する component id 集合。"""
    out: dict[str, set[str]] = {}
    for pf in sorted(plan_dir.glob("phase-*.md"), key=lambda p: p.name):
        text = pf.read_text(encoding="utf-8")
        fm = specfm.parse_frontmatter(text)
        phase_ref = str(fm.get("id") or pf.stem)
        entities = fm.get("entities_covered") or []
        if isinstance(entities, list):
            ids = {e for e in entities if isinstance(e, str) and e}
            if len(ids) >= 2:
                out.setdefault(phase_ref, set()).update(ids)
    return out


def _reference_tokens(comp: dict) -> set[str]:
    """component が「出力として提供する」識別トークン (他 component が参照すると密結合)。

    全 component_kind をカバーする: script は script_name/build_target basename (row-emit.py)、
    skill/sub-agent/command は name + build_target 末尾 (skills/run-foo/ → run-foo / agents/x.md → x)。
    拡張子あり/なし両形を入れて「row-emit.py」参照と「row-emit」参照の双方に当てる。
    """
    tokens: set[str] = set()
    for key in ("script_name", "name"):
        v = comp.get(key)
        if isinstance(v, str) and v.strip():
            tokens.add(v.strip())
    bt = comp.get("build_target")
    if isinstance(bt, str) and bt.strip():
        base = bt.strip().rstrip("/").split("/")[-1]
        if base:
            tokens.add(base)
            stem = base.rsplit(".", 1)[0]  # 拡張子除去 (row-emit.py → row-emit / x.md → x)
            if stem:
                tokens.add(stem)
    return {t for t in tokens if len(t) >= 4}  # 短すぎるトークンの誤マッチを避ける


def _consumer_text(comp: dict) -> str:
    """component が「入力として読む/相手を指す」記述を全 kind 横断で連結する。

    script=inputs/outputs/purpose・skill=goal/output_contract/purpose_background/purpose・
    sub-agent/command=description。dict/list 値は JSON 文字列化して substring 検査対象にする。
    """
    parts: list[str] = []
    for key in ("inputs", "outputs", "purpose", "description", "goal",
                "output_contract", "purpose_background"):
        v = comp.get(key)
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (dict, list)):
            parts.append(json.dumps(v, ensure_ascii=False))
    return "\n".join(parts)


def find_candidates(plan_dir: Path) -> list[dict]:
    """未宣言の密結合な同一 phase 兄弟ペア候補を昇順 (a<b) で返す。"""
    inv = _load_inventory(plan_dir)
    comps = {c["id"]: c for c in inv.get("components", []) if isinstance(c, dict) and c.get("id")}
    siblings = _same_phase_siblings(plan_dir)

    # 既宣言/既順序ペア (unordered) を除外集合にする。
    declared: set[frozenset[str]] = set()
    for cid, c in comps.items():
        for key in ("depends_on", "couples_with"):
            for other in c.get(key, []) or []:
                if isinstance(other, str) and other and other != cid:
                    declared.add(frozenset((cid, other)))

    candidates: list[dict] = []
    seen: set[frozenset[str]] = set()
    for phase_ref in sorted(siblings):
        ids = sorted(i for i in siblings[phase_ref] if i in comps)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                pair = frozenset((a, b))
                if pair in declared or pair in seen:
                    continue
                # データ流シグナル: 片方が他方の出力トークンを参照するか (両向き検査)。
                signal = None
                a_tokens, b_tokens = _reference_tokens(comps[a]), _reference_tokens(comps[b])
                a_text, b_text = _consumer_text(comps[a]), _consumer_text(comps[b])
                hit_ba = sorted(t for t in a_tokens if t in b_text)  # B が A の出力を参照
                hit_ab = sorted(t for t in b_tokens if t in a_text)  # A が B の出力を参照
                if hit_ba:
                    signal = f"{b} references {a} output token(s) {hit_ba}"
                elif hit_ab:
                    signal = f"{a} references {b} output token(s) {hit_ab}"
                if signal:
                    seen.add(pair)
                    candidates.append({"a": a, "b": b, "phase": phase_ref, "signal": signal})
    return sorted(candidates, key=lambda c: (c["phase"], c["a"], c["b"]))


def _usage() -> int:
    print("usage: lint-sibling-coupling.py <PLAN_DIR> [--strict]", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    strict = False
    if "--strict" in argv:
        strict = True
        argv.remove("--strict")
    if len(argv) != 1:
        return _usage()
    plan_dir = Path(argv[0])
    if not plan_dir.is_dir():
        print(f"not a directory: {plan_dir}", file=sys.stderr)
        return 2
    if not (plan_dir / "component-inventory.json").exists():
        print(f"component-inventory.json not found in {plan_dir}", file=sys.stderr)
        return 2
    try:
        candidates = find_candidates(plan_dir)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"read/parse error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"candidates": candidates}, ensure_ascii=False, indent=2))
    if candidates:
        for c in candidates:
            print(
                f"[advisory] 未宣言の密結合候補 {c['a']}<->{c['b']} (phase {c['phase']}): "
                f"{c['signal']} — couples_with 宣言 or depends_on 順序付けを検討 (盲目並列で統合 finding 先送りの恐れ)",
                file=sys.stderr,
            )
        if strict:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
