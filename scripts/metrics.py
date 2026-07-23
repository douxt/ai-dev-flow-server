#!/usr/bin/env python3
"""DevFlow 量化指标追踪 v3.0

用法:
  python3 metrics.py update --workspace <dir>    # 扫描 issues/ + git log → 更新 metrics.json
  python3 metrics.py show --workspace <dir>      # 打印当前指标
  python3 metrics.py show --workspace <dir> --json  # JSON 输出

指标:
  - total_tickets: 总 ticket 数
  - completed: done 状态数量
  - in_progress: 进行中
  - avg_digest_hours: 平均 issue 消化时间（ready → done）
  - pr_count: PR 总数
  - pr_merge_rate: PR 合并率（merged / total）
  - rework_count: 返工次数（failed 后重新 ready 的 ticket）
  - safety_marked: 含 safety 标记的 ticket 数
"""
import sys, os, re, json
from datetime import datetime, timezone

try:
    import frontmatter
except ImportError:
    print(json.dumps({"error": "缺少 python-frontmatter"}), file=sys.stderr)
    sys.exit(1)


def scan_issues(workspace):
    """扫描 issues/ 目录，统计 ticket 状态"""
    issues_dir = os.path.join(workspace, "issues")
    if not os.path.isdir(issues_dir):
        return {}

    stats = {"total": 0, "done": 0, "in_progress": 0, "ready": 0,
             "backlog": 0, "failed": 0, "in_review": 0, "safety_marked": 0,
             "tickets": []}

    for f in sorted(os.listdir(issues_dir)):
        if not f.endswith('.md'):
            continue
        path = os.path.join(issues_dir, f)
        try:
            post = frontmatter.load(path)
            status = post.get("status", "unknown")
            stats["total"] += 1
            stats[status] = stats.get(status, 0) + 1

            if post.get("safety"):
                stats["safety_marked"] += 1

            # 记录单个 ticket 信息
            est = post.get("estimate", "")
            match = re.search(r'(\d+\.?\d*)\s*d', str(est))
            est_days = float(match.group(1)) if match else 0

            stats["tickets"].append({
                "file": f,
                "status": status,
                "type": post.get("type", ""),
                "effort": post.get("effort", ""),
                "estimate_days": est_days,
                "safety": post.get("safety", ""),
            })
        except Exception:
            pass

    return stats


