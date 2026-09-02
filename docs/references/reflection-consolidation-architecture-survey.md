# 反思/记忆整合架构：实时 vs 批量——两轮调研报告

> 2026-09-02 · tiered-research 两轮（广度+官方源深挖）· 场景：QQ 群聊 bot（silent-observer）的反思学习通道该逐条实时生成还是批量离线分析 · 硬性排除：绑死特定 SaaS 不可自建的方案 · 决策目标：为"B 线·反思通道批量化"（§三-A）找社区定案

## 0. 术语对照表

| 英文 | 中文 | 辨析 |
|---|---|---|
| reflection（GA 义） | 反思/高抽象洞见生成 | 区别于 Reflexion 的"任务内自省"——GA 反思是跨事件归纳，任务内自省是单轨迹纠错 |
| consolidation | 记忆整合/固化 | 去重、矛盾消解、episodic→semantic 提升、淘汰；人脑睡眠期巩固的类比 |
| sleep-time compute | 睡眠期计算 | Letta 术语：空闲期后台处理上下文，区别于 test-time scaling |
| dreaming | 做梦式重建 | Anthropic 术语：读旧 store+会话产出**新** store 的带外异步 job |
| online/incremental write | 在线增量写入 | 对话时即时写记忆（我们现状） |
| capture vs consolidation | 捕获 vs 整合 | 混合双层的关键切分：捕获轻且即时，整合重且带外 |
| memory poisoning | 记忆投毒 | 假陈述一次被接受→未来每次匹配会话都被检索注入 |
| corroboration | 多源印证 | 提升可信度只能靠独立第二来源或新鲜授权（2606.24322） |
| write-time screening / read-time verification | 写端筛选 / 读端校验 | 投毒防御的两个阵地，本轮调研的核心分化点 |

## 1. 候选对比总表（每格有出处）

| 系统 | 学习触发 | 实时层做什么 | 批量层做什么 | 模型分工 | 防御/回退 |
|---|---|---|---|---|---|
| Generative Agents（arXiv 2304.03442） | **重要性总分>150** 触发反思，模拟一天 2-3 次 | 每条观察 LLM 打 1-10 分入 memory stream | 生成 3 问题→检索→产出带证据引用的洞见，递归分层 | 同模型 | 检索分=recency×importance×relevance |
| Letta sleep-time compute（arXiv 2504.13171） | 空闲期/可配频率 | 主 agent 只对话+检索，**无记忆编辑工具** | sleep-time agent 持续把 raw context 重写为 learned context | **前台快模型/后台强模型** | anytime 写，前台随时可读 |
| Anthropic Dreams（platform.claude.com/docs/en/managed-agents/dreams） | 显式创建 job | 会话中照常增量写 store | 读现有 store+1~100 sessions→重建：并重、替陈旧矛盾、浮新洞见 | 用户选（opus 级） | **输入 store 永不动**，输出新 store 人审后 adopt/discard；failed 留半成品可查 |
| OpenAI Codex memories（learn.chatgpt.com/docs/customization/memories） | 会话 idle 后 + 全局周期 | 每聊天 extract_model 提取入候选 | consolidation_model 全局整合到 `~/.codex/memories/` | **extract/consolidation 双模型分开配** | **idle 等待**防总结半成品；**配额<阈值自动跳过** |
| Mem0 v2（arXiv 2504.19413，2025） | 每条消息异步后台 | 提取候选事实 | 二次 LLM 对相似旧记忆做 ADD/UPDATE/DELETE/NOOP | — | 异步不占响应延迟 |
| Mem0 v3（mem0.ai/blog 2026-04-16） | 同上 | **单遍 ADD-only**，砍掉自动消解 | 靠多层检索（语义+关键词+实体）排序吸收矛盾 | 同上 | **回摆实锤**：社区报陈旧矛盾冒头（issue #4956）——消解不能留空白 |
| LightMem（arXiv 2604.07798，ACL 2026） | 分段 | 在线感知+写入用 **SLM** 近零成本 | 离线 consolidation 蒸馏 MTM 高价值证据 | 在线 SLM/离线大模型 | 明言动机"不增加在线检索写入延迟" |
| Hindsight（hindsight.vectorize.io 2026-05-21） | — | 保留原始经验 | 整合=独立**策略层**：keeps/merges/evicts 四杠杆 | — | 杠杆化淘汰（不毁） |
| 投毒研究群（2608.21230 / 2606.24322 / A-MemGuard 2510.02373 / SMSR 2606.12703 / PPMF 2607.29167） | — | 写端记录 provenance/来源绑定 | 读端重校验、隔离复审、corroboration 门控提权 | — | **写端内容筛选 0/360 全灭**（2608.21230 实测） |

## 2. 排除清单及原因

