import pytest
from unittest.mock import AsyncMock, Mock

import asyncio

from browser_service import BrowserService


@pytest.fixture
def session_progress_has_finished_homework():
    mock = Mock()
    mock.has_finished_homework.return_value = True
    return mock


@pytest.fixture
def session_progress_has_not_finished_homework():
    mock = Mock()
    mock.has_finished_homework.return_value = False
    return mock


@pytest.fixture
def session_service_wait_zero(session_progress_has_finished_homework):
    mock = Mock()
    mock.get_session_progress = AsyncMock(
        return_value=session_progress_has_finished_homework
    )
    return mock


@pytest.fixture
def session_service_wait_one(
    session_progress_has_finished_homework, session_progress_has_not_finished_homework
):
    mock = Mock()
    mock.get_session_progress = AsyncMock(
        side_effect=[
            session_progress_has_not_finished_homework,
            session_progress_has_finished_homework,
        ]
    )
    return mock


@pytest.fixture
def session_service_wait_many(
    session_progress_has_finished_homework, session_progress_has_not_finished_homework
):
    mock = Mock()
    mock.get_session_progress = AsyncMock(
        side_effect=[
            session_progress_has_not_finished_homework,
            session_progress_has_not_finished_homework,
            session_progress_has_finished_homework,
        ]
    )
    return mock


class TestBrowserService:
    @pytest.mark.parametrize(
        "env_variable",
        ["FRONTEND_URL", "ENV"],
    )
    def test_environment_variables_not_set(
        self, session_service_wait_zero, monkeypatch, env_variable
    ):
        monkeypatch.delenv(env_variable)
        with pytest.raises(ValueError):
            BrowserService(session_service_wait_zero)

    @pytest.mark.asyncio
    async def test_start_worker_twice(self, session_service_wait_zero):
        svc = BrowserService(session_service_wait_zero)
        svc.is_running = True  # manually setting flag
        with pytest.raises(RuntimeError):
            await svc.start_browser_worker()  # this should raise if the flag is true

    @pytest.mark.asyncio
    async def test_wait_zero_times(self, session_service_wait_zero):
        svc = BrowserService(session_service_wait_zero)
        await svc.start_browser_worker()
        assert session_service_wait_zero.get_session_progress.call_count == 1

    @pytest.mark.asyncio
    async def test_wait_one_time(self, session_service_wait_one):
        svc = BrowserService(session_service_wait_one)
        await svc.start_browser_worker()
        assert session_service_wait_one.get_session_progress.call_count == 2

    @pytest.mark.asyncio
    async def test_wait_many_times(self, session_service_wait_many):
        svc = BrowserService(session_service_wait_many)
        await svc.start_browser_worker()
        assert session_service_wait_many.get_session_progress.call_count == 3

    @pytest.mark.asyncio
    async def test_improperly_changing_state(self, session_service_wait_one):
        svc = BrowserService(session_service_wait_one)
        task = asyncio.create_task(svc.start_browser_worker())
        await asyncio.sleep(0)
        async with svc.lock:
            svc.is_running = False
        with pytest.raises(RuntimeError):
            await task