def git_stats(workspace):
    """从 git log 提取 PR 相关统计"""
    import subprocess
    stats = {"pr_count": 0, "pr_merged": 0, "rework_count": 0}

    try:
        # Total PR attempts: count "dispatch: claim" commits (each = one ticket claimed for PR)
        result = subprocess.run(
            ["git", "-C", workspace, "log", "--oneline", "--since=90.days",
             "--grep=dispatch: claim"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            stats["pr_count"] = len([l for l in result.stdout.splitlines() if l.strip()])

        # Merged PRs: count "Merge pull request" commits (successful merges)
        result = subprocess.run(
            ["git", "-C", workspace, "log", "--oneline", "--since=90.days",
             "--grep=Merge pull request"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            stats["pr_merged"] = len([l for l in result.stdout.splitlines() if l.strip()])

        # Rework: "dispatch: failed" commits (claim → fail → re-claim on same ticket)
        result = subprocess.run(
            ["git", "-C", workspace, "log", "--oneline", "--since=90.days",
             "--grep=dispatch: failed"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            stats["rework_count"] = len([l for l in result.stdout.splitlines() if l.strip()])

    except Exception:
        pass

    pr_total = stats["pr_count"]
    pr_merged = stats["pr_merged"]
    stats["pr_merge_rate"] = round(pr_merged / pr_total * 100, 1) if pr_total > 0 else 0

    return stats


def estimate_digest_time(workspace):
    """从 trace.jsonl 估算平均 ticket 消化时间（tickets:done → implement:done）

    注意：stage.transition 是项目级事件（非 per-ticket），dispatch 是单线程的，
    因此相邻的 tickets:done → implement:done 对可近似视为一个 ticket 的消化周期。
    """
    trace_file = os.path.join(workspace, ".devflow", "trace.jsonl")
    if not os.path.isfile(trace_file):
        return None

    # 收集所有阶段转换事件的时间戳
    transitions = []
    try:
        with open(trace_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("event") == "stage.transition":
                    transitions.append(event)
    except Exception:
        return None

    # 配对：每次 tickets:done 之后最近的 implement:done（单线程 dispatch 保证不交叉）
    intervals = []
    pending_ready = None
    for ev in transitions:
        to_stage = ev.get("to", "")
        ts_str = ev.get("ts", "")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue

        if to_stage == "tickets:done":
            pending_ready = ts
        elif to_stage in ("implement:done", "done") and pending_ready is not None:
            hours = (ts - pending_ready).total_seconds() / 3600
            if hours > 0:
                intervals.append(hours)
            pending_ready = None

    if intervals:
        return round(sum(intervals) / len(intervals), 1)
    return None


def update(workspace):
    """更新 metrics.json"""
    issues = scan_issues(workspace)
    git_s = git_stats(workspace)
    avg_digest = estimate_digest_time(workspace)

    metrics = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "tickets": {
            "total": issues.get("total", 0),
            "done": issues.get("done", 0),
            "in_progress": issues.get("in_progress", 0),
            "ready": issues.get("ready", 0),
            "backlog": issues.get("backlog", 0),
            "failed": issues.get("failed", 0),
            "in_review": issues.get("in_review", 0),
            "safety_marked": issues.get("safety_marked", 0),
        },
        "pr": {
            "count": git_s.get("pr_count", 0),
            "merged": git_s.get("pr_merged", 0),
            "merge_rate_pct": git_s.get("pr_merge_rate", 0),
            "rework_count": git_s.get("rework_count", 0),
        },
        "avg_digest_hours": avg_digest,
        "detail": issues.get("tickets", []),
    }

    # 写入文件
    metrics_path = os.path.join(workspace, ".devflow", "metrics.json")
    os.makedirs(os.path.dirname(metrics_path), exist_ok=True)
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    print(f"✅ metrics.json 已更新 ({metrics['tickets']['total']} tickets, "
          f"{metrics['pr']['count']} PRs, "
          f"digest avg: {metrics['avg_digest_hours'] or 'N/A'}h)")
    return 0


def show(workspace, json_out=False):
    """打印当前指标"""
    metrics_path = os.path.join(workspace, ".devflow", "metrics.json")
    if not os.path.isfile(metrics_path):
        if json_out:
            print(json.dumps({"error": "metrics.json 不存在，先运行 update"}, ensure_ascii=False))
        else:
            print("⚠️  metrics.json 不存在，先运行 python3 metrics.py update --workspace <dir>")
        return 1

    with open(metrics_path) as f:
        metrics = json.load(f)

    if json_out:
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
    else:
        t = metrics.get("tickets", {})
        p = metrics.get("pr", {})
        print(f"📊 DevFlow Metrics ({metrics.get('updated', 'unknown')})")
        print(f"   Tickets: {t.get('total', 0)} total | "
              f"{t.get('done', 0)} done | {t.get('in_progress', 0)} in_progress | "
              f"{t.get('ready', 0)} ready | {t.get('backlog', 0)} backlog")
        print(f"   Safety: {t.get('safety_marked', 0)} safety-marked")
        print(f"   PRs: {p.get('count', 0)} total | {p.get('merged', 0)} merged "
              f"({p.get('merge_rate_pct', 0)}%) | {p.get('rework_count', 0)} reworks")
        digest = metrics.get('avg_digest_hours')
        print(f"   Avg digest: {digest}h" if digest else "   Avg digest: N/A")

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3 or "--workspace" not in sys.argv:
        print("用法: python3 metrics.py <update|show> --workspace <dir> [--json]")
        sys.exit(1)

    ws_idx = sys.argv.index("--workspace")
    workspace = sys.argv[ws_idx + 1] if ws_idx + 1 < len(sys.argv) else "."
    json_out = "--json" in sys.argv

    cmd = sys.argv[1]
    if cmd == "update":
        sys.exit(update(workspace))
    elif cmd == "show":
        sys.exit(show(workspace, json_out))
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
