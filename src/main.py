import os
import asyncio

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv

from api import create_app
from personal_analytics import get_base_dir
from feedback_repository import FeedbackRepository

from feedback_collector import FeedbackCollector
from services import SessionService, IamService
from browser_service import BrowserService
from timing import TimingService


def main():
    load_dotenv(dotenv_path="../.env")

    env = os.getenv("ENV")

    if env == "TEST" and os.path.exists("info.log"):
        os.remove("info.log")

    logging.basicConfig(
        format="[%(asctime)s] %(message)s",
        level=logging.INFO,
        filename="info.log",
        filemode="a",
    )
    logging.info("=" * 80)
    logging.info("Starting new execution")

    if env == "TEST":
        logging.info("Environment set to development/testing")
    else:
        logging.info("Environment set to production")

    pa_base_dir = get_base_dir()
    logging.info(f"Base personal analytics path is {pa_base_dir}")

    if not os.path.exists("screenshots"):
        os.mkdir("screenshots")

    session_service = SessionService()
    iam_service = IamService()
    app = create_app(
        FeedbackCollector(
            session_service, iam_service, FeedbackRepository(), TimingService()
        ),
        BrowserService(session_service),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_headers=["*"],
        allow_methods=["*"],
        allow_origins=["*"],
        allow_credentials=True,
    )
    uvicorn.run(app, port=8001)


if __name__ == "__main__":
    main()
