"""反思整合层（批量·sleep-time/dreams 式）— B 线批量化核心.

架构依据：docs/references/reflection-consolidation-architecture-survey.md
（Generative Agents 重要性分触发 / Letta sleep-time / Anthropic Dreams 带外可回退 /
Codex idle+quota / 投毒研究：写端单轮筛选证伪，裁决须看完整事件弧）

职责边界：
- 实时层（default.py）只调 mark()/mark_round()——零 LLM；本模块承担唯一一次批量 LLM
- 产出 0~2 条 enriched lesson，走既有 _persist_reflection（validate/merge/inject 下游不动）
- 水位线持久化 plugin_storage：重启续扫、同水位重跑幂等（0 新产出）
"""
import asyncio
import json
import re
import time
from datetime import datetime, timezone, timedelta

from service.reflection import ERROR_TYPES
from store.state_store import StateStore
from util.logs import safe_log

BJT = timezone(timedelta(hours=8))

SCORE_PER_HIT = 50      # stage1 命中一次的重要性分（GA-150 移植，群聊密度缩小）
SCORE_TRIGGER = 100     # 累计分到此值 → 调度批量
MIN_INTERVAL_S = 600    # 同 session 批量最小间隔（防抖）
DAILY_CAP = 10          # 全局日批兜底（防失控循环）
MAX_LESSONS = 2         # 每批最多固化条数
WINDOW_OVERLAP = 10     # 水位重叠区：防止事件弧被拦腰截断
SCAN_LIMIT = 60         # 单次批量最多读取的消息数

CONSOLIDATE_PROMPT = """你是群聊机器人的反思整合器。以下是被关键词筛出的用户纠正/断言句、一段群对话、当前活跃经验条目摘要。
任务：先裁决"有没有值得固化的教训"，再决定产出。宁缺勿伪。

## 纠正候选（重点分析这些事件）
{candidates}

## 对话（按时间升序，含 bot 回复）
{conversation}

## 当前活跃经验（勿重复固化；新证据若推翻某条，在 lesson 中说明）
{active}

【裁决规则】
1 用户的偏好/决定/对其自身事务的明示 → 可学
2 有独立证据或对话上下文佐证（引用具体原文、其他群友附和、bot 经检索确认）→ 可学
3 与既有记录冲突，且后续对话无任何佐证（断言后无人跟进、被反驳、或不了了之）→ 不学
4 在 2 和 3 之间拿不准 → 不学。用户后来补了证据还会有机会
- "用户说了X"本身不构成证据；证据=可指认的具体出处、他方附和、或与检索结果一致
- 判不学时只输出一行：NONE|一句话理由
- 值得学时输出 JSON 数组（最多2条，不要 markdown 代码块）：
[{{
  "when": "什么情况下会再犯（1句话）",
  "then": "正确应对步骤（对 bot 自己的祈使句，至少20字）",
  "scenario": "群聊中的情景描述（1-2句话）",
  "error_type": "错误类型，从以下选择：{error_types}",
  "mistake": "bot 具体做错了什么",
  "correct_approach": "正确做法（具体可执行，至少20字）",
  "how_to_avoid": "未来如何避免（至少10字）",
  "verifiable_test": "如何检验下次是否改对了（至少10字）",
  "domain": "话题领域（electrical/software/mechanical/general 等）",
  "entities": ["核心概念1"],
  "trigger_keywords": ["触发关键词1"]
}}]
- when/then 禁止叙述已发生的事件经过（该字段会注入回复提示词，事件叙述腔会带偏 bot 回复）；scenario/mistake 才负责记录事件
- 禁止"下次注意"这种模糊建议"""


