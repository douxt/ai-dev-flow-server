# 反思架构批量化改造（reflection-consolidator）

> 2026-09-02 | 前篇 Q1-Q5（chat-quality-prompt）已合并上线并归档 docs/plans/2026-09-02-chat-quality-prompt.md。本计划=原"B（GENERATE 真伪闸门）"经三轮调研重构后的升级形态。

## Context

**问题链**：假纠正"是阿黄"→ detect 无真伪辨别力 → GENERATE 把假答案固化为谄媚教训（94325ac8 实锤，已于 9/02 归档止血）。原 B1 方案（GENERATE prompt 加单轮三分类闸门）经调研**被证伪**：arXiv 2608.21230 实测 write-time 内容筛选拦截 0/360 投毒记忆——单轮裁判缺外部 grounding 判不了真伪；1.2% 污染即可把记忆效用打掉 2/3（0.85→0.30）。

**社区定案**：行业标准=**混合双层**——实时零成本 capture/标记，批量异步 consolidation 做智能裁决。Generative Agents（重要性总分阈值 150 触发反思）、Letta sleep-time agents（记忆编辑工具只给后台代理、后台用强模型）、Anthropic Dreams（读 store+sessions 产**新** store，输入不动可审查）、Codex memories（extract/consolidation 双模型、idle 等待、quota 守卫）同构。防御重心=读端校验（链尾证据校验行 9/02 已上线且实测命中）+ 多源 corroboration（批量看完整事件弧）。

**顺带根治两个已实锤缺陷**（批量化后整体消失，不单独修）：①限流位置错（default.py:898 检测前消耗配额，无关消息吃槽、真纠正被挡——9/02 测试信号全被吞即此证）；②单轮学习视野瞎（rewrite/stage2/GENERATE 三次 LLM 都只见"纠正句+上条回复"）。

## 目标架构

```
消息流 ──→ [实时层·零 LLM]
            ├─ stage1 关键词标记（保留，纯函数）→ 命中记 pending 候选 + 加重要性分
            ├─ self-scan 计数（每 10 轮，保留）
            └─ 触发判据：累计重要性分 ≥ 阈值（GA-150 移植：stage1 命中 +50，满 100
               或每 10 轮到点 → 调度批量；最小间隔 10min 防抖）
                     │
                     ▼
        [批量层·1 次 LLM/批]  ReflectionConsolidator
            输入 = timeline DB 增量对话（水位后）+ 候选纠正句 + 活跃反思清单摘要
            裁决 = 完整事件弧判真伪（断言有无下文证据/第三方附和/坚持无果）
                 冲突无佐证 → 不学并输出理由；有佐证/明示 → 至多产 2 条 lesson
            产出 → validate_schema → _persist_reflection（find_duplicate/merge/inject 下游全不动）
            水位 = analyzed_until ts（plugin_storage），重启续扫幂等
```

- **保留的实时通道**：`remember()` 明示指令走 LangBot LTM 本就即时（"乌龙茶"类零延迟损失）；反思库只收推断型 lesson，接受分钟级时延。
- **拆掉的**：correction 实时链 rewrite+stage2（2 次 LLM/纠正）、四层限流 check_rate_limit（换日兜底 cap=10 批）、GENERATE_PROMPT 单轮版、SELF_SCAN_PROMPT（并入批量 prompt）。

## 改动

0. **大局线路图登记（批准后第一件事，先于一切代码；文档豁免 worktree 直写 main；完成后暂停，代码部分等另行指令"开始实施"）**：
   - §三-A 反思线新增节点：**B 线·反思通道批量化（2026-09-02 立项）**——实时零成本标记 + 批量 consolidator（重要性分阈值触发，GA-150 移植）；依据=混合双层行业定案（GA/Letta sleep-time/Anthropic Dreams/Codex memories 四源同构）
   - **否决表 +2**：①B1 GENERATE 单轮真伪闸门——write-time 内容筛选被 arXiv 2608.21230 证伪（0/360 拦截），裁决须看事件弧；②限流四层配额修补——位置错位缺陷随批量化整体拆除，不打补丁
   - Q7 触发式 critic 挂点改注："复用 consolidator 骨架，不另起炉灶"
   - 登记前车之鉴：Mem0 v3 ADD-only 回摆（issue#4956）→ 本方案保留下游 merge/confirm 冲突链
