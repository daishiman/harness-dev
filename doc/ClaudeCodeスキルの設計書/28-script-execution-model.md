# 28. Script 実行モデル

## 目的

`scripts/` 配下に置かれる決定論的処理を「**誰が・いつ・どの権限で・どの優先順位で**」実行するかを明文化する。
05 章で「Skill / Subagent / Hook / MCP / CLI」の責務分離を定義し、22 章で「クロスプラットフォーム実行基盤」を定義したが、両者の交点である「script そのものの実行モデル」は未定義であり、論理分析で最も致命的な穴と判定された。本章はその穴を埋める正本である。

## 出力 (このファイルが提供するもの)

- script 実行コンテキストの分類 (A-E の 5 種)
- script 種別 × 実行コンテキストの責務マトリクス
- script naming convention (22 章拡張)
- script 配置ルールと衝突解消
- 実行権限とサンドボックス境界
- script frontmatter (PEP 723 inline metadata 風) の規格
- 呼出プロトコル (LLM / Hook / CI の 3 経路)
- 実行順序と優先順位
- アンチパターン集

## 禁則

- LLM (Skill 本文) が script の中身を読んで判断を行ってはならない。script は black box である。
- script が rubric / 評価基準 / 設計書を書き換えてはならない。読み取り専用とする。
- script は追加ライブラリを要求してはならない。Python3 stdlib のみ (22 章準拠)。
- script はネットワークアクセスをしてはならない (CI 経路の `gh` 呼出、および 31 章の Sink Contract に従う adapter script を除く)。
- 同一 script を A (LLM) と C (Hook) の両方で同時に発火させてはならない。

## 読むべき関連章

- 04 章: invocation / permissions / settings.json の hook 定義
- 05 章: Skill / Hook / CLI の責務分離原則
- 22 章: クロスプラットフォーム実行基盤、no-deps 原則
- 23-26 章: meta-skill アーキテクチャと runbook
- 24 章: meta-skill template と `scripts/` 同梱パターン

---

## 1. 目的・位置付け

### 1.1 05 章との関係

05 章は「Skill は使い方を書くメタ層、決定論は scripts/ に寄せる」と宣言したが、寄せた先の script を「**いつ・誰が・どの経路で**」呼ぶかは未定義だった。本章は 05 章の決定木の右下 (決定論ブランチ) を引き継ぐ。

| 05 章で書いた決定 | 本章で引き継ぐ決定 |
|---|---|
| 決定論で組めるなら scripts/ へ | scripts/ をどの実行コンテキストで起動するか |
| Hook は強制レイヤ | Hook が呼ぶ script の責務範囲 |
| CLI は文脈依存判断をしない | script frontmatter で I/O 契約を明示 |

### 1.2 22 章との関係

22 章は「Python3 stdlib のみ / OS 標準 CLI のみ」を no-deps 原則として定めた。本章はその制約の上で動く実行モデルを定義する。22 章の制約は前提であり緩めない。

---

## 2. 実行コンテキスト分類

scripts/ の実行経路は次の 5 つに分類する。これ以外は禁止する。

| コード | コンテキスト | 起動主体 | 起動タイミング | 権限粒度 | 失敗時の扱い |
|---|---|---|---|---|---|
| A | SKILL.md 本文の Read/Write 処理中 | LLM が Bash tool 経由 | Skill 実行中 | ユーザーセッション権限 | LLM が読んで対処 |
| B | Subagent 経由 (context fork) | Subagent が Bash tool 経由 | Subagent 実行中 | parent session 継承 | Subagent が判断 |
| C | PreToolUse / PostToolUse Hook | Claude Code runtime | tool 呼出の前後 | settings.json で限定 | tool 呼出を allow/deny |
| D | SubagentStop / Stop Hook | Claude Code runtime | session 終了直前 | settings.json で限定 | session を deny 可能 |
| E | CI / 外部 automation | GitHub Actions 等 | push / PR 時 | CI runner 権限 | CI ジョブを fail |

### 2.1 コンテキスト判定の優先順位

同一 script が複数経路で呼べる場合、優先順位は **E > C > D > B > A** とする。理由は「LLM 判断を介在させない経路」ほど決定論的で監査可能だから。

---

## 3. 実行責務マトリクス

script 種別ごとに「**どのコンテキストで実行してよいか**」を表で固定する。`o` = 推奨、`-` = 許容、`x` = 禁止。

