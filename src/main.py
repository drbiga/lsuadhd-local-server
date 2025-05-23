import os

import logging

import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv

from feedback import collect_feedback
from api import create_app
from personal_analytics import get_base_dir


def main():
    load_dotenv()
    logging.basicConfig(
        format="[%(asctime)s] %(message)s",
        level=logging.INFO,
        filename="info.log",
        filemode="a",
    )
    logging.info("=" * 80)
    logging.info("Starting new execution")

    env = os.getenv("ENV")
    if env == "test":
        logging.info("Environment set to test")
    else:
        logging.info("Environment set to production")

    pa_base_dir = get_base_dir()
    logging.info(f"Base personal analytics path is {pa_base_dir}")

    app = create_app()
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
