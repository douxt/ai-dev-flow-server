#!/usr/bin/env python3
"""aiocqhttp.py 补丁：Image 组件构造时透传平台 CDN url。

⚠️ 现状：entrypoint 中该调用已注释停用。脚本在 NAS 上长期处于语法坏状态
（2026-08-28 发现并重写），即 url 透传从未生效，vision 全走 base64 路径。
插件 vision.py `_describe_one` 是 url 优先（:93）——启用本补丁会切换 vision
取图路径（CDN 链接过期性/容器网络可达性未验证），启用前需单独测试，勿随手解注释。

幂等：marker 判重；PR 版本（上游自带 url= 透传）自动 skip。
"""
import sys

TARGET = sys.argv[1] if len(sys.argv) > 1 else '/app/src/langbot/pkg/platform/sources/aiocqhttp.py'
MARKER = '[IMAGE-URL-PASS-THROUGH]'

with open(TARGET) as f:
    content = f.read()

if MARKER in content:
    print(f'{MARKER} already applied, skip')
    sys.exit(0)

HUNKS = [
    # process_message_data 内（引用/转发嵌套路径）
    (
        """                image_base64, image_format = await image.qq_image_url_to_base64(msg_data['data']['url'])
                reply_list.append(platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}'))""",
        """                image_base64, image_format = await image.qq_image_url_to_base64(msg_data['data']['url'])
                # [IMAGE-URL-PASS-THROUGH] 透传原 url，供下游按需取图
                reply_list.append(platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}', url=msg_data['data']['url']))""",
    ),
    # 顶层消息 image 分支
    (
        """                    image_base64, image_format = await image.qq_image_url_to_base64(msg.data['url'])
                    image_msg = platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}')""",
        """                    image_base64, image_format = await image.qq_image_url_to_base64(msg.data['url'])
                    # [IMAGE-URL-PASS-THROUGH] 透传原 url，供下游按需取图
                    image_msg = platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}', url=msg.data['url'])""",
    ),
]

# PR 版本检测：两处 Image 构造上游已自带 url= 透传则无需补丁
if "url=msg_data['data']['url']" in content and "url=msg.data['url']" in content:
    print(f'{MARKER} url= already present (PR version), skip')
    sys.exit(0)

for i, (old, _) in enumerate(HUNKS):
    if old not in content:
        print(f'{MARKER} ERROR: hunk{i} anchor not found（上游改版，人工核对）')
        sys.exit(1)

for old, new in HUNKS:
    content = content.replace(old, new, 1)
with open(TARGET, 'w') as f:
    f.write(content)
print(f'{MARKER} applied successfully')
