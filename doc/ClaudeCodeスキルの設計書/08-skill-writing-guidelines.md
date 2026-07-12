# 08. Skill 本文設計

## Less is More

Skill 本文に最も多い失敗は、書きすぎである。Claude が一般知識として知っていることを書くほど、重要なプロジェクト固有情報が薄まる。

### 行数上限（必須規律）

- **SKILL.md 本文は 300 行を上限とする**。これは HumanLayer "Writing a good CLAUDE.md" の「60 行目安・上限 300 行」を SKILL.md に適用したもの（原典 L1200）。300 行を超えると Claude が各セクションを optional 扱いし始め、規律が効かなくなる。
- Claude Code 公式 docs には「500 行未満を目安」とあるが、生成対象 `SKILL.md` ではそれを超える厳格な出荷基準として 300 行 hard cap を採用する。公式事実は `16`、本プロジェクトの判定基準は `08` / `13` / `24` に置く。
- この上限は生成される `.claude/skills/<skill-name>/SKILL.md` 本文の規律であり、`doc/ClaudeCodeスキルの設計書/*.md` には適用しない。設計書は正本性・追跡性・判断根拠を優先し、300 行以上でもよい。
- 補助知識は `references/` `examples/` `scripts/` に逃がす（07 Progressive Disclosure（段階的開示））。
- 100 行で書ける内容を 300 行まで膨らませない。短さは美徳である。
- 数字の根拠は経験則だが、生成対象の `SKILL.md` では 300 を hard cap として扱い、lint / 自己採点 rubric で機械的に強制する（24/26）。

### description 設計の必須規律

`description` は人間向け要約ではなく、Claude が「いつこの Skill を呼ぶか」を判断するための trigger 条件である。本文の動作詳細を description に書くと、Claude は本文を読まず description の短縮版だけで動く（原典 L496-500、obra/superpowers の writing-skills 事例）。

- **発動条件は 2〜3 個に収める**（1 個は不足、4 個以上は冗長・重複・処理混入を招く。原典 L504「上限は 2 個前後」を本群では 2〜3 個と定義）。
- **動詞や手順で「いつ呼ぶか」を書く**（名詞羅列ではなく動作主導。`Use when the user asks to …` の形）。
- **動作詳細（採点する／JSON で返す／4 枚並列実行する 等）を混ぜない**（原典 L500, L522）。動詞は「呼ぶ条件」のための動詞であり、「呼ばれた後の処理」のための動詞ではない。
- description が膨らむと `description` + `when_to_use` 合算 1,536 文字 cap を圧迫し、Skill listing 全体のコンテキスト予算も削る。

#### Before / After 例

悪い例（動作詳細混入・発動条件 1 個）:

```yaml
description: スキルレビュー機能。スキル設計を採点しJSONで返すスキルです。
```

良い例（発動条件 2 個・動詞ベース）:

```yaml
description: Skill design evaluator. Use when the user asks to "review a Skill" or score a SKILL.md against the rubric.
```

悪い例（発動ワード 4 個並列・重複）:

```yaml
description: スキル評価。「skillレビュー」「SKILL.md採点」「スキル設計の評価」「Skill品質チェック」で発動。
```

良い例（発動条件 3 個・重複なし）:

```yaml
description: Release check workflow. Use when the user asks to prepare a release, verify release readiness, or run a pre-release gate.
```

| 書くべき | 書かなくてよい |
|---|---|
| project 固有制約 | 一般的な CLI の使い方 |
| Skill 固有の失敗パターン | Markdown / JSON / YAML の基本 |
| 採用方針と理由 | 採用しなかった案の長い経緯 |
| domain 固有ルール | 一般的プログラミング知識 |
| output format / 禁止事項 / 完了条件 | 抽象的な「高品質に」 |

## Why（理由）-driven

LLM は強調ではなく妥当性で従う。`ALWAYS` / `NEVER` だけで押すより、理由を書く。

悪い例:

```markdown
ALWAYS validate input before passing to API.
NEVER deploy without confirmation.
```

良い例:

```markdown
API 呼び出し前に input を validate する。
validation failure は API 側で回復できず、上流で 400 を返すと orchestrator が無駄な retry を走らせる。手前で止めれば loop 予算を節約できる。

Deploy endpoint はユーザー確認なしで呼ばない。
本番反映は副作用が不可逆で、巻き戻しに人間判断が要る。
```

## 条件付き重要ルール

```xml
<important if="you are writing or modifying tests">
- Use `createTestApp()` helper for integration tests.
- Mock database with `dbMock` from `packages/db/test`.
- Do not edit generated snapshots manually.
</important>
```

使い方:

- 条件は具体的にする。
- 何でも囲まない。
- Why（理由）-driven と組み合わせる。

## Gotchas（落とし穴）

Gotchas（落とし穴）は、実運用で LLM が踏んだ落とし穴を書く場所。

良い Gotcha:

```markdown
- **`allowed-tools` は deny ではない** — `Read Grep` だけ書いても permissions で Edit/Write が許可なら呼べる。書き込み禁止は `permissions.deny` で行う。
```

条件:

- 見出しで罠が分かる。
- 1〜2 行で why と回避を書く。
- 具体的・検証可能。
- 古くなったら削る。

## Gotchas（落とし穴）から決定論へ

| 段階 | 仕組み | 検出 |
|---:|---|---|
| 1 | Gotchas（落とし穴） | 推論時 |
| 2 | schema validation / frontmatter lint / Hook | commit / 起動時 |
| 3 | CI script | CI |
| 4 | CLI / lint plugin | 開発フロー全体 |

同じ失敗が繰り返されるなら、Gotchas（落とし穴）に置いたままにせず、決定論へ昇格する。

## 繰り返し違反の昇格先

evaluator が同じ違反を 2 回連続で返した場合、個別 Skill の修正だけで終わらせない。原因を次の順で切り分ける。

| 原因 | 昇格先 |
|---|---|
| 生成物だけの記述漏れ | 当該 `SKILL.md` / 補助ファイルを修正 |
| 毎回同じ構造が欠ける | `templates/` を修正 |
| 評価基準が曖昧または過剰 | rubric 改正手続きへ |
| 命名規約そのものが現実に合わない | `06` 第15条の改正手続きへ |

この順序により、rubric を緩めて合格させる Goodhart（評価基準を都合よく歪める罠）と、テンプレ欠陥を個別修正で隠す運用を避ける。
