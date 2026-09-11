#!/usr/bin/env bats
# 薄封装：断言主体在零依赖自测脚本里（无需 docker / 网络，本机亦可运行）
#   bash tests/integration/health_check_selftest.sh

setup() {
    REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
    SELFTEST="$REPO_ROOT/tests/integration/health_check_selftest.sh"
}

@test "health-check.sh 零依赖自测全部通过" {
    run bash "$SELFTEST"
    echo "$output"
    [ "$status" -eq 0 ]
}
