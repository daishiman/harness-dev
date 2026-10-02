---
name: solo-git-flow
description: 個人開発(レビュアーが自分ひとり)で、Issue起票→ブランチ作成→コミット→PR作成→マージ→リリースタグ→取り消し までを gh CLI で一貫管理するための運用ルールとテンプレート集。「ブランチ切って」「ブランチ名どうする」「コミットして」「PR出して」「プルリク作って」「PRのタイトル/説明書いて」「Issue立てて」「課題を整理して」「マージして」「リリースして」「前の状態に戻して」などの依頼で必ず使用する。app-orchestrator の追加開発モード(ブランチ+PR)を実行するときの具体手順もこのスキルに従う。GitHub MCP は使わず gh CLI を使う。
---

# solo-git-flow — 個人開発のGit/GitHub運用

## §0. 前提と原則

1. **操作は `gh` CLI で行う**。GitHub MCP には依存しない。認証は `gh auth status` で確認でき、未認証なら利用者本人に `! gh auth login` の実行を依頼する(対話ログインは代行しない)。
2. **main は常にデプロイ可能**。main に直接 push しない。例外は初回リリース(v1)前のみ。app-orchestrator を使う場合、**v0 を関係者へ公開した後も v1 に到達するまでは「初回リリース前」として扱い、main 直コミットを継続してよい**(1画面ずつの設計深化を PR にすると育てるループが止まるため)。ブランチ + PR へ切り替えるのは **v1 公開後**である。
3. **1つのPRは1つの目的**。「ついでの修正」を混ぜない。混ざったら分ける。
4. **履歴は消さない**。`git reset --hard` と `git push --force` は使わない。取り消しは `git revert`(§7)。
5. **レビュアーが自分でもPRを出す**。理由は3つ — 変更の全体像を1画面で見返せる / マージ単位で戻せる / 後から「なぜこうしたか」を追える。セルフマージは正当な運用であり、承認を待つ必要はない。
6. **操作対象を推測しない**。最初に`ci-cd-pipeline/scripts/detect-github-repository.mjs`を実行し、`status: ok`の`recommended.repository`、`recommended.remote`、`recommended.default_branch`をそれぞれ`GITHUB_REPOSITORY`、`GIT_REMOTE`、`GITHUB_DEFAULT_BRANCH`として全コマンドで共用する。単一候補は推奨値を提示して自動採用し、質問するのは複数remote・remote未設定・`gh`未認証のときだけ。資格情報を含むremote URLやTokenを貼らせない。

## §1. 作業を始める前の3コマンド

```bash
gh auth status                                           # 認証確認
git switch "$GITHUB_DEFAULT_BRANCH"                      # 既定ブランチへ移動
git pull --rebase "$GIT_REMOTE" "$GITHUB_DEFAULT_BRANCH" # 最新化
gh issue list --repo "$GITHUB_REPOSITORY" --state open   # 今の課題を見る
```

## §2. Issueの運用

Issueは**「今やらないこと」を頭の外に出すための置き場**である。今すぐ着手して30分で終わることを起票するのは、起票自体が作業になり形骸化する。

### 立てる / 立てない の判断

| 状況 | Issue |
|---|---|
| 今すぐ着手せず、後日やる | **必ず立てる** — 立てないと数週間で消える |
| 依頼者・利用者から来た要望や不具合報告 | **必ず立てる** — 「言った/聞いてない」を防ぐ記録になる |
| 1回の作業セッションで終わらない見込み | **必ず立てる** — 中断時の再開メモになる |
| 今すぐ着手して1時間以内に終わる、自分で気づいた小改善 | 立てなくてよい。そのままブランチを切る |
| typo修正・依存更新などの雑務 | 立てなくてよい |

迷ったら立てる。**閉じるコストはゼロだが、忘れたことは取り戻せない**。

### Issue本文の構造 — PRと同じ2層構造

Issueも上半分は非エンジニア、下半分はエンジニア向けに書き分ける。**着手前に読み返して「これは何の話だったか」が復元できること**が目的。

