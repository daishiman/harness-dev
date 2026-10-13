# elicit-question-bank — カテゴリ×platform で確認する論点の一覧

R2-interview / R3-reask / R4-reopen がセルへの問を設計するときの補助資料。カテゴリの正本は C04 taxonomy。ここは聞き漏れを確かめる論点の一覧 (チェックリスト) であり、問の文面の雛形でも、収集項目そのものの SSOT でもない。問の文面は `neutral-question-criteria.md` の N1-N4 に従う (この基準が本資料より上位)。

## 進め方の原則

- 未収集セルを対象に「質問→回答→仕様反映」を 1 turn として回す。
- **platform 横断の一括判断を優先**: 対象とするプラットフォームを先に確かめ、非対象を一括 `対象外` にすると turn 数を圧縮できる (approval_log に一括承認を記録し、各セルへ `approval_ref`)。
- 対象 platform だけ各カテゴリの要件を確定 (`確定` + qa_ref)。
- 1 invocation は最大 5 turn。超過は未完了保存 (resume)。

## platform スコープ確認 (最初に聞く)

- 対象とするプラットフォーム (Web / モバイル / タブレット / デスクトップ Windows / Linux / macOS)。
- 対象外とするプラットフォームとその理由 → 一括承認 (approval) で非対象列を `対象外` に。

## カテゴリ別 確認する論点 (対象 platform ごとに確定)

下表は問の文面ではなく、カテゴリごとに確認する論点の一覧である。次の順で使う。

1. 最初は開いた 1 問で聞いてよい (例: 「<カテゴリ>について <platform> で決まっていることを教えてください」)。開いた問が N4 に当たらない条件は `neutral-question-criteria.md` の「N4 と開いた問」が正本。
2. 回答に欠けた論点だけを、1 論点ずつ別の問で補う。
3. 表の論点を並べて 1 問で聞かない (例: 認証方式・認可・セッションをまとめて問う)。複数の決定を 1 問に束ねると N4 違反になり、R6 で誘導として検出される。
4. **論点が揃った turn** は、表の論点のうちそのセルで決めるものすべてに回答が得られた turn である (補いが要らなければ開いた問の turn、補ったなら最後に補った論点の turn)。それより前の turn (開いた問の turn を含む) は qa だけを記録する (ops なし)。論点が揃った turn で候補 `confirm` を組み立て (`qa_ref` は turn の `qa_id` で補完される)、同じ turn の ops で `confirm` に続けて `add-qa-ref` を置き、そのセルのために記録した残りの qa (開いた問の qa と、先に補った論点の qa) をすべて同じセルへ結ぶ。先の qa が前の invocation に記録されていても同じである (5 loop 上限で未確定のまま resume した場合)。再開側は、qa_log のうちどのセルの `qa_ref` / `qa_refs` にも現れない entry を挙げ、問の文面からそのセルのために記録したものを選んで結ぶ。結ばない qa は、必須情報の接地にも章の根拠にも数えられない (`spec-state-contract.md`)。
5. `confirm` を含む writer `apply` / `chunk` は `--required-info <required-info-catalog.json>` を付け、候補 state の接地検証が通った後だけ公開する。初回候補が未接地で拒否されたら、元 state の確定を変更せず、回答だけを蓄積する turn で足りない item を聞き、保留した confirm と参照接続を揃えて再試行する。旧 state の確定後に、収集ゲート (`validate-knowledge-graph.py --profile required-info --state <spec-state>`) の `ungrounded_blocking_items` に item が残ったときは、確定を戻さずに補う。残った item を 1 item ずつ別の問で聞き、その turn に `required_info_items` を付け、ops の `add-qa-ref` で、その item の `domain` (`required-info-catalog.json`) が指すカテゴリの確定セルへ結ぶ。確定済みの論点は問い直さないので、R2-interview 1.1 の「聞き直し」には当たらない。回答が確定の内容と食い違う (前提が崩れる) ときだけ R4-reopen へ回す。

| カテゴリ (id) | 確認する論点 |
|---|---|
| データベース (database) | データモデル / 永続化 / トランザクション境界 / スキーマ移行方針 |
| 認証(ログイン) (auth) | 認証方式 (OIDC / 独自など) / 認可 (RBAC など) / セッション / SSO / MFA |
| UI-UX (ui-ux) | 画面設計 / 操作フロー / アクセシビリティ (WCAG) / レスポンシブ要件 |
| セキュリティ (security) | 脅威モデル / 暗号化 / 入力検証 / 監査ログ / OWASP Top10 への対応 |
| インフラ (infrastructure) | 実行環境 / デプロイ / スケーリング / 監視 / CI-CD |
| バックエンド (backend) | サーバ構成 / API 契約 / ビジネスロジック / 非同期処理 |
| フロントエンド (frontend) | クライアント構成 / 状態管理 / レンダリング / ビルド |
| 保守運用管理 (maintenance-ops) | 運用手順 / 障害対応 / バックアップ / バージョン管理 / ドキュメント |

## 再質問 (R3-reask)

- 未確定セルへ「前回未回答の論点」を絞って再質問する。既に確定/対象外のセルの要件は聞き直さない (補う論点は確定前に聞き終える)。
- 5 loop 到達時: writer が `next_question` に次の未収集セルを指す文を保存して停止する (resume)。`next_question` は再開位置 (どのセルか) の目印で、利用者にそのまま見せる問ではない。再開時の問は本資料の論点と N1-N4 から作る。

## 再オープン (R4-reopen)

- 確定済みセルの前提が崩れたとき「なぜ再検討が必要か(根拠)」を確認し、reopen (要 reason) してから追加質問へ。
