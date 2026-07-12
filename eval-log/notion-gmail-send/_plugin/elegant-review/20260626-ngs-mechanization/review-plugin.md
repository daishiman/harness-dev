# elegant-review レポート: notion-gmail-send 表示問題の修正検証 + 再発防止の仕組み化

- run-id: `20260626-ngs-mechanization`
- 問い: (1) マーケットプレイス非表示の修正は正しいか (2) skill-creator で量産しても二度と登録漏れが起きない仕組みか
- 結果: **4 条件全 PASS / status: complete / iteration 1 で収束**（独立 approver APPROVE）

## 結論サマリ
- **問1（修正の正しさ）= 正しい（ただし単体では不完全だった）**。ユーザーの修正（marketplace.json/bundles.json への登録 + MK-001/002/003 検出 lint + CI3面 hard 配線）は検出層として正しく、表示問題を解消する。検出器は**実体ディレクトリ起点**で巡回するため「漏れが漏れを隠す自己強化ループ」を構造的に断ち切っている。**だが2つの不完全さがあった**: (a) 既存テスト11件が4引数化に追従せず壊れて CI の pytest を落とす、(b) marketplace 登録により notion-gmail-send が skill-lint 被覆の母集合に入り `lint-plugin-lint-coverage.py` が新たに FAIL（配線漏れ露出）。
- **問2（再発防止）= 不十分だった → 本レビューで予防層を追加し充足**。生成層 skill-creator には登録ゲートの骨格（Gate2.5 / step3.5 bundle-register）が在るのに、plugin.json 形式では空 return / command=null で**機能していなかった**（配線の箱だけで中身が空）。検出（CI で落として手で直す）のみで、生成時の予防が無かった。

## 真因（3 エージェント独立検証で一致）
plugin 公開の SSOT が3集合（実体ディレクトリ / marketplace.json / bundles.json）に分かれているのに、**生成のたびに全集合へ登録を実行する機械機構が生成層に存在しない**。`build-manifest-registration-plan.py` は legacy manifest.json 専用で plugin.json は早期 return、`workflow-manifest step3.5` は実行機構 null、`build-steps Phase G` は alias/commit のみ。結果として「作る→手で登録し忘れる→CI で初めて落ちる」failure-then-detect が温存されていた。

## 30 思考法カバレッジ
- 論理構造系 10 / メタ発想系 9 / システム戦略系 11 = **計 30、skip 0**
- レバレッジポイント（system-strategic 特定）: 検出と予防を同一 SSOT スクリプトに同居させる。検出ロジック（MK/BD）は既に `validate-plugin-completeness.py` にあるので、ここに `--fix` を足すのが最小=最大。

## 改善内容（ユーザー選択: 二層防御＝予防+検出）
| finding | 修正 | ファイル |
|---|---|---|
| F-CORE (critical/dependency_break) | `--fix`（append-only 自動登録 + 書込後自己再検証 + 冪等）を検出と同居で追加 | scripts/validate-plugin-completeness.py |
| F-CORE 配線 | 生成フローに `--fix` を配線（step3.5 command / Phase G 手順 / 完了チェックリスト / 鍵ルール6） | run-skill-create/workflow-manifest.json, run-build-skill/references/build-steps.md, run-skill-create/SKILL.md |
| F-CORE 責務 | legacy registration-plan の plugin.json 早期 return に責務委譲コメント明記 | build-manifest-registration-plan.py |
| F-MK003 (inconsistency) | MK-003 を source basename 独立検査へ修正（行88-89 との重複解消） | scripts/validate-plugin-completeness.py |
| stale-tests (critical) | ユーザー修正で壊れた既存テスト11件を4引数化で修復 + `--fix`/MK の新規テスト追加（36 passed） | tests/scripts/test_root__validate-plugin-completeness.py |
| lint-coverage-wiring | marketplace 登録で露出した skill-lint 3種未配線を notion-gmail-send に配線 | Makefile |
| F-COVERAGE (smell) | marketplace 起点巡回の盲点が MK-001 で塞がれる依存を docstring 明記 | scripts/lint-plugin-lint-coverage.py |

## 4 条件判定（独立 approver による実機再現）
- C1 矛盾なし: PASS（SKILL.md/build-steps の記述と `--fix` 実挙動が一致。「--apply 済み」の実機能しない記述は新形式 plugin 経路に残っていない）
- C2 漏れなし: PASS（生成フロー step3.5 に `--fix` 配線・予防成立。bundle_targets を読み marketplace+bundles 両方 append）
- C3 整合性あり: PASS（legacy manifest.json=registration-plan / plugin.json=validate-completeness --fix の責務分離が一貫。append-only の2ファイル非対称を docstring で精緻化）
- C4 依存関係整合: PASS（step3.5 command パス規約・fatal_exit_codes=[1] が他 step と一貫。検出層↔予防層の依存健全）

## 検証（二段確認）
- 中央 pytest: **5720 passed / 4 skipped / 0 failed**
- 検出モード exit 0（14 plugins）/ `--fix` no-op exit 0（全登録済み）
- 退行実証: notion-gmail-send 除去 → 検出 exit 1（MK-001/BD-001 発火）→ `--fix` → 再登録 → 検出 exit 0
- 独立 approver（proposer≠approver）: byte 単位 append-only 実証 / fail-closed 2ケース（bundle_targets 不在・plugin.json 欠落とも exit 1）/ 冪等性 / pytest 36 passed を**自分で再現**して APPROVE

## 残リスク / deferred
- **F-SSOT-ROOT（本命の根治・ALT-D）**: marketplace/bundles を実体+plugin.json から全自動生成する派生物へ格下げし手編集禁止。3→1 SSOT 化で登録漏れが構造的に発生不能になるが、全 plugin の description/tags を plugin.json へ一元化する大規模移行のため将来課題。
- **plugin.json への category/tags 追記運用**: `--fix` のデフォルト（productivity/[]）を避けるため、新 plugin の plugin.json に category/tags を入れる運用を Phase G 手順で促す（既に言及）。
- **PKG harness への登録検査 PKG ID 新設**: PKG-016 は governance 未確定のため ID 化は避け、SKILL.md チェックリスト + Makefile/CI 配線で担保。
- リモート公開（public repo 一覧）への反映は push が必要（現状未コミット）。
