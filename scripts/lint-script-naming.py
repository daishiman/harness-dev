#!/usr/bin/env python3
"""lint-script-naming.py

28章 §4.1-§4.6 のscript命名規約を機械強制する。
- 動詞リスト: lint/validate/format/render/extract/diff/guard/build
- 例外節 (§4.4): sink_*.py / *_helper.py / audit_*.py
- 例外節 (§4.6): adapters/*.py (Hexagonal Architecture adapter固有名)
- 禁止: アンダースコア(例外節を除く), check/run/main/utils/helper のみ命名

usage:
  python3 scripts/lint-script-naming.py [path...]
  python3 scripts/lint-script-naming.py --report

exit code:
  0 違反なし
  1 違反検出
  2 設定エラー

CONVENTIONS: stdlib only.
"""
import json
import pathlib
import re
import sys

ALLOWED_VERBS = {
    "lint", "validate", "format", "render",
    "extract", "diff", "guard", "build",
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

# 暫定例外: 個別パス (初回投入時の既存スクリプト群、33章 Change Governance 管理下)
# リネーム計画は .claude/changelog/governance-log.jsonl 参照
PENDING_RENAME_PATHS = {
    # Multi-tenant public CLI names are fixed by doc/マルチ企業展開. Python module
    # helpers retain underscores because they are imported by standalone plugins.
    "scripts/tenant-init.py",
    "scripts/tenant-build.py",
    "scripts/tenant-doctor.py",
    "scripts/build-tenant-bundle.py",
    "scripts/install-tenant-bundle.py",
    "scripts/link_master_plugins.py",
    "scripts/tenant_runtime.py",
    "plugins/harness-creator/scripts/tenant_runtime.py",
    "plugins/skill-intake/scripts/tenant_runtime.py",
    "plugins/company-master/scripts/tenant_runtime.py",
    "plugins/mf-kessai-invoice-check/lib/tenant_runtime.py",
    "plugins/contract-generator/lib/tenant_runtime.py",
    "plugins/notion-gmail-send/lib/tenant_runtime.py",
    "plugins/skill-governance-automation/scripts/tenant_runtime.py",
    # company-master (PR: 日本郵便 addresszip 移行): scripts/*.py は相互 import される
    # Python モジュール (import notion_config / postal_api 等) のため §4.3 のハイフン命名を
    # 適用できず underscore 許容。skill-intake の同種モジュール群と同じ PENDING 扱い
    # (後続 Change Governance PR で一括リネーム検討。正本 harness-creator/scripts/notion_config.py も PENDING)。
    "plugins/company-master/scripts/notion_config.py",
    "plugins/company-master/scripts/notion_upsert.py",
    "plugins/company-master/scripts/postal_api.py",
    "plugins/company-master/scripts/postal_proxy.py",
    "plugins/company-master/scripts/enrich_company.py",
    "plugins/company-master/scripts/resolve_company.py",
    "plugins/company-master/scripts/validate_company_master.py",
    "plugins/company-master/scripts/company_master.py",
    "plugins/company-master/scripts/confirm_url.py",
    "plugins/company-master/scripts/bootstrap_plugin.py",
    "plugins/company-master/scripts/normalize.py",
    "plugins/company-master/scripts/remarks.py",
    "plugins/company-master/scripts/backfill.py",
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
    "plugins/skill-intake/scripts/append_eval_log.py",
    "plugins/skill-intake/scripts/apply_section_template.py",
    "plugins/skill-intake/scripts/check_completeness.py",
    "plugins/skill-intake/scripts/compose_diagram.py",
    "plugins/skill-intake/scripts/convert_md_to_json.py",
    "plugins/skill-intake/scripts/create_notion_database.py",
    "plugins/skill-intake/scripts/cross_check.py",
    "plugins/skill-intake/scripts/detect_contradictions.py",
    "plugins/skill-intake/scripts/enforce_visualization_rules.py",
    "plugins/skill-intake/scripts/extract_open_questions.py",
    "plugins/skill-intake/scripts/intake_publish_pipeline.py",
    "plugins/skill-intake/scripts/keychain_get_secret.py",
    "plugins/skill-intake/scripts/measure_value_realized.py",
    "plugins/skill-intake/scripts/notion_http.py",
    "plugins/skill-intake/scripts/optimize_layout.py",
    "plugins/skill-intake/scripts/prepare_notion_assets.py",
    "plugins/skill-intake/scripts/publish_notion_page.py",
    "plugins/skill-intake/scripts/quality_gate.py",
    "plugins/skill-intake/scripts/render_notion_page.py",
    "plugins/skill-intake/scripts/render_to_image.py",
    "plugins/skill-intake/scripts/render_to_svg.py",
    "plugins/skill-intake/scripts/section_quality_check.py",
    "plugins/skill-intake/scripts/select_diagram_type.py",
    "plugins/skill-intake/scripts/select_diagrams_per_section.py",
    "plugins/skill-intake/scripts/update_question_bank.py",
    "plugins/skill-intake/scripts/validate_intake.py",
    "plugins/skill-intake/scripts/validate_mermaid.py",
    "plugins/skill-intake/scripts/verify_notion_assets.py",
    "plugins/skill-intake/scripts/verify_notion_schema.py",
    "plugins/skill-intake/scripts/ci_dogfooding_retest.py",
    "plugins/skill-intake/scripts/render_v2_adapter.py",
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
    "plugins/harness-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/search_knowledge.py",
    # run-build-skill task-graph-engine template payload scripts (engine:task-graph 変種で生成
    # harness に焼き込まれる engine 実体・生成後 rename)。§4.3 (kebab-case) は満たすが verb
    # (self/ready/record) が ALLOWED_VERBS 外。knowledge-skeleton template と同種で repo tooling
    # でなく生成物 payload ゆえ後続 Change Governance PR まで PENDING
    # (extract-capability-dependency-graph.py は verb 'extract' が ALLOWED_VERBS 内ゆえ非対象)。
    "plugins/harness-creator/skills/run-build-skill/templates/task-graph-engine/scripts/self-reflect-append.py",
    "plugins/harness-creator/skills/run-build-skill/templates/task-graph-engine/scripts/ready-set-from-checklist.py",
    "plugins/harness-creator/skills/run-build-skill/templates/task-graph-engine/scripts/record-capability-graph-knowledge.py",
    # prompt-creator js→py 移行 (PR: spec-reflection): 旧 JS 名 (merge/verify/scaffold/generate/convert/log)
    # を踏襲。許可動詞へのリネームは後続 Change Governance PR で SKILL.md/agent/manifest 参照と同時実施。
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/merge-layers.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/verify-completeness.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/scaffold-prompt.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/generate-sheet.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/convert-format.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/log-usage.py",
    # PR #16: notion 3DB schema-as-code / harness-creator 連動 (notion-/sync- verb pending allowed-list extension)
    "scripts/notion-submit-improvement.py",
    "scripts/notion-upsert-plugin.py",
    "scripts/sync-notion-schema.py",
    # PR #16: build-trace SSOT shim (Python import がハイフン不可のため underscore 許容、§4.3 例外)
    "plugins/harness-creator/skills/run-build-skill/scripts/validate_build_trace_shim.py",
    # feedback_contract criteria の単一 SSOT モジュール。validate-build-trace.py /
    # lint-feedback-contract.py / lint-content-review.py から import される共有 module の
    # ため Python import 上ハイフン不可 (§4.3 恒久例外)。
    "scripts/feedback_contract_ssot.py",
    # repo 全域テスト探索の単一 SSOT モジュール (elegant-review 2026-06-30 / LS-F1)。
    # lint-test-discovery-coverage.py と tests/test_lint_test_discovery_coverage.py から
    # `import discover_repo_tests` される共有 module のため Python import 上ハイフン不可 (§4.3 恒久例外)。
    "scripts/discover_repo_tests.py",
    # 上記正本の vendored 実体コピー (harness-creator 単独 install 用)。runtime hook /
    # build-time validator が plugin 内で import するため、正本と byte 完全一致を要件とし
    # underscore 名のまま固定する (リネームすると import 名が変わり byte 一致が崩れる)。
    # byte 一致は scripts/lint-vendored-ssot.py が強制 (§4.3 恒久例外)。
    "plugins/harness-creator/scripts/feedback_contract_ssot.py",
    # PR #17: per-repo Notion config SSOT loader (Python import 必須、§4.3 例外。
    # skill-intake 側は harness-creator 側への symlink で SSOT 維持)
    "plugins/harness-creator/scripts/notion_config.py",
    "plugins/skill-intake/scripts/notion_config.py",
    # contract-generator 初回投入: 各 run-* スキルの実体スクリプト。
    # 旧 v1 由来の名詞名 (draft/finalize/sync) を SKILL.md/prompts/README 参照と
    # 同時にリネームする後続 Change Governance PR まで PENDING 扱い。
    "plugins/contract-generator/skills/run-contract-generate/scripts/draft.py",
    "plugins/contract-generator/skills/run-contract-finalize/scripts/finalize.py",
    "plugins/contract-generator/skills/run-template-sync/scripts/sync.py",
    # PR #27: skill-intake 単独配布の自己完結化 (vendoring / 同梱 SSOT)
    # _vendor.py / _jsonschema_compat.py は render-intake-final.py 等から import される
    # private module で Python import 上ハイフン不可のため underscore 許容 (§4.3 恒久例外)。
    "plugins/skill-intake/scripts/_vendor.py",
    "plugins/skill-intake/scripts/_jsonschema_compat.py",
    # contract-intake-enum-ssot.py (verb 'contract') / smoke_notion_publish.py (underscore) は
    # SKILL.md/Makefile/README/test 参照と同時にリネームする後続 Change Governance PR まで PENDING。
    "scripts/contract-intake-enum-ssot.py",
    "plugins/skill-intake/scripts/smoke_notion_publish.py",
    # PR #34: mf-kessai-invoice-check 初回投入。check_invoice_gaps.py は
    # tests/test_check_invoice_gaps.py から `import check_invoice_gaps` される module の
    # ため §4.3 例外 (ハイフン不可)。verb 'check' の許可動詞化 (diff/extract 等) と
    # verify/build の kebab 化は SKILL.md/prompts/README/manifest/test 参照と同時に
    # 実施する後続 Change Governance PR まで PENDING。
    "plugins/mf-kessai-invoice-check/skills/run-mf-invoice-check/scripts/check_invoice_gaps.py",
    # reconcile_invoices.py: 月次1コマンド orchestrator。tests/test_reconcile_invoices.py から
    # `import reconcile_invoices` される module のため §4.3 例外 (ハイフン不可)。許可動詞化
    # (reconcile→diff/build 等) は SKILL.md/README/manifest/test 参照と同時に実施する後続
    # Change Governance PR まで PENDING (check_invoice_gaps.py と同じ扱い)。
    "plugins/mf-kessai-invoice-check/scripts/reconcile_invoices.py",
    # build_reconcile_dbs.py: reconcile DB1/DB2 冪等 find-or-create ビルダー。
    # tests/test_build_reconcile_dbs.py から `import build_reconcile_dbs` される module のため
    # §4.3 例外 (ハイフン不可)。許可動詞化は reconcile_invoices.py と同時の後続 Change Governance PR まで PENDING。
    "plugins/mf-kessai-invoice-check/scripts/build_reconcile_dbs.py",
    # backfill_sheet_contract_dates.py / clear_unsupported_end_dates.py: 請求確認シート契約日の
    # 保守スクリプト (独立パス・dry-run 既定)。tests/test_backfill_sheet_contract_dates.py /
    # test_clear_unsupported_end_dates.py から `import backfill_sheet_contract_dates` /
    # `import clear_unsupported_end_dates` される module のため §4.3 例外 (ハイフン不可)。
    # 許可動詞化は reconcile_invoices.py と同時の後続 Change Governance PR まで PENDING。
    "plugins/mf-kessai-invoice-check/scripts/backfill_sheet_contract_dates.py",
    "plugins/mf-kessai-invoice-check/scripts/clear_unsupported_end_dates.py",
    # mfk_period_report.py (C05・前月↔今月分類エンジン) / notion_report_sink.py (C06・月次 DB sink):
    # run-mf-invoice-report が使う正本スクリプト。tests/test_mfk_period_report.py が
    # `import mfk_period_report`、tests/test_notion_report_sink.py が `import notion_report_sink`
    # する module のため §4.3 例外 (ハイフン不可)。mfk_period_report.py は guard-mfk-no-reinvent.py の
    # SANCTIONED basename でもあり、notion_report_sink.py は build_notion_db を再利用する。許可動詞化は
    # reconcile_invoices.py と同時の後続 Change Governance PR まで PENDING。
    "plugins/mf-kessai-invoice-check/scripts/mfk_period_report.py",
    "plugins/mf-kessai-invoice-check/scripts/notion_report_sink.py",
    # 取得忠実性 (fidelity) 改善 で追加。mfk_actuals.py (C05・MF実績 issued/実発行額 SSOT) は
    # mfk_period_report.py / lib/mfk_reconcile.py / tests/test_mfk_actuals.py が `import mfk_actuals`、
    # mfk_fetch_audit.py (C06・fetch fidelity 監査器) は tests/test_mfk_fetch_audit.py が
    # `import mfk_fetch_audit` する module のため §4.3 例外 (ハイフン不可)。許可動詞化は
    # reconcile_invoices.py と同時の後続 Change Governance PR まで PENDING (既存 mfk_* と同じ扱い)。
    "plugins/mf-kessai-invoice-check/scripts/mfk_actuals.py",
    "plugins/mf-kessai-invoice-check/scripts/mfk_fetch_audit.py",
    # 照合層 根本原因 根治 (matching rootcause) で追加。mfk_verdict_export.py (C05・R1 決定論 producer=
    # reconcile 全 row+orphans を carrier 込みで無損失直列化し LLM 手組みの curr=None を根治) は
    # tests/test_mfk_verdict_export.py / tests/test_mfk_matching_rootcause_golden.py が
    # `import mfk_verdict_export`、mfk_collect_status.py (C01・発行後 status 収集 SSOT) は
    # scripts/reconcile_invoices.py / scripts/mfk_fetch_audit.py / tests が `import mfk_collect_status`、
    # mfk_customer_id_resolve.py (顧客 ID 解決) は lib/notion_sheet_writeback.py / lib/sheet_to_master.py /
    # tests が `import mfk_customer_id_resolve` する module のため §4.3 例外 (ハイフン不可)。
    # mfk_verdict_export.py / mfk_collect_status.py は guard-mfk-no-reinvent.py の SANCTIONED basename
    # でもある。許可動詞化は reconcile_invoices.py と同時の後続 Change Governance PR まで PENDING (既存 mfk_* と同じ扱い)。
    "plugins/mf-kessai-invoice-check/scripts/mfk_verdict_export.py",
    "plugins/mf-kessai-invoice-check/scripts/mfk_collect_status.py",
    "plugins/mf-kessai-invoice-check/scripts/mfk_customer_id_resolve.py",
    # 請求書確認シート 月次アーカイブ&ロールオーバー (R5-archive・C07) で追加。
    # mfk_sheet_archive.py (C07 CLI) は tests/test_notion_sheet_archive.py が `import mfk_sheet_archive`
    # する module のため §4.3 例外 (ハイフン不可)。engine 本体 lib/notion_sheet_archive.py も同 test が
    # `import notion_sheet_archive` するが lib/ 配下は本 lint の scripts 走査対象外。許可動詞化は
    # reconcile_invoices.py と同時の後続 Change Governance PR まで PENDING (既存 mfk_* と同じ扱い)。
    "plugins/mf-kessai-invoice-check/scripts/mfk_sheet_archive.py",
    "plugins/mf-kessai-invoice-check/skills/run-mf-invoice-db-setup/scripts/verify_db_schema.py",
    "plugins/mf-kessai-invoice-check/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py",
    # run-mf-initial-month-enrich (取得担当向け任意スキル): MFクラウド請求書 OAuth エンリッチの
    # 実体スクリプト群。相互 import する module (api→oauth, enrich→api/oauth) で Python import 上
    # underscore 必須のため §4.3 例外。許可動詞化は SKILL.md/README 参照と同時の後続 PR まで PENDING。
    "plugins/mf-kessai-invoice-check/skills/run-mf-initial-month-enrich/scripts/mf_invoice_enrich.py",
    "plugins/mf-kessai-invoice-check/skills/run-mf-initial-month-enrich/scripts/mf_invoice_oauth.py",
    "plugins/mf-kessai-invoice-check/skills/run-mf-initial-month-enrich/scripts/mf_invoice_api.py",
    "plugins/mf-kessai-invoice-check/skills/run-mf-initial-month-enrich/scripts/mf_invoice_csv_match.py",
    # mf_invoice_names.py: enrich/csv_match が `import mf_invoice_names` する名寄せ正規化の
    # 共有 module (SSOT)。同上の §4.3 例外 (Python import 上 underscore 必須)。
    "plugins/mf-kessai-invoice-check/skills/run-mf-initial-month-enrich/scripts/mf_invoice_names.py",
    # notion-gmail-send 初回投入: §4.3 (kebab-case) は満たすが verb が ALLOWED_VERBS 外。
    # send (一斉送信実行) / verify (送信前再検査) / setup (送信ログ DB 冪等構築) は許可動詞に
    # 対応語が無いため、許可動詞化 (allowed-list 拡張 or build/validate 系へのリネーム) は
    # SKILL.md/prompts/agent/README/test 参照と同時に実施する後続 Change Governance PR まで
    # PENDING。emit-observable / notion-submit-improvement と同種の「新 verb pending」扱い。
    "plugins/notion-gmail-send/skills/run-notion-gmail-send/scripts/send-campaign.py",
    "plugins/notion-gmail-send/skills/run-notion-gmail-send/scripts/verify-plan.py",
    "plugins/notion-gmail-send/skills/run-notion-gmail-sendlog-setup/scripts/setup-send-log-db.py",
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
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/derive-task-graph.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/compute-ready-set.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/accept-discovered-task.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/apply-handoff-notes.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-plan-ledger.py",
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/migrate-plan-layout.py",
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
    "plugins/harness-creator/scripts/dispatch-ready-set.py",
    "plugins/harness-creator/scripts/sync-task-state.py",
    "plugins/harness-creator/scripts/inject-task-inputs.py",
    "plugins/harness-creator/scripts/emit-discovered-task.py",
    "plugins/harness-creator/scripts/summarize-task-progress.py",
    "plugins/harness-creator/scripts/manage-build-lease.py",
    "plugins/harness-creator/scripts/record-task-graph-knowledge.py",
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
    # specfm.py: check-spec-*.py / render-spec-skeleton.py / tests が `import specfm` する
    # kind→必須キーの共有 SSOT module。Python import 上ハイフン不可のため <verb>-<target> 形に
    # できず underscore も持たない単一トークン module 名で固定する (§4.3 恒久例外・
    # feedback_contract_ssot.py / discover_repo_tests.py と同列)。
    "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/specfm.py",
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
    # は許可動詞に対応語が無い。youtube_provider.py は run-youtube-sync-oneshot.py / tests が
    # `import youtube_provider` する provider I/F 共有 module のためハイフン不可 (§4.3 例外・
    # company-master notion_config.py と同列の underscore 許容)。許可動詞化は SKILL.md
    # (script_refs)/workflow-manifest/tests/EVALS.json 参照を原子的に更新する後続
    # Change Governance 一括改名 PR まで PENDING。
    "plugins/ubm-goal-setting/scripts/index-harness-artifact-graph.py",
    "plugins/ubm-goal-setting/scripts/consult-harness-artifact-graph.py",
    "plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py",
    "plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/check-youtube-backfill-completeness.py",
    "plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/youtube_provider.py",
}

VALID_NAME = re.compile(r"^([a-z]+)-[a-z0-9-]+\.py$")

SCAN_ROOTS = ["scripts", "plugins"]
SKIP_PARTS = {"_lib", "__pycache__", "node_modules", ".git"}


def find_scripts(roots):
    for root in roots:
        rp = pathlib.Path(root)
        if not rp.exists():
            continue
        for p in rp.rglob("*.py"):
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            if "/scripts/" in str(p) or str(p.parent).endswith("scripts"):
                yield p
            elif rp.name == "scripts":
                yield p


def classify(path: pathlib.Path):
    name = path.name
    posix = path.as_posix()
    if name in BANNED_NAMES:
        return ("VIOLATION", f"banned name: {name}")
    if path.parent.name == "adapters":
        return ("EXCEPTION", "Hexagonal adapter (§4.6)")
    for pat, reason in EXCEPTION_PATTERNS:
        if pat.match(name):
            return ("EXCEPTION", reason)
    if posix in PENDING_RENAME_PATHS:
        return ("PENDING_RENAME", "legacy path scheduled for rename (33章 Change Governance)")
    for pat in PENDING_RENAME_PATTERNS:
        if pat.match(name):
            return ("PENDING_RENAME", "hook-* prefix scheduled for rename (33章 Change Governance)")
    m = VALID_NAME.match(name)
    if not m:
        if "_" in name:
            return ("VIOLATION", "underscore not allowed (§4.3)")
        return ("VIOLATION", "does not match <verb>-<target>[-<scope>].py")
    verb = m.group(1)
    if verb not in ALLOWED_VERBS:
        return ("VIOLATION", f"verb '{verb}' not in allowed list {sorted(ALLOWED_VERBS)}")
    return ("OK", None)


def main(argv):
    report_mode = "--report" in argv
    paths = [a for a in argv[1:] if not a.startswith("--")]
    scripts = list(find_scripts(paths or SCAN_ROOTS))
    results = {"OK": [], "EXCEPTION": [], "PENDING_RENAME": [], "VIOLATION": []}
    for p in scripts:
        status, reason = classify(p)
        results[status].append({"path": str(p), "reason": reason})
    if report_mode:
        print(json.dumps({
            "summary": {k: len(v) for k, v in results.items()},
            "violations": results["VIOLATION"],
            "pending_rename": results["PENDING_RENAME"],
        }, indent=2, ensure_ascii=False))
    else:
        for item in results["VIOLATION"]:
            print(f"VIOLATION {item['path']}: {item['reason']}", file=sys.stderr)
        for item in results["PENDING_RENAME"]:
            print(f"PENDING  {item['path']}: {item['reason']}", file=sys.stderr)
        print(
            f"summary: OK={len(results['OK'])} "
            f"EXCEPTION={len(results['EXCEPTION'])} "
            f"PENDING={len(results['PENDING_RENAME'])} "
            f"VIOLATION={len(results['VIOLATION'])}"
        )
    return 1 if results["VIOLATION"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
