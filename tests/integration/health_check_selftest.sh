#!/bin/bash
# health-check.sh 零依赖自测 —— 不需要 bats / docker / 网络
#   用法: bash tests/integration/health_check_selftest.sh
# 原理: 用环境变量把脚本里的 DOCKER/STATE_DIR/LOG 指向沙箱，PATH/脚本路径上放一个假 docker，
#       断言脚本的日志、状态文件与 docker 调用序列。
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
TARGET="$REPO_ROOT/nas/health-check.sh"

PASS=0
FAIL=0
ok()  { PASS=$((PASS + 1)); echo "  ✅ $1"; }
bad() { FAIL=$((FAIL + 1)); echo "  ❌ $1"; }

has()  { if grep -q -- "$2" "$1" 2>/dev/null; then ok "$3"; else bad "$3 (缺少: $2)"; fi; }
hasnt() { if grep -q -- "$2" "$1" 2>/dev/null; then bad "$3 (不应出现: $2)"; else ok "$3"; fi; }
eq()   { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (期望 '$3'，实际 '$2')"; fi; }
le()   { if [ "${2:-999999}" -le "$3" ] 2>/dev/null; then ok "$1"; else bad "$1 (期望 ≤$3，实际 $2)"; fi; }

[ -f "$TARGET" ] || { echo "找不到被测脚本: $TARGET"; exit 1; }

# === 沙箱 + docker stub ===
setup() {
    SB=$(mktemp -d)
    mkdir -p "$SB/bin" "$SB/state"
    cat > "$SB/bin/docker" <<'STUB'
#!/bin/bash
echo "$*" >> "$STUB_CALLS"
case "$1" in
  inspect)
     if [ "${2:-}" = "langbot" ] && [ "${3:-}" = "--format" ]; then
         echo "${STUB_HEALTH:-healthy}"; exit 0
     fi
     [ "${STUB_NO_CONTAINERS:-0}" = "1" ] && exit 1
     exit 0 ;;
  exec)
     C="$2"; shift 2
     case "$*" in
       *st_mtime*)       echo "${STUB_HEARTBEAT_AGE:-5}"; exit 0 ;;
       *"grep -c 08E8"*) if [ "$C" = "napcat" ]; then echo "${STUB_LINK_COUNT:-1}"; else echo "${STUB_PORT_COUNT:-1}"; fi; exit 0 ;;
       *"grep -q 08E8"*) [ "${STUB_PORT_COUNT:-1}" -ge 1 ] && exit 0 || exit 1 ;;
       *"langbot:5300"*) echo "${STUB_HTTP_CODE:-200}"; exit 0 ;;
       *"/opt/QQ/qq"*)   [ "${STUB_NO_QQ_PROC:-0}" = "1" ] && exit 0; echo "${STUB_QQ_PROC:-/proc/143/cmdline}"; exit 0 ;;
     esac
     exit "${STUB_EXEC_EXIT:-0}" ;;
  logs)    [ "${STUB_LOGS_FAIL:-0}" = "1" ] && exit 1; cat "$STUB_LOGS" 2>/dev/null; exit 0 ;;
  restart) exit "${STUB_RESTART_EXIT:-0}" ;;
esac
exit 0
STUB
    chmod +x "$SB/bin/docker"
    export STUB_CALLS="$SB/calls.txt" STUB_LOGS="$SB/logs.txt"
    : > "$STUB_CALLS"; : > "$STUB_LOGS"
    export HC_DOCKER="$SB/bin/docker" HC_STATE_DIR="$SB/state" \
           HC_LOG="$SB/health.log" HC_SCAN_FILE="$SB/scan.txt"
    unset HC_FAIL_THRESHOLD HC_FORCE_FAIL STUB_NO_CONTAINERS STUB_HEARTBEAT_AGE \
          STUB_PORT_COUNT STUB_LINK_COUNT STUB_HTTP_CODE STUB_QQ_PROC STUB_NO_QQ_PROC \
          STUB_HEALTH STUB_LOGS_FAIL STUB_RESTART_EXIT STUB_EXEC_EXIT 2>/dev/null || true
    LOGFILE="$SB/health.log"
    CALLS="$SB/calls.txt"
    STATEFILE="$SB/state/health_fail_count"
}
runs() { for _ in $(seq 1 "$1"); do bash "$TARGET"; done; }

echo "=== health-check.sh 零依赖自测 ==="

# ---------- T1 五项全绿 ----------
echo "[T1] 五项探针全绿"
setup
bash "$TARGET"
has "$LOGFILE" "heartbeat probe=11111 link=1 restart=0" "写心跳行 probe=11111 link=1"
hasnt "$CALLS" "restart" "未触发重启"
[ ! -f "$STATEFILE" ] && ok "失败计数已清空" || bad "失败计数残留"
hasnt "$LOGFILE" "Traceback" "日志无 traceback"
hasnt "$LOGFILE" "can't open file" "日志无文件缺失报错"

# ---------- T2 连续 3 次失败触发重启 ----------
echo "[T2] HC_FORCE_FAIL 连续 3 次 → 重启"
setup
export HC_FORCE_FAIL=1
runs 3
unset HC_FORCE_FAIL
has "$LOGFILE" "FAIL #1" "记录 FAIL #1"
has "$LOGFILE" "FAIL #3" "记录 FAIL #3"
has "$LOGFILE" "threshold reached" "达到阈值"
has "$LOGFILE" "restart sequence complete" "重启序列完成"
[ ! -f "$STATEFILE" ] && ok "重启后计数清空" || bad "重启后计数未清空"
P1=$(grep -nE '^restart langbot-plugin$' "$CALLS" | head -1 | cut -d: -f1)
P2=$(grep -nE '^restart langbot$' "$CALLS" | head -1 | cut -d: -f1)
P3=$(grep -nE '^restart napcat$' "$CALLS" | head -1 | cut -d: -f1)
if [ -n "$P1" ] && [ -n "$P2" ] && [ -n "$P3" ] && [ "$P1" -lt "$P2" ] && [ "$P2" -lt "$P3" ]; then
    ok "重启顺序 plugin → langbot → napcat"
