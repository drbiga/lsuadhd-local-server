import asyncio
from typing import Annotated

from fastapi import FastAPI, UploadFile, Depends
from fastapi.security import OAuth2PasswordBearer


def create_timeout_case():
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="iam/session/token")

    app = FastAPI()

    @app.post("/session_execution/student/{student_name}/session/feedback")
    async def ingest_feedback_for_student(
        student_name: str,
        pa_feedback_str: str,
        screenshot_file: UploadFile,
        token: Annotated[str, Depends(oauth2_scheme)],
    ) -> dict:
        # Timeout should be triggered in 20 seconds
        await asyncio.sleep(20)
