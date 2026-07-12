"""lint-readme-plugin-root-portability.py の検出ロジック回帰テスト。

README の bash/sh コードフェンスに install 位置依存の壊れやすい記法
(裸 $CLAUDE_PLUGIN_ROOT / repo 相対直書き / os.environ 添字) が紛れ込む
再発を封じる lint そのものが腐らないよう、許可/禁止/走査/除外の各分岐を
pytest で機械保証する。CI の `python3 -m pytest tests/ -q`
(harness-creator-kit-ci.yml) が本ファイルを自動的に拾う。

検証する不変条件:
  ①裸一次手順 → FAIL 検出   ②fallback 形 → PASS
  ③開発者補足注記付き裸変数 → PASS   ④repo 相対直書き → FAIL
  ⑤os.environ["..."] → FAIL   ⑥引用フェンス (> ```bash) 内の裸変数 → 検出
  ⑦plugin.json / prompts / 散文 inline code の裸変数 → 検査対象外 (PASS)
  ⑧番号付きリスト内の 0-3 スペース字下げフェンスの裸変数/repo相対 → 検出
     (CommonMark 準拠。4スペース字下げはインデントコードブロックで走査しない)
  ⑨references/*-setup.md (setup 手順) → 走査対象 /
     *setup*.md 命名でない reference (LLM/開発者向け) → 対象外

import 経路: dash 入り script のため importlib.util.spec_from_file_location
(test_plugin_lint_coverage.py のパターンに倣う)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lint-readme-plugin-root-portability.py"
SPEC = importlib.util.spec_from_file_location(
    "lint_readme_plugin_root_portability", SCRIPT
)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def kinds(text: str, plugin: str = "demo") -> list[str]:
    """検出された違反種別のリスト。"""
    return [k for _lineno, k, _snip in MOD.check_readme_text(text, plugin)]


# --------------------------------------------------------------------------
# 単一パターンの検出/許可
# --------------------------------------------------------------------------
class TestPatternDetection:
    def test_bare_var_primary_step_fails(self):
        # ① 一次手順の裸 $CLAUDE_PLUGIN_ROOT (fallback も開発者注記も無い) → FAIL
        text = '```bash\npython3 "$CLAUDE_PLUGIN_ROOT/lib/foo.py"\n```\n'
        assert kinds(text) == ["bare-var"]

    def test_fallback_form_passes(self):
        # ② fallback 形 → PASS
        text = '```bash\npython3 "${CLAUDE_PLUGIN_ROOT:-plugins/demo}/lib/foo.py"\n```\n'
        assert kinds(text) == []

    def test_fallback_var_assignment_passes(self):
        # ② P= への代入 + "$P/..." 参照も PASS
        text = (
            "```bash\n"
            'P="${CLAUDE_PLUGIN_ROOT:-plugins/demo}"\n'
            'python3 "$P/lib/foo.py"\n'
            "```\n"
        )
        assert kinds(text) == []

    def test_braced_bare_var_fails(self):
        # ${CLAUDE_PLUGIN_ROOT}/ (fallback でない波括弧) も裸として検出
        text = '```bash\npython3 "${CLAUDE_PLUGIN_ROOT}/lib/foo.py"\n```\n'
        assert kinds(text) == ["bare-var"]

    def test_dev_note_in_fence_allows_bare_var(self):
        # ③ 同一フェンス内に開発者補足注記があれば裸変数を許可 (降格温存)
        text = (
            "```bash\n"
            "# 開発者向け (clone 直叩き)。$CLAUDE_PLUGIN_ROOT 未定義なら壊れる:\n"
            'python3 "$CLAUDE_PLUGIN_ROOT/lib/foo.py"\n'
            "```\n"
        )
        assert kinds(text) == []

    def test_dev_note_does_not_rescue_repo_relative(self):
        # 開発者注記があっても repo 相対直書きは救済しない (fallback 形が必須)
        text = (
            "```bash\n"
            "# 開発者向け (clone 直叩き):\n"
            "python3 plugins/demo/lib/foo.py\n"
            "```\n"
        )
        assert kinds(text) == ["repo-relative"]

    def test_repo_relative_direct_fails(self):
        # ④ repo 相対直書き → FAIL
        text = "```bash\npython3 plugins/demo/lib/setup_doctor.py --init\n```\n"
        assert kinds(text) == ["repo-relative"]

    def test_repo_relative_with_leading_dotslash_fails(self):
        text = "```bash\npython3 ./plugins/demo/lib/setup_doctor.py\n```\n"
        assert kinds(text) == ["repo-relative"]

    def test_repo_relative_with_python_option_fails(self):
        text = "```bash\npython3 -u plugins/demo/lib/setup_doctor.py\n```\n"
        assert kinds(text) == ["repo-relative"]

    def test_repo_relative_with_uv_run_python_fails(self):
        text = "```bash\nuv run python plugins/demo/lib/setup_doctor.py\n```\n"
        assert kinds(text) == ["repo-relative"]

    def test_bare_root_alias_then_path_fails(self):
        text = (
            "```bash\n"
            'P="$CLAUDE_PLUGIN_ROOT"\n'
            'python3 "$P/lib/foo.py"\n'
            "```\n"
        )
        assert kinds(text) == ["bare-var-alias"]

    def test_fallback_alias_then_path_passes(self):
        text = (
            "```bash\n"
            'P="${CLAUDE_PLUGIN_ROOT:-plugins/demo}"\n'
            'python3 "$P/lib/foo.py"\n'
            "```\n"
        )
        assert kinds(text) == []

    def test_os_environ_subscript_fails(self):
        # ⑤ os.environ["..."] → FAIL
        text = (
            "```python\n"
            'root = os.environ["CLAUDE_PLUGIN_ROOT"]\n'
            "```\n"
        )
        assert kinds(text) == ["os-environ-subscript"]

    def test_os_environ_get_passes(self):
        text = (
            "```python\n"
            'root = os.environ.get("CLAUDE_PLUGIN_ROOT") or "plugins/demo"\n'
            "```\n"
        )
        assert kinds(text) == []

    def test_os_environ_subscript_in_bash_heredoc_fails(self):
        # bash heredoc 内の python でも os.environ 添字を検出
        text = (
            "```bash\n"
            "python3 - <<'PY'\n"
            'import os\n'
            'root = os.environ["CLAUDE_PLUGIN_ROOT"]\n'
            "PY\n"
            "```\n"
        )
        assert kinds(text) == ["os-environ-subscript"]


# --------------------------------------------------------------------------
# フェンス走査 (引用/非引用) と対象外
# --------------------------------------------------------------------------
class TestFenceScanning:
    def test_quoted_fence_bare_var_detected(self):
        # ⑥ 引用付きフェンス (> ```bash) 内の裸変数も走査する
        text = (
            "> ```bash\n"
            '> python3 "$CLAUDE_PLUGIN_ROOT/lib/foo.py"\n'
            "> ```\n"
        )
        assert kinds(text) == ["bare-var"]

    def test_quoted_fence_dev_note_allows_bare_var(self):
        # 引用フェンス内でも開発者注記があれば裸変数を許可 (mf-kessai の実パターン)
        text = (
            "> ```bash\n"
            "> # 開発者向け (clone 直叩き)。$CLAUDE_PLUGIN_ROOT 未定義なら壊れる:\n"
            '> python3 "$CLAUDE_PLUGIN_ROOT/lib/foo.py"\n'
            "> ```\n"
        )
        assert kinds(text) == []

    def test_prose_inline_code_not_scanned(self):
        # ⑦ 散文 (blockquote / 段落) の inline code はコピペ対象フェンスでないため対象外
        text = (
            "> これは `python3 plugins/demo/foo.py` という手打ち例の説明です。\n"
            '通常の段落に `"$CLAUDE_PLUGIN_ROOT/lib/foo.py"` を書いても検査しません。\n'
        )
        assert kinds(text) == []

    def test_non_shell_fence_ignored_for_shell_patterns(self):
        # json / 言語なしフェンス内の repo 相対風文字列は shell パターンとして検査しない
        text = '```json\n{ "cmd": "python3 plugins/demo/foo.py" }\n```\n'
        assert kinds(text) == []

    def test_comment_mention_of_var_not_flagged(self):
        # コメント中の説明的言及 ($CLAUDE_PLUGIN_ROOT 未定義…, 直後が空白) は裸パス使用でない
        text = (
            "```bash\n"
            "# $CLAUDE_PLUGIN_ROOT 未定義なら repo 直下相対へ落ちる:\n"
            'P="${CLAUDE_PLUGIN_ROOT:-plugins/demo}"\n'
            'python3 "$P/lib/foo.py"\n'
            "```\n"
        )
        assert kinds(text) == []


class TestIndentedFences:
    """番号付きリスト内の字下げフェンス走査 (CommonMark: 開始 fence は 0-3 スペース許容)。

    行頭固定の正規表現だと `3. 手順:` の下に 3 スペース字下げした ` ```bash ` が
    丸ごと不可視になり、壊れるコマンドが素通りする (japanpost-api-setup.md で実在)。
    """

    def test_three_space_indented_fence_bare_var_detected(self):
        # ⑧ リスト内 3 スペース字下げフェンスの裸変数を検出する
        text = (
            "3. 手順:\n"
            "   ```bash\n"
            '   python3 "$CLAUDE_PLUGIN_ROOT/lib/foo.py"\n'
            "   ```\n"
        )
        assert kinds(text) == ["bare-var"]

    def test_three_space_indented_fence_repo_relative_detected(self):
        text = (
            "3. 手順:\n"
            "   ```bash\n"
            "   python3 plugins/demo/lib/foo.py\n"
            "   ```\n"
        )
        assert kinds(text) == ["repo-relative"]

    def test_indented_fence_fallback_form_passes(self):
        text = (
            "3. 手順:\n"
            "   ```bash\n"
            '   python3 "${CLAUDE_PLUGIN_ROOT:-plugins/demo}/lib/foo.py"\n'
            "   ```\n"
        )
        assert kinds(text) == []

    def test_four_space_indent_is_not_a_fence(self):
        # 4 スペース字下げの ``` は CommonMark ではフェンスでない (インデントコードブロック)。
        # フェンスとして開かないので中身は走査されない (desync 回避のため境界を 0-3 に固定)。
        text = (
            "本文:\n"
            "    ```bash\n"
            '    python3 "$CLAUDE_PLUGIN_ROOT/lib/foo.py"\n'
            "    ```\n"
        )
        assert kinds(text) == []


