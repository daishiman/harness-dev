# Phase 12 完了判定ガードチェックリスト

## 用途

Phase 12（ドキュメント整備）の完了判定時に、三点突合・N/Aログ検証・監査結果の3要素をすべて確認し、不完全な完了宣言を防止するための必須チェックリストです。このリストの全項目が ✓ の場合のみ Phase 12 完了を宣言できます。

## 全体フロー

```
Phase 11（手動テスト）完了
        ↓
Phase 12 ドキュメント整備開始
        ↓
SubAgent 分担（監査は並列）+ owner 直列編集 + リーダー検証（Phase 3）
        ↓
このチェックリストを実行 ← あなたはここ
        ↓
全項目 ✓ → Phase 12 完了宣言 → Phase 13 PR作成へ
        ↓（未達項目あり）
        未達項目を修正して再チェック
```

## 前提確認

### P1: Phase 11（手動テスト）が完了していることを確認

- [ ] Phase 11 の手動テスト結果ドキュメントが存在する
- [ ] 手動テスト対象機能がすべて「動作確認済み」と記載されている
- [ ] **重要**: Phase 12 は Phase 11 の後に実行する。順序を入れ替えない

**対応記事**: `.claude/rules/05-task-execution.md` 「Phase 1-13 概要」

---

## 三点突合チェック

### P2: artifacts.json が「completed」である

```bash
# 確認コマンド
cat artifacts.json | jq .phase12.status
```

期待結果: `"completed"`

- [ ] artifacts.json ファイルが存在する
- [ ] `.phase12.status` フィールドが存在する
- [ ] 値が正確に `"completed"` である（"pending", "in-progress" は NG）

**失敗時の対応**: Phase 12 の全タスクが本当に完了しているか再確認。未完了のタスクがあれば完了させてから再度実行。

---

### P3: documentation-changelog.md が「同期状態」である

```bash
# 確認コマンド1: changelog自体の変更確認
git diff --stat -- docs/30-workflows/*/outputs/phase-12/documentation-changelog.md

# 確認コマンド2: SubAgent完了後の仕様書変更実態確認（P51対策）
git diff --stat -- .claude/skills/

# 確認コマンド3: LOGS.md 2ファイル更新確認（P25対策）
git diff --stat -- */LOGS.md

# 確認コマンド4: SKILL.md 変更履歴更新確認
git diff --stat -- .claude/skills/*/SKILL.md

# 確認コマンド5: topic-map.md 再生成確認（P2/P27対策）
git diff --stat -- .claude/skills/*/indexes/topic-map.md
```

期待結果: 変更があれば、その変更がすべて `documentation-changelog.md` に記録されていること

- [ ] `documentation-changelog.md` ファイルが存在する
- [ ] 本タスク実施中に変更した全ファイルが「Task 1: 実装ガイド」セクションに記録されている
- [ ] 本タスク実施中に変更した全ファイルが「Task 2: システム仕様書更新」セクションに記録されている
- [ ] Step 1-A で更新した `.claude/skills/aiworkflow-requirements/*` / `.claude/skills/task-specification-creator/*` の `SKILL.md` / `LOGS.md` が `documentation-changelog.md` に列挙されている
- [ ] `skill-creator` を改善した場合、`.claude/skills/skill-creator/SKILL.md` / `.claude/skills/skill-creator/LOGS.md` と変更した asset / reference も `documentation-changelog.md` に列挙されている
- [ ] **重要**: P4 対策として、各セクションで「全て確認完了」と記載する前に、実際にファイルが更新されたことを確認
- [ ] **P51対策**: SubAgent完了報告の直後に `git diff --stat -- .claude/skills/` で実際の変更ファイル一覧を取得し、changelog記録と突合済み
- [ ] **P25対策**: `git diff --stat -- */LOGS.md` で LOGS.md 2ファイルの変更を確認済み
- [ ] `git diff --stat -- .claude/skills/*/SKILL.md` の結果も changelog 記録と突合済み
- [ ] **P2/P27対策**: `git diff --stat -- .claude/skills/*/indexes/topic-map.md` で topic-map.md の再生成を確認済み
- [ ] `generate-index.js` / `validate-structure.js` / mirror sync / `diff -qr` の実測結果を記録済み
- [ ] 存在しない監査スクリプト名を PASS 根拠にしていない

