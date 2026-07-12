# アイコンガイドライン

**責務**: アイコンライブラリ・マッピングテーブル・使用方法

---

## 1. 推奨アイコンライブラリ

### FontAwesome 6 Free（デフォルト）

```html
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
```

| 項目 | 内容 |
|------|------|
| アイコン数 | 2,000+ |
| 特徴 | 最も豊富、ブランドアイコン充実 |
| 使用方法 | `<i class="fa-solid fa-robot"></i>` |

### Bootstrap Icons（代替）

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
```

| 項目 | 内容 |
|------|------|
| アイコン数 | 2,000+ |
| 特徴 | シンプル、統一感 |
| 使用方法 | `<i class="bi bi-robot"></i>` |

### Material Symbols（代替）

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined">
```

| 項目 | 内容 |
|------|------|
| アイコン数 | 3,000+ |
| 特徴 | Google風、ウェイト調整可能 |
| 使用方法 | `<span class="material-symbols-outlined">smart_toy</span>` |

**重要**: 1つのプレゼンでは1つのライブラリに統一すること。

---

## 2. 頻出アイコン（クイックリファレンス）

### 最重要アイコン

| 用途 | アイコン | クラス |
|------|---------|--------|
| AI・テクノロジー | 🤖 | `fa-robot` |
| アイデア・発想 | 💡 | `fa-lightbulb` |
| 成長・向上 | 📈 | `fa-arrow-trend-up` |
| 効率・スピード | 🚀 | `fa-rocket` |
| 目標・ターゲット | 🎯 | `fa-bullseye` |
| チーム・組織 | 👥 | `fa-users` |
| チェック・完了 | ✅ | `fa-circle-check` |
| 警告・注意 | ⚠️ | `fa-triangle-exclamation` |
| セキュリティ | 🛡️ | `fa-shield-halved` |
| データ・分析 | 📊 | `fa-chart-bar` |

---

## 3. カテゴリ別マッピング

### テクノロジー・IT

| キーワード | アイコン |
|-----------|---------|
| AI, 人工知能, 機械学習, ML | `fa-robot` |
| データ, 分析, 統計 | `fa-chart-bar` |
| クラウド, SaaS | `fa-cloud` |
| コード, 開発, プログラミング | `fa-code` |
| データベース, DB | `fa-database` |
| サーバー, インフラ | `fa-server` |
| ネットワーク, 通信 | `fa-network-wired` |
| API, 連携 | `fa-plug` |
| バグ, デバッグ | `fa-bug` |
| ターミナル, CLI | `fa-terminal` |
| Git, バージョン管理 | `fa-code-branch` |
| セキュリティ, 保護 | `fa-shield-halved` |
| 暗号化, 鍵 | `fa-key` |
| ダウンロード | `fa-download` |
| アップロード | `fa-upload` |
| 同期, 更新 | `fa-rotate` |

### ビジネス・経営

| キーワード | アイコン |
|-----------|---------|
| コスト, 費用, 予算 | `fa-coins` |
| 成長, 向上 | `fa-arrow-trend-up` |
| 下降, 減少 | `fa-arrow-trend-down` |
| 効率, 生産性 | `fa-rocket` |
| チーム, 組織 | `fa-users` |
| 目標, KPI | `fa-bullseye` |
| 戦略, 計画 | `fa-chess` |
| 会議, ミーティング | `fa-handshake` |
| 契約, 合意 | `fa-file-signature` |
| 売上, 収益 | `fa-sack-dollar` |
| 投資, 資金調達 | `fa-hand-holding-dollar` |
| 株価, マーケット | `fa-chart-line` |
| マーケティング | `fa-bullhorn` |
| 顧客, クライアント | `fa-user-tie` |
| パートナー, 提携 | `fa-handshake-simple` |
| スタートアップ, 起業 | `fa-lightbulb` |
| リスク, 懸念 | `fa-triangle-exclamation` |

### プロジェクト管理