| script 種別 | 例 | A: SKILL本文 | B: Subagent | C: Hook | D: Stop Hook | E: CI |
|---|---|---|---|---|---|---|
| lint | `lint-frontmatter.py` | x | x | o | - | o |
| validate (schema) | `validate-skill-yaml.py` | x | x | o | - | o |
| format | `format-toc.py` | - | x | o | x | o |
| render (template) | `render-skill-template.py` | o | o | x | x | - |
| extract (parse) | `extract-anchors.py` | o | o | - | - | o |
| diff (差分検査) | `diff-rubric.py` | x | - | - | o | o |
| guard (禁止語) | `guard-banned-words.py` | x | x | o | o | o |
| index (索引生成) | `build-keyword-index.py` | - | o | x | o | o |
| adapter (出力先連携) | `sink_notion.py`, `sink_http.py` | - | x | x | x | o |

### 3.1 読み方

- **lint / validate / guard** は LLM 経由 (A/B) では実行禁止。LLM が結果を握り潰す可能性があるため必ず Hook か CI で強制する。
- **render / extract** は LLM が出力を加工するので A/B で OK。
- **format** は Hook か CI で自動修正するのが基本。A は対話的修正を許す例外。
- **adapter** は 31 章の Sink Contract v1.0 に従う例外分類である。外部API呼出し、Keychain参照、fallback は許可するが、stdout は最終JSONのみ、secret は context に出さない。

## 3.2 Bash / Python 2層規約

creator-kit と本プロジェクトの script は、言語を完全統一せず、役割で分離する。

| Layer | 言語 | 役割 | 例 |
|---|---|---|---|
| L1 Lifecycle / Provisioning | Bash (`.sh`) | ディレクトリ作成、symlink、mv、chmod、git操作、OS標準CLI呼び出し | `install.sh`, `uninstall.sh`, `migrate-from-project.sh` |
| L2 Logic / Tooling | Python (`.py`) | JSON解析、validation、lint、hook、adapter、secrets管理 | `sink_*.py`, `lint-*.py`, `keychain_helper.py`, `audit_secret_leak.py` |

Bash はファイルシステムとプロセス起動に限定する。構造化データ、HTTP応答、validation、secret処理を扱うなら Python に切り出す。

必須骨格:

- Bash: `#!/usr/bin/env bash` と `set -euo pipefail` を置く。Bash 3.2 互換を保ち、`jq` / `yq` / `mapfile` / 連想配列に依存しない。
- Python: `#!/usr/bin/env python3`、`main() -> int`、`if __name__ == "__main__": sys.exit(main())` を置く。終了コードを呼び出し元へ必ず返す。
- Bash 内 heredoc Python は5行以内にする。超える場合は独立した `.py` ファイルへ切り出す。

機械処理する設定ファイルは JSON を正本とし、Python 標準ライブラリ `json` で読む。例外は `SKILL.md` frontmatter と GitHub Actions workflow (`.yml`) など外部仕様が要求するファイルに限定する。PyYAML などの外部依存を導入してはならない。

---

## 4. Script Naming Convention

22 章 (CLI ホワイトリスト) を拡張し、scripts/ 配下のファイル名規約を定める。

### 4.1 規約

```
<動詞>-<対象>-<スコープ>.py
```

- 動詞: `lint` / `validate` / `format` / `render` / `extract` / `diff` / `guard` / `build` のいずれか (3.0 の種別と一致)
- 対象: 何を処理するか (frontmatter, rubric, anchors, toc, など)
- スコープ: 任意。対象が広い場合に限定する (例: `skill`, `subagent`)
- 拡張子: `.py` を既定。Windows 必須の場合のみ `.ps1` 併設可

### 4.2 例

| ファイル名 | 意味 |
|---|---|
| `lint-frontmatter.py` | frontmatter 全般のリント |
| `lint-skill-name.py` | Skill 名 (kebab-case) のリント |
| `validate-frontmatter.py` | frontmatter スキーマ検証 |
| `render-skill-template.py` | Skill テンプレート展開 |
| `extract-anchors.py` | アンカー抽出 |
| `guard-banned-words.py` | 禁止語チェック |

### 4.3 禁止される命名

- `check.py` / `run.py` / `main.py` (動詞・対象が不明)
- `utils.py` / `helper.py` (script ではなくライブラリ。`_lib/` に置く)
- 大文字、空白、日本語、`_` (アンダースコア)。`-` (ハイフン) で統一

