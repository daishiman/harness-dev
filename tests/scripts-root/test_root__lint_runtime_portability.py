"""scripts/lint-runtime-portability.py の genuine な回帰テスト (network 不要)。

この lint は runtime hook script が import-time に自 plugin root 外を fail-closed 依存
(失敗時 raise) しないことを静的検査する。単独 install で plugin 外 (repo-root scripts/)
が不在のとき import-time クラッシュする回帰を封じる。

回帰の核心 (必須):
  - 修正前パターン (動的 import ローダが「成功時 return / 全滅時 raise」をトップレベル
    呼び出し) を食わせると check_script が違反を1件以上返す (FAIL)。
  - 修正後パターン (raise 撤廃・失敗時 fallback return) を食わせると違反 0 (PASS)。
  - 実 repo の hook script 群は修正済みのため CLI exit 0 (PASS)。

network: false, keychain: なし, 実ファイル書換: なし (tmp_path のみ)。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-runtime-portability.py"

SPEC = importlib.util.spec_from_file_location("lint_runtime_portability_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# 修正前 (回帰) パターン: ローダが全滅時 raise。トップレベルで未保護に呼ぶ。
PRE_FIX_RAISE_ONLY = '''\
from pathlib import Path
def _load_feedback_contract_ssot():
    import importlib.util
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        cand = ancestor / "scripts" / "feedback_contract_ssot.py"
        if cand.is_file():
            spec = importlib.util.spec_from_file_location("feedback_contract_ssot", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise ImportError("feedback_contract_ssot.py not found upward")
_FC = _load_feedback_contract_ssot()
'''

# 修正後パターン: raise 撤廃、失敗時 fallback を return (fail-soft)。
POST_FIX_FAIL_SOFT = '''\
import os
from pathlib import Path
def _load_feedback_contract_ssot():
    import importlib.util
    candidates = []
    pr = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if pr:
        candidates.append(Path(pr) / "scripts" / "feedback_contract_ssot.py")
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidates.append(ancestor / "scripts" / "feedback_contract_ssot.py")
    for cand in candidates:
        try:
            if cand.is_file():
                spec = importlib.util.spec_from_file_location("x", cand)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
        except Exception:
            continue
    return _fallback()
def _fallback():
    import types
    return types.SimpleNamespace()
_FC = _load_feedback_contract_ssot()
'''


def _check(tmp_path, src):
    """check_script は ROOT 相対化するため MOD.ROOT 配下の一時ファイルで検査する。"""
    p = tmp_path / "hook.py"
    p.write_text(src)
    return MOD.check_script(p)


def test_pre_fix_raise_only_is_flagged(tmp_path, monkeypatch):
    """修正前 (raise-only) ローダのトップレベル呼び出しは違反検出される (回帰固定)。"""
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    violations = _check(tmp_path, PRE_FIX_RAISE_ONLY)
    assert violations, "raise-only ローダの import-time クラッシュ経路を見逃した"
    assert any("import-time" in v for v in violations)


def test_post_fix_fail_soft_passes(tmp_path, monkeypatch):
    """修正後 (fail-soft, raise 撤廃) ローダは違反 0 (PASS)。"""
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    assert _check(tmp_path, POST_FIX_FAIL_SOFT) == []


def test_toplevel_call_inside_try_is_not_flagged(tmp_path, monkeypatch):
    """try で保護されたトップレベル呼び出しは import 失敗を握れるため非違反。"""
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    src = (
        "from pathlib import Path\n"
        "def _load():\n"
        "    import importlib.util\n"
        "    cand = Path('x')\n"
        "    spec = importlib.util.spec_from_file_location('x', cand)\n"
        "    raise ImportError('boom')\n"
        "try:\n"
        "    _FC = _load()\n"
        "except Exception:\n"
        "    _FC = None\n"
    )
    assert _check(tmp_path, src) == []


def test_non_loader_toplevel_call_ignored(tmp_path, monkeypatch):
    """spec_from_file_location を使わない関数のトップレベル呼び出しは対象外。"""
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    src = (
        "def _setup():\n"
        "    raise RuntimeError('not a loader')\n"
        "_setup()\n"
    )
    assert _check(tmp_path, src) == []


def test_real_repo_hook_scripts_pass():
    """実 repo の hook script 群は修正済みのため違反 0 で CLI exit 0。"""
    res = subprocess.run([sys.executable, str(SCRIPT)], text=True, capture_output=True)
    assert res.returncode == 0, f"stderr={res.stderr}"
    assert "OK" in res.stdout


def test_hook_scripts_discovered():
    """plugin.json から hook script を実際に発見できること (検査対象 0 件の空振り防止)。"""
    scripts = MOD._hook_scripts()
    assert scripts, "hook script を1件も発見できていない (plugin.json 解析の回帰)"
    # check-review-trigger.py が対象に含まれること (今回の主修正ファイル)。
    names = {p.name for p in scripts}
    assert "check-review-trigger.py" in names
