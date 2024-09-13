import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv

from feedback import collect_feedback
from api import create_app


def main():
    load_dotenv()

    # from personal_analytics import compress_database
    # compress_database()

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
