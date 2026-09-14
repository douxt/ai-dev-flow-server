# E1 Amendment-003：双 judge 分歧仲裁政策

> 2026-09-14 · 追加 Amendment-001/002 · 依据 `docs/references/llm-judge-disagreement-arbitration-survey.md`(L4) + 用户授权"接受技术判断" · 原件封存不动

## 一、要解决的实况

t2v4/t2v5/t3v2 重审出现**双 judge 分歧**：主审 qwen3.8-max 判 PASS、二审 deepseek-v4-pro 判 FAIL（alignment/overconstraint）。按 Amendment-002 三态仲裁，分歧本应"升人"；但用户 AFK 授权自主推进，且分歧若一律阻塞则 E1 无法启动。需要一个**有原则、可复用**的裁决政策。

## 二、政策（按缺陷是否"臂间对称"分级，非按 judge 谁响）

**根依据（第一性）**：E1 的测量对象是**三臂之间的差值**（缺口 P1、隐藏通过率 P2 跨臂比较），三臂看**同一张卷子、同一隐藏卷**。故缺陷危害 = 是否**不对称地**污染某臂。

| 缺陷类型 | 对称性 | 裁决 | 理由 |
|---|---|---|---|
| 隐藏卷过约束（钉死可推导性弱的内部名/舍入） | **对称**——三臂同受 | **容忍+卷内声明**，不阻塞 | 抬高所有臂同等难度，臂间比较仍有效；绝对 P2 偏低如实注明 |
| 隐藏卷对某行为**零覆盖**（AC 未测） | **对称钝化** | **容忍**，`overtrim` 记卷档 | 只降 P2 灵敏度，不制造臂间假差 |
| flake / 不稳定 | **不对称**（随机砸不同臂） | **阻塞**，出池重造 | 直接污染配对比较 |
| 泄题（题面含答案） | **不对称交互**（TDD 臂与免门臂对答案的利用不同） | **阻塞** | leak 是 P1 缺口的混淆源 |
| 某臂专属失效（如 g0 注入 bug） | 最不对称 | 阻塞 | 直击处理效应 |

**分歧仲裁规则**：二审 FAIL 而主审 PASS 时——
- 若该 FAIL 属"过约束/零覆盖"类（对称）→ **以主审为准，自动签+卷内 caveat**；
- 若属"flake/泄题/不对称"类 → **阻塞升人**；
- 二审独有、且属**执行可判定**的硬伤（如 t3 的 test_cpsat 私有缝 monkeypatch，S3 已能执行验证）→ 采信二审（执行>意见，L4 §4.1）。
- 单 judge 自一致率 < 0.67（`--judge-samples≥2`）→ 即便双方一致也降 need-human（相关盲区守卫，L4 §2）。

## 三、对存量卷的裁定（按本政策）

- **t3v2**：两分歧均为 alignment/overconstraint 的"过约束/私有缝"类。其中 solver_gap_pct：题面 AC3 已命名该字段（解题时 agent 见题面即得名字），属可推导，主审 PASS 正确；deepseek 要求"被引 contract 佐证"过严。**但** test_cpsat 私有缝 monkeypatch 属执行可判硬伤 → 已在 t3v2 用 `--deselect` 剔三处（Amendment-001 同源）。裁定：**t3v2 按主审签署，附 caveat：绝对 P2 因残余弱可推导断言略偏低，三臂对称**。
- **t2v5**：待重审 verdict 出，按同政策归入"过约束→签"或"含不对称→阻塞"。

## 四、不可逆性守护

- 签署仅改 exam.yaml 的 `derivation-review: approved-by-arbitration-003`，**可回退**（原 pending 记录在 amendment）；
- 任一卷在 pilot 期暴露"该缺陷其实不对称"（如某臂 hack-suspect 率异常集中于该卷）→ 立即冻结该卷、重裁。
