"""[出卷方补题] AC1 随机可行性 + AC6 守恒式在 API 边界的性质化覆盖。

保留卷(test_api_contract/test_schema)对固定料单已断言守恒/lb≤bars 链，但原 test_bfd/
test_bounds 的 hypothesis 随机广度随接口钉死段一并剔除后，AC1 的"随机零违例"维缺兜底。
本补题只在 **POST /optimize 响应 dict** 上断言票面 AC 明列的外部不变量——不 import
optimizer 内部符号、不钉函数名——故不复制被剔段的可推导性缺陷。判据来源:票 AC1/AC2/AC6。
"""
import hashlib
import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

GOOD_KEY = "k-supplement-0001"


def make_client():
    # 不用 tmp_path fixture（函数级，@given 下不重置）——in-test 临时目录自管
    d = Path(tempfile.mkdtemp())
    keys = d / "api_keys.json"
    keys.write_text(json.dumps({hashlib.sha256(GOOD_KEY.encode()).hexdigest(): "t"}))
    from app.main import create_app
    return TestClient(create_app(keys_path=keys))


def _post(client, materials, kerf):
    body = {
        "client_request_id": "sup-1", "title": "sup",
        "options": {"time_limit_s_per_material": 10, "request_deadline_s": 120,
                    "kerf": kerf, "min_offcut_length": 500},
        "materials": materials,
    }
    return client.post("/optimize", json=body,
                       headers={"Authorization": f"Bearer {GOOD_KEY}"})


@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(
    lengths=st.lists(st.integers(400, 3200), max_size=40),
    cap=st.sampled_from([4000, 5000, 6000]),
    kerf=st.sampled_from([0.0, 3.0, 3.2]),
)
def test_random_conservation_and_bounds_via_api(lengths, cap, kerf):
    """票 AC1(随机可行性零违例)+AC6(守恒)+AC2(lb≤bars)：只断响应级不变量。"""
    client = make_client()
    materials = [{
        "group": "g",
        "stock": [{"length": cap, "quantity": 10000}],
        "parts": [{"length": l, "quantity": 1} for l in lengths],
    }]
    resp = _post(client, materials, kerf)
    assert resp.status_code == 200, resp.text
    r = resp.json()["results"][0]

    placed = sum(c["length"] * c["quantity"]
                 for s in r["schemes"] for c in s["cuts"])
    offcut_total = sum(o["length"] * o["quantity"] for o in r["offcuts"])
    n_parts = len(lengths)
    n_placed_cuts = sum(c["quantity"] for s in r["schemes"] for c in s["cuts"])
    n_unplaced = sum(u["quantity"] for u in r["unplaced"])

    # AC1 件不丢不重：placed + unplaced 恰等于请求件数
    assert n_placed_cuts + n_unplaced == n_parts
    # AC6 守恒恒等式（与保留卷 test_conservation_exact_with_kerf_in_waste 同式，契约 L55）
    assert r["bars_used"] * cap == placed + offcut_total + r["waste_length"]
    # AC2 证书界链：下界 ≤ 实排根数
    assert r["lower_bound"] <= r["bars_used"]


def test_ncut_accounting_discriminator():
    """[出卷方补题] 救回被剔 test_bounds 的唯一判别封条：n 口刀损记账(票附注1/契约 L56 用户定案)。

    2998×2/cap6000/kerf3.2：n 口 Σlen+n·kerf = 5996+6.4 = 6002.4 > 6000 → 不可并 → 2 根；
    2996×2/cap6000/kerf3.2：5992+6.4 = 5998.4 ≤ 6000 → 可并 → 1 根。
    (n−1) 口口径或基线桩(不计 kerf)会把 2998×2 误判 1 根 → 本断言专杀之。
    只经 POST /optimize 响应 bars_used，不触 optimizer 内部符号。
    """
    client = make_client()

    def bars(lengths, cap, kerf):
        r = _post(client, [{
            "group": "g", "stock": [{"length": cap, "quantity": 100}],
            "parts": [{"length": l, "quantity": 1} for l in lengths],
        }], kerf).json()["results"][0]
        return r["bars_used"]

    assert bars([2998, 2998], 6000, 3.2) == 2   # n 口：两根并不下
    assert bars([2996, 2996], 6000, 3.2) == 1   # 可并：判别对照
