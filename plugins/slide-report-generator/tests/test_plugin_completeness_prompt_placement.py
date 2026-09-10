"""validate-plugin-completeness.py の prompt 配置規約のテスト。

この規約は 3 つ壊れていた。

(1) 判定が python の版で割れていた。`glob("*/prompts/*/")` の末尾スラッシュを 3.9 は
    無視してファイルまで一致させ (実木で 20 件 FAIL)、3.11+ は 0 件を返した。同じコード
    と同じ木で赤と緑が入れ替わるので、規約をどう直しても直ったかを確かめられない。
(2) その結果、規約が充足不能だった。PROMPT_REF_RE (flat 限定) と 153/162/164 行が
    「skills/<skill>/prompts/R*.md という実ファイルが存在すること」を要求する一方、
    3.9 の nested 判定はその存在必須のファイルを弾いていた。
(3) agent adapter 超過時の案内が `skills/*/prompts/agents/` を指しており、そこへ移すと
    今度は PROMPT_REF_RE に弾かれた。従うと違反になる案内だった。

ここで固定するのは 2 点。
- flat な prompts/R*.md は、どの版で起動しても弾かれない (規約が充足可能である)
- prompts/ 配下にディレクトリを作ったら、どの版で起動しても弾かれる (禁止は生きている)
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _PLUGIN_ROOT / "scripts" / "validate-plugin-completeness.py"


def _load():
    spec = importlib.util.spec_from_file_location("validate_plugin_completeness_mod", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def _run_on(tree: Path) -> list[str]:
    """合成ツリーを PLUGIN_ROOT に差し替えて配置検査だけを走らせる。"""
    original = mod.PLUGIN_ROOT
    mod.PLUGIN_ROOT = tree
    try:
        errors: list[str] = []
        mod.check_thin_agent_adapters(errors)
        return errors
    finally:
        mod.PLUGIN_ROOT = original


def _nested_errors(errors: list[str]) -> list[str]:
    return [e for e in errors if "nested prompts directory forbidden" in e]


def _flat_prompt_tree(tmp_path: Path) -> Path:
    """規約が正とする配置。agent の prompt_ref が指せる唯一の形。"""
    tree = tmp_path / "plugin"
    prompts = tree / "skills" / "run-demo" / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "R1-orchestrate.md").write_text("body\n", encoding="utf-8")
    (prompts / "R2-agent-demo.md").write_text("body\n", encoding="utf-8")
    return tree


def test_flat_prompts_are_not_forbidden(tmp_path):
    """flat な prompts/R*.md を弾かない。弾くと規約が充足不能になる。

    162 行が存在を要求するファイルを同じスクリプトが禁止していた、というのが
    今回の欠陥の本体。ここが赤に戻ったら規約はまた誰も守れない。
    """
    tree = _flat_prompt_tree(tmp_path)
    assert _nested_errors(_run_on(tree)) == []


def test_prompts_subdirectory_is_forbidden(tmp_path):
    """prompts/ 配下のディレクトリは弾く。禁止そのものは残っている。

    ここで作る skills/X/prompts/agents/ は、修正前の agent adapter 超過メッセージが
    「detail はここへ移せ」と案内していた先そのもの。案内に従うと違反になっていた。
    """
    tree = _flat_prompt_tree(tmp_path)
    nested = tree / "skills" / "run-demo" / "prompts" / "agents"
    nested.mkdir()
    (nested / "R2-agent-demo.md").write_text("body\n", encoding="utf-8")

    errors = _nested_errors(_run_on(tree))
    assert len(errors) == 1
    assert "skills/run-demo/prompts/agents" in errors[0]


def test_verdict_does_not_depend_on_glob_trailing_slash(tmp_path):
    """版差の再導入を止める。

    旧実装の `glob("*/prompts/*/")` は、起動した python の版で返すものが変わった。
    ここでは版を跨いで比較する代わりに、版差が現れる唯一の入口 (ファイルが一致集合に
    混じるか) を不変条件として固定する。ファイルが 1 つでも混じったら、それは
    末尾スラッシュ依存の実装に戻ったということ。
    """
    tree = _flat_prompt_tree(tmp_path)
    (tree / "skills" / "run-demo" / "prompts" / "agents").mkdir()

    hits = sorted(
        path for path in (tree / "skills").glob("*/prompts/*") if path.is_dir()
    )
    assert [p.name for p in hits] == ["agents"]
    assert all(path.is_dir() for path in hits)
    assert not any(path.is_file() for path in hits)


def test_glob_does_not_rely_on_trailing_slash():
    """末尾スラッシュ形の再導入を、起動した版に関係なく止める。

    上の 3 件だけでは足りない。旧実装 `glob("*/prompts/*/")` は 3.11+ では新実装と
    同じものを返すので、ふだん pytest を回す版 (この環境では 3.11.4) では旧に戻しても
    赤にならない。実測: 旧実装は 3.9.6 で 3 件全滅、3.11.4 / 3.13.3 では全て緑。
    つまり挙動テストだけでは、版差そのものは押さえられない。
    版に依存しない形で押さえられるのはソース側だけなので、ここで形を固定する。
    """
    # 実行される行だけを見る。修正の経緯を説明するコメントは旧形を引用しており、
    # ソース全体を素の in で見ると、説明を書いたこと自体で赤になる。
    # これは想定ではなく一度踏んだ。最初この照合をソース全体に対して書いたところ、
    # 直したはずの現行実装がこのテストだけで落ちた。原因は check_thin_agent_adapters
    # の説明コメントが旧形 glob("*/prompts/*/") を引用していたこと。
    # 経緯を書いたこと自体で赤くなる検査は、次の人に「コメントを消す」を選ばせる。
    # 消させないために、照合対象を実行行へ狭める。
    code = "\n".join(
        line for line in _SCRIPT.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    assert 'glob("*/prompts/*/")' not in code
    assert "glob('*/prompts/*/')" not in code
    assert 'glob("*/prompts/*")' in code
    assert "path.is_dir()" in code


def test_agent_size_hint_points_at_a_placement_that_is_allowed(tmp_path):
    """超過時の案内先が、同じスクリプトの他の検査に当たらないこと。

    案内文に現れる配置は PROMPT_REF_RE を通り、かつ nested 判定に当たらない
    必要がある。罠を注釈付きで残さないための固定。
    """
    agents_dir = _PLUGIN_ROOT / "agents"
    hint_sample = "skills/run-demo/prompts/R2-agent-demo.md"
    assert mod.PROMPT_REF_RE.match(hint_sample)

    source = _SCRIPT.read_text(encoding="utf-8")
    assert "move detail to skills/*/prompts/agents/" not in source
    assert "skills/<owner_skill>/prompts/R*.md" in source
    assert agents_dir.is_dir()


def test_real_plugin_tree_has_no_nested_prompt_directories():
    """実木の回帰ガード。誰かが prompts/ を階層化したらここが赤になる。"""
    assert _nested_errors(_run_on(_PLUGIN_ROOT)) == []


# --- script inventory: 検査器を作っても配線せずに済んでしまう穴 -------------------
#
# 上の 3 つとは性質が違う。規約は正しいが、当たるべきものに当たっていなかった。
# 宣言側 COMPOSITION_SCRIPT_RE は拡張子を問わないので、集合一致の網の広さは
# SCRIPT_SUFFIXES だけで決まる。ここに無い拡張子は「実体として数えない」＝
# 未宣言でも赤にならない。


def _composition_tree(tmp_path: Path, script_names: list[str], declared: list[str]) -> Path:
    tree = tmp_path / "plugin"
    (tree / "scripts").mkdir(parents=True)
    for name in script_names:
        (tree / "scripts" / name).write_text("x\n", encoding="utf-8")
    lines = [f"  - {{ kind: script, ref: scripts/{d}, tier: core }}" for d in declared]
    (tree / "plugin-composition.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tree


def _inventory_errors(tree: Path) -> list[str]:
    original = mod.PLUGIN_ROOT
    mod.PLUGIN_ROOT = tree
    try:
        errors: list[str] = []
        mod.check_script_inventory(errors)
        return errors
    finally:
        mod.PLUGIN_ROOT = original


def test_undeclared_mjs_script_is_detected(tmp_path):
    """未宣言の .mjs を赤にする。

    修正前は SCRIPT_SUFFIXES に .mjs が無く、この合成ツリーは緑になった
    (実木でも .mjs 検査器 2 本が未宣言のまま通っていた)。検査器を作っても
    plugin-composition.yaml へ配線せずに済んでしまう穴だった。
    """
    tree = _composition_tree(
        tmp_path,
        script_names=["declared.py", "orphan.mjs"],
        declared=["declared.py"],
    )
    errors = _inventory_errors(tree)
    assert len(errors) == 1
    assert "scripts/orphan.mjs" in errors[0]
    assert "undeclared=" in errors[0]


def test_declared_mjs_script_is_not_flagged(tmp_path):
    """配線済みの .mjs は赤にしない (偽陽性を作っていないこと)。"""
    tree = _composition_tree(
        tmp_path,
        script_names=["declared.py", "wired.mjs"],
        declared=["declared.py", "wired.mjs"],
    )
    assert _inventory_errors(tree) == []


def test_script_suffixes_cover_every_runtime_present_in_scripts_dir():
    """実木の scripts/ に、集合一致の網から漏れる実行系が無いこと。

    次に誰かが別の拡張子 (.ts / .sh など) で検査器を足したとき、
    SCRIPT_SUFFIXES への追加を忘れたらここが赤になる。同じ穴を掘り直させない。
    """
    ignored = {".pyc", ".pyo"}
    present = {
        path.suffix
        for path in (_PLUGIN_ROOT / "scripts").iterdir()
        if path.is_file() and path.suffix and path.suffix not in ignored
    }
    assert present <= set(mod.SCRIPT_SUFFIXES), f"網から漏れている拡張子: {sorted(present - set(mod.SCRIPT_SUFFIXES))}"
