# Playwright E2E 测试质量检查

> 技术栈模块 — 仅对 `config.yaml` 中 `tech_stack.tags` 含 `playwright` 的项目部署。
> 通用测试规则见 `09-测试质量宪法.md`。

## 检查项

| # | 检查项 | 严重度 | 检测方式 |
|---|--------|:------:|---------|
| G3 | 无 `waitUntil: 'domcontentloaded'` 用于 SPA 页面 | 🔴 阻断 | grep `waitUntil.*domcontentloaded` |
| G4 | 无 `if (count() > 0)` 静默跳过模式 | 🔴 阻断 | grep `if.*count.*>\s*0` + `click\|check` |
| G5 | fixture/helper 中有 `page.on('pageerror')` 监听 | 🔴 阻断 | grep `page.on('pageerror'` |
| G6 | fixture/helper 中有 `console.error` 监听 | 🔴 阻断 | grep `msg.type() === 'error'` |
| G7 | 无裸 `waitForTimeout` 替代条件等待 | 🟡 警告 | grep `waitForTimeout(` 排除合理用途 |
| G8 | 测试数据源有完整性验证注释 | 🟡 警告 | 检查 sale_id/测试用户 附近有无数据来源说明 |

## 通过标准

- 🔴 阻断项 全部通过，缺一不可
- 🟡 警告项 需人工判断或附带 justification 注释

## 反例

### G3: SPA 页面用 domcontentloaded

```javascript
// ❌ 阻断 — SPA 用 domcontentloaded，React 异步渲染未完成
await page.goto(url, { waitUntil: 'domcontentloaded' });
await page.click('.ant-menu-item');  // 元素可能还不存在

// ✅ 用 networkidle + waitForSelector
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForSelector('.ant-menu-item', { timeout: 10000 });
```

### G4: 静默跳过

```javascript
// ❌ 阻断 — 元素不存在时静默通过，什么都没测
const tab = page.locator('.ant-menu-item');
if (await tab.count() > 0) {
  await tab.click();
}

// ✅ 硬断言 — 元素必须存在
const tab = page.locator('.ant-menu-item');
await expect(tab, '菜单项必须存在').toBeVisible({ timeout: 10000 });
await tab.click();
```

### G7: 裸 waitForTimeout

```javascript
// ❌ 警告 — 固定等待，不可靠且慢
await page.waitForTimeout(2000);
await expect(page.locator('.result')).toBeVisible();

// ✅ 条件等待
await page.waitForSelector('.result', { timeout: 5000 });
await expect(page.locator('.result')).toBeVisible();
```

## 参考

- 基于 UMES3 喷涂单/穿条单 46 条 E2E 实战踩坑（29 条假通过根因分析）
- fixture 参考实现：`react-scaffold/tests/e2e/helpers.js`（gotoSellDetail + clickMenuTab 模式）
- `memory/playwright-spa-wait-timing.md` — domcontentloaded 问题详细记录
