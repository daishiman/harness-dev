#!/usr/bin/env bash
# スケジューラーテンプレート（cron設定用）
# 用途: スキルの定期実行設定

set -euo pipefail

# ====================
# 設定
# ====================
SKILL_NAME="{{skill_name}}"
SKILL_PATH="{{skill_path}}"
CRON_EXPRESSION="{{cron_expression}}"  # 例: "0 9 * * *" (毎日9:00)
TIMEZONE="{{timezone}}"  # 例: "Asia/Tokyo"
LOG_DIR="${LOG_DIR:-./logs}"
NOTIFICATION_WEBHOOK="${NOTIFICATION_WEBHOOK:-}"

# ====================
# ヘルパー関数
# ====================
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

notify() {
    local status="$1"
    local message="$2"

    if [[ -n "$NOTIFICATION_WEBHOOK" ]]; then
        curl -s -X POST "$NOTIFICATION_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"status\":\"$status\",\"skill\":\"$SKILL_NAME\",\"message\":\"$message\"}" \
            > /dev/null || true
    fi
}

# ====================
# メイン処理
# ====================
main() {
    local log_file="${LOG_DIR}/${SKILL_NAME}-$(date +'%Y%m%d-%H%M%S').log"
    mkdir -p "$LOG_DIR"

    log "Starting scheduled execution: $SKILL_NAME"

    # タイムゾーン設定
    export TZ="$TIMEZONE"

    # スキル実行
    local start_time=$(date +%s)
    local exit_code=0

    if ! node "$SKILL_PATH" >> "$log_file" 2>&1; then
        exit_code=$?
        log "ERROR: Skill execution failed with exit code $exit_code"
        notify "failure" "Execution failed with exit code $exit_code"
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log "SUCCESS: Completed in ${duration}s"
        notify "success" "Completed in ${duration}s"
    fi

    return $exit_code
}

# ====================
# crontab登録用ヘルパー
# ====================
install_cron() {
    local script_path
    script_path=$(readlink -f "$0")

    # 既存のエントリを削除
    crontab -l 2>/dev/null | grep -v "$SKILL_NAME" | crontab - || true

    # 新しいエントリを追加
    (crontab -l 2>/dev/null; echo "$CRON_EXPRESSION $script_path") | crontab -

    log "Cron job installed: $CRON_EXPRESSION"
}

uninstall_cron() {
    crontab -l 2>/dev/null | grep -v "$SKILL_NAME" | crontab - || true
    log "Cron job uninstalled"
}

show_status() {
    echo "Skill: $SKILL_NAME"
    echo "Cron:  $CRON_EXPRESSION"
    echo "TZ:    $TIMEZONE"
    echo ""
    echo "Current crontab entries:"
    crontab -l 2>/dev/null | grep "$SKILL_NAME" || echo "(none)"
}

# ====================
# エントリポイント
# ====================
case "${1:-run}" in
    run)
        main
        ;;
    install)
        install_cron
        ;;
    uninstall)
        uninstall_cron
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {run|install|uninstall|status}"
        exit 1
        ;;
esac
