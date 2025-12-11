import os
import asyncio

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv

from feedback import collect_feedback
from api import create_app
from personal_analytics import get_base_dir
from feedback_repository import FeedbackRepository
from connection import Connection

from feedback_colletor import FeedbackColletor
from services import SessionService, IamService
from browser_service import BrowserService
from timing import TimingService


def main():
    load_dotenv(dotenv_path=".env")

    env = os.getenv("ENV")

    if env == "dev":
        os.remove("info.log")

    logging.basicConfig(
        format="[%(asctime)s] %(message)s",
        level=logging.INFO,
        filename="info.log",
        filemode="a",
    )
    logging.info("=" * 80)
    logging.info("Starting new execution")

    if env == "dev":
        logging.info("Environment set to development")
    else:
        logging.info("Environment set to production")

    pa_base_dir = get_base_dir()
    logging.info(f"Base personal analytics path is {pa_base_dir}")

    if not os.path.exists("screenshots"):
        os.mkdir("screenshots")

    session_service = SessionService()
    iam_service = IamService()
    app = create_app(
        FeedbackColletor(
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
