"""dogfooding 境界 (harness-creator 自身の除外/非除外) の SSOT 一本化を機械担保する。

findings SS-01 / SS-08 / SS-10 で検出した綻びを再発防止する:
  - 制御リテラル "harness-creator" が4 consumer に独立散在し、非対称な除外ルール
    (Stop block=除外 / feedback 配備=除外 / content-review=非除外) の SSOT が無かった。
  - 本テストは (a) SSOT 述語の真偽値、(b) 各 consumer が判定用スタンドアロン
    リテラルを残さず SSOT 述語へ委譲していること (textual + behavioral) を固定する。

二段確認 (feedback_verification_two_stage): textual grep だけでなく、各 consumer を
実際に import して _FC/FC が SSOT に解決し述語が正しい値を返すことも検証する。
"""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SSOT_PATH = ROOT / "scripts" / "feedback_contract_ssot.py"

LINT_CONTENT_REVIEW = ROOT / "scripts" / "lint-content-review.py"
LINT_FEEDBACK_PROTOCOL = ROOT / "scripts" / "lint-feedback-protocol.py"
CHECK_REVIEW_TRIGGER = (
    ROOT
    / "plugins" / "harness-creator" / "skills" / "run-elegant-review"
    / "scripts" / "check-review-trigger.py"
)
RENDER_COMBINATORS = (
    ROOT
    / "plugins" / "harness-creator" / "skills" / "run-build-skill"
    / "scripts" / "render-combinators.py"
)

CONSUMERS = [
    LINT_CONTENT_REVIEW,
    LINT_FEEDBACK_PROTOCOL,
    CHECK_REVIEW_TRIGGER,
    RENDER_COMBINATORS,
]

# 判定用スタンドアロン *リテラル* / 比較を禁止する (パス構築や SSOT 由来エイリアスは許容)。
# 核心は「制御リテラル "harness-creator" を判定に直書きしない」こと。SSOT から値を引く
# 後方互換エイリアス (= _FC.SELF_DOGFOODING_PLUGIN) は SSOT 一本化を破らないため許容する。
def _judgment_literal_res(plugin_name: str) -> list[re.Pattern[str]]:
    """SSOT の SELF_DOGFOODING_PLUGIN から regex を導出する。plugin 改名時に検査対象が
    自動追従し、旧名ハードコード regex の無音失効 (検査対象文字列の消滅で恒久緑) を防ぐ。"""
    lit = re.escape(plugin_name)
    return [
        re.compile(rf"""(?:==|!=)\s*["']{lit}["']"""),       # x == "<plugin>"
        re.compile(rf"""["']{lit}["']\s*(?:==|!=)"""),       # "<plugin>" == x
        re.compile(rf"""\bin\s*[\{{\(\[][^\}}\)\]]*["']{lit}["']"""),  # in {{"<plugin>"}}
        re.compile(rf"""\bSELF_EXCLUDED_PLUGIN\s*=\s*["']{lit}["']"""),  # 旧リテラル定数
        re.compile(rf"""EXEMPT_PLUGINS\s*=\s*[\{{\(\[][^\}}\)\]]*["']{lit}"""),
    ]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def fc():
    return _load(SSOT_PATH, "feedback_contract_ssot")


# ─────────────────────────── (a) 述語の真偽値 ───────────────────────────


def test_self_dogfooding_plugin_constant(fc):
    assert fc.SELF_DOGFOODING_PLUGIN == "harness-creator"


def test_stop_block_exempt_truth_table(fc):
    """Stop block: harness-creator は除外 (True)、他は非除外。"""
    assert fc.is_stop_block_exempt("harness-creator") is True
    for other in ("company-master", "mf-kessai-invoice-check", "skill-intake", ""):
        assert fc.is_stop_block_exempt(other) is False


def test_feedback_deploy_exempt_truth_table(fc):
    """feedback 配備: harness-creator は除外 (True)、他は非除外。"""
    assert fc.is_feedback_deploy_exempt("harness-creator") is True
    for other in ("company-master", "prompt-creator", "skill-intake", ""):
        assert fc.is_feedback_deploy_exempt(other) is False


def test_content_review_exempt_is_asymmetric(fc):
    """content-review: 生成器自身も dogfooding 対象なので **非除外** (常に False)。"""
    assert fc.is_content_review_exempt("harness-creator") is False
    for other in ("company-master", "prompt-creator", ""):
        assert fc.is_content_review_exempt(other) is False


def test_asymmetry_holds(fc):
    """非対称性の核: harness-creator は block/配備では除外だが content-review では非除外。"""
    p = fc.SELF_DOGFOODING_PLUGIN
    assert fc.is_stop_block_exempt(p) and fc.is_feedback_deploy_exempt(p)
    assert not fc.is_content_review_exempt(p)


def test_engine_skills_closure_is_ssot_frozenset(fc):
    """エンジン閉包 (収束ポリシー/評価経路) の列挙は SSOT の frozenset のみ (散在禁止)。"""
    assert isinstance(fc.ENGINE_SKILLS, frozenset)
    assert fc.ENGINE_SKILLS == frozenset(
        {"run-elegant-review", "run-skill-iter-improve", "run-skill-live-trial"}
    )