**失敗時の対応**: `git diff` で未記録の変更がないか確認。あれば `documentation-changelog.md` に追加。SubAgent の自己申告だけでは信頼性が不十分なため、必ず git diff による実態確認を行う。

**参考**: `06-known-pitfalls.md` P4「documentation-changelog への早期「完了」記載」、P51「サブエージェントの documentation-changelog 早期完了記載」

---

### P4: audit コマンド実行結果が「current violations === 0」である

```bash
# 確認コマンド（プロジェクトルートから実行）
cd /Users/dm/dev/dev/個人開発/AIWorkflowOrchestrator && \
  pnpm audit-unassigned-tasks --diff-from HEAD

# 出力例
# {
#   "currentViolations": {
#     "total": 0,
#     "details": []
#   },
#   "baselineViolations": {
#     "total": 2,
#     "details": ["違反A", "違反B"]
#   }
# }
```

期待結果: `"currentViolations": { "total": 0, "details": [] }`

- [ ] audit コマンドが正常に実行完了した
- [ ] JSON 出力パースに失敗していない
- [ ] `currentViolations.total === 0` である
- [ ] `baselineViolations` が存在してもよい（判定に影響しない）

**失敗時の対応**: currentViolations.total > 0 の場合、本タスク中に新規違反が発生した意味。以下を確認：

1. 仕様書の更新が不完全でないか
2. N/A判定の根拠が十分でないか
3. 未タスク（Task 4）の検出漏れがないか

上記すべて確認後、修正して再度 audit コマンド実行。

**参考**: `06-known-pitfalls.md` P3「未タスク管理の3ステップ不完全」

---

## N/Aログ検証チェック

### P5: 全仕様書に「更新」または「N/A」判定が記録されている

```bash
# 確認コマンド（.claude/scripts ディレクトリから実行）
cd .claude/scripts && pnpm vitest run __tests__/na-log-validator.test.ts
```

期待結果:

```
✓ __tests__/na-log-validator.test.ts (12)
Test Files  1 passed (1)
      Tests  12 passed (12)
```

- [ ] `na-log-validator.test.ts` テストが全件 PASS
- [ ] バリデーション結果に FAIL がない
- [ ] 以下の項目を各テスト結果から確認：
  - [ ] specName が空文字列でない
  - [ ] status が "更新" または "N/A" のいずれか
  - [ ] status="N/A" の場合、reason が空でない
  - [ ] status="N/A" の場合、reason がトリム後も空でない（P42対策）

**失敗時の対応**: テスト出力のエラーメッセージを確認し、対応する N/A判定ログを修正。例：

```
AssertionError: Expected false but got true
  at validateNaLogEntry (na-log-validator.ts:15)
  message: "reason field must not be empty for N/A status"
```

→ その仕様書の reason 欄を記入

---

### P6: N/A判定には「理由」と「代替証跡」が記録されている

- [ ] N/A判定された仕様書について、reason フィールド（「理由」）が1文以上記載されている
- [ ] N/A判定された仕様書について、alternativeEvidence フィールド（「代替証跡」）が記載されている
- [ ] 代替証跡として以下のいずれかが記載されている：
  - [ ] `grep -rn 'pattern' path/ で変更0件を確認`
  - [ ] `git diff --stat -- path/ で0ファイル変更`
  - [ ] `diff: +line / -line で確認`
  - [ ] 参照リンク + セクション名

**失敗時の対応**: N/A判定されたすべての仕様書について、reason と alternativeEvidence を記入。テンプレート参照: `phase12-na-judgment-log-template.md`

---

### P7: 担当SubAgent が記録されている

- [ ] 全仕様書の updatedBy フィールドに値が記入されている
- [ ] updatedBy の値が以下のいずれかである：
  - [ ] "SubAgent-A"
  - [ ] "SubAgent-B"
  - [ ] "SubAgent-C"
  - [ ] "SubAgent-D"
  - [ ] "SubAgent-E"
  - [ ] "leader"

