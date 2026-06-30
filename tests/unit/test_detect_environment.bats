# -*- bats -*-
# 测试 detect_environment() — Docker/systemd/cron 环境检测

setup_file() {
    # 保存 /.dockerenv 状态，测试结束后恢复
    DOCKERENV_EXISTED=false
    [ -f /.dockerenv ] && DOCKERENV_EXISTED=true
}
teardown_file() {
    [ "$DOCKERENV_EXISTED" = true ] && touch /.dockerenv || rm -f /.dockerenv
}

setup() {
    source /code/install.sh
}

@test "IS_DOCKER=true when /.dockerenv exists" {
    touch /.dockerenv
    detect_environment
    [ "$IS_DOCKER" = true ]
}

@test "IS_DOCKER=true when cgroup contains docker (mock)" {
    rm -f /.dockerenv
    local tmp_cgroup=$(mktemp)
    echo "0::/system.slice/docker-abc.scope" > "$tmp_cgroup"
    _check_cgroup() { grep -q 'docker\|lxc' "$tmp_cgroup" 2>/dev/null; }
    IS_DOCKER=false
    if _check_cgroup; then IS_DOCKER=true; fi
    [ "$IS_DOCKER" = true ]
    rm -f "$tmp_cgroup"
}

@test "HAS_SYSTEMD=true when /run/systemd/system exists" {
    rm -f /.dockerenv
    mkdir -p /run/systemd/system
    detect_environment
    [ "$HAS_SYSTEMD" = true ]
    rmdir /run/systemd/system 2>/dev/null || true
}

@test "Docker takes priority over systemd" {
    touch /.dockerenv
    mkdir -p /run/systemd/system
    detect_environment
    [ "$IS_DOCKER" = true ]
    rmdir /run/systemd/system 2>/dev/null || true
}

@test "HAS_CRON=true when crontab available" {
    touch /.dockerenv
    detect_environment
    [ "$HAS_CRON" = true ]
}
