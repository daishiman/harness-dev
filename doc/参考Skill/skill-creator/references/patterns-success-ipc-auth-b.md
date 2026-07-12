# 成功パターン: IPC/Auth/Testing・UI

> 親ファイル: [patterns.md](patterns.md)
> 続き: [patterns-success-ipc-auth.md](patterns-success-ipc-auth.md) の後半

## 成功パターン（続き）

### [UI] React Portalによるz-index問題解決パターン（AUTH-UI-001）

- **状況**: ドロップダウンメニューが他の要素の下に隠れる（z-indexだけでは解決不可）
- **アプローチ**:
  - 問題: CSSのスタッキングコンテキストにより、子要素のz-indexが親の範囲内に制限される
  - 解決: React Portalで`document.body`直下にレンダリングし、DOM階層から切り離す
  - 実装: `createPortal(<DropdownContent className="z-[9999]" />, document.body)`
- **結果**: z-[9999]がグローバルに機能し、確実に最前面表示
- **適用条件**: モーダル、ドロップダウン、ツールチップ等のオーバーレイUI
- **発見日**: 2026-02-04
- **関連タスク**: AUTH-UI-001
