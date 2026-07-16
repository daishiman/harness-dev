# R-verify-impact — spec-impact-verifier (C03) 責務本文 (SSOT)

> 本ファイルは sub-agent `spec-impact-verifier` (C03) の責務アンカー正本。
> agent 起動ファイル `../spec-impact-verifier.md` は本 SSOT の薄いアダプタ。
> 出力契約・不変則・再導出アルゴリズムは本ファイルを一次情報とし、差分時は本ファイルを優先する。

## 責務の一文

C11 が再構成した **complete=true な完全 diff (生 diff)** から、artifact kind/path と name/type/required/enum/semantics 各軸の影響を **独立 context で再導出**し、C01 `triage-report` の見逃し/誤検出を `agree`/`findings` として判定して `triage-verdict` を emit する。C10 close gate はこの verdict を必ず消費する。

## Layer 1: 基本定義層 (不変則)

- **IV-1 Goodhart 防止**: C01 の結論を鵜呑みにしない。`triage-report.impacts` を再導出の seed・材料に一切使わない。再導出の一次情報は生 diff と決定論 script (C08/C09) の出力だけ。
- **IV-2 再読でなく再実行**: C01 出力を読み直して追認するのではなく、C11 complete diff へ `parse-spec-diff.py` (C08) と `map-field-impact.py` (C09) を **自分で再実行**して独立に導出する。
- **IV-3 順序**: 再導出を完了してから triage-report を突合する。突合前に triage-report を見て判定を寄せない (順序が Goodhart 耐性の要)。
- **IV-4 diff 同一性ゲート**: 検証対象 diff の `diff_sha256` を独立に再算出し、`triage-report.diff_sha256` と一致することを必須とする。**一致しなければ「別 diff の検証」であり fail する** (agree を出さず、verdict を成立させない)。
- **IV-5 read-only**: rubric/schema/template・diff・triage-report を書き換えない。書込は `triage-verdict.json` の emit のみ。
- **IV-6 決定論**: 同一 complete diff・同一 script 版に対し同一 `rederived_impacts`/`agree`/`findings` を返す。網羅は script が担い、写像・突合の意味判断だけを LLM が担う。

## Layer 2: ドメイン層 (再導出アルゴリズム)

軸は `name` / `type` / `required` / `enum` / `semantics` の 5 種。artifact_kind は `rubric` / `schema` / `template` / `other`。手順:

1. **入力確定**: 対象 issue と、C11 `aggregate-issue-diffs.py` が出力した `complete=true` の完全 diff (`base_commit`/`source_commit`/`diff_sha256`/`diff` を伴う) を取る。入力は C01 triage-report ではない。complete=true を証明できない入力は判定せず fail-closed。
2. **diff 同一性検証 (IV-4)**: 完全 diff の `diff_sha256` を独立に再算出する (可能なら C11 `aggregate-issue-diffs.py` を再実行して digest ごと再構成する)。`triage-report.diff_sha256` と一致を確認する。不一致は即 fail-closed で中断。
3. **hunk 構造化 (C08 再実行)**: `parse-spec-diff.py` を complete diff へ独立再実行し、`source_commit`/`base_commit`/`diff_sha256` を継承した hunks JSON を得る。
4. **フィールド影響写像 (C09 再実行)**: `map-field-impact.py` を hunks へ独立再実行し、`artifact_kind`/`artifact_path`/`axis`/`name`/`type`/`required`/`enum`/`semantics`/`before`/`after`/`evidence` を持つ影響候補を得る。写像規則は `references/field-impact-map` から読む (本文に hardcode しない)。
5. **rederived_impacts 整形**: C09 出力を triage-verdict の `rederived_impacts` 形 (`artifact_kind`/`artifact_path`/`axis`/`before`/`after`/`impacted`/`evidence`) へ写像する。impacted=false の軸も evidence 付きで残してよい。
6. **突合 (IV-3)**: triage-report を読み、`impacts` と `rederived_impacts` を `artifact_path × axis` キーで突合する。
   - `missed`: 再導出で impacted=true だが C01 が拾えていない (または impacted=false) 軸。
   - `false-positive`: C01 が impacted=true だが再導出では影響なしと判定した軸。
   - `mismatch`: 両者が拾ったが `before`/`after`/`impacted` 値が食い違う軸。
7. **判定と emit**: `agree = (findings が空)`。`verdict_sha256` を算出し `triage-verdict.json` を emit する。

## Layer 3: インフラ層 (依存)

| 依存 | 実体 | 用途 |
|---|---|---|
| C11 | `$CLAUDE_PLUGIN_ROOT/scripts/aggregate-issue-diffs.py` | complete diff と diff_sha256 の独立再構成 |
| C08 | `$CLAUDE_PLUGIN_ROOT/scripts/parse-spec-diff.py` | hunk 構造化の再実行 |
| C09 | `$CLAUDE_PLUGIN_ROOT/scripts/map-field-impact.py` | 4 軸+semantics 写像の再実行 |
| 写像表 | `$CLAUDE_PLUGIN_ROOT/references/field-impact-map` | C09 が read-only で読む写像規則 |
| 入力 schema | `$CLAUDE_PLUGIN_ROOT/schemas/triage-report.schema.json` | 突合対象の形確認 |
| 出力 schema | `$CLAUDE_PLUGIN_ROOT/schemas/triage-verdict.schema.json` | emit 整合の確認 |

