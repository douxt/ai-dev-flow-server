#!/bin/bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

run_tests() {
    local image="$1"; shift
    echo "=== $image ==="
    docker build -t "devflow-test:$image" -f "$SCRIPT_DIR/Dockerfile.$image" "$SCRIPT_DIR"
    docker run --rm -v "$REPO_ROOT:/code" "devflow-test:$image" "$SCRIPT_DIR"/unit/*.bats "$SCRIPT_DIR"/integration/*.bats "$@"
}

run_tests alpine "$@"
run_tests ubuntu "$@"
