---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
P01 の要件を「改善デルタが要する機能クラスタ」から 5 種の component_kind へ写像し、C01〜C06 の 6 実体を `component-inventory.json` へ確定する。各 component の build_target・依存 DAG・quality_gates を確定し、plugin envelope (`.claude-plugin/plugin.json`) の draft を設計する owner フェーズ。

## 背景
既存 reconcile の上に前月↔今月比較という新次元を足す改善であり、5 種を対称に 1 つずつ埋めるのでなく、機能クラスタ (収集/描画オーケストレーション・分類・二段確認・手動起動・再発明遮断・単一恒久 DB sink) を先に列挙してから component_kind へ写像する (Goodhart 回避)。本改善では C05 (`mfk_period_report.py`) を既存 per-月 verdict を入力に取る薄い差分エンジンとして新設し、C06 (`notion_report_sink.py`) を **指定見出しに紐づく単一恒久レポート DB を更新する sink** として独立させる。C06 は `report_toggle_block` が指す指定見出しを起点に、トグル配下 DB → プレーン見出し2直下 DB → ページ直下既存 DB → 見出しの下(ページ直下)へ新規作成、の順で既存 DB を確認し、存在すればそれを更新する。Notion API は database を block_id 親で作成できないが、既存 DB の更新(行 upsert・列 PATCH)は可能なため、ユーザーが UI でトグル内/見出し下に置いた DB をそのまま更新できる。同月内の再実行は単一 DB 内の stored key (対象月,取引先名,商品名) で同じ行を再利用し、別月行は対象月列で共存する。C01 (report skill) はオーケストレーション (収集→分類呼出→二段確認→単一 DB への冪等描画) に徹する境界を設計する。C04 (hook) は新規 build ではなく既存 `guard-mfk-no-reinvent.py` への in-place 拡張 (SANCTIONED_BASENAMES に `mfk_period_report.py` 追加等) として設計し、C05 が新規 classify 系関数を持つため既存 guard に遮断されないよう `C05.depends_on=[C04]` で拡張が先行する順序を DAG へ焼く。

## 前提条件
- P01 の `goal-spec.json` が確定している。
- 5 種の component_kind の写像規約 (`references/component-domain.md`) と envelope 物理契約が参照できる。
- 既存 `lib/mfk_reconcile.py` の per-月 verdict・`lib/notion_reconcile_sink.py` の非破壊 upsert パターン・既存稼働 hook `guard-mfk-no-reinvent.py` (203 行・R1-R3/allowlist) を土台に再利用する方針が共有されている。

## ドメイン知識
正規化原則 (build_target/depends_on は inventory のみが保持) と kind 写像の判定核は index `## ドメイン知識` を参照。本フェーズ固有の差分: `placement_scope=plugin-root` で C05/C06 を `plugins/mf-kessai-invoice-check/scripts/` へ hoist する (独立単体テスト性の確保・既存 `scripts/reconcile_invoices.py` と同じ plugin-root 慣習)。C05 は既存 reconcile スキルとの分類共有を主張しない (reconcile 側に C05 消費 route は無い・over-claim を撤回)。C04 は `build_mode=extend-existing` として既存実装を保全しつつ SANCTIONED/`_REINVENT_DEF_RE`/`_DOMAIN_RE` を拡張する設計判断とする。C06 は親ページ ID/指定見出しブロック ID を plan 成果物へ焼かず論理キー (`report_parent_page`=探索/新規作成先ページ / `report_toggle_block`=出力先指定見出し) のみ宣言し、実行時 config(`mf-kessai-config.default.json` 配布既定 + `.notion-config.json`/`.mf-kessai-config.json` 上書き)が具体値を供給する two-layer 分離を設計する。配置は Design D の単一恒久 DB 方式で、`report_toggle_block` はトグル見出しでもプレーン見出し2でも受ける。レポート列は取引先名/対象月/漏れチェック/商品名/先月の金額/今月の金額/先月と今月の比較/コメントの 8 列とし、C06 が単一 DB へ書く際に対象月列で月を区別し先月分と今月分の金額を並置する。

**2026-07-10 実運用フィードバック設計差分 (C05/C06 の後段 /capability-build へ委譲・記録層と実行層を整合)**:
- **C06 出力先解決 (要件2)**: `resolve_report_db` に **step0 = 明示 DB pin (config `report_database_id`・ビュー/DB URL 許容)** を第一級として設計し、未設定時のみ構造同定 (in-block→under-heading→page) へ fallback する。明示 pin なし かつ 既存 report DB 未発見時は `page-created` (phantom DB) を作らず警告停止し、新規作成は明示 opt-in 時のみ許す設計とする (構造同定ズレで別 DB へ書き込む『出力先が指定先でない』の根治)。
- **C05 分類の設計判断 (要件1/3/4)**: (要件1) `STATE_CONTINUED` (今月あり×前月あり) は権威ある月契約正常として必ず `GAP_OK` で emit し、`period_diff`『継続発行』を正規トークンで出し C06 の `_STRUCTURAL_NORMAL_MARKERS` と byte 一致させる SSOT (C05 定数=正本) を設計する。(要件3) `_orphan_rows` (MF実績あり×シート契約なし=要マスタ登録) は `gap_check` を `GAP_ACTION`→`GAP_OK` へ反転する設計とし、コメントに名寄せ恒久化指示を保持する。(要件4) 4 状態分類はユーザー提供フローチャートを SSOT とし、両月なしの `_classify_both_absent` (月払い×アクティブ×2ヶ月以上未発行) を安全網として surface する設計を維持する。

## 成果物
- `component-inventory.json` (build 軸の唯一 SSOT・全 6 component C01〜C06)。
- `envelope-draft/plugin.json` (manifest draft)。

## スコープ外
- 設計の合否判定 (P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出 (P04 へ委譲)。
- 実体の生成 (P05・実 `plugins/` へは書かない)。

## 完了チェックリスト
- [ ] 全 6 component (C01〜C06) が build_target 非空・builder/build_kind 整合・depends_on 非循環 (C05←C04, C01←[C05,C06], C02/C03←C01) で inventory に載っている。
- [ ] considered_component_kinds が 5 種全列挙され、plugin_level_surfaces の採否が明示されている。
- [ ] `envelope-draft/plugin.json` に manifest draft (entry_points / hooks 配線(不変) / distribution) が設計され、C04 の `build_mode=extend-existing` (既存 hooks 配線を変更しない) が明示されている。

## 参照情報
- `references/component-domain.md` / `references/phase-lifecycle.md`。
- 対象 component C01〜C06 (`component-inventory.json`)。後続 P03 (この設計を design-gate で審査する)。
