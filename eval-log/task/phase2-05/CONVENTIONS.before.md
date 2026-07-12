# CONVENTIONS

このファイルは、リポジトリ直下で共有する運用規約を記録する。

## 三層モデル

`xl-skills` では、plugin 移行中のファイル責務を層 A / 層 B / 層 C に分ける。以後の変更は、まずこの三層モデルで所属を判定してから実施する。

### 層定義

| 層 | 役割 | 主なパス | 判定基準 |
|---|---|---|---|
| 層 A: 配布対象 plugin 本体 | marketplace で配布する plugin の正本。配布先でも単独で動作する必要がある | `plugins/<name>/`, 将来の `plugins/<name>/.claude-plugin/plugin.json`, `plugins/<name>/skills/`, `plugins/<name>/agents/`, `plugins/<name>/commands/`, `plugins/<name>/hooks/`, `plugins/<name>/scripts/`, `plugins/<name>/references/` | 他プロジェクトへ持って行きたい再利用単位か |
| 層 B: プロジェクト固有運用 | このリポジトリの設計、評価、派生生成、ログ、CI、運用補助 | `.claude/`, `.github/`, `doc/`, `eval-log/`, `scripts/`, `references/`, `CONVENTIONS.md`, `README.md`, `Makefile` | このリポジトリでだけ成立する運用物か |
| 層 C: 移行中 drift | Phase 0-2 の間だけ残す旧構造・暫定領域。Phase 4 で撤廃対象 | `creator-kit/`, 旧構造由来のルート `scripts/`, 旧構造由来のルート `references/` | まだ A/B に仕分け切れていない旧構造か |

層 C は恒久的な置き場ではない。層 C に新規責務を追加する場合は、移行先が層 A か層 B かを同時に記録する。

### パス列挙

- `plugins/<name>/`: 層 A。plugin として配布する正本。
- `.claude/`: 層 B。開発環境で使う symlink、自動生成 settings、ローカル運用情報。
- `doc/`: 層 B。設計書とタスク仕様書の正本。
- `eval-log/`: 層 B。検証ログ、レビュー承認、移行証跡。
- `scripts/`: 層 B。ただし旧構造からの未仕分け script は層 C として扱い、Phase 4 までに A/B へ移すか除却する。
- `references/`: 層 B。ただし旧構造からの未仕分け reference は層 C として扱い、Phase 4 までに A/B へ移すか除却する。
- `creator-kit/`: 層 C。試験移行前の暫定正本であり、最終形では `plugins/skill-creator/` に吸収する。

### 参照規則

| 参照元 \ 参照先 | 層 A | 層 B | 層 C |
|---|---|---|---|
| 層 A | 同一 plugin 内のみ許容 | 禁止 | 禁止 |
| 層 B | 許容。派生 symlink や生成処理から参照してよい | 許容 | 許容 |
| 層 C | 許容 | 許容 | 許容。ただし Phase 0-2 の時限扱い |

必須規則:

- A -> A: 同一 `plugins/<name>/` 内の参照のみ許容する。別 plugin への直接参照は plugin 間依存 governance が整うまで禁止する。
- A -> B: 禁止する。plugin 配布物は `.claude/`, `doc/`, `eval-log/`, ルート `scripts/`, ルート `references/` に依存してはならない。
- B -> A: 許容する。`.claude/` 派生生成、CI、検証、設計書は `plugins/<name>/` を参照してよい。
- C -> 任意: 許容する。ただし移行期間中だけの暫定参照であり、Phase 4 までに撤廃または A/B へ分類する。

Phase 0-2 では A -> B 禁止に例外を作らない。例外が必要な場合は、設計書 33 章の change governance に従い P1_structural proposal として扱う。

### 配布判定フローチャート

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

### 運用原則

1. 新規 plugin 配布物は層 A に置く。
2. このリポジトリ固有の設計、検証、ログ、生成補助は層 B に置く。
3. 層 C は移行中 drift の観測場所としてのみ使い、恒久仕様にしない。
4. 層 A から層 B/C への参照を見つけた場合は、配布前 gate で失敗扱いにする。
5. 層 C の残存は Phase 4 で撤廃対象として棚卸しする。
