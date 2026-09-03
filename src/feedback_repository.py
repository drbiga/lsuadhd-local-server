import os

import logging

from datetime import datetime

import aiosqlite

from feedback import Feedback
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
        """        
        Reflects the cloud's session_execution__personal_analytics table (same activity columns and primary key)
        but also adds the local screenshot path and the capture time
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                    CREATE TABLE IF NOT EXISTS personal_analytics (
                        id INTEGER NOT NULL,
                        session_seqnum INTEGER NOT NULL,
                        student_name TEXT NOT NULL,
                        num_mouse_clicks INTEGER,
                        mouse_move_distance REAL,
                        mouse_scroll_distance REAL,
                        num_keyboard_strokes INTEGER,
                        is_focused INTEGER,
                        screenshot TEXT,
                        created_at TEXT,
                        PRIMARY KEY (id, session_seqnum, student_name)
                    );
                """
            )
            await db.commit()
            if not self.table_was_created:
                logging.info(
                    "[ FeedbackRepository.create_table_if_not_exists ] personal_analytics table was created"
                )
                self.table_was_created = True

    async def insert_new(self, feedback: Feedback, session: IamSession) -> int:
        """
        Save one set of feedback locally, give it a per-session id and return it.

        The id is "largest id thus far + 1". 
        
        Important!! The local database the source of truth for feedback ids.
        The local ID is sent to the backend so local/cloud remain in sync.
        """
        if not self.table_was_created:
            await self.create_table_if_not_exists()

        if session.session_num is None:
            raise RuntimeError(
                "[ FeedbackRepository.insert_new ] Session num was not yet set"
            )

        personal_analytics = feedback.personal_analytics_data

        async with aiosqlite.connect(self.db_path) as db:
            next_id = await self._next_feedback_id(
                db, session.user.username, session.session_num
            )
            feedback.seqnum = next_id
            await db.execute(
                """
                INSERT INTO personal_analytics VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    next_id,
                    session.session_num,
                    session.user.username,
                    personal_analytics.numMouseClicks,
                    personal_analytics.mouseMoveDistance,
                    personal_analytics.mouseScrollDistance,
                    personal_analytics.keyboardStrokes,
                    personal_analytics.isFocused,
                    feedback.screenshot,
                    datetime.now().isoformat(),
                ),
            )
            await db.commit()

        return next_id

    async def _next_feedback_id(
        self, db: aiosqlite.Connection, student_name: str, session_seqnum: int
    ) -> int:
        """
        Return the next per-session feedback id. Getting the ID from the table 
        (instead of memory counter) ensures itll stay correct even if the collector 
        restarts mid-session.
        """
        cursor = await db.execute(
            """
                SELECT MAX(id) FROM personal_analytics
                WHERE student_name = ? AND session_seqnum = ?
            """,
            (student_name, session_seqnum),
        )
        (max_id,) = await cursor.fetchone()
        return (max_id or 0) + 1

    async def get_all(self) -> list[dict]:
        if not self.table_was_created:
            await self.create_table_if_not_exists()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            response = await db.execute(
                """
                    SELECT
                        id,
                        session_seqnum,
                        student_name,
                        num_mouse_clicks,
                        mouse_move_distance,
                        mouse_scroll_distance,
                        num_keyboard_strokes,
                        is_focused,
                        screenshot,
                        created_at
                    FROM personal_analytics
                """
            )
            rows = await response.fetchall()

        return [dict(row) for row in rows]

    async def get_local_session_seqnums(self, student_name: str) -> list[int]:
        """Return the session numbers a student has any locally-saved feedback for"""
        if not self.table_was_created:
            await self.create_table_if_not_exists()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                    SELECT DISTINCT session_seqnum FROM personal_analytics
                    WHERE student_name = ?
                    ORDER BY session_seqnum
                """,
                (student_name,),
            )
            rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def get_feedbacks_for_session(
        self, student_name: str, session_seqnum: int
    ) -> list[dict]:
        """
        Return all locally-saved feedback rows for one session, with the oldest id first.
        This is used to re-send the ones the cloud might be missing
        """
        if not self.table_was_created:
            await self.create_table_if_not_exists()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                    SELECT
                        id,
                        session_seqnum,
                        student_name,
                        num_mouse_clicks,
                        mouse_move_distance,
                        mouse_scroll_distance,
                        num_keyboard_strokes,
                        is_focused,
                        screenshot,
                        created_at
                    FROM personal_analytics
                    WHERE student_name = ? AND session_seqnum = ?
                    ORDER BY id
                """,
                (student_name, session_seqnum),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]
