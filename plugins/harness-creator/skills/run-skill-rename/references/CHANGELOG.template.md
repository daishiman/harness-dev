# CHANGELOG テンプレート（改名エントリ用）

run-skill-rename Step 4 が `references/CHANGELOG.md` に追記する雛形。

```markdown
## {{date}} rename: {{old_name}} → {{new_name}}

- old: `{{old_name}}`
- new: `{{new_name}}`
- reason: {{reason_one_line}}
- aliases: [{{old_name}}]
- updated_callers:
  - {{caller_skill_1}}
  - {{caller_skill_2}}
- source: {{source_url_or_path}}
- source-tier: internal
- audited: {{date}}
```

## 必須項目
- `date` (YYYY-MM-DD)
- `old_name`, `new_name`
- `reason_one_line` (1行で改名理由)
- `aliases` （旧名を必ず含める）

## 推奨項目
- `updated_callers` (`pair:` / `Skill()` 参照を更新した呼び出し元)
- `source` / `source-tier` (doc/21 出典追跡)
