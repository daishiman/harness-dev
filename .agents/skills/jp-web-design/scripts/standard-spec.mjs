// 配色の「検査するペア」と「見本に載せる色」の正本。値は持たず、正本CSSのトークン名だけを持つ。
// check-standard-contrast.mjs (合否を出す) と export-standard-tokens.mjs (見本HTMLを生成する) が共有する。
// 分けて持つと、検査は通るのに見本の数値だけ古いという状態が起きる。実際に v0.3 で起きた。

export const TEXT = 4.5
export const NON_TEXT = 3.0

/** 満たすべきペア [前景, 背景, 基準, 用途] */
export const required = [
  ['text-primary', 'surface', TEXT, '本文×白'],
  ['text-primary', 'app-background', TEXT, '本文×画面背景'],
  ['text-secondary', 'surface', TEXT, '補助文字×白'],
  ['text-muted', 'surface', TEXT, '説明・プレースホルダー×白'],
  ['text-muted', 'surface-alt', TEXT, '説明×補助面'],
  ['text-heading', 'surface', TEXT, '見出し×白'],
  ['nav-text', 'nav-background', TEXT, 'ナビ文字×淡色面'],
  ['nav-text-muted', 'nav-background', TEXT, 'ナビ補助×淡色面'],
  ['nav-selected-text', 'nav-selected-bg', TEXT, 'ナビ選択'],
  ['action-primary-text', 'action-primary-bg', TEXT, '主ボタン'],
  ['action-primary-text', 'action-primary-hover', TEXT, '主ボタンhover'],
  ['action-primary-text', 'action-primary-active', TEXT, '主ボタン押下'],
  ['action-secondary-text', 'action-secondary-bg', TEXT, '副ボタン'],
  ['action-secondary-text', 'action-secondary-hover', TEXT, '副ボタンhover'],
  ['action-danger-text', 'action-danger-bg', TEXT, '危険ボタン'],
  ['action-danger-text', 'action-danger-hover', TEXT, '危険ボタンhover'],
  ['action-disabled-text', 'action-disabled-bg', TEXT, '無効ボタン'],
  ['link', 'surface', TEXT, 'リンク'],
  ['link-hover', 'surface', TEXT, 'リンクhover'],
  ['input-text', 'input-readonly-bg', TEXT, '読み取り専用'],
  ['input-placeholder', 'input-bg', TEXT, 'プレースホルダー'],
  ['input-invalid-message', 'surface', TEXT, 'エラーメッセージ'],
  ['required-text', 'required-bg', TEXT, '必須ラベル'],
  ['table-head-text', 'table-head-bg', TEXT, '表ヘッダー'],
  ['text-primary', 'table-stripe-bg', TEXT, '表の交互行'],
  ['text-primary', 'table-selected-bg', TEXT, '選択行'],
  ['tab-text-active', 'surface', TEXT, 'タブ選択'],
  ['pagination-active-text', 'pagination-active-bg', TEXT, '現在ページ'],
  ['tag-text', 'tag-bg', TEXT, '分類タグ'],
  ['badge-unread-text', 'badge-unread-bg', TEXT, '未読件数'],
  ['status-neutral-text', 'status-neutral-bg', TEXT, '状態:未処理'],
  ['status-info-text', 'status-info-bg', TEXT, '状態:情報'],
  ['status-success-text', 'status-success-bg', TEXT, '状態:成功'],
  ['status-warning-text', 'status-warning-bg', TEXT, '状態:注意'],
  ['status-danger-text', 'status-danger-bg', TEXT, '状態:エラー'],
  ['tooltip-text', 'tooltip-bg', TEXT, 'ツールチップ'],
  ['selection-text', 'selection-bg', TEXT, '選択文字'],
  ['input-border', 'input-bg', NON_TEXT, '入力枠×白'],
  ['control-off-border', 'surface', NON_TEXT, 'チェック枠×白'],
  ['control-on', 'surface', NON_TEXT, 'チェックON×白'],
  ['focus-ring', 'focus-gap', NON_TEXT, 'フォーカス×白'],
  ['focus-ring', 'nav-background', NON_TEXT, 'フォーカス×淡色ナビ'],
  ['progress-fill', 'progress-track', NON_TEXT, '進捗バー'],
  ['chart-main', 'surface', NON_TEXT, 'グラフ主系列'],
  ['chart-1', 'surface', NON_TEXT, 'グラフ系列1'],
  ['chart-2', 'surface', NON_TEXT, 'グラフ系列2'],
  ['chart-3', 'surface', NON_TEXT, 'グラフ系列3'],
  ['chart-4', 'surface', NON_TEXT, 'グラフ系列4'],
  ['chart-5', 'surface', NON_TEXT, 'グラフ系列5'],
  ['number-negative', 'surface', TEXT, '赤字(損失)の数字'],
  ['number-positive', 'surface', TEXT, '黒字の数字'],
  ['number-negative', 'number-negative-soft', NON_TEXT, '赤字の図形(淡い地に線)'],
  ['chart-threshold', 'surface', NON_TEXT, '閾値線']
]

/** 使ってはいけないペア。基準未満であることを確認する(基準を満たしてしまったらルールの見直しが必要) */
export const avoided = [
  ['p-brand-accent', 'p-brand-indigo', TEXT, 'ブランド軸の面にアクセント色の小さい文字'],
  ['border-subtle', 'surface', NON_TEXT, '装飾罫線を入力欄の境界に使う']
]

/** 順序のないカテゴリ系列。見分けは明度ではなく色相差で作るので、総当たりの最小色相差を見る */
export const series = ['chart-main', 'chart-1', 'chart-2', 'chart-3', 'chart-4', 'chart-5']
export const seriesMinHueGap = 40

/** 見本の基本パレット [トークン, 見出し, 説明] */
export const swatches = [
  ['p-brand-indigo', 'INDIGO', 'ブランドの軸'],
  ['p-brand-accent', 'ACCENT', '重要操作のアクセント'],
  ['p-brand-vehicle-navy', 'VEHICLE NAVY', '車両を連想する補助色'],
  ['p-white', 'WHITE', '画面背景・作業領域'],
  ['surface-accent', 'SOFT ACCENT', '注目面(1画面1〜2か所)'],
  ['p-surface-subtle', 'SOFT SURFACE', '補助面・表ヘッダー']
]

/** 見本の文字・罫線の一覧 [説明, トークン...] */
export const tones = [
  ['通常文字 / 補助文字', 'text-primary', 'text-secondary'],
  ['説明・プレースホルダー', 'text-muted'],
  ['装飾罫線 / 入力枠', 'border-subtle', 'border-control']
]

/** 見本のコントラスト実例。required の用途名で引き、比率は計算値を出す */
export const contrastSamples = [
  { label: 'ブランド軸 × 白文字', fg: 'text-inverse', bg: 'p-brand-indigo', sample: 'Aa' },
  { label: '主ボタン', fg: 'action-primary-text', bg: 'action-primary-bg', sample: 'Aa' },
  { label: '本文 × 白', fg: 'p-ink', bg: 'p-white', sample: 'Aa' },
  { label: '入力枠 × 白', fg: 'text-primary', bg: 'surface', border: 'border-control', sample: '枠' }
]

/** 見本の面積比。正本は references/standard-color-system.md。ここは見本へ焼き込むための転記 */
export const areaRatio = {
  note: '面積の出発点：地と面 75% ／ 文字・罫線・ナビの骨格 20% ／ 操作と状態 5%。サイトの実測比率ではありません。',
  aria: '提案の面積目安：地と面75%、文字・罫線・ナビの骨格20%、操作と状態5%'
}
