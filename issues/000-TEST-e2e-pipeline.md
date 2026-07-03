---
type: AFK
estimate: 0.5d
effort: small
status: in_review
blocked_by: []
needs_llm: true
needs_vision: false
needs_pdf: false
needs_docker: false
test_files: ["archon/test-dispatch.sh"]
---

# TEST: 端到端管线验证

## Acceptance Criteria
- [ ] AC1: dispatch 扫描到本 issue 并 claim
- [ ] AC2: 宪法检查通过
- [ ] AC3: Archon DAG 至少 implement + validate 跑通
