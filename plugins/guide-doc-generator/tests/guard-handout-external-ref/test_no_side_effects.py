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
    """failure_modes[2]: settings.json と plugin 同梱 hooks の二重登録を作らない。

    登録面は settings.json 側を正本とし、plugin 同梱側 (hooks/hooks.json 方式・
    .claude-plugin/plugin.json の hooks キー方式) には C10 の登録を置かない。
    """

    HOOK_NAME = "guard-handout-external-ref"

    def setUp(self):
        # 実装が現れて初めて意味を持つ契約なので、未実装のあいだは赤にする
        require_hook()

    def test_no_bundled_hooks_json(self):
        p = PLUGIN_ROOT / "hooks" / "hooks.json"
        if not p.exists():
            return
        self.assertNotIn(self.HOOK_NAME, p.read_text(encoding="utf-8"),
                         "同梱 hooks.json に C10 を登録すると 1 回の書込で 2 回発火する")

    def test_plugin_manifest_does_not_register_hook(self):
        p = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
        if not p.exists():
            return
        text = p.read_text(encoding="utf-8")
        if "hooks" not in text:
            return
        data = json.loads(text)
        blob = json.dumps(data.get("hooks", ""), ensure_ascii=False)
        self.assertNotIn(self.HOOK_NAME, blob,
                         "plugin.json の hooks キーに C10 を登録しない (settings.json が正本)")