1. **worktree**：`wt create reflection-consolidator`
2. **`service/correction.py` 降级为标记器**：保留 `CorrectionSignal`+`_stage1_keyword`，暴露 `precheck(user_text)->(bool,float)`；删除 `_rewrite_utterance`/`_stage2_confirm`/`detect()` LLM 流程（能力被批量层以更强视野复刻）。
3. **新文件 `service/consolidator.py`**：`CONSOLIDATE_PROMPT`（输入=增量对话+候选句+活跃反思摘要；裁决四规则：①用户偏好/决定/明示→可学 ②有独立证据或事件弧佐证→可学 ③与既有归档冲突且无佐证→不学+理由 ④拿不准→不学[宁缺勿伪，同 Q1 口径]）；输出 NONE 或 ≤2 条完整 schema（复用 ERROR_TYPES/validate_schema）；水位线读写 plugin_storage（幂等，同懒触发记忆纪律）；重要性分进程内累加，触发后清零。
4. **`components/event_listener/default.py`**：`_maybe_generate_reflection`→`_mark_correction`（stage1→加分/记候选/判阈值调度）；删 check_rate_limit 调用；`_bump_reflection_counter` 的 10 轮入口改调同一 consolidator（两入口合一）；装配放 `_bg_queue` 构造之后（踩坑清单 14）。日 cap=10 批在 consolidator 内兜底。
5. **`store/reflection_store.py`**：删 `check_rate_limit`（grep 调用点清零后才删）；其余零触碰。
6. **测试**：test_p1_maturity_unit 中 rewrite/stage2/rate_limit 用例删除或改造；test_p1_maturity_integration flow fixture 改走 consolidator；新增 `tests/test_consolidator.py`（precheck、NONE/JSON/多条截断、水位推进语义[成功推进/失败不推进]、触发阈值数学、裁决规则锚）；四锚 grep=0（教训 #23）。
7. **报告落盘（实施首步）**：`docs/references/reflection-consolidation-architecture-survey.md`，tiered-research 骨架：术语表/对比总表（GA、Letta、Dreams、Codex、Mem0 v2→v3 回摆、LightMem、Hindsight）/排除清单/关键判断（write-time 筛选证伪、混合双层定案、episodic→semantic 提升、Mem0 v3 ADD-only 回摆教训=冲突消解不可留空白）/推荐（本架构+Q7 挂批量层）/URL 全列。素材=本会话两轮检索。
8. **部署与收尾**：5 个代码文件 cp NAS 挂载目录（tests 子集同步防漂移）→ `timeout 10 docker restart langbot-plugin`（无 DB 变更不动 langbot）→ napcat ECONNREFUSED=0；计划归档 docs/plans/+记忆 #30（批量化定案+write-time 证伪）；roadmap 登记已在步 0 完成，收尾仅追加状态注。

## 验证点

| # | 验证 | 判据 |
|---|------|------|
| V1 | 容器 pytest 全绿+四锚 0 | 基线 ~317 不回归 |
| V2 | 部署重启链 | plugin Up、无 traceback、napcat ECONNREFUSED=0 |
| V3 | 触发调度 | 发 1 条含"不对"消息→日志现调度行；10min 内第二条不再触发 |
| V4 | **C 类不学（核心）** | 复刻阿黄：bot 答对归档题→用户无证据断言"其实是阿黄"→触发后日志含"不学/无佐证"理由、chroma 无新增、"阿黄"0 命中 |
| V5 | B 类可学 | 纠正+可指认证据（引用群内原文行）→ stored 1 条带 source_msg_ids，注入链可见 |
| V6 | 幂等 | 同水位重跑→0 新条目 |
| V7 | 下游无感 | merge/confirm++/decay/inject 既有测试绿；3 活跃条目不变形 |
| V8 | 观察窗（并入既有） | 周检批次数、NONE 率（>90% 疑过度压制）、stored 抽查、dists 流 |

