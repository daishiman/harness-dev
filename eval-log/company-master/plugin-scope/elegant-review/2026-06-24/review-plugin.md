# elegant-review: company-master (plugin scope) — 2026-06-24

## 概要
- **対象**: `plugins/company-master/`（plugin 全体）
- **依頼観点**: ①skill-creator 仕様準拠 ②README の導入/APIキー/シークレット設定の網羅性（不特定多数が Claude Desktop + マーケットプレイス install で設定完了できること）③company-master 実装の正しさ
- **手法**: 思考リセット → 30 思考法（A2:10 / A3:9 / A4:11）並列分析 → 改善実行 → 独立 approver 再検証
- **最終 verdict**: 矛盾なし PASS / 漏れなし PASS / 整合性あり PASS / 依存関係整合 PASS（**4条件全 PASS**）
- **承認**: proposer ≠ approver を満たし、独立 context が **APPROVE**

## フェーズ実行ログ
- **Phase 1（思考リセット・read-only）**: `elegant-reset-observer` が fresh で全構成（skill2/cmd2/agent3/hook1/script13/ref9/prompt1）を再読込し `shared_state.md` 生成、3観点の懸念を種まき。
- **Phase 2（並列分析・read-only）**: 3 SubAgent が 30 思考法を分担適用。Phase 1 の種を実ファイルで二段確認し、偽の種4件（確認用URL一貫性/validate二重定義/preflight exit2/reference_refs重複）を棄却。
- **Phase 3（改善実行・write）**: 集約 findings を severity 順に是正。pre-phase3.patch でスナップショット取得済み。

## 是正した findings（fixed）
| id | severity | 条件 | 内容 | auto |
|---|---|---|---|---|
| LS-01 | contradiction | C1 | 配布モデル既定の正本割れ（proxy既定の取り残し6箇所）→ BYO直結既定へ一斉是正（2026-06-24 チーム判断+実装と一致） | 判断要 |
| SS-01/MD-01/MD-08 | dependency_break | C4 | README の /run-skill-feedback・/skill-creator:install-bundle が skill-creator 依存である旨を明記。単独 install では自然言語導線が常時有効と明示 | 要 |
| LS-04 | omission | C2 | enrich agent Outputs 雛形に正本キー source_by_field を追加（実装出力と一致） | 判断要 |
| MD-06 | omission | C2 | README に Mac 専用注記 / gBizINFO 発行待ち / 郵便番号は任意機能 を追記 | 要 |
| LS-02 | inconsistency | C3 | README-setup の deny 件数 7→10、2鍵→3鍵 | 要 |
| LS-03 | inconsistency | C3 | build resource-map の confirm-url-template キーを実 TEMPLATE_KEYS（footer 不在）へ是正 | 要 |
| MD-02 | inconsistency | C3 | README 冒頭「コマンド不要」の過剰約束を「定型コマンドを使う」へ後退 | 要 |
| SS-02 | inconsistency | C3 | composition に scripts capability の粒度規約コメント追記 | 要 |
| INC-EXTRA | inconsistency | C3 | settings-hardening _doc の「日本郵政」→「日本郵便」統一（approver 指摘） | 要 |

## チーム判断で確定した方針
- **feedback 導線（symlink run-skill-feedback）**: Option C = **symlink 維持・依存を明記**。README は skill-creator 同梱時のみ /run-skill-feedback が動作する旨を明記済み。単独 install では自然言語導線（「company-master の○○を直して」）が常時有効。

## 残課題（deferred / proposed・別 PR 候補）
- **SS-04（proposed）**: README 内 `/​<plugin>:<cmd>` 参照の解決性を検査する lint を新設し governance-check へ配線（全 plugin の単独 install 到達不能コマンドを横展開で予防）。
- **LS-05（deferred）**: doctor --probe の本番クエリ「霞が関」が一意確定しない場合 WARN に落ちる懸念。実 API キー登録後の疎通確認を要する。
- **MD-05（deferred）**: notion-config.fixed.json に社内 DB ID をコミットする既定の自己定義（社内ツール vs 汎用配布物）。配布ポリシー選択を要する。
- **MD-07（deferred）**: `/plugin marketplace add .`（カレントフォルダ方式）の複雑さ。社内 GitHub マーケットプレイス登録で簡素化できる余地（配布インフラ運用変更）。
- **MD-09（deferred）**: 確度ラベル「ネット検索(要確認)」「未確定(要確認)」の語尾衝突。SSOT enum + validate と連動するため影響大。
- **SS-03（deferred）**: postal_proxy.py の script_refs 種別注記（dangling でないため smell）。

## 機械検証（4条件 PASS の客観 signal）
- C1 再 grep：stale「プロキシ既定」現在状態主張の残存 = 0（履歴記述のみ残置）
- SKILL.md 本文行数：build 234 / backfill 162（P0-2 ≤300 PASS）
- lint-company-master-vendored-deps：OK（scripts 13 件 外部依存ゼロ）
- lint-skill-name / description / validate-frontmatter：OK=3 VIOLATION=0
- pytest（company-master 関連）：95 passed
- settings-hardening.json：deny 10 件・JSON 健全
- 独立 approver：C1-C4 全 PASS・新規矛盾なし・**APPROVE**