| キーワード | アイコン |
|-----------|---------|
| プロジェクト, 案件 | `fa-diagram-project` |
| タスク, ToDo | `fa-list-check` |
| マイルストーン | `fa-flag` |
| デッドライン, 期限 | `fa-hourglass-half` |
| スケジュール, カレンダー | `fa-calendar-days` |
| ガントチャート | `fa-bars-progress` |
| 進捗, ステータス | `fa-spinner` |
| 完了, Done | `fa-circle-check` |
| 進行中 | `fa-play` |
| 保留, Pending | `fa-pause` |
| 高優先, 緊急 | `fa-fire` |
| リリース, デプロイ | `fa-rocket` |
| テスト, QA | `fa-vial` |
| 改善, 最適化 | `fa-wrench` |
| レビュー, 確認 | `fa-magnifying-glass` |
| 承認 | `fa-thumbs-up` |
| 却下 | `fa-thumbs-down` |

### コミュニケーション

| キーワード | アイコン |
|-----------|---------|
| メール | `fa-envelope` |
| チャット, メッセージ | `fa-comments` |
| ビデオ通話 | `fa-video` |
| 電話 | `fa-phone` |
| SNS | `fa-share-nodes` |
| 通知, アラート | `fa-bell` |
| いいね, Like | `fa-heart` |
| シェア, 共有 | `fa-share-from-square` |
| プレゼン | `fa-person-chalkboard` |

### ドキュメント・ファイル

| キーワード | アイコン |
|-----------|---------|
| ドキュメント, 文書 | `fa-file-lines` |
| PDF | `fa-file-pdf` |
| Excel | `fa-file-excel` |
| PowerPoint | `fa-file-powerpoint` |
| フォルダ | `fa-folder` |
| コピー | `fa-copy` |
| 削除, ゴミ箱 | `fa-trash` |
| 編集 | `fa-pen-to-square` |
| 保存 | `fa-floppy-disk` |
| 検索 | `fa-magnifying-glass` |
| 添付 | `fa-paperclip` |
| リンク | `fa-link` |
| ブックマーク | `fa-bookmark` |

### 一般・ユーティリティ

| キーワード | アイコン |
|-----------|---------|
| アイデア, ひらめき | `fa-lightbulb` |
| 時間, 時刻 | `fa-clock` |
| 検索 | `fa-magnifying-glass` |
| 設定, オプション | `fa-gear` |
| ホーム | `fa-house` |
| ユーザー | `fa-user` |
| チェック, OK | `fa-check` |
| バツ, NG | `fa-xmark` |
| プラス, 追加 | `fa-plus` |
| マイナス, 削除 | `fa-minus` |
| 情報, ヘルプ | `fa-circle-info` |
| 警告, 注意 | `fa-triangle-exclamation` |
| エラー | `fa-circle-exclamation` |
| 成功, 完了 | `fa-circle-check` |
| スタート, 開始 | `fa-play` |
| ストップ, 停止 | `fa-stop` |
| 更新, リフレッシュ | `fa-arrows-rotate` |
| ログイン | `fa-right-to-bracket` |
| ログアウト | `fa-right-from-bracket` |
| ロック | `fa-lock` |
| お気に入り | `fa-star` |

### 矢印・方向

| キーワード | アイコン |
|-----------|---------|
| 右矢印, 次へ | `fa-arrow-right` |
| 左矢印, 前へ | `fa-arrow-left` |
| 上矢印 | `fa-arrow-up` |
| 下矢印 | `fa-arrow-down` |
| 両方向 | `fa-arrows-left-right` |
| 回転, リフレッシュ | `fa-rotate` |
| 元に戻す | `fa-rotate-left` |
| やり直し | `fa-rotate-right` |
| 循環, サイクル | `fa-arrows-spin` |
| 外部リンク | `fa-arrow-up-right-from-square` |

### チャート・グラフ