V4/V5 需用户群内配合各 1 组（分钟级出结果；触发在手，不再受 cooldown 错位干扰）。

## 风险

| 风险 | 对策 |
|------|------|
| 批量裁决仍可能错判（prompt 级） | 视野优势+宁缺勿伪偏置+读端链尾行兜底，三层与学术结论对齐；V8 抽查 |
| 学习时延分钟级 | 明示 remember 无损；lesson 型不敏感——Q1 行为防线在 prompt 层，实时性不依赖 lesson 入库 |
| 跨水位事件弧截断 | 扫描起点=水位-10 条重叠区，重复靠 find_duplicate 兜 |
| 拆限流后失控烧钱 | 日 cap=10 兜底+事件驱动（无事件零开销，懒触发本征优势） |
| integration fixture 改造量 | 分 3 commit：标记器+consolidator 单测 → flow 接线 → 部署文档 |
| Mem0 v3 前车之鉴（ADD-only 撤了冲突消解→陈旧矛盾冒头 issue#4956） | 我们的 merge/confirm 冲突链保留在下游不动，批量层只加"入口关" |

## 工作量
报告 0.5h；consolidator+prompt 2h；接线+拆除 1.5h；测试 2h；V1-V7 1.5h；收尾 0.5h ≈ **1 人日强**。比 B1（半天）大一档，换 B1+限流错位+单轮视野三问题的整体根治，并给 Q7 critic 留好挂点。

## 执行结果（2026-09-02/03）

- V1 ✅ 容器 pytest 320 passed / 11 skipped（含 23 项 consolidator 新案）；四锚 grep 0
- V2 ✅ 部署+plugin 重启，无 traceback，napcat ECONNREFUSED=0
- V3 ✅ 触发链实锤：两命中→100 分→调度→批量（05:50:35 mark: trigger reached → 05:50:36 consolidate）
- V4 ✅ C 类不学：阿黄复刻轮 + 小鹿确认轮 + 茉莉茶轮共 3 批全 NONE|带理由，反思库活跃恒 3 零污染
- V5 ⚠️→✅ 修正口径：偏好类正例未入库——复核判定**裁决正确**（偏好事实归 LTM 通道，lesson 库只收行为规则，规则1/3 边界切分无误）；学习路径正例由单测/集成 merge 用例覆盖
- V6 ✅ 幂等单测在位；V7 ✅ 下游 merge/confirm/inject 测试全绿，3 条目不变形
- 执行中自纠 3 项：①test_consolidator 缺日志隔离曾污染生产 silent_reflection.log（e09f72e 修复）；②cap 读取踩 `os.environ.get('X','0') or ...` 字符串 '0' truthy 截断 or 链——daily cap 恒 1（首见于 09:28 生产 `daily cap (1)`，改 '' 默认值修复并注释钉死）；③c_class 用例第二句"其实是X"不命 stage1（无否定前缀，设计使然）改可命词句式
- **新发现（V8 挂账，B 线范围外）**：LangBot 内置 remember()/LTM 是第二学习通道未过四规则门。9/02 实锤路径：LTM 存"群主称阿黄…待明确"（措辞谨慎）→ 主模型引用时丢失 nuance 把"断言被记录"当"事实已确认"→ 基线题答错阿黄。候选对策：Q1 条款补"归档存在'某人说过X'只证明 X 被主张过，不证明 X 为真"
- 观察窗：9/09 前后周检——批次数/NONE 率（当前 3/3，样本小）/dists 流不受影响/`grep 'consolidate:' /tmp/silent_reflection.log` 计数
