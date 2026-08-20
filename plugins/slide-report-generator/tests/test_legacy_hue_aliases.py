"""色相名の一時定義が「一時」で終わることを機械に保証させる。

`--sakura-pink` / `--wave-blue` / `--wave-aqua` / `--autumn-yellow` は、
規範 (符号系) が決まるまでのあいだ `references/theme-style.md` の生成区間が
定義している。参照が多数あり、定義が無いせいで宣言ごと無効になっていた
ための応急処置で、色相を配色へ戻したのではない。

当初は 6 名だった。`--spring-violet` は `--wave-blue` と、`--fuji-gray` は
この補助濃度と**同じ値を指す別名**で、区別を主張しながら区別を持っていなかった
ため、名前ごと落として参照側を寄せた。ここが 4 名なのはその結果で、
「6 名のうち 2 名を消し残した」状態ではない (下の部分削除テストを参照)。

補助濃度の正本は `--fg-muted` である (`--fg-dim` ではない)。値を代入している
のは style-builder.cjs / render-report.js / html-scaffold.js の
`--fg-muted: <inkMuted>` で、`--fg-dim: var(--fg-muted)` はそこから派生した
後方互換の別名にすぎない。**別名のほうへ寄せると、後で別名を消せなくなる**
(消した瞬間に寄せ先が消えるため)。図解/report 経路の参照はすべて代入先の
名前へ寄せてあり、残る `--fg-dim` は別名の定義 3 行と旧 slide 経路だけである。

区別は最終的に (濃度 x 形) の系列へ移り、参照側は 1 名を 1 色値へ写すのを
やめて `seriesStyle()` を呼ぶ。その時点でこの 6 名は不要になる。

一時が一時で終わるかどうかを人の記憶に任せると、応急処置は必ず残る。
そこで**引き金を機械にする**。系列 API が入った瞬間このテストが落ちるので、
移行の完了と互換名の削除が同じ 1 コミットの中でしか成立しなくなる。

このファイルは「消すべきものが消えたか」だけを見る。値が正しいかどうかは
`build-slide-skeleton-css.py --check` の担当。
"""
from __future__ import annotations

import re
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_THEME_DOC = _PLUGIN_ROOT / "references" / "theme-style.md"
_SERIES_SRC = _PLUGIN_ROOT / "vendor" / "scripts" / "svg-kit.cjs"

_HUES = (
    "--sakura-pink", "--wave-blue", "--wave-aqua", "--autumn-yellow",
)

_BEGIN = "<!-- BEGIN GENERATED: palette (scripts/build-slide-skeleton-css.py) -->"
_END = "<!-- END GENERATED: palette -->"


def _generated_region() -> str:
    src = _THEME_DOC.read_text(encoding="utf-8")
    assert src.count(_BEGIN) == 1 and src.count(_END) == 1, (
        "theme-style.md に生成区間の標識が 1 組ちょうど無い。"
        " 標識を失うと生成器が差し替え先を見失う (fail-closed)"
    )
    return src.split(_BEGIN, 1)[1].split(_END, 1)[0]


def _hues_in(region: str) -> set[str]:
    """区間が `:root` で定義している色相名。参照 (`var(--x, ...)`) は数えない。"""
    return {h for h in _HUES if re.search(rf"^\s*{re.escape(h)}\s*:", region, flags=re.M)}


def _defined_hues() -> set[str]:
    return _hues_in(_generated_region())


def _has_series_api(src: str) -> bool:
    """系列 API が実装に入ったか。呼び出し口が 1 つでもあれば入ったとみなす。"""
    return "seriesStyle(" in src


def _series_api_exists() -> bool:
    if not _SERIES_SRC.is_file():
        return False
    return _has_series_api(_SERIES_SRC.read_text(encoding="utf-8"))


