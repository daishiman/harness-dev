# elegant-review: plugin-plans/ubm-goal-setting/ (2026-07-04)

> 思考リセット → 30思考法 × 3 SubAgent 並列分析 → 改善 → proposer≠approver。
> scope_mode: plan（run-plugin-dev-plan 生成の開発計画成果物）。前回レビュー 2026-07-02 の後続（ドリフト検出 + backlog 消化）。

## verdict（独立 approver: plugin-dev-plan-evaluator）

| 条件 | 判定 | signal |
|---|---|---|
| C1 矛盾なし | PASS | contradiction=0 |
| C2 漏れなし | PASS | omission=0 |
| C3 整合性あり | PASS | inconsistency=0 |
| C4 依存関係整合 | PASS | dependency_break=0 |

- 機械決定論ゲート: 全12 exit0（現 worktree 実測）。単一 skill 退化なし（skill2/sub-agent10/slash-command2/hook1/script3=18）。
- 30思考法カバレッジ: used=30 / skip=0（A2=10 / A3=9 / A4=11）。

## 適用した改善（plan 内完結・最小パッチ・over-annotation なし）

- **FIX-B（provenance 回復）**: `plan-findings.json` の plan_dir と全 gate command が旧 worktree `task-20260701-214243-wt-1` の絶対パスで焼かれ stale だった。独立 approver が現 worktree `task-20260703-124959-wt-7` で全12ゲートを**実際に再実行**し再生成（sed による虚偽 attestation を回避）。3 analyst 一致（LS3/MD1/SS9）。
- **FIX-D（数値ピン規律の対称化）**: index 受入確認は「数値が宙に浮かないよう定義元を pin」と自ら宣言し 21項目のみ pin していた。output-formatter の「15項目品質チェック」定義正本（移送元 `agents/output-formatter.md` の『品質チェックリスト(コンテンツ検証)』節 + `references/output-formats.md` 公式21項目ブロック順）を 21項目と対称に pin。役割区別（21=出力構造 / 15=保存前コンテンツ検証）も明記。3 analyst 一致（LS2/MD2/SS8）。
- **FIX-E（mutable asset SSOT 完全性）**: `kitahara-principles-db.md` が references_config_assets と vendor L3_bookkeeping の2 surface に跨るが、L3 build_target 列挙に本ファイルが欠落（自 tier 記述と不一致）していた。build_target へ追記し「初期シード配置正本=references_config_assets / runtime writeback 正本=L3」の役割対応を1句 pin。3 analyst 一致（LS6/MD4/SS3）。

いずれも編集後に全12ゲート再実行し回帰0を確認。編集前バックアップ = `index.md.pre` / `component-inventory.json.pre`。

## 報告に留めた findings（backlog・plan 内で直すと有害 or scope 外）

### A. 生成器 scope（plugin-dev-planner / harness-creator）— instance で直すとゲート回帰 or SSOT ドリフト

| # | finding | 根拠 analyst | 直さない理由 |
|---|---|---|---|
| C-1 | steps1-5(C08-C12) が `independent_context=false`（起動しない inline 参照断片）なのに `component_kind=sub-agent`/`build_kind=agent`。description が auto-invocation トリガ契約と衝突 | LS1/LS4/LS5/LS10, MD3, SS4 | component_kind に「gate 携帯可能な非起動 reference-component」枠が無い語彙ギャップが根本原因（LS10 why）。instance で kind を変えると detect-unassigned/check-spec-gates が enum で回帰 FAIL |
| A-1 | 二相 build の scaffold 閉路: `C16.depends_on⊇{C01}`（criteria 順）↔ `C01.requires_parent_scaffold=C16`（物理順）を build-before エッジ合成すると C01↔C16 閉路。routes は scaffold 相を first-class node に持たない | LS9, MD5, SS1/SS7/SS10 | check-build-handoff の schema 変更（scaffold_phase node 分割 + 逆エッジ閉路検査）を要する生成器 scope。plan の prose は既に workaround を明記 |

**推奨（生成器 backlog）**: (1) harness-creator 語彙に「非起動 reference-component」種 or agent の `dispatch:none`/`inline_fragment` 機械キーを新設し、非起動断片の description/lint/verdict 被覆を意味論に一致させる。(2) check-build-handoff に requires_parent_scaffold を逆エッジとして畳んだ閉路検査を追加し、routes へ scaffold node を明示。

### B. repo 横断慣習 — 単独修正は横断不整合を生む

| # | finding | 根拠 | 直さない理由 |
|---|---|---|---|
| F-1 | PreToolUse hook `timeout: 10000`。Claude Code の hook timeout は秒指定で 10000=約2.7時間。ミリ秒(TIMEOUT_MS)慣習との単位曖昧 | MD7, SS2 | harness-creator/plugin-dev-planner の実 manifest も 10000 を共有。本 plan だけ 10→変更すると siblings と不整合 |

**推奨**: timeout 単位（TIMEOUT_MS 慣習 vs Claude Code 秒指定）を repo 規約として一度確定し、`hook-skeleton.md` 正本経由で全 plugin へ横展開統一。

### C. 設計深化（low・PASS 非阻害）— report-only

