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

USER coder
