# Phase 3 改善報告 — 移管計画.md

- worker: 移管計画.md 担当(elegant-review Phase 3)
- 変更ファイル: `doc/マルチ企業展開/移管計画.md` のみ(他ファイル編集なし)
- 検証: git archive コマンド dry-run OK(xl-skills HEAD で全 path 実在)/ TODO(human) 0 件 / コードフェンス 7 組整合 / Step 番号体系 1→7(6.5 挿入)維持

## 適用修正一覧

| # | 箇所 | 内容 | 対応 finding |
|---|---|---|---|
| 1 | §3 表 | core 出力を §6 Step 2 と同一の 9 path に更新し「唯一の定義」と宣言。Step 2 側は「§3 と同一定義。増減時は §3 を先に更新」と参照に変更 | paradigm 7 (mece) C3 low「core 出力の path 列挙が節間で不一致」 |
| 2 | §3 表 + §6 Step 2 | repo-root 統治ファイル行(CONVENTIONS.md / Makefile / config-version-lock.json / .pre-commit-config.yaml)を §3 に追加し、git archive 対象に 4 ファイルを明示追加。依存先(構築手順 Phase 0 / Phase 2-5)を注記。xl-skills HEAD で 4 ファイルとも git 管理を実測確認済み | paradigm 9 (process) C4 medium、paradigm 17 (if) C4 medium「Makefile 到達経路欠落で Phase 2-5 実行不能」 |
| 3 | §6 Step 5 | 「**順序の正**: tenant へコピー(Step 5)→ 一致検証 → core から除去(Step 6)」の原子順序を宣言。構築手順 Phase 2/3 も同一 PR 内でこの順序に従う旨を明記(全 worker 共通の整合決定に準拠。構築手順側にも同宣言が入る) | paradigm 9 (process) C4 medium、paradigm 20 (causal) C1 medium「Step 5→6 と Phase 2→3 の順序逆転」 |
| 4 | §6 Step 6.5 新設 + Step 2 | Step 6.5「切替直前の差分再同期」を追加: `git -C xl-skills diff <基準commit>..HEAD --name-status` をレビューし取り込み/破棄を判定。Step 2 に `git rev-parse HEAD > /tmp/xl-skills.import-base.txt` で基準 commit を記録する規定を追加 | paradigm 21 (causal-loop) C2 **high**「二重正本の発散・サイレントロールバック」 |
| 5 | §6 Step 7 | symlink を既定と確定。read-only mirror は「バックアップツール互換など symlink 起因の問題が実測された場合に限る代替」と 1 行で決着(構築手順 Phase 7 と同一の決定、全 worker 共通の整合決定に準拠) | paradigm 22 (trade-on) C1 low「symlink/mirror 両論併記のまま」 |
| 6 | §7 末尾 | 「Phase 4 で作る」を「tenant-init/build/doctor は構築手順 Phase 4、lint-tenant-isolation は構築手順 Phase 2 で作る」に具体化 | paradigm 30 (kj) C4 low「番号体系の対応曖昧・Phase 4 表記が lint 新設 Phase と矛盾」 |
| 7 | §4.5 冒頭 | 実測スナップショットに「計測日: 2026-07-06。実行時に本節末尾の再現コマンドで再計測する」を注記。計測値(plugin 7 本欠落・skill-intake 0.1.1 vs 0.1.3)は本日再実測し現時点でも正確なことを確認 | 陳腐化対策(team-lead 指示 7。README 側 C2 low「計測日なし」と同型) |
| 8 | §9 冒頭 | 「安全原則はこの節を正本とする。他文書の同種記述は本節の要約であり、変更時は本節を先に更新する」を 1 行追加(最小限。再編なし) | paradigm 30 (kj) C3 low「同一情報の島が 3-4 文書に重複」 |

## skip と理由

| 項目 | 理由 |
|---|---|
| variable_abstraction の `~/dev/dev/xlocal/xl-skills` 直書き | 本文書は単一供給元を対象とする実行 Runbook で、コマンドの copy-paste 実行可能性が要件。doc/ は lint-tenant-isolation の allowlist 対象(構築手順 §2-4)であり、テンプレート変数化は再現コマンドを壊す。最小パッチ原則により見送り(README 側の抽象化は該当 worker の裁量) |
| paradigm 20 (causal) C4 low「構築手順 Phase 1 に scripts/ 取込を明記」 | finding 自身が「移管計画 §6 Step 2 の git archive に scripts が含まれることで暗黙に解決」と認定。修正は構築手順側の担当 |
| 移管計画.md §6 Step 3 の clean 範囲 | §4.5 の保護規定(doc/ を含まない scope 維持)が引き続き成立するため変更不要。Step 2 に追加した repo-root 4 ファイルは tar 展開で上書きされるため clean 対象への追加は不要 |

## 検証コマンドと結果

```
cd ~/dev/dev/xlocal/xl-skills && git archive --format=tar HEAD <9 path + 統治4ファイル> > /dev/null  # exit 0
grep -c 'TODO(human)' 移管計画.md   # 0
python3 フェンス整合 + Step 順序検査  # fences balanced 7 blocks / Step 1..6, 6.5, 7
comm -13 <(ls harness/plugins) <(ls xl-skills/plugins)  # 7 本欠落を再実測(§4.5 記述と一致)
```

## 残リスク

- 構築手順.md 側の worker が「順序の正」宣言(Phase 2 冒頭)と Phase 7 symlink 既定の同一表現を入れないと、文書間整合が片側だけになる(team-lead の共通決定で担保予定)。
- 計測日 2026-07-06 のスナップショットは実行日までに再び陳腐化しうるが、再計測規定を明記済みのため許容。

convergence_status: converged(担当ファイル範囲内の findings は全消化、high severity 1 件対応済み)
