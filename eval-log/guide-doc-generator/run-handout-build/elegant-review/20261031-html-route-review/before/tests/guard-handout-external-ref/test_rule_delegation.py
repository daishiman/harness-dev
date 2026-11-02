"""rule_delegation を固定する (P03 Y-02 / Y-03 の再発防止)。

正本: hook-brief-C10.json#rule_delegation / #acceptance_checks[13..15]
      script-brief-C16.json#module_api / #canonical_rules

C10 は判定規則の独自定義を持たない。ソースに外部スキームの列挙も絵文字
コードポイントの列挙も現れず、判定は C16 module_api の呼び出しに一本化される。
"""

import ast
import os
import re
import shutil
import subprocess
import sys
import unittest

from hb_c10 import (C10TestCase, C16_SCRIPT, HOOK, external_html,
                    hook_code_only, hook_source, require_hook)


class TestNoRuleDuplication(unittest.TestCase):
    """acceptance_checks[13]: 規則本文の複製が 0 件であること。"""

    #: CR-EXT が列挙するスキーム。hook 側に現れてはいけない
    SCHEME_LITERALS = ["http://", "https://", "ftp://", "ws://", "wss://"]
    #: CR-EMOJI の層 1 / 層 2 に現れるコードポイント表記
    CODEPOINT_PATTERNS = [
        r"0x1[Ff][0-9A-Fa-f]{3}",       # 0x1F600 など
        r"\\U0001[Ff][0-9A-Fa-f]{3}",   # \U0001F600 など
        r"0x2[0-7][0-9A-Fa-f]{2}",      # 0x2705 / 0x2600 など
        r"0x[Ff][Ee]0[Ff]",             # 0xFE0F (VS16)
        r"U\+1[Ff][0-9A-Fa-f]{3}",
    ]

    def setUp(self):
        self.src = hook_source()
        # コメント・docstring を落とした「実行される側」だけを見る
        self.code = hook_code_only()

    def test_no_scheme_literals(self):
        found = [s for s in self.SCHEME_LITERALS if s in self.code]
        self.assertEqual([], found,
                         "外部スキームの列挙が hook 本体にある (CR-EXT の複製): {}".format(found))

    def test_no_emoji_codepoint_literals(self):
        found = []
        for pat in self.CODEPOINT_PATTERNS:
            found += re.findall(pat, self.code)
        self.assertEqual([], found,
                         "絵文字コードポイントの列挙が hook 本体にある (CR-EMOJI の複製): {}".format(found))

    def test_no_url_attribute_name_enumeration(self):
        """srcset / poster / formaction 等の属性名列挙も CR-EXT の複製。"""
        names = ["srcset", "poster", "formaction", "xlink:href", "@import"]
        found = [n for n in names if n in self.code]
        self.assertEqual([], found,
                         "URL 属性名の列挙が hook 本体にある: {}".format(found))

    def test_calls_c16_module_api(self):
        self.assertIn("scan_external_references", self.src,
                      "判定は C16 module_api の呼び出しへ一本化する")
        self.assertIn("scan_emoji", self.src,
                      "判定は C16 module_api の呼び出しへ一本化する")

    def test_loads_c16_by_spec_from_file_location(self):
        self.assertIn("spec_from_file_location", self.src,
                      "rule_delegation.how: importlib.util.spec_from_file_location で読む")
        self.assertIn("verify-handout-selfcontained.py", self.src,
                      "canonical_owner を名指しで読み込む")


class TestNoPurposeVocabulary(unittest.TestCase):
    """acceptance_checks[14]: 用途種別の語彙リテラルが 0 件 (C42 の重複を作らない)。

    語彙の正本は config/handout-purposes.json (owner C23)。
    C10 の同定は日付接頭ディレクトリ名 + handout-config.json の 2 マーカーのみに
    依存し、種別語彙を一切参照しない (applies_to.resolution_rationale)。
    """

    SLUGS = ["lecture", "agenda", "guide", "onboarding", "report", "proposal",
             "study-notes", "study-plan"]
    LABELS = ["勉強会", "レクチャー", "研修", "定例", "アジェンダ", "会議",
              "配布資料", "ガイド", "オンボーディング", "導入ガイド",
              "報告", "レポート", "提案", "企画", "学習まとめ", "勉強メモ",
              "学習計画"]

    def setUp(self):
        self.code = hook_code_only()

    def test_no_purpose_slug_literals(self):
        found = [s for s in self.SLUGS
                 if '"{}"'.format(s) in self.code or "'{}'".format(s) in self.code]
        self.assertEqual([], found, "用途種別 slug が hook 本体にある: {}".format(found))

    def test_no_purpose_label_literals(self):
        found = [s for s in self.LABELS if s in self.code]
        self.assertEqual([], found, "用途種別の日本語語彙が hook 本体にある: {}".format(found))

    def test_no_purposes_catalog_reference(self):
        self.assertNotIn("handout-purposes.json", self.code,
                         "C10 は用途語彙カタログを読まない (2 マーカーのみで同定する)")


