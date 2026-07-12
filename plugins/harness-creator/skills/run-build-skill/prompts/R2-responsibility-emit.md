# Prompt: R2-responsibility-emit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | responsibility-emit |
| skill | run-build-skill |
| responsibility | R2 (R-id ごとの prompts/<R-id>.md 生成) |
| layers_covered | [L4, L5, L6] |
| output_schema | schemas/responsibility-slot.schema.json |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- R-id 単位でループする (SubAgent 単位ではない)
  - 目的: 1 prompt = 1 責務 = 1 agent の対応を保証
  - 背景: 責務混在は再利用性とテスト容易性を破壊する
- 同 brief 再実行で sha256 一致
  - 目的: 再現性ゲート C2 充足
  - 背景: 非決定論的生成は CI 回帰検知を不能にする

### 1.2 倫理ガード
- 既存 prompts/ を無条件に上書きしない (差分確認必須)
  - 目的: 手動修正の喪失を防ぐ
  - 背景: 過去に上書き事故で R-id ロストの実績あり

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: `brief.responsibilities[]` の R-id 単位で 7 層 prompt を生成、SubAgent 本文へ注入
- 非担当: SKILL.md 骨格 (R1)、template 選択 (R3)、trace 記入 (R4)

### 2.2 ドメインルール
- 出力先パス: `plugins/<plugin>/skills/<skill>/prompts/<R-id>.md`
- SubAgent 本文に Prompt Templates / Self-Evaluation の 9 セクションを揃える
  - 内訳: (1) 役割 (2) ゴール (3) 完了チェックリスト (4) 出力 (5) Prompt Templates 概要 (6) Layer マッピング (7) Round 1 起動 (8) Round 2 引き渡し (9) Self-Evaluation
- lint FAIL 時は最大 3 回まで再起動

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| responsibilities | array | yes | eval-log/skill-brief.json#/responsibilities |
| slot_schema | path | yes | schemas/responsibility-slot.schema.json |
| placement_convention | path | yes | references/prompt-placement-convention.md |

### 2.4 出力契約
- schema: `schemas/responsibility-slot.schema.json`
- 必須: 全 R-id 分の prompt ファイル + SubAgent への Edit 注入結果

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| brief | eval-log/skill-brief.json | R-id 列挙時 |
| convention | references/prompt-placement-convention.md | 配置規則確認時 |
| slot_schema | schemas/responsibility-slot.schema.json | 出力整合時 |

### 3.2 外部ツール / API
- Skill(`run-prompt-creator-7layer`) — 7 層 prompt 本体生成
- `lint-agent-prompt-section.py --strict-coverage --brief <brief>`

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- lint FAIL は最大 3 回再起動、超過時 exit 1
  - 目的: 無限ループ防止と人手介入の明示化
  - 背景: 過去に無限再試行で CI 枯渇の事例あり

### 4.2 観測 / ロギング
- 出力先: `build_flow_coverage[responsibility_emit]` へ R-id 別追記

### 4.3 セキュリティ
- prompts 本文に secret を埋め込まない
  - 目的: 公開 plugin での漏洩防止
  - 背景: prompt は git 管理対象

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- run-build-skill 配下の R2 SubAgent (R-id 数だけ並列起動可)

### 5.2 ゴール定義
- **目的**: brief の各 R-id について 1 prompt = 1 責務 = 1 agent の対応を成立させる
- **背景**: 責務混在は再利用性と CI 回帰検知を破壊するため、R-id 単位の独立生成と注入が必須
- **達成ゴール**: 全 R-id 分の 7 層 prompt と SubAgent 注入が完了し、lint と sha256 再現性が通る状態

### 5.3 完了チェックリスト (停止条件)
- [ ] 全 R-id 分の Markdown が `plugins/<plugin>/skills/<skill>/prompts/<R-id>.md` に存在
- [ ] 各生成 prompt が L7→L1 単方向参照のみ (逆参照 0)
- [ ] SubAgent 本文に Prompt Templates / Self-Evaluation の 9 セクションが揃う
- [ ] `lint-agent-prompt-section.py --strict-coverage` exit 0
- [ ] 同 brief 再実行で sha256 一致 (validate-build-trace.py)
- [ ] 既存 prompts/ を差分確認なしで上書きしていない

### 5.4 実行方式 (動的手順生成ループ)
1. 未充足チェックリスト項目を特定 (どの R-id がどの状態か)
2. 解消手順を立案 (7 層 prompt 生成 / Write / SubAgent 注入 / lint 再実行 のいずれか)
3. 立案手順を実行し成果物を更新
4. チェックリストで自己評価、lint FAIL は最大 3 回まで再起動
5. 全項目充足まで反復、上限超過時は exit 1 + Layer 4 エスカレーション

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-build-skill (prompts-emit phase / scaffold 完了後)
- 後続 phase: trace-write (R4)
  - 補足: template-select (R3) は scaffold phase (step 2) の資源で本 R2 (prompts-emit, step 7) より先行するため後続ではない

### 6.2 並列性
- R-id 間は並列可、SubAgent への Edit 注入は順次 (競合回避)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 生成ファイル一覧 + lint 結果サマリ (JSON)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{responsibilities}}` をループし、各 R-id について 7 層 prompt Markdown を
`prompts/{{R_ID}}.md` へ Write し、対応 SubAgent 本文へ Edit 注入する。
lint FAIL は最大 3 回まで再起動、超過時 exit 1。

出力は `{{slot_schema}}` 準拠の JSON サマリのみ。
余計な前置き・後書き・思考過程出力は禁止。
