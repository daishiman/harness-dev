"""applies_to.rule の 5 条件を 1 つずつ固定する。

正本: hook-brief-C10.json#applies_to.rule
  (1) tool_name が Write / Edit
  (2) tool_input から書込先パスが取れる
  (3) 拡張子が .html (大小文字無視)
  (4) 同ディレクトリに handout-config.json がある
  (5) ディレクトリ名が ^\\d{4}-\\d{2}-\\d{2}- に一致する
外れた時点で exit0 (素通し)。

各テストは「その条件だけを外した違反入り HTML」を渡す。
清潔な HTML を渡すと exit0 の理由が『対象外だから』か『違反が無いから』か
切り分けられないため、素通し系の入力は必ず違反を含ませる。
"""

from hb_c10 import C10TestCase, D1, clean_html, external_html


class TestCondition1ToolName(C10TestCase):
    """(1) tool_name が Write / Edit のいずれか。"""

    def _run(self, tool_name):
        return self.run_on(external_html(), tool_name=tool_name)

    def test_write_is_in_scope(self):
        self.assertBlocked(self._run("Write"), D1, "Write は検査対象")

    def test_edit_is_in_scope(self):
        self.assertBlocked(self._run("Edit"), D1, "Edit は検査対象")

    def test_bash_passes_through(self):
        self.assertPassSilently(self._run("Bash"), "acceptance_checks[0]")

    def test_read_passes_through(self):
        self.assertPassSilently(self._run("Read"))

    def test_grep_passes_through(self):
        self.assertPassSilently(self._run("Grep"))

    def test_multiedit_passes_through(self):
        """matcher は Write|Edit であり MultiEdit を含まない (open_questions に記録済み)。

        見逃しは C16 の完成物ゲートで捕まる。この挙動を変えるには先に
        component-inventory.json の matcher を変えること。
        """
        self.assertPassSilently(self._run("MultiEdit"))

    def test_missing_tool_name_passes_through(self):
        p = self.payload(self.make_target(external_html()))
        del p["tool_name"]
        self.assertPassSilently(self.run_hook(p))

    def test_tool_name_is_case_sensitive(self):
        """語彙は Claude Code のツール名そのもの。小文字 write は該当しない。"""
        self.assertPassSilently(self._run("write"))


class TestCondition2PathExtraction(C10TestCase):
    """(2) tool_input から書込先パスを取り出せる (file_path > filePath > path)。"""

    def test_file_path_key(self):
        self.assertBlocked(self.run_on(external_html(), path_key="file_path"), D1)

    def test_camel_case_file_path_key(self):
        self.assertBlocked(self.run_on(external_html(), path_key="filePath"), D1)

    def test_plain_path_key(self):
        self.assertBlocked(self.run_on(external_html(), path_key="path"), D1)

    def test_key_precedence_file_path_wins(self):
        """3 キーの優先順位: file_path が最優先。清潔な側を指していれば素通し。"""
        clean = self.make_target(clean_html(), filename="clean.html")
        dirty = self.make_target(external_html(), filename="dirty.html")
        p = self.payload(None)
        p["tool_input"] = {"file_path": str(clean), "filePath": str(dirty),
                           "path": str(dirty)}
        self.assertPassSilently(self.run_hook(p), "file_path が最優先")

    def test_key_precedence_file_path_over_path_when_dirty(self):
        clean = self.make_target(clean_html(), filename="clean.html")
        dirty = self.make_target(external_html(), filename="dirty.html")
        p = self.payload(None)
        p["tool_input"] = {"file_path": str(dirty), "path": str(clean)}
        self.assertBlocked(self.run_hook(p), D1, "file_path が最優先")

    def test_camel_case_beats_plain_path(self):
        clean = self.make_target(clean_html(), filename="clean.html")
        dirty = self.make_target(external_html(), filename="dirty.html")
        p = self.payload(None)
        p["tool_input"] = {"filePath": str(clean), "path": str(dirty)}
        self.assertPassSilently(self.run_hook(p), "filePath は path より優先")

    def test_no_path_key_passes_through(self):
        p = self.payload(None)
        p["tool_input"] = {"content": "<html>https://example.com</html>"}
        self.assertPassSilently(self.run_hook(p), "acceptance_checks[1]")

    def test_empty_string_path_passes_through(self):
        p = self.payload(None)
        p["tool_input"] = {"file_path": ""}
        self.assertPassSilently(self.run_hook(p), "非空 str のみ採用する")

    def test_non_string_path_falls_through_to_next_key(self):
        """非 str の値は採用しない (input_contract: 最初に見つかった非空 str)。"""
        dirty = self.make_target(external_html(), filename="dirty.html")
        p = self.payload(None)
        p["tool_input"] = {"file_path": None, "path": str(dirty)}
        self.assertBlocked(self.run_hook(p), D1)

    def test_missing_tool_input_passes_through(self):
        p = self.payload(None)
        del p["tool_input"]
        self.assertPassSilently(self.run_hook(p))


