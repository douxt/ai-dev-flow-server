#!/usr/bin/env python3
"""P1.5 一键全量测试 — diagnose + unit + integration.
用法:
  python3 run_all.py               # 全量
  python3 run_all.py --quick       # 快速（diagnose + unit + 结构 smoke）
  python3 run_all.py --scene N     # 单场景
  python3 run_all.py --json        # JSON 输出
  python3 run_all.py --cleanup     # 测试后清理 session 残留
退出码: 0=全通过, 1=有失败, 2=诊断阻断
"""
import sys, os, time, json, inspect, re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, PLUGIN_ROOT)

from lib import (
    unique_session, session_name_of, send_sync, extract_text, check, skip,
    reset_results, json_result,
    get_dump_last, get_summary_row, clear_cooldown, cleanup_session,
    wait_for_summary, BOT_QQ,
)

SESSION_ID = unique_session()
SESSION_NAME = session_name_of(SESSION_ID)
FILLER = "x" * 200  # 填充文本确保突破 1500 tail

QUICK = "--quick" in sys.argv
CLEANUP = "--cleanup" in sys.argv
FORCE = "--force" in sys.argv
SCENE_ONLY = None
for a in sys.argv:
    if a.startswith("--scene="):
        SCENE_ONLY = a.split("=")[1]
    elif a == "--scene":
        idx = sys.argv.index("--scene")
        if idx + 1 < len(sys.argv):
            SCENE_ONLY = sys.argv[idx + 1]

USE_JSON = "--json" in sys.argv


def log(msg):
    if not USE_JSON:
        print(msg)


# ═══════════════════════════════════════════════════════
# Stage 0: 诊断
# ═══════════════════════════════════════════════════════
def stage_0_diag():
    log("\n── 阶段 0: 诊断 ──")
    try:
        from diagnose import CHECKS, ERRORS as DE, WARNS as DW
        DE.clear()
        DW.clear()
        for fn in CHECKS:
            try:
                fn()
            except Exception as e:
                DE.append(f"{fn.__name__}: {e}")
        if DE:
            log(f"诊断阻断: {len(DE)} ERROR")
            if not FORCE:
                sys.exit(2)
        elif DW:
            log(f"诊断通过但有 {len(DW)} WARN")
        else:
            log("诊断全部 OK")
    except ImportError as e:
        log(f"诊断加载失败: {e}")


# ═══════════════════════════════════════════════════════
# Stage 1: 单元测试 (35 用例)
# ═══════════════════════════════════════════════════════
def stage_1_unit():
    log("\n── 阶段 1: 单元测试 ──")

    from tests import test_p1_compress as t

    test_classes = [
        ("TestSummaryDocument", t.TestSummaryDocument),
        ("TestSummaryStore", t.TestSummaryStore),
        ("TestItemText", t.TestItemText),
        ("TestSplitMessages", t.TestSplitMessages),
        ("TestParseSummaryResponse", t.TestParseSummaryResponse),
        ("TestShouldCompress", t.TestShouldCompress),
        ("TestListToBullets", t.TestListToBullets),
        ("TestBuildCompressionPrompt", t.TestBuildCompressionPrompt),
    ]

    for name, cls in test_classes:
        inst = cls()
        methods = sorted(
            [m for m in dir(inst) if m.startswith("test_")],
            key=lambda m: getattr(cls, m, None).__code__.co_firstlineno
            if hasattr(getattr(cls, m, None), "__code__") else 0,
        )
        for m_name in methods:
            method = getattr(inst, m_name)
            full = f"{name}.{m_name}"
            try:
                sig = inspect.signature(method)
                # 无参数 → 直接调用（所有测试已改为无 fixture）
                if len(sig.parameters) == 0:
                    method()
                    check(True, full)
                else:
                    skip(full, f"requires params: {list(sig.parameters.keys())}")
            except Exception as e:
                check(False, full, str(e)[:100])


# ═══════════════════════════════════════════════════════
# Stage 2: 集成测试
# ═══════════════════════════════════════════════════════