| キーワード | アイコン |
|-----------|---------|
| 棒グラフ | `fa-chart-bar` |
| 折れ線グラフ | `fa-chart-line` |
| 円グラフ | `fa-chart-pie` |
| エリアチャート | `fa-chart-area` |
| ガントチャート | `fa-bars-progress` |
| ダッシュボード | `fa-gauge-high` |
| KPI, 指標 | `fa-bullseye` |
| トレンド | `fa-arrow-trend-up` |
| パーセント | `fa-percent` |
| テーブル | `fa-table` |
| ランキング | `fa-ranking-star` |

### デバイス・ハードウェア

| キーワード | アイコン |
|-----------|---------|
| パソコン, PC, デスクトップ | `fa-desktop` |
| ノートパソコン, ラップトップ | `fa-laptop` |
| スマートフォン, スマホ, モバイル | `fa-mobile-screen-button` |
| タブレット, iPad | `fa-tablet-screen-button` |
| プリンター, 印刷 | `fa-print` |
| キーボード, 入力 | `fa-keyboard` |
| マウス, クリック | `fa-computer-mouse` |
| モニター, ディスプレイ, 画面 | `fa-tv` |
| カメラ, 撮影, 写真 | `fa-camera` |
| マイク, 録音, 音声入力 | `fa-microphone` |
| ヘッドフォン, イヤホン | `fa-headphones` |
| スピーカー, 音声出力 | `fa-volume-high` |
| 電源, バッテリー, 充電 | `fa-battery-full` |
| SIMカード, 通信カード | `fa-sim-card` |
| SDカード, メモリーカード | `fa-sd-card` |

### 人事・HR・組織

| キーワード | アイコン |
|-----------|---------|
| 採用, リクルート, 求人 | `fa-user-plus` |
| 面接, 選考 | `fa-comments` |
| 履歴書, 職務経歴書 | `fa-file-lines` |
| 研修, トレーニング, 教育 | `fa-graduation-cap` |
| 評価, パフォーマンス | `fa-star` |
| 昇進, 昇格, キャリアアップ | `fa-stairs` |
| 退職, 離職 | `fa-door-open` |
| リモートワーク, 在宅勤務 | `fa-house-laptop` |
| 勤怠, 出退勤 | `fa-clock` |
| 有給, 休暇 | `fa-umbrella-beach` |
| 福利厚生, ベネフィット | `fa-gift` |
| ダイバーシティ, 多様性 | `fa-people-group` |
| 1on1, 面談 | `fa-user-group` |
| リーダーシップ, 統率力 | `fa-crown` |
| チームビルディング | `fa-users-gear` |
| 社員証, IDカード | `fa-id-card` |
| 名刺, ビジネスカード | `fa-address-card` |

### 教育・学習

| キーワード | アイコン |
|-----------|---------|
| 学習, 勉強, スタディ | `fa-book-open` |
| 教育, ティーチング | `fa-chalkboard-user` |
| 授業, レッスン, 講義 | `fa-person-chalkboard` |
| 卒業, 修了 | `fa-graduation-cap` |
| 試験, テスト, 検定 | `fa-file-circle-question` |
| 合格, パス | `fa-circle-check` |
| 不合格, フェイル | `fa-circle-xmark` |
| 成績, スコア, 点数 | `fa-ranking-star` |
| 教科書, テキスト | `fa-book` |
| ノート, メモ | `fa-note-sticky` |
| 研究, リサーチ | `fa-microscope` |
| 実験, ラボ | `fa-flask` |
| 資格, 認定 | `fa-certificate` |
| eラーニング, オンライン学習 | `fa-laptop-code` |
| メンター, 指導者 | `fa-user-graduate` |
| ワークショップ | `fa-hammer` |
| 知識, ナレッジ | `fa-brain` |

### 天気・自然

