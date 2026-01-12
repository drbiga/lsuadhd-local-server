import os

import traceback
import logging

import asyncio
import aiosqlite

from feedback import Feedback, PaFeedback
from session import IamSession


class FeedbackRepository:
    def __init__(self):
        self.db_path = os.getenv("SQLITE_DB_PATH", None)
        if self.db_path is None:
            raise ValueError(
                "[ FeedbackRepository ] The database path was not set in the environment variables"
            )

        self.table_was_created = False

    async def create_table_if_not_exists(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                    CREATE TABLE IF NOT EXISTS feedbacks (
                        student_name TEXT,
                        session_num INTEGER,
                        seqnum INTEGER,
                        screenshot TEXT,
                        is_focused INTEGER,
                        num_mouse_clicks INTEGER,
                        mouse_scroll_distance REAL,
                        mouse_move_distance REAL,
                        keyboard_strokes INTEGER,
                        PRIMARY KEY (student_name, session_num, seqnum)
                    );
                """
            )
            await db.commit()
            logging.info(
                "[ FeedbackRepository.create_table_if_not_exists ] Feedbacks table was created"
            )

    async def insert_new(self, feedback: Feedback, session: IamSession) -> None:
        if not self.table_was_created:
            await self.create_table_if_not_exists()

        if session.session_num is None:
            raise RuntimeError(
                "[ FeedbackRepository.insert_new ] Session num was not yet set"
            )

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO feedbacks VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """,
                (
                    session.user.username,
                    session.session_num,
                    feedback.seqnum,
                    feedback.screenshot,
                    feedback.personal_analytics_data.isFocused,
                    feedback.personal_analytics_data.numMouseClicks,
                    feedback.personal_analytics_data.mouseScrollDistance,
                    feedback.personal_analytics_data.mouseMoveDistance,
                    feedback.personal_analytics_data.keyboardStrokes,
                ),
            )
            await db.commit()

    async def get_all(self) -> Feedback:
        if not self.table_was_created:
            await self.create_table_if_not_exists()

        async with aiosqlite.connect(self.db_path) as db:
            response = await db.execute(
                """
                    SELECT
                        seqnum,
                        screenshot,
                        is_focused,
                        num_mouse_clicks,
                        mouse_scroll_distance,
                        mouse_move_distance,
                        keyboard_strokes
                    FROM feedbacks
                    LIMIT 10
                """
            )
            result = await response.fetchall()
        return [
            Feedback(
                seqnum=f[0],
                screenshot=f[1],
                personal_analytics_data=PaFeedback(
                    isFocused=f[2],
                    numMouseClicks=f[3],
                    mouseScrollDistance=f[4],
                    mouseMoveDistance=f[5],
                    keyboardStrokes=f[6],
                ),
            )
            for f in result
        ]
