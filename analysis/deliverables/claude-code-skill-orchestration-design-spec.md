# Claude Code Skill オーケストレーション設計書

作成日: 2026-05-17
対象資料: `doc/【コード共有有】Agent Skill大全 数百本のSkillをり続けた実践知から導いたオーケストレーション設計の概念体系Byまさおさん.md`
対象画像: Markdown 内で参照されている 54 点の PNG 画像
目的: 記事本文と画像内の図表情報を統合し、Claude Code Skill を「再現可能な業務部品」として作成・運用するための設計仕様に落とし込む。

## 1. エグゼクティブサマリー

この記事と画像群が伝えている中心メッセージは、Claude Code Skill を「便利なプロンプト保存場所」ではなく、「名前・責務・発動条件・評価契約を持つ再利用可能な業務部品」として扱うべきだ、という点にある。

Skill が 1 本だけなら、長いプロンプトを保存するだけでも機能する。しかし Skill が増えると、似た Skill が並び、呼び出し条件が曖昧になり、評価も自己申告に寄る。その結果、エージェント上に小さなアプリケーションのような構造が育つ一方で、設計言語がないと運用が破綻する。

本設計書では、記事の提唱体系を次のように構造化する。

- Skill はまず「辞書型」と「ワークフロー型」に分ける。
- 各 Skill を `Purpose / Trigger / Shape / Role` の 4 軸で記述する。
- 4 軸と派生関係から `ref- / run- / wrap- / assign- / delegate-` の 5 prefix を決める。
- Skill 名はラベルではなく、呼び出し側に事前条件を強制する契約として扱う。
- 生成器と評価器を分け、評価器は別コンテキストで動かす。
- 評価結果は感想ではなく、スコア・合否・指摘を持つ機械可読な出力にする。
- 決定論で処理できるものは Skill に書かず、Hook / CI / CLI / MCP / API に寄せる。
- `SKILL.md` は短く保ち、詳細資料・例・スクリプトは補助ファイルへ逃がす。

## 2. 抽出対象と解析方法

### 2.1 入力ファイル

- Markdown 本文: 記事全文 1,349 行
- 画像: Markdown 内の Obsidian 埋め込み画像 54 点
- 解析方法: 本文読解、画像リスト抽出、画像寸法確認、OCR、本文と OCR の相互照合

### 2.2 画像参照一覧

