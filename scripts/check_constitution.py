#!/usr/bin/env python3
"""Ticket 质量宪法机器检查 v3.0 — 15 项可自动化规则 + 安全红线扫描

用法:
  python3 check_constitution.py <ticket_file>           # 单文件检查
  python3 check_constitution.py <ticket_file> --json    # JSON 输出
  python3 check_constitution.py --batch <issues_dir>    # 批量扫描目录
  python3 check_constitution.py --batch <dir> --json    # 批量 + JSON

v3.0 新增:
  - 安全红线扫描 (auth/payment/crypto/delete/permission)
  - 上下文窗口预算估算
  - AC 验证级别校验 ([auto]/[human-verify]/[decision])
  - blocked_by 循环依赖检测
  - Ponytail 可机器检查项
  - 批量目录扫描模式
"""
import sys, os, re, json
from collections import defaultdict

try:
    import frontmatter
except ImportError:
    print(json.dumps({"file": sys.argv[1] if len(sys.argv) > 1 else "", "passed": 0, "failed": 1,
        "checks": [{"rule": "0.deps", "severity": "fail",
                     "desc": "缺少 python-frontmatter 依赖，请 pip install python-frontmatter"}]}))
    sys.exit(1)

try:
    import yaml
except ImportError:
    yaml = None

VALID_STATUSES = {"backlog", "ready", "in_progress", "in_review", "done", "failed"}
VALID_TYPES = {"AFK", "HITL"}
VALID_EFFORTS = {"small", "medium", "large"}
VALID_AC_LEVELS = {"[auto]", "[human-verify]", "[decision]"}

# 安全红线关键词 → 类型映射
SAFETY_KEYWORDS = {
    "auth": ["auth", "authentication", "login", "logout", "session", "token", "jwt",
             "oauth", "rbac", "permission", "role", "access control", "认证", "登录", "权限"],
    "payment": ["payment", "billing", "invoice", "charge", "refund", "price",
                "coupon", "order amount", "支付", "计费", "订单金额", "退款"],
    "crypto": ["encrypt", "decrypt", "cipher", "aes", "rsa", "hash", "signature",
               "private key", "secret key", "密码", "加密", "签名", "密钥"],
    "delete": ["delete", "drop table", "truncate", "destroy", "purge", "cascade delete",
               "hard delete", "删除", "销毁", "清空"],
    "permission": ["permission", "acl", "access control", "rbac", "role bind",
                   "scope change", "权限", "角色绑定", "访问控制"],
}


def load_issue(path):
    with open(path) as f:
        return frontmatter.load(f)


