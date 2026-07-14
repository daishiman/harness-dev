---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P08 — refactoring (改善)

## 目的
後段L4 buildでP07のACを維持したまま重複・歪みを解消するためのrefactoring契約を確定する。本L3 planでは実装変更を行わず、共有script・routing policy・schema authorityのSSOT境界を宣言する。

## 背景
複数 skill から利用される共有ロジックがコピペで散在すると、修正時に一部だけ更新され drift する。C11 (スキーマ検証)・C12 (GitHub連携)・C13 (HTML生成) は複数 skill からの多消費構造、C16 (ready-set/並列バッチ算出) は C15 単独からの決定論ゲート独立性による hoist であるため (consumer 一覧の正本は `component-inventory.json` の depends_on 逆引き・散文で二重維持しない)、plugin-root への単一実体化 (`ssot_dedup` lint 対象) を維持できているかを本フェーズで再点検する。criteria/AC を変更せずに内部構造のみ改善する (tdd-refactor)。

## 前提条件
- P07のAC matrixが確定している。
- 共有 script の消費元一覧は `component-inventory.json` の `depends_on` 逆引きが SSOT であり、本フェーズはそれを参照するのみで散文へ複製しない (drift 防止)。
- `lint-ssot-duplication` の検査観点を参照できる。

## ドメイン知識
- SSOT 重複 = 同一ロジックが複数箇所にコピーされ、修正時に一部のみ反映され drift するリスク (`lint-ssot-duplication` が機械検出)。
- placement_scope=plugin-root は「≥2 skill 共有」「独立検証要否」「280 行超」のいずれかを根拠に昇格する (根拠なき昇格は不要な水増し)。
- リファクタリングは外部観測可能な振る舞い (criteria/AC) を変えない (振る舞いが変わる場合は P04/P07 への差し戻し)。

## 成果物
- 後段buildが適用する重複排除・命名一貫性・依存整理のrefactoring checklist。

## スコープ外
- criteria/AC 自体の変更 (振る舞いを変える場合は P04/P07 へ差し戻す)。
- 新規機能の追加 (本 plan のスコープ外・スコープ変更は goal-spec 側で扱う)。
- QA 全域ゲート実行 (P09)。

## 完了チェックリスト
- [ ] C11/C12/C13/C16をplugin-root単一実体とする契約がある。
- [ ] routing policyとfrontmatter authorityをC01/C02/C11で二重定義しないSSOT規則がある。
- [ ] 後段buildが`lint-ssot-duplication`とP07回帰を実走することが明記されている。

### 受入例
- 満たす例: `plugins/dev-graph/scripts/validate-graph-schema.py` が単一実体として存在し、C01/C02/C03/C05/C14/C18 の各 skill 配下にスキーマ検証ロジックの再コピーが存在しない。
- 満たさない例: `run-dev-graph-sync/` skill 配下に `gh-bridge.py` と同等の GitHub 連携ロジックが独自実装されている → SSOT 重複として `lint-ssot-duplication` が検出する。
- 満たさない例: リファクタ後に C03 の OUT2 criterion (id+updated_at タイブレーク) が FAIL に変わる → 振る舞い変更とみなし P04/P07 へ差し戻し。

### 事前解決済み判断
- 共有 script の consumer 一覧は `component-inventory.json` の depends_on 逆引きを唯一の SSOT とし、本フェーズ・他フェーズの散文では複製しない。
- plugin-root hoist の根拠は「≥2 skill 共有」「独立検証要否」「280 行超」のいずれかに固定し、本フェーズで新たな昇格根拠を発明しない。
- リファクタリングは外部観測可能な振る舞い (criteria/AC) を変えない不変条件を維持する。

## 参照情報
- `component-inventory.json` (C11/C12/C13/C16 の consumers)。
- `lint-ssot-duplication` (SSOT 重複検査)。
- 後続 P09 (quality-assurance)。