| 行 | 画像 | 抽出した主題 |
|---:|---|---|
| 95 | `Obsidian 2026-05-17 15.13.53.png` | Context Reset: compaction ではなく真っ白なスレートへ構造化引き継ぎ |
| 162 | `Obsidian 2026-05-17 15.14.31.png` | 散らかった運用知を Purpose / Trigger / Shape / Role と prefix で整理する全体像 |
| 248 | `Obsidian 2026-05-17 15.14.41.png` | 同上: 再利用可能な Skill を設計するための設計体系 |
| 281 | `Pasted image 20260517151648.png` | Skill / Subagent / Hook / MCP の使い分け早見表 |
| 294 | `Pasted image 20260517151701.png` | Skill / Subagent / Hook / MCP の比較表 |
| 297 | `Pasted image 20260517151710.png` | 運用・判断層と実装層のレイヤー図 |
| 320 | `Pasted image 20260517151722.png` | Skill を作る前に通す決定木 |
| 335 | `Pasted image 20260517151733.png` | やりたいこと別の置き場所: CLI / MCP / API / Hook / Skill |
| 343 | `Pasted image 20260517151757.png` | Skill は実装層の上に立つメタ層 |
| 346 | `Pasted image 20260517151806.png` | CLI / MCP / API/SDK の比較 |
| 353 | `Pasted image 20260517151812.png` | Skill が CLI / MCP / API/SDK の使い方を書く構造 |
| 369 | `Brave Browser 2026-05-17 15.19.55.png` | CLI と MCP は対立せず、Skill が状況に応じて使い分ける |
| 427 | `Pasted image 20260517152051.png` | 実装層 4 段階の昇華ラダー |
| 457 | `Pasted image 20260517152110.png` | Claude は description / when_to_use を読んで Skill を選ぶ |
| 474 | `Pasted image 20260517152123.png` | SKILL.md の YAML frontmatter と Markdown 本文の役割 |
| 515 | `Pasted image 20260517152140.png` | description の Before / After 例 |
| 529 | `Pasted image 20260517152159.png` | SKILL.md frontmatter の主要フィールド |
| 536 | `Pasted image 20260517152216.png` | frontmatter フィールド別の役割と注意点 |
| 542 | `Pasted image 20260517152444.png` | 呼び出し制御マトリクス |
| 543 | `Pasted image 20260517152451.png` | `disable-model-invocation` / `user-invocable` の比較表 |
| 564 | `Pasted image 20260517152506.png` | Progressive Disclosure と compaction 予算 |
| 588 | `Pasted image 20260517152518.png` | Progressive Disclosure の 3 層 |
| 591 | `Pasted image 20260517152529.png` | 入口情報 / SKILL.md 本文 / 補助ファイルのロードタイミング |
| 601 | `Pasted image 20260517152540.png` | なぜ分けるのか: attention は有限 |
| 675 | `Obsidian 2026-05-17 15.25.56.png` | 段階的開示の 3 つの失敗 |
| 682 | `Pasted image 20260517152614.png` | 失敗パターン、悪さ、直し方 |
| 695 | `Pasted image 20260517152620.png` | どこに置くか × どこで読ませるか |
| 758 | `Pasted image 20260517152658.png` | Skill の最初の分岐: 副作用の有無 |
| 791 | `Pasted image 20260517152707.png` | 辞書型 / ワークフロー型の比較 |
| 805 | `Pasted image 20260517152717.png` | やりたいこと別の分類例 |
| 806 | `Pasted image 20260517152728.png` | 公式の Reference content / Task content 例 |
| 817 | `Pasted image 20260517152736.png` | CLAUDE.md / ref-* / docs のメモリ濃度比較 |
| 877 | `Pasted image 20260517152915.png` | Purpose / Trigger / Shape / Role の 4 軸 |
| 900 | `Pasted image 20260517152941.png` | Purpose 軸 |
| 904 | `Pasted image 20260517152948.png` | Trigger 軸 |
| 910 | `Pasted image 20260517152958.png` | Shape 軸 |
| 916 | `Pasted image 20260517153005.png` | Role 軸 |
| 923 | `Obsidian 2026-05-17 15.30.09.png` | `ref-agent-essence` の 4 軸例 |
| 937 | `Pasted image 20260517153028.png` | `wrap-masao-ch-thumbnails` の 4 軸例 |
| 945 | `Pasted image 20260517153041.png` | 4 軸は分類表ではなく設計レビュー用の問い |
| 964 | `Pasted image 20260517153048.png` | 4 軸のズレと扱い方 |
| 974 | `Pasted image 20260517153106.png` | 5 prefix の一覧 |
| 978 | `Pasted image 20260517153115.png` | prefix 決定木 |
| 979 | `Pasted image 20260517153120.png` | 4 軸から 5 prefix へ決める決定マトリクス |
| 991 | `Pasted image 20260517153137.png` | 名前は契約: prefix が事前条件を約束する |
| 1009 | `Pasted image 20260517153146.png` | 独自メタデータ `base:` / `pair:` / `kind:` |
| 1075 | `Pasted image 20260517153203.png` | Skill 本文は人間への教材ではなく行動設計文書 |
| 1082 | `Pasted image 20260517153212.png` | 書くべきこと / 書かなくてよいこと |
| 1185 | `Obsidian 2026-05-17 15.32.20.png` | Less is More と Why-driven |
| 1228 | `Pasted image 20260517153330.png` | Gotchas から決定論へ昇格する 4 段階 |
| 1246 | `Pasted image 20260517153351.png` | 動的コンテキスト注入と外部 LLM 出力の扱い |
| 1331 | `Pasted image 20260517153442.png` | 評価が壊れる理由と forked evaluator |
| 1332 | `Pasted image 20260517153432.png` | Sycophancy と評価分離の詳細図 |
| 1333 | `Pasted image 20260517153449.png` | Generator / Evaluator の役割表 |
| 1338 | `Pasted image 20260517153455.png` | Generator → Artifact → Evaluator → 再実行 / Done の評価ループ |

## 3. 記事の主張を構造化した概念体系

### 3.1 問題設定

AI エージェントから「再現性のある出力」を引き出すには、毎回プロンプトを書き直す運用から脱却する必要がある。レビュー、画像生成、スライド作成、調査、評価などを「その時の調子」ではなく、「呼べばこの品質で返ってくる」状態にすることが目的である。

Claude Code Skill はそのための仕組みだが、Skill は単なるプロンプト保存場所ではない。複数 Skill を組み合わせると、エージェント上に小さなアプリケーション構造が組み上がる。ここで必要になるのが、責務分割、命名、評価、運用の設計言語である。

### 3.2 この記事の位置づけ

記事は公式仕様の翻訳ではなく、数百本の Skill 運用から抽出した設計規範の提唱である。公式仕様が示すのは「Skill とは何か」「どこに置くか」「どう動かすか」までであり、本記事はその上に次の問いを扱う。

- どこまでを 1 つの Skill にまとめるべきか。
- 何を切り出すべきか。
- どの Skill に何を任せるべきか。
- 任せた仕事の品質を誰がどう判定するべきか。
- 増えた Skill 群をアプリらしさを保ったまま進化させるにはどうするか。

### 3.3 持ち帰るべき結論

- Skill はプロンプト断片ではなく、エージェントが読みに来る再利用部品である。
- Skill を作る前に、Skill / Subagent / Hook / 実装層のどこで解くかを判断する。
- Skill の命名は感覚で決めない。4 軸を埋めれば prefix は概ね機械的に決まる。
- ワークフロー型 Skill は「できました」で終わらせない。生成役と評価役を分け、外部評価器で完了判定する。

## 4. Skill / Subagent / Hook / MCP / CLI / API のレイヤー設計

### 4.1 基本思想

