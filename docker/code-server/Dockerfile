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
RUN pip3 install --no-cache-dir --break-system-packages \
    yt-dlp openai google-auth-oauthlib google-api-python-client

# P0: Archon CLI（coleam00/Archon, MIT, v0.5.0 binary）
RUN curl -fsSL https://archon.diy/install | bash

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

USER coder