def scene_1_trigger():
    """发 8 条 @ 消息 → 压缩触发."""
    log("\n[1] 压缩触发")
    for i in range(8):
        resp = send_sync(SESSION_ID, [
            {"type": "Plain", "text": f"P1压缩测试第{i}条。{FILLER}"},
            {"type": "At", "target": BOT_QQ},
        ])
        if not extract_text(resp) and resp.get("error"):
            check(False, f"compress-msg-{i}", f"HTTP: {resp['error']}")
            return False
        time.sleep(1)
    row = wait_for_summary(SESSION_NAME, timeout=90)
    check(row is not None and (row[6] or 0) > 0, "compress-triggered",
          f"message_count={row[6] if row else 'N/A'}")
    return True


def scene_2_inject():
    """发送 @ → prompt dump 含新格式摘要."""
    log("\n[2] 摘要注入")
    send_sync(SESSION_ID, [
        {"type": "Plain", "text": "P1.5格式验证"},
        {"type": "At", "target": BOT_QQ},
    ])
    time.sleep(5)
    dump = get_dump_last()
    if not dump:
        check(False, "summary-in-prompt", "no prompt dump")
        return
    has_new = "─── 群聊背景" in dump
    no_old = "[上下文摘要]" not in dump
    check(has_new, "summary-marker-new", f"{'has' if has_new else 'missing'} ─── marker")
    check(no_old, "summary-marker-old-gone", f"{'has' if not no_old else 'no'} [上下文摘要]")

    # 在 [7] summary 段内验证 bullet
    s7 = dump.split("[7] summary:")
    if len(s7) >= 2:
        s7_text = s7[1].split("\n[")[0] if "\n[" in s7[1] else s7[1]
        has_bullet = "- " in s7_text
    else:
        has_bullet = "- " in dump
    check(has_bullet, "summary-bullets", f"{'has' if has_bullet else 'missing'} bullet lines")


def scene_3_facts_preserved():
    """先发秘密 → 再发填充 → 确保秘密进入 to_summarize."""
    log("\n[3] 信息保真")
    clear_cooldown(SESSION_NAME)
    # 先发含秘密数字的消息
    secret = "938271645"
    for i in range(5):
        send_sync(SESSION_ID, [
            {"type": "Plain", "text": f"保留测试{secret} 第{i}条。P1保留测试专用标记_{i}。"},
            {"type": "At", "target": BOT_QQ},
        ])
        time.sleep(3)
    # 再发填充，把秘密挤出 tail
    for i in range(8):
        send_sync(SESSION_ID, [
            {"type": "Plain", "text": f"P1填充消息第{i}条。{FILLER}"},
            {"type": "At", "target": BOT_QQ},
        ])
        time.sleep(1)
    row = wait_for_summary(SESSION_NAME, timeout=120)
    if not row:
        check(False, "facts-summary", "no summary after scene_3")
        return
    facts = str(row[2] or "")
    check(secret in facts, "facts-number", f"secret={'found' if secret in facts else 'missing'}")


def scene_4_tail_dedup():
    """timeline 不含已被压缩的早期消息."""
    log("\n[4] Tail 去重")
    dump = get_dump_last()
    if not dump:
        check(False, "tail-dedup", "no dump")
        return
    # scene_1 填充消息不在 timeline 中
    has_filler_in_timeline = "P1压缩测试第0条" in dump.split("[4] timeline")[1].split("[5]")[0] if "[4] timeline" in dump and "[5]" in dump else True
    has_filler_in_summary = "P1压缩测试" in dump.split("[7] summary")[1][:500] if "[7] summary:" in dump else False
    check(has_filler_in_summary, "tail-dedup-summary", "compressed msg in summary block")
    check(not has_filler_in_timeline, "tail-dedup-timeline", "compressed msg NOT in timeline")


