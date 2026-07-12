# 公式ソース判定カタログ (R2 補助資料)

> R2-fetch が「公式 publisher / official_host」を見極めるための指針集。網羅表ではなく判定基準 + 代表例。
> 最終的な現行版の意味判定は C08 (`system-spec-doc-freshness-auditor`) が公式サイト再照合で担う。

## 公式 host の判定基準

1. **正規ドメイン優先**: プロジェクトが公式に運用するドメイン、または公式 docs サブドメインを最優先する。
2. **ホスティング上の公式**: GitHub / Read the Docs / npm 等の上でも、その project の **公式 org / 公式リポジトリ / 公式パッケージ** なら公式扱い。第三者アカウントの複製・解説は非公式。
3. **非公式の除外**: 個人ブログ、まとめ記事、Q&A、ミラーサイト、AI 生成の要約サイトは採らない。
4. **一意性**: 公式 host を一意に特定できないときは「未取得 (要確認)」に倒し、非公式で穴埋めしない。

## version / last_updated の取り方

- 安定版のバージョン番号が明示される技術は `version` (例 `19.0`, `16.4`) を記録する。
- 版が数値で表されない/ローリング更新のドキュメントは、ページの **最終更新日** を `last_updated` (ISO 日付) に記録する。
- どちらか一方を必ず得る (両欠落は `validate-source-citation.py` で FAIL)。

## 代表例 (公式 host の目安)

| 種別 | 対象例 (target_id) | official_publisher | official_host の目安 |
|---|---|---|---|
| フレームワーク | react | Meta | react.dev |
| フレームワーク | nextjs | Vercel | nextjs.org |
| 言語ランタイム | node | OpenJS Foundation | nodejs.org |
| データベース | postgres | PostgreSQL Global Development Group | postgresql.org |
| データベース | mysql | Oracle | dev.mysql.com |
| Web サーバ | nginx | F5/NGINX | nginx.org |
| コンテナ基盤 | kubernetes | CNCF | kubernetes.io |
| クラウド | aws-s3 | Amazon Web Services | docs.aws.amazon.com |
| 認証 | oauth2 | IETF | datatracker.ietf.org |

> 上表は目安であり固定辞書ではない。実際の `official_host` は R2 が WebSearch で都度確認し、`source_url` は必ずその host 配下のページにする。
