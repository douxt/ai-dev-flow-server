#!/bin/sh
# 只杀僵尸 docker exec 子 sshd 进程，保留活跃终端
SSHD_PID=$(cat /var/run/sshd.pid 2>/dev/null)
[ -z "$SSHD_PID" ] && exit 0

for child in $(ps --ppid $SSHD_PID -o pid= 2>/dev/null); do
  cmdline=$(cat /proc/$child/cmdline 2>/dev/null | tr "\0" " ")
  case "$cmdline" in
    # 僵尸：挂在 docker exec 上的 sshd 子进程
    *"docker exec"*)
      # 判断是否卡死：stat 看 state，S=睡眠 D=IO等待 R=运行
      state=$(awk "{print \$3}" /proc/$child/stat 2>/dev/null)
      # 只看 cgroup 确认在容器 namespaces 里
      cgroup=$(cat /proc/$child/cgroup 2>/dev/null | head -1)
      if echo "$cgroup" | grep -q "docker" || [ "$state" = "D" ]; then
        echo "killing zombie sshd[exec]: PID=$child state=$state cmd=$cmdline"
        kill -9 $child 2>/dev/null
      fi
      ;;
    # 僵尸：sshd 会话（非交互终端），无控制 tty
    *"sshd: "*)
      tty=$(awk "{print \$7}" /proc/$child/stat 2>/dev/null)
      # 无 tty + 运行超 10 分钟 = 僵尸
      if [ "$tty" = "0" ] || [ -z "$tty" ]; then
        start=$(awk "{print \$22}" /proc/$child/stat 2>/dev/null)
        now=$(awk "{print int(\$1)}" /proc/uptime 2>/dev/null)
        [ -n "$start" ] && [ -n "$now" ] && elapsed=$(( (now - start / 100) ))
        if [ -n "$elapsed" ] && [ "$elapsed" -gt 600 ]; then
          echo "killing zombie sshd[no-tty]: PID=$child elapsed=${elapsed}s"
          kill -9 $child 2>/dev/null
        fi
      fi
      ;;
  esac
done

echo "$(date): clean-zombie ran" >> /var/log/clean-zombie.log
