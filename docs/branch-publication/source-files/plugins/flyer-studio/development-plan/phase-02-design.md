---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C02, C05, C12]
applicability:
  applicable: true
  reason: チラシ制作の再現性と導入品質のため適用
---

# P02 — design

## 目的
正本データ・構図・描画・独立評価を分離する。

## 背景
制作担当と独立検査者の受け渡しが曖昧だと、画像更新前の所見や一覧だけのレビューが納品へ混入する。C02は検査呼出と証拠集約に責務を限定する。1.2.0では提案評価C05が同じ形で加わり、全skillが同じ実行入口C12を使う。呼出と入口の境界を設計で固定しないと、評価の書込み主体や入口が二重化する。また1.2.0はFIXを毎回分析からやり直すため、文字欠けのような決定論の失敗でも分析と提案評価の2担当が起動して費用が膨らみ、完了条件が「適用基準の全PASS」なので好みの所見でも周回が進む。戻り先をFIXの種類で振り分け、完了を本質成果で判定する(C15/C16)。プラグイン自体を改善するたびに規則と担当が増える傾向も、入口C12のessence-checkで受け付け時に止める(C17)。

## 前提条件
P01のC03/C07入力・返却契約とreferences/essence.jsonの項目契約、component-inventory.jsonのC02→C03・C05→C07依存、plugin-composition.yamlのcapabilities/dependencies/revisionBudgetを使用する。

## ドメイン知識
review-templateは未承認の雛形である。制作データのfingerprintと各PNGのSHAを一致させ、構図多様性のメタデータと実見判定を区別する。analysis-sealは構造と元SHAの確定であり提案の承認ではない。構図・文字・配色の知見はdesign-knowledge-index.jsonのlensとして各担当が読み、agentとして相談しない。実見判定の再利用は案単位の判定に限り、画像SHA・brief digest・規範digest(review-contract.md・prompts/visual-review.md・その判定が読んだlens項目・essence.jsonのE*の各SHA)の3つが一致する場合だけC02が機械的に決める(1つでも変われば転用せず、C03の裁量にしない)。構図差・白系黒系各1案・全案の一貫性のように案の集合に掛かる判定は再利用しない。

