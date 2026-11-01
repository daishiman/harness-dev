#!/usr/bin/env python3
# /// script
# name: lint-script-naming
# purpose: 28章 §4.1-§4.6 の script 命名規約 (<verb>-<target>.py・許可動詞・例外節) を機械強制する。
# inputs:
#   - argv: [path...] [--report] [-h|--help] (path 省略時は cwd の scripts / plugins)
# outputs:
#   - stdout: summary 行、--report なら summary・violations・permanent_exception・pending_rename・ledger_stale の JSON、--help なら usage
#   - stderr: VIOLATION / PENDING / STALE の一覧と設定エラー
#   - exit: 0=違反なし・--help / 1=違反あり・台帳の stale あり / 2=設定エラー (存在しない path・走査 0 件・未知の option)
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""lint-script-naming.py

28章 §4.1-§4.6 のscript命名規約を機械強制する。
- 動詞リスト: lint/validate/format/render/extract/diff/guard/build/sync/install/record/manage/migrate
  (後ろの5つは状態を書き換える動詞。意味と境界は 28章 §4.1.1)
- 例外節 (§4.4): sink_*.py / *_helper.py / audit_*.py
- 例外節 (§4.6): adapters/*.py (Hexagonal Architecture adapter固有名)
- 禁止: アンダースコア(例外節を除く), check/run/main/utils/helper のみ命名

usage:
  python3 scripts/lint-script-naming.py [path...]
  python3 scripts/lint-script-naming.py --report
  python3 scripts/lint-script-naming.py --help

個別パスの照合キーは repo root (この script の 2 階層上。その外なら cwd) からの相対パス。
絶対パスや別の cwd から渡しても同じ登録に当たる。symlink は実体へ解決せず、渡された
path のまま照合する (scripts/ 直下の symlink は自分の path で登録している)。

exit code:
  0 違反なし (--help も 0)
  1 違反検出、または台帳の stale (返済済み・実体不在・import 参照の無い恒久例外) あり
  2 設定エラー (存在しない path・走査対象 0 件・未知の option)。検査が空振りしたまま
    0 を返すと、別の cwd や打ち間違いの path で CI が素通りするので止める。

CONVENTIONS: stdlib only.
"""
import json
import os
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

ALLOWED_VERBS = {
    "lint", "validate", "format", "render",
    "extract", "diff", "guard", "build",
    # 状態を書き換える動詞 (28章 §4.1.1・PROP-2026-10-12-SCRIPT-VERBS)。同じ意味の別名
    # (apply/reconcile→sync, setup→install, write/log/append→record, backfill→migrate) は足さない。
    "sync", "install", "record", "manage", "migrate",
}
BANNED_NAMES = {"check.py", "run.py", "main.py", "utils.py", "helper.py"}

# §4.4 例外節
EXCEPTION_PATTERNS = [
    (re.compile(r"^sink_[a-z0-9]+\.py$"), "Sink Contract adapter (§4.4)"),
    (re.compile(r"^[a-z0-9]+_helper\.py$"), "secret helper (§4.4)"),
    (re.compile(r"^audit_[a-z0-9_]+\.py$"), "audit helper (§4.4)"),
]

# 暫定例外 (Change Governance 経由でリネーム予定)
PENDING_RENAME_PATTERNS = [
    re.compile(r"^hook-[a-z0-9-]+\.py$"),
]

# §4.3 恒久例外: path 固定。**リネーム待ちではない** (改名すると壊れる)。
#
# 登録条件は 1 つだけ: その path が repo 内のどこかから素の import
# (`import <stem>` / `from <stem> import`) で参照されていること。Python の import は
# ハイフンを含む module 名を解決できないので、kebab-case 化は import の破断と同義であり、
# Change Governance を通しても改名できない。だから「予定」の棚に置かない。
#
# 値は 1 件ずつの理由。グループ共通の事情であっても、各行だけ読んで
# 「なぜ改名できないのか」が分かる形にする。
#
# 追加するとき: 参照箇所を grep で示せることが条件。
# 外すとき: 参照が 0 件になったら PENDING_RENAME_PATHS へ移すか、その場で改名する。
# 参照が消えたまま残った登録は、全域走査のときに _stale_registrations() が検出して
# exit 1 にする。数えるのは cwd 以下の .py にある行頭の素の import で、stem 単位で
# 照合する (同じ stem の複製どうしは区別しない)。そのファイル自身の行は数えない。
PERMANENT_EXCEPTION_PATHS = {
    # マルチテナント runtime の共有 module。plugin を跨いで 10 箇所から
    # `import tenant_runtime` される (contract-generator/lib/slack_common.py:21 他)。
    "scripts/tenant_runtime.py": "import tenant_runtime (10 箇所) — §4.3",
    "plugins/harness-creator/scripts/tenant_runtime.py": "import tenant_runtime (10 箇所) — §4.3",
    "plugins/skill-intake/scripts/tenant_runtime.py": "import tenant_runtime (10 箇所) — §4.3",
    "plugins/skill-governance-automation/scripts/tenant_runtime.py": "import tenant_runtime (10 箇所) — §4.3",
    # feedback_contract criteria の単一 SSOT。lint-content-review.py:30 /
    # lint-feedback-contract.py:54 / lint-feedback-protocol.py:28 他 11 箇所が import。
    "scripts/feedback_contract_ssot.py": "import feedback_contract_ssot (11 箇所) — §4.3",
    # 上記正本の vendored 実体コピー (harness-creator 単独 install 用)。正本と byte 完全一致を
    # lint-vendored-ssot.py が強制しており、名前を変えると import 名が変わって一致が崩れる。
    "plugins/harness-creator/scripts/feedback_contract_ssot.py": "vendored SSOT・import feedback_contract_ssot — §4.3",
    # repo 全域テスト探索の単一 SSOT。lint-test-discovery-coverage.py:52 /
    # validate-plugin-test-roots.py:40 / test_ci_integration.py:47 が import。
    "scripts/discover_repo_tests.py": "import discover_repo_tests (3 箇所) — §4.3",
    # per-repo Notion config SSOT loader。skill-intake 側は harness-creator 側への symlink。
    "plugins/harness-creator/scripts/notion_config.py": "import notion_config (19 箇所) — §4.3",
    "plugins/skill-intake/scripts/notion_config.py": "import notion_config (19 箇所) — §4.3",
    # HC consumers が plugin-local module として import する (sync-task-state.py:44 他 7 箇所)。
    # 繰り返しの importlib bootstrap を素の import に置き換えた結果なので戻せない。
    "plugins/harness-creator/scripts/plugin_resources.py": "import plugin_resources (7 箇所) — §4.3",
    # dev-graph の共通 util。bd-bridge.py:24 / build-graph-node.py:30 他 17 箇所が import。
    "plugins/dev-graph/scripts/_common.py": "import _common (17 箇所) — §4.3",
    # check-spec-*.py / render-spec-skeleton.py が kind→必須キーを引く共有 SSOT。26 箇所が import。
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/specfm.py": "import specfm (26 箇所) — §4.3",
    # skill-intake 単独配布の vendoring private module。render-intake-final.py:24-26 /
    # validate-plugin-vendor.py:25,46 / render_notion_page.py:23 他が import。
    "plugins/skill-intake/scripts/_vendor.py": "import _vendor (2 箇所) — §4.3",
    "plugins/skill-intake/scripts/_jsonschema_compat.py": "import _jsonschema_compat (8 箇所) — §4.3",
    # skill-intake の相互 import する module 群。quality_gate.py / notion_http.py /
    # publish_notion_page.py / enforce_visualization_rules.py / dry_render_notion.py が
    # それぞれ素の import で解決する。
    "plugins/skill-intake/scripts/check_completeness.py": "import check_completeness (quality_gate.py:10) — §4.3",
    "plugins/skill-intake/scripts/detect_contradictions.py": "import detect_contradictions (quality_gate.py:11) — §4.3",
    "plugins/skill-intake/scripts/validate_intake.py": "import validate_intake (quality_gate.py:9) — §4.3",
    "plugins/skill-intake/scripts/validate_mermaid.py": "import validate_mermaid (enforce_visualization_rules.py:11) — §4.3",
    "plugins/skill-intake/scripts/keychain_get_secret.py": "import keychain_get_secret (4 箇所) — §4.3",
    "plugins/skill-intake/scripts/notion_http.py": "import notion_http (6 箇所) — §4.3",
    "plugins/skill-intake/scripts/publish_notion_page.py": "import publish_notion_page (2 箇所) — §4.3",
    "plugins/skill-intake/scripts/render_notion_page.py": "import render_notion_page (3 箇所) — §4.3",
    "plugins/skill-intake/scripts/render_v2_adapter.py": "import render_v2_adapter (dry_render_notion.py:26) — §4.3",
    # build-trace SSOT shim。lint-prompt-placement.py:37 が import。
    "plugins/harness-creator/skills/run-build-skill/scripts/validate_build_trace_shim.py": "import validate_build_trace_shim (lint-prompt-placement.py:37) — §4.3",
    # elegant-review の Phase 順序・signal・verdict 導出検査を分離した sibling module。
    # validate-paradigm-coverage.py:58 が素の import で解決する。
    "plugins/harness-creator/skills/run-elegant-review/scripts/validate_phase_order.py": "from validate_phase_order import ... (validate-paradigm-coverage.py:58) — §4.3",
    # knowledge-skeleton template 内の共有 module。add_entry.py:426 / build_index.py:248 が import。
    "plugins/harness-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/search_knowledge.py": "import search_knowledge (2 箇所) — §4.3",
    # youtube ingest の provider I/F と path 正規化。どちらも
    # run-youtube-sync-oneshot.py:44-45 が素の import で解決する。
    "plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/youtube_provider.py": "import youtube_provider (run-youtube-sync-oneshot.py:44) — §4.3",
    "plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/normalized_source_path.py": "from normalized_source_path import ... (run-youtube-sync-oneshot.py:45) — §4.3",
    # system-spec-harness の上位概念 (U1-U9) 検証を分けた import 専用 module。
    # validate-coverage-matrix.py:68 が coverage_foundation を、coverage_foundation.py:14 が
    # foundation_provenance を素の import で解決する (apply-spec-transition.py も後者を読む)。
    "plugins/system-spec-harness/scripts/coverage_foundation.py": "from coverage_foundation import ... (validate-coverage-matrix.py:68) — §4.3",
    "plugins/system-spec-harness/scripts/foundation_provenance.py": "from foundation_provenance import ... (coverage_foundation.py:14) — §4.3",
}

# 暫定例外: 個別パス (初回投入時の既存スクリプト群、33章 Change Governance 管理下)
# こちらは **改名待ち**。誰も import していないので、参照 (SKILL.md / command / doc /
# hook / contract / test) を原子的に更新すれば改名できる。恒久例外は上の
# PERMANENT_EXCEPTION_PATHS にあり、両者は summary で別の数として出る。
# リネーム計画は .claude/changelog/governance-log.jsonl 参照
PENDING_RENAME_PATHS = {
    # PR #41: Claude/Codex fleet の公開 CLI 名と、既存 Python import/module 名。
    # 利用者向け command・文書・hook・contract が参照するため、この PR では個別 path を
    # Change Governance 管理下へ置く。ALLOWED_VERBS/underscore 規則自体は緩和しない。
    # install-codex-plugin.py / install-local-plugins.py / sync-plugin-platforms.py は動詞
    # install・sync の追加 (PROP-2026-10-12-SCRIPT-VERBS) で規約を満たしたので登録を外した。
    "plugins/harness-creator/scripts/audit-capability-parity.py",
    "plugins/skill-intake/scripts/post_publish_notify.py",
    "plugins/slide-report-generator/scripts/mention_mask.py",
    # Multi-tenant public CLI names are fixed by doc/マルチ企業展開.
    # tenant_runtime.py 系 (素の import 対象) は PERMANENT_EXCEPTION_PATHS へ移した。
    # ただし plugins/contract-generator/lib/tenant_runtime.py は lib/ 配下で本 lint の
    # 走査対象外 (登録しても一度も判定されない) なので、登録ごと外した。
    # build-tenant-bundle.py は verb "build" が ALLOWED_VERBS にあり既に規約を満たすため登録を外した。
    # install-tenant-bundle.py も動詞 install の追加で規約を満たしたので登録を外した。
    "scripts/tenant-init.py",
    "scripts/tenant-build.py",
    "scripts/tenant-doctor.py",
    "scripts/link_master_plugins.py",
    # plugins/company-master/ の 14 件は plugin ごと削除済み (実体不在) のため登録を外した。
    "scripts/detect-repeated-rubric-violations.py",
    "scripts/inventory-skill-references.py",
    "scripts/skill-fixture-runner.py",
    "scripts/re-evaluate-on-rubric-bump.py",
    "scripts/gate-phase0.py",
    "plugins/skill-governance-lint/scripts/check-rubric-sync.py",
    "plugins/skill-governance-automation/scripts/cross_platform_secret.py",
    "plugins/skill-governance-automation/scripts/rollback-to-stable.py",
    "plugins/skill-governance-automation/scripts/compute-rubric-hash.py",
    "plugins/skill-governance-automation/scripts/doc-to-skill-adapter.py",
    "plugins/skill-governance-automation/scripts/compose-rubrics.py",
    # 上の正本を harness-creator 単独 install 用に byte 一致で同梱した複製 (lint-vendored-ssot.py)。
    # 名前を変えると正本との組が崩れるので、正本のリネームと同時に動かす。
    "plugins/harness-creator/scripts/compose-rubrics.py",
    "plugins/skill-governance-automation/scripts/notify-if-governance-trigger.py",
    "plugins/skill-governance-automation/scripts/write-eval-log.py",
    "plugins/skill-governance-automation/scripts/re-evaluate-on-rubric-bump.py",
    "plugins/skill-governance-migration/scripts/migrate/audit.py",
    "plugins/skill-governance-migration/scripts/migrate/to-brief.py",
    "plugins/skill-governance-migration/scripts/migrate/backfill-source-tier.py",
    "plugins/harness-creator/skills/wrap-git-commit-safe/scripts/pre-commit-secret-scan.py",
    "plugins/harness-creator/skills/run-skill-create/scripts/resolve-brief-to-category.py",
    "plugins/harness-creator/skills/run-build-skill/scripts/set-frontmatter-field.py",
    "scripts/phase2/gen-rollback.py",
    # skill-intake js→py migration (PR #4): keep snake_case until kebab-case rename PR
    # (相互 import される 9 件は PERMANENT_EXCEPTION_PATHS、実体削除済みの
    #  apply_section_template.py / section_quality_check.py は登録ごと外した)
    "plugins/skill-intake/scripts/append_eval_log.py",
    "plugins/skill-intake/scripts/compose_diagram.py",
    "plugins/skill-intake/scripts/convert_md_to_json.py",
    "plugins/skill-intake/scripts/create_notion_database.py",
    "plugins/skill-intake/scripts/cross_check.py",
    "plugins/skill-intake/scripts/enforce_visualization_rules.py",
    "plugins/skill-intake/scripts/extract_open_questions.py",
    "plugins/skill-intake/scripts/intake_publish_pipeline.py",
    "plugins/skill-intake/scripts/measure_value_realized.py",
    "plugins/skill-intake/scripts/optimize_layout.py",
    "plugins/skill-intake/scripts/prepare_notion_assets.py",
    "plugins/skill-intake/scripts/quality_gate.py",
    "plugins/skill-intake/scripts/render_to_image.py",
    "plugins/skill-intake/scripts/render_to_svg.py",
    "plugins/skill-intake/scripts/select_diagram_type.py",
    "plugins/skill-intake/scripts/select_diagrams_per_section.py",
    "plugins/skill-intake/scripts/update_question_bank.py",
    "plugins/skill-intake/scripts/verify_notion_assets.py",
    "plugins/skill-intake/scripts/verify_notion_schema.py",
    "plugins/skill-intake/scripts/ci_dogfooding_retest.py",
    "plugins/skill-intake/scripts/m3_deprecation_reverse_index.py",
    "plugins/skill-intake/scripts/dry_render_notion.py",
    "plugins/skill-intake/scripts/dogfooding_regression.py",
    "plugins/skill-intake/scripts/validate_intake_schema.py",
    # prompt-creator scaffold (PR #4): non-standard verb until renamed
    "plugins/harness-creator/skills/run-build-skill/scripts/resolve-skill-dirs.py",
    "plugins/harness-creator/skills/run-skill-create/scripts/evaluate-create-gates.py",
    "plugins/harness-creator/skills/delegate-codex-skill-review/scripts/check-codex-installed.py",
    # PR #12: skill-intake / prompt-creator / harness-creator 拡張に伴う暫定 PENDING (Change Governance で rename 予定)
    "plugins/prompt-creator/skills/run-prompt-create/scripts/evaluate-create-gates.py",
    "plugins/skill-intake/scripts/analyze_user_intent.py",
    "plugins/skill-intake/scripts/convert_v1_to_v2_context.py",
    "plugins/skill-intake/scripts/lint_subagent_seven_layer.py",
    "plugins/skill-intake/skills/run-intake-next-action/scripts/decide-mode.py",
    "plugins/skill-intake/skills/run-intake-interview/scripts/check-five-axes-coverage.py",
    "plugins/skill-intake/skills/run-intake-visualize/scripts/verify-visuals.py",
    "plugins/harness-creator/scripts/compute-dogfooding-metrics.py",
    "plugins/harness-creator/skills/run-build-skill/scripts/auto-record-lesson.py",
    "plugins/harness-creator/skills/run-elegant-review/scripts/check-review-trigger.py",
    "plugins/harness-creator/skills/wrap-git-commit-safe/scripts/preflight-git-commit.py",
    "plugins/harness-creator/skills/run-skill-rubric-governance/scripts/aggregate-evals.py",
    "plugins/harness-creator/skills/ref-task-context-map/scripts/preload-context-map.py",
    # run-skill-update-notifier (PR #8): notifier verb pending allowed-list extension
    "plugins/harness-creator/skills/run-skill-update-notifier/scripts/notifier-check.py",
    # PR #13: elegant-review v2 / plugin-package-check の新規 verb (emit/aggregate) pending rename
    "plugins/harness-creator/skills/run-elegant-review/scripts/emit-observable.py",
    "plugins/harness-creator/skills/run-plugin-package-check/scripts/aggregate-pkg-findings.py",
    # PR #15: run-build-skill knowledge-skeleton template scripts (生成後 rename)
    "plugins/harness-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/add_entry.py",
    "plugins/harness-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/build_index.py",
    "plugins/harness-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/record_usage.py",
    # prompt-creator js→py 移行 (PR: spec-reflection): 旧 JS 名 (merge/verify/scaffold/generate/convert/log)
    # を踏襲。許可動詞へのリネームは後続 Change Governance PR で SKILL.md/agent/manifest 参照と同時実施。
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/merge-layers.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/verify-completeness.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/scaffold-prompt.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/generate-sheet.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/convert-format.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/log-usage.py",
    # PR #16: notion 3DB schema-as-code / harness-creator 連動 (notion-/sync- verb pending allowed-list extension)
    # sync-notion-schema.py は動詞 sync の追加で規約を満たしたので登録を外した。notion- は
    # 対象名が先頭に来た名前で動詞ではないので、残る2本は改名まで PENDING。
    "scripts/notion-submit-improvement.py",
    "scripts/notion-upsert-plugin.py",
    # harness-creator native-surface projection (C01/C02)。sync-/check- は native surface の
    # 同期 (C01) / parity 検証 (C02) を表す domain 動詞で ALLOWED_VERBS 外。Makefile/CI
    # (governance-check.yml)/reference doc/test が exact name を参照し、sync-native-surfaces.py
    # が sibling として exact name で呼び出すため、許可動詞化 (build/validate 系リネーム or
    # allowed-list 拡張) は参照を原子的に更新する後続 Change Governance PR まで PENDING
    # (sync-notion-schema.py と同種の「sync-/check- verb pending」扱い)。
    # sync-native-surfaces.py / sync-codex-project-settings.py は動詞 sync の追加で規約を
    # 満たしたので登録を外した。残る check- は改名まで PENDING。
    "plugins/harness-creator/scripts/check-native-surface-parity.py",
    # PR #21: spec-drift-guardian の triage/sync パイプライン。parse-/map-/aggregate-/check-/eval-
    # は spec 差分の解析段を表す domain 動詞で ALLOWED_VERBS 外。SKILL.md script_refs /
    # commands / hooks / tests が exact name を参照し、skill 間で sibling 呼び出しするため、
    # 許可動詞化 (validate-/extract- 系リネーム or allowed-list 拡張) は参照を原子的に更新する
    # 後続 Change Governance PR まで PENDING (sync-native-surfaces.py と同種の domain verb pending)。
    "plugins/spec-drift-guardian/scripts/parse-spec-diff.py",
    "plugins/spec-drift-guardian/scripts/map-field-impact.py",
    "plugins/spec-drift-guardian/scripts/aggregate-issue-diffs.py",
    "plugins/spec-drift-guardian/scripts/check-triage-complete.py",
    "plugins/spec-drift-guardian/scripts/eval-fixture-matrix.py",
    "plugins/spec-drift-guardian/scripts/eval-safety-matrix.py",
    # contract-generator 初回投入: 各 run-* スキルの実体スクリプト。
    # 旧 v1 由来の名詞名 (draft/finalize/sync) を SKILL.md/prompts/README 参照と
    # 同時にリネームする後続 Change Governance PR まで PENDING 扱い
    # (3 件とも素の import 参照は 0 件。改名を阻んでいるのは名前参照のみ)。
    "plugins/contract-generator/skills/run-contract-generate/scripts/draft.py",
    "plugins/contract-generator/skills/run-contract-finalize/scripts/finalize.py",
    "plugins/contract-generator/skills/run-template-sync/scripts/sync.py",
    # contract-intake-enum-ssot.py (verb 'contract') / smoke_notion_publish.py (underscore) は
    # SKILL.md/Makefile/README/test 参照と同時にリネームする後続 Change Governance PR まで PENDING。
    "scripts/contract-intake-enum-ssot.py",
    "plugins/skill-intake/scripts/smoke_notion_publish.py",
    # plugins/mf-kessai-invoice-check/ の 21 件と plugins/notion-gmail-send/ の 4 件は
    # plugin ごと削除済み (実体不在) のため登録を外した。
    # plugin-dev-planner 初回投入: §4.3 (kebab-case) は満たすが verb が ALLOWED_VERBS 外。
    # check (構造/ゲート検証) / verify (top-sort 検証) / evaluate (plan 評価) / detect (未配置検出) は
    # 許可動詞 (validate/lint 等) に機械置換すると SKILL.md(script_refs)/prompts/manifest/test/CI
    # (governance-check.yml・build-steps.md)/golden examples の参照を一括改名する必要があり、
    # 参照整合の原子性のため後続 Change Governance PR で同時実施する (mf-kessai / notion-gmail-send /
    # prompt-creator と同種の「新規 plugin 初回投入時の verb pending」扱い)。
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-plugin-goal-spec.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-requirements-coverage.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-spec-frontmatter.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-spec-gates.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-spec-matrix-coverage.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-surface-inventory.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-build-handoff.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-plugin-surface-audit.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-runtime-portability.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-upstream-pins.py",
    # 拡張ゲート3本 (layer A/B 下流ハーネス検査 + dogfooding selfcheck) の追加投入。既存
    # check-* 群と同一ディレクトリ・同一動詞規約のため、同じ Change Governance 一括改名
    # PR で同時に許可動詞化する (3本だけ validate-* へ先行改名すると兄弟 script と不整合)。
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-generative-fidelity.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-downstream-harness.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-harness-coverage-selfcheck.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/verify-index-topsort.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/detect-unassigned.py",
    # plugin-dev-planner task-graph 拡張 (C1-C16 第3の射影) 投入: §4.3 (kebab-case) は満たすが
    # verb (derive/compute/accept/apply/check/migrate) が ALLOWED_VERBS 外。既存 check-* 決定論
    # ゲート族と同種で、SKILL.md(script_refs)/schemas/tests/handoff の参照整合の原子性のため、
    # 許可動詞化は planner check-* 群と同じ後続 Change Governance 一括改名 PR まで PENDING
    # (validate-task-graph.py / render-task-graph-mermaid.py は verb が ALLOWED_VERBS 内ゆえ非対象)。
    # migrate-plan-layout.py は動詞 migrate の追加で規約を満たしたので登録を外した。
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/derive-task-graph.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/compute-ready-set.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/accept-discovered-task.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/apply-handoff-notes.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-plan-ledger.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-shape-non-regression.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-task-state-schema.py",
    "plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator/scripts/evaluate-plan.py",
    # harness-creator パイプライン境界契約 (E1/E2/E3) 初回投入: §4.3 (kebab-case) は満たすが
    # verb (check/emit) が ALLOWED_VERBS 外。これらは既存の check-* 決定論ゲート族 (上記 19 本) と
    # 同種で、plan の component-inventory.json / handoff-run-plugin-dev-plan.json の build_target が
    # 正確なパスを参照する (C08 check-route-component-parity / check-build-handoff の parity) ため、
    # 許可動詞化 (validate/render 系へのリネーム) は inventory/handoff/prompts/commands/tests 参照を
    # 原子的に更新する後続 Change Governance PR まで PENDING (plugin-dev-planner check-* /
    # notion-gmail-send emit-observable と同種の「初回投入時の verb pending」扱い)。
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-intake-consumption.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-provenance-chain.py",
    "plugins/harness-creator/scripts/check-route-component-parity.py",
    "plugins/harness-creator/scripts/emit-improvement-handoff.py",
    # task-graph consumer (harness-creator 実行系 C01-C08 初回投入): dispatch (ready-set 配信) /
    # sync (task-state write-back) / inject (成果物注入) / emit (discovered-task) / summarize
    # (進捗集計) / manage (build lease) / record (knowledge 記録) は ALLOWED_VERBS 外。
    # commands/capability-build.md / references / tests / SKILL 参照の原子的更新を伴う後続
    # Change Governance 一括改名 PR まで PENDING (planner check-* / emit-improvement-handoff と同種)。
    # sync-task-state.py / manage-build-lease.py / record-task-graph-knowledge.py は動詞 sync・
    # manage・record の追加で規約を満たしたので登録を外した。
    "plugins/harness-creator/scripts/dispatch-ready-set.py",
    "plugins/harness-creator/scripts/inject-task-inputs.py",
    "plugins/harness-creator/scripts/emit-discovered-task.py",
    "plugins/harness-creator/scripts/summarize-task-progress.py",
    # project-task-status.py (TG-C09 status live 投影): task-state.json の live status を
    # plan dir へ射影 (task-graph.json は graph_hash pin ゆえ不変設計・state は別ファイル)。
    # 上記 task-graph consumer 族と同種で verb 'project' が ALLOWED_VERBS 外。commands/
    # references/tests 参照の原子的更新を伴う後続 Change Governance 一括改名 PR まで PENDING。
    "plugins/harness-creator/scripts/project-task-status.py",
    # ubm-goal-setting 初回投入: detect (registry MD5 差分検出) / check (knowledge 500 行
    # ガード) は verb pending。SKILL.md(script_refs)/workflow-manifest/tests/EVALS.json/
    # 計画書 (plugin-plans/finish) の参照整合の原子性のため、planner 群と同じ後続
    # Change Governance 一括改名 PR で許可動詞化する。
    "plugins/ubm-goal-setting/skills/run-ubm-knowledge-sync/scripts/detect-knowledge-updates.py",
    "plugins/ubm-goal-setting/skills/run-ubm-knowledge-sync/scripts/check-knowledge-split.py",
    # task-graph consumer 族 (harness-creator の project-task-status / record-task-graph-knowledge
    # と同種) を planner 側 run-plugin-dev-plan にも同梱: project-task-status.py (TG-C09 status
    # live 投影) は verb 'project'、check-cycle-knowledge.py (依存 closure の循環検出 knowledge
    # ガード) は verb 'check' が ALLOWED_VERBS 外。SKILL.md(script_refs)/tests/schemas 参照の
    # 原子的更新を伴う後続 Change Governance 一括改名 PR まで PENDING (既存 check-* 群と同種)。
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/project-task-status.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-cycle-knowledge.py",
    # run-skill-live-trial 初回投入 (anti-goodhart D2/D12): §4.3 (kebab-case) は満たすが
    # 接頭辞が <feature>-<role> 形 (live-trial-*) で verb が ALLOWED_VERBS 外。boot/send/
    # poll/status/verdict は trial セッションのライフサイクル語で許可動詞に対応語が無く、
    # backend は tmux 輸送層の版依存モジュール境界 (唯一の tmux 呼出点) の固有名。許可動詞化
    # は SKILL.md(script_refs)/references/tests 参照と同時に実施する後続 Change Governance PR
    # まで PENDING (notion-gmail-send / plugin-dev-planner と同種の「初回投入時の verb pending」扱い)。
    "plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-backend.py",
    "plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-boot.py",
    "plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-send.py",
    "plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-status.py",
    "plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-poll.py",
    "plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-verdict.py",
    # system-spec-harness 初回投入: §4.3 (kebab-case) は満たすが verb が ALLOWED_VERBS 外。
    # compile (収集仕様→章立て仕様書へコンパイル) / apply (spec-state 遷移適用) / aggregate
    # (観点別 verdict を総合 verdict へ集約) は許可動詞に対応語が無い。許可動詞化は
    # SKILL.md(script_refs)/prompts/tests/agent 参照を原子的に更新する後続 Change Governance
    # 一括改名 PR まで PENDING (plugin-dev-planner check-* / notion-gmail-send emit-observable
    # と同種の「新規 plugin 初回投入時の verb pending」扱い)。
    "plugins/system-spec-harness/skills/run-system-spec-compile/scripts/compile-spec-doc.py",
    "plugins/system-spec-harness/skills/run-system-spec-elicit/scripts/apply-spec-transition.py",
    "plugins/system-spec-harness/skills/assign-system-spec-completeness-evaluator/scripts/aggregate-completeness.py",
    # extract-system-blueprint (新規 plugin 初回投入): ドメイン固有 verb (fetch/authz/browser/doc/
    # mermaid/layout/emit/recount) が SKILL.md/prompts/tests/EVALS/workflow-manifest に深く参照されるため、
    # 参照一括更新を伴う rename は後続 Change Governance PR まで PENDING 扱い (system-spec-harness と同種)。
    "plugins/extract-system-blueprint/scripts/fetch-snapshot.py",
    "plugins/extract-system-blueprint/scripts/authz-classify.py",
    "plugins/extract-system-blueprint/scripts/browser-render.py",
    "plugins/extract-system-blueprint/scripts/doc-emit.py",
    "plugins/extract-system-blueprint/scripts/mermaid-validate.py",
    "plugins/extract-system-blueprint/scripts/layout-template-dedup.py",
    "plugins/extract-system-blueprint/skills/assign-blueprint-fidelity-evaluator/scripts/emit-verdict.py",
    "plugins/extract-system-blueprint/skills/assign-blueprint-fidelity-evaluator/scripts/recount-palette-orphans.py",
    # ubm-goal-setting YouTube取込+相談グラフ初回投入: §4.3 (kebab-case) は満たすが verb が
    # ALLOWED_VERBS 外。index (成果物グラフ索引化) / consult (read-only グラフ相談) / run
    # (scheduler one-shot 実行体) / check (backfill 完全性の決定論ゲート・既存 check-* 族と同種)
    # は許可動詞に対応語が無い。許可動詞化は SKILL.md (script_refs)/workflow-manifest/
    # tests/EVALS.json 参照を原子的に更新する後続 Change Governance 一括改名 PR まで PENDING
    # (同ディレクトリの youtube_provider.py / normalized_source_path.py は import 対象なので
    #  PERMANENT_EXCEPTION_PATHS)。
    "plugins/ubm-goal-setting/scripts/index-harness-artifact-graph.py",
    "plugins/ubm-goal-setting/scripts/consult-harness-artifact-graph.py",
    "plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py",
    "plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/check-youtube-backfill-completeness.py",
    # dev-graph / system-dev-planner 投入 (マクロ/ミクロ二層 + verification-obligation 拡張):
    # domain 動詞 (promote/resolve/check/init/manage/schedule/reconcile/register/derive/record/
    # plan/sandbox/run) と bd-/gh- bridge が ALLOWED_VERBS 外 (_common.py は import 対象なので
    # PERMANENT_EXCEPTION_PATHS)。SKILL.md script_refs /
    # hooks / manifest / test 参照を原子的に更新する後続 Change Governance PR (許可動詞化 or 一括
    # リネーム) まで PENDING。
    # manage-system-plan-lock.py / manage-worktree-lease.py / record-verification-evidence.py は
    # 動詞 manage・record の追加で規約を満たしたので登録を外した。
    "plugins/system-dev-planner/scripts/promote-system-plan.py",
    "plugins/system-dev-planner/scripts/resolve-project-context.py",
    "plugins/system-dev-planner/scripts/check-implementation-readiness.py",
    "plugins/system-dev-planner/scripts/init-project-layout.py",
    "plugins/dev-graph/scripts/bd-bridge.py",
    "plugins/dev-graph/scripts/gh-bridge.py",
    "plugins/dev-graph/scripts/schedule-graph.py",
    "plugins/dev-graph/scripts/reconcile-github-lifecycle.py",
    "plugins/dev-graph/scripts/resolve-repo-context.py",
    "plugins/dev-graph/scripts/register-package.py",
    "plugins/harness-creator/skills/run-build-skill/scripts/derive-route-build-obligations.py",
    "plugins/harness-creator/skills/run-build-skill/scripts/derive-verification-contract.py",
    "plugins/harness-creator/skills/run-build-skill/scripts/plan-verification-obligations.py",
    "plugins/harness-creator/skills/run-plugin-package-check/scripts/sandbox-plugin-lifecycle.py",
    "plugins/harness-creator/skills/run-plugin-package-check/scripts/run-pkg-015.py",
    "plugins/harness-creator/skills/run-skill-live-trial/scripts/plan-live-trials.py",
    # slide-report-generator の Playwright vendor bootstrap: §4.3 (kebab-case) は満たすが
    # verb 'setup' が ALLOWED_VERBS 外。plugin-local vendor へ OS/CPU 別 Chromium を復元する
    # 段で、build (成果物生成) とも validate (検査) とも意味がずれる。SKILL.md/README/
    # tests/CI が exact name を参照するため、許可動詞化 (allowed-list 拡張) は参照を原子的に
    # 更新する後続 Change Governance PR まで PENDING
    # (setup-send-log-db.py と同種の「setup verb pending」扱い)。
    # setup は install と同じ意味なので動詞には足さず、install に寄せた
    # (PROP-2026-10-12-SCRIPT-VERBS)。install-* への改名まで PENDING。
    "plugins/slide-report-generator/scripts/setup-playwright.py",
    # guide-doc-generator 初回投入: §4.3 (kebab-case) は満たすが verb が ALLOWED_VERBS 外。
    # verify-* 5 本は「生成済み HTML が自己完結か / a11y・印刷に耐えるか / 言語規約を守るか /
    # 語りが通っているか」を検査する成果物ゲートで、構成データを検査する validate-handout-config.py
    # (verb 'validate' ゆえ非対象) とは検査対象の層が違う。両者を validate-* へ潰すと
    # 「入力の妥当性」と「出力の健全性」の区別が名前から消え、C09 のゲート集約が何を集約して
    # いるのか読めなくなる。resolve (プリセット解決) / route (出力先ルーティング) /
    # embed (data URI 化) も同様に domain 動詞で、既存の許可動詞に写像先が無い。
    # srg-image-bridge.py は verb でなく委譲先 plugin 名 (slide-report-generator) を冠しており
    # §4.3 の形からも外れる — 単独で直すと bridge 先の対応が名前から消えるため一括で扱う。
    # SKILL.md script_refs / plugin-composition.yaml / EVALS.json / hook / 23 スイート 3,565 tests
    # が exact name を参照するため、許可動詞化 (allowed-list 拡張) と改名は参照を原子的に更新する
    # 後続 Change Governance PR まで PENDING (setup-playwright.py と同種の「新 verb pending」扱い)。
    "plugins/guide-doc-generator/scripts/embed-assets.py",
    "plugins/guide-doc-generator/scripts/resolve-handout-preset.py",
    "plugins/guide-doc-generator/scripts/route-handout-output.py",
    "plugins/guide-doc-generator/scripts/srg-image-bridge.py",
    "plugins/guide-doc-generator/scripts/verify-handout-a11y-print.py",
    "plugins/guide-doc-generator/scripts/verify-handout-language.py",
    "plugins/guide-doc-generator/scripts/verify-handout-narrative.py",
    "plugins/guide-doc-generator/scripts/verify-handout-selfcontained.py",
    # 上記正本の fixture コピー。contract test が「受理される plugin 実体の形」を組み立てるため
    # 実在ファイルとして置いており、正本と同名でなければ script_refs の解決契約を検査できない。
    # 正本の改名と同じ PR で同時に追従させる (先に fixture だけ改名すると test が正本を見失う)。
    "plugins/guide-doc-generator/tests/assign-handout-readability-evaluator/fixtures/accept/scripts/verify-handout-language.py",
    "plugins/guide-doc-generator/tests/handout-extract/fixtures/accept/scripts/verify-handout-selfcontained.py",
    "plugins/guide-doc-generator/tests/handout-verify/fixtures/accept/scripts/verify-handout-a11y-print.py",
    "plugins/guide-doc-generator/tests/handout-verify/fixtures/accept/scripts/verify-handout-language.py",
    "plugins/guide-doc-generator/tests/handout-verify/fixtures/accept/scripts/verify-handout-narrative.py",
    "plugins/guide-doc-generator/tests/handout-verify/fixtures/accept/scripts/verify-handout-selfcontained.py",
    "plugins/guide-doc-generator/tests/run-handout-build/fixtures/accept/scripts/resolve-handout-preset.py",
    "plugins/guide-doc-generator/tests/run-handout-build/fixtures/accept/scripts/route-handout-output.py",
    "plugins/guide-doc-generator/tests/run-handout-build/fixtures/accept/scripts/verify-handout-a11y-print.py",
    "plugins/guide-doc-generator/tests/run-handout-build/fixtures/accept/scripts/verify-handout-language.py",
    "plugins/guide-doc-generator/tests/run-handout-build/fixtures/accept/scripts/verify-handout-narrative.py",
    "plugins/guide-doc-generator/tests/run-handout-build/fixtures/accept/scripts/verify-handout-selfcontained.py",
    "plugins/guide-doc-generator/tests/run-handout-extract/fixtures/accept/scripts/verify-handout-selfcontained.py",
}

VALID_NAME = re.compile(r"^([a-z]+)-[a-z0-9-]+\.py$")

# §4.1 の動詞リスト変更 (P1 Structural change・33章ワークフロー) を待っている path。
# doc/ClaudeCodeスキルの設計書/28-script-execution-model.md:199 (§4.7) 逐語:
# 「動詞リスト変更は P1 Structural change として33章ワークフローに従う」。
#
# ここへ入れる条件は「33章の記録があること」。script が何をしているかを読んだ上での
# 判断は機械的に確定できないので、この集合は空から始める。判定できない path は
# UNDECIDED として別に数える (全部ここへ寄せて棚を空に見せない)。
VERB_LIST_CHANGE_PATHS = frozenset()

SCAN_ROOTS = ["scripts", "plugins"]
SKIP_PARTS = {"_lib", "__pycache__", "node_modules", ".git"}


def find_scripts(roots):
    for root in roots:
        rp = pathlib.Path(root)
        if not rp.exists():
            continue
        if rp.is_file():
            # 明示されたファイルは置き場所を問わず照合する。
            if rp.suffix == ".py":
                yield rp
            continue
        for p in rp.rglob("*.py"):
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            # 判定は repo 相対の path で行う (repo の外にある祖先 dir の名前に引きずられない)。
            rel = pathlib.PurePosixPath(repo_key(p))
            if "scripts" in rel.parts[:-1] or rel.parent.name.endswith("scripts"):
                yield p
            elif rp.name == "scripts":
                yield p


def repo_key(path) -> str:
    """個別パスの照合キー: repo root (その外なら cwd) からの posix 相対パス。

    symlink は実体へ解決しない。/tmp と /private/tmp のような親 dir の別名だけは、親を
    実パスにしてから照合する。どちらの root の下にも無ければ、渡された path のまま返す。
    """
    path = pathlib.Path(path)
    absolute = pathlib.Path(os.path.abspath(path))
    forms = (absolute, pathlib.Path(os.path.realpath(absolute.parent)) / absolute.name)
    for base in (REPO_ROOT, pathlib.Path.cwd().resolve()):
        for form in forms:
            try:
                return form.relative_to(base).as_posix()
            except ValueError:
                continue
    return path.as_posix()


def classify_without_ledger(path: pathlib.Path):
    """台帳 (PERMANENT_EXCEPTION_PATHS / PENDING_RENAME_PATHS) を一切参照しない判定。

    返済検出がこの関数だけを使う。台帳に載っている path をここへ通して VIOLATION でなく
    なっていたら、その登録はもう不要だと機械的に言える。classify() から台帳を引き算した
    残りをここに置いているので、規約本体を直せば両方に効く。
    """
    name = path.name
    if name in BANNED_NAMES:
        return ("VIOLATION", f"banned name: {name}")
    if path.parent.name == "adapters":
        return ("EXCEPTION", "Hexagonal adapter (§4.6)")
    for pat, reason in EXCEPTION_PATTERNS:
        if pat.match(name):
            return ("EXCEPTION", reason)
    m = VALID_NAME.match(name)
    if not m:
        if "_" in name:
            return ("VIOLATION", "underscore not allowed (§4.3)")
        return ("VIOLATION", "does not match <verb>-<target>[-<scope>].py")
    verb = m.group(1)
    if verb not in ALLOWED_VERBS:
        return ("VIOLATION", f"verb '{verb}' not in allowed list {sorted(ALLOWED_VERBS)}")
    return ("OK", None)


def classify(path: pathlib.Path):
    name = path.name
    posix = repo_key(path)
    if name in BANNED_NAMES:
        return ("VIOLATION", f"banned name: {name}")
    if path.parent.name == "adapters":
        return ("EXCEPTION", "Hexagonal adapter (§4.6)")
    for pat, reason in EXCEPTION_PATTERNS:
        if pat.match(name):
            return ("EXCEPTION", reason)
    if posix in PERMANENT_EXCEPTION_PATHS:
        return ("PERMANENT_EXCEPTION", PERMANENT_EXCEPTION_PATHS[posix])
    if posix in PENDING_RENAME_PATHS:
        return ("PENDING_RENAME", "legacy path scheduled for rename (33章 Change Governance)")
    for pat in PENDING_RENAME_PATTERNS:
        if pat.match(name):
            return ("PENDING_RENAME", "hook-* prefix scheduled for rename (33章 Change Governance)")
    return classify_without_ledger(path)


def pending_repayment_class(path: pathlib.Path):
    """PENDING を「どうやって返済できるか」で分ける。推測で振らない。

    P: kebab 化するだけで規約を満たす (先頭トークンが既に許可動詞)。実測で確定できる
    G: §4.1 の動詞リスト変更待ち。VERB_LIST_CHANGE_PATHS に 33章の記録つきで載せた path のみ
    H: hook-* パターン由来 (台帳に無い)
    U: 上のどれでもない。その script が何をしているかを人が読まないと
       「改名で返済できる」か「動詞リスト変更が要る」か決められない

    U を G に寄せると棚が空に見える。だから寄せない。
    """
    posix = repo_key(path)
    if posix not in PENDING_RENAME_PATHS:
        return "H"
    if posix in VERB_LIST_CHANGE_PATHS:
        return "G"
    kebab = path.name.replace("_", "-")
    if classify_without_ledger(path.with_name(kebab))[0] == "OK":
        return "P"
    return "U"


def _imported_stems(stems, base: pathlib.Path):
    """base 以下の .py に、stems のどれかを素の import する行があるか。見つかった stem の集合を返す。

    `import <stem>` / `from <stem> import` を行頭 (インデント可) で探す。ファイル名が
    `<stem>.py` のファイル自身の行は参照に数えない。隠し dir (.git・.venv など) と
    __pycache__ / node_modules は降りない。
    """
    if not stems:
        return set()
    alternatives = "|".join(re.escape(stem) for stem in sorted(stems))
    pattern = re.compile(
        rf"^[ \t]*(?:from[ \t]+({alternatives})[ \t]+import\b|import[ \t]+({alternatives})\b)",
        re.M,
    )
    found = set()
    for dirpath, dirnames, filenames in os.walk(base):
        # _lib の中の import も参照に数えるので、SKIP_PARTS ではなくこの集合で絞る。
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in {"__pycache__", "node_modules"}
        ]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            try:
                text = pathlib.Path(dirpath, filename).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for match in pattern.finditer(text):
                stem = match.group(1) or match.group(2)
                if filename != f"{stem}.py":
                    found.add(stem)
    return found


def _stale_registrations(scripts, *, full_scope: bool):
    """台帳の逆向きの歯止め。(返済済み, 実体不在, import 参照の無い恒久例外) を返す。

    一方向ラチェット (新規違反だけを弾く) だと、台帳は増える一方で現実からズレる。
    この関数が逆向き、つまり「もう要らない登録」を検出して exit 1 にする。

    full_scope=False (走査 path を明示した narrow 実行) のときは不在検出と参照検出を
    無効化する。範囲外 plugin の登録が「今回集めた path に無い」ことは消滅の証拠にならず
    誤検出になる (plugins/harness-creator/scripts/lint-skill-runtime-profiles.py の
    _stale_legacy_paths と同じ理由)。参照は repo 全域から数えるので、走査の基準 (cwd) が
    repo root である全域走査のときだけ意味を持つ。返済検出は走査した path に限って行うので
    範囲に依存しない。

    台帳を増やすほど緑になる道は作らない。登録を足しても「実体が無い」「もう規約を満たす」
    「恒久例外なのに誰も import していない」なら即 stale で赤になり、満たさないなら
    PENDING/PERMANENT の数として summary に残る。
    走査対象 (ディスク上の実ファイル) と台帳の置き場 (この .py のリテラル) は別のままにする。
    """
    registered = set(PERMANENT_EXCEPTION_PATHS) | set(PENDING_RENAME_PATHS)
    scanned = {repo_key(p) for p in scripts}
    repaid = tuple(sorted(
        posix for posix in registered & scanned
        if classify_without_ledger(pathlib.Path(posix))[0] != "VIOLATION"
    ))
    if not full_scope:
        return repaid, (), ()
    absent = tuple(sorted(registered - scanned))
    # 返済済み・不在の登録は既に stale なので、参照の有無は残りの恒久例外だけで見る。
    candidates = (set(PERMANENT_EXCEPTION_PATHS) & scanned) - set(repaid)
    stems = {pathlib.PurePosixPath(posix).stem for posix in candidates}
    imported = _imported_stems(stems, pathlib.Path.cwd())
    unreferenced = tuple(sorted(
        posix for posix in candidates
        if pathlib.PurePosixPath(posix).stem not in imported
    ))
    return repaid, absent, unreferenced


def main(argv):
    if "-h" in argv[1:] or "--help" in argv[1:]:
        print(__doc__.strip())
        return 0
    options = [a for a in argv[1:] if a.startswith("--")]
    unknown = [a for a in options if a != "--report"]
    if unknown:
        print(f"config error: unknown option(s): {' '.join(unknown)}", file=sys.stderr)
        return 2
    report_mode = "--report" in options
    paths = [a for a in argv[1:] if not a.startswith("--")]
    missing = [a for a in paths if not pathlib.Path(a).exists()]
    if missing:
        print(f"config error: path not found: {' '.join(missing)}", file=sys.stderr)
        return 2
    scripts = list(find_scripts(paths or SCAN_ROOTS))
    if not scripts:
        print(
            f"config error: no scripts scanned under {' '.join(paths or SCAN_ROOTS)} "
            f"(cwd={pathlib.Path.cwd()})",
            file=sys.stderr,
        )
        return 2
    results = {
        "OK": [],
        "EXCEPTION": [],
        "PERMANENT_EXCEPTION": [],
        "PENDING_RENAME": [],
        "VIOLATION": [],
    }
    for p in scripts:
        status, reason = classify(p)
        results[status].append({"path": str(p), "reason": reason})
    repaid, absent, unreferenced = _stale_registrations(scripts, full_scope=not paths)
    stale_total = len(repaid) + len(absent) + len(unreferenced)
    pend = {"P": [], "G": [], "H": [], "U": []}
    for item in results["PENDING_RENAME"]:
        pend[pending_repayment_class(pathlib.Path(item["path"]))].append(item["path"])
    if report_mode:
        print(json.dumps({
            "summary": {
                **{k: len(v) for k, v in results.items()},
                "pending_rename_only": len(pend["P"]),
                "pending_verb_list_change": len(pend["G"]),
                "pending_hook_pattern": len(pend["H"]),
                "pending_undecided": len(pend["U"]),
                "ledger_stale": stale_total,
            },
            "pending_undecided": pend["U"],
            "violations": results["VIOLATION"],
            "permanent_exception": results["PERMANENT_EXCEPTION"],
            "pending_rename": results["PENDING_RENAME"],
            "ledger_stale_repaid": list(repaid),
            "ledger_stale_absent": list(absent),
            "ledger_stale_unreferenced": list(unreferenced),
        }, indent=2, ensure_ascii=False))
    else:
        for item in results["VIOLATION"]:
            print(f"VIOLATION {item['path']}: {item['reason']}", file=sys.stderr)
        for item in results["PENDING_RENAME"]:
            print(f"PENDING  {item['path']}: {item['reason']}", file=sys.stderr)
        for posix in repaid:
            print(
                f"STALE    {posix}: 既に規約を満たしているので台帳から外す (返済済み)",
                file=sys.stderr,
            )
        for posix in absent:
            print(f"STALE    {posix}: 実体が無いので台帳から外す (消滅)", file=sys.stderr)
        for posix in unreferenced:
            print(
                f"STALE    {posix}: 素の import 参照が 0 件なので恒久例外から外す "
                "(PENDING_RENAME_PATHS へ移すか改名する)",
                file=sys.stderr,
            )
        print(
            f"summary: OK={len(results['OK'])} "
            f"EXCEPTION={len(results['EXCEPTION'])} "
            f"PERMANENT={len(results['PERMANENT_EXCEPTION'])} "
            f"PENDING={len(results['PENDING_RENAME'])} "
            f"(P={len(pend['P'])} G={len(pend['G'])} "
            f"H={len(pend['H'])} UNDECIDED={len(pend['U'])}) "
            f"VIOLATION={len(results['VIOLATION'])} "
            f"stale={stale_total}"
        )
    return 1 if results["VIOLATION"] or stale_total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