### 4.4 例外: Sink Contract準拠の adapter / secret helper

- 31章 Sink Contract v1.0 に従う sink adapter (`scripts/adapters/sink_<name>.py`) は接頭辞 `sink_` の慣習により、アンダースコアを許容する
- secret helper (`scripts/secrets/<purpose>_helper.py`、`scripts/secrets/audit_<target>.py`) は機能分類接頭辞の慣習により、アンダースコアを許容する
- これら以外の新規 script はハイフン区切り規約に従うこと

### 4.6 例外: adapters/ 配下 (Hexagonal Architecture)

- 31章 Hexagonal Architecture の adapter dispatch entry point (`scripts/adapters/*.py` / `creator-kit/scripts/adapters/*.py`) は建築物的固有名 (`dispatch.py`, `resolve_route.py` 等) の存在意義が動詞よりルーティング機能で決まる
- adapter ファイルは `<verb>-<target>-<scope>` 規約ではなく **アーキテクチャ役割名** で命名し、§4.3 のアンダースコア禁止からも除外する
- adapter かどうかは親ディレクトリ名 `adapters` で判定 (機械強制 lint で `EXCEPTION` 扱い)
- 例外スコープ拡大には **P1 Structural change** として33章ワークフローを通すこと

### 4.7 機械強制 (lint-script-naming)

§4.1-§4.6 の規約は `scripts/lint-script-naming.py` により機械強制される。実行ステータスは3種:

| ステータス | 意味 |
|---|---|
| `OK` | 規約完全準拠 |
| `EXCEPTION` | §4.4 (sink_/audit_/_helper) または §4.6 (adapters/) の例外節に該当 |
| `PENDING_RENAME` | 既存違反のうちリネーム計画済み (例: `hook-*.py`)。33章 Change Governance下で段階移行 |
| `VIOLATION` | 規約違反。CI/pre-commit でブロック |

新規scriptを追加する場合は、`§4.1` の動詞8種 (lint/validate/format/render/extract/diff/guard/build) のいずれかを使う。動詞リスト変更は **P1 Structural change** として33章ワークフローに従う。

---

> **plugin 移行時の scripts 配置**: plugin 移行後は `plugins/<name>/scripts/` が script の配置先になる。plugin 内 scripts は plugin 外の設定・rubric・Skill を参照してはならない（公式制約 e）。plugin 命名規約は 06章 第17条を参照。適用開始は 34章 Phase 0 完了後。

---

## 5. Script 配置ルール

### 5.1 配置先

| 配置 | パス | 用途 |
|---|---|---|
| Skill 固有 | `<skill-dir>/scripts/` | その Skill だけが使う script |
| 共有 | `ref-*-scripts/scripts/` | 複数 Skill が共有する script |
| meta 共有 | `ref-meta-skill-scripts/scripts/` | meta-skill (23-26 章) 専用共有 |
| ライブラリ | `<skill-dir>/scripts/_lib/` | script 内部から import される共通モジュール |

### 5.2 衝突時の名前空間ルール

複数 Skill が同名 script を持つことは許可するが、**Hook / CI から呼ぶ場合はフルパスで指定**する。短縮名 (`PATH` 解決) は使用禁止。

```bash
# OK: フルパスで一意
python3 xl-skills/ref-skill-lint/scripts/lint-frontmatter.py SKILL.md

# NG: PATH 解決に依存
lint-frontmatter.py SKILL.md
```

### 5.3 _lib/ の扱い

`scripts/_lib/` 配下は **`__init__.py` を持つ Python パッケージ**として `sys.path` 操作で取り込む。先頭 `_` でリポジトリ全体の lint 対象から外れることを明示する。

---

## 6. 実行権限とサンドボックス

### 6.1 共通制約 (全コンテキスト)

- Python は **stdlib のみ** (22 章準拠)。`pip install` 禁止
- **ネットワークアクセス禁止**。`urllib.request` / `socket` の使用を grep で検出する CI を設けてよい
- **ファイル書込は出力ディレクトリ限定**。引数 `--output-dir` で受け取り、その配下以外への write を禁止
- 環境変数の読取は **allowlist 方式**。読んでよいのは `CI` / `GITHUB_*` / `HOME` / `PATH` / `OS` のみ

### 6.2 コンテキスト別の追加制約

