# LangBot 补丁

本目录存放对 LangBot 框架源码的修改。每次 LangBot 升级后需重新应用。

## 补丁清单

| 补丁 | 目标文件 | 原因 | 上游 |
|------|---------|------|------|
| [process.py](process.py) | `/app/src/langbot/pkg/pipeline/process/process.py` | `str()` 大 message_chain 阻塞事件循环 → WS ping timeout | 待提交 issue |

## 应用

```bash
# 部署单个补丁
ssh root@nas "docker cp patches/process.py langbot:/app/src/langbot/pkg/pipeline/process/process.py"

# 或运行批量脚本
bash apply.sh
```

## 新增补丁步骤

1. 从容器导出原始文件
2. 修改后放到此目录
3. 更新上方清单
4. 运行 apply.sh 部署