## 成果物
C02: skills/assign-flyer-review/SKILL.md・workflow-manifest.json。C05: skills/assign-flyer-analysis-review/SKILL.md・workflow-manifest.json。C12: scripts/flyer.pyを4skill共通の入口とする設計、essence-checkサブコマンドの検査項目表と基準ファイル(references/essence-baseline.json)・承認記録(references/essence-approvals.jsonl)の形、plugin-composition.yamlのimplementation・revisionBudget・FIX戻り先の更新。envelope-draft/plugin.jsonとhandoffはplugin-level設計物。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] C02がverify結果と全PNG一覧をC03へ渡し、各案のSHA・具体所見・必須修正・判定をvisual-review.jsonへ集約する契約がある。
- [ ] C02が画像未実見/古いSHA/未解消修正を拒否し、C8/C9の検査結果とC03の主観所見を混同しない。
- [ ] C05がanalysis-sealの済んだanalysis.jsonと元画像をC07へ渡し、返った判定をanalysis-review.jsonへ書き、FIXはrun-analyze-flyerへ戻す契約がある。C05とC02はcontext forkで起動する。
- [ ] C12としてscripts/flyer.pyを4skill共通の実行入口にし、plugin-composition.yamlのimplementation.shared_script_componentをtrueへ改め、Node未導入時はexit 2で案内する設計がある。
- [ ] 旧agents/flyer-reviewer.mdと共有専門役3本をagentsディレクトリから外し、前者はreview-contract.mdへ、後者はdesign-knowledge-index.jsonのlensへ吸収する。plugin-composition.yamlのcapabilitiesとconsults辺、参照元(prompts/visual-review.md・references/*.json/*.md・scripts/package.pyの必須一覧)の張替え一覧がある。
- [ ] revisionBudget(工程全体maxCycles 3・提案再評価でリセットしない・同一画像と所見の反復を進捗にしない・上限でINCOMPLETE)を4skillの戻り先と1対1で対応付けた表があり、stopWhenを「該当する本質成果が全てPASS」へ改め、好みだけの所見を周回に数えない(C14/C15)。
- [ ] C02のFIXが元要件ID・本質成果ID・種類を持ち、決定論検査の失敗(QR読取・安全域・文字欠け・中心軸・外縁)はC01の制作へ直接、目的・事実・公開範囲のずれはrun-analyze-flyerへ戻す振分表がある。直接戻しの修正でbriefの必須事実・公開範囲が変わればC03が拒否して分析へ戻し、失敗したE*基準の観測が無い、または観測の画像SHAが現行の案と・引用した基準文言が現行E*と一致しない本質区分の所見はC02が好みへ回してFIXにしない(C15)。
- [ ] C02が案単位の実見判定のうち3 digestが一致したものだけを再利用し、変わった案と集合に掛かる判定をC03へ渡す。LLM担当の起動数は宣言値でなく呼出記録から数え、essence.jsonの予算と突き合わせる。担当への入力束はflyer.pyだけが発行して発行時に呼出記録へ追記し、C02は記録に無い入力束IDの判定を受け付けないので、追記漏れは過少申告でなく判定の欠落として表に出る。再利用した判定は元の入力束IDを引き継ぎ、essence-checkは再利用元の判定が呼出記録に残っていることを確かめる(C16)。
- [ ] C12にessence-check(Python標準ライブラリ・読取専用)を置く設計がある。--project指定時は原依頼hashの不変・本質区分の観測の有無・FIX振分・呼出記録の起動数と予算を、指定なしではplugin-composition.yamlの各capabilityと規則のservesが現行essence.jsonのE*に、evidenceが同梱の実事例(production-history・hyogo-v13-feedback)のpathかIDに解決すること、担当数・LLM評価予算・E*の数が基準を超えないこと、golden事例と試験の対応を検査する(C17)。
- [ ] 比較の基準は直前リリースでscripts/package.pyが書き出すreferences/essence-baseline.json(担当数・LLM評価予算・E*とgoldenのID集合・元のessence.json digest・版)とし、改善の変更では書き換えない。基準の版が、CHANGELOGのうちplugin.jsonの現在版以下で最新のリリース版と異なる(基準が古い。版を上げる前の作業中の新版の項目は数えない)、または基準を超えるとessence-checkは常に失敗し、例外は対象digestと利用者の発言原文を持つ承認記録が一致する場合に限る。リリースではpackage.pyが版を上げる前にessence-checkを呼び、通過した時だけ新版の基準を書き出し、その後に版を上げる。基準が無い状態はplugin.jsonの現在版がessence.jsonのbaseline_introduced_in(1.3.0想定)より前の初期化中だけ許し、初期化中はessence.jsonのdigestに一致する承認記録(build時に利用者が確定した値)を必須として予算と担当数をessence.jsonの値と比べ、基準比較以外の検査は通常どおり行う。導入版より後で基準が無ければ失敗する(C17)。

### 受入例
- 満たす例: 変更後PNGをC03が再実見し、そのSHAでreviewを更新してfinalizeへ渡す。
- 満たさない例: 前版のreviewをコピー、制作担当だけの判定を独立レビューと表示する。

### 事前解決済み判断
独立担当を呼べない環境では制約を明記し、独立レビュー済みと名乗らない。Node描画backend(scripts/*.cjs)は4skillが共有するためC01付随物から共有script C12の背後へ移す(2skill以上が使うscriptはplugin-root)。入口をPython標準ライブラリのflyer.pyにするのはplanner規約とNode未導入時の案内のため、backendをNodeのまま残すのはChromium描画をPython標準ライブラリで代替できないため。新規の.js/.shは追加しない。flyer-reviewerと専門役3本を外すのは、agentsディレクトリのfrontmatter付きファイルは独立agentとして登録され、coordinatorの契約を通らずに起動できてしまうため。決定論の失敗を制作へ直接戻しても、新しい画像は必ずC03の独立評価を通るので、制作者≠画像評価者の分離は崩れない。essence-checkを描画backendでなくPython側に置くのは、JSONの照合だけで済みNodeとChromiumを要らない検査にするため。基準をessence.jsonと別ファイルにしリリース時だけ更新するのは、変更そのものが比較の基準を書き換える抜け道を塞ぐため。承認記録はローカルファイルなので偽装を機械で完全には防げず、P10の独立判定が原文を利用者との会話と照合する。初期化を導入版までに限るので、基準を消しても初期化へは戻れず、baseline_introduced_inを書き換えればessence.jsonのdigestが承認記録と合わなくなって止まる。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
