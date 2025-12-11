import json
import httpx

import pytest
from unittest.mock import Mock, AsyncMock

from connection import Connection
from feedback import Feedback, PaFeedback
from session import IamSession, User, Role


@pytest.fixture
def feedback():
    return Feedback(
        seqnum=1,
        personal_analytics_data=PaFeedback(
            isFocused=0,
            numMouseClicks=12,
            mouseScrollDistance=234,
            mouseMoveDistance=10,
            keyboardStrokes=10,
        ),
        screenshot="screenshots/example-screenshot.png",
    )


@pytest.fixture
def send_feedback_timeout():
    mock = AsyncMock()

    async def side_effect(*args):
        raise httpx.TimeoutException("Intentional timeout for testing")

    mock.side_effect = side_effect
    return mock


@pytest.fixture
def send_feedback_generic_exception():
    mock = AsyncMock()

    async def side_effect(*args):
        raise Exception()

    mock.side_effect = side_effect

    return mock


@pytest.fixture
def send_feedback__returns_valid_feedback():
    mock = AsyncMock(return_value={"valid": "feedback"})
    return mock


@pytest.fixture
def send_feedback__returns_error():
    mock = AsyncMock(return_value={"detail": {"errcode": 1}})
    return mock


@pytest.fixture
def send_feedback__json_decode_error():
    mock = AsyncMock(side_effect=json.JSONDecodeError("error", "?", 0))
    return mock


@pytest.fixture
def session():
    return IamSession(
        token="valid",
        user=User(username="u", role=Role.STUDENT),
        ip_address="localhost",
        session_num=1,
    )


@pytest.fixture
def get_session_progress__no_active_session():
    mock = AsyncMock()
    mock.return_value = {
        "status": "err",
        "message": "You do not have an active session yet",
    }

    return mock


@pytest.fixture
def get_session_progress__unknown_error():
    mock = AsyncMock()
    mock.return_value = {
        "status": "err",
        "message": "Unknown",
    }

    return mock


@pytest.fixture
def get_session_progress__raises_exception():
    mock = AsyncMock(side_effect=Exception())

    return mock


@pytest.fixture
def get_session_progress__session_over():
    mock = AsyncMock(return_value={"stage": "finished"})
    return mock


@pytest.fixture
def get_session_progress__ongoing():
    mock = AsyncMock(return_value={"stage": "readcomp"})
    return mock


class TestConnection:
    # ==============================================================================================
    # Testing method send_feedback
    @pytest.mark.asyncio
    async def test_send_feedback_raises_timeout_error_if_timeout(
        self, feedback, send_feedback_timeout
    ):
        c = Connection()
        c._send_feedback = send_feedback_timeout
        with pytest.raises(TimeoutError):
            await c.send_feedback(feedback)

    @pytest.mark.asyncio
    async def test_send_success(self, feedback, send_feedback__returns_valid_feedback):
        c = Connection()
        c._send_feedback = send_feedback__returns_valid_feedback
        result = await c.send_feedback(feedback)
        assert result == True

    @pytest.mark.asyncio
    async def test_send_session_is_over(self, feedback, send_feedback__returns_error):
        c = Connection()
        c._send_feedback = send_feedback__returns_error
        result = await c.send_feedback(feedback)
        assert result == False

    @pytest.mark.asyncio
    async def test_json_decode_error_should_continue_collecting(
        self, feedback, send_feedback__json_decode_error
    ):
        c = Connection()
        c._send_feedback = send_feedback__json_decode_error
        result = await c.send_feedback(feedback)
        assert result == True

    @pytest.mark.asyncio
    async def test_any_other_exception_should_return_true(
        self, feedback, send_feedback_generic_exception
    ):
        c = Connection()
        c._send_feedback = send_feedback_generic_exception
        assert (await c.send_feedback(feedback)) == True

    # ==============================================================================================
    # Getters and setters
    def test_session_is_set_after_creation(self, session):
        c = Connection()

        assert c.session is None

        c.set_session(session)

        assert c.session is not None

    def test_get_session(self, session):
        c = Connection()

        assert c.get_session() is None

        c.set_session(session)

        assert c.get_session() is not None

    # ==============================================================================================
    # Testing method is_session_active

    @pytest.mark.asyncio
    async def test_session_was_not_started(
        self, get_session_progress__no_active_session
    ):
        c = Connection()
        c._get_session_progress = get_session_progress__no_active_session

        result = await c.is_session_active()

        assert result == False

    @pytest.mark.asyncio
    async def test_exception_is_raised_should_continue(
        self, get_session_progress__raises_exception
    ):
        c = Connection()
        c._get_session_progress = get_session_progress__raises_exception

        result = await c.is_session_active()
        # If this is true, the local server will continue the loop
        assert result == True

    @pytest.mark.asyncio
    async def test_unknown_error_messages_should_continue(
        self, get_session_progress__unknown_error
    ):
        c = Connection()
        c._get_session_progress = get_session_progress__unknown_error

        result = await c.is_session_active()
        # If this is true, the local server will continue the loop
        assert result == True

    @pytest.mark.asyncio
    async def test_session_is_over(self, get_session_progress__session_over):
        c = Connection()
        c._get_session_progress = get_session_progress__session_over

        result = await c.is_session_active()
        # If this is true, the local server will continue the loop
        assert result == False

    @pytest.mark.asyncio
    async def test_session_ongoing(self, get_session_progress__ongoing):
        c = Connection()
        c._get_session_progress = get_session_progress__ongoing

        result = await c.is_session_active()
        # If this is true, the local server will continue the loop
        assert result == True
