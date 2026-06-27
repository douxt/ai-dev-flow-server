#!/usr/bin/env python3
"""DevFlow 成本追踪 — 记录每次 AFK 执行的资源消耗
用法:
  python3 cost_tracker.py log --issue <name> --status <done|failed> --duration <sec> [--workflow auto-execute-afk]
  python3 cost_tracker.py summary [--days 30] [--workspace /path/to/project]
"""
import os, sys, json, datetime, argparse
from collections import defaultdict


def get_log_path(workspace):
    return os.path.join(workspace, "logs", "cost.jsonl")


def log_entry(workspace, issue, status, duration, workflow="auto-execute-afk", model="deepseek-v4-pro"):
    """追加一条成本记录"""
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "issue": issue,
        "status": status,
        "duration_sec": int(duration),
        "workflow": workflow,
        "model": model,
    }
    log_path = get_log_path(workspace)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def summary(workspace, days=30):
    """汇总最近 N 天的成本"""
    log_path = get_log_path(workspace)
    if not os.path.exists(log_path):
        print("暂无成本数据")
        return
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    records = []
    with open(log_path) as f:
        for line in f:
            try:
                r = json.loads(line)
                ts = datetime.datetime.fromisoformat(r["timestamp"])
                if ts >= cutoff:
                    records.append(r)
            except (json.JSONDecodeError, KeyError):
                continue

    if not records:
        print(f"最近 {days} 天无记录")
        return

    total = len(records)
    done = sum(1 for r in records if r["status"] == "done")
    failed = sum(1 for r in records if r["status"] == "failed")
    durations = [r["duration_sec"] for r in records]
    avg_dur = sum(durations) / len(durations) if durations else 0
    by_workflow = defaultdict(int)
    for r in records:
        by_workflow[r["workflow"]] += 1

    print(f"📊 最近 {days} 天成本汇总")
    print(f"  总执行: {total} 次")
    print(f"  成功: {done} | 失败: {failed} | 成功率: {done/total*100:.0f}%")
    print(f"  平均耗时: {avg_dur:.0f}s")
    print(f"  按 workflow:")
    for wf, cnt in sorted(by_workflow.items()):
        print(f"    {wf}: {cnt}")
    print(f"  日均: {total/days:.1f} 次")

    # 成本估算（DeepSeek 定价：¥1/M input, ¥4/M output）
    est_input_tokens = total * 20000
    est_output_tokens = total * 5000
    est_cost = (est_input_tokens / 1_000_000) * 1 + (est_output_tokens / 1_000_000) * 4
    print(f"  估算 token: {est_input_tokens/1000:.0f}K in + {est_output_tokens/1000:.0f}K out")
    print(f"  估算费用: ¥{est_cost:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser("cost_tracker")
    sub = parser.add_subparsers(dest="cmd")

    sum_p = sub.add_parser("summary")
    sum_p.add_argument("--days", type=int, default=30)
    sum_p.add_argument("--workspace", default=os.getcwd())

    log_p = sub.add_parser("log")
    log_p.add_argument("--issue", required=True)
    log_p.add_argument("--status", required=True)
    log_p.add_argument("--duration", type=int, default=0)
    log_p.add_argument("--workflow", default="auto-execute-afk")
    log_p.add_argument("--workspace", default=os.getcwd())

    args = parser.parse_args()

    if args.cmd == "summary":
        summary(args.workspace, args.days)
    elif args.cmd == "log":
        entry = log_entry(args.workspace, args.issue, args.status, args.duration, args.workflow)
        print(json.dumps(entry, ensure_ascii=False))
    else:
        parser.print_help()
