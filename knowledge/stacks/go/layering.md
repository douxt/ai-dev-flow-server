# Go 后端分层

> 技术栈模块 — 按 `tags: go` 部署。
> 来源：go-vue-scaffold 最佳实践调研（2026-08），通用部分萃取。

## 分层结构

**核心原则：Handler 只做 HTTP 事，业务逻辑在 Service，数据访问在 Repository。**

```
internal/
├── handler/     # HTTP 层：参数绑定、校验、组装响应。不写业务逻辑
├── service/     # 业务逻辑层：依赖 repository 接口（可 mock）
├── repository/  # GORM 数据访问：纯 SQL/ORM 操作
├── model/       # GORM 模型 + 领域结构
├── middleware/  # 认证、日志、request-id、限流
├── router/      # 路由注册
├── config/
└── dto/         # 请求/响应 DTO（与 model 分离，防字段泄漏）
```

## 硬性规则

- 依赖方向单向：handler → service → repository，禁止反向 import、禁止跨层调用（handler 不直接碰 DB）
- `service` 依赖 `repository` 的**接口**而非具体实现，测试时可替换为 stub/fake/mock
- `cmd/` 只做依赖装配：config → db → repository → service → handler → router → server
- 早期可跳过 service 层直接 handler → db，但 repository 接口化要尽早做（成本最低收益最大）

## 分层与测试的配合

| 层 | 测试方式 |
|------|------|
| handler | `httptest.NewRecorder` + fake service |
| service | 注入 fake repository（内存实现）或手写 stub |
| repository | 集成测试（`//go:build integration` 标签隔离） |

## 常见违规

```go
// ❌ handler 直接持有 *gorm.DB
func (h *UserHandler) Get(c *gin.Context) {
    var u User
    h.db.Where("id = ?", c.Param("id")).First(&u)
}

// ✅ repository 接口化
type UserRepository interface {
    FindByID(ctx context.Context, id uint) (*User, error)
}
```

## 参考

- go-admin-team/go-admin（MIT）——分层清晰，结构设计可直接借鉴
- flipped-aurora/gin-vue-admin——栈匹配但含 TS/JS 混用等历史包袱，只取模式不抄实现
