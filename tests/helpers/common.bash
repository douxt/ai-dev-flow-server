# common.bash — 集成测试共享 setup/teardown
setup() {
    TEST_HOME=$(mktemp -d)
    TEST_PROJECT="$TEST_HOME/project"
    mkdir -p "$TEST_PROJECT"
    cd "$TEST_PROJECT"
    git init
    git config user.email "test@devflow.test"
    git config user.name "DevFlow Test"
    git commit --allow-empty -m "init"
    export HOME="$TEST_HOME"
}
teardown() {
    [ -n "${TEST_HOME:-}" ] && [ -d "$TEST_HOME" ] && rm -rf "$TEST_HOME"
}
