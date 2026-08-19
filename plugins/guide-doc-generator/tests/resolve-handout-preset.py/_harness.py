"""C23 resolve-handout-preset.py の受入テスト共通ヘルパ (P04-C23-01)。

方針:
- 用途語彙 (lecture / guide / report ...) をテストへ列挙しない。期待値は語彙正本
  config/handout-purposes.json から機械的に導出し、CLI 出力とカタログの一致を検査する。
  例外は AC が名指しする最小限の slug (lecture) のみで、LECTURE_SLUG に 1 箇所だけ置く。
- 実装が未存在でも import 例外にしない。require_script() が「実装が無い」という
  診断可能な失敗として赤を出す。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

# tests/resolve-handout-preset.py/ -> tests -> guide-doc-generator -> plugins -> repo root
TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TESTS_DIR.parents[1]
REPO_ROOT = TESTS_DIR.parents[3]

SCRIPT = PLUGIN_ROOT / "scripts" / "resolve-handout-preset.py"
CATALOG_RELPATH = "config/handout-purposes.json"
CATALOG = PLUGIN_ROOT / CATALOG_RELPATH
SECTIONS_FILE = PLUGIN_ROOT / "config" / "handout-sections.json"
PARTS_FILE = PLUGIN_ROOT / "config" / "handout-parts.json"
# IMG の役の値域の正本 (thresholds.min_images_per_main_section.role_split.roles)。
VISUAL_POLICY_FILE = PLUGIN_ROOT / "config" / "handout-visual-policy.json"
SCHEMA_FILE = PLUGIN_ROOT / "schemas" / "handout-config.schema.json"
MANIFEST_FILE = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"

# AC-C23-R21-53 / 57 が名指しする唯一の用途 slug。ここ以外へ用途語彙を書かない。
LECTURE_SLUG = "lecture"

# preset オブジェクトの許可キー (script-brief-C23.json structural_guarantee)。
# 契約は「閉じた allowlist であること」であって個数ではない (P04-x-05 裁定 A)。
# 個数はこの集合からの導出値なので、テスト側も数値リテラルで固定しない。
ALLOWED_PRESET_KEYS = {
    "section_order",
    "recommended_parts",
    "notes",
    "presentation_order_variants",
    "required_document_fields",
    "granularity_defaults",  # R22 C61 / 裁定 A・C: 全 preset の必須キー
}
PRESENTATION_ORDER_KEYS = {"demo_first", "explain_first"}

# granularity_defaults の値のキー集合 (厳密一致。裁定 A・C / algorithm 4(j))。
GRANULARITY_DEFAULT_KEYS = {"detail_level", "evidence_depth"}

# 全 preset が必ず持つ必須キー (fallback を置かず catalog 検査で欠落を落とす)。
REQUIRED_PRESET_KEYS = {"section_order", "recommended_parts", "granularity_defaults"}

# AC-C23-01: 語彙は 8 件。slug そのものは列挙せず件数だけを契約として持つ。
EXPECTED_VOCABULARY_SIZE = 8


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
        tc.fail("依存データが未存在: {} (owner: {})".format(path, owner))
    return path


def clean_env(**overrides: str) -> dict:
    env = dict(os.environ)
    for key in ("HB_ROOT", "CLAUDE_PLUGIN_ROOT"):
        env.pop(key, None)
    env["PYTHONIOENCODING"] = "utf-8"
    env.update({k: v for k, v in overrides.items() if v is not None})
    return env


def run(args, env=None, cwd=None, stdin_data: str | None = None):
    """script を subprocess で起動する。戻り値は CompletedProcess (bytes)。"""
    cmd = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(
        cmd,
        input=(stdin_data or "").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env if env is not None else clean_env(),
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        timeout=60,
    )


def out_text(proc) -> str:
    return proc.stdout.decode("utf-8")


def err_text(proc) -> str:
    return proc.stderr.decode("utf-8")


def describe(proc) -> str:
    return "exit={}\n--- stdout ---\n{}\n--- stderr ---\n{}".format(
        proc.returncode, out_text(proc)[:4000], err_text(proc)[:4000]
    )


def load_catalog(tc: unittest.TestCase) -> dict:
    require_file(tc, CATALOG, "C23")
    try:
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - 赤の診断用
        tc.fail("語彙正本が JSON として読めない: {} ({})".format(CATALOG, exc))
    for key in ("vocabulary", "presets"):
        if key not in data:
            tc.fail("語彙正本に必須キー '{}' が無い: {}".format(key, CATALOG))
    return data


def vocabulary_entries(tc: unittest.TestCase, catalog: dict | None = None) -> list:
    catalog = catalog if catalog is not None else load_catalog(tc)
    entries = catalog["vocabulary"]
    if not isinstance(entries, list) or not entries:
        tc.fail("vocabulary が 1 件以上の配列でない")
    return entries


def slugs(tc: unittest.TestCase, catalog: dict | None = None) -> list:
    return [e["slug"] for e in vocabulary_entries(tc, catalog)]


def presets(tc: unittest.TestCase, catalog: dict | None = None) -> dict:
    catalog = catalog if catalog is not None else load_catalog(tc)
    return catalog["presets"]


def slug_without_variants(tc: unittest.TestCase) -> str:
    """presentation_order_variants を持たない preset の slug を 1 つ選ぶ (AC-C23-R21-50c)。"""
    for slug, preset in presets(tc).items():
        if "presentation_order_variants" not in preset:
            return slug
    tc.fail("presentation_order_variants を持たない preset が 1 件も無い (50c を検査できない)")


def make_fixture_root(
    tc: unittest.TestCase, tmp: Path, mutate=None, mutate_policy=None, omit_policy=False
) -> Path:
    """実 plugin root の宣言データを一時 root へ複製する。

    mutate(catalog_dict) が与えられればカタログへ適用してから書き出す。
    mutate_policy(policy_dict) は視覚方針正本へ同じことをする (IMG の役の値域を
    動かして『値の出所が正本であること』を対照で確かめるため)。omit_policy=True は
    正本を置かない (fail-soft で控えへ落ちることの対照)。
    HB_ROOT にこの root を渡せば 4 段の実体解決の 1 段目で拾われる。
    """
    catalog = load_catalog(tc)
    root = tmp / "hb-root"
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)

    for src in (SECTIONS_FILE, PARTS_FILE):
        require_file(tc, src, "C12 / C11")
        shutil.copy2(src, root / "config" / src.name)

    if MANIFEST_FILE.is_file():
        shutil.copy2(MANIFEST_FILE, root / ".claude-plugin" / "plugin.json")
    else:
        (root / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "guide-doc-generator"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if SCHEMA_FILE.is_file():
        (root / "schemas").mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCHEMA_FILE, root / "schemas" / SCHEMA_FILE.name)

    if not omit_policy and VISUAL_POLICY_FILE.is_file():
        policy = json.loads(VISUAL_POLICY_FILE.read_text(encoding="utf-8"))
        if mutate_policy is not None:
            mutate_policy(policy)
        (root / "config" / VISUAL_POLICY_FILE.name).write_text(
            json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    if mutate is not None:
        mutate(catalog)
    (root / CATALOG_RELPATH).write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return root


def run_in_root(root: Path, args, stdin_data: str | None = None):
    return run(args, env=clean_env(HB_ROOT=str(root)), stdin_data=stdin_data)


def canonical_json_bytes(payload) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
