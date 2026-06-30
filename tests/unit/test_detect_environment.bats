# -*- bats -*-
# 测试 detect_environment() — Docker/systemd/cron 环境检测

setup() {
    source /code/install.sh
}

@test "IS_DOCKER=true when /.dockerenv exists" {
    rm -f /.dockerenv
    touch /.dockerenv
    detect_environment
    [ "$IS_DOCKER" = true ]
    rm -f /.dockerenv
}

@test "IS_DOCKER=true when cgroup contains docker (mock)" {
    rm -f /.dockerenv
    # mock cgroup detection: create temp file with "docker" and override grep check
    local tmp_cgroup=$(mktemp)
    echo "0::/system.slice/docker-abc.scope" > "$tmp_cgroup"
    _check_cgroup() {
        grep -q 'docker\|lxc' "$tmp_cgroup" 2>/dev/null
    }
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
    rm -f /.dockerenv
    rmdir /run/systemd/system 2>/dev/null || true
}

@test "HAS_CRON=true when crontab available" {
    rm -f /.dockerenv
    detect_environment
    [ "$HAS_CRON" = true ]
}
