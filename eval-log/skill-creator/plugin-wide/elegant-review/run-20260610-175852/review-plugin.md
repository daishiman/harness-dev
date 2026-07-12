# elegant-review レポート: skill-creator skill構成最適性 (plugin-wide)

- run-id: run-20260610-175852 / 実施日: 2026-06-10
- テーマ: (1) SKILL.md単独/資産極少スキルの責務分離要否 (2) 複数資産スキルの構成最適性
- 結果: **4条件 全PASS / status: complete / 1周で収束** / 独立承認 APPROVE (spot check 10/10)
- 42 findings (30思考法 coverage 30/30) → 37 fixed + 5 設計判断記録

## ユーザーの問いへの回答

### Q1: SKILL.md しかないスキルに責務分離(prompts/references/scripts等)は必要か?
**不要が正解**(3分析エージェントが独立に同結論: 2軸思考・逆説思考・論点思考)。
- SKILL.md 単独は実体28スキル中 run-goal-seek の1件のみ。全資産を cross-skill 参照+completeness_exempt で充足する設計意図的な構成
- インライン40行Pythonは lint-goal-seek --self-test がトークン照合で正本と係留済みの「正当な二重実装」。分離するとこの SSOT 機構が壊れる
- 分離はファイル数増・参照hop増・dangling面積増という再現性コストを伴う。単一ファイル読了で実行完結する方が「100人中100人」に有利
- **恒久対策**: prompt-placement-convention.md に no-split threshold を成文化(分離は (a)第二消費者存在 (b)機械検証対象 (c)300行cap逼迫 のいずれか成立時のみ)。レビュー振動を構造的に停止

### Q2: 複数ファイル/ディレクトリがあるスキルの構成は最適か?
**ref-* 12本の同型構成は最適**(変更不要)。一方、真の問題は構成の粒度ではなく**正本→派生の照合断線**にあった:
- check-rubric-sync.py が creator-kit 移行残渣の死パスで恒久 exit 1 → rubric drift (L0 1.3.0 vs L2 1.2.0) が未検出で現存(実害)
- L2 rubric が 1.2.0 フルコピーで L0 1.3.0 の KL-* rule を採点から打ち消していた
- handoff schema 二重(draft-07 vs 2020-12、required 非互換)+量産テンプレが旧版を新規スキルへ複製
- resource-map 索引の dangling 3+6箇所(R-id リネーム未追従)

## 主要修正 (severity 順)

### contradiction (4→0)
- exempt宣言と実態の乖離(LS-201/MD-202) → 宣言の事実整合化+schema正本先行でPR URL項目追加
- rubric正規パスのlint間矛盾(LS-210) → references/rubric.json へ統一
- build-steps Phase D の固定Step記述がlint-goal-seekと自己矛盾(SS-212) → ゴールシーク構成へ書き換え

### omission (8→0)
- *_refs fail-open(MD-208) → 3段解決+不存在exit 1(YAML行内コメント偽陽性もパーサ修正)
- CI構成系lintがskill-creator/prompt-creator限定(SS-201) → 全pluginへ段階導入拡張
- creator-kit参照のメタ検出欠如(LS-215) → lint-path-canonical に fail-closed 検査追加+残存4箇所修正
- run kind の manifest検査漏れ(LS-211) → REQUIRED_BY_KINDに追加(段階導入)
- ALLOWED_DIRS warn未実装(LS-203)、L0先頭強制欠如(SS-214)、4充足手段の人間向け正本欠如(MD-211)

### inconsistency (11→0)
- L2 rubricフルコピー腐敗(MD-207) → delta-only化+upstream_version_pin 1.3.0
- handoff処置非対称(LS-206/MD-205) → redirect stub化(skill-brief既知解の横展開)
- resource-mapキー二流儀(LS-205) → file: へ9ファイル統一
- manifest宣言非対称(LS-204)、配布注記欠如(MD-204)、検証のschema未使用(SS-209)、保証範囲過大宣言(SS-210)、hook配置二系統(SS-202)、表層改善の再発防止(SS-213)

### dependency_break (8→0)
- check-rubric-sync死パス(LS-213/SS-205) → 修復・exit 0復旧・dry-run確認
- rubric upstream宣言のreferences/欠落 3+2箇所(SS-206/MD-206)
- 量産テンプレ旧schema参照(LS-207/SS-204) → 生成器根治
- resource-map/manifest dangling 9箇所(LS-208/SS-211)

## 検証
- 機械再検証 19/19 PASS、回帰テスト新規6+既存63 pass
- check-rubric-sync exit 0 / render-findings-score L0+L2合成 score=100 / 非L0先頭 exit 1
- SKILL.md cap: 288/292/286行(バッファ確保)

## 残課題(smell・次周回候補)
- self-testトークン照合の強度(LS-202/SS-207)、ref scaffold テンプレ化(MD-210)
- prompt-creator側の同型dangling(スコープ外)、manifest欠落7skillのwarning棚卸し

## 追補: 再発防止の機械層配線 (2026-06-10 後続対応)

ユーザー指摘「hook/CI で再現性高くカバーされているか」への対応として未配線4件+fail-open 1件を解消:

| 再発防止対象 | 機械層 | 配線先 | 強度 |
|---|---|---|---|
| rubric L0/L2 版ずれ (SS-205) | check-rubric-sync.py | run-ci-checks.sh (pre-push hook SSOT) + creator-kit-ci.yml | strict |
| creator-kit 残存参照 (LS-215) | lint-path-canonical --scripts-dir | 同上 | strict |
| lint fail-open 退行 (MD-208/LS-211/LS-215) | 回帰テスト6件 | pytest 統合 (tests/ + governance-lint/tests/) ローカル+CI | strict |
| rubric_refs 解決 (LS-210) | lint-rubric-refs-exist | run-ci-checks.sh | soft (棚卸し待ち) |

追加修正:
- lint-path-canonical.py の fail-open バグ(--scripts-dir 単独呼出で targets 空→help+return 2 となり creator-kit 検査に未到達)を修復
- findings-partial.schema.json の required を paradigm_findings のみへ縮約(DUP-REQUIRED-SET 解消、per-agent 出力の意味とも整合)

配線後検証: pytest 69 passed / run-ci-checks PASS 66・レビュー起因 FAIL 0 (残2件は company-master 別作業WIP起因)
