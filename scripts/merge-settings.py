#!/usr/bin/env python3
"""merge-settings.py — 智能合并 settings.local.json 与模板

用法: python3 merge-settings.py <existing> <template> <output>

合并策略:
- hooks.PreToolUse / hooks.PostToolUse: 按 matcher + hook 文件名(basename)匹配
  - 模板新增的 hook → 注入到对应 matcher 的首位
  - 用户已有的 hook → 保留原位
  - 用户自定义的 matcher → 完整保留
- 非 hooks 字段: 已有值优先（用户自定义不覆盖）
"""

import json
import os
import sys


def hook_basename(hook):
    """提取 hook command 路径的文件名，用于跨路径匹配。"""
    cmd = hook.get("command", "")
    return os.path.basename(cmd)


def merge_hook_groups(existing_groups, template_groups):
    """合并一组 hook（PreToolUse 或 PostToolUse）。

    existing_groups / template_groups 都是 [{"matcher": "...", "hooks": [...]}, ...] 格式。
    返回合并后的列表。
    """
    existing_by_matcher = {g["matcher"]: g.get("hooks", []) for g in existing_groups}
    template_by_matcher = {g["matcher"]: g.get("hooks", []) for g in template_groups}

    result = []

    # 先处理模板中的 matcher（保持模板顺序）
    for tgroup in template_groups:
        matcher = tgroup["matcher"]
        existing_hooks = existing_by_matcher.get(matcher, [])
        template_hooks = template_by_matcher.get(matcher, [])

        existing_basenames = {hook_basename(h) for h in existing_hooks}

        merged = list(existing_hooks)  # 用户已有 hook 保留原位

        # 模板新增的 hook 插入首位（倒序遍历保证最终顺序与模板一致）
        for th in reversed(template_hooks):
            if hook_basename(th) not in existing_basenames:
                merged.insert(0, th)

        result.append({"matcher": matcher, "hooks": merged})

    # 追加用户自定义的 matcher（模板中没有的）
    for egroup in existing_groups:
        matcher = egroup["matcher"]
        if matcher not in template_by_matcher:
            result.append(egroup)

    return result


def main():
    if len(sys.argv) != 4:
        print(f"用法: {sys.argv[0]} <existing> <template> <output>", file=sys.stderr)
        sys.exit(1)

    existing_path = sys.argv[1]
    template_path = sys.argv[2]
    output_path = sys.argv[3]

    with open(existing_path) as f:
        existing = json.load(f)
    with open(template_path) as f:
        template = json.load(f)

    # 合并 hooks（仅处理模板中存在的 hook 类型）
    if "hooks" in template:
        existing.setdefault("hooks", {})
        for hook_type in ("PreToolUse", "PostToolUse"):
            if hook_type in template["hooks"]:
                eg = existing["hooks"].get(hook_type, [])
                tg = template["hooks"].get(hook_type, [])
                existing["hooks"][hook_type] = merge_hook_groups(eg, tg)

    with open(output_path, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    main()
