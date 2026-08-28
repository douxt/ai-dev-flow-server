# Node 集成测试

> 技术栈模块 — `tags: node, vitest`。通用分层策略见 `knowledge/10-测试分层策略.md`
> reviewed_at: __REVIEWED_AT__
> status: current

## 工具矩阵

| 工具 | 用途 | 版本约束 |
|------|------|---------|
| **Vitest** | 测试框架（项目已有则复用） | 1.x（Node 14+） |
| **Testing Library** | 组件集成测试（render + fireEvent/screen） | 按项目 React/Vue 版本选 |
| **nock** | HTTP mock（拦截 Node http 层） | nock@13（Node 14 兼容，锁定版本不升 v14+） |
| **Playwright request context** | API 集成测试（真实 HTTP，双 baseURL 模式） | 项目已有 Playwright 则复用其 `request` |

## 模式 A：API 集成测试（Playwright request context）

适用：在 E2E 项目里测 API 契约，但不走浏览器。

```typescript
// tests/integration/api_store.spec.ts
import { test, expect } from '@playwright/test'

test.describe('store_api — 涂料列表', () => {
  test('GET paint_list_by_sale 返回涂料列表', async ({ request }) => {
    const res = await request.get('http://app:8080/store_api.php?action=paint_list_by_sale&sale_id=40462')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body.code).toBe(0)
    expect(body.list.length).toBeGreaterThan(0)
  })

  test('GET paint_list_by_sale 无权限返回错误', async ({ request }) => {
    const res = await request.get('http://app:8080/store_api.php?action=paint_list_by_sale&sale_id=99999')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body.code).not.toBe(0)
  })
})
```

### 双 baseURL 模式

```typescript
// playwright.config.ts 中配置
export default defineConfig({
  use: {
    // 浏览器测试用
    baseURL: 'http://localhost:3000',
    // API 集成测试用（通过 request context 指定不同 baseURL）
  },
  projects: [
    { name: 'e2e', testDir: './tests/e2e' },
    { name: 'integration', testDir: './tests/integration' },
  ]
})
```

## 模式 B：组件集成测试（Vitest + Testing Library）

适用：测 React/Vue 组件的交互行为。

```typescript
// tests/integration/OrderForm.spec.tsx
import { test, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { OrderForm } from '@/components/OrderForm'

test('填写订单号 → 点击查询 → 显示结果', async () => {
  render(<OrderForm />)

  const input = screen.getByPlaceholderText('订单号')
  await fireEvent.change(input, { target: { value: '40462' } })

  const btn = screen.getByText('查询')
  await fireEvent.click(btn)

  const result = await screen.findByText('涂料列表')
  expect(result).toBeVisible()
})
```

## 模式 C：模块集成测试（Vitest + nock）

适用：调用内部模块 + mock HTTP 边界。

```typescript
// tests/integration/paint_service.spec.ts
import { test, expect } from 'vitest'
import nock from 'nock'

// 被测模块
import { getPaintList } from '@/services/paint'

test('getPaintList 调用后端 API → 返回涂料数组', async () => {
  // mock 外部边界
  nock('http://localhost:8080')
    .get('/store_api.php?action=paint_list_by_sale&sale_id=40462')
    .reply(200, { code: 0, list: [{ id: 1, name: '水性漆' }] })

  const result = await getPaintList({ sale_id: '40462' })

  expect(result).toHaveLength(1)
  expect(result[0].name).toBe('水性漆')
})
```

## 模式 D：数据库集成（事务回滚）

```typescript
// tests/integration/db_order.spec.ts
import { test, expect } from 'vitest'
import { db } from '@/db'

test.beforeEach(async () => {
  await db.query('BEGIN')
})

test.afterEach(async () => {
  await db.query('ROLLBACK')
})

test('insertOrder → SELECT 能查到新订单', async () => {
  await db.query(
    "INSERT INTO orders (id, status) VALUES (99999, 'new')"
  )
  const [row] = await db.query('SELECT * FROM orders WHERE id = 99999')
  expect(row.status).toBe('new')
})
```

## 渐进集成策略

1. 重构前：特征测试 `tests/characterization/` 锁现状
2. 新功能：按决策树选集成测试（不增 E2E）
3. 存量 E2E：不动，通过增量稀释降低比例
4. CI：Vitest 集成测试比 Playwright E2E 快 10-50x，可入 pre-push hook
