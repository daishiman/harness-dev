# Secure by Design — deep knowledge card

> knowledge_id: `secure-by-design` / status: `seed-example`。OWASP/CISA等は探索seedであり、法域・業界・threat model固有の統制を網羅しない。

## 目的

利用者の注意や運用後のpatchへ安全性を押し付けず、systemのdefault、architecture、development lifecycleに安全な結果を組み込み、被害可能性と復旧費を下げる。

## 背景

脆弱性対応をrelease直前の診断や利用者設定に限定すると、設計由来の欠陥、過大権限、unsafe default、観測不能は残る。Secure by Designはsecurityを品質属性と製造者責任として早期から扱い、Secure by Defaultと継続的検証を組み合わせる。

## 解決する問題

- 認証・認可・data protectionが後付けで、business flowと矛盾する。
- defaultが過大権限/公開状態で、利用者の完全な設定に安全性が依存する。
- 単一防御の突破で全面侵害になり、検知・封じ込め・復旧の証拠が無い。
- dependency、secret、build、releaseの供給chain riskが製品境界外として放置される。

## 中核概念

- **Threat modeling**: asset、actor、trust boundary、abuse case、impactを設計前提にする。
- **Least privilege / deny by default**: identity、service、data、networkの権限を最小化し、判断不能時はfail closed。
- **Defense in depth**: preventive、detective、responsive controlを独立層で持ち、単一failureを全体failureにしない。
- **Secure defaults and usable security**: 初期状態を安全にし、MFA/logging/update等を利用者が無理なく維持できる。
- **Data lifecycle**: collection minimization、classification、encryption、retention、deletion、backupまで設計する。
- **Assurance**: abuse-case test、dependency/provenance、review、logging、incident exerciseでcontrolの実効性を検証する。

## 適用条件

- identity、個人/機密data、金銭、外部入力、admin操作、multi-tenant boundaryを扱う全system。
- compromise時の影響がgoal、法規、信頼、運用継続を損なう。
- vendor/serviceを使う場合も、共有責任とfailure/exit planを明示できる。

## 非適用条件

- security自体が不要なsystemは原則ない。asset/threatが極小ならcontrolを軽量化できるが、根拠付きrisk acceptanceが必要。
- controlがthreatを減らさず、accessibility/availability/safetyを重大に損なう場合はそのcontrolを採用しない。代替・補償統制を設計する。
- checklist準拠だけでproject固有のtrust boundaryとabuse caseを置き換えない。

## トレードオフ・失敗モード

- friction、latency、delivery費、運用負荷が増えるため、risk reductionと明示的に釣り合わせる。
- security theaterとしてcontrol数だけ増やし、owner、evidence、responseを持たない。
- fail closedを無差別適用してavailability/safety incidentを起こす。degraded modeとbreak-glass監査が必要。
- secretを隠しても過大権限や長期credentialを残す、暗号化してもkey lifecycleを設計しない等の局所最適。
- free tier製品を価格だけで選び、audit、export、retention、MFA、incident support不足を見落とす。

## 目的達成への寄与

- stakeholderの安全・信頼・継続性をsuccess criteriaへ変換し、threat/control/evidenceをgoalへトレースする。
- security controlは「導入済み」ではなく、阻止/検知/復旧時間、権限範囲、data exposureで効果を測る。
- 予算0制約でも、secure default、最小data、短命credential、標準機能、open-source検査を優先し、残余riskを隠さない。

## ヒアリング・判断観点

- 守るasset、攻撃者、trust boundary、最大impact、法規、復旧目標は何か。
- userが設定しなくても安全なdefaultか。管理者・service accountの権限は最小か。
- control failureを誰が何で検知し、どのevidenceで復旧を確認するか。

## 一次資料

- CISA, Secure by Design, https://www.cisa.gov/securebydesign
- NIST SP 800-218, Secure Software Development Framework, https://csrc.nist.gov/pubs/sp/800/218/final
- OWASP ASVS, https://github.com/OWASP/ASVS

## 鮮度

- class: `standard-tracked`
- last_checked: `2026-07-11`; review_by: `2026-10-11`
- trigger: CISA/NIST/OWASP改訂、CVE/advisory、threat model・法規・data classification変更、vendor EOL/価格・security機能変更。

