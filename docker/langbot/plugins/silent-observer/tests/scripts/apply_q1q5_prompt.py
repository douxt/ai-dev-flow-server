#!/usr/bin/env python3
"""Q1-Q5【讨论质量】段写入 LangBot pipeline 主 prompt（会话质量线短期包）.

执行通道：本地 Write → scp → docker cp 进 langbot 容器 → /app/.venv/bin/python 运行
用法：
  python apply_q1q5_prompt.py apply             # 幂等插入 + 备份 + json_set 精确更新
  python apply_q1q5_prompt.py verify <v3.md>    # DB 内容与单一事实源文件逐字节 diff + 四锚自查
  python apply_q1q5_prompt.py rollback <bak.json>  # 从本次备份恢复整 config

幂等锚：【讨论质量】段头存在即 skip。
段头在但内容残缺=中途失败，人工核对后 rollback 或删段重跑。
禁整 JSON 覆写（该库历史上整包覆写崩过三次，见 langbot-config-update-safety 记忆），
只用 json_set 更新目标字段，其余键原样保留。
生效前提：pipeline 配置启动时加载一次——apply 后必须重启 langbot 容器。
"""
import json
import os
import sqlite3
import sys
from datetime import datetime

DB_PATH = "/app/data/langbot.db"
PIPELINE_UUID = "dc0ff402-edc3-4dab-8054-d2a855241dea"
JSON_PATH = "$.ai.local-agent.prompt[0].content"
BACKUP_DIR = "/app/data/prompt_backups"

BASE_ANCHOR = "你是机器豆。"  # 基底校验：人设首行必须在位
INSERT_BEFORE = "[工具]"  # 插入点：人设段之后、[工具]段之前
SECTION_HEAD = "【讨论质量】"

# 教训 #23：新增 prompt 文本禁止含以下测试断言锚
FORBIDDEN_ANCHORS = ["触发条件：", "先前经验", "仅供你内部理解", "旁白口吻"]

SECTION = """【讨论质量】
1 证据优先：有人说你错了，先对照记忆与检索结果。对方没给出新事实时不改结论，回复格式=「我这边记录支持X，除非你有新证据」；新证据出现才更新。与既有沉淀条目冲突时，以本条证据规则为准。
2 先审前提：问题里带预设（时间/人物/"你说过"）先核对；查无此据就先点破预设再答，不顺着虚假前提往下说。
3 可以不知道：没把握就用你的语气说不确定（短句，可冷幽默，例：「这超出我的存档了」）。硬猜比弃权伤害大；禁止编造记忆。
4 从不说：「作为AI助手」/道歉客套/安慰模板/排比长文/群友称谓"你们"。
  以下示例只示范语气节奏——其中人名/日期/事件是占位内容，禁止当记忆引用、禁止复读：
  - 「已归档。下次再考：小鹿，7月20号，领养橘猫——时间人物都齐了。」
  - 「小鹿。8月29号你考过一回，当时你给的答案就是这个，我归档了。这题现在稳的。」
  - 「没工资，发不了。倒是可以每月给你发一条"已记录"，这个免费。」
  - 「重复了一遍，是怕我忘了自己说过什么吗。记性还行，不用复习。」
5 真人不排座次：让你点评/比较/排名群里真人时，只复述公开说过的事，不评高低不站队，「这个我不排」是合法回复。"""


def _content(db):
    row = db.execute(
        "SELECT config FROM legacy_pipelines WHERE uuid=?", (PIPELINE_UUID,)
    ).fetchone()
    if not row:
        sys.exit("ERROR: pipeline not found")
    return json.loads(row[0])["ai"]["local-agent"]["prompt"][0]["content"]


def apply():
    for a in FORBIDDEN_ANCHORS:
        assert a not in SECTION, f"条款文本含测试断言锚「{a}」，拒写"
    db = sqlite3.connect(DB_PATH)
    content = _content(db)
    assert BASE_ANCHOR in content, "基底人设首行缺失——基底不对，中止"
    assert INSERT_BEFORE in content, "[工具] 段缺失——插入点不存在，中止"
    if SECTION_HEAD in content:
        print("SKIP: 【讨论质量】段已在位（幂等）")
        return
    new = content.replace(INSERT_BEFORE, SECTION + "\n\n" + INSERT_BEFORE, 1)

    cfg_raw = db.execute(
        "SELECT config FROM legacy_pipelines WHERE uuid=?", (PIPELINE_UUID,)
    ).fetchone()[0]
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(BACKUP_DIR, f"q1q5_{ts}.json")
    with open(bak, "w") as f:
        f.write(cfg_raw)

    db.execute(
        "UPDATE legacy_pipelines SET config = json_set(config, ?, ?) WHERE uuid = ?",
        (JSON_PATH, new, PIPELINE_UUID),
    )
    db.commit()
    after = _content(db)
    assert after == new, "写后回读不一致"
    print(f"APPLIED. backup={bak}  len={len(content)}->{len(new)}")
    print("REMINDER: 重启 langbot 容器后才生效（配置启动时加载一次）")


def verify(path):
    db = sqlite3.connect(DB_PATH)
    content = _content(db)
    with open(path) as f:
        expect = f.read()
    if content == expect.rstrip("\n"):
        print("VERIFY OK: DB 内容与事实源文件逐字节一致")
    else:
        print("VERIFY FAILED: diff")
        for i, (a, b) in enumerate(zip(content, expect.rstrip("\n"))):
            if a != b:
                print(f"  first diff at {i}: db={a!r} file={b!r}")
                break
        sys.exit(1)


def rollback(bak_path):
    db = sqlite3.connect(DB_PATH)
    with open(bak_path) as f:
        cfg_raw = f.read()
    json.loads(cfg_raw)  # 合法性自检
    db.execute(
        "UPDATE legacy_pipelines SET config = ? WHERE uuid = ?",
        (cfg_raw, PIPELINE_UUID),
    )
    db.commit()
    print(f"ROLLED BACK from {bak_path}（仍需重启 langbot）")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "apply":
        apply()
    elif cmd == "verify" and len(sys.argv) > 2:
        verify(sys.argv[2])
    elif cmd == "rollback" and len(sys.argv) > 2:
        rollback(sys.argv[2])
    else:
        print(f"Usage: {sys.argv[0]} apply | verify <v3.md> | rollback <bak.json>")
        sys.exit(1)
