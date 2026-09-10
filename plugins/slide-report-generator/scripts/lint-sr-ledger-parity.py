#!/usr/bin/env python3
# /// script
# name: lint-sr-ledger-parity
# purpose: 検査 ID が名指しする SR-ID と spec-registry の規則行を突合し、「規則本文が無いまま検査だけが在る」状態が台帳(§17)に載らずに隠れることを fail-closed で封鎖する plugin-root glue。CLI と import(pytest) 両対応・Python 標準ライブラリのみ。
# inputs:
#   - CLI: [--root <plugin-root>] [--json] [--self-test]
# outputs:
#   - stdout: JSON (passed/count/findings[])
#   - exit: 0=ずれ無し(PASS) / 1=ずれ検出(fail-closed) / 2=対象ファイル不在・self-test 失敗。
# contexts: [glue]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""検査 ID の `sr:` ↔ spec-registry の規則行 の突合ゲート (fail-closed)。

## 何を解く問題か

`vendor/scripts/validate-structure.js` の `V_DEFINITIONS` は各検査に
`sr: "SR-4-03"` の形で規則 ID を持つ。**この名前が指す規則本文が
`references/spec-registry.md` に無くても、検査は動くし緑にもなる。**
検査 ID の側に名前があるので、読んだ人は規則があると思う。

これは V-001 で起きた「規則はあるが判定する実行体がどこにも無い」の裏返しで、
どちらも**見ていないものが緑に見える**同じ形をしている。

## 何を正とするか (2 つの集合を分けて数える)

- **規則行がある**   : §17 以外の節に `| SR-... |` で始まる表行がある
- **台帳に載っている**: §17 (欠落台帳) の表に `| SR-... |` の行がある

§17 は規則を定める節ではなく「仕様本文がまだ無い SR の一覧」なので、
**§17 の中に SR-ID が書いてあることを『規則がある』と数えてはいけない。**
実際にこの取り違えが起きた: 走査を md 全体で行うと、台帳へ載せた 5 件が
「本文がある」と数えられ、欠落が 7 件から 2 件へ減ったように見えた。
**台帳に載せた行為が、台帳の対象を消す**という自己参照になっていた。
節を分けて数えるのはこのため。

## 検出する 3 つのずれ

| check | 状態 | なぜ危険か |
|---|---|---|
| `sr-unlogged`     | 規則行が無く、台帳にも無い | 欠落が誰にも見えない。検査 ID の名前だけが規則があるように読める |
| `sr-ledger-stale` | 規則行があるのに台帳に残っている | 台帳が減らない。「減らない台帳は増えるだけ」になる |
| `sr-ledger-vids`  | 台帳行の V-ID 列が実際の参照と違う | 台帳を読んで影響範囲を測れなくなる |
| `sr-ledger-count` | 台帳の散文が言う「N 種 / M 件」が実測と違う | 減ったかどうかを数字で読めなくなる |

`sr-ledger-stale` を入れているのは、**このゲートを「台帳へ足せば緑」にしないため**。
足す方向だけを見る検査は、規則を書く動機ではなく台帳へ書く動機を作る。

## 何を検査しないか (意図的な非対象)

- **規則の中身は見ない。**行があるかどうかだけを見る。中身の妥当性は人が読む。
- **台帳の数詞は `lint-count-parity.py` の `<!-- count: -->` へ寄せない。**あちらの実測器は
  「0 を返してはならない (0 は空集合という別の主張)」という約束の上に立っているが、
  この台帳の 0 は**目標の状態**で、規則を全部書き終えた日に self-test が倒れる。
  数える対象がこの lint 自身の内側にあるので、ここで突合する。
- **`| SR-... |` の表行以外の言及は規則行として数えない。**散文中の「SR-0-01 参照」を
  規則本文と数えると、参照を 1 行足すだけで欠落が消える。数え方は
  `lint-count-parity.py` の `specRegistryRule` と揃えてある (同じものを別の数え方で
  数えると、2 つの正本ができる)。

exit: 0=PASS / 1=ずれ検出 / 2=usage・対象不在・self-test 失敗。
pytest からは run_checks(root) / missing_sr(root) を import して使う。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SPEC_REGISTRY = "references/spec-registry.md"
_VALIDATE_STRUCTURE = "vendor/scripts/validate-structure.js"

