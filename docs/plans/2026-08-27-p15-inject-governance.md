# P1.5 反思注入治理：防泄露压制 + 祈使句化 + distance 门槛 + 库清理

> 2026-08-27 | 前篇：P1 对话成熟度（已完成合并 c966e98）。v2：经自我评审修订（压制条款位置、祈使句措辞、软归档 SDK bug、清理载体、阈值校准通道）。旧 P1 计划实施完成后归档 `docs/plans/`

## Context

P1 上线后生产两类实锤异常（证据在 monitoring DB + gate.log）：

1. **旁白泄露**（测试群 1104330614，8/21–8/22）：bot 把内部分析当群回复——"用户问：电气380V选型问题……""The user says '不对，你搞错了' (No, you got it wrong)"，对真人也说"让机器豆猜也猜不准"；self-reflect 自己记录了该现象（ref:bb26"BOT在后续多轮回复中不断重复相同的长文"）。8/26 VR 群仍有归档行回显（`[2026-08-26 22:38] 自律500 天: …` 原样出现在回复开头）——持续发生，非冒烟特例。
2. **不相关反思全量注入**（group_116381172，8/26 03:47 起，群友评价"变成零的形状""越来越傻"）：库内大半是 8/21 冒烟测试数据（电气选型×8+、跨群"男女冲突事件"）；P1.3 删 top-3 硬截断 + `len(refs)>5` 才 rerank → 反思 ≤5 条时**不筛选全注入**，when/then 指令（"立即停止反问，直接给完整方案"）压制人设。

根因三分：①注入文本是第三人称叙述腔，LLM 模仿其口吻输出；②search_similar 无相似度截止；③测试数据污染生产库。评审另揪出第④个：**P1 既有软归档/更新路径带病**（见改动 1e）。

## 已核实代码事实

