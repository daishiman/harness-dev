---
date: 2026-05-09
deck: slide-2026-05-08-claudecode-concept-guide
type: feedback
sr_count_reflected: 15
escalations: [E-01 章2/章4二重提示, E-02 章4肥大]
---

# フィードバックログ — claudecode-concept-guide

> 本ファイルは E10 スキル反映実行プロンプトの成果物。`specs/04-09-skill-reflection-classification.md` の分類に従い、15 件のスキル反映 (SR-01〜SR-15) と 2 件のエスカレーション (E-01/E-02) を集約した。

## §1 発見した問題（15 SR + 2 E + 10 L 抜粋）

### スキル反映項目（SR）

| ID | 種別 | 発見 | 出典 |
|---|---|---|---|
| SR-01 | 検出機構不足 | total_slides 等メタ情報 vs 実装 のドリフト検出機構なし | 04-02 F-01 |
| SR-02 | スクリプトバグ | check-consistency.js が実装スライド検出に失敗（38 枚を 1 枚扱い） | bash 実行結果 |
| SR-03 | 検証不足 | viewBox 16:9 逸脱検査がない（S07 = 1600x720 が漏れた） | 04-02 F-11 |
| SR-04 | 検証不足 | SVG `<text>` font-size 13px 最小値検査がない | 04-05 G6 |
| SR-05 | 文書化不足 | "N" 接頭 ID（NarrativeOrder）命名規約未文書化 | 04-02 F-06 |
| SR-06 | 入力契約不足 | narrative_pattern (Z字 vs 4要素) frontmatter 未必須 | 04-03 P-2.4.2 |
| SR-07 | 配色拡張 | ビビッドアクセント variable 代替セット未提供 | 04-05 G1 |
| SR-08 | テンプレ不備 | print-color-adjust: exact がデフォルトテンプレに無い | 04-05 G4 |
| SR-09 | テンプレ不備 | 印刷時 box-shadow 除去がデフォルトテンプレに無い | 04-05 L4 |
| SR-10 | テンプレ不足 | sr-only / aria-live 雛形なし | 04-05 G5 |
| SR-11 | パターン未登録 | ペルソナ別導線 (経営/現場) パターン記載なし | 04-04 F-08/09/10 |
| SR-12 | パターン未登録 | 失敗パターン枠の標準テンプレなし | 04-04 F-12 |
| SR-13 | フロー未文書化 | 用語先出しスライドの標準パターンなし | 04-03 素人思考 |
| SR-14 | 検証不足 | 検証4条件の機械チェック不足（V-039/V-040 候補） | 04-07 |
| SR-15 | 運用整備 | feedback ディレクトリ運用テンプレ整備 | プロセス改善 |

### エスカレーション項目（E）

| ID | 内容 | 引き継ぎ先 | 理由 |
|---|---|---|---|
| E-01 | 章2 / 章4 二重提示の構成再設計 | 02-08 outline 再生成プロンプト | 構成全体の影響評価が必要 (CONST_007 大規模変更) |
| E-02 | 章4 16/38 肥大の章再分割 or Appendix 化 | 02-08 outline + 02-09 structure 再設計プロンプト | 章配分の全面的見直しが必要 |

### このデッキ限り（L）抜粋（参考・本プロンプト責務外）

L-01〜L-10 (10 件) は `specs/04-09-skill-reflection-classification.md` §2 に集約済み。次プロンプトでデッキ側修正に反映する。

## §2 分類

| 分類 | 件数 | ID |
|---|---|---|
| P0（即反映） | 6 | SR-02, SR-03, SR-04, SR-08, SR-09, SR-15 |
| P1（順次反映） | 7 | SR-01, SR-05, SR-06, SR-10, SR-11, SR-12, SR-13 |
| P2（フォローアップ・記述のみ） | 2 | SR-07, SR-14 |
| Esc（大規模変更） | 2 | E-01, E-02 |

## §3 反映先

### P0 反映完了

| ID | 反映先ファイル | 追加箇所 |
|---|---|---|
| SR-02 | `scripts/check-consistency.js` | スライド抽出ループ修正（depth 計算ロジック差替）|
| SR-03 | `scripts/check-consistency.js` | viewBox 16:9 逸脱検査ブロック追加（type: viewbox-aspect-mismatch）|
| SR-04 | `scripts/check-consistency.js` | SVG `<text font-size>` 13px 最小値検査追加（type: svg-fontsize-too-small）|
| SR-08 | `references/print-layout.md` | 「必須事項チェックリスト §1: print-color-adjust 強制」追加 |
| SR-09 | `references/print-layout.md` | 「必須事項チェックリスト §2: box-shadow 除去」追加 |
| SR-15 | `feedback/_template.md` | 新規作成（frontmatter + §1-§6 ひな形）|

