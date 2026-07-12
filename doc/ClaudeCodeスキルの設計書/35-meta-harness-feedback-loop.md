# 35. Meta-Harness Feedback Loop

最終更新: 2026-05-18

## 目的

セッションログを根拠に `ref-*` Skill（および全 Skill）の `description` / 本文 / `gotchas` / `examples` を**統制ある形で**改善するパイプラインを定義する。

Stanford IRIS Lab の Meta-Harness（execution traces → harness end-to-end 最適化）と Hermes Agent（経験から Skill 自己生成）の問題意識に応えるが、**自己採点罠と Goodhart 罠の予防を最優先**とする。本章はそのための構造設計を提示する。

## 正本の分担

| 領域 | 正本 |
|---|---|
| 観測対象 failure mode の閉じた列挙 | `plugins/skill-governance-config/config/meta-harness-observables.json`（配布正本） / `.claude/config/meta-harness-observables.json`（導入先コピー） |
| ガバナンス境界（log由来改善のカテゴリ） | `33-change-governance.md` § log-driven ref-* 改善 |
| 改善の周回ロジック（既存の elegant-review 周回） | `plugins/harness-creator/skills/run-elegant-review/references/{amplified-patterns,convergence-policy}.json` |
| 本章で扱うこと | パイプライン全体（収集 → 分類 → 起票 → ガバナンス接続） |

## 中核原則

| 原則 | 意味 |
|---|---|
| **観測軸は閉じた列挙** | failure_modes は observables.json に列挙されたものに限る。追加は P0_breaking |
| **再現性しきい値** | 単一セッション観測で恒久ルール化しない（gotchas は最低3回横断） |
| **改善は P1_structural** | log 由来の ref-* 改善は P2 ではなく P1（自己採点罠予防） |
| **rationale に観測根拠** | log 由来改善の changelog は failure_mode ID と session_id を必須記載 |
| **観測スキーマの不変性** | スキーマ変更は P0_breaking（改善履歴の比較性が失われるため） |

## パイプライン全体図

```
[session logs (.claude/logs/*.jsonl)]
        │
        ▼
[1. collect]   ── 機械収集（hook or 後処理）
        │
        ▼
[2. classify]  ── observables.json の failure_modes と照合
        │
        ▼
[3. accumulate] ── min_recurrence_for_action しきい値判定
        │
        ▼
[4. propose]   ── ref-* 改善 PR 起票（人間レビュー前提）
        │
        ▼
[5. govern]    ── 33章 P1_structural ワークフローに接続
        │
        ▼
[changelog 記録 + Skill 更新]
```

## Phase 別ロードマップ

| Phase | スコープ | 入口ゲート | 出口ゲート |
|---|---|---|---|
| **Phase 0** | observables 列挙確定 + ガバナンス境界定義 | （前提なし） | `.claude/config/meta-harness-observables.json` 初版完成 + 33章 § log-driven 節 |
| **Phase 1** | ログ収集機構（.claude/logs/ スキーマ + collect hook） | Phase 0 完了 | skill-governance-config plugin manifest 登録 + スキーマ v1.0 確定 + 収集スクリプト配置 + **実ログ蓄積 ≥ 1 セッション** |
| **Phase 2** | classify + accumulate（observables との突合・カウント蓄積） | Phase 1 実装完了 + 実ログ蓄積 ≥ 1 セッション + 7日以上のログ蓄積 | failure_mode 別に閾値超え検出が機械実行できる |
| **Phase 3** | propose（改善 PR 自動起票） | Phase 2 完了 + 誤検出率 < 20% の検証 | ref-* 改善 PR が drafts として自動生成される |
| **Phase 4** | govern 接続（33章 P1_structural ワークフロー自動連結） | Phase 3 完了 + 3件以上の手動 PR 経験 | classify_change が log 起源 PR を P1 として自動分類 |

**現在地**: Phase 1 実装完了・実ログ蓄積待機中（スキーマ v1.0 確定 + `plugins/skill-governance-automation/scripts/extract-session-events.py` 配置 + hook example + manifest 登録 + .gitignore）。Phase 2 開始ゲート: 実ログ蓄積 ≥ 1 セッション（未達）。Phase 2 (classify + accumulate) は実ログ蓄積達成後に着手。

## ログスキーマ v1.0（Phase 1 確定）

