# Open-world system-design knowledge lifecycle

## 目的

現行の知識領域を閉じた完全リストと誤認せず、プロジェクトの目的・制約・技術変化から未知または追加の手段知識を発見し、一次資料で裏付け、目的適合で選べる深さまで育てる。

## 責務境界

- C04 (`ref-system-design-knowledge`): seed、card schema、catalog、発見・昇格・鮮度監査の規則をReadで返す。ネットワーク検索、candidate書込、curated更新を実行しない。
- C01 (`run-system-spec-elicit`): ヒアリング中の未知語、未決定事項、goal/constraintとのgapを発見シグナルとして記録し、project candidateを所有する。
- C02 (`run-system-spec-doc-fetch`): candidateごとに公式publisher/host、一次資料、version/updated、checked_atを取得・再照合する。
- 保守担当: project candidateをレビューし、汎用性・重複・一次資料・深度・ライセンスを確認してC04 curated catalogへ昇格する。自動昇格は禁止。

## Lifecycle

1. **Discover**: U1-U9、未決定事項、カテゴリmatrix、障害/非機能要件、既存カードの `related_topics` から不足知識を候補化する。現行6領域は探索開始点であり探索終了条件ではない。
2. **Qualify**: 公式標準、仕様、原著者、標準化団体、公式vendor docsを優先する。検索結果要約や二次ブログだけの候補は `unqualified` のまま仕様判断に使わない。書籍由来は書名・著者・版・年を記録する。
3. **Deepen**: `knowledge-card.schema.json` の `purpose/background/problems/core_concepts/applies_when/does_not_apply_when/tradeoffs/failure_modes/goal_contribution/primary_sources/freshness` を埋める。名称と短い要点だけでは完了しない。
4. **Goal map**: candidateが資する `goal_ids`、守る `constraint_ids`、解決するproblem、採用しない条件を明示する。goalに結べない候補は探索メモに留める。
5. **Project candidate**: C01のproject-local stateへ `candidate` として保存する。推奨の前にC02のqualificationを通し、事実・推論・ユーザー決定を分離する。
6. **Curated promotion**: 複数projectへ再利用可能、既存カードと非重複、深度必須欄充足、一次資料あり、freshness policyあり、担当者承認済みの場合だけC04へ昇格する。類似カードは新設せず既存へ統合する。
7. **Freshness audit**: `review_by` またはtrigger到来時に一次資料を再照合する。破壊的変更、標準改訂、security advisory、vendor EOL、価格/無料枠変更は即時trigger。未確認は `stale` と明示し、最新推奨の根拠に使わない。

## Project candidate 最小形

project candidate は C01 の project-local state (`spec-state.json`) の `knowledge_candidates[]` へ保存し、書込は `apply-spec-transition.py set-knowledge-candidate` のみが行う。**形状の正本は C01 の `references/spec-state-contract.md`「KNOWLEDGE_CANDIDATES_EXTENSION_C」であり、writer が受理する実形状に忠実であること** (本節はその要約。lifecycle 語彙と writer の status enum を取り違えると writer が全拒否する)。

必須共通項目は kebab-case `id` / stable `topic` / `status` / `problem` / 実在 goal を指す `serves_goals` / `source_refs` (配列)。`status` は writer の 4 値 enum `discovered → qualified → deepened → promoted` で、一段階前進のみ (巻き戻し・飛び級・topic 変更は禁止)。`discovered` 段階の最小形:

```json
{
  "id": "offline-first-conflict-resolution",
  "topic": "offline-first conflict resolution",
  "status": "discovered",
  "problem": "複数端末のオフライン更新競合を解決する必要がある",
  "serves_goals": ["G1"],
  "source_refs": []
}
```

status が進むごとに writer が追加フィールドを強制する:

- `qualified` 以降: `source_refs[]` は各 `{url (HTTPS), official_or_primary: true, checked_at}` を持つ非空配列 (二次ブログのみは不可)。qualification 担当は C02。
- `deepened` 以降: `card` が deep-card 必須意味項目 (`purpose/background/problems/core_concepts/applies_when/does_not_apply_when/tradeoffs/failure_modes/goal_contribution/primary_sources/freshness`) を全て持ち、`card.primary_sources[].locator` は HTTPS。
- `promoted`: 保守担当の承認・curated 配置を指す `curation_ref` が必須 (自動昇格しない)。

### Lifecycle 7 段階 → writer status 4 値の対応

| Lifecycle 段階 | writer status | writer が強制する形状 |
|---|---|---|
| 1. Discover | `discovered` | 必須共通項目 (`source_refs` は空可) |
| 2. Qualify | `qualified` | `source_refs[]` を公式/一次 HTTPS + `checked_at` 付き非空へ |
| 3. Deepen | `deepened` | `card` 必須意味項目を全充足 (`primary_sources[].locator` HTTPS) |
| 4. Goal map | (status 横断) | `serves_goals` を実在 goal へ結ぶ (全 status で必須共通) |
| 5. Project candidate | `discovered`/`qualified` | C01 `knowledge_candidates[]` へ `set-knowledge-candidate` で保存 |
| 6. Curated promotion | `promoted` | `curation_ref` (承認・curated 配置) 必須・自動昇格禁止 |
| 7. Freshness audit | (status 不変) | `card.freshness` / `source_refs[].checked_at` を再照合 |

Goal map と Freshness audit は独立した status を持たず、それぞれ全 status で必須の `serves_goals` 付与と、既存 candidate の鮮度再照合という横断的規律。Project candidate は保存という行為で、その時点の status (`discovered` か `qualified`) を保つ。

## 停止条件

- 候補の各必須深度欄が具体的で、同義反復や「適宜検討」だけでない。
- 一次資料と鮮度が追跡可能で、goal/constraintへ結ばれている。
- 適用条件と非適用条件の両方があり、万能解として提示されていない。
- project candidateとcurated cardの境界、昇格判断、重複統合先が明示されている。

