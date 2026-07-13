#!/bin/bash
# 自动化 Face 识别测试
# 用法: ssh root@nas 'sh /volume1/docker/langbot/test_face.sh'
# 或通过 ssh root@nas 'docker exec langbot-plugin sh ...'

API="http://localhost:3000"
TOKEN="udimc123"
GROUP=1104330614
PASS=0
FAIL=0

send_face() {
    local face_id=$1
    local desc=$2
    local text=${3:-""}
    local msg='[{"type":"face","data":{"id":"'"$face_id"'"}}'
    if [ -n "$text" ]; then
        msg="$msg,{\"type\":\"at\",\"data\":{\"qq\":\"3228649756\"}},{\"type\":\"text\",\"data\":{\"text\":\" $text\"}}"
    fi
    msg="$msg]"
    curl -s -X POST "$API/send_group_msg?access_token=$TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"group_id\":$GROUP,\"message\":$msg}" | grep -q '"status":"ok"' && echo "  [OK] 发送 face_id=$face_id ($desc)" || echo "  [FAIL] 发送 face_id=$face_id"
}

echo "=== Face 识别自动化测试 ==="
echo ""

# 测试1: 单独表情
echo "--- 测试1: 单独表情 face_id=178 (斜眼笑) ---"
send_face 178 "斜眼笑"

# 测试2: 单独表情
echo "--- 测试2: 单独表情 face_id=264 (捂脸) ---"
send_face 264 "捂脸"

# 测试3: 表情+@bot+文本
echo "--- 测试3: 表情+@bot face_id=178 + 文本 ---"
send_face 178 "斜眼笑" " 这个表情是什么？"

# 测试4: 混合表情
echo "--- 测试4: 混合表情 face_id=3 (发呆) ---"
send_face 3 "发呆"

echo ""
echo "等待 bot 响应 (15s)..."
sleep 15
echo ""

echo "=== 验证结果 ==="
echo "检查 chat_index 中最近存储的消息格式..."
echo "预期: [QQ表情:斜眼笑] 或 [QQ表情:捂脸] 而非 [Unknown]"
echo ""
echo "请检查测试群 bot 的回复内容，确认 bot 提到了表情名称。"
