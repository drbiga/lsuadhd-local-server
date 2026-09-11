import json
import logging

import asyncio

import traceback

from feedback import (
    Feedback,
    PaFeedback,
    get_feedback_personal_analytics,
    take_screenshot,
)
from feedback_repository import FeedbackRepository
from timing import TimingService
from services import SessionService, IamService


class FeedbackCollector:
    """This class will take care of collecting the feedback data from the laptop,
    including both personal analytics and screenshots."""

    def __init__(
        self,
        session_service: SessionService,
        iam_service: IamService,
        repository: FeedbackRepository,
        timing_service: TimingService,
    ):
        self.session_service = session_service
        self.iam_service = iam_service
        assert (
            repository is not None
        ), "[ FeedbackCollector.start_collecting ] FeedbackRepository cannot be None"
        assert (
            timing_service is not None
        ), "[ FeedbackCollector.start_collecting ] TimingService cannot be None"
        self.repository = repository
        self.timing_service = timing_service

        self.feedback_count = 0
        self.worker_is_running = False
        self.lock_worker_is_running = asyncio.Lock()

    async def start_collecting(self):
        """Loop that collects the feedbacks for the session.

        Pre-conditions:
            - The backend has the session set
            - The user has started a session in the backend

        Post-conditions:
            - At least 1 feedback was collected
            - All collected feedbacks were sent to the backend, but no guarantees are made. The collector will try once
            - All collected feedbacks were saved in the local database
            - The session is over

        Invariants:
            - The session is active throughout the entire collection loop
            - The worker method can only run once at a time, meaning a second call to it
                while it is still running should raise an exception

        Uses the timing service to implement the proper collection frequency.
        Proceeds to the next iteration if the server is not able to respond in time
        Uses the backend to
            - Send the data to the server
            - Receive the computed feedback back
            - Determine loop condition
        If there is no active session, the loop should not run
        Uses the database module to create a local copy of the feedback data that
            is sent to the server.
        """
        async with self.lock_worker_is_running:
            if self.worker_is_running:
                logging.info("[ FeedbackCollector ] Worker already running")
                return
            self.worker_is_running = True

        # Pre-condition checks
        if self.iam_service.get_iam_session() is None:
            logging.error("[ FeedbackCollector ] IamSession is not set, cannot start collection")
            async with self.lock_worker_is_running:
                self.worker_is_running = False
            return

        session_still_active = await self.session_service.is_session_active()
        if not session_still_active:
            logging.error("[ FeedbackCollector ] No active session, cannot start collection")
            async with self.lock_worker_is_running:
                self.worker_is_running = False
            return

        # Feedback ids restart at 1 for every session, so this counter has to restart too.
        self.feedback_count = 0

        logging.info("Starting worker...")
        while session_still_active:
            async with self.lock_worker_is_running:
                if not self.worker_is_running:
                    # Added a new method to stop collection, so now I'm adding this break
                    # statement in case the stop method changed the state of the worker_is_running
                    # attribute to false
                    break

            # Waits for the amount of time needed to run the loop once every minute
            await self.timing_service.wait()

            # Computing how much time it takes to run the feedback
            # to account for that in the wait method. If sending
            # the feedback and getting it back takes 20 seconds,
            # then the wait method will wait for 40 seconds, making
            # the whole loop execute once every minute
            self.timing_service.start_iteration()

            try:
                feedback = await self._collect_feedback_data()
            except Exception:
                # Personal Analytics or the screenshot grab failed 
                # (for insance, the PA app is not running).
                logging.error(
                    "[ FeedbackCollector ] Error collecting feedback data (PA/screenshot): "
                    + traceback.format_exc()
                )
                self.timing_service.finish_iteration()
                await asyncio.sleep(1)
                continue

            # Save locally before sending, so the data survives upload failure
            # insert_new gives the feedback its per-session id
            try:
                await self.repository.insert_new(
                    feedback, self.iam_service.get_iam_session()
                )
            except Exception as e:
                logging.error(
                    f"[ worker ] Error while saving the feedback locally: {traceback.format_exc()}"
                )
                # The local insert is what assigns the real per-session id, so it never ran.
                # seqnum still holds self.feedback_count, which counts every feedback this
                # process has ever collected across all sessions - not this session's id.
                # Send -1 so the backend assigns the id itself, the same path it uses for
                # older clients that send no id at all
                feedback.seqnum = -1

            logging.info("Sending feedback")
            logging.info(json.dumps(feedback.model_dump()))
            try:
                session_still_active = await self.session_service.ingest_feedback(
                    feedback
                )
            except TimeoutError:
                logging.error("[ worker ] The server took too long to respond")
            except Exception as e:
                logging.error(
                    f"[ worker ] Error while sending feedback: {traceback.format_exc()}"
                )

            logging.info(f"Session is still active: {session_still_active}")

            self.timing_service.finish_iteration()

            if not session_still_active:
                logging.info("Session is not active anymore or collection stopped.")
                break

        async with self.lock_worker_is_running:
            self.worker_is_running = False

        logging.info(
            "Session worker exited."
        )

    async def _collect_feedback_data(self) -> Feedback:
        self.feedback_count += 1

        pa_feedback = await self._get_feedback_personal_analytics()
        screenshot = take_screenshot()
        feedback = Feedback(
            seqnum=self.feedback_count,
            personal_analytics_data=pa_feedback,
            screenshot=screenshot,
        )
        return feedback

    def get_feedback_count_for_session(self) -> int:
        return self.feedback_count

    async def _get_feedback_personal_analytics(self) -> PaFeedback:
        pa_feedback = await get_feedback_personal_analytics()
        return PaFeedback(
            numMouseClicks=pa_feedback.clickTotal,
            keyboardStrokes=pa_feedback.keyTotal,
            mouseMoveDistance=pa_feedback.movedDistance,
            mouseScrollDistance=pa_feedback.scrollDelta,
            isFocused=pa_feedback.isFocused,
        )

    async def stop_collecting(self):
        async with self.lock_worker_is_running:
            if not self.worker_is_running:
                raise RuntimeError(
                    "[ FeedbackCollector.stop_collecting ] Collector is not running"
                )
            # Setting this variable to false will trigger a break statement on the
            # collection loop
            self.worker_is_running = False
