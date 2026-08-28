#!/usr/bin/env python3
"""Monkey-patch aiocqhttp.py: 构造 Image 时同时传入 url，保留原始平台 CDN URL"""
import sys

TARGET = "/app/src/langbot/pkg/platform/sources/aiocqhttp.py"
MARKER = "[IMAGE-URL-PASS-THROUGH]"

with open(TARGET) as f:
    content = f.read()

if MARKER in content:
    print(f"{MARKER} already applied (marker), skip")
    sys.exit(0)

# 检测 PR 版本：url= 已经存在即为已修复，无需 patch
if "url=msg_data[" in content and "url=msg.data[" in content:
    print(f"{MARKER} url= already present (PR version), skip")
    sys.exit(0)

# L242-243: reply 消息中的 Image 构造
old1 = """                image_base64, image_format = await image.qq_image_url_to_base64(msg_data[\\data\][\\url\])
                reply_list.append(platform_message.Image(base64=f\\data:image/{image_format}