Skill は道具そのものではなく、道具の使い方を書く一段上のレイヤーである。Claude Code には Skill / Subagent / Hook / MCP があるが、これらは同列ではない。

| 領域 | 何をするか | 向いていること | 向いていないこと |
|---|---|---|---|
| Skill | Claude に手順・知識・作法を読ませる | 再利用プレイブック、チェックリスト、参照知識、運用方針 | 毎回必ず実行する処理、外部 API の実体 |
| Subagent | 別コンテキストでタスクを実行する | 調査、レビュー、評価、長い作業の分離 | 単なる参照知識の注入 |
| Hook | イベントで自動実行する | PreToolUse / PostToolUse など LLM 判断に任せたくない自動化 | モデルに考えさせる判断 |
| MCP | agent が扱える意味単位で tool / resource / prompt を提供する | API、DB、社内システム、ブラウザ、GitHub などの schema 付き操作 | 複数ツールをまたぐチーム固有の運用ポリシー集約 |
| CLI / API / SDK | 実装層の道具 | 決定論的処理、既存ツール、薄い自作ラッパー | 運用上の文脈判断そのもの |

### 4.2 決定木

Skill を作る前に次の順に問う。

1. 決定論で組めるか。
2. 決定論で組めるなら Hook / CI / CLI / MCP / API に逃がせないか。
3. 文脈依存の判断が必要か。
4. 独立コンテキストが必要か。
5. 必要なら Subagent、そうでなければ Skill とする。

禁止語チェック、format、lint、schema validation、API 呼び出し、DB 更新のように機械で確実に処理できるものは Skill に戻さない。Skill は「どの検査をいつ使うか」「結果をどう解釈するか」「複数手段をどう使い分けるか」に集中する。

### 4.3 実装層の昇華ラダー

ローカル shell 環境では、実装層は次の 4 段階で育てる。

| 段階 | 内容 | 昇格トリガー | Skill への影響 |
|---|---|---|---|
| 1 | 既存 CLI を組み合わせる | `git` / `gh` / `rg` / `jq` で足りる | Skill は順序とチーム規約だけを書く |
| 2 | 薄いスクリプトを書く | 3 ステップ以上、条件分岐、I/O 整形が必要 | Skill からスクリプトを呼ぶ |
| 3 | 自作 CLI に昇華する | API キー、認証、キャッシュ、設定、状態が必要 | Skill 本文はさらに薄くなる |
| 4 | 自作 CLI と既存 CLI を組み合わせる | 小さなアプリとして運用したい | Skill は目的別 API 面を使う手順を書く |

## 5. Claude Code Skill の公式仕様と YAML 設定設計

この章は、元記事に含まれる内容に加え、2026-05-17 時点で公式 Claude Code Docs に記載されている Skill 設定項目を統合したものである。公式ドキュメント上、Skill は `SKILL.md` の YAML frontmatter と Markdown 本文で構成される。すべての frontmatter フィールドは任意だが、`description` は Claude がいつ使うかを判断するため推奨される。

### 5.1 Skill の配置場所と優先順位

| スコープ | パス | 適用範囲 |
|---|---|---|
| Enterprise | managed settings | 組織の全ユーザー |
| Personal | `~/.claude/skills/<skill-name>/SKILL.md` | すべてのプロジェクト |
| Project | `.claude/skills/<skill-name>/SKILL.md` | 対象プロジェクト |
| Plugin | `<plugin>/skills/<skill-name>/SKILL.md` | plugin 有効時 |

同名 Skill が複数スコープに存在する場合、enterprise が personal を上書きし、personal が project を上書きする。Plugin Skill は `plugin-name:skill-name` の namespace を持つため、他スコープと衝突しない。

### 5.2 SKILL.md の 2 部構成

| 部分 | 役割 |
|---|---|
| YAML frontmatter | Claude に「いつこの Skill を使うべきか」「どう呼び出せるか」「どの実行設定を使うか」を伝える |
| Markdown 本文 | Skill が呼ばれたときに Claude が読む手順・知識・制約・出力契約 |

### 5.3 公式 frontmatter フィールド一覧

