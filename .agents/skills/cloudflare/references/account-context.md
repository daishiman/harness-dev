# Account文脈の自動検出

このreferenceは、Cloudflare作業の対象Accountをプロジェクトごとに安全に確定するためのcontrol planeである。特定のrepository、組織、利用者、固定Accountを前提にしない。Wrangler CLIの具体的なcommandとversion差分は`wrangler` Skillへ委譲する。

## 利用者へ見せる最初の案内

説明を求めず、次の一文で開始してread-only調査へ進む。

> このプロジェクトで使うCloudflare環境をこちらで確認します。選択が必要な場合だけ、最後に番号を1つ伺います。

ログインが必要な場合も、利用者には「Cloudflareのログイン画面を開きます。完了したらこの画面へ戻ってください」とだけ案内する。token、secret、Account IDをチャットへ貼るよう求めない。

## 自動検出

次を順に行い、利用者へ途中の用語説明や確認を求めない。

1. **プロジェクトを調べる。** 適用される`AGENTS.md`、lockfile、`wrangler.json` / `wrangler.jsonc` / `wrangler.toml`、IaC、deploy workflowから、Worker名、Pages project名、D1/R2/KV等のbinding名と既存resource識別子を内部で収集する。`data/`、`.dev.vars`、secret file、credential storeは読まない。
2. **Account候補を列挙する。** `wrangler` Skillのread-only手順で、現在のdirectory-bound auth profileとアクセス可能なAccountを取得する。CLIのraw出力は内部でcaptureし、利用者やagentの通常出力へ流す前に完全なAccount IDを除去する。
3. **既存resourceの所有先を照合する。** 検出した製品に関係するread-only list/getだけを各候補で実行し、Worker、Pages、D1、R2等の名前・bindingがどのAccountに存在するか調べる。無関係な全製品を走査しない。create/update/delete/deployは行わない。
4. **チーム用Accountを判定する。** Account membership、既存の組織所有resource、既存CIのscopeなどの客観的根拠を使う。表示名だけでteam/personalを推測しない。Cloudflareの「Account」を料金plan名と混同しない。

完全なAccount IDが既存設定やCLI応答に含まれていても、照合中のprocess memoryだけで扱う。tool output、temporary file、project file、chat、screenshot、最終報告へ書かない。

## 自動選択規則

優先順位は次のとおり。

1. 既存project resourceの所有Accountが1つに定まるなら、自動選択する。
2. resourceが複数Accountへ分散しているなら自動選択しない。重複作成せず、候補ごとの一致resourceを示して移行を別taskに分ける。
3. resourceがまだ存在しない新規projectでは、客観的に確認できたチーム用Accountが1つなら自動選択する。
4. チーム用とpersonalが各1つで、既存所有先がない場合はチーム用を自動選択する。personalは利用者が明示した場合だけ使う。
5. 同順位の候補が複数残る場合だけ番号選択にする。単一候補について確認質問をしない。

### 選定modeの契約

選定結果は次の3値で後続Skillへ渡す。

| mode | 使う条件 | 表示 |
|---|---|---|
| `existing` | 既存resourceの所有先を優先して選んだ | 「既存resourceの所有先」 |
| `team` | resourceがない新規projectで、客観的に確認できたチーム用Accountを選んだ | 「チーム用」 |
| `personal` | resourceがない新規projectで、利用者がpersonalを明示選択した | 「個人用」 |

`existing`ではteam/personalを推測・断定しない。Account表示名が個人名や組織名に見えてもmodeを変更しない。新規projectだけが`team`既定の対象である。

番号選択は次の形に限定する。完全なAccount IDやtokenの一部は表示しない。

```text
このプロジェクトで使える環境が複数見つかりました。番号を1つ選んでください。
1. ○○チーム — チーム用（推奨）— 既存: Worker「example」
2. 個人用 — personal — 既存resourceなし
```

利用者にAccount名の入力、IDのコピー、Cloudflare用語の説明を求めない。番号が返ったら再質問せず続行する。

## プロジェクト単位での安全な保持

選択後は、利用中のWranglerが対応していればnamed auth profileをproject directoryへbindする。profileの作成・有効化方法と対応versionは`wrangler` Skillで公式docsを再取得して決める。profile名はproject slugを基にし、tokenやAccount IDを含めない。

- auth profileには対象Accountだけを許可し、別projectのprofileを流用しない。
- profile利用時も、対応するAccountを内部で再照合してからmutationする。
- profileを使えない環境では選択をsession memoryだけに保持し、project fileへ完全なAccount IDを書かない。次のsessionでは再検出する。
- CI/CDのAccount IDやAPI tokenは`ci-cd-pipeline`へ委譲し、CI providerのsecret storeからだけ注入する。repository、生成ドキュメント、command argument、ログへ値を書かない。
- 既存`wrangler`設定に完全なAccount IDがある場合は値を増殖させない。利用者の明示依頼なしに削除・移動もせず、内部照合だけに使う。

mutation直前に、選択したprofile、既存resource所有先、対象製品が同じAccount文脈を示すことを再確認する。不一致なら作成やdeployを行わず停止する。

## 専用Skillへ渡す情報

委譲先には次だけを渡す。

- Account表示名
- 選定mode（`existing` / `team` / `personal`）
- 選定根拠（既存resource所有先、team既定、利用者の番号選択）
- directory-bound auth profile名（使う場合）
- 対象製品と既存resource名

完全なAccount ID、token、secret、raw CLI応答は渡さない。専用SkillがAPI callにAccount IDを必要とする場合は、同じprofileまたは安全なcredential contextからprocess内で解決する。

## 利用者への完了表示

```text
Cloudflare環境を確認しました。
- 使用環境: ○○（既存resourceの所有先）
- 判断理由: このプロジェクトの既存Workerと一致（mode: existing）
- 保護方法: このプロジェクト専用のWrangler profile

このまま設定を続けます。利用者側の操作はありません。
```

候補選択やログインなど実際に操作が残る場合だけ、次に押す場所または選ぶ番号を1つ示す。
