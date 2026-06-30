# -*- bats -*-
# 集成测试: scheduler 输出

load /code/tests/helpers/common.bash

@test "--scheduler systemd outputs systemctl enable" {
    run bash /code/install.sh "$TEST_PROJECT" --mode backend --scheduler systemd
    [ "$status" -eq 0 ]
    [[ "$output" =~ systemctl ]]
}

@test "--scheduler cron outputs crontab" {
    run bash /code/install.sh "$TEST_PROJECT" --mode backend --scheduler cron
    [ "$status" -eq 0 ]
    [[ "$output" =~ crontab ]]
}

@test "--scheduler external outputs docker exec hint" {
    run bash /code/install.sh "$TEST_PROJECT" --mode backend --scheduler external
    [ "$status" -eq 0 ]
    [[ "$output" =~ 宿主机|docker\ exec|external ]]
}

@test "--scheduler none outputs no scheduler instructions" {
    run bash /code/install.sh "$TEST_PROJECT" --mode backend --scheduler none
    [ "$status" -eq 0 ]
    ! [[ "$output" =~ systemctl|crontab ]] || true
}

@test "--skip-root suppresses root section" {
    run bash /code/install.sh "$TEST_PROJECT" --mode backend --skip-root
    [ "$status" -eq 0 ]
    ! [[ "$output" =~ root.*段|以.*root.*执行 ]] || true
}

@test "--user flag sets cron user" {
    run bash /code/install.sh "$TEST_PROJECT" --mode backend --scheduler cron --user devops
    [ "$status" -eq 0 ]
    [[ "$output" =~ devops ]]
}
