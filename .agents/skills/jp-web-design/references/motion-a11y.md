# モーション・hover・操作感・アクセシビリティ

動きは装飾ではなく、①操作できる ②押した ③現れた場所 ④状態が変わった ⑤処理が続いている、のいずれかを伝えるためだけに使う。理由を1文で言えないアニメーションは入れない。

## 1. モーション時間とイージング

```css
:root {
  --motion-instant: 90ms;
  --motion-fast: 140ms;
  --motion-base: 200ms;
  --motion-slow: 280ms;
  --ease-standard: cubic-bezier(.2, 0, 0, 1);
  --ease-exit: cubic-bezier(.4, 0, 1, 1);
}
```

| 場面 | 見た目 | 時間 | 目的 |
|---|---|---:|---|
| hover | border / surface / textの変化。移動は0〜1px | 90〜140ms | 操作対象を示す |
| pressed | `scale(.985)` または1px沈む | 90ms | 押下を即時に返す |
| focus | outlineを即時表示。フェードさせない | 0ms | キーボード現在地を失わせない |
| 小要素の入場 | opacity 0→1 + translateY(6px→0) | 180〜220ms | 「パッと出る」が唐突にならない |
| ページ/大面の入場 | opacity + translateY 8px | 220〜280ms | 空間の連続性を示す |
| popover/menu | opacity + translateY(-4px) + scale(.98→1) | 140〜180ms | 呼び出し元との関係を示す |
| modal/dialog | overlay fade + panel translateY(8px)/scale(.985→1) | 180〜220ms | 前景へ移ったことを示す |
| accordion/details | grid row / height + opacity | 180〜220ms | 開いた領域を追えるようにする |
| toast | 右または下から8px + opacity | 180〜220ms | 結果の発生場所を知らせる |
| 状態更新 | 背景/罫線を一度だけ変化 | 180〜240ms | 変更された対象を示す |
| progress | width/transformを線形寄りに更新 | 200〜500ms | 進捗の方向と量を示す |

- 同時入場は最大6要素。staggerは30〜50ms、全体を300ms以内に収める。長い一覧を1件ずつ順番に出さない。
- hoverでカードを大きく浮かせない。border変化を基本とし、移動しても1pxまで。レイアウトを動かすプロパティは使わない。
- 画面全体の毎回フェード、バウンス、オーバーシュート、常時点滅、背景の自動移動、カーソル追従は禁止。
- 処理中は対象の近くへ進捗と文言を出す。画面全体を動かして待たせない。

## 2. 参照CSS

```css
.interactive {
  transition:
    background-color var(--motion-fast) var(--ease-standard),
    border-color var(--motion-fast) var(--ease-standard),
    color var(--motion-fast) var(--ease-standard),
    transform var(--motion-instant) var(--ease-standard);
}
.interactive:hover { border-color: var(--border-control); }
.interactive:active { transform: scale(.985); }

@keyframes enter-soft {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
.enter-soft {
  animation: enter-soft var(--motion-base) var(--ease-standard) both;
  animation-delay: var(--enter-delay, 0ms);
}

@keyframes popover-in {
  from { opacity: 0; transform: translateY(-4px) scale(.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.popover[data-state="open"] {
  transform-origin: top;
  animation: popover-in var(--motion-fast) var(--ease-standard) both;
}

@keyframes dialog-in {
  from { opacity: 0; transform: translateY(8px) scale(.985); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.dialog[data-state="open"] {
  animation: dialog-in var(--motion-base) var(--ease-standard) both;
}

@keyframes busy-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .55; }
}
.busy-indicator { animation: busy-pulse 1.2s ease-in-out infinite; }
```

要素をDOMへ追加するときは、追加された要素だけへ `.enter-soft` を付ける。同じ要素を再レンダーするたびに入場アニメーションを再実行しない。戻る操作では進行方向を逆にするか、動きを省く。

