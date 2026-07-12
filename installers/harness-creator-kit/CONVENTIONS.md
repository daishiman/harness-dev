# Scripting Conventions (Bash vs Python)

本kitおよびプロジェクトにおけるシェルスクリプト言語選択の正典。
「どっちで書くか?」で迷ったらこの文書だけを参照する。

---

## 1. 2層モデル

| Layer | 言語 | 役割 | 例 |
|---|---|---|---|
| L1: Lifecycle / Provisioning | **Bash (.sh)** | ディレクトリ作成、symlink、mv、chmod、git操作、OS標準CLI呼び出し | `install.sh`, `uninstall.sh`, `migrate-from-project.sh` |
| L2: Logic / Tooling | **Python (.py)** | 構造化データ解析、validation、lint、hook、API呼出、secrets管理 | `sink_*.py`, `lint-*.py`, `hook-*.py`, `keychain_helper.py`, `audit_secret_leak.py` |

**原則**: Bash はファイルシステムを動かすだけ。ロジックが要るなら `python3 script.py` を呼ぶ。

---

## 2. 判定フロー (3問)

1. **副作用が「ファイルシステム/プロセス起動」だけか?** → Yes: **Bash**
2. **構造化データ (YAML/JSON/HTTP応答) を解析するか?** → Yes: **Python**
3. **1回限りのセットアップか、繰り返し呼ばれるツールか?** → セットアップ: **Bash** / ツール: **Python**

3問のうち2問以上が Python 寄りなら Python を選ぶ。

---

## 3. 必須骨格

### Bash (.sh)
```bash
#!/usr/bin/env bash
# <one-line purpose>
set -euo pipefail
KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
# ... lifecycle operations only ...
```

- `set -euo pipefail` 必須
- 絶対パスを使う (相対パスは `cd` 依存で壊れる)
- ロジックを書きたくなったら Python に出す

### Python (.py)
```python
#!/usr/bin/env python3
# /// script
# name: <verb-target-scope>
# version: 0.1.0
# purpose: <one-line purpose>
# inputs:
#   - argv / --flag: 説明
# outputs:
#   - stdout / file / exit code
# requires-python: ">=3.9"
# dependencies: []
# contexts: [<A|B|C|D|E から複数選択>]
# network: false
# write-scope: <none|output-dir|workspace>
# ///
"""<one-line purpose>"""
import sys

def main() -> int:
    ...
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- shebang + PEP 723 frontmatter + main() + `sys.exit(code)` **すべて必須**（28章§7 準拠）
- `contexts:` フィールドは **全 Python script で必須**。値は28章2節の `A`(SKILL本文)/`B`(Subagent)/`C`(PreToolUse Hook)/`D`(SubagentStop/Stop Hook)/`E`(CI) から複数選択
- `dependencies: []` で stdlib 限定を機械強制（`creator-kit/scripts/lint-script-frontmatter.py` が検証）
- `network: false` を既定。31章 Sink Contract 準拠 adapter のみ `true` 可
- `write-scope:` は `none` / `output-dir` / `workspace` のいずれか
- exit code は `Sink Contract v1.0` に準拠 (0 success / 1 validation / 2 secret / 3 API / 4 fallback)

---

## 4. 過去違反 (すべて解消済み・履歴)

> ⚠️ このセクションは「過去の解消履歴」であり、現在の状態ではない。新規違反を見つけた場合は §6 例外ポリシーに従って記録し、別ファイル `CONVENTIONS-EXCEPTIONS.md` (将来作成) で管理する。

| ファイル | 過去違反 | 解消日 | 解消内容 |
|---|---|---|---|
| `install.sh` / `uninstall.sh` | heredoc Python で YAML 解析 (PyYAML依存) | 2026-05-18 | manifest.yaml → manifest.json 化、heredoc は3行以内の `python3 -c json` に短縮 |
| `resolve_route.py` | `import yaml` で adapter-registry/output-routing 読込 | 2026-05-18 | JSON 化、stdlib `json` のみで完結 |
| `resolve_route.py` | `if __name__ == "__main__": main()` が `sys.exit()` を呼ばず exit code 伝達不能 | 2026-05-18 | `sys.exit(main())` 形式に修正 (§3 必須骨格遵守) |

**現状**: §3 必須骨格・§5 禁則・§6 例外ポリシーの未解決違反なし。ただし[§8.1](#81-命名形式の使い分けkebab-case--snake_case)のscript命名規約については PENDING_RENAME / VIOLATION が残存しており、33章 P1_structural ワークフローで段階的に解消中（最新状況は `python3 scripts/lint-script-naming.py --report` で確認）。

---

## 5. 禁則

- **Bash に jq/yq などの非標準依存を入れない** (kit が macOS pristine state で動く前提を破る)
- **Python 内で `subprocess.run([..], shell=True)` を使わない** (引数注入リスク。配列形式必須)
- **Bash heredoc Python ブロックは 5行を超えない** (超えたら Python ファイルに切り出す)
- **Python で `os.system` 禁止** (例外なし。`subprocess` を使う)

---

## 6. 例外ポリシー

**大前提**: macOS デフォルトで入っているもの**だけ**で動かす。新規ライブラリ追加 (pip / brew / npm) は原則禁止。社内配布時のハードルを上げないため。

**統一方針 (Option D)**: 言語は完全統一しない。2層モデル (L1=Bash provisioning / L2=Python stdlib logic) をルールとして固定する。これは「Bash 3.2 で HTTP/JSON を扱う方が壊れやすい」「Python stdlib は `/usr/bin/python3` で必ず入っている」という実利判断に基づく。

**例外を認める条件** (以下すべて満たすこと):

1. **macOSデフォルトのみ**: 例外コードも `/usr/bin/python3` (stdlib) と `/bin/bash` + 標準CLI (`curl`/`security`/`find` 等) だけで動くこと。`import yaml` `import requests` 等は不可。
2. **5行ルール**: Bash内の heredoc Python は5行以内。超えるなら独立 `.py` に切り出す。
3. **記録**: 例外箇所のコード冒頭に `# EXCEPTION: <理由> (<日付>)` コメント必須。レビュー (`run-elegant-review`) で grep して棚卸し可能にする。
4. **クロスプラットフォーム**: Linux/Windows 対応を将来導入する場合、Bash側はOS分岐 (`uname` で判定) で許容。`security` (Keychain) の代替は Python 側で抽象化 (`keychain_helper.py` にOS分岐を集約) し、kit 利用者には CLI 統一を維持する。
5. **承認**: solo_operator_mode のため自己承認。ただし例外を入れる commit には `convention-exception:` プレフィクスを付け、git log で追跡可能にする。

