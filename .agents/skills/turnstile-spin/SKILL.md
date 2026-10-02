---
name: turnstile-spin
description: Cloudflare Turnstileをprojectへend-to-endで導入する。codebaseを調査し、Cloudflare APIでwidgetを作成し、適切なformへ埋め込み、既存backendへ正式なserver-side siteverifyを接続して検証する。Turnstile追加、CAPTCHA設定、botからのform保護、Turnstile連携修正を依頼されたときに使用する。developers.cloudflare.com/turnstile/spinの中核手順へAIDD固有の安全規則を重ねたSkill。
---

> 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。

# Turnstile Spin

「Turnstileを設定して」という依頼を、動作するend-to-end連携へ変える。成果物はwidget、選定した全挿入箇所のfrontend、既存backendでの正式なserver-side siteverify、成功報告前の実検証である。

agentは`scripts/`配下のscriptを実行し、JSON出力の`status`で分岐する。API calls、retry、error handlingなどの決定的処理はscriptが持つ。agentはorchestration、codebaseの読解、推奨案の選定、frontend/backend編集を担う。

Turnstile連携の中核手順は[`developers.cloudflare.com/turnstile/spin`](https://developers.cloudflare.com/turnstile/spin/)を参照する。ただし、repository所有権、AIDDの編集原本→sync、秘密値・Account IDの非開示、package manager選択はこのrepository固有の安全overlayであり、upstream文書を直接取得して上書きしない。製品仕様で不一致があれば公式docsを優先し、local overlayと統合して編集原本へ反映する。

Token種別はCloudflare公式の[Account API Token互換表](https://developers.cloudflare.com/fundamentals/api/get-started/account-owned-tokens/)を正本とする。現行の互換表ではTurnstileはAccount API Token非対応である。Turnstile widget管理には、対象Accountだけへ`Account.Turnstile:Edit`を付けたuser-owned API tokenを例外的に使う。Workers/D1/R2のCI/CD用account-owned tokenとは分離し、相互に使い回さない。

## このSkillをloadする条件

依頼に次のいずれかが含まれるときにloadする。

- 「Turnstile」「CAPTCHA」「bot対策」「bot protection」
- "siteverify", "cf-turnstile-response"
- 「このformを保護」「bot signupを止める」「spam signup」
- 特定のsignup、login、contact formと「Cloudflare」または「bot」の組み合わせ

Turnstileに言及しないWorkers、Pages、R2などのCloudflare作業ではloadしない。

## 成果物先行フロー

Turnstile設定の依頼は、repository調査、安全かつ正式な挿入箇所の選定、範囲内の実装、検証を行う権限を含む。多段の質問票にはしない。`Evidence → Decide → Draft → Validate → Diff`で進め、最初にread-only調査を行い、推奨構成を1つ選び、連携を作り、検証済み結果とunified diffを示す。credentials/Account identity、推論不能なproduction hostname、破壊的なCAPTCHA移行など、利用者だけが決められる境界でのみ停止する。

1. **すぐ開始する。** 作る成果を短く伝え、事前確認の往復を挟まずauth確認とread-only scanへ進む。

2. **CLI確認。** 最初にlockfileを調べ、既存package managerを使う。`pnpm-lock.yaml`/`pnpm-workspace.yaml`なら`pnpm exec wrangler`、`package-lock.json`なら`npx --no-install wrangler`、`yarn.lock`なら`yarn exec wrangler`を使う。このrepositoryの例はpnpmである。helperは`api.cloudflare.com`への`curl`とproject-localな`wrangler whoami`でAccountを列挙する。Step 8ではWrangler 4.109+の`wrangler turnstile widget create`を優先し、利用できなければ同梱curl scriptへfallbackする。global installは不要であり、勧めない。

3. **Authとscope probe（最初の不可逆操作より前）。** `scripts/auth-probe.sh`を実行し、`status`で分岐する。
   - `ok`: Step 4へ進む。scriptは単一Accountまたは`$CLOUDFLARE_ACCOUNT_INDEX`からAccountを選択済み。後続scriptにも候補番号だけを渡し、完全なAccount IDをJSON、command argument、chat、質問文、最終報告、screenshotへ出さない。
   - `wrong_token_type`: `cfat_`のAccount API Tokenまたは`cfk_`のGlobal API Keyが指定されている。Turnstile非対応または権限過大なので使用せず、次のuser-owned token作成導線へ進む。CI/CD用tokenの権限を変更しない。
   - `missing_token`または`missing_scope`: 所有者に、対象Accountだけへ`Account.Turnstile:Edit`を持つ**Turnstile専用User API Token**を作ってもらう。Dashboardで`My Profile > API Tokens > Create Token > Custom token`を開き、Permissionは`Account / Turnstile / Edit`、Account Resourcesは選定済みAccountだけにする。他のWorkers/D1/R2権限は追加しない。新しいtokenは`cfut_`形式であり、旧形式のunprefixed user tokenもscope probeで確認して利用できる。Tokenはchatで受け取らず、repositoryやCI secretへ保存しない。shell historyへ値を残さない次の方法でownerに起動してもらう。
     ```bash
     printf 'Turnstile専用User API Tokenを貼り付けてEnter: '
     IFS= read -rs CLOUDFLARE_API_TOKEN
     printf '\n'
     export CLOUDFLARE_API_TOKEN
     # このTerminalからAIエージェントを再起動する
     ```
     auth確立後に`auth-probe.sh`を再実行し、Step 8へ進む。
   - `multiple_accounts`: `cloudflare` SkillのAccount文脈自動検出を使い、既存resource所有先を優先する。候補提示には`account_candidates`の番号、name、`masked_id`だけを使う。候補が複数残る場合だけownerに番号を選んでもらい、`CLOUDFLARE_ACCOUNT_INDEX=<number> scripts/auth-probe.sh`を再実行する。完全なIDは各scriptのprocess memoryだけで解決する。
   - `account_mismatch`: 内部用`$CLOUDFLARE_ACCOUNT_ID`がtokenのAccountと一致しない。raw値や内部`accounts`を表示せず、`declared_masked`と`account_candidates`だけを示す。変数をunsetするか候補番号で再選択する。

4. **Account選択。** `multiple_accounts`後に`ok`なら選択済み。単一Accountの場合はscriptが内部で選ぶ。既存resourceが個人Accountにありチーム運用へ変えたい場合は停止し、移行を別taskとして計画する。チーム側へ重複widget/resourceを作らない。選択済み番号はsession内の`CLOUDFLARE_ACCOUNT_INDEX`だけで扱い、完全なAccount IDを保存しない。

5. **Domain。** `localhost`と`127.0.0.1`を必ず含める。productionは`package.json`の`homepage`、`wrangler.toml`、`README.md`、`AGENTS.md`、git remoteを調べ、根拠が最も強いhostnameを選ぶ。明確なhostnameが1つなら確認質問しない。見つからなければlocalhost連携を先に作成・検証し、production widget作成前に不足hostnameを1件だけ尋ねる。

6. **Codebase scan。** 次の3点を質問せず検出する。
   - **Frontend framework**（Next.js、Astro、SvelteKit、Hugo、vanilla等）→ widget embed snippetを決める
   - **Backend handlerの場所**（Express route、Next.js API route、Rails controller、Workers fetch handler、Pages Function等）→ siteverify snippetを決める
   - **既存CAPTCHA**（reCAPTCHA / hCaptcha）→ Step 7をmigration modeへ切り替える

7. **挿入箇所の決定。** public exposure、abuse impact、既存submit path、backend verificationの可否、実装riskで候補を採点する。利用者へ選択を丸投げせず、`[recommended]`を全て選び、`[skip by default]`は除外する。理由は最終報告に残す。既存CAPTCHAがあれば具体的なmigration diffを先に作り、破壊的置換またはEnterprise設定だけ承認を求める（「他CAPTCHAからの移行」参照）。

8. **Widget作成。** 既存package managerで`turnstile widget` subcommandを利用できる場合はWrangler CLIを優先する。このrepositoryのpnpm例:

   ```sh
   pnpm exec wrangler turnstile widget create "<name>" \
     --domain <d1> --domain <d2> ... --mode managed --json
   ```

   stdout JSONから`sitekey`と`secret`をparseする。Wranglerがproject-localにない、subcommandより古い（`unknown command`）、または失敗した場合は、Cloudflare APIへ直接`curl`する`scripts/widget-create.sh --account-index <number> --name <name> --domains <list> --mode managed`へfallbackする。scriptはAccount IDをprocess内で解決し、出力・保存しない。global installはしない。sitekeyは報告してよい。secretはshell変数`WIDGET_SECRET`へ保持し、Step 9で利用者自身のenv/secret storeへ入れる場合を除いてdiskへ書かない。

9. **連携を配線する。** 選定した各formへ正式なcontractを適用する。widgetを埋め込み、既存submit handler内へ`success === true`でgateするsiteverify callを追加する。handlerの既存logicは変えず、secretは`TURNSTILE_SECRET`へ置く。明示的な設定依頼は、この限定的で可逆なcode editを許可する。先に検証し、その後unified diffを示す。mail deliveryやcustom backendなどの別機能を提案しない。

   Canonical server-side siteverify (Node / fetch idiom; adapt to the detected backend):

   ```js
   const r = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
     method: 'POST',
     headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
     body: new URLSearchParams({
       secret: process.env.TURNSTILE_SECRET,
       response: token,         // cf-turnstile-response from the request
       remoteip: clientIp,      // X-Forwarded-For / req.ip / etc.
     }),
   });
   const result = await r.json();
   if (!result.success) {
     return reject(403, 'forbidden');  // platform-appropriate equivalent
   }
   // existing handler logic runs here, unchanged
   ```

   secretは利用者のsecret storeへ入れる（Node/Rails/Pythonなら`.env`、Workersなら`wrangler secret put TURNSTILE_SECRET`、Vercel/Fly/Render等はplatformのsecret manager）。inlineしない。

10. **検証。** `scripts/validate.sh`を実行し、各checkのPASSを報告する。1件でもFAILならerrorを示して停止する。**[失敗時は利用者を待つ]**

11. **repository所有権を迂回せずSkillを保存・更新する。** 最初に適用される`AGENTS.md`を読み、保存先を分類する。
    - **AIDD管理repository:** `.claude/skills`と`.agents/skills`は生成されるruntime配置。直接write/fetchしない。`AGENTS.md`が指定する編集原本（このbundleでは`aidd-agent-kit/skills/turnstile-spin/`）を更新し、repositoryのsyncとverify commandを使う。upstreamを取得する必要があればtemporary directoryへ取得し、diffをreviewして承認済み変更だけを編集原本へ適用する。`persist-skill.sh`のtargetに管理runtimeを指定しない。
    - **別のauthoring ruleがあるrepository:** そのruleに従う。runtime discovery pathを編集原本と仮定しない。
    - **authoring ruleがない非管理repository:** repository-local runtime pathを提案する。Claude Codeは`.claude/skills/turnstile-spin/SKILL.md`、Codexは`.agents/skills/turnstile-spin/SKILL.md`。後続task用に保存するか尋ね、既定はyes。**[利用者を待つ]** この場合だけ`scripts/persist-skill.sh --path <selected-client-path>`を実行する。

12. **最終報告。** 「作成・変更したもの」「選んだformと理由」「検証結果」「残る利用者操作」「次にすること」を日本語で構造化して示す。sitekeyは必要時に示してよい。Token、widget secret、raw Account IDはchatと最終報告へ出さない。Accountはnameだけを示す。

### 禁止事項

- 利用者自身のenv/secret store以外へTurnstile secretを書かない。
- 検証を省略しない。
- 関係ない挙動を上書きしない。変更を限定し、検証し、最終報告でdiffを示す。
- browserからsiteverifyを呼ばない。常にbrowser → 利用者のbackend → siteverify。
- 追加infrastructure（Workers、proxy、sidecar）をdeployしない。既存backendから直接siteverifyを呼ぶ。
- `sudo`やglobal package installを使わない。既存package managerのproject-local commandまたはcurl fallbackを使う。
- 依頼されていないcustom Workers、custom domains、advanced WAF rulesを提案しない。
- raw Account IDをchat、質問、最終報告へ出さない。候補はname、番号、masked IDだけを表示する。
- TurnstileにAccount API Tokenを使わない。Turnstile専用user-owned tokenをCI/CD用account-owned tokenと共有しない。
- 管理runtime directoryへこのSkillをpersist/downloadしない。`AGENTS.md`に従って編集原本を更新し、syncとverifyを行う。

### 対象外のことを利用者へ尋ねない

Spinが行うのは、利用者の既存form handlerが動く前に正式なsiteverifyでTurnstile tokenを検証すること。次は対象外。

- **Email / SMS / notification delivery。** 既存submit handlerは`success === true`でgateする以外変更しない。Resend、Mailchannels、SMTP、mailtoを提案しない。
- **新しいbackendの追加。** 現在backend handlerがないpure-static siteやmailto-only formなら、その事実を伝えて終了する。Spinにはsiteverifyを置くserver-side処理が必要。
- **Database / payment / OAuth / form persistence。** 対象外。
- **Frontend framework migration、refactoring、styling。** 必要箇所だけを編集する。
- **reCAPTCHA v3 score thresholds。** Turnstileは`success: true/false`を返す。
- **Pre-clearance-only設定。** `clearance_level !== no_clearance`ならsiteverifyはoptionalでSpin対象外。該当docsへ案内して終了する。

### 復旧フロー: 既存widget設定を尊重する

利用者がCloudflare dashboardへaccessできる場合、dashboard内の**Fix with Spin** bannerが既存widget用のone-click recoveryである。以下はeditorから進める場合の同等フロー。

既存Turnstile widgetのsitekeyをrotateせずsiteverifyだけ接続したい場合:

1. Step 8（widget作成）をskipする。既存sitekeyを利用者から受け取る。
2. 選択済み候補番号を使い`scripts/fetch-secret.sh --account-index <number> --sitekey <key>`でmetadataを取得し、`status`で分岐する。scriptは完全なAccount IDをprocess内だけで解決する。
   - `ok`: responseの`secret`、`clearance_level`、`domains`を内部で読む。`domains`にproduction hostnameがなければ、先へ進む前に不足を示す。
   - `missing_read_scope`: tokenへ`Account.Turnstile:Read`を追加してもらう。追加できない場合、secretをchatへ貼らせず、利用者自身に対象platformのsecret storeへ`TURNSTILE_SECRET`として登録してもらう。この経路では`clearance_level`と`domains`を取得できないため、dashboard上の表示だけを確認してもらう。
3. responseまたはdashboard確認から`clearance_level`を判定する。
   - `no_clearance`: 標準の接続（Step 9）へ進む。
   - それ以外: pre-clearanceにsiteverifyを重ねるか確認するか、対象範囲に従って終了する。
4. Step 9から続行する。sitekeyは変えず、既存widgetを動作させたままにする。
5. 新しいsecretを得る目的でwidgetを再作成しない。deploy済みの全sitekeyを壊す。

### Frontend編集contract

既存formを接続するときのcontractは、**置換せずgateする**こと。既存submit handlerの処理は維持し、その前にvalidationだけを追加する。

Frontend（widgetを埋め込み、既存endpointへsubmit）:

```html
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>

<form action="/signup" method="POST">
  <!-- existing inputs unchanged -->
  <div class="cf-turnstile" data-sitekey="<SITEKEY>" data-action="turnstile-spin-v2"></div>
  <button type="submit">Sign up</button>
</form>
```

Backendは既存handler内でStep 9の正式なsiteverify fetchを使う。`req.body['cf-turnstile-response']`からtokenを読み、`success === true`でgateし、残りのhandlerは変えない。既存handlerがstubなら、success gate付きstubのまま残す。stubの置換はSpinの仕事ではない。

## 他CAPTCHAからの移行

Step 6のscanで既存reCAPTCHA/hCaptchaも探す。見つかったらStep 7をmigration planへ切り替える。

検出signal:
- reCAPTCHA: `https://www.google.com/recaptcha/api.js`, `class="g-recaptcha"`, `data-sitekey="6L..."`, backend POST to `/recaptcha/api/siteverify`
- hCaptcha: `https://js.hcaptcha.com/1/api.js`, `class="h-captcha"`, backend POST to `https://hcaptcha.com/siteverify`

置換内容:
- script tagを`https://challenges.cloudflare.com/turnstile/v0/api.js`（`async defer`）へ置換する。
- `class="g-recaptcha"` / `class="h-captcha"`のdivを`class="cf-turnstile"`へ置換し、`data-sitekey`を新Turnstile sitekeyへ更新し、`data-action="turnstile-spin-v2"`を追加する。
- Token fieldを`g-recaptcha-response`から`cf-turnstile-response`へ変更する。
- Backend siteverify URLを`https://challenges.cloudflare.com/turnstile/v0/siteverify`へ向ける。`RECAPTCHA_SECRET` / `HCAPTCHA_SECRET` env varsを廃止し、`TURNSTILE_SECRET`を追加する。

利用者へ明示するedge cases:
- **reCAPTCHA v3 score thresholds。** Turnstileにscoreはない。移行後は`success === false`でrejectすることを明示する。
- **reCAPTCHA Enterprise。** 自動移行せず、[developers.cloudflare.com/turnstile/migration/recaptcha/](https://developers.cloudflare.com/turnstile/migration/recaptcha/)へ案内する。
- **Custom `action=` values。** `grecaptcha.execute`へ渡していたcustom actionをwidgetの`data-action`として維持する。custom actionがない場合だけ`turnstile-spin-v2`を使う。

## Edge cases

| 状況 | 対応 |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| project-localな`wrangler whoami`が失敗 | lockfileで既存package managerを再確認する。このrepositoryなら`pnpm exec wrangler whoami`。global installは勧めず、subcommandがなければbundled curl scriptへfallbackする。 |
| Cloudflare Accountが複数 | 既存resource所有先を優先し、新規自社appは複数memberのチーム用Accountを既定にする。候補は番号・name・masked IDだけを表示し、選択番号を`CLOUDFLARE_ACCOUNT_INDEX`へ渡す。 |
| Cloudflare Pages project | Pages Functionまたはframework相当箇所へsiteverifyを置く。[Pages Plugin](https://developers.cloudflare.com/pages/functions/plugins/turnstile/)も利用できる。 |
| Cloudflare Workers backend | Workerのrequest handler内でStep 9の正式なfetchを使う。`challenges.cloudflare.com`への`fetch`はNodeと同様に動く。 |
| `EXPECTED_HOSTNAME` mismatch | widget domainsはPATCHでなくPUTで更新する（PATCHは`10405 Method not allowed`）: `curl -X PUT .../widgets/$SITEKEY -d '{"name":"...","mode":"managed","domains":[...]}'` |
| flow途中でToken失効 | 停止し、`scripts/auth-probe.sh`を再実行して新しいcredentialsをownerに用意してもらう。 |
| Validationが`invalid-input-secret` | secretがbackendへ届いていない。対象env/secret managerの`TURNSTILE_SECRET`を再確認する。Workersなら`wrangler secret list`で正しいscriptへのbinding名を確認する。 |
| Validationが`invalid-input-response` | dummy probe tokenでは想定結果で、secretが有効であることを示す。`validate.sh`は成功として扱う。 |

## Telemetry marker

このSkillが書く全`cf-turnstile` divには`data-action="turnstile-spin-v2"`を含める。これはAccount-levelのaggregate telemetryであり、per-userではない。Cloudflareはactivation測定に使う。利用者がattributeを削除しても連携は動作し、analytics segmentationだけが失われる。

V1 agent flowが作った`turnstile-spin-v1`付きの古いwidgetがproductionに存在する場合、既存markerを維持し、retagしない。