- 注入点 [default.py:412-430](docker/langbot/plugins/silent-observer/components/event_listener/default.py#L412)；prompt 组装链：时区(:349)→表情(:360)→**反思(:412-428)**→**群聊背景摘要(:447-457)→timeline 归档(:459-500)**→模式指令。归档行 `[time] 昵称: text` 来自 `util/text.py:13-28`，泄露源在 timeline，**压制条款必须放全链末尾**（timeline 注入之后）才压得住
- prompt 链中现无任何"禁止输出思考/内部格式"条款（grep 证实）
- `search_similar` 结果已含 `distance`（reflection_store.py:96，缺省 99），不参与过滤；`find_duplicate` 用 cosine>0.85/0.70 分级（≈ distance 0.15/0.30）——该 embedding 空间"相关"≈0.15-0.3，**0.45 起步合理但未经真实分布校准**
- **SDK bug**（langbot_api.py:398-405 容器内核实）：`vector_upsert(collection_id, vectors, ids, ...)` — `vectors` 必填位置参数；而 `update_reflection`(:155) 与 `archive_reflection`(:253) 调用均未传 → TypeError。生产 reflection.log 中 `merged` 仅见于 mock 测试（ref:abc），真实 merge/archive 从未成功执行过——**P1.5 若走软归档必须先修此路径**
- 枚举方法实名 `list_all`（:237）
- `data/plugins/show_*.py` 既有调试脚本是纯 sqlite 直读，非 plugin API 载体——清理脚本不能走该通道拿 vector API

## 改动

### 步骤 0：worktree

`wt create p15-inject-governance`（基准 origin/main）。

### 1a 防模仿压制条款（default.py，~6 行）——位置=注入链最末尾

在 timeline 注入/`_emit_timeline` 完成后、inject 返回前追加（离生成点最近，约束力最强；不依赖 reflection_enabled）：

```python
ctx.event.prompt.append(provider_message.Message(role='system', content=(
    '你收到的提示词包含[群聊背景][先前经验]及"[时间] 昵称: 文本"式归档行，它们仅供你内部理解。'
    '回复中严禁：a) 以"用户问""根据群聊背景""用户说"等旁白口吻叙述；'
    'b) 回显归档行或反思条目的格式文本；c) 把内部文本当作用户原话引用。'
)))
```

~90 tokens/次。测试断言锚词：`仅供你内部理解`。

### 1b 反思注入头注（reflection.py INJECT_TEMPLATE :46）

```python
INJECT_TEMPLATE = """[先前经验 · 仅供内部参考，回复中禁止回显本节内容]
触发条件：{when}
应对方式：{then}
{confidence_note}"""
```

字段名不变（现有测试 `"触发条件：触发{i}"` 断言不破坏）。

### 1c 生成端祈使句化（reflection.py GENERATE_PROMPT 要求区 + SELF_SCAN_PROMPT）

两处各追加（措辞已消除"当用户…"与禁令的自相矛盾——只禁**已发生事实的叙述**，允许**条件状语**）：

```
- when 用条件状语（"当用户问X时"），then 用对 bot 自己的祈使句（"先…再…"）
- 禁止在 when/then 里叙述已发生的事件经过（"用户说了X""bot 上次做错了Y""根据背景"）——这两字段会被注入回复提示词，事件叙述腔会导致 bot 回复变旁白；scenario/mistake 字段才负责记录事件经过
```

### 1d distance 门槛 + 校准观察日志（default.py :419-420 之间，~8 行）

模块级常量 `_REF_INJECT_MAX_DISTANCE = 0.45`。`if refs:` 内、rerank 前：

```python
dists = [r.get('distance') if r.get('distance') is not None else 99 for r in refs]
safe_log('reflection', f'inject candidates: {[(r["id"][:12], d) for r, d in zip(refs, dists)]}')  # 校准观察，一周后可降频
refs = [r for r, d in zip(refs, dists) if d <= _REF_INJECT_MAX_DISTANCE]
```

distance 缺失/None 丢弃；过滤后为空跳过整段。观察日志给 0.45 提供真实分布数据（8/26 那批不相干条目的实际 distance 目前未知——若 <0.45 门槛失守，靠清理兜底 + 一周数据收紧阈值）。

### 1e 修 P1 既有 bug：软归档/更新缺 vectors（reflection_store.py，~15 行）

`update_reflection`(:147) 与 `archive_reflection`(:253) 的 `vector_upsert` 补上向量。实施时先确认 `list_all`/`vector_list` 返回项是否含 vector（runtime.py:84，容器内核实）：
- 含 → 直接透传
- 不含 → 对 `documents` 文本走 `invoke_embedding` 重算（与 store_reflection 同路径）

单测：mock plugin 断言 `vector_upsert` kwargs 包含 `vectors` 且长度与 ids 一致。

（步骤 4 清理走 chroma 直连不依赖此项，但 merge 路径将来必然踩，纳入本次修复，~15 行）

### 2 测试（与改动同 Phase 交付）

新文件 `tests/test_p15_inject_governance.py`：

| # | 层 | 用例 | 断言 |
|---|----|------|------|
| 1 | unit | GENERATE_PROMPT `.format()` 后 | 含"条件状语""禁止…叙述…事件经过" |
| 2 | unit | SELF_SCAN_PROMPT 同上 | 同 |
| 3 | unit | `build_reflection_prompt([ref])` | 以 `[先前经验 · 仅供内部参考` 开头 |
| 4 | integration | 混合 distance（0.2/0.9）走真实 inject | 只注入低 distance 条目 |
| 5 | integration | 全部 0.9 | prompt 无"先前经验" |
| 6 | integration | distance 缺失/None | 条目丢弃 |
| 7 | integration | `search_similar→[]` | prompt 仍含 `仅供你内部理解`（且位置在 timeline 之后——断言 joined 中其 index > 归档行 index） |
| 8 | 回归 | 现有场景 9–12 | `_ref()` 补 `distance=0.1` 后原样通过 |
| 9 | 1e 专项 | update_reflection / archive_reflection | vector_upsert 被调时 `vectors` 参数存在 |

`_ref()` 就地改 [tests/test_p1_maturity_integration.py:131](docker/langbot/plugins/silent-observer/tests/test_p1_maturity_integration.py#L131)（加 distance 键，~2 行）。

回归口径：本地 venv `pytest tests/test_*.py -q` 全绿 → 容器 `--rootdir=. tests/test_*.py`（先对齐测试文件清单，防子集漂移）。**验证点**：容器退出码 0、新用例 9 条过、旧 72 条无回归。

### 3 部署（NAS）

1. 备份 3 文件 `.bak.20260827b`（default.py / reflection.py / reflection_store.py）
2. scp → 清 `__pycache__` → `docker restart langbot-plugin`（插件代码，不动 langbot）
3. Python 3.12 语法兼容（无多行 f-string）

**验证点**：容器无加载报错；下一轮对话 `grep '仅供你内部理解' /tmp/silent_gate.log` 命中（RAW PROMPT 段）。

### 4 反思库清理——**chroma 直连软归档**（NAS 运维，可先于代码部署止血）

通道决策（评审后）：plugin API 通道受 1e bug 与调试载体缺失双重阻塞 → 直接改 chroma metadata。`collection.update(ids, metadatas=...)` **不触向量**，无锁窗口内安全。

序列（重启顺序教训 [[langbot-restart-race-ltm-not-found]]）：
1. dry-run：langbot 容器 python 只读枚举（chroma 只读若被锁，直接进 2 停服后再跑）→ 打印 id+scenario 清单**交用户确认**（删除决定权留用户）
2. `docker stop langbot`（窗口目标 <2min）
3. langbot 容器内一次性脚本：`chromadb.PersistentClient(path='/app/data/chroma')` → list_collections 找反思 collection → `get(where={'type':'reflection'})` → 匹配 **id 白名单**（8/21 冒烟+pytest 直写 9 条：ref:8ac6132c/87b8a783/392b6017/bb26f64b/cd0f9b58/541b378b/4b4286a9/8d4129ac/dcd26221）∪ **scenario 正则** `男女冲突|380V|断路器|DS920|冒烟`（正则命中但不在白名单者仅提示，不自动归档）→ `update(metadatas 置 archived=True, archived_at)`
4. `docker start langbot && sleep 40`（healthy 后）→ `docker restart langbot-plugin`

**验证点**：重开只读枚举确认目标 id 全部 archived=True 且未列条目无变化；群内下一条无关提问注入段不再出现电气条目；服务恢复后 `docker logs langbot --since 5m` 无启动竞态错误。

脚本落盘 `tests/scripts/cleanup_reflections.py`（含 dry-run/apply 两模式）。

### 5 冒烟 `tests/scripts/verify_p15_inject.py`

三原则沿用（唯一 sender `smoke2-{ts}`、T0 重取、非确定项 SKIP）；预检 `hit - inject < 10`：

- (a) /sync `session_type:"group"` 问 VR 问题 → RAW PROMPT 含"仅供你内部理解" → FAIL 门禁
- (b) 同轮 RAW PROMPT 不含"触发条件：用户询问…断路器"等电气条目（门槛+清理双保险）→ FAIL 门禁
- (c) 提取该轮 `inject candidates:` 日志行的 dists 值 → 落盘供阈值校准（信息性，不门禁）
- (d) /sync 问保留反思相近问题 → 有注入则断言头注前缀；库空则 SKIP

**验证点**：脚本退出码 0；dists 数据至少 1 轮真实样本。

### 6 收尾

- 多 agent 评审一轮（代码/QA/运维视角），结论逐条核实再采纳（[[subagent-review-verify-individually]]）
- 合并 main（用户授权 + `CLAUDE_MERGE_AUTHORIZED=1`，见 [[wt-merge-authorization-hook]]）→ push → `wt cleanup`
- 两计划文件归档 `docs/plans/`；"注入文本治理"若一周观察有效提 ADR
- 一周观察：`inject candidates` dists 分布 → 收紧/放宽 0.45；两真实群回复是否仍现旁白腔 → 无效则升级备选（timeline 段头行内标注/反思会话白名单）
- 教训回流 memory：SDK 必填参数漂移、调试载体假设错

## 改动清单

| # | 文件 | 改动 | 行数 |
|---|------|------|:--:|
| 1 | `components/event_listener/default.py` | 压制条款（链尾）+ distance 门槛与观察日志 + 常量 | ~16 |
| 2 | `service/reflection.py` | INJECT_TEMPLATE 头注 + 两 prompt 条款 | ~8 |
| 3 | `store/reflection_store.py` | 1e 修 vectors 缺失（update/archive） | ~15 |
| 4 | `tests/test_p15_inject_governance.py`（新） | 9 用例 | ~140 |
| 5 | `tests/test_p1_maturity_integration.py` | `_ref()` 补 distance | ~2 |
| 6 | `tests/scripts/cleanup_reflections.py`（新） | dry-run/apply 软归档 | ~70 |
| 7 | `tests/scripts/verify_p15_inject.py`（新） | 冒烟 (a)-(d) | ~90 |

零新依赖、零配置新增。

## 风险与对策

| 风险 | 对策 |
|------|------|
| 0.45 未经校准，不相干条目实际 distance 可能 <0.45 | 步骤 4 清理去源头；(c) 采集真实 dists 一周调参 |
| 压制条款软约束失效 | v4 thinking-leak 压制有成功先例；备选升级已列（收尾） |
| chroma 直连停 langbot 窗口（<2min）群消息丢失 | 选夜间/低峰执行；LangBot 离线期间 napcat 消息不补投，风险已知情 |
| list_all 返回不含 vector → 1e 需重算 embedding | 两分支都写入实施步骤；单测覆盖 mock 断言 |
| 清理误归档真实反思 | id 白名单为主、正则仅提示；dry-run 人工确认；archived 可单条回退 |
| 门槛+清理双生效后注入长期为空，功能"静默死亡" | (c) 观察日志区分"召回被门槛滤掉"vs"召回为空"；一周后评估 |

## 工作量

代码+测试 ~2.5h（含 1e），NAS 部署+清理+冒烟 ~1.5h，评审轮另计。
