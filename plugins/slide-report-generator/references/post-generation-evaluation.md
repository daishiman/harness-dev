# 生成後評価サブシステム（正本）

> プレゼン生成完了後に「成果物が仕様通り・要望通り・エレガントか」を多角的に評価する仕組みの SSoT。
> 機械評価 `vendor/scripts/evaluate-deck.js` ＋ LLM評価 `agents/deck-evaluator.md`（思考リセット後30種思考法）＋
> fail-soft 自動起動フック `hooks/hook-postgen-eval.py` の3点で構成する。

## 1. 全体像

```
プレゼン生成（P3/P3-determ で index.html 等を出力）
        │
        ▼  PostToolUse フック（Write|Edit|MultiEdit が中核ファイルを書いた時）
  hook-postgen-eval.py
        │  mode を判定し、additionalContext で評価起動を促す（重い評価は hook 内で強制実行しない）
        ▼
  evaluate-deck.js（slide 機械評価の正本）
        │  Dx(動作可能性)・D1〜D4 を機械判定 → evaluation-report.json / .md を出力
        ▼
  deck-evaluator.md（30種思考法のLLM評価）
        │  D5(要望↔構成)＋視覚的多角評価＋4条件最終判定 → 改善指示
        ▼
  改善（slide-modifier / 直接Edit）→ evaluate-deck.js 再実行（最大3周）
```

- **機械(evaluate-deck.js)**: 再現性のある判定（崩れ・ナビ・仕様適合）。chromium非依存の静的検証が中核。
- **LLM(deck-evaluator.md)**: 機械では不可能な「要望との矛盾・仕組みの反映・配置の妥当性・エレガンス」を30種思考法で判定。
- **フック**: 生成完了をトリガに上記の起動を促す。hook 自体は fail-soft に留め、即時の軽量検知＋遅延の完全評価指示で「うるさすぎ/動かない」を両立回避。

## 2. 既存資産との関係（重複させない）

| 既存 | 役割 | 本サブシステムでの扱い |
|------|------|----------------------|
| `scripts/verify-slides.js` | スクショ/16:9/型崩れ | 視覚裏取りに利用。evaluate-deck.js の動的検証は同手法を内蔵 |
| `scripts/evaluate-image-consistency.js` | 全面画像デッキの画風一貫性（lockTiers.tier1+consistencyAnchors） | gpt-image-2 生成画像群を LLM-judge で 0-1 採点し閾値割れページの再生成推奨を出す（破壊操作なし）。evaluate-deck.js(HTML崩れ/ナビ) とは別系統で画像内容の一貫性を見る。目視の前段ゲート |
| `scripts/sync-checker.js` | structure.md⇔HTML 同期 | evaluate-deck.js が D4 で呼出・集約 |
| `scripts/validate-structure.js` | 構造仕様 V-001〜V-043 | evaluate-deck.js が D4 で集約（structure.json がある時のみ） |
| `scripts/check-consistency.js` | 色/フォント統一 | 任意で併用（deck-evaluator 視覚評価の補助） |
| `agents/ui-quality-reviewer.md` | S1〜S26 UIレビュー(Phase 3.5) | deck-evaluator の視覚チェックリスト参照元。**置換せず上位ゲート** |
| `agents/cross-deck-reviewer.md` | シリーズ横断(Phase 5) | 単一デッキ評価は本サブシステム、横断はP5 と役割分担 |

**根本原因（why5回）**: 評価基準が verify-slides / ui-quality-reviewer / sync-checker / validate-structure に散在し、
(1) それらを束ねる単一の生成後ゲートが無く、(2) 自動起動(フック)が無かった。本サブシステムは
「既存の統合 ＋ 自動化 ＋ 要望適合(D5)の追加」であり、新規の重複チェックを増やすものではない。

## 3. 評価次元（Dx・D1〜D5）と機械チェックID

