#!/usr/bin/env python3
# /// script
# name: specfm
# purpose: タスク仕様書 frontmatter の最小 YAML サブセットパーサと component_kind 別契約/criteria 制約の単一正本 (import 専用モジュール)。
# inputs: []
# outputs: []
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""タスク仕様書 frontmatter の共有パーサ + 契約定数 (SSOT)。

check-spec-frontmatter.py / check-spec-gates.py / check-spec-matrix-coverage.py が
import 共有する。yaml は import しない (scripts 規約)。nested map / inline flow list /
block list (scalar item or 平坦 map item) を扱う最小 YAML サブセットを解析する。

feedback_contract.criteria の制約は plugins/harness-creator/scripts/feedback_contract_ssot.py を
逐語複製 (plugin 自己完結のため cross-plugin import を避ける)。
"""
from __future__ import annotations

import re

# ─────────────────────────── 二重保持台帳 (複製契約の登録簿) ───────────────────────────
# 本 module は plugin 自己完結のため上流契約を複製保持する。**新規複製は本台帳へ登録し
# parity test を同時に追加すること** (登録漏れ = 無音 drift の温床)。「(projection)」は
# 本 module 側が機械正本で相手が人間可読写像、無印は相手側が正本で本 module が複製。
# | 定数 / 値 | 相手 (upstream パス or projection 先) | parity test |
# |---|---|---|
# | CRITERIA_ID_RE / CRITERIA_VERIFY_BY / LOOP_SCOPES / REQUIRED_CRITERION_KEYS / FEEDBACK_LOOP_SKILL_KINDS | plugins/harness-creator/scripts/feedback_contract_ssot.py | tests/test_schema_parity.py |
# | SKILL_BRIEF_FIELDS / SKILL_BRIEF_PRESENCE_ONLY / skill_conditional_required | plugins/harness-creator/skills/run-skill-create/schemas/skill-brief.schema.json | tests/test_schema_parity.py |
# | SKILL_P0_LINTS | plugins/skill-governance-lint/scripts/*.py (実体 glob) | tests/test_schema_parity.py |
# | evaluator threshold>=80 / high_max==0 (validate_component_quality_gates) | plugins/harness-creator/skills/assign-skill-design-evaluator/ + references/4-conditions.json | tests/test_matrix_doc_integrity.py |
# | HARNESS_MIN_REQUIRED=80 | doc/harness-coverage-spec.md | tests/test_matrix_doc_integrity.py |
# | BUILDER_BY_KIND / BUILD_KIND_BY_KIND / BUILDER_STATUS | references/io-contract.md §9 build handoff 契約 (projection) | tests/test_kind_key_doc_parity.py |
# | PHASE_BODY_SECTIONS | references/io-contract.md §5 表 / prompts/R3-emit-specs.md (projection) | tests/test_kind_key_doc_parity.py |
# | INDEX_REQUIRED_SECTIONS | references/io-contract.md §9 / verify-index-topsort docstring (projection) | tests/test_kind_key_doc_parity.py |
# | GATE_SCRIPTS | references/io-contract.md §11 表 / SKILL.md / golden index.md (projection) | tests/test_kind_key_doc_parity.py |
# | GATE_SCOPE / evaluator_plan_gate_scripts | assign-plugin-plan-evaluator/scripts/evaluate-plan.py の _gate_defs (projection) | assign-plugin-plan-evaluator/tests/test_gate_parity.py |

# --- feedback_contract.criteria SSOT 制約 (feedback_contract_ssot.py 逐語) ---
CRITERIA_ID_RE = re.compile(r"^(IN|OUT|C)[0-9]+$")
CRITERIA_VERIFY_BY = {"lint", "test", "script", "evaluator", "elegant-review", "live-trial", "human", "verification-obligation"}
LOOP_SCOPES = {"inner", "outer"}
REQUIRED_CRITERION_KEYS = ("id", "loop_scope", "text", "verify_by")

# --- component_kind / skill kind の語彙 ---
COMPONENT_KINDS = ("skill", "sub-agent", "slash-command", "hook", "script")
SKILL_KINDS = ("run", "ref", "wrap", "assign", "delegate")
FEEDBACK_LOOP_SKILL_KINDS = ("run", "wrap", "delegate")
HOOK_EVENTS = ("PreToolUse", "PostToolUse", "Stop", "UserPromptSubmit", "SessionEnd")
HARNESS_MIN_REQUIRED = 80
# component の配置境界 (deploy 境界の内/外)。既定 skill=当該 skill 配下、plugin-root=
# plugins/<slug>/scripts/ へ hoist した共有 script。属性であって新 component_kind ではない。
PLACEMENT_SCOPES = ("skill", "plugin-root")
PLUGIN_LEVEL_SURFACES = (
    "manifest",
    "composition",
    "harness_eval",
    "references_config_assets",
    "schemas",
    "vendor",
    "mcp_app_connector",
    # feedback+Notion 連携の宣言スロット (Option 1)。DB キー=plan 宣言 / DB ID=設置先
    # .notion-config.json 供給の二層分離 (解決 SSOT=plugins/harness-creator/scripts/notion_config.py
    # の名前参照のみ・ロジック再実装禁止)。required:true の値域は validate_surface_inventory が検査。
    "notion_config",
)

# --- component_kind 別の構造的必須 frontmatter キー (kind 別分岐) ---
# skill は skill-brief.schema.json の base required 14 と逐語一致 (schema parity の正本)。
# 旧版は言い換えで 6 フィールド(cli_tools/deterministic_checks/external_systems/mcp_tools/
# needs_independent_context/needs_lifecycle_enforcement)を欠落し「無加工で写せる」が偽だった。
# 実 schema: plugins/harness-creator/skills/run-skill-create/schemas/skill-brief.schema.json#required
SKILL_BRIEF_FIELDS = (
    "skill_name", "prefix", "kind", "hierarchy_level", "trigger_conditions",
    "output_contract", "boundary", "placement_candidates",
    "cli_tools", "deterministic_checks", "external_systems", "mcp_tools",
    "needs_independent_context", "needs_lifecycle_enforcement",
)
# 存在のみ要求 (実 schema で minItems 無し=空配列/false も valid)。空でも欠落扱いしない。
SKILL_BRIEF_PRESENCE_ONLY = frozenset({
    "cli_tools", "deterministic_checks", "external_systems", "mcp_tools",
    "needs_independent_context", "needs_lifecycle_enforcement",
})
STRUCTURAL_REQUIRED = {
    "skill": SKILL_BRIEF_FIELDS,
    "sub-agent": ("name", "description", "tools", "independent_context", "responsibility_anchor"),
    "slash-command": ("name", "description", "argument-hint", "allowed-tools", "disable-model-invocation"),
    "hook": ("event", "matcher", "exit_semantics", "settings_wiring", "fail_closed"),
    "script": ("script_name", "purpose", "inputs", "outputs", "exit_codes",
               "network", "write_scope", "stdlib_only", "tests_min"),
}


def skill_conditional_required(skill_kind: str) -> tuple[str, ...]:
    """skill-brief.schema の allOf 条件付き required を skill kind で返す。

    prefix∈{run,wrap,assign,delegate} → goal/purpose_background/checklist、
    kind∈{run,assign} → responsibilities、wrap → base_skill、delegate → delegate_agent。
    (実 schema の allOf を逐語反映。L2→rubric_refs は hierarchy_level 軸で別途)
    """
    req: list[str] = []
    if skill_kind in ("run", "wrap", "assign", "delegate"):
        req += ["goal", "purpose_background", "checklist"]
    if skill_kind in ("run", "assign"):
        req.append("responsibilities")
    if skill_kind == "wrap":
        req.append("base_skill")
    if skill_kind == "delegate":
        req.append("delegate_agent")
    return tuple(req)

# --- quality_gates.p0_lint が component_kind 別に網羅すべき lint 集合 ---
SKILL_P0_LINTS = (
    "lint-skill-name", "lint-skill-description", "lint-skill-tree", "validate-frontmatter",
    "lint-dependency-direction", "lint-skill-dep-step7", "lint-forbidden-deps", "lint-manifest-contents",
)
P0_LINT_BY_KIND = {
    "skill": SKILL_P0_LINTS,
    "sub-agent": ("validate-frontmatter", "lint-skill-description", "lint-agent-prompt-section"),
    "slash-command": ("validate-frontmatter",),  # 注: command 専用 lint は未提供。実在する validate-frontmatter のみ
    "hook": ("validate-frontmatter", "lint-script-frontmatter"),
    "script": ("lint-script-frontmatter",),
}

# --- component_kind → 後段 builder / build_kind マッピング (io-contract §9 build handoff 契約の SSOT) ---
# routes[] は component-inventory.json の components[] から導出する (phase からではない)。
# builder/build_kind の整合はこの写像を正本にして validate_inventory_component / check-build-handoff が検査する。
BUILDER_BY_KIND = {
    "skill": "run-skill-create",
    "sub-agent": "run-build-skill",
    "slash-command": "run-build-skill",
    "hook": "run-build-skill",
    "script": "parent-skill-build",
}
BUILD_KIND_BY_KIND = {
    "skill": "skill",
    "sub-agent": "agent",
    "slash-command": "command",
    "hook": "hook",
    "script": "script",
}
# builder → 実行実体の有無 (io-contract §9 build handoff 契約「builder → 実行手段の解決表」の機械正本)。
# executor-backed = 実在 skill が build を実行できる / contract-only = planner 上の routing 語彙で
# run-build-skill の 7 kind ではない。script route は L4 で harness-creator/scripts/build-script-route.py
# が消費するが、contract-only の route は handoff の open_issues に routing gap を起票し
# routes[].gap_ref で追跡することを check-build-handoff が fail-closed 強制する。
BUILDER_STATUSES = ("executor-backed", "contract-only")
BUILDER_STATUS = {
    "run-skill-create": "executor-backed",
    "run-build-skill": "executor-backed",
    "parent-skill-build": "contract-only",
    "plugin-scaffold": "contract-only",
}
# elegant-review 4 条件 (quality_gates.elegant_review.conditions の SSOT)。
ELEGANT_CONDITIONS = ("C1", "C2", "C3", "C4")

# ─────────────────────────── task-graph (第3の射影) の語彙 SSOT (C1/C10/C13/C16) ───────────────────────────
# task-graph.json / task-state.json / plan-ledger.json の共有語彙。derive/validate/compute-ready-set/
# check-task-state-schema/render-task-graph-mermaid/check-plan-ledger が本定数を単一正本として参照する
# (値域を各 script に複製しない=doc-points-to-SSOT)。
# canonical task-graph node.state の seed 値域。runtime更新は task-state.json のみ。
TASK_NODE_STATES = ("pending",)
# task-state.json へ永続化される runtime state 4 値 (harness ALLOWED_TRANSITIONS と整合)。
# ready は compute-ready-set の出力にのみ現れる派生状態で、永続 state に焼くのは非正準 (validate が拒否)。
TASK_STATE_PERSISTED = ("pending", "running", "done", "blocked")
# task-graph edge の型 4 種。blocks は独立宣言禁止の派生ビューゆえ列挙に含めない (schema レベルで機械強制)。
TASK_EDGE_TYPES = ("parent_of", "depends_on", "produces", "consumes")
# blocked node の起点区別 (GAP-FAILED-STATE-VOCAB 解消・state==blocked のとき条件付き必須の第一級 field)。
BLOCKED_REASONS = ("origin-failure", "propagated")
# index.md frontmatter の shape_marker 値域。既定 fixed-13-phase (task-graph-derived は C14 非劣化ゲート PASS が前提)。
SHAPE_MARKERS = ("fixed-13-phase", "task-graph-derived")
# plan-ledger.json の cycle_id 形式 (YYYYMMDD-<concept-slug>) と status 値域 (C13)。
CYCLE_ID_RE = re.compile(r"^\d{8}-[a-z0-9-]+$")
LEDGER_STATUSES = ("active", "finished", "superseded")
# task node の実行分類 (C17)。component-build だけが明示 route_ref を持ち dispatch 対象、
# direct-task は route_ref を持たない実行タスク、phase-gate は非 dispatch の phase 完了集約点。
# entity_ref は分類/traceability 専用であり builder 選択には使わない (暗黙 route を fail-closed 拒否)。
EXECUTION_KINDS = ("direct-task", "component-build", "phase-gate")
# envelope 合成 (dispatch) 対象の execution_kind (phase-gate は集約点ゆえ dispatch 対象外)。
DISPATCHABLE_EXECUTION_KINDS = ("direct-task", "component-build")
# task spec の knowledge_refs.decision 値域 (C19・過去 cycle 蒸留知見の採否)。
KNOWLEDGE_DECISIONS = ("adopted", "rejected")

# ─────────────────────────── 決定論ゲートの単一正本 (名称 + 起動引数・2 層命名) ───────────────────────────
# core = plan 本体の 5 scripts / 6 invocations (matrix-coverage は --self-test と PLAN の 2 起動)。
# extended = 入力ゲート/採否/routing/install 携帯性/dogfood の拡張ゲート。SKILL.md・golden index・
# io-contract §11 の列挙は本定数の人間可読 projection (総数の散文正本は io-contract §11 表)。
# <PLAN_DIR> は plan_output_dir が解決する計画出力先へ置換して起動する (repo-root cwd 前提)。
GATE_SCRIPTS = {
    "core": (
        ("verify-index-topsort.py", "<PLAN_DIR>"),
        ("detect-unassigned.py", "--inventory <PLAN_DIR>/component-inventory.json --specs-dir <PLAN_DIR>"),
        ("check-spec-frontmatter.py", "--specs-dir <PLAN_DIR>"),
        ("check-spec-gates.py", "--specs-dir <PLAN_DIR>"),
        ("check-spec-matrix-coverage.py", "--self-test"),
        ("check-spec-matrix-coverage.py", "<PLAN_DIR>"),
    ),
    "extended": (
        ("check-plugin-goal-spec.py", "<PLAN_DIR>/goal-spec.json"),
        ("check-requirements-coverage.py", "<PLAN_DIR>"),
        ("check-surface-inventory.py", "<PLAN_DIR>/component-inventory.json"),
        ("check-build-handoff.py", "<PLAN_DIR>/handoff-run-plugin-dev-plan.json"),
        ("validate-task-graph.py", "<PLAN_DIR>"),
        ("check-runtime-portability.py", "<PLAN_DIR>"),
        ("check-plugin-surface-audit.py", "--plugins-dir plugins --strict-manifest --expect-plan-ready plugin-dev-planner"),
    ),
}

# ─────────── ゲート実行 scope 分類 (独立評価器が PLAN に回す集合の SSOT・S2/S11) ───────────
# 独立評価器 (assign-plugin-plan-evaluator の evaluate-plan.py._gate_defs) がどのゲートを
# PLAN_DIR に対し必ず実行するかを GATE_SCRIPTS から導く分類。extended へゲートを足したとき
# 評価器の実行経路へ伝播したかを test_gate_parity が本分類で機械照合する。
# 2026-06-30 build-handoff / 2026-07-02 runtime-portability の「planner 側 SSOT には載ったが
# 評価器 _gate_defs へ伝播せず、壊れた plan が独立評価を PASS しうる」Goodhart 穴の再発を封じる根。
#   plan-scoped = 評価器が PLAN_DIR に対し必ず実行 (plan の 4 条件に直結)
#   input-gate  = R1 が goal-spec に対し実行 (評価器は requirements-coverage で被覆を検査するため再実行しない)
#   dogfood     = plugin-dev-planner 自身の現物 surface 検査 (PLAN_DIR 非対象ゆえ評価器から除外)
GATE_SCOPE = {
    "verify-index-topsort.py": "plan-scoped",
    "detect-unassigned.py": "plan-scoped",
    "check-spec-frontmatter.py": "plan-scoped",
    "check-spec-gates.py": "plan-scoped",
    "check-spec-matrix-coverage.py": "plan-scoped",
    "check-requirements-coverage.py": "plan-scoped",
    "check-surface-inventory.py": "plan-scoped",
    "check-build-handoff.py": "plan-scoped",
    "validate-task-graph.py": "plan-scoped",
    "check-runtime-portability.py": "plan-scoped",
    "check-plugin-goal-spec.py": "input-gate",
    "check-plugin-surface-audit.py": "dogfood",
}


def all_gate_scripts() -> tuple[str, ...]:
    """GATE_SCRIPTS 全 group の script 名を出現順・重複排除で返す (matrix は 1 script)。"""
    seen: list[str] = []
    for group in GATE_SCRIPTS.values():
        for name, _args in group:
            if name not in seen:
                seen.append(name)
    return tuple(seen)


def evaluator_plan_gate_scripts() -> tuple[str, ...]:
    """独立評価器が PLAN_DIR に対し実行すべきゲート script 名 (plan-scoped 集合)。

    GATE_SCRIPTS を GATE_SCOPE で filter した唯一の導出。evaluate-plan.py._gate_defs は
    この集合を漏れなく実行しなければならず、test_gate_parity が両者を機械照合する
    (input-gate=goal-spec / dogfood=surface-audit は PLAN 非対象ゆえ評価器から除外)。
    """
    return tuple(s for s in all_gate_scripts() if GATE_SCOPE.get(s) == "plan-scoped")


def placement_of(comp: dict) -> str:
    """component の placement_scope を解決する (未指定/空は既定 "skill")。"""
    v = comp.get("placement_scope")
    return v.strip() if isinstance(v, str) and v.strip() else "skill"


def builder_for(component_kind: str, placement_scope: str = "skill") -> str:
    """placement_scope を builder 選択へ写す。plugin-root 実体化は plugin-scaffold が担う。

    共有 script (plugin-root へ hoist) は親 skill build でなく plugin-scaffold が
    plugins/<slug>/scripts/ 直下へ実体化する。その他は §9 build handoff 契約の kind→builder 写像に従う。
    """
    if component_kind == "script" and placement_scope == "plugin-root":
        return "plugin-scaffold"
    return BUILDER_BY_KIND[component_kind]


# ─────────────────────────── 13 フェーズ定義 (per-phase 分解の SSOT) ───────────────────────────
# per-component (旧 C*.md) 分解を廃し、人間可読な 13 フェーズ (ファイル軸 = phase-NN-<kebab>.md) と
# component-inventory.json (build 軸) の 2 軸直交へ全面転換した (references/component-domain.md)。
# 各 phase = 1 Markdown ファイル。phase_number-1 で PHASE_NAMES を index する (1 始まり)。
PHASE_NAMES = (
    "requirements", "design", "design-review", "test-design", "implementation",
    "test-run", "acceptance-criteria", "refactoring", "quality-assurance",
    "final-review", "evidence", "documentation", "release",
)
# category は日本語ラベル (enum 緩め・phase-lifecycle.md §8 の値を使う)。
PHASE_CATEGORY = {
    "requirements": "要件",
    "design": "設計",
    "design-review": "レビュー",
    "test-design": "テスト",
    "implementation": "実装",
    "test-run": "テスト",
    "acceptance-criteria": "判定",
    "refactoring": "改善",
    "quality-assurance": "品質",
    "final-review": "レビュー",
    "evidence": "検証",
    "documentation": "文書",
    "release": "完了",
}
PHASE_GATE_TYPE = {
    "requirements": "none",
    "design": "none",
    "design-review": "design-gate",
    "test-design": "tdd-red",
    "implementation": "tdd-green",
    "test-run": "none",
    "acceptance-criteria": "none",
    "refactoring": "tdd-refactor",
    "quality-assurance": "qa",
    "final-review": "final-gate",
    "evidence": "evidence",
    "documentation": "none",
    "release": "none",
}
# id は大文字ゼロ埋め 2 桁 (P01..P13)。
PHASE_ID_RE = re.compile(r"^P(0[1-9]|1[0-3])$")
GATE_TYPES = {"none", "design-gate", "final-gate", "tdd-red", "tdd-green", "tdd-refactor", "qa", "evidence"}
PHASE_STATUS = {"未実施", "進行中", "完了"}
# phase ファイル frontmatter の必須キー (io-contract §9 phase projection 表と parity=schemas/phase-spec.schema.json)。
PHASE_REQUIRED = (
    "id", "phase_number", "phase_name", "category", "prev_phase",
    "next_phase", "status", "gate_type", "entities_covered", "applicability",
)
# ─────────────────────────── 宣言型セクション床の SSOT (仕様書標準・毎回再現性) ───────────────────────────
# 「宣言型 + 毎回再現性」= セクション構造を specfm で凍結し detect-unassigned / verify-index-topsort が
# 床 (見出し存在 + 直後の非空本文) を機械強制する。各節の散文内容は下流トラスト (形状と手順の直交)。
# 各 phase ドキュメント本文 (§5) が備える仕様書標準セクション。宣言型 (declarative) 方針で
# 手続き的な「実行タスク」を排し、到達すべき状態 (成果物) と満たすべき二値条件 (完了チェックリスト)
# だけを宣言する (HOW = 具体手順は後段 build/実行者に委ねる)。意味的に独立な最小集合へ畳んだ
# (冗長統合: ゴール⊂成果物 / 達成条件・完了条件⊂完了チェックリスト / 入力⊂前提条件・
# 実行タスクは宣言型ゆえ排除)。単独実行の自足性 (実行者が phase ファイルだけで着手→完了判定
# →次 phase へ移行できる) のため、ドメイン知識 (phase 固有の前提知識) とスコープ外 (境界宣言)
# を持つ。読み順=目的→背景→前提条件→ドメイン知識→成果物→スコープ外→完了チェックリスト→参照情報。
# detect-unassigned が REQUIRED_SECTIONS として import する。
PHASE_BODY_SECTIONS = (
    "## 目的",              # なぜこのフェーズが要るか (到達状態の意図)
    "## 背景",              # 文脈・前段の状況・関連制約
    "## 前提条件",          # 開始前に満たすべき状態・受け取る入力 (先行成果物/参照/component id)
    "## ドメイン知識",      # phase 固有の用語・不変条件・外部制約 (plan 全体の用語集=index ## ドメイン知識 への引用+差分のみ・重複焼込禁止)
    "## 成果物",            # 確定/生成する到達成果物 (=ゴール状態の具体化・build 実体は component-inventory.json が SSOT)
    "## スコープ外",        # このフェーズで扱わない事項と委譲先 phase/component (境界宣言・次タスクへの移行点を確定)
    "## 完了チェックリスト",  # 完了=達成を宣言的に判定する観測可能な二値項目 (gate フェーズは gate_type 合否)
    "## 参照情報",          # 参照すべき正本・資料・関連 component/phase
)
# index(main) が備える基盤層 + 全体制御セクション。elegant-review 7 層 (Layer1 基本定義 / Layer2 ドメイン /
# Layer3 インフラ / Layer4 共通ポリシー) を計画の土台として index へ焼き、フェーズ一覧・完了チェックリスト・
# 受入確認と併せて verify-index-topsort が床を機械強制する (計画全体の宣言型コンテキストの再現性)。
INDEX_REQUIRED_SECTIONS = (
    "## 基本定義",        # メタ情報・最上位目的・スコープ (Layer 1)
    "## ドメイン知識",    # 用語集・ドメイン前提知識 (Layer 2)
    "## インフラ",        # ツール・実行環境・依存 (Layer 3)
    "## 環境ポリシー",    # 品質基準・共通ポリシー・エスカレーション (Layer 4)
    "## フェーズ一覧",    # P01..P13 を phase_number 昇順で全列挙 (verify-index-topsort が別途 top-sort 検証)
    "## 完了チェックリスト",  # 計画全体の完了=達成を判定する観測可能な二値項目 (基盤層〜inventory 網羅の充足)
    "## 受入確認",        # build 後に purpose 充足を確認する trace (成果物評価)
)


# ─────────────────────────── 最小 YAML サブセットパーサ ───────────────────────────
def split_frontmatter(text: str) -> str | None:
    """先頭 --- ブロック本文を返す (無ければ None)。"""
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return parts[1]


def phase_body_sections(text: str) -> dict[str, str]:
    """phase Markdown 本文を {"## 見出し": 本文} へ分解する (frontmatter/H1 を除外)。

    `## ` (H2) のみを節境界にし `### ` サブ見出しは親 H2 本文へ内包する。本文は strip 済み。
    §5 節床検査・生成時品質検査 (未カスタマイズ/曖昧語)・下流ハーネス検査 (受入例サブ節) の
    共有 SSOT パーサ (節本文抽出を各 script に複製しない=doc-points-to-SSOT)。
    """
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line.strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _strip_comment(v: str) -> str:
    """スカラ値から YAML コメントを除去する (flow list / quote 内は保持)。"""
    v = v.strip()
    if v.startswith("#"):
        return ""
    if v.startswith(("[", "{", '"', "'")):
        return v
    m = re.search(r"\s#", v)
    return v[: m.start()].strip() if m else v


def _split_top(inner: str) -> list[str]:
    """カンマ区切りを深さ0で分割する (ネストした [] {} 内のカンマは保持)。"""
    parts: list[str] = []
    depth = 0
    buf = ""
    for ch in inner:
        if ch in "[{":
            depth += 1
            buf += ch
        elif ch in "]}":
            depth -= 1
            buf += ch
        elif ch == "," and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return [p.strip() for p in parts if p.strip()]


def _scalar(v: str):
    """文字列値を bool / int / list / dict(inline flow) / str へ変換する。"""
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in _split_top(inner)] if inner else []
    if v.startswith("{") and v.endswith("}"):
        inner = v[1:-1].strip()
        d: dict = {}
        for pair in _split_top(inner):
            if ":" in pair:
                k, _, val = pair.partition(":")
                d[k.strip()] = _scalar(val.strip())
        return d
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def _tokens(fm_text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for raw in fm_text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        out.append((indent, raw.strip()))
    return out


def _parse_map(toks: list[tuple[int, str]], pos: int, indent: int):
    result: dict = {}
    while pos < len(toks):
        ci, content = toks[pos]
        if ci != indent or content.startswith("- "):
            break
        key, _, raw = content.partition(":")
        key = key.strip()
        val = _strip_comment(raw.strip())
        pos += 1
        if val == "":
            if pos < len(toks) and toks[pos][0] > indent:
                child_indent = toks[pos][0]
                if toks[pos][1].startswith("- "):
                    child, pos = _parse_list(toks, pos, child_indent)
                else:
                    child, pos = _parse_map(toks, pos, child_indent)
                result[key] = child
            else:
                result[key] = None
        else:
            result[key] = _scalar(val)
    return result, pos


def _parse_list(toks: list[tuple[int, str]], pos: int, indent: int):
    items: list = []
    while pos < len(toks):
        ci, content = toks[pos]
        if ci != indent or not content.startswith("- "):
            break
        rest = content[2:].strip()
        inner_indent = indent + 2
        if ":" in rest and not rest.startswith("["):
            item: dict = {}
            k, _, v = rest.partition(":")
            item[k.strip()] = None if _strip_comment(v.strip()) == "" else _scalar(_strip_comment(v.strip()))
            pos += 1
            sub, pos = _parse_map(toks, pos, inner_indent)
            item.update(sub)
            items.append(item)
        else:
            items.append(_scalar(_strip_comment(rest)))
            pos += 1
    return items, pos


def parse_frontmatter(text: str) -> dict:
    """SKILL/spec の frontmatter を nested dict に解析する (yaml 非依存)。"""
    fm = split_frontmatter(text)
    if fm is None:
        return {}
    toks = _tokens(fm)
    if not toks:
        return {}
    value, _ = _parse_map(toks, 0, toks[0][0])
    return value


# ─────────────────────────── 共有バリデータ ───────────────────────────
def validate_criteria(criteria) -> list[str]:
    """feedback_contract.criteria を SSOT 制約で検査 (inner+outer 各 1 件以上)。"""
    errs: list[str] = []
    if not isinstance(criteria, list) or not criteria:
        return ["feedback_contract.criteria が空 (inner/outer 各 1 件以上を携帯すること)"]
    seen_ids: set[str] = set()
    seen_scopes: set[str] = set()
    for idx, item in enumerate(criteria):
        if not isinstance(item, dict):
            errs.append(f"criteria[{idx}] が object でない")
            continue
        for key in REQUIRED_CRITERION_KEYS:
            v = item.get(key)
            if not (isinstance(v, str) and v.strip()):
                errs.append(f"criteria[{idx}].{key} が空")
        cid = str(item.get("id", "")).strip()
        if cid and not CRITERIA_ID_RE.match(cid):
            errs.append(f"criteria[{idx}].id={cid!r} は ^(IN|OUT|C)[0-9]+$ に不一致")
        if cid and cid in seen_ids:
            errs.append(f"criteria[{idx}].id={cid!r} が重複")
        seen_ids.add(cid)
        vb = str(item.get("verify_by", "")).strip()
        if vb and vb not in CRITERIA_VERIFY_BY:
            errs.append(f"criteria[{idx}].verify_by={vb!r} が enum 外 {sorted(CRITERIA_VERIFY_BY)}")
        scope = str(item.get("loop_scope", "")).strip().lower()
        if scope and scope not in LOOP_SCOPES:
            errs.append(f"criteria[{idx}].loop_scope={scope!r} は inner|outer のみ")
        elif scope:
            seen_scopes.add(scope)
    for required_scope in ("inner", "outer"):
        if required_scope not in seen_scopes:
            errs.append(f"feedback_contract.criteria に {required_scope} loop_scope が 1 件以上必要")
    return errs


# --- purpose-acceptance (成果物が当初 purpose を満たすか) の trace 検査 ---
# R3-emit-specs.md §2.2「criteria は goal/checklist から test-first 導出・フォールバック既定文禁止」を
# 機械化する。criteria が品質ゲートの言い換え (lint exit0 / 4条件 PASS 等) に退化し purpose を
# 一度も参照しない汎用フォールバックを fail-closed で弾く。意味の正否 (criterion が purpose を
# *正しく* 受入検証するか) は evaluator の責務として残す=機械層は「purpose 語彙を一度も参照しない」
# 明白な退化のみ検出する二層分離 (Goodhart 回避)。
_PURPOSE_ASCII_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]{2,}")
# Han (CJK 統合漢字 + 拡張A) + Katakana。hiragana/数字/記号は語の接着辞ゆえ区切りとして bigram を跨がせない。
_PURPOSE_CJK_RE = re.compile(r"[一-鿿㐀-䶿゠-ヿ]{2,}")


def purpose_signals(text) -> set[str]:
    """goal/checklist/criterion から「内容語シグナル」集合を抽出する (purpose 由来性の素片)。

    ascii 語 (3 文字以上・小文字化) + CJK (漢字/カタカナ) 連続の bigram。hiragana を区切りに
    することで「を/する/した」等の機能語ノイズで bigram が偽マッチするのを避ける。形態素解析に
    依存しない決定論実装 (stdlib 規約)。
    """
    s = str(text or "")
    signals: set[str] = set()
    for m in _PURPOSE_ASCII_RE.findall(s):
        signals.add(m.lower())
    for run in _PURPOSE_CJK_RE.findall(s):
        for i in range(len(run) - 1):
            signals.add(run[i : i + 2])
    return signals


def _purpose_vocab(goal, checklist) -> set[str]:
    """goal + checklist から purpose 語彙シグナルの和集合を作る。"""
    vocab = set(purpose_signals(goal))
    if isinstance(checklist, list):
        for item in checklist:
            vocab |= purpose_signals(item)
    elif checklist is not None:
        vocab |= purpose_signals(checklist)
    return vocab


def criteria_purpose_traceability_errors(criteria, *, goal=None, checklist=None) -> list[str]:
    """skill loop spec の criteria が当該 spec の goal/checklist 語彙を最低 1 件参照するか検査。

    どの criterion も purpose 語彙を参照しなければ「汎用フォールバックへの退化」と判定し error。
    goal/checklist から content シグナルが 1 つも取れない場合は判定不能として [] (lenient・
    判定材料が無いのに弾く偽陽性を避ける)。criteria の構造不備は validate_criteria が別途担う。

    機械層の射程 (二層分離・正直開示): 判定は字面 (CJK bigram + ascii 語) の重複ベースゆえ、
    (a) goal を字面再利用せず**同義語/翻訳のみ**で表した正しい purpose criterion は誤検出しうる
    (緩和=「最低 1 件」で足り inner/outer の一方が領域名詞を再利用すれば通る・最終的な意味の正否は
    evaluator の意味判定に残す)、(b) 本関数は criteria↔goal の内部整合のみ見て **goal 自体が真の
    plugin purpose に接地しているか**は検査しない (接地は受入確認章 / EVALS llm_eval / evaluator の責務)。
    """
    vocab = _purpose_vocab(goal, checklist)
    if not vocab:
        return []
    if not isinstance(criteria, list) or not criteria:
        return []
    for item in criteria:
        if isinstance(item, dict) and (purpose_signals(item.get("text", "")) & vocab):
            return []
    return [
        "feedback_contract.criteria が purpose 由来でない: どの criterion も spec の goal/checklist "
        "語彙を参照しない汎用フォールバック (R3 §2.2 違反)。goal/checklist から受入基準を test-first 導出すること"
    ]


def as_int(v) -> int | None:
    """scalar を int 化する (失敗時 None)。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and re.fullmatch(r"-?\d+", v.strip()):
        return int(v.strip())
    return None


