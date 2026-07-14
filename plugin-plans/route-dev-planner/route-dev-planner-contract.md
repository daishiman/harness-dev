# route-dev-planner-contract

> 開発構想を plugin ルート / system ルートへ機械 dispatch する router の I/O・分類・フォールバック契約 (正本)。
> 判定基準の正本は `plugin-plans/dev-graph/references/execution-tracker-contract.md §0`。本契約はそれを引用・機械化する (§0 を複製・改変しない)。

## 0. 責務 (1 行)

構想文を受け取り「plugin 実体を作るのか / system コードを作るのか」だけを判定して正しいプランナーを起動する。**計画生成・tracker 投影・build は行わない** (各プランナーへ委譲)。

## 1. I/O 契約

### 入力
| 引数 | 必須 | 説明 |
|---|---|---|
| `concept` | yes | 開発構想 1 件 (自然文)。曖昧でも停止せず confidence を下げて判定する |
| `--intake-json <path>` | no | skill-intake / 構想ヒアリング結果。あれば分類シグナルの補強に使う |

### 出力 (routing-decision.json)
```json
{
  "route": "plugin | system | split | ambiguous",
  "target_planner": "plugin-dev-planner | dev-graph | null",
  "confidence": 0.0,
  "reason": "<判定根拠を 1-2 文で。どのシグナルが効いたか>",
  "dispatch_command": "<起動する slash-command。ambiguous/split では null>",
  "split_parts": null
}
```
- `route=plugin` → `target_planner=plugin-dev-planner`, `dispatch_command="/plugin-dev-plan \"<concept>\""`。
- `route=system` → `target_planner=dev-graph`, `dispatch_command="/dev-graph decompose \"<concept>\""` (**マクロ分解が起点**。§2 参照)。**注意**: `/system-dev-plan` は system-dev-planner 所有のミクロ入口で feature 解決済みを前提とするため、router は素の構想を直接そこへ流さない。`/system-dev-plan` は dev-graph が ready feature ごとに起動する下流ステップ (C51) であり router の dispatch 対象ではない。
- `route=split|ambiguous` → `target_planner=null`, `dispatch_command=null` (§4 フォールバック)。

## 2. dispatch 表 (execution-tracker-contract §0 と 1:1)

| route | 起点プランナー | router が起動する入口 | 後続 (router 対象外・下流が担う) |
|---|---|---|---|
| **plugin** | plugin-dev-planner | `/plugin-dev-plan "<concept>"` | task-graph → §6 consumer beads 直接投影 (dev-graph 非経由) |
| **system** | dev-graph (マクロ) | `/dev-graph decompose "<concept>"` | dev-graph マクロ分解 (feature+architecture+機能間depends_on) → ready feature ごとに dev-graph が `/system-dev-plan` を起動 (C51・ミクロ 13 task) → dev-graph atomic 登録 → §1-§5 tracker_binding 解決 |

- router が起動するのは各ルートの**入口コマンド1つ**のみ。system ルートの `/system-dev-plan` (per-feature) は dev-graph が下流で自動起動するもので router は呼ばない (誤って feature 未解決の構想を `/system-dev-plan` へ渡さない)。
- 成果物の所属は起点プランナー側に従い、`external_ref` prefix (plugin=`<plan-slug>/<node-id>` / system=`tasks/<id>`) で二重登録を防ぐ (§0)。

## 3. classify_construction_target(concept, intake) → {route, confidence, reason}

判定は「成果物が最終的にどこへ置かれるか」を軸にする。**正本の判定基準 (§0)**: 成果物が `plugins/<slug>/` 配下の Claude Code plugin 実体なら plugin ルート、導入先リポジトリのアプリケーション/システムコードなら system ルート。両方を含む構想は `split`、どちらとも決めきれない低信頼は `ambiguous`。

