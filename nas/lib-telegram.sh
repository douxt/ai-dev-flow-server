#!/bin/bash
# NAS 侧 Telegram 发送库（被 alert-flush.sh / daily-digest.sh source）
# 依赖：state/telegram.conf（PROXY/TOKEN/CHAT_ID，600 权限）；curl 走网关 Clash 代理
# 用法：tg_send "消息文本"   → 0 成功 / 非 0 失败
set -uo pipefail

TG_CONF=${TG_CONF:-/volume1/docker/langbot/state/telegram.conf}

tg_load() {
    if [ ! -r "$TG_CONF" ]; then
        echo "telegram.conf 不存在或不可读: $TG_CONF" >&2
        return 1
    fi
    # shellcheck disable=SC1090
    . "$TG_CONF"
    [ -n "${TOKEN:-}" ] && [ -n "${CHAT_ID:-}" ] || { echo "TOKEN/CHAT_ID 未配置" >&2; return 1; }
    return 0
}

tg_send() {
    local text="$1" resp
    [ -n "$text" ] || return 2
    resp=$(timeout 20 curl -s -m 15 ${PROXY:+-x "$PROXY"} \
        -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${CHAT_ID}" \
        --data-urlencode "text=${text}" \
        --data-urlencode "disable_web_page_preview=true" 2>&1)
    case "$resp" in
        *'"ok":true'*) return 0 ;;
        *) echo "tg_send failed: $(printf '%s' "$resp" | head -c 200)" >&2; return 1 ;;
    esac
}
