# 反思向量归一化对称修复 + 距离度量口径纠错（reflect-dist-norm-fix）

> 2026-08-31 | 前篇 vision-url-enable 已合并归档（docs/plans/2026-08-28-vision-url-enable.md），本文件覆盖

## Context

8/29 受控纠正首跑把反思全链路（detect→rewrite→stored→inject 检索）钉活了，但 `inject candidates` 给出**强相关查询 dist=3.02**，门槛 0.45 永拒。8/31 容器内探针实锤根因，本计划修三处已验证的度量层错误：

1. **归一化不对称（主因）**：查询侧向量归一化到 1.0（reflection_store.py:62/192 同款代码×2、kb_store.py:271），存储侧原样写入——实测生产库唯一真实条目向量 **norm=1.8595**。数学推论：查询 norm=1 vs 存储 norm=1.86 时 l2² 下限 =(1.86−1)²=0.74 > 0.45 → **一字不差的句子都过不了门槛，注入通道数学性死亡**。
2. **错误空间认知**：collection 无 space 配置（col.metadata=None）→ chroma 默认 **l2²**，而 `find_duplicate`（reflection_store.py:212/223）按 `cosine = 1.0 − distance` 换算（这是 cosine 空间公式；l2² 空间应为 `1 − d/2`）。叠加不对称后实际 cos≈0.39 的强相关查询被算成 cosine≈0.26<0.70 → **merge 去重同样永久失效**。
3. **阈值语义失准**：`_REF_INJECT_MAX_DISTANCE=0.45` 的注释（default.py:52）自称"cosine distance，find_duplicate 区间 ≈0.15-0.30"——建立在前两条错误口径上的自校准，从未有真实数据。

已定界**不修**（记录为观察项）：kb_store 向量通道纯 rank 用途（RRF 融合，无距离阈值），不对称只造成排序轻微失真，非致命；生产 embedding 模型为 seekdb-local（插件配置 uuid 62e075f9，探针时已查明非 MiniLM），其 norm 随文本浮动，归一化后免疫。

## 改动

### 1. worktree（首步）
`wt create reflect-dist-norm-fix`

### 2. 代码（docker/langbot/plugins/silent-observer/）

**store/reflection_store.py**：
- 新增 `_norm_vec(v: list[float]) -> list[float]` 静态方法（norm>0 除之，否则原样）
- 替换 4 个调用点（第 5 处 L33 是维度探针只取 len()，无需归一）：
  - `search_similar`（L55 后）、`find_duplicate`（L188 后）查询侧 → 改用 helper（行为不变，消重复）
  - `store_reflection`（L128）upsert 前 → 归一化
  - `_embed`（L147-152）→ 返回值归一化（**update L160 / archive L282 两路径自动继承**，已核实）
- `find_duplicate` 两处换算（L212/L223）：`cosine = 1.0 - distance / 2.0`，clamp 到 [0,1]（distance∈[0,4]，≥2 自然归 0）
- `search_similar` 返回的 `distance` 字段透传不动（语义随存储侧修复自动变正确）

**components/event_listener/default.py**：
- `_REF_INJECT_MAX_DISTANCE` 0.45 → **1.4**（评审纠错：原拟 1.0=cos≥0.5 会被自家实证数据否定——强相关样本实测 cos≈0.39 即 d≈1.22>1.0，V3 注定失败；1.4=cos≥0.3 放行实证样本，不相关文本典型 d≈1.6-1.8 仍挡门外，配合 >5 条 rerank 护栏）
- 注释重写（钉死度量语义，杜绝再考古）：对称归一化后 d=2−2cos（0=同句，1=正交，2=反相关）；实证锚点——口语查询 vs JSON 全文 doc 强相关样本 cos≈0.39；`inject candidates` 真实分布攒够（≥20 条）后收紧；旧值 0.45 因 norm 不对称数学不可达

### 3. 测试（与实现同 Phase 交付）

- 新增 `tests/test_reflection_vector_norm.py`：
  - `_norm_vec`：norm≈1.86 样例归一到 1；零向量原样
  - `store_reflection`：SDK mock 捕获 upsert 参数 → 断言 vectors norm≈1
  - `_embed`：同上（覆盖 update/archive 继承）
  - `find_duplicate` 换算表（避开代码严格大于的恰边界）：d=0.1→cos=0.95（direct）、d=0.45→0.775（candidate）、d=1.0→0.5（none 走三级）、d=2.0+→clamp 0
  - 修复前症状回归用例：query norm1 vs stored norm1.86 同句 dist 下限 0.74 场景 → 修复后对称 dist=0 <1.0 通过
- **必挂测试逐个修**（评审实锤+已抽查核对行号）：
  - `test_p15_inject_governance.py`：TestDistanceGate 4 处——"远"样本 d=0.9 全部抬到 **1.8**（>1.4，L41-46/L58-62/L73-78 含 rerank 零调用断言）；边界用例 L51 `==0.45`→`==1.4`、d 0.45/0.4501→1.4/1.4001；L106 `vectors[0][0]==0.1` → 改断言 **norm≈1**（`abs(sum(v*v)-1)<1e-6`，conftest mock [[0.1]*384] norm≈1.96，_embed 归一化后必红）
  - `test_p1_maturity_store.py`：test_candidate L90-92 mock d=0.2 → 新公式 cos=0.9 判 direct 必红 → d 改 **0.4**（cos=0.8 落候选带）；test_direct d=0.05 不红但注释"cosine 0.95"失真顺手改；entity_link/none 用例 d=0.99→cos=0.505 仍走三级，复核即可
  - `test_p1_maturity_integration.py`：**核实不会坏**（merge 用例 d=0.01 新旧公式均判 direct），不改
