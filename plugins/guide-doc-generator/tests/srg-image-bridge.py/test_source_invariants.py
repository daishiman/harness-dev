"""ソースに対する不変条件 — AC-C21-1 / AC-C21-10、C17 / C27、P03 Y-01。

**委譲であって再実装でないこと**をソースの静的検査で固定する。C21 が画像生成を
自前で持ったら、どれだけ出力が正しく見えても R12 の設計 (SRG へ委譲) が壊れている。
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

import _harness as H


def _code(source: str) -> str:
    """行コメントを落とした本文。"""
    return "\n".join(re.sub(r"#.*$", "", line) for line in source.splitlines())


class DelegationOnlyTest(H.BridgeTestCase):
    """AC-C21-1: プロンプト本文の組み立て・genome の複製・画像生成 API 呼び出しが 0 件。"""

    def setUp(self):
        super().setUp()
        self.source = H.read_source(self)
        self.code = _code(self.source)

    def test_no_image_generation_api_call(self):
        for token in ("images.generate", "gpt-image", "dall-e", "openai", "api.openai.com"):
            self.assertNotIn(token.lower(), self.code.lower(), "画像生成 API 呼び出し {}".format(token))

    def test_no_direct_codex_exec(self):
        """codex を起動するのは委譲先 (generate-images-codex.js) だけ。"""
        self.assertIsNone(
            re.search(r"""['"]codex['"]\s*,\s*['"]exec['"]""", self.code),
            "codex exec を直接組み立てている",
        )
        self.assertIsNone(
            re.search(r"""subprocess\.[a-z_]+\(\s*\[?\s*['"]codex['"]""", self.code),
            "codex を subprocess で直接起動している",
        )

    def test_no_prompt_body_assembly(self):
        """プロンプト本文を書かない (SRG の promptSuffix / negativePrompt を再現しない)。"""
        for token in ("promptSuffix", "negativePrompt", "consistencyAnchors", "artStyle"):
            self.assertNotIn(token, self.code, "genome のプロンプト構成物 {} を触っている".format(token))

    def test_no_prompt_file_is_written_by_this_script(self):
        """<slug>.prompt.txt を書くのは build-image-prompts.js。"""
        self.assertIsNone(
            re.search(r"""\.prompt\.txt['"]\s*\)?\s*\.?\s*write""", self.code),
            "prompt ファイルを自前で書いている",
        )

    def test_no_genome_copy(self):
        """genome は参照するだけ (複製すると『再実装しない』方針の縁に触れる)。"""
        genome_lines = [line for line in self.code.splitlines() if "genome" in line.lower()]
        for line in genome_lines:
            for token in ("copy2", "copyfile", "copytree", "write_bytes", "write_text"):
                self.assertNotIn(token, line, "genome を複製している: {}".format(line.strip()))

    def test_vendor_script_names_are_referenced(self):
        """委譲先の 2 本を実際に起動する形で持っている。"""
        for name in ("build-image-prompts.js", "generate-images-codex.js"):
            self.assertIn(name, self.source, "委譲先 {} への参照が無い".format(name))

    def test_subprocess_is_used_without_shell(self):
        self.assertIn("subprocess", self.code, "委譲していない (subprocess が無い)")
        self.assertIsNone(re.search(r"shell\s*=\s*True", self.code), "shell=True で起動している")

    def test_png_signature_is_checked_in_source(self):
        """algorithm 13/14: 委譲先の exit code ではなく自前の署名検査で判定する。"""
        self.assertTrue(
            re.search(r"\\x89PNG|\\x89\\x50\\x4[eE]\\x47|89\s*50\s*4[eE]\s*47", self.source),
            "PNG 署名検査がソースに無い",
        )

    def test_no_base64_encoding(self):
        """data URI 化は C13 の責務。C21 は base64 化しない。"""
        self.assertNotIn("base64", self.code, "base64 化を持っている (C13 の責務)")


