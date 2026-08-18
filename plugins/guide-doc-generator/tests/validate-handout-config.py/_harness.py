# -*- coding: utf-8 -*-
"""C12 validate-handout-config.py の受入テスト共通ハーネス。

判定基準の出所は plugin-plans/guide-doc-generator/briefs/script-brief-C12.json
(argv / exit_codes / algorithm / normalize_algorithm / acceptance_checks) と
briefs/RESOLUTION-R21.md。ここには契約を書かず、契約を叩くための足場だけを置く。

実装 (plugins/guide-doc-generator/scripts/validate-handout-config.py) は P05 の担当で
本テスト作成時点では存在しない。存在しない場合 run() は returncode=127 の合成結果を
返すため、各テストは「期待する exit code / 診断コードが出ない」という形で赤になる。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_PLUGIN_ROOT = REPO_ROOT / "plugins" / "guide-doc-generator"
SCRIPT_RELPATH = Path("scripts") / "validate-handout-config.py"
SRC_SCRIPT = SRC_PLUGIN_ROOT / SCRIPT_RELPATH

# ブリーフ dependencies.reads が挙げる、この script が読むデータ正本 (plugin root 相対)
SECTIONS_CATALOG_RELPATH = Path("config") / "handout-sections.json"
PARTS_CATALOG_RELPATH = Path("config") / "handout-parts.json"
PURPOSES_CATALOG_RELPATH = Path("config") / "handout-purposes.json"
SCHEMA_RELPATH = Path("schemas") / "handout-config.schema.json"
TOKENS_RELDIR = Path("assets") / "tokens"

NOT_IMPLEMENTED_MARKER = "HB-TEST-SCRIPT-NOT-FOUND"


def _synthetic_missing(script_path):
    return subprocess.CompletedProcess(
        args=[str(script_path)],
        returncode=127,
        stdout="",
        stderr="%s %s (P05 未実装)\n" % (NOT_IMPLEMENTED_MARKER, script_path),
    )


def run(args, root, stdin_data=None, env_root=True, cwd=None):
    """コピーした plugin root 配下の script を argv 付きで起動する。

    args: --config 以降のフラグ列 (str のリスト)
    root: plugin root として使う一時ディレクトリ
    """
    script = Path(root) / SCRIPT_RELPATH
    if not script.exists():
        return _synthetic_missing(script)
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    if env_root:
        env["HB_ROOT"] = str(root)
    else:
        env.pop("HB_ROOT", None)
    return subprocess.run(
        [sys.executable, str(script)] + [str(a) for a in args],
        input=stdin_data,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd) if cwd else str(REPO_ROOT),
    )


# --------------------------------------------------------------------------
# 構成データ fixture
# --------------------------------------------------------------------------

def text_part(part_id, body="対話は目的を先に書き、次に前提を書く。そうすると出力が安定する。", **over):
    p = {"part": "TEXT", "id": part_id, "data": {"body": body}}
    p.update(over)
    return p


def diagram_part(part_id, diagram_id, **over):
    p = {"part": "DIAGRAM", "id": part_id, "data": {"diagram_id": diagram_id}}
    p.update(over)
    return p


def table_part(part_id, **over):
    """視覚部品として数えられる表 (B05 は列 2 件以上が必要)。"""
    p = {
        "part": "B05",
        "id": part_id,
        "data": {
            "columns": ["項目", "内容"],
            "rows": [
                {"header": "目的", "cells": ["目的", "先に書くと出力が揺れない"]},
                {"header": "前提", "cells": ["前提", "後から足すと崩れる"]},
            ],
        },
    }
    p.update(over)
    return p


def diagram(diagram_id, title="指示文が出力へ届くまで", **over):
    """C14 の flow パターン。形の正本は C14 で、C12 は $defs.diagram の形だけを見る。"""
    d = {
        "id": diagram_id,
        "pattern": "flow",
        "title": title,
        "data": {"steps": [{"label": "目的を書く"}, {"label": "前提を書く"}, {"label": "出力を確かめる"}]},
    }
    d.update(over)
    return d


def visual_section(section_id, **over):
    """図解 1 枚と表 1 つと本文 1 つを持つセクション。

    section() が本文だけなのは「必須フィールドの最小形」を示すためであり、
    そのまま資料の見本にすると W-VISUAL-ABSENT が当たる。図解の下限を
    満たした見本が要る場所ではこちらを使う (config/handout-visual-policy.json)。

    表を挟んで部品 3 件にしてあるのは、TEXT 1 件で上限比率
    (max_text_parts_ratio_per_section) を超えないようにするためである。
    部品 2 件のうち 1 件が TEXT だと、それだけで W-TEXT-HEAVY が当たる。
    """
    parts = [diagram_part(section_id + "-d1", section_id + "-flow"),
             table_part(section_id + "-b1"),
             text_part(section_id + "-t1")]
    over.setdefault("parts", parts)
    return section(section_id, **over)


def section(section_id, **over):
    """全ての必須セクションフィールドを満たす標準セクション。"""
    s = {
        "id": section_id,
        "heading": "対話の組み立て",
        "goal": "この節を読み終えると、指示文を目的から書き起こせるようになる",
        "lead_line": "指示は目的から書くと崩れない",
        "judgment_axis": "迷ったら、出力を受け取る人が何を判断できるかで決める",
        "duration": "30分",
        "role": "main",
        "ties_to": ["goal", "target_task:vehicle-pl"],
        "attainment_step": "operable",
        "section_kind": "standard",
        "parts": [text_part(section_id + "-t1")],
    }
    s.update(over)
    return s


def valid_config(**over):
    """全必須フィールドを満たす構成データ (AC-C12-01 の入力)。

    - attainment_step に document.attainment_level と一致する section を含む (E-ATTAINMENT-UNREACHED 回避)
    - role=main の ties_to は goal 系と target_task 系の双方を含む (C48 / C58)
    - min_duration_share を持つ section_kind を含まないので duration は必須化されない
    """
    cfg = {
        "schema_version": "1.0",
        "title": "AI handout builder workshop",
        "subject_slug": "ai-handout-workshop",
        "date": "2026/08/17",
        "doc_type": "lecture",
        "purpose": "生成 AI を日々の集計業務へ組み込む手順を、その場で再現できる形で共有する",
        "background": "現場では月次の車両収支集計を手作業で行っており、締め日前の残業が慢性化している",
        "goal": "受講者が自分の集計業務を 1 つ選び、生成 AI へ渡す指示文を自力で書けるようになる",
        "reader": "月次集計を担当する管理部門の担当者",
        "prior_knowledge_level": "basic",
        "essential_problem": "手順は分かっていても、どこから自動化に着手すればよいかを決められない",
        "duration": "60分",
        "focus_theme": ["自分の集計業務を生成 AI へ任せる勘所をつかむ"],
        "target_tasks": [{"id": "vehicle-pl", "label": "車両収支レポートの月次集計を自動化する"}],
        "presentation_order": "demo_first",
        "attainment_level": "operable",
        "must_remember": ["指示文は目的から書く"],
        "no_need_to_remember": ["個々のモデル名とオプションの綴り"],
        "theme": None,
        "notes_enabled": True,
        "glossary": [{"term": "プロンプト", "plain": "AI へ渡す指示文"}],
        "diagrams": [diagram("intro-flow"), diagram("practice-flow", title="集計を任せる手順")],
        "sections": [visual_section("intro"), visual_section("practice", id="practice")],
    }
    cfg.update(over)
    return cfg


class C12TestCase(unittest.TestCase):
    """plugin root を temp へ複製し、そこの script を叩く基底クラス。

    データファイル (config/handout-sections.json 等) を書き換えても実行結果が
    追従することを検査するために、毎テスト独立したコピーを使う。
    """

    maxDiff = None

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "plugin-root"
        if SRC_PLUGIN_ROOT.exists():
            # tests / __pycache__ は script が読まないので複製しない (実行時間の都合)
            shutil.copytree(SRC_PLUGIN_ROOT, self.root,
                            ignore=shutil.ignore_patterns("tests", "__pycache__"))
        else:
            self.root.mkdir(parents=True)
        self.out = self.tmp / "out.json"

    def tearDown(self):
        self._tmp.cleanup()

    # ---- 入力ファイル ----------------------------------------------------

    def write_config(self, cfg, name="config.json", raw=None, encoding="utf-8"):
        path = self.tmp / name
        if raw is not None:
            path.write_bytes(raw)
        else:
            path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding=encoding)
        return path

    # ---- 実行 ------------------------------------------------------------

    def run_cli(self, *args, **kwargs):
        return run(list(args), self.root, **kwargs)

    def validate(self, cfg, *extra, **kwargs):
        path = self.write_config(cfg)
        return self.run_cli("--config", path, *extra, **kwargs), path

    def normalize(self, cfg, *extra, out=None, **kwargs):
        path = self.write_config(cfg)
        out = out or self.out
        res = self.run_cli("--config", path, "--normalize", "--out", out, *extra, **kwargs)
        return res, path, out

    # ---- assert ----------------------------------------------------------

    def assert_exit(self, res, expected):
        self.assertEqual(
            expected,
            res.returncode,
            "exit code が %d でない (実際 %d)\nstdout=%r\nstderr=%r"
            % (expected, res.returncode, res.stdout, res.stderr),
        )

    def assert_diag(self, res, code, pointer=None):
        """stderr に '<診断コード> <JSON Pointer> <説明>' の行があること。"""
        lines = [l for l in res.stderr.splitlines() if l.split(" ")[0] == code]
        self.assertTrue(
            lines,
            "stderr に診断コード %s の行が無い\nstderr=%r\nexit=%d" % (code, res.stderr, res.returncode),
        )
        if pointer is not None:
            self.assertTrue(
                any(pointer in l for l in lines),
                "%s の行にキーパス %s が含まれない: %r" % (code, pointer, lines),
            )
        return lines

    def assert_no_diag(self, res, code):
        lines = [l for l in res.stderr.splitlines() if l.split(" ")[0] == code]
        self.assertFalse(lines, "出るべきでない診断 %s が出ている: %r" % (code, lines))

    def assert_fails_with(self, res, code, pointer=None):
        self.assert_exit(res, 1)
        return self.assert_diag(res, code, pointer)

    def read_out(self, out=None):
        out = out or self.out
        self.assertTrue(out.exists(), "--out が書き出されていない: %s" % out)
        return json.loads(out.read_text(encoding="utf-8"))

    # ---- 参照データ ------------------------------------------------------

    def sections_catalog(self):
        path = self.root / SECTIONS_CATALOG_RELPATH
        self.assertTrue(path.exists(), "section_kind 正本が無い: %s" % path)
        return json.loads(path.read_text(encoding="utf-8"))

    def patch_sections_catalog(self, slug, **attrs):
        """section_kind 正本の属性を書き換える (閾値が script に埋まっていないことの回帰用)。"""
        path = self.root / SECTIONS_CATALOG_RELPATH
        catalog = self.sections_catalog()
        for kind in catalog.get("section_kinds", []):
            if kind.get("slug") == slug:
                for key, value in attrs.items():
                    if value is None:
                        kind.pop(key, None)   # None は「属性ごと消す」の意
                    else:
                        kind[key] = value
                break
        else:
            self.fail("section_kind %s が正本に無い: %s" % (slug, path))
        path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    def script_source(self):
        script = self.root / SCRIPT_RELPATH
        self.assertTrue(
            script.exists(),
            "実装 %s が存在しない (build_target: plugins/guide-doc-generator/scripts/validate-handout-config.py)"
            % script,
        )
        return script.read_text(encoding="utf-8")
