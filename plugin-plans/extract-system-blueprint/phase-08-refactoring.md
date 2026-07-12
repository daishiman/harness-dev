---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 完了
gate_type: tdd-refactor
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P08 — refactoring (リファクタリング)

## 目的
テストが緑の状態を保ったまま、SSOT 重複を排除する (lint-ssot-duplication・上書き一本化)。本プラグインでは共有 script (fetch-snapshot/mermaid-validate/doc-emit/authz-classify) が run-extract-blueprint・4 sub-agent・assign-blueprint-fidelity-evaluator・pre-fetch-authz-guard から二重定義されない単一実体であることを保証する改善フェーズ。特に URL認可分類述語は authz-classify.py (C12) を単一SSOTとし、pre-fetch-authz-guard (C08) と fetch-snapshot (C09) が同一モジュールを import することを機械検査する。

## 背景
共有ロジック (URL認可分類・Mermaid構文検証・md+json整形) が複数 builder 境界 (skill/sub-agent/hook) から二重定義されると SSOT が崩れ、片方だけ修正した際にドリフトする (特に C08 hook と C09 script の認可分類述語が乖離すると C5 の fail-closed 保証が崩れる)。この認可分類は authz-classify.py (C12) の単一SSOT関数へ切り出し済みで、C08 と C09 が共に C12 を import することで乖離を構造的に封じる。テスト緑を保ったまま重複を上書きで一本化し、第二消費者は import/参照で共有する tdd-refactor。

## 前提条件
- P07 の受入判定が全 PASS。
- P06 のテストが緑。
- lint-ssot-duplication が利用可能で、共有 script C09/C10/C11/C12 が plugin-root へ hoist 済み。

## ドメイン知識
- 上書き一本化: 重複を発見したら両方残さず一方を正本に確定し、他方は削除して import/参照へ置換する (共存縮退は禁止)。
- 第二消費者 = 正本を複製せず import/参照で共有する側 (C09/C10/C11/C12 は plugin-root 実体が正本・C08 と C09 は C12 を import する第二消費者)。
- tdd-refactor の不変条件: リファクタリング中もテスト緑を維持する (赤に戻ったら即巻き戻し)。

## 成果物
- SSOT 重複が 0 件になった状態 (共有 script が単一実体)。

## スコープ外
- 新機能の追加 (リファクタリングは挙動不変)。
- 受入基準・criteria の変更 (P04/P07 の責務)。
- plugin 外 (他 plugin・repo 共有層) への hoist (本 plan のスコープは plugin 内)。

## 完了チェックリスト
- [x] lint-ssot-duplication が exit0 で、共有ロジック (C09/C10/C11/C12) が一本化されている。
- [x] C08 hook と C09 script が authz-classify.py (C12) の同一モジュールを import している (機械検査=『C08 と C09 が同一モジュールを import』・認可分類述語の二重実装0)。C15 browser-render も C12 発行の同一 AuthzEvidence/budget(decide())を import 共有し、認可・低負荷レバーの二重定義が0である(screenshot 専用 budget は発行しない)。
- [x] C12へのdepends_onはP02/P05で既に成立しており、本phaseは依存導入を先送りせず重複実装の除去だけを行う。
- [x] WebFetchをレンダリング済みブラウザ(browser-render)として扱う重複経路、欠測をinference化するfallback、外部サービス(MCP/Notion)へegressする経路が0件。
- [x] リファクタリングによってテストが赤に戻っていない (tdd-refactor 維持)。

### 受入例
- Authz/budget述語、visual field定義、expert roster、browser-render認可共有の重複実装がなく、各SSOTから参照される。

### 事前解決済み判断
- C12=budget/authz、schema=visual fields、inventory=expert promptの各SSOTを統合しない。

## 参照情報
- lint-ssot-duplication (SSOT 重複検査)。
- 共有 component C09 (fetch-snapshot) / C10 (mermaid-validate) / C11 (doc-emit) / C12 (authz-classify)。
- 後続 P09 (quality-assurance)。