| フィールド | 必須 | 用途 | 設計上の注意 |
|---|---:|---|---|
| `name` | 任意 | Skill の表示名。省略時はディレクトリ名 | lowercase letters / numbers / hyphens、最大 64 文字 |
| `description` | 推奨 | 何をするか、いつ使うか | 人間向け要約ではなく、Claude が照合する発動条件。`when_to_use` と合わせて 1,536 文字 cap |
| `when_to_use` | 任意 | 発動条件の補足、トリガー例 | `description` に追加される。長くしすぎない |
| `argument-hint` | 任意 | `/skill` autocomplete 時に期待引数を示す | 例: `[issue-number]`, `[filename] [format]` |
| `arguments` | 任意 | 名前付き positional arguments | 文字列または YAML list。`$name` 置換に使う |
| `disable-model-invocation` | 任意 | Claude の自動ロードを防ぐ | 手動起動したい副作用強い Skill に使う。subagent preload も防ぐ。既定値 `false` |
| `user-invocable` | 任意 | `/` メニューから隠す | ユーザーが直接呼ぶ意味のない背景知識に使う。既定値 `true` |
| `allowed-tools` | 任意 | Skill active 中に承認なしで使える tool | deny ではない。未列挙 tool は通常の permission settings に従う |
| `model` | 任意 | Skill active 中の model override | 現在 turn のみ。次 prompt で session model に戻る。`inherit` 可 |
| `effort` | 任意 | Skill active 中の reasoning effort | `low` / `medium` / `high` / `xhigh` / `max`。利用可能値は model 依存 |
| `context` | 任意 | `fork` で forked subagent context 実行 | explicit task がある Skill に向く。参照知識だけだと subagent が動く仕事を持たない |
| `agent` | 任意 | `context: fork` 時の subagent type | `Explore` / `Plan` / `general-purpose` / custom subagent など |
| `hooks` | 任意 | Skill lifecycle に scope された hooks | hooks in skills and agents の形式に従う |
| `paths` | 任意 | 自動発動対象を file glob で制限 | ファイル作業時に pattern match する場合だけ自動ロードされる |
| `shell` | 任意 | `!` 動的注入で使う shell | `bash` 既定、`powershell` は Windows で `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` が必要 |

### 5.4 呼び出し制御マトリクス

| 設定 | ユーザーが `/skill` で呼べる | Claude / 親 Skill が呼べる | context loading |
|---|---|---|---|
| デフォルト | Yes | Yes | description は常駐、full content は invocation 時 |
| `disable-model-invocation: true` | Yes | No | description も context に載らない。手動 invocation 時のみ full content |
| `user-invocable: false` | No | Yes | description は常駐、full content は invocation 時 |

重要な注意点:

- `user-invocable: false` はメニュー非表示であり、Claude の Skill tool access を禁止しない。
- programmatic invocation を止めたい場合は `disable-model-invocation: true` を使う。
- `assign-*` のように親 Skill から呼ばれる internal Skill に `disable-model-invocation: true` を付けると、親からも呼べなくなる。
- 両方を雑に併用すると、ユーザーからも Claude からも使えない Skill になり得る。
- さらに厳密に制御する場合は permission rules で `Skill(name)` または `Skill(name *)` を allow / deny する。

### 5.5 `allowed-tools` の設計

`allowed-tools` は「この tool だけを使える」という制限ではなく、列挙した tool を承認なしで使えるようにする allow-list である。書き込みを止めたい場合は permission settings の deny rule を使う。

例:

```yaml
---
name: commit
description: Stage and commit the current changes
disable-model-invocation: true
allowed-tools:
  - Bash(git add *)
  - Bash(git commit *)
  - Bash(git status *)
---
```

設計原則:

- 副作用が強い tool は `disable-model-invocation: true` と組み合わせる。
- Project Skill の `allowed-tools` は repository trust と結びつくため、共有 repo に置く場合はレビュー対象にする。
- 本当に禁止したい操作は `allowed-tools` ではなく permissions deny で止める。

### 5.6 引数と文字列置換

Skill 本文では以下の置換が使える。

| 置換 | 意味 |
|---|---|
| `$ARGUMENTS` | Skill invocation 後の全引数 |
| `$ARGUMENTS[N]` | 0-based の N 番目引数 |
| `$N` | `$ARGUMENTS[N]` の短縮形 |
| `$name` | `arguments` frontmatter で宣言した名前付き引数 |
| `${CLAUDE_SESSION_ID}` | 現在の session ID |
| `${CLAUDE_EFFORT}` | 現在の effort level |
| `${CLAUDE_SKILL_DIR}` | Skill ディレクトリ。bundled script / reference 参照に使う |

例:

```yaml
---
name: migrate-component
description: Migrate a component from one framework to another
arguments: [component, from, to]
argument-hint: "[component] [from] [to]"
---

Migrate `$component` from `$from` to `$to`.
```

### 5.7 動的コンテキスト注入

`!` 構文は、Skill content が Claude に渡る前に shell command を実行し、その stdout を本文へ埋め込む仕組みである。Claude が Bash tool を呼ぶのではなく、Claude が見る前に prompt がレンダリングされる。

主用途:

- `git diff`, `git status`, `gh pr diff` などの決定論的な事実取得
- `jq` による JSON 整形
- `node --version`, `npm --version` など環境情報注入

例:

```markdown
## Pull request context

- PR diff: !`gh pr diff`
- PR comments: !`gh pr view --comments`
- Changed files: !`gh pr diff --name-only`
```

複数行:

````markdown
```!
node --version
npm --version
git status --short
```
````

注意:

- command output は plain text として挿入され、再スキャンされない。
- 外部 LLM CLI を `!` で呼ぶ場合、その出力は未信頼入力として扱う。
- 決定論的 facts と外部 LLM opinion は見出しで分離する。
- 必要なら外部 LLM 呼び出しは `delegate-*` または forked subagent 側へ隔離する。
- `disableSkillShellExecution` 設定で user/project/plugin/additional-directory source の shell injection を無効化できる。

### 5.8 `context: fork` と Subagent

`context: fork` を付けると、Skill content が subagent の task prompt になり、別コンテキストで実行される。親会話の履歴にはアクセスしない。

