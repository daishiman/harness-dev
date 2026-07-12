# Phase2 メタ・発想・拡張分析 findings（meta-divergent-analyst・read-only）

対象全件精査（README/両SKILL.md/plan_build.py approval_nonce/send_guard.py/send-campaign.py C-1/R1-orchestrate/presend-verifier/source-audit）。

## M-1 承認の時間アンカー問題（3時点＝別不変の束縛・名指し分離が解）
- **t0 Notionチェック=意図(I)**: 耐久データフラグ。差し込み置換前＝「この人/本文」であり「最終レンダ本文」ではない。
- **t1 dry-run生成=完全性(II)**: send_guard/決定論再計算で束縛。現APPROVE文字列はここ。self-derive で auto化してもトートロジーは無害（元々*改竄検出*で内容妥当性の停止点ではない）。
- **t2 実送信=鮮度(III)**: C-1再取得。ただし subtract-only。

推奨: 完全性をt1束縛のまま自動化 / 意図をt0耐久フラグ / 鮮度をt2再取得へ不変ごと再配線。**dry-run→send を単一アトミック実行**にすれば t1≈t2 で改竄窓が消える。

## C2漏れ（重要・実バグ示唆）
C-1 は subtract-only かつ `送信対象`/`送らない` フラグでしか引かず、`送信対象=✅` 維持のまま**宛先アドレスを編集**すると古いアドレスへ送信される（content_hash は plan 内一致＝改竄検出されない）。→ auto モードは古 plan.json 再利用を禁じ**単一アトミック実行必須**。

## M-2 nonce再配置カタログ（収束）
per-unit nonce 撤去 + 本文DB campaign単位『送信承認=✅』go トグル(1ビット・耐久・帰属・時刻付き=監査強) + 初回canary既定 へ再配置。nonce残置+auto照合はトートロジーで却下。

## 前提を覆す発見
- **ダブルループ**: 前回レビューが対話ゲートを足したのは「送信時 blind approve」前提下。自動化で支配変数が「データ整備時 human-in-loop」へ転換し前提崩壊。装置はもう無い問題を解き続けている（feedback_contract OUT1 三本柱と不整合）。
- **逆説**: APPROVE文字列は揮発的、Notionチェックは永続・帰属・時刻付き＝データ層移設で**監査性は上がる**。危険は「確認0」でなく「耐久意図記録なしの確認0」。
- **素人**: 初心者は誤リスト/stale✅/可視CC秘書で事故る。nonce はコピペ blind approve（非問題）を守り真リスクを守らない。

## 推奨モデル: 宣言的レコンサイラ+三不変分離（確認0だが安全）
意図=耐久`送信承認`トグル / 完全性=単一アトミックauto実行+self-derive(send_guard温存) / 鮮度=C-1を再レンダリング照合へ強化 / 被害局限=初回canary既定 / nonce撤去・presend-verifierとAPPROVEは`--interactive`後方互換。reset-observer A1-A5を全吸収。

## C4依存（注意）
presend-verifier は人間APPROVE文字列を独立入力に取る。self-derive で proposer==approver 化し fork独立性が破れる→auto モードで verifier 意義の再定義要。

## 横展開上位3
approval-locus-migration(reference) / approval-three-invariant-decomposition(rubric) / irreversible-side-effect-confirm-reduction(skill)。