配布正本: `plugins/skill-governance-config/config/meta-harness-log-schema-v1.0.json`。導入先コピー: `.claude/logs/schema-v1.0.json`。スキーマ変更は P0_breaking（33章 § log-driven ref-* 改善）。

### 構成

| field | type | event 共通/個別 | 用途 |
|---|---|---|---|
| `schema_version` | string | 共通（const "1.0"） | スキーマ互換性 |
| `ts` | ISO8601 string | 共通 | turn 内/turn 間判定 |
| `session_id` | string | 共通 | cross-session 集計の主キー |
| `event` | enum: user_prompt/tool_use/stop | 共通 | event 種別 |
| `text` | string (≤2000) | user_prompt | 発動語/follow-up/境界条件の照合対象 |
| `tool_name`, `skill_invoked`, `skill`, `success` | string/bool | tool_use | 発動有無・誤発動判定 |
| `reason` | string | stop | 中断要因の付帯情報 |

### 収集機構（opt-in）

- スクリプト: `plugins/skill-governance-automation/scripts/extract-session-events.py`（install後は `scripts/extract-session-events.py`。28章 §4 動詞 `extract` 準拠）
- hook 登録例: `plugins/skill-governance-config/config/meta-harness-hooks.json.example`（install後は `.claude/settings.meta-harness-hooks.json.example`。UserPromptSubmit / PostToolUse / Stop の3点）
- 出力先: `.claude/logs/<YYYY-MM-DD>.jsonl`（`.claude/logs/.gitignore` で git 追跡除外）

### observables との対応

`.claude/logs/schema-v1.0.json` の `observable_mapping` を正本とする。各 failure mode の `observable_signal` は本スキーマ上で**全て機械観測可能**であることを保証する（Phase 1 出口ゲートの達成条件）。

#### failure_mode: `pkg_check_failed`（36章連動、2026-05-20 追加）

36章 PKG-001〜017（PKG-013 分割後の 013a〜d、および将来の 016/017 を含む）のいずれかの gate が fail した時に発火する failure_mode。observables.json への追加は P0_breaking（本章 中核原則「観測軸は閉じた列挙」）。

| field | 内容 |
|---|---|
| `failure_mode_id` | `pkg_check_failed` |
| `observable_signal` | 34章 Phase 0/1/2 ゲートで実行される PKG gate script の exit code（非ゼロ）。eval-log 保存先は `eval-log/<plugin>/pkg-<id>/`（27章 §3.1） |
| 観測指標 | (1) PKG ID 別 fail 件数、(2) 同一 plugin × 同一 PKG ID での再発率、(3) fail 発生から修正 merge までの平均解決時間 |
| min_recurrence_for_action | 1（P0 gate のため即時起票。gotchas のしきい値とは別ルール） |
| 起票先 | 36章 §現状との差分（PKG ID 改廃が必要な場合は 36章 + 27章 §4 governance） |

#### failure_mode: `elegant_review_4condition_failed`（run-elegant-review v2 連動、2026-05-23 追加）

`run-elegant-review` v2（25章 §runbook Step 5.5）の Phase 3 完了時、検証 4 条件（矛盾なし / 漏れなし / 整合性あり / 依存関係整合）のいずれかが FAIL した場合、または max_iterations(=3) 到達による安全弁発火（`safety_valve_fired=true`）時に発火する failure_mode。observables.json への追加は P0_breaking。

| field | 内容 |
|---|---|
| `failure_mode_id` | `elegant_review_4condition_failed` |
| `observable_signal` | `scripts/emit-observable.py` が `verdict.json`（`schemas/verdict.schema.json` 準拠）から `verdict.*=FAIL` または `safety_valve_fired=true` を検出し、`.claude/logs/meta-harness.jsonl` に 1 行 append。eval-log 保存先は `eval-log/<plugin>/<skill>/elegant-review/<run-id>/`（27章 §3.1） |
| 観測指標 | (1) 4 条件別 fail 件数（contradiction/omission/inconsistency/dependency_break）、(2) 同一 plugin × 同一 skill での再発率、(3) `iteration_count` 分布（収束効率）、(4) `safety_valve_fired` 比率 |
| min_recurrence_for_action | 1（設計 elegance gate のため即時起票。3 周回 max は安全弁であり成功扱いにしない） |
| 起票先 | 30章 paradigm-analogy-map（思考法カタログ改廃）+ 27章 §4 rubric governance（rubric 強化が必要な場合） |
| Goodhart 予防 | force_pass 禁止（max_iter 到達は failure 扱い）、proposer ≠ approver（23章）、Phase 1/2 read-only 強制 |