---

## 7. 関連

- `doc/ClaudeCodeスキルの設計書/28-script-execution-model.md` — script実行の責務分離
- `manifest.json` — kit が公開するscript一覧 (Layer/言語別に整理)
- `manifest.json` の `requirements.forbidden_dependencies` — 追加禁止ライブラリの正典リスト
- `scripts/lint-forbidden-deps.py` — forbidden_dependencies の自動検出 (CI/pre-commit用)

---

## 8. scripts 配置の正本ルール (パス二重管理回避)

スクリプト本体の物理配置は以下の階層で正本を一つに固定する。SKILL.md からの参照は **常にプロジェクトルート基準の相対パス**で書く。

| 配置パス | 正本性 | 用途 |
|---|---|---|
| `scripts/*.py` (harness ルート) | **正本 (canonical)** | hook / lint / validate / governance — 全 Skill が共有する横断ツール |
| `creator-kit/scripts/*.py` | **正本 (canonical)** | creator-kit 専用の lifecycle (install/migrate/build-manifest-registration-plan 等) |
| `creator-kit/skills/<skill>/scripts/*.py` | **正本 (canonical)** | その Skill 固有のロジック (例: `run-build-skill/scripts/render-frontmatter.py`) |
| `.claude/skills/<skill>/scripts/*.py` | **派生 (symlink予定)** | Phase 0 完了後、`creator-kit/skills/` への symlink になる。直接編集禁止 |

**SKILL.md 内 bash 記述ルール**:
- harness ルートから起動される前提で **`python3 scripts/foo.py`** または **`python3 creator-kit/scripts/foo.py`** と書く
- skill-local script は **`python3 creator-kit/skills/<skill>/scripts/foo.py`** と書く (`.claude/skills/...` 形式は禁止)
- これにより Phase 0 移行時にもパス参照が破綻しない

**過去の二重管理**: `run-skill-create/SKILL.md` で `scripts/build-manifest-registration-plan.py` と書きつつ実体は `creator-kit/scripts/` にあった等の不整合は、§8 ルールで一意に解消する。

### 8.1 命名形式の使い分け（kebab-case / snake_case）

scripts/ 配下のファイル名は配置階層によって命名形式を切り替える。28章§4 規約と例外節（§4.4 / §4.6）の正本対応関係：

