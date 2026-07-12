# Skill Ledger Conventions — skill 出力時の必須要件

本書は `.claude/skills/<name>/` 配下の skill を **新規作成・改修** する際に守るべき
共有 ledger 規約をまとめる。task-conflict-prevention-skill-state-redesign
（Phase 12 完了 / 2026-04-28）で確定した 4 施策（A-1 / A-2 / A-3 / B-1）を
skill 出力プロセスへ恒久的に反映するためのチェックリストである。

source of truth:

- `docs/30-workflows/completed-tasks/task-conflict-prevention-skill-state-redesign/outputs/phase-12/implementation-guide.md`
- `docs/30-workflows/completed-tasks/task-conflict-prevention-skill-state-redesign/outputs/phase-12/system-spec-update-summary.md`
- `docs/30-workflows/completed-tasks/task-conflict-prevention-skill-state-redesign/outputs/phase-12/skill-feedback-report.md`
- `docs/00-getting-started-manual/specs/skill-ledger.md`（Phase 12 後に追記される正本）

## 1. 4 施策の俯瞰

| ID | 施策 | 対象ファイル | 衝突解消メカニズム |
| --- | --- | --- | --- |
| A-1 | 自動生成 ledger の `.gitignore` 化 | `indexes/keywords.json` / `index-meta.json` 等 | git tree から外れるため衝突対象外 |
| A-2 | Changesets パターン fragment 化 | `LOGS.md` / `SKILL-changelog.md` / `lessons-learned-*.md` | 各 worktree が一意 path に新規作成 |
| A-3 | SKILL.md の Progressive Disclosure | 肥大化した `SKILL.md` 本体 | 200 行未満 entrypoint + `references/` 分割 |
| B-1 | `.gitattributes merge=union` | 行独立な append-only ledger | 両 worktree の追記行を保存 |

## 2. skill 新規作成時の必須要件

新しい skill を `.claude/skills/<name>/` に出力するとき、以下の 5 要件を必ず満たす。

### 2.1 SKILL.md は 200 行未満の entrypoint

- 入口情報（front matter / 設計原則 / クイックスタート / リソース一覧）のみを置く
- 詳細は `references/<topic>.md` に分割し、本体からはリンクのみで誘導する
- 200 行を超えそうな場合は **生成段階で分割** する（後追い分割は衝突源になる）

### 2.2 LOGS は fragment 構造で初期化

- `LOGS.md` 単体ファイルではなく、`LOGS/` ディレクトリ + `LOGS/_legacy.md`（空でも可）構造で出力する
- 利用者が追記するときは `LOGS/<YYYYMMDD-HHMMSS>-<escaped-branch>-<nonce>.md` を新規作成
- skill scaffold 時に `LOGS/README.md` で命名規約を案内する

### 2.3 自動生成ファイルは `.gitignore` に記載

skill が以下を生成する場合は、skill 配下に `.gitignore` を置いて除外する。

```
indexes/keywords.json
indexes/index-meta.json
indexes/topic-map.json
*.cache.json
```

regenerate スクリプト（`scripts/generate-index.js` 等）の存在が前提。

### 2.4 `.gitattributes` で `merge=union` を明示（fallback 用）

fragment 化できない / 移行猶予中の legacy ledger に対する保険として、skill ルートの
`.gitattributes` に以下を記載する。

```
LOGS.md merge=union
SKILL-changelog.md merge=union
```

ただし **JSON / YAML / 構造化テキスト** には適用しない（行独立性が崩れるため）。

### 2.5 Progressive Disclosure の徹底

`SKILL.md` から `references/` への導線は単方向に保ち、循環参照を避ける。
各 reference は 500 行以内（CONST_002 準拠）。超過時は family file に分割する。

## 3. skill 改修時のチェックリスト

既存 skill を更新する PR では以下を確認する。

- [ ] `SKILL.md` の行数が 200 行を超えていないか（超えていたら A-3 分割を検討）
- [ ] 改修対象に `LOGS.md` / `SKILL-changelog.md` の **末尾追記** が含まれていないか
  - 含まれる場合は `LOGS/` fragment へ書き直す（または `merge=union` を確認）
- [ ] 自動生成物が tracked になっていないか（`git ls-files indexes/` で確認）
- [ ] 参照リンクが循環していないか / 死リンクがないか
- [ ] 各 reference が 500 行以内か（CONST_002）
- [ ] `legacy-ordinal-family-register` の命名規約に合致しているか（CONST_005）

### 3.1 衝突しやすい hot spot 一覧

