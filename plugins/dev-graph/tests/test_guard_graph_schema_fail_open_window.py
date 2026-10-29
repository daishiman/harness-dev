"""C10 guard: 遮断経路に fail-open の窓を作らない契約 (HarnessHub-6in4 / 7dw)。

背景:
  PreToolUse hook が timeout すると Claude Code は tool を通す。旧実装は Bash の破壊操作枝
  だけが `context_ok()` の後段にあり、さらに遮断/許可を左右しない `schema_ok()` (= graph
  全件の C11 検証) を理由文の出し分けのためだけに呼んでいた。実測で Write 枝 0.10s に対し
  Bash 枝は 39.79s を要し、run-dev-graph-init の live-trial では `.dev-graph/config.json` と
  `.dev-graph/state/graph.json` への Bash 直書きが 2 回素通りした。

本 test が固定する 3 つの契約:
  1. 遮断は repository context 検査より前に確定し、graph サイズ・マシン負荷に依存しない
     (受入条件 1 の機械化)。
  2. redirect の判定は shell 文法どおり quote の外だけを見る。遮断パターンを説明する散文を
     引数へ渡すコマンドを巻き込まない (7dw の散文誤遮断)。
  3. `.dev-graph/config.json` の sanctioned writer 呼出しは通り、writer の名前を騙るだけの
     直書きは通らない (allowlist が名前文字列一致でないこと)。

判定の構造そのもの (遮断経路が subprocess を起動しないこと) は
test_semantic_contract_boundaries_c10_c11_c24.py が固定する。ここでは *実プロセスの
遮断結果* と *入力の分類* を実測で押さえる。絶対所要時間は machine load まで測る
proxy metric であり、閾値を上げるほど graph 走査の退行を見逃す範囲が広がるため使わない。
"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
HOOK = PLUGIN / "hooks" / "guard-graph-schema.py"
OWNERSHIP_MARKER = Path(".dev-graph") / "config.json"


def managed(root: Path) -> Path:
    """guard は所有 marker (`.dev-graph/config.json`) を持つ repo でだけ判定する。

    marker の無い repo では最初に no-op で抜けるため、遮断契約を見る fixture には marker を置く。
    """
    marker = root / OWNERSHIP_MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    if not marker.exists():
        marker.write_text("{}\n", encoding="utf-8")
    return root


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return load(HOOK, "guard_fail_open_window")


def run_hook_process(command: str, root: Path) -> tuple[int, str]:
    """hook を実プロセスとして起動し (exit code, stderr) を返す。"""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(
        [sys.executable, "-B", str(HOOK), "--repo-root", str(managed(root))],
        input=payload, capture_output=True, text=True, check=False,
    )
    return proc.returncode, proc.stderr


def decide(guard, monkeypatch, capsys, command: str, root: Path) -> tuple[int, str]:
    """context 解決を bypass して静的判定だけを in-process で評価する。"""
    monkeypatch.setattr(guard, "context_ok", lambda _root: (True, "{}"))
    monkeypatch.setattr(sys, "argv", [str(HOOK), "--repo-root", str(managed(root))])
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))
    )
    code = guard.main()
    return code, capsys.readouterr().err


@pytest.mark.parametrize("target", [".dev-graph/config.json", ".dev-graph/state/graph.json"])
def test_bash_redirect_into_graph_authority_is_denied_in_real_process(target, tmp_path):
    """live-trial で素通りした 2 経路が、実プロセスでも exit 2 で遮断される。"""
    command = f"ROOT=/tmp/dev-graph-probe\ncat > \"$ROOT/{target}\" <<'EOF'\n{{}}\nEOF"

    code, stderr = run_hook_process(command, tmp_path)

    assert code == 2, f"遮断されていない: {stderr}"
    assert "C02 atomic writer" in stderr


def test_denial_does_not_resolve_repository_context_for_any_graph_size(
    guard, monkeypatch, capsys, tmp_path,
):
    """graph を持つ repo と空 repo の双方で graph 検査より前に遮断する。

    旧実装は --repo-root の graph 全件を C11 検証していたため、書込先が別 repo でも本体
    graph の大きさがそのまま遅延になった。絶対時間や大小 2 process の比は machine load
    も測る proxy metric であり、並列実行では graph 非依存でも偽陽性になりうる。

    現在の直接契約は、遮断対象が repository context 解決へ到達しないこと。context_ok()
    は subprocess を起動する唯一の後段なので、これを呼んだ時点で失敗させれば graph
    サイズ非依存性と fail-open window の不在を負荷に依存せず検査できる。
    """
    command = "cat > /tmp/dev-graph-probe/.dev-graph/config.json <<'EOF'\n{}\nEOF"
    with_graph = managed(tmp_path / "with-graph")
    graph = with_graph / ".dev-graph" / "state" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text(
        json.dumps({"schema_version": "1.0.0", "graph_revision": 1,
                    "nodes": [{"graph_node_id": f"n{i}"} for i in range(2000)]}),
        encoding="utf-8",
    )
    empty = managed(tmp_path / "empty")

    def context_must_not_run(_root):
        raise AssertionError("遮断前に repository context 検査へ到達した")

    monkeypatch.setattr(guard, "context_ok", context_must_not_run)
    for label, root in (("with-graph", with_graph), ("empty", empty)):
        monkeypatch.setattr(sys, "argv", [str(HOOK), "--repo-root", str(root)])
        monkeypatch.setattr(
            sys,
            "stdin",
            io.StringIO(
                json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
            ),
        )
        assert guard.main() == 2, label
        assert "C02 atomic writer" in capsys.readouterr().err

    # 陽性対照: trap 自体が空振りしていないことを、遮断対象外の入力で確認する。
    # static_denial() が None の場合は必ず context_ok() へ進むため、この入力だけは発火する。
    monkeypatch.setattr(sys, "argv", [str(HOOK), "--repo-root", str(empty)])
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo safe"}})
        ),
    )
    with pytest.raises(AssertionError, match="repository context 検査"):
        guard.main()


# quote の内側にある `>` は shell 文法上 redirect ではない。旧実装は command 全体を正規表現で
# 走査していたため、遮断パターンを説明する散文を引数に渡すだけのコマンドまで遮断していた。
PROSE_MUST_PASS = [
    # 6in4 の調査中に実際に誤遮断された形 (bd notes へ迂回手順を記録するだけ)
    'python3 plugins/dev-graph/scripts/bd-bridge.py update HarnessHub-6in4'
    ' --notes "Write 遮断後に cat > .dev-graph/config.json へ迂回した経路を閉じた"',
    "python3 plugins/dev-graph/scripts/bd-bridge.py update HarnessHub-7dw"
    " --notes 'echo x > .dev-graph/state/graph.json も遮断対象である'",
    # commit message / grep pattern / echo の本文として保護 path を含むだけ
    'git commit -m "guard: cat > .dev-graph/config.json を遮断する"',
    "grep -n 'cat > .dev-graph/config.json' plugins/dev-graph/hooks/guard-graph-schema.py",
    'echo "cat > .dev-graph/state/graph.json は遮断される"',
]

# quote の外にある本物の redirect は形を変えても遮断される (緩和ではなく解析の精密化)。
REDIRECT_MUST_BLOCK = [
    "cat > .dev-graph/config.json",
    "printf '{}' >> .dev-graph/state/graph.json",
    'echo "{}" > ".dev-graph/config.json"',
    "python3 -m json.tool 1> .dev-graph/state/graph.json",
    # 前段が read-only でも、後段の redirect 宛先が保護 path なら書込である
    "jq . /tmp/draft.json > .dev-graph/config.json",
]


@pytest.mark.parametrize("command", PROSE_MUST_PASS)
def test_prose_arguments_are_not_treated_as_redirects(guard, command):
    assert guard.destructive_graph_or_schema_operation(command) is False, command


@pytest.mark.parametrize("command", REDIRECT_MUST_BLOCK)
def test_real_redirects_into_graph_authority_are_blocked(guard, command):
    assert guard.destructive_graph_or_schema_operation(command) is True, command


def test_unparsable_quoting_falls_back_to_the_safe_side(guard):
    """quote 不一致でトークナイズ不能な入力を「redirect 無し」と扱うのは fail-open。"""
    assert guard.destructive_graph_or_schema_operation('cat > .dev-graph/config.json "') is True


# HD の sanctioned writer: config と初期 graph は build-init-scaffold.py、node 更新は
# build-graph-node.py。保護 path を `--config` の値として渡すだけの起動は書込みではない。
WRITER_CALL = (
    'python3 "$DEV_GRAPH_PLUGIN/scripts/build-init-scaffold.py" --repo-root "$ROOT"'
    " --config .dev-graph/config.json"
)
GRAPH_WRITER_CALL = (
    'python3 "$DEV_GRAPH_PLUGIN/scripts/build-graph-node.py" add --repo-root "$ROOT"'
    ' --input "$ROOT/.dev-graph/tmp/draft.json" --config .dev-graph/config.json'
)

WRITER_MUST_PASS = [
    WRITER_CALL,
    f'{WRITER_CALL} < "$ROOT/.dev-graph/tmp/draft.json"',
    f"{WRITER_CALL} <<'JSON'\n{{}}\nJSON",
    f'cat "$ROOT/.dev-graph/tmp/draft.json" | {WRITER_CALL}',
    WRITER_CALL + " --hook-source project-fallback",
    WRITER_CALL + " --dry-run",
    GRAPH_WRITER_CALL,
    GRAPH_WRITER_CALL + " --dry-run",
]

WRITER_MUST_BLOCK = [
    # writer の名前をコメントへ書いても直書きは直書き (allowlist は名前一致ではない)
    "cat > \"$ROOT/.dev-graph/config.json\" <<'EOF'  # build-init-scaffold.py\n{}\nEOF",
    'echo "{}" | tee "$ROOT/.dev-graph/config.json"',
    'cp /tmp/draft.json "$ROOT/.dev-graph/config.json"',
]


@pytest.mark.parametrize("command", WRITER_MUST_PASS)
def test_sanctioned_writer_invocation_passes_the_guard(guard, monkeypatch, capsys, tmp_path, command):
    """init が config を生成できること = fail-open に依存しないこと (受入条件 3)。"""
    code, stderr = decide(guard, monkeypatch, capsys, command, tmp_path)
    assert code == 0, f"sanctioned writer が遮断された: {stderr}"


@pytest.mark.parametrize("command", WRITER_MUST_BLOCK)
def test_writer_name_does_not_launder_a_direct_write(guard, monkeypatch, capsys, tmp_path, command):
    code, stderr = decide(guard, monkeypatch, capsys, command, tmp_path)
    assert code == 2, command
    assert "build-init-scaffold.py" in stderr, "遮断理由が正規経路を案内していない"


# HarnessHub-lp36: interpreter 経由 (python -c / heredoc) の書込み API 検出を issue の静的
# probe と同じ形で固定する。取りこぼし側 (false negative) は pathlib write_text/write_bytes に
# 加えて shutil.copy* / shutil.move / os.replace / os.rename / json.dump を、過剰遮断側
# (false positive) は open(..., 'r'/'rb') が ALLOW になり 'r+' は BLOCK のまま残ることを見る。
# shell redirect (cat> / tee) 側は REDIRECT_MUST_BLOCK / WRITER_MUST_BLOCK が別途固定済み。
INTERPRETER_WRITE_MUST_BLOCK = [
    "open('.dev-graph/state/graph.json', 'w')",
    "open('.dev-graph/config.json', 'a')",
    "open('.dev-graph/state/graph.json', 'x')",
    "open('.dev-graph/state/graph.json', 'r+')",
    "open('.dev-graph/state/graph.json', 'br+')",
    "open('.dev-graph/state/graph.json', '+rb')",
    "open('.dev-graph/state/graph.json', 'bw')",
    "from pathlib import Path\nPath(sys.argv[1]).write_text('{}')  # .dev-graph/state/graph.json",
    "from pathlib import Path\nPath('.dev-graph/state/graph.json').write_text('{}')",
    "from pathlib import Path\nPath('.dev-graph/config.json').write_bytes(b'{}')",
    "shutil.copy(src, '.dev-graph/state/graph.json')",
    "shutil.copyfile(src, '.dev-graph/config.json')",
    "shutil.copy2(src, '.dev-graph/state/graph.json')",
    "shutil.move(src, '.dev-graph/state/graph.json')",
    "os.replace(src, '.dev-graph/state/graph.json')",
    "os.rename(src, '.dev-graph/config.json')",
    "json.dump(data, open('.dev-graph/state/graph.json', 'w'))",
]

INTERPRETER_READ_MUST_ALLOW = [
    "open('.dev-graph/state/graph.json', 'r')",
    "open('.dev-graph/state/graph.json', 'rb')",
    "open('.dev-graph/state/graph.json', 'br')",
    "json.load(open('.dev-graph/state/graph.json'))",
    "from pathlib import Path\nprint(Path('.dev-graph/state/graph.json').read_text())",
]


@pytest.mark.parametrize("command", INTERPRETER_WRITE_MUST_BLOCK)
def test_interpreter_write_apis_into_graph_authority_are_blocked(guard, command):
    assert guard.interpreter_writes_graph_authority(command) is True, command


@pytest.mark.parametrize("command", INTERPRETER_READ_MUST_ALLOW)
def test_interpreter_read_only_calls_are_not_blocked(guard, command):
    assert guard.interpreter_writes_graph_authority(command) is False, command


def test_write_denial_names_the_actual_protected_scope(guard, monkeypatch, capsys, tmp_path):
    """遮断理由が保護範囲を広く名乗ると、正規手順まで塞がれていると読まれる。

    `.dev-graph/tmp/` は再生成可能で保護対象外であり、run-dev-graph-init は config draft を
    そこへ置いてから writer に渡す。理由文が「.dev-graph/ 配下」と述べると、遮断された agent は
    その正規手順も封じられていると解釈して別の迂回を探す (6in4 の fail-open が起きた局面)。
    理由文の範囲は `GRAPH_AUTHORITY_PATH` の実体と一致させる。
    """
    monkeypatch.setattr(guard, "context_ok", lambda _root: (True, "{}"))
    monkeypatch.setattr(sys, "argv", [str(HOOK), "--repo-root", str(managed(tmp_path))])
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / ".dev-graph" / "config.json"), "content": "{}"},
        })),
    )
    assert guard.main() == 2
    stderr = capsys.readouterr().err
    for member in (".dev-graph/state/", ".dev-graph/config.json", "graph-node.schema.json"):
        assert member in stderr, f"保護対象 {member} が理由文に現れない"
    assert ".dev-graph/ 配下" not in stderr, "保護外の tmp/ cache/ まで含む表現になっている"
    assert ".dev-graph/tmp/" in stderr, "draft の正規置き場が案内されていない"

    # 理由文の主張どおり tmp/ への Write は通る (文言と実挙動の一致)。
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / ".dev-graph" / "tmp" / "config-draft.json"),
                "content": "{}",
            },
        })),
    )
    assert guard.main() == 0, capsys.readouterr().err


# redirect 境界の分類。判定軸は「その操作の後に graph authority の内容が変わるか」であり、
# 保護 path が command のどこかに現れるかではない。
#
#   (c) VCS 経由の巻き戻しは書込みである。`git checkout -- <graph>` は C02 atomic writer を
#       通さずに graph の内容を過去 revision へ差し替えるため、revision の単調増加を
#       迂回する。redirect でないことは免罪符にならない。
#   (a) writer receipt の宛先 .dev-graph/tmp/ は再生成可能で保護対象外。run-dev-graph-init が
#       config draft を置く正規手順そのものなので、`.dev-graph/` 配下という理由で塞がない
#       (6in4 の fail-open は、正規手順まで塞がれたと読んだ agent が迂回を探して起きた)。
#   (b) source が保護 path でも読取は書込みではない。宛先が保護外の cache/ なら通す。
#       ここを塞ぐと a5w.1 が解消した参照↔書込 conflation を再導入する。
BOUNDARY_MUST_BLOCK: list[str] = [
    "git checkout -- .dev-graph/state/graph.json",
    "git checkout HEAD~1 -- .dev-graph/state/graph.json",
    "git restore .dev-graph/state/graph.json",
    # 保護外の receipt 手順を騙っても、宛先が state/ なら書込みである
    'python3 build-init-scaffold.py --stdin > .dev-graph/state/receipt.json',
]
BOUNDARY_MUST_PASS: list[str] = [
    'python3 build-init-scaffold.py --repo-root "$ROOT" --stdin > .dev-graph/tmp/receipt.json',
    "jq . .dev-graph/state/graph.json > .dev-graph/cache/pretty.json",
]


@pytest.mark.parametrize("command", BOUNDARY_MUST_BLOCK)
def test_boundary_cases_classified_as_writes_are_blocked(guard, command):
    assert guard.destructive_graph_or_schema_operation(command) is True, command


@pytest.mark.parametrize("command", BOUNDARY_MUST_PASS)
def test_boundary_cases_classified_as_reads_pass(guard, command):
    assert guard.destructive_graph_or_schema_operation(command) is False, command


# HarnessHub-f84o: path や mode を一度変数へ束ねてから書込む形は、字面一致だけを見る旧実装で
# 素通りした。遮断判定はコマンド文字列の中で閉じている代入を畳んでから行う。畳めるのは
# literal・Path()/os.path.join()・f-string・`+` 連結までで、実行時にしか値が定まらないもの
# (関数戻り値・環境変数・argv) は畳まない = ALLOW となる。そこは C10 の遮断範囲の外であり、
# PostToolUse の audit-graph-authority-drift.py が事後に拾う (HarnessHub-kzth)。
VARIABLE_WRITE_MUST_BLOCK = [
    "python3 -c \"p='.dev-graph/state/graph.json'; open(p,'w').write('{}')\"",
    "python3 -c \"from pathlib import Path; p = Path('.dev-graph') / 'state' / 'graph.json'; p.write_text('{}')\"",
    "python3 -c \"import pathlib; p = pathlib.Path('.dev-graph', 'config.json'); p.write_text('{}')\"",
    "python3 -c \"import os; p = os.path.join('.dev-graph', 'config.json'); open(p, 'w')\"",
    "python3 -c \"root='.dev-graph'; p=f'{root}/state/graph.json'; open(p,'w')\"",
    "python3 -c \"p='.dev-graph' + '/state/graph.json'; open(p,'w')\"",
    # mode 側だけを変数に逃がす形。path が literal でも write verb が読めなくなる。
    "python3 -c \"p='.dev-graph/state/graph.json'; m='w'; open(p, m)\"",
    # 2 段の後方参照 (d -> p)。
    "python3 -c \"d='.dev-graph/state'; p=d+'/graph.json'; Path(p).write_text('{}')\"",
]

VARIABLE_MUST_ALLOW = [
    # 変数を畳んでも読取りのままのもの。
    "python3 -c \"p='.dev-graph/state/graph.json'; print(open(p).read())\"",
    "python3 -c \"p='.dev-graph/state/graph.json'; open(p,'r')\"",
    # 畳んだ先が保護対象外。
    "python3 -c \"p='docs/notes.md'; open(p,'w')\"",
    # 実行時決定値は畳めない。ここは C10 の遮断範囲外であることを明示的に固定する。
    "python3 -c \"p=compute_path(); open(p,'w')\"",
    "python3 -c \"p=os.environ['GRAPH']; open(p,'w')\"",
]


@pytest.mark.parametrize("command", VARIABLE_WRITE_MUST_BLOCK)
def test_variable_bound_paths_and_modes_are_resolved_before_deciding(guard, command):
    assert guard.interpreter_writes_graph_authority(command) is True, command


@pytest.mark.parametrize("command", VARIABLE_MUST_ALLOW)
def test_variable_resolution_does_not_over_block(guard, command):
    assert guard.interpreter_writes_graph_authority(command) is False, command


def test_script_file_indirection_is_outside_the_pretooluse_blocking_range(guard):
    """書込みを別 script file へ移した形は C10 では遮断できない (HarnessHub-kzth)。

    これは欠陥ではなく遮断範囲の上限である。「interpreter 起動 x 書込み動詞 x authority
    path」の共起がコマンド文字列上で 1 つも成立しないため、遮断するには script の中身を
    読む必要があり、それは本 test file が固定している遮断時間契約 (subprocess/file I/O を
    遮断経路に置かない) を破る。範囲外であることを test で明示しておかないと、後続の実装が
    「C10 があるから graph authority は保護されている」と誤読する。事後検出は PostToolUse の
    audit-graph-authority-drift.py が担う。
    """
    for command in (
        "python3 tools/writer.py",
        "python3 tools/writer.py .dev-graph/state/graph.json",
        "bash tools/writer.sh",
    ):
        assert guard.interpreter_writes_graph_authority(command) is False, command
        assert guard.destructive_graph_or_schema_operation(command) is False, command


# HarnessHub-l1ru: `_mutating_operands` はセグメント分割に改行を含める。`_pipelines` が既に
# 改行で分割しているのに片方だけ分割しないと、先頭行の `git restore` が後続行のトークンまで
# 自分の operand として吸収し、保護外 path の復元だけのコマンドが誤って BLOCK になる。
NEWLINE_SEGMENTS_MUST_PASS = [
    "git restore eval-log/harness-coverage.json\ngit add docs/foo.md\ngit status",
    "git restore eval-log/x.json && git add docs/foo.md",
]

NEWLINE_SEGMENTS_MUST_BLOCK = [
    "git restore docs/foo.md",
    "git restore eval-log/x.json\ngit restore .dev-graph/state/graph.json",
]


@pytest.mark.parametrize("command", NEWLINE_SEGMENTS_MUST_PASS)
def test_newline_joined_commands_do_not_absorb_later_operands(guard, command):
    assert guard.destructive_graph_or_schema_operation(command) is False, command


@pytest.mark.parametrize("command", NEWLINE_SEGMENTS_MUST_BLOCK)
def test_newline_split_still_blocks_protected_operands_in_any_segment(guard, command):
    assert guard.destructive_graph_or_schema_operation(command) is True, command


def test_mutating_operands_and_pipelines_split_on_the_same_separators():
    """分割規則の非対称そのものを固定する (症状ではなく原因側の契約)。

    l1ru の再発は「片方の分割規則だけ直す」形で起きる。個別コマンドの期待値だけを test に
    置くと、次に別の区切り文字が追加されたときに同じ非対称が復活する。
    """
    module = load(PLUGIN / "lib" / "guard_graph_commands.py", "guard_commands_split")
    command = "git restore eval-log/x.json\ngit add docs/foo.md"
    assert module._mutating_operands(command) == ["eval-log/x.json"]
    assert len(module._pipelines(command)) == len(command.split("\n"))