# --------------------------------------------------------------------------
# repo 単位: distributable / allowlist / 実 repo 統合
# --------------------------------------------------------------------------
def _make_plugin(root: Path, name: str, readme: str, distributable=None) -> None:
    pdir = root / "plugins" / name
    (pdir / ".claude-plugin").mkdir(parents=True)
    manifest: dict = {"name": name}
    if distributable is not None:
        manifest["distributable"] = distributable
    (pdir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (pdir / "README.md").write_text(readme, encoding="utf-8")


class TestRepoScope:
    def test_distributable_false_skipped(self, tmp_path):
        # distributable:false の plugin (clone 専用) は repo 相対で正しいため検査対象外
        root = tmp_path / "repo"
        (root / "plugins").mkdir(parents=True)
        _make_plugin(
            root,
            "devtool",
            "```bash\npython3 plugins/devtool/foo.py\n```\n",
            distributable=False,
        )
        errors, report = MOD.check_repo(root)
        assert errors == []
        assert any("skip" in line and "devtool" in line for line in report)

    def test_distributable_plugin_checked_and_fails(self, tmp_path):
        root = tmp_path / "repo"
        (root / "plugins").mkdir(parents=True)
        _make_plugin(root, "ship", "```bash\npython3 plugins/ship/foo.py\n```\n")
        errors, _ = MOD.check_repo(root)
        assert any("ship/README.md" in e and "repo-relative" in e for e in errors)

    def test_missing_distributable_defaults_to_checked(self, tmp_path):
        root = tmp_path / "repo"
        (root / "plugins").mkdir(parents=True)
        _make_plugin(root, "ship", "```bash\npython3 plugins/ship/foo.py\n```\n")
        # distributable 未指定 → 配布対象扱いで検査される
        assert MOD.is_distributable(root / "plugins" / "ship") is True


class TestAllowlist:
    def test_allowlist_suppresses_matching_violation(self, tmp_path):
        root = tmp_path / "repo"
        (root / "plugins").mkdir(parents=True)
        _make_plugin(root, "ship", "```bash\npython3 plugins/ship/foo.py\n```\n")
        allow = {("ship", "python3 plugins/ship/foo.py"): "後日是正 (fixture 理由)"}
        errors, _ = MOD.check_repo(root, allowlist=allow)
        assert errors == []

    def test_allowlist_requires_reason(self, tmp_path):
        root = tmp_path / "repo"
        (root / "plugins").mkdir(parents=True)
        _make_plugin(root, "ship", "```bash\npython3 plugins/ship/foo.py\n```\n")
        allow = {("ship", "python3 plugins/ship/foo.py"): "   "}
        errors, _ = MOD.check_repo(root, allowlist=allow)
        assert any("理由" in e for e in errors)

    def test_stale_allowlist_entry_fails(self, tmp_path):
        root = tmp_path / "repo"
        (root / "plugins").mkdir(parents=True)
        _make_plugin(root, "ship", "```bash\necho ok\n```\n")  # 違反なし
        allow = {("ship", "python3 plugins/ship/foo.py"): "もう不要のはずの理由"}
        errors, _ = MOD.check_repo(root, allowlist=allow)
        assert any("stale" in e for e in errors)

    def test_real_allowlist_reasons_nonempty(self):
        for (plugin, sig), reason in MOD.ALLOWLIST.items():
            assert str(reason).strip(), f"({plugin}, {sig}) の理由が空"


class TestRealRepoIntegration:
    def test_real_repo_passes(self):
        """実 repo の全 plugin README が合格状態であること (回帰検知)。"""
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(ROOT)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"

    def test_usage_error_on_bad_root(self, tmp_path):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 2


def _make_plugin_root(root: Path, name: str, distributable=None) -> Path:
    """plugin ディレクトリ (README + plugin.json) を作り plugin dir を返す。"""
    pdir = root / "plugins" / name
    (pdir / ".claude-plugin").mkdir(parents=True)
    manifest: dict = {"name": name}
    if distributable is not None:
        manifest["distributable"] = distributable
    (pdir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (pdir / "README.md").write_text("# ok\n", encoding="utf-8")
    return pdir


class TestSetupDocScope:
    """README だけでなく references/*-setup.md 等の setup 手順も走査対象に入ること
    (company-master 等は setup 手順を references 配下に置くため、README のみでは被覆漏れ)。
    *setup*.md 命名でない reference (LLM/開発者向け仕様) は対象外に保つこと。"""

    def test_references_setup_doc_scanned(self, tmp_path):
        root = tmp_path / "repo"
        (root / "plugins").mkdir(parents=True)
        pdir = _make_plugin_root(root, "ship")
        (pdir / "references").mkdir()
        (pdir / "references" / "keychain-setup.md").write_text(
            "```bash\npython3 plugins/ship/scripts/x.py\n```\n", encoding="utf-8"
        )
        errors, _ = MOD.check_repo(root)
        assert any(
            "references/keychain-setup.md" in e and "repo-relative" in e
            for e in errors
        )

    def test_skill_nested_setup_doc_scanned(self, tmp_path):
        root = tmp_path / "repo"
        (root / "plugins").mkdir(parents=True)
        _make_plugin_root(root, "ship")
        nested = root / "plugins" / "ship" / "skills" / "do-thing" / "references"
        nested.mkdir(parents=True)
        (nested / "oauth-setup.md").write_text(
            '```bash\npython3 "$CLAUDE_PLUGIN_ROOT/lib/x.py"\n```\n', encoding="utf-8"
        )
        errors, _ = MOD.check_repo(root)
        assert any(
            "skills/do-thing/references/oauth-setup.md" in e and "bare-var" in e
            for e in errors
        )

    def test_non_setup_reference_not_scanned(self, tmp_path):
        # *setup*.md 命名でない reference (build-steps.md 等) は Claude Code 注入文脈で
        # 実行される LLM/開発者向け仕様のため裸変数でも対象外に保つ。
        root = tmp_path / "repo"
        (root / "plugins").mkdir(parents=True)
        pdir = _make_plugin_root(root, "ship")
        (pdir / "references").mkdir()
        (pdir / "references" / "build-steps.md").write_text(
            '```bash\npython3 "$CLAUDE_PLUGIN_ROOT/lib/x.py"\n```\n', encoding="utf-8"
        )
        errors, _ = MOD.check_repo(root)
        assert errors == []

    def test_distributable_false_setup_doc_skipped(self, tmp_path):
        root = tmp_path / "repo"
        (root / "plugins").mkdir(parents=True)
        pdir = _make_plugin_root(root, "devtool", distributable=False)
        (pdir / "references").mkdir()
        (pdir / "references" / "x-setup.md").write_text(
            "```bash\npython3 plugins/devtool/scripts/x.py\n```\n", encoding="utf-8"
        )
        errors, report = MOD.check_repo(root)
        assert errors == []
        assert any("skip" in line and "x-setup.md" in line for line in report)

    def test_plugin_dir_derivation_for_nested_doc(self, tmp_path):
        root = tmp_path / "repo"
        doc = root / "plugins" / "ship" / "skills" / "s" / "references" / "a-setup.md"
        assert MOD.plugin_dir_of(root, doc) == root / "plugins" / "ship"

    def test_iter_target_docs_collects_readme_and_setup(self, tmp_path):
        root = tmp_path / "repo"
        (root / "plugins").mkdir(parents=True)
        pdir = _make_plugin_root(root, "ship")
        (pdir / "references").mkdir()
        (pdir / "references" / "keychain-setup.md").write_text("x\n", encoding="utf-8")
        (pdir / "references" / "architecture.md").write_text("x\n", encoding="utf-8")
        docs = {p.relative_to(root).as_posix() for p in MOD.iter_target_docs(root)}
        assert "plugins/ship/README.md" in docs
        assert "plugins/ship/references/keychain-setup.md" in docs
        # setup 命名でない reference は収集しない
        assert "plugins/ship/references/architecture.md" not in docs