| # | 見出し(不具合 / 要望) | 読者 | 書く内容 |
|---|---|---|---|
| 1 | 何が起きているか / 困っていること | 全員 | 専門用語なしで1〜2文 |
| 2 | 本来どうなってほしいか / 背景 | 全員 | 期待する動き、今やる理由 |
| 3 | 再現手順 / こうなっていれば解決 | 全員 | 不具合は手順、要望は**達成された状態**(実装方法ではない) |
| 4 | どれくらい困っているか / 今どうしのいでいるか | 全員 | 優先順位の判断材料。頻度・影響人数・回避の手間 |
| 5 | 今の回避策 / 含めたいこと・含めなくてよいこと | 全員 | 着手前の線引き |
| 6 | 技術メモ | エンジニア | 環境・エラー・原因の見立て・想定作業。**起票時は空欄可** |
| 7 | 完了の条件 | 全員 | 何ができたら閉じてよいか |

3つの原則:

1. **要望は「解決策」ではなく「困っていること」で書く**。「CSVエクスポートが欲しい」と書くと実装がCSVに固定されるが、「集計結果を経理に渡すのが手作業でつらい」と書けば印刷でもメール送信でもよくなり、より安く解ける道が残る。
2. **§6は起票時に空欄でよい**。原因の見立ては着手時に埋める。ここを埋めないと起票できない運用にすると、起票が面倒になってIssueを立てなくなる。
3. **§7「完了の条件」が書けないIssueは、まだ要件が固まっていない**。書けないまま着手すると、どこまでやれば終わりか分からず作業が膨らむ。

雛形は `assets/ISSUE_TEMPLATE/` に同梱。リポジトリの `.github/ISSUE_TEMPLATE/` に設置すると、GitHubのIssue作成画面で種類を選べるようになる。

```bash
mkdir -p .github/ISSUE_TEMPLATE && cp -R <skill>/assets/ISSUE_TEMPLATE/. .github/ISSUE_TEMPLATE/
```

### 運用ルール

- 起票時に**必ず本文を書く**(記入例は `assets/pr-and-issue-templates.md`。実際に本文を書くときだけ開く)。タイトルだけのIssueは1週間後に自分でも意味が分からなくなる。
- **起票は `gh issue create --repo "$GITHUB_REPOSITORY" --web` を使う**。`--web` なしのCLI起票はテンプレートが適用されず、空本文のIssueができてしまう。CLIで完結させたい場合は `--repo "$GITHUB_REPOSITORY" --body-file .github/ISSUE_TEMPLATE/bug_report.md` で雛形を明示的に渡す(先頭のfrontmatterは削って渡す)。
- タイトルはブランチ名・PRタイトルと同じ `<type>: 日本語` 形式にする(`fix: 評価シートの印刷が2枚に分かれる`)。テンプレートが `fix: ` `feat: ` まで自動で入れる。
- **着手するときに自分をアサインする**(`gh issue edit --repo "$GITHUB_REPOSITORY" 12 --add-assignee @me`)。「起票済み」と「着手中」が一覧で区別できる。
- Issueは**PRの `Closes #12` で自動的に閉じる**。手で閉じない。閉じ忘れと、閉じたのに直っていない状態の両方を防ぐ。
- **月1回、openなIssueを上から読み直す**。もうやらないと分かったものは `someday` ラベルを付けるか閉じる。放置されたIssueが20件を超えると一覧を見なくなり、置き場としての機能を失う。

## §3. ブランチ

### 命名規則

`<type>/<issue番号>-<内容を表す短い英語ケバブケース>`

```
feat/12-evaluation-sheet-print
fix/15-score-rounding
docs/18-setup-guide
```

- **type** はコミットのprefix(§4)と同じ語彙を使う。頭の中の分類をひとつに保つため。
- Issue番号を入れると `gh pr create` の本文に `Closes #12` を書き忘れても紐付けを追える。Issueが無い小変更は番号を省略してよい(`fix/typo-in-readme`)。
- **日本語は使わない**。ブランチ名はURL・CI・タグ名に露出し、環境によって壊れる。日本語で表現したい内容はPRタイトル(§5)に書く。
- 長くしない。3〜5語で切る。

### 作成

```bash
git switch "$GITHUB_DEFAULT_BRANCH"
git pull --rebase "$GIT_REMOTE" "$GITHUB_DEFAULT_BRANCH"
git switch -c feat/12-evaluation-sheet-print
```

作業ブランチは**mainから切る**。他の作業ブランチから派生させると、親のPRがマージされるまで自分のPRが出せなくなる。

## §4. コミット

### メッセージ形式

```
<type>: <日本語で「何ができるようになったか」>

<なぜそうしたか。自明なら省略>
```

