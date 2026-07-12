# consult-frames.md — 思考フレーム カタログ正本

`run-ubm-consult` の R3-frame-consult が提示する「考え方（思考フレーム）」の正本カタログ。
各フレームは **選択肢＋適用視点（問い）** として提示するためのものであり、単一の処方解ではない。
対話中に技法名（フレーム名）を振りかざさず、質問の形で自然に適用する（phase3-coordinator CONST_003）。
`frame_id`（GF-xxx）は記録・出典管理用。`related_knowledge` は `router.json` デュアルパスで引く既存 knowledge の
カテゴリ／代表 ID（原則 PR-xxx / マインドセット MS-xxx / 事例）で、R3 は該当 `knowledge/*.json` を Read して
intent/background を出典として確認する。

## thinking-guide.md との差分理由（重複ではない・完全統合しない）

capability A（`run-ubm-goal-setting`）は思考法カタログ `thinking-methods-toolkit.md` を `thinking-guide.md` へ統合済み（前者は tombstone）。本 `consult-frames.md`（GF-01..10）は類似カタログに見えるが**用途軸が異なる**ため別置きにする:

- **thinking-guide.md**: 目標設定 Phase 3 の **Step 1〜5 に紐付いた**思考法適用ガイド（「この Step で何の思考法をどう使うか」）。正本＝`$CLAUDE_PLUGIN_ROOT/skills/run-ubm-goal-setting/references/thinking-guide.md`。
- **consult-frames.md（本ファイル）**: Step に縛られない **相談（壁打ち）向けの適用視点**カタログ。相談種別ごとに「どの見方を選択肢として並べるか」を `frame_id`（GF-xxx）＋出典 ID 付きで管理する。相談は固定 Step を持たないため、Step 紐付けの thinking-guide とは索引軸が違う。

重複する上位概念（ゴール指向分解・逆算・フェーズ適合・前提検証・やらないこと設計・関係構築ファースト）は **thinking-guide 側の該当節を正本として参照**し、本カタログでは相談適用視点（核となる問い）だけを持つ。完全統合はしない（相談と目標設定で提示文脈・粒度が異なるため）。

| 本カタログ frame | thinking-guide.md の対応節（概念の正本） |
|---|---|
| GF-01 ゴール指向分解 / GF-05 逆算 | 「Step 3: 前提検証 + 目標設定」の逆算思考（No.31）・「Step横断の共通セクション」の現状→ゴール→ギャップ→次の一歩 |
| GF-02 前提検証 | 「Step 3」のダブルループ／クリティカルシンキング（前提を疑う） |
| GF-04 因果深掘り | 「Step 2: 差分分析 + 原因深掘り」 |
| GF-06 やらないこと設計 | 「Step 4: 行動計画」のやらないこと（3つ以上） |
| GF-07 関係構築ファースト / GF-09 考え→思い→行動 | 「Step 5: 最終確認 + 合宿整合性」の関係構築軸の最終確認 |
| GF-08 フェーズ適合 | 「Step 1」のフェーズ判定フレームワーク（0→1 / 1→10 / 10→100） |

## 使い方（3ステップ翻訳・CONST_006）

1. **原則を引き出す**: フレームの核となる普遍原則を、対応 knowledge の intent/background から取り出す。
2. **ユーザー状況に翻訳する**: R2 でユーザーが話すことに同意した relevant_context にだけ当てはめ、「あなたの場合はどう現れていますか？」と問う。
3. **行動の問いに落とす**: 「誰に・何を・いつ・何件」の粒度で、次の一歩を考えさせる問いにする。

R3 は**2件以上のフレームを並べ**、どれが当てはまるかはユーザーに選ばせる（具体解の押し付けゼロ）。

## フレーム一覧

| frame_id | 名称 | 核となる問い（適用視点） | 向く相談 | related_knowledge |
|---|---|---|---|---|
| GF-01 | ゴール指向分解 | 現状は？ ありたい姿（ゴール）は？ その差（ギャップ）は？ 埋める次の一歩は？ | 漠然とした行き詰まり全般。全相談の収束枠 | 原則: principles-business-strategy / mindset: mindset-goal-strategy |
| GF-02 | 前提検証 | それは事実ですか、思い込みですか？「できない」の前提を1つ外すと何が変わりますか？ | 「無理」「うちの業種は特殊」等の固定観念 | mindset: mindset-self（MS-007 恐れの転換 等） |
| GF-03 | トレードオフ二軸 | 何を得るために何を手放しますか？ 2つの軸で並べると選択肢はどこに位置しますか？ | 複数案で迷う意思決定 | 原則: principles-business-execution |
| GF-04 | 因果深掘り | なぜそれが起きる？ そのまた原因は？（浅い対症でなく根っこへ） | 症状は見えるが原因が曖昧 | 原則: principles-mindset（PR-032 / PR-035 等） |
| GF-05 | 逆算 | ゴールの期日から逆算すると、今週やるべきことは何ですか？ | 期日がある目標・計画倒れ | mindset: mindset-goal-strategy |
| GF-06 | やらないこと設計 | 迷いを減らすために、やらないことを3つ決めるなら？ 判断基準は1文で言うと？ | あれもこれもで動けない | 原則: principles-business-execution / mindset: mindset-growth-habit |
| GF-07 | 関係構築ファースト | 売上を「追う」でなく、誰との関係を「育む」順で考えると？（売上は関係の結果） | 集客・売上の相談 | 原則: principles-relationship |
| GF-08 | フェーズ適合 | 今は 0→1 / 1→10 / 10→100 のどこ？ そのフェーズで効く一手は？ | 打ち手が現フェーズと噛み合わない | phase-advice-0to1 / phase-advice-1to10 / phase-advice-10to100 |
| GF-09 | 考え→思い→行動 | なぜそうするか（考え）→相手は何を思うか（思い）→だから何をするか（行動）で設計すると？ | 相手が動かない行動計画 | 原則: principles-relationship / mindset: mindset-organization |
| GF-10 | 他者矢印への転換 | 矢印が自分に向いていませんか？ 相手に矢印を向けると打ち手はどう変わりますか？ | 自己犠牲・他者比較で消耗 | mindset: mindset-self（MS-016 / MS-020） |

## 出典の引き方

- `related_knowledge` のカテゴリ名は `router.json` の routing_rules / categories で該当 `*.json` に解決する。
- 代表 ID（PR-039/PR-035/PR-032・MS-020/MS-016/MS-007 等）は intent/background を Read で確認して出典に付す。
- グラフ consult（`consult-harness-artifact-graph.py`）が利用可能なら `--query-type local` で関連 node を裏取りに使う。起動条件・不在時の fallback（harness 不在→knowledge 単独 / knowledge 不在→skip / exit2→WARN skip）は `../../references/graph-consult-fallback-contract.md` が正本。グラフ全不在/zero-hit 時は本カタログ＋デュアルパスのみで提示し、その旨を consult_evidence に記す。

## 不変則

- フレームは **見方の提示**であり、選択と言語化はユーザーが行う（AI は構造化・検証のみ）。
- 引用する北原原則/マインドセットは1対話あたり1〜2件まで（CONST_004）。
- 目標設定そのものの相談は本カタログの対象外（`run-ubm-goal-setting` へ誘導）。
