# bash-firewall 误拦截分析报告

@author: Claude
@created: 2026-06-23
@status: 待开发者处理

---

## 一、现象

连续两次 `Bash` 命令被 bash-firewall 拦截，输出如下：

```
╔══════════════════════════════════════════════════╗
║  bash-firewall：拦截非 worktree 文件写入         ║
╠══════════════════════════════════════════════════╣
║  ▸ /home/dou/dev/MAF-Hub/&1
║  ▸ /home/dou/dev/MAF-Hub/&1
║  ▸ /home/dou/dev/MAF-Hub/&1
╠══════════════════════════════════════════════════╣
║  请先 wt create 创建隔离分支                      ║
╚══════════════════════════════════════════════════╝
```

被拦截的命令：

1. `uv add pymupdf 2>&1 | tail -3`
2. `/tmp/invoice-venv/bin/python3 -c "..." 2>&1 || (cd /tmp && uv venv ... 2>&1 && pip install ... 2>&1 | tail -3)`

这两条命令目标路径都在 `/tmp`，不涉及受保护仓库的任何文件。

---

## 二、根因分析

### 2.1 触发链路

```
Bash 命令含 2>&1
  → extract_target_files 正则匹配 2>&1
    → sed 剥离前缀后剩余 &1
      → resolve_relative_path(&1, /home/dou/dev/MAF-Hub) → /home/dou/dev/MAF-Hub/&1
        → is_protected_repo 命中
          → is_in_worktree 未命中
            → BLOCKED
```

### 2.2 缺陷代码

文件：`~/.claude/hooks/common.sh`，`extract_target_files()` 函数。

**问题 1（核心）— 重定向正则未排除 fd 复制语法**

```bash
# common.sh 第 64 行
redirects=$(echo "$cmd" | grep -oP '[12&]?>>?(?:\s*\S+)' ...)
```

`[12&]?>>?(?:\s*\S+)` 含义：
- `[12&]?` — 可选的 fd 编号（1、2、&）
- `>>?` — > 或 >>
- `(?:\s*\S+)` — 可选空格 + 目标

此正则匹配 `2>&1` 时：
- `2` 匹配 `[12&]?`
- `>` 匹配 `>>?`
- `&1` 匹配 `(?:\s*\S+)`

**问题 2 — 提取后未校验目标是否为 fd**

```bash
# common.sh 第 67-69 行
file=$(echo "$token" | sed -E 's/^[12&]?>>?\s*//; s/\s.*$//')
# 此时 file = "&1"
[ -n "$file" ] && results+=("$file")   # 未过滤 &\d
```

`&1` 不是文件路径，是"复制 fd 到 stdout"的 shell 语法。sed 剥离 `2>` 后残留 `&1`，直接进入 results 数组。

**问题 3 — 相对路径解析未处理特殊字符**

```bash
# common.sh 第 46-53 行
resolve_relative_path() {
  ...
  *) echo "${cwd%/}/${path}" ;;   # &1 不匹配 / 或 ~，走此分支
}
```

`&1` 被当作相对路径拼上 CWD，产出一个看似在仓库内的伪路径。

### 2.3 受影响的所有误拦截模式

| Shell 语法 | 含义 | 被误判为 | 常见度 |
|------------|------|----------|:---:|
| `2>&1` | stderr → stdout | 写文件 `&1` | ⭐⭐⭐⭐⭐ |
| `1>&2` | stdout → stderr | 写文件 `&2` | ⭐⭐⭐ |
| `>&2` | stdout → stderr | 写文件 `&2` | ⭐⭐ |
| `2>&-` | 关闭 stderr | 写文件 `&-` | ⭐ |
| `0<&-` | 关闭 stdin | 不触发（正则只匹配 >） | — |

### 2.4 次要问题

`cp`/`mv` 目标提取过于粗糙（第 94-103 行）：

```bash
dst=$(echo "$cmd" | awk '{print $NF}')  # 取最后一个词
```

管道命令的最后一个词不一定是文件路径，例如：
- `cp a b && echo done` → 取到 `done`（无害，`done` 不在仓库内）
- 但配合 `&&`、`||` 等，`$NF` 可能意外匹配其他内容

此问题暂未观察到实际误拦截，但属于不可靠实现。

---

## 三、推荐修复方案

### 方案 A（最小改动，推荐）：提取后加 fd 过滤

**修改文件：** `~/.claude/hooks/common.sh`
**修改函数：** `extract_target_files()`
**位置：** 第 69 行之前

```bash
# 第 68 行之后插入：
# 排除 fd 复制/关闭语法（2>&1, 1>&2, >&2, 2>&-）
case "$file" in
  '&'[0-9] | '&'[0-9][0-9] | '&-') continue ;;
esac
[ -n "$file" ] && results+=("$file")
```

**改动量：** +2 行，无侵入，不改变现有逻辑。

### 方案 B（更彻底）：重写重定向解析

将当前的一条笼统正则替换为两条精确正则：

```bash
# 1. 文件重定向：>file, >>file, 1>file, 2>file, &>file（目标不以 & 开头）
#    注意：&>word 在 bash 中是 stdout+stderr 都写入 word
file_redirects=$(echo "$cmd" | grep -oP '(?:^|\s)[12&]?>>?\s*[^&\s/][^\s]*' 2>/dev/null || true)

# 2. &>file 格式（单独处理，避免歧义）
both_redirects=$(echo "$cmd" | grep -oP '(?:^|\s)&>>?\s*[^&\s][^\s]*' 2>/dev/null || true)
```

此方案改动较大，需充分测试。建议先实施方案 A，观察效果后再考虑方案 B。

### 方案 C（防御层）：在 resolve_relative_path 加合理性校验

```bash
resolve_relative_path() {
  local path="$1" cwd="${2:-$PWD}"
  # 新增：非法路径字符检测
  case "$path" in
    *'&'*) return 1 ;;   # & 不是合法文件名字符
  esac
  case "$path" in
    /*) echo "$path" ;;
    ~*) echo "${HOME}${path:1}" ;;
    *) echo "${cwd%/}/${path}" ;;
  esac
}
```

此方案不能单独解决问题（firewall 需要配合上层过滤），但作为防御层可防止类似问题再次出现。

---

## 四、建议实施优先级

| 优先级 | 动作 | 位置 |
|:---:|---|------|
| P0 | 方案 A：`&\d` / `&-` 过滤 | `extract_target_files` 第 68 行后 |
| P1 | 方案 C：非法字符防御 | `resolve_relative_path` 入口 |
| P2 | 正则拆分（方案 B） | 长期优化，需回归测试 |
| P2 | `cp`/`mv` 的 `$NF` 改为更可靠的目标提取 | `extract_target_files` 底部 |

---

## 五、验证方法

修复后，以下命令应全部通过（不被拦截）：

```bash
# 1. fd 复制
echo "test" 2>&1

# 2. 管道中的 fd 复制
python3 -c "print(1)" 2>&1 | tail -3

# 3. 关闭 fd
some_cmd 2>&-

# 4. 多实例
cmd1 2>&1 || cmd2 2>&1 && cmd3 2>&1
```

以下命令应继续被拦截：

```bash
# 真正的文件写入
echo "data" > /home/dou/dev/MAF-Hub/some_file.txt
tee /home/dou/dev/MAF-Hub/output.log
```
