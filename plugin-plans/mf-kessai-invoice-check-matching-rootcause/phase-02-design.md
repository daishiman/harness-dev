---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
7 component を component_kind (script×5 / sub-agent×1 / skill×1) へ写像し、依存 DAG (C01/C02/C04 は依存なし・C03 は C04 依存・C05 は C01 依存・C06 は C04/C05 依存・C07 は C03/C04/C05/C06 依存、build順 C01→C02→C04→C03→C05→C06→C07) を確定する。この DAG は component-inventory.json depends_on / handoff routes[].depends_on を唯一の正本とし、本ファイル内の記述はそれと一致させる。各 component の build_target・integration_targets・required_file_edits を確定する。

## 背景
P01 で固定した確定6要因(C1 収集/C2 R1決定論/C3 NEW分類/C4 取消継続/C5 代理店collapse/C6 顧客ID)根治要件を、build 可能な実体へ落とす設計フェーズ。既存 SSOT (lib/mfk_reconcile.py の normalize/reconcile・scripts/mfk_actuals.py の resolve_actual・scripts/mfk_period_report.py の compare_periods/classify) の再発明禁止制約下で、script (C01 収集是正/C02 顧客ID解決/C03 collapse保全/C04 分類是正/C05 R1決定論producer) + 検証 sub-agent (C06) + 配線 skill (C07) へ分解する。plugin_level_surfaces のうち manifest/references_config_assets のみ必須とし、composition/harness_eval/schemas/vendor/mcp_app_connector/notion_config は既存温存を理由に不要とする。

## 前提条件
- P01 の要件が確定している。
- 5 種 component_kind の写像規約と、既存 hooks (guard-mfk-readonly.py/guard-mfk-no-reinvent.py) の allowlist 拡張契約が参照できる。
- 各 script の integration_targets/required_file_edits が現行 component の実ファイル・関数単位 (C01=scripts/reconcile_invoices.py collect_mf、C04=scripts/mfk_period_report.py compare_periods/classify_period_transition/STATE_NEW、C03=scripts/notion_report_sink.py _prefer_action、C05=scripts/mfk_verdict_export.py 新規、C02=scripts/mfk_customer_id_resolve.py 新規、R1-collect.md 配線) で特定済み。正確な行番号の正本は handoff-run-plugin-dev-plan.json の各 route.build_args.required_file_edits とする。

## ドメイン知識
- component 依存 DAG: C01 (収集billing-status是正, dep なし)。C02 (MF顧客ID解決, dep なし)。C04 (分類是正=NEW/年契約/取消継続/代理店突合, dep なし) → C03 (collapse保全, dep C04)。C05 (R1-collect決定論producer=構造的主因, dep C01)。C06 (検証sub-agent, dep C04,C05)。C07 (skill配線, dep C03,C04,C05,C06)。
- placement_scope=plugin-root: C01-C05 は共有 script として plugin 直下 scripts/ へ hoist し、単一 skill 配下への退化を避ける。
- guard-mfk-no-reinvent.py の sanctioned basename 登録が C01-C05 の required_file_edits 共通項目 (関数名は _REINVENT_DEF_RE 語幹 classify/reconcile/detect_orphans/build_mf_index/compare/period_diff と衝突しない語を選ぶ)。
- evidence(DB2 matched_amount)は据え置き・actual/carrier のみ additive 拡張 (find_mf_match の evidence を書き換えない)。

## 成果物
- component_kind 写像 (script×5/sub-agent×1/skill×1) の確定。
- 依存 DAG (非循環) の確定。
- 各 component の build_target/integration_targets/required_file_edits の確定 (component-inventory.json 記載済み)。

## スコープ外
- 設計の合否判定 (P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出 (P04 へ委譲)。
- 実体の生成 (P05・実 plugins/ へは書かない)。

## 既存部分build の reconcile 方針 (build 着手前に確定・GAP-PARTIAL-BUILD-RECONCILE)
working tree には旧・名寄せ主因説の時点で着手された部分build が残存する。build は greenfield でなくこれを吸収/置換/撤去する前提で設計する:
- `lib/sheet_to_master.py` の MF顧客ID導出 (`_mf_customer_id_for` 等) は C02 (mfk_customer_id_resolve.py) が正式 SSOT として吸収・置換する (二重実装/orphan化を防ぐ)。
- `lib/mfk_reconcile.py` の `_COMPANY_ALIAS_GROUPS` (2nd Community/細野/paws の個社会社名ハードコード) は撤回済み仮説 (RETRACT-1) の対症療法であり、**C02 の一般解 (MF顧客ID結合) へ吸収し撤去する** (C14・会社名リテラル0件)。
- 主因 C05 (mfk_verdict_export.py) は未着手であり、build の最優先で新規実装する。

## 完了チェックリスト
- [ ] 全 7 component が build_target 非空・builder/build_kind 整合・depends_on 非循環で inventory に載っている。
- [ ] considered_component_kinds が 5 種全検討され、plugin_level_surfaces の採否 (必須2: manifest/references_config_assets、不要5) が明示されている。
- [ ] C01-C05 の required_file_edits が現行 component の実ファイル・関数 (reconcile_invoices.py collect_mf / mfk_period_report.py compare_periods・classify・STATE_NEW / notion_report_sink.py _prefer_action / mfk_verdict_export.py 新規 / mfk_customer_id_resolve.py 新規 / R1-collect.md 配線) で特定され、正確な行番号は handoff routes[].build_args.required_file_edits と一致している (撤回済み _boundary_customers/find_mf_match/detect_orphans の行番号を残さない)。
- [ ] 既存部分build の reconcile 方針が確定している (下記スコープ外の注記参照)。

## 参照情報
- references/component-domain.md・references/phase-lifecycle.md。
- component-inventory.json (C01-C07全件)。
- 実 plugin hooks/guard-mfk-no-reinvent.py・hooks/guard-mfk-readonly.py。
- 後続 P03 (design-review)。
