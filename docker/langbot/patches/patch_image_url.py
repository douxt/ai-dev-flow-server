#!/usr/bin/env python3
"""Monkey-patch aiocqhttp.py: 构造 Image 时同时传入 url，保留原始平台 CDN URL"""
import sys

TARGET = '/app/src/langbot/pkg/platform/sources/aiocqhttp.py'
MARKER = '[IMAGE-URL-PASS-THROUGH]'

with open(TARGET) as f:
    content = f.read()

if MARKER in content:
    print(f'{MARKER} already applied, skip')
    sys.exit(0)

# L242-243: reply 消息中的 Image 构造
old1 = """                image_base64, image_format = await image.qq_image_url_to_base64(msg_data['data']['url'])
                reply_list.append(platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}'))"""

new1 = """                image_base64, image_format = await image.qq_image_url_to_base64(msg_data['data']['url'])
                reply_list.append(platform_message.Image(url=msg_data['data']['url'], base64=f'data:image/{image_format};base64,{image_base64}'))  # [IMAGE-URL-PASS-THROUGH]"""

# L287-288: 普通消息中的 Image 构造
old2 = """                    image_base64, image_format = await image.qq_image_url_to_base64(msg.data['url'])
                    image_msg = platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}')"""

new2 = """                    image_base64, image_format = await image.qq_image_url_to_base64(msg.data['url'])
                    image_msg = platform_message.Image(url=msg.data['url'], base64=f'data:image/{image_format};base64,{image_base64}')  # [IMAGE-URL-PASS-THROUGH]"""

for old, new, label in [(old1, new1, 'L242'), (old2, new2, 'L287')]:
    if old not in content:
        print(f'{MARKER} ERROR: target line {label} not found in {TARGET}')
        sys.exit(1)
    content = content.replace(old, new, 1)

with open(TARGET, 'w') as f:
    f.write(content)

print(f'{MARKER} applied successfully')
