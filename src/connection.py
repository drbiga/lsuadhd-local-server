import os

import logging

import httpx
import requests
import json

from session import Session, User
from feedback import Feedback


class HealthCheckError(Exception):
    def __init__(self) -> None:
        super().__init__("Health Check Error. Could not connect to the server")


class Connection:
    base_url: str
    session: Session

    def __init__(self) -> None:
        host = os.getenv("BACKEND_HOST")
        port = int(os.getenv("BACKEND_PORT"))
        self.base_url = f"http{'s' if port == 443 else ''}://{host}:{port}/api"
        try:
            response = requests.get(f"{self.base_url}/health_check")
        except requests.exceptions.ConnectionError:
            raise HealthCheckError()
        if response.status_code != 200 or response.json()["status"] != "ok":
            raise HealthCheckError()
        self.session = None

    def set_session(self, session: Session) -> None:
        self.session = session

    async def connect(self) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/iam/session/{self.session.token}"
            )
            if (
                response.status_code == 200
                and response.json()["token"] == self.session.token
            ):
                logging.info("Connected")
            else:
                raise ConnectionError("It was not possible to connect to the backend")

    async def send_feedback(self, feedback: Feedback) -> bool:
        """Returns a flag if session is still active and false otherwise.
        This is used to control the state and know when to stop sending
        feedbacks to the backend"""
        pa_feedback_str = json.dumps(feedback.personal_analytics_data.model_dump())

        with open(feedback.screenshot, "rb") as screenshot_file:
            logging.info("Sending feedback")
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        f"{self.base_url}/session_execution/student/{self.session.user.username}/session/feedback",
                        headers={"Authorization": f"Bearer {self.session.token}"},
                        params={
                            "pa_feedback_str": pa_feedback_str,
                        },
                        files={"screenshot_file": screenshot_file},
                    )
                except Exception as e:
                    logging.error("There was an error while sending the feedback")
                    logging.error(str(e))
        logging.info("Feedback sent")
        try:
            logging.info(
                f"Got {response.status_code} while sending feedback: {response.json()}"
            )
        except:
            try:
                logging.info(
                    f"Got {response.status_code} while sending feedback: {response.content}"
                )
            except:
                pass

        if response.status_code == 400:
            if response.json()["detail"]["errcode"] == 1:
                return False
        return True

    async def get_current_feedback(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/session_execution/student/{self.session.user.username}/session/feedback",
                headers={"Authorization": f"Bearer {self.session.token}"},
            )
            try:
                return response.json()
            except:
                return None

    async def check_user_has_active_session(self) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/session_execution/student",
                params={"student_name": self.session.user.username},
            )
            if response.status_code != 200:
                logging.debug(
                    f"Received status code {response.status_code} in Connection.check_user_has_active_session()"
                )
                return False
            else:
                student = response.json()
                if len(student["sessions"]) == 0:
                    return False
                if student["sessions"][-1]["stage"] != "FINISHED":
                    return True
                return False

    async def check_user_has_finished_homework(self) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/session_execution/student",
                params={"student_name": self.session.user.username},
            )
            if response.status_code != 200:
                logging.debug(
                    f"Received status code {response.status_code} in Connection.check_user_has_finished_homework()"
                )
                return False
            else:
                student = response.json()
                assert "sessions" in student
                if len(student["sessions"]) == 0:
                    logging.error(
                        "[ Connection.check_user_has_finished_homework() ] Tried to check if user has finished homework but user does not even have an active session"
                    )
                    raise RuntimeError("Student does not have an active session")
                return (
                    student["sessions"][-1]["stage"] == "homework"
                    and student["sessions"][-1]["remaining_time_seconds"] < 5
                ) or student["sessions"][-1]["stage"] == "survey"

    async def upload_tracking_user_input_batch(
        self, student_name: str, batch: list[dict]
    ) -> None:
        async with httpx.AsyncClient() as client:
            try:
                logging.info("Uploading user input tracking data", batch[0])
                response = await client.post(
                    f"{self.base_url}/tracking/user_input",
                    json=batch,
                    params={"student_name": student_name},
                )
                if response.status_code != 200:
                    logging.debug(
                        f"Received status code {response.status_code} in Connection.upload_tracking_user_input_batch()"
                    )

                logging.info(f"Success when uploading tracking data: {response.json()}")
            except Exception as e:
                logging.debug(e)
                logging.debug("Error while uploading windows activity batch")

    async def upload_tracking_windows_activity_batch(
        self, student_name: str, batch: list[dict]
    ) -> None:
        async with httpx.AsyncClient() as client:
            try:
                logging.info(f"Uploading window activity tracking data: {batch[0]}")
                response = await client.post(
                    f"{self.base_url}/tracking/windows_activity",
                    json=batch,
                    params={"student_name": student_name},
                )
                if response.status_code != 200:
                    logging.debug(
                        f"Received status code {response.status_code} in Connection.upload_traupload_tracking_windows_activity_batchcking_user_input_batch()"
                    )
                logging.info(
                    f"Success when uploading windows activity batch: {response.json()}"
                )
            except Exception as e:
                logging.debug(e)
                logging.debug("Error while uploading tracking data")