def test_互換名と系列APIは共存できない():
    """これが落ちたら互換名を消す。移行が終わった合図なので、直し方は削除。

    直し方: `scripts/build-slide-skeleton-css.py` の `_LEGACY_HUES` を空にして
    再生成し、`read_legacy_hues()` ごと落とす。参照側 (1046 箇所) の
    `var(--wave-blue, ...)` も同時に `seriesStyle()` 由来の値へ移す。
    """
    defined = _defined_hues()
    if not defined:
        return  # 既に削除済み。ここが恒常状態。
    assert not _series_api_exists(), (
        "系列 API (seriesStyle) が入ったのに色相名の一時定義が残っている: "
        + ", ".join(sorted(defined))
        + "。一時定義は符号系への移行と同時に削除する。"
        " 残すと『色で分ける』経路と『系列で分ける』経路の 2 本が同時に生き、"
        "どちらが正本か判定できなくなる。"
    )


def test_一時定義は全名そろっているか空である():
    """中途半端に一部だけ消すと、消えた側だけ宣言ごと無効に戻る。

    `_HUES` は同じ理由で同時に入り、同じ理由で同時に消える。部分削除は
    「対応済みに見えるが一部の色が落ちている」という最も気づきにくい壊れ方。

    名前そのものを廃する (同値の別名を 1 本へ寄せる) 場合は、参照側を寄せた
    うえで `_HUES` からも落とす。そのとき集合は縮むが、縮んだ集合の中では
    「全部あるか空」が保たれるので、この判定は効き続ける。
    """
    defined = _defined_hues()
    assert defined in (set(), set(_HUES)), (
        "色相名の一時定義が中途半端に残っている。定義済み: "
        + ", ".join(sorted(defined))
        + " / 欠け: "
        + ", ".join(sorted(set(_HUES) - defined))
    )


def test_一時定義の値は書き写されていない():
    """値は svg-kit.cjs の fallback 由来。区間に hex を直書きしていないこと。

    手で hex を書くと、正本が動いた日に静かにズレる。生成器はパレット変数
    (`var(--tone-3)` 等) を指す形で出すので、色相名の行に `#` は出ない。
    """
    region = _generated_region()
    for h in _defined_hues():
        m = re.search(rf"^\s*{re.escape(h)}\s*:\s*([^;]+);", region, flags=re.M)
        assert m, f"{h} の定義行を読めない"
        value = m.group(1).strip()
        assert value.startswith("var("), (
            f"{h} に hex が直書きされている ({value})。"
            " 値はパレット変数を指す形で生成する"
        )


def test_検出能_引き金が実際に引けること():
    """現物が緑であることと、落ちるべきときに落ちることは別。

    このテストが無いと、判定を空振りさせる書き換え (正規表現の取りこぼし、
    参照と定義の取り違え) が入っても全部緑のまま通る。合成入力で
    「引き金が引けること」を固定する。
    """
    # 定義の検出: `:root` の定義行だけを拾い、`var()` 参照は拾わない
    assert _hues_in("  --wave-blue: var(--tone-3);") == {"--wave-blue"}
    assert _hues_in("  fill: var(--wave-blue, #4B6681);") == set()
    assert _hues_in("") == set()
    assert len(_hues_in("\n".join(f"  {h}: var(--ink);" for h in _HUES))) == len(_HUES)

    # 系列 API の検出: 呼び出し口の有無で判定し、語の一部には反応しない
    assert _has_series_api("const s = seriesStyle(i);")
    assert not _has_series_api("const SERIES = [];")
    assert not _has_series_api("// seriesStyle をいずれ足す")  # 呼び出し括弧が無い


def test_値の出所が実在する():
    """svg-kit.cjs 側に `_HUES` 全名の fallback が残っていること。

    生成器はここから値を作るので、出所が消えていれば生成もできない。
    このテストが落ちるのは「移行が始まったが互換名を消していない」場合で、
    上の共存テストと同じ結論 (削除) になる。
    """
    if not _defined_hues():
        return
    src = _SERIES_SRC.read_text(encoding="utf-8")
    missing = [
        h for h in _HUES
        if not re.search(rf"var\(\s*{re.escape(h)}\s*,\s*#[0-9A-Fa-f]{{6}}\s*\)", src)
    ]
    assert not missing, (
        "svg-kit.cjs に fallback が無い色相名がある: " + ", ".join(missing)
        + "。一時定義の値の出所が消えているので、互換名も同時に削除する"
    )
