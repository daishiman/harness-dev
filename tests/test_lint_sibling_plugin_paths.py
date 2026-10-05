"""lint-sibling-plugin-paths.py の検出と除外の回帰テスト。

install 先 (<cache>/<marketplace>/<plugin>/<version>/) では `<plugin root>/..` が兄弟 plugin に
届かない。親ディレクトリ起点の兄弟参照を拾う lint 自体が腐らないよう、検出する 4 形と
許容する注記・rubric_refs・自 plugin 名・対象外ファイルを pytest で固定する。

import 経路: dash 入り script のため importlib.util.spec_from_file_location を使う。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lint-sibling-plugin-paths.py"
SPEC = importlib.util.spec_from_file_location("lint_sibling_plugin_paths", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)

NAMES = ["alpha", "beta", "beta-lint"]
PATTERNS = MOD.compile_patterns(NAMES)


def kinds(text: str, self_name: str = "alpha") -> list[tuple[str, str]]:
    return [(f.kind, f.sibling) for f in MOD.scan_text(text, self_name, PATTERNS)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("script_refs:\n  - ../../../beta/scripts/run.py\n", [("dotdot", "beta")]),
        ('GOV="$(dirname "$PLUGIN_ROOT")/beta-lint"\n', [("dirname", "beta-lint")]),
        ('P = Path(__file__).resolve().parents[2] / "beta" / "x.json"\n', [("pyparent", "beta")]),
        ('p = os.path.join(HERE, "..", "beta", "x.json")\n', [("osjoin", "beta")]),
    ],
)
def test_detects_each_parent_relative_form(text, expected):
    assert kinds(text) == expected


def test_pyparent_spanning_lines_reports_sibling_line():
    text = 'X = (\n    Path(__file__).resolve().parents[4]\n    / "beta"\n    / "scripts"\n)\n'
    findings = MOD.scan_text(text, "alpha", PATTERNS)
    assert [(f.kind, f.sibling, f.line) for f in findings] == [("pyparent", "beta", 3)]


def test_longest_name_wins():
    # `beta-lint` を `beta` で部分一致させない。
    assert kinds("../beta-lint/scripts/x.py\n") == [("dotdot", "beta-lint")]


@pytest.mark.parametrize(
    "text",
    [
        # 自 plugin 名は兄弟参照ではない。
        "../../alpha/scripts/x.py\n",
        # editor 向けの注記は runtime が解決しない。
        '  "$schema": "../../beta/schemas/x.schema.json",\n',
        "# 正本スキーマ: ../beta/references/x.schema.json\n",
        # rubric_refs は lint-rubric-refs-exist.py の別契約。
        "rubric_refs:\n  - skills/a/rubric.json\n  - ../beta/skills/r/rubric.json\n",
        # 推奨する書き方は検出しない。
        "path: plugin:beta/plugin-composition.yaml\n",
        "$(python3 ${PLUGIN_ROOT}/scripts/extract-plugin-root.py beta)/scripts/x.py\n",
        "reference_refs:\n  - plugins/beta/references/x.md\n",
        'REPO_ROOT / "plugins" / "beta" / "x.py"\n',
    ],
)
def test_allowed_forms_are_not_reported(text):
    assert kinds(text) == []


def test_list_after_other_key_is_still_reported():
    text = "rubric_refs:\n  - skills/a/rubric.json\nscript_refs:\n  - ../beta/x.py\n"
    assert kinds(text) == [("dotdot", "beta")]


def _make_repo(tmp_path: Path) -> Path:
    for name in ("alpha", "beta"):
        manifest = tmp_path / "plugins" / name / ".claude-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": name}), encoding="utf-8")
    return tmp_path


def test_scan_skips_docs_tests_and_eval_log(tmp_path):
    root = _make_repo(tmp_path)
    plugin = root / "plugins" / "alpha"
    bad = "see ../beta/scripts/x.py\n"
    for rel in ("README.md", "CHANGELOG.md", "EVALS.json", "tests/t.py", "eval-log/x.md", "a.png"):
        target = plugin / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(bad, encoding="utf-8")
    assert MOD.scan(root) == []

    (plugin / "skills" / "s").mkdir(parents=True)
    (plugin / "skills" / "s" / "SKILL.md").write_text(bad, encoding="utf-8")
    findings = MOD.scan(root)
    assert [(f.path, f.line, f.sibling) for f in findings] == [
        ("plugins/alpha/skills/s/SKILL.md", 1, "beta")
    ]


def test_main_exit_codes(tmp_path, capsys):
    root = _make_repo(tmp_path)
    assert MOD.main(["--root", str(root)]) == 0
    (root / "plugins" / "alpha" / "x.yaml").write_text("p: ../beta/x\n", encoding="utf-8")
    assert MOD.main(["--root", str(root)]) == 1
    assert "plugins/alpha/x.yaml:1 [dotdot] beta" in capsys.readouterr().err
    assert MOD.main(["--root", str(tmp_path / "missing")]) == 2


def test_repository_has_no_parent_relative_sibling_refs():
    findings = MOD.scan(ROOT)
    assert findings == [], "\n".join(f"{f.path}:{f.line} {f.sibling}" for f in findings)
