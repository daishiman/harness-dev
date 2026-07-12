/skill-improve
# /skill-improve 用途プロンプト（30思考法エレガント検証→改善実行）

## ① スラッシュコマンド入力

まずこれを打つ。

```
/skill-improve <capability-path>
```

例:

```
/skill-improve plugins/company-master/skills/run-company-master-build
```

```
/skill-improve plugins/harness-creator/agents/elegant-reset-observer.md
```

実態: `command → run-elegant-review (Phase1-3) → elegant-improvement-executor` を自動チェイン。レビューと**その場改善(in-place)**を1コマンドで完結させる近道。

---

### オプション

`/skill-improve` の全オプション（正本 = `commands/skill-improve.md`）:

| オプション | 何を入れるか | 用途 |
|---|---|---|
| `capability-path`（必須） | 改善対象の skill/agent/hook/command パス | レビュー→改善→再レビューを最大 3 周自動実行 |

> オプションは 1 つのみ。**破壊的変更**を行うため事前に git commit clean 推奨。plan 正本を保ちたい改善は in-place でなく `/plugin-dev-plan --mode update --improvement-handoff <handoff>` 経由（②Layer1 の注記参照）。

## ② 構造化プロンプト（説明）

### Layer 1: 基本定義層（不変原則）

- 対象: `<capability-path>` で指定された既存 skill / agent / hook / command 1件（以下「対象capability」）。
- 目的: 対象capabilityを思考リセット後に30思考法で多角的検証し、4条件PASSまで**その場で改善実行**する。
- 位置づけ: `/capability-review` はレビューのみ（改善しない・dry-run）。`/skill-improve` はレビュー→改善実行まで進める点で異なる。
- CONST_001: リセット＝直前contextの**クリア**であり対象ファイルの削除ではない。Phase1は観察専用・write禁止。
- CONST_002: 30種全使用省略禁止。使用不能な思考法は `skip_reason` 必須記録、`used + skipped_with_reason == 30` に到達させる。
- CONST_003: 4条件（矛盾なし／漏れなし／整合性あり／依存関係整合）を全PASSまで反復する。未達のまま完了扱い（force_pass）は禁止。
- **重要な注記（plan非再生成 / task-graph 非還流）**: 本コマンドは**in-placeパッチ**であり、タスク仕様書（plan）も**その `task-graph.json`（成果物の第一級・依存グラフ駆動の正本）も更新されない**。plan 正本を保ち、改善を **task-graph へ還流**したい場合は `/plugin-dev-plan --mode update --improvement-handoff <handoff>` 経由を使う。この経路は改善を task-graph へ反映し、次回 `/capability-build --handoff`（既定=task-graph route モード）が改善済み依存グラフで再駆動する（＝spec-improvement 外ループ）。in-place は速い代わりに task-graph と乖離しうる点に注意（乖離が問題になる改善は plan 経路へ）。

### Layer 2: ドメイン定義層

#### 2.1 用語集
| 用語 | 意味 |
|---|---|
| `capability-path` | 改善対象の skill/agent/hook/command の相対パス |
| `findings.json` | 30思考法分析の集約結果（`paradigm_findings[]` + `variable_abstraction` + `four_conditions`） |
| `severity` | finding の優先度（low/medium/high/critical、Agent5のパッチ順序を決める） |
| `condition_signal` | 4条件の機械観測signal（contradiction/omission/inconsistency/dependency_break、警告枠smell） |
| `convergence_status` | 収束判定（complete/in_progress/diverging/human_escalate/incomplete） |
| `auto_fixable` | 単純パス修正/chmod等のみtrue。意味変更を伴う修正は必ずfalse |
| `shared_state.md` | Phase1→2の中継（200字以内、context肥大防止） |

#### 2.2 30思考法カタログ（7カテゴリ・全30種・詳細1行観点はLayer5）
論理分析系(5)／構造分解系(4)／メタ抽象系(3)／発想拡張系(6)／システム系(3)／戦略価値系(4)／問題解決系(5) = 計30。

#### 2.3 検証4条件
| # | 条件 | condition_signal |
|---|---|---|
| C1 | 矛盾なし | contradiction |
| C2 | 漏れなし | omission |
| C3 | 整合性あり | inconsistency |
| C4 | 依存関係整合 | dependency_break |

### Layer 3: インフラストラクチャ定義層

- **Agent Team並列実行**: Phase2の3 Agent（論理構造／メタ発想／システム戦略問題解決）は互いの中間出力を参照せず独立並列で起動する。
- **Codex委譲**（Phase3限定、Phase1/2中の委譲は禁止＝context再汚染）: 変更行数 > 50 ／ テスト変更を含む ／ 複数ファイル横断（unique file数 > 3）のいずれかで `delegate-codex-skill-review` へ委譲。
- 利用ツール: Read/Write/Edit/Grep/Glob/Bash(python3 *)/Bash(git diff *)。
- 参照artifact: `findings.json` / `verdict.json` / `eval-log/<plugin>/<skill>/elegant-review/<run-id>/`。

### Layer 4: 共通ポリシー層

- 30思考法は全種使用（省略時はCONST_002のskip_reasonのみ許容）。
- 改善パッチは必ず**根拠となった思考法とfinding**を明示して紐付ける（どのAgent・どの思考法由来か遡れること）。
- 4条件は全PASSまで反復。未達をforce_passで握り潰すことは禁止。
- エスカレーション: `iteration_count >= 3`（安全弁）で `status: incomplete` + `human_review` 必須。Δneg（負フィードバック）が2周連続増加＝発散なら `human_escalate`。
- plan/task-graph 整合性の注意: in-place 改善は plan も `task-graph.json` も更新しない。plan 正本・task-graph 還流を維持したい改善は `/plugin-dev-plan --mode update` 経由へ誘導する（task-graph へ反映され、次回 `/capability-build --handoff` が改善済み依存グラフで再駆動する）。

