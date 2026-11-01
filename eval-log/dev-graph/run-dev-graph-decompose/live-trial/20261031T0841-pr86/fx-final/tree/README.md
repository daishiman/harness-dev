# gm4b-render

## Beads の代わり (読取り専用)

この fixture の Beads は `tools/fake-bd.py` だけです。実在の bd と Beads の DB には接続しません。

- `bd version` と `bd where --json` の 2 つにだけ答えます (`bd-bridge.py` が Beads の操作の前に確かめる読取り)。
- それ以外の呼出し (create・dep・show・update・close・ready など) はすべて拒否し、何も出さずに exit 4 で終わります。この fixture から Beads の issue や edge は作れません。
- 呼出しは答えたものも拒否したものも、すべて fixture の root の `fake-bd-calls.jsonl` に 1 行ずつ記録されます。
- `bd-bridge.py` に使わせるには、呼出しの環境変数に `DEV_GRAPH_BD=<この fixture の root>/tools/fake-bd.py` を付けます。
