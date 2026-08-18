"""input_contract と fail_closed_scope (a)(b) を固定する。

正本: hook-brief-C10.json#input_contract / #fail_closed_scope

- stdin に hook ペイロードの JSON オブジェクトが 1 個渡る
- JSON パース失敗 / dict でない → exit0 素通し
- ファイル本文は tool_input からではなく、書込先パスを実際に読んで取得する
- 対象ファイルを読めない (削除済み・権限不足) → exit0 (fail_closed_scope (b))
"""

import json
import os
import stat
import unittest

from hb_c10 import BLOCK_PREFIX, C10TestCase, D1, clean_html, external_html


class TestMalformedStdin(C10TestCase):
    """JSON として読めない stdin は素通しする (dev-graph の payload() と同じ姿勢)。"""

    def test_empty_stdin(self):
        self.assertPassSilently(self.run_hook_raw(""))

    def test_whitespace_only_stdin(self):
        self.assertPassSilently(self.run_hook_raw("   \n\t "))

    def test_broken_json(self):
        self.assertPassSilently(self.run_hook_raw('{"tool_name": "Write",'))

    def test_not_json_at_all(self):
        self.assertPassSilently(self.run_hook_raw("hello world"))

    def test_json_array_is_not_dict(self):
        self.assertPassSilently(self.run_hook_raw('[{"tool_name":"Write"}]'))

    def test_json_string_is_not_dict(self):
        self.assertPassSilently(self.run_hook_raw('"Write"'))

    def test_json_number_is_not_dict(self):
        self.assertPassSilently(self.run_hook_raw("42"))

    def test_json_null_is_not_dict(self):
        self.assertPassSilently(self.run_hook_raw("null"))

    def test_tool_input_not_a_dict(self):
        self.assertPassSilently(self.run_hook_raw(json.dumps(
            {"tool_name": "Write", "tool_input": "handout.html"})))

    def test_hook_never_raises_traceback(self):
        """異常入力でも Python の traceback を stderr へ漏らさない。"""
        res = self.run_hook_raw("{{{")
        self.assertNotIn("Traceback", res.err)


class TestPayloadShape(C10TestCase):
    """実物の PostToolUse ペイロード形をそのまま受ける。"""

    def test_full_post_tool_use_payload(self):
        target = self.make_target(external_html())
        payload = {"tool_name": "Write",
                   "tool_input": {"file_path": str(target),
                                  "content": "<html></html>"},
                   "tool_response": {"filePath": str(target), "success": True},
                   "hook_event_name": "PostToolUse",
                   "cwd": str(self.tmp)}
        self.assertBlocked(self.run_hook(payload), D1)

    def test_unknown_extra_keys_are_ignored(self):
        target = self.make_target(external_html())
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(target)},
                   "session_id": "abc", "transcript_path": "/tmp/x.jsonl",
                   "permission_mode": "default"}
        self.assertBlocked(self.run_hook(payload), D1)

    def test_relative_path_is_resolved_against_cwd(self):
        """cwd 相対のパスでも書込先を同定できる。"""
        target = self.make_target(external_html())
        rel = os.path.relpath(str(target), str(self.tmp))
        payload = {"tool_name": "Write", "tool_input": {"file_path": rel},
                   "hook_event_name": "PostToolUse", "cwd": str(self.tmp)}
        self.assertBlocked(self.run_hook(payload), D1)


class TestBodyComesFromDisk(C10TestCase):
    """input_contract: 本文は tool_input ではなくディスク上の実ファイルから読む。"""

    def test_content_field_is_not_the_source_of_truth_when_clean_on_disk(self):
        """tool_input.content が汚れていてもディスクが清潔なら素通し (Edit の差分対策)。"""
        target = self.make_target(clean_html())
        payload = self.payload(target)
        payload["tool_input"]["content"] = external_html()
        payload["tool_input"]["new_string"] = "\U0001F680"
        self.assertPassSilently(self.run_hook(payload))

    def test_disk_content_blocks_even_when_payload_content_is_clean(self):
        target = self.make_target(external_html())
        payload = self.payload(target)
        payload["tool_input"]["content"] = clean_html()
        self.assertBlocked(self.run_hook(payload), D1)


class TestUnreadableTarget(C10TestCase):
    """fail_closed_scope (b): 読めないファイルは exit0 (非ゼロで落とさない)。"""

    def test_deleted_target(self):
        target = self.make_target(external_html())
        payload = self.payload(target)
        target.unlink()
        res = self.run_hook(payload)
        self.assertEqual(0, res.rc,
                         "acceptance_checks[9]: 削除済みでも非ゼロ終了しない\n{}".format(res))
        self.assertNotIn(BLOCK_PREFIX, res.err)

    def test_target_is_a_directory(self):
        d = self.make_dir(self.IN_SCOPE_DIR)
        weird = d / "handout.html"
        weird.mkdir()
        res = self.run_hook(self.payload(weird))
        self.assertEqual(0, res.rc, "ディレクトリを指されても落とさない\n{}".format(res))
        self.assertNotIn(BLOCK_PREFIX, res.err)

    @unittest.skipIf(os.geteuid() == 0, "root では権限不足を再現できない")
    def test_permission_denied(self):
        target = self.make_target(external_html())
        os.chmod(str(target), 0o000)
        self.addCleanup(os.chmod, str(target), stat.S_IRUSR | stat.S_IWUSR)
        res = self.run_hook(self.payload(target))
        self.assertEqual(0, res.rc, "権限不足は exit0\n{}".format(res))
        self.assertNotIn(BLOCK_PREFIX, res.err)

    def test_undecodable_bytes(self):
        """UTF-8 として読めないファイルも hook を落とさない (検査不能側)。"""
        d = self.make_dir(self.IN_SCOPE_DIR)
        target = d / "handout.html"
        target.write_bytes(b"\xff\xfe<html>\x80\x81</html>")
        res = self.run_hook(self.payload(target))
        self.assertIn(res.rc, (0, 2),
                      "検査不能なら 0、判定できたなら 2。それ以外の exit code は契約に無い\n{}".format(res))
        self.assertNotIn("Traceback", res.err)