| 次元 | 内容 | 機械(evaluate-deck.js) check ID | LLM(deck-evaluator) |
|------|------|-------------------------------|---------------------|
| Dx 動作可能性 | CSS/JS の実在（インライン or 実体）/ スライド表示切替CSS / ページ送り制御JS（**動かないデッキを CRITICAL 検出**・静的・chromium非依存） | `operability.css` `operability.js` `operability.slideToggleCss` `operability.pagingJs` | playwright スクショで実描画・ページ送り動作を最終確認 |
| D1 視覚的崩れ | 型崩れ/画像欠落/broken img/カードはみ出し/枠外/16:9 | `visual.corruption` `visual.missingImage`（静的）/ `visual.brokenImg` `visual.overflow` `visual.outOfBounds` `visual.ratio`（動的） | スクショ目視で崩れ・バランス |
| D2 文字サイズ | rem<1.4 / SVG<13px（静的）/ computed px（動的） | `font.remMin` `font.svgMinPx` / `font.bodyComputed` `font.svgComputed` | 視認性・階層 |
| D3 ナビ | 左右送り/ページネーション/上部インデックス/カウンター/進捗 | `nav.prevNext` `nav.dots` `nav.topIndex` `nav.counter` `nav.progress` | 配置（両サイド・位置）の妥当性 |
| D4 仕様適合 | structure⇔HTML 同期 / 構造仕様 V-001〜 | `spec.sync` `spec.validate` `spec.noStructure` | 構成意図への適合 |
| D5 要望↔構成 | 要望との矛盾・仕組みの反映・読者フック（入口ホリゾンタル: 入口が読者の得たい変化で開くか） | `requirement.pendingLlm`（記録のみ） | **核心。機械不可・LLM必須** |

### 3.1 ナビ検出（命名3系統 union）

実デッキでナビのCSS命名が複数系統混在する（`.pg-*` / `.section-nav`・`.agenda-indicator` / `.nav__*`）ため、
機能ベースの複数セレクタ union ＋ aria-label(前/次)・キーボード(ArrowLeft/Right) ヒューリスティックで検出する。
正本は `evaluate-deck.js` の `CONFIG.nav`。

- 左右送り `nav.prevNext`: prev と next の両方が必要（無ければ error）
- ページネーション `nav.dots`: 無ければ warn
- 上部インデックス `nav.topIndex`: 無ければ warn（**ユーザー要望項目。deck-evaluatorが要望と照合し昇格/降格**）

### 3.2 chromium 縮退（graceful degradation）

動的検証は playwright(chromium) を使う。未導入環境では `dynamic.status = skipped(no-chromium)` とし
**静的検証のみで継続**（exit を落とさない）。導入手順:

```bash
python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/setup-playwright.py" --install
```

## 4. 30種思考法マッピング（deck-evaluator が全件評価・省略禁止）

deck-evaluator は下表の30種すべてを必ず適用し、評価レポートに `30種適用カバレッジ` を出す。
問題発見に寄与しなかった思考法も `PASS_NO_FINDING` として記録する。これにより「30種すべてを使用したか」を後から監査できる。

| カテゴリ | 思考法 | 主担当次元 | 評価で見ること |
|---------|-------|-----------|--------------|
| 論理分析 | 批判的思考 | D4/D5 | 要望・仕様の前提を疑う |
| 論理分析 | 演繹思考 | D5 | 要望→構成→実装の論理一貫性 |
| 論理分析 | 帰納的思考 | D3 | 複数スライドの崩れから一般傾向を導く |
| 論理分析 | アブダクション | D1 | 崩れの最も妥当な原因を推論 |
| 論理分析 | 垂直思考 | D5 | 矛盾を根本まで深掘り |
| 構造分解 | 要素分解 | D1 | 崩れを最小要素に分解 |
| 構造分解 | MECE | D3 | ナビ要素を漏れ重複なく被覆 |
| 構造分解 | 2軸思考 | D1/D2 | 機械↔LLM × static↔dynamic で整理 |
| 構造分解 | プロセス思考 | D4 | 構成順(目的→背景→手段→結論)の妥当性 |
| メタ抽象 | メタ思考 | D5 | 評価の観点自体の妥当性 |
| メタ抽象 | 抽象化思考 | D5 | 粒度がデッキ全体で揃うか |
| メタ抽象 | ダブルループ | D5 | 要望の前提そのものを疑う |
| 発想拡張 | ブレインストーミング | D1 | 崩れ候補を自由に洗い出す |
| 発想拡張 | 水平思考 | D3 | 両サイド配置など別案で見る |
| 発想拡張 | 逆説思考 | D3 | 「評価しない方が良い場面」を検討 |
| 発想拡張 | 類推思考 | D1 | 視覚回帰テスト/lintの知見を借用 |
| 発想拡張 | if思考 | D1 | 別ブラウザ/投影/印刷で崩れるか |
| 発想拡張 | 素人思考 | D1/D3 | 専門知識なしでも崩れ・迷子に気づくか |
| システム | システム思考 | D1↔D2↔D3 | font小→はみ出し→ナビ被りの連鎖 |
| システム | 因果関係分析 | D1 | 崩れの原因と結果の連鎖 |
| システム | 因果ループ | 改善 | 改善→再評価ループの暴走防止(最大3周) |
| 戦略価値 | トレードオン思考 | フック | 即時静的＋遅延完全の両立 |
| 戦略価値 | プラスサム思考 | D5 | デッキ全体の伝達価値最大化 |
| 戦略価値 | 価値提案思考 | D5 | 崩れ/不足が価値を毀損しないか |
| 戦略価値 | 戦略的思考 | 全体 | クロスランタイム・chromium非依存の戦略 |
| 問題解決 | why思考 | 改善 | なぜ反映されなかったか根本原因 |
| 問題解決 | 改善思考 | 改善 | 改善ポイントの優先順位 |
| 問題解決 | 仮説思考 | 改善 | 真に解くべき問いの仮説 |
| 問題解決 | 論点思考 | D5 | 「崩れ検出」か「自動化」か「仕様適合」か |
| 問題解決 | KJ法 | 改善 | finding をグルーピングし構造化 |

