"""マトリクス散文と引用実体の整合 (A6 型誤帰属の再発防止)。

2026-06-30 elegant-review (finding L1) で、harness-creator-spec-reflection.md の A6 行が
L2 評価器固有 rule (PG-001/PG-002/BND-001/REG-001) を L0 rubric 正本に**誤帰属**していた
事実誤りを検出した。根本原因 (L10) は `check-spec-matrix-coverage.py --self-test` が
ROW-ID 集合の drift しか検査せず、散文「何を強制」列と引用パスの**実体一致を未検証**だった
こと (= 完全性証明の循環論法が機構レベルで未解消)。

本テストは reflection.md の各行について『絶対パス列が rubric.json を指す場合、その行が
「何を強制」列で挙げる rule-ID が当該 rubric に実在するか』を機械突合する。rubric.json は
rule-ID 構造が明確で false-positive を生まないため検査対象をこれに絞る (パスがディレクトリや
brace 展開の行は対象外)。standalone 配布で harness-creator が不在なら skip (repo 文脈で機能)。

射程の限界 (機械層 vs LLM 層の境界・正直開示): 本ガードは『非実在 rule-ID の引用』
(A6 の旧 PG/BND/REG=L0 に存在しない ID の誤帰属) を捕捉するが、『実在 rule-ID の**意味
ラベル**取り違え』は捕捉できない (ID 存在のみ検査するため)。実際 2026-06-30 の是正過程で
A6 に混入した『BD-004=TODO(human)』(BD-004 は L0 実在だが意味は description↔body 手順整合)
は本テストを素通りし、独立 approver の LLM 二段確認で検出された。意味ラベルの faithfulness は
機械層では縛れず、reflection.md の rule gloss 変更時は独立 SubAgent/人間の二段確認を残す運用が
前提 (機構=機械保証 / 内容判断=AI/人間 の二層分離)。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# tests/ -> run-plugin-dev-plan -> skills -> plugin-dev-planner -> plugins -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
_REFLECTION = (
    Path(__file__).resolve().parents[1] / "references" / "harness-creator-spec-reflection.md"
)
_HARNESS_CREATOR_SKILLS = _REPO_ROOT / "plugins" / "harness-creator" / "skills"
_ROW_RE = re.compile(r"^\|\s*[A-G]\d{1,2}\s*\|")
_RUBRIC_PATH_RE = re.compile(r"`([^`]*rubric\.json)`")
_BACKTICK_PATH_RE = re.compile(r"`([^`]+)`")
_RULE_ID_RE = re.compile(r"\b([A-Z]{2,4}-\d{1,3})\b")
# skill 名形状: prefix を伴い必ずハイフンを含む (assign-*/ref-*/run-*/wrap-*/delegate-*)。
# 表ヘッダの "skill" (ハイフン無し) や区切り "---" を確実に除外する。
_SKILL_NAME_RE = re.compile(r"[a-z][a-z0-9]*-[a-z0-9-]+")


def _completeness_proof_skill_names(md_text: str) -> set[str]:
    """reflection.md「完全性の証明」§ の skill 列挙表 (| skill | ラベル | 根拠 |) から
    skill 名集合を抽出する。`### skills/` 見出し〜次 `### ` 見出しの範囲のみ対象。"""
    names: set[str] = set()
    in_section = False
    for line in md_text.splitlines():
        if line.startswith("### skills/"):
            in_section = True
            continue
        if in_section and line.startswith("### "):
            break  # 次セクション (設計書 関連章) で終了
        if not in_section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 4:
            continue
        # 先頭 skill 名トークンを抽出 (注記サフィックス「(22章)」「(symlink→…)」を許容)。
        # ヘッダ "skill" (ハイフン無し) / 区切り "---" は先頭一致しないため除外される。
        m = _SKILL_NAME_RE.match(cells[1])
        if m:
            names.add(m.group(0))
    return names


def _rubric_rule_ids(path: Path) -> set[str]:
    """rubric.json から rule-ID (id / rule_id) を再帰抽出する。"""
    ids: set[str] = set()

    def walk(o: object) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("id", "rule_id") and isinstance(v, str):
                    ids.add(v)
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(json.loads(path.read_text(encoding="utf-8")))
    return ids


def _row_cells(line: str) -> list[str]:
    """Markdown table 行を | 区切りセルへ分解 (前後の空セルを保持)。"""
    return [c.strip() for c in line.split("|")]


def _cited_plugin_paths(md_text: str) -> list[tuple[str, str]]:
    """マトリクス『絶対パス』列から plugins/ 接頭の引用パスを (row-id, path) で抽出する。

    cross-plugin upstream 結合 (harness-creator / skill-governance-lint / prompt-creator) のみ
    対象とし、brace 展開 ({a,b}) / glob (*) を含むトークン (複数実体を畳む) と、bare ファイル名
    や tests/ 配下の注記トークン (絶対パス列の実引用でなく説明) は除外する。
    """
    out: list[tuple[str, str]] = []
    for line in md_text.splitlines():
        if not _ROW_RE.match(line):
            continue
        cells = _row_cells(line)
        if len(cells) < 6:
            continue
        rid, path_cell = cells[1], cells[3]
        for raw in _BACKTICK_PATH_RE.findall(path_cell):
            p = raw.strip()
            if p.startswith("plugins/") and not any(ch in p for ch in "{}*"):
                out.append((rid, p))
    return out


def test_matrix_rows_cite_real_rubric_rule_ids():
    """rubric.json を引用する行の rule-ID が当該 rubric に実在する (A6 型誤帰属の封止)。"""
    if not _REFLECTION.is_file():
        pytest.skip(f"reflection.md 不在: {_REFLECTION}")
    offenders: list[str] = []
    checked = 0
    skipped_absent = 0
    for line in _REFLECTION.read_text(encoding="utf-8").splitlines():
        if not _ROW_RE.match(line):
            continue
        cells = _row_cells(line)
        # cells: ['', ID, 仕様, 絶対パス, 何を強制, 焼き先, '']
        if len(cells) < 6:
            continue
        rid, path_cell, force_cell = cells[1], cells[3], cells[4]
        pm = _RUBRIC_PATH_RE.search(path_cell)
        if not pm:
            continue  # 絶対パス列が rubric.json を指さない行は対象外
        rubric_path = _REPO_ROOT / pm.group(1)
        if not rubric_path.is_file():
            skipped_absent += 1
            continue  # standalone 配布等で実体不在 → この行のみスキップ
        real_ids = _rubric_rule_ids(rubric_path)
        cited = set(_RULE_ID_RE.findall(force_cell))
        missing = sorted(c for c in cited if c not in real_ids)
        if missing:
            offenders.append(
                f"{rid}: {pm.group(1)} に不在の rule-ID を「何を強制」列が引用: {missing}"
            )
        checked += 1
    if checked == 0:
        pytest.skip(
            f"rubric.json 引用行を検査できず (不在 {skipped_absent} 行・standalone 配布?)"
        )
    assert not offenders, (
        "マトリクス散文が引用 rubric と不整合 (L0/L2 層の取り違え等):\n" + "\n".join(offenders)
    )


def test_matrix_integrity_catches_misattribution(tmp_path):
    """本ガードが A6 型誤帰属 (実在しない rule-ID 引用) を確かに fail させる回帰固定。"""
    rubric = tmp_path / "rubric.json"
    rubric.write_text(
        json.dumps({"layer": "L0", "rules": [{"id": "FM-001"}, {"id": "BD-001"}]}),
        encoding="utf-8",
    )
    real_ids = _rubric_rule_ids(rubric)
    # 正例: 実在 ID のみ引用 → 不整合なし
    good = set(_RULE_ID_RE.findall("FM-001(frontmatter) BD-001(body)"))
    assert not [c for c in good if c not in real_ids]
    # 負例: L2 固有 rule を L0 rubric に誤帰属 → 検出される
    bad = set(_RULE_ID_RE.findall("PG-001(prompts) BND-001(bundles) REG-001(trace)"))
    assert sorted(c for c in bad if c not in real_ids) == ["BND-001", "PG-001", "REG-001"]


def test_matrix_rows_cite_existing_plugin_paths():
    """マトリクス『絶対パス』列が引用する plugins/ 配下の実体が存在する (上流改名の無音 stale 化封止)。

    rule-ID 整合 (test_matrix_rows_cite_real_rubric_rule_ids) + skill 列挙
    (test_completeness_proof_enumerates_all_harness_creator_skills) に続く、上流結合の最後の辺
    = cross-plugin パス存在を機械保証する (2026-06-30 elegant-review DEF-1)。harness-creator が
    ファイルを改名/移動すると reflection.md のパス列が無音で stale 化し、生成 spec が dead path
    を焼いて後段 build 時に初めて発覚する因果連鎖を、plan/CI 時点へ前倒しして断つ。
    閾値値や gloss の faithfulness は機械化しない (意図的に LLM 二段確認へ残す=Goodhart 回避)。"""
    if not _REFLECTION.is_file():
        pytest.skip(f"reflection.md 不在: {_REFLECTION}")
    if not _HARNESS_CREATOR_SKILLS.is_dir():
        pytest.skip(f"harness-creator/skills 不在 (standalone 配布?): {_HARNESS_CREATOR_SKILLS}")
    cited = _cited_plugin_paths(_REFLECTION.read_text(encoding="utf-8"))
    if not cited:
        pytest.skip("検査可能な plugins/ 引用パスが無い")
    offenders = [
        f"{rid}: 引用パスが実在しない (上流改名/移動?): {p}"
        for rid, p in cited
        if not (_REPO_ROOT / p.rstrip("/")).exists()
    ]
    assert not offenders, (
        "マトリクス『絶対パス』列が上流実体と drift:\n" + "\n".join(offenders)
    )


def test_path_canary_helper_filters_and_extracts():
    """_cited_plugin_paths が plugins/ 接頭のみ抽出し brace/glob・非 plugins/ を除外する回帰固定。"""
    sample = (
        "| A1 | x | `plugins/harness-creator/skills/run-elegant-review/SKILL.md` | y | z |\n"
        "| F1 | x | `plugins/skill-governance-lint/scripts/{a,b}.py` | y | z |\n"  # brace 除外
        "| C3 | x | `sitecustomize.py` / `tests/test_scripts_smoke.py` | y | z |\n"  # 非 plugins/ 除外
        "| ZZ | not a row |\n"  # ID 形状でなく対象外
    )
    paths = {p for _, p in _cited_plugin_paths(sample)}
    assert paths == {"plugins/harness-creator/skills/run-elegant-review/SKILL.md"}


def test_completeness_proof_enumerates_all_harness_creator_skills():
    """循環論法 (分母自己定義) 解消の核 =「完全性の証明」のサーフェス全列挙が
    harness-creator/skills の実体と一致する。harness-creator が skill を増減したら
    本表の追記/削除漏れを機械検出し、『未分類の漏れ 0』証明の無音陳腐化を防ぐ
    (--self-test の行 ID 集合 drift 検査 + 本テストのサーフェス被覆 = 二層機械保証)。"""
    if not _HARNESS_CREATOR_SKILLS.is_dir():
        pytest.skip(f"harness-creator/skills 不在 (standalone 配布?): {_HARNESS_CREATOR_SKILLS}")
    if not _REFLECTION.is_file():
        pytest.skip(f"reflection.md 不在: {_REFLECTION}")
    actual = {
        p.name for p in _HARNESS_CREATOR_SKILLS.iterdir() if _SKILL_NAME_RE.fullmatch(p.name)
    }
    enumerated = _completeness_proof_skill_names(_REFLECTION.read_text(encoding="utf-8"))
    missing = sorted(actual - enumerated)  # 実体にあるが表に無い (追記漏れ)
    extra = sorted(enumerated - actual)    # 表にあるが実体に無い (削除漏れ)
    assert not missing and not extra, (
        "完全性の証明サーフェス列挙が harness-creator/skills と drift: "
        f"表に未登録の実体={missing} / 実体に無い表エントリ={extra}"
    )


# ─────────────────── 閾値の値 parity (島D: 数値=複製+値 parity) ───────────────────
# 三層方式「引用=path/ID+実在テスト、数値=複製+値 parity、意味 gloss=event-driven 監査」の
# 数値層。マトリクス散文と specfm が複製保持する数値を、引用先の機械可読値と突合する
# (sha256 pin (check-upstream-pins) は「変わったこと」しか言えない — どの数値が正か迄縛る)。

_ELEGANT_REFS = _REPO_ROOT / "plugins" / "harness-creator" / "skills" / "run-elegant-review" / "references"
_CONVERGENCE = _ELEGANT_REFS / "convergence-policy.json"
_FOUR_CONDITIONS = _ELEGANT_REFS / "4-conditions.json"
_HARNESS_SPEC = _REPO_ROOT / "doc" / "harness-coverage-spec.md"
_EVALUATOR_SKILL = (
    _REPO_ROOT / "plugins" / "harness-creator" / "skills" / "assign-skill-design-evaluator" / "SKILL.md"
)


def _matrix_row(row_id: str) -> str:
    """reflection.md の 46 行マトリクスから row_id の行を返す (不在は skip)。"""
    if not _REFLECTION.is_file():
        pytest.skip(f"reflection.md 不在: {_REFLECTION}")
    for line in _REFLECTION.read_text(encoding="utf-8").splitlines():
        if re.match(rf"^\|\s*{row_id}\s*\|", line):
            return line
    pytest.skip(f"マトリクスに {row_id} 行が無い")


def _load_or_skip(path: Path) -> dict:
    if not path.is_file():
        pytest.skip(f"引用先不在 (standalone 配布?): {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def test_matrix_a4_numbers_match_convergence_policy():
    """A4 行の数値 gloss ↔ convergence-policy.json の機械可読値 (収束閾値の値 parity)。"""
    row = _matrix_row("A4")
    policy = _load_or_skip(_CONVERGENCE)
    neg = policy["negative_feedback"]["thresholds"]
    params = policy["parameters"]
    bounds = policy["loop_bounds"]
    expectations = {
        "all_conditions_score_min": neg["all_conditions_score_min"],
        "delta_max_ratio": neg["delta_findings_count_max_ratio"],
        "max_iterations": params["max_iterations"],
        "rubric_min_score": params["rubric_min_score"],
    }
    for label, upstream in expectations.items():
        m = re.search(rf"{label}=([0-9.]+)", row)
        assert m, f"A4 行に {label}=<数値> の gloss が無い"
        assert float(m.group(1)) == float(upstream), (
            f"A4 行 {label}={m.group(1)} が convergence-policy.json の {upstream} と不一致 "
            "(数値複製は引用先変更と同一変更で追従すること)"
        )
    m = re.search(r"Δ<([0-9.]+)", row)
    assert m and float(m.group(1)) == float(params["delta_threshold"]), (
        f"A4 行の Δ 閾値が convergence-policy.json の delta_threshold={params['delta_threshold']} と不一致"
    )
    m = re.search(r"loop_bounds\((\d+)/(\d+)/(\d+)\)", row)
    assert m, "A4 行に loop_bounds(x/y/z) の gloss が無い"
    assert [int(g) for g in m.groups()] == [
        bounds["goal_seek_inner"]["value"],
        bounds["content_review_inner_reeval"]["value"],
        bounds["content_review_outer_reeval"]["value"],
    ], "A4 行の loop_bounds が convergence-policy.json の 3 ループ値と不一致"


def test_matrix_a1_matches_4_conditions():
    """A1 行の loop_limit / 各条件 severity ↔ 4-conditions.json の機械可読値。"""
    row = _matrix_row("A1")
    cond = _load_or_skip(_FOUR_CONDITIONS)
    m = re.search(r"loop_limit=(\d+)", row)
    assert m and int(m.group(1)) == cond["completion"]["loop_limit"], (
        f"A1 行の loop_limit が 4-conditions.json の {cond['completion']['loop_limit']} と不一致"
    )
    for c in cond["conditions"]:
        cm = re.search(rf"{c['id']}\s+\S*\(([^)]*)\)", row)
        assert cm, f"A1 行に {c['id']} の gloss が無い"
        assert c["severity_on_fail"] in cm.group(1), (
            f"A1 行 {c['id']} の severity gloss ({cm.group(1)}) が "
            f"4-conditions.json の severity_on_fail={c['severity_on_fail']} と不一致"
        )


def test_specfm_harness_min_matches_coverage_spec(specfm_mod):
    """specfm.HARNESS_MIN_REQUIRED (=C1 行の ≥80%) が doc/harness-coverage-spec.md の
    閾値表現と一致する (散文 anchor による値 parity — 上流が値を 85 等へ改訂すれば
    「80% 以上」表現が消えて fail し、specfm 側の追従を強制する)。"""
    if not _HARNESS_SPEC.is_file():
        pytest.skip(f"harness-coverage-spec.md 不在 (standalone 配布?): {_HARNESS_SPEC}")
    text = _HARNESS_SPEC.read_text(encoding="utf-8")
    anchor = f"{specfm_mod.HARNESS_MIN_REQUIRED}% 以上"
    assert anchor in text, (
        f"harness-coverage-spec.md に『{anchor}』表現が無い — 上流閾値の改訂? "
        "specfm.HARNESS_MIN_REQUIRED を追従し pin bump と同一変更で更新すること"
    )


def test_specfm_evaluator_threshold_matches_evaluator_skill(specfm_mod):
    """specfm 複製の evaluator threshold (valid_quality_gates が焼く 80) が
    assign-skill-design-evaluator の契約例 (SKILL.md 内 fenced JSON) と一致する。"""
    if not _EVALUATOR_SKILL.is_file():
        pytest.skip(f"assign-skill-design-evaluator/SKILL.md 不在 (standalone 配布?): {_EVALUATOR_SKILL}")
    threshold = specfm_mod.valid_quality_gates("skill")["evaluator"]["threshold"]
    anchor = f'"threshold": {threshold}'
    assert anchor in _EVALUATOR_SKILL.read_text(encoding="utf-8"), (
        f"evaluator SKILL.md に {anchor} が無い — 上流閾値の改訂? specfm の evaluator "
        "threshold (valid_quality_gates / validate_component_quality_gates) を追従すること"
    )


def test_specfm_evaluator_high_max_upstream_prose_only():
    """evaluator high_max==0 の値 parity は機械化不能 — fail-open の明示 skip。

    引用先候補を走査した結果: 4-conditions.json は条件定義のみ (high_max 数値なし)、
    evaluator-output.schema.json は threshold の型域のみ、assign-skill-design-evaluator
    SKILL.md は severity weight (high -20) の散文のみで high_max=0 の機械可読正本が無い。
    値の凍結は upstream-pins.json の sha256 pin (event-driven 監査=drift 時に matrix_rows
    再監査) が担い、本テストは検査対象不在を記録として明示する。
    """
    pytest.skip("high_max=0 の上流機械可読正本なし — sha256 pin (check-upstream-pins) の再監査運用で担保")


def test_completeness_proof_parser_excludes_header():
    """表ヘッダ 'skill' / 区切り '---' を除外し、注記サフィックス付き名は先頭 token を抽出する回帰固定。"""
    sample = (
        "### skills/ 全 31 本\n"
        "| skill | ラベル | 根拠 |\n"
        "|---|---|---|\n"
        "| run-build-skill | 反映済 C4 | build |\n"
        "| ref-pkg-contract | 反映済 F5 | PKG |\n"
        "| ref-output-routing (31章) | 意図的除外 | routing |\n"  # 注記サフィックス
        "| run-contract-finalize (symlink→contract-generator) | 意図的除外 | x |\n"
        "### 設計書 関連章\n"
        "| run-should-not-appear | x | y |\n"  # 次セクションは対象外
    )
    names = _completeness_proof_skill_names(sample)
    assert names == {
        "run-build-skill", "ref-pkg-contract", "ref-output-routing", "run-contract-finalize",
    }


# ─────────────────── マトリクス行数の値 parity (二重保持台帳の機械辺) ───────────────────
# 散文の「46 行」複製が上流 (reflection.md の実行 ID 数) と乖離すると stale になる
# (旧「44 行」が R4/assign 側で実際に腐った前例)。行数を散文に残すファイルは
# ここで実数と突合する (行が増減したら散文も同一変更で更新することを強制)。

_MATRIX_ROW_ID_RE = re.compile(r"^\|\s*([A-G][0-9]+)\s*\|")


def _matrix_row_count() -> int:
    """reflection.md マトリクスの実行 ID 数 (A1..G6 形式の table 行) を数える。"""
    if not _REFLECTION.is_file():
        pytest.skip(f"reflection.md 不在: {_REFLECTION}")
    ids = {
        m.group(1)
        for line in _REFLECTION.read_text(encoding="utf-8").splitlines()
        if (m := _MATRIX_ROW_ID_RE.match(line))
    }
    return len(ids)


def test_matrix_row_count_prose_parity():
    """散文の行数複製 (「全 N 行」「N 行マトリクス」等) が実行 ID 数と一致する。

    対象 = 行数を数値で明記する主要 projection (reflection.md 自身 / SKILL.md /
    io-contract §11 / docs 設計書)。数値を書かない引用形 (「マトリクス全行」) は対象外。
    """
    actual = _matrix_row_count()
    skill_dir = Path(__file__).resolve().parents[1]
    plugin_root = skill_dir.parents[1]
    # agents/*.md・commands/*.md も走査母数に含める。2026-07-02 elegant-review (M1/S8):
    # architect agent が「44 行」で腐ったのに parity 対象が SKILL/io-contract/reflection の
    # 3 ファイル固定で agents/commands を取りこぼしていた構造穴を封じる (drift 生息域の網羅)。
    prose_files = [
        _REFLECTION,
        skill_dir / "SKILL.md",
        skill_dir / "references" / "io-contract.md",
        *sorted((plugin_root / "agents").glob("*.md")),
        *sorted((plugin_root / "commands").glob("*.md")),
    ]
    pat = re.compile(r"(?:全\s*)?(\d+)\s*行(?:マトリクス|反映|を|の|と|」)?")
    for path in prose_files:
        if not path.is_file():
            pytest.skip(f"projection 不在: {path}")
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in pat.finditer(line):
                n = int(m.group(1))
                # マトリクス行数を指す文脈のみ突合 (「13 フェーズ」「43 行 (指示インベントリ)」等の
                # 他数値と区別するため、同一行に reflection/マトリクス/仕様 の語がある場合に限る)
                context = ("マトリクス" in line or "harness-creator 仕様" in line
                           or "harness-creator-spec-reflection" in line or "46行" in line)
                if not context or n in {43, 13}:  # 43=指示インベントリの歴史的内訳・13=フェーズ数
                    continue
                if 40 <= n <= 60:  # マトリクス行数域の数値のみ検査
                    assert n == actual, (
                        f"{path.name}:{lineno} の行数複製 {n} が実マトリクス {actual} 行と乖離 "
                        f"(行を増減したら散文も同一変更で更新する=二重保持台帳の規律)"
                    )
