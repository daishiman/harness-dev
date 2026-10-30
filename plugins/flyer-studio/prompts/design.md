# 意図を持つ構図の設計

[指針ID正本](../references/design-knowledge-index.json)から目的・今回の未達に必要な規範/知見だけを読み、今回のbrief・確認済み素材・参照画像からconceptsとsceneを設計する。実行形式は[runtime](../references/runtime.md)。過去の座標や表層の模写を既定にしない。

brief.purposeの読者・価値・主要行動から、主題と読み順を決める。目的3項目が未確定なら、好みの構図を先に確定しない。

各案のdesignIntentに読む順序、意味群の役割と配置理由、色の役割と理由、機能を持つ余白の領域、均衡の理由、写真・画像と文字の関係を書く。余白を埋めることや数式一致を目的にしない。構図・文字・色の3レンズを候補比較に用い、今回の読者と主要行動への効用で採否を決める。

各案のdesignIntent.rejectedAlternativesに、その案で実際に比較して採らなかった候補と理由を書く。他案の理由を流用しない。候補を比べずに1つ目の思い付きを採用しない。

表現様式はbrief.stylePreferencesの任意の様式から案ごとに選ぶ。決まった選択肢に限らず、既知の例に無い様式は[様式の記述軸](../references/style-profiles.md#様式の記述軸)の8軸で具体化して設計へ反映する。style-proposals.jsonがあればchosenの提案の軸と根拠を起点にし、chosenBy=delegated（おまかせ）なら、pilotで様式も確かめてもらえるよう選んだ理由を残す。[DD11](../references/style-profiles.md)の判断点（伝わるもの・構図と余白・文字・起きやすい失敗）から、その様式で今回の目的が届く理由をimageRelationshipへ書く。様式と配色(tone)は別に決める。

中心軸はbrief.policyに従う。center=whole-pageならaxisGroupsの意味群だけを紙面全幅の中心に置き、QRを除いた領域の中心を使わない。center=noneなら軸を使わない構図の均衡理由をbalanceReasonへ書く。requiredTonesにある配色は案の集合に必ず含める。

案件方針の明示制約を守りつつ、上部の非対称・写真の占有・主題の方向を含めた異なる案を考える。生成・配置・検査の順序は[workflow](../references/workflow.md)へ。設計文を書いたことを実画像の合格にせず、最終レビューの5観点から同じ意図へ追跡できる状態で引き渡す。

改善は独立PASSのanalysisを制作の入力にし、[production-contract](../skills/run-create-flyer/references/production-contract.md)に従う。現在の未達、保持条件、使う指針IDからnext_actionを選び、その理由を残す。提案の採否と新画像の観察を混同しない。