# --- index.plugin_meta が要求する plugin 階層キー (値域検証用) ---
# core = 全 plugin で必須の非空 dict (manifest/marketplace は別途 field 検証も持つ・ci は CI 配線)。
# feedback_deploy は conditional→core へ昇格 (評価フィードバックループは全構想の既定装備)。
# opt-out は {enabled: false, reason: <非空>} の明示例外のみ (applicable:false 形は不可)。
# 値域 (deploy/notion_sink/portability) は check-spec-gates.py が検証する。
PLUGIN_META_CORE_DICTS = ("manifest", "marketplace", "ci", "feedback_deploy")
# conditional = 該当しない構想では {applicable: false, reason: <非空>} で明示 N/A 可。
# reflection.md A7「skill-only は PKG 一部 N/A」と gate 実装を一致させる (無条件強制を緩和)。
# 空/欠落は不可 (省略は必ず根拠付き明示=「不要なら plugin_level_surfaces.<surface>.omitted_reason に理由」原則と同型)。
PLUGIN_META_CONDITIONAL_DICTS = ("pkg_contract", "governance", "ssot_dedup")
# 後方互換: plugin 階層キー全体 (core + conditional)。集合として従来 7 キーと等価。
PLUGIN_META_REQUIRED_DICTS = PLUGIN_META_CORE_DICTS + PLUGIN_META_CONDITIONAL_DICTS


