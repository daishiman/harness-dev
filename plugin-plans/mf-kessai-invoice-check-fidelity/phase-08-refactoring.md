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

# P08 — refactoring (リファクタリング)

## 目的
テストが緑の状態を保ったまま、SSOT 重複を排除する(lint-ssot-duplication・上書き一本化)。本改善では突合ロジック(`mfk_reconcile.normalize/extract_names`等)や fetch fidelity 監査(C06)が第二の実装として再発明・二重定義されていないことを保証する改善フェーズ。

## 背景
突合ロジックの再発明禁止は goal-spec の constraints に明記された最重要制約であり、C05(`mfk_actuals.py`)の新規実装時、および `lib/mfk_reconcile.py` の `find_mf_match`/`classify` が C05 を consume するよう modify する際、既存の正規化・分類エンジンをコピーして別名関数を作るような重複が起きやすい。テスト緑を保ったまま重複を上書きで一本化し、guard-mfk-no-reinvent.py の SANCTIONED allowlist(C12)で機械的にも遮断する。

## 前提条件
- P07 の受入判定が全 PASS。
- P06 のテストが緑。
- lint-ssot-duplication と hooks/guard-mfk-no-reinvent.py が利用可能で、C05/C06 の新規関数シグネチャが allowlist へ登録済み。

## ドメイン知識
- 上書き一本化: 重複を発見したら両方残さず一方を正本に確定し、他方は削除して import/参照へ置換する。
- 第二消費者 = 正本(`mfk_reconcile.normalize`等)を複製せず import/参照で共有する側(C03/C06 は C05 の関数を再利用)。
- tdd-refactor の不変条件: リファクタリング中もテスト緑を維持する(赤に戻ったら即巻き戻し)。

## 成果物
- SSOT 重複が 0 件になった状態(突合ロジック=`lib/mfk_reconcile.py`・実績抽出=C05(`mfk_actuals.py`)がそれぞれ単一実体で保たれている)。

## スコープ外
- 新機能の追加(リファクタリングは挙動不変)。
- 受入基準・criteria の変更(P04/P07 の責務)。
- 既存 `run-mf-invoice-reconcile` 等の温存対象への波及(スコープ外)。

## 完了チェックリスト
- [ ] lint-ssot-duplication が exit0 で、突合ロジック(`lib/mfk_reconcile.py`)と実績抽出(C05)がそれぞれ一本化されている。
- [ ] hooks/guard-mfk-no-reinvent.py の SANCTIONED allowlist へ C05/C06 の新規関数シグネチャが登録され、自作 compare/classify 相当を PreToolUse で機械的に遮断する(C12)。
- [ ] リファクタリングによってテストが赤に戻っていない(tdd-refactor 維持)。

## 参照情報
- lint-ssot-duplication(SSOT 重複検査)。
- 共有 component C05(mfk_actuals.py) / 統合先 lib/mfk_reconcile.py / hooks/guard-mfk-no-reinvent.py。
- 後続 P09(quality-assurance)。
