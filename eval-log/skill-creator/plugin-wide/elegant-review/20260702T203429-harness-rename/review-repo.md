# elegant-review レポート — plugin 改名 skill-creator → harness-creator

- run-id: `20260702T203429-harness-rename` / scope_mode: repo / 実施: 2026-07-02
- 対象: plugins/skill-creator の harness-creator への改名+repo 全域の依存追従
- 意味論境界 (ユーザー確定): 単体スキル生成=skill 表現維持 / ハーネス総体構築=harness 表現。ファイル名・ディレクトリ名・本文・項目内容の全レベル適用
- 4 条件: **C1 矛盾なし PASS / C2 漏れなし PASS / C3 整合性あり PASS / C4 依存関係整合 PASS** (findings.json / verdict.json)
- 30 思考法: used 30 / skipped 0 (validate-paradigm-coverage OK)
- proposer≠approver: 独立 approver の APPROVE は approver-verdict.json 参照

## 実施内容 (Phase 3)

1. **W1 git mv**: plugin dir / spec-reflection.md / creator-kit-ci.yml→harness-creator-kit-ci.yml / installers/creator-kit→harness-creator-kit / settings example / テスト 39 本 (計 377 rename)
2. **W2 固有名機械置換**: 3 変形+複合形を 374 ファイル (凍結層除外・symlink 除外・台帳 w2-replace-ledger.json)。追加で大文字 env `SKILL_CREATOR_*`→`HARNESS_CREATOR_*`・camel・空白形 16 ファイル
3. **W3 機械層連鎖セット**: NEVER_DISTRIBUTE / SELF_DOGFOODING_PLUGIN (正本+vendored byte 一致) / VENDORED_PAIRS / CI 42 箇所+Makefile / settings.json / upstream-pins 6 pin (sha 再計算+B1 行再監査対応) / criteria_roster / coverage 台帳
4. **W4 symlink**: 量産先 14 plugin repoint+.claude 41 本再生成 (dangling 0)
5. **W5 新規ガード**: dir↔定数 parity test 2 本 / NEVER_DISTRIBUTE 実在 test / _JUDGMENT_LITERAL_RES の SSOT 導出化 / **lint-legacy-plugin-name 新設+3 経路配線** (実効性は自己捕捉 4 件で実証)
6. **W6/W7 意味論+定義**: 概念判定台帳 20 判定 / glossary ハーネスエントリ / README 新設 / description 書換 / CONVENTIONS 用語規約 / spec 関係注記 / CHANGELOG 1.2.0 (機械可読対応表) / tombstone / retarget 規約+schema 拡張 / plugin-rename-checklist.md 恒久化
7. **W8 verdict**: byte 不変 3 skill×2 retarget (retargeted_from 監査キー) / 27 skill×2 を独立 SubAgent 7 体で genuine 再生成 (全 PASS・FAIL 0)

## 完了検証 battery (機械層 8+意味論層 2)

| # | 項目 | 結果 |
|---|---|---|
| 1 | 旧名 grep 残存=allowlist 一致 | PASS (lint-legacy-plugin-name OK: 能動層 0 件) |
| 2 | make lint 全通過 | PASS (exit 0) |
| 3 | 中央 pytest 直接実行 | PASS (6210 passed / coverage 台帳追従後) |
| 4 | CI 同一 cwd 再現 (plugin-cwd walk) | PASS (planner 371+13 / mf 612 / gmail 198 / gov-lint 6) |
| 5 | build-claude-symlinks --check | PASS (conflict 0) |
| 6 | plugin 単独コピー hook smoke | PASS (check-review-trigger 他 3 hook exit 0) |
| 7 | is_stop_block_exempt("harness-creator")==True | PASS (旧名は False) |
| 8 | git archive clean-checkout | commit 後に実施 (コミット時) |
| 9 | 概念判定インベントリ | PASS (concept-judgment-ledger.json 20 判定+over-rename ガード 33 skill 同名実在) |
| 10 | proposer≠approver 独立レビュー | approver-verdict.json 参照 |

補足: `validate-harness-coverage` の総合 FAIL は改名前 main と同一の既知 ratchet 状態 (CI WARN 非ブロック配線) であり改名起因ではない。

## 主要な設計判断 (詳細: phase3-plan.md / concept-judgment-ledger.json)

- DEC-1: eval-log 履歴=凍結+tombstone、runtime 参照層 (content-review verdict / coverage 台帳) のみ新名追従
- DEC-3: 境界例 rubric「操作/生成対象の単位で判定。部品の集合名は harness 側」
- DEC-7: 恒久 denylist lint (一時スクリプト案より再流入防御を優先)
- ADR コメント「skill を量産する」は量産対象=単体 skill のため維持 (pin bump 二重発生の回避と両立)
