import pytest
from unittest.mock import Mock, AsyncMock

from services import SessionService
from session import IamSession, User


@pytest.fixture
def get_remaining_sessions_method():
    return AsyncMock(return_value=[1, 2])


class TestSessionService:
    @pytest.mark.asyncio
    async def test_set_iam_session_triggers_get_session_num(
        self, get_remaining_sessions_method
    ):
        svc = SessionService()
        svc.get_remaining_sessions_seqnum = get_remaining_sessions_method
        svc.set_iam_session(
            IamSession(
                token="valid", user=User(username="u", role="s"), ip_address="localhost"
            )
        )
        assert svc.get_remaining_sessions_seqnum_task is not None
        await svc.get_remaining_sessions_seqnum_task
        assert get_remaining_sessions_method.call_count == 1
        assert svc.iam_session.session_num == 1