class StdlibOnlyTest(H.BridgeTestCase):
    """AC-C21-10 / C27: 標準ライブラリのみ。node の起動は委譲であって Python 依存ではない。"""

    def setUp(self):
        super().setUp()
        self.source = H.read_source(self)

    def test_all_imports_are_stdlib(self):
        modules = set()
        for line in self.source.splitlines():
            m = re.match(r"\s*import\s+([A-Za-z_][\w.]*)", line)
            if m:
                modules.add(m.group(1).split(".")[0])
            m = re.match(r"\s*from\s+([A-Za-z_][\w.]*)\s+import", line)
            if m:
                modules.add(m.group(1).split(".")[0])
        allowed = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}
        self.assertEqual(set(), modules - allowed, "標準ライブラリ以外を import している")

    def test_no_socket_is_opened_by_this_script(self):
        """network=true は『委譲を経由した通信』の宣言であって自前 HTTP ではない (Y-01)。"""
        code = _code(self.source)
        for token in ("urllib.request", "http.client", "socket.socket", "requests.", "httpx"):
            self.assertNotIn(token, code, "自前でネットワークを開いている: {}".format(token))

    def test_no_environment_specific_absolute_path(self):
        for token in ("/Users/", "/home/", "C:\\\\"):
            self.assertNotIn(token, self.source, "環境固有の絶対パスがある: {}".format(token))


class FrontmatterTest(H.BridgeTestCase):
    """P0 lint (lint-script-frontmatter) と P03 Y-01 の network 宣言。"""

    REQUIRED_KEYS = ("name", "purpose", "inputs", "outputs", "contexts", "network", "write-scope", "dependencies")

    def setUp(self):
        super().setUp()
        self.source = H.read_source(self)

    def _frontmatter(self):
        block = re.search(r"^# /// script$(.*?)^# ///$", self.source, re.MULTILINE | re.DOTALL)
        if not block:
            self.fail("PEP 723 形式の script frontmatter (# /// script) が無い")
        fields = {}
        for line in block.group(1).splitlines():
            m = re.match(r"#\s*([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
            if m:
                fields[m.group(1)] = m.group(2).strip()
        return fields

    def test_required_keys_are_declared(self):
        fields = self._frontmatter()
        missing = [key for key in self.REQUIRED_KEYS if key not in fields]
        self.assertEqual([], missing, "frontmatter に不足キーがある")

    def test_network_is_declared_true(self):
        """Y-01: 実効の通信有無で宣言する。委譲先 codex がモデル API へ通信するため true。"""
        self.assertEqual("true", self._frontmatter().get("network", "").lower())

    def test_network_declaration_matches_inventory(self):
        self.assertIs(True, H.inventory_component("C21").get("network"))

    def test_write_scope_is_declared_as_assets_dir(self):
        self.assertIn("assets", self._frontmatter().get("write-scope", "").lower())

    def test_frontmatter_linter_passes(self):
        linter = H.require_file(self, H.FRONTMATTER_LINTER, "skill-governance-lint")
        proc = subprocess.run(
            [sys.executable, str(linter), str(H.SCRIPT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(H.REPO_ROOT),
            timeout=60,
        )
        self.assertEqual(
            0,
            proc.returncode,
            "lint-script-frontmatter 失敗:\n{}\n{}".format(
                proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")
            ),
        )


class BuildTargetTest(H.BridgeTestCase):
    """brief build_target と inventory の一致 (置き場所を勝手に変えない)。"""

    def test_script_is_at_the_declared_build_target(self):
        expected = H.brief()["build_target"]
        self.assertEqual(expected, str(H.SCRIPT.relative_to(H.REPO_ROOT)))

    def test_inventory_build_target_matches_brief(self):
        self.assertEqual(H.brief()["build_target"], H.inventory_component("C21").get("build_target"))

    def test_script_is_executable_as_a_module_free_cli(self):
        proc = H.run(["--help"])
        self.assertIn(proc.returncode, (0, 2), H.describe(proc))


class NoReimplementationAcrossScriptsTest(H.BridgeTestCase):
    """AC-C21-1: guide-doc-generator/scripts 全体で画像生成の再実装が 0 件。"""

    def _sources(self):
        return sorted(H.SCRIPTS_DIR.glob("*.py")) if H.SCRIPTS_DIR.is_dir() else []

    def test_scripts_directory_exists(self):
        if not H.SCRIPTS_DIR.is_dir():
            self.fail("scripts ディレクトリが未存在: {}".format(H.SCRIPTS_DIR))

    def test_no_other_script_calls_an_image_generation_api(self):
        H.require_script(self)
        offenders = []
        for path in self._sources():
            text = _code(path.read_text(encoding="utf-8")).lower()
            if any(token in text for token in ("gpt-image", "dall-e", "images.generate")):
                offenders.append(path.name)
        self.assertEqual([], offenders, "画像生成 API を持つ script がある")

    def test_only_this_script_launches_the_srg_vendor_scripts(self):
        H.require_script(self)
        offenders = [
            path.name
            for path in self._sources()
            if path.name != H.SCRIPT_NAME and "generate-images-codex.js" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual([], offenders, "委譲の入口が 2 つ以上ある")


if __name__ == "__main__":
    unittest.main()
