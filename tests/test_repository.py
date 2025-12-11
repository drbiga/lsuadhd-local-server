import os

import pytest
from unittest.mock import AsyncMock

from session import IamSession, User
from feedback import Feedback, PaFeedback
from feedback_repository import FeedbackRepository


class TestRepository:
    @pytest.mark.asyncio
    async def test_raises_if_db_path_not_set(self, monkeypatch):
        db_path = os.getenv("SQLITE_DB_PATH")
        monkeypatch.delenv("SQLITE_DB_PATH")
        with pytest.raises(ValueError):
            FeedbackRepository()

        assert not os.path.exists(db_path)

    @pytest.mark.asyncio
    async def test_creates_table_on_constructor(self):
        db_path = os.getenv("SQLITE_DB_PATH")
        repo = FeedbackRepository()

        # I can't think of a better way to test this, but the behavior I want to test is
        # that the repository creates the table, so if it doesn't, an error will be raised
        result = await repo.get_all()

        os.remove(db_path)
        assert not os.path.exists(db_path)

    @pytest.mark.asyncio
    async def test_insert_creates_new_row(self):
        db_path = os.getenv("SQLITE_DB_PATH")
        repo = FeedbackRepository()

        await repo.insert_new(
            Feedback(
                seqnum=1,
                personal_analytics_data=PaFeedback(
                    isFocused=1,
                    numMouseClicks=2,
                    mouseMoveDistance=2,
                    mouseScrollDistance=3,
                    keyboardStrokes=1,
                ),
                screenshot="s",
            ),
            IamSession(
                token="t",
                user=User(username="u", role="student"),
                ip_address="l",
                session_num=1,
            ),
        )
        result = await repo.get_all()

        assert len(result) == 1

        os.remove(db_path)
        assert not os.path.exists(db_path)
