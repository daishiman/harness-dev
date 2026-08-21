"""lint-sr-ledger-parity.py のテスト。

(1) 回帰ガード: 現行実体で finding ゼロ (規則行の無い SR は全て §17 の台帳に載っている)。
(2) 検出能: 実データを 1 箇所ずつ壊して 4 種の finding が出ること (合成でなく実体を壊す)。
(3) 取り違えの固定: §17 の台帳行を「規則本文がある」と数えない。

(3) は実際に起きた誤りの回帰ガードである。spec-registry を節で分けずに走査すると、
台帳へ載せた SR-ID がその台帳行によって「本文がある」と数えられ、欠落が 7 種から
0 種へ減ったように見えた。**台帳へ書く行為が台帳の対象を消す**という自己参照で、
これを許すと「§17 へ書けば緑」になる。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _PLUGIN_ROOT / "scripts" / "lint-sr-ledger-parity.py"
_REGISTRY = _PLUGIN_ROOT / "references" / "spec-registry.md"


def _load():
    spec = importlib.util.spec_from_file_location("lint_sr_ledger_parity_mod", _SCRIPT)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mod = _load()


def _live() -> str:
    return _REGISTRY.read_text(encoding="utf-8")


def _checks(findings: list[dict]) -> set[str]:
    return {f["check"] for f in findings}


# --- (1) 回帰ガード -----------------------------------------------------------

def test_current_state_has_no_findings() -> None:
    """規則行の無い SR は全て §17 に載っており、載っている SR は全て本文が無い。

    ここが赤くなる直し方は 2 つある。**規則を書いて台帳から消す**か、
    **書けない理由と行き先を台帳へ足す**か。台帳へ足すだけで緑にできるのは
    「まだ書けていない」と自認した場合だけで、その行は残り続けて目に入る。
    """
    assert mod.run_checks(_PLUGIN_ROOT) == []


def test_cli_self_test_passes() -> None:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--self-test"],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["passed"] is True


def test_cli_exit_code_is_zero_when_clean() -> None:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT)], capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["count"] == 0


# --- (2) 検出能: 実データを 1 箇所ずつ壊す ------------------------------------

def _sample_sr() -> tuple[str, list[str]]:
    """台帳に載っている SR を 1 つ選び、(SR-ID, 参照 V-ID) を返す。"""
    gap = mod.missing_sr(_PLUGIN_ROOT)
    assert gap, "台帳が空だと壊す対象が無い。この前提が崩れたらテストを書き直す"
    sr = sorted(gap)[-1]
    return sr, gap[sr]


def test_dropping_a_ledger_row_is_detected() -> None:
    sr, _ = _sample_sr()
    broken = "\n".join(l for l in _live().splitlines() if not l.startswith(f"| {sr} "))
    found = mod.run_checks(_PLUGIN_ROOT, registry=broken)
    assert "sr-unlogged" in _checks(found)
    assert any(sr in f["message"] for f in found)


def test_shifting_a_ledger_vid_is_detected() -> None:
    """台帳の V-ID 列を 1 件ずらす。件数でなく値がずれる形なので、数を数えても出ない。"""
    sr, vids = _sample_sr()
    other = "V-999"
    broken = _live().replace(f"| {sr} | {vids[0]}", f"| {sr} | {other}", 1)
    assert broken != _live(), "台帳行の書式が変わった。置換が空振りしている"
    assert "sr-ledger-vids" in _checks(mod.run_checks(_PLUGIN_ROOT, registry=broken))


def test_writing_the_rule_without_clearing_the_ledger_is_detected() -> None:
    sr, _ = _sample_sr()
    broken = _live().replace("## §17", f"| {sr} | 規則を書いた |\n\n## §17", 1)
    assert "sr-ledger-stale" in _checks(mod.run_checks(_PLUGIN_ROOT, registry=broken))


def test_renumbering_the_ledger_section_fails_closed() -> None:
    """§17 を見失ったら緑にならないこと。全件 unlogged にするのでなく、倒れる。

    番号が変わる (節が増えて §18 へ動く) と検査は台帳を見つけられない。そのとき
    「台帳が空」と読むと、載っていた 7 件が一斉に sr-unlogged になり、直し方を
    間違える方向 (台帳へ書き直す) へ人を送る。見つからないことを別の名前で出す。

    見出しの**文言**が変わっても追随する (`§17` の直後で境界を取る) のは意図どおりで、
    追随できないのは**番号**が変わったときだけ。
    """
    broken = _live().replace("## §17", "## §18", 1)
    assert "sr-ledger-section-missing" in _checks(
        mod.run_checks(_PLUGIN_ROOT, registry=broken))

    renamed = _live().replace("## §17 仕様本文がまだ無い SR の一覧", "## §17 欠落台帳", 1)
    assert mod.run_checks(_PLUGIN_ROOT, registry=renamed) == [], (
        "見出しの文言変更まで倒れると、台帳の書き直しができなくなる"
    )


def test_unreferenced_sr_in_ledger_is_detected() -> None:
    """台帳へ、どの検査も名指ししていない SR を足す。

    追加位置は既存の台帳行の直後にする。ファイル末尾へ足すと §17 の外 (改訂方針の節)
    に入り、規則行として読まれて finding が出ない。**節の中か外かで意味が変わる**ので、
    位置を実データの行に相対で決める。
    """
    sr, _ = _sample_sr()
    anchor = next(l for l in _live().splitlines() if l.startswith(f"| {sr} "))
    broken = _live().replace(anchor, anchor + "\n| SR-9-99 | V-999 | 行き先 |", 1)
    assert "sr-ledger-orphan" in _checks(mod.run_checks(_PLUGIN_ROOT, registry=broken))


def test_ledger_position_does_not_change_the_verdict() -> None:
    """§17 が文書のどこにあっても結果が変わらないこと。

    検査器が「§17 は最後の節」を前提にしていた時期があり、§17 の**後ろ**に規則節
    (§18) を足した瞬間に self-test が倒れた。前方だけを切り出す合成をしていたので、
    後ろの節ごと落ちて規則行が消え、欠落が増えていた。**文書の節順を検査器の都合で
    縛るのは筋が違う**ので、前提の側を外した。ここはその回帰ガード。
    """
    body, ledger = mod._split_ledger(_live())
    assert ledger.strip(), "§17 が空。位置を動かす対象が無い"
    assert mod.run_checks(_PLUGIN_ROOT, registry=body + "\n" + ledger) == []
    assert mod.run_checks(_PLUGIN_ROOT, registry=ledger + "\n" + body) == []


def test_shifting_the_declared_count_is_detected() -> None:
    """台帳の散文が名乗る「N 種」を 1 ずらす。表を直さずに数字だけ書き換えた形。

    行を消し忘れたのでなく**数え直さずに数字を触った**ときに出る。表と散文の
    どちらが正しいかを lint は決めない (実測が正しい) が、食い違いは必ず出す。
    """
    gap = mod.missing_sr(_PLUGIN_ROOT)
    broken = _live().replace(f"**{len(gap)} 種", f"**{len(gap) + 1} 種", 1)
    assert broken != _live(), "台帳の数詞の書式が変わった。置換が空振りしている"
    assert "sr-ledger-count" in _checks(mod.run_checks(_PLUGIN_ROOT, registry=broken))


def test_dropping_the_declared_count_is_detected() -> None:
    """散文から件数を消しても素通りしないこと。

    数字を書かなければ食い違わない、という逃げ道を塞ぐ。件数の宣言は台帳の
    「今いくつ残っているか」を人が読む唯一の場所なので、無い状態を許すと
    表を数えない限り増減が見えなくなる。
    """
    gap = mod.missing_sr(_PLUGIN_ROOT)
    line = next(l for l in _live().splitlines() if f"**{len(gap)} 種" in l)
    broken = _live().replace(line, "本文が書かれた SR はこの表から消える。", 1)
    assert "sr-ledger-count-unstated" in _checks(
        mod.run_checks(_PLUGIN_ROOT, registry=broken))


# --- (3) 取り違えの固定 -------------------------------------------------------

def test_ledger_rows_do_not_count_as_rule_bodies() -> None:
    """§17 を含めて数えると欠落が消えること。この差が無くなったら節分割が壊れている。"""
    live = _live()
    refs = mod.sr_references(_PLUGIN_ROOT)
    naive_have = set(mod._ROW_RE.findall(live))
    naive_missing = {sr for sr in refs if sr not in naive_have}
    split_missing = set(mod.missing_sr(_PLUGIN_ROOT))

    assert split_missing, "規則行の無い SR が 0 種ならこのテストは前提を失う"
    assert split_missing - naive_missing, (
        "§17 を含めて数えても欠落が同じなら、台帳行が規則行として数えられていないか、"
        "そもそも台帳が空。どちらなのか確かめてからこのテストを直すこと"
    )


def test_measurers_match_missing_set() -> None:
    """散文の数詞を縛る実測器が、この lint と同じ集合を数えていること。"""
    gap = mod.missing_sr(_PLUGIN_ROOT)
    assert mod.count_missing_sr(_PLUGIN_ROOT) == len(gap)
    assert mod.count_missing_sr_vids(_PLUGIN_ROOT) == sum(len(v) for v in gap.values())


def test_sr_references_come_only_from_the_validator() -> None:
    """SR-ID の出所は validate-structure.js の V_DEFINITIONS だけであること。

    spec-registry 側から集めると、規則はあるが検査が無い SR まで混ざり、
    「検査が名指ししている SR」という母集団が変わる。
    """
    refs = mod.sr_references(_PLUGIN_ROOT)
    assert len(refs) > 10
    for sr, vids in refs.items():
        assert sr.startswith("SR-"), sr
        assert vids and all(v.startswith("V-") for v in vids), (sr, vids)
