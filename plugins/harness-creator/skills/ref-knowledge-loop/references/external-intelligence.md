# 外部知能 runtime 契約

## 目的と因果境界

外部知能は、過去に支払った調査・失敗・判断コストを次の Codex / Claude Code 実行へ引き継ぐ仕組みであり、モデル学習やプロンプトキャッシュそのものではない。直接狙うのは再検索・同一失敗・説明のやり直しの削減である。

ユーザー提供の X 記事には「約4,835万入力 token の約98.7%が再利用され、週間表示が1%変化」という観測値があるが、外部知能がその cache 比率や quota 表示を生んだ因果は記事自身も証明していない。本ハーネスは token/quota 削減を保証せず、次を直接 KPI とする。

- 同一・高類似観測が新規 entry にならず統合された割合
- 別文脈で役立った `helpful reuse` 件数
- 再検索・同一失敗を回避した証拠
- 独立証拠と反証条件を備えて promoted された割合

OpenAI / Anthropic の prompt cache は「変わらない prefix」の再利用である。常時コンテキストを短く安定させ、必要な知見だけ後段で取得する設計は cache を壊しにくいが、外部知能とは別レイヤーとして扱う。

## 採用した構造

`decision-os-v13-loopkit` から転用するのは、薄い入口・必要時だけ厚い記憶へ戻ること、1観測を即ルール化しないこと、agent-neutral core と薄い adapter、証拠付き状態遷移、監査可能な履歴である。作者環境固有の巨大 OS、営業文、hard-coded adapter、全 maturity model は取り込まない。

| 層 | 正本 | 書込み方針 |
|---|---|---|
| curated seed | 配布物の `knowledge/` / harness の `knowledge/`, `lessons-learned/` | version-control review を通った著作/昇格のみ。hook は書かない |
| runtime observations | `build-external-intelligence.py` の event log | plugin package 外。Codex/Claude 共通 |
| thin retrieval | runtime `index.json` | summary と count のみ。観測本文は含めない |
| thick detail | runtime `entries/<id>.json` | `show --id` で必要時だけ読む |

project scope の既定は Git common dir の `harness-creator/external-intelligence/v1`（worktree 間共有）、非 Git は `<project>/.harness/external-intelligence/v1`。user scope は `HARNESS_INTELLIGENCE_HOME`、plugin data、XDG/OS state の順に解決する。version 付き plugin cache/install directory へ runtime state を保存しない。

## 状態遷移と重複規則

```text
observation --独立 context/evidence source が各2件--> candidate
candidate --別 context/evidence source で helpful reuse--> verified
verified --承認者+承認証跡 + target + falsifier + rollback--> promoted
observation/candidate/verified/promoted --無効・陳腐化の理由--> superseded
```

- Unicode NFKC/casefold と punctuation collapse で canonicalize し、同一 fingerprint と高類似は同じ entry へ統合する。
- 同じ `context-id` + `evidence-ref` は Codex/Claude の双方から来ても同一 observation として数える。成熟度に寄与する「独立証拠」は、毎回異なる ID ではなく `evidence-source` （issue、別テスト系、別調査元など）の異なりで数える。
- 曖昧な類似は対話 CLI では exit 3 と候補を返し、`--merge-with` または `--force-new --distinct-reason` を要求する。無人 hook は観測を捨てず `pending_duplicate` として隔離保存し、解決まで candidate 以上へ進めない。解決時は detail の候補を確認し、同一なら元の payload を `--merge-with` で再記録後に pending entry を `supersede`、別物なら pending entry を理由付き `supersede` して `--force-new --distinct-reason` で再記録する。
- promoted rule には承認者と承認証跡、反証条件、rollback を残す。event log は SHA-256 hash chain で、`search` / `show` も authoritative events と index/detail の不一致時は fail-closed にする。`verify --repair` だけが派生ファイルを再構成する。
- 誤観測や陳腐化は物理削除せず `supersede --reason` で監査履歴を残し、検索対象から除外する。`superseded` は終端であり、merge・reuse・promote で復活させない。

## 運用コマンド

```bash
python3 scripts/build-external-intelligence.py --agent codex search --query "<task>" --limit 5
python3 scripts/build-external-intelligence.py --agent claude show --id <entry-id>
python3 scripts/build-external-intelligence.py --agent codex capture --title "..." --summary "..." --rule "..." --context-id "..." --evidence-ref "..." --evidence-source "issue:<independent-source>"
python3 scripts/build-external-intelligence.py --agent claude reuse --id <entry-id> --context-id "..." --evidence-ref "..." --evidence-source "test-suite:<independent-source>" --outcome helpful
python3 scripts/build-external-intelligence.py promote --id <entry-id> --target "..." --owner-approved --approved-by "<owner-id>" --approval-evidence-ref "<review-artifact>" --falsifier "..." --rollback "..."
python3 scripts/build-external-intelligence.py supersede --id <entry-id> --reason "..."
python3 scripts/build-external-intelligence.py verify
python3 scripts/build-external-intelligence.py metrics
```

`auto-record-lesson.py` は両製品の PostToolUse payload を同じ `capture` 契約へ変換する fail-soft adapter である。自動記録は再現可能な失敗観測だけを対象にし、正規化 failure signature を同一性に、個別 path/command を証拠に分離する。成功知見の抽出や promotion は自動化しない。

通常のartifact生成runtimeは上記の生engine CLIをproviderごとに直接組み立てず、[`external-intelligence-runtime-contract.md`](external-intelligence-runtime-contract.md) の共通 `search → adopt → finish` adapterを使う。この経路はproject scopeに限定し、上位5件・score threshold・summary/detail byte capを機械強制する。選択IDだけをdetail取得し、採用時にreuse、終了時にcapture最大1件を記録する。memory未生成・破損・timeoutはwarningとし、artifact生成を止めない。

## 長期運用境界

v1 は「改竄しない hash-chain event + 再生成可能な projection」を優先する。`metrics` で event 数・容量・観測統合率・helpful reuse・promotion を定期確認し、10,000 events または 64 MiB への到達を delta event/checkpoint/archive 方式の再監査 trigger とする。これは prompt cache や quota の代理指標ではない。unhelpful reuse や反証を得た promoted entry は自動削除せず、承認者が `supersede` して監査履歴を保つ。

## 出典

- OpenAI Prompt Caching: <https://developers.openai.com/api/docs/guides/prompt-caching>
- OpenAI Codex Hooks: <https://developers.openai.com/codex/hooks.md>
- Anthropic Claude Code memory: <https://code.claude.com/docs/en/memory>
- Anthropic Claude Code prompt caching: <https://code.claude.com/docs/en/prompt-caching>
- Decision OS V13 Loopkit: <https://github.com/shin4141/decision-os-v13-loopkit>（分析時 commit `be5286b332c37182d686bcc2dc9068fd22f902ed`）
