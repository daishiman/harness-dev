# ガイドライン・型定義リファクタリング

> 親ファイル: [patterns.md](patterns.md)

## ガイドライン

実行時の判断基準。

### 抽象度レベル判定

- **状況**: ユーザー要求の具体性を判断する時
- **指針**: L1（概念）→ 詳細インタビュー、L2（機能）→ 軽いヒアリング、L3（実装）→ 直接実行
- **根拠**: 抽象度に応じて必要な対話量が変わる
- **発見日**: 2026-01-15

### モード選択

- **状況**: create/update/improve-prompt の選択時
- **指針**: 既存スキルパスの有無、更新対象の特定で判断
- **根拠**: detect_mode.js の判定ロジックに準拠
- **発見日**: 2026-01-06

### [Phase12] Step 1-A 台帳ファイルも `documentation-changelog.md` に同値転記する

- **状況**: `system-spec-update-summary.md` では Step 1-A の `SKILL.md` / `LOGS.md` 更新を記録したが、`documentation-changelog.md` の更新ファイル一覧から漏れやすい
- **指針**: Step 1-A で更新した `aiworkflow-requirements` / `task-specification-creator` の `SKILL.md` / `LOGS.md` は必ず changelog に canonical path で列挙する。`skill-creator` を改善した場合はその `SKILL.md` / `LOGS.md` / asset / reference も同時に列挙する
- **根拠**: 完了記録と変更台帳がずれると、再監査時に「更新したのに changelog へ無い」「changelog にあるのに根拠がない」の両方が起きる
- **発見日**: 2026-03-19

---

## 型定義リファクタリング

### 成功パターン: deprecated プロパティの段階的移行（TASK-FIX-13-1）

**コンテキスト**: TypeScript型定義で `@deprecated` マーク付きプロパティを推奨代替に移行し、定義を削除する

**課題**:

- 同名プロパティ（`name`, `lastUpdated`）が複数の型に存在し、単純な文字列置換では誤修正のリスクが高い
- 永続化互換のため残すべきプロパティと削除すべきプロパティの判定が必要

**解決策**:

1. **スコープ分離**: 削除対象の型を明確にし、同名プロパティが存在する他の型（`SkillImportConfig.lastUpdated`, `StorageMetadata.lastUpdated`）をスコープ外として明示
2. **TDD型レベルテスト**: `@ts-expect-error` ディレクティブで「プロパティが存在しないこと」を型レベルで検証
3. **型スコープ限定grep**: `Anchor` 型スコープに限定して参照箇所を検索し、汎用プロパティ名の誤検出を回避

**結果**: 型定義2箇所の削除、テスト8件PASS、全参照移行完了

**適用条件**: TypeScriptプロジェクトでdeprecatedプロパティを安全に削除したい場合

```typescript
// TDD型レベルテストパターン
it("削除されたプロパティにアクセスするとエラーになること", () => {
  const obj: MyType = { newProp: "value" };
  // @ts-expect-error -- oldProp は削除済み
  const _old = obj.oldProp;
  expect(obj).toBeDefined();
});
```

### 失敗パターン: ドキュメント偏重による実装検証省略

**コンテキスト**: Phase 1-12の並列エージェント実行でドキュメント成果物を高速生成

**課題**: 5つの並列エージェントでPhase 1-11のドキュメントを同時生成し、Phase 12まで完了と報告したが、コードの実装検証（grep・テスト・型チェック）が不十分だった

**原因**: ドキュメント生成の完了を「実装完了」と混同。並列エージェントの出力に対する品質ゲートが未設定

**教訓**:

1. **コード検証ファースト**: ドキュメント生成前に、テスト・型チェック・grepでコード変更の完了を確認する
2. **並列エージェント後の統合検証**: 全エージェント完了後に成果物一覧と整合性チェックを実施
3. **品質ゲートの明示化**: Phase 5（実装）完了の判定基準をテスト結果で定義し、Phase 6以降はその結果を前提とする

