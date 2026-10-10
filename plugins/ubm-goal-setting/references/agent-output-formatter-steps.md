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

**完了条件**: 使用するテンプレートが確定している

## Step 2: データ整形

1. interview_dataから各セクションの値を抽出
2. past_dataから前回目標・実績の数値を転記
3. 数値ルール適用: 全角→半角変換、差分に+/-付与
4. 行動目標に期日と数値が含まれているか最終確認
5. テンプレートの変数を全て埋める

**完了条件**: テンプレートの全変数が埋まり、プレースホルダーが残っていない

## Step 3: 品質チェック+バリデーション

1. `agents/output-formatter.md` の「品質チェックリスト（コンテンツ検証）」（Layer 4）を上から順に全項目確認する（件数で数えない）
2. 一時ファイルとしてWrite（`monthly` は提出用セクション＋管理用セクションを含む1ファイル）
3. 正本 validation-gates.md の表を上の行から順に実行する

**決定論ゲート**: `skills/run-ubm-goal-setting/references/validation-gates.md` の「入力の出所と保存前後の対象」「決定論ゲート」「受領書」を Read し、その契約を適用する。下書きの作成前に Bash で一時パスを1回解決し、Write へ渡す。peer_paths は info-collector の同じ期の選択結果で、作成中の層を draft_path に置き換えて照合する。

4. `monthly` も**1ファイル**なので各スクリプトは保存前/保存後に1回ずつ（`--type monthly`）。提出用セクションの見出しに「（提出）」が付いていることで重複見出し検査（完全一致）を通り、`## 【今月の行動目標（提出）】` は所属の検査（C4/C5）と件数の上限（S3）からも外れる（提出用はグループ見出しを持たない1行1行動のため）
5. 層間照合の分担と適用条件は validation-gates.md を参照。補足: `validate-goal-output.py` と `validate-goal-linkage.py` はどちらも1本のファイルしか見ないため、期報の数字を直して月報・週報へ降ろし忘れても rc=0 で通る（層をまたぐ値を突き合わせる口が無い＝分母0件）。不一致が出たら**上の層を正本として**作成中の下書きを修正する（1年 → 期報 → 月報 → 週報）。既存 peer の変更が必要なら親へ差し戻す（下から上へ直さない）。**1年目標が存在する期では `validate-cross-level.py` に必ず `--yearly` を渡す**。1年層のアンカーは `requires_level="yearly"` なので、`--yearly` を渡さない呼び出しでは照合されず `[未照合]` として件数つきで列挙され、それでも rc=0 になりうる。渡さなかった場合はその件数をそのまま報告に載せる（照合できていない分を合格に数えない）
6. エラーごとの停止/修復は validation-gates.md の終了コードの契約に従う（環境不備を本文修復で隠さない）
7. 報告の形は `agents/output-formatter.md` の「インターフェース」の「出力」に従う

**完了条件**: 品質チェック全項目OK ＋ 決定論ゲートの、回す条件に当たる各行が rc=0

## Step 4: 検証済み下書きの返却

1. 正式保存予定先を `{vault_root}/05_Project/UBM/目標設定/<ファイル名>` として解決する。ファイル名は `${PLUGIN_ROOT}/references/agent-output-formatter-rules.md` の「ファイル命名規則」の表に従う（どの種別も1本。`archive/` には置かない）。
2. 一時draft_pathの絶対パス・SHA256・正式保存予定先・保存前の全ゲート受領書を親へ返す。vault/ Daily.md/ archiveへWrite/Editせず、移動・削除もしない。
3. 正式保存とarchiveの分離は親が `references/guarded-publication-contract.md` のmanifestを作り、ユーザー確認と中央guard executeで行う。親はvalidation-gates.mdに従いfinal_pathで保存後ゲートを各1回実行し、非0ならDaily更新を止める。

**完了条件**: 検証済み下書き・SHA256・保存予定先が親へ返る状態。