向いている用途:

- 重い調査
- 初見レビュー
- 評価器
- 長い作業の分離
- 大量資料の読み込みを親会話に残したくない場合

向いていない用途:

- 単なる guidelines
- 参照知識だけの Skill
- task prompt がなく、subagent が何を返せばよいか不明な Skill

Skill と Subagent の 2 方向:

| Approach | System prompt | Task | Also loads |
|---|---|---|---|
| Skill with `context: fork` | `agent` type | SKILL.md content | CLAUDE.md |
| Subagent with `skills` field | Subagent markdown body | delegation message | preloaded skills + CLAUDE.md |

### 5.9 Skill content lifecycle と compaction

Skill が呼ばれると、rendered `SKILL.md` content は 1 つの message として会話に入り、session 中に残る。後続 turn でファイルを自動再読込するわけではない。

Auto-compaction 後は、最近呼ばれた Skill から順に再付与される。公式仕様では、各 Skill の先頭 5,000 tokens、合計 25,000 tokens までが対象で、古い Skill は丸ごと落ちる場合がある。

設計への含意:

- 最重要ルールは冒頭 30 行へ置く。
- output contract と禁則は先頭側へ置く。
- 長い表・例・API 仕様は補助ファイルへ逃がす。
- 重要 Skill は必要に応じて再 invocation できる前提で設計する。

### 5.10 `skillOverrides` による visibility 管理

`skillOverrides` は settings 側で Skill visibility を制御する。共有 repo の Skill や編集したくない Skill に対して使える。

| 値 | Claude に listed | `/` menu |
|---|---|---|
| `"on"` | name + description | Yes |
| `"name-only"` | name only | Yes |
| `"user-invocable-only"` | Hidden | Yes |
| `"off"` | Hidden | Hidden |

例:

```json
{
  "skillOverrides": {
    "legacy-context": "name-only",
    "deploy": "off"
  }
}
```

## 6. Progressive Disclosure 設計

### 6.1 3 層構造

| 層 | 何がロードされるか | いつロードされるか | token コスト |
|---|---|---|---|
| 入口情報 | `name` + `description` / `when_to_use` | session 開始時に常駐。ただし `disable-model-invocation: true` は例外 | Skill 1 個あたり数十 token |
| SKILL.md 本文 | frontmatter 以下の本文全文 | Claude が関係あると判断して Skill を呼んだ時 | 数百〜数千 token |
| 補助ファイル | `reference.md`, `examples/`, `scripts/` など | Claude が能動的に Read / 実行した時 | ファイル単位 |

### 6.2 3 つの失敗

| 失敗 | 何が悪いか | 直し方 |
|---|---|---|
| 全部を `SKILL.md` に詰め込む | 発動した瞬間に大量 context を消費し、重要指示が埋もれる | 本文は最小手順、判断分岐、補助ファイル案内に絞る |
| 補助ファイルを置いたのに案内しない | Claude が補助ファイルへ辿れず、情報を隠しただけになる | `Additional resources` で何がいつ必要かを明記 |
| 読ませた情報を親会話に残し続ける | 複数 Skill / 参照資料が積み上がり、古い情報が判断に混ざる | 重い調査・評価は `context: fork` に任せ、親には短い結論だけ戻す |

### 6.3 推奨ディレクトリ構造

```text
my-skill/
├── SKILL.md
├── reference.md
├── examples/
│   └── sample.md
└── scripts/
    └── validate.sh
```

`SKILL.md` は 500 行未満を目安にする。ただし本質は行数ではなく、最初から読ませるべき情報だけを残すことである。

## 7. Skill の最初の分類: 辞書型 / ワークフロー型

最初に見るべき問いは 1 つだけである。

その Skill は副作用を持つか。

| 種類 | 副作用 | 役割 | 例 |
|---|---|---|---|
| 辞書型 | なし | 知識・基準・文脈を注入する | API 規約、設計原則、業務知識、レビュー観点 |
| ワークフロー型 | あり | 手順を実行し、成果物や状態変化を作る | デプロイ、レポート生成、レビュー JSON 出力、コード修正 |

副作用の例:

- ファイルを作る
- ファイルを編集する
- コマンドを実行する
- API を呼び出す
- DB を更新する
- チケットを作る
- メールを送る

辞書型とワークフロー型は混ぜない。設計原則を読ませる Skill と、実際に修正する Skill は分ける。ワークフロー側が辞書側を参照すればよい。

### 7.1 CLAUDE.md / ref-* / docs のメモリ濃度

| メモリ層 | 常駐度 | token コスト | 想定用途 |
|---|---|---|---|
| `CLAUDE.md` | 常時 hot context | 重い | プロジェクト全体の必須規約、毎回知らせたい禁則 |
| `ref-*` Skill | Skill index に入口情報だけ常駐、本文は発動時 | 中 | 領域固有の規約・設計原則・レビュー観点 |
| `docs/` | 探されなければ触れない | 0 | 人間が直接読む静的文書、ADR、議事録 |

`ref-*` は `CLAUDE.md` ほど常時持たせたくないが、`docs/` のように探されないと存在に気づかれないのも困る知識の置き場である。

