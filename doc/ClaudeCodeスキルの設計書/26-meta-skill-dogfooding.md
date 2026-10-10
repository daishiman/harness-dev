# 26. メタSkillドッグフーディング

設計書（`doc/ClaudeCodeスキルの設計書/` の番号付き章。現在 41 本）自身を artifact とみなし、Skill と同じ考え方（生成役と評価役を分ける・基準で採点する）で検査する。目指すのは「Skill の作り方を書いた文書」と「Skill を作る Skill」と「採点する Skill」が同じ基準で評価される閉ループである。

ただし、閉ループのうち **設計書を `assign-skill-design-evaluator` で機械採点する経路は未実装（計画）** である。今動いているのは、独立レビューの結果を coverage 記録として残し、率が下がったら CI で止める経路だけである（§現行の手順）。

## なぜ必要か

- 設計書が基準を満たさなければ、それを参照して作られる Skill も満たさない (推移律)
- 設計書 = 人間向けの README 化が進むと冗長化し、`run-build-skill` が参照しづらくなる
- 09 の sycophancy: 書き手が自分の文書を採点しても甘くなる → 書き手とは別の評価役が必要

## 09 の Generator（生成役）/Evaluator（評価役） 分離を設計書群に適用

設計書を次のロールに割り当てる:

| ロール | 現行（実装済み） | 計画（未実装） |
|---|---|---|
| Generator（生成役） | 設計書の著者 (人間 or Claude) | 同左 |
| Artifact（成果物） | `doc/**/*.md`（外部参考資料を除く。集計範囲は `scripts/validate-harness-coverage.py` の `measure_docs`） | 同左 |
| Evaluator（評価役） | 著者とは別の独立レビュー Agent。正確さ・漏れ・整合・実行可能性を見て `eval-log/coverage/docs/<slug>.json` に記録する | `assign-skill-design-evaluator` を context: fork で起動 |
| Rubric（評価基準） | high / medium の指摘が 1 件でもあれば FAIL、score は 100 から減点（high -20 / medium -10 / low -2〜-4） | 設計書用の kind（または rubric プロファイル）を `ref-skill-design-rubric/references/rubric.json` に追加する。改正は 27章の governance 経由 |

### 現行の手順

1. 各設計書を 1 artifact として扱う。
2. 著者とは別の独立レビュー Agent が読み、パス・コマンド・数値を現物と照合する。
3. 結果を `eval-log/coverage/docs/<slug>.json` に記録する。`llm_eval` に `verdict`（PASS / FAIL）・`score`・`notes`（レビューした版の sha256 を含む）、ほかに `reviewed_by` を持つ。書き手や修正担当は記録を書かない。
4. `python3 scripts/validate-harness-coverage.py`（= `make harness-coverage`）が docs の PASS 率（llm_eval）を集計する。
5. `make harness-ratchet`（CI: `.github/workflows/harness-creator-kit-ci.yml`）が、PASS 率が `eval-log/harness-coverage-floor.json` の floor を下回ったら止める。

### 計画中の手順（未実装）

- `plugins/skill-governance-automation/scripts/doc-to-skill-adapter.py` は実在するが、出力は Skill 候補の brief JSON（`skill_name` / `description` / `trigger_conditions` / `artifact_path`）である。採点スクリプト `render-findings-score.py` は SKILL.md を前提にしており、設計書 md や brief JSON を渡すと FM・BD・NM 系がすべて欠落扱いになって score 0 になる。
- 閉ループを成り立たせるには、(a) 設計書用の kind か rubric プロファイルの追加、(b) adapter 出力を採点スクリプトへつなぐ経路、の 2 つが要る。どちらも未着手である。

## 再帰的 rubric チェック (設計書版)

rubric の中から、設計書にも適用可能なルールを抜粋（現行は独立レビューの観点として使う）:

