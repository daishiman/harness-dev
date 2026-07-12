# 06. 分類と命名

## 最初の分岐: 副作用と成果物返却を分ける

問い:

> その Skill は副作用を持つか。

| 種類 | 副作用 | 役割 | 例 |
|---|---|---|---|
| 辞書型 | なし | 知識・基準・文脈を注入する | API 規約、設計原則、業務知識、レビュー観点 |
| ワークフロー型 | あり | 成果物や状態変化を作る | デプロイ、レポート生成、コード修正 |

会話内に JSON を返すだけのレビューや採点は、外部状態を変えないため副作用ではない。ただし、観測可能な output contract（契約） を持つため workflow として扱う。

| Effect（副作用） | 意味 | 例 |
|---|---|---|
| `none` | 状態を変えず、知識や判断だけを返す | API 規約、設計原則 |
| `conversation-output` | 会話内に structured output を返す | レビュー JSON、採点結果 |
| `local-artifact` | file を作る・編集する | report markdown、画像、コード修正 |
| `external-mutation` | 外部 system を変える | deploy、ticket 作成、email 送信、DB 更新 |

副作用:

- file create / edit
- command execution
- API call
- DB update
- ticket creation
- email / message send

副作用が強いほど、`disable-model-invocation: true`、permissions deny、Hook の必要性が上がる。

辞書型とワークフロー型を混ぜない。必要なら `ref-*` と `run-*` に分割する。

## 4 軸分類

| 軸 | 値 | 問い |
|---|---|---|
| Purpose（目的） | `knowledge` / `produce` / `judge` / `pass-through` | 呼ぶと何が返るか |
| Trigger（発動条件） | `user` / `internal` / `both` | 誰が呼ぶか |
| Shape（成果物の形） | `atomic` / `forked` / `orchestrated` | 内部構造は単純か、分離・複合か |
| Role（役割） | `generator` / `evaluator` / `contributor` / `delegate` / `null` | 評価ループや委譲構造の中で何役か |

4 軸は命名を決めるための診断軸であり、単独で完全な分類体系ではない。特に `wrap-*` は `base:` の有無、`ref-*` は到達方式、`assign-*` は role-suffix で最終裁定する。

## Purpose（目的）

| 値 | 意味 | 典型例 |
|---|---|---|
| `knowledge` | 知識注入のみ | 設計原則、API 規約、domain knowledge |
| `produce` | 成果物や状態変化を作る | report, image, file edit |
| `judge` | 評価結果を返す | review, scoring, quality evaluation |
| `pass-through` | 外部 LLM / agent に委譲 | Codex / Gemini / other agent |

## Trigger（発動条件）

| 値 | 意味 | frontmatter / 到達方式 |
|---|---|---|
| `user` | ユーザーが直接呼ぶ | `user-invocable: true`; dangerous なら `disable-model-invocation: true` |
| `internal` | Claude / parent Skill / forked worker が呼ぶ | `user-invocable: false` |
| `both` | ユーザー要求を起点に、Claude や parent Skill が必要時に読む・呼ぶ | 直呼び可を意味しない。`ref-*` では Read 到達や parent 経由を指す |

`both` は「user menu に直接出す」意味ではない。`ref-*` はユーザー要求に関連して読まれることがあっても、原則として `user-invocable: false` のままにし、ユーザー直呼びが必要なら `run-*-cheatsheet` のような workflow / view を別に作る。

## Shape（成果物の形）

| 値 | 意味 |
|---|---|
| `atomic` | 1 context で完結 |
| `forked` | `context: fork` / Subagent |
| `orchestrated` | multi-phase / loop / parallel / multi-skill |

## Role（役割）

| 値 | 意味 |
|---|---|
| `generator` | 成果物を作る |
| `evaluator` | 成果物を評価する |
| `contributor` | 複数視点の 1 役 |
| `delegate` | 外部 LLM / agent へ渡す |
| `null` | 通常 Skill |

## 5 prefix