| キーワード | アイコン |
|-----------|---------|
| 晴れ, 太陽 | `fa-sun` |
| 曇り, 雲 | `fa-cloud` |
| 雨, レイン | `fa-cloud-rain` |
| 雪, スノー | `fa-snowflake` |
| 雷, サンダー | `fa-cloud-bolt` |
| 風, ウィンド | `fa-wind` |
| 温度, 気温 | `fa-temperature-half` |
| 傘, 雨具 | `fa-umbrella` |
| 月, 夜 | `fa-moon` |
| 星, 夜空 | `fa-star` |
| 山, マウンテン | `fa-mountain` |
| 海, 波 | `fa-water` |
| 森, 木, 自然 | `fa-tree` |
| 花, フラワー | `fa-spa` |
| 葉, リーフ, エコ | `fa-leaf` |
| 地球, 環境 | `fa-earth-americas` |
| リサイクル, 循環 | `fa-recycle` |
| 火, 炎 | `fa-fire` |
| 水, ウォーター | `fa-droplet` |

### 交通・移動

| キーワード | アイコン |
|-----------|---------|
| 車, 自動車, カー | `fa-car` |
| 電車, 列車, 鉄道 | `fa-train` |
| 地下鉄, メトロ | `fa-train-subway` |
| バス | `fa-bus` |
| タクシー | `fa-taxi` |
| 飛行機, 航空, フライト | `fa-plane` |
| 船, フェリー | `fa-ship` |
| 自転車, サイクル | `fa-bicycle` |
| バイク, オートバイ | `fa-motorcycle` |
| 徒歩, 歩く | `fa-person-walking` |
| トラック, 輸送 | `fa-truck` |
| 駐車場, パーキング | `fa-square-parking` |
| ガソリン, 燃料 | `fa-gas-pump` |
| 地図, マップ | `fa-map` |
| 位置, ロケーション, GPS | `fa-location-dot` |
| コンパス, 方位 | `fa-compass` |
| ナビ, ナビゲーション | `fa-route` |

### 医療・健康

| キーワード | アイコン |
|-----------|---------|
| 病院, 医療機関 | `fa-hospital` |
| 医者, ドクター, 医師 | `fa-user-doctor` |
| 看護師, ナース | `fa-user-nurse` |
| 診察, 診療 | `fa-stethoscope` |
| 薬, 薬品 | `fa-pills` |
| 注射, ワクチン | `fa-syringe` |
| 心臓, ハート | `fa-heart-pulse` |
| 脳, 神経 | `fa-brain` |
| 歯, 歯科 | `fa-tooth` |
| 血液, 検査 | `fa-vial` |
| DNA, 遺伝子 | `fa-dna` |
| ウイルス, 感染症 | `fa-virus` |
| マスク, 感染予防 | `fa-mask-face` |
| 体温, 熱 | `fa-thermometer` |
| 救急, 緊急 | `fa-truck-medical` |
| 車椅子, 介護 | `fa-wheelchair` |
| 健康, ヘルス | `fa-heart` |
| 運動, フィットネス | `fa-dumbbell` |

### 食事・飲料

| キーワード | アイコン |
|-----------|---------|
| 食事, フード | `fa-utensils` |
| レストラン, 飲食店 | `fa-utensils` |
| コーヒー, カフェ | `fa-mug-hot` |
| お茶, 紅茶 | `fa-mug-saucer` |
| ビール, アルコール | `fa-beer-mug-empty` |
| ワイン | `fa-wine-glass` |
| 水, ウォーター | `fa-bottle-water` |
| パン, ベーカリー | `fa-bread-slice` |
| ピザ | `fa-pizza-slice` |
| ハンバーガー | `fa-burger` |
| ケーキ, スイーツ | `fa-cake-candles` |
| アイスクリーム | `fa-ice-cream` |
| りんご, フルーツ | `fa-apple-whole` |
| 野菜 | `fa-carrot` |
| 魚, シーフード | `fa-fish` |
| キッチン, 調理 | `fa-kitchen-set` |

### ショッピング・買い物

