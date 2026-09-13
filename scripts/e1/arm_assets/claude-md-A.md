# 本项目工作方式（ai-dev-flow 流程约束）

完成工单必须走 TDD 流程，阶段状态机由 hook 自动追踪：

```
tickets:reviewed → tdd:done → implement:done
```

## 必经步骤（写任何实现源码前）

1. 按工单验收标准（AC）先写**失败测试** + 必要的接口 stub
2. 运行测试确认 🔴 RED（新测试必须真实失败）
3. RED commit：message 必须含 `TDD: RED`
4. 之后系统放开实现写入，写最小实现让测试转绿
5. GREEN commit：message 含 `TDD: GREEN`

## 铁律

- 测试 = 验收标准的可执行版本；GREEN 阶段**禁止修改测试文件**（不许削弱断言/删失败测试来"变绿"）
- 跳过 RED 直接写实现 = 流程违规，会被门禁拦截
- 测试确实有 bug → 停下说明原因，等人工判断，不许私改
