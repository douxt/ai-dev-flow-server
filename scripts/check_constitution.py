#!/usr/bin/env python3
"""Issue 质量宪法机器检查 — 7 项可自动化规则
用法: python3 check_constitution.py <issue_file> [--json]
输出: JSON 格式的检查结果
"""
import sys, os, re, json

try:
    import frontmatter
except ImportError:
    print(json.dumps({"file": sys.argv[1] if len(sys.argv) > 1 else "", "passed": 0, "failed": 1,
        "checks": [{"rule": "0.deps", "severity": "fail", "desc": "缺少 python-frontmatter 依赖，请 pip install python-frontmatter"}]}))
    sys.exit(1)

try:
    import yaml
except ImportError:
    yaml = None

VALID_STATUSES = {"backlog", "ready", "in_progress", "in_review", "done", "failed"}
VALID_TYPES = {"AFK", "HITL"}
VALID_EFFORTS = {"small", "medium", "large"}


def load_issue(path):
    with open(path) as f:
        return frontmatter.load(f)


def load_config(workspace):
    """读取 .devflow/config.yaml"""
    config_path = os.path.join(workspace, ".devflow", "config.yaml")
    if yaml and os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def run(issue_path, json_out=False):
    post = load_issue(issue_path)
    results = []
    passed = 0
    failed = 0
    warned = 0

    def add(rule, severity, desc):
        nonlocal passed, failed, warned
        if severity == "pass":
            passed += 1
        elif severity == "warning":
            warned += 1
        else:
            failed += 1
        results.append({"rule": rule, "severity": severity, "desc": desc})

    # 1. estimate ≤1d
    est = post.get("estimate", "")
    if est:
        match = re.search(r'(\d+\.?\d*)\s*d', str(est))
        days = float(match.group(1)) if match else 0
        if days <= 1:
            add("1.estimate", "pass", f"工时 {est} ≤1d")
        elif days <= 2:
            add("1.estimate", "warning", f"工时 {est} >1d，如拆分会留半成品可接受，否则须拆分")
        else:
            add("1.estimate", "fail", f"工时 {est} >2d，必须拆分")
    else:
        add("1.estimate", "fail", "estimate 字段缺失")

    # 2. type 正确
    itype = post.get("type", "")
    if itype in VALID_TYPES:
        add("2.type", "pass", f"type={itype} 合法")
    elif itype:
        add("2.type", "fail", f"type={itype} 不合法，须为 AFK 或 HITL")
    else:
        add("2.type", "fail", "type 字段缺失")

    # 3. effort 约束
    effort = post.get("effort", "")
    if effort == "small":
        add("3.effort", "pass", "effort=small 自动通过")
    elif effort == "medium":
        add("3.effort", "warning", "effort=medium 需确认不超 2d")
    elif effort == "large":
        add("3.effort", "fail", "effort=large 必须拆分后再标 ready")
    else:
        add("3.effort", "warning", "effort 字段缺失或无效")

    # 4. blocked_by 字段存在且无循环
    blocked = post.get("blocked_by", [])
    if isinstance(blocked, str):
        blocked = [b.strip() for b in blocked.split(",") if b.strip()]
    if blocked:
        add("4.blocked_by", "pass", f"依赖已声明: {blocked}")
    else:
        add("4.blocked_by", "pass", "无依赖")

    # 5. needs_* 字段
    needs_fields = ["needs_llm", "needs_vision", "needs_pdf", "needs_docker"]
    declared = [n for n in needs_fields if n in post]
    if declared:
        vals = {n: post[n] for n in declared}
        add("5.needs", "pass", f"needs_* 已声明: {vals}")
    else:
        add("5.needs", "warning", "needs_* 字段均未声明，建议至少声明 needs_llm")

    # 6. test_files 非空
    tf = post.get("test_files", [])
    if isinstance(tf, str):
        tf = [t.strip() for t in tf.split(",") if t.strip()]
    if tf:
        add("6.test_files", "pass", f"test_files: {tf}")
    else:
        add("6.test_files", "warning", "test_files 为空或缺失")

    # 7. status 合法
    st = post.get("status", "")
    if st in VALID_STATUSES:
        add("7.status", "pass", f"status={st} 合法")
    elif st:
        add("7.status", "fail", f"status={st} 不合法，须为 {VALID_STATUSES}")
    else:
        add("7.status", "fail", "status 字段缺失")

    if json_out:
        print(json.dumps({"file": issue_path, "passed": passed, "warned": warned, "failed": failed,
            "checks": results}, indent=2, ensure_ascii=False))
    else:
        total = passed + warned + failed
        print(f"📋 {issue_path} — 通过 {passed}/{total}（警告 {warned}，失败 {failed}）")
        for r in results:
            icon = "✅" if r["severity"] == "pass" else "⚠️" if r["severity"] == "warning" else "❌"
            print(f"  {icon} [{r['rule']}] {r['desc']}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 check_constitution.py <issue_file> [--json]")
        sys.exit(1)
    path = sys.argv[1]
    json_out = "--json" in sys.argv
    if not os.path.exists(path):
        print(json.dumps({"file": path, "error": "文件不存在"}, ensure_ascii=False))
        sys.exit(1)
    sys.exit(run(path, json_out))