| prefix | 役割 | Purpose（目的） | Trigger（発動条件） |
|---|---|---|---|
| `ref-*` | 参照知識 | `knowledge` | `internal` / `both` |
| `run-*` | user-facing workflow | `produce` | `user` |
| `wrap-*` | 既存 Skill の派生 | `produce` | `user` |
| `assign-*` | internal role Skill | `produce` / `judge` / `pass-through` | `internal` |
| `delegate-*` | 外部 LLM / agent 委譲 | `pass-through` | `user` |

## 命名の最小モデル

最小形:

```text
<prefix>-<domain>[-<subdomain>]-<action-or-object>[-<role>]
```

prefix を選ぶ前に、次の順で答える。

1. 知識を読むだけか → `ref-*`
2. ユーザーが成果物や状態変化を作らせるか → `run-*`
3. 既存 Skill の preset / variant か → `wrap-*`
4. 内部で生成・評価・分担・委譲するか → `assign-*`
5. ユーザーが外部 LLM / agent へ渡すか → `delegate-*`

命名規約は 3 層で扱う。

| 層 | 内容 | 破った時の扱い |
|---|---|---|
| 必須規則 | prefix、kebab-case、Trigger（発動条件） 整合、`assign-*` role-suffix、改名手続き | lint / PR gate で止める |
| 推奨規則 | domain segment 数、配下ディレクトリ、scripts/references/examples 命名、resource-map | warning と人間レビュー |
| 組織運用規則 | CHANGELOG、deprecation、例外宣言、改正手続き、重複整理 | governance で裁定 |

## 5 prefix × 4 軸 対応マトリクス（パッと見でわかる表）

「prefix を決めたら、4 軸の値は自動でほぼ確定する」という関係を一覧化する。新規 Skill の命名で迷ったとき、まず prefix を仮置きし、この表で 4 軸の値を逆算して整合性を確認する。

| prefix | Purpose（目的） | Trigger（発動条件） | Shape（成果物の形） | Role（役割） | Effect（副作用） | 典型 frontmatter |
|---|---|---|---|---|---|---|
| `ref-*` | `knowledge` | `internal` / `both` | `atomic` | `null` | `none` | `user-invocable: false` (default) |
| `run-*` | `produce` | `user` | `atomic` / `orchestrated` | `generator` / `null` | `local-artifact` / `external-mutation` | `user-invocable: true` |
| `wrap-*` | `produce` | `user` | `atomic` | `generator` / `null` | `base:` を継承 | `user-invocable: true`, `base:` 必須 |
| `assign-*` | `judge` / `produce` / `pass-through` | `internal` | `forked` / `orchestrated` | `evaluator` / `contributor` / `generator` / `delegate` | `conversation-output` | `user-invocable: false`, `context: fork` |
| `delegate-*` | `pass-through` | `user` | `atomic` / `forked` | `delegate` | `conversation-output` / `external-mutation` | `user-invocable: true`, 外部 agent 明示 |

**読み方**: 同じ行は「同時に成立する組」。列の値が表と異なるなら、prefix 選択を再考するか、軸を再設計する（→ `4 軸の限界` セクション）。

## Decision Table（主要ケース表）

決定木 7 ステップだけでは複合条件の漏れが生じる。下表は主要 8 ケースを扱う裁定表であり、完全網羅を保証するものではない。表外のケースは「例外」ではなく、Trigger（発動条件） / `base:` / role-suffix / Effect（副作用）を追加確認して裁定する。