# 台帳の節。見出しが変わったら「§17 が無い」で fail-closed に倒す (黙って
# 全件 unlogged にすると、節を消すことで検査を通せてしまう)。
_LEDGER_HEADING_RE = re.compile(r"^##\s*§17\b")
_ANY_H2_RE = re.compile(r"^##\s")

# SR-ID は `SR-4-03` の数字系と `SR-V8-COVER` の語系が混在する。どちらも取る。
_SR_ID = r"SR-[0-9A-Za-z]+-[0-9A-Za-z-]+"
_ROW_RE = re.compile(rf"^\|\s*({_SR_ID})\s*\|", re.M)
_V_ENTRY_RE = re.compile(r'"(V-\d+)":\s*\{([^}]*)\}')
# 台帳の散文が自分で言う件数。「7 種」「参照している V-ID は 10 件」の 2 つを取る。
_COUNT_KIND_RE = re.compile(r"(\d+)\s*種")
_COUNT_VID_RE = re.compile(r"V-ID\s*は?\s*(\d+)\s*件")
_SR_FIELD_RE = re.compile(r'sr:\s*"([^"]+)"')
_VID_RE = re.compile(r"V-\d+")


def _plugin_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    return Path(__file__).resolve().parent.parent


def _read(root: Path, rel: str) -> str:
    p = root / rel
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def sr_references(root: Path) -> dict[str, list[str]]:
    """`V_DEFINITIONS` が名指しする SR-ID -> それを参照する V-ID の一覧。

    正本は validate-structure.js のみ。spec-registry からは 1 バイトも読まない
    (規則の側から検査を数えると、規則が無い検査を数え落とす)。
    """
    out: dict[str, list[str]] = {}
    for vid, body in _V_ENTRY_RE.findall(_read(root, _VALIDATE_STRUCTURE)):
        m = _SR_FIELD_RE.search(body)
        if not m or m.group(1) == "?":
            continue
        out.setdefault(m.group(1), []).append(vid)
    return {k: sorted(v) for k, v in sorted(out.items())}


def _split_ledger(registry: str) -> tuple[str, str] | None:
    """spec-registry を (§17 以外, §17) に割る。§17 が無ければ None。"""
    lines = registry.splitlines()
    start = next((i for i, l in enumerate(lines) if _LEDGER_HEADING_RE.match(l)), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if _ANY_H2_RE.match(lines[i])), len(lines))
    body = "\n".join(lines[:start] + lines[end:])
    ledger = "\n".join(lines[start:end])
    return body, ledger


def _ledger_rows(ledger: str) -> dict[str, list[str]]:
    """台帳の表行 -> その行が挙げている V-ID の一覧。"""
    rows: dict[str, list[str]] = {}
    for line in ledger.splitlines():
        m = _ROW_RE.match(line)
        if m:
            rows[m.group(1)] = sorted(set(_VID_RE.findall(line[m.end():])))
    return rows


def missing_sr(root: Path, registry: str | None = None) -> dict[str, list[str]]:
    """規則行が無い SR-ID -> 参照している V-ID。台帳への記載の有無は問わない。

    `lint-count-parity.py` の実測器はこれを呼ぶ。数える場所を 1 つにしておかないと、
    散文の「7 種 / 10 件」を縛る値がこの lint と別勘定になる。
    """
    registry = _read(root, _SPEC_REGISTRY) if registry is None else registry
    split = _split_ledger(registry)
    body = registry if split is None else split[0]
    have = set(_ROW_RE.findall(body))
    return {sr: vids for sr, vids in sr_references(root).items() if sr not in have}


def _prose_lines(ledger: str) -> list[str]:
    """台帳の散文行 (表行と見出しを除く)。件数の主張はここに書かれる。"""
    return [l for l in ledger.splitlines()
            if l.strip() and not l.lstrip().startswith("|") and not l.startswith("#")]


