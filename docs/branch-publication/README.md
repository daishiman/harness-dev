# 元ブランチの全残存差分

対象は `devgraph/package-artifacts-and-feature-promotion` の元HEAD `8c1eb6c8` と、その作業ツリーに残っていた全変更。guide関連だけに限定せず、[全1,440項目の対応表](manifest.json)を作った。

## 反映した実装

| 対象 | 統合内容 |
|---|---|
| dev-graph | materialize、confirm-feature、link-beads、planned_features。mainのparity provenance・MVP順位・lifecycleを保持 |
| UBM | 3つのチェックシートと継承・移行・検査、Codexのskills領域への書込許可。mainの相談・feedback修正を保持 |
| harness-creator / governance lint | JSON compositionの構造・型・依存・版の検査と、動的なプラグイン集合の照合 |
| system-briefing-book | 画像内の番号を押して説明へ移動する機能。元の未公開commit11ファイルを統合 |
| guide-doc-generator | 前段でプラグイン・実資料・全証跡を反映済み。[全資料の入口](../guide-doc-generator-delivery/README.md) |
| flyer-studio | mainの新版を維持。古い元コピーで戻さず、旧ソース・素材42件・検証85件・計画25件をそのまま保存 |

版・marketplace・fingerprintは正規release writerで整合させた。元ブランチの古い採番値を新しいmainへ上書きしていない。元のファイル内容とモードも保存した。

## 全ての元データを確認・復元する

`manifest.json` の `all_source_changes` は全status項目を列挙し、各項目の元SHA・反映先・判断・元版保存先を示す。`unaccounted_count=0` は、対応先が不明な元変更が0件という意味であり、未実施の検証を成功扱いするものではない。

```bash
# このパッケージの元版362件を検証する
python3 docs/branch-publication/restore-source.py --verify

# 空のcheckout外へ全て復元する。現在のコードは上書きしない
python3 docs/branch-publication/restore-source.py --out /tmp/harness-branch-source-restored

# guide資料と証跡の1,108件は別の対応表に保存済み
python3 docs/guide-doc-generator-delivery/restore-evidence.py --verify
```

`source-evidence/` の各ZIPは、元ファイルを `payload` として保持する。同じ内容の重複を避け、SHA256・バイト数・モードを検証してから元のパスへ復元する。元の未公開commitの内容は `committed-before-worktree/`、未commitの元版は `worktree/` に復元される。

過去の検証記録は当時の版に対する証拠として保持し、新版のPASSへ転用しない。依存物・自動生成キャッシュ・OSメタデータ・Dolt内部DBはGitへ混在させない。Beadsの更新は正規bridgeを使用し、通常taskの新規昇格が未対応の箇所はdraftを維持して、既存の`harness-86kh`へscope拡張を記録して追跡する。

## 仕様と検証

- [統合仕様](../../specs/branch-publication.md)
- [責務設計](../../architecture/branch-publication.md)
- [機能の整理](../../features/branch-publication.md)
- [タスク契約](../../tasks/branch-remaining-publication.md)
- [仕様影響の受領書](../../system-spec/branch-publication/spec-impact-receipt.json)
- [公開統合の検証記録](publication-receipt.json)

実走の追加範囲はMVPの予算と別に記録する。未実施・旧証跡のstale・環境セットアップ失敗を、PASSに読み替えない。
