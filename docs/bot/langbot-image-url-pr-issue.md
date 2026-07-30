# Issue: 平台适配器应透传图片原始 URL 至 Image 组件

> **标题**: `[Feature]: 平台适配器构造 Image 时同时传入 url 字段`
> **类型**: 现有功能优化
> **模板**: feature-request.yml

## 问题描述

当前大部分平台适配器在处理接收到的图片消息时，会先调用下载函数将平台图片 URL 下载并转为 base64，然后**仅设置 `Image.base64`，丢弃了原始 URL**。

以 aiocqhttp.py 为例（telegram/discord/lark/slack/wecom/qqofficial 均相同）：

```python
# aiocqhttp.py L242-243, L287-288
image_base64, image_format = await image.qq_image_url_to_base64(msg.data['url'])
platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}')
#                      ↑ url 字段未设置，原始 QQ CDN URL 被丢弃
```

唯一例外是 **Satori adapter**（satori.py:168），它已正确透传 url：

```python
components.append(platform_message.Image(url=img_url))
```

## 影响

### 1. 插件无法利用 URL 直传，被迫重复下载

LangBot SDK 已提供 `ContentElement.from_image_url()`，允许 vision 模型直接从 CDN URL 读取图片（服务端下载）。但因为 `Image.url` 为空，插件只能走 `get_bytes()` → 重新下载 → base64 编码 → `from_image_base64()` 的绕路流程：

```
当前链路：
QQ CDN → adapter 下载(第1次) → base64 → WS 传输(~150KB) → 插件 get_bytes() 下载(第2次) → vision API

理想链路：
QQ CDN → adapter 提取 url → WS 传输(~200B) → 插件 from_image_url() → vision API
```

**同一张图片被下载了 2 次**，其中插件侧的那次完全是浪费。

### 2. WebSocket 消息体膨胀

base64 编码使数据量膨胀 ~33%。单张普通图片 ~100-200KB base64，在引用/合并转发场景下嵌套图片可达 MB 级，导致 WS 消息处理延迟 45s+（见 commit 95d684c）。

透传 URL 后，图片数据从 ~150KB base64 降为 ~200B URL 字符串，**缩小约 750 倍**。

### 3. 插件被迫做 workaround

silent-observer 插件为了 vision 能工作不得不保留顶层 Image 的 base64（否则 `get_bytes()` 三字段全空报错），只能分层 strip（顶层保留、嵌套清除）。这是对 adapter 缺陷的补偿逻辑，不应由插件承担。

## 推荐方案

所有平台适配器在构造 `Image` 时，**同时传入 `url` 和 `base64`**：

```python
platform_message.Image(
    url=msg.data['url'],     # 透传原始平台 CDN URL
    base64=f'data:image/{image_format};base64,{image_base64}',  # 保留兼容
)
```

### 为什么是加法而非替换

- 仅新增 `url` 字段，不删除 `base64`——**零破坏性**
- SDK 的 `get_bytes()` 逻辑是 `url → base64 → path` 优先级链，url 有值会自动走 HTTP 下载
- 旧插件仍依赖 base64 工作，不受影响
- 新插件可选择 `from_image_url()` 获得零下载体验

### 涉及文件

| 文件 | 改动 |
|------|------|
| `aiocqhttp.py` L242, L287 | +`url=` |
| `telegram.py` L102 | +`url=` |
| `discord.py` L783 | +`url=` |
| `lark.py` L466 | +`url=` |
| `slack.py` L50 | +`url=` |
| `wecom.py` L136 | +`url=` |
| `qqofficial.py` L99 | +`url=` |

总计约 **10 行改动**，每个 adapter 在已有 `base64=` 前加一个 `url=` 参数。

### 参考

Satori adapter 已经是正确实现，可作为其他 adapter 的参考模板。

## 收益

| 维度 | 当前 | 改进后 |
|------|------|--------|
| 图片下载次数 | 2 次（adapter + 插件） | 0 次（vision API 服务端直读 CDN） |
| WS 单图传输 | ~150KB (base64) | ~200B (url) |
| 引用/转发含图片 | MB 级，可能阻塞 45s+ | 不受图片数量影响 |
| 插件处理延迟 | 下载 + resize + b64encode | 一行 `from_image_url()` |
| 插件 workaround 代码 | 分层 strip_base64 逻辑 | 可彻底移除 |

## 实证验证

已在生产环境（LangBot v4.10.5 + NapCat QQ）通过 entrypoint patch 方式对 `aiocqhttp.py` 应用此改动，silent-observer 插件同步改为优先 `from_image_url()`。运行 4 小时+，结果：

```
vision: img[1] url_ok lat=18.2s desc="夜晚，从车内后座视角看去..."
vision: img[4] url_ok lat=22.6s desc="桌面上摆放着机械键盘、游戏手柄..."
vision: img[7] url_ok lat=16.7s desc="拼多多0.80元转账入账截图"
vision: img[11] url_ok lat=13.5s desc="评价领奖励页面..."
vision: img[13] url_ok lat=20.2s desc="金发Q版卡通女孩..."
vision: img[17] url_ok lat=41.9s desc="绝区零官方徽章商品页面"
```

- **url_ok 占比**：100%（无 fallback 到 base64）
- **零本地下载**：`get_bytes()` 被完全跳过
- **零 resize/b64encode**：图片处理管线完全绕过
- **WS 传输**：Image 组件的 base64 可安全清除，降为纯 url ~200B
- **稳定性**：无异常，vision API（通义千问）正常从 QQ CDN 读取图片

## 环境

- LangBot 版本: v4.10.5
- 平台: NapCat QQ (OneBot v11)
- 影响范围: 所有使用 `Image` 组件的插件
