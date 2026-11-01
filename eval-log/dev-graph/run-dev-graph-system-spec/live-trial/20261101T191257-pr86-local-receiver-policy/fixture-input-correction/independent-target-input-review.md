PASS（v4の入力補完のみ）

- targets以外のstate全fieldはv3と完全一致。旧targets4件と旧references4件も保持し、Kubernetes1件を追加。
- 隔離scratchで正規set-targets・assembler・C13・compileを独立再実行し全exit0。state・出典JSON・全10章がv4とbytes一致。
- 保存HTTP200 metadataとHTMLの521401 bytes・更新日時・SHAが出典recordへ対応。独立GETもHTTP200で本文bytes/SHAが完全一致。
- 出典はinfrastructure/backend/maintenance-opsの宣言3章へ反映。public全47 fileが元Dと完全一致。評価/PASS/graph seedはない。

不足: 今回の限定scopeではなし。

この判定は新native trialのgoal達成・受入PASSや実利用者承認ではない。111のFAILは保持し、新trialのrawは未読。詳しい根拠・検証限界は /tmp/pr86-positive-input-v4-review.json に記録した。