### Phase 1 出口判定

- [x] スキーマ v1.0 確定（本節）
- [x] 収集スクリプト動作確認（stdin JSON → jsonl 追記）
- [x] hook 登録 example 配置（opt-in）
- [x] skill-governance-config plugin manifest 登録
- [x] gitignore でログ実体を git から除外
- [ ] 1セッション以上の実ログ蓄積（運用フェーズで達成）

## Goodhart 罠の予防（再強調）

ログを観測対象に組み込むと、以下のいずれかが必然的に発生する。本章はこれらを構造で予防する:

| 罠 | 予防策 |
|---|---|
| ログ映えする発動の最適化 | observables を**閉じた列挙**に固定。追加は P0_breaking |
| 偶発事象の恒久ルール化 | `min_recurrence_for_action` を性質ごとに設定（gotchas≥3） |
| 自己採点罠（自分のログで自分を採点） | log 由来改善は P1_structural（27章の自己採点禁則と同型） |
| 観測軸の振動 | スキーマ変更を P0_breaking 化。改善履歴の比較性を保護 |

## PKG gate 連動の閉ループ（36章 ⇔ 本章 ⇔ 27章）

34章 Phase 0/1/2 ゲートで実行される 36章 PKG-001〜017 gate が fail した場合、(1) eval-log は 27章 §3.1 規約の `eval-log/<plugin>/pkg-<id>/` に保存され、(2) 本章 collect → classify ステップで `pkg_check_failed` failure_mode として観測カウントが蓄積され、(3) 蓄積結果は 36章 §現状との差分（PKG ID 改廃案の根拠）に feedback される。これにより 36章で導入された片道リンクが閉じ、PKG check が落ちても誰も観測しない single point of failure を解消する。PKG ID 改廃を伴う改善は本章単独では起票せず、必ず 36章正本 + 27章 §4 rubric governance の承認経路を経る。

## elegant-review v2 連動の閉ループ（25章 ⇔ 本章 ⇔ 30章）

25章 §runbook Step 5.5 で実行される `run-elegant-review` v2 の Phase 3 完了時に 4 条件のいずれかが FAIL すると、(1) verdict は `eval-log/<plugin>/<skill>/elegant-review/<run-id>/verdict.json` に保存され、(2) `scripts/emit-observable.py` が `elegant_review_4condition_failed` event を `.claude/logs/meta-harness.jsonl` に append、(3) 本章 collect → classify ステップで観測カウントが蓄積され、(4) 蓄積結果は 30章 paradigm-analogy-map（思考法カタログ改廃）および `run-elegant-review/references/thought-methods.yaml` 改訂の根拠に feedback される。これにより 25章 Step 5.5 で elegance lint が落ちても誰も観測しない single point of failure を解消し、PKG check（契約適合）と並列に設計 elegance（構造適合）を可視化する。思考法カタログ改廃を伴う改善は本章単独では起票せず、必ず 30章正本 + 27章 §4 rubric governance の承認経路を経る。

## 既存メカニズムとの関係

| 既存 | 本章との関係 |
|---|---|
| `run-elegant-review/references/amplified-patterns.json` (P001-P004) | **elegant-review 周回内の正FB**。本章は**周回を跨ぐ（cross-session）正負FB** |
| `run-elegant-review/references/convergence-policy.json` (C1-C4) | elegant-review の収束ポリシー。本章 propose 段階で参照可能 |
| 24章 SKILL.md テンプレの `gotchas` セクション | 静的記述。本章は gotchas を**観測根拠付きで動的更新**する経路 |
| 27章 rubric-governance | Skill 品質を rubric で評価。本章は rubric では捉えにくい**発動条件と判断材料**を補完 |
| 33章 change-governance | 本章は 33章のワークフローを**log 起源変更にも適用**する経路 |

## 反パターン

