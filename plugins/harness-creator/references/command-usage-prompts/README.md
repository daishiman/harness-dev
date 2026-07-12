# コマンド用途プロンプト集（30思考法エレガント検証つき）

各パイプラインコマンドを「**① スラッシュコマンド入力 → ② その用途に合わせた構造化プロンプト**」の形でまとめた、そのまま貼って使えるプロンプト集。
② は参考雛形「思考リセット後に30種の思考法で多角的にエレガントさを検証・改善するプロンプト」(7層構造)を各コマンドの**検証対象**に合わせて構築したもの。**30思考法は全ファイルで全30種を使用**(機械検証済み)。

## 使い方

1. 対象コマンドのファイルを開く
2. **①** のスラッシュコマンドを打つ
3. コマンドの出力(生成物)に対し、**②** の7層プロンプトを Claude に渡し、思考リセット→30思考法並列分析→4条件検証→(改善) を回す

## 一覧

| ファイル | コマンド | 検証対象 | Phase3(改善) |
|---|---|---|---|
| `intake.md` | `/intake` | ヒアリング成果 (intake.json・5軸・真の目的) | 改善あり |
| `plugin-dev-plan.md` | `/plugin-dev-plan` | タスク仕様書 (component分解・依存DAG・task-graph デフォルト成果物・handoff routes) | 改善あり |
| `capability-build.md` | `/capability-build` | 構築実体 ↔ 仕様書 route の整合 | 改善あり |
| `capability-review.md` | `/capability-review` | 既存 capability | **提案のみ (analyse-only)** |
| `skill-improve.md` | `/skill-improve` | 既存 capability (in-place改善) | 改善あり (plan非再生成) |
| `run-skill-feedback.md` | `/run-skill-feedback` | 収集する改善要望 (schema準拠・対象同定) | **収集前セルフ検証のみ** |

## 共通骨格 (全ファイル共通)

- **30思考法**: 論理分析系5 / 構造分解系4 / メタ抽象系3 / 発想拡張系6 / システム系3 / 戦略価値系4 / 問題解決系5
- **4条件**: 矛盾なし / 漏れなし / 整合性あり / 依存関係整合
- **オーケストレーション**: Phase1 思考リセット・俯瞰(必須ゲート) → Phase2 3エージェント並列分析 → Phase3 改善実行/提案。最大反復3回。
- 変わるのは各コマンド固有の **検証対象** と **4条件の読み替え**、そして Phase3 が「改善実行」か「提案のみ」か。

## オプション表の保守 (SSOT 同期)

各ファイルの「① スラッシュコマンド入力」内の `### オプション` 表は、各コマンドの `commands/<cmd>.md` (frontmatter の argument-hint + 引数表) を**正本 (SSOT) とする写像**であり、ここは二次コピーである。①のコマンド例は代表用途のみを示し、全オプションの列挙は表側が担う。

**更新プロトコル (必須)**: オプション表を直す前に、必ず対応する正本を**最新の状態で読み直してから**反映する。正本側で新オプションの追加・改名・削除を見つけたら、当該ファイルの `### オプション` 表へ同じ変更を写す (二次コピーだけを勘で編集しない)。正本の無変更が確認できれば表は最新と一致とみなせる。

| 用途プロンプト | 正本 (SSOT) |
|---|---|
| `intake.md` | `plugins/skill-intake/commands/intake.md` |
| `plugin-dev-plan.md` | `plugins/plugin-dev-planner/commands/plugin-dev-plan.md` |
| `capability-build.md` | `plugins/harness-creator/commands/capability-build.md` |
| `capability-review.md` | `plugins/harness-creator/commands/capability-review.md` |
| `skill-improve.md` | `plugins/harness-creator/commands/skill-improve.md` |
| `run-skill-feedback.md` | (command 実体なし) `plugins/harness-creator/skills/run-skill-feedback/SKILL.md` |

> `run-skill-feedback` は command ファイルを持たない skill のため引数・オプションを取らない (対話起動)。SSOT は SKILL.md。

## 関連

- `../pipeline-command-reference.md` — コマンドの表記・実態・用途の一覧
- `../pipeline-boundary-contract.md` — E1/E2/E3/E4 境界契約