## 3. hoverと状態の設計

- **ボタン**: hoverで同色相の明度、pressedでscale、loadingで幅を維持したまま文言 + 進捗表示。二度押しを防ぐ。
- **カード/行**: クリック可能な場合だけhoverで`border-control`またはsurface変化。押せないカードへhover・pointerを付けない。
- **リンク/ナビ**: textまたはsurface変化に加えて太さ・border・`aria-current`を使う。色だけに頼らない。
- **入力**: hoverはborder、focusはoutline、errorはdanger border + 直し方。hoverをfocusより強くしない。
- **状態バッジ**: 状態変化時に1回だけsurface/borderを変える。連続点滅させない。処理中は `--status-info-*` + 文言 + 必要なら穏やかなpulse。
- **ドラッグ**: 掴める形、grab/grabbing、移動先のプレースホルダーを同時に示す。hoverだけに隠さない。

タッチ端末にはhoverがない。重要操作・説明・状態をhoverだけに置かず、`@media (hover: hover) and (pointer: fine)` の中だけでhover固有効果を有効にする。

## 4. 展開・オーバーレイ

- popover/menuはトリガーに近い方向から短く現れる。閉じるときは120〜160msで速く退出する。
- modalはoverlayとpanelを別々に動かす。開いたらフォーカスを移し、閉じたら呼び出し元へ戻す。破壊的確認は外側クリックで閉じない。
- accordionは内容を先に表示してopacityだけ動かす実装を避ける。高さ/行とopacityを同時に変え、フォーカス可能要素が閉じた領域に残らないようにする。
- toastは成功なら一定時間後に消してよい。エラーは次の行動と閉じる操作を持ち、自動で消さない。
- tooltipは補助であり、操作に必須の情報を置かない。キーボードfocusとタッチでも到達可能にする。

## 5. reduced motion / contrast / forced colors

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
  }
}

@media (forced-colors: active) {
  :where(a, button, input, select, textarea, summary):focus-visible {
    outline: 3px solid CanvasText;
  }
}
```

reduced-motionでも状態変化そのものは消さない。animationを止めた状態で、文言・アイコン・border・DOM順だけで同じ意味が伝わることを確認する。

`prefers-contrast: more` の役割トークン上書きは `assets/hiraga/hiraga-color-system.css` が唯一の正本。ここやアプリ側へ値を複製せず、正本CSSをそのまま読み込む。

## 6. アクセシビリティ

- `:focus-visible` は `--focus-ring`(アクセント色)の3px outline + 3px offset + `--focus-gap`(白)の隙間、即時表示。濃色のナビ内では `--focus-ring-inverse`。
- タップ領域44×44px以上。SPでは主要CTAを原則全幅にする。
- 状態を色だけで伝えない。文言、border、アイコン、位置のうち少なくとも1つを併用する。
- `node scripts/check-hiraga-contrast.mjs` でトークンの組を検査し、画面はaxe等で本文・状態色・focusを機械検査する(ライトのみ)。
- スクリーンリーダーのlive regionは必要な結果だけを短く読み上げる。アニメーションの途中経過を連続通知しない。
- キーボードでpopover / modal / accordion / tabbarを操作し、フォーカスが見え、閉じた要素へ入らず、固定要素の下へ隠れないことを実測する。

## 7. 検収

- [ ] すべての動きに「何を伝えるか」の理由がある。
- [ ] hover / pressed / focus / loading / success / errorが別々に設計されている。
- [ ] 入場は追加された対象だけ、6要素以内、全体300ms以内。
- [ ] hoverでレイアウトが動かず、タッチでも重要情報へ到達できる。
- [ ] modal・popover・accordion・toastを実操作し、開閉・ESC・フォーカス復帰を確認した。
- [ ] reduced-motionで装飾動作が止まり、意味と操作が残る。
- [ ] contrast/forced-colors/print/keyboard/screen readerを確認した。