class TestCondition3Extension(C10TestCase):
    """(3) 拡張子が .html (大小文字無視)。"""

    def test_html_is_in_scope(self):
        self.assertBlocked(self.run_on(external_html(), filename="handout.html"), D1)

    def test_uppercase_html_is_in_scope(self):
        self.assertBlocked(self.run_on(external_html(), filename="HANDOUT.HTML"), D1)

    def test_mixed_case_html_is_in_scope(self):
        self.assertBlocked(self.run_on(external_html(), filename="Handout.Html"), D1)

    def test_htm_passes_through(self):
        """契約は `.html` であり `.htm` を含まない。"""
        self.assertPassSilently(self.run_on(external_html(), filename="handout.htm"))

    def test_markdown_passes_through(self):
        self.assertPassSilently(self.run_on(external_html(), filename="README.md"),
                                "acceptance_checks[2] / out_of_scope_examples")

    def test_python_passes_through(self):
        self.assertPassSilently(self.run_on(external_html(), filename="build.py"),
                                "acceptance_checks[2]")

    def test_json_passes_through(self):
        self.assertPassSilently(self.run_on(external_html(), filename="data.json"))

    def test_no_extension_passes_through(self):
        self.assertPassSilently(self.run_on(external_html(), filename="handout"))

    def test_html_in_the_middle_of_name_passes_through(self):
        self.assertPassSilently(self.run_on(external_html(), filename="handout.html.bak"))


class TestCondition4ConfigMarker(C10TestCase):
    """(4) 同じディレクトリに handout-config.json が存在する。"""

    def test_config_present_is_in_scope(self):
        self.assertBlocked(self.run_on(external_html(), with_config=True), D1)

    def test_config_absent_passes_through(self):
        self.assertPassSilently(self.run_on(external_html(), with_config=False),
                                "acceptance_checks[3]")

    def test_config_in_parent_directory_only_passes_through(self):
        """マーカーは『同じディレクトリ』。親にあるだけでは対象にしない。"""
        parent = self.make_dir(self.IN_SCOPE_DIR, with_config=True)
        sub = parent / "2026-08-17-lecture-入れ子"
        sub.mkdir()
        target = sub / "handout.html"
        target.write_text(external_html(), encoding="utf-8")
        self.assertPassSilently(self.run_hook(self.payload(target)))

    def test_similar_config_name_does_not_count(self):
        d = self.make_dir(self.IN_SCOPE_DIR, with_config=False)
        (d / "handout-config.json.bak").write_text("{}", encoding="utf-8")
        (d / "handout-config.yaml").write_text("{}", encoding="utf-8")
        target = d / "handout.html"
        target.write_text(external_html(), encoding="utf-8")
        self.assertPassSilently(self.run_hook(self.payload(target)))

    def test_deck_index_html_passes_through(self):
        """out_of_scope_examples: srg が出す deck の index.html (config が無い)。"""
        d = self.make_dir("2026-08-17-lecture-deck", with_config=False)
        target = d / "index.html"
        target.write_text(external_html(), encoding="utf-8")
        self.assertPassSilently(self.run_hook(self.payload(target)))


class TestCondition5DirectoryName(C10TestCase):
    """(5) ディレクトリ名が ^\\d{4}-\\d{2}-\\d{2}- に一致する。"""

    def _run_in(self, dirname):
        return self.run_on(external_html(), dirname=dirname)

    def test_dated_directory_is_in_scope(self):
        self.assertBlocked(self._run_in("2026-08-17-lecture-生成AIの業務活用入門"), D1)

    def test_other_purpose_token_is_in_scope(self):
        """種別語彙は一切参照しない (C42 の重複を作らない)。任意の語で通る。"""
        self.assertBlocked(self._run_in("2026-08-17-agenda-月次定例"), D1)

    def test_unknown_token_is_still_in_scope(self):
        self.assertBlocked(self._run_in("2026-08-17-zzz-未知の語"), D1,
                           "同定は日付接頭とマーカーのみに依存する")

    def test_undated_directory_passes_through(self):
        self.assertPassSilently(self._run_in("lecture-生成AIの業務活用入門"),
                                "acceptance_checks[4]")

    def test_unpadded_date_passes_through(self):
        self.assertPassSilently(self._run_in("2026-8-17-lecture-x"))

    def test_date_not_at_prefix_passes_through(self):
        self.assertPassSilently(self._run_in("lecture-2026-08-17-x"))

    def test_date_without_trailing_hyphen_passes_through(self):
        """正規表現は末尾のハイフンまでを要求する。"""
        self.assertPassSilently(self._run_in("2026-08-17"))

    def test_date_only_with_hyphen_is_in_scope(self):
        self.assertBlocked(self._run_in("2026-08-17-"), D1)


class TestOutOfScopeExamples(C10TestCase):
    """applies_to.out_of_scope_examples をそのまま入力にする。"""

    def test_demo_sample_html_with_cdn_passes_through(self):
        d = self.make_dir("demo", with_config=False)
        target = d / "sample.html"
        target.write_text(external_html(), encoding="utf-8")
        self.assertPassSilently(self.run_hook(self.payload(target)))

    def test_readme_edit_inside_output_dir_passes_through(self):
        self.assertPassSilently(
            self.run_on(external_html(), filename="README.md", tool_name="Edit"))

    def test_component_catalog_md_passes_through(self):
        d = self.make_dir("references", with_config=False)
        target = d / "component-catalog.md"
        target.write_text(external_html(), encoding="utf-8")
        self.assertPassSilently(self.run_hook(self.payload(target)))
