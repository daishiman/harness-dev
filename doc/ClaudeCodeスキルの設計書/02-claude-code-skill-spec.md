# 02. Skill 構造の設計判断

## このファイルの責務

Claude Code Skill の **構造に関する設計判断** だけを保持する。公式仕様の事実（ディレクトリ構成、配置場所、優先順位、live change detection、lifecycle の token budget、補助ファイル種別）は記載しない。

**更新責務マトリクス**: 公式仕様（lifecycle 値、配置パス、優先順位ルール等）が変わった場合は `16` のみを更新する。本ファイルは「なぜそう設計するか」「どう運用するか」が変わったときだけ更新する。

→ 公式仕様の正本は [16-official-skills-complete-reference.md](./16-official-skills-complete-reference.md) を参照
  - 配置場所: [§3](./16-official-skills-complete-reference.md#3-skill-の配置場所)
  - 自動 discovery: [§5](./16-official-skills-complete-reference.md#5-自動-discovery)
  - Live change detection: [§4](./16-official-skills-complete-reference.md#4-live-change-detection)
  - Skill content lifecycle (token budget): [§14](./16-official-skills-complete-reference.md#14-skill-content-lifecycle)
  - Skill directory 構成と補助ファイル: [§7](./16-official-skills-complete-reference.md#7-skill-directory-構成) / [§12](./16-official-skills-complete-reference.md#12-supporting-files)
  - Reference content（参照内容）と Task content（タスク内容）: [§8](./16-official-skills-complete-reference.md#8-skill-content-の種類)

## 設計判断 1: どのスコープに置くか

| 状況 | 推奨スコープ | 理由 |
|---|---|---|
| 個人の日常 workflow（commit、PR 作成等） | Personal (`~/.claude/skills/`) | repository を汚さない、全 project で再利用 |
| team 共有の規約・workflow | Project (`.claude/skills/`) | version control で履歴を残し review を通せる |
| monorepo の package 固有 | nested Project | 作業中 package でだけ自動 discovery される |
| 組織強制 | Enterprise (managed) | 個人が override できないことを保証 |
| 配布したい再利用 unit | Plugin | namespace 衝突を避けつつ独立 update |

**Why（理由）**: 公式の優先順位（Enterprise > Personal > Project）は「強い側が勝つ」ため、組織強制したい Skill を Project に置くと個人 Personal Skill に override されないが、逆に試行錯誤中の Skill を Enterprise に置くと取り返せない。**最小権限スコープ**で始めて昇格させるのが安全。

## 設計判断 2: Reference（参照） 型と Task 型の使い分け

| 種別 | 命名規約（推奨） | invocation | `disable-model-invocation` |
|---|---|---|---|
| Reference（参照） 型（規約・dictionary） | `ref-*` | Read 経由 or auto load | しばしば `true` |
| Task 型（手順・副作用あり） | `run-*` / 動詞-名詞 | `/skill-name` or auto | 副作用強なら `true` |

**Why（理由）**: 混在させると Claude が「読むべき」か「実行すべき」か判断を誤る。Reference（参照） 型は description で「Use when editing X」のように適用条件を書き、Task 型は「Use when the user asks to deploy」のように動作要求を書く（日本語で書くこと）。

## 設計判断 3: nested `.claude/skills/` の活用

monorepo で repository root に共通 Skill、`packages/frontend/.claude/skills/` に frontend 固有 Skill を置く。**作業対象 file の位置で自動 discovery が変わる** という公式挙動を利用し、Claude が無関係 Skill の description を context に持たないようにする。

注意: `--add-dir` は file access を増やすが、`.claude/skills/` 以外の `.claude/` 設定は root 化されない（→ [§6](./16-official-skills-complete-reference.md#6-additional-directories)）。CLAUDE.md は `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` が必要。

## 設計判断 4: compaction 後の token budget 制約への対策

公式 lifecycle により、compaction 後は最近呼ばれた Skill 順に先頭が一定 token だけ残り、それ以外は drop される（数値は → [16 §14](./16-official-skills-complete-reference.md#14-skill-content-lifecycle)）。設計への含意:

- `SKILL.md` の **冒頭 30 行に目的・出力契約・禁則** を集約する。 (`PD-002` として rubric.json で機械強制される)
- 重要 rule を末尾に置かない（lost in the middle）。
- 生成対象 `SKILL.md` の出荷基準は `08` の 300 行 hard cap なので、300 行を超えそうなら補助ファイルへ逃がす。`doc/スキルの設計書/*.md` はこの上限の対象外。
- compaction で消えた場合は **再 invocation できる前提** で hook と組み合わせる。

詳細な Progressive Disclosure（段階的開示） 設計は [07-progressive-disclosure.md](./07-progressive-disclosure.md)。

## 設計判断 5: 補助ファイルへの「案内」が必須

`SKILL.md` から補助ファイルへの案内を書かなければ、Claude から見れば存在しないのと同じ。本文末尾に `## Additional resources` を置き、各補助ファイルが「何を含み、いつ読むか」を 1 行で書く。

```markdown
## Additional resources

- `reference.md`: 全 API field 一覧。新規 endpoint 設計時に Read。
- `examples/`: input/output サンプル。出力 format に迷ったら Read。
- `scripts/validate.sh`: 生成後の自動検証。完了前に必ず Bash で実行。
```