| type | 使う場面 |
|---|---|
| `feat` | 利用者にとっての機能が増える |
| `fix` | 想定どおり動いていなかったものを直す |
| `refactor` | 外から見た動きは変えず、内部を整理する |
| `docs` | ドキュメント・コメントのみ |
| `test` | テストの追加・修正のみ |
| `chore` | 依存更新・設定・ビルド周り |

- 件名は**日本語**、50字程度まで、句点なし。`fix: 評価点の四捨五入が0.5で切り下がる問題を修正`
- **「何をしたか(コードを見れば分かる)」ではなく「何ができるようになったか」を書く**。差分は読めば分かるが、意図は書かないと消える。
- 粒度は「revertしたときに意味が通る最小単位」。ファイル単位でもタスク単位でもない。

### 個人開発での現実的な運用

作業中は粒度を気にせず細かくコミットしてよい。**squashマージ(§6)で最終的に1コミットに畳まれる**ため、mainの履歴はPR単位で綺麗に保たれる。畳まれる前提なので `wip` のようなメッセージも作業中は許容する。ただしPRのタイトルは畳んだ後のコミットメッセージそのものになるので、そこは丁寧に書く。

## §5. Pull Request

### 作成

```bash
git push -u "$GIT_REMOTE" "$(git branch --show-current)"
gh pr create --repo "$GITHUB_REPOSITORY" --title "feat: 評価シートを印刷できるようにする" --body-file .github/PULL_REQUEST_TEMPLATE.md
```

対話で書きたい場合は `gh pr create --repo "$GITHUB_REPOSITORY" --web` でブラウザを開く。

### タイトル

**コミットメッセージ件名と同じ形式**(`<type>: 日本語で何ができるようになったか`)。squashマージ後、これがmainの履歴に残る唯一の行になる。

- ✅ `feat: 評価シートをA4縦1枚で印刷できるようにする`
- ❌ `印刷機能` — 何が変わったか分からない
- ❌ `PrintLayout.tsxの修正` — ファイル名は履歴に不要

### 本文

`.github/PULL_REQUEST_TEMPLATE.md` の雛形を使う(`gh pr create` が自動で読み込む)。**リポジトリに無ければ、このスキル同梱の雛形をコピーして最初に設置する**:

```bash
mkdir -p .github && cp <skill>/assets/PULL_REQUEST_TEMPLATE.md .github/PULL_REQUEST_TEMPLATE.md
```

### 本文の構造 — 上半分は非エンジニア、下半分はエンジニア

PR本文は**2層構造**にする。上半分(§1〜5)は開発を知らない人が読んで分かること、下半分(§6〜8)はエンジニアが差分を読む前の見取り図になること。読者が違うので、同じことを2回書いてよい。

| # | 見出し | 読者 | 書く内容 |
|---|---|---|---|
| 1 | 目的 | 全員 | 何のためにやったか。1〜2文 |
| 2 | 背景 | 全員 | どんな困りごとがあったか。`Closes #12` でIssueを閉じる |
| 3 | やったこと(中学生にも分かる説明) | 非エンジニア | 専門用語を使わず、たとえ話を使ってよい |
| 4 | できるようになったこと | 非エンジニア | 利用者から見た変化を「〜できる」の形で |
| 5 | 含めたこと / 含めていないこと | 全員 | 今回の線引き。**食い違いを防ぐ最重要項目** |
| 6 | 技術的にやったこと | エンジニア | 変更の要点・設計判断・影響範囲 |
| 7 | 確認したこと | エンジニア | 実際に叩いた操作。「動作確認済み」だけは不可 |
| 8 | 注意・残課題 | 全員 | 既知の制約・後で直す約束。無ければ「なし」 |

3つの原則:

1. **§3は専門用語を1つも使わない**。「レスポンシブ対応した」ではなく「スマホでも文字が小さくならずに読めるようにした」。用語を使わずに説明できないなら、自分がその変更を理解しきれていない。
2. **§5「含めていないこと」を空欄にしない**。「頼んだのにできていない」という食い違いは、ほぼすべてここを書かなかったことが原因で起きる。やらないと決めたことは、なぜやらないかまで書く。
3. **未来の自分は他人である**。§6の「設計判断」は、3ヶ月後に「なぜこの実装にしたか」を思い出すための唯一の記録になる。他案を捨てた理由こそ書く。

詳細な記入例は `assets/pr-and-issue-templates.md`(実際にPR本文を書くときだけ開く)。

### レビュー(自分ひとりの場合)

