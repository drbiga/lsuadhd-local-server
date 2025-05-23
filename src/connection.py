import os
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
        self.base_url = f"http{'s' if port == 443 else ''}://{host}:{port}"
        response = requests.get(f"{self.base_url}/health_check")
        if response.status_code != 200 or response.json()["status"] != "ok":
            raise HealthCheckError()
        self.session = None

    def set_session(self, session: Session) -> None:
        self.session = session

    def connect(self) -> None:
        response = requests.get(f"{self.base_url}/iam/session/{self.session.token}")
        if (
            response.status_code == 200
            and response.json()["token"] == self.session.token
        ):
            print("Connected")
        else:
            raise ConnectionError("It was not possible to connect to the backend")

    def send_feedback(self, feedback: Feedback) -> bool:
        """Returns a flag if session is still active and false otherwise.
        This is used to control the state and know when to stop sending
        feedbacks to the backend"""
        pa_feedback_str = json.dumps(feedback.personal_analytics_data.model_dump())

        with open(feedback.screenshot, "rb") as screenshot_file:
            print("Sending feedback")
            response = requests.post(
                f"{self.base_url}/session_execution/student/{self.session.user.username}/session/feedback",
                headers={"Authorization": f"Bearer {self.session.token}"},
                params={
                    "pa_feedback_str": pa_feedback_str,
                },
                files={"screenshot_file": screenshot_file},
            )
        print("Feedback sent")
        try:
            print(
                f"Got {response.status_code} while sending feedback:", response.json()
            )
        except:
            try:
                print(
                    f"Got {response.status_code} while sending feedback:",
                    response.content,
                )
            except:
                pass

        if response.status_code == 400:
            if response.json()["detail"]["errcode"] == 1:
                return False
        return True

    def get_current_feedback(self) -> dict:
        response = requests.get(
            f"{self.base_url}/session_execution/student/{self.session.user.username}/session/feedback",
            headers={"Authorization": f"Bearer {self.session.token}"},
        )
        try:
            return response.json()
        except:
            return None

    def check_user_has_active_session(self) -> bool:
        response = requests.get(
            f"{self.base_url}/session_execution/student",
            params={"student_name": self.session.user.username},
        )
        if response.status_code != 200:
            print(response.status_code)
            return False
        else:
            student = response.json()
            return student["active_session"] is not None

    def check_user_has_finished_homework(self) -> bool:
        response = requests.get(
            f"{self.base_url}/session_execution/student",
            params={"student_name": self.session.user.username},
        )
        if response.status_code != 200:
            print(response.status_code)
            return False
        else:
            student = response.json()
            if "active_session" in student:
                # print(student["active_session"])
                return (
                    student["active_session"]["stage"] == "homework"
                    and student["active_session"]["remaining_time_seconds"] < 5
                ) or student["active_session"]["stage"] == "survey"
            else:
                return False

    def upload_tracking_user_input_batch(
        self, student_name: str, batch: list[dict]
    ) -> None:
        try:
            print("Uploading user input tracking data", batch[0])
            response = requests.post(
                f"{self.base_url}/tracking/user_input",
                json=batch,
                params={"student_name": student_name},
            )
            if response.status_code != 200:
                print("Upload tracking user input did not return 200")
                print(response.status_code)

            print("Success:", response.json())
        except Exception as e:
            print(e)
            print("Error while uploading tracking data")

    def upload_tracking_windows_activity_batch(
        self, student_name: str, batch: list[dict]
    ) -> None:
        try:
            print("Uploading window activity tracking data", batch[0])
            response = requests.post(
                f"{self.base_url}/tracking/windows_activity",
                json=batch,
                params={"student_name": student_name},
            )
            if response.status_code != 200:
                print("Upload tracking windows activity did not return 200")
                print(response.status_code)
            print("Success:", response.json())
        except Exception as e:
            print(e)
            print("Error while uploading tracking data")
