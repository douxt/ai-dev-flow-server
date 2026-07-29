#!/bin/bash
# ===========================================================================
# rollback.sh — Silent Observer 部署一键回滚
#
# 用法:
#   bash rollback.sh              # 回滚到上次备份
#   bash rollback.sh --backup     # 仅备份当前版本（不执行回滚）
#   bash rollback.sh --status     # 查看备份状态
#
# 前置条件:
#   - SSH 到 NAS 可用（ssh root@nas）
#   - 已用 --backup 创建过备份
# ===========================================================================

set -euo pipefail

NAS="root@nas"
DOCKER="/volume1/@appstore/ContainerManager/usr/bin/docker"
CONTAINER="langbot-plugin"
PLUGIN_DIR="/app/data/plugins/dou__langbot-silent-observer"
BACKUP_DIR="/app/data/plugins/.silent-observer-backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[rollback]${NC} $*"; }
warn() { echo -e "${YELLOW}[rollback]${NC} $*"; }
err()  { echo -e "${RED}[rollback]${NC} $*"; }

do_backup() {
    local label="${1:-$TIMESTAMP}"
    log "备份当前版本 → $label"

    ssh "$NAS" "$DOCKER exec $CONTAINER mkdir -p $BACKUP_DIR"

    # 备份关键文件
    local files=(
        "components/event_listener/default.py"
        "manifest.yaml"
        "store/kb_store.py"
        "service/vision.py"
        "service/timeline.py"
        "util/text.py"
        "util/image.py"
    )

    for f in "${files[@]}"; do
        ssh "$NAS" "$DOCKER exec $CONTAINER sh -c \"cp $PLUGIN_DIR/$f $BACKUP_DIR/${f##*/}.$label 2>/dev/null || true\""
    done

    # 备份全量（tar）
    ssh "$NAS" "$DOCKER exec $CONTAINER sh -c \"cd $PLUGIN_DIR && tar czf $BACKUP_DIR/full.$label.tar.gz . 2>/dev/null || true\""

    # 记录备份元信息
    ssh "$NAS" "$DOCKER exec $CONTAINER sh -c \"echo '$label $(date -Iseconds)' >> $BACKUP_DIR/backup.log\""

    log "备份完成: $label"
    log "备份列表:"
    do_status
}

do_status() {
    ssh "$NAS" "$DOCKER exec $CONTAINER sh -c \"cat $BACKUP_DIR/backup.log 2>/dev/null || echo '(无备份)'\""
}

do_rollback() {
    local label="${1:-}"

    # 列出可用备份
    log "可用备份:"
    ssh "$NAS" "$DOCKER exec $CONTAINER sh -c "cat $BACKUP_DIR/backup.log 2>/dev/null" || {
        err "无可用备份！先执行 bash rollback.sh --backup 创建备份"
        exit 1
    }

    if [ -z "$label" ]; then
        # 使用最新备份
        label=$(ssh "$NAS" "$DOCKER exec $CONTAINER sh -c "tail -1 $BACKUP_DIR/backup.log 2>/dev/null" | awk '{print $1}')
        if [ -z "$label" ]; then
            err "无法确定最新备份标签"
            exit 1
        fi
        warn "使用最新备份: $label"
    fi

    # 确认
    echo ""
    warn "============================================"
    warn "  即将回滚到备份: $label"
    warn "  容器 $CONTAINER 将重启"
    warn "  生产群 Bot 会短暂不可用 (~15s)"
    warn "============================================"
    echo ""
    read -p "确认回滚? (输入 yes 继续): " confirm
    if [ "$confirm" != "yes" ]; then
        log "已取消"
        exit 0
    fi

    # 执行回滚：从 tar 恢复
    log "正在从 $label 恢复..."
    ssh "$NAS" "$DOCKER exec $CONTAINER sh -c \"
        cd /tmp &&
        tar xzf $BACKUP_DIR/full.$label.tar.gz &&
        cp -r ./* $PLUGIN_DIR/ &&
        rm -rf $PLUGIN_DIR/__pycache__ &&
        echo 'rolled back to $label at \$(date -Iseconds)' >> $BACKUP_DIR/rollback.log
    \""

    # 重启容器
    log "重启容器..."
    ssh "$NAS" "$DOCKER restart $CONTAINER"

    # 等待启动
    log "等待容器启动 (15s)..."
    sleep 15

    # 验证
    log "验证 init.log..."
    ssh "$NAS" "$DOCKER exec $CONTAINER cat /tmp/silent_init.log" || warn "无法读取 init.log"

    log "回滚完成: $label"
    log "请在 QQ 群发送 @Bot 测试基本功能"
}

# ============================================================================
# Main
# ============================================================================

case "${1:-}" in
    --backup)
        do_backup "${2:-$TIMESTAMP}"
        ;;
    --status)
        do_status
        ;;
    --rollback)
        do_rollback "${2:-}"
        ;;
    *)
        # 默认：回滚模式
        do_rollback "${1:-}"
        ;;
esac