### [ビルド・環境] 4ファイル同期漏れパターン（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: @repo/shared に新サブパスを追加する際、4つのファイル（package.json exports/typesVersions、tsconfig.json paths、vitest.config.ts alias、tsup.config.ts entry）のうち一部のみ更新
- **結果**: TypeScript は通るが Vitest が失敗、またはその逆。CI で初めてエラーが検出される
- **解決策**: 4ファイル同時更新チェックリストを development-guidelines.md に配置。整合性テストの追加
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001
- **関連未タスク**: UT-FIX-TS-VITEST-TSCONFIG-PATHS-001（vitest-tsconfig-paths プラグインによる自動化）

### [UI/TypeScript] HTMLAttributes Props型衝突（TASK-UI-00-ATOMS）

- **状況**: Badge コンポーネントに `content?: string | number` Props を追加
- **問題**: `React.HTMLAttributes<HTMLSpanElement>` の標準属性 `content?: string` と型衝突し、TS2430エラーが発生
- **原因**: HTML標準属性と同名のカスタムPropsを定義したため、TypeScriptが型の互換性を検証できなかった
- **教訓**: `Omit<React.HTMLAttributes<HTMLElement>, "conflictingProp">` で衝突属性を除外してからカスタム型を定義する
- **発見日**: 2026-02-23
- **関連タスク**: TASK-UI-00-ATOMS
- **関連Pitfall**: [06-known-pitfalls.md#P46](../../rules/06-known-pitfalls.md)

```typescript
// ❌ TS2430エラー
interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  content?: string | number; // HTML標準のcontent(string)と衝突
}

// ✅ Omitで衝突回避
interface BadgeProps extends Omit<
  React.HTMLAttributes<HTMLSpanElement>,
  "content"
> {
  content?: string | number;
}
```

**衝突しやすい属性**: `content`, `color`, `translate`, `hidden`, `title`, `dir`, `slot`

### [Phase3] Props命名の仕様-実装間ドリフト（TASK-UI-00-ATOMS）

- **状況**: RelativeTime コンポーネントの自動更新間隔Propsで、仕様書では `updateInterval`、実装では `refreshInterval` と命名が乖離
- **問題**: Phase 10レビュー時に命名不整合が発覚し、仕様書の修正が必要になった
- **原因**: Phase 3設計レビューでProps命名の仕様-実装間突合チェックが不足していた
- **教訓**: Phase 3にProps命名突合チェック項目を追加。仕様書と実装で同一用語を使用する
- **対策**: Phase 3レビューチェックリストに「Props命名の仕様-実装一致確認」を追加
- **発見日**: 2026-02-23
- **関連タスク**: TASK-UI-00-ATOMS

### [Phase4] 修正箇所数の事前ファイル検証不足（UT-SKILL-IMPORT-CHANNEL-CONFLICT-001）

- **状況**: Phase 4（テスト作成）で task-022 の修正箇所を「3箇所」と仕様書に記載
- **問題**: 実装時に検証したところ、外部ソースインポート文脈の `skill:import` は 1箇所のみだった
- **原因**: Phase 4 設計時にファイル内容を `grep` で事前検証せず、概算で修正箇所数を決定
- **教訓**: Phase 4 テスト設計時は対象ファイルを `grep -c` で事前カウントし、期待値を「N件以上」のような柔軟な基準で設計する。P37（ドキュメント数値の早期固定）と同じパターン
- **対策**: テスト仕様書の期待値は `>=N` 形式で記述し、Phase 5 実行後に実測値で更新
- **発見日**: 2026-02-24
- **関連タスク**: UT-SKILL-IMPORT-CHANNEL-CONFLICT-001

### [Phase12] 対象テスト限定実行の明示（TASK-UI-01-C 再監査）

- **状況**: Phase 12 再監査で「対象5ファイルのみ再検証」したい場面
- **成功パターン**:
  - `pnpm exec vitest run <file1> <file2> ...` で対象を明示し、`N files / M tests` を成果物へ固定
  - 監査ログに「対象ファイル列挙 + 実測件数」を残し、再実行時の比較可能性を確保
- **失敗パターン**:
  - `pnpm run test:run -- <files...>` を使い、script側の設定で全体テストへ展開されて長時間化・中断を招く
- **標準ルール**:
  - 再監査時の限定テストは script ラッパーを経由せず `pnpm exec vitest run` を正とする
  - 目的が「再確認」の場合は coverage を同時実行せず、まず対象テストのPASSを確定する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-C-NOTIFICATION-HISTORY-DOMAIN

### [Phase12] Step 1-A四点同期 + Phase 11再撮影運用ガード（TASK-UI-01-D 再確認）

- **状況**: Phase 12 の再確認で `spec-update-summary.md` と system spec は更新済みでも、`LOGS.md` / `SKILL.md` / `topic-map` の同期が後回しになりやすい。さらに再撮影時に workflow 固定出力先と `Port 5177` 競合で証跡運用が不安定化する
- **成功パターン**:
  - Step 1-A を「`LOGS.md` x2 + `SKILL.md` x2 + `generate-index`」の四点セットとして同一ターンで完了する
  - Phase 11 再撮影は workflow 配下保存を固定し、ポート preflight の分岐（停止/再利用）を `unassigned-task-detection.md` へ記録する
  - 運用ギャップは `docs/30-workflows/unassigned-task/` へ未タスク化し、`audit --target-file` で `currentViolations=0` を確認する
- **失敗パターン**:
  - `spec-update-summary` のみ更新して Step 1-A 完了扱いにする
  - 固定出力先のまま再撮影して手動コピーで帳尻を合わせる
  - ポート競合を記録せずに「再撮影済み」と判定する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-D-VIEWTYPE-ROUTING-NAV, UT-IMP-TASK-056D-PHASE11-SCREENSHOT-CAPTURE-PATH-GUARD-001

### [Phase12] UI再撮影のworkflow保存先固定 + strictPort preflight（5177）記録テンプレート（TASK-UI-01-D 追補）

- **状況**: system spec へ「実装内容」と「苦戦箇所」を追記しても、再撮影の実行前ガード（保存先/ポート）をテンプレートに書かないと再発しやすい
- **成功パターン**:
  - `phase12-system-spec-retrospective-template.md` / `phase12-spec-sync-subagent-template.md` に `lsof -nP -iTCP:5177 -sTCP:LISTEN` を追加し、分岐（停止/再利用/別ポート）記録を必須化
  - `test -d <workflow>/outputs/phase-11/screenshots` で保存先を先に固定し、workflow外証跡の流入を防止
  - 5分解決カードを `task-workflow` / `lessons-learned` / `ui-ux-navigation` へ同一内容で同期する
- **失敗パターン**:
  - preview preflight だけ実施して strictPort preflight を省略する
  - `task-056` 固定パスの証跡を手動コピーで帳尻合わせし、分岐記録を残さない
- **標準ルール**:
  - UI再撮影運用は「preview preflight」「strictPort preflight」「workflow保存先確認」の3点を必須セットとする
  - preflight失敗時は再撮影を継続せず未タスク化し、再発条件を `lessons-learned` に固定する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-D-VIEWTYPE-ROUTING-NAV, UT-IMP-TASK-056D-PHASE11-SCREENSHOT-CAPTURE-PATH-GUARD-001

### [Phase12] shared transport DTO + cross-cutting doc + 専用 harness 同期（TASK-FIX-AUTH-MODE-CONTRACT-ALIGNMENT-001）

- **状況**: IPC transport 契約をコード上は是正したが、`ipc-contract-checklist.md` / `quick-reference.md` の横断導線や、画面検証の対象 view 専用 harness 条件が後追いになりやすい
- **成功パターン**:
  - shared transport DTO を `packages/shared` に集約し、Main / Preload / Renderer は import / re-export のみで追従する
  - Step 2 で `interfaces` / `api-ipc` / `security` / `task-workflow` / `lessons` に加えて `ipc-contract-checklist.md` / `indexes/quick-reference.md` を同一ターンで同期する
  - UI契約だけを確認したい場合は対象 view 専用 harness を追加し、`SCREENSHOT` 証跡と `validate-phase11-screenshot-coverage` をセットで固定する
  - 運用ギャップがスクリプト改善領域なら未タスク化し、`audit --target-file` で `currentViolations=0` を確認する
- **失敗パターン**:
  - `interfaces` / `api-ipc` だけ更新して、cross-cutting doc が古いまま残る
  - App 全体起動のノイズを抱えたまま画面検証し、対象 contract の変化点が読み取れない
  - `verify-unassigned-links` の `missing` だけを見て原因を手で辿り、改善バックログへ formalize しない
- **標準ルール**:
  - IPC transport 契約修正は「shared DTO」「cross-cutting doc」「画面検証方針」の3点を同一ターンで閉じる
  - ユーザーが画面検証を要求した場合、初期方針が非視覚でも `SCREENSHOT` へ昇格し、必要なら専用 harness を許可する
  - 監査ツールの説明力不足は `docs/30-workflows/unassigned-task/` へ未タスク化し、配置・形式・参照を機械検証してから完了扱いにする
- **発見日**: 2026-03-06
- **関連タスク**: TASK-FIX-AUTH-MODE-CONTRACT-ALIGNMENT-001, UT-IMP-PHASE12-UNASSIGNED-LINK-DIAGNOSTICS-001

### [Phase12] domain spec に `実装内容` / `苦戦箇所` / `5分カード` を対称配置する（TASK-FIX-AUTH-MODE-CONTRACT-ALIGNMENT-001 追補）

- **状況**: `task-workflow` と `lessons-learned` には知見があるのに、`interfaces` / `api-ipc` の domain spec 側は契約表だけで終わり、再利用時に背景と難所が読めない
- **成功パターン**:
  - `assets/phase12-domain-spec-sync-block-template.md` を使い、更新した domain spec に `### 実装内容（要点）` / `### 苦戦箇所（再利用形式）` / `### 同種課題の5分解決カード` を同居させる
  - `interfaces` と `api-ipc` の両方で、shared DTO 正本化・UI表示契約・Phase 11 画面検証方針を同じ粒度で記録する
  - `task-workflow` / `lessons-learned` / domain spec の 3 点で 5 ステップ順序をそろえる
- **失敗パターン**:
  - domain spec をチャネル表や型表の更新だけで終え、苦戦箇所を lessons のみに押し込む
  - `task-workflow` と domain spec で 5 分解決カードの順序や検証値が異なる
- **標準ルール**:
  - Phase 12 Step 2 で触る domain spec は、契約表だけでなく「実装内容」「苦戦箇所」「5分カード」の3点を最小セットとする
  - `rg -n '^### 実装内容（要点）$|^### 苦戦箇所（再利用形式）$|^### 同種課題の5分解決カード$' <domain-spec-file>` を完了前に必ず実行する
- **発見日**: 2026-03-06
- **関連タスク**: TASK-FIX-AUTH-MODE-CONTRACT-ALIGNMENT-001

### [Phase12] UI domain spec は「主目的 + 状態契約 + 画面証跡」を先に固定する（TASK-UI-06-HISTORY-SEARCH-VIEW）

- **状況**: UI task の system spec を作るとき、コンポーネント一覧と screenshot 一覧だけでは「何のための画面か」「どの state/IPC が正本か」が後から読み取りにくい
- **成功パターン**:
  - 専用 domain spec に `### 実装内容（要点）` を置き、`画面の主目的` / `変更範囲` / `契約上の要点` / `視覚検証` / `完了根拠` を最初に固定する
  - `ui-ux-feature-components.md` 側は圧縮サマリーと 5分解決カードだけを保持し、詳細は専用 spec へリンクする
  - `task-workflow.md` / `lessons-learned.md` / UI domain spec の 3 点で 5 ステップ順序を揃える
- **失敗パターン**:
  - UI spec が責務表と screenshot 一覧だけで終わり、変更範囲や state 契約の要点が本文から見えない
  - 専用 spec と feature summary spec で見出し名や 5分カードの粒度がずれる
- **標準ルール**:
  - UI domain spec の `実装内容（要点）` には少なくとも `画面の主目的` / `契約上の要点` / `視覚検証` の 3 行を入れる
  - `ui-ux-feature-components.md` の対応節にも `同種課題の5分解決カード` を置き、専用 spec と task-workflow の橋渡しに使う
- **発見日**: 2026-03-10
- **関連タスク**: TASK-UI-06-HISTORY-SEARCH-VIEW

### [Phase12] `ui-ux-feature-components.md` も 3ブロック構成で閉じる（TASK-SKILL-LIFECYCLE-01）

- **状況**: `task-workflow.md` と `lessons-learned.md` には実装内容と苦戦箇所が入っているのに、`ui-ux-feature-components.md` 側はサマリー表だけで終わり、feature spec 単体では再利用手順が読み取りにくくなる
- **成功パターン**:
  - `ui-ux-feature-components.md` の対象節にも `実装内容（要点）` / `苦戦箇所（再利用形式）` / `同種課題の5分解決カード` を置く
  - `実装内容（要点）` には少なくとも `画面の主目的` / `契約上の要点` / `視覚検証` / `完了根拠` を含める
  - `苦戦箇所` は `task-workflow.md` / `lessons-learned.md` と同じ再発条件で揃え、feature spec では UI 起点の対処へ寄せて圧縮する
  - `currentViolations=0` と `baselineViolations>0` の二軸報告が必要なら feature spec 側にも短く残す
- **失敗パターン**:
  - feature spec を「UI観点の要点」だけで閉じ、苦戦箇所を別仕様書に追い出す
  - task-workflow と feature spec で 5分解決カードの順序や検証値がズレる
- **標準ルール**:
  - UI task の feature spec は圧縮サマリー専用にせず、最小3ブロックを持つ再利用正本として形成する
  - `rg -n '^#### 実装内容（要点）$|^#### 苦戦箇所（再利用形式）$|^#### 同種課題の5分解決カード$' references/ui-ux-feature-components.md` を完了前に実行する
- **発見日**: 2026-03-11
- **関連タスク**: TASK-SKILL-LIFECYCLE-01

### [Phase12] 「更新予定のみ」残置を排除し、実更新ログへ昇格する（TASK-10A-E-C）

- **状況**: Phase 12 で `spec-update-summary.md` は更新されているが、`documentation-changelog.md` や `phase-12-documentation.md` が「仕様策定のみ」「実行中」のまま残る
- **成功パターン**:
  - `documentation-changelog.md` を最終正本として再作成し、Task 1〜5 の実施結果を確定値で記録する
  - `phase-12-documentation.md` のチェックボックスを実績へ同期する
  - `verify-all-specs` / `validate-phase11-screenshot-coverage` / `verify-unassigned-links` の結果を changelog に固定する
- **失敗パターン**:
  - `spec-update-summary.md` だけ更新して完了扱いにする
  - 「更新予定」「実行待ち」記述を残したまま Phase 12 を閉じる
- **標準ルール**:
  - Phase 12 完了前に `rg -n "仕様策定のみ|実行中|実行待ち|更新が必要" outputs/phase-12` を実行し、残置文言をゼロにする
  - completed workflow では `phase-12-documentation.md` に対しても `rg -n "仕様策定のみ|実行予定|保留として記録"` を実行し、本文だけ stale な状態を残さない
  - `phase-12-documentation.md` の完了条件と `Task 100% 実行確認` を `[x]` へ同期し、Phase 13 以外の保留を残さない
  - Task 1〜5 の実施証跡を 1 ファイル（`documentation-changelog.md`）で追跡可能にする
- **発見日**: 2026-03-06
- **関連タスク**: TASK-10A-E-C

### [Phase12] 未タスク指示書は 9見出しテンプレート準拠で作成する（TASK-10A-E-C）

- **状況**: 未タスクを短縮形式で作成すると、`audit-unassigned-tasks` の format violation が発生
- **成功パターン**:
  - `assets/unassigned-task-template.md` を適用し、`## 1..9` を全て埋める
  - 作成直後に `audit-unassigned-tasks --target-file` で個別検証する
- **失敗パターン**:
  - メタ情報 + 背景 + 受け入れ条件だけで未タスクを作る
  - 参照情報/リスク/検証手順を省略する
- **標準ルール**:
  - 未タスク新規作成時は「テンプレート適用→個別監査PASS→台帳同期」の3点を同一ターンで完了する
- **発見日**: 2026-03-06
- **関連タスク**: UT-10A-E-C-001, UT-10A-E-C-002

### [Phase12] スキルフィードバックレポートテンプレート（TASK-UI-03）

- **状況**: Phase 12 Task 5（スキルフィードバックレポート）の記載粒度がタスクごとにばらつき、後続のスキル改善で活用しにくい
- **成功パターン**:
  - 以下の4セクション構成を標準テンプレートとして使用する:

```markdown
# スキルフィードバックレポート
