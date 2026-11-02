"""build_target の置き場所と、レビュー実行が成果物を 1 バイトも変えないこと (AC6 の形式面)。

AC6 の実測 (資料 2 本を渡して実行) は P06 の受入であり、ここでは
「変えない」が宣言として本文に固定されているかまでを見る。
"""

from __future__ import annotations

import hb_c06 as H


class TestBuildTargetPlacement(H.AgentContractTestCase):
    def test_build_target_path_matches_brief(self):
        self.assertEqual(
            H.BRIEF["build_target"],
            str(H.AGENT.relative_to(H.REPO_ROOT)),
            "build_target のパスがブリーフと違う",
        )

    def test_agent_lives_under_agents_dir(self):
        self.assertEqual("agents", H.AGENT.parent.name)

    def test_only_one_agent_definition_for_c06(self):
        """production surface に C06 の定義が 1 本しか無いこと。

        不変条件は「production surface の定義が一意」であり、tests/ 配下の
        fixture (他 component の受入資材) は production surface ではない。
        そのため plugin ルート全域を再帰探索したうえで tests/ ツリーだけを
        除外する。agents/ 配下に限定しないのは、skills/ や commands/ など
        本来置いてはならない場所へ紛れ込んだ定義も検出し続けるため。
        """
        tests_root = H.TESTS_DIR.parent  # plugins/guide-doc-generator/tests
        matches = sorted(
            p
            for p in H.PLUGIN_ROOT.glob("**/handout-readability-reviewer.md")
            if tests_root not in p.parents
        )
        self.assertEqual(
            [H.AGENT],
            matches,
            "production surface の C06 定義は 1 ファイル: {}".format(matches),
        )


class TestNoArtifactMutation(H.AgentContractTestCase):
    def test_no_artifact_is_modified_declaration(self):
        self.assert_mentions_any(
            ("1 バイトも", "書き換えない", "read-only"),
            "成果物を変更しないことの宣言",
        )

    def test_no_output_directory_is_written(self):
        self.assert_mentions_any(
            ("ファイルは書かない", "ファイルを介さない", "戻り値"),
            "findings をファイルで受け渡さないことの宣言",
        )


class TestTestDirectoryHygiene(H.AgentContractTestCase):
    """write_scope の自己検査: このテストディレクトリに実装本体を置いていないこと。"""

    def setUp(self):
        # 実装の有無に依存しない検査なので require_agent を通さない。
        pass

    def test_only_tests_harness_and_readme_present(self):
        allowed_suffixes = {".py", ".md"}
        for path in H.TESTS_DIR.iterdir():
            if path.name == "__pycache__":
                continue
            with self.subTest(path=path.name):
                self.assertIn(path.suffix, allowed_suffixes)

    def test_no_agent_markdown_inside_tests_dir(self):
        strays = [p.name for p in H.TESTS_DIR.glob("*.md") if p.name != "README.md"]
        self.assertEqual([], strays, "テストディレクトリに agent 定義を置かない")

    def test_python_files_are_tests_or_harness(self):
        for path in sorted(H.TESTS_DIR.glob("*.py")):
            with self.subTest(path=path.name):
                self.assertTrue(
                    path.name.startswith("test_") or path.name == "hb_c06.py",
                    "想定外の .py: {}".format(path.name),
                )