| キーワード | アイコン |
|-----------|---------|
| ショッピング, 買い物 | `fa-bag-shopping` |
| カート, ショッピングカート | `fa-cart-shopping` |
| バスケット, かご | `fa-basket-shopping` |
| ストア, 店舗, ショップ | `fa-store` |
| ギフト, プレゼント | `fa-gift` |
| クーポン, 割引券 | `fa-ticket` |
| セール, バーゲン | `fa-percent` |
| レジ, 会計 | `fa-cash-register` |
| バーコード, スキャン | `fa-barcode` |
| タグ, 値札 | `fa-tag` |
| 配送, デリバリー | `fa-truck-fast` |
| 梱包, パッケージ | `fa-box` |
| 返品, 返却 | `fa-rotate-left` |
| レビュー, 評価 | `fa-star-half-stroke` |
| 新着, New | `fa-sparkles` |
| 人気, ベストセラー | `fa-fire` |

### 感情・表現

| キーワード | アイコン |
|-----------|---------|
| 笑顔, スマイル, 嬉しい | `fa-face-smile` |
| 大笑い, 爆笑 | `fa-face-laugh` |
| 泣く, 悲しい | `fa-face-sad-tear` |
| 怒り, 怒る | `fa-face-angry` |
| 驚き, びっくり | `fa-face-surprise` |
| 困惑, 困った | `fa-face-frown` |
| 愛, ラブ | `fa-heart` |
| グッド, いいね | `fa-thumbs-up` |
| バッド, だめ | `fa-thumbs-down` |
| 拍手, 称賛 | `fa-hands-clapping` |
| 握手, 合意 | `fa-handshake` |
| 祝い, パーティー | `fa-champagne-glasses` |
| トロフィー, 優勝 | `fa-trophy` |
| メダル, 表彰 | `fa-medal` |
| 王冠, クラウン, 一位 | `fa-crown` |

### セキュリティ・プライバシー

| キーワード | アイコン |
|-----------|---------|
| セキュリティ, 安全, 保護 | `fa-shield-halved` |
| ロック, 鍵, 施錠 | `fa-lock` |
| アンロック, 解錠 | `fa-lock-open` |
| 鍵, キー | `fa-key` |
| 指紋, 生体認証 | `fa-fingerprint` |
| 二段階認証, 2FA | `fa-mobile-screen` |
| 暗号化 | `fa-file-shield` |
| ファイアウォール | `fa-fire-flame-curved` |
| ウイルス対策 | `fa-shield-virus` |
| バックアップ | `fa-cloud-arrow-up` |
| プライバシー, 個人情報 | `fa-user-shield` |
| 匿名, シークレット | `fa-user-secret` |
| 監視, モニタリング | `fa-eye` |
| アラート, 警報 | `fa-bell` |
| 危険, ハザード | `fa-skull-crossbones` |
| 禁止, ブロック | `fa-ban` |
| VPN | `fa-network-wired` |

---

## 4. アイコンサイズ（CSS変数）

| 用途 | CSS変数 |
|------|---------|
| 大きいアイコン | `var(--fs-icon-lg)` |
| 中サイズアイコン | `var(--fs-icon-md)` |
| 小さいアイコン | `var(--fs-icon-sm)` |

---

## 5. アイコンラッパースタイル

```css
.icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--bg-dim);
}

.icon-wrapper i {
  font-size: var(--fs-icon-md);
  color: var(--wave-blue);
}

/* アクセントカラー */
.icon-wrapper.accent-pink i { color: var(--sakura-pink); }
.icon-wrapper.accent-aqua i { color: var(--wave-aqua); }
.icon-wrapper.accent-yellow i { color: var(--autumn-yellow); }
.icon-wrapper.accent-violet i { color: var(--spring-violet); }
```

---

## 6. 完成チェックリスト

- [ ] アイコンライブラリは統一されているか
- [ ] アイコンは内容を適切に表現しているか
- [ ] アイコンサイズはCSS変数を使用しているか
- [ ] アクセントカラーは意味に沿っているか
