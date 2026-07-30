# P1 特征测试——最佳实践调研

> 2026-07-30 | 为 DevFlow P1 "遗留代码特征测试"提供设计决策依据
> 调研源：Feathers WELC 2024 更新、PHP 社区实践、TDD+RGR 混合模型、测试组织模式

## 一、核心概念

**特征测试（Characterization Tests）** 出自 Michael Feathers《Working Effectively with Legacy Code》——捕获代码"当前实际行为"的测试，不关心对不对，只关心"改了之后不变"。

```
标准 TDD:  写期望行为 → RED → GREEN → REFACTOR  （测"应该怎样"）
特征测试:  跑当前代码 → 记录实际输出 → 锁定为基线  （测"现在怎样"）
```

Feathers 的核心对比：

| | Edit and Pray | Cover and Modify |
|--|-------------|-----------------|
| 做法 | 分析代码 → 最小改动 → 祈祷没坏 | 写特征测试锁行为 → 改动 → 测试确认 |
| 风险 | 高，不知道改坏了什么 | 低，安全网在 |

**本质**："安全网先于改动"——先建网，再走钢丝。

## 二、触发机制：何时写特征测试

Feathers 的完整步骤链（2024 更新版）：

```
1. 识别改动点（Identify change points）
2. 找到测试点（Find test points — 能观测行为的位置）
3. 发现或创建接缝（Find or create a seam）
4. 打破依赖（Break dependencies）
5. 写特征测试（Write characterization tests）
6. 做功能改动（Make the functional change）
7. 重构清理（Refactor for clarity）
```

**不是触发器，是一个步骤**。当改动目标是"没有测试的现有代码"时，步骤 2-5 自动发生。

业界实践中有三种触发模式：
- **显式命令**：`/characterize` 独立 skill，用户决定何时调用
- **自动检测**：AI 检测到改动文件的测试覆盖率为 0 → 提示
- **Ticket 标注**：`[legacy]` 标签 → 流程自动插入特征测试步骤

## 三、文件放置：特征测试放哪

### 主流方案：独立 `tests/characterization/` 目录

```
tests/
├── characterization/     ← 特征测试（临时安全网）
│   ├── paint_create_test.php
│   └── order_calc_test.php
├── e2e/                  ← E2E 测试（永久）
├── integration/          ← 集成测试（永久）
└── unit/                 ← 单元测试（永久）
```

**为什么独立**：
- 概念不同——特征测试不是 TDD 测试，语义不应混淆
- 生命周期不同——特征测试是短期的（改完后可删/可升级为正式测试）
- 方便批量运行：`phpunit tests/characterization/`
- 方便清理：改完确认后可以整目录扫掉

### 替代方案：源码旁边

PHP 项目可以让探针测试放 `proc/tests/`（UMES3 已有此目录），测试和生产代码就近。

## 四、与 TDD 流程的集成

调研揭示了一个关键区别——**特征测试的 RGR 与标准 TDD 的 RGR 完全相反**：

| 步骤 | 标准 TDD | 特征测试 RGR |
|------|---------|------------|
| RED | 写期望行为的测试 → 失败（代码不存在） | 写捕获当前行为的测试 → **立即通过**（证明理解正确） |
| GREEN | 实现最小代码 → 通过 | —（特征测试本身就是 GREEN，它描述现状） |
| REFACTOR | 清理实现 | 在有安全网的前提下做改动 |

**如果特征测试不通过**：不是代码有问题，是**你对代码行为的理解有问题**——修测试，不修代码。

### 四阶段集成模型

```
Phase 1: 特征测试     → 锁当前行为（安全网）
Phase 2: 预重构       → 提取方法/打破依赖（让改动可行）
Phase 3: 标准 TDD     → RED→GREEN 做实际功能改动
Phase 4: 后重构       → 清理，所有测试（特征+新TDD）保持绿
```

这个模型在金融行业遗留系统现代化中实现了 60-70% 的事故减少。

## 五、技术栈：PHP 遗留项目的特征测试

UMES3 是 PHP 5.4 后端 + Smarty/jQuery 前端。PHP 社区有成熟的模式：

### A. Golden Master / 快照测试

```php
// 跑真实 API，记录完整响应
$response = file_get_contents('http://localhost/store_api.php?action=paint_list_by_sale&sale_id=40462');
file_put_contents('tests/characterization/snapshots/paint_list_by_sale.json', $response);

// 测试中对比快照
$this->assertJsonStringEqualsJsonFile(
    'tests/characterization/snapshots/paint_list_by_sale.json',
    $currentResponse
);
```

### B. Xdebug 追踪 + 自动生成（Sebastian Bergmann 的 de-legacy-fy）

```
xdebug.auto_trace=1
xdebug.collect_params=5
xdebug.collect_return=1
```

CLI 工具从追踪文件自动生成 PHPUnit data provider，每个 data set 包含实际传入参数和实际返回值。

### C. 请求/响应录制中间件

对 HTTP API 端点，录制真实请求-响应对，回放验证。

### D. 数据库状态对比

用专用测试数据库，已知 fixture → 跑操作 → 对比表状态（dump/checksum）。

### **UMES3 推荐策略**

```
策略 A（主推）: HTTP 探针 — curl 调 store_api.php，assert 返回值快照
策略 B（补充）: DB 查询对比 — SELECT 关键表，assert 结果集不变
策略 C（前端）: Playwright page.route() mock API → E2E 锁 UI 行为
```

## 六、快照测试 + 随机数据（2024 现代模式）

结合快照测试和确定性随机数据（Bogus/Faker + 固定 seed）：
- 生成 50+ 变体输入
- 跑遗留代码
- 记录完整 I/O 到 `.verified.txt`
- 可达 ~91% 代码覆盖率

## 参考资料

- Michael Feathers, "Working Effectively with Legacy Code" (2004, 2024 updated): https://github.com/mattpocock/agent-rules-books/blob/main/working-effectively-with-legacy-code/working-effectively-with-legacy-code.md
- Feathers 2024 播客: AI 辅助遗留代码: https://share.snipd.com/episode/15b07f03-6b10-46b4-b302-ef5f1fd7e708
- PHP 特征测试实践: https://thephp.cc/topics/characterization-tests
- Sebastian Bergmann de-legacy-fy: https://github.com/sebastianbergmann/de-legacy-fy
- Gil Zilberfeld, "How to TDD in Legacy Code": https://www.conf42.com/Python_2022_Gil_Zilberfeld_TDD_legacy_code
- 快照测试 + 随机数据: https://blog.nimblepros.com/blogs/characterization-tests-with-snapshot-testing/
