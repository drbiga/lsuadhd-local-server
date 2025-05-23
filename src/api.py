import os

import logging

import asyncio
from fastapi import FastAPI, status, HTTPException
from session import Session
from connection import Connection
from feedback import collect_feedback, clean
from timing import TimingService
from personal_analytics import get_tracking_data
from tracking import UserInput, WindowsActivity
import webbrowser


def create_app() -> FastAPI:
    connection = Connection()

    app = FastAPI()

    global stop_collection
    stop_collection = False
    global current_worker_id
    current_worker_id = 0

    @app.post("/session")
    async def set_session(session: Session) -> None:
        global stop_collection
        global current_worker_id

        logging.info(session.model_dump())
        connection.set_session(session)
        if connection.check_user_has_active_session():
            # If the session is already running, we want to start
            # collecting feedback
            current_worker_id += 1
            asyncio.ensure_future(worker(current_worker_id))
            asyncio.ensure_future(chrome_comeback_worker(current_worker_id))
        # At every new session that is set, we should stop
        # sending feedbacks in case we are sending them

    @app.get("/session")
    def get_session() -> Session:
        if connection.session is not None:
            return connection.session
        else:
            message = "The user has not logged in on the web app yet"
            logging.info(message)
            raise HTTPException(
                status.HTTP_412_PRECONDITION_FAILED,
                {"status": "err", "message": message},
            )

    @app.post("/collection")
    async def start_collecting():
        global current_worker_id
        current_worker_id += 1
        asyncio.ensure_future(chrome_comeback_worker(current_worker_id))
        asyncio.ensure_future(worker(current_worker_id))

    @app.post("/tracking")
    def send_tracking_database():
        logging.info("Starting to send tracking database")
        user_input_batch, windows_activity_batch = get_tracking_data()
        user_input_batch = [
            UserInput(
                username=connection.session.user.username,
                filename=ui.filename,
                id=ui.id,
                ts_time=ui.time,
                ts_start=ui.tsStart,
                ts_end=ui.tsEnd,
                keys_total=ui.keyTotal,
                clicks_total=ui.clickTotal,
                scroll_delta=ui.scrollDelta,
                moved_distance=ui.movedDistance,
            ).model_dump()
            for ui in user_input_batch
        ]
        windows_activity_batch = [
            WindowsActivity(
                username=connection.session.user.username,
                filename=wa.filename,
                id=wa.id,
                ts_time=wa.time,
                ts_start=wa.tsStart,
                ts_end=wa.tsEnd,
                window_name=wa.window,
                process_name=wa.process,
            ).model_dump()
            for wa in windows_activity_batch
        ]
        logging.info(
            "TOTAL COUNT OF ROWS FOR ONE AND THE OTHER:",
            len(user_input_batch),
            len(windows_activity_batch),
        )
        batch_size = 10000
        for i in range(len(user_input_batch) // batch_size + 1):
            connection.upload_tracking_user_input_batch(
                connection.session.user.username,
                user_input_batch[i * batch_size : (i + 1) * batch_size],
            )

        for i in range(len(windows_activity_batch) // batch_size + 1):
            connection.upload_tracking_windows_activity_batch(
                connection.session.user.username,
                windows_activity_batch[i * batch_size : (i + 1) * batch_size],
            )

    async def chrome_comeback_worker(wid: int):
        global current_worker_id
        logging.info("Chrome comeback sob")
        while current_worker_id == wid:
            logging.info("Chrome comeback sob")
            await asyncio.sleep(1)
            logging.info("Checking if user has to return to survey ... ", end="")
            if connection.check_user_has_finished_homework():
                logging.info("Yes")
                if os.getenv("ENV", None) == "test":
                    webbrowser.open("http://localhost:5173/lsuadhd-frontend/")
                else:
                    webbrowser.open("https://drbiga.github.io/lsuadhd-frontend/")
                break
            logging.info("No")
        logging.info("Chrome comeback worker finished")

    async def worker(wid: int):
        global current_worker_id
        timing_service = TimingService()
        logging.info("Starting worker...")
        while current_worker_id == wid:
            # Waits for the amount of time needed to run the loop once every minute
            await timing_service.wait()

            # Computing how much time it takes to run the feedback
            # to account for that in the wait method. If sending
            # the feedback and getting it back takes 20 seconds,
            # then the wait method will wait for 40 seconds, making
            # the whole loop execute once every minute
            timing_service.start_iteration()

            feedback = collect_feedback()
            logging.info("Sending feedback")
            logging.info(feedback.model_dump())
            try:
                session_still_active = connection.send_feedback(feedback)
            except:
                timing_service.finish_iteration()
                continue
            logging.info("Session is still active:", session_still_active)
            # clean(feedback)
            processed_feedback = connection.get_current_feedback()
            logging.info("=" * 80)
            logging.info("Processed feedback")
            logging.info(processed_feedback)
            logging.info("=" * 80)
            if processed_feedback is None:
                timing_service.finish_iteration()
                continue
            # if (
            #     "output" in processed_feedback
            #     and processed_feedback["output"] == "distracted"
            # ):
            #     logging.info("Setting time to wait to 20")
            #     timing_service.set_time(20)
            # else:
            #     logging.info("Setting time to wait to 60")
            #     timing_service.set_time(60)

            timing_service.finish_iteration()

            if not session_still_active:
                logging.info("Session is not active anymore")
                break

        send_tracking_database()
        logging.info("Worker finished")

    return app
