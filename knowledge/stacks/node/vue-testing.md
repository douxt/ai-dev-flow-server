# Vue 组件测试（Vitest + @vue/test-utils）

> 技术栈模块 — 按 `tags: node` 部署（Vue 项目）。
> 门禁联动：test-gate.sh C0.5 Vitest 分支、g0-inject.sh vitest runner

## 基础模式

```ts
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import UserCard from '@/components/UserCard.vue'

describe('UserCard', () => {
  it('渲染用户名', () => {
    const wrapper = mount(UserCard, { props: { name: 'Alice' } })
    expect(wrapper.text()).toContain('Alice')
  })

  it('emit 删除事件', async () => {
    const wrapper = mount(UserCard)
    await wrapper.find('button.del').trigger('click')
    expect(wrapper.emitted('delete')).toBeTruthy()
    // 强断言优于存在断言——emit 的 payload 也要验：
    expect(wrapper.emitted('delete')?.[0]).toEqual(['1'])
  })
})
```

## Mock 策略

- **Pinia**：`createTestingPinia()`（官方测试工具）或 setup store 直接注入初始 state
- **axios**：`vi.mock('@/api/request')` 模块级 mock——组件只依赖 api 层出口，mock 一个文件即可
- **Router**：`createRouter(createMemoryHistory())` 内存路由；或 `global.plugins` 挂测试 router
- 子组件：`shallowMount` 或 `global.stubs` 替换重组件（Element Plus 弹窗/表格常需 stub）

## 断言原则（与 ASI 一致）

| 弱（避免） | 强（优先） |
|------|------|
| `expect(wrapper.exists()).toBe(true)` | `expect(wrapper.text()).toContain('具体文案')` |
| `expect(fn).toHaveBeenCalled()` | `expect(fn).toHaveBeenCalledWith(具体参数)` |
| 只断言 DOM 结构 | 断言用户可见行为（文本/角色/URL） |

## Element Plus 常见坑

- 异步组件（Message/MessageBox）用 `vi.mock('element-plus')` 或用真实挂载 + `flushPromises`
- 弹窗内容在 `Teleport` 里——测试需 `document.body` 查询或配置 `attachTo`
- 表格/分页组件复杂交互优先走 E2E，单测只验数据流

## 门禁行为说明

- test-gate.sh：C0.2 恒真断言（toBeTruthy/toBeDefined）对 `.test.ts` 生效；C0.8 弱断言占比同扫
- g0-inject.sh：vitest runner，`npx --prefix frontend vitest run`；注入策略 1-5（JS/TS 模式）适用
- 测试文件命名 `.test.ts` / `.spec.ts`——G2.1 会拦 GREEN 阶段修改测试文件
