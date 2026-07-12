---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
P01 のギャップ一覧 (G1-G7) と C1-C8 対応表を入力に、procedure 軸の構造化スキーマ形状・決定論フォールバック閾値・purpose/procedure 両方揃うまでの下流ハンドオフゲート・as-is 忠実性原則 (平均回帰禁止・相手固有の具体性・as-is/to-be 分離) を設計し、4 個の buildable component (C01-C04) と依存 DAG として `component-inventory.json` に確定する。

## 背景
goal-spec constraints は「格納先 (新設 procedure.json / interview.json 拡張 / intake.json 新設 section のいずれか) は R2 のコンポーネント分解判断に委ねる」「フォールバック切替閾値は R2/R3 の実装判断に委ねる」「procedure 抽出を独立 SubAgent とするか既存拡張とするかは R2 が判断する」としている。本 phase でこれら 3 点を含む設計判断を確定し、以降の phase (P03 レビュー〜P13 リリース) が参照する不変の component 目録を作る。

## 前提条件
- P01 のギャップ一覧・改善要否・C1-C8 対応表が確定している。
- 既存 4 SubAgent の分離パターン (起動独立性 × LLM 自律 dispatch 非該当・adversarial/客観推定/バイアス回避固有の独立 context 化) が判読済みである。

## ドメイン知識
- 用語集は index `## ドメイン知識` を参照。本 phase 固有差分は以下。
- **procedure スキーマ形状**: `interview.json.procedure.mode` ∈ {`detailed`, `overview_fallback`}。`detailed` は `procedure.steps[]` (各要素: `action`/`input`/`output`/`tool`/`frequency` 非空)。`overview_fallback` は `procedure.difficulty_flag=true` かつ `procedure.overview` (`step_count_estimate`/`participants`/`frequency`) 非空。下流 `intake.json` では既存 v2 の 12 section 契約を崩さず `sections.6_five_axes_summary.procedure` へ格納し、C02 の成功結果は root `validation.procedure_completeness` へ格納する。
- **決定論閾値**: `validate-answer-abstraction.py` の抽象判定を `axis=procedure` へ拡張し、procedure 軸で **2 連続抽象判定または未回答** が発生した時点で `overview_fallback` へ切り替える (同一回答パターン→同一経路、goal-spec C6)。
- **as-is 忠実性原則 (goal-spec C7/C8)**: ヒアリングの第一目的は一般的情報収集ではなく「クライアントが本当に解決したい課題・問題・現状の流れ・実行したいこと」を相手固有の具体性で抽出しハーネス構築材料にすることである (goal-spec purpose 追記)。設計上の帰結は次の 2 点。(1) **as-is/to-be フィールド分離 (C7)**: 本サイクルでは to-be (改善提案・理想手順・最適化) 専用の永続フィールドを新設しない (ヒアリング段階で to-be 設計をしない goal-spec constraints)。代わりに handoff 対象の既存 as-is フィールド (`procedure.*` と `five_axes.rows[name="真の課題"].content`) に to-be 語彙が混入していないことを contamination check (C02 拡張) で強制し、raw 会話ログ中の to-be 発話は検査対象外とする。(2) **相手固有の具体性 (C8)**: 質問設計・記録指示は「固有名詞・実例・頻度・関与者」を伴う回答を目標とし、抽象的・平均的な回答が来た場合は正規化・要約せず追加質問で具体化を促す (C01 プロンプト層拡張、`abstract-answer-patterns.md` の抽象判定と同じ軸で運用)。
- **as-is フィールド正準表 (C01 保護宣言 ↔ C02 検査対象の対応)**:

  | 論理名 (C01 保護語彙) | interview.json パス | intake.json パス | C02 検査対象 |
  |---|---|---|---|
  | 解決したい課題・問題 (真の課題) | `five_axes.rows[name="真の課題"].content` | `sections.6_five_axes_summary.axes[axis_id="real_problem"].answer` | ○ (contamination) |
  | 現状の流れ・仕組み (手順) | `procedure.steps[]` / `procedure.overview` の各テキスト値 | `sections.6_five_axes_summary.procedure` | ○ (完全性+contamination) |
  | 実行したいこと | 専用フィールド無し (上記 2 系へ内包記録) | 同左 | △ (2 系に内包される範囲のみ機械検査) |

  rows[name="真の課題"] (日本語 name) ↔ axes[axis_id="real_problem"] (英語 enum) の変換は既存 render 経路 (`render-intake-final.py`) が担い、本改善では変更しない。2 系に内包されない as-is 発話の保護は第一線 (C01 保存抑止・R3-as-is-fidelity) と第三線 (OUT2 独立レビュー) が担う。

