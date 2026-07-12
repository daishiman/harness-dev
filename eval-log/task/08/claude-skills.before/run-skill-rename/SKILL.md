---
name: run-skill-rename
description: Skill名を変更するとき、改名後の参照整合を確認するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[old-skill-name] [new-skill-name]"
arguments: [old_name, new_name]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(python3 *)
  - Bash(git *)
kind: run
owner: team-platform
since: 2026-05-18
# doc/21 source-traceability
source: doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md
source-tier: internal
last-audited: 2026-05-19
audit-trigger: source-update
effect: local-artifact
---

# run-skill-rename

## Purpose & Output Contract

スキルを安全に改名するワークフロー（A5/C2: 未実装スキルの新規作成）。

**入力**: old_name (現在のスキル名), new_name (新しいスキル名)
**出力**:
- 改名済みディレクトリ `$OUT_BASE/<new-name>/`
- SKILL.md frontmatter の `name:` 更新
- `aliases:` に旧名を追加
- `CHANGELOG.md` に改名エントリ追加
- 参照元スキルの `pair:` / `Skill()` 記述を新名に更新

**完了条件**: lint-skill-name.py, lint-skill-tree.py が exit 0。

## Key Rules

1. **ディレクトリ名 == frontmatter.name**: 第8条。改名後は両方を同時更新。
2. **alias必須**: 旧名を `aliases:` に登録して参照切れを防ぐ（第6条）。
3. **CHANGELOG必須**: 改名エントリを `references/CHANGELOG.md` に追加（第6条）。
4. **参照元更新**: `pair:` / `Skill()` の旧名参照を新名に更新する。
5. **gitの履歴保持**: `git mv` を使い、ファイル移動の履歴を残す。

## Steps

### Step 0: 出力先解決

```bash
# SKILL_DIR / OUT_BASE を環境変数または fallback で確立する。
# creator-kit 配置なら OUT_BASE=creator-kit/skills、それ以外は .claude/skills
source creator-kit/scripts/resolve-skill-dirs.sh
# または手動 fallback:
# OUT_BASE="${CLAUDE_SKILL_OUT_BASE:-}"
# if [ -z "$OUT_BASE" ]; then
#   if [ -d "creator-kit/skills" ]; then OUT_BASE="creator-kit/skills"
#   else OUT_BASE=".claude/skills"; fi
# fi
```

### Step 1: 事前検証

```bash
# 旧名の存在確認
ls "$OUT_BASE/$OLD_NAME/SKILL.md"

# 新名の重複確認
ls "$OUT_BASE/$NEW_NAME" 2>/dev/null && echo "ERROR: new name already exists" && exit 1

# 新名の命名検証
python3 creator-kit/scripts/lint-skill-name.py --name "$NEW_NAME"
```

### Step 2: ディレクトリ改名

```bash
git mv "$OUT_BASE/$OLD_NAME" "$OUT_BASE/$NEW_NAME"
```

### Step 3: frontmatter 更新

`$OUT_BASE/$NEW_NAME/SKILL.md` を Edit:
- `name: $OLD_NAME` → `name: $NEW_NAME`
- `aliases:` に `$OLD_NAME` を追加（なければ新規追加）

### Step 4: CHANGELOG 更新

`$OUT_BASE/$NEW_NAME/references/CHANGELOG.md` に追記:
```markdown
## <date> rename

- Renamed from `$OLD_NAME` to `$NEW_NAME`
- Reason: <ユーザー指定の理由>
- aliases: [$OLD_NAME]
```

### Step 5: 参照元更新

```bash
# pair: / Skill() の旧名参照を検索
grep -r "$OLD_NAME" "$OUT_BASE/" --include="SKILL.md" -l
```
ヒットした各ファイルを Edit で新名に更新。

### Step 6: Lint 検証

```bash
python3 creator-kit/scripts/lint-skill-name.py "$OUT_BASE/$NEW_NAME/SKILL.md"
python3 creator-kit/scripts/lint-skill-tree.py "$OUT_BASE/$NEW_NAME"
python3 creator-kit/scripts/validate-frontmatter.py "$OUT_BASE/$NEW_NAME/SKILL.md"
```

すべて exit 0 でなければ Step 3 へ戻る。

## Gotchas

- **git mv 省略禁止**: `rm` + `mkdir` で移動すると git 履歴が途切れる。
- **alias 追加忘れ**: alias なしで旧名参照があると呼び出し先が消える。
- **CHANGELOG 省略禁止**: 第6条違反。CI で検出される。
- **部分更新**: ディレクトリ名だけ or frontmatter だけの更新は不整合を生む。Step3とStep1は必ずセット。

## Additional Resources

- `06-classification-and-naming.md` — 命名規約 第6条（改名手続き）
- `13-checklists.md` — 命名規約条文チェックリスト
- `creator-kit/scripts/lint-skill-name.py` — 命名検証
- `creator-kit/scripts/resolve-skill-dirs.sh` — OUT_BASE 解決スクリプト