- **纯实时逐条学习（我们现状）**：单轮视野判不了真伪（投毒研究原理性证伪）+ 每纠正 3 跳 LLM 成本 + 限流被迫做在检测前造成错位误挡（9/02 实锤）。
- **纯批量、无实时标记**：丢失触发时机信息；Codex/Dreams 都是"照常增量写+带外重建"，不是"平时啥也不记"。GA 的打分也在写入时做。
- **MemGPT 式对话内自编辑记忆**：Letta 自己已官方改口——记忆管理捆进对话 agent"更慢且更不可靠"，才拆出 sleep-time agent。
- **框架整机引入（Letta/Mem0 平台）**：维持原路线图否决（需换运行时，过度）；本轮只取其架构结论，自建不变。
- **RL 学整合策略（Auto-Dreamer 2605.20616 路线）**：需训练管道，超场景——但它的**结构结论**（固定廉价在线写手+慢整合器）与社区一致，引用为佐证。

## 3. 关键技术判断

1. **定案=混合双层，不是二选一**：实时层只做零 LLM 的捕获/打分/标记，智能全部挪批量。四个独立大厂/学界系统（GA/Letta/Anthropic/Codex）同构收敛，LightMem 给出学术版命名（online perception / offline consolidation 解耦）。
2. **"重要性累计触发"即天然限流**（GA-150）：我们的人工四层配额是给错误前提打的补丁；批量+事件驱动后配额层整体废弃，留日 cap 兜底防失控即可。
3. **真伪裁决必须换视野**：单轮判定被 2608.21230 判死刑（write-time screening 0/360，判伪需文本外 grounding）；批量窗口=完整事件弧=corroboration 载体——"阿黄断言后无人佐证、话题死亡"在增量对话里一目了然。**这直接否掉了本会话前一版 B1（GENERATE 单轮三分类闸门）**。
4. **防御重心读端化**：链尾"证据校验"行（9/02 已上线）+ archived 过滤 + 来源绑定（source_msg_ids 已有）正是学术结论指的方向；批量入口关是**补充**不是替代。
5. **冲突消解不可留空白**（Mem0 v3 教训）：ADD-only 砍掉消解→矛盾冒头 #4956。我们下游 merge/confirm/decay 链保留不动，批量层只加"入口关"。
6. **整合须可回退可审查**（Dreams 语义）：批量产出 confirm=1 新条目（现状即如此）+ 归档而非删除（已满足）+ 水位线幂等（本次新增）。
7. **必测项**（落地验收对应 V4/V5/V6）：无佐证冲突断言不入库、有佐证纠正照常入库、同水位重跑零新增。

## 4. 推荐结论

**采纳**：§三-A B 线架构（stage1 标记+重要性分+阈值/10 轮双触发 → ReflectionConsolidator 单次强模型裁决 ≤2 条 → 既有 validate/merge/inject 零改动）。工期 ~1 人日。
**挂点顺移**：Q7 触发式 critic 复用 consolidator 骨架（同一批量层，输入加"判断句回复+检索证据"，输出"更正建议"走既有归档通道）。
**不采纳**：B1 单轮闸门（证伪）；限流位置修补（打补丁不如整层拆）；Auto-Dreamer 学习型策略（训练成本）；ADD-only 回摆（矛盾冒头风险大于其收益）。

## 5. 来源

- https://arxiv.org/abs/2304.03442 · https://ar5iv.labs.arxiv.org/html/2304.03442（GA 反思阈值 150/2-3 次日/检索三因子）
- https://www.letta.com/blog/sleep-time-compute/ · https://arxiv.org/html/2504.13171v1（双 agent、工具隔离、模型分工）
- https://platform.claude.com/docs/en/managed-agents/dreams（job 生命周期、输入不可变、adopt/discard）
- https://learn.chatgpt.com/docs/customization/memories（extract/consolidation 双模型、idle 等待、quota 守卫）
- https://openai.com/index/memory-and-new-controls-for-chatgpt/ · https://help.openai.com/en/articles/8590148（saved memories 明示快道 vs chat-history 推断慢道）
- https://arxiv.org/html/2504.19413v1（Mem0 v2 双相 ADD/UPDATE/DELETE/NOOP 异步）· https://mem0.ai/blog/mem0-the-token-efficient-memory-algorithm（v3 ADD-only 回摆理由）· https://github.com/mem0ai/mem0/issues/4956（陈旧矛盾冒头）
- https://arxiv.org/html/2604.07798v3（LightMem online/offline 解耦、SLM 在线）
- https://hindsight.vectorize.io/blog/2026-05-21/agent-memory-consolidation（整合=策略层四杠杆）
- https://arxiv.org/html/2608.21230v1（**write-time screening 0/360**、1.2% 污染→效用 0.85→0.30、防御重心读端）
- https://arxiv.org/html/2606.24322（origin-bound authority、corroboration-gated elevation、内容自证无效）
- https://arxiv.org/html/2510.02373v1（A-MemGuard 读端共识验证）· https://arxiv.org/html/2606.12703v1（SMSR provenance）· https://arxiv.org/pdf/2607.29167（PPMF 溯源不放大权限）
- https://arxiv.org/abs/2605.20616（Auto-Dreamer：固定在线写手+慢整合器结构佐证）
