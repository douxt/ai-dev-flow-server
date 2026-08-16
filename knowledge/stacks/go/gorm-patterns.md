# GORM 模式与常见坑

> 技术栈模块 — 按 `tags: go` 部署。
> 来源：go-vue-scaffold 最佳实践调研（2026-08），通用部分萃取。

## 事务

- **事务永远用闭包**：`db.Transaction(func(tx *gorm.DB) error {...})`，返回 error 自动回滚。手写 Begin/Commit/Rollback 是连接泄漏头号来源
- 嵌套事务用 `tx` 传参，不要另开
- 条件更新检查 `RowsAffected == 0` 并报错（并发扣库存场景必须）

## N+1 与关联

- 循环里禁 `Association()`/`Related()`；列表用 `Preload`
- 字段裁剪时**必须包含外键**：`Preload("Orders", db.Select("id", "user_id"))`，否则关联匹配失败

## 软删除

- `DeletedAt` 加索引
- 唯一字段（email 等）用复合索引 `UNIQUE KEY (deleted_at, email)`，否则软删后无法重建同名记录
- 永久删除用 `Unscoped()`

## 连接池（必须显式配置）

```go
sqlDB, _ := db.DB()
sqlDB.SetMaxOpenConns(100)
sqlDB.SetMaxIdleConns(20)      // 20~30
sqlDB.SetConnMaxLifetime(time.Hour)  // 略低于 MySQL wait_timeout，防僵尸连接
```

## 其他

- 零值更新（false/0/""）需 `Select` 指定字段或 map
- 禁止裸 `Find` 无 `Where/Limit`；查询条件用链式 `Where` 占位符，禁止字符串拼接
- 高写入吞吐的日志/缓存类写入可用 `SkipDefaultTransaction`（~30% 提升），业务原子链禁用
- 分页：行数 >10 万时 `LIMIT/OFFSET` 是性能悬崖，首选游标分页（`WHERE id > ?` + 单调主键）；`Count()` 单独语句执行

## 迁移

- 迁移工具选 **Goose**（SQL 文件可 review、可回滚），AutoMigrate 只用于原型
