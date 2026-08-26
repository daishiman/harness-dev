# deck-principles consumer bootstrap

資料作成の大原則を consumer へ届ける共通契約。各 agent prompt は次の宣言と
consumer 固有の取得責務だけを持ち、本節の規則を複製しない。

```html
<!-- deck-principles-consumer: <consumer-id>; run-by: <agent|orchestrator> -->
```

## 取得と受け渡し

- `run-by: agent`: 作業開始前に
  `python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/select-deck-principles.py" --consumer <consumer-id> --format json`
  を 1 回実行し、返却された selection を判断軸へ加える。
- `run-by: orchestrator`: 起動側が同じ selector を `--format json` で Task 起動直前に実行し、返却された
  tool-neutral な selection envelope を task brief へ載せる。agent は envelope がなければ
  作業を始めず、起動側へ差し戻す。
- consumer、選択条件、pin、実行主体の正本は `binding.json`。返却件数と内訳は
  selector の実出力から導出し、prompt や SKILL.md に固定値を写さない。
- checklist consumer は通常の selection envelope ではなく checklist 用の返却型を受ける。

## 全 consumer 共通の適用規則

- `principles.json` を直接読まず、selector が返した原則だけを使う。原則本文・閾値を
  promptへ転記しない。
- 原則は既存の plugin 固有 reference を置き換えず、判断軸として追加する。衝突時は
  plugin 固有 reference を優先する。
- `rule` と selection envelope は PowerPoint、Google Slides、HTML に共通の
  tool-neutral 契約とする。製品固有の操作は `tool_intent` を各 tool adapter が解釈し、
  共通規範へ混ぜない。
- pt 等の投影・印刷向け閾値を HTML の実値へ直写しない。HTML は
  `../unit-system.md` と各描画 token の正本に従う。
