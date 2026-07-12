# Git Operations スクリプトテンプレート指示

> **読み込み条件**: type === "git-ops" の場合
> **対応ランタイム**: Bash, Node.js

---

## 目的

Gitリポジトリの操作およびGitHub連携を自動化するスクリプトを生成する。

---

## AIへの実装指示

### 必須機能

1. **リポジトリ状態確認**
   - 変更ファイルの検出
   - 現在のブランチ取得
   - リモートとの差分確認

2. **コミット操作**
   - ステージング
   - コミットメッセージ生成/指定
   - Co-Authored-By対応

3. **ブランチ操作**
   - ブランチ作成/切り替え
   - フィーチャーブランチの命名規則適用
   - ブランチ削除（ローカル/リモート）
   - マージ/リベース

4. **リモート操作**
   - プッシュ（上流設定含む）
   - プル/フェッチ
   - リモート設定

5. **GitHub連携（gh CLI使用）**
   - Pull Request作成/更新
   - Issue作成/クローズ
   - GitHub Actions実行
   - Workflow状態確認
   - リリース作成

6. **GitHub Actions操作**
   - ワークフローの手動トリガー
   - ワークフロー実行状態の確認
   - 実行ログの取得
   - ワークフロー一覧取得

### 安全対策

AIは以下の安全対策を実装してください:

- `--force` オプションの使用を避ける（明示的に要求された場合のみ）
- `main`/`master`への直接プッシュ警告
- 未コミット変更の確認
- dry-runモードのサポート
- 保護ブランチへの操作警告

### 引数仕様

| 引数 | 必須 | 説明 |
|------|------|------|
| --action | ○ | 実行アクション |
| --message | △ | コミット/PR/Issueメッセージ |
| --branch | △ | ブランチ名 |
| --base | × | ベースブランチ（PR作成時） |
| --workflow | △ | ワークフロー名（Actions操作時） |
| --dry-run | × | 実行せずに内容を表示 |

### サポートアクション

| アクション | 説明 |
|-----------|------|
| status | リポジトリ状態表示 |
| commit | コミット実行 |
| push | プッシュ実行 |
| branch | ブランチ操作 |
| pr-create | Pull Request作成 |
| pr-merge | Pull Requestマージ |
| issue | Issue操作 |
| workflow-run | GitHub Actions手動実行 |
| workflow-status | ワークフロー状態確認 |
| release | リリース作成 |

### 環境変数

- `{{GIT_AUTHOR_NAME}}`: 著者名（任意）
- `{{GIT_AUTHOR_EMAIL}}`: 著者メール（任意）
- `{{GITHUB_TOKEN}}`: GitHub API トークン（gh CLI認証用）

---

## コード構造の指示

AIは以下の構造でコードを生成してください:

```
1. 依存確認
   - git コマンドの存在確認
   - gh CLI の存在確認（GitHub操作時）
   - リポジトリ内かの確認

2. ユーティリティ関数
   - runGit(): gitコマンド実行ラッパー
   - runGh(): gh CLIコマンド実行ラッパー
   - getStatus(): 状態取得
   - getCurrentBranch(): 現在ブランチ取得
   - hasUncommittedChanges(): 未コミット確認

3. Git操作関数
   - actionStatus(): 状態表示
   - actionCommit(): コミット実行
   - actionPush(): プッシュ実行
   - actionBranch(): ブランチ操作

4. GitHub連携関数
   - actionPrCreate(): PR作成
   - actionPrMerge(): PRマージ
   - actionIssue(): Issue操作
   - actionWorkflowRun(): ワークフロー実行
   - actionWorkflowStatus(): ワークフロー状態
   - actionRelease(): リリース作成

5. メイン処理
   - 引数パース
   - アクション実行
   - 結果出力
```

---

## 品質基準

AIは以下の基準を満たすコードを生成してください:

- [ ] gitリポジトリ外での実行時の適切なエラー
- [ ] 危険な操作の事前確認
- [ ] dry-runでの変更内容の明確な表示
- [ ] コミットメッセージの適切なフォーマット
- [ ] リモートの存在確認
- [ ] gh CLI未認証時の適切なエラー
- [ ] ワークフロー実行の非同期/同期対応