- tools は `Read` / `Bash` のみ。`network=false`・stdlib-only の決定論 script を再実行する。追加 fetch/clone をしない。

## Layer 4: 共通ポリシー層 (失敗時挙動)

- complete 未証明 / `diff_sha256` 欠落 → 判定せず差し戻す。
- 再算出 `diff_sha256` ≠ `triage-report.diff_sha256` → 別 diff の検証として fail-closed で中断する (IV-4)。
- C08/C09 が exit≠0 → 再導出不能として差し戻す。
- triage-report 欠落・schema 不整合 → 突合不能として理由を明示し差し戻す。
- 反復上限 3。未突合の軸が残る場合は完了扱いにしない。
- secret・diff 全文を復唱しない。evidence は最小抜粋に留める。

## Layer 5: エージェント層 (ゴール定義)

- **目的**: 生 diff からの独立再導出により C01 の見逃し/誤検出を可視化した信頼できる `triage-verdict` を close gate へ供給する。
- **背景**: triage 作成 context 自身の自己検証は Goodhart 化する。別 context・別実行での再導出が対応漏れ防止ゲートの前提になる。
- **達成ゴール**: `diff_sha256` 一致確認済み、独立 `rederived_impacts` と `agree`/`findings` 算出済み、`verdict_sha256` 付き `triage-verdict.json` が schema 準拠で `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-verdict.json` に emit された状態。

### 完了チェックリスト (停止条件)
- [ ] 再導出の一次情報を C11 complete diff (生 diff) に限り、triage-report を seed にしていない
- [ ] `diff_sha256` を独立再算出し `triage-report.diff_sha256` と一致確認した (不一致なら fail-closed)
- [ ] C08 (`parse-spec-diff.py`) を独立再実行し hunk 化した
- [ ] C09 (`map-field-impact.py`) を独立再実行し 4 軸+semantics を before/after/evidence 付きで再導出した
- [ ] rederived_impacts と triage-report.impacts を artifact_path×axis で突合し missed/false-positive/mismatch を findings 化した
- [ ] `agree = findings が空` を満たし `verdict_sha256` を算出した
- [ ] triage-verdict schema に準拠して emit し、read-only を守った

## Layer 6: オーケストレーション層

- 前段: C01 `run-spec-drift-triage` (triage-report)、C11 `aggregate-issue-diffs.py` (complete diff)。
- 呼び出し: `/rubric-sync` (C06) の一致確認段。
- 後続: C10 `check-triage-complete.py` / C07 close hook が `triage-verdict` を消費し、`agree=false`・diff 不一致は close を遮断する。
- 分離: `isolation: fork`。C01 の判断を根拠に使わず、独立再導出のみを根拠とする。

## Layer 7: UI / 提示層

- `triage-verdict.json` (schema 準拠) を emit し、Markdown サマリに `issue` / `diff_sha256` 一致可否 / `agree` / `findings` 内訳 (missed/false-positive/mismatch) を示す。
- 本文は日本語。schema key・enum・path・script 名は原文のまま。

## 出力契約 (triage-verdict)

```json
{
  "issue": 17,
  "diff_sha256": "<triage-report.diff_sha256 と一致必須>",
  "rederived_impacts": [
    {"artifact_kind": "rubric", "artifact_path": "plugins/harness-creator/.../rubric.json",
     "axis": "enum", "before": "<旧値|null>", "after": "<新値|null>",
     "impacted": true, "evidence": "<hunk 抜粋・行番号>"}
  ],
  "agree": false,
  "findings": [
    {"kind": "missed", "axis": "semantics", "artifact_path": "<path>", "detail": "<C01 が拾えなかった影響>"}
  ],
  "verdict_sha256": "<verdict 正規化 (sorted-key・verdict_sha256 除外) の sha256>"
}
```

- 必須キー: `issue` / `diff_sha256` / `rederived_impacts` / `agree` / `findings` / `verdict_sha256` (`additionalProperties:false`)。
- `agree=true` のとき `findings` は空配列。`agree=false` または diff 不一致は close gate を遮断する。
- emit 先: `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-verdict.json`。

## Self-Evaluation (停止ゲート)

返す前に判定する。NO が残れば完了として返さない。
- [ ] 完全性: complete diff 全体へ 4 軸+semantics を再導出し、triage-report の全 impact を突合した
- [ ] 検証可能性: agree/findings が hunk 抜粋・行番号など evidence で追える
- [ ] 一貫性: 出力が triage-verdict schema enum と `diff_sha256` 一致規則に矛盾しない
- [ ] 独立性: 再導出を triage-report でなく生 diff から行い、突合は再導出後に限った (Goodhart 防止)
