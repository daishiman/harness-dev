# 01a. Skill 作成フロー

## 全体フロー

```text
問題定義
  -> 実行レイヤー判断
  -> 分類
  -> 命名
  -> frontmatter
  -> 本文
  -> 補助ファイル
  -> 権限・Hook
  -> 検証
  -> 運用改善
```

## Step 1. 問題定義

1 文で書く。

```text
この Skill は、何度も貼っている PR レビュー観点を再利用可能にする。
```

避ける表現:

- 便利にする
- 高品質にする
- なんでも確認する

詳細: [02-claude-code-skill-spec.md](02-claude-code-skill-spec.md) で Skill の定義と公式 spec を確認する。

## Step 2. 実行レイヤー判断

| 問い | Yes の置き場所 |
|---|---|
| 決定論で落とせるか | Hook / CI / CLI |
| 外部 system 接続が主か | MCP / CLI / API |
| 別 context が必要か | Subagent |
| 複数 session の協調が必要か | Agent Team |
| 運用知識・手順が主か | Skill |

詳細: [05-layering-skill-subagent-hook-mcp-cli.md](05-layering-skill-subagent-hook-mcp-cli.md) で Skill / Subagent / Hook / MCP / CLI の使い分けを確認する。

## Step 3. 分類

### 3a. prefix（Trigger 軸 = 誰が呼ぶか） — 5 つで固定

prefix は **Trigger 軸** の表現であり、値は 5 個に閉じる（増やさない）。

| 問い | 値 | Trigger 軸の値 |
|---|---|---|
| 知識だけ・自動発動禁止か | `ref-*` | claude が read のみ |
| user が直接実行する workflow か | `run-*` | user-invocable |
| 既存 Skill の **preset / 派生** か | `wrap-*` | user-invocable + base 継承 |
| 内部 worker（forked context）か | `assign-*` | parent Skill から呼ばれる |
| 外部 LLM / 別 agent への委譲か | `delegate-*` | user-invocable + 外部 agent |

**prefix を増やしたくなったら役割を疑う**: `lint-*` / `hook-*` / `mcp-*` を作りたくなる衝動は、ほぼ常に **scripts/ や settings.json で表現すべき**（Skill にしない）。28 章「script 実行モデル」を参照。

### 3b. role-suffix（Role 軸 = 内部で何をするか） — 拡張点はここ

精度を上げたい場合は、prefix ではなく **role-suffix** の語彙を増やす。これにより Trigger 軸を保ったまま、内部役割を細分化できる。

| role-suffix | 用途 | 主に組み合わさる prefix |
|---|---|---|
| `-generator` | artifact を生成する | `assign-*-generator` |
| `-evaluator` | 生成物を採点・判定する | `assign-*-evaluator` |
| `-linter` | 決定論的検査（pass/fail のみ） | `assign-*-linter` |
| `-auditor` | 既存資産を監査・report 出力 | `assign-*-auditor` / `run-*-auditor` |
| `-aggregator` | 複数 source を集約・要約 | `assign-*-aggregator` |
| `-runbook` | 手順書として実行 | `run-*-runbook` |
| `-watcher` | trigger 検出・通知のみ | `assign-*-watcher` |
| `-dispatcher` | 他 Skill に振り分け | `run-*-dispatcher` |

**新しい role-suffix を増やす条件**: 同一 prefix の中で 3 つ以上の Skill が同じ役割を担い始めたら、role-suffix を新設して語彙化する（governance ボード承認、27 章）。

### 3c. 細分化を促す閾値ルール

1 つの Skill に役割を詰め込みすぎないため、以下のいずれかを満たしたら **Skill を分割**:

| 指標 | 閾値 | 分割の方向 |
|---|---|---|
| SKILL.md 本文 | > 300 行 | references/ 分離 → それでも溢れたら子 Skill |
| 同一 Skill 内の独立フロー | ≥ 2 個 | 各フローを別 Skill に |
| allowed-tools の権限カテゴリ | ≥ 3 種類 | 権限境界で分割（04 章 最小権限） |
| 評価軸（rubric） | ≥ 2 個 | evaluator を分割（or rubric_refs で合成） |

詳細: [06-classification-and-naming.md](06-classification-and-naming.md) で 5 prefix の判定基準と role-suffix 語彙の正本を確認する。Skill にせず別レイヤーで解く判定は [05-layering-skill-subagent-hook-mcp-cli.md](05-layering-skill-subagent-hook-mcp-cli.md) を参照。

## Step 4. 命名

prefix から契約を決める。**ただし「domain segment 1個だけ」は知識爆発時に精度劣化を招くため、原則は 2〜3 segment（`<prefix>-<topic>-<subtopic>`）。**

### 4a. 良い例 / 悪い例（曖昧さの自覚）

