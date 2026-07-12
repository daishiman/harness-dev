# harness-creator-kit

Claude Code のハーネス (Skill と評価・統治機構の総体) を「**構築する**」「**評価する**」「**承認する**」「**出力先にルーティングする**」ためのハーネス構成部品一式。**プロジェクトに依存しない portable kit** として設計されている。単体 Skill の生成は部品単位の能力として内包する。

## 5分で最初のSkillを作る（最短経路）

```bash
# 1. kit を導入（symlink 推奨）
bash installers/install.sh

# 2. Claude Code で次のスラッシュコマンドを実行
/run-skill-create
```

`/run-skill-create` が要望ヒアリング → ブリーフ確定 → SKILL.md 生成 → rubric 採点 → eval-log 書込までの全フローを単一エントリーポイントで起動する。**個別の `/run-skill-elicit` や `/run-build-skill` を順番に呼ぶ必要はない**。

bootstrap フェーズ（最初の 20 件）は governance ループが pending 扱いになり、minor/patch の自己承認が許容される。詳細は `config/governance-policy.json` の `bootstrap_phase` を参照。

## 何が入っているか

`manifest.json` が正本。サマリ:

| カテゴリ | Skill |
|---|---|
| オーケストレーター | `run-skill-create` (E2E: 要望→完成) |
| 生成系 | `run-skill-elicit`, `run-build-skill`, `run-skill-rename` |
| 評価系 | `assign-skill-design-evaluator`, `run-elegant-review` |
| ガバナンス | `run-skill-rubric-governance` |
| 参照系 (ref-*) | `ref-skill-design-rubric`, `ref-claude-code-skill-spec`, `ref-skill-naming-convention`, `ref-skill-glossary`, `ref-yaml-spec-fetcher`, `ref-output-routing` |
| Scripts | adapters (sink_*), secrets (keychain_helper), lint, hooks |
| Config | `adapter-registry.json`, `output-routing.json.example` |

## クイックスタート (別プロジェクトで使う)

### Pattern A: git submodule (推奨, version追従)

```bash
cd ~/projects/your-new-project
git submodule add <kit-repo-url> creator-kit
git submodule update --init
bash creator-kit/install.sh
```

### Pattern B: 単純コピー (オフライン環境)

```bash
cd ~/projects/your-new-project
cp -R /path/to/harness/creator-kit ./creator-kit
bash creator-kit/install.sh --mode copy
```

### Pattern C: symlink (同一マシン内で実体共有)

```bash
cd ~/projects/your-new-project
ln -s /path/to/harness/creator-kit ./creator-kit
bash creator-kit/install.sh   # mode=symlink がデフォルト
```

## 動作の仕組み

現在の `harness` リポジトリは、kit 正本 + symlink 構成へ移行済みである。`.claude/skills/` と root `scripts/` は Claude Code / workflow からの安定した参照先で、実体は `creator-kit/` に置く。

```
[your-new-project]/
├── creator-kit/                    ← この kit (submodule/cp/ln)
│   ├── manifest.json
│   ├── CONVENTIONS.md
│   ├── install.sh
│   └── skills/, scripts/, config/
│
├── .claude/skills/                 ← Claude Code が探索する場所
│   ├── run-skill-create ──→ ../../creator-kit/skills/run-skill-create  (symlink)
│   ├── run-build-skill  ──→ ../../creator-kit/skills/run-build-skill   (symlink)
│   ├── ...
│   └── run-your-domain/            ← プロジェクト固有 (kit外、実体)
│
├── scripts/adapters/  ──→ kit/scripts/adapters/  (symlink)
├── scripts/secrets/   ──→ kit/scripts/secrets/   (symlink)
└── .claude/config/    ──→ kit/config/            (symlink)
```

Claude Code は `.claude/skills/` 配下を探索し、symlinkも追跡する。つまり**Claude Codeの標準仕様だけ**で kit-symlink構成が動く (独自loader不要)。

## install.sh のオプション

| Flag | 効果 |
|---|---|
| (default) | symlink で配置。kit更新が即座に反映される |
| `--mode copy` | 実体コピー。kitと独立して進化させたい時 |
| `--force` | 既存ファイル衝突時に上書き |

## アンインストール

```bash
bash creator-kit/uninstall.sh
```

kit由来のsymlinkのみ削除し、プロジェクト固有ファイルは保持する。

## 既存プロジェクトの移行

このリポジトリのように、既に `.claude/skills/` 配下に実体ファイルがある状態から kit化したい場合:

```bash
# まずdry-runで確認
bash creator-kit/migrate-from-project.sh --dry-run

# 問題なければ実行
bash creator-kit/migrate-from-project.sh
```

`.claude/skills/<meta-skill>/` の実体を `creator-kit/skills/` に移動し、元の位置にsymlinkを張り直す。プロジェクト固有skillはそのまま残る。

