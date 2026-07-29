#!/usr/bin/env python3
"""verify-fix.sh 的结果解析辅助脚本，避免 shell 内嵌 Python 的引号地狱。"""
import sys, json

def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    data = json.loads(sys.stdin.read())
    cmd = sys.argv[1]

    if cmd == "check":
        sys.exit(0 if data.get("failed", 1) == 0 else 1)
    elif cmd == "summary":
        passed = data.get("passed", 0)
        total = data.get("total", 0)
        elapsed = data.get("elapsed_s", 0)
        failed = data.get("failed", 0)
        if failed == 0:
            print(f"✅ {passed}/{total} 通过 ({elapsed}s)")
        else:
            for r in data.get("results", []):
                if r["status"] == "FAIL":
                    print(f"  ❌ {r['name']}: {r['detail']}")
            print(f"\n❌ {failed}/{total} 失败 ({elapsed}s)")
    elif cmd == "passed":
        print(data.get("passed", 0))
    elif cmd == "total":
        print(data.get("total", 0))
    elif cmd == "elapsed":
        print(data.get("elapsed_s", 0))

if __name__ == "__main__":
    main()