**失敗時の対応**: 空の updatedBy フィールドがあれば、適切な SubAgent（またはリーダー）を記入。

---

## 検証コマンド実行結果

### P8: 3つのバリデーターテストがすべて PASS である

```bash
# コマンド1: N/Aログバリデーター
cd .claude/scripts && pnpm vitest run __tests__/na-log-validator.test.ts

# コマンド2: 三点突合バリデーター
cd .claude/scripts && pnpm vitest run __tests__/triple-check-validator.test.ts

# コマンド3: 監査出力パーサー
cd .claude/scripts && pnpm vitest run __tests__/audit-output-parser.test.ts
```

期待結果（3コマンドすべて）:

```
Test Files  1 passed (1)
      Tests  31 passed (31)
```

- [ ] コマンド1（N/Aログ）: 12テスト PASS
- [ ] コマンド2（三点突合）: 7テスト PASS
- [ ] コマンド3（監査出力パーサー）: 12テスト PASS
- [ ] **合計 31テスト PASS**

**失敗時の対応**: テスト出力を確認し、エラーの原因となったデータを修正。多くの場合、N/A判定ログの記入漏れ、artifacts.json のステータス誤り、または documentation-changelog.md の未同期が原因。

---

## 最終判定

### P9: 全チェック項目が ✓ である

このセクションに到達した時点で、以下を確認：

- [ ] P2 三点突合：artifacts = completed ✓
- [ ] P3 三点突合：changelog = synced ✓
- [ ] P4 三点突合：audit currentViolations.total === 0 ✓
- [ ] P5 N/Aログ検証：全件 PASS ✓
- [ ] P6 N/A判定理由記録：reason + alternativeEvidence ✓
- [ ] P7 担当SubAgent記録：updatedBy が全件入力 ✓
- [ ] P8 バリデーターテスト：31/31 PASS ✓

### P10: Phase 12 完了宣言

**全項目 ✓ の場合のみ以下を実行**:

```bash
# 最終確認（Phase 12 完了の最後のステップ）
echo "Phase 12 完了判定: PASS"
echo "実行日時: $(date)"
echo "検証者: {{YOUR_NAME}}"
```

**宣言文**:

> 本チェックリストの全項目を確認し、Phase 12（ドキュメント整備）の完了を宣言します。  
> - 三点突合: PASS（artifacts=completed, changelog=synced, audit current=0）
> - N/Aログ検証: PASS（31テスト全件成功）
> - 監査実行: PASS（currentViolations.total === 0）
>
> 日時: {{YYYY-MM-DD HH:MM:SS}}  
> 検証者: {{YOUR_NAME}}  
> 次フェーズ: Phase 13（PR作成）へ進む

---

## 未達項目がある場合

### 対応フロー

```
チェックリスト実行
    ↓
未達項目あり？
    ├─ YES → 対応セクション（P2-P9）を確認
    │       → 該当する修正を実施
    │       → 修正後、P2 からチェックリスト再実行
    │       → （多くの場合、複数の項目が改善される）
    │
    └─ NO → P10 で Phase 12 完了宣言
```

### 多発する未達パターン

| 未達項目 | 原因 | 対応方法 |
|---------|------|--------|
| P2 (artifacts) | Phase 12 全タスク未完了 | Task 1-4 の完了状況を再確認、未完了タスクを完了 |
| P3 (changelog) | documentation-changelog 未記録 | git diff で変更ファイルを確認、changelog に追加 |
| P4 (audit) | 新規違反が存在 | Task 4（未タスク検出）で違反の根拠を記載 |
| P5 (N/Aログ) | バリデーターテスト FAIL | テストエラーメッセージを確認、該当フィールドを修正 |
| P6 (N/A理由) | reason/alternativeEvidence 未記入 | `phase12-na-judgment-log-template.md` 参照して記入 |
| P7 (updatedBy) | SubAgent 名前誤り | 「SubAgent-A」等、正確な名前を記入 |

---

## 関連ドキュメント