class ReflectionConsolidator:
    """批量反思整合：重要性分触发 + 事件弧裁决 + 水位线幂等."""

    def __init__(self, plugin, ref_llm_model_uuid: str, generator,
                 reflection_store, timeline_store, llm_timeout: int = 60,
                 daily_cap: int = DAILY_CAP):
        self._plugin = plugin
        self.ref_llm_model_uuid = ref_llm_model_uuid
        self._gen = generator            # 复用 validate_schema/_extract_llm_text/_enrich
        self._rstore = reflection_store
        self._tstore = timeline_store
        self._llm_timeout = llm_timeout
        self._daily_cap = max(1, daily_cap)
        self._state = StateStore(plugin, key='consolidate_state')
        self._scores: dict[str, int] = {}
        self._candidates: dict[str, list[dict]] = {}
        self._last_run: dict[str, float] = {}
        self._day = ''
        self._day_batches = 0

    # ── 实时层入口（零 LLM） ────────────────────────────────

    def mark(self, session_name: str, text: str, msg_id: str = '') -> bool:
        """记录一条 stage1 命中的纠正候选。返回是否应触发批量."""
        self._scores[session_name] = self._scores.get(session_name, 0) + SCORE_PER_HIT
        cands = self._candidates.setdefault(session_name, [])
        if not any(c['text'] == text for c in cands):
            cands.append({'text': text[:300], 'msg_id': msg_id})
            del cands[:-10]
        return self._scores[session_name] >= SCORE_TRIGGER and self._can_run(session_name)

    def mark_round(self, session_name: str) -> bool:
        """每 10 轮到点：不加分，仅判断可否跑批."""
        return self._can_run(session_name)

    def _can_run(self, session_name: str) -> bool:
        if time.time() - self._last_run.get(session_name, 0) < MIN_INTERVAL_S:
            return False
        today = datetime.now(BJT).strftime('%Y-%m-%d')
        if today != self._day:
            self._day, self._day_batches = today, 0
        if self._day_batches >= self._daily_cap:
            safe_log('reflection', f'consolidate: daily cap ({self._daily_cap}) reached')
            return False
        return True

    # ── 批量层（1 次 LLM/批） ───────────────────────────────

    async def consolidate(self, session_name: str) -> list[dict]:
        """跑一批。返回 enriched lessons（可为空）。失败不推水位（下次幂等重试）."""
        popped: list[dict] = []
        try:
            watermarks = await self._state.load() or {}
            last_ts = float(watermarks.get(session_name, 0))
            recent = await self._tstore.get_recent_messages(session_name, SCAN_LIMIT)
            msgs = sorted(recent, key=lambda m: m.get('metadata', {}).get('timestamp_unix', 0))
            window = self._window_after(msgs, last_ts)
            if not window:
                return []

            self._last_run[session_name] = time.time()
            self._day_batches += 1

            candidates = popped = self._candidates.pop(session_name, [])
            score_reset = self._scores.get(session_name, 0)
            self._scores[session_name] = 0
            cand_text = '\n'.join(f"- {c['text']}" for c in candidates) or '(无纠正候选，例行回顾找 bot 自身错误)'
            conv = '\n'.join(
                m.get('metadata', {}).get('text', '')[:200] for m in window)
            active = await self._active_summary()

            from langbot_plugin.api.entities.builtin.provider.message import Message
            prompt = CONSOLIDATE_PROMPT.format(
                candidates=cand_text, conversation=conv[-6000:], active=active,
                error_types=", ".join(ERROR_TYPES))
            resp = await asyncio.wait_for(
                self._plugin.invoke_llm(
                    llm_model_uuid=self.ref_llm_model_uuid,
                    messages=[Message(role='user', content=prompt)]),
                timeout=self._llm_timeout)
            text = self._gen._extract_llm_text(resp).strip()

            new_ts = max(m.get('metadata', {}).get('timestamp_unix', 0) for m in window)
            if not text:
                self._requeue(session_name, candidates)
                safe_log('reflection', 'consolidate: empty response, watermark held')
                return []
            if text.upper().startswith('NONE'):
                safe_log('reflection', f'consolidate: skipped | {text[:80]}')
                await self._advance(session_name, new_ts)
                return []
            lessons = self._parse_lessons(text)
            if lessons is None:
                self._requeue(session_name, candidates)
                safe_log('reflection', f'consolidate: parse failed | {text[:60]}')
                return []
            src_ids = [c['msg_id'] for c in candidates if c.get('msg_id')]
            out = []
            for item in lessons[:MAX_LESSONS]:
                if not self._gen.validate_schema(item):
                    safe_log('reflection', 'consolidate: schema rejected item')
                    continue
                out.append(self._gen._enrich(item, source_msg_ids=src_ids))
            await self._advance(session_name, new_ts)
            safe_log('reflection',
                     f'consolidate: {len(out)} lessons (score={score_reset}, window={len(window)})')
            return out
        except asyncio.TimeoutError:
            self._requeue(session_name, popped)
            safe_log('reflection', 'consolidate: LLM timeout')
            return []
        except Exception as e:
            self._requeue(session_name, popped)
            safe_log('reflection', f'consolidate error: {type(e).__name__}: {str(e)[:120]}')
            return []

    def _requeue(self, session_name: str, candidates: list[dict]):
        merged = self._candidates.setdefault(session_name, [])
        merged.extend(c for c in candidates if c not in merged)
        del merged[:-10]

    @staticmethod
    def _window_after(msgs: list[dict], last_ts: float) -> list[dict]:
        """水位后增量 + 固定重叠区（msgs 须已按时间升序）."""
        if not msgs:
            return []
        idx = next((i for i, m in enumerate(msgs)
                    if m.get('metadata', {}).get('timestamp_unix', 0) > last_ts), None)
        if idx is None:
            return []
        start = max(0, idx - WINDOW_OVERLAP)
        return msgs[start:]

    @staticmethod
    def _parse_lessons(text: str) -> list[dict] | None:
        """兼容 JSON 数组/单对象/多对象。失败返回 None（不推水位），空数组返回 []."""
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            try:
                arr = json.loads(m.group(0))
                if isinstance(arr, list):
                    return [x for x in arr if isinstance(x, dict)]
            except json.JSONDecodeError:
                pass
        objs = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        parsed = []
        for o in objs:
            try:
                d = json.loads(o)
                if isinstance(d, dict):
                    parsed.append(d)
            except json.JSONDecodeError:
                continue
        return parsed or None

    async def _active_summary(self) -> str:
        try:
            items = await self._rstore.list_all(limit=50)
            lines = []
            for it in items:
                meta = it.get('metadata') or {}
                if meta.get('archived'):
                    continue
                lines.append(f"- {str(meta.get('scenario', ''))[:40]} (confirm={meta.get('confirm_count', 1)})")
            return '\n'.join(lines) or '(空)'
        except Exception:
            return '(读取失败，按空处理)'

    async def _advance(self, session_name: str, ts: float):
        try:
            wm = await self._state.load() or {}
            wm[session_name] = ts
            await self._state.save(wm)
        except Exception as e:
            safe_log('reflection', f'consolidate: watermark save error: {e}')
