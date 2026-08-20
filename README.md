# skills

`skills` は、Claude Code を強化する **plugin 群** (機能拡張パッケージ) です。Claude Code に「スキルを作る」「品質を検査する」「非エンジニアからヒアリングする」といった能力を後から追加できます。

> **plugin (プラグイン)**: Claude Code 本体を書き換えずに、後から機能を足すための小さな部品。スマートフォンアプリのようなものと考えてください。

---

## このドキュメントの読み方

- **インストールしたい方** → [Part 1: インストール手順](#part-1-インストール手順) を順番に実行
- **API キーを設定したい方** → [Part 2: API キーの安全な保存 (Keychain)](#part-2-api-キーの安全な保存-keychain)
- **どの plugin を入れるか迷う方** → [Part 3: plugin 一覧と役割](#part-3-plugin-一覧と役割)
- **plugin の中身を理解したい方** → [Part 4: plugin の仕組み](#part-4-plugin-の仕組み)

---

# Part 1: インストール手順

このリポジトリの plugin を入れる入口は **2 つ**あります。用途で選んでください。

| 入口 | 入る plugin | clone | 手順 |
|---|---|---|---|
| **公開 marketplace** (`skills`) | 配布可の 20 個 | 不要 | Step 1〜3 |
| **ローカル marketplace** (`harness-local`) | **全 23 個**（非配布を含む） | 必要 | Step 4 |

`harness-creator` / `prompt-creator` / `plugin-dev-planner` の
**開発・個人利用向け plugin は公開 marketplace に載りません**。これは事故防止の意図的な設計で、
`.claude-plugin/marketplace.json` に `distributable: false` の plugin を書くと
`validate-plugin-completeness.py` が fail-closed で拒否します。これらを使うには Step 4 へ進んでください。

> **marketplace (マーケットプレイス)**: plugin が並んでいるお店のような場所。`skills` 自体が 1 つのお店で、その中に複数の plugin が並んでいます。

## Step 0: 前提を確認する

Claude Code CLI が動く環境が必要です。

```bash
claude --version
# → claude code x.y.z が表示されれば OK
```

> ❌ 入っていなければ公式ガイド <https://docs.claude.com/claude-code/setup> を参照してください。

## Step 1: marketplace を追加する

Claude Code セッションを起動し、以下を打ちます。

```text
/plugin marketplace add daishiman/harness-dev
```

これで「skills というお店」が Claude Code に登録されます。

> 📌 **リポジトリ名と marketplace 名は別物です。** `marketplace add` に渡すのは
> **リポジトリ名** `daishiman/harness-dev`、`install` の `@` の後ろに付けるのは
> **marketplace 名** `skills` (`.claude-plugin/marketplace.json` の `name`) です。

✅ **確認**:

```text
/plugin marketplace list
```

`skills` が表示されれば成功。

## Step 2: plugin をインストールする

用途に合わせて選んでください。**まずは最小構成から始めることをおすすめします。**

### 2a. 最小構成 (やりたいことを Skill 化する入口だけ)

```text
/plugin install skill-intake@skills
```

`skill-intake` は公式 `plugin.json.dependencies` で共通runtimeの
`skill-governance-adapters` を宣言しています。Claude Code は同じ
marketplace から依存pluginを自動導入・有効化するため、個別installでも
project-scopeの外部知能hookが欠落しません。

> ⚠️ Skill 本体を作る `harness-creator`、プロンプトを作る `prompt-creator` は**非配布**のため
> ここでは入りません。**Step 4** のローカル marketplace 経由で入れてください。

### 2b. 標準構成 (品質検査も使う)

最小構成 + governance (運用検査) を追加:

```text
/plugin install skill-governance-config@skills
/plugin install skill-governance-lint@skills
/plugin install skill-governance-hooks@skills
```

### 2c. フル構成 (全部入り)

Claude Code の marketplace でinstallできる名前は `marketplace.json` の
pluginだけです。`skills-full` はplugin名ではなく、このリポジトリの
決定論的な一括installリストです。次の実在するインストーラーを使います。

```bash
git clone https://github.com/daishiman/harness-dev.git
cd harness-dev
bash scripts/install-bundle.sh skills-full
```

`skills-intake` も同じscriptの引数として選べます。scriptは
`.claude-plugin/bundles.json` の各pluginを実在する `name@marketplace` へ展開します。
各consumerも公式dependenciesを持つため、一括・個別のどちらでも共通runtimeは
依存閉包に含まれます。

✅ **確認**:

```text
/plugin list
```

入れた plugin が `installed` と表示されれば成功。

## Step 3: 動作確認

Claude Code セッション内で以下を打ち、補完候補に出ることを確認します。

```text
/skill-intake:run-skill-intake
```

実行が始まれば成功。一旦キャンセル (`Ctrl-C` または「やめる」と返答) して構いません。

## Step 4: 全 plugin を入れる (ローカル marketplace)

非配布 plugin (`harness-creator` `prompt-creator` `plugin-dev-planner`) は
公開 marketplace に載らないため、**手元の clone を 2 枚目の marketplace として登録**します。
配布ではなく、自分の clone を Claude Code へ束ねて見せるだけです。

> ⚠️ **install は copy です。** source がローカル実体を指していても、実体は
> `~/.claude/plugins/cache/harness-local/<name>/<version>/` へコピーされ、
> `installed_plugins.json` に commit SHA が固定されます。**clone 側を編集しても
> install 済み plugin には反映されません** (2026-08-11 実測)。反映手順は 4-4 参照。

### 4-1. clone して marketplace を生成する

```bash
git clone <this-repo> harness && cd harness
python3 scripts/build-local-marketplace.py
```

`marketplaces/local/.claude-plugin/marketplace.json` に**全 23 plugin** が書き出されます。

### 4-2. 絶対パスで登録する

`marketplace add` にはリポジトリ名ではなく `marketplaces/local` の**絶対パス**を渡します。

```bash
python3 -c "import pathlib; print(pathlib.Path('marketplaces/local').resolve())"
```

出力されたパスを使って、Claude Code セッション内で:

```text
/plugin marketplace add <出力された絶対パス>
/plugin marketplace list
```

`harness-local` が表示されれば成功。

### 4-3. インストールする

サフィックスは `@skills` ではなく **`@harness-local`** です。

```text
/plugin install harness-creator@harness-local
/plugin install ubm-goal-setting@harness-local
```

### 4-4. 変更を反映する

plugin を編集したら **`version` を上げてから**再生成します。install は copy でありキャッシュが
version 単位のため、version 据え置きの編集は install 側へ届きません。

```bash
python3 scripts/build-local-marketplace.py --check   # ズレていれば exit 1
python3 scripts/build-local-marketplace.py           # 再生成
```

そのうえで Claude Code セッション内で:

```text
/plugin marketplace update harness-local
/plugin update <name>@harness-local
```

`make lint` がこの `--check` を実行するため、再生成漏れは CI で赤化します。

## Step 5: アップデート / アンインストール

```text
# アップデート (公開)
/plugin marketplace update skills
/plugin update skill-intake@skills

# アップデート (ローカル) — clone を git pull した後に
/plugin marketplace update harness-local

# アンインストール
/plugin uninstall skill-intake@skills
/plugin marketplace remove skills
```

## トラブルシュート

| 症状 | 対処 |
|---|---|
| `/plugin` コマンドが効かない | Claude Code のバージョンが古い可能性。`claude --version` を確認し最新化 |
| `marketplace add` で `not found` | リポジトリ名を確認。`daishiman/harness-dev` が正しい (旧名 `manju/skills` は存在しません) |
| `install` で `authentication failed` | `gh auth login` でログイン。現在このリポジトリは public です |
| PR をマージしたのに新しい plugin が出てこない | ① `/plugin marketplace update skills` で目録を取り直す ② それでも出ないなら**非配布 plugin**。`.claude-plugin/marketplace.json` に載っているか確認し、無ければ **Step 4** 経由 |
| Skill が補完に出ない | `/plugin list` で `installed` か確認、無ければ再 install |
| 入れたい plugin が一覧に出ない | 非配布 plugin の可能性。**Step 4** のローカル marketplace 経由で入れる |
| `source: Invalid input` で install 失敗 | `marketplaces/local/plugins` symlink が壊れている。`build-local-marketplace.py` を再実行 |
| clone を編集したのに install 側が古い | `build-local-marketplace.py` で再生成し `/plugin marketplace update harness-local` |

---

# Part 2: API キーの安全な保存 (Keychain)

`skill-intake` plugin など、外部サービス (Notion 等) を呼ぶ plugin は **API キー (秘密の合言葉)** が必要です。

skills では API キーを **コード・ファイル・環境変数に書かず、Mac の Keychain (キーチェーン) に保存**する方針を取っています。

> **Keychain (キーチェーン)**: Mac に標準で入っている、パスワードや秘密情報を安全に保管してくれる金庫のような仕組み。Safari のパスワード保存にも使われています。

## なぜ Keychain を使うのか?

- `.env` ファイルや環境変数に書くと **間違って git に commit してしまう**事故が起きやすい
- Keychain は OS レベルで暗号化されており、他人が覗けない
- Mac ログイン中だけ取り出せるので、自動で守られる

## Step 1: Keychain に API キーを登録する

例として Notion の API キー (Internal Integration Token) を登録します。Mac のターミナルで実行:

```bash
security add-generic-password \
  -s "notion-api-key.skills" \
  -a "skills" \
  -w "ntn_xxxxxxxxxxxxxxxxxxx" \
  -U
```

- `-s` … サービス名 (=Keychain 内の項目名。plugin が読みに行く名前)
- `-a` … アカウント名 (=どの用途で使うかの区別)
- `-w` … 実際の API キー (この値だけは秘密に)
- `-U` … 既にあれば更新

> 💡 上のコマンドは履歴に API キーが残ります。`-w` を省略するとターミナルが対話的にキーを聞いてくれるので、その方が安全です。

## Step 2: 登録できたか確認

```bash
security find-generic-password -s "notion-api-key.skills" -a "skills" >/dev/null
```

終了コードが `0` なら登録成功。API キー本体は表示しません。

## Step 3: plugin が読みに行くサービス名

各 plugin が期待する Keychain のサービス名は以下です。**この名前で登録してください。**

| plugin | サービス名 (-s) | アカウント名 (-a) | 用途 |
|---|---|---|---|
| `skill-intake` | `notion-api-key.skills` | `skills` | Notion ページ作成 |

このリポジトリでは `.notion-config.json` の `keychain_service` / `keychain_account` が正本です。

## 環境変数で上書きしたい場合

CI など Keychain が使えない環境では、以下の環境変数で上書きできます。

```bash
export NOTION_CONFIG_PATH="/path/to/.notion-config.json"
```

通常の利用では上書き不要です。

---

# Part 3: plugin 一覧と役割

`skills` には複数の plugin が入っており、それぞれ役割が分かれています。「料理に例えると」のイメージで読んでください。

## 中核 plugin (まず入れる)

| plugin | 役割 | 料理例 |
|---|---|---|
| **harness-creator** | Skill (作業手順書) を作る・更新する・評価する司令塔 | レシピを設計するシェフ |
| **prompt-creator** | Skill の中で使う「AI への指示文」を 7 層構造で作る | 調味料の配合表を作る人 |
| **skill-intake** | 非エンジニアからヒアリングして Skill 要件を引き出す | お客様の好みを聞き取る接客係 |

## 運用検査 plugin (品質を保つ)

`skill-governance-*` という名前の plugin は、Skill の **品質を機械的に検査する仕組み** を提供します。手作りの料理が衛生基準を満たしているか確認する保健所のような役割です。

| plugin | 役割 |
|---|---|
| **skill-governance-config** | 共通設定の置き場 (出力先 adapter / rubric 採点表 / routing ルール) |
| **skill-governance-lint** | Skill の命名・依存方向・frontmatter (ヘッダ情報) を機械チェック |
| **skill-governance-hooks** | Claude Code のイベント (ファイル変更時など) に反応する検査スクリプト |
| **skill-governance-automation** | rubric (採点表) の合成、評価ログ管理、巻き戻し処理 |
| **skill-governance-adapters** | Notion / Google Sheets / Slack など外部サービスへの出力口 |
| **skill-governance-migration** | 古い形式の prompt や CLAUDE.md を Skill 形式へ移行 |
| **skill-governance-secrets** | API キー取得と「うっかり漏洩」検査 |

> **rubric (ルーブリック)**: 採点表のこと。「ここまでできたら 80 点」のように、Skill が良いか悪いかを数値化する物差し。
>
> **lint (リント)**: 自動チェックツールのこと。「ファイル名のルールが守られているか」「文字数が長すぎないか」を機械的に確認します。
>
> **hook (フック)**: 特定のタイミング (ファイルを変更したとき・コミットしようとしたときなど) に自動で走るスクリプト。

## どれを入れるべきか?

- **試してみたいだけ** → `harness-creator` + `prompt-creator` の 2 つ
- **チームで使う・品質を保ちたい** → 上記 + `skill-governance-config` / `lint` / `hooks` の 3 つ
- **非エンジニアからヒアリングしたい** → `skill-intake` を追加
- **全部試したい** → bundle `skills-full` で一括

---

# Part 4: plugin の仕組み

ここからは「plugin がどう動いているか」を知りたい方向けの解説です。インストールだけしたい方は読み飛ばして OK です。

## 4.1 plugin に入っている 4 つの部品

1 つの plugin の中には、以下の 4 種類の部品を入れることができます。Claude Code はそれぞれを別の方法で利用します。

| 部品 | 役割 | 利用方法 |
|---|---|---|
| **Skill (スキル)** | 作業手順書 + 知識資料 | `/harness-creator:run-skill-create` のようにスラッシュコマンドで呼ぶ。または AI が自動で発火条件を見て呼ぶ |
| **SubAgent (サブエージェント)** | 独立した別 AI として動く専門家 | Skill から呼ばれて、別の文脈で 1 つの仕事だけをこなす |
| **Hook (フック)** | 特定タイミングで自動実行されるスクリプト | ユーザーが直接呼ばない。「保存したら走る」「コマンド前に走る」など |
| **Slash Command (スラッシュコマンド)** | `/コマンド名` で呼べるショートカット | ユーザーが直接タイプする |

> **SubAgent (サブエージェント)**: 親 AI とは別の文脈で動く子分 AI。先入観を避けたいとき (例: 自分が書いた文章を客観的にレビューするとき) に使います。

### Skill とは具体的に何か?

Skill は **1 つのフォルダ** で、中に以下のような構造を持ちます。

```
plugins/harness-creator/skills/run-skill-create/
├── SKILL.md           ← 必須。何のスキルか、いつ呼ぶか、手順を書く
├── references/        ← 補助資料 (長い仕様書や採点表)
│   ├── resource-map.yaml  ← 補助資料の索引
│   └── ...
├── scripts/           ← Python スクリプト (機械的処理を担当)
└── prompts/           ← AI に渡す指示文の雛形
```

`SKILL.md` の冒頭には **frontmatter (フロントマター)** という設定欄があり、ここで「いつ Claude が自動でこのスキルを呼ぶか」を宣言します。

```yaml
---
name: run-skill-create
description: 新規スキルを作りたいとき、既存スキルを更新したいときに使う。
kind: run
---
```

### SubAgent とは?

SubAgent は **plugin の `agents/` フォルダに `.md` ファイル 1 つ**として置かれます。

```
plugins/skill-intake/agents/skill-intake-purpose-excavator.md
```

呼ばれると **新しい AI 文脈** で起動し、親 Claude の会話履歴を引きずらない状態で 1 つの仕事をします。

### Hook とは?

Hook は **plugin の `hooks/` フォルダ**にスクリプトとして置かれ、`settings.json` で「いつ走らせるか」を設定します。

```
plugins/skill-intake/hooks/pre-publish-secret-scrub.sh
```

例: 「Notion に公開する直前に、API キーが文章に混じっていないか自動チェック」など。

### Slash Command とは?

`/intake` のように打つだけで Skill を起動するショートカット。**plugin の `commands/` フォルダ**に置かれます。

```
plugins/skill-intake/commands/intake.md
```

## 4.2 plugin の最小構造

新しい plugin を作るなら、最低限以下があれば動きます。

```
plugins/my-plugin/
├── .claude-plugin/
│   └── plugin.json    ← この plugin の名前・バージョンなどの設定
├── skills/            ← Skill 群を置く (任意)
├── agents/            ← SubAgent を置く (任意)
├── hooks/             ← Hook を置く (任意)
└── commands/          ← Slash Command を置く (任意)
```

`plugin.json` の例:

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "私の作業を自動化する plugin"
}
```

## 4.3 marketplace にどう登録されているか

リポジトリ直下の `.claude-plugin/marketplace.json` が **plugin 一覧の目録**です。

```json
{
  "name": "skills",
  "plugins": [
    {"name": "harness-creator", "source": "./plugins/harness-creator"},
    {"name": "skill-intake",  "source": "./plugins/skill-intake"}
  ]
}
```

Claude Code は `/plugin marketplace add daishiman/harness-dev` を実行すると、この `marketplace.json` を読み、`plugins/` 配下から実体をキャッシュにコピーします。

## 4.4 `.claude/` と `~/.claude/` の役割

インストール後、ファイルがどこに置かれるかを整理します。

| 場所 | 中身 | 性質 |
|---|---|---|
| `plugins/<plugin>/` (リポジトリ内) | plugin の **正本** (オリジナル) | これが本物 |
| `~/.claude/plugins/...` (ホームディレクトリ) | Claude Code が自動で保持するキャッシュ | 自動管理、編集しない |
| `<repo>/.claude/skills/...` | 開発用の **派生 (symlink)** | `plugins/` の正本へのショートカット |

> **symlink (シンボリックリンク)**: ファイルの近道。実体は別の場所にあり、symlink はその場所を指すだけ。Windows のショートカットや、Mac の Finder の「エイリアス」と似た仕組み。

### なぜ symlink を使うのか?

リポジトリ内では `plugins/` が正本ですが、Claude Code は本来 `~/.claude/` 配下しか見ないため、**開発中の plugin を即座に試す**には `.claude/skills/` 等にコピーする必要があります。コピーだと差分管理が大変なので、symlink で「`.claude/skills/run-foo` は実は `plugins/.../run-foo` を指している」とすることで、片方を編集すれば両方反映される仕組みにしています。

利用者として `/plugin install` で入れる場合、symlink の存在を意識する必要はありません。

## 4.5 scripts / references がホームディレクトリ配下にあるとき

`/plugin install` で入れた plugin は、実体が `~/.claude/plugins/cache/.../` に展開されます。Skill が参照する scripts や references も同じ場所にコピーされるため、**ユーザーが直接触る必要はありません**。

カスタマイズしたい場合のみ、リポジトリを clone してローカルの `plugins/` を編集し、`/plugin marketplace add /path/to/skills` でローカル marketplace として登録します。

## 4.6 plugin が読み込む順番

Claude Code セッション起動時:

1. `~/.claude/settings.json` を読む
2. 登録済 marketplace から `marketplace.json` を読む
3. `installed` 状態の plugin の `plugin.json` を読む
4. 各 plugin の `skills/` / `agents/` / `commands/` / `hooks/` を Claude Code に登録
5. ユーザーが `/コマンド` を打つ、または会話の文脈が Skill の `description` (発火条件) に合致すると起動

---

# Part 5: 参考リンク

## Claude Code 公式

- Plugin 作成: <https://code.claude.com/docs/en/plugins>
- Plugin reference: <https://code.claude.com/docs/en/plugins-reference>
- Marketplace 作成と配布: <https://code.claude.com/docs/en/plugin-marketplaces>
- Plugin の発見とインストール: <https://code.claude.com/docs/en/discover-plugins>

## このリポジトリの設計資料

- 設計思想と詳細仕様: `doc/ClaudeCodeスキルの設計書/` (01〜35章)
- 配布境界の取り決め: `CONVENTIONS.md`

---

# 運用メモ (上級者向け)

- `plugins/` は配布対象の **正本**。
- `doc/`, `eval-log/`, `.claude/` は設計・評価・ローカル運用のためのディレクトリで、配布対象には含まれません。
- plugin はインストール時にキャッシュへコピーされるため、plugin root の外側を `../` で参照しないでください。
- 他 plugin と共有したい共通ファイルは、marketplace 内の sibling plugin として置くか、同一 plugin 内に取り込んでください。