## 8. 4 軸分類: Purpose / Trigger / Shape / Role

### 8.1 4 軸一覧

| 軸 | 値 | 問い |
|---|---|---|
| Purpose | `knowledge` / `produce` / `judge` / `pass-through` | 呼ぶと何が返るか |
| Trigger | `user` / `internal` / `both` | 誰が呼ぶか |
| Shape | `atomic` / `forked` / `orchestrated` | 内部構造は単純か、分離・複合か |
| Role | `generator` / `evaluator` / `contributor` / `delegate` / `null` | 評価ループや委譲構造の中で何役か |

### 8.2 Purpose

| 値 | 意味 | 典型例 |
|---|---|---|
| `knowledge` | 知識注入のみ | 設計原則、API 規約、ドメイン知識 |
| `produce` | 成果物や状態変化を作る | レポート生成、画像生成、ファイル編集 |
| `judge` | 評価結果を返す | レビュー、採点、品質評価 |
| `pass-through` | 外部 LLM / agent に委譲する | Codex / Gemini / 別 agent への丸投げ |

### 8.3 Trigger

| 値 | 意味 | frontmatter の典型 |
|---|---|---|
| `user` | ユーザーが直接呼ぶ | `user-invocable: true`。副作用が強ければ `disable-model-invocation: true` |
| `internal` | Claude や親 Skill が内部的に呼ぶ | `assign-*` は `user-invocable: false`。Read 経由専用 `ref-*` は `disable-model-invocation: true` も可 |
| `both` | 直接呼び出しも内部呼び出しも許す | デフォルト、または本文に両対応の分岐 |

### 8.4 Shape

| 値 | 意味 |
|---|---|
| `atomic` | 1 つのコンテキストで完結する |
| `forked` | `context: fork` や Subagent で独立コンテキストを使う |
| `orchestrated` | 複数フェーズ、ループ、並列、複数 Skill の指揮を行う |

### 8.5 Role

| 値 | 意味 |
|---|---|
| `generator` | 成果物を作る側 |
| `evaluator` | 成果物を評価する側。`context: fork` で別コンテキスト実行が必須 |
| `contributor` | 共有ボードや複数視点の 1 役として参加する側 |
| `delegate` | 外部 LLM / agent へ処理を委譲する側 |
| `null` | 上記に該当しない通常 Skill |

### 8.6 4 軸の限界

4 軸は数学的な分類表ではなく、設計レビュー用の問いである。

| ズレ | 何が起きるか | 扱い方 |
|---|---|---|
| `Purpose=judge` と `Role=evaluator` | 出力と役割が近い | Purpose は出力、Role はループ内役割 |
| `Purpose=pass-through` と `Role=delegate` | 委譲を 2 方向から表す | Purpose は処理種別、Role は構造上の役割 |
| Trigger | internal で始めた Skill を後から直接呼びたくなる | frontmatter と運用実態がずれたら見直す |
| Shape | atomic が処理追加で orchestrated に育つ | 実装が重くなった時点で再分類 |
| `wrap-*` と `run-*` | 4 軸だけでは区別できない | `base:` による派生関係を二次分岐として扱う |

## 9. 5 prefix 命名規約

### 9.1 prefix 一覧

| prefix | 役割 | Purpose | 典型 Trigger |
|---|---|---|---|
| `ref-*` | 参照知識 | `knowledge` | `internal` / `both` |
| `run-*` | ユーザーが直接使う独立ワークフロー | `produce` | `user` |
| `wrap-*` | 既存 Skill の派生ラッパー | `produce` | `user` |
| `assign-*` | 内部から役割付きで呼ばれる Skill | `produce` / `judge` / `pass-through` | `internal` |
| `delegate-*` | 外部 LLM / agent への委譲 | `pass-through` | `user` |

`assign-` は family 名であり、実際には `assign-*-generator`、`assign-*-evaluator`、`assign-*-contributor` のように role suffix を付ける。

### 9.2 prefix 決定木

1. `Purpose=knowledge` なら `ref-*`
2. `Purpose=judge` なら `assign-*-evaluator`
3. `Purpose=pass-through` かつ user 直叩きなら `delegate-*`
4. `Purpose=pass-through` かつ internal なら `assign-*-delegate` または `assign-*-generator`
5. `Role=generator` かつ internal なら `assign-*-generator`
6. `Trigger=user` かつ派生元 `base:` があるなら `wrap-*`
7. `Trigger=user` かつ派生元がないなら `run-*`
8. internal で役割付きなら `assign-*-{role}`

### 9.3 名前は契約

prefix を見た瞬間、Claude と人間は次の事前条件を置く。

| prefix | 事前条件 |
|---|---|
| `ref-*` | 副作用ゼロ、read-only、純粋知識 |
| `run-*` | ユーザーが直接叩く独立ワークフロー、副作用は契約上明示 |
| `wrap-*` | 既存 Skill の派生、契約は `base:` 側を継承 |
| `assign-*-evaluator` | fork で独立コンテキストの採点器。評価基準を触らない |
| `delegate-*` | 外部 LLM / agent への丸投げ。品質保証は薄く、未信頼入力扱い |