分類シグナルの本体 (どの語・構造が plugin 構築 / system 構築 を示すか、および tie-break) は下記で確定する (best-practice 選定済み)。周辺 (入力正規化・出力整形・§4 フォールバック接続) は本契約で確定済み。設計原則: **一次軸は §0 の「成果物がどこに置かれるか」**、語彙スコアはその proxy、判定は **fail-closed** (迷ったら split/ambiguous へ倒し、誤 dispatch より確認を優先する)。

```
# classify_construction_target の分類シグナル定義 (best-practice 確定版)
# 入力: concept (正規化済み構想文), intake (任意)
# 出力: route ∈ {plugin, system, split, ambiguous}, confidence ∈ [0,1], reason
CONF_THRESHOLD = 0.60          # これ未満は dispatch せず ambiguous へ降格
SPLIT_MARGIN   = 0.34          # 優勢差がこれ未満で両シグナル陽性なら split

# --- 第1優先: 明示的な成果物配置 (§0 一次軸・決定的) -------------------------
# concept か intake が成果物の置き場を明示していれば語彙スコアより優先する:
#   "plugins/<slug>/ 配下" / "SKILL.md" / "plugin.json" / "marketplace" を作る
#        → route=plugin,  confidence 0.90 (+intake裏取りで 0.95)
#   導入先リポジトリの "アプリ/サービス/API 実体" を作る
#        → route=system,  confidence 0.90 (+intake裏取りで 0.95)
#   intake.artifact_class ∈ {plugin-plan, skill*} → plugin 裏取り / {system-spec, app*} → system 裏取り

# --- 第2優先: 語彙シグナルスコア (配置が非明示のとき) -------------------------
PLUGIN_SIGNALS = ハーネス語彙:  skill / sub-agent / slash-command(/コマンド) / hook / script(plugin) /
    "Claude Code plugin" / SKILL.md / plugin.json / marketplace / ".claude/ 配下" / "エージェントに〜させる"
SYSTEM_SIGNALS = プロダクト語彙: API / エンドポイント / DB・データベース / フロントエンド・画面・UI /
    バックエンド / インフラ / デプロイ / 認証 / "エンドユーザー向け機能" / 導入先アプリのビジネスロジック
# p = PLUGIN_SIGNALS ヒット数, s = SYSTEM_SIGNALS ヒット数
# dominant = max(p,s); other = min(p,s); margin = (dominant - other) / (dominant + other + 1)

# --- tie-break (fail-open 禁止・§4 接続) -------------------------------------
#   p>0 かつ s>0 かつ margin < SPLIT_MARGIN → route=split     (両立。split_parts に plugin/system 部分を分解提示)
#   dominant == 0                          → route=ambiguous (シグナル皆無。§0 判定表を提示し確認)
#   margin ≥ SPLIT_MARGIN                  → route=優勢側,   confidence = clamp(0.5 + margin*0.5 [+intake 0.1], 0, 0.95)
#   confidence < CONF_THRESHOLD            → route=ambiguous へ降格 (低信頼は dispatch しない)
# reason には効いた第1優先根拠 or (p,s,margin) と代表ヒット語を必ず残す (監査可能性)
```

## 4. フォールバック (fail-open 禁止)

- **split**: plugin と system の両方を含む構想は自動でどちらかへ流さず、`split_parts` に plugin 部分 / system 部分の分解案を提示し、それぞれを対応プランナーへ投入するようユーザー/orchestrator へ促す (§0 「両方を含む構想は分割し、それぞれのプランナーへ投入する」)。
- **ambiguous**: confidence が閾値未満なら dispatch せず、§0 判定表を提示してユーザー確認を求める (router は勝手に決めない)。
- router 不在・無効化時も §0 判定表を人間/orchestrator フォールバックとして維持する。

## 5. 責務境界

- router は **dispatch のみ**。plan 生成 (plugin-dev-planner / dev-graph / system-dev-planner)、tracker 投影 (execution-tracker-contract §1-§7)、build (capability-build / task-graph build) は一切行わない。
- 判定基準の唯一の正本は execution-tracker-contract §0。本契約が §0 と矛盾した場合は §0 を優先し本契約を Edit で追従させる (分類基準の二重管理を避ける)。
