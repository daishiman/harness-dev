"""write-scope: none と登録面の一本化を固定する。

正本:
  - hook-brief-C10.json#event_rationale (ファイルの削除やロールバックは行わない)
  - hook-brief-C10.json#settings_registration / #failure_modes[2][3]

PostToolUse の exit2 は「書込を取り消せる」ことを意味しない。hook はファイルを
1 バイトも書き換えず、同じ入力に対して何度でも同じ結果を返す。
"""

import hashlib
import json
import unittest

from hb_c10 import (C10TestCase, PLUGIN_ROOT, clean_html, emoji_html,
                    external_html, require_hook)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestWriteScopeNone(C10TestCase):
    """hook は何も書かない (対象ファイルも周辺も)。"""

    def test_target_is_untouched_on_block(self):
        target = self.make_target(external_html())
        before = _digest(target)
        res = self.run_hook(self.payload(target))
        self.assertEqual(2, res.rc, str(res))
        self.assertTrue(target.exists(), "exit2 でファイルを消してはならない")
        self.assertEqual(before, _digest(target), "対象ファイルを書き換えてはならない")

    def test_target_is_untouched_on_pass(self):
        target = self.make_target(clean_html())
        before = _digest(target)
        self.run_hook(self.payload(target))
        self.assertEqual(before, _digest(target))

    def test_no_new_files_are_created(self):
        target = self.make_target(emoji_html())
        before = sorted(p.name for p in target.parent.iterdir())
        self.run_hook(self.payload(target))
        after = sorted(p.name for p in target.parent.iterdir())
        self.assertEqual(before, after, "hook の write_scope は none")

    def test_config_marker_is_untouched(self):
        target = self.make_target(external_html())
        cfg = target.parent / "handout-config.json"
        before = _digest(cfg)
        self.run_hook(self.payload(target))
        self.assertEqual(before, _digest(cfg))


class TestIdempotent(C10TestCase):
    """同じ入力に対し何度実行しても同じ結果 (判定に状態を持たない)。"""

    def test_block_is_reproducible(self):
        target = self.make_target(external_html())
        a = self.run_hook(self.payload(target))
        b = self.run_hook(self.payload(target))
        self.assertEqual((a.rc, a.out, a.err), (b.rc, b.out, b.err),
                         "2 回目で結果が変わる\n1:{}\n2:{}".format(a, b))

    def test_pass_is_reproducible(self):
        target = self.make_target(clean_html())
        a = self.run_hook(self.payload(target))
        b = self.run_hook(self.payload(target))
        self.assertEqual((a.rc, a.out, a.err), (b.rc, b.out, b.err))


class TestSingleRegistrationSurface(unittest.TestCase):
    """failure_modes[2]: plugin hooks.json 以外に C10 を重複登録しない。

    Claude/Codex 共通の配布正本は plugin root ``hooks/hooks.json``。
    Claude Code は標準配置を自動検出するため manifest で再指定せず、Codex
    manifest だけが同じファイルを明示参照する。project settings には投影しない。
    """

    HOOK_NAME = "guard-handout-external-ref"

    def setUp(self):
        # 実装が現れて初めて意味を持つ契約なので、未実装のあいだは赤にする
        require_hook()

    def test_bundled_hooks_json_registers_c10_once(self):
        p = PLUGIN_ROOT / "hooks" / "hooks.json"
        self.assertTrue(p.is_file(), "Claude/Codex 共通の hooks/hooks.json が必要")
        self.assertEqual(
            p.read_text(encoding="utf-8").count(self.HOOK_NAME),
            1,
            "C10 の配布登録は hooks/hooks.json の1回だけ",
        )

    def test_manifests_use_each_runtime_canonical_hook_registration(self):
        p = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
        codex = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
        self.assertNotIn(
            "hooks",
            json.loads(p.read_text(encoding="utf-8")),
            "Claude Code は標準 hooks/hooks.json を自動検出するため二重指定しない",
        )
        self.assertEqual(json.loads(codex.read_text(encoding="utf-8"))["hooks"], "./hooks/hooks.json")
