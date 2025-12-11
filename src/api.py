import os

import traceback

import httpx

import logging
import json

import asyncio

from fastapi import FastAPI, status, HTTPException, BackgroundTasks

from session import IamSession
from connection import Connection
from feedback import collect_feedback, clean
from timing import TimingService

# from personal_analytics import get_tracking_data
from tracking import UserInput, WindowsActivity
import webbrowser

from feedback_colletor import FeedbackColletor
from browser_service import BrowserService


# def create_app(connection: Connection) -> FastAPI:
#     app = FastAPI()

#     global stop_collection
#     stop_collection = False
#     global current_worker_id
#     current_worker_id = 0

#     tasks = []

#     @app.get("/checkPA")
#     async def check_pa() -> bool:
#         async with httpx.AsyncClient() as client:
#             try:
#                 response = await client.get(
#                     "http://localhost:57827/intervention_status"
#                 )
#                 return True
#             except:
#                 return False

#     @app.post("/session")
#     async def set_session(session: IamSession) -> None:
#         global stop_collection
#         global current_worker_id

#         logging.info(json.dumps(session.model_dump()))
#         connection.set_session(session)
#         if await connection.is_session_active():
#             # If the session is already running, we want to start
#             # collecting feedback
#             current_worker_id += 1
#             worker_task = asyncio.create_task(worker(current_worker_id))
#             browser_task = asyncio.create_task(
#                 chrome_comeback_worker(current_worker_id)
#             )
#             tasks.append(worker_task)
#             tasks.append(browser_task)
#             worker_task.add_done_callback(lambda result: tasks.remove(worker_task))
#             browser_task.add_done_callback(lambda result: tasks.remove(browser_task))
#         # At every new session that is set, we should stop
#         # sending feedbacks in case we are sending them

#     @app.get("/session")
#     async def get_session() -> IamSession:
#         if connection.session is not None:
#             return connection.session
#         else:
#             message = "The user has not logged in on the web app yet"
#             logging.info(message)
#             raise HTTPException(
#                 status.HTTP_412_PRECONDITION_FAILED,
#                 {"status": "err", "message": message},
#             )

#     @app.post("/collection")
#     async def start_collecting():
#         global current_worker_id, stop_collection
#         stop_collection = False
#         current_worker_id += 1
#         worker_task = asyncio.create_task(worker(current_worker_id))
#         browser_task = asyncio.create_task(chrome_comeback_worker(current_worker_id))
#         tasks.append(worker_task)
#         tasks.append(browser_task)

#         def worker_done(result=None):
#             logging.info(
#                 "Worker task has finished and is being removed from the tasks array"
#             )
#             tasks.remove(worker_task)

#         def browser_done(result=None):
#             logging.info(
#                 "Worker task has finished and is being removed from the tasks array"
#             )
#             tasks.remove(browser_task)

#         worker_task.add_done_callback(worker_done)
#         browser_task.add_done_callback(browser_done)

#     @app.post("/stop_collection")
#     async def stop_collecting():
#         global stop_collection, current_worker_id
#         stop_collection = True
#         current_worker_id += 1
#         logging.info("Data collection has now been stopped.")
#         return {"status": "success", "message": "Data collection stopped successfully"}

#     @app.post("/tracking")
#     async def send_tracking_database():
#         logging.info("Starting to send tracking database")
#         user_input_batch, windows_activity_batch = get_tracking_data()
#         user_input_batch = [
#             UserInput(
#                 username=connection.session.user.username,
#                 filename=ui.filename,
#                 id=ui.id,
#                 ts_time=ui.time,
#                 ts_start=ui.tsStart,
#                 ts_end=ui.tsEnd,
#                 keys_total=ui.keyTotal,
#                 clicks_total=ui.clickTotal,
#                 scroll_delta=ui.scrollDelta,
#                 moved_distance=ui.movedDistance,
#             ).model_dump()
#             for ui in user_input_batch
#         ]
#         windows_activity_batch = [
#             WindowsActivity(
#                 username=connection.session.user.username,
#                 filename=wa.filename,
#                 id=wa.id,
#                 ts_time=wa.time,
#                 ts_start=wa.tsStart,
#                 ts_end=wa.tsEnd,
#                 window_name=wa.window,
#                 process_name=wa.process,
#             ).model_dump()
#             for wa in windows_activity_batch
#         ]
#         logging.info(
#             f"TOTAL COUNT OF ROWS FOR ONE AND THE OTHER: {len(user_input_batch)} {len(windows_activity_batch)}"
#         )
#         batch_size = 10000
#         for i in range(len(user_input_batch) // batch_size + 1):
#             await connection.upload_tracking_user_input_batch(
#                 connection.session.user.username,
#                 user_input_batch[i * batch_size : (i + 1) * batch_size],
#             )

