# Task 05 三層モデル定義表

## 層定義

| 層 | 役割 | 主なパス | 判定基準 |
|---|---|---|---|
| 層 A: 配布対象 plugin 本体 | marketplace で配布する plugin の正本。配布先でも単独で動作する必要がある | `plugins/<name>/`, `plugins/<name>/.claude-plugin/plugin.json`, `plugins/<name>/skills/`, `plugins/<name>/agents/`, `plugins/<name>/commands/`, `plugins/<name>/hooks/`, `plugins/<name>/scripts/`, `plugins/<name>/references/` | 他プロジェクトへ持って行きたい再利用単位か |
| 層 B: プロジェクト固有運用 | このリポジトリの設計、評価、派生生成、ログ、CI、運用補助 | `.claude/`, `.github/`, `doc/`, `eval-log/`, `scripts/`, `references/`, `CONVENTIONS.md`, `README.md`, `Makefile` | このリポジトリでだけ成立する運用物か |
| 層 C: 移行中 drift | Phase 0-2 の間だけ残す旧構造・暫定領域。Phase 4 で撤廃対象 | `creator-kit/`, 旧構造由来のルート `scripts/`, 旧構造由来のルート `references/` | まだ A/B に仕分け切れていない旧構造か |

## 参照規則

| 参照元 \ 参照先 | 層 A | 層 B | 層 C |
|---|---|---|---|
| 層 A | 同一 plugin 内のみ許容 | 禁止 | 禁止 |
| 層 B | 許容。派生 symlink や生成処理から参照してよい | 許容 | 許容 |
| 層 C | 許容 | 許容 | 許容。ただし Phase 0-2 の時限扱い |

## 配布判定

```text
変更対象ファイル X
   |
   +-- 他プロジェクトに持って行きたい? -- Yes --> 層 A (plugins/)
   |                                             |
   |                                      Plugin 名は決まっている?
   |                                         +-- Yes --> plugins/<name>/
   |                                         +-- No  --> タスク 08 で確定
   |
   +-- No
       |
       +-- このリポジトリの運用ログ/設計書? -- Yes --> 層 B
       |
       +-- 旧構造 (creator-kit/, scripts/, references/)? -- Yes --> 層 C (Phase 4 で除却)
       |
       +-- どれにも該当しない --> P1_structural proposal で分類を先に決める
```
