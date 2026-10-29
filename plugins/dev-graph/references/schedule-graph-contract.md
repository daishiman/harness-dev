# C16 schedule graph 契約

## 目的と責務

C16 `schedule-graph.py` は canonical graph、C28 の Beads ready payload (`--ready-source bd-bridge` のとき)、
C27 lease snapshot を読み、実行候補と、候補にしなかった理由を報告する read-only コンポーネントである。
C28 の payload 投影・Beads mutation・parity manifest の生成規則は `execution-tracker-contract.md` を正本とし、
本書は C16 固有の分類、判定順序、候補被覆だけを所有する。

## 出力の区分

| key | 中身 |
|---|---|
| `ready_set` / `batches` | 推薦する feature と task。batch は `resource_scope` が重ならない組だけを束ね、`--max-parallel` を上限にする。 |
| `conflicts` | ready だったが active lease と同じ node か、その `resource_scope` と重なる node の id。 |
| `conflict_pairs` | 重なりの組と共有 path。`kind` は ready 同士の `ready_pair` か `lease`。 |
| `excluded` | selected かつ schedulable な node を ready にしなかった理由。 |
| `unmapped` | ready payload と graph の対応付けに失敗した entry。 |
| `selection_receipt` | 候補をその順に並べた理由 (`policy: mvp-first/v1`)。entry ごとに `mvp_fit`・`sort_rank`・`mvp_alignment` の目的/背景/根拠と、deferred の繰り延べ理由を載せる。`mvp_established` は載せた feature の direct task が全件 done かを graph 全体から決め、direct が 0 件なら null。 |

## excluded の reason

| reason | 意味と復旧 |
|---|---|
| `dependency_unsatisfied` | 未完了の依存がある。`blocking_depends_on` に推移的に辿った未完了 node と graph に無い依存を並べる。上流を完了してから再実行する。 |
| `ready_payload_entry_absent` | beads binding (または binding 未設定) の node に payload entry が無い。C28 の同期と parity manifest を作り直して再実行する。ready set へ推測で足さない。 |
| `beads_parity_stale_or_unconfirmed` | entry はあるが edge parity 未確認、または entry が見た status / `depends_on` が現 graph と一致しない。C28 同期後に再実行する。 |

## unmapped の reason

| reason | source | 意味と復旧 |
|---|---|---|
| `not_an_object` / `missing_external_ref` | `schedule-graph` | payload の item の形が不正。payload の生成元を直して再実行する。 |
| `graph_node_missing` | `schedule-graph` | payload が指す node が canonical graph に無い。C02 で復元するか、失効済みなら C28 で close する。 |
| C28 由来の reason | `bd-bridge` | C28 が ready から落とした `unmapped` / `conflicts` をそのまま引き継ぐ。C16 は判断せず見せるだけにする。 |

## 判定順序

1. `--scope` があれば、その node と `parent_feature` を辿って属する node だけを選ぶ。未知の scope は停止する。
2. `status=active`・`confirmation_status=confirmed`・`evaluation_status=pass`・`implementation_readiness.status=complete` をすべて満たす node だけを schedulable とし、それ以外は候補にも理由にも出さない。
3. 依存を評価する。P01 task は親 feature の `depends_on` も入口ゲートとして評価し、親が無ければ停止する。未充足なら `dependency_unsatisfied` を 1 件だけ記録し、payload 判定へ進まない。
4. bd-bridge mode では binding ごとに判定する。`github` / `none` は graph だけで ready、`beads` は entry・edge parity・status・`depends_on` (順序を無視して比較) がすべて一致するときだけ ready、binding 未設定は entry の有無だけで決める。それ以外の binding は解決前の値として停止する。
5. ready の node を active lease と照合し、重なるものを `conflicts` へ移す。`state` が `released` / `expired` の lease は無視し、`reserving` / `claimed` / `in_progress` / `claim_pending_local_repair` は `expires_at` を過ぎていれば無視する。時刻が不正か timezone を持たなければ停止する。
6. 残った候補を `mvp_alignment.mvp_fit` の rank (direct → enabling → 未設定 → deferred) で並べ、同 rank は node id の辞書順にする。rank は C28 が ready_set を見せる順と同じ定数 (`lib/bd_bridge_contracts.py` の `MVP_FIT_RANK`) を使う。enum 外の値や object でも null でもない `mvp_alignment` は未設定へ丸めず停止する。

## 被覆の不変条件

selected かつ schedulable な node は、`ready_set`・`excluded`・`conflicts` のどれか 1 つにだけ現れる。
候補が理由なしに消えることはない。`conflicts` は lease 由来の除外で、`excluded` の reason と混同しない。

## 鮮度と read-only

- ready payload に `parity_provenance.source_graph_digest` が付いていれば、現 graph の canonical digest
  (`build-parity-manifest.py` と同じ式) と比べ、一致しなければ stale として停止する。付いていなければ
  node 単位の parity 判定だけで決める。
- payload 内で同じ `external_ref` が 2 回現れたら停止する。どちらを信じたかが入力順で変わるため。
- graph・ready payload・lease snapshot を読み終えた後に再読込し、bytes が変わっていれば停止する。
  出力の `*_sha256_before` / `*_sha256_after` は同じ値になる。
