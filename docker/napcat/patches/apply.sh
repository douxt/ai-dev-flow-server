#!/bin/bash
# napcat patches 一键部署 + 回滚
# 用法: ./apply.sh            # 部署
#       ./apply.sh --rollback  # 回滚
#
# 宿主机直接执行 (需能 ssh root@nas)

set -euo pipefail
NAS="root@nas"
CONTAINER="napcat"
NAP="/app/napcat/napcat.mjs"
BAK_DIR="/tmp/napcat-backups"

# ============ 颜色 ============
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
say()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
die()  { echo -e "${RED}[X]${NC} $*"; exit 1; }

# ============ 工具函数 ============
nexec() {
    local quoted=()
    for a in "$@"; do quoted+=("$(printf '%q' "$a")"); done
    ssh -oBatchMode=yes "$NAS" docker exec "$CONTAINER" "${quoted[@]}"
}
ncp()   { ssh -oBatchMode=yes "$NAS" "docker cp $*"; }

# ============ 回滚 ============
if [[ "${1:-}" == "--rollback" ]]; then
    say "开始回滚..."

    # 找最新备份
    LATEST=$(ssh -oBatchMode=yes "$NAS" "ls -t $BAK_DIR/napcat.mjs.* 2>/dev/null | head -1" || true)
    if [[ -z "$LATEST" ]]; then
        die "未找到备份文件 ($BAK_DIR/napcat.mjs.*)"
    fi
    say "从备份恢复: $LATEST"

    ncp "$LATEST" "$CONTAINER:$NAP"
    say "恢复完成，重启 napcat 进程..."
    nexec sh -c 'kill -TERM $(pgrep -f "node.*napcat" | head -1)'
    sleep 10

    # 验证重启
    if nexec pgrep -f "node.*napcat" > /dev/null 2>&1; then
        say "napcat 已重启"
    else
        die "napcat 重启失败! 请手动检查"
    fi
    say "回滚完成"
    exit 0
fi

# ============ 部署 ============
say "napcat patches 部署开始"
say "目标: $CONTAINER 容器 / $NAP"

# Step 0: 创建远程备份目录
ssh -oBatchMode=yes "$NAS" "mkdir -p $BAK_DIR"

# Step 1: 备份原始文件 (时间戳命名 + 远程持久化)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
say "备份原始文件 (时间戳: $TIMESTAMP)..."
nexec cp "$NAP" "${NAP}.bak.${TIMESTAMP}"
ncp "$CONTAINER:${NAP}.bak.${TIMESTAMP}" "$BAK_DIR/napcat.mjs.${TIMESTAMP}"
ncp "$CONTAINER:$NAP" "$BAK_DIR/napcat.mjs.${TIMESTAMP}.orig"
say "备份完成: $BAK_DIR/napcat.mjs.${TIMESTAMP}"

# Step 2: 检查目标字符串存在
say "检查 Patch 1a 目标字符串..."
if ! nexec grep -qF 'let multiMsgs = await this.getMultiMessages(msg, parentMsgPeer);' "$NAP"; then
    # 尝试回滚并退出
    ncp "$BAK_DIR/napcat.mjs.${TIMESTAMP}" "$CONTAINER:$NAP"
    die "Patch 1a: 目标字符串不存在 (napcat 版本可能不匹配)"
fi
say "  Patch 1a 目标 OK"

say "检查 Patch 1b 目标字符串..."
if ! nexec grep -qF 'multiMsgs = await this.core.apis.PacketApi.pkt.operation.FetchForwardMsg(element.resId);' "$NAP"; then
    ncp "$BAK_DIR/napcat.mjs.${TIMESTAMP}" "$CONTAINER:$NAP"
    die "Patch 1b: 目标字符串不存在 (napcat 版本可能不匹配)"
fi
say "  Patch 1b 目标 OK"

# Note: Patch 2 (quote-url/base64 清空) 不通过 sed 自动部署
# 原因: "file: element.fileName," 在 picElement/fileElement/videoElement 3 处重复
# 当前 enableLocalFile2Url:true + 插件 _strip_base64 已覆盖 base64 问题
# 如需手动干预，参见 README.md §Patch 2

# Step 3: 应用 Patch 1a (getMultiMessages 10s 超时)
say "应用 Patch 1a: getMultiMessages 10s 超时..."
nexec sed -i \
    's/let multiMsgs = await this\.getMultiMessages(msg, parentMsgPeer);/let multiMsgs = await Promise.race([this.getMultiMessages(msg, parentMsgPeer), new Promise(resolve => setTimeout(() => resolve(null), 10000))]);/' \
    "$NAP"

# Step 4: 应用 Patch 1b (FetchForwardMsg 5s 超时)
say "应用 Patch 1b: FetchForwardMsg 5s 超时..."
nexec sed -i \
    's/multiMsgs = await this\.core\.apis\.PacketApi\.pkt\.operation\.FetchForwardMsg(element\.resId);/multiMsgs = await Promise.race([this.core.apis.PacketApi.pkt.operation.FetchForwardMsg(element.resId), new Promise(resolve => setTimeout(() => resolve(null), 5000))]);/' \
    "$NAP"

# Step 5: 验证替换成功
say "验证替换..."
# Patch 1a 验证
if nexec grep -qF 'Promise.race([this.getMultiMessages(msg, parentMsgPeer), new Promise(resolve => setTimeout(() => resolve(null), 10000))])' "$NAP"; then
    say "  Patch 1a 验证通过"
else
    warn "  Patch 1a 验证失败! 回滚..."
    ncp "$BAK_DIR/napcat.mjs.${TIMESTAMP}" "$CONTAINER:$NAP"
    die "回滚完成，部署中止"
fi

# Patch 1b 验证
if nexec grep -qF 'Promise.race([this.core.apis.PacketApi.pkt.operation.FetchForwardMsg(element.resId), new Promise(resolve => setTimeout(() => resolve(null), 5000))])' "$NAP"; then
    say "  Patch 1b 验证通过"
else
    warn "  Patch 1b 验证失败! 回滚..."
    ncp "$BAK_DIR/napcat.mjs.${TIMESTAMP}" "$CONTAINER:$NAP"
    die "回滚完成，部署中止"
fi

# Step 6: 语法检查跳过 (容器内无独立 node 二进制)
# grep 字符串验证已足够; napcat 启动失败时可快速回滚
say "语法检查: 跳过 (容器内无 node CLI, grep 验证已通过)"

# Step 8: 重启 napcat 容器
say "重启 napcat 容器..."
ssh -oBatchMode=yes "$NAS" "docker restart $CONTAINER"
say "容器重启中..."
sleep 5

# Step 9: 等待 napcat 恢复
say "等待 napcat 恢复..."
for i in $(seq 1 15); do
    sleep 2
    if ssh -oBatchMode=yes "$NAS" "docker exec $CONTAINER pgrep -f qq" > /dev/null 2>&1; then
        say "napcat 进程已恢复 (${i}x2s)"
        break
    fi
    if [[ $i -eq 15 ]]; then
        die "napcat 进程在 30s 内未恢复! 请手动检查 docker logs napcat"
    fi
done

# Step 10: 部署成功
say ""
say "======================================"
say "  部署完成!"
say "  备份: $BAK_DIR/napcat.mjs.${TIMESTAMP}"
say "  回滚: $0 --rollback"
say "  检查: ssh root@nas docker logs napcat --tail 20"
say "======================================"
