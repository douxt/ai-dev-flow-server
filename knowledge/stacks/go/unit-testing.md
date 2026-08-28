# Go 单元测试规范

> 技术栈模块 — 按 `tags: go` 部署。
> 来源：go-vue-scaffold 最佳实践调研（2026-08），通用部分萃取。
> 门禁联动：.devflow/scripts/test-gate.sh（C0.5 发现 `*_test.go`）、g0-inject.sh（策略 6/7 Go 注入）
> reviewed_at: __REVIEWED_AT__
> status: current

## 硬性要求

1. **表驱动 + `t.Run` 子测试**（项目 CLAUDE.md 已锁定的通用惯例）：
   ```go
   tests := []struct {
       name    string
       input   int
       want    int
       wantErr bool
   }{...}
   for _, tt := range tests {
       t.Run(tt.name, func(t *testing.T) { ... })
   }
   ```
   - `wantErr` 字段显式表达错误分支
2. **测试 helper 标 `t.Helper()`**——失败定位到调用行
3. **fixtures 放 `testdata/`**

## Handler 测试

```go
req := httptest.NewRequest("GET", "/users/1", nil)
rec := httptest.NewRecorder()
router.ServeHTTP(rec, req)

// 完整断言，不只断言 200：
// 状态码、Content-Type、响应 JSON 结构、错误体形状
```

## 分层 mock

- service 测试注入 fake repository（内存实现）或手写 stub
- `require` 用于 setup 断点，`assert` 用于状态检查
- mock 只验证关键协作，勿过度耦合实现细节

## 集成测试隔离

- 集成测试用 `//go:build integration` 标签隔离，保证单测秒级
- CI 设覆盖率门禁（≥80% 起步）

## 断言强度对照（ASI 映射）

| ASI 级别 | Go 写法 |
|:--:|------|
| 恒真 | ❌ `if err != nil { t.Skip }` |
| 存在 | `assert.NoError(t, err)`（仅存活性） |
| 精确值 | `assert.Equal(t, want, got)` ✅ |
| 结构 | `assert.JSONEq` / 逐字段断言 ✅ |
| 错误分支 | `wantErr` 表驱动字段 ✅ |

## 门禁行为说明

- test-gate.sh 对 Go 项目只扫描 `*_test.go`（源码 DSN 等不会误报 C0.3 硬编码端口）
- g0-inject.sh 策略 6/7：`return true`→`return false`、`StatusOK`→`StatusInternalServerError`
