FROM codercom/code-server:latest
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm tmux git gh jq curl python3-pip python3-venv iputils-ping && \
    rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

RUN pip3 install --no-cache-dir --break-system-packages uv paramiko mcp

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
# P2: cron（systemd 替代，jq 已在上方装过）+ unzip（Bun 安装需要）
RUN apt-get update && apt-get install -y --no-install-recommends cron unzip && \
    rm -rf /var/lib/apt/lists/*

# Bun — Archon 运行时前提
RUN curl -fsSL https://bun.sh/install | BUN_INSTALL=/usr/local bash

# P0: Python 包
RUN pip3 install --no-cache-dir --break-system-packages pyyaml requests python-frontmatter

# youtube-kb 开发依赖（2026-07-04）
# yt-dlp + yt-dlp-ejs 版本锁定（2026-07-28），防 PO Token 插件不兼容
RUN pip3 install --no-cache-dir --break-system-packages \
    yt-dlp==2026.6.9 yt-dlp-ejs==0.8.0 openai google-auth-oauthlib google-api-python-client

# ====== PO Token 体系（2026-07-28）======
# 防 YouTube 字幕 429；SHA256 校验防供应链攻击

# deno（yt-dlp-ejs JS 运行时，~106MB）
RUN curl -fsSL --retry 3 https://github.com/denoland/deno/releases/download/v2.9.2/deno-x86_64-unknown-linux-gnu.zip -o /tmp/deno.zip && \
    echo "934d1bd5cb09eaed7f2e4a4fc58208d04a3c5c0fcde9f319d93d735265c67a4a  /tmp/deno.zip" | sha256sum -c - && \
    unzip -o /tmp/deno.zip -d /usr/local/bin && \
    chmod +x /usr/local/bin/deno && \
    rm /tmp/deno.zip

# bgutil-pot（PO Token HTTP server，端口 4416，~51MB）
RUN curl -fsSL --retry 3 https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs/releases/download/v0.8.1/bgutil-pot-linux-x86_64 -o /usr/local/bin/bgutil-pot && \
    echo "e7c264a574fa2705b6e5dc62283a8a4e80130f27b9d7e9df44e6b09aa6151a87  /usr/local/bin/bgutil-pot" | sha256sum -c - && \
    chmod +x /usr/local/bin/bgutil-pot

# bgutil pot provider 插件（yt-dlp extractor）
RUN mkdir -p /home/coder/.config/yt-dlp/plugins && \
    curl -fsSL --retry 3 https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs/releases/download/v0.8.1/bgutil-ytdlp-pot-provider-rs.zip -o /tmp/plugin.zip && \
    echo "99fd83b98fa93b193d6a3b69dc74410d76e7a2b889868c54d16121cac9060344  /tmp/plugin.zip" | sha256sum -c - && \
    unzip -o /tmp/plugin.zip -d /home/coder/.config/yt-dlp/plugins/bgutil-ytdlp-pot-provider-rs/ && \
    rm /tmp/plugin.zip && \
    chown -R coder:coder /home/coder/.config/yt-dlp

# ====== 按需安装（不在 Dockerfile 中，容器启动后手动装）======
# OpenKB: pip3 install --break-system-packages 'openkb==0.4.5'
# Klore:  python3 -m venv ~/.venvs/klore && ~/.venvs/klore/bin/pip install klore==0.1.1

# P0: Archon CLI（coleam00/Archon, MIT, v0.5.0 binary）
# NAS 网络不稳，预先下载 archon-linux-x64 到 Dockerfile 同目录，COPY 进镜像
COPY archon-linux-x64 /usr/local/bin/archon
RUN chmod +x /usr/local/bin/archon

# P3: Archon 工作目录
RUN mkdir -p /opt/archon/workspaces /tmp/archon-worktrees && \
    chown -R coder:coder /opt/archon /tmp/archon-worktrees

# ====== 基础设施增量（2026-07-04）======
# 编译工具链 + SQLite（cuotiben 错题本）+ 辅助工具 + 进程守护
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libsqlite3-dev sqlite3 less supervisor && \
    rm -rf /var/lib/apt/lists/*

ENV ARCHON_HOME=/home/coder/.archon
EXPOSE 8420

# Archon serve 自启动（supervisor）
RUN mkdir -p /etc/supervisor/conf.d && \
    printf '[program:archon]\ncommand=archon serve --port 8420\ndirectory=/home/coder/project\nuser=coder\nautostart=true\nautorestart=true\nenvironment=HOME="/home/coder",ARCHON_HOME="/home/coder/.archon"\n' \
    > /etc/supervisor/conf.d/archon.conf

# ====== Supervisor 增量（2026-07-28）======
# bgutil-pot + youtube-kb 进程守护；archon 暂不启用

# bgutil-pot（代理仅注入此进程，通过 supervisor 的 %(ENV_VAR)s 从 compose 继承）
RUN printf '[program:bgutil-pot]\ncommand=bgutil-pot server\ndirectory=/tmp\nuser=coder\nautostart=true\nautorestart=true\npriority=10\nstdout_logfile_maxbytes=10MB\nstdout_logfile_backups=3\nstderr_logfile_maxbytes=10MB\nstderr_logfile_backups=3\nenvironment=HTTP_PROXY="%(ENV_CLASH_PROXY_URL)s",HTTPS_PROXY="%(ENV_CLASH_PROXY_URL)s",ALL_PROXY="%(ENV_CLASH_PROXY_URL)s"\n' \
    > /etc/supervisor/conf.d/bgutil-pot.conf

# youtube-kb 启动包装脚本（含错误检查 + bgutil-pot 就绪等待）
RUN printf '#!/bin/bash\nset -e\nCONFIG="/home/coder/.config/claude/settings.local.json"\nif [ ! -f "$CONFIG" ]; then echo "FATAL: $CONFIG not found" >&2; exit 1; fi\nANTHROPIC_AUTH_TOKEN=$(jq -r ".env.ANTHROPIC_AUTH_TOKEN // empty" "$CONFIG" 2>/dev/null)\nif [ -z "$ANTHROPIC_AUTH_TOKEN" ]; then echo "FATAL: ANTHROPIC_AUTH_TOKEN empty in $CONFIG" >&2; exit 1; fi\nexport ANTHROPIC_AUTH_TOKEN\nfor i in $(seq 30); do curl -sf http://127.0.0.1:4416 >/dev/null 2>&1 && break; sleep 1; done\nexec python3 -m app.main --source both\n' \
    > /usr/local/bin/youtube-kb-start.sh && \
    chmod +x /usr/local/bin/youtube-kb-start.sh

# youtube-kb supervisor program
RUN printf '[program:youtube-kb]\ncommand=/usr/local/bin/youtube-kb-start.sh\ndirectory=/home/coder/project/youtube-kb\nuser=coder\nautostart=true\nautorestart=true\npriority=20\nstartsecs=30\nstartretries=5\nstdout_logfile_maxbytes=10MB\nstdout_logfile_backups=3\nstderr_logfile_maxbytes=10MB\nstderr_logfile_backups=3\n' \
    > /etc/supervisor/conf.d/youtube-kb.conf

# ENTRYPOINTD：容器启动时自动拉起 supervisord
# base image 的 /usr/bin/entrypoint.sh 内置此机制，创建目录即可
RUN mkdir -p /entrypoint.d && \
    printf '#!/bin/bash\nsudo supervisord -c /etc/supervisor/supervisord.conf\n' \
    > /entrypoint.d/supervisord.sh && \
    chmod +x /entrypoint.d/supervisord.sh

# Docker HEALTHCHECK：检查 code-server 自身可用
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8080/healthz || exit 1

USER coder
