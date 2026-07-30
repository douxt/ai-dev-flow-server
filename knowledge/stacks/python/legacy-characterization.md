# Python 遗留代码特征测试

> 技术栈模块 — 按 `tags: python` 部署。
> 通用流程见 `knowledge/11-遗留代码特征测试.md`

## 模式 A：pytest-syrupy 快照（推荐）

```bash
pip install syrupy
```

```python
# tests/characterization/test_ticket_001_order_calc.py
import pytest
from app.services.order import calc_order_total

def test_calc_order_total_standard(snapshot):
    """特征测试：锁 cal_order_total 当前行为"""
    order = {"items": [{"price": 100, "qty": 2}], "discount": 0.1}
    result = calc_order_total(order)
    assert result == snapshot(name="standard_order")

def test_calc_order_total_empty(snapshot):
    assert calc_order_total({"items": []}) == snapshot(name="empty_order")

def test_calc_order_total_negative_discount(snapshot):
    assert calc_order_total({"items": [{"price": 50}], "discount": -0.2}) == snapshot(name="negative_discount")
```

首次运行：
```bash
pytest tests/characterization/ --snapshot-update
```

## 模式 B：API 响应快照（Django/Flask/FastAPI）

```python
# tests/characterization/test_ticket_001_api.py
import json
from django.test import Client

def test_paint_list_api_current_behavior(snapshot):
    client = Client()
    response = client.get('/store_api.php', {
        'action': 'paint_list_by_sale',
        'sale_id': '40462',
    })
    snapshot_data = {
        'status_code': response.status_code,
        'body': json.loads(response.content),
    }
    assert snapshot_data == snapshot(name="paint_list_api")

def test_paint_create_with_minimal_params(snapshot):
    client = Client()
    response = client.post('/store_api.php', {
        'action': 'paint_create',
        'sale_id': '40462',
        'user_id': '124',
        'items': json.dumps([{'material_id': 'M001', 'qty': 1}]),
    })
    assert {
        'status_code': response.status_code,
        'body': json.loads(response.content),
    } == snapshot(name="paint_create_minimal")
```

## 模式 C：Approval Mode

行为有意变更时，审查 diff 后批准新快照：

```bash
# 查看变更
pytest tests/characterization/ --snapshot-diff

# 批准变更（更新快照）
pytest tests/characterization/ --snapshot-update
git add tests/characterization/__snapshots__/
git commit -m "reconcile: update characterization snapshots for paint_create API change"
```

## 元验证

```python
def test_safety_net_effective():
    """特征测试完成后：改代码 → 确认变红 → 恢复 → 确认变绿"""
    import app.services.order as mod

    original = mod.calc_order_total

    # 注入变更
    def broken_version(order):
        return {"total": 99999}
    mod.calc_order_total = broken_version

    # 验证变红
    with pytest.raises(AssertionError):
        test_calc_order_total_standard(snapshot_fixture)

    # 恢复
    mod.calc_order_total = original
```

## 环境探针

```python
# conftest.py
import pytest

@pytest.fixture(autouse=True)
def infra_probe():
    """特征测试前验证环境"""
    import socket
    try:
        socket.create_connection(('localhost', 8000), timeout=2)
    except OSError:
        pytest.skip('[infra] API server not reachable')
```
