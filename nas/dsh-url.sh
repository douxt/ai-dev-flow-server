#!/bin/bash
# 取 NAS 上 DSH web 当前可用的带 token 入口 URL
#
# 背景：DSH 0.1.5-rc.2 起 web 有浏览器鉴权（BrowserAuth）。启动 token 是**进程级随机值**，
# 只出现在 supervisord 程序 `dsh` 的 stdout 里，且**每次重启/重建都会变**（实测 rc.2 前后不同）。
# 但 token 只是"每台设备一次性登录"用：用它开一次会签发 30 天有效的 cookie，
# cookie 校验依赖卷内的持久签名密钥，**dsh 重启与容器重建都不会让它失效**。
# 上游无关闭或固定该 token 的开关（`dsh web --help` / settings schema 均无对应项）。
# 用法：bash nas/dsh-url.sh [user@host]        # 默认 root@nas
#       bash nas/dsh-url.sh root@nas <authority> <port>   # tailnet 名或端口变了时覆盖
# 输出：一条可直接点开的 https URL（打开后签发 30 天 cookie，此后裸地址长期可进，重启不影响）
set -uo pipefail

NAS=${1:-root@nas}
AUTHORITY=${2:-nas.tail152b92.ts.net}
PORT=${3:-3080}
D=/volume1/@appstore/ContainerManager/usr/bin/docker

raw=$(timeout 30 ssh -nT -o BatchMode=yes -o ConnectTimeout=6 "$NAS" \
    "$D exec code-server sudo supervisorctl tail -8000 dsh stdout" 2>/dev/null \
    | grep -oE 'token=[A-Za-z0-9_-]+' | tail -1)

if [ -z "$raw" ]; then
    echo "取不到 token：dsh 未运行，或 supervisor stdout 缓冲已被轮转覆盖" >&2
    echo "  先看状态：ssh $NAS \"$D exec code-server sudo supervisorctl status dsh\"" >&2
    echo "  再重启取新：ssh $NAS \"$D exec code-server sudo supervisorctl restart dsh\"  # startsecs=30，等 40s" >&2
    exit 1
fi

url="https://$AUTHORITY:$PORT/?$raw"
code=$(timeout 20 curl -sS -o /dev/null -w '%{http_code}' "$url" 2>/dev/null)
echo "$url"
# 带 token 访问首页应放行（302 跳干净路径或 200）；仍 401 说明 token 已过期（dsh 又重启过）
if [ "$code" = "401" ]; then
    echo "警告：该 token 返回 401，多半已失效——dsh 在此期间又重启过，重新跑本脚本" >&2
    exit 2
fi
[ -n "$code" ] && echo "# 自检：首页 HTTP $code" >&2
