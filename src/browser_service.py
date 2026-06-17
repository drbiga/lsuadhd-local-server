import os
import logging
import asyncio
from asyncio import Lock
import webbrowser
import websockets
import json

from services import SessionService, SessionProgress


class BrowserService:
    def __init__(self, session_service: SessionService):
        self.lock = Lock()
        self.is_running = False
        self.session_service = session_service
        self.frontend_url = os.getenv("FRONTEND_URL")
        if self.frontend_url is None or self.frontend_url == "":
            raise ValueError(
                "[ BrowserService.__init__ ] The FRONTEND_URL environment variable was not set"
            )
        self.env = os.getenv("ENV")
        if self.env is None or self.env == "":
            raise ValueError(
                "[ BrowserService.__init__ ] The ENV environment variable was not set"
            )

    async def start_browser_worker(self):
        """
        Starts a loop to periodically check if the browser needs to be opened to take
        the post survey after homework

        Pre-conditions
        - A session was started

        Post-conditions
        - The browser was opened
        """
        logging.info("[ BrowserService ] Browser worker started")
        async with self.lock:
            if self.is_running:
                logging.info("[ BrowserService ] Already running, skipping")
                return
            self.is_running = True

        ws_url = self.session_service.get_websocket_url()
        try:
            while True:
                try:
                    async with websockets.connect(ws_url) as ws:
                        logging.info(f"[ BrowserService ] WebSocket connected: {ws_url}")
                        async for msg in ws:
                            progress = SessionProgress(**json.loads(msg))
                            if progress.has_finished_homework():
                                if self.env == "TEST":
                                    webbrowser.open("http://localhost:5173/?autoclose=true")
                                elif self.env == "PROD":
                                    webbrowser.open(f"{self.frontend_url}?autoclose=true")
                                return
                except Exception as e:
                    logging.warning(f"[ BrowserService ] WebSocket error/disconnect: {e}")
                    await asyncio.sleep(2) # retry websocket connection repeatedly every 2 sec if failed
        finally:
            async with self.lock:
                self.is_running = False
                logging.info("[ BrowserService ] Chrome comeback worker finished")
