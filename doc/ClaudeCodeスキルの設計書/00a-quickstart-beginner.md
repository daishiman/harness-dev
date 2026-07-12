# 00a. Quickstart: 15分で最小 Skill を作る

目的: まず 1 本の Skill を作り、Claude Code に認識・発動・検証させる。

## 1. Skill の置き場所を決める

| 使い方 | 置き場所 |
|---|---|
| 全プロジェクトで使う | `~/.claude/skills/<skill-name>/SKILL.md` |
| この repo だけで使う | `.claude/skills/<skill-name>/SKILL.md` |

最初は project skill でよい。

```bash
mkdir -p .claude/skills/ref-project-rules
```

## 2. 最小 `SKILL.md` を作る

```markdown
---
name: ref-project-rules
description: Project rules. Use when editing or reviewing this repository.
---

# Project rules

Use these rules when editing this repository.

## Core rules

- Follow the existing file structure.
- Prefer existing helper functions before adding new abstractions.
- Mention changed files in the final response.
```

## 3. Claude Code で確認する

Claude Code を再起動、または既存 watched directory 内ならそのまま反映を待つ。

確認 prompt:

```text
この repo の編集ルールを確認して
```

直接呼び出し:

```text
/ref-project-rules
```

## 4. 発動しない場合

確認順:

1. `SKILL.md` が skill directory 直下にある。
2. `description` が user prompt と対応している。
3. top-level `.claude/skills/` を session 開始後に初めて作ったなら Claude Code を再起動する。
4. `disable-model-invocation: true` を付けていない。
5. `paths` で対象 file が絞られすぎていない。

## 5. 次にやること

- 知識だけなら `ref-*` として育てる。
- file 作成や command 実行を含むなら `run-*` に分ける。
- 品質判定が必要なら output contract（契約） を追加する。
- 評価が甘いなら `assign-*-evaluator` を追加する。

## 6. 次に読むべき設計書

最小 Skill ができたら、以下を順に参照すると詰まりにくい。

- [03-yaml-frontmatter-reference.md](03-yaml-frontmatter-reference.md): frontmatter の設計判断と組み合わせ事故
- [11-templates.md](11-templates.md): prefix 別 SKILL.md テンプレート
- [13-checklists.md](13-checklists.md): リリース前セルフチェック 4 条件
- [19-troubleshooting.md](19-troubleshooting.md): 発動しない・誤発動・権限拒否の対処
