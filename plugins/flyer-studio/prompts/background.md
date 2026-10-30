# 背景生成への引き渡し

入力は今回の用途・読み手・選択表現・conceptsのdesignIntent・公開可能な素材。[共通規範](../references/design-rules.md#5-写真と背景白い外縁)に従い、文字を置く静かな領域、画像との接続、光・質感、外縁、不要要素を背景プロンプトへ具体化する。

conceptsのexpressionはbrief.stylePreferencesの任意の様式で、決まった選択肢に限らない。その様式を[様式の記述軸](../references/style-profiles.md#様式の記述軸)の8軸（媒体・質感・色の気質・密度など）で背景の要素へ具体化してbackgroundPromptに書き、既知の例にある様式ならその「背景生成」の判断点も使う。「描かない物」（文字・ロゴ・落款・実在人物の似顔・実在の作家名や作品名による模倣など）も明記する。様式名だけを書いて生成ツールに任せない。

背景の実体と、使用ツール・プロンプト・生成時刻・出力SHAを返す。保存したプロンプトだけを生成完了としない。生成と代替手段の扱いは[workflow](../references/workflow.md)、provenanceの形式は[runtime](../references/runtime.md#追加素材と生成記録)。生成後の紛らわしい文字・偽ロゴ・不自然な境界・人物の変化は実画像で確認する。
