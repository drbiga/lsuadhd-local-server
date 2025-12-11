import os
import requests
import httpx

import logging

import json

from pydantic import BaseModel
from pydantic_core import ValidationError

from session import IamSession
from feedback import Feedback


class HealthCheckError(Exception):
    def __init__(self) -> None:
        super().__init__("Health Check Error. Could not connect to the server")


class SessionProgress(BaseModel):
    stage: str
    remaining_time: int

    def has_finished_homework(self) -> bool:
        if self.stage.lower() == "homework" and self.remaining_time < 5:
            return True
        if self.stage.lower() in ["survey", "finished"]:
            return True
        return False


class SessionService:
    TIMEOUT_SECONDS = 15

    # Session Progress errors
    SESSION_PROGRESS_ERR_NO_ACTIVE_SESSION = "You do not have an active session yet"
    SESSION_PROGRESS_ERR_UNAUTHORIZED = "You are not authorized to perform this action"

    def __init__(self):
        """Handles all requests to the endpoints related to the session service in the backend

        This class performs data validation for the following environment variables
        - BACKEND_HOST
        - BACKEND_PORT
        - PATH_PREFIX
        - ENV
        """
        host = os.getenv("BACKEND_HOST", None)
        port_str: str = os.getenv("BACKEND_PORT", None)
        path_prefix = os.getenv("PATH_PREFIX", None)
        env = os.getenv("ENV", None)

        if host is None:
            raise ValueError("[ SessionService.__init__ ] Host cannot be None")
        if port_str is None:
            raise ValueError("[ SessionService.__init__ ] Port cannot be None")
        if not port_str.isdigit():
            raise ValueError("[ SessionService.__init__ ] Port has to be a number")
        if path_prefix is None:
            raise ValueError("[ SessionService.__init__ ] Path prefix cannot be None")
        if env is None:
            raise ValueError("[ SessionService.__init__ ] Env cannot be None")
        if env not in ["DEV", "TEST", "PROD"]:
            raise ValueError(
                "[ SessionService.__init__ ] Env has to one of DEV, TEST, or PROD"
            )

        port = int(port_str)

        self.base_url = f"http{'s' if port == 443 else ''}://{host}:{port}{path_prefix}"

        if env == "PROD":
            try:
                response = requests.get(f"{self.base_url}/health_check")
            except requests.exceptions.ConnectionError:
                raise HealthCheckError()
            if response.status_code != 200 or response.json()["status"] != "ok":
                raise HealthCheckError()
        self.iam_session = None

    async def get_session_progress(self) -> SessionProgress:
        """Get the session progress for the current authenticated student.

        Pre-conditions
        - An IamSession object needs to be set
        - A session needs to be running (see associated error)

        Post-conditions
        - Return value is not none (see associated error)
        - Type is enforced

        Raises
        ------
            ValueError - If the server returned something that json cannot parse
            RuntimeError - If there is no authenticated users
            RuntimeError - If there is no active session for the authenticated user
            RuntimeError - If the backend returns an unknown exception
        """
        if self.iam_session is None:
            raise RuntimeError(
                "[ Backend.get_session_progress ] IamSession is still none"
            )
        async with httpx.AsyncClient() as client:
            progress = await client.get(
                f"/student/{self.iam_session.user.username}/session"
            )

        if progress is None:
            raise ValueError("[ Backend.get_session_progress ] SessionProgress is None")

        try:
            progress = progress.json()
        except json.JSONDecodeError:
            raise ValueError(
                "[ Backend.get_session_progress ] JSON cannot parse the response"
            )

        if "status" in progress and progress["status"] == "err":
            if (
                progress["message"]
                == SessionService.SESSION_PROGRESS_ERR_NO_ACTIVE_SESSION
            ):
                raise RuntimeError(
                    "[ Backend.get_session_progress ] There is no session running for the authenticated user"
                )
            elif (
                progress["message"] == SessionService.SESSION_PROGRESS_ERR_UNAUTHORIZED
            ):
                raise RuntimeError(
                    "[ Backend.get_session_progress ] Unauthorized error"
                )
            else:
                raise RuntimeError("[ Backend.get_session_progress ] Unknown exception")

        try:
            session_progress = SessionProgress(**progress)
        except ValidationError:
            raise ValueError(
                "[ Backend.get_session_progress ] The returned value is not a session progress object (validation failed)"
            )

        return session_progress

    def get_iam_session(self) -> IamSession:
        return self.iam_session

    def set_iam_session(self, iam_session: IamSession) -> None:
        self.iam_session = iam_session

    async def is_session_active(self) -> bool:
        try:
            session_progress = await self.get_session_progress()
            if session_progress.stage.lower() == "finished":
                return False
        except RuntimeError:
            # A runtime error can be caused either by 1) a user not having an active session, or 2) a user not being authenticated
            # in the backend, both of which should be considered "Inactive"
            return False
        except ValueError:
            # The two situations where a ValueError is raised is when 1) the server returns something that is not a JSON, which
            # should not even happen, and 2) when the object the server returned is neither a session progress object nor an error
            # Both of these should be considered anomalies and the local server should proceed checking
            return True

        return True

    async def ingest_feedback(self, feedback: Feedback) -> Feedback:
        with open(feedback.screenshot, "rb") as screenshot_file:
            logging.info("Sending feedback")
            async with httpx.AsyncClient(
                timeout=SessionService.TIMEOUT_SECONDS
            ) as client:
                response = await client.post(
                    f"{self.base_url}/session_execution/student/{self.iam_session.user.username}/session/feedback",
                    headers={"Authorization": f"Bearer {self.iam_session.token}"},
                    params={
                        "pa_feedback_str": json.dumps(
                            feedback.personal_analytics_data.model_dump()
                        ),
                    },
                    files={"screenshot_file": screenshot_file},
                )
        return response.json()


class IamService:
    def __init__(self):
        self._iam_session: IamSession | None = None

    def set_iam_session(self, s: IamSession) -> None:
        if s is None:
            raise ValueError("[ IamService.set_iam_session ] IamSession cannot be none")

        self._iam_session = s

    def get_iam_session(self) -> IamSession:
        return self._iam_session