else
    bad "重启顺序错误 (plugin=$P1 langbot=$P2 napcat=$P3)"
fi

# ---------- T3 前置条件缺失 → SKIP ----------
echo "[T3] 容器不存在 → SKIP 不计失败"
setup
export STUB_NO_CONTAINERS=1
bash "$TARGET"
unset STUB_NO_CONTAINERS
has "$LOGFILE" "SKIP container-missing" "输出 SKIP"
hasnt "$CALLS" "restart" "未触发重启"
[ ! -f "$STATEFILE" ] && ok "未计入失败" || bad "被计入失败"

# ---------- T4 防抖锁 ----------
echo "[T4] 10 分钟防抖锁"
setup
date +%s > "$SB/state/health.lock"
bash "$TARGET"
has "$LOGFILE" "locked (last restart" "锁定期间直接退出"
hasnt "$CALLS" "restart" "未触发重启"
hasnt "$CALLS" "exec" "未执行探针"

# ---------- T5 flock 防重入 ----------
echo "[T5] flock 被占用"
setup
( flock -x 9; sleep 4 ) 9>"$SB/state/hc.flock" &
HOLDER=$!
sleep 0.5
bash "$TARGET"
kill "$HOLDER" 2>/dev/null || true
wait "$HOLDER" 2>/dev/null || true
has "$LOGFILE" "busy: previous run still active" "并发的第二轮直接退出"
hasnt "$CALLS" "restart" "未触发重启"
hasnt "$CALLS" "exec" "未执行探针"

# ---------- T6 阈值 99 只计数不重启（对应 Phase 3a） ----------
echo "[T6] HC_FAIL_THRESHOLD=99 只累计不重启"
setup
export HC_FORCE_FAIL=1 HC_FAIL_THRESHOLD=99
runs 5
unset HC_FORCE_FAIL HC_FAIL_THRESHOLD
hasnt "$CALLS" "restart" "未触发重启"
eq "累计到 FAIL #5" "$(grep -c 'FAIL #' "$LOGFILE")" "5"
eq "计数文件=5" "$(cat "$STATEFILE" 2>/dev/null)" "5"

# ---------- T7 探针单项失败能识别 ----------
echo "[T7] 单项失败（心跳过期）"
setup
export STUB_HEARTBEAT_AGE=600
bash "$TARGET"
unset STUB_HEARTBEAT_AGE
has "$LOGFILE" "FAIL #1 probe=01111" "心跳项判定为失败且其余四项通过"

# ---------- T7b QQ 进程死亡 → 计入重启阈值 ----------
echo "[T7b] QQ 进程不存在（重启项）"
setup
export STUB_NO_QQ_PROC=1
bash "$TARGET"
unset STUB_NO_QQ_PROC
has "$LOGFILE" "FAIL #1 probe=11110" "napcat 进程缺失判定为失败"

# ---------- T7c WS 掉线（未登录）→ 不计重启 ----------
echo "[T7c] WS 掉线 → ACCOUNT-OFFLINE 且不计重启"
setup
export STUB_LINK_COUNT=0
runs 4
unset STUB_LINK_COUNT
has "$LOGFILE" "ACCOUNT-OFFLINE" "记录 ACCOUNT-OFFLINE"
has "$LOGFILE" "heartbeat probe=11111 link=0" "心跳标记 link=0"
hasnt "$CALLS" "restart" "未触发重启（重启对此类故障无效）"
[ ! -f "$STATEFILE" ] && ok "未计入失败计数" || bad "被计入失败计数"


echo "[T8] 日志轮换上界"
setup
for i in $(seq 1 600); do echo "[pad] line $i" >> "$LOGFILE"; done
bash "$TARGET"
le "日志行数 ≤ 510" "$(wc -l < "$LOGFILE")" 510

# ---------- T9 静态断言 ----------
echo "[T9] 静态断言（零 LLM / 时间窗 / timeout）"
hasnt "$TARGET" "/sync" "不含 /sync（不走 LLM pipeline）"
hasnt "$TARGET" "/bots" "不含 /bots"
has "$TARGET" -- "--since 5m --tail" "日志扫描保留时间窗"
has "$TARGET" -- "/tmp/hc_scan.txt" "日志扫描经外部文件（不跨管道）"
if grep -nE '\$DOCKER"? +logs.*\|' "$TARGET" >/dev/null 2>&1; then
    bad "存在 docker logs 管道写法"
else
    ok "无 docker logs 管道写法"
fi
if grep -n '"$DOCKER" restart' "$TARGET" | grep -v 'timeout' | grep -q .; then
    bad "存在无 timeout 的 restart"
else
    ok "所有 restart 均带 timeout"
fi
if grep -n '"$DOCKER" logs' "$TARGET" | grep -v 'timeout' | grep -q .; then
    bad "存在无 timeout 的 docker logs"
else
    ok "所有 docker logs 均带 timeout"
fi

# ---------- T10 语法检查 ----------
echo "[T10] bash -n 语法检查"
if bash -n "$TARGET" 2>/dev/null; then ok "语法正确"; else bad "语法错误"; fi

echo ""
echo "=== 结果: 通过 $PASS，失败 $FAIL ==="
[ "$FAIL" -eq 0 ]