def load_config(workspace):
    config_path = os.path.join(workspace, ".devflow", "config.yaml")
    if yaml and os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def estimate_tokens(text):
    """粗略 token 估算：中英文混合，~1.5 chars/token"""
    return max(1, len(text) // 1.5)


def detect_safety_types(text):
    """扫描文本中的安全敏感关键词 → 返回命中的类型集合"""
    text_lower = text.lower()
    hits = set()
    for stype, keywords in SAFETY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                hits.add(stype)
                break
    return hits


def detect_blocked_by_cycle(issues_dir, issue_file, blocked_ids, visited=None):
    """检测 blocked_by 循环依赖（DFS）"""
    if visited is None:
        visited = set()
    basename = os.path.basename(issue_file)
    if basename in visited:
        return True  # 发现循环
    visited.add(basename)
    for bid in blocked_ids:
        # 尝试在 issues/ 目录中找到被依赖的文件
        for f in os.listdir(issues_dir):
            if f.startswith(str(bid)) or str(bid) in f:
                dep_path = os.path.join(issues_dir, f)
                try:
                    dep = load_issue(dep_path)
                    dep_blocked = dep.get("blocked_by", [])
                    if isinstance(dep_blocked, str):
                        dep_blocked = [b.strip() for b in dep_blocked.split(",") if b.strip()]
                    if detect_blocked_by_cycle(issues_dir, dep_path, dep_blocked, visited.copy()):
                        return True
                except Exception:
                    pass
    return False


def scan_ac_levels(content):
    """检测 AC 是否标注验证级别"""
    ac_matches = re.findall(r'-\s*\[.\]\s*(?:\[(auto|human-verify|decision)\])?\s*(AC\d*):', content)
    if not ac_matches:
        # 尝试另一种格式
        ac_matches = re.findall(r'\[(auto|human-verify|decision)\]', content)
    return ac_matches


def run(issue_path, issues_dir=None, json_out=False, workspace=None):
    post = load_issue(issue_path)
    content = post.content if hasattr(post, 'content') else ""
    results = []
    passed = 0
    failed = 0
    warned = 0
    safety_hits = set()

    def add(rule, severity, desc):
        nonlocal passed, failed, warned
        if severity == "pass":
            passed += 1
        elif severity == "warning":
            warned += 1
        else:
            failed += 1
        results.append({"rule": rule, "severity": severity, "desc": desc})

    # ── 原有 7 项 ──

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

    # 4. blocked_by 字段存在 + 循环检测
    blocked = post.get("blocked_by", [])
    if isinstance(blocked, str):
        blocked = [b.strip() for b in blocked.split(",") if b.strip()]
    if blocked:
        if issues_dir and os.path.isdir(issues_dir):
            if detect_blocked_by_cycle(issues_dir, issue_path, blocked):
                add("4.blocked_by", "fail", f"依赖存在循环: {blocked}")
            else:
                add("4.blocked_by", "pass", f"依赖已声明且无循环: {blocked}")
        else:
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

    # ── v3.0 新增 8 项 ──

    # 8. 安全红线扫描
    full_text = json.dumps({k: str(v) for k, v in post.items()}) + " " + (content or "")
    safety_hits = detect_safety_types(full_text)
    existing_safety = post.get("safety", "")
    if safety_hits:
        safety_labels = ",".join(sorted(safety_hits))
        if existing_safety:
            add("8.safety", "pass",
                f"⚠️ HUMAN_REVIEW_REQUIRED — 安全标记: {safety_labels}（frontmatter 已标注）")
        else:
            add("8.safety", "warning",
                f"⚠️ 检测到安全敏感内容: {safety_labels}，建议在 frontmatter 添加 safety: {safety_labels}")
    else:
        if existing_safety:
            add("8.safety", "pass", f"safety={existing_safety}（关键词未命中，保留手动标记）")
        else:
            add("8.safety", "pass", "无安全敏感内容")

    # 9. 上下文窗口预算估算
    text_len = len(full_text)
    est_tokens = int(estimate_tokens(full_text))
    # 120K 窗口的 40% = 48K tokens
    if est_tokens <= 48000:
        add("9.window_budget", "pass",
            f"估算 {est_tokens} tokens（≤48K 的 {est_tokens * 100 // 48000}%）")
    elif est_tokens <= 60000:
        add("9.window_budget", "warning",
            f"估算 {est_tokens} tokens（超过 48K 预算，建议精简或拆分）")
    else:
        add("9.window_budget", "fail",
            f"估算 {est_tokens} tokens（严重超过 48K 预算，必须拆分）")

    # 10. AC 验证级别标注
    ac_levels = scan_ac_levels(content)
    if ac_levels:
        unique_levels = set(ac_levels)
        if "[auto]" in unique_levels:
            add("10.ac_levels", "pass",
                f"AC 已标注验证级别: {', '.join(sorted(unique_levels))}")
        else:
            add("10.ac_levels", "warning",
                "AC 缺少 [auto] 级别标注，建议至少包含机器可验证项")
    else:
        add("10.ac_levels", "warning",
            "未检测到 AC 验证级别标注 ([auto]/[human-verify]/[decision])")

    # 11. Scope 边界声明
    body = content if content else ""
    has_scope_in = bool(re.search(r'(?:##\s*Scope|In[：:])', body, re.IGNORECASE))
    has_scope_out = bool(re.search(r'(?:Out[：:]|不含|不包含|不碰)', body, re.IGNORECASE))
    if has_scope_in and has_scope_out:
        add("11.scope", "pass", "Scope 边界（In/Out）已声明")
    elif has_scope_in:
        add("11.scope", "warning", "Scope 仅声明了 In 范围，缺少 Out 边界")
    else:
        add("11.scope", "warning", "Scope 边界未声明")

    # 12. 架构约束引用
    has_constraint = bool(re.search(r'(?:架构约束|不可变规则|Constraints|Architecture)', body, re.IGNORECASE))
    if has_constraint:
        add("12.constraints", "pass", "架构约束段已引用")
    else:
        add("12.constraints", "warning", "未找到架构约束引用")

    # 13. 前置准备
    has_prereq = bool(re.search(r'(?:前置准备|Prerequisites|依赖表格)', body, re.IGNORECASE))
    if has_prereq:
        add("13.prerequisites", "pass", "前置准备段存在")
    else:
        add("13.prerequisites", "warning", "前置准备段缺失")

    # 14. 测试策略
    has_test_strategy = bool(re.search(r'(?:测试策略|单元测试|E2E|mock)', body, re.IGNORECASE))
    if has_test_strategy:
        add("14.test_strategy", "pass", "测试策略已声明")
    else:
        add("14.test_strategy", "warning", "测试策略未声明")

    # 15. Ponytail 可机器检查：import 是否可标准库替代
    imports = re.findall(r'import\s+(\S+)', body)
    third_party = [imp for imp in imports
                   if not imp.startswith(('.', 'builtins', 'os', 'sys', 're', 'json',
                                          'math', 'datetime', 'collections', 'itertools',
                                          'functools', 'typing', 'pathlib', 'logging'))]
    if third_party:
        add("15.ponytail_imports", "pass",
            f"第三方依赖: {', '.join(third_party[:5])}" +
            (f" ... 等 {len(third_party)} 个" if len(third_party) > 5 else ""))
    else:
        add("15.ponytail_imports", "pass", "无第三方依赖或无可替代的标准库替代")

    # ── 输出 ──
    if json_out:
        result = {
            "file": issue_path,
            "passed": passed, "warned": warned, "failed": failed,
            "safety_hits": sorted(safety_hits) if safety_hits else [],
            "checks": results,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        total = passed + warned + failed
        print(f"📋 {issue_path} — 通过 {passed}/{total}（⚠️ 警告 {warned}，❌ 失败 {failed}）")
        if safety_hits:
            print(f"  🛡️  安全红线命中: {', '.join(sorted(safety_hits))} → ⚠️ HUMAN_REVIEW_REQUIRED")
        for r in results:
            icon = "✅" if r["severity"] == "pass" else "⚠️" if r["severity"] == "warning" else "❌"
            print(f"  {icon} [{r['rule']}] {r['desc']}")

    return 0 if failed == 0 else 1


def run_to_dict(issue_path, issues_dir=None, workspace=None):
    """内部使用：调用 run() 的 JSON 模式并返回 dict"""
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    exit_code = 1
    try:
        exit_code = run(issue_path, json_out=True, issues_dir=issues_dir, workspace=workspace)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {"file": issue_path, "error": output.strip(), "passed": 0, "warned": 0, "failed": 1,
                "safety_hits": [], "checks": []}


def run_batch(issues_dir, json_out=False, workspace=None):
    """批量扫描 issues/ 目录下所有 .md 文件"""
    if not os.path.isdir(issues_dir):
        print(f"❌ {issues_dir} 不是有效目录")
        return 1

    md_files = sorted([f for f in os.listdir(issues_dir) if f.endswith('.md')])
    if not md_files:
        print(f"⚠️  {issues_dir} 中无 .md 文件")
        return 0

    all_results = []
    total_passed = 0
    total_warned = 0
    total_failed = 0
    total_safety = set()

    for f in md_files:
        path = os.path.join(issues_dir, f)
        try:
            result = run_to_dict(path, issues_dir, workspace)
            all_results.append(result)
            total_passed += result.get("passed", 0)
            total_warned += result.get("warned", 0)
            total_failed += result.get("failed", 0)
            total_safety.update(result.get("safety_hits", []))
        except Exception as e:
            all_results.append({"file": path, "error": str(e), "passed": 0, "warned": 0, "failed": 0,
                                "safety_hits": [], "checks": []})

    if json_out:
        summary = {
            "scanned": len(md_files),
            "total_passed": total_passed,
            "total_warned": total_warned,
            "total_failed": total_failed,
            "safety_hits": sorted(total_safety),
            "results": all_results,
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        total = total_passed + total_warned + total_failed
        ok = total_failed == 0
        status = "✅ 全部通过" if ok else f"❌ {total_failed} 项失败"
        print(f"\n📊 批量扫描: {issues_dir}/ ({len(md_files)} files)")
        print(f"   通过 {total_passed}/{total} | ⚠️ {total_warned} | ❌ {total_failed} | {status}")
        if total_safety:
            print(f"   🛡️  安全红线文件: {', '.join(sorted(total_safety))}")

    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 check_constitution.py <ticket_file> [--json]")
        print("       python3 check_constitution.py --batch <issues_dir> [--json]")
        sys.exit(1)

    json_out = "--json" in sys.argv

    if "--batch" in sys.argv:
        batch_idx = sys.argv.index("--batch")
        if batch_idx + 1 < len(sys.argv):
            issues_dir = sys.argv[batch_idx + 1]
            sys.exit(run_batch(issues_dir, json_out))
        else:
            print("❌ --batch 需要指定 issues/ 目录")
            sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(json.dumps({"file": path, "error": "文件不存在"}, ensure_ascii=False))
        sys.exit(1)
    sys.exit(run(path, json_out=json_out))
