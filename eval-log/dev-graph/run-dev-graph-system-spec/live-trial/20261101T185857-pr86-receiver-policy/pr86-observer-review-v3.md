# observer v3 coverage修復案の独立レビュー

**PASS**。blocker: なし。

対象 `/tmp/pr86-tool-observer-v3.py` SHA-256: `d0ac1e4c9dc5053bf5262bd779bcfe4de6ba1699bbc288352b07b0966fc79184`。
独立測定: `/tmp/pr86-observer-v3-independent-probe.json`（同じSHAに束縛）。

105 rawは一切読まず、許可済み104 frozen mainとC08原本、および `/tmp` の合成入力だけで評価した。コード/Wは無編集。稼働中v2のSHAは `d80a0f69bf214af01485c04f7a6eabfc6df48b529ff7864765e95508aac6ddc0` で不変だった。

## 実測

- 以前の25境界probeを含む **42 probe全通過**。WebFetch/WebSearchのsuccess/errorについてinput・result content・is_error・native toolUseResultを無改変保持。UUID再掲、逆順pair、marker反射も確認した。
- 104 main: **78 event**（tool_call73、正規Skill本文注入5）。151箇所のsource prefix bytes/SHAと全payloadが原本に一致。Web追加により既存eventが変わる退行は無い（marker/schemaの版差を除いた全内容がv2と一致）。
- 104 C08: v3は **11 event**（Read7、WebFetch4）。native assistant原本から別に導出したWebFetch ID集合と完全一致し、22箇所のsource prefixおよび実input/result/native metadataに不一致0。v2では7 eventだったため、欠けていた実WebFetch4件が増えたことを直接確認した。
- 一時的な隔離native-homeへ上記2 streamだけを複写してscanし、indexの全stream bytes/SHAが原本と一致した。実105や実homeへの探索/scanはしていない。この2-stream scanは78+11件であり、旧版main89件のmeasurementを流用したものではない。

## 退行と境界

差分は5 primitiveへのcoverage追加、marker/schema v3、index metadataに限られる。既存のanchored write（全component NOFOLLOW、dirfd、random O_EXCL/O_NOFOLLOW temporary、非regular target拒否、dirfd replace）、競合tool ID/UUID排除、結果と注入の時系列、成功Skill/commandName/host metadata/親UUID/正規Base directoryへの束縛は維持された。symlinkのnegative probeでも外側sentinelは不変だった。

Readのrealpath alias、Bash入力alias、input/resultの固有markerによるobserver自己I/O除外も通過した。Agentの直接結果、api-request-blob再掲は追加coverageへ入らない。Skill本文保護も同じpositive/negativeで再確認した。

indexは `Read/Bash/Skill/WebFetch/WebSearch` を明示し、除外対象と「coverage外のabsenceは何も証明しない」を記録する。Webの保存結果は実際のengine I/Oが起きた証拠であり、本文の指示/事実の真実性・信頼性を付与しないと明記される。記録処理はネットワーク取得を再実行せず、source/validator/正規workflowの動作も代替しない。被験側のshell/home/network権限を拡張する変更はない。

このPASSは別fileのharness coverage修復案の範囲であり、稼働中105を救済・改変したものではなく、105のgoal判定でもない。将来の実走ではstop後の最終scan/freezeと、別fresh evaluatorによる凍結原本からのevent集合・全payload/metadata/prefix/stream SHAの再照合を予定どおり実施すること。
