#!/usr/bin/env bash
# E1 pilot/主段 一键控制。数据落 ledger.jsonl，进度落 runs/pilot.log（不用 /tmp）。
# 用法：pilot_ctl.sh {status|start|stop|resume|tail|next}
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
RUNS_ROOT="${RUNS_ROOT:-$HOME/projects/cut-optimizer/experiments/e1/runs}"
PLAN="${PLAN:-$HOME/projects/cut-optimizer/experiments/e1/pilot-plan.json}"
LOG="$RUNS_ROOT/pilot.log"
LEDGER="$RUNS_ROOT/ledger.jsonl"
MODEL="${MODEL:-qwen3.8-flash[1m]}"
MAX_TURNS="${MAX_TURNS:-120}"
TIMEOUT="${TIMEOUT:-2400}"

mkdir -p "$RUNS_ROOT"

running_pids() { pgrep -f 'pilot_runner\.py|run_driver\.py run' 2>/dev/null || true; }
plan_count()   { [ -f "$PLAN" ] && python3 -c "import json;print(len(json.load(open('$PLAN'))))"; }
done_count()   { [ -f "$LEDGER" ] && wc -l < "$LEDGER" || echo 0; }
next_cells() {
  [ -f "$PLAN" ] || return 0
  python3 - "$PLAN" "$LEDGER" <<'PY'
import json, sys, os
plan = json.load(open(sys.argv[1]))
done = set()
if os.path.exists(sys.argv[2]):
    for l in open(sys.argv[2]):
        try: done.add(json.loads(l)['run_id'])
        except Exception: pass
rem = [p['run_id'] for p in plan if p['run_id'] not in done]
for r in rem[:5]: print(r)
print(f'(剩余 {len(rem)} 格)', file=sys.stderr)
PY
}

status() {
  local total=$(plan_count) done=$(done_count)
  local pids=$(running_pids)
  echo "计划: ${total:-?}   已完成: $done"
  if [ -n "$pids" ]; then
    echo "状态: 运行中 (pid $(echo $pids | tr '\n' ' '))"
  else
    if [ "$done" = "$total" ]; then echo "状态: 全部完成"; else echo "状态: 未运行 (可 start)"; fi
  fi
  if [ -f "$LEDGER" ]; then
    echo "最近 5 条:"
    python3 -c "$(printf '%s' '
import sys, json
for line in open(sys.argv[1]).read().splitlines()[-5:]:
    try:
        e = json.loads(line)
        print("  %-16s %-11s wall=%ss bc=%s vis=%s hid=%s hack=%s" % (e["run_id"], e["status"], e.get("wall_s",0), e.get("behavior_currency",0), e.get("visible_pass"), e.get("hidden_pass"), e.get("hack_suspect")))
    except Exception:
        pass')" "$LEDGER"
  fi
}

do_start() {
  local pids=$(running_pids)
  if [ -n "$pids" ]; then
    echo "⚠️ 已有 pilot 进程在跑 (pid $pids)：拒绝双跑。要重启用先 stop。"; return 1
  fi
  [ -f "$PLAN" ] || { echo "❌ 无排程 $PLAN (用 make_exam+schedule 先生成)"; return 2; }
  cd "$HERE/.."
  setsid nohup python3 "$HERE/pilot_runner.py" \
      --plan "$PLAN" --exam-root "$(dirname $PLAN)" --runs-root "$RUNS_ROOT" \
      --model "$MODEL" --max-turns "$MAX_TURNS" --timeout "$TIMEOUT" \
      >> "$LOG" 2>&1 < /dev/null & disown
  local newpid=$!
  echo "▶ 已启动 (pid $newpid) → $LOG"
  sleep 1; running_pids | head -3 | sed 's/^/   /'
}

do_stop() {
  pkill -f 'pilot_runner\.py' 2>/dev/null && echo "killed pilot_runner" || echo "no pilot_runner"
  pkill -f 'run_driver\.py run' 2>/dev/null && echo "killed run_driver" || true
  pkill -f 'claude -p' 2>/dev/null && echo "killed claude -p 子进程(单格求解会丢)" || true
  sleep 1
  local rest=$(running_pids); [ -n "$rest" ] && echo "⚠️ 仍有: $rest" || echo "✓ 已停"
  echo "提示：被杀的那格若未落台账，下次 start 会自愈清孤儿目录重跑"
}

case "${1:-status}" in
  status) status ;;
  start|resume) do_start ;;   # resume=start 幂等（pilot_runner 依 ledger 跳过已完成）
  stop) do_stop ;;
  tail) [ -f "$LOG" ] && tail -f "$LOG" || echo "无日志 $LOG" ;;
  next) next_cells ;;
  ""|help|-h|--help)
    cat <<EOF
E1 pilot 控制：$0 {status|start|resume|stop|tail|next}
  status  看进度/最近 5 条台账
  start   后台起（setsid 分离，跨我这边会话切换活）
  resume  同 start（幂等，读台账跳过已完成，孤儿自愈）
  stop    干净停（会丢未落账的那格，下次 resume 补跑）
  tail    跟踪日志 $LOG
  next    列接下来 5 格
EOF
    ;;
  *) echo "未知命令 $1"; exit 2 ;;
esac
