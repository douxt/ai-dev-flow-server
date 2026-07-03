---
type: AFK
estimate: 0.5d
effort: small
status: in_progress
blocked_by: []
needs_llm: true
needs_vision: false
needs_pdf: false
needs_docker: false
test_files: ["archon/test-dispatch.sh"]
---

# TEST: cron 自动调度验证

## Acceptance Criteria
- [ ] AC1: cron 触发 dispatch 自动扫描到本 issue
- [ ] AC2: claim + Archon DAG 自动执行
- [ ] AC3: 最终 status 为 in_review 或 done
