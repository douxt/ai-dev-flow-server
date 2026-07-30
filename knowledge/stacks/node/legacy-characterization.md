# Node/React 遗留代码特征测试

> 技术栈模块 — 按 `tags: node,react` 部署。
> 通用流程见 `knowledge/11-遗留代码特征测试.md`

## 模式 A：Vitest `toMatchSnapshot()`（推荐）

适用：React 组件、纯函数、工具函数

```javascript
// tests/characterization/ticket-001-order-calc.test.js
import { describe, it, expect } from 'vitest';
import { calcOrderTotal } from '../../src/utils/orderCalc';

describe('characterization: calcOrderTotal', () => {
  it('captures current behavior for standard order', () => {
    const order = { items: [{ price: 100, qty: 2 }], discount: 0.1 };
    const result = calcOrderTotal(order);
    // 快照锁定当前行为（不管对不对）
    expect(result).toMatchSnapshot();
  });

  it('captures edge case: empty order', () => {
    expect(calcOrderTotal({ items: [] })).toMatchSnapshot();
  });

  it('captures edge case: negative discount', () => {
    expect(calcOrderTotal({ items: [{ price: 50 }], discount: -0.2 })).toMatchSnapshot();
  });
});
```

首次运行 `vitest --update` 生成快照。后续运行对比。

## 模式 B：Scrubber — 处理非确定性数据

```javascript
// 处理时间戳、UUID、随机数
import { replaceProperty } from 'vitest';

expect.anyDate = () => expect.any(String); // 简化日期匹配

const result = await generateReport({ from: '2026-01-01' });
expect({
  ...result,
  generatedAt: '[SCRUBBED]',  // 替换非确定性字段
  requestId: '[SCRUBBED]',
}).toMatchSnapshot();
```

## 模式 C：E2E page.route() — API 行为锁

适用：SPA 页面的 API 调用行为

```javascript
// tests/characterization/ticket-001-paint-list.test.js
import { test, expect } from '@playwright/test';

test('characterization: paint_list API 当前响应快照', async ({ page }) => {
  let capturedResponse;

  await page.route('**/store_api.php?action=paint_list*', async (route) => {
    const response = await route.fetch();
    capturedResponse = await response.json();
    await route.fulfill({ response });
  });

  await page.goto('/chain_sell_detail?sale_id=40462');
  await page.waitForSelector('.paint-list');

  // 快照对比
  expect(capturedResponse).toMatchSnapshot('paint-list-api-response');
});
```

## 环境探针

```bash
# 特征测试前验证
curl -s http://localhost:8890/ | head -1 || echo "[infra] 前端未启动"
```

## 关键约束

- Node 版本：UMES3 用 Node 14.21.3（`.nvmrc`）
- Snapshot 文件在 `tests/characterization/__snapshots__/`（Vitest 自动管理）
- E2E CHARACTERIZATION 测试不替代正式 E2E——改完后应删除
