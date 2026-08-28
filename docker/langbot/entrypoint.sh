#!/bin/sh
# 启动前打 patch（幂等，已打则跳过）
python3 /patches/patch_mcp_timeout.py
python3 /patches/patch_image_url.py
python3 /patches/patch_event_loop_blocks.py
python3 /patches/patch_forward_speaker.py
# 执行原命令
exec "$@"