def test_requires_subject_copy_truth_table(fc):
    """INV7: harness-creator×エンジン閉包の交差時のみ被験体コピー強制 (True)。"""
    for engine in sorted(fc.ENGINE_SKILLS):
        assert fc.requires_subject_copy("harness-creator", engine) is True
    # 通常 skill は直接編集を維持 (False)
    for normal in ("run-build-skill", "run-skill-feedback", ""):
        assert fc.requires_subject_copy("harness-creator", normal) is False
    # 他 plugin はエンジン名の skill でも False (交差条件は自己 plugin のみ)
    for other in ("company-master", "mf-kessai-invoice-check", ""):
        assert fc.requires_subject_copy(other, "run-elegant-review") is False


# ────────────── (b-1) 判定用リテラルが consumer に残っていない ──────────────


@pytest.mark.parametrize("path", CONSUMERS, ids=lambda p: p.name)
def test_no_standalone_judgment_literal(path, fc):
    src = path.read_text(encoding="utf-8")
    for rgx in _judgment_literal_res(fc.SELF_DOGFOODING_PLUGIN):
        m = rgx.search(src)
        assert m is None, (
            f"{path.name}: 判定用 {fc.SELF_DOGFOODING_PLUGIN!r} リテラルが残存 "
            f"(SSOT 述語へ委譲すべき): {m.group(0)!r}"
        )


# ────────────── (b-0) dir 実在 ↔ SSOT 定数の parity (plugin 改名 drift 検知) ──────────────


def test_self_dogfooding_plugin_dir_exists(fc):
    """SELF_DOGFOODING_PLUGIN が指す plugin dir が実在する。dir 改名×定数据え置きの
    象限 (Stop hook 自己ブロック+feedback 自己配備の同時誤作動) を fail-closed 化する。"""
    assert (ROOT / "plugins" / fc.SELF_DOGFOODING_PLUGIN).is_dir(), (
        f"plugins/{fc.SELF_DOGFOODING_PLUGIN} が存在しない: plugin dir 改名時は "
        "SELF_DOGFOODING_PLUGIN (正本+vendored) を同一 commit で更新すること"
    )


def test_self_derive_parity_with_ssot_literal(fc):
    """parents[N].name self-derive する consumer (check-review-trigger/render-combinators)
    と SSOT literal の値が一致する。二重管理 drift (consumer 依存で述語真理値が分裂) を検知。"""
    for consumer, depth in ((CHECK_REVIEW_TRIGGER, 3), (RENDER_COMBINATORS, 3)):
        derived = consumer.resolve().parents[depth].name
        assert derived == fc.SELF_DOGFOODING_PLUGIN, (
            f"{consumer.name}: parents[{depth}].name={derived!r} が "
            f"SELF_DOGFOODING_PLUGIN={fc.SELF_DOGFOODING_PLUGIN!r} と不一致"
        )


# ────────────── (b-2) 各 consumer が SSOT 述語へ委譲している (textual) ──────────────


def test_content_review_uses_predicate():
    src = LINT_CONTENT_REVIEW.read_text(encoding="utf-8")
    assert "is_content_review_exempt" in src


def test_feedback_protocol_uses_predicate():
    src = LINT_FEEDBACK_PROTOCOL.read_text(encoding="utf-8")
    assert "is_feedback_deploy_exempt" in src
    assert "import feedback_contract_ssot" in src


def test_check_review_trigger_uses_predicate():
    src = CHECK_REVIEW_TRIGGER.read_text(encoding="utf-8")
    assert "is_stop_block_exempt" in src
    assert "feedback_contract_ssot" in src


def test_render_combinators_uses_predicate():
    src = RENDER_COMBINATORS.read_text(encoding="utf-8")
    assert "is_feedback_deploy_exempt" in src
    assert "feedback_contract_ssot" in src


# ───────────── (b-3) 二段確認: import して runtime で SSOT に解決する ─────────────


def test_check_review_trigger_resolves_ssot_at_runtime():
    mod = _load(CHECK_REVIEW_TRIGGER, "check_review_trigger_under_test")
    assert mod._FC.is_stop_block_exempt("harness-creator") is True
    assert mod._FC.is_stop_block_exempt("company-master") is False


def test_render_combinators_resolves_ssot_at_runtime():
    mod = _load(RENDER_COMBINATORS, "render_combinators_under_test")
    assert mod._FC.is_feedback_deploy_exempt("harness-creator") is True
    assert mod._FC.is_feedback_deploy_exempt("company-master") is False


def test_apply_feedback_loop_still_skips_self(tmp_path):
    """apply_feedback_loop は harness-creator では自己コピーを作らない。"""
    mod = _load(RENDER_COMBINATORS, "render_combinators_behavior")
    sc = tmp_path / "harness-creator"
    sc.mkdir()
    link = mod.apply_feedback_loop(sc)
    assert link == sc.resolve() / "skills" / "run-skill-feedback"
    assert not link.exists()  # 自己へのコピーは作らない

    other = tmp_path / "company-master"
    other.mkdir()
    link2 = mod.apply_feedback_loop(other)
    assert link2.is_dir()
    assert not link2.is_symlink()
