# 今回の資料・証跡一式

前回のPRに未収録だった実資料・素材・改善前資料・全レビュー記録・画面キャプチャ・中間成果物を収録した。内容の一覧は [manifest.json](manifest.json) が正本。

## 最終資料を見る

[改善済みHTML](handout/2026-10-30_Claude-Codeサブエージェント-勉強会資料/handout.html)を、clone後にブラウザで開く。画像を内包した単一HTMLで、外部サービスの起動は不要。同じフォルダに構成JSON・素材・選定記録・案内がある。

## レビュー記録を見る

- [30思考法の検証・改善記録](reviews/run-handout-build/elegant-review/20261031-html-route-review/)
- [実資料の改善・表示検査記録](reviews/handout-improvement-20261031/)
- [全画面キャプチャ](reviews/handout-improvement-20261031/screens/)
- [今回の全件照合結果](../guide-doc-generator-review/completeness-receipt.json)

同じ内容の重複ファイルは一度だけ保存し、対応表から全ての元パスへ復元できる。最終資料と読めるレビュー本文・JSON・キャプチャは通常ファイル、過去のプラグイン全体スナップショットや大きい中間成果物は `evidence/` のZIPに格納した。各ZIPには元ファイルそのものが `payload` として入っている。

## 全件を検証・復元する

リポジトリのルートから実行する。Python標準ライブラリだけで動く。

```bash
python3 docs/guide-doc-generator-delivery/restore-evidence.py --verify
python3 docs/guide-doc-generator-delivery/restore-evidence.py --out /tmp/guide-doc-complete-restored
```

復元先は空のディレクトリを指定する。過去のテストコードも含むため、復元先はこのcheckoutの外に置く。上書きは行わない。

| 名前空間 | 内容 |
|---|---|
| `handout/` | 利用者指定の資料フォルダ全体。改善前バックアップも含む |
| `harness/` | 元作業ツリーに残っていた今回の全未収録証跡 |
| `review-input/` | 最終レビューで置換した元の入力版。稼働版へ戻すものではない |

元ファイルのSHA256・バイト数・モードを照合してから復元する。コードと設計書752ファイルの照合結果も `code_inventory` に含めている。16ファイルの差は、前回の最終レビューで行った修正や採番であり、元の古い版へ戻さず、その入力版も履歴として収録した。

自動生成キャッシュ、OSメタデータ、一時ロック、無関係な他機能の既存差分は収録対象にしない。今回のdev-graph設定・graph・受領書・テンプレートは `.dev-graph/` に追跡済み。個々のファイルが100MBを超えないことも確認した。