マージ前に**自分のPRのDiffタブを必ず一度上から下まで見る**。エディタで書いているときとは別の視点になり、消し忘れのデバッグ出力・コメントアウトした旧コード・意図しないファイルの混入がここで見つかる。

```bash
gh pr diff --repo "$GITHUB_REPOSITORY"        # ターミナルで差分確認
gh pr view --repo "$GITHUB_REPOSITORY" --web  # ブラウザで確認
```

## §6. マージとリリース

```bash
gh pr merge --repo "$GITHUB_REPOSITORY" --squash --delete-branch
git switch "$GITHUB_DEFAULT_BRANCH"
git pull --rebase "$GIT_REMOTE" "$GITHUB_DEFAULT_BRANCH"
```

- **必ず `--squash`**。作業中の細かいコミットをmainに持ち込まない。mainの履歴が「PR1件 = 1コミット」に揃い、revertの単位と一致する。
- `--delete-branch` でリモート・ローカル両方のブランチを掃除する。残すと次に切るとき紛らわしい。
- デプロイを伴うリリースでは、本番URLでの確認が済んでからタグを打つ。

```bash
git tag v3 && git push "$GIT_REMOTE" v3
```

### 手元からデプロイするときの注意

`wrangler` は git のコミットではなく**その場の作業ツリー**をビルドする。「mainにマージしたから、mainの内容が公開される」とは限らない。実行直前に必ず確認する。

```bash
git status --porcelain   # 何も出ないこと
git diff --stat          # 何も出ないこと
```

この食い違いは、**公開を CI に任せれば構造的に消える**(まっさらなチェックアウトしか存在しないため)。設定方法は Skill `ci-cd-pipeline`。導入後は、手元からのデプロイは緊急時のみとする。

## §7. 取り消し(INV-6)

```bash
git log --oneline -10            # どのコミットまで戻すか特定
git revert <commit>              # 打ち消すコミットを新しく作る
git push
```

- squashマージ済みなら、PR1件がコミット1個なので `git revert` 1回で綺麗に戻る。これが§6で `--squash` を必須にする実利。
- `gh pr view --repo "$GITHUB_REPOSITORY" <番号>` でマージコミットのSHAを確認できる。
- **`git reset --hard` / `git push --force` は使用禁止**。履歴が消えると二度と戻せない。

## §8. やってはいけないこと

| 禁止 | 理由 |
|---|---|
| main への直接 push | 戻す単位が作れない。CIも通らない (例外は §0-2。v1 公開前のみ) |
| `git push --force` | 履歴が消える。個人開発では得るものがない |
| 1PRに複数の目的 | 片方だけ戻せなくなる |
| `.env` / 認証情報のコミット | push した時点で漏洩。history から消すのは困難 |
| 巨大PR(1000行超) | 自己レビューが機能しなくなる。機能単位で分割する |

## §9. コマンド早見表

```bash
# Issue
gh issue create --repo "$GITHUB_REPOSITORY" --web       # テンプレートを使って起票(推奨)
gh issue list --repo "$GITHUB_REPOSITORY" --state open
gh issue view --repo "$GITHUB_REPOSITORY" 12
gh issue edit --repo "$GITHUB_REPOSITORY" 12 --add-assignee @me

# ブランチ〜PR
git switch "$GITHUB_DEFAULT_BRANCH"
git pull --rebase "$GIT_REMOTE" "$GITHUB_DEFAULT_BRANCH"
git switch -c feat/12-xxx
git push -u "$GIT_REMOTE" "$(git branch --show-current)"
gh pr create --repo "$GITHUB_REPOSITORY" --title "feat: ..." --body-file .github/PULL_REQUEST_TEMPLATE.md
gh pr diff --repo "$GITHUB_REPOSITORY"
gh pr merge --repo "$GITHUB_REPOSITORY" --squash --delete-branch

# 状態確認
gh pr status --repo "$GITHUB_REPOSITORY"      # 自分のPRの状況
gh run list --repo "$GITHUB_REPOSITORY" -L 5 # CIの実行結果
git log --oneline -10
```

## §10. 依頼者に伝えるときの言葉

非エンジニアに報告するときはgit用語を使わない(app-orchestrator の語彙対応表に従う)。

| git用語 | 伝え方 |
|---|---|
| ブランチ作成 | 「今のアプリに影響しない作業スペースで進めます」 |
| PR作成 | 「変更内容の確認をお願いします(この画面で試せます)」 |
| マージ | 「確認いただいた内容を本番に反映しました」 |
| revert | 「1つ前の状態に戻しました」 |
