# 忠実性評価ルブリック (assign-blueprint-fidelity-evaluator)

> C01 draft を独立 context で採点する観点集。各観点は完了チェックリスト CL-1..CL-10 と 1:1 対応し、
> finding の `criterion` に載せる。判定は改変せず read-only。共有ゲート (C10/C11) と非共有再計数を先に
> 通し、意味判定をその後に行う。verdict の PASS/FAIL 最終確定は `emit-verdict.py` の決定論規則が担う。

## severity 規約

- **high**: 三値の混同 / レンズ主張の fact 混入 / ペルソナ偽装 fact / 鍵画面 gap / palette 孤児>0 /
  top-level 必須欠落 / 未回答質問>0 / 共有ゲート fail / 非共有再計数の不一致。**1 件でも verdict=FAIL**。
- **medium**: 被覆の部分欠落が理由付き gap だが粒度が薄い / confidence rationale が形式的 / observed_scope 未明示。
- **low**: 表記ゆれ / 正準表現の軽微逸脱 (gamut 注記漏れ等)。

## CL-1 再構築十分性 (top-level schema + 最小スカフォールド逆テスト)

- top-level が `system-blueprint.schema.json` 準拠で必須項目 (screens/design_tokens/tech_stack/essence 等) を欠かない。
- 生成 blueprint から最小スカフォールド骨子を試導出し、必須フィールド欠落 0・AI 追加質問 0 で着手できるか。
- 重要 fact 欠測 0。欠測があれば high。`reconstruction` へ top_level_missing / open_questions / scaffold_derivable を記録。

## CL-2 visual formation 全カテゴリ + coverage manifest

- 取得は WebFetch + C09 静的 snapshot (常時 baseline) + 任意の browser-render (C15 headless Chrome) の rendered
  enhancement の両方併用。静的 CSS/HTML から得られる identity/geometry/paint
  (caret/accent/selection/scrollbar/text-decoration 色・色値の正準表現)/typography (font provider/src)/media/effects/
  pseudo-elements/state (cursor)/motion/responsive/a11y/tokens を、取得された範囲で網羅 (computed/rendered カテゴリは
  browser-render 取得時のみ fact、ブラウザ不在時は observation_gap で妥当)。
- 画面→region→主要 element の coverage manifest が揃う。screenshot・番号付き注釈 overlay・computed layout は browser 依存の
  ため **取得された場合のみ評価し、未取得は observation_gap として妥当** (FAIL 要因にしない)。
- 未取得 field は無言欠落でなく not_observed+reason。鍵画面が取得手段 (WebFetch/静的 snapshot/browser-render) の
  範囲でまったく観測できていない場合のみ high。`observation_completeness` へ記録。

## CL-3 合成 design-tokens 被覆 (palette 孤児 0)

- palette + type/spacing/radius/shadow(elevation)/breakpoint/z-layer scale + theme 別 color set + document brand 色。
  観測は WebFetch 静的 CSS からで、**取得された場合のみ完全性を評価し、未取得カテゴリは observation_gap として妥当**。
- 観測色の palette 孤児 0 (C11 --check-screens + 非共有 recount 両方で確認)。light/dark 両対応時は両 color set。
- 色値が正準表現 (hex8+gamut) で保持。孤児>0 (観測色が palette に不在) は high。`recount` の agrees_with_gate=true を必須とする。

## CL-4 content / essence 被覆

- verbatim コピー fact (見出し/CTA/本文/meta・OGP) の欠落が理由付き gap (無言でない)。
- C13 content-intent 推測 (価値提案/キーメッセージ/想定読者/トーン&ボイス/CTA 意図/JTBD 仮説) が全て evidence_refs+confidence 接地。
- C06 essence 章 (本質的問題(JTBD)/読者/価値提案/キーメッセージ/トーン/positioning・差別化) が fact と明示区別。

## CL-5 tech / nonfunctional 被覆

- tech_signals (header/generator/bundle パス/third-party domain/cookie 名) と nonfunctional_baseline
  (転送 byte/cache/圧縮/画像 format/security headers) が既取得 response からの fact で observed_scope 付き。
- 未観測が理由付き gap。tech_stack.identified[] の named 同定 (framework/hosting/CDN/analytics/SaaS) が
  全て signal fact への evidence_refs+confidence 接地で、fact レーンへ混入していない (混入は high)。

## CL-6 被覆の深さ・広さ (R5)

- feature_map (fact 集約) と user_journeys (推測) の明示区別。
- security_observations (cookie 属性/認証 UI/CSP) fact→security_design 推測が OWASP 観点で evidence 接地し受動観測のみ
  (侵入テスト/脆弱性スキャン言及 0)。delivery_topology 推測が header fact 接地。cwv_field_sample が scope_note 付き fact。
- compliance_surfaces (privacy/規約/特商法/CMP) 記録。site_inventory coverage (discovered/extracted/pending/excluded+reason)
  が無言欠落なく、full_site で pending を残したまま完全被覆と偽装していない (偽装は high)。

## CL-7 実名 prompt 構造検査 (anti-overfit)

- C03-C06/C13 実プロンプトに inventory.prompt_contract の実名見出し・cross-lens conflicts・neutral synthesis・
  非模倣/非推薦 guard が存在する。
- **名前出現だけで PASS にしない**: レンズ由来推測が evidence_refs+confidence で接地し fact 非混入で、
  high 主張が複数の直接根拠を持つことを判定する。名前はあるが接地が無い/high が単一根拠なら high finding。

## CL-8 ペルソナ偽装

- 実在個人/組織を代弁する主張が fact レーンに混入していたら、根拠つき inference へ落ちているか (evidence_refs+confidence) を確認。
  fact のままなら high。

## CL-9 共有ゲート + 非共有再計数 (common-mode 破り)

- `mermaid-validate.py` (C10) exit0 で 5 種図種網羅。
- `doc-emit.py --check-screens` (C11) exit0 で screenshot/layout 参照整合・観測色 palette 孤児 0・pending 無言欠落なし。
- **非共有** `recount-palette-orphans.py` が C11 と別走査経路で orphan_count==0 を再計数し一致 (`recount.agrees_with_gate=true`)。
  共有ゲートが 0 でも再計数が孤児を検出したら C11 の走査漏れ=common-mode 誤りとして high。

## CL-10 低負荷 policy + verdict 発行

- request ledger が対象 origin 並列 1・最小間隔・request/byte budget・Retry-After・停止条件を満たす。
  `load_policy_result` へ within_budget/concurrency_ok を記録 (screenshot 専用 budget は設けないため screenshot_budget_ok は任意。負荷は request/byte/pages budget + min_interval で有界)。
- `emit-verdict.py` が assessment へ決定論規則を適用し draft_hash 束縛 verdict receipt を ESB_VERDICT_DIR へ発行。
