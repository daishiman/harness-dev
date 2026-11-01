# ローカルで利用する

このREADMEがあるプラグインルートを指定します。プラグイン本体は自己完結し、元のObsidianフォルダや一時フォルダを必要としません。個人の写真・ロゴ・参考画像を含むローカル用パッケージです。

## Claude Code

一時的に読み込む方法：

```bash
claude --plugin-dir /absolute/path/to/flyer-studio
```

起動した会話では、[README の入口](README.md#入口)（利用者が直接呼べる skill）のどれかを呼びます。迷ったら `/flyer-studio:run-intake-flyer` から始めます。プラグイン自体は `claude plugin validate /absolute/path/to/flyer-studio` と `python3 scripts/build-local-package.py --check` で検査できます。

## Codex / 両環境へ登録

ローカル導入キットを作ります。新しい出力先を指定してください。

```bash
python3 scripts/build-local-package.py --out /absolute/path/to/flyer-studio-kit
```

生成したキットを登録します。以下は利用者が導入するときに実行する操作で、このプラグインの作成・検査では実行しません。

```bash
codex plugin marketplace add /absolute/path/to/flyer-studio-kit
codex plugin add flyer-studio@flyer-studio-local
```

Claude Codeへ永続登録する場合：

```bash
claude plugin marketplace add /absolute/path/to/flyer-studio-kit
claude plugin install flyer-studio@flyer-studio-local
```

導入後の新しい会話で「Flyer Studioでチラシを作成」と伝えます。導入先のプラグインルートで `npm ci --ignore-scripts` と `python3 scripts/build-flyer.py doctor` を実行します。インストール先は製品側が管理するため、パスを推測せず、読み込んだSKILL.mdから解決します。

## 検査した範囲

JSON構文、Claude native validate、マニフェストの同一性、両製品向けローカルカタログと配布境界、実際のHTML/PDF/PNG描画と、QRを使う案件ではQR読取を検査します。利用者のグローバル登録・新規ログイン済みセッションでの実行は別の検査です。検証記録に実施/未実施を区別します。

## 参照した公式仕様

- [Claude Code プラグイン仕様](https://code.claude.com/docs/en/plugins-reference)：`.claude-plugin/plugin.json`、skills/agentsの配置、相対パス、validate。
- [OpenAI プラグインのパッケージ仕様](https://developers.openai.com/plugins/build/plugins)：`.codex-plugin/plugin.json`、skillsとローカルカタログ。

両製品向けのファイルを同梱し、同じ分析/評価/制作データと描画処理を使います。生成ツールの可用性、フォント、ブラウザ環境はdoctorと制作時の確認で扱います。
