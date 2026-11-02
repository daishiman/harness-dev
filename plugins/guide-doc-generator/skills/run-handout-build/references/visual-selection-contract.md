# 図解選定の検討と実配置を結ぶ契約

選定手順は `config/handout-visual-policy.json#diagram_selection` を正本とする。
本契約は、選定を飛ばして長文を返す経路と、検討だけして部品へ配置しない経路を防ぐ。
図種の候補は開いており、この記録でカタログ外の表現も採用できる。

## C05が返す記録

既存の戻り値 `decision_log` 配列に `kind: "visual-selection"` の項目を入れる。
本編の情報単位ごとに作り、1件で複数の部品を担当してもよい。先頭の場面画像を指す
記録だけで後続の説明を検討済みとしない。原文コピーのB11はコピー用途として扱う。
他の既存の設計判断は同じ配列に残してよい。

同じ読者の問いに答える図・結論の短文・補足・導線は1記録へまとめ、その部品を全て
`target_part_ids` へ載せてよい。自明な部品ごとに形式的な比較を増やさない。
候補比較はその情報単位の表現判断に対して行い、図の説明を別の文章へ再掲しない。

```json
{
  "kind": "visual-selection",
  "section_id": "request",
  "source_excerpt": "依頼を送ると担当が結果を返す",
  "reader_question": "誰が何を受け渡すか",
  "relations": "主体間の受け渡しと時間順序",
  "candidates": [
    {"form": "sequence", "reason": "主体と順序を同時に追える"},
    {"form": "flow", "reason": "順序は分かるが担当を追いにくい"}
  ],
  "chosen": "sequence",
  "mode": "diagram",
  "target_part_ids": ["request-diagram"],
  "reason": "受け渡しが判断の中心だから",
  "preserved_facts": ["依頼を送る", "結果を返す"],
  "replaced_content": ["受け渡しを説明する段落"]
}
```

`chosen` と `relations` は自由記述。`mode` だけを `diagram / image / part / text`
に制限する。図を不採用にした場合も、表・カード・短い文などとの候補比較と具体的な
理由を書く。全件を図へする必要はない。`target_part_ids` は実配置済みの部品を指す。
原文の引用と保持した意味は根拠であり、図の全ラベルを別の本文へ再掲する指示ではない。
`replaced_content` は追加の情報なら空配列を許す。

## C01/R2が保存・検査する証跡

`--normalize` 後の構成に対し、`validate-visual-selection.py --config <config> --digest`
の出力を `config_sha256`、C05の戻り値を `decision_log` としてJSONへ保存する。
保存先は構成データと並ぶ `<config-path>.visual-selection.json`。writerは親C01。
この証跡を構成データの未定義フィールドへ埋め込まない。

```bash
python3 "$PLUGIN_ROOT/scripts/validate-visual-selection.py" \
  --config <normalized-config.json> --decisions <normalized-config.json.visual-selection.json>
```

新規設計では、この検査のexit0をG1の構成確定に含める。欠落なら該当する節と部品を
C05へ戻す。正規化で新たな部品が生じた場合も、その部品を含む選定記録をC05から回収する。
親が意味判断を代作して埋めない。変更後は旧ハッシュを再利用しない。

納品時はC19の `--place-config` を使う。構成の隣に正しい選定証跡があれば、C19が検査し、
納品先の `handout-config.json.visual-selection.json` へバイト同一で複製する。C01は証跡の
writer、C19は複製のwriterである。古い・不正な証跡は配置前に差し戻し、ハッシュだけを
書き換えて通さない。証跡の無い既存構成は、下記の再生成経路を保つ。

検証済み構成を再生成する `config_given` で既存の証跡が無い場合は、設計を捏造せず
選定検査を `not-run: 既存構成の再生成` と報告してレンダリングする。利用者から内容改善を
求められたときに変更した情報単位の選定を実行する。

この検査が保証するのは検討漏れ・候補比較の欠落・部品参照・媒体一致・構成ハッシュの
整合である。原文の関係を正しく読んだか、候補が最適か、見た目が読めるかは保証しない。
意味と見た目の確認は既存の可読性レビューで別に行う。
