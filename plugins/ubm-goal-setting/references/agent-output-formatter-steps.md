# output-formatter の実行手順（Step 1〜4）

`agents/output-formatter.md` の「思考プロセス」の正本。output-formatter は Step 1 の前にこのファイルを Read し、この順で実行する。各 Step の要約と完了条件は `agents/output-formatter.md` の Layer 6「実行フロー」の表と同じ。用語・対応表・命名規則は `${PLUGIN_ROOT}/references/agent-output-formatter-rules.md` にある。

## Step 1: フォーマットテンプレート取得

1. `Read: $PLUGIN_ROOT/skills/run-ubm-goal-setting/references/output-formats.md`
2. goal_typeに対応するテンプレートセクションを選択
3. `quarterly` の場合: 直近の既存期報ファイルもReadでスタイル・語彙のみを動的学習（output-formats.mdと並列Read可能）。旧名の期報ファイル（`UBM - 3-月報（２ヶ月） - …` / `UBM - 3-期報 - …`）も参照対象に含める。**旧期報の重複見出し（【今期の売上目標】が2回出る等）・禁止セクション（【プロジェクト別タスク】）・旧サマリー見出し（【2ヶ月の目標】）は模倣しない。見出し集合・セクション順・A1は output-formats.md を正本とする**
4. `yearly` の場合: 期報のテンプレートを骨格として期間語を「今年 / 前年」に置き換える。到達点（月間売上到達点・継続コンサル人数）を【今年の最重要数字】の注記へ写す（**到達点の値は挑戦宣言が正本。下位層の数字から逆算して書き換えない**）。
   - 値は次の順で取る: (1) interview_data の `yearly_monthly_sales_goal` / `yearly_continuous_consult_count`（Phase 3 で挑戦宣言から提示し、利用者が確認した値） (2) past_data の「1年層の到達点」で、出所が挑戦宣言のもの (3) 同じく、出所が現行の1年目標の注記のもの。どれにも無いか `[要ヒアリング]` のままなら、値を作らずに親へ差し戻す。
   - 読むファイルは親が渡したパスだけにする: 挑戦宣言は past_data の「1年層の到達点」の出所に書かれた絶対パス、既存の1年目標は peer_paths の `yearly`。この2つを output-formats.md と並列 Read する。ディレクトリを探して最新の挑戦宣言を選ぶことはしない（Glob を持たない。選ぶのは info-collector）。パスが null なら、その理由を報告に載せて読まない。
   - interview_data の値が挑戦宣言の原文と食い違うときは、どちらかに合わせて書かず、両方の値と出所を親へ返す。
5. `quarterly` / `monthly` の場合: peer_paths の `yearly`（同じ期の1年目標）があれば output-formats.md と並列 Read し、その【今年の最重要数字】にある到達点2件（`月間売上到達点：<数値>` / `継続コンサル人数：<数値>`）を、期報は【今期の売上以外の成果目標】、月報は管理用セクションの【今月の最重要数字】へ、注記行で同値のまま写す（**正本は1年目標。下位層の数字から逆算して書き換えない**）。書き方は output-formats.md の「1年目標がある期の到達点の注記（期報）」と「1年目標がある期の到達点の注記（月報）」の例に従う。規則の正本は `skills/run-ubm-goal-setting/references/data-contract.md` §3.1.3「4層ロールアップ契約」。
   - 注記行は `（` で始め、節の見出しの直後（本文の成果目標より前）に置く。`>` で始めると成果目標の件数に入る。ラベルは言い換えない。本文の成果目標の行に同じラベルを使わない（抽出は節の先頭から最初に当たった行を取るため、本文の行が継承値として拾われる）。
   - peer_paths の `yearly` が null なら注記を置かず、その理由を報告に載せる。1年目標から2件のどちらかが取れないとき、または interview_data の `yearly_monthly_sales_goal` / `yearly_continuous_consult_count` が1年目標の値と食い違うときは、値を作らず、どちらかに合わせて書かず、両方の値と出所を親へ返す。

**完了条件**: 使用するテンプレートが確定している

## Step 2: データ整形