def _check_declared_counts(ledger: str, refs: dict[str, list[str]], have: set[str],
                           rows: dict[str, list[str]], add) -> None:
    """台帳の散文が言う「N 種 / M 件」を実測と突合する。

    この 2 つの数は**減ることに意味がある**。減ったことを読み手が数字で確かめられ
    なくなると、台帳は「増えるだけの一覧」に戻る。だから数字を消させるのではなく
    実測へ縛る。台帳が空 (規則を全部書き終えた) のときは、主張する対象が無いので
    数詞そのものを求めない。
    """
    if not rows:
        return
    missing = {sr: v for sr, v in refs.items() if sr not in have}
    want_kind = len(missing)
    want_vid = sum(len(v) for v in missing.values())
    prose = " ".join(_prose_lines(ledger))

    kinds = [int(x) for x in _COUNT_KIND_RE.findall(prose)]
    vids = [int(x) for x in _COUNT_VID_RE.findall(prose)]
    if not kinds or not vids:
        add("sr-ledger-count-unstated",
            f"台帳が件数を書いていない (実測は {want_kind} 種 / V 参照 {want_vid} 件)。"
            "「N 種 / 参照している V-ID は M 件」の形で書く。数が無いと、"
            "この表が減っているのかどうかを読み手が確かめられない",
            _SPEC_REGISTRY)
        return
    if want_kind not in kinds:
        add("sr-ledger-count",
            f"台帳が言う種類数 ({'/'.join(map(str, kinds))}) に実測 {want_kind} が無い",
            _SPEC_REGISTRY)
    if want_vid not in vids:
        add("sr-ledger-count",
            f"台帳が言う V-ID 件数 ({'/'.join(map(str, vids))}) が実測 {want_vid} と違う",
            _SPEC_REGISTRY)


def run_checks(root: Path, registry: str | None = None) -> list[dict]:
    findings: list[dict] = []

    def add(check: str, message: str, where: str) -> None:
        findings.append({"check": check, "message": message, "where": where})

    registry = _read(root, _SPEC_REGISTRY) if registry is None else registry
    refs = sr_references(root)
    if not refs:
        add("sr-source-unreadable",
            f"{_VALIDATE_STRUCTURE} から `sr:` を 1 件も読めない "
            "(V_DEFINITIONS の書き方が変わった。抽出を追随させる。"
            "読めないまま通すと、この検査が静かに無効になる)",
            _VALIDATE_STRUCTURE)
        return findings

    split = _split_ledger(registry)
    if split is None:
        add("sr-ledger-section-missing",
            "spec-registry に §17 (欠落台帳) の見出しが無い。台帳が消えると、"
            "規則本文の無い SR がどこにも記録されない。見出しを直したなら "
            "_LEDGER_HEADING_RE を追随させる",
            _SPEC_REGISTRY)
        return findings

    body, ledger = split
    have = set(_ROW_RE.findall(body))
    rows = _ledger_rows(ledger)

    for sr, vids in refs.items():
        listed = sr in rows
        if sr in have:
            if listed:
                add("sr-ledger-stale",
                    f"{sr} は規則行が書かれたのに §17 の台帳に残っている "
                    "(本文が書けた SR は台帳から消す。残すと台帳が減らなくなる)",
                    _SPEC_REGISTRY)
            continue
        if not listed:
            add("sr-unlogged",
                f"{sr} は {'/'.join(vids)} が名指ししているのに規則行が無く、"
                "§17 の台帳にも載っていない (規則を書くか、書けない理由と行き先を台帳へ載せる)",
                _VALIDATE_STRUCTURE)
        elif rows[sr] != vids:
            add("sr-ledger-vids",
                f"{sr} の台帳行が挙げる V-ID ({'/'.join(rows[sr]) or 'なし'}) が"
                f"実際の参照 ({'/'.join(vids)}) と違う",
                _SPEC_REGISTRY)

    _check_declared_counts(ledger, refs, have, rows, add)

    for sr in sorted(set(rows) - set(refs)):
        add("sr-ledger-orphan",
            f"{sr} は §17 の台帳にあるが、どの検査からも `sr:` で名指しされていない "
            "(検査が消えたなら台帳からも消す)",
            _SPEC_REGISTRY)

    return findings


