import os

import httpx

import logging
import json

import asyncio
import traceback

from fastapi import FastAPI, status, HTTPException

from session import IamSession

from feedback_colletor import FeedbackColletor
from browser_service import BrowserService


def create_app(
    feedback_collector: FeedbackColletor,
    browser_service: BrowserService,
) -> FastAPI:
    app = FastAPI()
    tasks = []

    @app.get("/checkPA")
    async def check_pa() -> dict:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://localhost:57827/intervention_status"
                )
            return {"status": "success", "active": True}
        except Exception as e:
            logging.error(f"[checkPA] Exception: {e}")
            return {"status": "error", "active": False, "message": str(e)}

    @app.post("/session")
    async def set_session(session: IamSession):
        try:
            logging.info(json.dumps(session.model_dump()))
            feedback_collector.iam_service.set_iam_session(session)
            feedback_collector.session_service.set_iam_session(session)
            session_active = await feedback_collector.session_service.is_session_active()
            if session_active:
                worker_task = asyncio.create_task(feedback_collector.start_collecting())
                browser_task = asyncio.create_task(browser_service.start_browser_worker())
                tasks.append(worker_task)
                tasks.append(browser_task)
                worker_task.add_done_callback(lambda r: tasks.remove(worker_task) if worker_task in tasks else None)
                browser_task.add_done_callback(lambda r: tasks.remove(browser_task) if browser_task in tasks else None)
            return {"status": "success", "message": "Session set and collection started if session is active."}
        except HTTPException as he:
            raise he
        except Exception as e:
            logging.error(f"[set_session] Exception: {e}\n{traceback.format_exc()}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, {"status": "error", "message": str(e)})

    @app.get("/session")
    async def get_session():
        try:
            iam_session = feedback_collector.iam_service.get_iam_session()
            if iam_session is not None:
                return iam_session
            else:
                message = "The user has not logged in on the web app yet"
                logging.info(message)
                raise HTTPException(
                    status.HTTP_412_PRECONDITION_FAILED,
                    {"status": "error", "message": message},
                )
        except HTTPException as he:
            raise he
        except Exception as e:
            logging.error(f"[get_session] Exception: {e}\n{traceback.format_exc()}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, {"status": "error", "message": str(e)})

    @app.post("/collection")
    async def start_collecting():
        try:
            # Check if session is active
            session_active = await feedback_collector.session_service.is_session_active()
            if not session_active:
                return {"status": "error", "message": "No active session. Cannot start collection."}, status.HTTP_400_BAD_REQUEST
            # Check if worker is already running
            if feedback_collector.worker_is_running:
                return {"status": "error", "message": "Collection already running."}, status.HTTP_409_CONFLICT
            worker_task = asyncio.create_task(feedback_collector.start_collecting())
            browser_task = asyncio.create_task(browser_service.start_browser_worker())
            tasks.append(worker_task)
            tasks.append(browser_task)
            worker_task.add_done_callback(lambda r: tasks.remove(worker_task) if worker_task in tasks else None)
            browser_task.add_done_callback(lambda r: tasks.remove(browser_task) if browser_task in tasks else None)
            return {"status": "success", "message": "Data collection has started"}
        except Exception as e:
            logging.error(f"[start_collecting] Exception: {e}\n{traceback.format_exc()}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, {"status": "error", "message": str(e)})

    @app.post("/stop_collection")
    async def stop_collecting():
        try:
            # If not running, return 409
            if not feedback_collector.worker_is_running:
                return {"status": "error", "message": "Collection is not running."}, status.HTTP_409_CONFLICT
            asyncio.create_task(feedback_collector.stop_collecting())
            return {"status": "success", "message": "Data collection stopped successfully"}
        except Exception as e:
            logging.error(f"[stop_collecting] Exception: {e}\n{traceback.format_exc()}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, {"status": "error", "message": str(e)})

    return app