| 配置 | 命名形式 | 理由 | 例 |
|---|---|---|---|
| `creator-kit/scripts/*.py`（直下） | **kebab-case** `<動詞>-<対象>-<スコープ>.py` | 28章§4.1 既定規約。動詞 8 種（lint/validate/format/render/extract/diff/guard/build）のいずれかで始める | `lint-script-frontmatter.py`, `compute-rubric-hash.py`, `doc-to-skill-adapter.py` |
| `creator-kit/scripts/adapters/*.py` | **snake_case** 許容 | 28章§4.6 Hexagonal Architecture の adapter dispatch entry point は機能名で命名 | `sink_local.py`, `dispatch.py`, `resolve_route.py` |
| `creator-kit/scripts/secrets/*.py` | **snake_case** 許容 | 28章§4.4 secret helper の機能分類接頭辞慣習 | `keychain_helper.py`, `audit_secret_leak.py` |
| `creator-kit/scripts/migrate/*.py` | **kebab-case** | 通常規約。`migrate/` は配置スコープのみで命名例外なし。単語名のみ（`audit.py`）は PENDING_RENAME 対象として動詞接頭辞付き名（例: `audit-skill-set.py`）へ移行予定 | `to-brief.py`, `backfill-source-tier.py`（PENDING: `audit.py`） |
| `creator-kit/scripts/cross_platform_*.py`（暫定） | **PENDING_RENAME** | アンダースコア使用は28章例外節非該当。`scripts/secrets/` 配下への移動 or `cross-platform-secret.py` への改名を計画 | `cross_platform_secret.py` |

`hook-*.py` 命名は28章規約では `guard-*.py` 等へ移行予定（PENDING_RENAME）。事前互換のため当面は `hook-*.py` を許容し、`lint-script-frontmatter.py` の `EXCEPTION` 扱いとする。33章 P1 Structural change を経て移行する。

---

## 9. 変数台帳（横展開時のパス・環境変数の正本）

別プロジェクトに creator-kit を導入する際に上書き可能なパス変数・環境変数の単一参照源。
SKILL.md / scripts / 設計書から参照する場合は **必ず本表の変数名を使い**、独自命名を禁止する。

| 変数名 | デフォルト | 設定主体 | 用途 |
|---|---|---|---|
| `PROJECT_ROOT` | `$(pwd)` 起動ディレクトリ | shell / hook | プロジェクトルート。`eval-log/` `creator-kit/` 等の起点 |
| `OUT_BASE` | `creator-kit/skills` (Phase 0) / `plugins/<name>/skills` (Phase 0 完了後) | `resolve-skill-dirs.sh` | 生成 Skill の出力ベース。`$OUT_BASE/<skill-name>/SKILL.md` |
| `SKILL_DIR` | self-relative 解決 | `resolve-skill-dirs.sh` | 当該 Skill 自身のディレクトリ（SKILL.md と同階層） |
| `CLAUDE_SKILL_DIR` | (未設定) | 利用者 | 強制的に SKILL_DIR を上書きしたい場合の手動入口 |
| `CLAUDE_SKILL_OUT_BASE` | (未設定) | 利用者 | OUT_BASE を上書き（別プロジェクト導入時に必須） |
| `EVAL_LOG_DIR` | `$PROJECT_ROOT/eval-log` | 利用者 / hook | eval-log の置き場を上書き |
| `SKILL_DESIGN_RUBRIC` | `creator-kit/skills/ref-skill-design-rubric/rubric.json` | 利用者 | L0 共通 rubric の差し替え (設計書29) |
| `DOMAIN_RUBRIC_REFS` | (未設定) | brief から確定 / `resolve-skill-dirs.sh` | L1 ドメイン rubric の append-only 注入リスト。空白区切り。値は `creator-kit/config/rubric-registry.json` の `rubrics[].rubric` から `brief.domain` で解決される。**evaluator 自身が書き換えてはならない (設計書29 §10 アンチパターン)** |
| `RUBRIC_REGISTRY_PATH` | `creator-kit/config/rubric-registry.json` | 利用者 | L1 rubric レジストリの正本パス。別プロジェクトで rubric を完全独立管理したい場合のみ上書き |
| `SKILL_NAME` | brief から確定 | `run-build-skill` Step 1 | 生成中のSkill名（kebab-case） |
| `KIND` | brief から確定 | `run-build-skill` Step 1 | run/ref/assign/wrap/delegate |
| `DOMAIN` | brief.domain から確定 | `run-build-skill` Step 1 | L1 rubric 解決キー。未指定時は L0+L2 構成 (L1 スキップ) |

### 9.1 必須環境変数（別プロジェクト導入時）

別プロジェクトに kit を持ち込む際、最低限以下を `.envrc` / hook / shell init に設定する:

```bash
export PROJECT_ROOT="$(pwd)"                       # 必須
export CLAUDE_SKILL_OUT_BASE="$PROJECT_ROOT/.claude/skills"   # 任意（Phase 0完了後）
export EVAL_LOG_DIR="$PROJECT_ROOT/eval-log"       # 任意（デフォルトで PROJECT_ROOT 配下）
```