### P1 反映完了

| ID | 反映先ファイル | 追加箇所 |
|---|---|---|
| SR-01 | `scripts/sync-checker.js` | parseStructureMd で frontmatter / JSON meta から total_slides 抽出、verifySynchronization で HTML 実装枚数と突合（type: meta-total-slides-drift）|
| SR-05 | `references/spec-registry.md` | §4 末尾に SR-4-09（N/S 接頭 ID 命名規約）追加 |
| SR-06 | `schemas/structure.schema.json` | meta.narrative_pattern (optional, enum 8 値) 追加、meta.total_slides (optional) 追加 |
| SR-06 | `references/composition-patterns.md` | §9 ナラティブ構造パターン 8 種を追記 |
| SR-10 | `references/slide-components.md` | アクセシビリティ必須テンプレート（sr-only CSS / aria-live HTML / SVG aria-label / nav aria-label / prefers-reduced-motion）追加 |
| SR-11 | `references/composition-patterns.md` | §10 ペルソナ別導線パターン 5 種追加（経営/現場/エンジニア/非エンジニア/混合）|
| SR-12 | `references/slide-design-patterns.md` | 「失敗パターン提示型スライド」セクション追加（desc-compare ベース、CSS / バリエーション 3 種 / 配置ルール）|
| SR-13 | `references/slide-text-guidelines.md` | 「用語注釈先出しフロー」セクション追加（slide-glossary 仮称テンプレ + アンチパターン）|

### P2 反映完了（記述のみ）

| ID | 反映先ファイル | 追加箇所 |
|---|---|---|
| SR-07 | `references/spec-registry.md` | SR-2-04 直下に SR-2-04-alt（Apple トーン代替セット）併記。validator V-018' 検討は将来課題として明記 |
| SR-14 | 本フィードバックログ §5 | 議論記録のみ。validate-structure.js への V-039/V-040 追加は次回プロンプトで実装判断 |

## §4 適用内容サマリ（差分概要）

| ファイル | 種別 | 概要 |
|---|---|---|
| `scripts/check-consistency.js` | 修正 + 追加 | 約 +50 行: スライド抽出 depth 計算修正 / viewBox 16:9 検査 / SVG font-size 13px 検査 / typeCounts ラベル 2 件 |
| `scripts/sync-checker.js` | 追加 | 約 +20 行: parseStructureMd で frontmatter total_slides 抽出 / verifySynchronization で drift 検査 |
| `schemas/structure.schema.json` | 追加 | meta に narrative_pattern (enum 8) と total_slides (integer) を optional で追加。backwards-compatible |
| `references/print-layout.md` | 追加 | 約 +50 行: 必須事項チェックリスト 3 項目 / 変更履歴 3.1.0 |
| `references/spec-registry.md` | 追加 | 2 行: SR-4-09 / SR-2-04-alt |
| `references/composition-patterns.md` | 追加 | 約 +120 行: §9 ナラティブ構造 8 種 + §10 ペルソナ別導線 5 種 + 変更履歴 |
| `references/slide-components.md` | 追加 | 約 +90 行: アクセシビリティ必須テンプレ 6 項目 |
| `references/slide-design-patterns.md` | 追加 | 約 +90 行: 失敗パターン提示型スライド標準テンプレ + バリエーション 3 種 + 配色 + スキーマ参照 |
| `references/slide-text-guidelines.md` | 追加 | 約 +60 行: 用語注釈先出しフロー + slide-glossary テンプレ + 配置ルール + アンチパターン |
| `references/changelog.md` | 追加 | v7.6.0 エントリ |
| `feedback/_template.md` | 新規 | 1 ファイル: frontmatter + §1-§6 + 使用方法 |

### 構文チェック結果

- `node --check scripts/check-consistency.js` → OK
- `node --check scripts/sync-checker.js` → OK
- `JSON.parse(schemas/structure.schema.json)` → OK
- 既存 spec への影響: backwards-compatible（meta 追加プロパティはすべて optional、required 変更なし）

### 既存 spec 影響確認の制約

`validate-structure.js` を既存 spec に対して走らせる検証は本プロンプト範囲外（CONST: 「既存 spec への影響はユーザー確認後」）。schema 構文 OK、新規プロパティはすべて optional のため既存 spec は invalid 化しない見込み。

