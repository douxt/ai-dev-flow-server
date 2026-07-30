# Go 遗留代码特征测试

> 技术栈模块 — 按 `tags: go` 部署。
> 通用流程见 `knowledge/11-遗留代码特征测试.md`

## 模式 A：Golden File（推荐）

Go 标准做法——`testdata/` 目录存放预期输出。

```go
// tests/characterization/ticket_001_order_test.go
package characterization_test

import (
    "encoding/json"
    "flag"
    "os"
    "path/filepath"
    "testing"

    "example.com/app/services"
)

var update = flag.Bool("update", false, "update golden files")

func TestCalcOrderTotal_Golden(t *testing.T) {
    order := services.Order{
        Items:    []services.Item{{Price: 100, Qty: 2}},
        Discount: 0.1,
    }
    result := services.CalcOrderTotal(order)

    golden := filepath.Join("testdata", "calc_order_total.json")
    got, _ := json.MarshalIndent(result, "", "  ")

    if *update {
        os.WriteFile(golden, got, 0644)
        t.Log("golden file updated")
        return
    }

    want, err := os.ReadFile(golden)
    if err != nil {
        t.Fatalf("golden file not found. Run with -update to create: %v", err)
    }

    if string(got) != string(want) {
        t.Errorf("behavior changed!\nGOT:\n%s\nWANT (golden):\n%s", got, want)
    }
}
```

运行：
```bash
# 首次生成 golden file
go test ./tests/characterization/ -update

# 验证行为未变
go test ./tests/characterization/
```

## 模式 B：表格测试 + Golden File

```go
func TestOrderCalculationScenarios(t *testing.T) {
    tests := []struct {
        name  string
        order services.Order
    }{
        {"standard", services.Order{Items: []services.Item{{Price: 100, Qty: 2}}, Discount: 0.1}},
        {"empty", services.Order{Items: []services.Item{}}},
        {"negative_discount", services.Order{Items: []services.Item{{Price: 50}}, Discount: -0.2}},
        {"zero_quantity", services.Order{Items: []services.Item{{Price: 100, Qty: 0}}}},
        {"large_order", services.Order{Items: []services.Item{{Price: 99999, Qty: 999}}}},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            result := services.CalcOrderTotal(tt.order)
            got, _ := json.MarshalIndent(result, "", "  ")

            golden := filepath.Join("testdata", "order_"+tt.name+".json")
            if *update {
                os.WriteFile(golden, got, 0644)
                return
            }
            want, _ := os.ReadFile(golden)
            if string(got) != string(want) {
                t.Errorf("behavior changed for %s:\nGOT:\n%s\nWANT:\n%s", tt.name, got, want)
            }
        })
    }
}
```

## 模式 C：HTTP API 快照

```go
func TestAPIEndpoint_Golden(t *testing.T) {
    resp, err := http.Get("http://localhost:8080/api/orders?sale_id=40462")
    if err != nil {
        t.Skipf("[infra] API not reachable: %v", err)
    }
    defer resp.Body.Close()

    body, _ := io.ReadAll(resp.Body)
    golden := filepath.Join("testdata", "api_orders.json")

    if *update {
        os.WriteFile(golden, body, 0644)
        return
    }

    want, _ := os.ReadFile(golden)
    if string(body) != string(want) {
        t.Errorf("API behavior changed")
    }
}
```

## 文件组织

```
tests/characterization/
├── ticket_001_order_test.go
├── ticket_002_api_test.go
└── testdata/
    ├── calc_order_total.json
    ├── order_standard.json
    ├── order_empty.json
    └── api_orders.json
```

## 元验证

```go
func TestSafetyNetEffective(t *testing.T) {
    // 不适用——Go golden file 模式不依赖可变断言
    // 替代：手动改 golden file → 验证测试变红 → 恢复
}
```

> Go 的 golden file 模式天然有"修改即检测"特性——改源码后运行测试，任何行为变更都会 diff 出来。
