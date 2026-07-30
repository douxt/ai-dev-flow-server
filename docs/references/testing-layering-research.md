# P2 测试分层策略——最佳实践调研

> 2026-07-30 | 四路并行调研：Trophy 分层共识 + 遗留项目起步 + E2E 比例控制 + AI 决策树

## 一、分层比例共识

### Testing Trophy（Kent C. Dodds）

```
        / E2E 10% \       ← 仅核心用户路径
       / 集成 50-70% \    ← 最大层，ROI 最高
      / 单元 20-30%   \
     / 静态分析        \   ← TypeScript/ESLint（不计入比例）
```

**核心主张**："Write tests. Not too many. Mostly integration."

### 2025 年争议：Trophy 是否要倒转？

Kent Dodds 在 2025 年《Call Kent》播客中质疑——SSR 时代（Remix/Next.js）E2E 成本下降、集成测试更难写，倾向于让 E2E 成为最大层。**但 UMES3 是 CSR React 16 + PHP 后端，SSR 论点不适用**。原始 Trophy 仍是最佳参考。

### E2E 比例上限共识

| 来源 | 建议 | 
|------|------|
| 经典金字塔 | 10%（70/20/10） |
| Katalon 2026 | 5-10% |
| UK HomeOffice 标准 | "MUST avoid large numbers" |
| Hack23 强制工具 | 5%（80/15/5） |

**共识：5-10% 安全，不超过 15%。UMES3 当前 100%（46/46）属典型 Ice Cream Cone 反模式。**

## 二、遗留项目集成测试起步

### 前端（Node 14.21.3）

| 方案 | 兼容性 | 推荐度 |
|------|:--:|:--:|
| **uvu** — 超轻量 runner，Node 10+ | ✅ | ⭐ 首选：`npm install uvu`，零配置，72ms 启动 |
| Node 内置 assert + shell runner | ✅ | 零依赖起步 |
| node-core-test — Node 18 回移植 | ✅ | 有 describe/it/mock |
| **MSW** | ❌ | v1 需 Node 16，v2 需 Node 18 |
| nock — HTTP mock 替代 | ✅ | 替代 MSW |

### 后端（PHP 5.4，无 Composer）

| 方案 | 兼容性 | 推荐度 |
|------|:--:|:--:|
| **裸 PHP assert() + shell runner** | ✅ | ⭐ 今天就能用：`php -d assert.active=1 test.php` |
| simpleunit — 纯 PHP assert()，PHP 5.4+ | ✅ | 下载即用，无 Composer |
| 事务型 DB 集成测试 | ✅ | begin_transaction → 测试 → rollback |

### 起步策略

**先写测试，用手头工具。** 不先装框架——遗留项目最大风险是"装了框架跑不起来"。

优先级：核心 API → 支付/状态机 → 历史 Bug 区域 → CRUD。

Strangler Fig 模式：新功能用新方式，旧代码只加特征测试不改测试方式。

## 三、AI 测试类型决策树

### 核心决策维度

| 维度 | 单元 | 集成 | E2E |
|------|:--:|:--:|:--:|
| 需要浏览器？ | 否 | 否 | **是** |
| 涉及多模块交互？ | 否 | **是** | 是 |
| 外部依赖（DB/API）？ | 无/Mock | Real 内/Mock 外 | 全 Real |
| 执行速度 | ms | s | min |
| 适合 CI | push | PR | merge |

### 决策树（嵌入 Prompt 时放前端）

```
开始
  ├─ 需要浏览器/真实 UI？
  │   ├─ 是 → 关键业务路径？（支付/登录/核心转化）
  │   │   ├─ 是 → E2E（≤总测试数 10%）
  │   │   └─ 否 → 能否拆成独立交互步骤？→ 集成
  │   └─ 否 → 继续
  ├─ 涉及多模块/服务交互？
  │   ├─ 是 → API 请求？→ Playwright request context（集成）
  │   │       组件协作？→ 组件集成测试
  │   └─ 否 → 继续
  ├─ 纯逻辑/计算/状态迁移？
  │   └─ 是 → 单元测试
  └─ 防冗余检查：
      已被更低层测试覆盖？→ 降级
      能用集成替代 E2E？→ 降级
```

### 让 AI 可靠遵循的关键

1. **决策树放 prompt 前端**，不用自然语言建议
2. **默认禁 E2E**——AI 选 E2E 必须输出理由，人工确认
3. **要求输出决策路径**——"根据判断 2，选集成测试"
4. **Scoring 机制**——多维度评分，总分决定层级

## 四、E2E 比例控制

### Ice Cream Cone 反模式

E2E 占比最高（或全 E2E）= 慢反馈 + 高 flaky 率 + 难定位失败根因。业界共识：E2E > 30% 即反模式。

### CI 检测脚本

```bash
E2E=$(find tests/ -path '*e2e*' -name '*.spec.*' | wc -l)
TOTAL=$(find tests/ -name '*.test.*' -o -name '*.spec.*' | wc -l)
PCT=$((E2E * 100 / (TOTAL > 0 ? TOTAL : 1)))
[ "$PCT" -gt 15 ] && echo "WARNING: E2E ${PCT}% exceeds 15%" && exit 1
```

### 分层比例建议（UMES3 目标）

| 层 | 当前 | 目标 | 
|----|:--:|:--:|
| E2E | 46（100%） | ~10%（核心路径） |
| 集成 | 0 | ~60%（API + 组件集成） |
| 单元 | 0 | ~30%（纯逻辑 + 工具函数） |

### 渐进路线

- **P0（立即）**：spec 阶段用决策树决定层级，新 ticket 不新增 E2E 原则
- **P1（短期）**：uvu 跑第一个集成测试，裸 PHP assert 跑第一个后端集成
- **P2（中期）**：CI 脚本检测比例，E2E > 30% → warning
- **P3（长期）**：存量 E2E 下沉，硬阻断

## 参考资料

- Kent C. Dodds, Testing Trophy: https://kentcdodds.com/blog/static-vs-unit-vs-integration-vs-e2e-tests
- Kent 2025 Trophy 更新讨论: https://kentcdodds.com/calls/05/02/does-the-testing-trophy-need-updating-for-2025
- uvu test runner (Node 10+): https://github.com/lukeed/uvu
- UK HomeOffice test pyramid standard: https://engineering.homeoffice.gov.uk/standards/test-pyramid/
- BMAD test levels framework: https://gitcode.com/gh_mirrors/bm/BMAD-METHOD/blob/main/bmad-core/data/test-levels-framework.md
- Hack23 testing-strategy-enforcement: https://lobehub.com/skills/hack23-cia-testing-strategy-enforcement
- simpleunit (PHP 5.4+): https://packagist.org/packages/chrisguitarguy/simpleunit
