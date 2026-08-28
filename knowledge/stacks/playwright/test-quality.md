# Playwright E2E 测试质量检查

> 技术栈模块 — 仅对 `config.yaml` 中 `tech_stack.tags` 含 `playwright` 的项目部署。
> 通用测试规则见 `09-测试质量宪法.md`。
> reviewed_at: __REVIEWED_AT__
> status: current

## 检查项

| # | 检查项 | 严重度 | 检测方式 |
|---|--------|:------:|---------|
| G3 | 无 `waitUntil: 'domcontentloaded'` 用于 SPA 页面 | 🔴 阻断 | grep `waitUntil.*domcontentloaded` |
| G4 | 无 `if (count() > 0)` 静默跳过模式 | 🔴 阻断 | grep `if.*count.*>\s*0` + `click\|check` |
| G5 | fixture/helper 中有 `page.on('pageerror')` 监听 | 🔴 阻断 | grep `page.on('pageerror'` |
| G6 | fixture/helper 中有 `console.error` 监听 | 🔴 阻断 | grep `msg.type() === 'error'` |
| G7 | 无裸 `waitForTimeout` 替代条件等待 | 🟡 警告 | grep `waitForTimeout(` 排除合理用途 |
| G8 | 测试数据源有完整性验证注释 | 🟡 警告 | 检查 sale_id/测试用户 附近有无数据来源说明 |
| G9 | 无调试残留提交 — `test.only`/`describe.only`/`page.pause()` 零容忍 | 🔴 阻断 | grep `test\.only\|describe\.only\|it\.only\|page\.pause` |
| G10 | TDD RED 用 `test.fail()` 非 `test.skip()` — 预期失败必须用 `test.fail()`，禁止用 `test.skip()`/`test.fixme()` 绕过 RED 阶段 | 🔴 阻断 | grep `test\.skip\|test\.fixme` tests/e2e/ |
| G11 | Action 走 UI 不绕过 — 被测行为通过 click/fill/submit 执行，不直接 `apiCall()`/`fetch()` 调后端 | ⚠️ 警告 | grep `apiCall\|request\.post\|fetch.*action=` tests/e2e/ |

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

### G10: TDD RED 用 test.skip 冒充

```javascript
// ❌ 阻断 — test.skip() 不运行测试，无法验证功能缺失
test.skip('AC1: pack Tab 有 checkbox 列', async ({ page }) => {
  await gotoSellDetail(page);
  await expect(page.locator('.ant-table-tbody input[type="checkbox"]').first())
    .toBeVisible();
});

// ❌ 阻断 — 裸超时等 RED，无明确 RED 标记
test('AC1: pack Tab 有 checkbox 列', async ({ page }) => {
  await gotoSellDetail(page);
  // 元素不存在时超时 → 测试报告为普通失败，无法区分"预期 RED"和"意外失败"
  await expect(page.locator('.ant-table-tbody input[type="checkbox"]').first())
    .toBeVisible({ timeout: 10000 });
});

// ✅ test.fail() — Playwright 官方 TDD RED 机制
test('AC1: pack Tab 有 checkbox 列', async ({ page }) => {
  test.fail(); // 🔴 AC1: 待实现 — pack Tab 勾选+checkbox
  await gotoSellDetail(page);
  await expect(page.locator('.ant-table-tbody input[type="checkbox"]').first())
    .toBeVisible();
});
```

> `test.fail()` 行为：失败 → "expected failure ✅"；意外通过 → "unexpected pass ❌"（GREEN 后忘删标记会报错）。既验证功能确实缺失，又防止假 GREEN。

### G11: Action 绕过 UI

```javascript
// ❌ 警告 — Action 绕过 UI，直接调 API。handlePaintCreate 内部逻辑从未被测试
test('AC1: 发起喷涂创建', async ({ page }) => {
  await gotoSellDetail(page);
  const res = await apiCall(page, 'paint_create', {
    sale_id: '40462', user_id: '124', items: paintItems
  });
  expect(res.status).toBe(0);  // API 返回正确 ≠ 按钮能用
});

// ✅ Action 走完整 UI 路径
test('AC1: 发起喷涂创建', async ({ page }) => {
  test.fail(); // 🔴 待实现
  await gotoSellDetail(page);
  await page.click('.ant-checkbox-wrapper').first();     // 勾选
  await page.click('button:has-text("发起喷涂")');        // 点按钮
  await page.fill('.ant-modal input[name="count"]', '2'); // 填 Modal
  await page.click('.ant-modal button:has-text("确认")'); // 确认
  await expect(page.locator('.ant-message-success')).toBeVisible(); // UI 反馈
});
```

> **Setup 例外**：`beforeAll`/`beforeEach` 中的 `apiCall` 用于创建测试数据/清理——合法。只有 `test()` 函数体内的 Action 才必须走 UI。

## 性能优化

### workers 并行度

默认 `workers: 1` 串行执行。实测 47 条 E2E 耗时 430s → `workers: 2` 降为 237s（45% ↓）。

```javascript
// playwright.config.js
export default defineConfig({
  workers: 2,              // 并行 worker 数（建议 2，CI 环境按 CPU 核数调整）
  fullyParallel: false,    // 同一 spec 文件内串行（避免 describe.serial 冲突）
})
```

- `workers: 1` → 全串行，稳定但慢
- `workers: 2` → 推荐默认值，提速 ~45%，风险低
- `workers: 4+` → 仅在 CI 大机器上使用，注意 flaky 风险

### 页面导航策略

SPA 页面避免 `networkidle`——Webpack HMR WebSocket 可能无限等待。改用 `load` + `waitForSelector`：

```javascript
// ❌ 慢且可能超时
await page.goto(url, { waitUntil: 'networkidle' });

// ✅ 快且稳定
await page.goto(url, { waitUntil: 'load' });
await page.waitForSelector('.ant-table', { timeout: 10000 });
```

## 参考

- 基于 UMES3 喷涂单/穿条单 46 条 E2E 实战踩坑（29 条假通过根因分析）
- fixture 参考实现：`react-scaffold/tests/e2e/helpers.js`（gotoSellDetail + clickMenuTab 模式）
- `memory/playwright-spa-wait-timing.md` — domcontentloaded 问题详细记录

## 项目级 pre-commit 硬门禁（参考）

> DevFlow 不强制安装。项目需要硬阻断时，复制以下脚本到 `.git/hooks/pre-commit`：

```bash
#!/bin/bash
# C0 硬门禁版 — .git/hooks/pre-commit
# 阻断：调试残留 / 恒真断言 / 硬编码端口
git diff --cached | grep -E "test\.only|describe\.only|page\.pause" \
  && echo "❌ C0.1: 调试残留" && exit 1
git diff --cached | grep -E "toBeGreaterThanOrEqual\(0\)|typeof.*toBe\('number'\)" \
  && echo "❌ C0.2: 恒真断言" && exit 1
exit 0
```
