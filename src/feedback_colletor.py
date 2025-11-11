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
from connection import Connection


class FeedbackColletor:
    """This class will take care of collecting the feedback data from the laptop,
    including both personal analytics and screenshots."""

    def __init__(self, connection: Connection):
        self.connection = connection
        self.repository = FeedbackRepository()
        self.timing_service = TimingService()

        self.feedback_count = 0
        self.worker_is_running = False
        self.lock_worker_is_running = asyncio.Lock()

    async def worker(self):
        """Loop that collects the feedbacks for the session.

        Pre-conditions:
            - The connection has the session set
            - The user has started a session in the backend

        Post-conditions:
            - At least 90 feedbacks were collected
            - At least 90 feedbacks were sent to the server
            - At least 90 feedbacks were saved in the local database
            - The session is over

        Invariants:
            - The session is active throughout the entire collection loop
            - The worker method can only run once at a time, meaning a second call to it
                while it is still running should raise an exception

        Uses the timing service to implement the proper collection frequency.
        Proceeds to the next iteration if the server is not able to respond in time
        Uses the connection to
            - Send the data to the server
            - Receive the computed feedback back
            - Determine loop condition
        If there is no active session, the loop should not run
        Uses the database module to create a local copy of the feedback data that
            is sent to the server.
        """
        async with self.lock_worker_is_running:
            if self.worker_is_running:
                raise RuntimeError()
            self.worker_is_running = True

        # Pre-condition checks
        if self.connection.get_session() is None:
            raise AttributeError(
                "The session object must be set in the connection in order to start feedback collection"
            )

        session_still_active = await self.connection.is_session_active()
        if not session_still_active:
            raise RuntimeError(
                "A session must be active in order to start feedback collection"
            )

        # global current_worker_id, stop_collection
        timing_service = TimingService()
        logging.info("Starting worker...")
        while session_still_active:
            # Waits for the amount of time needed to run the loop once every minute
            await timing_service.wait()

            # Computing how much time it takes to run the feedback
            # to account for that in the wait method. If sending
            # the feedback and getting it back takes 20 seconds,
            # then the wait method will wait for 40 seconds, making
            # the whole loop execute once every minute
            timing_service.start_iteration()

            feedback = self.collect_feedback_data()
            self.repository.insert_new(feedback, self.connection.get_session())
            logging.info("Sending feedback")
            logging.info(json.dumps(feedback.model_dump()))
            try:
                session_still_active = await self.connection.send_feedback(feedback)
            except TimeoutError:
                logging.error("[ worker ] The server took too long to respond")
            except Exception as e:
                logging.error(
                    f"[ worker ] Error while sending feedback: {''.join(traceback.format_exc())}"
                )
            logging.info(f"Session is still active: {session_still_active}")

            timing_service.finish_iteration()

            if not session_still_active:
                logging.info("Session is not active anymore or collection stopped.")
                break

        async with self.lock_worker_is_running:
            self.worker_is_running = False

        logging.info(
            "Session worker exited. Initiating personal analytics database dump"
        )

    def collect_feedback_data(self) -> Feedback:
        self.feedback_count += 1

        pa_feedback = self.get_feedback_personal_analytics()
        screenshot = take_screenshot()
        feedback = Feedback(
            personal_analytics_data=pa_feedback,
            screenshot=screenshot,
        )
        return feedback

    def get_feedback_count_for_session(self) -> int:
        return self.feedback_count

    def get_feedback_personal_analytics(self) -> PaFeedback:
        pa_feedback = get_feedback_personal_analytics()
        return PaFeedback(
            numMouseClicks=pa_feedback.clickTotal,
            keyboardStrokes=pa_feedback.keyTotal,
            mouseMoveDistance=pa_feedback.movedDistance,
            mouseScrollDistance=pa_feedback.scrollDelta,
            isFocused=pa_feedback.isFocused,
        )
