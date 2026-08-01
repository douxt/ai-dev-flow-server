#!/usr/bin/env python3
"""查询 langbot monitoring DB，输出 JSON 统计数据。
用法（langbot 容器内）:
  python3 /tmp/query_monitoring.py --session group_1104330614 --last 20
  python3 /tmp/query_monitoring.py --session group_1104330614 --after '2026-08-01 20:00' --before '2026-08-01 22:00'
  python3 /tmp/query_monitoring.py --check   # 一键复查
"""
import sqlite3, json, sys, argparse, os
from datetime import datetime, timedelta

DB_PATH = "/app/data/langbot.db"
PLUGIN_DIR = "/app/data/plugins/dou__langbot-silent-observer"


def connect():
    if not os.path.exists(DB_PATH):
        print(json.dumps({"error": f"DB not found: {DB_PATH}"}))
        sys.exit(1)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def stats(rows, col):
    """计算 median, IQR, mean, min, max, n."""
    vals = sorted(r[col] for r in rows if r[col] is not None)
    if not vals:
        return {"n": 0, "median": None, "q1": None, "q3": None, "mean": None, "min": None, "max": None}
    n = len(vals)
    median = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    q1 = vals[n // 4]
    q3 = vals[3 * n // 4]
    return {
        "n": n, "median": median, "q1": q1, "q3": q3,
        "mean": round(sum(vals) / n, 1), "min": vals[0], "max": vals[-1],
    }


def query_llm(db, session=None, after=None, before=None, status=None,
              min_rows=1, last=None):
    wheres = []
    params = []
    if session:
        wheres.append("session_id = ?")
        params.append(session)
    if after:
        wheres.append("timestamp >= ?")
        params.append(after)
    if before:
        wheres.append("timestamp <= ?")
        params.append(before)
    if status:
        wheres.append("status = ?")
        params.append(status)

    where = ("WHERE " + " AND ".join(wheres)) if wheres else ""
    order = "ORDER BY timestamp DESC"
    limit = f"LIMIT {int(last)}" if last else ""
    query = f"SELECT * FROM monitoring_llm_calls {where} {order} {limit}"
    rows = db.execute(query, params).fetchall()

    if len(rows) < min_rows:
        return {"error": f"只有 {len(rows)} 条记录（要求 ≥{min_rows}）", "n": len(rows)}

    return {
        "n": len(rows),
        "total_tokens": stats(rows, "total_tokens"),
        "input_tokens": stats(rows, "input_tokens"),
        "output_tokens": stats(rows, "output_tokens"),
        "duration_ms": stats(rows, "duration"),
        "status_breakdown": {
            s: sum(1 for r in rows if r["status"] == s)
            for s in sorted(set(r["status"] for r in rows))
        },
        "model_breakdown": {
            m: sum(1 for r in rows if r["model_name"] == m)
            for m in sorted(set(r["model_name"] for r in rows))
        },
        "time_range": {
            "from": rows[-1]["timestamp"] if len(rows) > 1 else rows[0]["timestamp"],
            "to": rows[0]["timestamp"],
        },
    }


def query_errors(db, session=None, after=None, before=None):
    wheres = []
    params = []
    if session:
        wheres.append("session_id = ?")
        params.append(session)
    if after:
        wheres.append("timestamp >= ?")
        params.append(after)
    if before:
        wheres.append("timestamp <= ?")
        params.append(before)
    where = ("WHERE " + " AND ".join(wheres)) if wheres else ""
    rows = db.execute(
        f"SELECT error_type, error_message, timestamp FROM monitoring_errors {where} ORDER BY timestamp DESC LIMIT 50",
        params,
    ).fetchall()
    return [{"type": r["error_type"], "message": r["error_message"][:200],
             "timestamp": r["timestamp"]} for r in rows]


def check_mode(db, after=None):
    """一键复查：errors + 成功率 + token 超大调用 + plugin log ERROR."""
    if not after:
        after = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    results = {}

    # 1. monitoring_errors
    err_rows = db.execute(
        "SELECT count(*) FROM monitoring_errors WHERE timestamp >= ?", (after,)
    ).fetchone()[0]
    results["errors_new"] = err_rows
    results["errors_ok"] = err_rows == 0

    # 2. LLM 成功率
    total_calls = db.execute(
        "SELECT count(*) FROM monitoring_llm_calls WHERE timestamp >= ?", (after,)
    ).fetchone()[0]
    fail_calls = db.execute(
        "SELECT count(*) FROM monitoring_llm_calls WHERE timestamp >= ? AND status != 'success'",
        (after,),
    ).fetchone()[0]
    fail_rate = fail_calls / total_calls if total_calls else 0
    results["llm_calls_total"] = total_calls
    results["llm_fail_rate"] = round(fail_rate, 3)
    results["llm_fail_ok"] = fail_rate < 0.05

    # 3. 超大 token 调用
    oversized = db.execute(
        "SELECT count(*) FROM monitoring_llm_calls WHERE timestamp >= ? AND total_tokens > 15000",
        (after,),
    ).fetchone()[0]
    results["oversized_gt_15000"] = oversized
    results["oversized_ok"] = oversized == 0

    # 4. plugin log ERROR
    gate_log = os.path.join(PLUGIN_DIR, "silent_gate.log")
    event_log = os.path.join(PLUGIN_DIR, "silent_event.log")
    log_errors = 0
    for log_path in [gate_log, event_log]:
        if os.path.exists(log_path):
            try:
                with open(log_path) as f:
                    for line in f:
                        if "ERROR" in line:
                            log_errors += 1
            except Exception:
                pass
    results["plugin_log_errors"] = log_errors
    results["plugin_log_ok"] = log_errors == 0

    results["all_ok"] = all([
        results["errors_ok"], results["llm_fail_ok"],
        results["oversized_ok"], results["plugin_log_ok"],
    ])
    return results


def main():
    parser = argparse.ArgumentParser(description="查询 langbot monitoring DB")
    parser.add_argument("--session", help="session_id 过滤")
    parser.add_argument("--after", help="开始时间 (YYYY-MM-DD HH:MM)")
    parser.add_argument("--before", help="结束时间 (YYYY-MM-DD HH:MM)")
    parser.add_argument("--status", help="状态过滤 (success/error)")
    parser.add_argument("--min-rows", type=int, default=1, help="最少行数 (默认 1)")
    parser.add_argument("--last", type=int, help="最近 N 条")
    parser.add_argument("--check", action="store_true", help="一键复查模式")
    args = parser.parse_args()

    db = connect()

    if args.check:
        result = check_mode(db, after=args.after)
    else:
        result = query_llm(
            db, session=args.session, after=args.after, before=args.before,
            status=args.status, min_rows=args.min_rows, last=args.last,
        )
        if not args.last and not args.check and not args.after:
            result["_hint"] = "未指定时间范围，返回全量数据可能不全。建议加 --after/--last"

    db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