命名を破ると、呼び出し側の前提が壊れる。命名規約は見た目ではなく、依存関係と安全性の契約である。

### 9.4 独自メタデータ

次のフィールドは Claude Code 公式制御フィールドではなく、設計体系・棚卸し・lint のための独自メタデータである。

| 独自メタデータ | 用途 | 対象 |
|---|---|---|
| `base:` | 派生元 Skill を示す | `wrap-*` |
| `pair:` | generator / evaluator の相方を示す | `assign-*-generator` / `assign-*-evaluator` |
| `kind:` | 参照知識の粒度を示す | `ref-*` |
| `owner:` | 保守責任者を示す | 全 Skill |
| `since:` | 導入時期を示す | 全 Skill |
| `deprecated_in:` | 廃止予定を示す | 移行中 Skill |
| `replaces:` | 置換元を示す | rename / refactor 時 |

Claude Code はこれらを読まない。だからこそ、grep / yq / lint / CI で棚卸し・依存グラフ化・孤児検出ができる。

## 10. 読まれる Skill 本文を書く規範

### 10.1 Less is More

Skill は人間への教材ではなく、エージェントの行動を変える設計文書である。Claude が一般知識として知っている可能性が高い情報を書き連ねると、プロジェクト固有情報が埋もれる。

| 書くべき | 書かなくてよい |
|---|---|
| プロジェクト固有の制約 | 一般的な CLI の使い方 |
| この Skill 固有の失敗パターン | Markdown / JSON / YAML の基本構文 |
| 採用した方針と理由 | 検討したが採用しなかった案の長い経緯 |
| 業務ドメイン固有のルール | 一般的なプログラミング知識 |
| 出力形式、禁止事項、完了条件 | 抽象的な「高品質にしてください」 |

### 10.2 Why-driven

強い命令よりも理由を書く。LLM は強調ではなく妥当性で従うかを判断する。`ALWAYS` / `NEVER` を書きたくなったら、理由を添えて通常文に直す。

悪い例:

```markdown
ALWAYS validate input before passing to API.
NEVER call the deploy endpoint without confirmation.
```

良い例:

```markdown
API 呼び出し前に input を validate する。
validation failure は API 側でリトライできず、上流で 400 を返すと orchestrator が無駄な再実行を走らせる。手前で止めればループ予算を節約できる。

Deploy endpoint はユーザー確認なしで呼ばない。
本番反映は副作用が不可逆で、巻き戻しに人間判断が要る。
```

### 10.3 条件付き重要ルール

特定状況だけ効かせたいルールは、条件で囲む。

```xml
<important if="you are writing or modifying tests">
- Use `createTestApp()` helper for integration tests.
- Mock database with `dbMock` from `packages/db/test`.
- Snapshot files are generated by CI and should not be edited manually.
</important>
```

何でも `<important>` にしない。条件は「テストを書く」「`.claude/settings.json` を変更する」「PR を作る」のように具体化する。

## 11. Gotchas と決定論への昇格

Gotchas は LLM が実際に踏んだ落とし穴の記録である。一般論ではなく、運用から出た失敗を書く。

良い Gotcha の条件:

- 見出しだけで何が罠か分かる。
- 本文 1〜2 行で why と回避を書く。
- コマンド名、フラグ名、閾値、ファイルパスなどで検証可能にする。
- 古くなったら削る。

### 11.1 昇格ラダー

| 段階 | 仕組み | 重さ | 検出タイミング |
|---:|---|---|---|
| 1 | Gotchas に書く | LLM 注意力依存 | 推論時、運に左右される |
| 2 | 軽い決定論: schema validation / frontmatter lint / Hook / permissions.deny | 設定ファイルレベル | commit 時 / 起動時 |
| 3 | 重い決定論: `validate.sh --all`, `check-pair.sh` などを CI に組み込む | コードレベル | CI 通過必須 |
| 4 | ツール化: CLI app や lint plugin に切り出す | 製品レベル | 開発フロー全体 |

昇格判断は、再発頻度、ブラスト半径、検出可能性で決める。決定論で書けるものは Gotchas ではなく lint / Hook / CI に寄せる。

## 12. 評価駆動の Skill 運用

### 12.1 自己申告を完了判定にしない

ワークフロー型 Skill の最大の罠は、Claude の「完了しました」「問題ありません」「高品質に仕上げました」を完了判定にすることである。これらは output ではない。

生成する agent と評価する agent を同じ文脈で動かすと、作り手の意図や文脈を知っているため評価が甘くなりやすい。これは sycophancy、つまり自己迎合的な評価ループとして扱う。

### 12.2 Generator / Evaluator 分離

| 役割 | Skill 名の例 | 仕事 |
|---|---|---|
| Generator | `assign-pr-review-generator` | 成果物を作る |
| Evaluator | `assign-pr-review-evaluator` | 成果物を採点する |

設計条件:

- Evaluator は `context: fork` で別コンテキスト実行する。
- Generator の内部思考や作成意図を渡さない。
- 受け渡しはファイルや artifact 経由にする。
- Evaluator は評価基準を編集しない。
- 出力は JSON など機械可読形式にする。

