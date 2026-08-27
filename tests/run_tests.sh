#!/bin/bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

run_tests() {
    local image="$1"; shift
    echo "=== $image ==="
    docker build -t "devflow-test:$image" -f "$SCRIPT_DIR/Dockerfile.$image" "$SCRIPT_DIR"
    # tests/hooks 含 stdin JSON 测试——依赖 GNU grep -oP（busybox 不支持），仅 ubuntu 镜像跑
    local hook_glob=""
    [ "$image" = "ubuntu" ] && hook_glob="tests/hooks/*.bats"
    docker run --rm --entrypoint bash -v "$REPO_ROOT:/code" "devflow-test:$image" \
        -c "cd /code && bats tests/unit/*.bats tests/integration/*.bats $hook_glob $*"
}

run_tests alpine "$@"
run_tests ubuntu "$@"
