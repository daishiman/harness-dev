---
name: extract-blueprint
description: 対象URLからC01のローカルdraft生成を起動し、C02の独立verdict(ローカルdraftの独立品質評価PASS/FAIL)を同一draft_hashで発行する。FAIL時はruntime request budgetをリセットしないまま有界差し戻しする
kind: command
version: 0.1.0
owner: harness maintainers
since: 2026-07-11
argument-hint: "<url> [--crawl-mode single|full_site] [--resume]"
allowed-tools: Read, Bash, Skill
disable-model-invocation: false
entrypoint: run-extract-blueprint
---

# /extract-blueprint

`$ARGUMENTS` を対象 URL 1 件としてパースし、参考システムのブループリント抽出→独立品質評価を **順序保証つき**で起動する薄いラッパ。品質判定のロジックは持たず、C01 (`run-extract-blueprint`) と C02 (`assign-blueprint-fidelity-evaluator`) の起動順序を強制し、最終判定は C02 verdict の機械層へ委ねる (proposer≠approver をコマンド層でも二重化)。パス解決は `$CLAUDE_PLUGIN_ROOT` 起点。
Marketplace から install した場合の呼び出し名は通常 `/extract-system-blueprint:extract-blueprint`。

## 振る舞い

1. **入力パース**: `$ARGUMENTS` の先頭を対象 URL 1 件として取り出す。URL が無ければ argument-hint を表示して停止する。`--crawl-mode single|full_site` (既定 single) と `--resume` は C01 への passthrough として保持する。

2. **Step1 — ローカル draft 生成 (C01)**: `Skill(run-extract-blueprint, args="<url> [--crawl-mode ...] [--resume]")` を起動する。C08 hook の bootstrap は C01 の R1 冒頭 combined call (`mkdir -p .esb-authz && authz-classify` の単一 Bash 呼び) が正本 — command 層で単独 `mkdir` を先行させることは**禁止** (dir 発見で hook が即アクティブ化し、evidence の唯一の producer である C12 呼び自身が evidence 不在=fail-closed deny で遮断される bootstrap deadlock)。C01 は R1-fetch → R2-analyze → R3-document を回して章別 draft (md/json/5種Mermaid/画面別 layout/design-tokens/site coverage manifest/request ledger) を生成する。screenshot/annotated/overlay/computed-style は browser 不使用のため取得せず observation_gap として記録する。`doc-emit.py [--check-screens]` (screens が空なら check-screens はスキップ) + `mermaid-validate.py` の自己検証 exit0 後に `draft_hash = sha256(canonical)` を固定する。完了レポートが返す **draft ディレクトリ**と **draft_hash** を控える。draft_hash 固定前に C01 が失敗 (決定論チェック fail 等) したら停止する。

3. **Step2 — 独立 verdict (C02・ローカル draft の独立品質評価)**: `Skill(assign-blueprint-fidelity-evaluator, args="--draft-dir <Step1 の draft dir>")` を **独立 context (context:fork)** で起動する。C02 は共有決定論ゲート (`doc-emit.py [--check-screens]`=C11 / `mermaid-validate.py`=C10) の再実行 + 非共有 `recount-palette-orphans.py` (common-mode 破り) + R1-evaluate の意味判定 → `emit-verdict.py` で `draft_hash` に束縛した独立品質 verdict (PASS/FAIL) receipt を `${ESB_VERDICT_DIR:-.esb-verdict}/<draft_hash>.verdict.json` へ発行する。C01 自身の自己評価では品質を確定しない (proposer≠approver)。

4. **Step3 — 独立品質判定 (完結)**:
   - **verdict=PASS かつ draft_hash 一致**のとき、ローカル draft を独立品質評価 PASS として確定する (パイプライン完結)。
   - **verdict=FAIL / verdict receipt 不在 / draft_hash 不一致**なら **PASS としない**。runtime request budget を **リセットせず** (既消費分を引き継ぐ)、C02 の `findings[]` を差し戻し理由として提示して**有界に停止**する (bounded handback)。budget 非リセットの保証 scope は**同一 out-dir (同一 run-dir) 内**: 同一 run-dir で再抽出する限り既消費分を引き継ぎ初期化されない (別 out-dir は per-run 予算が新規に始まる)。瞬間負荷レバー (並列 1・最小間隔・Retry-After・停止条件) は out-dir 非依存で常に不変。

## 順序保証

```
[Step1] C01 → ローカル draft → doc-emit [--check-screens] + mermaid-validate 自己検証 (exit0) → draft_hash 固定
[Step2] C02 (context:fork) → draft_hash に束縛した独立品質 verdict (PASS/FAIL) を ${ESB_VERDICT_DIR:-.esb-verdict}/<draft_hash>.verdict.json へ発行
[Step3] verdict=PASS かつ draft_hash 一致 か? ── NO → budget 非リセットで有界差し戻し
                                              └ YES → ローカル draft を独立品質評価 PASS として確定 (完結)
```

- 本 command は起動順序の責任だけを持ち、抽出・評価の実装は C01/C02 が担う (薄いラッパ)。

## 引数

| 引数 | 説明 |
|---|---|
| `<url>` | 対象システムの公開 URL 1 件 (必須) |
| `--crawl-mode single\|full_site` | C01 への passthrough (既定 single)。full_site は per-run 有界 + multi-run resume で全 in-scope URL へ到達 |
| `--resume` | C01 への passthrough。前 run の site coverage manifest から継続する |

## 失敗時

- URL 未指定: argument-hint を表示して停止。
- C01 が draft_hash 固定前に失敗: 決定論チェック fail 等を提示し停止。
- C02 verdict=FAIL / receipt 不在 / draft_hash 不一致: PASS とせず、budget 非リセットで C02 findings を差し戻し理由として提示 (bounded handback)。

## 注意

- 本 command は薄いラッパ。忠実性の設計品質は C02 (独立評価器) が担う。command 単体では品質可否を判定しない。
- 認証必須領域への無断到達・実侵入・認可外スクレイピングをしない (C12 が allow した AuthzEvidence 範囲外は C08 が fail-closed 遮断)。参考/学習目的限定。