推奨評価 JSON:

```json
{
  "score": 82,
  "passed": true,
  "threshold": 80,
  "findings": [
    {
      "severity": "medium",
      "item": "説明画像の引用",
      "message": "画像由来の設計ルールは抽出されているが、元画像IDとの対応が不足している"
    }
  ],
  "required_fixes": []
}
```

### 12.3 再実行ループ

基本ループ:

```text
Generator
  -> Artifact
  -> Evaluator
  -> score < threshold なら Generator へ戻す
  -> passed なら Done
```

上位 orchestrator は専用 Skill でなくてもよい。Generator と Evaluator の `pair:` が揃っていれば、汎用指揮役が再実行制御できる。

## 13. スキル作成のための標準設計テンプレート

### 13.1 設計前チェック

1. これは決定論で処理できるか。
2. Hook / CI / CLI / MCP / API で解くべきではないか。
3. 副作用はあるか。
4. 辞書型か、ワークフロー型か。
5. 4 軸を埋められるか。
6. prefix は決定木と一致するか。
7. 重要ルールは先頭 30 行にあるか。
8. output contract は明確か。
9. 評価器が必要か。
10. Gotchas に留めず lint / Hook / CI に昇格すべき項目はないか。

### 13.2 標準 frontmatter テンプレート

```yaml
---
name: run-example-workflow
description: "Example workflow. Use when the user asks to generate the example artifact."
when_to_use: "Use for example artifact generation requests; do not use for generic explanation."
argument-hint: "[input-file] [output-format]"
arguments: [input_file, output_format]
disable-model-invocation: true
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
model: inherit
effort: medium
context: fork
agent: general-purpose
paths:
  - "examples/**"
shell: bash

# Independent design metadata; Claude Code does not enforce these.
kind: workflow
owner: team-ai
since: "2026-05-17"
pair: assign-example-evaluator
---
```

### 13.3 `ref-*` テンプレート

```yaml
---
name: ref-api-conventions
description: "API conventions. Use when designing or reviewing API endpoints in this repository."
disable-model-invocation: true
user-invocable: false
kind: atomic
---

# API conventions

Use this reference when endpoint naming, error format, or validation policy matters.

## Core rules

- ...

## Additional resources

- Detailed examples: [examples/api.md](examples/api.md)
```

### 13.4 `run-*` テンプレート

```yaml
---
name: run-release-check
description: "Release check workflow. Use when the user asks to prepare or verify a release."
disable-model-invocation: true
argument-hint: "[version]"
allowed-tools:
  - Bash(git status *)
  - Bash(gh *)
---

# Release check

Output contract:
- release summary
- blocking issues
- changed files
- next action

Steps:
1. ...
```

### 13.5 `assign-*-evaluator` テンプレート

```yaml
---
name: assign-skill-review-evaluator
description: "Skill review evaluator. Use internally to judge SKILL.md design against the rubric."
user-invocable: false
context: fork
agent: general-purpose
allowed-tools:
  - Read
  - Grep
pair: assign-skill-review-generator
kind: evaluator
---

# Evaluator contract

Evaluate the submitted artifact only. Do not edit the artifact or the rubric.

Return JSON:

{
  "score": 0,
  "passed": false,
  "findings": [],
  "required_fixes": []
}
```

## 14. 設計レビュー用チェックリスト

### 14.1 frontmatter

- `description` は発動条件になっているか。
- `description` は処理手順や出力形式を書きすぎていないか。
- trigger phrase は 2 個前後に絞られているか。
- 副作用が強い user Skill に `disable-model-invocation: true` があるか。
- internal Skill に `user-invocable: false` があるか。
- internal Skill に誤って `disable-model-invocation: true` を付けていないか。
- `allowed-tools` を deny と誤解していないか。
- `context: fork` の Skill は explicit task を持っているか。
- `paths` を使うべき file-specific Skill ではないか。
- `model` / `effort` override が本当に必要か。

### 14.2 本文

- 先頭 30 行で目的、出力、禁則が分かるか。
- 一般知識の写経になっていないか。
- プロジェクト固有ルールに理由が添えられているか。
- 補助ファイルへの案内があるか。
- output contract があるか。
- Gotchas は短く、検証可能か。
- stale Gotcha が残っていないか。

### 14.3 オーケストレーション

- Generator と Evaluator が分離されているか。
- Evaluator は forked context で動くか。
- 評価基準を Evaluator が編集できないようにしているか。
- `pair:` が正しいか。
- `base:` の派生関係が正しいか。
- prefix から 4 軸を復元できるか。
- 決定論で守れるルールを LLM の注意力に頼っていないか。

## 15. 参考情報

- Claude Code Docs, Extend Claude with skills: https://code.claude.com/docs/en/skills
- 参照元 Markdown: `skills/doc/【コード共有有】Agent Skill大全 数百本のSkillをり続けた実践知から導いたオーケストレーション設計の概念体系Byまさおさん.md`
- OCR 出力: `skills/analysis/ocr-all.txt`

