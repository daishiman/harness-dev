# 挑戦宣言の引き継ぎ契約

完了・保留・中止の状態を親コンテキストが記録する正本。提出用本文の正本は `challenge-format.md`。

## 置き場

`SKILL.md` の `goal_seek.handoff` を、呼出元のプロジェクトルートから絶対パスへ解決する。Claude Codeでは `CLAUDE_PROJECT_DIR`、Codexではホストから渡されたプロジェクトルートを使う。作業ディレクトリから推測せず、未解決なら記録せず理由を伝える。

## 形

```json
{
  "schema_version": 1,
  "status": "pending",
  "declared_on": "YYYY-MM-DD",
  "original_goal": "C0で固定した非空文字列",
  "iteration": 1,
  "confirmed": {},
  "open_issues": [{"field": "purpose", "missing": ["未確定の要素"], "resume_when": "再開に必要な情報"}],
  "draft_path": null,
  "saved_path": null,
  "validation": {"draft": null, "saved": null, "anchor": null}
}
```

- `status`: `completed` / `pending` / `cancelled` / `failed`。`iteration`はC6提示回数（提示前の中断は0、初回1、最大3）。
- `confirmed`と`open_issues[*].field`は `question-map.md` の「欄とfieldの対応」のキーを使う。保留のままなら未確定要素と再開条件を残し、vaultへ未検証ファイルを書かない。
- パスは解決済みの絶対パスかnull。`validation`の受領書は対象パス・終了コード・検査出力を持ち、未実施ならnull。
- `completed`には提出用本文の了承、保存後検査とアンカー検査の終了コード0、非nullの`saved_path`が必要。他の状態を完了扱いにしない。
