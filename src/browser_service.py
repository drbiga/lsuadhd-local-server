import os

import logging

import asyncio
from asyncio import Lock

import webbrowser

from services import SessionService


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
        async with self.lock:
            if self.is_running:
                raise RuntimeError(
                    "[ BrowserService.start_browser_worker ] The worker has already started"
                )
            self.is_running = True

        session_progress = await self.session_service.get_session_progress()

        while not session_progress.has_finished_homework():
            await asyncio.sleep(1)
            session_progress = await self.session_service.get_session_progress()

        if self.env == "dev":
            webbrowser.open("http://localhost:5173/?autoclose=true")
        elif self.env == "prod":
            url = f"{self.frontend_url}?autoclose=true"
            webbrowser.open(url)

        async with self.lock:
            if not self.is_running:
                logging.error(
                    "[ BrowserService ] Something changed the state of is_running improperly"
                )
                raise RuntimeError(
                    "[ BrowserService ] Something changed the state of is_running improperly"
                )
            self.is_running = False

        logging.info("Chrome comeback worker finished")
