# PHP 集成测试

> 技术栈模块 — `tags: php`。通用分层策略见 `knowledge/10-测试分层策略.md`
> 适用：PHP 5.4+ 遗留项目，无 Composer/无测试框架

## 工具矩阵

| 工具 | 用途 | 依赖 |
|------|------|------|
| **裸 PHP `assert()`** | 断言 + shell runner，零依赖起步 | PHP 内置 |
| **simpleunit** | 轻量测试框架（PHP 5.4+，下载即用） | 无 Composer |
| **Docker Compose** | 隔离执行环境（`docker compose run --rm`） | Docker |
| **PHP `ob_*` 函数** | 捕获输出作为快照 | PHP 内置 |
| **PHP `PDO` 事务** | DB 集成测试（begin → test → rollback） | PHP 内置 |

## 模式 A：API 探针测试（HTTP + assert）

适用：后端 API 端点集成验证。

```php
<?php
// tests/integration/api/test_paint_list.php
define('IN_ECS', true);

// 构造请求
$_GET = ['action' => 'paint_list_by_sale', 'sale_id' => '40462'];
$_SESSION = ['user_id' => '124'];

ob_start();
require __DIR__ . '/../../../store_api.php';
$output = ob_get_clean();

$result = json_decode($output, true);

// 断言 API 契约
assert($result['code'] === 0, 'API 返回成功码');
assert(is_array($result['list']), 'list 字段为数组');
assert(count($result['list']) > 0, 'list 非空');
// 禁止恒真断言：assert($result['code'] >= 0) 是无效断言

echo "PASS: test_paint_list\n";
```

### Docker 隔离执行

```bash
# 启动服务
docker compose up -d

# 在容器内跑测试
docker compose run --rm php php -d assert.active=1 /app/tests/integration/api/test_paint_list.php

# 清理
docker compose down
```

### Shell Runner 批量运行

```bash
#!/bin/bash
# tests/integration/run.sh
set -e
PASS=0
FAIL=0

for test in tests/integration/api/test_*.php; do
    echo -n "  $test ... "
    if php -d assert.active=1 "$test"; then
        ((PASS++))
    else
        ((FAIL++))
        echo "  FAIL"
    fi
done

echo "---"
echo "$PASS passed, $FAIL failed"
exit $FAIL
```

## 模式 B：数据库集成测试（事务回滚）

适用：测试数据库操作但保持数据隔离。

```php
<?php
// tests/integration/db/test_order_insert.php
define('IN_ECS', true);
require_once __DIR__ . '/../../../init.php';

$db = $GLOBALS['db'];

// BEGIN → 测试 → ROLLBACK
$db->query('BEGIN');
try {
    // 测试操作
    $db->query("INSERT INTO orders (id, order_sn, status) VALUES (99999, 'TEST-001', 'new')");
    $row = $db->getRow("SELECT * FROM orders WHERE id = 99999");

    assert($row !== false, '插入后可查到');
    assert($row['status'] === 'new', '状态正确');

    echo "PASS: test_order_insert\n";
} finally {
    $db->query('ROLLBACK');
}
```

## 模式 C：快照集成测试（Golden Master）

适用：批量输入→输出对比，覆盖已有 API。

```php
<?php
// tests/integration/snapshot/test_api_snapshot.php
define('IN_ECS', true);

$snapshot_file = __DIR__ . '/snapshots/paint_list_by_sale.json';
$saved = json_decode(file_get_contents($snapshot_file), true);

$_GET = $saved['input'];
ob_start();
require __DIR__ . '/../../../store_api.php';
$output = ob_get_clean();
$current = json_decode($output, true);

// 对比快照（排除时间戳等非确定性字段）
unset($current['server_time']);
assert($current === $saved['output'], '快照匹配');
echo "PASS: test_api_snapshot\n";
```

**快照更新**：行为有意变更后，重新录制快照文件。

## 模式 D：simpleunit 结构化测试

```php
<?php
// tests/integration/simpleunit/test_store_api.php
require_once __DIR__ . '/../../lib/simpleunit/TestSuite.php';

class StoreApiTest extends TestSuite {
    function testPaintList() {
        $_GET = ['action' => 'paint_list_by_sale', 'sale_id' => '40462'];
        ob_start();
        require ROOT_PATH . 'store_api.php';
        $output = ob_get_clean();
        $result = json_decode($output, true);

        $this->assertEquals(0, $result['code']);
        $this->assertArrayHasKey('list', $result);
    }

    function testUnauthorized() {
        $_GET = ['action' => 'paint_delete', 'paint_id' => '1'];
        $_SESSION = []; // 未登录
        ob_start();
        require ROOT_PATH . 'store_api.php';
        $output = ob_get_clean();
        $result = json_decode($output, true);

        $this->assertNotEquals(0, $result['code']);
    }
}

(new StoreApiTest())->run();
```

## 渐进策略

1. 从 1 个 API 探针开始（模式 A），不用装任何工具
2. 2-3 个探针后引入 shell runner 批量跑
3. DB 操作引入事务回滚（模式 B）
4. 需要结构化输出时升级到 simpleunit（模式 D）
5. 存量 PHP E2E 不动，新功能走决策树选测试层级