## §5 大規模変更エスカレーション

### E-01 章2 / 章4 二重提示の構成再設計

- **現象**: 章2 でも章4 でも同じ「7要素マップ」が再描画されている（N06/S07/S08/N16/S17/N28/N29、計 6 回再描画）
- **必要な変更**: outline 再設計でどちらか 1 章に集約。共有図解を「参照スライド」として宣言する仕組みも検討
- **引き継ぎ**: 02-08 outline 再生成プロンプト
- **理由**: 章構造の全面的影響評価が必要（CONST_007 大規模変更）

### E-02 章4 16/38 肥大

- **現象**: 章4 が 16/38 スライド（42%）を占有し、認知負荷過多
- **必要な変更**: 章4 を 2 章に再分割、または半分を Appendix 化
- **引き継ぎ**: 02-08 outline + 02-09 structure 再設計プロンプト

### SR-14 検証4条件の機械チェック追加検討（議論記録）

- 提案 V-039: `slide-statement` 内の `statement-sub > ul > li` 数 → 0 件であること（文字列リスト禁止）
- 提案 V-040: `slide-diagram` 内の `code-list > li` 数 → 0 件であること（chip/card に置換済みか）
- 提案 V-041: フローカード／step ボックス container に `align-items: center` 指定があること
- 提案 V-042: SVG `max-height` 指定の禁止（HTML カードフロー推奨）
- **議論**: いずれも HTML レンダリング後の構造を見るため、現行 `validate-structure.js`（spec JSON 検証）よりは `check-consistency.js` 側のレスポンシビリティに近い。実装は次回 (D-01) で意思決定する。
- **アクション**: 本プロンプトでは記述のみ。実装は別プロンプトで決定。

### D-01 / D-02 議論記録

- D-01: V-039〜V-042 の実装場所（validate-structure.js / check-consistency.js / 新スクリプト）の決定
- D-02: 失敗パターンスライド `diagram-misfire` の `slideTypeEnum` 正式追加タイミング（現状は `slide-compare` で代用）

## §6 resource-map drift 確認結果

`references/resource-map.md` と実ファイルの突合（2026-05-09 時点）。

| カテゴリ | 記載 | 実際 | drift |
|---|---|---|---|
| references/ | 35 | 39 | **+4 件**: structure.md / svg-design-spec.md / v8-spec-fields.md / (本フィードバックで追加なし) のうち resource-map 未記載のもの |
| agents/ | 12 | 13 | **+1 件**: html-generator.diff.md（差分管理用、resource-map 未記載）|
| scripts/ | 19 | 23 | **+4 件**: cross-deck-consistency.js / d3-bootstrap.cjs / validate-print.js / templates ディレクトリ / test-fixtures ディレクトリ（一部はディレクトリ）|
| schemas/ | 3 | 5 | **+2 件**: example-full.structure.json / example.v8.structure.json |

### Drift 詳細

**references/ で resource-map 未記載**:
- `structure.md` （構造設計テンプレート、resource-map では構造・戦略系に列挙されているが行数不明）
- `svg-design-spec.md`（SVG 設計仕様、未記載）
- `v8-spec-fields.md`（v8 拡張フィールド、未記載）

**agents/ で未記載**:
- `html-generator.diff.md`（差分ノート、本来 .gitignore 候補）

**scripts/ で未記載**:
- `cross-deck-consistency.js`
- `d3-bootstrap.cjs`
- `validate-print.js`
- `templates/`（ディレクトリ、テンプレ HTML 等を保持と推定）
- `test-fixtures/`（ディレクトリ、テストフィクスチャ）

**schemas/ で未記載**:
- `example-full.structure.json`
- `example.v8.structure.json`

### 対応方針

- 本プロンプトの責務外（CONST: アーキテクチャ変更ではない、ファイル追加でもないが記述更新は要する）
- 次回スキル整備プロンプト（または harness-creator メンテナンス）で `references/resource-map.md` を更新する
- 特に `validate-print.js` は SR-08/SR-09 の自動検査に直結するため、resource-map で位置づけを明確化することを推奨

---

## 完了サマリ

- **反映完了**: 15 SR（P0: 6 / P1: 7 / P2: 2）
- **エスカレーション**: 2 E（E-01 / E-02）
- **議論記録**: SR-14 / D-01 / D-02
- **drift 検出**: references/+4, agents/+1, scripts/+5, schemas/+2 → resource-map.md 更新は次プロンプトで実施
