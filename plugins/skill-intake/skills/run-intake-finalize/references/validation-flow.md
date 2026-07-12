# Validation Flow (Phase 9)

順序: render → quality_gate → cross_check

| step | 失敗時の戻り先 |
|--|--|
| render | context 集約 (render-intake-final.py の入力 phase = output/<hint>/ 直下の per-phase JSON / context.json) |
| quality_gate (五軸) | 該当軸の Phase (出力先=Phase 4, 真の課題=Phase 5, ナレッジ資産=Phase 4 もしくは 5) |
| cross_check (md ↔ json) | render を再実行 |