## 5. 4条件（生成デッキへの適用）

| 条件 | 定義 | 機械判定(conditions) |
|------|------|---------------------|
| 矛盾なし | 仕様間・実装間・要望との相反が無い | `contradiction_free`: error が0 |
| 漏れなし | 必須項目（左右送り・要望の仕組み・全スライド）が揃う | `completeness`: nav.prevNext の error が無い |
| 整合性あり | 用語・フォーマット・構成・同期が統一 | `consistency`: 同期/仕様 error が無い |
| 依存関係整合 | 参照画像・structure・CSS/JS依存が解決 | `dependency_integrity`: 画像欠落 error が無い |

機械 verdict=PASS ＋ deck-evaluator の D5を加えた4条件すべて PASS で合格。

## 6. 手動実行（クロスランタイム）

4ランタイム（Claude Code Bash / `!` 手動 / Codex shell / 手動CLI）で同一動作する。

```bash
# 機械評価（完全：chromium があれば動的検証も実行）
node scripts/evaluate-deck.js "05_Project/スライド/slide-XXXX/"

# フック相当の高速静的のみ
node scripts/evaluate-deck.js "05_Project/スライド/slide-XXXX/" --static-only

# JSON出力 / 厳格(WARNも失敗) / レポート先指定
node scripts/evaluate-deck.js "<deck>" --json
node scripts/evaluate-deck.js "<deck>" --strict
node scripts/evaluate-deck.js "<deck>" --report ./report.json

# 画像一貫性採点（全面画像デッキ・lockTiers.tier1+consistencyAnchors rubric / 破壊操作なし）
node scripts/evaluate-image-consistency.js "<deck>" --threshold 0.8
node scripts/evaluate-image-consistency.js "<deck>" --dry-run   # 評価プロンプトのみ（codex呼ばない・コスト無し）
```

終了コード: `0=PASS` / `4=FAIL` / `2=引数` / `3=不在`。

## 7. フック登録（.claude/settings.json）

PostToolUse（matcher: `Write|Edit|MultiEdit`）に登録する。フックは deck の中核ファイル
（`index.html` / `styles.css` / `scripts.js` / `structure.md` / `structure.json`）書込時に発火し、
それ以外は無音（通常編集を妨げない）。`index.deploy.html` / `index-single.html` は除外。
`index.html` 書込時に CSS/JS がまだ無い生成順序でも、後続の `styles.css` / `scripts.js` 書込で評価を起動できるようにする。

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command",
            "command": "python3 $CLAUDE_PLUGIN_ROOT/hooks/hook-postgen-eval.py" }
        ]
      }
    ]
  }
}
```

## 8. 出力先とスコープ

評価レポートは `<deck-dir>/evaluation-report.json` と `.md`（05_Project配下＝変更可）に出力する。
プラグイン本体のリソース（本reference・agent・script・schema）は `$CLAUDE_PLUGIN_ROOT` 配下に置く。
