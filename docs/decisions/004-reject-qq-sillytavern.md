# ADR-004：不用 QQ 酒馆插件

**状态**：已拒绝  
**日期**：2026-07-13  
**决策者**：项目维护者

## 背景

QQ 酒馆（QQSillyTavern）是 LangBot 生态中一个成熟的记忆插件，提供：
- 短期记忆（滑动窗口）
- 长期记忆（向量检索）
- 世界书（知识图谱）
- 用户画像

考虑是否可以基于 QQ 酒馆构建反思层，避免重复造轮子。

## 决策

**拒绝采用 QQ 酒馆**，原因如下：

1. **设计目标不同**
   - QQ 酒馆：面向角色扮演（RP）场景，强调人设一致性和世界书
   - Silent Observer：面向群聊助手，强调反思机制和自我进化

2. **记忆机制不匹配**
   - QQ 酒馆：定期总结对话，生成"故事"形式的长期记忆
   - Silent Observer：需要结构化反思记录（情境、错误、正确做法），支持语义检索

3. **许可证风险**
   - QQ 酒馆：AGPL-3.0（传染性许可证）
   - Silent Observer：闭源项目
   - 风险：如果使用 QQ 酒馆代码，可能需要开源整个插件

4. **架构耦合**
   - QQ 酒馆：深度集成 LangBot 事件系统，难以解耦
   - Silent Observer：需要独立的反思层，便于独立演进

## 理由

1. **反思层需要定制**：Silent Observer 的反思机制（情境、错误、正确做法）与 QQ 酒馆的记忆机制（故事总结）本质不同
2. **许可证合规**：避免 AGPL 传染风险
3. **架构独立性**：反思层应该独立于记忆层，便于未来扩展（如加入自我评估层）

## 后果

### 正面
- 反思层可以完全按需设计，不受 QQ 酒馆限制
- 无许可证风险
- 架构更清晰，职责分离

### 负面
- 需要自己实现记忆层（KB 读写、向量检索）
- 开发工作量增加（约 1-2 周）

## 替代方案

1. **参考 langbot-longterm-memory**：Apache-2.0 许可证，可安全参考其 store/ 层实现
2. **参考 astrbot-livingmemory**：AGPL-3.0 许可证，仅参考架构思路，不复制代码
3. **自建记忆层**：基于 ChromaDB 实现，符合 Silent Observer 需求

## 实施计划

1. 自建 KBStore（基于 ChromaDB）
2. 自建 ReflectionStore（结构化反思记录）
3. 自建 PromptBuilder（基于反思记录组装 prompt）
4. 参考 langbot-longterm-memory 的实现，但独立开发

## 相关 ADR

- ADR-001：插件目录结构选 plugins/
- ADR-002：测试策略选核心层单测优先
- ADR-003：可测性设计用依赖注入

## 参考资料

- [QQ 酒馆 GitHub](https://github.com/NanaTyrannus/QQSillyTavern)
- [langbot-longterm-memory](https://github.com/langbot-app/langbot-longterm-memory)
- [astrbot-livingmemory](https://github.com/langbot-app/astrbot-livingmemory)
