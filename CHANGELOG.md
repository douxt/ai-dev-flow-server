# ai-dev-flow-server v2.0 变更说明

> 发布日期：2026-06-30  
> 变更范围：`install.sh` / `uninstall.sh` 通用化 + 离线 skill 缓存 + 测试套件

## 一句话总结

install.sh 从硬编码 openlobby 服务器专用 → **环境自适应 + 三种部署模式**的通用安装器，一套脚本适配裸机 / VPS / Docker 容器 / WSL2。

---

## 新增功能

### 1. 三种部署模式（`--mode`）

```bash
bash install.sh <项目路径> --mode frontend   # 仅装开发工具链（gate/skills/config）
bash install.sh <项目路径> --mode backend    # 仅装调度管线（archon/scripts/调度器）
bash install.sh <项目路径> --mode full       # 全装（默认）
```

| 组件 | frontend | backend | full |
|------|:--------:|:-------:|:----:|
| gate 脚本（6 个） | ✅ | — | ✅ |
| gate skills（7 个） | ✅ | — | ✅ |
| gate-checklists（6 个） | ✅ | — | ✅ |
| CC skills（15 个） | ✅ 默认 | — | ✅ 默认 |
| settings + hooks + CLAUDE.md | ✅ 默认 | — | ✅ 默认 |
| .devflow/config.yaml | ✅ 简化版 | ✅ | ✅ |
| knowledge/（7 份知识文档） | ✅ | ✅ | ✅ |
| archon/（调度管线） | — | ✅ | ✅ |
| scripts/（检查脚本） | — | ✅ | ✅ |
| 调度器配置（root 段） | — | ✅ | ✅ |
| .gate-state | ✅ | — | ✅ |
| git hooks | ✅ | ✅ | ✅ |

### 2. 四种调度器（`--scheduler`）

| 值 | 输出内容 |
|----|---------|
| `systemd` | service + timer unit |
| `cron` | crontab 条目（`--user` 指定运行用户） |
| `external` | 提示文本（宿主机配置 `docker exec ...`） |
| `none` | 不输出（前端默认） |

不指定 `--scheduler` 时自动检测：Docker → none，有 systemd → systemd，有 crontab → cron。

### 3. 环境自适应

- 自动检测 Docker / systemd / cron 环境
- Docker 内自动创建 `~/.claude → ~/.config/claude` symlink（持久化）
- `--home <path>` 覆盖 `$HOME`（Docker 内 coder 用户路径与宿主机不同时使用）

### 4. 增量更新（`--update`）

```bash
bash install.sh <项目> --update          # 读取 .devflow/config.yaml 的 mode，只更新已有文件
bash install.sh <项目> --force --update  # 强制覆盖（config 模板更新后刷新 hook 等）
```

`--update` 不影响 `.gate-state` 和 `config.yaml` 的 mode 字段。

### 5. 预览与强制模式

| 参数 | 行为 |
|------|------|
| `--dry-run` | 只打印每步将做什么，不实际写入 |
| `--force` | 覆盖已有文件（**永不覆盖 `.gate-state`**） |
| `--no-config` | 跳过 settings + hooks + CLAUDE.md |
| `--no-skills` | 跳过 CC skill 安装 |
| `--skip-root` | 跳过 root 段调度器输出 |

### 6. 离线 skill 缓存（`skills-cache/`）

15 个 CC skill 纳入 git 管理，安装时不依赖网络。附带 `.version` 版本文件和 `sync-skills.sh` 同步脚本。

### 7. 自动化测试套件（`tests/`）

17 个 bats-core 测试文件，60 个用例，Docker 容器内运行：

```bash
bash tests/run_tests.sh              # Alpine + Ubuntu 双发行版
bash tests/run_tests.sh -f "update"  # 过滤单个测试
```

---

## 变更文件清单

| 文件 | 改动 | 说明 |
|------|:----:|------|
| `install.sh` | 重写 | +881/-270 行，新增 CLI 参数、环境检测、mode 条件化 |
| `uninstall.sh` | 新增 | 按 mode 反向清理，支持 `--dry-run`/`--force` |
| `config-templates/default/` | 新增 | settings.json 模板 + 4 个 hook + CLAUDE.md |
| `skills-cache/` | 新增 | 15 个 CC skill，git tracked |
| `templates/pre-commit` | 修改 | 新增 install.sh/uninstall.sh 保护 |
| `tests/` | 新增 | 17 文件 60 用例，Docker 测试框架 |

---

## 兼容性

**向前兼容**：旧的 `bash install.sh <路径> --tech-stack python` 用法不变，效果等同于 `--mode full --scheduler systemd`。

**新增参数**：`--mode`、`--home`、`--user`、`--scheduler`、`--no-config`、`--no-skills`、`--skip-root`、`--dry-run`、`--force`、`--update`。

---

## 典型场景

### 场景 1：本地开发机

```bash
git clone https://github.com/douxt/ai-dev-flow-server.git /tmp/devflow
bash /tmp/devflow/install.sh ~/my-project --mode frontend
```

### 场景 2：NAS / Docker 容器

```bash
# 容器内（coder 用户，$HOME=/home/coder）
bash install.sh ~/project/MAF-Hub --mode frontend --home /home/coder
```

### 场景 3：VPS 后端节点

```bash
bash install.sh /opt/my-project --mode backend --scheduler cron --user www
```

### 场景 4：预览变更

```bash
bash install.sh ~/my-project --mode full --dry-run
```

### 场景 5：升级已有安装

```bash
cd /opt/ai-dev-flow-server && git pull    # 先更新安装器本身
bash install.sh ~/my-project --update      # 只更新已有组件的文件
```

### 场景 6：卸载

```bash
bash uninstall.sh ~/my-project --mode full --force
bash uninstall.sh ~/my-project --mode frontend --dry-run  # 先预览
```

---

## 注意事项

1. **`.gate-state` 永不覆盖**：`--force` 也不会覆盖，防止丢失 Gate 进度
2. **`--update` 只更新已有文件**：不会引入新模式的文件。如需切换模式，用完整安装命令
3. **Docker 持久化**：容器内自动创建 `~/.claude → ~/.config/claude` symlink。确保 `~/.config` 挂载了持久卷
4. **CC skills 离线缓存**：版本跟随 repo。定期运行 `skills-cache/sync-skills.sh` 同步最新 skill
5. **首次使用**：安装后检查 `.devflow/config.yaml`，填写 telegram 配置（如需通知功能）
