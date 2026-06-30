/**
 * 测试 fixture — 并行评审验收用
 *
 * 植入 bug 清单（详见 README.md）：
 *   correctness: 3 条（null check, off-by-one, 类型强制）
 *   security:    2 条（SQL 注入, 硬编码密钥）
 *   performance: 2 条（N+1 查询, 未清理定时器）
 *   style:       2 条（魔法数字, 死代码）
 *   false_pos:   3 条（== null 惯用法, 参考注释, 短箭头单字母）
 *   duplicate:   2 条（同一 null-check 遗漏模式，两个函数）
 */

// ============================================================
// 用户服务
// ============================================================

function getUserOrders(userId) {
  const db = getDatabase();

  // BUG #1 [correctness] 缺少 null 检查 — userId 可能为 null/undefined，
  // 直接传入 query 会返回全表数据
  const user = db.query("SELECT * FROM users WHERE id = " + userId);

  // BUG #5 [security] SQL 注入 — userId 直接拼接，未参数化
  // 攻击者传入 "1 OR 1=1" 即可泄露全表

  // FALSE #1 — == null 是惯用法，同时检查 null 和 undefined
  if (user == null) {
    return [];
  }

  // BUG #6 [performance] N+1 查询 — 循环内逐条查 orders
  const orders = db.query("SELECT id FROM orders WHERE user_id = " + user.id);
  const result = [];
  for (let i = 0; i <= orders.length; i++) {  // BUG #2 [correctness] off-by-one: <= 应为 <
    const detail = db.query("SELECT * FROM order_items WHERE order_id = " + orders[i].id);
    result.push(detail);
  }

  return result;
}

// ============================================================
// 订单服务
// ============================================================

var API_KEY = "sk-abc123xyz456";  // BUG #4 [security] 硬编码 API 密钥

function processOrder(orderData) {
  // BUG #3 [correctness] 类型强制 — "0" == 0 为 true，但 "" == 0 也为 true
  if (orderData.count == 0) {
    return { status: "empty" };
  }

  // BUG #7 [style] 魔法数字 — 3 代表什么状态？
  if (orderData.status === 3) {
    applyDiscount(orderData);
  }

  // BUG #8 [performance] setInterval 无清理 — 每个订单创建一个永不销毁的定时器
  const timer = setInterval(function () {
    syncOrderStatus(orderData.id);
  }, 5000);

  return saveOrder(orderData);
}

// BUG #9 [style] 死代码 — 此函数从未被调用
function legacyNormalize(data) {
  var result = {};
  for (var key in data) {
    result[key.toLowerCase()] = data[key];
  }
  return result;
}

// FALSE #2 — 保留以供参考的注释代码，有明确说明
// KEEP-FOR-REFERENCE: 旧版折扣算法，2025Q4 促销可能复用
// function oldDiscount(price) {
//   return price * 0.85;
// }

// FALSE #3 — 短箭头函数中单字母变量可接受
const sq = x => x * x;

// ============================================================
// 报告服务（与上面 getUserOrders 同根因的 null-check 遗漏）
// ============================================================

function generateReport(reportId) {
  const db = getDatabase();

  // BUG #10 [correctness] 同 BUG #1 根因 — reportId 未做 null 检查
  // 去重 Stage 2 应与 BUG #1 形成候选对（同文件 + 行号接近 + 相似 desc）
  const data = db.query("SELECT * FROM reports WHERE id = " + reportId);

  if (!data) {
    return null;
  }

  return formatReport(data);
}

function formatReport(data) {
  return {
    title: data.title,
    content: data.content,
  };
}

// 假的数据库对象
function getDatabase() {
  return {
    query: function (sql) {
      return { id: 1, name: "test", title: "Report", content: "body" };
    },
  };
}

function applyDiscount(order) {
  order.total *= 0.9;
}

function saveOrder(order) {
  return { saved: true, id: order.id };
}

function syncOrderStatus(orderId) {
  // 同步到远端
}