| ドキュメント | 参照する理由 |
|------------|-----------|
| `phase12-na-judgment-log-template.md` | N/A判定ログの記入ルール確認 |
| `phase12-subagent-assignment-template.md` | SubAgent 分担と実行順序確認 |
| `phase12-audit-record-template.md` | 監査結果の記録方法確認 |
| `.claude/rules/05-task-execution.md` | Phase 12 全体的な実行ルール確認 |
| `.claude/rules/06-known-pitfalls.md` | P4, P25, P43 等の既知の落とし穴確認 |
| `.claude/scripts/src/na-log-validator.ts` | バリデーターの実装仕様確認 |
| `.claude/scripts/src/triple-check-validator.ts` | 三点突合の判定ロジック確認 |
| `.claude/scripts/src/audit-output-parser.ts` | 監査出力パースの仕様確認 |

---

## チェックリスト印刷用テンプレート

以下をコピーして、Phase 12 実行時に紙に印刷するか、テキストエディタで ✓ を記入しながら進めることをお勧めします。

```
[ ] 前提確認: Phase 11 完了
[ ] P2: artifacts.json status = "completed"
[ ] P3: documentation-changelog.md が同期状態
[ ] P4: audit currentViolations.total === 0
[ ] P5: na-log-validator すべて PASS
[ ] P6: N/A判定に理由と代替証跡が記載
[ ] P7: 全仕様書に updatedBy が記入
[ ] P8: 3つのバリデーターテスト 31/31 PASS
[ ] P9: 全チェック項目が完了
[ ] P10: Phase 12 完了宣言を記入

実行日時: ________
検証者: ________
```

---

## よくある質問

### Q1: 「audit current = 0」が出ない場合、Phase 12 完了を宣言できない？

**A**: その通りです。currentViolations.total > 0 の場合は、本タスク実施中に新規違反が発生したことを意味します。以下のいずれかを実施してください：

1. 仕様書の更新を再度確認（git diff で漏れがないか）
2. N/A判定の根拠を強化（grep 検索を追加、参照リンクを明記）
3. 違反を未タスク化して Task 4 で対応

完了を急がず、品質を優先してください。

### Q2: バリデーターテストが FAIL した場合、フェーズを戻る必要がある？

**A**: いいえ。ほとんどの場合、N/A判定ログの修正で解決します（P2-P7）。以下の手順で対応：

1. テストエラーメッセージを読む
2. 対応する N/A判定ログのフィールドを修正
3. バリデーターテストを再実行
4. PASS したら次へ

Phase を戻す必要はありません。

### Q3: 「完了を急いでいる」場合、チェックリストを簡略化できる？

**A**: できません。このチェックリストはすべての項目が **必須** です。P4（documentation-changelog への早期「完了」記載）等の既知の落とし穴を防止するため、全項目の確認は絶対条件です。

急いでいる場合は、SubAgent の並列実行（P1-2 で同時実行）や時間計画の見直しを検討してください。

### Q4: 複数の SubAgent の成果物を検証する場合、手順の順序は？

**A**: 以下の順序で検証してください：

1. **全 SubAgent の N/A判定ログが完成したか確認**（P5）
2. **artifacts.json が completed か確認**（P2）
3. **documentation-changelog が同期しているか確認**（P3）
4. **audit コマンド実行**（P4）
5. **バリデーターテスト実行**（P8）

この順序で進めることで、早期に不整合を発見できます。

---

## チェックリスト完了時の報告

Phase 12 が完了したら、以下をプロジェクト記録に残してください：

```markdown
## Phase 12 完了レポート

- **完了日時**: {{YYYY-MM-DD HH:MM:SS}}
- **検証者**: {{YOUR_NAME}}
- **チェック結果**: 全31項目 ✓ PASS
- **三点突合**: PASS (artifacts=completed, changelog=synced, audit current=0)
- **N/Aログ検証**: 31テスト成功
- **次フェーズ**: Phase 13（PR作成）

### チェック所要時間
- 前提確認: {{分}}
- 三点突合: {{分}}
- N/Aログ検証: {{分}}
- バリデーター実行: {{分}}
- **合計**: {{分}}

### 実施した修正
- {{修正内容1}}
- {{修正内容2}}
- {{修正内容3}}
```