- MD8: `ubm-write-path-guard` の縮退契約が検知系と非対称（`UBM_VAULT_ROOT` 未設定時の許可/拒否ポリシ・L3 writeback allowlist 未 pin）。best/worst/edge を P07/P11 受入シナリオ化推奨。
- MD6: faithful-transfer の等価ガード（golden-master）が旧3 .sh のみ。phase3-interviewer DROP・steps inline 化の topology 変更に behavioral-equivalence 受入項目が無い。
- SS5: `knowledge/schema.json` を C05(read)/C15(write) が対称参照する共有 SSOT だが、双方の schema conformance を突合するゲートが無い（片側追従で A/B 同時崩壊の negative-sum リスク）。
- SS6: distributable:false 個人 plugin で `feedback_deploy.enabled=true`。improvement-request DB ID 供給手順（.notion-config.json 設置）を build 手引きへ明記 or optional 化して価値/コスト整合。
- MD9: C14 欠番が散文のみ（機械可読 `reserved_ids:["C14"]` フィールド無し）。原資産11/active10/総18 の count glossary が novice 障壁。
- LS8: capability 軸（A/B）が P02 散文のみで component エントリに機械可読フィールド無し（第2軸の符号化粒度差）。

## 移植完全性監査（源泉↔計画 忠実度・機械ゲート射程外）

> 契機: ユーザー問い「既存 UBM の情報を全て漏れなく反映する仕組みか／harness-creator で更に精度良くできるか」。C2「漏れなし」ゲートは *goal-spec→index* トレースのみで *原本→goal-spec* の抽出網羅性を検証しないため、原本（`~/dev/dev/ObsidianMemo/.claude/skills/ubm-goal-setting/`）を SSOT に capability A/B を実地突合した。

### 検出した実移植漏れ（機械12ゲート緑の裏に隠れていた）
| # | 漏れ | severity | 根拠(原本) | 閉鎖 |
|---|---|---|---|---|
| 1 | **Phase 5「Daily.md 自動更新」丸ごと脱落** | CRITICAL | SKILL.md:253/388-414（保存後に Templates/Daily.md の embed 4箇所を最新目標へ置換） | C16 に Phase6-daily-update responsibility+checklist+boundary / L2 を write 対象へ訂正 / C04 guard 許可 write / 受入確認行追加 |
| 2 | **capability B「目標設定/ 除外フィルタ」欠落**（ユーザー自作目標が北原ナレッジとして誤抽出→KB汚染） | HIGH | command:20/55/76 | C17 Phase2-extract / C19.description / C02.purpose |
| 3 | **`--all`/`--since` 脱落・`--dry-run` 発明**（C15 Rule F mode:full が孤立） | HIGH | detect.sh usage / get_source_type 7分類 | C02.inputs+purpose / C19.argument-hint / C17 に Rule F 接続 |
| 4 | info-collector/goal-reviewer の Bash/Glob 削除（最新合宿dir・最新目標自動検出が劣化） | MEDIUM | info-collector.md:51-54 / goal-reviewer.md:87-88 | C05.tools+Bash / C07.tools+Glob,Bash |
| 5 | registry.json 空シード（74ファイル処理済み台帳喪失→初回全件NEW誤検知） | MEDIUM | registry.json total_processed:74 | L3 を実台帳初期シードへ全6箇所一貫訂正（sync-log は空シード保持） |
| 6 | XLOCAL 表記統一ルール欠落 | MEDIUM | SKILL.md:20 | C16.output_contract |
| 7 | get_source_type 7分類 home不在 | MEDIUM | detect.sh:61-71 | C02.purpose に7分類明記 |
| 8 | 20件/バッチ上限欠落 | LOW | command:62-64 | C17 Phase1-detect |
| 9 | L1 entry数記述誤り（各5〜9→実155）・goal-spec 概数残渣 | LOW | router.json 集計155 | L1記述+derivation+goal-spec constraints[0] |
| +新 | guard 許可 write が C15 の plugin-dir 書込を封鎖しうる（policy_note 追加で露呈） | MEDIUM | — | C04.policy_note を vault-only スコープへ明記 |

### 独立再監査（proposer≠approver）の指摘で二次補正
- registry.json 修正が description 1箇所のみで build_target 等6箇所が「空seed」残存＝片手落ち → 全箇所一貫化で閉鎖。
- guard スコープが plugin-dir 書込を巻込み capability B 封鎖リスク → vault-only 明記で解消。

### 精度向上（第2の問いへの回答: harness-creator による uplift）
- **uplift**: validate .sh→py+tests≥80+golden-master 等価 / feedback-contract criteria-test / 全component ≥80フロア / C04 write-path-guard 新設（原本に無い破壊防御）/ schema.json hoist で A/B 対称参照。
- **リスク根源**: 「逐語移植でなく契約移植」の抽象化が周辺挙動（--all/source_type/目標設定除外/Daily更新）を取りこぼす主因。→ 上記で全て first-class 化して解消。

**最終**: HIGH以上（Daily.md/目標設定除外/--all）を含む全10件を計画へ忠実 first-class 化。12ゲート緑継続・独立再監査 APPROVE_WITH_NOTES→補正後クローズ。ただし plan は L3 契約ゆえ、実挙動（正規表現 embed 置換・mode:full リセット・実 registry 同梱）の逐語再現は **build 段階（run-skill-create/parent-skill-build）の残作業**。

## メタ観察（キャリブレーション）

- 対象 plan は改善前から機械12ゲート全緑。elegant-review の付加価値は「機械射程外の意味整合・provenance・数値ピン規律の対称性」に集中。
- 高価値 findings の**大半が生成器の語彙ギャップに根を持つ**（C-1/A-1）。plan instance の最小パッチで安全に閉じられるのは provenance(FIX-B)・doc 対称性(FIX-D)・SSOT 完全性(FIX-E)の3件のみ。残りは生成器 backlog / repo 横断規約 / 設計深化として透明化。
- gate 網羅外の残余リスク（requires_parent_scaffold 閉路検査・dual-surface 一致 lint・数値↔定義元 pin の対検査）を機械層へ昇格する backlog を KJ 法(SS11)が指摘。