| ルール | 設計書での意味 |
|---|---|
| DRY (01) | 同じ事を複数設計書で繰り返し書かない、リンクで一意化 |
| Less is More (08) | 正本リファレンスを除き、長文は補助ファイルへ分割 |
| Why（理由）-driven (08) | 各章冒頭に「なぜこの規約が必要か」 |
| 4条件PASS (01) | 矛盾なし / 漏れなし / 整合性あり / 依存関係整合を満たす |
| Gotchas（落とし穴） (08) | 設計書にも known-bad-pattern を含める |
| Progressive Disclosure（段階的開示） (07) | 詳細は `references/` 相当のサブ文書に逃がす |
| `max_skill_md_lines: 300` (24 rubric) | 生成対象 Skill は 300 行以内。通常設計書も 300 行以内を目標にする（`16` / `17` のような公式正本リファレンスは例外として長文を許容し、入口文書からリンクする）。現状は例外以外にも 300 行を超える章が複数あり、分割は残課題（`wc -l doc/ClaudeCodeスキルの設計書/*.md` で確かめる） |
| `trigger_count_min: 2` / `trigger_count_max: 3` (24 rubric) | 設計書内で例示する description 雛形は発動条件 2 個で書く（rubric は 2〜3 個を許すが、機械ゲートは 2 個ちょうどを強制する。24章） |
| `description_no_action_detail: true` (24 rubric) | 設計書内 description 例から動作詳細（採点する／JSON で返す／段数）を排除 |

### 自己採点の追加観点（Phase3-H 由来）

設計書を見直すとき（現行は独立レビュー、計画では evaluator）、次を確かめる:

- 設計書本文行数 ≤ 300 (`BD-003` 相当を設計書自身にも適用。上記の例外と残課題に注意)
- 設計書内に登場する `description:` 例示が `trigger_count_min/max` を満たす (`FM-003`)
- 設計書内に登場する `description:` 例示に動作詳細トークンが混入していない (`FM-004`)
- 設計書内 description 例示が動詞 / 手順ベース (`FM-005`)

設計書自身がこれらを満たさない場合、`run-build-skill` が参照したときに「設計書の悪い例をそのまま新 Skill に持ち込む」事故が起きる。設計書 → Skill の推移律で品質が伝播するため、設計書側を先に守る必要がある。

## 自己進化フィードバック

```text
docs (artifact)
   │
   ▼
独立レビュー（計画: assign-skill-design-evaluator を fork で起動）
   │
   ▼
findings: "10 と 17 で SubAgent 説明が重複 (DRY違反)"
   │
   ▼
fix: 重複箇所を 10 に集約、17 からリンク
   │
   ▼
re-review → 新しい記録で PASS を確認
```

同じ findings が `run-build-skill` 生成物でも頻出するなら、`templates/` か rubric（27章の governance 経由）を更新し、過去の Skill にも適用 (regression check)。

## dogfooding と `skill-only` モードの関係（恒久例外）

[36-plugin-package-harness-contract.md](./36-plugin-package-harness-contract.md) §`skill-only` では、`package_mode: skill-only` を「legacy / dev-only / migration exception」と定義し、新規量産では選択しない方針を取る。一方で本章の dogfooding ループ（設計書自身を artifact とみなして検査する運用）は、配布対象ではなく設計書の自己検査であり、`/plugin install` UX を保証する必要がない。したがって dogfooding 用途に限り `skill-only` モードを**恒久例外として許容**する。これは 36章で列挙された3例外（legacy / dev-only / migration）のうち「dev-only（局所検証）」に該当し、設計書側に明示しておくことで「dogfooding が package completeness check に通らない」ことを fail として誤検知するのを防ぐ。36章の表では `skill-only` は PKG-001〜009 が任意適用、PKG-010 以降が適用対象外である。dogfooding artifact は plugin package を構成しないため、任意適用の PKG-001〜009 も適用せず、`completeness check: not applicable (dogfooding)` を完了レポートに残す。逆方向のリンクとして、36章 §`skill-only` 列挙箇所からは本章を「dev-only の恒久例外運用」として参照する。

## 運用ルール

- 設計書を変更したら、独立レビューをやり直して coverage 記録を新しい版の sha256 で取り直す。記録の hash だけを書き換えない。
- rubric を更新したら全設計書を見直し、回帰を検知する。
- rubric 変更は生成物修正と同じ PR に混ぜない。別承認者と `rubric_hash` 記録で Goodhart（評価基準を都合よく歪める罠）を防ぐ。
- マージを止めるのは、設計書 1 本ごとの FAIL ではなく docs の PASS 率が floor を下回ったとき（`make harness-ratchet`）である。FAIL の設計書は記録に残り、率を下げる。floor は意図した変更のときだけ `--update-floor` で動かし、評価の書き換えで緑にしない。
- 1 本ごとに「score < threshold ならマージ禁止」とする gate と、`TaskCompleted` Hook での自動再採点は未実装（計画）。

## 期待効果

- 設計書品質と Skill 品質を、生成役と評価役を分けた同じ考え方で担保する
- 「書いただけで動かない」設計書を、現物との照合で見つける
- メタSkill 自身も同じループで改善され続ける (自己進化)
