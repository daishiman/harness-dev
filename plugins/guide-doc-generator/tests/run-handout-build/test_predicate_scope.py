"""全 AC 述語が「1 箇所だけの違反注入」で発火することを機械的に固定する。

背景 (P05-x-17):
`contract_lib.py` には本文全体への部分文字列一致で判定する述語があり、同じ語が
本文の別箇所にも現れると、宣言を消しても違反状態を作れない (偽緑)。
`reject_cases.py` の注入は単一 (old, new) ペアであり、`test_contract_checker.py`
の `_materialize` は `text.count(old) == 1` を assert しているため、
「1 箇所だけ潰して違反状態にできるか」は述語ごとに検証可能な性質である。

本モジュールは `contract_lib.check_skill` が持つ全 Violation 発生箇所について、
受入 fixture へ単一箇所の変更 (または単一ファイルの削除) を入れると対応する契約 id
が発火することを網羅的に確認する。確認手順は `test_contract_checker._materialize`
と同一 (ACCEPT_ROOT 全体を temp へ copytree し SKILL.md だけ差し替えて
`check_skill(skill_dir)` を呼ぶ) である。方針は PREDICATE-SCOPE-POLICY.md を参照。
"""

import re
import shutil
import sys
import tempfile
import unittest
from collections import Counter, namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402