def is_plugin_meta_na(v) -> bool:
    """plugin_meta の conditional キーが明示 N/A ({applicable: false}) かを返す。"""
    return isinstance(v, dict) and v.get("applicable") is False


# --- タスク仕様書 (計画成果物) の出力先 解決の SSOT (再現性) ---
# 既定: repo-root 相対の <PLAN_OUTPUT_BASE>/<plan_slug(name)>。同一構想 → 常に同一出力先。
# 可視・永続の tracked ディレクトリ (gitignore しない)。計画成果物はレビュー可能な
# deliverable であり捨て置き scratch ではない (io-contract.md §9)。goal-seek の transient
# 作業ログ (progress/intermediate) のみ <PLAN_DIR>/.goal-seek/ 配下へ隔離する。
PLAN_OUTPUT_BASE = "plugin-plans"


def plan_slug(name: str) -> str:
    """プラグイン構想名を決定論的 kebab-case slug へ変換する (出力先 <plugin-slug>)。

    小文字化 → 英数とハイフン以外を '-' → 連続ハイフン圧縮 → 前後 '-' 除去。
    同一構想名は常に同一 slug = 同一出力先 (再現性アンカー)。冪等:
    plan_slug(plan_slug(x)) == plan_slug(x)。
    入力は対象プラグインの **ASCII kebab フォルダ名** を想定する (io-contract.md §9)。
    日本語(CJK)主体の自由文は ASCII 以外が脱落し別構想が同一 slug へ衝突しうるため、
    R1 は構想自由文でなく確定済みの target plugin kebab 名を渡すこと。
    """
    s = re.sub(r"[^a-z0-9-]+", "-", str(name).strip().lower())
    return re.sub(r"-+", "-", s).strip("-")