| # | Purpose（目的） | Trigger（発動条件） | base? | Role（役割） | → prefix | 命名例 |
|---|---|---|---|---|---|---|
| 1 | `knowledge` | * | - | - | `ref-*` | `ref-api-conventions` |
| 2 | `produce` | `user` | あり | - | `wrap-*` | `wrap-deploy-staging` |
| 3 | `produce` | `user` | なし | - | `run-*` | `run-release-prepare` |
| 4 | `produce` | `internal` | - | `generator` | `assign-*-generator` | `assign-summary-generator` |
| 5 | `judge` | `internal` | - | `evaluator` | `assign-*-evaluator` | `assign-skill-design-evaluator` |
| 6 | `judge` | `internal` | - | `contributor` | `assign-*-contributor` | `assign-security-contributor` |
| 7 | `pass-through` | `user` | - | `delegate` | `delegate-*` | `delegate-codex-implementation` |
| 8 | `pass-through` | `internal` | - | `delegate` | `assign-*-delegate` | `assign-gemini-delegate` |

ケース外（例: `Trigger（発動条件）=both` で `Role（役割）=evaluator`、`ref-*` を user menu に出したい、簡易版で evaluator を置かない）は **追加裁定が必要な設計分岐**。原則として `assign-*` は internal、`run-*`/`delegate-*` は user に分離する。分離できない場合は `name-policy-exception` に理由を書き、rubric / lint の対象にする。

## 命名規約条文（法律的命名規則）

スキル群を**規範的・違反検出可能**に保つため、以下を命名規約の条文とする。「○条」は規約単位、「違反検出」は自動化できる範囲、「但書」は例外規定を示す。第1〜5条は必須規則、第6〜14条は推奨または運用規則、第15〜16条は governance 規則である。

### 第1条 (prefix 必須)
**全 Skill は `ref-` / `run-` / `wrap-` / `assign-` / `delegate-` のいずれかで始まる**。
- 違反検出: `^(ref|run|wrap|assign|delegate)-[a-z0-9-]+$` に合致しない `name:` を lint で失格。
- 但書: なし。例外を作る前に「軸の再設計」または「責務分割」で対応する。

### 第2条 (domain segment 必須)
**prefix の直後に 1〜3 個の `<domain>` segment を置く**。形式: `<prefix>-<domain>[-<sub-domain>]-<verb-or-noun>[-<role-suffix>]`
- `<domain>` は kebab-case の名詞または名詞句。DDD（ドメイン駆動設計）のユビキタス言語と一致させる。
- `<verb-or-noun>` は動詞または成果物名（`run-*` は動詞優先、`ref-*` は名詞優先）。
- `<role-suffix>` は `assign-*` の場合のみ `-evaluator` / `-generator` / `-contributor` / `-delegate` を置く。
- 例: `run-github-issue-create`, `ref-payment-api-conventions`, `assign-skill-design-evaluator`
- 違反検出: segment 数が 2 未満（domain 抜け）または 5 超（domain 階層が深すぎ）で lint 失格。

### 第3条 (kebab-case 限定)
**`name:` は lower-case + `-` 区切りに限定する**。`_` / camelCase / 連続 `-` / 先頭末尾 `-` は禁止。
- 違反検出: `^[a-z][a-z0-9]*(-[a-z0-9]+)+$` に合致しないものを lint 失格。

### 第4条 (Trigger（発動条件） 命名強制)
**`user-invocable: true` の Skill は `run-*` / `wrap-*` / `delegate-*` のいずれかで始まる**。`assign-*` / `ref-*` を `user-invocable: true` にすることを禁ずる。
- 但書: `ref-*` を user に開放したい場合は `run-*-cheatsheet` のように `run-*` に変換する。
- 補足: `ref-*` の Trigger（発動条件） が `both` になる場合でも、これはユーザー直呼びではなく「ユーザー要求に関連して Claude / parent Skill が読む」意味である。
- 違反検出: prefix と `user-invocable` の組合せを cross-check。

### 第5条 (role-suffix 一意性)
**`assign-*` の末尾 segment は `-evaluator` / `-generator` / `-contributor` / `-delegate` のいずれか**。複数併用禁止。
- 違反検出: 末尾正規表現で check。`assign-*` で role-suffix なしも失格。