HERE = Path(__file__).resolve().parent
ACCEPT_ROOT = HERE / "fixtures" / "accept"
ACCEPT_SKILL_REL = Path("skills") / "run-handout-build"
ACCEPT_TEXT = (ACCEPT_ROOT / ACCEPT_SKILL_REL / "SKILL.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 受入 fixture から一意な断片を取り出す補助 (一意性はここで固定する)
# --------------------------------------------------------------------------


def _uline(needle: str) -> str:
    """needle を含む行が受入 fixture に唯一であることを確かめ、その行を返す。"""
    hits = [l for l in ACCEPT_TEXT.splitlines() if needle in l]
    if len(hits) != 1:
        raise AssertionError(f"受入 fixture に {needle!r} を含む行が {len(hits)} 本ある")
    return hits[0] + "\n"


def _field_block(field: str) -> str:
    """hearing_required_items_r21 の 1 項目ぶんのブロックを返す。"""
    lines = ACCEPT_TEXT.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if line.rstrip("\n") == f"    - field: {field}":
            if start is not None:
                raise AssertionError(f"field {field} が複数ある")
            start = i
    if start is None:
        raise AssertionError(f"field {field} が受入 fixture に無い")
    end = start + 1
    while end < len(lines) and lines[end].startswith("      "):
        end += 1
    return "".join(lines[start:end])


# --------------------------------------------------------------------------
# 変異の定義: sub = SKILL.md の 1 箇所置換 / delfile = 参照ファイル 1 個の削除
# --------------------------------------------------------------------------

M = namedtuple("M", ["name", "ac_id", "kind", "a", "b"])


def _sub(name, ac_id, old, new):
    return M(name, ac_id, "sub", old, new)


def _delfile(name, ac_id, relpath):
    return M(name, ac_id, "delfile", relpath, None)


def _mutations():
    out = []
    add = out.append

    # AC-C01-1: SKILL.md 実在
    add(_delfile("skill-md-missing", "AC-C01-1", ACCEPT_SKILL_REL / "SKILL.md"))

    # AC-C01-2: frontmatter の有無 / identity 4 キー
    add(_sub("frontmatter-removed", "AC-C01-2", "---\nname: run-handout-build", "name: run-handout-build"))
    add(_sub("identity-name", "AC-C01-2", "\nname: run-handout-build\n", "\nname: build-handout\n"))
    add(_sub("identity-prefix", "AC-C01-2", "prefix: run\n", "prefix: assign\n"))
    add(_sub("identity-kind", "AC-C01-2", "kind: run\n", "kind: ref\n"))
    add(_sub("identity-hierarchy", "AC-C01-2", "hierarchy: L1\n", "hierarchy: L2\n"))

    # AC-C01-3: description の 3 述語
    desc = _uline("description: レクチャー資料")
    add(_sub("description-empty", "AC-C01-3", desc, 'description: ""\n'))
    add(_sub("description-not-trigger-form", "AC-C01-3", desc, "description: handout を生成する。\n"))
    add(_sub("description-without-vocabulary", "AC-C01-3", desc, "description: 成果物を作りたいときに使う。\n"))

    # AC-C01-4: responsibilities の一致 / prompt_required
    add(_sub(
        "extra-responsibility",
        "AC-C01-4",
        "  - id: R4-verify\n    prompt_required: true",
        "  - id: R5-selfreview\n    prompt_required: true\n  - id: R4-verify\n    prompt_required: true",
    ))
    add(_sub(
        "prompt-required-false",
        "AC-C01-4",
        "  - id: R2-design\n    prompt_required: true",
        "  - id: R2-design\n    prompt_required: false",
    ))

    # AC-C01-5: responsibility_refs の宣言と実在
    for rid in contract_lib.REQUIRED_RESPONSIBILITIES:
        add(_sub(f"responsibility-ref-dropped-{rid}", "AC-C01-5", f"  - prompts/{rid}.md\n", ""))
        add(_delfile(f"prompt-file-missing-{rid}", "AC-C01-5", ACCEPT_SKILL_REL / "prompts" / f"{rid}.md"))

    # AC-C01-6: combinators / goal_seek
    for comb in contract_lib.REQUIRED_COMBINATORS:
        add(_sub(f"combinator-dropped-{comb}", "AC-C01-6", f"  - {comb}\n", ""))
    add(_sub(
        "goal-seek-block-removed",
        "AC-C01-6",
        "goal_seek:\n  engine: inline\n  fork: subagent\n  max_loops: 5\n",
        "",
    ))
    add(_sub("goal-seek-engine", "AC-C01-6", "  engine: inline\n", "  engine: subagent\n"))
    add(_sub("goal-seek-fork", "AC-C01-6", "  fork: subagent\n", "  fork: inline\n"))
    add(_sub("goal-seek-max-loops", "AC-C01-6", "  max_loops: 5\n", "  max_loops: 3\n"))

    # AC-C01-7: feedback_contract.criteria
    add(_sub("criteria-block-removed", "AC-C01-7", "  criteria:\n", ""))
    for cid, (scope, verify_by) in contract_lib.REQUIRED_CRITERIA.items():
        add(_sub(f"criterion-id-renamed-{cid}", "AC-C01-7", f"    - id: {cid}\n", f"    - id: {cid}X\n"))
        add(_sub(
            f"criterion-loop-scope-{cid}",
            "AC-C01-7",
            f"    - id: {cid}\n      loop_scope: {scope}\n",
            f"    - id: {cid}\n      loop_scope: {'outer' if scope == 'inner' else 'inner'}\n",
        ))
        text_line = _uline(f'      text: "{_criterion_text_head(cid)}')
        add(_sub(f"criterion-text-empty-{cid}", "AC-C01-7", text_line, '      text: ""\n'))
        add(_sub(
            f"criterion-verify-by-{cid}",
            "AC-C01-7",
            text_line + f"      verify_by: {verify_by}\n",
            text_line + f"      verify_by: {'test' if verify_by == 'live-trial' else 'live-trial'}\n",
        ))

    # AC-C01-8: 必須セクション / サブセクション
    for heading in contract_lib.REQUIRED_SECTIONS + contract_lib.REQUIRED_SUBSECTIONS:
        add(_sub(f"heading-renamed-{heading}", "AC-C01-8", heading + "\n", heading + " (改題)\n"))

    # AC-C01-9: Criteria acceptance 節と criteria id への言及
    add(_sub(
        "criteria-acceptance-heading-renamed",
        "AC-C01-9",
        "## Criteria acceptance\n",
        "## 受入基準まとめ\n",
    ))
    for cid in contract_lib.REQUIRED_CRITERIA:
        add(_sub(f"criteria-acceptance-mention-{cid}", "AC-C01-9", f"`criteria:{cid}`", f"`criteria-{cid.lower()}`"))

    # AC-C01-10: deterministic_checks 7 本
    for name in contract_lib.REQUIRED_SCRIPTS:
        add(_sub(f"script-ref-dropped-{name}", "AC-C01-10", f"  - ../../scripts/{name}\n", ""))
        add(_delfile(f"script-file-missing-{name}", "AC-C01-10", Path("scripts") / name))

    # AC-C01-11: ヒアリング 5 項目
    add(_sub("hearing-item-dropped", "AC-C01-11", _field_block("target_tasks"), ""))
    for field in contract_lib.REQUIRED_HEARING_FIELDS:
        block = _field_block(field)
        add(_sub(f"hearing-required-false-{field}", "AC-C01-11", block, block.replace("required: true", "required: false")))
        add(_sub(
            f"hearing-question-empty-{field}",
            "AC-C01-11",
            block,
            re.sub(r'question_ja: ".*"', 'question_ja: ""', block),
        ))

    # AC-C01-12: target_tasks
    tt = _field_block("target_tasks")
    add(_sub("target-tasks-item-dropped", "AC-C01-12", tt, ""))
    add(_sub("target-tasks-min-count", "AC-C01-12", tt, tt.replace("min_count: 1", "min_count: 0")))
    add(_sub(
        "target-tasks-checked-by",
        "AC-C01-12",
        tt,
        tt.replace("E-TARGET-TASKS-EMPTY / ", ""),
    ))

    # AC-C01-13: must_remember / no_need_to_remember の対
    mr = _field_block("must_remember")
    nn = _field_block("no_need_to_remember")
    add(_sub("remember-pair-item-dropped", "AC-C01-13", nn, ""))
    add(_sub("remember-paired-with-mr", "AC-C01-13", mr, mr.replace("paired_with: no_need_to_remember", "paired_with: focus_theme")))
    add(_sub("remember-paired-with-nn", "AC-C01-13", nn, nn.replace("paired_with: must_remember", "paired_with: focus_theme")))
    add(_sub("remember-max-count", "AC-C01-13", mr, mr.replace("max_count: 2", "max_count: 5")))
    add(_sub("remember-checked-by-mr", "AC-C01-13", mr, mr.replace("E-REMEMBER-PAIR / ", "")))
    add(_sub("remember-checked-by-nn", "AC-C01-13", nn, nn.replace("E-REMEMBER-PAIR", "E-REMEMBER-MAX")))

    # AC-C01-14: 提示順
    add(_sub(
        "presentation-order-as-hearing-item",
        "AC-C01-14",
        "    - field: must_remember\n",
        "    - field: presentation_order\n      required: true\n      question_ja: \"どちらにしますか\"\n    - field: must_remember\n",
    ))
    add(_sub(
        "presentation-order-source-dropped",
        "AC-C01-14",
        "C12 の CR-PRESENTATION-ORDER が決定論導出する",
        "C12 が決定論導出する",
    ))
    order_line = _uline("提示順 (demo_first / explain_first) は質問しない")
    add(_sub(
        "presentation-order-asked-in-body",
        "AC-C01-14",
        order_line,
        order_line + "\n- 提示順はデモ先行でよいですか\n",
    ))

    # AC-C01-15: ゲート集約
    add(_sub("gate-entrypoint-dropped", "AC-C01-15", "`/handout-verify` (C09) 経由で実行し", "C09 経由で実行し"))
    add(_sub("gate-agg-source-dropped", "AC-C01-15", "C09 の CR-GATE-AGG が単一正本であり", "C09 が単一正本であり"))
    add(_sub("gate-reimplementation-allowed", "AC-C01-15", "本 skill では再実装も再解釈もしない。", "本 skill はこれを踏まえて実行する。"))
    add(_sub(
        "not-run-folded-into-pass",
        "AC-C01-15",
        "本 skill では再実装も再解釈もしない。",
        "本 skill では再実装も再解釈もしない。ただし not-run は pass とみなす。",
    ))
    gate_line = _uline("4 ゲート (C16 / C17 / C18 / C22) は")
    add(_sub(
        "four-states-enumerated-by-self",
        "AC-C01-15",
        gate_line,
        gate_line + "\n- 結果は pass / fail / error / not-run へ本 skill が分類する。\n",
    ))

    # AC-C01-16: 同梱物の writer 境界
    for flag in ("--place-config", "--assets-src"):
        add(_sub(f"route-flag-dropped-{flag}", "AC-C01-16", f"`{flag}` ", ""))
    add(_sub(
        "config-placed-by-self",
        "AC-C01-16",
        "handout-config.json と assets/ の複製は C19 に行わせる。",
        "handout-config.json と assets/ の複製は C19 に行わせる。\n\n- handout-config.json と assets/ は本 skill が出力先へ配置する。\n",
    ))

    # AC-C01-17: README.md writer 宣言と 5 節 (P05-x-17 で節スコープ化)
    readme_line = _uline("`README.md` を書くのは本 skill の責務で")
    add(_sub("readme-writer-declaration-dropped", "AC-C01-17", readme_line, "README.md の作成も C19 に任せる。\n"))
    for sec in contract_lib.README_SECTIONS:
        add(_sub(
            f"readme-section-dropped-{sec}",
            "AC-C01-17",
            readme_line,
            readme_line.replace(sec, "").replace("・・", "・"),
        ))

    # AC-C01-18: 読みやすさ判定の C03 委譲
    add(_sub("c03-dependency-dropped", "AC-C01-18", "depends_on: [C03, C04,", "depends_on: [C04,"))
    add(_sub(
        "readability-delegation-dropped",
        "AC-C01-18",
        "読みやすさの最終判定は assign-handout-readability-evaluator (C03) へ委譲し",
        "読みやすさの最終判定は C03 へ委譲し",
    ))

    # AC-C01-19: 非対話経路 (P05-x-14 で節スコープ化済み)
    nonint_line = _uline("検証済みの構成データを直接渡された場合はヒアリングを省き")
    add(_sub("non-interactive-path-blocked", "AC-C01-19", nonint_line, "常に対話でヒアリングを行ってから R2 へ進む。\n"))
    add(_sub(
        "non-interactive-input-dropped",
        "AC-C01-19",
        nonint_line,
        "非対話でも ヒアリングを省く 経路を用意する。\n",
    ))

    # AC-C01-20: HTML 組み立ての決定論委譲 (P05-x-17 で宣言行スコープ化)
    llm_line = _uline("HTML の組み立て自体は決定論 script へ委譲し LLM で書かない。")
    add(_sub(
        "html-written-by-llm",
        "AC-C01-20",
        "HTML の組み立て自体は決定論 script へ委譲し LLM で書かない。",
        "HTML は本 skill が決定論的な手順で直接書き起こす。",
    ))
    add(_sub(
        "deterministic-delegation-dropped",
        "AC-C01-20",
        "HTML の組み立て自体は決定論 script へ委譲し LLM で書かない。",
        "HTML の組み立て自体は既存テンプレートの流用で行い LLM で書かない。",
    ))

    # AC-C01-21: Purpose & Output Contract の同梱 4 点と生成レポート 4 要素
    add(_sub("bundled-html-dropped", "AC-C01-21", "`handout.html` (writer C11) / ", ""))
    add(_sub("bundled-config-dropped", "AC-C01-21", "`handout-config.json` と `assets/` (writer C19)", "構成データと `assets/` (writer C19)"))
    add(_sub("bundled-assets-dropped", "AC-C01-21", "`handout-config.json` と `assets/` (writer C19)", "`handout-config.json` と素材 (writer C19)"))
    add(_sub("bundled-readme-dropped", "AC-C01-21", "`README.md` (writer 本 skill) の 4 点。", "説明ファイル (writer 本 skill) の 4 点。"))
    report_line = _uline("- 生成レポート: 適用部品")
    for element in contract_lib.REPORT_ELEMENTS:
        add(_sub(
            f"report-element-dropped-{element}",
            "AC-C01-21",
            report_line,
            report_line.replace(element, "項目").replace("・・", "・"),
        ))

    # AC-C01-22: allowed-tools
    tools_line = _uline("allowed-tools: [")
    for tool in ("Read", "Write", "Bash"):
        add(_sub(
            f"allowed-tool-dropped-{tool}",
            "AC-C01-22",
            tools_line,
            tools_line.replace(f"{tool}, ", ""),
        ))

    # AC-C01-23 / AC-C01-24
    add(_sub("output-language-not-ja", "AC-C01-23", "output_language: ja\n", "output_language: en\n"))
    add(_sub(
        "source-traceability-dropped",
        "AC-C01-24",
        "source: plugin-plans/guide-doc-generator/component-inventory.json#C01\n",
        "source: plugin-plans/guide-doc-generator/component-inventory.json\n",
    ))
    return out


def _criterion_text_head(cid):
    heads = {
        "IN1": "構成データが",
        "OUT1": "生成した単一 HTML 資料",
        "OUT2": "同梱された構成データから",
        "OUT3": "題材と素材だけを与えた実起動で",
    }
    return heads[cid]


MUTATIONS = _mutations()


def _violation_sites():
    """contract_lib.py の Violation 発生箇所を静的に数える。"""
    src = (HERE / "contract_lib.py").read_text(encoding="utf-8")
    return [m.group(1) for m in re.finditer(r'Violation\(\s*\n?\s*"(AC-C01-\d+)"', src)]


class PredicateSinglePointRejectabilityTest(unittest.TestCase):
    """全 AC 述語が単一箇所の違反注入で発火する。"""

    def _materialize(self, mutation):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c01-scope-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        root = tmp / "accept"
        if mutation.kind == "delfile":
            target = root / mutation.a
            self.assertTrue(target.is_file(), f"削除対象が存在しない: {mutation.a}")
            target.unlink()
        else:
            skill_md = root / ACCEPT_SKILL_REL / "SKILL.md"
            text = skill_md.read_text(encoding="utf-8")
            self.assertEqual(
                1,
                text.count(mutation.a),
                f"注入箇所が受入例に一意に存在しない ({mutation.name}): {mutation.a[:60]!r}",
            )
            self.assertNotEqual(mutation.a, mutation.b, f"変異になっていない: {mutation.name}")
            skill_md.write_text(text.replace(mutation.a, mutation.b), encoding="utf-8")
        return root / ACCEPT_SKILL_REL

    def test_accept_fixture_is_clean_before_injection(self):
        """変異を入れない複製は違反 0 件 (以下の判定の対照)。"""
        tmp = Path(tempfile.mkdtemp(prefix="hb-c01-scope-base-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        violations = contract_lib.check_skill(tmp / "accept" / ACCEPT_SKILL_REL)
        self.assertEqual([], [(x.contract_id, x.message) for x in violations])

    def test_mutation_names_are_unique(self):
        dup = [n for n, c in Counter(m.name for m in MUTATIONS).items() if c > 1]
        self.assertEqual([], dup, f"変異名が重複している: {dup}")

    def test_every_violation_site_has_a_mutation(self):
        """contract_lib の Violation 発生箇所すべてに対応する変異がある。

        契約 id ごとに「発生箇所数 <= 変異数」を要求する。述語を増やしたのに
        単一箇所注入で発火することを確かめないまま緑になるのを防ぐ。
        """
        sites = Counter(_violation_sites())
        covered = Counter(m.ac_id for m in MUTATIONS)
        self.assertEqual(set(sites), set(covered), "契約 id の集合が一致しない")
        short = {cid: (n, covered[cid]) for cid, n in sites.items() if covered[cid] < n}
        self.assertEqual({}, short, f"変異が発生箇所数に足りない契約 id (発生箇所, 変異数): {short}")

    def test_single_point_injection_triggers_each_predicate(self):
        for mutation in MUTATIONS:
            with self.subTest(mutation=mutation.name):
                skill_dir = self._materialize(mutation)
                ids = contract_lib.violation_ids(contract_lib.check_skill(skill_dir))
                self.assertIn(
                    mutation.ac_id,
                    ids,
                    f"変異 {mutation.name} が {mutation.ac_id} で落ちていない (検出: {ids})",
                )


class BodyWidePredicateScopeTest(unittest.TestCase):
    """本文全体一致の述語が受入 fixture 上で一意に潰せることを固定する。

    語が本文に 2 回以上現れる述語は、単一 (old, new) 置換で違反状態を作れない。
    PREDICATE-SCOPE-POLICY.md の方針 (A) はこれを節/宣言行スコープへ寄せて解いた。
    """

    # (契約 id, 判定スコープ名, 語) — contract_lib の本文側述語の語彙
    BODY_TOKENS = (
        ("AC-C01-14", "body", "CR-PRESENTATION-ORDER"),
        ("AC-C01-15", "body", "/handout-verify"),
        ("AC-C01-15", "body", "CR-GATE-AGG"),
        ("AC-C01-16", "body", "--place-config"),
        ("AC-C01-16", "body", "--assets-src"),
        ("AC-C01-18", "body", "assign-handout-readability-evaluator"),
        ("AC-C01-20", "llm_decl", "LLM で書かない"),
        ("AC-C01-20", "llm_decl", "決定論"),
        ("AC-C01-17", "readme_decl", "README.md"),
        ("AC-C01-19", "非対話節", "検証済みの構成データ"),
        ("AC-C01-19", "非対話節", "非対話"),
    ) + tuple(("AC-C01-17", "readme_decl", s) for s in contract_lib.README_SECTIONS) \
      + tuple(("AC-C01-21", "purpose", s) for s in ("handout.html", "handout-config.json", "assets/", "README.md")) \
      + tuple(("AC-C01-21", "purpose", s) for s in contract_lib.REPORT_ELEMENTS) \
      + tuple(("AC-C01-9", "accept", s) for s in contract_lib.REQUIRED_CRITERIA)

    def _scopes(self):
        _fm, body = contract_lib.split_frontmatter(ACCEPT_TEXT)
        body_lines = body.splitlines()
        return {
            "body": body,
            "purpose": contract_lib._section_text(body_lines, "## Purpose & Output Contract") or "",
            "accept": contract_lib._section_text(body_lines, "## Criteria acceptance") or "",
            "非対話節": contract_lib._section_text_containing(body_lines, "非対話") or "",
            "readme_decl": "\n".join(
                l for l in body_lines
                if "README.md" in l and any(w in l for w in contract_lib.WRITE_VERBS)
            ),
            "llm_decl": "\n".join(l for l in body_lines if "LLM で書かない" in l),
        }

    def test_body_side_tokens_occur_once_in_their_scope(self):
        scopes = self._scopes()
        for ac_id, scope_name, token in self.BODY_TOKENS:
            with self.subTest(ac_id=ac_id, token=token):
                self.assertEqual(
                    1,
                    scopes[scope_name].count(token),
                    f"{ac_id} の語 {token!r} が判定スコープ {scope_name} に一意でない。"
                    "単一箇所注入で違反状態を作れないため、述語をより狭いスコープへ寄せること",
                )


if __name__ == "__main__":
    unittest.main()