def plan_output_dir(
    name: str,
    out_dir: str | None = None,
    base: str = PLAN_OUTPUT_BASE,
    cycle_id: str | None = None,
) -> str:
    """タスク仕様書の出力先 (PLAN_DIR) を決定論的に解決する (repo-root 相対)。

    out_dir 明示指定があればそれを使う (相対は repo-root 基準)。無ければ
    `<base>/<plan_slug(name)>` を返す。slug が空になる name は ValueError。
    既定では plugin ごとに `plugin-plans/<plugin-slug>/` (可視・永続の tracked deliverable) へ出力する。

    cycle_id (C13): 省略 (None/空) 時は現行の flat 配置 (`plugin-plans/<slug>/`) を **完全不変**で返し
    (既存の全呼び出し元は無改修)、非空指定時のみ解決済みルートの配下へ `/<cycle_id>` をスコープ化して
    `plugin-plans/<slug>/<cycle_id>` を返す。cycle_id は `CYCLE_ID_RE` (`^\\d{8}-[a-z0-9-]+$`) に一致
    しなければ ValueError (不正な cycle_id で build dir が黙って変わる事故を fail-closed で防ぐ)。

    `name` は生 plugin 名でも plan_slug 済 slug でも可 (plan_slug が冪等のため二重適用は無害)。
    戻り値は **repo-root 相対パス**。絶対化が要る場合は呼び出し側が `$CLAUDE_PROJECT_DIR`/cwd
    (repo-root 前提) で前置する責務とする (本関数は cwd を参照しない=純関数で再現性を担保)。
    """
    if out_dir is not None and str(out_dir).strip():
        root = str(out_dir).strip().rstrip("/")
    else:
        slug = plan_slug(name)
        if not slug:
            raise ValueError("plan_output_dir: name から有効な slug を導出できない (--out-dir を明示指定すること)")
        root = f"{base.rstrip('/')}/{slug}"
    if cycle_id is not None and str(cycle_id).strip():
        cid = str(cycle_id).strip()
        if not CYCLE_ID_RE.match(cid):
            raise ValueError(f"plan_output_dir: cycle_id={cid!r} は {CYCLE_ID_RE.pattern} に不一致")
        return f"{root}/{cid}"
    return root