- 本地 `pytest tests/test_*.py -q` 全绿 → 容器内回归（**部署清单须含 tests/**，否则容器跑旧测试必红、V6 不可达——评审 P1-3）：`cd /app/data/plugins/dou__langbot-silent-observer && /app/.venv/bin/python -m pytest --rootdir=. tests/test_*.py -q`

### 4. 部署（NAS，仅插件容器，不碰宿主——patches 体系无关）

- scp **reflection_store.py + default.py + tests/**（conftest.py、两个改名测试、新增 norm 测试）→ `docker cp` 进 langbot-plugin 插件目录 → `docker restart langbot-plugin` → 启动日志无异常
- **回滚 = 容器内 `cp 文件 .bak` 先行 → 出错时 cp .bak → docker cp 旧文件 → restart langbot-plugin**（无 DB 迁移，整体可逆）
- **存量条目 ref:88244bed 不归档不迁移**（删除决定权留用户）。"自动失效"结论已量化（评审补充，钉死防再考古）：其向量未归一化，对新查询 dist 下限 =(1.86−1)²=0.74 → 新公式下 cosine 上限 =1−0.74/2=**0.63 < 0.70** → find_duplicate 永不误触 direct/candidate merge。注意：find_duplicate 的 filter 不排除 archived（L201），旧条目会占 top-5 槽位——由上限 0.63 兜底无害，若未来条目多再议排除
- 若要正式清理/自愈，走 cleanup_reflections.py 既定流程（停 langbot→apply→重启复查 archived 未被冲掉），本计划不执行

### 5. 每步验证点

| # | 验证 | 判据 |
|---|------|------|
| V1 | 部署生效 | 容器内两文件 md5 == worktree 版；plugin 启动日志无 error |
| V2 | 新写向量归一 | 用户重演一次纠正（素材复用橘猫/小鹿，旧条目已失效不冲突）→ `stored:` 新 id → 探针查该条 norm=1.0000（复用 /tmp/chroma_norm_probe.py 改 DOC_ID，只读） |
| V3 | 注入通道复活 | 冷却 10min 后强相关 @ 提问 → `inject candidates` 出现 dist<1.4 条目 **且** gate.log `LLM RAW PROMPT` 段见"触发条件："注入段（断言位纪律见记忆 #25）；同时记录 dist 值——相对 1.22 实证锚点的偏移即口径校准数据 |
| V4 | merge 路径首验（判据按评审放宽） | 第二次同主题相近纠正（再隔 >10min）→ find_duplicate 被触发即可：direct/candidate→update+confirm_count 递增、norm 仍=1（闭环 8/27 移交项）；**none+新存也属可接受结果**，记录分布（口语短句 vs JSON doc 真 cos>0.85 本就苛刻，实测参照 0.39）。失败分诊：dump find_duplicate raw distance 列表手算 1−d/2 对照，区分"公式/阈值/文本口径"三层 |
| V5 | 无旁白回归 | V3/V4 bot 回复人设正常（8/29"已归档"回复已证压制条款过一关，继续抽查） |
| V6 | 回归面 | 容器 pytest 全绿；生产日志无新增 `inject error`/`search error` |

### 6. 文档收尾

- 计划归档 docs/plans/2026-08-31-reflect-dist-norm-fix.md
- 团队记忆 #28：l2² 空间三错一体（norm 不对称 + cosine 换算公式错 + 阈值伪校准）；教训句式——**距离阈值上线前必须实测真实存储向量的几何下限（norm 不对称时 (1−‖d‖)² 这种不可达性口算即现）**；另记 8/29 观察期移交项闭环（merge 首验并入 V4）；三副本同步 + MEMORY.md 索引 27→28
- 观察期改口径：0.45 校准作废；新基线自部署日起 `inject candidates` 攒 ≥20 条真实 dists 后收紧阈值（约 9 月中）

## 风险

| 风险 | 对策 |
|------|------|
| 阈值 1.4 偏松→弱相关反思混注入 | 库总量极小 + >5 条走 rerank + 注入条数护栏；观察日志持续积累，收紧只改一个常量 |
| find_duplicate 新语义误合并 | direct 0.85/candidate 0.70 数值未动、只修换算公式；此前 merge 从未真正工作，属语义纠正非行为回归 |
| 旧条目 ref:88244bed 与新条目同主题并存 | dist 虚高天然不参与注入/merge；去留走 cleanup 既定流程由用户裁决 |
| V3 若仍无注入段 | 逐层排查：dist 是否入 1.4（观察日志）→ `build_reflection_prompt` 是否空返回 → 注入 append 段是否在屏——每层有独立日志锚点 |

## 工作量

代码+测试 ~1h；部署+V1 ~10min；V2-V4 依赖用户配合 3 条消息（跨 ~30min 冷却窗）；文档 ~15min。
