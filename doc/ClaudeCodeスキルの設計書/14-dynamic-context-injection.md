# 14. 動的コンテキスト注入

## 責務

このファイルは、Claude Code Skills の `!` 構文による dynamic context injection を独立して扱う。元記事では「決定論的 CLI 出力を Skill 本文へ焼き込む主用途」と「外部 LLM CLI を呼ぶ副次用途」の区別が強調されている。

## 基本

`!` 構文は、Skill content が Claude に渡る前に shell command を実行し、その stdout を本文へ埋め込む。

Claude が Bash tool を呼んでいるのではない。Claude が見る時点では、command はすでに出力へ置換されている。

## inline form

```markdown
## Current changes

!`git diff HEAD`
```

## multi-line form

````markdown
## Environment

```!
python3 --version
bash --version | head -1
git status --short
```
````

## 主用途

### Git / GitHub の状態注入

```markdown
## Pull request context

- PR diff: !`gh pr diff`
- PR comments: !`gh pr view --comments`
- Changed files: !`gh pr diff --name-only`
```

向いている情報:

- PR diff
- issue body
- review comments
- changed files
- working tree status
- recent commits

### JSON / metrics の整形

```markdown
## Active deployments

- Environments: !`python3 -c "import json; print(', '.join(json.load(open('deploy.json'))['environments'].keys()))"`
- Last deploy SHA: !`python3 -c "import json; print(json.load(open('deploy.json'))['last_deploy']['sha'])"`
```

この例は Python 3 標準ライブラリを前提にした Skill 向けである。Mac / Windows 両対応 Skill では、後述の OS プリアンブルと OS 別分岐を使い、PowerShell fallback を含める。

向いている情報:

- API response
- local JSON
- metrics
- config
- environment state

### Runtime / shell 状態

```markdown
## Runtime

```!
python3 --version
bash --version | head -1
pwd
```
```

## 決定論的情報として扱う条件

`!` に入れる主対象は、次の条件を満たすもの。

- 再現可能
- 検証可能
- 外部 LLM の主観判断を含まない
- command output が事実として扱える
- 毎回 Claude に tool call させるより prompt rendering 時に入れた方が安い

## 外部 LLM CLI を呼ぶ場合

`codex exec`, `gemini`, `claude -p` など外部 LLM CLI を `!` で呼ぶことはできる。ただしこれは主用途ではなく副次用途である。

```markdown
## Other model view

!`codex exec "この差分の設計上の懸念を3点に絞って指摘してください"`
```

## 外部 LLM 出力の扱い

外部 LLM output は未信頼入力として扱う。

禁止:

- 評価基準に昇格しない。
- `ref-*` や長期記憶へそのまま貼らない。
- security / permission 判断の根拠にしない。
- deterministic facts と同じ見出しに混ぜない。

推奨:

- `## Facts` と `## Other-LLM views` を分ける。
- 出所を明示する。
- 一時的な参考意見として扱う。
- 必要なら `delegate-*` Skill に切り出す。

## forked Claude を仲介するパターン

外部 LLM 生出力を親 context に直接入れたくない場合、forked subagent を 1 段挟む。

```text
Parent
  -> Subagent / context: fork
      -> !`codex exec "..."`
      -> subagent が要約・構造化・危険箇所を除去
  -> Parent には構造化済み結果だけ返す
```

利点:

- 親 context に未信頼の長文を残さない。
- 生 output を subagent 内で消費できる。
- 親へ返す情報を JSON / summary に制限できる。

## shell 指定

Skill frontmatter の `shell` で dynamic injection の shell を選ぶ。

```yaml
shell: bash
```

Windows PowerShell を使う場合:

```yaml
shell: powershell
```

PowerShell には `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` が必要。

## クロスプラットフォーム動的注入 (Mac / Windows 両対応)

詳細仕様は `22-cross-platform-runtime.md` を参照。本節は dynamic injection 側の共通プリアンブル契約のみを定義する。

### 共通プリアンブル 1 行

OS 分岐を行うすべての Skill は、本文先頭付近に次の 1 行を必ず置く。これを「OS プリアンブル」と呼ぶ。

```markdown
!`uname -s 2>/dev/null || ver`
```

意図:

- `uname -s` は Mac / Linux で `Darwin` / `Linux` を返す
- 不在の Windows では `||` で `ver` にフォールバックし `Microsoft Windows ...` を返す
- 双方失敗した場合は空または非ゼロ — `os=unknown` と扱い、ユーザーへ OS を問い合わせる

### 本文側の分岐

プリアンブル出力を踏まえ、本文は `<important if="os=...">` で OS 別の手順を提示する。