def expected_kind_pass_tokens(component_kind: str, skill_kind: str) -> set[str]:
    """harness_coverage.kind_pass が含むべき kind 別の語 (最小整合チェック)。

    harness-coverage-spec の kind 別パス (ref→source-traceability+ref-review /
    assign→evaluator verdict / loop→criteria検証test+content-review verdict) に対応。
    緩めだが「kind と無関係な値」を弾く。
    """
    if component_kind == "skill":
        if skill_kind in FEEDBACK_LOOP_SKILL_KINDS:
            return {"criteria", "content-review"}
        if skill_kind == "ref":
            return {"source-traceability", "ref-review"}
        if skill_kind == "assign":
            return {"evaluator", "verdict"}
    # 非 skill (sub-agent/slash-command/hook/script) と skill 既定
    return {"content-review", "verdict", "coverage", "test", "ref-review"}


def kind_pass_ok(kind_pass: str, component_kind: str, skill_kind: str) -> bool:
    """kind_pass が component_kind/skill kind と整合する語を含むか。"""
    kp = str(kind_pass or "").lower()
    return any(tok in kp for tok in expected_kind_pass_tokens(component_kind, skill_kind))


def _skill_kind_of(comp: dict) -> str:
    """skill component の kind を解決する。

    §4 の `skill_kind` を正 (canonical) とし、skill-brief 由来の `kind` を後方互換 fallback にする
    (旧 C*.md frontmatter / 現 golden inventory は `kind` を使うため両受容で移送を無破壊にする)。
    """
    v = comp.get("skill_kind")
    if isinstance(v, str) and v.strip():
        return v.strip()
    v2 = comp.get("kind")
    return v2.strip() if isinstance(v2, str) and v2.strip() else ""


def _component_field_present(comp: dict, field: str, ck: str) -> bool:
    """component エントリが構造的必須フィールドを携帯するか (presence-only / skill_kind alias 込み)。"""
    # skill component は skill-brief の "kind" を component_kind との衝突回避のため
    # top-level "skill_kind" (fallback "kind") として携帯する。
    if ck == "skill" and field == "kind":
        return bool(_skill_kind_of(comp))
    if field in SKILL_BRIEF_PRESENCE_ONLY:
        return field in comp and comp[field] is not None
    return field in comp and comp[field] not in (None, "", [])


def validate_component_quality_gates(comp: dict) -> list[str]:
    """component の quality_gates ブロックを値域検証する (旧 check-spec-gates の quality_gates 部を移送)。

    p0_lint が component_kind 別必須集合を網羅・build_trace=required・elegant_review C1-C4/all_pass・
    content_review verdict=PASS/sha_match・evaluator threshold>=80/high_max=0 を fail-closed で検査する。
    """
    ck = str(comp.get("component_kind", "")).strip()
    if ck not in COMPONENT_KINDS:
        return [f"component_kind={ck!r} が未宣言/enum 外 (quality_gates 検証不能)"]
    errs: list[str] = []
    qg = comp.get("quality_gates")
    if not isinstance(qg, dict):
        return [f"[{ck}] quality_gates ブロックが無い (harness-creator 規律の出力強制に必須)"]
    required = set(P0_LINT_BY_KIND.get(ck, ()))
    declared = set(qg.get("p0_lint")) if isinstance(qg.get("p0_lint"), list) else set()
    missing = sorted(required - declared)
    if missing:
        errs.append(f"[{ck}] quality_gates.p0_lint が必須 lint を欠く: {missing}")
    if str(qg.get("build_trace", "")).strip() != "required":
        errs.append(f"[{ck}] quality_gates.build_trace は 'required' であること")
    er = qg.get("elegant_review")
    if not isinstance(er, dict):
        errs.append(f"[{ck}] quality_gates.elegant_review ブロックが無い")
    else:
        conds = er.get("conditions") if isinstance(er.get("conditions"), list) else []
        if sorted(str(c) for c in conds) != list(ELEGANT_CONDITIONS):
            errs.append(f"[{ck}] elegant_review.conditions は {list(ELEGANT_CONDITIONS)} 全部であること")
        if er.get("all_pass") is not True:
            errs.append(f"[{ck}] elegant_review.all_pass は true であること")
    cr = qg.get("content_review")
    if not isinstance(cr, dict):
        errs.append(f"[{ck}] quality_gates.content_review ブロックが無い")
    else:
        if str(cr.get("verdict", "")).strip() != "PASS":
            errs.append(f"[{ck}] content_review.verdict は PASS であること")
        if cr.get("sha_match") is not True:
            errs.append(f"[{ck}] content_review.sha_match は true であること")
    ev = qg.get("evaluator")
    if not isinstance(ev, dict):
        errs.append(f"[{ck}] quality_gates.evaluator ブロックが無い")
    else:
        th = as_int(ev.get("threshold"))
        if th is None or th < 80:
            errs.append(f"[{ck}] evaluator.threshold は >=80 (現値 {ev.get('threshold')!r})")
        hm = as_int(ev.get("high_max"))
        if hm is None or hm != 0:
            errs.append(f"[{ck}] evaluator.high_max は 0 (現値 {ev.get('high_max')!r})")
    return errs


def validate_component_harness_coverage(comp: dict) -> list[str]:
    """component の harness_coverage ブロックを値域検証する (旧 check-spec-gates の harness 部を移送)。"""
    ck = str(comp.get("component_kind", "")).strip()
    if ck not in COMPONENT_KINDS:
        return [f"component_kind={ck!r} が未宣言/enum 外 (harness 検証不能)"]
    errs: list[str] = []
    skill_kind = _skill_kind_of(comp)
    hc = comp.get("harness_coverage")
    if not isinstance(hc, dict):
        errs.append(f"[{ck}] harness_coverage ブロックが無い (min/kind_pass を持つこと)")
    else:
        mn = as_int(hc.get("min"))
        if mn is None or mn < HARNESS_MIN_REQUIRED:
            errs.append(f"[{ck}] harness_coverage.min は >={HARNESS_MIN_REQUIRED} (現値 {hc.get('min')!r})")
        kp = str(hc.get("kind_pass", "")).strip()
        if not kp:
            errs.append(f"[{ck}] harness_coverage.kind_pass が空 (kind 別パスを明記)")
        elif not kind_pass_ok(kp, ck, skill_kind):
            tokens = sorted(expected_kind_pass_tokens(ck, skill_kind))
            errs.append(f"[{ck}] harness_coverage.kind_pass='{kp}' が kind と無関係 (期待語のいずれかを含むこと: {tokens})")
    return errs


