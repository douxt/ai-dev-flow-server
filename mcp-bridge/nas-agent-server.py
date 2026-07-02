#!/usr/bin/env python3
"""NAS Claude Code Agent MCP Server — HTTP/SSE 模式，供本机 CC 远程调用"""

import json, subprocess, sys, os, signal

PID_FILE = "/tmp/nas-agent.pid"

# 优雅重启：先杀旧进程
if os.path.exists(PID_FILE):
    try:
        with open(PID_FILE) as f:
            old_pid = int(f.read().strip())
        os.kill(old_pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, ValueError):
        pass

with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("nas-agent", port=9876, host="127.0.0.1")

@mcp.tool()
def ask(prompt: str, cwd: str = None) -> str:
    """向 NAS 上的 Claude Code agent 发 prompt，返回结果。
    cwd 可选指定工作目录，默认 ~/project/MAF-Hub
    """
    workdir = os.path.expanduser(cwd or "~/project/MAF-Hub")
    try:
        result = subprocess.run(
            ["claude", "-p", "--output-format", "json", prompt],
            cwd=workdir, capture_output=True, text=True, timeout=300,
            env={**os.environ, "HOME": os.path.expanduser("~")}
        )
        if result.returncode != 0:
            return f"[nas-agent error] exit={result.returncode}\n{result.stderr[:500]}"
        data = json.loads(result.stdout)
        return data.get("result", result.stdout[:2000])
    except subprocess.TimeoutExpired:
        return "[nas-agent] timeout (300s)"
    except Exception as e:
        return f"[nas-agent error] {str(e)}"

@mcp.tool()
def status() -> str:
    """查看 NAS 容器状态、磁盘、git 状态"""
    cmds = [
        ("docker ps --format '{{.Names}} {{.Status}}'", "容器状态"),
        ("df -h / | tail -1", "磁盘"),
        ("cd ~/project/MAF-Hub && git status --short 2>&1 | head -10", "MAF-Hub"),
        ("cd ~/project/ai-dev-flow-server && git status --short 2>&1 | head -10", "ai-dev-flow-server"),
    ]
    out = []
    for cmd, label in cmds:
        try:
            r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=15)
            out.append(f"### {label}\n{r.stdout.strip() or '(空)'}")
        except Exception:
            out.append(f"### {label}\n(超时)")
    return "\n\n".join(out)

@mcp.tool()
def run_task(prompt: str, cwd: str = None) -> str:
    """向 NAS agent 发长期任务，返回任务 ID 供后续查询进度"""
    import uuid, time
    task_id = str(uuid.uuid4())[:8]
    workdir = os.path.expanduser(cwd or "~/project/MAF-Hub")
    logfile = f"/tmp/nas-task-{task_id}.log"
    cmd = f"cd {workdir} && claude -p --output-format json '{prompt}' > {logfile} 2>&1"
    subprocess.Popen(["bash", "-c", cmd])
    time.sleep(1)
    if os.path.exists(logfile):
        os.chmod(logfile, 0o600)
        with open(logfile) as f:
            content = f.read()
        if content:
            return json.dumps({"task_id": task_id, "status": "completed", "result": content[:2000]})
    return json.dumps({"task_id": task_id, "status": "running", "log": logfile})

if __name__ == "__main__":
    mcp.run(transport="sse")
