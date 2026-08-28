"""补丁脚本自测：在容器导出的基线副本上验证幂等、可编译、关键行、import 完整。

基线来源（必须 langbot 容器——langbot-plugin 那份是死代码副本）：
    docker exec langbot cat /app/src/langbot/pkg/platform/sources/aiocqhttp.py > baselines/aiocqhttp.py
    docker exec langbot cat /app/src/langbot/pkg/pipeline/process/process.py > baselines/process.py
    docker exec langbot cat /app/src/langbot/pkg/pipeline/monitoring_helper.py > baselines/monitoring_helper.py
运行：python3 test_patches.py
"""
import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
BASELINES = HERE / 'baselines'

CONTAINER_PATHS = {
    'aiocqhttp.py': '/app/src/langbot/pkg/platform/sources/aiocqhttp.py',
    'process.py': '/app/src/langbot/pkg/pipeline/process/process.py',
    'monitoring_helper.py': '/app/src/langbot/pkg/pipeline/monitoring_helper.py',
}

CASES = {
    'aiocqhttp.py': ('patch_forward_speaker.py', 'FWD-SPEAKER-PATCH',
                     ['ForwardMessageNode(', "bot.get_msg(message_id=msg.data['id'])",
                      '_fhead = ', 'asyncio.wait_for', '[引用消息获取失败]']),
    'process.py': ('patch_event_loop_blocks.py', 'EVL-BLOCK-PATCH',
                   ['run_in_executor', 'message_text[:500]']),
    'monitoring_helper.py': ('patch_event_loop_blocks.py', 'EVL-BLOCK-PATCH',
                             ['run_in_executor']),
}


def run_case(baseline, script, marker, asserts):
    src = BASELINES / baseline
    if not script.exists():
        sys.exit(f'FATAL: {script} missing')
    if not src.exists():
        print(f'SKIP {baseline}: baselines/{baseline} 未导出')
        return
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / baseline
        shutil.copyfile(src, work)
        cmd = [sys.executable, str(script)]
        if script.name == 'patch_event_loop_blocks.py':
            cmd.append(f'--map={CONTAINER_PATHS[baseline]}={work}')
            other = [v for k, v in CONTAINER_PATHS.items() if k != baseline and 'aiocqhttp' not in k]
            for o in other:
                cmd.append(f'--skip={o.rsplit("/", 1)[-1]}')
        else:
            cmd.append(str(work))
        r1 = subprocess.run(cmd, capture_output=True, text=True)
        assert r1.returncode == 0, f'{baseline} apply failed: {r1.stdout}{r1.stderr}'
        r2 = subprocess.run(cmd, capture_output=True, text=True)
        assert r2.returncode == 0 and 'skip' in r2.stdout, f'{baseline} 不幂等: {r2.stdout}'

        patched = work.read_text()
        assert marker in patched, f'{baseline}: marker 缺失'
        for a in asserts:
            assert a in patched, f'{baseline}: 断言缺失 {a}'
        tree = ast.parse(patched)  # 隐式 compile 校验
        imported = {n.name.split('.')[0] for x in ast.walk(tree)
                    if isinstance(x, ast.Import) for n in x.names}
        used_mods = {x.value.id for x in ast.walk(tree)
                     if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name)}
        missing = (used_mods & {'asyncio', 'time', 'json'}) - imported
        assert not missing, f'{baseline}: 使用未导入 {missing}'
        print(f'OK {baseline}')


if __name__ == '__main__':
    for b, (s, m, a) in CASES.items():
        run_case(b, HERE / s, m, a)
    print('ALL PATCH SELFTESTS PASSED')
