import pytest
from unittest.mock import Mock, AsyncMock

import asyncio

from session import IamSession, User
from feedback_colletor import FeedbackColletor
from feedback import Feedback, PaFeedback


@pytest.fixture
def iam_service_no_session():
    mock = Mock()
    mock.get_iam_session.return_value = None

    return mock


@pytest.fixture
def iam_service_with_session():
    mock = Mock()
    mock.get_iam_session.return_value = IamSession(
        session_num=1,
        token="valid-token",
        user=User(username="username", password=None, role="student"),
        ip_address="localhost",
    )

    return mock


@pytest.fixture
def session_service__ingest__raises_exception():
    mock = Mock()
    mock.is_session_active = AsyncMock(return_value=True)
    mock.ingest_feedback = AsyncMock()
    mock.ingest_feedback.side_effect = [Exception("Something went wrong"), False]

    return mock


@pytest.fixture
def session_service_is_active_session_false():
    mock = Mock()
    mock.is_session_active = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def session_service_is_session_active_true():
    mock = Mock()
    mock.is_session_active = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def session_service__with_successful_ingest():
    mock = Mock()
    mock.ingest_feedback = AsyncMock()
    mock.ingest_feedback.side_effect = [True, False]
    mock.is_session_active = AsyncMock()
    mock.is_session_active.side_effect = [True, False]

    return mock


@pytest.fixture
def session_service_no_active_session():
    mock = Mock()
    mock.is_session_active = AsyncMock(return_value=True)
    mock.ingest_feedback = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def repository():
    mock = Mock()
    mock.insert_new = AsyncMock()

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
    mock = AsyncMock(
        return_value=PaFeedback(
            numMouseClicks=0,
            keyboardStrokes=0,
            mouseMoveDistance=0,
            mouseScrollDistance=0,
            isFocused=0,
        )
    )
    return mock


@pytest.fixture
def collect_feedback():
    mock = AsyncMock(
        return_value=Feedback(
            seqnum=1,
            personal_analytics_data=PaFeedback(
                numMouseClicks=0,
                keyboardStrokes=0,
                mouseMoveDistance=0,
                mouseScrollDistance=0,
                isFocused=0,
            ),
            screenshot="somepath",
        )
    )
    return mock


@pytest.fixture
def ingest_feedback_fails_first_works_second():
    mock = Mock()
    mock.is_session_active = AsyncMock(return_value=True)
    mock.ingest_feedback = AsyncMock()
    mock.ingest_feedback.side_effect = [
        TimeoutError(),
        True,
        False,  # adding a false to let the loop break and finish the start_collecting
    ]
    return mock


@pytest.fixture
def repository__insert_new__raises_exception(repository):
    def exc():
        raise Exception("Something went wrong")

    repository.insert_new.side_effect = exc
    return repository


