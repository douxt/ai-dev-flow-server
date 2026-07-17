"""P2: 异步核心测试 — asyncio.Queue + 熔断器，需要 pytest-asyncio"""
import asyncio
import pytest


class TestRunBackground:
    def test_put_to_queue(self, listener):
        listener._bg_queue = asyncio.Queue(maxsize=10)
        listener._bg_workers = []
        async def dummy(): pass
        listener._run_background(dummy())
        assert listener._bg_queue.qsize() == 1

    def test_queue_full_no_raise(self, listener):
        listener._bg_queue = asyncio.Queue(maxsize=1)
        listener._bg_workers = []
        async def dummy(): pass
        listener._run_background(dummy())  # fills queue
        listener._run_background(dummy())  # queue full, logged but no exception
        assert listener._bg_queue.qsize() == 1


class TestBgWorker:
    @pytest.mark.asyncio
    async def test_consumes_and_awaits(self, listener):
        listener._bg_queue = asyncio.Queue(maxsize=10)
        executed = []
        async def task():
            executed.append(1)
        await listener._bg_queue.put(task())
        worker_task = asyncio.create_task(listener._bg_worker())
        await asyncio.sleep(0.05)
        worker_task.cancel()
        try: await worker_task
        except asyncio.CancelledError: pass
        assert len(executed) == 1
        assert listener._bg_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_exception_does_not_crash_worker(self, listener):
        listener._bg_queue = asyncio.Queue(maxsize=10)
        async def failing(): raise ValueError("boom")
        async def ok(): pass
        await listener._bg_queue.put(failing())
        await listener._bg_queue.put(ok())
        worker_task = asyncio.create_task(listener._bg_worker())
        await asyncio.sleep(0.1)
        worker_task.cancel()
        try: await worker_task
        except asyncio.CancelledError: pass
        assert listener._bg_queue.qsize() == 0


class TestCheckVisionQuota:
    @pytest.mark.asyncio
    async def test_zero_limit_unlimited(self, listener):
        listener.vision_daily_limit = 0
        assert await listener._check_vision_quota() is True

    @pytest.mark.asyncio
    async def test_exceeded_daily(self, listener):
        from datetime import date
        listener.vision_daily_limit = 3
        listener._vision_daily_count = 3
        listener._vision_daily_date = date.today()
        assert await listener._check_vision_quota() is False

    @pytest.mark.asyncio
    async def test_edge_exactly_at_limit(self, listener):
        from datetime import date
        listener.vision_daily_limit = 3
        listener._vision_daily_count = 2
        listener._vision_daily_date = date.today()
        assert await listener._check_vision_quota() is True

    @pytest.mark.asyncio
    async def test_date_reset(self, listener):
        from datetime import date, timedelta
        listener.vision_daily_limit = 3
        listener._vision_daily_count = 3
        listener._vision_daily_date = date.today() - timedelta(days=1)
        assert await listener._check_vision_quota() is True
        assert listener._vision_daily_count == 1

    @pytest.mark.asyncio
    async def test_circuit_open_blocks(self, listener):
        from datetime import datetime, timezone, timedelta
        listener._vision_circuit_open_until = datetime.now(timezone(timedelta(hours=8))) + timedelta(hours=1)
        assert await listener._check_vision_quota() is False


class TestRecordVisionResult:
    def test_success_resets_streak(self, listener):
        listener._vision_fail_streak = 3
        listener._record_vision_result(True)
        assert listener._vision_fail_streak == 0

    def test_fail_increments_streak(self, listener):
        listener._record_vision_result(False)
        assert listener._vision_fail_streak == 1

    def test_5_fails_opens_circuit(self, listener):
        for _ in range(5):
            listener._record_vision_result(False)
        assert listener._vision_circuit_open_until is not None
        assert listener._vision_fail_streak == 5

    def test_stats_aggregated(self, listener):
        listener._record_vision_result(True)
        listener._record_vision_result(False)
        assert listener._vision_stats['total'] == 2
        assert listener._vision_stats['success'] == 1
        assert listener._vision_stats['fail'] == 1
