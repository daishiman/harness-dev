# eval-log/guide-doc-generator — 記録の出所

このディレクトリは `run-handout-build` の実走が残したログを置く。規約を書く場所ではない。
規約の正本は `plugins/guide-doc-generator/skills/run-handout-build/SKILL.md` にある。

## run-handout-build-intermediate.jsonl は現行規約より前の記録である

この jsonl の 3 行は、`SKILL.md#ゴールシーク検証` が `drift_signal` の値域と `iteration`
キーを要求するようになる**前**の run が書いたものである。したがって現行の検証を適用すると
落ちる。

```
drift_signal: "none"   -> 正本 enum (initial/aligned/compressing/stagnant/widening/oscillating) の外
iteration              -> このキーが無く、代わりに loop を持つ
```

**遡及して書き換えていない。** 3 行はいずれも非空の `delta_from_original` を持つので
`aligned` は事実に反し、正しい値を後から推定して埋めるのは記録の捏造にあたる。落ちること自体が
「規約が変わり、この記録はその前のものである」という事実の正しい表示である。

現行規約下の新しい run はこのファイルへ追記せず、別ファイルとして始めること。混在した瞬間、
どの行がどの規約下で書かれたかが読めなくなる。

## run-handout-build-progress.json も同じ世代の記録である

`SKILL.md#ゴールシーク配線` は progress に `build_stage` を記録するよう定めているが、この
ファイルにそのキーは無く、`checklist` の各要素も正本 schema の `{id,text,status}` 形ではなく
`{item,status,evidence}` の独自形である。同じく現行規約より前の記録として扱う。

なお `### ゴールシーク検証` の検証ブロックは progress.json を読まない。上の不整合が機械的に
検出されないのはこのためである。