#         for i in range(len(windows_activity_batch) // batch_size + 1):
#             await connection.upload_tracking_windows_activity_batch(
#                 connection.session.user.username,
#                 windows_activity_batch[i * batch_size : (i + 1) * batch_size],
#             )

#     async def chrome_comeback_worker(wid: int):
#         global current_worker_id, stop_collection
#         # logging.info("Chrome comeback sob")
#         while current_worker_id == wid and not stop_collection:
#             # logging.info("Chrome comeback sob")
#             await asyncio.sleep(1)
#             try:
#                 finished = await connection.check_user_has_finished_homework()
#             except:
#                 continue
#             if finished:
#                 # logging.info("Checking if user has to return to survey ... Yes")
#                 if os.getenv("ENV", None) == "dev":
#                     webbrowser.open("http://localhost:5173/?autoclose=true")
#                 else:
#                     frontend_url = os.getenv("FRONTEND_URL")
#                     url = f"{frontend_url}?autoclose=true"
#                     webbrowser.open(url)
#                 break
#             # logging.info("Checking if user has to return to survey ... No")
#         logging.info("Chrome comeback worker finished")

#     async def worker(wid: int):
#         global current_worker_id, stop_collection
#         timing_service = TimingService()
#         logging.info("Starting worker...")
#         while current_worker_id == wid and not stop_collection:
#             # Waits for the amount of time needed to run the loop once every minute
#             await timing_service.wait()

#             # Computing how much time it takes to run the feedback
#             # to account for that in the wait method. If sending
#             # the feedback and getting it back takes 20 seconds,
#             # then the wait method will wait for 40 seconds, making
#             # the whole loop execute once every minute
#             timing_service.start_iteration()

#             try:
#                 feedback = await collect_feedback()
#             except:
#                 logging.error(
#                     "[ worker ] Error while collecting data from personal analytics"
#                 )
#                 timing_service.finish_iteration()
#                 await asyncio.sleep(1)
#                 continue
#             logging.info("Sending feedback")
#             logging.info(json.dumps(feedback.model_dump()))
#             try:
#                 session_still_active = await connection.send_feedback(feedback)
#             except Exception as e:
#                 timing_service.finish_iteration()
#                 logging.error(
#                     f"[ worker ] Error while sending feedback: {''.join(traceback.format_exc())}"
#                 )
#                 continue
#             logging.info(f"Session is still active: {session_still_active}")

#             timing_service.finish_iteration()

#             if not session_still_active or stop_collection:
#                 logging.info("Session is not active anymore or collection stopped.")
#                 break

#         logging.info(
#             "Session worker exited. Initiating personal analytics database dump"
#         )
#         await send_tracking_database()
#         logging.info("Worker finished")

#     return app


def create_app(
    feedback_collector: FeedbackColletor,
    browser_service: BrowserService,
) -> FastAPI:
    app = FastAPI()

    @app.get("/checkPA")
    async def check_pa() -> bool:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "http://localhost:57827/intervention_status"
                )
                return True
            except:
                return False

    @app.post("/session")
    async def set_session(
        session: IamSession, background_tasks: BackgroundTasks
    ) -> None:
        logging.info(json.dumps(session.model_dump()))
        feedback_collector.iam_service.set_iam_session(session)
        if await feedback_collector.session_service.is_session_active():
            # If the session is already running, we want to start
            # collecting feedback
            background_tasks.add_task(lambda: feedback_collector.start_collecting())
            background_tasks.add_task(lambda: browser_service.start_browser_worker())
        # At every new session that is set, we should stop
        # sending feedbacks in case we are sending them

    @app.get("/session")
    async def get_session() -> IamSession:
        iam_session = feedback_collector.iam_service.get_iam_session()
        if iam_session is not None:
            return iam_session
        else:
            message = "The user has not logged in on the web app yet"
            logging.info(message)
            raise HTTPException(
                status.HTTP_412_PRECONDITION_FAILED,
                {"status": "err", "message": message},
            )

    @app.post("/collection")
    async def start_collecting(background_tasks: BackgroundTasks):
        background_tasks.add_task(lambda: feedback_collector.start_collecting())
        background_tasks.add_task(lambda: browser_service.start_browser_worker())
        return {"status": "success", "message": "Data collection has started"}

    @app.post("/stop_collection")
    async def stop_collecting(background_tasks: BackgroundTasks):
        background_tasks.add_task(lambda: feedback_collector.stop_collecting())
        logging.info("Data collection has now been stopped.")
        return {"status": "success", "message": "Data collection stopped successfully"}

    return app