## 新ドメインを追加する3ステップ（rubric 横展開）

設計書29 (rubric multi-project composition) の 3層階層モデル (L0 共通 / L1 ドメイン / L2 プロジェクト) に従い、新しい業務ドメイン (例: `meeting-minutes`, `design-doc`) を creator-kit に取り込む手順。**L0 rubric (`ref-skill-design-rubric`) も既存スキルも変更しない**。

### Step 1: L1 rubric を雛形から派生

```bash
DOMAIN="meeting-minutes"  # kebab-case
cp -R creator-kit/skills/ref-domain-rubric-template \
      creator-kit/skills/ref-domain-${DOMAIN}-rubric
# rubric.json 内の {{domain_name}} を $DOMAIN に置換し、TODO(human) のルール本体を埋める
```

### Step 2: rubric-registry.json に登録

`creator-kit/config/rubric-registry.json` の `rubrics[]` に新エントリを追加:

```json
{
  "domain": "meeting-minutes",
  "layer": "L1",
  "rubric": "creator-kit/skills/ref-domain-meeting-minutes-rubric/rubric.json",
  "description": "議事録ドメイン固有 rubric",
  "upstream": ["creator-kit/skills/ref-skill-design-rubric/rubric.json"]
}
```

### Step 3: 整合性検証して /run-skill-create で量産

```bash
python3 creator-kit/scripts/lint-rubric-refs-exist.py  # exit 0 必須
# Claude Code で:
#   /run-skill-create
# brief の domain フィールドに "meeting-minutes" を入れると
# run-build-skill が rubric-registry から L1 を解決し、
# 生成された SKILL.md の rubric_refs に L0 + L1 が自動注入される
```

**evaluator (`assign-skill-design-evaluator`) を増やす必要はない**。同じ evaluator が rubric_refs を deep-merge して採点する (設計書29 §7.1)。

## kitの境界線 (再利用 vs プロジェクト固有)

### kit化する (再利用)
- メタスキル (生成/評価/ガバナンス)
- 汎用フレームワーク (routing/adapter/secret管理)
- Lint/Hook scripts
- adapter-registry / routing雛形

### kit化しない (プロジェクト固有)
- 業務workflow skill (`run-task-spec`, `run-meeting-minutes` 等)
- プロジェクト設計書 (`doc/`)
- 業務分析 (`analysis/`)
- 評価履歴 (`eval-log/`)
- 具体的な output-routing.json の中身 (DB ID等)

判断基準: **複数プロジェクトで同じものを使うか?** Yes → kit、No → プロジェクト直下。

## 依存 (追加ライブラリ禁止)

- macOS / Linux / Windows を対象にする。OS差分は `ref-cross-platform-runtime` と `creator-kit/scripts/cross_platform_secret.py` に集約する。
- Python 3.9+ stdlib のみ。PyYAMLや requests 等は使わない。
- Bash 利用箇所は `/bin/bash` 3.2+ 互換で書く。Windows では PowerShell または Python フォールバックを使う。
- `security` CLI は macOS の Keychain 操作用。Linux / Windows では標準ライブラリ実装または環境変数フォールバックを使う。
- `git` (オプション、submodule取得用)

詳細ルール: `CONVENTIONS.md` 参照。「Bash か Python か」で迷ったらここを見る。

## 設計書

本kitの設計根拠は親リポジトリの `doc/ClaudeCodeスキルの設計書/` を参照:

- 23-25章: meta-skill architecture (kit の中身の設計)
- **26章: メタSkillドッグフーディング** — 設計書自身を `assign-skill-design-evaluator` で採点する自己進化ループ。起動装置は `creator-kit/scripts/doc-to-skill-adapter.py`
- **27章: rubric governance Runbook** — 違反検出 → 招集 → 影響評価 → 猶予 → 発効の5ステップ。正本スクリプトは `creator-kit/scripts/lint-rubric-violation.py` / `compute-rubric-hash.py` / `rollback-to-stable.py` / `notify-if-governance-trigger.py`
- **28章: script 実行モデル** — A-Eの5実行コンテキスト、PEP 723 風 frontmatter、命名規約。機械検証は `creator-kit/scripts/lint-script-frontmatter.py`
- 29章: rubric multi-project composition (rubric_refs)
- 31章: output routing & adapter architecture (Hexagonal Arch)

## ブートストラップ（最後の砦）

`run-build-skill` と `assign-skill-design-evaluator` が相互依存しているため、どちらかが壊れた状態から復旧したい場合は `creator-kit/_bootstrap/MANUAL.md` を参照。エディタとPython3 stdlibだけで最小Skillを手書きで再構築する手順を載せている。

## バージョニング

`manifest.json` の `kit_version` で semver管理。後方互換破壊時は major up。

## ライセンス

(プロジェクトに合わせて設定)
