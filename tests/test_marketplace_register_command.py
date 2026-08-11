# /// script
# requires-python = ">=3.11"
# ///
"""`/marketplace-register` command が説明する marketplace 実体との drift を止める。

この command は「どのファイルが何を保証するか」を手順として書き下したもので、
実体 (2 枚の marketplace.json・plugins symlink・fail-closed 判定名) がずれると
読者を誤った操作へ導く。frontmatter 健全性だけでなく、本文が名指ししている
事実そのものを実体と突き合わせる。
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMD = ROOT / "plugins" / "harness-creator" / "commands" / "marketplace-register.md"
LOCAL_MK = ROOT / "marketplaces" / "local" / ".claude-plugin" / "marketplace.json"
PUBLIC_MK = ROOT / ".claude-plugin" / "marketplace.json"


def _frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "frontmatter が無い"
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


class MarketplaceRegisterCommandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = CMD.read_text(encoding="utf-8")
        cls.fm = _frontmatter(cls.text)

    def test_frontmatter_contract(self) -> None:
        self.assertEqual(self.fm.get("name"), "marketplace-register")
        self.assertEqual(self.fm.get("kind"), "command")
        for key in ("description", "argument-hint", "allowed-tools", "version", "owner", "since"):
            self.assertTrue(self.fm.get(key), f"{key} が空")
        # 案内専用なので書込 tool を持たないこと (手順を勝手に実行しない)
        tools = {t.strip() for t in self.fm["allowed-tools"].split(",")}
        self.assertEqual(tools, {"Read", "Bash"})

    def test_referenced_scripts_exist(self) -> None:
        for rel in re.findall(r"\$\{HARNESS_ROOT:-\.\}/([\w./-]+\.py)", self.text):
            self.assertTrue((ROOT / rel).is_file(), f"本文が参照する {rel} が無い")

    def test_marketplace_names_match_reality(self) -> None:
        local = json.loads(LOCAL_MK.read_text(encoding="utf-8"))
        public = json.loads(PUBLIC_MK.read_text(encoding="utf-8"))
        self.assertEqual(local["name"], "harness-local")
        self.assertEqual(public["name"], "skills")
        # ローカルは全 plugin、公開は distributable のみ = ローカルが真に広いこと
        self.assertGreater(len(local["plugins"]), len(public["plugins"]))

    def test_source_is_marketplace_relative(self) -> None:
        """本文の「`../` で遡ると source: Invalid input」を実体側で担保する。"""
        for mk in (LOCAL_MK, PUBLIC_MK):
            for entry in json.loads(mk.read_text(encoding="utf-8"))["plugins"]:
                src = entry["source"]
                self.assertIsInstance(src, str)
                self.assertTrue(src.startswith("./plugins/"), f"{mk.name}: {src}")
                self.assertNotIn("..", src)

    def test_plugins_symlink_shape(self) -> None:
        link = ROOT / "marketplaces" / "local" / "plugins"
        self.assertTrue(link.is_symlink(), "marketplaces/local/plugins が symlink でない")
        self.assertEqual(str(link.readlink()), "../../plugins")

    def test_fail_closed_guards_named_in_doc_exist(self) -> None:
        guard = (ROOT / "scripts" / "validate-plugin-completeness.py").read_text(encoding="utf-8")
        for token in ("MK-004", "NEVER_DISTRIBUTE"):
            self.assertIn(token, guard, f"本文が名指しする {token} が実体に無い")

    def test_release_script_supports_documented_flags(self) -> None:
        release = (ROOT / "scripts" / "build-plugin-release.py").read_text(encoding="utf-8")
        for flag in ("--install", "--project-dir", "--check", "--only"):
            self.assertIn(flag, release, f"本文が案内する {flag} が script に無い")


if __name__ == "__main__":
    unittest.main()
