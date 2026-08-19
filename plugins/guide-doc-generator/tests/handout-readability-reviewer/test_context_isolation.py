"""must_not_assume / isolation_rationale: 親会話の前提を持ち込んだ場合に落ちる検査。

task-spec P04-C06-01 の acceptance_criterion が名指しした 2 本のうちの 1 本。
C06 の価値は「context に何が載っていないか」で決まるので、持ち込み禁止の 5 項目が
本文に明示されていることを固定する。1 項目でも欠けると、その面から設計意図が
流れ込み、書かれていない情報で行間が埋まる。
"""

from __future__ import annotations

import hb_c06 as H


class TestMustNotAssume(H.AgentContractTestCase):
    """input_contract.must_not_assume の (1)-(5)。"""

    def test_1_design_intent_not_carried_over(self):
        self.assert_mentions_any(
            ("設計したときの意図", "設計意図", "こういう狙い"),
            "(1) 構成データを設計したときの意図を持ち込まない",
        )

    def test_1_judgement_is_grounded_in_written_text_only(self):
        self.assert_mentions_any(
            ("書かれている文字だけ", "書かれた文字だけ", "逐語引用"),
            "(1) 判定根拠を HTML と構成データの記述に限る",
        )

    def test_2_hearing_log_not_carried_over(self):
        self.assert_mentions_any(
            ("ヒアリングの生ログ", "ヒアリング生ログ", "ヒアリングで語られた"),
            "(2) ヒアリングの生ログと背景の補足を持ち込まない",
        )

    def test_2_no_prior_knowledge_beyond_reader_profile(self):
        self.assert_mentions_any(
            ("reader_profile に明示された属性を超える", "超える前提知識", "前提知識を読者に仮定しない"),
            "(2) reader_profile を超える前提知識を読者に仮定しない",
        )

    def test_3_reference_html_wording_not_carried_over(self):
        self.assert_mentions_any(
            ("参照 HTML", "参照HTML", "v1/v2"),
            "(3) 参照 HTML の文面を指摘根拠にしない",
        )

    def test_3_norm_is_the_writing_pattern_not_the_wording(self):
        self.assert_mentions_any(
            ("文面ではない", "文面は読まない", "規範として参照するのは文章設計の型"),
            "(3) 規範は文章設計の型であって文面ではない",
        )

    def test_4_loop_count_and_deadline_not_carried_over(self):
        self.assert_mentions_any(
            ("何周目", "loop 数", "残り loop", "締切"),
            "(4) 生成が何周目か・締切・残り loop 数を持ち込まない",
        )

    def test_5_past_findings_not_carried_over(self):
        self.assert_mentions_any(
            ("過去に出した findings", "過去の findings", "前回の findings"),
            "(5) 自分が過去に出した findings を持ち込まない",
        )

    def test_5_html_is_reread_every_time(self):
        self.assert_mentions_any(
            ("毎回 HTML を読み直", "毎回通読", "冒頭から通読"),
            "(5) 毎回 HTML を通読して判定する",
        )


class TestIsolationRationale(H.AgentContractTestCase):
    def test_independent_context_is_declared_in_frontmatter(self):
        self.assertEqual("fork", H.frontmatter(self.text).get("isolation"))

    def test_reader_is_fixed_in_one_sentence(self):
        self.assert_mentions_any(
            ("1 文で確定", "一文で確定", "1文で確定"),
            "手順 2: 演じる読者を 1 文で確定する",
        )

    def test_standpoint_is_stated_in_the_verdict(self):
        self.assert_mentions_any(
            ("立場を明示", "reviewed_as"),
            "判定文の中で読者としての立場を明示する",
        )

    def test_proposer_is_not_approver(self):
        self.assert_mentions_any(
            ("proposer", "生成した本人", "自分が直したものを自分が合格"),
            "生成した本人が採点しない構図であることの明示",
        )
