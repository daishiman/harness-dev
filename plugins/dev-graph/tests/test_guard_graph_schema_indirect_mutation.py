"""C10 guard: find/xargs 経由の間接一括書換 (書込先を静的抽出できない mutation) の遮断契約。

背景 (a5w.1 / bxz の横展開):
  system-spec 側 guard は「書込先を静的に確定できない mutation が保護領域を走査するなら
  安全側で遮断する」規則を持つ (guard-confirmed-chapter-overwrite.py。境界定義は
  plugins/system-spec-harness/hooks/references/hook-guard-protection-scope.md §2/§4)。
  姉妹 hook の guard-graph-schema.py にはこの規則が無く、`find tasks -name '*.md' |
  xargs sed -i ...` のように書換対象が find の列挙結果として渡る経路は _mutating_operands で
  宛先を抽出できず、graph 権威 (tasks/ docs/ specs/ .dev-graph/) を素通りで一括改変できた (FN)。

本 test の二重の契約:
  1. MUST_BLOCK: 間接構文 (xargs / find -exec) + mutation ツール + 保護領域の走査 の共起を遮断する。
  2. MUST_PASS: a5w.1 が解消した参照↔書込 conflation を再導入しない。特に判定は pipeline 単位で、
     別 pipeline が保護領域を read arg として参照するだけのコマンドを巻き込まないこと。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
HOOKS = PLUGIN / "hooks"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return load(HOOKS / "guard-graph-schema.py", "guard_indirect_mutation")


MUST_BLOCK = [
    # find | xargs: 書換対象が列挙結果として渡るため静的トークンに現れない
    "find tasks -name '*.md' | xargs sed -i 's/a/b/'",
    # find -exec: 同上 ({} は宛先トークンにならない)
    "find tasks -name '*.md' -exec sed -i 's/a/b/' {} +",
    # graph 権威ディレクトリ自体の一括削除
    "find .dev-graph -name '*.json' | xargs rm -f",
    # 成果物ディレクトリの一括切り詰め
    "find docs -type f | xargs truncate -s 0",
    # 列挙元が git でも mutation ツールが xargs 側にあれば遮断
    "git ls-files specs | xargs rm",
    # find 自身が mutation する経路 (pipeline 内に書換ツールのトークンが現れない)
    "find issues -name '*.md' -delete",
    # -execdir も -exec と同じく列挙結果を動的 operand として渡す
    "find tasks -name '*.md' -execdir sed -i 's/a/b/' {} +",
    # xargs の列挙結果が cp の destination になる経路
    "find tasks -name '*.md' | xargs -I{} cp /tmp/replacement {}",
    "find tasks -name '*.md' -exec cp /tmp/replacement {} \\;",
    # tokenize 回帰: `|` が前後どちらに密着しても stage 境界と consumer 名を取り違えない
    # (shlex.split は `|xargs` を 1 トークンにするため、判定を token 一致へ精密化した際の FN 源)
    "find tasks -name '*.md' |xargs rm",
    "find tasks|xargs rm",
    "find tasks -name '*.md'|xargs sed -i 's/a/b/'",
    # 既存の直接指定経路の遮断は維持する (回帰アンカー)
    "sed -i 's/a/b/' tasks/sys-x-p01.md",
]

MUST_PASS = [
    # 列挙のみ (mutation ツール無し) は read-only
    "find tasks -name '*.md' | xargs wc -l",
    "find specs -type f | xargs grep -l TODO > /tmp/out.txt",
    # git の read サブコマンドを mutation と誤認しない
    "git ls-files tasks | xargs wc -l",
    # xargs consumer は read-only。後段の tee は静的な /tmp だけへ書く
    "find tasks | xargs wc -l | tee /tmp/count",
    "find tasks | xargs sed 's/a/b/' > /tmp/rendered.txt",
    # mutation tool 名が consumer の引数にあるだけなら mutation ではない
    "find tasks | xargs echo rm",
    "find tasks -exec echo rm {} +",
    # quote 内の `|` は演算子ではない (tokenize 精密化で stage を割ってはならない)
    "find tasks | xargs grep -lE 'rm|cp' > /tmp/hits.txt",
    # 保護領域外の一括削除は通す
    "find /tmp -name '*.tmp' | xargs rm -f",
    "find /tmp -name '*.tmp' -delete",
    # 列挙結果が source で、書込先は保護領域外に静的確定する
    "find tasks -name '*.md' -exec cp {} /tmp/backup/ \\;",
    "find tasks -name '*.md' | xargs cp -t /tmp/backup/",
    # pipeline スコープ: 後段は graph を read arg に取るだけ (参照↔書込 conflation の再導入防止)
    "find /tmp -name '*.tmp' | xargs rm -f && python3 scripts/x.py --graph .dev-graph/state/graph.json",
    # 保護領域を source にした複製 (書込先は保護領域外)
    "cp .dev-graph/state/graph.json /tmp/graph-backup.json",
]


@pytest.mark.parametrize("command", MUST_BLOCK)
def test_indirect_bulk_mutation_over_guarded_area_blocked(guard, command):
    assert guard.destructive_graph_or_schema_operation(command) is True, command


@pytest.mark.parametrize("command", MUST_PASS)
def test_read_only_or_out_of_scope_commands_pass(guard, command):
    assert guard.destructive_graph_or_schema_operation(command) is False, command


def test_pipeline_split_keeps_pipe_as_single_unit(guard):
    """`|` は 1 pipeline 内、`&&`/`;` は分離 — 判定スコープの前提を固定する。"""
    assert guard._pipelines("find tasks | xargs rm") == [["find", "tasks", "|", "xargs", "rm"]]
    assert len(guard._pipelines("rm /tmp/a && rm /tmp/b")) == 2
    assert len(guard._pipelines("rm /tmp/a ; rm /tmp/b")) == 2


def test_guarded_scan_root_matches_bare_authority_dirs(guard):
    """`find tasks ...` の走査起点は末尾 '/' を持たないため専用境界で判定する。"""
    for token in ("tasks", "docs", "specs", ".dev-graph", "./issues", "features/feat-x"):
        assert guard.GUARDED_SCAN_ROOT.match(token), token
    for token in ("/tmp", "plugins", "taskschedule", "eval-log"):
        assert not guard.GUARDED_SCAN_ROOT.match(token), token


@pytest.mark.parametrize(
    "scan_root",
    ["{root}", "{root}/tasks", "$PWD/tasks", "${PWD}/docs", "$(pwd)/specs"],
)
def test_repo_root_normalisation_blocks_absolute_and_pwd_scans(guard, tmp_path, scan_root):
    """absolute path / PWD 表現でも caller repo の保護領域を同じ境界で扱う。"""
    root = tmp_path / "caller"
    root.mkdir()
    command = f"find {scan_root.replace('{root}', str(root))} -name '*.md' | xargs sed -i 's/a/b/'"
    assert guard.destructive_graph_or_schema_operation(command, root) is True, command


def test_same_named_directory_outside_repo_is_not_guarded(guard, tmp_path):
    """repo 外の /tmp/tasks 等は名前が同じでも graph 権威ではない。"""
    root = tmp_path / "caller"
    outside = tmp_path / "tasks"
    root.mkdir()
    outside.mkdir()
    command = f"find {outside} -name '*.md' | xargs rm -f"
    assert guard.destructive_graph_or_schema_operation(command, root) is False
