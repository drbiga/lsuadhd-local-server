import os

import httpx

import logging
import json

import asyncio
import traceback

from fastapi import FastAPI, status, HTTPException

from session import IamSession

from feedback_collector import FeedbackCollector
from browser_service import BrowserService
from reconcile import reconcile_pending_feedbacks, count_pending_feedbacks


def create_app(
    feedback_collector: FeedbackCollector,
    browser_service: BrowserService,
) -> FastAPI:
    app = FastAPI()
    tasks = []
    reconcile_lock = asyncio.Lock()

    @app.get("/checkPA")
    async def check_pa() -> bool:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("http://localhost:57827/intervention_status")
            return True
        except Exception as e:
            logging.error(f"[checkPA] Personal Analytics not reachable: {e}")
            return False

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

    @app.get("/reconcile/pending")
    async def reconcile_pending():
        # Check how many locally-saved feedbacks never made it to the cloud
        iam_session = feedback_collector.iam_service.get_iam_session()
        if iam_session is None:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, {"status": "error", "message": "No session set"})
        try:
            pending = await count_pending_feedbacks(
                feedback_collector.session_service,
                feedback_collector.repository,
                iam_session,
            )
            return {"pending": pending}
        except Exception as e:
            logging.error(f"[reconcile_pending] Exception: {e}\n{traceback.format_exc()}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, {"status": "error", "message": str(e)})

    @app.post("/reconcile")
    async def reconcile():
        # Restore every locally-saved feedback the cloud is missing, then replay each affected session
        iam_session = feedback_collector.iam_service.get_iam_session()
        if iam_session is None:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, {"status": "error", "message": "No session set"})
        async with reconcile_lock:
            try:
                summary = await reconcile_pending_feedbacks(
                    feedback_collector.session_service,
                    feedback_collector.repository,
                    iam_session,
                )
                return {"status": "success", **summary}
            except Exception as e:
                logging.error(f"[reconcile] Exception: {e}\n{traceback.format_exc()}")
                raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, {"status": "error", "message": str(e)})

    return app
