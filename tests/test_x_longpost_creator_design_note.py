"""x-longpost-creator 設計ノートの可変な主張が実装とずれないことを保証する。

設計ノートは「なぜその形にしたか」を残す散文だが、その論拠として skill の一覧・
script 名・検査 ID・配色といった実装側の事実を引用している。引用は書いた時点では
正しくても、実装が動けば静かに古くなる。ここでは散文のうち **実装から導出できる
主張だけ** を突き合わせ、乖離を落として気づけるようにする。

「なぜそうしたか」の判断そのものは機械検証の対象にしない。検証できるのは
「その判断が指している対象が今も存在し、今もそう呼ばれているか」までである。
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "x-longpost-creator"
DOC = ROOT / "doc" / "x-longpost-creator-設計ノート.md"

# 設計ノートの effect 列は散文の語で、artifact-delivery.json の enum 値とは
# 語彙が 1 箇所だけ異なる。成果物を作らない参照 skill を散文では reference と
# 呼び、機械宣言では none と書く。対応を明示して両方を動かせなくする。
EFFECT_ALIAS = {"reference": "none"}


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def _delivery() -> dict:
    return json.loads((PLUGIN / "artifact-delivery.json").read_text(encoding="utf-8"))


def _owned_skill_effects() -> dict[str, str]:
    """本 plugin が所有する skill の entrypoint effect を返す。

    run-skill-feedback は全 plugin へ同一内容で配備される共通 skill で、正本は
    harness-creator が所有する。本 plugin の設計判断ではないので設計ノートの
    表にも載らない。ここでも除外して、所有する 5 skill だけを対象にする。
    """
    effects = {}
    for entry in _delivery()["entrypoints"]:
        name = Path(entry["path"]).parent.name
        if name == "run-skill-feedback":
            continue
        effects[name] = entry["effect"]
    return effects


def test_skill_table_matches_artifact_delivery() -> None:
    text = _doc_text()
    owned = _owned_skill_effects()

    # 表に並ぶ行を読み取る。行数を直書きせず表から導出することで、skill を
    # 増減したのに表を直し忘れた場合にここで落ちる。
    rows = dict(
        re.findall(r"^\| `(run-x-[a-z-]+|ref-x-[a-z-]+)` \| .+? \| ([a-z-]+) \|$", text, re.M)
    )

    assert rows, "設計ノートの skill 表が読み取れなかった (表の書式が変わった可能性)"
    assert set(rows) == set(owned), (
        "設計ノートの skill 表と artifact-delivery.json の所有 entrypoint がずれている。\n"
        f"  ノート側: {sorted(rows)}\n  宣言側:   {sorted(owned)}"
    )
    for name, doc_effect in rows.items():
        assert EFFECT_ALIAS.get(doc_effect, doc_effect) == owned[name], (
            f"{name} の effect が食い違う: ノート '{doc_effect}' / 宣言 '{owned[name]}'"
        )
    # 所有していない共通 skill を自分の設計判断として書いていないことも見る。
    assert "run-skill-feedback" not in text


def test_referenced_scripts_all_exist() -> None:
    text = _doc_text()
    scripts = set(re.findall(r"`([a-z0-9_-]+\.(?:js|mjs|py))`", text))
    assert scripts, "設計ノートが script を 1 つも参照していない (書式が変わった可能性)"

    missing = [
        s for s in sorted(scripts)
        if not (PLUGIN / "scripts" / s).is_file() and not (ROOT / "scripts" / s).is_file()
    ]
    assert not missing, f"設計ノートが実在しない script を参照している: {missing}"


def test_thumbnail_lint_ids_and_palette_exist_in_canon() -> None:
    text = _doc_text()
    linter = (PLUGIN / "scripts" / "lint-thumbnail-prompt.js").read_text(encoding="utf-8")
    canon = (
        PLUGIN / "skills" / "run-x-visual-generate" / "references" / "thumbnail-style-canon.md"
    ).read_text(encoding="utf-8")

    # 設計ノートが名指しする検査 ID が linter に実在すること。TL-11 / TL-12 は
    # 「課金前に止める」という論拠そのものなので、消えたら論拠が崩れる。
    for tl in sorted(set(re.findall(r"TL-\d{2}", text))):
        assert tl in linter, f"設計ノートが参照する {tl} が lint-thumbnail-prompt.js に無い"

    # ノートが役割つきで挙げる色が画風の正本に実在すること。色数そのものは
    # 主張しない (canon は白など役割の無い色も持ちうる)。
    for color in sorted(set(re.findall(r"#[0-9A-F]{6}", text))):
        assert color in canon, f"設計ノートが挙げる {color} が thumbnail-style-canon.md に無い"


def test_thumbnail_dimensions_are_derived_from_visual_spec() -> None:
    """ノートが挙げるサムネイル 2 枚の寸法を visual-spec.json から導出して照合する。

    期待値をこのテストに直書きしない。直書きすると仕様を変えたとき「実装とテストを
    一緒に直す」で緑になり、doc だけが古いまま取り残される。正本から値を組み立てて
    その文字列が散文に現れることを見れば、doc を直さない限り落ちる。
    """
    text = _doc_text()
    spec = json.loads(
        (PLUGIN / "skills" / "run-x-visual-generate" / "references" / "visual-spec.json")
        .read_text(encoding="utf-8")
    )
    kinds = spec["kinds"]

    # X 用は比率で、note 用は実寸で語られる。媒体ごとに「何が効くか」が違うため
    # ノートの表現も違っており、その違いごと正本から導出する。
    x_ratio = kinds["x-thumb"]["ratio"]["label"]
    note = kinds["note-thumb"]["delivery"]
    assert f"X 用 {x_ratio}" in text, (
        f"設計ノートの X サムネイル比率が visual-spec.json ({x_ratio}) とずれている"
    )
    assert f"note 用 {note['width']}x{note['height']}" in text, (
        "設計ノートの note サムネイル寸法が visual-spec.json "
        f"({note['width']}x{note['height']}) とずれている"
    )