class TestStdlibOnly(unittest.TestCase):
    """acceptance_checks[15] (C27): Python 標準ライブラリのみを import する。"""

    def _imported_roots(self):
        tree = ast.parse(hook_source())
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    roots.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    roots.add(node.module.split(".")[0])
        return roots

    def test_all_imports_are_stdlib(self):
        stdlib = set(getattr(sys, "stdlib_module_names", ()))
        self.assertTrue(stdlib, "Python 3.10+ が要る (sys.stdlib_module_names)")
        extra = sorted(r for r in self._imported_roots() if r not in stdlib)
        self.assertEqual([], extra,
                         "標準ライブラリ以外を import している: {}".format(extra))

    def test_no_site_packages_import(self):
        src = hook_source()
        for name in ["requests", "bs4", "lxml", "yaml", "jinja2"]:
            self.assertNotIn("import {}".format(name), src)


class TestImportFailureIsSoft(C10TestCase):
    """rule_delegation.if_import_fails: C16 を読めないときは exit0 + systemMessage。"""

    def _isolated_hook(self):
        """C16 が同居しない偽 plugin root へ hook 本体だけを複製する。"""
        require_hook()
        root = self.tmp / "fake-plugin-root"
        (root / "hooks").mkdir(parents=True)
        dst = root / "hooks" / HOOK.name
        shutil.copy2(str(HOOK), str(dst))
        self.assertFalse((root / "scripts" / C16_SCRIPT.name).exists())
        return dst

    def test_exit_zero_when_c16_unresolvable(self):
        target = self.make_target(external_html())
        env_hook = self._isolated_hook()
        res = self.run_hook(self.payload(target), hook_path=env_hook)
        self.assertEqual(0, res.rc,
                         "判定モジュール解決不能は fail_closed_scope (a) と同じ扱い\n{}".format(res))

    def test_system_message_when_c16_unresolvable(self):
        target = self.make_target(external_html())
        env_hook = self._isolated_hook()
        res = self.run_hook(self.payload(target), hook_path=env_hook)
        obj = res.system_message()
        self.assertIsNotNone(obj,
                             "『判定モジュール解決不能のため未検査』を systemMessage で出す\n{}".format(res))

    def test_no_traceback_when_c16_unresolvable(self):
        target = self.make_target(external_html())
        env_hook = self._isolated_hook()
        res = self.run_hook(self.payload(target), hook_path=env_hook)
        self.assertNotIn("Traceback", res.err, str(res))


class TestSelfResolution(C10TestCase):
    """settings_registration: HB_ROOT / CLAUDE_PLUGIN_ROOT が無くても自己解決する。"""

    def _run_with_env(self, env_overrides):
        require_hook()
        target = self.make_target(external_html())
        env = dict(os.environ)
        env.pop("HB_ROOT", None)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        env.update(env_overrides)
        import json as _json
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            input=_json.dumps(self.payload(target)),
            capture_output=True, text=True, cwd=str(self.tmp), timeout=120, env=env)
        return proc

    def test_works_without_any_env(self):
        proc = self._run_with_env({})
        self.assertEqual(2, proc.returncode,
                         "env 未設定でも __file__ 相対で C16 を解決して検査する: {!r}".format(
                             (proc.returncode, proc.stdout, proc.stderr)))

    def test_hb_root_takes_precedence(self):
        proc = self._run_with_env({"HB_ROOT": str(C16_SCRIPT.parents[1])})
        self.assertEqual(2, proc.returncode,
                         "HB_ROOT で解決できる: {!r}".format(
                             (proc.returncode, proc.stdout, proc.stderr)))
