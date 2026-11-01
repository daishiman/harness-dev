---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 未実施
gate_type: qa
entities_covered: []
applicability:
  applicable: true
  reason: チラシ制作の再現性と導入品質のため適用
---

# P09 — quality-assurance

## 目的
印刷・素材・全案可読性を保証範囲内で検査する。

## 背景
自然な境界と空白の均衡は座標検査だけで保証できない。印刷用PNGを1枚ずつ見て文字と人物の関係を評価する。

## 前提条件
全対象のout/<ID>/print.pngとout/checks.jsonが最新fingerprintで存在する。

## ドメイン知識
F07/F11は紙面中央の品質見本。黄金比は固定強制せず、主題→実例→参加判断→申込の読み順を優先する。

## 成果物
projectのvisual-review.jsonとverification/visual-smoke-review.json。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] 全案のprint.pngを個別実見し、顔保護・写真境界・主題の読み順・下部中央軸・QR衝突を具体所見に記す。
- [ ] mandatoryFixesが0でない画像、未実見画像、古いSHAはfinalize不可であり、連絡先/住所/料金/Peatix補足の意味群も検査する。
- [ ] scripts/package.pyの必須ファイル検査がplugin-composition.yamlのcapabilitiesから導出され、4skill・stage local agent4本・references/essence.jsonを漏れなく含み(essence-baseline.jsonは導入版の初期化中だけ欠落を許し、以降の版では必須とする)、旧agents/flyer-reviewer.mdと共有専門役3本を要求しない。
- [ ] python3 scripts/flyer.py essence-checkがプラグイン全体でexit 0で、essence-baseline.json(初期化中は承認済みのessence.json)より担当数・LLM評価予算・E*の数が増えず(一致する承認記録のある超過を除く)、golden事例(過去の中心軸・白黒欠落・旧SHA)が全て試験に対応して残る(C17)。
- [ ] plugins/flyer-studio/node_modules配下にある他製品のSKILL.mdが、repoのskill走査・governance検査・配布キットのいずれにも混入しないことを確認する。

### 受入例
- 満たす例: CTAは「お申し込み」、補足は「（詳細はPeatix）」として1群に見え、料金と税込食事代が隣接する。
- 満たさない例: 細い箱線で写真世界観を分断、右下QRに合わせ文字全体を左へずらす。

### 事前解決済み判断
文字量を増やして余白を埋めない。濃淡の自然なfieldと群内近接を先に調整する。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