| ファイル | 典型的な衝突原因 | 対処 |
| --- | --- | --- |
| `SKILL.md` | 並列 wave で同じセクションを更新 | A-3 で `references/` に逃がす |
| `LOGS.md` | 末尾 append の 3-way merge | A-2 で fragment 化、B-1 で merge=union |
| `SKILL-changelog.md` | バージョン番号の衝突 | A-2 で fragment 化 |
| `indexes/*.json` | 自動生成物の手動編集 | A-1 で gitignore + hook 再生成 |

## 4. CONST_002（500 行ガード）の遵守方法

すべての markdown ファイルは 500 行以内に収める。確認手順:

```bash
# skill 配下の 500 行超過を検出
find .claude/skills/<name> -name "*.md" -exec wc -l {} \; | awk '$1 > 500'
```

超過時の対処:

1. テーマ別の家族ファイル（family file）に分割（例: `patterns-success.md` →
   `patterns-success-ipc.md` / `patterns-success-testing.md`）
2. 親ファイルから子ファイルへ目次リンクを張る
3. CONST_005 の命名規約（後述）に従う

## 5. CONST_005（legacy-ordinal-family-register）の遵守方法

skill 配下のファイル名は、historical/ordinal な命名（`*-v2.md` / `*-old.md` 等）を避け、
**topic-based family register** を採用する。

| 良い例 | 悪い例 |
| --- | --- |
| `patterns-success-ipc.md` | `patterns-v2.md` |
| `patterns-failure-phase12.md` | `patterns-old.md` |
| `phase-template-phase12.md` | `phase-template-2026.md` |
| `logs-archive-2026-march.md` | `logs-old-3.md` |

- 連番ではなく **テーマ + 範囲** で命名する
- アーカイブは `logs-archive-<YYYY>-<month>.md` のように **時間範囲** を入れる
- リファクタで分割した場合は family register（親ファイルの目次）を更新する

## 6. fragment 命名規約（A-2 詳細）

skill 利用者が `LOGS/` に追記するときの規約。

```
<skill>/LOGS/<YYYYMMDD-HHMMSS>-<escaped-branch>-<nonce>.md
```

| 要素 | 規約 |
| --- | --- |
| timestamp | `YYYYMMDD-HHMMSS`（UTC 推奨、ローカル時刻は許容） |
| escaped-branch | `/` を `-` に、英数字以外をハイフン化（例: `feat/abc` → `feat-abc`） |
| nonce | 8〜12 文字の小文字 hex / base36（同一秒・同一 branch 衝突対策） |

front matter（任意だが推奨）:

```markdown
---
skill: <skill-name>
date: 2026-04-28
branch: feat/example
agent: skill-creator (update)
---

## <タイトル>

- 内容...
```

## 7. render API 連携

fragment を集約して読むときは render CLI を使う。

```bash
pnpm skill:logs:render --skill <name> [--since <ISO>] [--out <path>] [--include-legacy]
```

- 既定ソート: timestamp 降順
- `--out` は tracked な canonical ledger path を拒否する
- `--include-legacy` 有効時は `_legacy.md` も対象に含める（移行 30 日間の既定）

## 8. skill-creator スクリプトへの組み込みポイント

| script | 反映すべき点 |
| --- | --- |
| `scripts/detect_mode.js` | create モード時に `LOGS/` ディレクトリ + `.gitignore` + `.gitattributes` を scaffold |
| `scripts/quick_validate.js` | SKILL.md 行数 (< 200) / fragment 構造 / gitignore 存在を validate |
| `scripts/validate_all.js` | 全 references が 500 行以内 / CONST_005 命名規約に合致するかを validate |
| `agents/generate-skill.md` | scaffold テンプレに本書のチェックリストを反映 |

## 9. 後方互換方針

- 既存 `LOGS.md` は `_legacy.md` として退避し、削除しない
- A-2 移行後 30 日間は `_legacy.md` を render に含める
- skill 利用者は外部 API の変更を受けない（render CLI のみ追加）
- 既存 skill のドッグフーディング順序は `task-specification-creator` →
  `aiworkflow-requirements` → `skill-creator` の順に適用する（衝突頻度が高い順）

## 10. 関連リンク

- 仕様書: `docs/30-workflows/completed-tasks/task-conflict-prevention-skill-state-redesign/`
- 正本: `docs/00-getting-started-manual/specs/skill-ledger.md`（Phase 12 後追記）
- skill 出力規約: `references/skill-structure.md` / `references/output-patterns.md`
- 並列実行: `references/parallel-execution-guide.md`
- 自己改善: `references/self-improvement-cycle.md`