### 第6条 (改名は破壊的変更)
**Skill 名は対外契約。改名は破壊的変更とみなし、`CHANGELOG.md` への記載と旧名 alias の deprecation 期間を要求する**。
- 但書: `_drafts/` 配下の未公開 Skill はこの限りでない。
- 違反検出: git diff で `name:` 変更を検出し、対応する CHANGELOG エントリの存在を確認。

### 第7条 (重複禁止)
**同一 prefix + 同一 domain segment 1 階層目内で重複 `name:` を禁ずる**。
- 例: `run-github-issue-create` と `run-github-issue-add` は議論対象（synonym）。先行 Skill を維持し、後発は wrap-* 化または役割分離する。
- 違反検出: 全 Skill の `name:` を集約し、prefix + 第1 domain segment の組で重複を検知。

## スキル配下ファイル・ディレクトリの命名規約

Skill 配下の構造も第1〜7条に準ずる法律的規範とする。

### 標準ディレクトリ規約

```
.claude/skills/<skill-name>/
├── SKILL.md                ← 必須・本文（300行以下）
├── frontmatter.yaml        ← 任意・大型 frontmatter を分離する場合のみ
├── references/             ← 任意・参照知識（自動 read 対象外）
│   ├── <topic>.md
│   ├── <topic>.yaml        ← 構造化リファレンス（rubric, schema, allowlist）
│   └── resource-map.yaml   ← references/ 配下の索引（任意だが推奨）
├── examples/               ← 任意・完成例
│   ├── <case-name>.md
│   └── <case-name>/        ← 複数ファイルなら 1 ケース 1 ディレクトリ
├── scripts/                ← 任意・実行可能スクリプト
│   ├── lint-<target>.{sh,py,ps1}
│   ├── validate-<target>.{sh,py,ps1}
│   └── <verb>-<target>.{sh,py,ps1}
├── templates/              ← 任意・雛形ファイル
│   └── <target>.template.{md,yaml,json}
├── prompts/                ← 任意・サブ prompt（外部 LLM 委譲用）
│   └── <stage>-<purpose>.md
└── CHANGELOG.md            ← 任意だが第6条適用 Skill では必須
```

### 第8条 (固定ディレクトリ名)
**Skill 配下のディレクトリ名は以下の語彙集合から選ぶ**: `references` / `examples` / `scripts` / `templates` / `prompts` / `eval-log` / `_drafts`。
- 但書: ドメイン固有のディレクトリを足す場合は `xl-<domain>` 形式で prefix を付け、第8条の予約語と衝突を避ける。
- 違反検出: ディレクトリ走査で許可リスト外のディレクトリを lint 失格。

### 第9条 (ファイル名 kebab-case)
**Skill 配下のファイル名（拡張子前）は kebab-case 限定**。`_` / camelCase / 空白 / 全角文字を禁ずる。
- 但書: `SKILL.md` / `README.md` / `CHANGELOG.md` の3つは慣習に従い大文字許可。
- 但書: scripts/ 配下の `.ps1` ファイル名で PowerShell 慣習の PascalCase を選ぶ場合は frontmatter `name-policy: pwsh-pascal` で明示宣言する。
- 違反検出: 配下ファイルの basename を `^[a-z0-9][a-z0-9.-]*\.[a-z0-9]+$` で検証。

### 第10条 (scripts/ 命名は動詞先頭)
**`scripts/` 配下のファイル名は `<verb>-<target>[.<sub-target>].<ext>` 形式**。`verb` は `lint` / `validate` / `build` / `format` / `check` / `score` / `extract` / `convert` のいずれか。
- 但書: 未定義 verb を導入する場合、SKILL.md 冒頭で「scripts naming」セクションを設けて宣言する。
- 違反検出: 先頭 segment が動詞リストに含まれるかを lint。

### 第11条 (references/ 命名は名詞先頭)
**`references/` 配下のファイル名は `<topic>[-<aspect>].<ext>` 形式の名詞句**。動詞先頭を禁ずる（scripts/ と区別するため）。
- 例: `rubric.json`, `naming-convention.md`, `api-allowlist.yaml`
- 違反検出: 先頭 segment が動詞辞書に該当する場合 lint 警告。

