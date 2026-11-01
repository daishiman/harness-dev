---
status: confirmed
category: maintenance-ops
aggregate: 確定
spec_cells: [maintenance-ops.web, maintenance-ops.mobile, maintenance-ops.tablet, maintenance-ops.desktop-windows, maintenance-ops.desktop-linux, maintenance-ops.desktop-macos]
serves_goals: [G1]
---

# 保守運用管理 (maintenance-ops)

- カテゴリ集約状態: **確定**
- 章確定マーカー: `status: confirmed`

## カテゴリ別収集状態

| プラットフォーム | 状態 | 根拠 |
|---|---|---|
| Web (web) | 確定 | 確定質疑: qa-008。裏付け質疑 (`qa_refs`): `qa-036` — 本章の「確定内容 (質疑録)」へ接地根拠として併記。資するゴール: G1 |
| モバイル (mobile) | 対象外 | 理由: 承認: appr-001 |
| タブレット (tablet) | 対象外 | 理由: 承認: appr-001 |
| デスクトップ (Windows) (desktop-windows) | 対象外 | 理由: 承認: appr-001 |
| デスクトップ (Linux) (desktop-linux) | 対象外 | 理由: 承認: appr-001 |
| デスクトップ (macOS) (desktop-macos) | 対象外 | 理由: 承認: appr-001 |

## 対象外の承認範囲

> 本章の対象外セルが引用している承認の実体。状態表の「承認: <id>」だけでは、その承認が何をどこまで認めたものかを章から辿れない。

### 承認: `appr-001`

ユーザー一括承認: 非 Web プラットフォームは全カテゴリで対象外

## 上流指針 (doctrine anchors)

> 本章の設計判断が従う上流の正本 (1 concern 1 authority)。具体技術ではなく上流工程を導く規範であり、下位の技術選定は本節と矛盾してはならない。正本: `ref-system-design-knowledge/references/doctrine-anchor-registry.json`

| 設計 concern | 上流の正本 (authority) | 導く範囲 | 出典 | 最終確認 | 本章の確定セルへの反映 |
|---|---|---|---|---|---|
| operations | Google SRE | 運用手順・障害対応・トイル削減・ポストモーテムの上流指針 | https://sre.google/workbook/ | 2026-07-12 | オンコール輪番と障害 runbook (qa-008) を、月末 3 営業日の遅延通知 (qa-029) の受け手として結ぶ。週次のリストア訓練 (qa-008) は、日次バックアップ (qa-001) が戻せたかを記録に残す。 (根拠の性質: アシスタントの推定 (利用者確認も検証可能な出典も経ていない)) |

## 確定内容 (質疑録)

> 本章の各確定セルが何を根拠に確定したかの実体。`qa_ref` が主たる接地根拠、`qa_refs` がそれを支える裏付け質疑であり、いずれも qa_log (spec-state.json) の逐語である。ここに現れない主張は本章の確定内容ではない。

### Web (web)

- 資するゴール: G1

#### 主たる接地根拠: `qa-008`

**問**

保守運用管理（maintenance-ops）× Web の要件は?

**答**

オンコール輪番・障害 runbook・週次リストア訓練。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 原本 (orig-spec-state.json、ファイル更新 2026-10-05) に当初から記録されていたシナリオ上の利用者回答。対話の逐語ログと回答時刻は残っていない。問は開いた問 (選択肢なし) で、代替案を提示した記録は無い (basis の user-decision は原本の値で、writer は記録済みの basis を上書きできない))

#### 裏付け質疑: `qa-036`

**問**

当番への通知を、どこからどのような手段で届けたいかを教えてください。

**答**

情報システム部の社内監視基盤のアラートから、オンコール輪番 (qa-008) のその週の担当者へ、社内チャットの当番チャンネルとメールの両方で送る。通知には、該当する runbook の手順へのリンクを付ける。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 再構築 (orchestrator 補助, 2026-10-12, sysspec5): シナリオ上の利用者発言として記録した。実利用者との対話ログではない。R2 のセル補充の開いた問 (選択肢なし、代替案の提示なし)。sysspec4 の評価で、infrastructure 章の応答時間の目安と通知の送り方に利用者の決定が無いことが指摘されたため、team-lead の指示 (2026-10-12) で足した。answered_at は本記録の作成時刻 / 回答時刻: 2026-10-12T07:39:16Z)

## To-Be / Delta

> 本章の**規範**。上位概念 (要件定義書 U3 ゴール / U4 目標 / U9 具体的やりたいこと) を本章の serves_goals で絞り込んだ射影であり、設計知識 card (非規範の参考資料) とは役割が異なる。As-Is (現行実装の姿) は spec-state.json の管轄外のため本節では断定せず、到達点と、その到達を判定する観測点だけを規範として置く。

### 到達すべき状態 (To-Be)

- **G1**: 請求・監査データを単一の信頼できる情報源へ統合する

### 受入条件 (Delta の判定点)

| 目標 | 到達点 | 達成の観測点 (measure) |
|---|---|---|
| O1 | 請求漏れをシステムが自動で検知する | 締め後に残る請求漏れ 月次 0 件 (稼働後最初の月次締めから計測) |

### 本章がかなえる具体的やりたいこと (U9)