def validate_inventory_component(comp: dict) -> list[str]:
    """component-inventory.json の 1 component エントリを検証する (旧 C*.md 検証を component 単位へ集約)。

    per-phase 転換で C*.md frontmatter は inventory の components[] エントリへ載せ替わったため、旧
    check-spec-frontmatter.py + check-spec-gates.py の per-spec 検査ロジックをここへ移送する:
      - component_kind ∈ 5 種 enum
      - build_target 非空 / builder・build_kind が §9 build handoff 契約のマッピングと整合
      - component_kind 別の構造的必須キー (STRUCTURAL_REQUIRED・presence-only 込み)
      - skill: skill_kind enum + 条件付き必須 (skill_conditional_required) + loop(run/wrap/delegate) は
        feedback_contract.criteria を validate_criteria + criteria_purpose_traceability_errors で検査
        (ref/assign は skip_reason か criteria)。非 skill は criteria をスキップ
      - quality_gates / harness_coverage の値域 (harness-creator 規律の出力強制)
      - script は tests_min>=80
    """
    if not isinstance(comp, dict):
        return ["component が object でない"]
    cid = str(comp.get("id", "")).strip() or "?"
    prefix = f"[{cid}]"

    ck = str(comp.get("component_kind", "")).strip()
    if ck not in COMPONENT_KINDS:
        return [f"{prefix} component_kind={ck!r} が enum 外 {list(COMPONENT_KINDS)}"]

    errs: list[str] = []

    # 0. placement_scope (配置境界) の enum + plugin-root は script 限定
    ps = placement_of(comp)
    if ps not in PLACEMENT_SCOPES:
        errs.append(f"{prefix} placement_scope={ps!r} が enum 外 {list(PLACEMENT_SCOPES)}")
    if ps == "plugin-root" and ck != "script":
        errs.append(f"{prefix} placement_scope=plugin-root は script のみ許可 (component_kind={ck})")

    # 1. build_target 非空 (L3→L4 追跡)
    if not str(comp.get("build_target", "")).strip():
        errs.append(f"{prefix} build_target が空")

    # 2. builder / build_kind が §9 build handoff 契約のマッピングと整合 (builder は placement_scope を写す)
    exp_builder, exp_build_kind = builder_for(ck, ps), BUILD_KIND_BY_KIND[ck]
    builder = str(comp.get("builder", "")).strip()
    if not builder:
        errs.append(f"{prefix} builder が空 (期待 {exp_builder!r})")
    elif builder != exp_builder:
        errs.append(f"{prefix} builder={builder!r} が component_kind={ck} と不整合 (期待 {exp_builder!r})")
    build_kind = str(comp.get("build_kind", "")).strip()
    if not build_kind:
        errs.append(f"{prefix} build_kind が空 (期待 {exp_build_kind!r})")
    elif build_kind != exp_build_kind:
        errs.append(f"{prefix} build_kind={build_kind!r} が component_kind={ck} と不整合 (期待 {exp_build_kind!r})")

    # 3. component_kind 別の構造的必須キー (skill_kind alias / presence-only 込み)
    for field in STRUCTURAL_REQUIRED[ck]:
        if not _component_field_present(comp, field, ck):
            label = "skill_kind" if (ck == "skill" and field == "kind") else field
            errs.append(f"{prefix} [{ck}] 構造的必須フィールド欠落: {label}")

    # 4. skill: skill_kind enum + 条件付き必須 + feedback_contract.criteria
    if ck == "skill":
        skill_kind = _skill_kind_of(comp)
        if skill_kind and skill_kind not in SKILL_KINDS:
            errs.append(f"{prefix} [skill] skill_kind={skill_kind!r} が enum 外 {list(SKILL_KINDS)}")
        for field in skill_conditional_required(skill_kind):
            if field not in comp or comp[field] in (None, "", []):
                errs.append(f"{prefix} [skill] skill_kind={skill_kind} の条件付き必須フィールド欠落: {field}")
        # responsibilities の shape 床: skill-brief.schema.json allOf (kind∈{run,assign}) の
        # fail-closed 制約のみ写す = object 配列 + prompt_required:true を 1 件以上含む (contains)。
        # 文字列配列は brief round-trip で実 schema に落ちるため plan 段階で弾く。緩い上限は写さない。
        if skill_kind in ("run", "assign"):
            resp = comp.get("responsibilities")
            if isinstance(resp, list) and resp:
                if not all(isinstance(r, dict) for r in resp):
                    errs.append(
                        f"{prefix} [skill] responsibilities は object 配列であること "
                        "(skill-brief.schema の items=object。文字列配列は round-trip 不能)"
                    )
                elif not any(r.get("prompt_required") is True for r in resp):
                    errs.append(
                        f"{prefix} [skill] responsibilities に prompt_required:true の項目が 1 件以上必要 "
                        "(skill-brief.schema allOf contains)"
                    )
        fc = comp.get("feedback_contract")
        if skill_kind in FEEDBACK_LOOP_SKILL_KINDS:
            if not isinstance(fc, dict):
                errs.append(f"{prefix} [skill] loop kind は feedback_contract.criteria 必須")
            else:
                errs.extend(f"{prefix} {e}" for e in validate_criteria(fc.get("criteria")))
                errs.extend(f"{prefix} {e}" for e in criteria_purpose_traceability_errors(
                    fc.get("criteria"), goal=comp.get("goal"), checklist=comp.get("checklist")))
        else:
            if isinstance(fc, dict) and not fc.get("skip_reason") and not fc.get("criteria"):
                errs.append(f"{prefix} [skill] ref/assign は feedback_contract.skip_reason か criteria のいずれかが必要")

    # 5. quality_gates / harness_coverage の値域
    errs.extend(f"{prefix} {e}" for e in validate_component_quality_gates(comp))
    errs.extend(f"{prefix} {e}" for e in validate_component_harness_coverage(comp))

    # 6. script は tests_min>=80 + placement 別 build_target 不変条件
    if ck == "script":
        tm = as_int(comp.get("tests_min"))
        if tm is None or tm < HARNESS_MIN_REQUIRED:
            errs.append(f"{prefix} [script] tests_min は >={HARNESS_MIN_REQUIRED} (現値 {comp.get('tests_min')!r})")
        bt = str(comp.get("build_target", "")).strip()
        if bt:
            if ps == "plugin-root":
                # plugin-root 共有 script は plugins/<slug>/scripts/ 直下 (親 skill 配下に置かない)。
                if "/scripts/" not in bt or "/skills/" in bt:
                    errs.append(
                        f"{prefix} [script] placement_scope=plugin-root の build_target は "
                        f"plugins/<slug>/scripts/ 直下であること (/scripts/ を含み /skills/ を含まない): {bt}"
                    )
            elif "/skills/" not in bt or "/scripts/" not in bt:
                # skill placement の専用 script は親 skill の scripts/ に畳む。
                errs.append(
                    f"{prefix} [script] placement_scope=skill の build_target は親 skill 配下 "
                    f"(/skills/ と /scripts/ を含む) であること: {bt}"
                )

    # 7. couples_with (optional・接合が密な兄弟ペアの直列化宣言) の形状検査
    #    depends_on とは別概念: 成果物ハード依存ではなく「同時 build すると統合 finding が
    #    先送りされる密結合 (共有 contract を挟む producer↔consumer 等)」を宣言し、
    #    derive-task-graph が直列化 depends_on を焼く根拠にする (盲目並列の代償=統合コスト前倒し)。
    #    参照先 component の実在/直列化実現は inventory 横断で validate-task-graph (j) が検査する。
    cw = comp.get("couples_with")
    if cw is not None:
        if not isinstance(cw, list) or not all(isinstance(x, str) and x.strip() for x in cw):
            errs.append(f"{prefix} couples_with は非空文字列の list であること (現値 {cw!r})")
        elif cid in cw:
            errs.append(f"{prefix} couples_with に自身 {cid} を含められない (自己結合は無意味)")
    return errs


