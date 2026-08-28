#!/bin/sh
# 启动前打 patch（幂等，已打则跳过）
python3 /patches/patch_mcp_timeout.py
# 停用：url 透传会切换 vision 取图路径（url 优先，从未实际启用过），单独验证后再放开
# python3 /patches/patch_image_url.py
python3 /patches/patch_event_loop_blocks.py
python3 /patches/patch_forward_speaker.py
# 执行原命令
exec "$@"