## 成果物
- **新規 SubAgent 非新設の設計判断**: procedure 抽出は非 adversarial な直接聴取のため、既存 4 SubAgent の分離パターンに該当しない。よって `run-intake-interview` (C01) を拡張し、procedure 抽出を Phase4 の会話継続性の中で完結させる (`component-inventory.json.derivation` に逐語記録済み)。
- **component 分解 (4 件、詳細は `component-inventory.json` が SSOT)**:
  - **C01 (skill, extend)** `run-intake-interview` — procedure 軸の詳細抽出 (R1-procedure-elicit) とフォールバック切替 (R2-procedure-fallback) に加え、as-is 忠実性記録 (R3-as-is-fidelity: 具体性を促す追加質問・to-be 提案をしない指示) を追加する (goal-spec C7/C8)。
  - **C02 (script, new, placement_scope=plugin-root)** `validate-procedure-completeness.py` — procedure ブロックの完全性 (mode 別) 判定に加え、as-is フィールドへの to-be 語彙混入を検出する contamination check (goal-spec C7) を持つ共有ゲート。C01 (Phase4 完了チェック) と C04 拡張 (Phase9 ハンドオフゲート) の 2 消費者から参照されるため no-split threshold を満たし独立 component へ昇格する (contamination check 追加後も 2 消費者関係は不変)。
  - **C03 (skill, extend)** `run-intake-finalize` — purpose (true_purpose) と procedure の両方が `intake.json` に非空で揃うまで Phase10/11 (下流ハンドオフ) へ進めないゲートを実行する。
  - **C04 (script, extend, placement_scope=plugin-root)** `quality_gate.py` — 既存決定論ゲートに「purpose と procedure の両方非空」invariant を追加する。
- **依存 DAG (循環なし)**: C01 → C02 → C03 → C04 (C02.depends_on=[C01], C03.depends_on=[C01,C02], C04.depends_on=[C02,C03])。テスト実行では C02 の純粋ロジック単体テストを先に走らせてよいが、統合順序はこの DAG に従う。
- **新規 sub-agent/slash-command/hook 非新設の根拠**: (a) sub-agent — 上記の通り非 adversarial のため独立 context 化の動機がない。(b) slash-command — procedure 軸は既存 `run-skill-intake` → Phase4 自動フローに内包され手動起動エントリを要しない。(c) hook — 必要なのは「フェーズ遷移前の完全性ゲート」であり決定論 script の exit code 判定で足り、ツール呼び出し単位の遮断を要する破壊的操作が無いため新規 hook は不要 (詳細根拠は `component-inventory.json.derivation` を正本とする)。
- **plugin-level surfaces の採否**: manifest/composition/harness_eval/references_config_assets/schemas = required、vendor/mcp_app_connector/notion_config = omitted (根拠は `component-inventory.json.plugin_level_surfaces` を正本とする)。

## スコープ外
- 実装 (C01/C03 への実際の Edit 差分、C02/C04 の実コード) は本 phase では行わない。実改修は後段 build (`run-skill-create`/`plugin-scaffold`) へ委譲する。
- 5 軸ヒアリングシート自体の質問文言・スキップ条件の変更 (goal-spec constraints によりスコープ外)。
- Notion 公開・Slack 通知・Keychain 認証の既存契約変更 (goal-spec constraints によりスコープ外)。

## 完了チェックリスト
- [ ] `component-inventory.json` が 5 component_kind (skill/sub-agent/slash-command/hook/script) の検討証跡を持ち、sub-agent/slash-command/hook を新設しない根拠が明記されている。
- [ ] C01-C04 の全てが `build_target`/`builder`/`build_kind` を非空で持ち、依存 DAG (C01→C02→C03→C04) が非循環である。
- [ ] procedure スキーマ形状 (`mode`/`steps[]`/`difficulty_flag`/`overview`) と決定論閾値 (2 連続抽象判定/未回答) が確定している。
- [ ] `intake.json` 側の格納先が `sections.6_five_axes_summary.procedure`、C02 成功結果の格納先が root `validation.procedure_completeness` として確定している。
- [ ] as-is/to-be フィールド分離の設計 (to-be 専用フィールド非新設 + contamination check による混入検出, goal-spec C7) と、相手固有の具体性を促す質問設計 (goal-spec C8) が確定している。
- [ ] `check-surface-inventory.py` が exit0 (5 kind 検討証跡 + plugin-level surface 採否)。

## 参照情報
- `plugin-plans/skill-intake/component-inventory.json` (本 phase の主成果物・build 実体の SSOT)。
- `skills/run-plugin-dev-plan/references/component-domain.md` (2 軸直交 + no-split threshold 定義)。
- P01 (ギャップ一覧・C1-C8 対応表を入力とする)。
- 後続 P03 (この component 分解を独立 approver がレビューする)。