def validate_surface_inventory(data: dict) -> list[str]:
    """component-inventory.json の surface 採否契約を検査する。

    `considered_component_kinds` は「5 種を検討した」証跡で、`components` は実際に生成する
    必要最小の buildable spec 集合。両者を分けることで、単一 skill 退化と不要な水増し生成を
    同時に防ぐ。
    """
    errs: list[str] = []
    considered = data.get("considered_component_kinds")
    if not isinstance(considered, list) or set(considered) != set(COMPONENT_KINDS):
        errs.append(
            "considered_component_kinds は 5 component_kind 全種 "
            f"{list(COMPONENT_KINDS)} を漏れなく含むこと"
        )
    components = data.get("components")
    if not isinstance(components, list) or not components:
        errs.append("components が非空 list でない")
    else:
        for idx, comp in enumerate(components):
            if not isinstance(comp, dict):
                errs.append(f"components[{idx}] が object でない")
                continue
            # per-phase 転換: 旧 C*.md frontmatter を載せ替えた component エントリを丸ごと検証する
            # (component_kind / build_target / builder / 構造契約 / quality_gates / harness / criteria)。
            errs.extend(validate_inventory_component(comp))

    surfaces = data.get("plugin_level_surfaces")
    if not isinstance(surfaces, dict) or not surfaces:
        errs.append("plugin_level_surfaces が非空 dict でない")
    else:
        for surface in PLUGIN_LEVEL_SURFACES:
            item = surfaces.get(surface)
            if not isinstance(item, dict):
                errs.append(f"plugin_level_surfaces.{surface} が object でない/欠落")
                continue
            required = item.get("required")
            reason = item.get("omitted_reason")
            if required is True:
                continue
            if required is False and isinstance(reason, str) and reason.strip():
                continue
            errs.append(
                f"plugin_level_surfaces.{surface} は required:true または "
                "required:false + omitted_reason 非空で明示すること"
            )
        # notion_config surface の値域: required:true は databases[] 非空 + 各 entry の
        # key/direction 非空 + used_by が実在 component id を指すこと。DB ID は設置先
        # .notion-config.json 供給の二層分離ゆえ plan には key のみ宣言する (ID を焼かない)。
        nc = surfaces.get("notion_config")
        if isinstance(nc, dict) and nc.get("required") is True:
            comp_ids = {
                str(c.get("id", "")).strip()
                for c in (components if isinstance(components, list) else [])
                if isinstance(c, dict) and str(c.get("id", "")).strip()
            }
            dbs = nc.get("databases")
            if not isinstance(dbs, list) or not dbs:
                errs.append("plugin_level_surfaces.notion_config は required:true なら databases[] 非空であること")
            else:
                for idx, db in enumerate(dbs):
                    p = f"plugin_level_surfaces.notion_config.databases[{idx}]"
                    if not isinstance(db, dict):
                        errs.append(f"{p} が object でない")
                        continue
                    if not str(db.get("key", "")).strip():
                        errs.append(f"{p}.key が空 (plan は DB キーのみ宣言・ID は設置先 config 供給)")
                    used_by = db.get("used_by")
                    if not isinstance(used_by, list) or not used_by:
                        errs.append(f"{p}.used_by が非空 list でない (消費 component id を宣言)")
                    else:
                        for u in used_by:
                            if str(u).strip() not in comp_ids:
                                errs.append(f"{p}.used_by={u!r} が components[].id に存在しない")
                    if not str(db.get("direction", "")).strip():
                        errs.append(f"{p}.direction が空 (read|write 等の向きを宣言)")
    return errs


# ─────────────────────────── 生成 skeleton (実行可能ひな形) ───────────────────────────
def valid_quality_gates(component_kind: str) -> dict:
    """component_kind 別に最小妥当な quality_gates ブロックを返す。"""
    if component_kind not in COMPONENT_KINDS:
        raise ValueError(f"unknown component_kind: {component_kind!r}")
    return {
        "p0_lint": list(P0_LINT_BY_KIND[component_kind]),
        "build_trace": "required",
        "elegant_review": {"conditions": ["C1", "C2", "C3", "C4"], "all_pass": True},
        "content_review": {"verdict": "PASS", "sha_match": True},
        "evaluator": {"threshold": 80, "high_max": 0},
    }


def valid_harness_coverage(component_kind: str, skill_kind: str = "run") -> dict:
    """component_kind/skill kind と整合する最小 harness_coverage ブロックを返す。"""
    if component_kind == "skill":
        if skill_kind == "ref":
            kind_pass = "ref=source-traceability+ref-review"
        elif skill_kind == "assign":
            kind_pass = "assign=evaluator-verdict"
        else:
            kind_pass = "loop=criteria-test+content-review-verdict"
    else:
        kind_pass = "content-review-verdict"
    return {"min": HARNESS_MIN_REQUIRED, "kind_pass": kind_pass}


def minimal_frontmatter(component_kind: str, *, spec_id: str = "C01", skill_kind: str = "run") -> dict:
    """検証を通せる最小 frontmatter skeleton を返す。

    静的 Markdown ひな形を増やさず、`STRUCTURAL_REQUIRED` / `P0_LINT_BY_KIND` から
    生成することで「ひな形」の正本を実行可能契約へ寄せる。
    """
    if component_kind not in COMPONENT_KINDS:
        raise ValueError(f"unknown component_kind: {component_kind!r}")
    if skill_kind not in SKILL_KINDS:
        raise ValueError(f"unknown skill kind: {skill_kind!r}")

    fm: dict = {"id": spec_id, "component_kind": component_kind, "depends_on": []}
    if component_kind == "skill":
        fm.update({
            "skill_name": f"{skill_kind}-sample",
            "prefix": skill_kind,
            "kind": skill_kind,
            "hierarchy_level": "L1",
            "trigger_conditions": ["明示的に呼び出されたとき", "対象構想がこの責務に一致するとき"],
            "output_contract": "観測可能な成果物と検証結果を返す",
            "boundary": "単一責務を超える実装・配布判断は上位 plan に委ねる",
            "placement_candidates": ["Skill"],
            "cli_tools": [],
            "deterministic_checks": [],
            "external_systems": [],
            "mcp_tools": [],
            "needs_independent_context": False,
            "needs_lifecycle_enforcement": False,
        })
        if skill_kind in ("run", "wrap", "assign", "delegate"):
            fm.update({
                "goal": "この component spec の完了条件が検証可能な形で満たされている",
                "purpose_background": "後段 build が迷わない粒度で責務と評価基準を固定する",
                "checklist": ["frontmatter 契約を満たす", "本文の目的・成果物・完了条件が非空"],
            })
        if skill_kind in ("run", "assign"):
            # skill-brief.schema allOf (kind∈{run,assign}) の shape: object 配列 + prompt_required:true ≥1 件。
            fm["responsibilities"] = [{
                "id": "R1-core",
                "summary": "component spec の責務を実装可能な入力へ落とす",
                "prompt_required": True,
            }]
            fm["prompt_layer"] = "7layer"
        if skill_kind == "wrap":
            fm["base_skill"] = "run-base"
        if skill_kind == "delegate":
            fm["delegate_agent"] = "sample-agent"
        if skill_kind in FEEDBACK_LOOP_SKILL_KINDS:
            # criteria は当該 spec の goal/checklist 由来 (purpose-acceptance) であること。
            # skeleton は domain purpose を持たないため goal/checklist 語彙を参照する雛形に留め、
            # 実 spec では「この component の goal を満たすことを test/script で確認する」へ置換する。
            # 汎用ゲートの言い換え (lint exit0 / 4条件 PASS) は criteria_purpose_traceability_errors が弾く。
            fm["feedback_contract"] = {"criteria": [
                {"id": "IN1", "loop_scope": "inner",
                 "text": "frontmatter 契約と本文セクションが満たされ決定論 lint が exit0 になる", "verify_by": "lint"},
                {"id": "OUT1", "loop_scope": "outer",
                 "text": "本文の完了条件 (goal の受入基準) が観測可能な形で満たされ受入テストが PASS する",
                 "verify_by": "test"},
            ]}
            fm["goal_seek"] = {"engine": "inline", "fork": "subagent", "max_loops": 5}
        else:
            fm["feedback_contract"] = {"skip_reason": f"{skill_kind} kind は loop criteria 必須対象外"}
        fm["combinators"] = ["with-goal-seek"] if skill_kind in FEEDBACK_LOOP_SKILL_KINDS else []
    elif component_kind == "sub-agent":
        fm.update({
            "name": "sample-subagent",
            "description": "独立 context で計画を検証する sub-agent",
            "tools": ["Read"],
            "independent_context": True,
            "responsibility_anchor": "prompts/R1.md",
            "prompt_layer": "7layer",
        })
    elif component_kind == "slash-command":
        fm.update({
            "name": "sample-command",
            "description": "計画スキルを呼び出す slash command",
            "argument-hint": "[args]",
            "allowed-tools": ["Read"],
            "disable-model-invocation": False,
        })
    elif component_kind == "hook":
        fm.update({
            "event": "PreToolUse",
            "matcher": "Write|Edit",
            "exit_semantics": "fail-closed-exit2",
            "settings_wiring": "settings.json",
            "fail_closed": True,
        })
    elif component_kind == "script":
        fm.update({
            "script_name": "sample.py",
            "purpose": "決定論検査を実行する",
            "inputs": "argv",
            "outputs": "stdout/stderr + exit code",
            "exit_codes": "0=OK / 1=violation / 2=usage",
            "network": False,
            "write_scope": "none",
            "stdlib_only": True,
            "tests_min": HARNESS_MIN_REQUIRED,
        })
    fm["quality_gates"] = valid_quality_gates(component_kind)
    fm["harness_coverage"] = valid_harness_coverage(component_kind, skill_kind)
    return fm


