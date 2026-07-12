---
name: execution-surface-rubric
description: スキルを Claude Code / Cowork / 両方 のどこで実行するかを判定する rubric。intake-final-schema.json#/properties/notion_db_properties.実行環境 と notion-db-schema.json#/properties/実行環境 の値ドメインの正本。
type: reference
version: 1.0.0
last_updated: 2026-05-22
---

# 実行サーフェス判定 rubric

intake 完了時に `execution_surface.primary ∈ {Claude Code, Cowork, 両方}` を確定するための判定基準。
Notion DB select 列「実行環境」と一対一対応する。

## 1. 判定木 (top-down)

```
Q1: スキルがローカルファイル R/W、Bash/Python subprocess、git ops のいずれかを必要とするか？
  ├─ YES → Q2 へ
  └─ NO  → Q3 へ

Q2: スキルが MCP のみで完結可能か (= ローカル依存をオプション化できるか)？
  ├─ YES → "両方"
  └─ NO  → "Claude Code"

Q3: スキルが MCP / Artifacts / 対話 UI を中心に動作するか？
  ├─ YES → "Cowork"
  └─ NO  → "Claude Code" (フォールバック: 不明時はローカル前提)
```

## 2. 観測フィーチャ → surface 対応表

| フィーチャ | Claude Code | Cowork | 両方 |
|---|---|---|---|
| `Read` / `Write` / `Edit` ツール必須 | ✅ | ❌ | ❌ |
| `Bash` / `subprocess` 実行 | ✅ | ❌ | ❌ |
| git ops (commit / branch / push) | ✅ | ❌ | ❌ |
| Notion / Slack / Gmail MCP のみで完結 | △ (可) | ✅ | ✅ |
| Artifacts (HTML/React preview) 中心 | ❌ | ✅ | ❌ |
| 対話的な hearing / 多段プロンプト | △ | ✅ | △ |
| ローカル fixture / eval-log への書込 | ✅ | ❌ | ❌ |
| schedule / cron / hook 連動 | ✅ | ❌ | △ |

## 3. 境界ケース

| ケース | 判定 | 理由 |
|---|---|---|
| 「Notion に投稿するだけ」スキル | Cowork | MCP only、ローカル R/W 不要 |
| 「Notion 投稿 + ローカル md 出力」 | Claude Code | ローカル Write が必須 |
| 「intake hearing → Notion 投稿」 | 両方 | hearing 部は Cowork でも可、ローカル context 化は CC 必須 |
| 「intake hearing → ローカル context.json」 | Claude Code | Write 必須 |
| 「分析エージェント (read-only)」 | 両方 | MCP fetch のみで完結する場合 |

## 4. 自動判定ヒューリスティック (harness-creator 向け)

`brief.cli_tools` / `brief.mcp_tools` / `brief.file_ownership` から決定論的に推定:

```
if brief.file_ownership not empty OR "Bash" in brief.cli_tools OR "git" in any cli:
    if brief.mcp_tools not empty AND brief.file_ownership covers only optional outputs:
        return "両方"
    return "Claude Code"
elif brief.mcp_tools not empty:
    return "Cowork"
else:
    return "Claude Code"  # default: 不明はローカル前提
```

## 5. Cowork 制約 (現時点で既知)

- ローカル FS なし: `Read/Write/Edit/Bash` ツール不在
- セッション間の永続化なし (Artifacts 内のみ)
- MCP 経由の外部 I/O は可能 (Notion / Slack / Gmail / Google Drive)
- スキル自体の登録は `claude.ai/skills` に直接 upload (harness repo とは別経路)
- harness repo のスキルを **そのまま** Cowork で呼べるのは `kind=ref / wrap` かつ `file_ownership=[]` の場合のみ

## 6. 「両方」を採用する基準

以下を**全て**満たす場合のみ "両方" を許可する:

1. `file_ownership` が空 (ローカル成果物を持たない)
2. `cli_tools` に Bash / Python が含まれない
3. すべての I/O が MCP または対話で完結
4. CI hook / scheduled trigger を要求しない

これに合致しないものは保守的に "Claude Code" 寄せに分類する。

## 7. canonical-source

- 列挙値正本: `intake-final-schema.json#/properties/notion_db_properties.properties.実行環境.enum`
- 判定 derive: `execution_surface.primary`
- Notion select: `notion-db-schema.json#/properties/実行環境.options`

3 箇所の値ドメインは常に同一でなければならない。verify_notion_schema.py が差異を eval-log/notion-conflicts.json に記録する。