### Layer 5: エージェント定義層（ゴール駆動の実行主体）

#### Agent1（思考リセット俯瞰）
対象capabilityを評価せず観察のみ行う。`purpose / scope / stakeholders / first_impressions / facts_vs_assumptions / concrete_values_to_abstract` を出力し `shared_state.md`（200字以内）を生成する。

#### Agent2（論理構造：9思考法）
| 思考法 | 対象capabilityでの1行観点 |
|---|---|
| 批判的思考 | SKILL.md/frontmatterが謳う責務と実装(scripts/prompts/agents)の一致を疑う |
| 演繹思考 | 7層/ゴールシーク契約を満たす前提から各節が論理必然的に導けるか検算する |
| 帰納的思考 | 類似capabilityの過去改善事例から起こりやすい欠陥パターンを推定する |
| アブダクション | 挙動不備の観察から最も説明力のある原因仮説を1つ立てる |
| 垂直思考 | 表層の文言修正で止めず責務定義・入出力契約の根本まで掘り下げる |
| 要素分解 | frontmatter/本文Layer/参照scripts/schemasへ分解し単一責務を点検する |
| MECE | 入出力・検証・エラー処理の機能一覧に抜け漏れ・重複がないか棚卸しする |
| 2軸思考 | 「変更の重大度×可逆性」で改善候補を分類しin-place可否を判断する |
| プロセス思考 | レビュー→改善→再検証の手順順序とゲートが明確に定義されているか確認する |

#### Agent3（メタ発想：9思考法）
| 思考法 | 対象capabilityでの1行観点 |
|---|---|
| メタ思考 | いま適用している4条件/rubric自体がこの対象の性質に合っているか問い直す |
| 抽象化思考 | 個別欠陥を1段抽象化し他capabilityへ横展開できるパターンか見極める |
| ダブル・ループ思考 | 表層バグ修正でなく対象の目的設定・スコープ自体を見直すべきか検討する |
| ブレインストーミング | 改善案を批判保留でまず複数出し早期に1案へ収束させない |
| 水平思考 | 直接パッチ以外に参照ドキュメント移設や責務分割など既存枠外の解を探る |
| 逆説思考 | 「最小パッチ」と「本質改善」が同時に成立する変更範囲を探る |
| 類推思考 | 直近のin-place改善成功事例の構造を借用できないか検討する |
| if思考 | もしplanに紐づく変更だったら破綻しないか、in-place限定の前提を極端条件で確かめる |
| 素人思考 | 初見の利用者がSKILL.md/コマンドだけで目的・完了条件を理解できるか確認する |

#### Agent4（システム戦略問題解決：12思考法）
| 思考法 | 対象capabilityでの1行観点 |
|---|---|
| システム思考 | capability単体でなくplugin全体（呼び出し元・下流）への波及効果を捉える |
| 因果関係分析 | findingの表層原因（誤字・欠落）と真の原因（設計欠陥）を混同していないか検証する |
| 因果ループ | 今回の改善が別の品質低下（例: 検証scriptの過検出）を誘発するループがないか確認する |
| トレードオン思考 | 速度（1コマンド即時改善）と正本性（planとの整合）を同時に満たす条件を設計する |
| プラスサム思考 | 改善が実行者だけでなく後続利用者・下流skillにも価値が増える選択か確認する |
| 価値提案思考 | 利用者が期待する成功状態（改善済みcapabilityが安全に動く）と出力契約が一致しているか見る |
| 戦略的思考 | 限られた反復回数（最大3周）をどの4条件違反に優先配分すべきか判断する |
| why思考 | なぜこの欠陥が生まれたかを繰り返し掘り下げ直接原因でなく真因まで特定する |
| 改善思考 | 小さく検証可能な最小パッチ単位に改善を分割し一括変更を避ける |
| 仮説思考 | 「この修正で4条件がPASSする」仮説を立て最小コストで検証できる順に適用する |
| 論点思考 | いま解くべき真の論点（plan再生成が必要かin-place十分か）を明確にしてから着手する |
| KJ法 | 3並列Agentから集まったfindingsをグルーピングし重複・関連を整理して優先順位付けする |

#### Agent5（改善実行）
severity（critical>high>medium>low）順に、依存DAGで独立分は並列・依存分は直列で最小パッチを適用。`auto_fixable=true` は自動適用、`false` は提案のみ。適用後に4条件を再検証し、全PASSまたは`iteration_count>=3`到達まで反復。proposer≠approver（自己承認禁止・別SubAgentまたは人間が承認）。

### Layer 6: オーケストレーション層

```
Phase1 リセット俯瞰(必須ゲート・スキップ不可)
   → Agent1 が shared_state.md を出力
Phase2 3並列分析ゲート
   → Agent2/3/4 が並列独立実行、完了判定 = 3 Agent完了 かつ used+skipped_with_reason==30
Phase3 改善実行
   → severity順パッチ → 4条件再検証
   → 全PASSなら完了 / 未PASSならPhase2へ再ループ(最大3周) / 3周超過でhuman_escalate
```

### Layer 7: UI / 提示層

**ユーザー提示**: まず①を実行し、対象に 思考リセット→30思考法並列分析→4条件検証→改善実行→4条件再検証 を回す。plan正本維持が要る改善は `/plugin-dev-plan --mode update` 経由。
次の内容を元に実行してください。@