def _yaml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    return str(value)


def yaml_lines(data: dict, indent: int = 0) -> list[str]:
    """本スキルが使う YAML サブセットで dict を出力する。"""
    pad = "  " * indent
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.extend(yaml_lines(value, indent + 1))
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            lines.append(f"{pad}{key}:")
            for item in value:
                pairs = list(item.items())
                first_key, first_value = pairs[0]
                lines.append(f"{pad}  - {first_key}: {_yaml_scalar(first_value)}")
                for child_key, child_value in pairs[1:]:
                    lines.append(f"{pad}    {child_key}: {_yaml_scalar(child_value)}")
        elif isinstance(value, list):
            lines.append(f"{pad}{key}: [{', '.join(_yaml_scalar(x) for x in value)}]")
        else:
            lines.append(f"{pad}{key}: {_yaml_scalar(value)}")
    return lines


def render_minimal_spec(component_kind: str, *, spec_id: str = "C01", skill_kind: str = "run") -> str:
    """component-inventory.json の components[] に入れる最小 JSON object skeleton を返す。"""
    import json

    return json.dumps(minimal_frontmatter(component_kind, spec_id=spec_id, skill_kind=skill_kind), ensure_ascii=False, indent=2)


# ─────────────────────────── phase ファイル skeleton (床付きひな形) ───────────────────────────
def phase_id(n: int) -> str:
    """phase_number (1-13) を大文字ゼロ埋め 2 桁 id (P01..P13) へ変換する。"""
    if not (1 <= n <= 13):
        raise ValueError(f"phase_number は 1..13 の範囲 (現値 {n!r})")
    return f"P{n:02d}"


def minimal_phase_frontmatter(phase_number: int) -> dict:
    """床を通す最小 phase frontmatter skeleton (PHASE_REQUIRED 全キー) を返す。

    id/phase_name/category/gate_type は phase_number から §1 表 (PHASE_* dict) を引いて決定論導出する。
    prev_phase は P01 で 0、next_phase は P13 で 14。applicability は既定 applicable:true。
    """
    if not (1 <= phase_number <= 13):
        raise ValueError(f"phase_number は 1..13 の範囲 (現値 {phase_number!r})")
    name = PHASE_NAMES[phase_number - 1]
    return {
        "id": phase_id(phase_number),
        "phase_number": phase_number,
        "phase_name": name,
        "category": PHASE_CATEGORY[name],
        "prev_phase": phase_number - 1,
        "next_phase": phase_number + 1,
        "status": "未実施",
        "gate_type": PHASE_GATE_TYPE[name],
        "entities_covered": [],
        "applicability": {"applicable": True, "reason": ""},
    }


# PHASE_BODY_SECTIONS 各節の宣言型プレースホルダ (skeleton 本文の床を満たす最小 prose)。
# 実 spec では domain purpose へ置換する。汎用フォールバックのままでも床 (非空) は通るが、
# 意味の正否は下流トラスト / evaluator の意味判定に委ねる (Goodhart 回避)。
_PHASE_SECTION_HINT = {
    "## 目的": "このフェーズが達成する到達状態を目的ドリブンに宣言する (なぜ必要か)。",
    "## 背景": "このフェーズが要る文脈・前段の状況・関連する制約を宣言する。",
    "## 前提条件": "開始前に満たされているべき状態・先行フェーズの成果物・受け取る入力を宣言的に列挙する。",
    "## ドメイン知識": "実行者が repo/前段成果物から導出できない phase 固有の用語・不変条件・外部制約を列挙する (plan 全体の用語集は index ## ドメイン知識 を引用し差分のみ記載。phase 固有分が無ければ引用で足りる旨を明示)。",
    "## 成果物": "このフェーズで確定/生成する到達成果物を宣言的に列挙する (build 実体は component-inventory.json が SSOT)。",
    "## スコープ外": "このフェーズで扱わない事項と、その委譲先 phase/component を宣言する (境界=次タスクへの移行点)。",
    "## 完了チェックリスト": "完了=達成を判定する受入基準を観測可能な二値項目で宣言的に列挙する (gate フェーズは gate_type の合否)。",
    "## 参照情報": "参照すべき正本・資料・関連 component/phase を列挙する。",
}


def render_minimal_phase(phase_number: int) -> str:
    """§5 本文 section 床 (PHASE_BODY_SECTIONS = 宣言型 8 節) を満たす phase Markdown skeleton を返す。"""
    fm = minimal_phase_frontmatter(phase_number)
    parts = [f"\n# {fm['id']} — {fm['phase_name']} ({fm['category']})\n"]
    for sec in PHASE_BODY_SECTIONS:
        parts.append(f"\n{sec}\n{_PHASE_SECTION_HINT[sec]}\n")
    return "---\n" + "\n".join(yaml_lines(fm)) + "\n---\n" + "".join(parts)


# INDEX_REQUIRED_SECTIONS 各節の宣言型プレースホルダ (index skeleton 本文の床を満たす最小 prose)。
# 注: `## フェーズ一覧` は enumeration 本体をそのまま本文にするため hint を持たない (hint 文に phase-id
# トークンを埋めると extract_phase_list_ids が誤って拾い skeleton が自身の層1 検証に落ちるのを構造で回避)。
_INDEX_SECTION_HINT = {
    "## 基本定義": "メタ情報 (プロジェクトID/構想slug)・最上位目的 (goal-spec.purpose)・仕様駆動の大前提 (harness-creator 仕様基点・spec-first・要件正本=goal-spec checklist)・スコープ (含む/含まない) を宣言する。",
    "## ドメイン知識": "用語集とドメイン前提知識を列挙する (後段 build と評価者が同じ語彙で解釈できるように)。",
    "## インフラ": "ツール・実行環境・cwd 前提・依存 (Python 標準ライブラリ規約等) を宣言する。",
    "## 環境ポリシー": "品質基準 (harness>=80/評価ゲート)・共通ポリシー・エスカレーション方針を宣言する。",
    "## 完了チェックリスト": "基本定義/ドメイン/インフラ/環境ポリシー/フェーズ完全性/component 網羅を二値で列挙する (goal-spec checklist の要件 id をここか受入確認で引用する=RTM)。",
    "## 受入確認": "build 後に組み上がった実プラグインが purpose を満たすか確認する trace を宣言する。",
}


def render_minimal_index(*, plugin_slug: str = "sample-plugin") -> str:
    """INDEX_REQUIRED_SECTIONS の床を満たす index(main) skeleton を返す (基盤層 + フェーズ一覧 + チェックリスト + 受入確認)。

    plugin_meta は値域検証を持つため最小妥当な conditional N/A 形で出す (実 plan では architect が焼く)。
    フェーズ一覧は P01..P13 を昇順列挙し verify-index-topsort の phase 完全性も同時に満たす。
    """
    meta = {
        "id": "IDX0",
        "title": f"{plugin_slug} 開発計画 index (main)",
        "plugin_meta": {
            "manifest": {"required": True, "path": ".claude-plugin/plugin.json",
                         "name_matches_folder": True, "no_unresolved_placeholders": True, "validate_plugin": True},
            "marketplace": {"default_personal": True,
                            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL", "category": "Productivity"},
                            "cachebuster_for_update": True},
            # distribution は F3 (配布判定) の必須スロット。check-spec-gates.check_plugin_meta が
            # dict 必須で要求するため、skeleton も非配布既定 (実 plan で architect が確定) で携帯する。
            # distributable:false → bundles 空 + marketplace:false が check-spec-gates の値域と整合。
            "distribution": {"distributable": False, "bundles": [], "marketplace": False},
            "ci": {"workflow": "governance-check"},
            "pkg_contract": {"applicable": False, "reason": "skeleton (実 plan で確定)"},
            "governance": {"applicable": False, "reason": "skeleton (実 plan で確定)"},
            "ssot_dedup": {"applicable": False, "reason": "skeleton (実 plan で確定)"},
            # feedback_deploy は core 昇格につき opt-out 形 (enabled:false+reason) で床を満たす
            # (実 plan では deploy/notion_sink/portability の拡張形へ確定する)。
            "feedback_deploy": {"enabled": False, "reason": "skeleton (実 plan で確定)"},
        },
    }
    lines = [f"\n# {meta['title']}\n"]
    for sec in INDEX_REQUIRED_SECTIONS:
        if sec == "## フェーズ一覧":
            # enumeration 本体を本文にする (hint を挟まない=phase-id トークン汚染の構造回避)。
            lines.append(f"\n{sec}\n\n")
            for n in range(1, 14):
                name = PHASE_NAMES[n - 1]
                lines.append(f"{n}. {phase_id(n)} — {name} ({PHASE_CATEGORY[name]}) / 未実施\n")
        else:
            lines.append(f"\n{sec}\n{_INDEX_SECTION_HINT[sec]}\n")
    return "---\n" + "\n".join(yaml_lines(meta)) + "\n---\n" + "".join(lines)
