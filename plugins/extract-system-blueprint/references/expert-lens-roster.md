# 原則レンズ名簿 (expert-lens roster)

各 analyzer (C03-C06 / C13) の実プロンプトに焼く**著名エンジニア/組織の実名見出し付き原則レンズ**を、
1 箇所で見渡せるよう決定論展開した参照。

> **正本 (SSOT) は `plugin-plans/extract-system-blueprint/component-inventory.json` の各 component の
> `expert_lenses` / `prompt_contract`**。本ファイルはそれを人間可読へ展開したミラーであり、値が食い違った
> ときは inventory を正とする。各 analyzer の `$CLAUDE_PLUGIN_ROOT/agents/*.md` は同じ contract を
> 7 層プロンプトへ展開している。

## レーン (lane) の二層

レンズは **「何を観測/推論するか」だけを導く**。名前を権威根拠にせず、本人の口調も模倣しない。

| lane | 意味 | 該当 component |
|---|---|---|
| `observation-planning-only` | レンズは**観測候補の列挙だけ**を導く。出力は fact / gap に限定し inference を生成しない | C03 (frontend-surface-analyzer) |
| `inference` | レンズは推論を導く。ただし全主張へ `evidence_refs` + `confidence` 必須で fact へ混入させない | C04 / C05 / C13 / C06 |

## 全 analyzer 共通の必須セクションと guard

各 analyzer の実プロンプトは `prompt_contract` に従い、以下を必須にする (`names_must_appear_in_prompt: true`)。

- **必須セクション**: `Observations` → 各レンズ見出し (下表) → `Cross-lens conflicts` → `Neutral synthesis` → `Confidence and gaps`
- **per-lens review → cross-lens conflicts → neutral synthesis** の順で、一致点・対立点・反証候補を neutral synthesis へ残す。
- **guard rules (全 analyzer 共通の骨子)**:
  - 公開された設計原則を分析レンズとして用い、本人/組織の口調を**模倣しない**。
  - 本人/組織が**レビュー・承認・推薦したと主張しない** (非承認 guard)。
  - 名前を権威の根拠にせず、fact lane は persona-neutral に保つ。
  - inference レーンの全レンズ主張へ `evidence_refs` + `confidence` を付け fact へ混入させない。`high` confidence は直接支持する**複数** evidence_refs がある場合だけ許す。
  - 一致点・対立点・反証候補を neutral synthesis へ残す。

> **評価は名前出現だけで PASS しない**。C02 (`assign-blueprint-fidelity-evaluator`) は実名見出し・cross-lens
> conflicts・neutral synthesis・非模倣/非承認 guard の**構造存在**を検査したうえで、レンズ由来推測の
> `evidence_refs` + `confidence`・fact 非混入・high の複数直接根拠まで意味判定する。

---

## C03 — frontend-surface-analyzer (fact / observation-planning-only)

観測計画だけを導き、出力は fact / gap に限定する。

| 実名見出し (prompt_heading) | 役割 (role) |
|---|---|
| `Lens — Dan Abramov: state ownership and data flow` | 状態所有・データフロー・UI 状態境界から**観測候補**を列挙する |
| `Lens — Evan You: component composition and responsive state` | component 構成・reactivity・progressive enhancement・responsive 状態から**観測候補**を列挙する |

- 必須セクション: `Observations` / 上記 2 見出し / `Cross-lens conflicts` / `Neutral synthesis` / `Confidence and gaps`
- 追加 guard: 「レンズは観測計画だけを導き、C03 は inference を生成しない」。

## C04 — backend-inference-analyzer (inference)

C03/C09 の観測 fact から、バックエンド機構・named 同定・security 設計・配信トポロジーを推論する。

| 実名見出し (prompt_heading) | 役割 (role) |
|---|---|
| `Lens — Martin Kleppmann: data models and consistency` | データモデル・一貫性・log/stream・storage/communication 境界を推論する |
| `Lens — Werner Vogels: distributed failure and availability` | 分散失敗・可用性・scaling・failure isolation・CDN/edge/origin 配信トポロジー (static\|SSR\|ISR) を推論する |
| `Lens — OWASP: security design (ASVS/Top10, passive)` | cookie 属性/認証UI/CSP/security headers fact から認証方式・セッション管理・CSRF/XSS 対策・攻撃面と真似すべき/避けるべきプラクティスを**受動観測のみ**で推論する |

- 追加 guard: **security 推測は受動観測のみを根拠とし、侵入テスト/脆弱性スキャン/認証突破を提案・実行しない**。named 同定 (framework/hosting/CDN/analytics/SaaS) は必ず signal fact への `evidence_refs` + `confidence` 付き=シグナルは事実・命名は推測のレーン二層化。

## C05 — uiux-rationale-analyzer (inference)

観測 fact (静的観測/layout/機能アフォーダンス含む) から UI/UX 設計意図と user_journeys 仮説を推論する。

| 実名見出し (prompt_heading) | 役割 (role) |
|---|---|
| `Lens — Josh Comeau: CSS layout and component composition` | CSS layout・component 構成・responsive behavior を推論する |
| `Lens — Sarah Drasner: interaction and visual hierarchy` | interaction・animation・state transition・visual hierarchy を推論する |

- 区別: `feature_map` = C03 観測集約の fact / `user_journeys` = 推測。両者を混ぜない。

## C13 — content-intent-analyzer (inference)

verbatim コピー/見出し階層/CTA/meta・OGP/構造化データの content fact から、伝えたいこと (価値提案・
キーメッセージ・想定読者・トーン&ボイス・CTA 意図) と本質的問題 (JTBD) 仮説を推論する。

| 実名見出し (prompt_heading) | 役割 (role) |
|---|---|
| `Lens — Kinneret Yifrah: microcopy and voice` | microcopy・トーン&ボイス・UX ライティングの意図と一貫性を推論する |
| `Lens — Nielsen Norman Group: content usability and information scent` | 情報階層・スキャナビリティ・information scent から訴求の構造を推論する |
| `Lens — Marty Cagan: product value and viability` | 価値提案・製品意図・viability 仮説を推論する |
| `Lens — Teresa Torres: opportunity and JTBD discovery` | 対象が解く本質的問題 (JTBD)・機会構造・想定読者を推論する |

- C04 (backend) / C05 (uiux) とは C03 起点の**直交する推測レンズ**。突合・統合は本 agent でなく C06 で行う (DAG 深化を避ける)。

## C06 — architecture-essence-synthesizer (inference)

C03 の fact・C04/C05/C13 の推測を統合し、essence 章・feature_map・user_journeys・security_design・
delivery_topology・5 種 Mermaid 図・合成 design-token palette を生成する。

| 実名見出し (prompt_heading) | 役割 (role) |
|---|---|
| `Lens — Martin Fowler: boundaries and integration patterns` | boundary・integration pattern・refactoring opportunity を統合評価する |
| `Lens — Kent Beck: simple design and feedback` | simple/evolutionary design・feedback・testability を統合評価する |

- essence 章 (本質的問題 JTBD/想定読者/価値提案/キーメッセージ/トーン&ボイス/positioning・差別化) は各項目 `evidence_refs` + `confidence` 付き inference として fact と区別する。
- 合成 design-token palette は**観測 fact の機械的集約**でありペルソナ推測を混ぜない (観測色の palette 孤児 0)。

---

## 関連

- 運用手順: [`runbook.md`](runbook.md)
- 各 analyzer 実体: `$CLAUDE_PLUGIN_ROOT/agents/{frontend-surface,backend-inference,uiux-rationale,content-intent,architecture-essence}-*.md`
