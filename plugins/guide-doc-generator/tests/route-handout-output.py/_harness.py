"""C19 route-handout-output.py の受入テスト共通ヘルパ (P04-C19-01)。

方針:
- 用途種別の語彙 (lecture / agenda / ...) をテストへ列挙しない。doc_type も dir_token も
  語彙正本 config/handout-purposes.json (owner: C23) を読んで機械的に導出する。
  script-brief-C19.json acceptance_checks #3 が「語彙リテラル 0 件」を script へ要求している
  以上、その判定基準を持つテスト側が語彙を焼き付けたら基準が壊れる。
- 実ファイルシステムへの書き込みは全て tempfile.TemporaryDirectory 内に閉じる。
  既定出力先 (config/handout-output.json の default_out_dir) を使う経路は --check-only か、
  fixture ツリー (scripts + config を tmp へ複製したもの) 経由でしか実行しない。
- 実装が未存在でも import 例外にしない。require_script() が「実装が無い」という
  診断可能な失敗 (failure) として赤を出す。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

# tests/route-handout-output.py/ -> tests -> guide-doc-generator -> plugins -> repo root
TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TESTS_DIR.parents[1]
REPO_ROOT = TESTS_DIR.parents[3]

SCRIPT = PLUGIN_ROOT / "scripts" / "route-handout-output.py"
PRESET_SCRIPT = PLUGIN_ROOT / "scripts" / "resolve-handout-preset.py"
CATALOG_RELPATH = "config/handout-purposes.json"
CATALOG = PLUGIN_ROOT / CATALOG_RELPATH
OUTPUT_CONFIG_RELPATH = "config/handout-output.json"
OUTPUT_CONFIG = PLUGIN_ROOT / OUTPUT_CONFIG_RELPATH

# 他 component の成果物 (AC-C19-20 の writer 一意性突き合わせで読むだけ)。
RENDER_SCRIPT = PLUGIN_ROOT / "scripts" / "render-handout.py"          # C11
EMBED_SCRIPT = PLUGIN_ROOT / "scripts" / "embed-assets.py"             # C13
BUILD_SKILL = PLUGIN_ROOT / "skills" / "run-handout-build" / "SKILL.md"  # C01
VERIFY_LANGUAGE_SCRIPT = PLUGIN_ROOT / "scripts" / "verify-handout-language.py"  # C18

STDERR_PREFIX = "[route-handout-output]"

# 同梱 4 点と writer の割り当て。正本は script-brief-C19.json bundle_writers (P03 Y-04)。
# 固定名と writer id はここ 1 箇所にだけ置く。
BUNDLE_WRITERS = (
    ("handout.html", "C11"),
    ("handout-config.json", "C19"),
    ("assets", "C19"),
    ("README.md", "C01"),
)
BUNDLE_NAMES = tuple(name for name, _ in BUNDLE_WRITERS)

# 通常実行 (mkdir 直後) で present であることが確定している 2 点 (algorithm 9 / 9b / 9c)。
SELF_WRITTEN = ("handout-config.json", "assets")

ROUTE_MARKER = ".handout-route.json"
PLACED_CONFIG_NAME = "handout-config.json"

# algorithm 3: ディレクトリ名の日付は構成データの date の純変換。
FIXTURE_DATE = "2026/08/17"
FIXTURE_DATE_DIR = "2026-08-17"

# algorithm 6 の解決段を --json-report / stdout から同定するための語 (どれか 1 つが現れればよい)。
STAGE_TOKENS = {
    "argv": ("--out-dir", "out_dir", "out-dir"),
    "env": ("HB_OUT_DIR",),
    "config": ("default_out_dir", "handout-output.json", "config"),
}


class MissingArtifact(AssertionError):
    """実装成果物がまだ存在しないことを示す (P04 では赤が正しい状態)。"""


def require_script(tc: unittest.TestCase) -> Path:
    if not SCRIPT.is_file():
        tc.fail(
            "実装が未存在: {} (P04 時点ではこの失敗が期待値。P05 で解消する)".format(SCRIPT)
        )
    return SCRIPT


def require_file(tc: unittest.TestCase, path: Path, owner: str) -> Path:
    if not path.is_file():
        tc.fail("依存成果物が未存在: {} (owner: {})".format(path, owner))
    return path


def clean_env(**overrides) -> dict:
    """ユーザー環境の既定出力先が漏れ込まないようにした実行環境。"""
    env = dict(os.environ)
    for key in ("HB_OUT_DIR", "HB_ROOT", "CLAUDE_PLUGIN_ROOT"):
        env.pop(key, None)
    env["PYTHONIOENCODING"] = "utf-8"
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return env


def run(args, env=None, cwd=None, script: Path | None = None, stdin_data: str | None = None):
    """script を subprocess で起動する。戻り値は CompletedProcess (bytes)。"""
    cmd = [sys.executable, str(script or SCRIPT), *[str(a) for a in args]]
    return subprocess.run(
        cmd,
        input=(stdin_data or "").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env if env is not None else clean_env(),
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        timeout=120,
    )


def out_text(proc) -> str:
    return proc.stdout.decode("utf-8")


def err_text(proc) -> str:
    return proc.stderr.decode("utf-8")


def describe(proc) -> str:
    return "exit={}\n--- stdout ---\n{}\n--- stderr ---\n{}".format(
        proc.returncode, out_text(proc)[:4000], err_text(proc)[:4000]
    )


# --------------------------------------------------------------------------
# 語彙正本 (C23) からの機械導出
# --------------------------------------------------------------------------


def load_catalog(tc: unittest.TestCase) -> dict:
    require_file(tc, CATALOG, "C23")
    try:
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - 赤の診断用
        tc.fail("語彙正本が JSON として読めない: {} ({})".format(CATALOG, exc))
    if "vocabulary" not in data:
        tc.fail("語彙正本に 'vocabulary' が無い: {}".format(CATALOG))
    return data


def vocabulary_entries(tc: unittest.TestCase) -> list:
    entries = load_catalog(tc)["vocabulary"]
    if not isinstance(entries, list) or not entries:
        tc.fail("vocabulary が 1 件以上の配列でない: {}".format(CATALOG))
    return entries


def any_doc_type(tc: unittest.TestCase) -> str:
    """語彙正本の先頭 slug。テストへ語彙を書かないための唯一の取得口。"""
    return vocabulary_entries(tc)[0]["slug"]


def dir_token_of(tc: unittest.TestCase, slug: str) -> str:
    for entry in vocabulary_entries(tc):
        if entry["slug"] == slug:
            return entry.get("dir_token", slug)
    tc.fail("語彙正本に slug が無い: {}".format(slug))


def name_prefix(tc: unittest.TestCase, doc_type: str | None = None) -> str:
    """<date>-<dir_token>- までの固定部 (slug 部を切り出すための境界)。"""
    slug = doc_type or any_doc_type(tc)
    return "{}-{}-".format(FIXTURE_DATE_DIR, dir_token_of(tc, slug))


def slug_part(tc: unittest.TestCase, dirname: str, doc_type: str | None = None) -> str:
    prefix = name_prefix(tc, doc_type)
    if not dirname.startswith(prefix):
        tc.fail("ディレクトリ名 {!r} が {!r} で始まっていない".format(dirname, prefix))
    return dirname[len(prefix):]


def unknown_doc_type(tc: unittest.TestCase) -> str:
    """語彙正本のどの slug / alias / dir_token とも一致しない値を機械生成する。"""
    known = set()
    for entry in vocabulary_entries(tc):
        known.add(entry.get("slug"))
        known.add(entry.get("dir_token"))
        known.update(entry.get("aliases") or [])
    candidate = "not-a-purpose"
    suffix = 0
    while candidate in known:
        suffix += 1
        candidate = "not-a-purpose-{}".format(suffix)
    return candidate


# --------------------------------------------------------------------------
# 正規化済み構成データ fixture
# --------------------------------------------------------------------------


def normalized_config(tc: unittest.TestCase, **overrides) -> dict:
    """C12 --normalize 済み相当の構成データ。

    C19 が読むのは date / doc_type / title / subject_slug と正規化マーカーだけ (brief
    dependencies.reads)。正規化マーカーの正本は C12 の provenance.normalized_by。
    """
    payload = {
        "schema_version": "1.0",
        "title": "テスト資料",
        "subject_slug": "route-fixture",
        "date": FIXTURE_DATE,
        "doc_type": any_doc_type(tc),
        "purpose": "C19 の出力先解決を検査するための固定入力である",
        "background": "P04 の受入テストが実装より先に判定基準を固定するために置く",
        "goal": "出力先ディレクトリの命名と同梱 4 点の検査契約を確定する",
        "reader": "P05 の実装担当",
        "prior_knowledge_level": "basic",
        "essential_problem": "出力先の命名規則が二重定義されると変更が片方に取り残される",
        "duration": "30分",
        "sections": [],
        "provenance": {
            "normalized_by": "validate-handout-config.py",
            "schema_version": "1.0",
            "date_source": "config",
        },
    }
    payload.update(overrides)
    for key, value in list(payload.items()):
        if value is _OMIT:
            del payload[key]
    return payload


class _Omit:
    def __repr__(self):  # pragma: no cover - 診断用
        return "<omit>"


_OMIT = _Omit()
OMIT = _OMIT


def canonical_json_bytes(payload) -> bytes:
    """C12 の encoding_rules と同じ正準表現 (--place-config のバイト一致検査の基準)。"""
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def write_config(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(payload))
    return path


def config_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# stdout / --json-report の読み取り (書式に過度に依存しない緩い解釈)
# --------------------------------------------------------------------------


def resolved_path(tc: unittest.TestCase, proc) -> Path:
    """stdout 1 行目 = 解決した出力先の絶対パス (brief stdout 契約)。"""
    lines = out_text(proc).splitlines()
    if not lines:
        tc.fail("stdout が空 (解決した出力先の絶対パス 1 行が必要)\n" + describe(proc))
    candidate = lines[0].strip()
    if not candidate.startswith("/"):
        tc.fail(
            "stdout 1 行目が絶対パスでない: {!r}\n{}".format(candidate, describe(proc))
        )
    return Path(candidate)


def bundle_lines(tc: unittest.TestCase, proc) -> dict:
    """同梱 4 点それぞれの present/absent 行を name -> 行文字列で返す。"""
    text = out_text(proc)
    found = {}
    for name in BUNDLE_NAMES:
        matches = [
            line
            for line in text.splitlines()[1:]
            if name in line and not _is_other_bundle_line(name, line)
        ]
        if not matches:
            tc.fail(
                "stdout に同梱物 '{}' の present/absent 行が無い\n{}".format(
                    name, describe(proc)
                )
            )
        found[name] = matches[0]
    return found


def _is_other_bundle_line(name: str, line: str) -> bool:
    """'handout.html' 行と 'handout-config.json' 行の取り違えを防ぐ。"""
    others = [n for n in BUNDLE_NAMES if n != name and name not in n]
    return any(other in line and name not in other for other in others)


def assert_bundle_state(tc: unittest.TestCase, proc, name: str, state: str):
    line = bundle_lines(tc, proc)[name]
    opposite = "absent" if state == "present" else "present"
    tc.assertIn(state, line, "{} の状態行: {!r}\n{}".format(name, line, describe(proc)))
    tc.assertNotIn(
        opposite, line, "{} の状態行が両方の語を含む: {!r}".format(name, line)
    )


def flatten_strings(payload) -> list:
    """JSON レポートの構造を仮定せず、含まれる文字列を全て平坦化する。"""
    acc = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                acc.append(str(key))
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif node is not None and not isinstance(node, bool):
            acc.append(str(node))

    walk(payload)
    return acc


def load_report(tc: unittest.TestCase, path: Path) -> dict:
    if not path.is_file():
        tc.fail("--json-report が書かれていない: {}".format(path))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        tc.fail("--json-report が JSON として読めない: {} ({})".format(path, exc))


def assert_stage_recorded(tc: unittest.TestCase, blob: str, stage: str):
    tokens = STAGE_TOKENS[stage]
    tc.assertTrue(
        any(token in blob for token in tokens),
        "解決段 '{}' が記録されていない (期待する語のいずれか: {})\n{}".format(
            stage, tokens, blob[:2000]
        ),
    )


# --------------------------------------------------------------------------
# fixture ツリー (既定出力先の差し替えを env に頼らず行うための複製)
# --------------------------------------------------------------------------


def make_fixture_tree(
    tc: unittest.TestCase,
    tmp: Path,
    mutate_output_config=None,
    include_preset: bool = True,
    include_output_config: bool = True,
) -> Path:
    """scripts/ と config/ を tmp へ複製した plugin root を作る。

    script が自身の位置から相対で config と C23 を解決する (brief dependencies /
    sanctioned_access) ため、この複製ツリー越しに起動すれば既定出力先も C23 の在否も
    実ツリーを 1 バイトも触らずに差し替えられる。
    """
    require_script(tc)
    root = tmp / "plugin-root"
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir(parents=True, exist_ok=True)

    shutil.copy2(SCRIPT, root / "scripts" / SCRIPT.name)
    if include_preset:
        require_file(tc, PRESET_SCRIPT, "C23")
        shutil.copy2(PRESET_SCRIPT, root / "scripts" / PRESET_SCRIPT.name)

    for src in (CATALOG,):
        require_file(tc, src, "C23")
        shutil.copy2(src, root / "config" / src.name)

    for extra in ("handout-sections.json", "handout-parts.json"):
        candidate = PLUGIN_ROOT / "config" / extra
        if candidate.is_file():
            shutil.copy2(candidate, root / "config" / extra)

    manifest_src = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    if manifest_src.is_file():
        shutil.copy2(manifest_src, root / ".claude-plugin" / "plugin.json")
    else:
        (root / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "guide-doc-generator"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if include_output_config:
        require_file(tc, OUTPUT_CONFIG, "C19 / packaging")
        data = json.loads(OUTPUT_CONFIG.read_text(encoding="utf-8"))
        if mutate_output_config is not None:
            mutate_output_config(data)
        (root / OUTPUT_CONFIG_RELPATH).write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return root


def fixture_script(root: Path) -> Path:
    return root / "scripts" / SCRIPT.name


def tree_snapshot(root: Path) -> dict:
    """ディレクトリ配下の相対パス -> バイト列 (無変更検査用)。"""
    snapshot = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        snapshot[rel] = path.read_bytes() if path.is_file() else b"<dir>"
    return snapshot


def read_source(tc: unittest.TestCase) -> str:
    require_script(tc)
    return SCRIPT.read_text(encoding="utf-8")