| 反パターン | リスク | 予防 |
|---|---|---|
| ログ収集を先に作って observables 未確定運用 | 観測軸が振動、改善方向が定まらない | Phase 0 ゲートで遮断 |
| observables を無制限に追加 | Goodhart 罠 | 追加を P0_breaking 化 |
| 単一セッション観測で description 即変更 | 偶発事象の恒久化 | `min_recurrence_for_action` 必須参照 |
| log 由来改善を P2_content として処理 | 自己採点罠 | 33章ルールで P1_structural 固定 |
| ログを KPI 化して数値最適化 | Skill本来の目的が侵食される | rationale で改善の質的根拠を必須化 |
| 観測スキーマを軽率に変更 | 改善履歴の比較性喪失 | スキーマ変更を P0_breaking 化 |

## reflective loop の Capability 用語による再記述 (2026-05-22)

23章 § Capability 抽象への拡張 で導入した **Capability / CapabilityBundle / CapabilityManifest / CapabilityContract** 用語に基づき、本章のパイプラインを kind 横断の reflective loop として再定式化する。従来 Skill 限定で書かれた本章の改善経路は、Agent / Hook / Command / Plugin-Composition / Prompt / Workflow へも汎用に適用される。

### reflective loop の正本定義

```
intake → build → review → lessons-learned → rubric-governance → 次回 build
```

| 段 | Capability 用語での意味 | 対象 kind | 具体実装 |
|---|---|---|---|
| **intake** | ユーザー要求 → CapabilityManifest 雛形生成 | 全 kind | `run-skill-elicit` (skill), `prompt-creator` (prompt), 等 |
| **build** | CapabilityManifest + 三層 contract 生成 | 全 kind | `run-build-skill` 等の generator |
| **review** | 生成された Capability の rubric 採点 (kind 別 rubric) | 全 kind | `assign-*-evaluator` + `run-elegant-review` |
| **lessons-learned** | failure_mode の bundle 直下蓄積 | bundle 単位 | bundle 直下 `lessons-learned/` |
| **rubric-governance** | EVALS → rubric 改正 PR 自動化 | kind 別 rubric | 27章 + 33章 § CapabilityBundle governance (3) EVALS → rubric 自動 PR 経路 |
| **次回 build** | 改訂 rubric が次回 build 時に強制 | 全 kind | reflective closure |

### 具体実装の参照

| 機構 | 役割 | 正本パス |
|---|---|---|
| **auto-record-lesson hook** | review 完了時に failure_mode を bundle 直下 `lessons-learned/` へ自動追記 | (Phase 3 で実装予定。PostToolUse hook として `plugins/harness-creator/.claude-plugin/plugin.json` または独立 `kind: hook` manifest に登録) |
| **aggregate-evals script** | bundle 直下 `EVALS.json` を時系列集計し、閾値超え failure_mode を検出 | `plugins/skill-governance-automation/scripts/aggregate-evals.py` (Phase 2 で実装予定) |
| **observables.json** | 閉じた failure_mode 列挙 | `plugins/skill-governance-config/config/meta-harness-observables.json` / `.claude/config/meta-harness-observables.json` |
| **log schema v1.0** | session log の正本スキーマ | `plugins/skill-governance-config/config/meta-harness-log-schema-v1.0.json` / `.claude/logs/schema-v1.0.json` |
| **extract-session-events.py** | UserPromptSubmit / PostToolUse / Stop を jsonl に追記 | `plugins/skill-governance-automation/scripts/extract-session-events.py` |

### Capability 用語でのループ閉鎖条件

reflective loop が閉じる (= 同じ failure_mode が再発しない状態に収束する) ための機械検証条件は以下:

1. **CapabilityContract の invariant 強化**: failure_mode が再発した場合、対象 Capability の invariant (rubric) を強化する PR が EVALS → rubric 自動 PR 経路で起票される
2. **CapabilityBundle 直下の三点蓄積**: `EVALS.json` + `changelog/` + `lessons-learned/` が bundle 直下で揃っており、次回 build 時に必ず読み込まれる (23a § 5 を bundle 単位に拡張)
3. **composition lint PASS**: bundle 全体の DAG / rubric_refs / hooks 配線が PostToolUse hook で機械検証される (33章 § composition lint)

### kind 別 reflective loop の差分