| 名前 | 評価 | 理由 |
|---|---|---|
| `ref-api-conventions` | **△ 暫定** | どの API か不明（REST? GraphQL? gRPC? 社内? Project X?）。本文 100 行以内・トピック 1 個に限る場合のみ許容 |
| `ref-api-rest-conventions` | ◯ | technology が明確 |
| `ref-api-project-x-conventions` | ◯ | bounded context が明確 |
| `run-release-check` | △ | どの release か（mobile? backend?）。単一 repo・単一サービスなら可 |
| `run-release-mobile-check` | ◯ | scope 明示 |
| `wrap-team-thumbnail` | △ | thumbnail の何を wrap？ `wrap-team-thumbnail-uploader` 等で動詞補強 |
| `assign-skill-review-evaluator` | ◎ | prefix + domain + role-suffix が揃っている（第5条準拠） |
| `delegate-codex-review` | △ | review 対象不明。`delegate-codex-skill-review` のように対象を入れる |

### 4b. 細分化（subdivision）の閾値ルール

ref-* / wrap-* が**以下のいずれかを満たしたら必ず細分化**:

| 指標 | 閾値 | 理由 |
|---|---|---|
| `references/` 配下の総行数 | > 2,000 行 | LLM が探索しきれず精度↓（Progressive Disclosure 破綻） |
| 扱う**独立トピック数** | ≥ 3 個 | 1 Skill = 1 Bounded Context が原則（DDD） |
| 異なる **technology / framework** を内包 | ≥ 2 個 | REST と GraphQL を 1 Skill にしない |
| 異なる **プロジェクト固有ルール** | ≥ 2 個 | L1 共通基準と L2 案件特化を分離（29 章 rubric_refs） |

細分化は **L0/L1/L2 階層**で行う:

```text
L0 共通基準:    ref-api-conventions              (HTTP method / status code 等 全API共通)
L1 ドメイン特化: ref-api-rest-conventions        (REST固有: resource oriented)
                ref-api-graphql-conventions     (GraphQL固有: schema first)
L2 案件固有:    ref-api-project-x-conventions   (Project X の auth / pagination)
```

L0 を直接読み込まず、L1/L2 から `rubric_refs` / `reference_refs` で参照させる。これで L0 の共通改正が L1/L2 へ自動波及し、L0 ← L1 ← L2 の **一方向依存** が保たれる（29 章）。

### 4c. 命名から契約を読み取れるかセルフチェック

新規 Skill 名を見た第三者が、SKILL.md を読まずに次に答えられること:

1. **誰が呼ぶか** (user / claude / 別 Skill) — prefix から
2. **何の領域か** (API / release / review) — 1st domain segment から
3. **どの subdomain か** (REST / mobile / skill-design) — 2nd segment から
4. **どんな役割か** (evaluator / generator / runbook) — role-suffix から

このうち 1 つでも答えられないなら、segment を 1 個追加する。

詳細: [06-classification-and-naming.md](06-classification-and-naming.md) の命名規約、[29-multi-project-rubric-composition.md](29-multi-project-rubric-composition.md) の L0/L1/L2 階層、[07-progressive-disclosure.md](07-progressive-disclosure.md) の token budget を確認する。

## Step 5. frontmatter

最小:

```yaml
---
name: ref-api-conventions
description: API conventions. Use when designing or reviewing API endpoints.
---
```

副作用が強い:

```yaml
disable-model-invocation: true
allowed-tools:
  - Bash(git status *)
```

internal:

```yaml
user-invocable: false
context: fork
```

詳細: [03-yaml-frontmatter-reference.md](03-yaml-frontmatter-reference.md) で設計判断、[16-official-skills-complete-reference.md](16-official-skills-complete-reference.md) で公式 field 一覧、[04-invocation-permissions-settings.md](04-invocation-permissions-settings.md) で呼び出し制御と権限設定を確認する。

## Step 6. 本文

本文は次だけに集中する。

- output contract（契約）
- 手順
- 禁止事項
- Gotchas（落とし穴）
- 補助ファイルへの案内

一般知識の説明は書かない。

詳細: [08-skill-writing-guidelines.md](08-skill-writing-guidelines.md) で SKILL.md 本文の書き方ガイドラインを確認する。

## Step 7. 補助ファイル

長い reference / examples / scripts は分離する。

```text
my-skill/
├── SKILL.md
├── reference.md
├── examples.md
└── scripts/
    └── validate.sh
```

詳細: [07-progressive-disclosure.md](07-progressive-disclosure.md) で 3 層ロードと token budget の考え方を確認する。

## Step 8. 検証

1. `/skill-name` で直接呼ぶ。
2. description に合う自然文で自動発動するか見る。
3. 誤発動しないか見る。
4. output contract（契約） を満たすか見る。
5. dangerous action は permission / hook で止まるか見る。

詳細: [13-checklists.md](13-checklists.md) のリリース前 4 条件、[09-evaluation-orchestration.md](09-evaluation-orchestration.md) の generator / evaluator 分離を確認する。

## Step 9. 運用改善

繰り返し踏む失敗は Gotchas（落とし穴）へ書く。さらに再発するなら lint / Hook / CI へ昇格する。

詳細: [10-subagents-hooks-integration.md](10-subagents-hooks-integration.md) で Subagent / Hook への昇格パターンを確認する。
