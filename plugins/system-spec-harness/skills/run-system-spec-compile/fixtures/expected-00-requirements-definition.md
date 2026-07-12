---
status: confirmed
category: requirements-definition
---

# 要件定義書 (上位概念)

> 本章は spec-state.json の requirements_foundation を正本とする、システム構築の憲法。
> 以降の各技術章は frontmatter の serves_goals でここ (ゴール) へトレース (anchor) する。
> 上位概念がブレなければ、仕様が整った後もブレない。

- 確定マーカー: `status: confirmed`

## U1 本質的目的 (essential_purpose)

社内の請求・監査業務を単一の Web システムへ統合し、手作業と二重管理をなくす

## U2 背景 (background)

現状は表計算と個別ツールが乱立し、請求漏れと監査対応コストが慢性的に発生している

## U3 ゴール (goals)

| ID | ゴール |
|---|---|
| G1 | 請求・監査データを単一の信頼できる情報源へ統合する |
| G2 | 主要業務動線を Web だけで完結できるようにする |

## U4 目標 (objectives)

| ID | 目標 | 測定基準 |
|---|---|---|
| O1 | 請求漏れ検知を自動化する | 請求漏れ 月次0件 |
| O2 | 監査証跡を全操作で取得する | 監査ログ網羅率 100% |

## U5 成功基準 (success_criteria)

- 請求漏れ0件が3ヶ月継続する
- 監査対応工数を50%削減する

## U6 ステークホルダー (stakeholders)

- 経理チーム
- 監査担当
- 情報システム部

## U7 スコープ (scope)

- **対象 (in)**: 請求管理, 監査ログ, ユーザー管理
- **対象外 (out)**: 給与計算, 在庫管理

## U8 制約 (constraints)

- 社内 k8s 上で稼働する
- 個人情報は国内リージョンに保持する

## U9 具体的にやりたいこと (concrete_intents)

| ID | やりたいこと | 資するゴール |
|---|---|---|
| I1 | 請求データを日次でバックアップする | G1 |
| I2 | レスポンシブ Web UI を提供する | G2 |

## 意思決定支援 (decisions)

| ID | 論点 | 状態 | 選択肢 (費用・適合・注意点) | AI推奨 | ユーザー決定 | 資するゴール |
|---|---|---|---|---|---|---|
| D1 | 認証基盤を無料枠のmanagedサービスとOSS self-hostedのどちらにするか | recommended_pending_confirmation | managed-free:無料枠のあるmanaged認証 / cost=無料枠後は月間利用者数に応じた従量課金 / free=月間アクティブユーザー1万まで無料 / fit=短期導入と運用負荷削減に適合 / pros=初期費用0円, 運用負荷が低い / cons=無料枠超過後は課金 / risks=将来の価格改定 / lock-in=中 / ops=低 / evidence=https://example.com/official-managed-pricing<br>self-hosted:OSS self-hosted認証 / cost=ライセンス無料だがインフラと保守の人件費が必要 / free=機能上の無料枠制限なし / fit=内製運用能力を確保できる場合に適合 / pros=ライセンス費0円, 移行自由度が高い / cons=保守と更新が必要 / risks=脆弱性対応の遅延 / lock-in=低 / ops=高 / evidence=https://example.org/official-oss-docs | managed-free — 現在の利用規模では無料枠内で、運用負荷を最小化できる (注意: 無料枠上限と価格改定を定期確認する; confidence=medium; checked=2026-07-11T00:00:00Z) | 確認待ち | G2 |
