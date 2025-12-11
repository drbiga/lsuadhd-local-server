import os
import traceback
import logging

import httpx
import requests
import json

from session import IamSession, User
from feedback import Feedback


class HealthCheckError(Exception):
    def __init__(self) -> None:
        super().__init__("Health Check Error. Could not connect to the server")


class Connection:
    base_url: str
    session: IamSession | None

    if os.getenv("env", "prod") == "prod":
        TIMEOUT_SECONDS = 20
    else:
        TIMEOUT_SECONDS = 0.05

    def __init__(self) -> None:
        host = os.getenv("BACKEND_HOST")
        port = int(os.getenv("BACKEND_PORT"))
        path_prefix = os.getenv("PATH_PREFIX", "")
        self.base_url = f"http{'s' if port == 443 else ''}://{host}:{port}{path_prefix}"
        if os.getenv("env", "prod") == "prod":
            try:
                response = requests.get(f"{self.base_url}/health_check")
            except requests.exceptions.ConnectionError:
                raise HealthCheckError()
            if response.status_code != 200 or response.json()["status"] != "ok":
                raise HealthCheckError()
        self.session = None

    def set_session(self, session: IamSession) -> None:
        self.session = session

    def get_session(self) -> IamSession:
        return self.session

    async def is_session_active(self) -> bool:
        try:
            session = await self._get_session_progress()
            if "status" in session and session["status"] == "err":
                if session["message"] == "You do not have an active session yet":
                    return False
                else:
                    logging.error(
                        f"[ Connection.is_session_active ] Error while getting the session progress for the student: {session['message']}"
                    )
                    # The other possible err so far is the user not being authorized, which means
                    # that they probably have not authenticated yet. So, let's just wait for them
                    # to do that.
                    return True
            if "stage" in session and session["stage"].lower() == "finished":
                return False
            return True
        except Exception as e:
            logging.error(
                f"[ Connection.is_session_active ] Error while decoding the response from the server {traceback.format_exc()}"
            )

        # Returning false as a default value.
        # This will prevent data from being sent if the participant did not
        # shut down the laptop or just let it running
        return True

    async def _get_session_progress(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/session_execution/students/{self.session.user.username}/session"
            )
            return response.json()

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
        response = None
        try:
            pa_feedback_str = json.dumps(feedback.personal_analytics_data.model_dump())
            with open(feedback.screenshot, "rb") as screenshot_file:
                logging.info("Sending feedback")
                response = await self._send_feedback(pa_feedback_str, screenshot_file)
        except httpx.TimeoutException:
            raise TimeoutError()
        except json.JSONDecodeError:
            logging.error(
                "[ Connection.send_feedback ] Error while trying to decode (json) the response from the server"
            )
        except Exception as e:
            logging.error(
                "[ Connection.send_feedback ] There was an error while sending the feedback"
            )
            logging.error(traceback.format_exc())

        if response is None:
            logging.error("[ Connection.send_feedback ] response was none")
            return True

        logging.info("[ Connection.send_feedback ] Feedback sent")
        logging.info(f"[ Connection.send_feedback ] Server response: {response}")

        if "detail" in response and response["detail"]["errcode"] == 1:
            return False
        return True

    async def _send_feedback(self, pa_feedback_str: str, screenshot_file) -> dict:
        async with httpx.AsyncClient(timeout=Connection.TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{self.base_url}/session_execution/student/{self.session.user.username}/session/feedback",
                headers={"Authorization": f"Bearer {self.session.token}"},
                params={
                    "pa_feedback_str": pa_feedback_str,
                },
                files={"screenshot_file": screenshot_file},
            )
        return response.json()

    async def get_current_feedback(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/session_execution/student/{self.session.user.username}/session/feedback",
                headers={"Authorization": f"Bearer {self.session.token}"},
            )
            try:
                return response.json()
            except:
                logging.info("[ get_current_feedback ] returning none")
                return None

    # async def check_user_has_active_session(self) -> bool:
    #     async with httpx.AsyncClient() as client:
    #         response = await client.get(
    #             f"{self.base_url}/session_execution/student",
    #             params={"student_name": self.session.user.username},
    #         )
    #         if response.status_code != 200:
    #             logging.info(
    #                 f"Received status code {response.status_code} in Connection.check_user_has_active_session()"
    #             )
    #             return False
    #         else:
    #             student = response.json()
    #             if len(student["sessions"]) == 0:
    #                 return False
    #             if student["sessions"][-1]["stage"] != "FINISHED":
    #                 return True
    #             return False

    async def check_user_has_finished_homework(self) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/session_execution/student",
                params={"student_name": self.session.user.username},
            )
            if response.status_code != 200:
                logging.info(
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

    # async def upload_tracking_user_input_batch(
    #     self, student_name: str, batch: list[dict]
    # ) -> None:
    #     async with httpx.AsyncClient() as client:
    #         try:
    #             logging.info("Uploading user input tracking data", batch[0])
    #             response = await client.post(
    #                 f"{self.base_url}/tracking/user_input",
    #                 json=batch,
    #                 params={"student_name": student_name},
    #             )
    #             if response.status_code != 200:
    #                 logging.info(
    #                     f"Received status code {response.status_code} in Connection.upload_tracking_user_input_batch()"
    #                 )

    #             logging.info(f"Success when uploading tracking data: {response.json()}")
    #         except Exception as e:
    #             logging.info(e)
    #             logging.info("Error while uploading windows activity batch")

    # async def upload_tracking_windows_activity_batch(
    #     self, student_name: str, batch: list[dict]
    # ) -> None:
    #     async with httpx.AsyncClient() as client:
    #         try:
    #             logging.info(f"Uploading window activity tracking data: {batch[0]}")
    #             response = await client.post(
    #                 f"{self.base_url}/tracking/windows_activity",
    #                 json=batch,
    #                 params={"student_name": student_name},
    #             )
    #             if response.status_code != 200:
    #                 logging.info(
    #                     f"Received status code {response.status_code} in Connection.upload_traupload_tracking_windows_activity_batchcking_user_input_batch()"
    #                 )
    #             logging.info(
    #                 f"Success when uploading windows activity batch: {response.json()}"
    #             )
    #         except Exception as e:
    #             logging.info(e)
    #             logging.info("Error while uploading tracking data")
