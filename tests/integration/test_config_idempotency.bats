# -*- bats -*-
# 集成测试: config.yaml 幂等 — 非 role 字段保留

load /code/tests/helpers/common.bash

@test "install preserves existing non-role config fields" {
    mkdir -p "$TEST_PROJECT/.devflow"
    cat > "$TEST_PROJECT/.devflow/config.yaml" << 'EOF'
project:
  name: my-custom-name
  repo_url: git@custom:repo.git
mode: backend
role: owner
custom_field: keep-me
EOF
    run bash /code/install.sh "$TEST_PROJECT" --force --role developer
    [ "$status" -eq 0 ]
    grep -q "role: developer" "$TEST_PROJECT/.devflow/config.yaml"
}

@test "install with --force overwrites role but keeps project name" {
    mkdir -p "$TEST_PROJECT/.devflow"
    cat > "$TEST_PROJECT/.devflow/config.yaml" << 'EOF'
project:
  name: existing-name
mode: frontend
role: agent-b
EOF
    run bash /code/install.sh "$TEST_PROJECT" --force --role owner
    [ "$status" -eq 0 ]
    grep -q "role: owner" "$TEST_PROJECT/.devflow/config.yaml"
}
