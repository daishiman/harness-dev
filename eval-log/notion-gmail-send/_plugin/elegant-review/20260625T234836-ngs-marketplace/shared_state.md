# shared_state（Phase 1 → Phase 2 ファンアウト中継）

## 200字要約
notion-gmail-send は Notion2DB→Gmail一斉個別送信 plugin（6 skills + 1 agent + 1 hook、plugin.json は entry_points 構造で整備済）。症状＝マーケットプレイス一覧に非表示。最重要観察＝ルート `.claude-plugin/marketplace.json` の `plugins[]`（13件登録）に notion-gmail-send が**未登録**。company-master/mf-kessai は登録済なのに本plugin だけ取り残し。登録形式整合と version 整合も要確認。

## 観察した全関連ファイル（絶対パス）
- /Users/dm/dev/dev/xlocal/xl-skills/.worktrees/task-20260625-234505-wt-3/.claude-plugin/marketplace.json  ← プラグイン一覧の定義元（SSOT）
- /Users/dm/dev/dev/xlocal/xl-skills/.worktrees/task-20260625-234505-wt-3/plugins/notion-gmail-send/.claude-plugin/plugin.json
- /Users/dm/dev/dev/xlocal/xl-skills/.worktrees/task-20260625-234505-wt-3/plugins/notion-gmail-send/README.md
- plugins/notion-gmail-send/{skills,agents,hooks,lib,tests}/  ← ツリー

## 検証すべき仮説（先入観として断定しない・独立検証対象）
H1: マーケットプレイス非表示の直接原因は marketplace.json plugins[] への登録漏れ（C2 漏れなし FAIL）

## 第一印象の懸念点（観察事実・原因断定なし）
- O1: marketplace.json plugins[] 13件に notion-gmail-send が無い（最重要）
- O2: plugin.json の version=0.1.0。marketplace 登録時の version 整合要確認
- O3: 他 plugin エントリは {name, source, description, version, category, tags} の6キー構成。追加時この形式に合わせる必要
- O4: plugin.json description が極端に長い（marketplace 表示文との整合・冗長性）
- O5: bundles / bundle_targets / entry_points 等 plugin.json 固有フィールドと marketplace 登録の依存関係整合