1. interview_dataから各セクションの値を抽出
2. past_dataから前回目標・実績を `output-formats.md` の「共通部品D 前回ブロック」のとおり転記する。週報・月報の `{{prev_not_doing_check}}` は interview_data の `prev_not_doing_check`（data-contract #37）から書き、null（初回）は同節の初回マーカーにする。月報の `{{principles}}` は interview_data の `principles`（data-contract #38）から1要素1行で書く
   - 月報・期報の【今(月|期)の最重要数字】に置く `今(月|期)の売上目標：{金額}` の1行は、【今(月|期)の売上目標】の値をそのまま写す（期報は節を置く場合だけ。`validate-goal-output.py` が一致を照合する。書き方は `output-formats.md` の月報の【今月の最重要数字】の注記と期報の読み替え規則）
3. 行動目標は interview_data の `actions[]`（data-contract #14）から組み立てる。要素ごとに `- [ ] {item_name}：{what}　期日{deadline_token}` を作り、`outcome_group` ごとのグループ見出し（`### → `）の下に置く。グループと行の並び・日付索引・月報の提出用（射影）は `output-formats.md` の「共通部品A 行動行」に従う
4. 数値ルール適用: 全角→半角変換、差分に+/-付与
5. 行動目標が `output-formats.md` の「共通部品A 行動行」に合うか（期日があるか）最終確認
6. テンプレートの変数を全て埋める

**完了条件**: テンプレートの全変数が埋まり、プレースホルダーが残っていない

## Step 3: 品質チェック+バリデーション

1. `agents/output-formatter.md` の「品質チェックリスト（コンテンツ検証）」（Layer 4）を上から順に全項目確認する（件数で数えない）
2. 一時ファイルとしてWrite（`monthly` は提出用セクション＋管理用セクションを含む1ファイル）
3. 正本 validation-gates.md の表を上の行から順に実行する

**決定論ゲート**: `skills/run-ubm-goal-setting/references/validation-gates.md` の「入力の出所と保存前後の対象」「決定論ゲート」「受領書」を Read し、その契約を適用する。下書きの作成前に Bash で一時パスを1回解決し、Write へ渡す。peer_paths は info-collector の同じ期の選択結果で、作成中の層を draft_path に置き換えて照合する。

4. `monthly` も**1ファイル**なので各スクリプトは保存前/保存後に1回ずつ（`--type monthly`）。提出用セクションの見出しに「（提出）」が付いていることで重複見出し検査（完全一致）を通り、`## 【今月の行動目標（提出）】` は所属の検査（C4/C5）と件数の上限（S3）からも外れる（提出用はグループ見出しを持たない1行1行動のため）
5. 層間照合は validation-gates.md、誤記と月・週の軌道修正の区別は正本「四層（1年目標・期報・月報・週報）の連携」、軌道修正の記録は `output-formats.md` の「共通部品E 軌道修正記録」に従う。記録のある局所調整を一律に上位値へ戻さない。既存peerの変更が必要なら親へ差し戻す。1年層の引数は validation-gates.md の「IN3 の1年層の引数」に従い、未照合・WARN・`[調整確認]` の件数と結果を受領書へそのまま残す。
6. エラーごとの停止/修復は validation-gates.md の終了コードの契約に従う（環境不備を本文修復で隠さない）
7. 報告の形は `agents/output-formatter.md` の「インターフェース」の「出力」に従う

**完了条件**: 品質チェック全項目OK ＋ 決定論ゲートの、回す条件に当たる各行が rc=0

## Step 4: 検証済み下書きの返却

1. 正式保存予定先を `{vault_root}/05_Project/UBM/目標設定/<ファイル名>` として解決する。ファイル名は `${PLUGIN_ROOT}/references/agent-output-formatter-rules.md` の「ファイル命名規則」の表に従う（どの種別も1本。`archive/` には置かない）。
2. 一時draft_pathの絶対パス・SHA256・正式保存予定先・保存前の全ゲート受領書を親へ返す。vault/ Daily.md/ archiveへWrite/Editせず、移動・削除もしない。
3. 正式保存とarchiveの分離は親が `references/guarded-publication-contract.md` のmanifestを作り、ユーザー確認と中央guard executeで行う。親はvalidation-gates.mdに従いfinal_pathで保存後ゲートを各1回実行し、非0ならDaily更新を止める。

**完了条件**: 検証済み下書き・SHA256・保存予定先が親へ返る状態。
