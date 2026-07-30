# PHP 遗留代码特征测试

> 技术栈模块 — 按 `tags: php` 部署。
> 通用流程见 `knowledge/11-遗留代码特征测试.md`

## 模式 A：HTTP 探针 + JSON 快照（推荐）

适用：后端 API 端点（`store_api.php?action=` 模式）

### 通用探针模板

```php
<?php
// tests/characterization/ticket-001-paint_list.php
define('IN_ECS', true);
require_once __DIR__ . '/../../../init.php';

// 1. 准备输入
$sale_id = '40462';
$user_id = '124';

// 2. 调用被测 API
$_GET['action'] = 'paint_list_by_sale';
$_GET['sale_id'] = $sale_id;
ob_start();
require ROOT_PATH . 'store_api.php';
$output = ob_get_clean();

// 3. 输出为快照
$snapshot = [
    'input' => ['sale_id' => $sale_id, 'user_id' => $user_id],
    'output' => json_decode($output, true),
    'captured_at' => date('Y-m-d H:i:s'),
];
file_put_contents(
    __DIR__ . '/snapshots/ticket-001-paint_list.json',
    json_encode($snapshot, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)
);

echo "Snapshot saved.\n";
```

### 验证测试

```php
<?php
// tests/characterization/ticket-001-paint_list_test.php
$snapshotFile = __DIR__ . '/snapshots/ticket-001-paint_list.json';
$snapshot = json_decode(file_get_contents($snapshotFile), true);

// 重新执行
$_GET['action'] = 'paint_list_by_sale';
$_GET['sale_id'] = $snapshot['input']['sale_id'];
ob_start();
require ROOT_PATH . 'store_api.php';
$currentOutput = json_decode(ob_get_clean(), true);

// 对比
assert($currentOutput === $snapshot['output'], 'API 行为已变更');
echo "✅ 特征测试通过\n";
```

## 模式 B：DB 状态对比

适用：有数据库副作用的操作（INSERT/UPDATE/DELETE）

```php
<?php
// 记录执行前的 DB 状态
$before = $db->getAll("SELECT * FROM orders WHERE sale_id='40462'");

// 执行被测操作
$_GET['action'] = 'paint_create';
// ... 参数准备 + 执行

// 记录执行后的 DB 状态
$after = $db->getAll("SELECT * FROM orders WHERE sale_id='40462'");

// 对比行数变化
$diff = count($after) - count($before);
echo "Rows changed: $diff\n";
// 手动确认是否符合预期
```

### Docker 环境探针

```bash
# 特征测试前验证环境
docker exec fa56-php-php-fpm-1 php -r "echo 'OK';" 2>/dev/null || echo "[infra] PHP 容器不可用"
```

## 关键约束

- **PHP 5.4 兼容**：禁用 `??`、`[]` 短数组、`::class`
- 语法检查：`docker exec fa56-php-php-fpm-1 php -l /var/www/html/proc/tests/characterization/<文件>`
- 数据库：用 `$GLOBALS['db']->getOne()`、`getAll()`，不混用 `mysqli_*`
- 探针放 `proc/tests/characterization/`（UMES3 约定），快照放同级 `snapshots/`