| コンテキスト | 追加制約 |
|---|---|
| A: SKILL 本文 | Read/Write tool で取得済みのファイルしか参照しないこと |
| B: Subagent | parent context のファイル参照は禁止。明示的に引数で渡されたパスのみ |
| C: Hook | settings.json で `allowedPaths` を絞る。`/tmp` か workspace 配下のみ |
| D: Stop Hook | write 全面禁止。read-only で diff だけ返す |
| E: CI | secrets を script に渡さない。`gh` 経由の API は CI runner 権限で実行 |

### 6.3 PreToolUse Hook での allow/deny 判定例

settings.json:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "command": "python3 xl-skills/ref-skill-lint/scripts/guard-banned-words.py",
        "onFailure": "deny"
      }
    ]
  }
}
```

`onFailure: deny` を選んだ場合、script の exit code != 0 で Write tool 呼出自体がブロックされる。LLM はその理由を読んで再試行する。

---

## 7. Script Frontmatter（先頭メタ情報） (PEP 723 inline metadata 風)

各 script は **先頭コメントブロックに inline metadata** を持つ。PEP 723 のスタイルを準用するが、追加で **実行コンテキストヒント**を含める。

### 7.1 規格

```python
#!/usr/bin/env python3
# /// script
# name: lint-frontmatter
# version: 0.2.0
# purpose: SKILL.md frontmatter (YAML) の必須キーと型を検証する
# inputs:
#   - argv[1]: path to SKILL.md
# outputs:
#   - stdout: 違反一覧 (1 行 1 違反)
#   - exit: 0 = pass, 1 = fail, 2 = usage error
# requires-python: ">=3.9"
# dependencies: []          # stdlib only (22 章準拠)
# contexts: [C, E]          # 許可される実行コンテキスト (本章 2 節)
# network: false
# write-scope: none         # none | output-dir | workspace
# ///
"""SKILL.md の frontmatter を検査する。"""
```

### 7.2 必須キー

| キー | 必須 | 説明 |
|---|---|---|
| `name` | o | ファイル名と一致 |
| `purpose` | o | 1 行で何をするか |
| `inputs` / `outputs` | o | I/O 契約 |
| `contexts` | o | 本章 2 節の A-E から複数選択 |
| `network` | o | true/false |
| `write-scope` | o | 書込範囲 |
| `dependencies` | o | 必ず `[]` (stdlib only) |

### 7.3 frontmatter 自体の lint

`lint-script-frontmatter.py` (meta-lint) が CI で動き、上記必須キーの欠落を検出する。

---

## 8. 呼出プロトコル

### 8.1 LLM 経由 (コンテキスト A / B)

SKILL.md 本文または Subagent 指示書に次のように書く。

```markdown
## 検証手順

必要なら次を実行する:

\`\`\`bash
python3 xl-skills/ref-skill-lint/scripts/extract-anchors.py path/to/SKILL.md
\`\`\`

stdout を読み、抜けているアンカーを補う。
```

LLM は **script の中身を読まない**。出力だけを解釈する。

### 8.2 Hook 経由 (コンテキスト C / D)

`.claude/settings.json` または `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "pathPattern": "**/SKILL.md",
        "command": "python3 ${WORKSPACE}/xl-skills/ref-skill-lint/scripts/lint-frontmatter.py",
        "onFailure": "deny"
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write",
        "pathPattern": "**/SKILL.md",
        "command": "python3 ${WORKSPACE}/xl-skills/ref-skill-lint/scripts/format-toc.py --in-place"
      }
    ],
    "SubagentStop": [
      {
        "command": "python3 ${WORKSPACE}/xl-skills/ref-skill-lint/scripts/diff-rubric.py"
      }
    ]
  }
}
```

### 8.3 CI 経由 (コンテキスト E)

`.github/workflows/skill-lint.yml`:

```yaml
name: skill-lint
on:
  pull_request:
    paths:
      - "xl-skills/**/SKILL.md"
      - "xl-skills/**/scripts/**"

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: lint frontmatter
        run: |
          find xl-skills -name SKILL.md -print0 \
            | xargs -0 -n1 python3 xl-skills/ref-skill-lint/scripts/lint-frontmatter.py
      - name: validate script frontmatter
        run: |
          find xl-skills -path "*/scripts/*.py" -print0 \
            | xargs -0 -n1 python3 xl-skills/ref-skill-lint/scripts/lint-script-frontmatter.py
      - name: guard banned words
        run: python3 xl-skills/ref-skill-lint/scripts/guard-banned-words.py xl-skills/
```

