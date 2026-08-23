"""図解型の語彙が 6 か所で一致していることの照合 (cross-component parity)。

図解型 (flow / compare / …) の集合は、実装・契約・schema・policy の 6 か所が
それぞれ独立に保持している。各所は自分の中では閉じているため、片側だけが語を
増減しても各コンポーネントのテストは全件 PASS のまま通る。

2026-08-23 に実際に起きた形がこれである。C21 の写像だけが日本語ラベルの英訳
(`comparison` / `binary-contrast`) を id として持ち、C14 の id (`compare` /
`versus`) と食い違ったまま両側のテストが緑だった。schema はその 2 語を含む
9 語を受理していたため、schema を通った構成データが C21 で exit2 になる経路が
開いていた。

この 1 本は「どの語が正しいか」を判定しない。6 か所が同じ集合を指していること
だけを見る。語を増やすときは 6 か所を同時に直す必要がある、という規律の実行点。
"""

import importlib.util
import json
import unittest

import _harness as H


def _load_module(path, name):
    """ファイル名にハイフンを含む script を module として読む。"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema() -> dict:
    return json.loads(
        (H.PLUGIN_ROOT / "schemas" / "handout-config.schema.json").read_text(encoding="utf-8")
    )


def _visual_policy() -> dict:
    return json.loads(
        (H.PLUGIN_ROOT / "config" / "handout-visual-policy.json").read_text(encoding="utf-8")
    )


class PatternVocabularyParityTest(unittest.TestCase):
    """図解型の語彙を持つ 6 か所が同一集合であること。"""

    def holders(self) -> dict:
        """語彙集合 -> それを保持している場所の名前。"""
        c14 = _load_module(H.SCRIPTS_DIR / "render-diagram-svg.py", "hb_render_diagram_svg")
        c21 = _load_module(H.SCRIPTS_DIR / "srg-image-bridge.py", "hb_srg_image_bridge")
        schema = _schema()
        image_plan = schema["$defs"]["image_plan"]["properties"]["diagram_pattern"]["enum"]
        diagram = schema["$defs"]["diagram"]["properties"]["pattern"]["enum"]
        policy = _visual_policy()["diagram_patterns_by_intent"]["map"]
        return {
            "C14 render-diagram-svg.py#PATTERNS": frozenset(c14.PATTERNS),
            "C21 srg-image-bridge.py#PATTERN_TO_FAMILY": frozenset(c21.PATTERN_TO_FAMILY),
            "C21 script-brief-C21.json#selection_rule.map": frozenset(
                H.brief()["image_style_families"]["selection_rule"]["map"]
            ),
            "schema#$defs.diagram.properties.pattern": frozenset(diagram),
            "schema#$defs.image_plan.properties.diagram_pattern": frozenset(image_plan),
            "config/handout-visual-policy.json#diagram_patterns_by_intent": frozenset(
                entry["pattern"] for entry in policy
            ),
        }

    def test_all_holders_declare_the_same_pattern_set(self):
        holders = self.holders()
        baseline_name = "C14 render-diagram-svg.py#PATTERNS"
        baseline = holders[baseline_name]
        for name, values in holders.items():
            if name == baseline_name:
                continue
            self.assertEqual(
                values,
                baseline,
                "\n".join(
                    [
                        "図解型の語彙が {} と食い違っている: {}".format(baseline_name, name),
                        "  {} にだけある: {}".format(name, sorted(values - baseline) or "なし"),
                        "  {} にだけある: {}".format(baseline_name, sorted(baseline - values) or "なし"),
                        "語を増減するときは 6 か所を同時に直す。片側だけ直すと各所のテストは",
                        "全件 PASS のまま、schema を通った値が実行時に exit2 になる。",
                    ]
                ),
            )

    def test_the_style_family_map_is_total_over_the_vocabulary(self):
        """C21 の写像は語彙全体に対して全域である (fallback を持たないため)。"""
        c14 = _load_module(H.SCRIPTS_DIR / "render-diagram-svg.py", "hb_render_diagram_svg")
        c21 = _load_module(H.SCRIPTS_DIR / "srg-image-bridge.py", "hb_srg_image_bridge")
        families = set(H.brief()["image_style_families"]["families"])
        for pattern in c14.PATTERNS:
            self.assertIn(
                pattern,
                c21.PATTERN_TO_FAMILY,
                "図解型 {} に対応する画風系統が無い。C21 は fallback を持たないため exit2 になる".format(pattern),
            )
            self.assertIn(
                c21.PATTERN_TO_FAMILY[pattern],
                families,
                "図解型 {} の写像先 {} が brief の families に無い".format(
                    pattern, c21.PATTERN_TO_FAMILY[pattern]
                ),
            )


if __name__ == "__main__":
    unittest.main()