### 第12条 (examples/ 命名は case 形式)
**`examples/` 配下は `<case-id>-<short-description>.<ext>` または同名ディレクトリ**。`<case-id>` は `case01` / `case-happy-path` / `case-failure-X` 等の識別子。
- 違反検出: case-id 段が無い examples ファイルを lint 警告。

### 第13条 (resource-map.yaml の役割)
**`references/` に 3 ファイル以上ある場合、`references/resource-map.yaml` を置くことを推奨する**。
- 形式（標準スキーマ）:
  ```yaml
  resources:
    - file: rubric.json
      topic: 評価基準
      read_when: forked evaluator 実行時
    - file: naming-convention.md
      topic: 命名規約条文
      read_when: 命名違反検出時のみ
  ```
- 違反検出: `references/` のファイル数を数え、3 ファイル以上で resource-map.yaml の不在を lint 警告。
- 効果: Progressive Disclosure（段階的開示）の「どれをいつ読むか」を機械可読化する。

### 第14条 (_drafts/ の特例)
**`_drafts/` 配下は第1〜13条の適用対象外**。未公開・実験用と扱う。
- 但書: PR / merge 時に `_drafts/` 配下が含まれる場合、CI で deprecation 警告を出す。

## plugin 移行時の命名規約（第17条・Phase 0 完了後に適用）

> **適用条件**: 34章の Phase 0 (classify_change 実装 + 全 SKILL.md 外部参照棚卸し) 完了後に限り適用する。Phase 0 未完了での plugin 移行・命名変更は禁止。

### 第17条 (plugin 名前空間)

**plugin に分離する Skill 群は `plugins/<name>/` の kebab-case ディレクトリ名を使用し、名前空間衝突を禁ずる**。