---

## 9. 実行順序と優先順位

複数 script が同一イベントで発火する場合、順序を決定論的に固定する。

### 9.1 標準パイプライン順序

```
lint  →  validate  →  guard  →  format  →  render  →  extract  →  build
```

- 左ほど **早期 fail で安価な検査** (構文)
- 右ほど **生成・派生処理** (出力)
- guard までで fail したら format 以降は実行しない (fail-fast)

### 9.2 fail-fast / continue-on-error の選択基準

| 用途 | モード | 理由 |
|---|---|---|
| PreToolUse Hook | fail-fast | tool 呼出をブロックする目的 |
| PostToolUse Hook | continue-on-error | 既に書込済みなので全違反を出す |
| CI lint job | continue-on-error | PR 作者に全違反を一度に見せる |
| CI release job | fail-fast | リリース阻止が目的 |

### 9.3 同一種別内の順序

`lint-*` が複数ある場合は **ファイル名の辞書順** で実行する。意図的に順序を変えたい場合は `0_lint-*` のような数値プレフィクスを禁止し、代わりに **CI ジョブを分割**して明示的に依存させる。

---

## 10. アンチパターン

次のいずれもレビューで reject する。

| アンチパターン | 何が壊れるか | 正しい姿 |
|---|---|---|
| LLM が `cat scripts/lint-foo.py` で中身を読んで判断 | script が black box でなくなり、Skill 本文との二重実装が発生 | 出力 (stdout / exit) だけを読む |
| script が rubric / 設計書を rewrite | 評価基準の自動改ざん。監査不能 | script は read-only。書込は output-dir のみ |
| script が `pip install` を実行 | 22 章 no-deps 原則違反 | stdlib のみで書き直す |
| Bash 内で長い heredoc Python を書く | Bash と Python の責務境界が曖昧になる | 5行以内に抑え、超えたら `.py` に切り出す |
| `import yaml` / `import requests` を使う | pristine macOS で動かず、禁止依存を増やす | JSON + stdlib `json`、HTTP は stdlib または adapter contract に従う |
| Hook が LLM プロンプトを生成 | Hook が判断レイヤに侵食 | Hook は exit code のみ。判断は Skill |
| 同名 script を複数 Skill で `PATH` 解決 | どれが呼ばれるか非決定論 | フルパスで指定 (5.2) |
| `utils.py` を scripts/ 直下に置く | script かライブラリか不明 | `scripts/_lib/utils.py` |
| A (SKILL 本文) で `lint-*` を呼ぶ | LLM が結果を握り潰せる | C (Hook) か E (CI) に移す |
| script frontmatter なし | I/O 契約 / コンテキスト不明 | 7 節の必須キーを記載 |
| adapter 以外の script がネットワークアクセス | 監査不能、CI で再現不能 | 入力は引数経由、外部取得は CI step で行う |
| adapter 以外の script が secret を読む | APIキーがLLM contextやログへ漏れる | 31 章の Keychain helper と Sink Contract に閉じる |
| Stop Hook で write | session 終了直前の副作用は追跡困難 | Stop Hook は read-only |

---

## 付録: チェックリスト

新規 script を追加する PR レビューで次を確認する。

- [ ] 命名が `<動詞>-<対象>-<スコープ>.py` 規約に従う (4 節)
- [ ] 配置先が 5.1 の表のいずれかに一致する
- [ ] 先頭に PEP 723 風 frontmatter がある (7 節)
- [ ] `dependencies: []` で stdlib only である
- [ ] `creator-kit/manifest.json` の `requirements.forbidden_dependencies` に触れる import / CLI 依存がない
- [ ] `contexts` フィールドが 3 節のマトリクスと矛盾しない
- [ ] `network: false` である。31 章 adapter の場合のみ `network: true` と Sink Contract 準拠理由を記載する
- [ ] `write-scope` が `none` か `output-dir` のいずれか
- [ ] Hook / CI から呼ぶ場合はフルパス指定である (5.2)
- [ ] LLM 経路 (A/B) で呼ぶ場合、本文で「中身を読まない」旨が明示されている
- [ ] 同一イベントで他 script と競合する場合、9 節の順序に従う

以上を満たさない script はマージしない。