class TestFeedbackCollector:
    @pytest.mark.asyncio
    async def test_session_not_set_should_raise(
        self,
        session_service_no_active_session,
        iam_service_no_session,
        repository,
        timing_service,
    ):
        c = FeedbackColletor(
            session_service_no_active_session,
            iam_service_no_session,
            repository,
            timing_service,
        )
        with pytest.raises(AttributeError):
            await c.start_collecting()

    @pytest.mark.asyncio
    async def test_session_is_not_active_should_raise(
        self,
        session_service_is_active_session_false,
        iam_service_with_session,
        repository,
        timing_service,
    ):
        c = FeedbackColletor(
            session_service_is_active_session_false,
            iam_service_with_session,
            repository,
            timing_service,
        )
        c.timing_service = timing_service
        with pytest.raises(RuntimeError):
            await c.start_collecting()

    @pytest.mark.asyncio
    async def test_collects_feedbacks_if_active_session(
        self,
        session_service__with_successful_ingest,
        iam_service_with_session,
        repository,
        timing_service,
        get_pa_feedback_data,
    ):
        c = FeedbackColletor(
            session_service__with_successful_ingest,
            iam_service_with_session,
            repository,
            timing_service,
        )
        # This is useless at this point since the collector class instantiates
        # the timing service within the start_collecting method
        # c.timing_service = timing_service
        c._get_feedback_personal_analytics = get_pa_feedback_data

        await c.start_collecting()
        assert c.get_feedback_count_for_session() > 0

    @pytest.mark.asyncio
    async def test_saves_feedbacks_in_repo(
        self,
        session_service__with_successful_ingest,
        iam_service_with_session,
        repository,
        timing_service,
        collect_feedback,
    ):
        c = FeedbackColletor(
            session_service__with_successful_ingest,
            iam_service_with_session,
            repository,
            timing_service,
        )
        c._collect_feedback_data = collect_feedback
        await c.start_collecting()
        assert repository.insert_new.call_count > 0

    @pytest.mark.asyncio
    async def test_sends_feedbacks_to_server(
        self,
        session_service__with_successful_ingest,
        iam_service_with_session,
        repository,
        timing_service,
        collect_feedback,
    ):
        c = FeedbackColletor(
            session_service__with_successful_ingest,
            iam_service_with_session,
            repository,
            timing_service,
        )
        c.timing_service = timing_service
        c._collect_feedback_data = collect_feedback
        await c.start_collecting()
        assert session_service__with_successful_ingest.ingest_feedback.call_count > 0

    @pytest.mark.asyncio
    async def test_running_loop_breaks_on_no_active_session_condition(
        self,
        session_service_no_active_session,
        iam_service_with_session,
        repository,
        timing_service,
        collect_feedback,
    ):
        c = FeedbackColletor(
            session_service_no_active_session,
            iam_service_with_session,
            repository,
            timing_service,
        )
        c.timing_service = timing_service
        c._collect_feedback_data = collect_feedback
        await c.start_collecting()
        assert c.get_feedback_count_for_session() == 0

    @pytest.mark.asyncio
    async def test_runs_until_session_is_over(
        self,
        session_service__with_successful_ingest,
        iam_service_with_session,
        repository,
        timing_service,
        get_pa_feedback_data,
    ):
        c = FeedbackColletor(
            session_service__with_successful_ingest,
            iam_service_with_session,
            repository,
            timing_service,
        )
        # c._collect_feedback_data = collect_feedback
        c._get_feedback_personal_analytics = get_pa_feedback_data
        await c.start_collecting()
        is_session_active = (
            await session_service__with_successful_ingest.is_session_active()
        )
        assert is_session_active == False

    @pytest.mark.asyncio
    async def test_send_timeout_proceeds_next_iteration(
        self,
        ingest_feedback_fails_first_works_second,
        iam_service_with_session,
        repository,
        timing_service,
        get_pa_feedback_data,
    ):
        c = FeedbackColletor(
            ingest_feedback_fails_first_works_second,
            iam_service_with_session,
            repository,
            timing_service,
        )
        c._get_feedback_personal_analytics = get_pa_feedback_data
        await c.start_collecting()

        # A retry will trigger the send feedback method twice while only
        # collecting one feedback
        assert (
            c.get_feedback_count_for_session() == 3
        )  # collects one feedback more than the server processes
        assert (
            ingest_feedback_fails_first_works_second.ingest_feedback.call_count == 3
        )  # last call will be the one to break the loop

    @pytest.mark.asyncio
    async def test_running_twice_raises_exception(
        self,
        session_service__with_successful_ingest,
        iam_service_with_session,
        repository,
        timing_service,
        get_pa_feedback_data,
    ):
        c = FeedbackColletor(
            session_service__with_successful_ingest,
            iam_service_with_session,
            repository,
            timing_service,
        )
        c._get_feedback_personal_analytics = get_pa_feedback_data
        task = asyncio.create_task(c.start_collecting())
        await asyncio.sleep(0.05)
        with pytest.raises(RuntimeError):
            await c.start_collecting()

        await task

    @pytest.mark.asyncio
    async def test_repo_raises_exception_should_continue(
        self,
        session_service_no_active_session,
        iam_service_with_session,
        repository__insert_new__raises_exception,
        timing_service,
        get_pa_feedback_data,
    ):
        c = FeedbackColletor(
            session_service_no_active_session,
            iam_service_with_session,
            repository__insert_new__raises_exception,
            timing_service,
        )
        c._get_feedback_personal_analytics = get_pa_feedback_data

        # The backend no active session fixture will make the loop run once and
        # break, which should trigger the timing service finish_iteration() method
        # to be called exactly once
        await c.start_collecting()

        timing_service.finish_iteration.call_count == 1

    @pytest.mark.asyncio
    async def test_repo_raises_exception_should_continue(
        self,
        session_service__ingest__raises_exception,
        iam_service_with_session,
        repository__insert_new__raises_exception,
        timing_service,
        get_pa_feedback_data,
    ):
        c = FeedbackColletor(
            session_service__ingest__raises_exception,
            iam_service_with_session,
            repository__insert_new__raises_exception,
            timing_service,
        )
        c._get_feedback_personal_analytics = get_pa_feedback_data

        # The backend__ingest__raises_exception fixture will make the loop run once and
        # break, which should trigger the timing service finish_iteration() method
        # to be called exactly once
        await c.start_collecting()

        timing_service.finish_iteration.call_count == 1