# ---------------------------------------------------------------------------
# count-parity 用の実測器。散文の「7 種 / 10 件」をこの実測へ縛るために公開する。
# ---------------------------------------------------------------------------
def count_missing_sr(root: Path) -> int | None:
    """規則本文がまだ無い SR-ID の種類数。"""
    return len(missing_sr(root)) or None


def count_missing_sr_vids(root: Path) -> int | None:
    """上記の SR を参照している V-ID の件数 (種類数とは別の数)。"""
    n = sum(len(v) for v in missing_sr(root).values())
    return n or None


# ---------------------------------------------------------------------------
# self-test: 正しい状態と壊れた状態の双方を判定できることを自己検証する
# ---------------------------------------------------------------------------
def _self_test(root: Path) -> tuple[bool, list[str]]:
    log: list[str] = []
    ok = True

    def check(label: str, cond: bool) -> None:
        nonlocal ok
        log.append(f"{'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            ok = False

    refs = sr_references(root)
    check(f"T1 V_DEFINITIONS から `sr:` を読める (SR-ID {len(refs)} 種)", len(refs) > 10)

    live = _read(root, _SPEC_REGISTRY)
    check("T2 §17 の見出しを見つけられる", _split_ledger(live) is not None)

    gap = missing_sr(root)
    body, ledger = _split_ledger(live) or ("", "")
    # T3: §17 を除かずに数えると欠落は過少にしか出ない。台帳へ載せた SR は
    #     §17 の中に `| SR-... |` の行を持つので、節を分けずに数えると
    #     「本文がある」と読まれる。等号で固定せず不等号にしてあるのは、
    #     台帳が空のとき両者が一致するのが正しい状態だから。
    whole = {sr for sr in refs if sr not in set(_ROW_RE.findall(live))}
    check(f"T3 台帳を除いた欠落 ({len(gap)} 種) は md 全体で数えた場合 ({len(whole)} 種) 以上",
          len(gap) >= len(whole))

    # T4: 実データが今どうなっているかを log へ残す (PASS/FAIL でなく観測値)。
    log.append(f"INFO 規則行の無い SR: {len(gap)} 種 / V 参照 "
               f"{sum(len(v) for v in gap.values())} 件: {', '.join(sorted(gap)) or 'なし'}")
    log.append(f"INFO §17 の台帳行: {len(_ledger_rows(ledger))} 件")

    # T5-T8: 合成した spec-registry で 4 つの状態を作り、それぞれを検出できるか。
    #        正本 (validate-structure.js) は本物のまま使う。
    sample = sorted(refs)[0]
    sample_vids = "/".join(refs[sample])
    others = "\n".join(f"| {sr} | 規則 |" for sr in refs if sr != sample)

    def probe(text: str) -> list[dict]:
        return run_checks(root, registry=text)

    all_written = f"## §1 規則\n\n| SR-ID | 規則 |\n|---|---|\n| {sample} | 規則 |\n{others}\n\n" \
                  "## §17 仕様本文がまだ無い SR の一覧\n\n| SR-ID | V-ID | 行き先 |\n|---|---|---|\n"
    check("T5 全件に規則行があり台帳が空なら finding 0", probe(all_written) == [])

    unlogged = f"## §1 規則\n\n{others}\n\n## §17 仕様本文がまだ無い SR の一覧\n\n"
    f_unlogged = probe(unlogged)
    check("T6 規則行が無く台帳にも無いと sr-unlogged を出す",
          any(f["check"] == "sr-unlogged" and sample in f["message"] for f in f_unlogged))

    stale = all_written + f"| {sample} | {sample_vids} | 行き先 |\n"
    check("T7 規則行があるのに台帳へ残っていると sr-ledger-stale を出す",
          any(f["check"] == "sr-ledger-stale" for f in probe(stale)))

    wrong_vids = f"## §1 規則\n\n{others}\n\n## §17 仕様本文がまだ無い SR の一覧\n\n" \
                 f"| {sample} | V-999 | 行き先 |\n"
    check("T8 台帳行の V-ID が実際と違うと sr-ledger-vids を出す",
          any(f["check"] == "sr-ledger-vids" for f in probe(wrong_vids)))

    no_section = f"## §1 規則\n\n| SR-ID | 規則 |\n|---|---|\n| {sample} | 規則 |\n{others}\n"
    check("T9 §17 が無いと sr-ledger-section-missing で倒れる (fail-closed)",
          any(f["check"] == "sr-ledger-section-missing" for f in probe(no_section)))

    orphan = all_written + "| SR-9-99 | V-999 | 行き先 |\n"
    check("T10 どの検査も名指ししない SR が台帳にあると sr-ledger-orphan を出す",
          any(f["check"] == "sr-ledger-orphan" for f in probe(orphan)))

    # T12-T14: 台帳の件数の主張。実データの数字を 1 ずらして赤くなること、
    #          件数を書いていない台帳を素通ししないこと。
    #
    # 実データの §17 を差し替えるのに `_split_ledger` の body を使う。
    # 当初は live を "## §17" の位置で前方だけ切り出していたが、これは **§17 が最後の節である**
    # ことを暗黙に前提しており、後ろに節を足すとその節ごと落ちる。実際 §18 を §17 の
    # 後ろへ置いた時点で T12 が FAIL した (2026-08-14・exec-docs が踏んだ)。
    # 落ちた節の中の規則行が消えるので欠落が増え、合成側の台帳と件数が食い違う。
    # **文書の節順を検査器の都合で縛るのは筋が違う** ので、検査器の側から前提を外した。
    # body は §17 の前後を連結したものなので、どこに §17 があっても同じ結果になる。
    ledger_only = f"## §17 仕様本文がまだ無い SR の一覧\n\n" \
                  f"2026-08-14 時点で {len(gap)} 種 / 参照している V-ID は " \
                  f"{sum(len(v) for v in gap.values())} 件。\n\n" \
                  + "".join(f"| {sr} | {'/'.join(v)} | 行き先 |\n" for sr, v in gap.items())
    check("T12 台帳の件数が実測と合っていれば count の finding は出ない",
          not any(f["check"].startswith("sr-ledger-count")
                  for f in run_checks(root, registry=body + "\n" + ledger_only)))

    shifted = ledger_only.replace(f"{len(gap)} 種", f"{len(gap) + 1} 種", 1)
    check("T13 台帳の種類数を 1 ずらすと sr-ledger-count を出す",
          any(f["check"] == "sr-ledger-count"
              for f in run_checks(root, registry=body + "\n" + shifted)))

    silent = "## §17 仕様本文がまだ無い SR の一覧\n\n件数を書かない台帳。\n\n" \
             + "".join(f"| {sr} | {'/'.join(v)} | 行き先 |\n" for sr, v in gap.items())
    check("T14 件数を書いていない台帳は sr-ledger-count-unstated を出す",
          any(f["check"] == "sr-ledger-count-unstated"
              for f in run_checks(root, registry=body + "\n" + silent)))

    # T11: 実測器が 0 を返さない (0 は「空集合」という別の主張なので None へ倒す)。
    check("T11 欠落が 0 種のとき実測器は None を返す (0 を返さない)",
          count_missing_sr(root) is None or count_missing_sr(root) > 0)

    return ok, log


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lint-sr-ledger-parity",
        description="検査 ID の sr: ↔ spec-registry の規則行 の突合ゲート (fail-closed)",
    )
    p.add_argument("--root", default=None, help="plugin root (既定=本スクリプトの1つ上)")
    p.add_argument("--json", action="store_true", help="(既定で JSON 出力・互換用フラグ)")
    p.add_argument("--self-test", action="store_true", help="検出器の自己検証のみ行う")
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    root = _plugin_root(args.root)
    for rel in (_SPEC_REGISTRY, _VALIDATE_STRUCTURE):
        if not (root / rel).is_file():
            sys.stderr.write(f"error: {rel} not found under {root}\n")
            return 2
    if args.self_test:
        ok, log = _self_test(root)
        sys.stdout.write(json.dumps(
            {"passed": ok, "count": len(log), "findings": log}, ensure_ascii=False, indent=2) + "\n")
        return 0 if ok else 2
    findings = run_checks(root)
    result = {"passed": len(findings) == 0, "count": len(findings), "findings": findings}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