- **I1**: 請求・監査データを日次でバックアップする
- **I3**: 確定した請求書は書き換えず赤黒訂正で直し、監査ログは追記のみとする

### 本章に効く確定意思決定

- **D1**: データベースに使う PostgreSQL の版をどれにするか (情報システム部の提供版は 15 と 16, qa-018)
  - 採択: PostgreSQL 16 (情報システム部が提供する版) (`pg16`)
  - 目的適合: G1 (単一の信頼できる情報源) に要るトランザクション・制約・バックアップの機能を満たす
  - 採択の接地根拠: `qa-031`
- **D3**: 社内 IdP の OIDC で得たトークンを、どこで持ち、API へどう送るか
  - 採択: バックエンド (FastAPI) がトークンを持ち、ブラウザには cookie のセッションだけを渡す方式 (`bff-session`)
  - 目的適合: G1 (請求・監査データの単一の情報源) の信頼を、トークンをブラウザに出さないことで支える。8 時間のセッション (qa-002) と、IdP でのアカウントの無効化 (qa-026) をサーバ側で扱える
  - 採択の接地根拠: `qa-034`

## 適用された設計知識

> 以下の deep knowledge card は設計判断を支援する**非規範の参考資料**であり、実装済み・検証済みの証拠ではない。カード内の `採否: applied` は設計採用を意味し、実装状態は意味しない。規範となる差分は本章の To-Be / Delta 節と参照先仕様で管理する。

### 本章での適用

clean-code の『意図の分かる名前』と『効果とエラーを明示する』を runbook (qa-008) に当てた。障害手順は『何が起きたら・誰が・何をするか』が名前で分かる単位に分ける。週次のリストア訓練 (qa-008) は、実行できる手順そのものを runbook に置き、日次バックアップ (qa-001) が戻せることを毎週確かめる (実行できる例)。

- (根拠の性質: アシスタントの推定 (利用者確認も検証可能な出典も経ていない) / 記録時刻: 2026-10-12T00:17:23Z)

### Clean Code — deep knowledge card

- 出典カード: `ref-system-design-knowledge/references/clean-code.md`

#### 目的

codeを、次の変更者が意図・制約・failureを短時間で理解し、安全に変更・検証できる作業媒体にする。

#### 解決する問題

- 名前と抽象度が意図を表さず、readerが実装詳細からbusiness ruleを逆算する。
- 一つの変更理由が複数moduleへ散り、副作用とerror pathを予測できない。
- 重複したruleが別々に更新され、仕様のSSOTが崩れる。
- testがimplementation detailへ結合し、refactoringを妨げる。

#### 適用条件

- 複数人・長期保守・高変更頻度・重要ruleがあり、理解と変更の費用が支配的。
- test/lint/review/observabilityで改善効果をfeedbackできる。
- domain languageとcoding conventionをteamで合意・更新できる。

#### 非適用条件

- throwaway explorationでは全規則を先行適用せず、学習後に残すcodeだけを整理する。
- generated/vendor codeへ手動styleを強制しない。generation inputとboundaryを管理する。
- 短い関数、class化、DRY等を絶対値として扱い、局所的な明瞭さを悪化させる場合は適用しない。

#### トレードオフ・失敗モード

- naming/refactoring/testへ時間を使うため、寿命とriskが低いcodeでは投資超過になり得る。
- micro-function化でcontrol flowが多数fileへ散り、かえって読みにくくなる。
- DRYを急ぎ、異なるdomain conceptを一つの抽象へ結合して変更を難しくする。
- commentを全否定して、理由、trade-off、外部制約、security decisionまで消す。
- coverageやlint scoreを目的化し、重要behaviorの未検証を隠す。

#### goalへの寄与

- goalに関わるbusiness ruleを名前とtestで明示し、仕様→code→evidenceのtraceを短くする。
- maintenance objectiveには変更lead time、review指摘、escaped defect、rollback率などのoutcomeを使う。
- 無料toolの導入自体を成功とせず、teamが継続運用でき、重要riskを減らすかで判断する。

---

### 確定判断ごとの原則採否

- 確定内容 `qa-008` (対応セル: web)
  - 確定要件: 「オンコール輪番・障害 runbook・週次リストア訓練。」 (正本: 本章「確定内容 (質疑録)」の `qa-008`)
  - 設計解釈の記録経路: `legacy_backfill` (`set-qa-design-applications`)
  - 原則 (`plugins/system-spec-harness/skills/ref-system-design-knowledge/references/clean-code.md#中核概念`): 意図と効果・失敗を明示し、実行例で手順を検証する
    - 採否: `applied`
    - 章固有の根拠: qa-008のオンコール輪番・障害runbook・週次リストア訓練を、誰が何を実行し何を確認すれば回復したと言えるかが読み取れる単位で記録する。バックアップが存在することだけで復旧済みとはせず、既存のRTO/RPOの運用条件と訓練結果へ結び付ける。
    - トレードオフ:
      - 手順と実際の運用がずれないよう、訓練後の更新作業が必要。
      - 自動化は目的ではなく、障害時にも効果と失敗が追えることを優先する。
- 資するゴール: G1

## 最新ドキュメント出典

- (このカテゴリに割り当てた取得済みドキュメントなし。全体出典は index.md 参照)
