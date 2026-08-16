# Vue 3 + TS 项目模式

> 技术栈模块 — 按 `tags: node` 部署（Vue 项目）。
> 来源：go-vue-scaffold 最佳实践调研（2026-08），通用部分萃取。

## 目录约定

```
src/
├── api/          # 唯一 API 出口：request.ts 封装 + 业务模块；组件/页面禁止直接 import axios
├── components/   # 可复用组件（无 API 调用、无 store 访问，纯 props/emits）
├── views/        # 页面级组件（路由）
├── composables/  # useXxx 组合函数
├── stores/       # Pinia
├── router/
├── types/        # 全局 TS 类型（契约生成物放这里）
├── utils/
└── styles/
```

## 组件写法

- 全部 `<script setup lang="ts">`
- props：`withDefaults(defineProps<T>(), {...})`；`defineEmits<T>()` 类型化；Vue 3.4+ 用 `defineModel()`
- 组件 >250 行拆分或抽 composable
- 组合函数：`use` 前缀、副作用在 `onUnmounted` 清理、无模块级副作用
- 容器/展示组件分离：容器管数据获取与副作用，展示组件只收 props 发 emits
- 弹窗/抽屉用 `<Teleport to="body">` 防样式污染
- 路由懒加载 + `RouteMeta` 类型扩展（`requiresAuth`、`title`）；守卫只做前端 UX，**真实鉴权永远在后端**

## Pinia 约定

- 用 **setup store** 写法（与 Composition API 心智一致）
- 异步操作（API 调用）放 actions，组件里不裸调 API
- 状态修改一律走 action；`$patch` 只用于 store 内部批量更新
- 状态选型：局部状态 `ref` → 父子 props/emits → provide/inject → Pinia → 服务端数据用带缓存的 composable
- 每个异步 action 处理 loading/成功/失败三态

## API 层

- axios 实例：`baseURL` 走 `import.meta.env`、超时 10~15s
- 请求拦截器注入 token；响应拦截器按业务 code 分支：0 放行、401 清 store 跳登录、403 提示、网络错误统一提示
- 拦截器只做横切（token/错误归一），业务解包在模块函数里做
- 路由切换时取消进行中请求（AbortController）

## 前端安全

- `{{ }}` 插值默认转义，**唯一逃逸口是 `v-html`**——任何 `v-html` 都要安全评审；用户可控内容渲染 HTML 必须过 DOMPurify（或 Sanitizer API）
- CSP：`default-src 'self'` 起步，避免 `unsafe-inline/unsafe-eval`；`frame-ancestors 'none'` 防点击劫持；先 Report-Only 观察再收紧
- 依赖供应链：提交 lockfile、`npm ci` 安装、CI 跑 `npm audit` 门禁、升级漏洞依赖不拖延
- 秘密禁止进前端：一切 `VITE_*` 都等于公开
- 生产禁用 sourcemap；第三方 CDN 脚本加 SRI

## 认证共识（2025-2026）

JWT 不放 localStorage（XSS 可窃取），改用 **HttpOnly Cookie + 双 token**：

| 方案 | 结论 |
|------|------|
| localStorage | ❌ XSS 一键偷走 refresh token |
| **HttpOnly Cookie** | ✅ `HttpOnly + Secure + SameSite=Lax`；access token 短效（5~15min），refresh token 放 cookie（7~30 天） |

- Cookie 方案必须配 CSRF 防御：`SameSite=Lax` + 状态变更请求带 CSRF token（double-submit cookie）或 Origin 校验
- refresh token 每次使用即轮换 + 旧 token 服务端黑名单
