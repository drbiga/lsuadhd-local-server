import asyncio
import httpx

import pytest
from unittest.mock import Mock, AsyncMock

from connection import Connection
from feedback import Feedback, PaFeedback


@pytest.fixture
def feedback():
    return Feedback(
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


class TestConnection:
    @pytest.mark.asyncio
    async def test_send_feedback_raises_timeout_error_if_timeout(
        self, feedback, send_feedback_timeout
    ):
        c = Connection()
        c._send_feedback = send_feedback_timeout
        with pytest.raises(TimeoutError):
            await c.send_feedback(feedback)

    @pytest.mark.asyncio
    async def test_any_other_exception_should_return_true(
        self, feedback, send_feedback_generic_exception
    ):
        c = Connection()
        c._send_feedback = send_feedback_generic_exception
        assert (await c.send_feedback(feedback)) == True
