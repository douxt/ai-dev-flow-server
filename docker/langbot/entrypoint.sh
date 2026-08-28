#!/bin/sh
# 启动前打 patch（幂等，已打则跳过）
python3 /patches/patch_mcp_timeout.py
# 启用（2026-08-28）：Image 构造透传 QQ CDN url，插件 vision URL-first 直传模型免上传；url 失败自动回退 base64
python3 /patches/patch_image_url.py
python3 /patches/patch_event_loop_blocks.py
python3 /patches/patch_forward_speaker.py
# 执行原命令
exec "$@"