def scene_5_cooldown():
    """cooldown_until 在压缩后被设置."""
    log("\n[5] 冷却期")
    row = get_summary_row(SESSION_NAME)
    if not row:
        check(False, "cooldown-row", "no summary row")
        return
    cooldown = row[8] or 0
    updated = row[7] or 0
    check(cooldown > 0, "cooldown-set", f"cooldown_until={cooldown}")
    # cooldown ≈ updated_at + 600s（±120s 容差）
    expected = updated + 600
    ok_range = abs(cooldown - expected) < 120
    check(ok_range, "cooldown-approx", f"cooldown={cooldown} updated={updated} diff={cooldown - updated:.0f}s")


def scene_6_disabled():
    """关闭压缩回归 — 需手动操作，skip."""
    skip("compress-disabled", "需要手动设置 compression_enabled=false")


def scene_7_second_compress():
    """二次压缩: clear_cooldown → 再发 → message_count 增加."""
    log("\n[7] 二次压缩")
    clear_cooldown(SESSION_NAME)
    row_before = get_summary_row(SESSION_NAME)
    count_before = row_before[6] if row_before else 0
    for i in range(10):
        send_sync(SESSION_ID, [
            {"type": "Plain", "text": f"P1二次压缩第{i}条。{FILLER}"},
            {"type": "At", "target": BOT_QQ},
        ])
        time.sleep(1)
    row_after = wait_for_summary(SESSION_NAME, timeout=120)
    count_after = row_after[6] if row_after else 0
    check(count_after > count_before, "second-compress-triggered",
          f"msg_count {count_before} → {count_after}")
    # 秘密数字仍在
    facts = str(row_after[2] or "") if row_after else ""
    check("938271645" in facts, "second-compress-facts",
          f"secret={'preserved' if '938271645' in facts else 'LOST'}")


SCENES = {
    "1": scene_1_trigger,
    "2": scene_2_inject,
    "3": scene_3_facts_preserved,
    "4": scene_4_tail_dedup,
    "5": scene_5_cooldown,
    "6": scene_6_disabled,
    "7": scene_7_second_compress,
}


def scene_quick_smoke():
    """--quick smoke: 发 1 条 @ → 断言 dump 结构完整."""
    log("\n[quick-smoke] 结构验证")
    send_sync(SESSION_ID, [
        {"type": "Plain", "text": "P1.5 quick smoke"},
        {"type": "At", "target": BOT_QQ},
    ])
    time.sleep(3)
    dump = get_dump_last()
    if not dump:
        check(False, "smoke-dump", "no dump")
        return
    check("[1] time:" in dump, "smoke-struct-1", "time section")
    check("[4] timeline" in dump, "smoke-struct-4", "timeline section")
    check("[7] summary:" in dump, "smoke-struct-7", "summary section")


def stage_2_integration():
    log(f"\n── 阶段 2: 集成测试 (session={SESSION_ID}) ──")
    if QUICK:
        scene_quick_smoke()
        return
    if SCENE_ONLY:
        fn = SCENES.get(SCENE_ONLY)
        if fn:
            try:
                fn()
            except Exception as e:
                check(False, f"scene_{SCENE_ONLY}", str(e)[:100])
        else:
            log(f"未知场景: {SCENE_ONLY}，可选: {list(SCENES.keys())}")
        return
    for key in sorted(SCENES.keys()):
        fn = SCENES[key]
        try:
            fn()
        except Exception as e:
            check(False, f"scene_{key}", str(e)[:100])


# ═══════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════
def main():
    start = time.time()

    if not SCENE_ONLY:
        stage_0_diag()

    stage_1_unit()

    try:
        stage_2_integration()
    finally:
        if CLEANUP:
            cleanup_session(SESSION_NAME)

    elapsed = time.time() - start
    result = json_result()
    log(f"\n{'─' * 24}")
    log(f"总结果: {result['passed']} 通过, {result['failed']} 失败, {result['skipped']} 跳过 ({elapsed:.0f}s)")

    if USE_JSON:
        result["elapsed"] = elapsed
        result["session_id"] = SESSION_ID
        print(json.dumps(result, ensure_ascii=False))

    sys.exit(1 if result["failed"] > 0 else 0)


if __name__ == "__main__":
    main()