```markdown
<important if="os=mac">
`python3 scripts/build_skill.py --name $1` を実行する。
</important>

<important if="os=windows">
`powershell -ExecutionPolicy Bypass -File scripts\build_skill.ps1 -Name $1` を実行する。
</important>

<important if="os=unknown">
ユーザーへ「お使いの OS は Mac / Windows / Linux のどれですか？」と問い合わせる。回答を得るまで以降の手順を実行しない。
</important>
```

### no-deps 原則

`!` 経由で呼ぶコマンドは **OS 標準同梱**に限定する (詳細は 22 章ホワイトリスト)。
`jq` / `rg` / `yq` 等を `!` で呼ぶ設計は禁止 — Windows ユーザーで破綻する。
代替として Python 3 標準ライブラリ (`json` / `re` / `pathlib`) を `python3 -c "..."` で呼ぶ。

### shell frontmatter との整合

- Mac/Linux 主の Skill: `shell: bash`
- Windows 主の Skill: `shell: powershell` + `CLAUDE_CODE_USE_POWERSHELL_TOOL=1`
- 両対応 Skill: `shell` を指定しない (各 OS の既定 shell を使い、本文側で OS プリアンブル + 分岐)

## 無効化

settings で shell execution を無効化できる。

```json
{
  "disableSkillShellExecution": true
}
```

用途:

- shared repo の Skill から任意 command を実行させたくない
- enterprise policy
- plugin / additional directory source の安全対策

## タスク分類による条件付き読込

`!` 構文を「**次に Read すべきファイルを決める制御信号**」として使うパターン。Skill 本文の先頭付近で task 分類 script を実行し、その出力に基づいて Claude が後続の Read 対象を選ぶ。設計思想は [07 章 §タスク文脈に応じた自動読込パターン](./07-progressive-disclosure.md#タスク文脈に応じた自動読込パターン) を参照。

### パターン例

```markdown
## Task routing

!`python3 scripts/classify-task.py "$ARGUMENTS"`
```

`$ARGUMENTS` は公式 substitution である。`$USER_REQUEST` のような独自変数名を使う場合は、生成器側で値を注入する契約を別途定義し、公式変数と混同しない。

script の stdout（決定論的 JSON）:

```json
{ "category": "skill-design", "refs": ["29", "27"] }
```

Skill 本文側はこの出力を踏まえ、以下を続ける。

```markdown
<important>
上記 routing の `refs` 各章を Read してから設計を開始すること。
`category` が `unknown` の場合は user に分類確認を求める。
</important>
```

### 設計上の要件

- 分類 script は **再現可能・OS 標準同梱依存のみ**（22 章の no-deps 原則に従う）。
- 出力は JSON など機械可読形式に固定し、Claude に再パースさせない。
- 分類辞書の正本は 07 章で定義する `ref-task-context-map` に集約する。
- 分類失敗時の fallback（unknown category）を必ず本文側で扱う。

## 設計チェック

- [ ] `!` は決定論的情報の注入に使っている
- [ ] 外部 LLM output と facts を分離している
- [ ] command output が巨大になりすぎない
- [ ] secret を出力する command を含んでいない
- [ ] `${CLAUDE_SKILL_DIR}` を使うべき script path を hardcode していない
- [ ] policy で無効化されても Skill が破綻しない


## 量産フローへの自動組込

`run-*` Skill を量産する際、`skill-brief-schema.json` の以下の2フィールドが自動挿入の制御信号となる。

| フィールド | 型 | デフォルト | 役割 |
|---|---|---|---|
| `cross_platform` | boolean | `false` | `true` のとき render-frontmatter.py が OSプリアンブルを挿入対象とマーク |
| `os_preamble_required` | boolean | `false` | `true` のとき ``!`uname -s 2>/dev/null || ver` `` を本文先頭付近へ自動挿入 |

`scripts/render-frontmatter.py` は brief を読み込み、`cross_platform=true` かつ `os_preamble_required=true` の場合に OS プリアンブル 1 行を生成 SKILL.md の `## OS preamble` セクションへ挿入する。

**no-deps 原則との整合**: 自動挿入されるコマンド `uname -s 2>/dev/null || ver` は OS 標準同梱のみを使用し、外部ライブラリに依存しない（22 章ホワイトリスト準拠）。`!` 構文の決定論的情報注入の原則とも矛盾しない。

**lint との連携**: 挿入後、`creator-kit/scripts/lint-skill-tree.py` の `check_os_preamble` が OSプリアンブルの存在を検証する（欠落時 exit 1）。量産パイプラインでの自動検証が完結する。
