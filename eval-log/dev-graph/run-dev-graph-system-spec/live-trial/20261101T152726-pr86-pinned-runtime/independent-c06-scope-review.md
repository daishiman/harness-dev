# 122 C06 scope独立レビュー

結論: `qa-009`が補助`qa_refs`に残ることを新しいtraceability mediumへ分類した件は、入力不足ではなく監査範囲の過剰拡張である。nativeの`AUDIT_VERDICT: FAIL`を変更しない。最終run判定は保留する。

## 原本

C06 `a1449746db8c235e1` raw全761,558bytesを `/tmp/pr86-sysspec122-c06-native.jsonl` に無改変保存した。SHA-256は `a811b9fd44d157f975a817da31c7782f5cc14c26097378ad4ff40d0fa8988571`。最終応答はnative L55で、全文を`/tmp/pr86-sysspec122-c06-final.txt`、JSON部分を`/tmp/pr86-sysspec122-c06-audit-original.json`へ保存した。

## 正本の射程

R6軸4は確定セルの`qa_ref`の欠落・danglingを調べる。active consumerの定義と停止条件も、確定セル`qa_ref`と`effective_source_refs`の`qa_ref`であり、補助`qa_refs`ではない。さらに`spec-state-contract.md` L403は「裏付け (`qa_refs`) からの参照は残してよい」と明示する。R6の「安全側」という一般原則は、明示許可を禁止へ変える根拠にならない。

ui-ux/webの主根拠は実在する`qa-003`。`qa-009`は実在し`superseded_by=qa-019`、置換先`qa-019`も実在しuser-decision/回答時刻を持つ。主`qa_ref`として`qa-009`を使う確定セルは0件。schema1.0でeffective_source_refsもない。C06自身も有効な置換、全主参照実在、全補助参照実在、danglingなしを明記している。

したがって、R6の「補助1件がdanglingならmediumにできる」という重大度の例は当てはまらない。今回の補助参照は、正本が保持を認める実在履歴である。保持から確定の根拠切れを導く具体的欠損は示されていない。

`aspect-criteria.md` 1aは、有効置換を閉じた検出とし、軸2mediumが補助qa_refsだけにある場合を注記に残す。一方で非軸2mediumはFAILになる。この表は軸の意味を定義し直す許可ではない。許可された履歴参照を新しい軸4へ付け替えると、主根拠と補助根拠を分ける正本の扱いを迂回してFAILを作る。

## 原本FAILの再現と境界

無改変の監査JSONを正規`aggregate-completeness.py --hearing ... --state ...`へ読み取り専用で渡すとexit1/FAILになり、唯一のblockingは当該traceability mediumだった。閉じた3件と注記2件も原本どおり再導出された。出力を`/tmp/pr86-sysspec122-c06-aggregate-original.json`へ保存した。これは集約器の誤動作ではなく、監査が正本外のblocking findingを生成した意味判定の問題を示す。

native・監査JSON・台帳・入力・正本を変更していない。新入力や正本変更を要求する根拠はこの件にはない。反実仮想のPASS reportも作成していない。C05やC02取込などが未達のままrunが終了した場合、そのgoalFAILはこのscope指摘によって覆らない。
