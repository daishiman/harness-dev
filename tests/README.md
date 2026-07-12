# tests/ 配置と命名規則

中央 pytest (`python3 -m pytest tests/ -q`) が一括収集する回帰テスト群。CI は
`harness-creator-kit-ci.yml` 機構A がこのディレクトリを丸ごと実行する (plugin 同梱テストは
機構B の per-plugin 実行)。

## ディレクトリ (対象ドメイン別)

| ディレクトリ | 対象 |
| --- | --- |
| `tests/` 直下 | 横断的な統合・整合テスト (coverage 整合 / discovery / SSOT parity 等) |
| `tests/scripts-root/` | repo-root `scripts/` 配下スクリプトの機能テスト |
| `tests/scripts-plugins/` | `plugins/<plugin>/**/scripts/` 配下スクリプトの機能テスト |
| `tests/criteria/` | feedback_contract criteria の検証テスト |

> 旧 `tests/scripts`〜`tests/scripts4` は生成ウェーブ (harness-coverage backfill の
> 回次) ごとの番号ディレクトリで、対象ドメインと無関係だったため 2026-07-02 に
> 上記2ディレクトリへ再ソートした。回次の痕跡はファイル名サフィックスに残る。

## ファイル命名

```
test_<target>__<script>[_<wave>].py
```

- `<target>`: `root` (repo-root scripts/) / `scripts` (同上・旧表記) /
  `<plugin名>` (ハイフンは underscore に置換。例: `skill_governance_lint`)
- `<script>`: 対象スクリプト名 (ハイフンは underscore に置換)
- `<wave>`: 同一対象への追加ウェーブ分のみ `_s2` / `_r2` / `_r3` / `_r4` で衝突回避
- 区切りは **ダブルアンダースコア** (`__`)。basename は tests/ 全体で一意にする
  (pytest の import mode 制約。`__init__.py` を置かない運用のため)

## 規約

- テストは対象スクリプトを `importlib` でロードし、CLI 契約は `subprocess` で検証する
- network/secret 系は monkeypatch で副作用遮断 (fail-closed 経路も genuine に踏む)
- 一時ファイルは `tmp_path` fixture。repo 内 fixture を書き換えるテストは禁止
  (skill-intake fixture 汚染の既知問題を再生産しない)