| kind | failure_mode の主な観測点 | 改訂対象 |
|---|---|---|
| `skill` | description 未発動 / 出力不十分 | description + 本文 + gotchas |
| `agent` | system_prompt 不整合 / tools 漏れ | system_prompt + tools 許可リスト |
| `hook` | trigger 漏れ / 副作用越境 | event/matcher 条件 + 副作用境界宣言 |
| `command` | 引数 schema 不一致 | argument schema + 出力フォーマット |
| `plugin-composition` | DAG 断裂 / governance 配線漏れ | `dependencies` / `governance.rubric_refs` |
| `prompt` | layer 欠落 / output schema 違反 | 7層 markdown 骨格 + expected output schema |
| `workflow` | gate 通過漏れ / handoff 型不整合 | phases / gates / schemas |

### Goodhart 罠の Capability 横断的予防

Capability 抽象を導入することで、本章既存の Goodhart 罠予防策は **kind 横断で機械強制** できる:

| 予防策 | Capability 抽象での強化点 |
|---|---|
| 観測軸は閉じた列挙 | observables.json の `failure_modes` を `kind` で分類 (追加は P0_breaking 維持) |
| 再現性しきい値 | `min_recurrence_for_action` を kind 別に設定可能化 |
| 改善は P1_structural | 33章 § CapabilityBundle governance MECE 表で kind 横断に固定 |
| rationale に観測根拠 | EVALS → rubric 自動 PR の rationale に `failure_mode ID + session_id + capability_name + kind` を必須化 |
| 観測スキーマの不変性 | log schema v1.0 + observables.json + `plugin-composition.yaml` の `observability` フィールドが**三位一体で不変**。いずれの変更も P0_breaking |

### 関連章 (再掲)

- 23章 § Capability 抽象への拡張: 統一抽象の定義 + 三層 contract 横断写像表
- 23a章: 三層 contract モデル (本章 reflective loop が改訂対象とする正本構造)
- 27章: rubric governance (EVALS → rubric 自動 PR の起点)
- 33章 § CapabilityBundle governance: 自動 PR 経路 3 点 + composition lint
- 34a章 §13: hook の Capability 化 (auto-record-lesson hook の登録経路)

## 3 層メタモデル (META-001)

reflective loop は 3 層に分解できる。Phase 3 で追加された emit_observable step はこの 3 層の Layer 2 ↔ Layer 3 を結線する。

| 層 | 名称 | 役割 | 具体実装 |
|---|---|---|---|
| Layer 1 | Object-level (対象 Skill) | 直接の Capability 実行 | 各 Skill の business logic |
| Layer 2 | Review-level (品質ゲート) | C1-C4 / PKG / rubric 採点 | `run-elegant-review` / `run-plugin-package-check` / `assign-skill-design-evaluator` |
| Layer 3 | Meta-level (収束ガバナンス) | failure_mode 蓄積 → rubric 改訂 | 本章 + 27章 + 33章 |

## observable 形式選定理由 (BRAIN-001)

JSONL append 1 行を採用した理由は (1) 並行書き込み安全性 (append-only)、(2) tail/jq による cross-session 集計の容易さ、(3) schema_version によるスキーマ互換性確保、の 3 点。SQLite 等の構造化 store は採用しなかった (toolchain 依存増・grep 不能を回避)。

## safety_valve_fired の独立観測 (F-0010)

`safety_valve_fired=true` は verdict.* が全 PASS であっても observable emit を強制する。これは max_iterations 到達 = 自動収束失敗の構造的シグナルであり、見かけ上の PASS を Goodhart 罠として隠蔽しないため。`scripts/emit-observable.py` 内の判定 `not failed and not verdict.get("safety_valve_fired")` で実装済。

## rate-limit (F-0008 strategic)

同一 plugin × skill × failed_condition の組合せでの自動 PR 起票は **7 日 / 1 PR** に制限する。連続発火時は 2 回目以降を既存 issue にコメント追記し、新規 PR を抑止する。これは Goodhart 罠（観測軸の振動）と PR ノイズ増殖を予防するため。

## 更新ルール

1. observables.json の `failure_modes` を変更する場合、本章「現在地」と 33章 § log-driven 節を同時更新する
2. Phase 進捗があった場合、本章「Phase 別ロードマップ」の出口ゲート判定と「現在地」を更新する
3. ログスキーマを変更する場合、本章「ログスキーマ」セクションを正本確定版に書き換え、changelog に P0_breaking として記録する
4. 本章を変更する場合、自分自身が P1_structural になる（33章自己適用ルール）
5. Capability 用語の写像表 (kind 別 reflective loop) を変更する場合、23章 § Capability 抽象への拡張 の横断適用表と同時更新する
