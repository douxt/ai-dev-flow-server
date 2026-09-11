FROM codercom/code-server:latest
USER root

# 阿里云源加速（国内环境）
RUN sed -i "s|http://deb.debian.org|http://mirrors.aliyun.com|g" /etc/apt/sources.list.d/*.sources 2>/dev/null || true

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm tmux git gh jq curl python3-pip python3-venv iputils-ping && \
    rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

# 全量 pip wheel 离线安装（一次性 COPY，后续全用本地）
COPY all-wheels /tmp/all-wheels

RUN pip3 install --no-cache-dir --break-system-packages --no-index --find-links=/tmp/all-wheels uv paramiko mcp

RUN mkdir -p /home/coder/.config/claude && \
    if [ -d /home/coder/.claude ] && [ ! -L /home/coder/.claude ]; then \
      cp -rn /home/coder/.claude/* /home/coder/.config/claude/ 2>/dev/null || true; \
      rm -rf /home/coder/.claude; \
    elif [ ! -e /home/coder/.claude ]; then \
      rm -rf /home/coder/.claude; \
    fi && \
    ln -sfn /home/coder/.config/claude /home/coder/.claude && \
    chown -R coder:coder /home/coder/.config/claude /home/coder/.claude

RUN mkdir -p /home/coder/.config && \
    touch /home/coder/.config/gitconfig && \
    touch /home/coder/.config/bashrc && \
    touch /home/coder/.config/npmrc && \
    touch /home/coder/.config/claude.json && \
    ln -sf /home/coder/.config/gitconfig /home/coder/.gitconfig && \
    ln -sf /home/coder/.config/bashrc   /home/coder/.bashrc && \
    ln -sf /home/coder/.config/npmrc    /home/coder/.npmrc && \
    ln -sf /home/coder/.config/claude.json /home/coder/.claude.json

# ====== AFK 管线依赖（2026-07-03）======
# P2: cron（systemd 替代）+ unzip（deno.zip 解压）
RUN apt-get update && apt-get install -y --no-install-recommends cron unzip && \
    rm -rf /var/lib/apt/lists/*

# Bun（Archon 运行时）—— 不再需要，Archon 预编译 COPY

# P0: Python 包
RUN pip3 install --no-cache-dir --break-system-packages --no-index --find-links=/tmp/all-wheels pyyaml requests python-frontmatter

# youtube-kb 开发依赖 + PySocks（SOCKS5 代理）——离线安装
RUN pip3 install --no-cache-dir --break-system-packages --no-index --find-links=/tmp/all-wheels \
    yt-dlp==2026.6.9 yt-dlp-ejs==0.8.0 openai google-auth-oauthlib google-api-python-client PySocks

# ====== PO Token 体系（2026-07-28）======
# 防 YouTube 字幕 429；SHA256 校验防供应链攻击

# deno（yt-dlp-ejs JS 运行时）
# 预下载 + SHA256 校验，COPY 进镜像（NAS 无稳定 GitHub 访问）
COPY deno.zip /tmp/deno.zip
RUN echo "934d1bd5cb09eaed7f2e4a4fc58208d04a3c5c0fcde9f319d93d735265c67a4a  /tmp/deno.zip" | sha256sum -c - && \
    unzip -o /tmp/deno.zip -d /usr/local/bin && \
    chmod +x /usr/local/bin/deno && \
    rm /tmp/deno.zip

# bgutil-pot（PO Token HTTP server，端口 4416）
# 预下载 + SHA256 校验，COPY 进镜像
COPY bgutil-pot /usr/local/bin/bgutil-pot
RUN echo "e7c264a574fa2705b6e5dc62283a8a4e80130f27b9d7e9df44e6b09aa6151a87  /usr/local/bin/bgutil-pot" | sha256sum -c - && \
    chmod +x /usr/local/bin/bgutil-pot

# bgutil pot provider 插件（yt-dlp extractor）
# 预下载 + SHA256 校验，COPY 进镜像
COPY plugin.zip /tmp/plugin.zip
RUN mkdir -p /home/coder/.config/yt-dlp/plugins && \
    echo "99fd83b98fa93b193d6a3b69dc74410d76e7a2b889868c54d16121cac9060344  /tmp/plugin.zip" | sha256sum -c - && \
    unzip -o /tmp/plugin.zip -d /home/coder/.config/yt-dlp/plugins/bgutil-ytdlp-pot-provider-rs/ && \
    rm /tmp/plugin.zip && \
    chown -R coder:coder /home/coder/.config/yt-dlp

# P0: Archon CLI（coleam00/Archon, MIT, v0.5.0 binary）
# NAS 网络不稳，预先下载 archon-linux-x64 到 Dockerfile 同目录，COPY 进镜像
COPY archon-linux-x64 /usr/local/bin/archon
RUN chmod +x /usr/local/bin/archon

# P3: Archon 工作目录
RUN mkdir -p /opt/archon/workspaces /tmp/archon-worktrees && \
    chown -R coder:coder /opt/archon /tmp/archon-worktrees

# ====== 基础设施增量（2026-07-04）======
# 编译工具链 + SQLite（cuotiben 错题本）+ 进程守护
# 预下载 69 个 .deb (80MB) COPY 进镜像，离线安装
COPY debs /tmp/debs
RUN dpkg -i /tmp/debs/*.deb 2>/dev/null || true && \
    apt-get install -f -y --no-install-recommends && \
    rm -rf /tmp/debs /var/lib/apt/lists/*

ENV ARCHON_HOME=/home/coder/.archon
EXPOSE 8420

# ====== Node 22 + DeepSeek Harness（2026-09-11）======
# Node 22：DSH 0.1.0-rc.7 在 base 镜像自带的 Node 20.19.2 上起不来——
#   node:module 缺 stripTypeScriptTypes、node:zlib 缺 createZstdDecompress，
#   插件树加载即失败退出（实测报错，非猜测）。
#   预下载官方 tarball + SHA256 校验，沿用 deno.zip/archon 的离线作风。
#   解到 /usr/local：PATH 中 /usr/local/bin 优先于 /usr/bin，覆盖 Debian 版 node/npm；
#   不 apt purge 旧包，避免连带拆掉依赖它的既有组件。
COPY node-v22.22.2-linux-x64.tar.xz /tmp/node.tar.xz
RUN echo "88fd1ce767091fd8d4a99fdb2356e98c819f93f3b1f8663853a2dee9b438068a  /tmp/node.tar.xz" | sha256sum -c - && \
    tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 && \
    rm /tmp/node.tar.xz && \
    node -v && npm -v

# DeepSeek Harness：版本与开发机一致（0.1.0-rc.7）。升级 = 改这一行 + 重建。
# pnpm：`dsh plugin` 与设置页安装插件依赖它（base 镜像没有）。
RUN npm install -g @deepseek-ai/dsh@0.1.0-rc.7 pnpm@11 && dsh --version

# socat：容器内 TCP 转发。DSH 的 --host 只接受 127.0.0.1|0.0.0.0，且 0.0.0.0 被 CLI
#   明确拒绝（"would expose remote code execution to the network"）——所以不绕过它：
#   DSH 保持绑 127.0.0.1:3081，由 socat 转到容器 0.0.0.0:3080，compose 只把 3080
#   发布到 NAS 的 127.0.0.1，最后交 tailscale serve（tailnet only）对外。
RUN apt-get update && apt-get install -y --no-install-recommends socat && \
    rm -rf /var/lib/apt/lists/*

# ~/.dsh 指向持久卷（沿用 .claude/.gitconfig 的既有符号链接做法）。DSH_HOME 另在
#   compose 里显式设置；符号链接是第二道保险，防止漏传环境变量时状态落到镜像层。
RUN ln -sfn /home/coder/.config/dsh /home/coder/.dsh && chown -h coder:coder /home/coder/.dsh

# ====== Supervisor 配置（2026-07-28 / 2026-08-06 修复 % 转义）======
# printf 中 % 需写为 %% 才能输出字面 %

RUN mkdir -p /etc/supervisor/conf.d

# Archon serve
RUN printf '[program:archon]\ncommand=archon serve --port 8420\ndirectory=/home/coder/project\nuser=coder\nautostart=true\nautorestart=true\nenvironment=HOME="/home/coder",ARCHON_HOME="/home/coder/.archon"\n' \
    > /etc/supervisor/conf.d/archon.conf

# bgutil-pot（%%(ENV_VAR)s → 输出 %(ENV_VAR)s，supervisor 运行时解析）
RUN printf '[program:bgutil-pot]\ncommand=bgutil-pot server\ndirectory=/tmp\nuser=coder\nautostart=true\nautorestart=true\npriority=10\nstdout_logfile_maxbytes=10MB\nstdout_logfile_backups=3\nstderr_logfile_maxbytes=10MB\nstderr_logfile_backups=3\nenvironment=HTTP_PROXY="%%(ENV_CLASH_PROXY_URL)s",HTTPS_PROXY="%%(ENV_CLASH_PROXY_URL)s",ALL_PROXY="%%(ENV_CLASH_PROXY_URL)s"\n' \
    > /etc/supervisor/conf.d/bgutil-pot.conf

# youtube-kb 启动包装脚本（含 PROXY_URL 环境变量注入）
RUN printf '#!/bin/bash\nset -e\nCONFIG="/home/coder/.config/claude/settings.local.json"\nif [ ! -f "$CONFIG" ]; then echo "FATAL: $CONFIG not found" >&2; exit 1; fi\nANTHROPIC_AUTH_TOKEN=$(jq -r ".env.ANTHROPIC_AUTH_TOKEN // empty" "$CONFIG" 2>/dev/null)\nif [ -z "$ANTHROPIC_AUTH_TOKEN" ]; then echo "FATAL: ANTHROPIC_AUTH_TOKEN empty in $CONFIG" >&2; exit 1; fi\nexport ANTHROPIC_AUTH_TOKEN\nENVFILE="/home/coder/project/youtube-kb/.env"\nif [ -f "$ENVFILE" ]; then set -a; source "$ENVFILE"; set +a; fi\nfor i in $(seq 30); do curl -sf http://127.0.0.1:4416 >/dev/null 2>&1 && break; sleep 1; done\nexec python3 -m app.main --source both\n' \
    > /usr/local/bin/youtube-kb-start.sh && \
    chmod +x /usr/local/bin/youtube-kb-start.sh

# youtube-kb supervisor program
RUN printf '[program:youtube-kb]\ncommand=/usr/local/bin/youtube-kb-start.sh\ndirectory=/home/coder/project/youtube-kb\nuser=coder\nautostart=true\nautorestart=true\npriority=20\nstartsecs=30\nstartretries=5\nstdout_logfile_maxbytes=10MB\nstdout_logfile_backups=3\nstderr_logfile_maxbytes=10MB\nstderr_logfile_backups=3\n' \
    > /etc/supervisor/conf.d/youtube-kb.conf

# DeepSeek Harness Web + socat 转发（2026-09-11）
# DSH_PERMISSION_MODE：base bundle 的部署默认值来源（sandbox-policy 的 mode 与
#   user-approval 的 policy 都读它）。Synology 内核 5.10 既无 Landlock 又未开
#   user namespaces，workspace-write 沙箱因此没有可用后端，bash 工具会 fail-closed
#   直接拒绝执行（bubblewrap 实测亦不可用）。故显式设为 danger-full-access
#   → 沙箱 danger-full-access + 审批 never，隔离边界交给容器本身。
# --trusted-host：/api 请求要求 Host 是 loopback 或在 trustedHosts 内（无端口条目匹配任意端口）。
#   经 tailscale serve 访问时 Host 是 nas.tail152b92.ts.net:3080，不声明会「页面能开、对话连不上」。
#   NAS 的 tailnet 名若变更，改这里。
# 用 printf '%s\n' 多参数而不是 \n 转义：避免 % 转义坑（见上方注释）。
RUN printf '%s\n' \
    '[program:dsh]' \
    'command=/usr/local/bin/dsh web --port 3081 --no-open --trusted-host nas.tail152b92.ts.net' \
    'directory=/home/coder/project' \
    'user=coder' \
    'autostart=true' \
    'autorestart=true' \
    'startsecs=30' \
    'startretries=5' \
    'environment=HOME="/home/coder",DSH_HOME="/home/coder/.config/dsh",DSH_PERMISSION_MODE="danger-full-access",PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",TZ="Asia/Shanghai"' \
    'stdout_logfile_maxbytes=10MB' \
    'stdout_logfile_backups=3' \
    'stderr_logfile_maxbytes=10MB' \
    'stderr_logfile_backups=3' \
    > /etc/supervisor/conf.d/dsh.conf && \
    printf '%s\n' \
    '[program:dsh-relay]' \
    'command=/usr/bin/socat TCP-LISTEN:3080,fork,reuseaddr TCP:127.0.0.1:3081' \
    'user=coder' \
    'autostart=true' \
    'autorestart=true' \
    'startsecs=5' \
    > /etc/supervisor/conf.d/dsh-relay.conf

# OpenKB Wiki 编译器（2026-08-06）——离线安装
RUN pip3 install --no-cache-dir --break-system-packages --no-index --find-links=/tmp/all-wheels openkb==0.4.5 && \
    rm -rf /tmp/all-wheels

# ENTRYPOINTD：容器启动时自动拉起 supervisord
# base image 的 /usr/bin/entrypoint.sh 内置此机制，创建目录即可
RUN mkdir -p /entrypoint.d && \
    printf '#!/bin/bash\nsudo -E supervisord -c /etc/supervisor/supervisord.conf\n' \
    > /entrypoint.d/supervisord.sh && \
    chmod +x /entrypoint.d/supervisord.sh

# Docker HEALTHCHECK：检查 code-server 自身可用
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8080/healthz || exit 1

# /data/ Volume 权限（2026-08-08）—— 首次挂载属 root，coder 需写权限
RUN chown -R coder:coder /data || true

USER coder