### 9.2 変数化ポリシー（直書き禁止ルール）

- SKILL.md / combinator patch / templates 配下では **絶対パス・プロジェクト固有名を直書き禁止**
- ハードコードが必要なケース（design-docs-index.md 等の正本パス）は本表に変数を追加し、置換可能にする
- 違反検出: `creator-kit/scripts/lint-path-canonical.py` で grep 検出（Phase 1 で正式運用）

### 9.3 rubric_refs 注入経路（設計書29 §2 / §10 準拠）

3層 (L0/L1/L2) の決定論的合成は次の経路でのみ行う。**evaluator 自身が rubric_refs を書き換える経路は禁止** (設計書29 §10 アンチパターン)。

| 経路 | 役割 | 主体 |
|---|---|---|
| frontmatter `rubric_refs:` リスト | 静的宣言 (L0 + L2) | SKILL.md 作成者 |
| CLI `--rubric-refs <path>...` | append-only 動的注入 (L1) | runner / orchestrator (run-build-skill / run-skill-create) |
| `DOMAIN_RUBRIC_REFS` 環境変数 | rubric-registry.json から domain で解決された L1 一覧 | `resolve-skill-dirs.sh` |

**優先順位**: frontmatter `rubric_refs` の後ろに `--rubric-refs` の値が append される。`merge_strategy: deep-merge` + `conflict_policy: most-specific-wins` により リスト末尾 (= 最 specific = L2) が優先される。**override は禁止 (append-only)**、これにより L0/L1 の存在が消えないことを保証する。

---

## 10. source-tier 決定表（doc/21 source-traceability の単一参照源）

新規 Skill / 更新 Skill の frontmatter で `source-tier:` を選ぶときの正典。
auto-backfill に頼らず**作成時点で正しい値を入れる**ことで、設計書21の
「再監査ルール」を後付けで補正する強化ループ（backfill 依存）を断ち切る。

| source-tier | 選択条件 | 典型ソース | 補足 |
|---|---|---|---|
| `article-text` | **元記事 Markdown** の本文を実ファイルで確認済み | `doc/【コード共有有】Agent Skill大全 …/【…】.md` | 設計書21 が article-text を「元記事 Markdown を確認済み」と定義する |
| `image-derived` | 画像 OCR / 手描き図から翻文した内容を含む | `doc/【…】/Pasted image *.png` 由来の本文 | 設計書21 image-extraction-map の対応行を `source:` に書く |
| `code-unavailable` | 記事説明由来でコード現物が未取得 | 記事中の `skills.zip` / Notion 同梱コードがリポジトリに存在しない時 | 取得後 `code-verified` に昇格する |
| `code-verified` | 実コードを取得し動作を検証済み | リポジトリに同梱した参照実装 | 設計書21 再監査ルール 7 で昇格 |
| `internal` | **本リポジトリ内製** の設計書・規約・lint・hook 由来 | `doc/ClaudeCodeスキルの設計書/20-…`, `21-…`, `22-…` 等 | doc/ 配下の内製ドキュメントはすべてこちらに分類する |
| `external-spec` | 外部公式仕様書 (claude.com docs / GitHub docs 等) のローカル写しまたは参照 | `https://code.claude.com/docs/en/skills` 等 | URL を `source:` に書く |

### 9.1 判定フロー（3問）

1. **ソースは外部公式仕様 URL か？** → Yes: `external-spec`
2. **ソースは内製の `doc/` 配下か？** → Yes: `internal`
3. **元記事 Markdown かその派生か？**
   - 元記事 .md 本文確認済み → `article-text`
   - 画像由来の翻文 → `image-derived`
   - 記事中で言及されるコード現物が手元にない → `code-unavailable`（取得後 `code-verified`）

### 9.2 量産フロー上の単一参照源

- スクリプト側マッピング: `creator-kit/scripts/migrate/to-brief.py` の `ORIGIN_TO_TIER`
- 列挙値の機械検証: `creator-kit/scripts/validate-frontmatter.py` の `SOURCE_TIER_VALUES`
- 本決定表 (§9) はこの 2 箇所と語彙的に同期している。**変更時は 3 箇所を必ず一緒に更新する**。

### 9.3 後付け backfill の非推奨

`creator-kit/scripts/migrate/backfill-source-tier.py` は移行期の救済策であり、
新規 Skill 作成では使わない。`audit.py` → `to-brief.py` のフローで
`origin` フィールドから自動派生されるため、ユーザーが手動で `source-tier:`
を埋める場面は限定的になる（量産時 `--owner` と同様に `--source-tier`
override が必要な場合のみ）。
