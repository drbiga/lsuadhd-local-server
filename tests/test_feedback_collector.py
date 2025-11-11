import pytest
from unittest.mock import Mock, AsyncMock

import asyncio

from session import IamSession, User
from feedback_colletor import FeedbackColletor
from feedback import Feedback, PaFeedback


@pytest.fixture
def connection_no_session():
    mock = Mock()
    mock.get_session.return_value = None

    return mock


@pytest.fixture
def connection_with_session():
    mock = Mock()
    mock.get_session.return_value = IamSession(
        token="valid-token",
        user=User(username="username", password=None, role="student"),
        ip_address="localhost",
    )

    return mock


@pytest.fixture
def connection_is_active_session_false(connection_with_session):
    connection_with_session.is_session_active = AsyncMock(return_value=False)
    return connection_with_session


@pytest.fixture
def connection_is_session_active_true(connection_with_session):
    connection_with_session.is_session_active = AsyncMock(return_value=True)
    return connection_with_session


@pytest.fixture
def connection_with_successful_send(connection_with_session):
    connection_with_session.send_feedback = AsyncMock()
    connection_with_session.send_feedback.side_effect = [True, False]

    connection_with_session.is_session_active = AsyncMock()
    connection_with_session.is_session_active.side_effect = [True, False]
    return connection_with_session


@pytest.fixture
def connection_no_active_session(connection_with_session):
    connection_with_session.is_session_active = AsyncMock(return_value=True)
    connection_with_session.send_feedback = AsyncMock(return_value=False)
    return connection_with_session


@pytest.fixture
def repository():
    mock = Mock()
    mock.insert_new.return_value = None

    return mock


@pytest.fixture
def timing_service():
    mock = Mock()
    mock.wait = AsyncMock(return_value=None)
    mock.start_iteration.return_value = None
    mock.finish_iteration.return_value = None

    return mock


@pytest.fixture
def get_pa_feedback_data():
    mock = Mock()
    mock.return_value = PaFeedback(
        numMouseClicks=0,
        keyboardStrokes=0,
        mouseMoveDistance=0,
        mouseScrollDistance=0,
        isFocused=0,
    )
    return mock


@pytest.fixture
def collect_feedback():
    mock = Mock()
    mock.return_value = Feedback(
        personal_analytics_data=PaFeedback(
            numMouseClicks=0,
            keyboardStrokes=0,
            mouseMoveDistance=0,
            mouseScrollDistance=0,
            isFocused=0,
        ),
        screenshot="somepath",
    )
    return mock


@pytest.fixture
def send_feedback_fails_first_works_second(connection_is_session_active_true):
    connection_is_session_active_true.send_feedback = AsyncMock()
    connection_is_session_active_true.send_feedback.side_effect = [
        TimeoutError(),
        True,
        False,  # adding a false to let the loop break and finish the worker
    ]
    return connection_is_session_active_true


class TestFeedbackCollector:
    @pytest.mark.asyncio
    async def test_session_not_set_should_raise(
        self, connection_no_session, timing_service
    ):
        c = FeedbackColletor(connection_no_session)
        c.timing_service = timing_service
        with pytest.raises(AttributeError):
            await c.worker()

    @pytest.mark.asyncio
    async def test_session_is_not_active_should_raise(
        self, connection_is_active_session_false, timing_service
    ):
        c = FeedbackColletor(connection_is_active_session_false)
        c.timing_service = timing_service
        with pytest.raises(RuntimeError):
            await c.worker()

    @pytest.mark.asyncio
    async def test_collects_feedbacks_if_active_session(
        self, connection_with_successful_send, timing_service, get_pa_feedback_data
    ):
        c = FeedbackColletor(connection_with_successful_send)
        # This is useless at this point since the collector class instantiates
        # the timing service within the worker method
        # c.timing_service = timing_service
        c.get_feedback_personal_analytics = get_pa_feedback_data
        await c.worker()
        assert c.get_feedback_count_for_session() > 0

    @pytest.mark.asyncio
    async def test_saves_feedbacks_in_repo(
        self,
        connection_with_successful_send,
        timing_service,
        collect_feedback,
        repository,
    ):
        c = FeedbackColletor(connection_with_successful_send)
        # c.timing_service = timing_service
        c.collect_feedback_data = collect_feedback
        c.repository = repository
        await c.worker()
        assert c.repository.insert_new.call_count > 0

    @pytest.mark.asyncio
    async def test_sends_feedbacks_to_server(
        self, connection_with_successful_send, timing_service, collect_feedback
    ):
        c = FeedbackColletor(connection_with_successful_send)
        c.timing_service = timing_service
        c.collect_feedback_data = collect_feedback
        await c.worker()
        assert connection_with_successful_send.send_feedback.call_count > 0

    @pytest.mark.asyncio
    async def test_running_loop_breaks_on_no_active_session_condition(
        self, connection_no_active_session, timing_service, collect_feedback
    ):
        c = FeedbackColletor(connection_no_active_session)
        c.timing_service = timing_service
        c.collect_feedback_data = collect_feedback
        await c.worker()
        assert c.get_feedback_count_for_session() == 0

    @pytest.mark.asyncio
    async def test_runs_until_session_is_over(
        self, connection_with_successful_send, get_pa_feedback_data
    ):
        c = FeedbackColletor(connection_with_successful_send)
        # c.collect_feedback_data = collect_feedback
        c.get_feedback_personal_analytics = get_pa_feedback_data
        await c.worker()
        is_session_active = await connection_with_successful_send.is_session_active()
        assert is_session_active == False

    @pytest.mark.asyncio
    async def test_send_timeout_proceeds_next_iteration(
        self, send_feedback_fails_first_works_second, get_pa_feedback_data
    ):
        c = FeedbackColletor(send_feedback_fails_first_works_second)
        c.get_feedback_personal_analytics = get_pa_feedback_data
        await c.worker()

        # A retry will trigger the send feedback method twice while only
        # collecting one feedback
        assert (
            c.get_feedback_count_for_session() == 3
        )  # collects one feedback more than the server processes
        assert (
            send_feedback_fails_first_works_second.send_feedback.call_count == 3
        )  # last call will be the one to break the loop

    @pytest.mark.asyncio
    async def test_running_twice_raises_exception(
        self, connection_with_successful_send, get_pa_feedback_data
    ):
        c = FeedbackColletor(connection_with_successful_send)
        c.get_feedback_personal_analytics = get_pa_feedback_data
        task = asyncio.create_task(c.worker())
        await asyncio.sleep(0.05)
        with pytest.raises(RuntimeError):
            await c.worker()

        await task