- plugin ディレクトリ名の形式: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`（kebab-case 必須）
- 名前空間衝突禁止: 既存の `plugins/` 配下ディレクトリ名と重複した `<name>` は使用禁止
- plugin 内の Skill 名は第1〜16条をそのまま適用する（prefix 体系は変わらない）
- plugin 外の Skill から plugin 内 Skill を直接参照することを禁ずる（公式制約 e: plugin 外参照禁止）

**plugin 命名の失格パターン:**

| パターン | 例 | 理由 |
|---|---|---|
| 大文字混在 | `plugins/HarnessCreator/` | kebab-case 違反 |
| アンダースコア | `plugins/harness_creator/` | kebab-case 違反 |
| 既存 plugin と同名 | `plugins/core/` (既存) | 名前空間衝突 |
| plugin 外 Skill への参照 | `skills/run-foo` が `plugins/bar/ref-baz` を Read | 公式制約 e 違反 |

**公式制約 e の影響**: plugin スコープ宣言外の Skill・scripts・設定ファイルへのアクセスは plugin 境界違反となる。全 SKILL.md の外部参照棚卸しが Phase 0 の必須要件である理由はこれにある（34章参照）。

- 違反検出: `scripts/lint-plugin-namespace.py`（Phase 0 完了後に実装）
- 但書: Phase 0 完了前は第17条を適用しない。適用開始は 34章のゲート判定後。

## 違反検出と改正手続き

第1〜14条は **lint script で機械検出可能** にすることを設計目標とする。実装の対応は次の通り。

| 条 | 検出手段 | 配置例 |
|---|---|---|
| 1, 3, 4, 5 | regex / yaml parse | `scripts/lint-skill-name.{sh,py}` |
| 2, 11 | segment count / 動詞辞書照合 | 同上 |
| 6 | git diff + CHANGELOG 突合 | CI workflow |
| 7 | 全 Skill `name:` 集約スキャン | `scripts/lint-name-uniqueness.sh` |
| 8, 9, 12 | directory walk + regex | `scripts/lint-skill-tree.sh` |
| 10 | scripts/ 配下の verb 先頭判定 | 同上 |
| 13 | references/ ファイル数 + resource-map.yaml 存在 | 同上 |
| 14 | path filter | CI workflow |

### 改正手続き（第15条）
**本条文の改正は次の3段階を経る**:
1. **提案**: PR で条文変更案 + 影響を受ける既存 Skill のリストを提示。
2. **影響評価**: 既存 Skill のうち何件が新条文で違反になるか lint で計測し、PR 本文に記載。
3. **猶予期間**: 違反 Skill 数が 0 でない場合、`deprecation: <date>` を付与し、最低 1 release（または 30 日）の猶予期間を設ける。

### 例外規定の作り方（第16条）
**条文に対する例外は SKILL.md の frontmatter に `name-policy-exception: <条番号>: <理由>` で明示宣言する**。lint script は宣言された例外を尊重する。
- 例: `name-policy-exception: "9: PowerShell PascalCase convention"`

## 汎用性応用例

法律的命名規約は Clean Architecture（依存方向を守る設計） / Clean Code / DDD（ドメイン駆動設計） だけでなく、エンジニアリング・マーケティング等の他分野の概念体系を Skill に乗せる際にも適用できる。「prefix=責務、domain=ユビキタス言語、role-suffix=役割」の3層構造は汎用。

| 分野 | 概念体系 | Skill 命名例 |
|---|---|---|
| **DDD（ドメイン駆動設計）** | Bounded Context（境界づけられた文脈） / Ubiquitous Language（共通言語） | `ref-order-context-glossary`, `run-order-place`, `assign-order-validation-evaluator` |
| **Clean Architecture（依存方向を守る設計）** | Entities / Use Cases / Adapters | `ref-domain-entities`, `run-usecase-checkout`, `assign-adapter-contract（契約）-evaluator` |
| **SOLID** | 単一責任原則 | 1 Skill 1 責任を `prefix-<responsibility>-<verb>` で表現 |
| **マーケティング (AIDA)** | Attention / Interest / Desire / Action | `run-marketing-aida-headline-generate`, `assign-marketing-aida-funnel-evaluator` |
| **マーケティング (STP)** | Segmentation / Targeting / Positioning | `ref-marketing-stp-framework`, `assign-marketing-segmentation-contributor` |
| **JTBD** | Jobs To Be Done | `run-jtbd-interview-template`, `ref-jtbd-job-statement-rules` |
| **OKR** | Objectives / Key Results | `ref-okr-writing-rules`, `assign-okr-quality-evaluator` |
| **データ分析** | Hypothesis / Experiment / Insight | `run-hypothesis-design`, `assign-experiment-power-evaluator` |
| **PMBOK** | プロジェクト10領域 | `ref-pmbok-risk-register`, `run-pmbok-charter-create` |
| **本プロジェクト（メタSkill構築）** | requirement-analysis / skill-build / task-boundary / delegation | `ref-skill-build-conventions`, `run-requirement-analyze`, `assign-task-boundary-evaluator`, `delegate-codex-implementation` |

**ポイント**: 「分野が変わっても、prefix の意味（副作用・呼び出し可能性）は普遍」。domain segment と role-suffix で分野固有の語彙を表現する。これにより一つの命名規約で全分野の Skill を統一的に運用できる。

## 人間/AI 責務境界の設計原則（プロジェクト中核コンセプト）

本プロジェクトのコンセプトは「**ユーザー要望分析 → Skill 化 → タスクを AI に巻き取らせる**」。これは Skill が「人間の作業時間を AI に委譲するための契約装置」として機能することを意味する。命名規約・チェックリストタグ・rubric（評価基準）は次の対応関係で**責務境界**を明示する:

| 責務境界 | 命名上の表現 | チェックリストタグ | 委譲先 |
|---|---|---|---|
| **人間が判断する作業** | `ref-*-conventions`（参照のみ） | `[人]` / `[人+Lint]` | 人間（業務妥当性・表現品質・命名のセマンティクス） |
| **AI が実行する作業** | `run-*` / `assign-*-generator` | （自動実行） | Claude / メタSkill |
| **機械的に検証する作業** | `assign-*-evaluator` | `[Lint]` | スクリプト（regex / yaml parse / segment count） |
| **lifecycle で守る作業** | `assign-*-evaluator` + Hook | `[Hook]` | PreToolUse / PostToolUse / PreCompact |
| **外部 AI に委譲する作業** | `delegate-*` | （別 LLM） | Codex / Gemini / 他 agent |

### 委譲判定の3段階

1. **巻き取り対象**: 決定論で解ける／繰り返し発生する／品質が rubric で測れる作業は AI 側へ。
2. **人間専管**: 業務妥当性・命名のユビキタス言語・例外宣言の理由付け・改正承認は人間側へ（第15・16条）。
3. **境界例外**: `name-policy-exception` のように人間判断を明示宣言する仕組みで、機械検証と人間判断を両立する。

この原則により、Skill 群は**ユーザー時間を最小化する委譲装置**として動作し、命名規約とチェックリストタグはその境界の**契約**を担う。

## 決定木

1. `Purpose（目的）=knowledge` -> `ref-*`
2. `Purpose（目的）=judge` -> `assign-*-evaluator`
3. `Purpose（目的）=pass-through` and `Trigger（発動条件）=user` -> `delegate-*`
4. `Purpose（目的）=pass-through` and `Trigger（発動条件）=internal` -> `assign-*-delegate` or role suffix
5. `Role（役割）=generator` and `Trigger（発動条件）=internal` -> `assign-*-generator`
6. `Trigger（発動条件）=user` and `base:` exists -> `wrap-*`
7. `Trigger（発動条件）=user` and no `base:` -> `run-*`

## 名前は契約

| prefix | 呼び出し側が置く事前条件 |
|---|---|
| `ref-*` | 副作用ゼロ、read-only、純粋知識 |
| `run-*` | ユーザー直叩き、独立 workflow、副作用明示 |
| `wrap-*` | `base:` の契約を継承する派生 |
| `assign-*-evaluator` | forked evaluator、rubric を編集しない |
| `delegate-*` | 未信頼の外部 LLM output を返す |

## 4 軸の限界

| ズレ | 扱い |
|---|---|
| `judge` と `evaluator` が近い | Purpose（目的）は output、Role（役割）は loop 内役割 |
| `pass-through` と `delegate` が近い | Purpose（目的）は処理種別、Role（役割）は構造 |
| Trigger（発動条件） が運用中に変わる | name / frontmatter を再設計 |
| Shape（成果物の形） が育つ | atomic から orchestrated へ再分類 |
| `wrap-*` と `run-*` | `base:` を二次分岐にする |

## 迷った時のデフォルト

| 迷い | デフォルト |
|---|---|
| docs か `ref-*` か | Claude に自動想起させたいなら `ref-*`、人間向け記録なら docs |
| `ref-*` か `run-*` か | file / command / API を触るなら `run-*` |
| `run-*` か `wrap-*` か | `base:` を持つ preset / variant なら `wrap-*` |
| evaluator が必要か | 合否や score で再実行制御したいなら evaluator |
| Subagent か Agent Team か | worker 間 communication が不要なら Subagent |

## 分割例

悪い例:

```text
skill-api-helper
  - API 規約を説明する
  - endpoint を実装する
  - review JSON を返す
```

良い例:

```text
ref-api-conventions
run-api-implementation
assign-api-review-evaluator
```

## § X prefix 別内部構造規約 → 23a 章参照

prefix が宣言する実行モードに応じて、`prompts/` `agents/` `schemas/` `templates/` `references/` `workflow-manifest.json` の設置要件は非対称に決まる。本章は命名（外形）の正本であり、内部構造の正本は別章に分離する。
詳細は [23a-prefix-driven-internal-structure.md](23a-prefix-driven-internal-structure.md) を参照。

