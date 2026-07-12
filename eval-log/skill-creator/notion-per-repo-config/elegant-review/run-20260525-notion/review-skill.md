# Elegant Review: Notion per-repo config 仕組み

- **対象**: `.notion-config.json` + `notion_config.py` SSOT loader + 関連 sync/intake scripts
- **run_id**: run-20260525-notion
- **status**: complete (iteration 1, safety_valve_fired=false)
- **verdict**: 4 条件すべて PASS

## 検証した 3 つのユーザー懸念

| # | 懸念 | 検証結果 |
|---|---|---|
| A | xl-skills repo で共有 Notion key/DB ID が正しく使われるか | **OK**: `notion_http.get_me()` が bot `xl-ClaudeCode-Skill-Interview` を返す。`get_db_id('skill-list')` が config 内 ID を解決 |
| B | Keychain `notion-api-key` のグローバル衝突対策 | **OK**: `notion-api-key.<slug>` への namespacing 実装。xl-skills 自身も `notion-api-key.xl-skills` / account=`xl-skills` へ migrate 済 |
| C | 100% 再現性 | **OK**: `init-notion-config.py` (1 コマンド生成) + `lint-notion-config.py` (規約違反を ERR) の twin pattern で機械的に強制 |

## 改善実装一覧 (Phase 3, 全 8 件)

1. `notion_config.find_repo_root`: `.git` AND xl-skills marker の AND 条件化 (KJ-4, 他 repo 誤読防止)
2. `notion_config.get_db_id`: env-first SSOT に統一 (KJ-2)
3. `notion_http._resolve_token`: env > config > legacy の単一解決経路に統合 (KJ-2)
4. `keychain_get_secret`: module-level constants → 毎呼び出し env 再評価 (KJ-1, 同 process 内 repo 切替対応)
5. `.notion-config.example.json`: slug placeholder 化 (KJ-1, 裸名コピペ防止)
6. **`scripts/init-notion-config.py` 新設**: git remote basename → slug 自動推定 → namespaced config + Keychain 登録コマンド生成 (KJ-3)
7. **`scripts/lint-notion-config.py` 新設**: L1-L5 (legacy 名 / placeholder / slug 不一致 / Keychain 未登録) を ERR (KJ-3)
8. `notion-per-repo-setup.md`: init flow と解決順を反映、なぜ slug 必須かの理由を本文に記載

## 4 条件 verdict

| 条件 | severity tag 件数 | 判定 |
|---|---|---|
| 矛盾なし (C1) | contradiction=0 | PASS |
| 漏れなし (C2) | omission=0 (init/lint 両方実装済) | PASS |
| 整合性あり (C3) | inconsistency=0 (token 解決経路を 1 本化) | PASS |
| 依存関係整合 (C4) | dependency_break=0 (repo_root 境界 + Keychain 名前空間整合) | PASS |

警告枠 `smell` × 2 件残置 (`get_db_id` SSOT 集約 = 既に実装済で smell 解消、`--explain` flag = 将来課題)。

## E2E 検証ログ

```
$ python3 scripts/lint-notion-config.py
[lint-notion-config] OK service=notion-api-key.xl-skills account=xl-skills dbs=3
exit 0

$ /usr/bin/python3 -c 'import sys; sys.path.insert(0,"plugins/skill-intake/scripts"); import notion_http; print(notion_http.get_me()["name"])'
xl-ClaudeCode-Skill-Interview
```

## 横展開資産 (amplified patterns)

- **shape vs identity 分離**: schema (properties=共有) と config (DB ID/token=repo 固有) を物理的に別ファイルへ分離
- **init+lint twin**: 「正しい初期状態を作る script」と「drift を機械検出する script」の対パターン。CI で後者を回せば規約違反が PR で止まる
- **SSOT loader via symlink**: `plugins/skill-creator/scripts/notion_config.py` を `plugins/skill-intake/scripts/notion_config.py` から symlink。複数 plugin が同じ解決ロジックを参照

## 残課題 (human review 推奨)

- CI への `lint-notion-config.py --skip-keychain` 組み込み (ローカル lint は merge gate 化済んでない)
- 他 repo 移植時の dogfooding: 実際に別 repo へ symlink して migrate を 1 回通す
