import requests
from pydantic import BaseModel
import os

# import shutil
from typing import List, Tuple

import sqlite3 as sql
from datetime import datetime


class PersonalAnalyticsData(BaseModel):
    isFocused: int
    clickTotal: int
    keyTotal: int
    movedDistance: float
    scrollDelta: float


def get_feedback_personal_analytics() -> PersonalAnalyticsData:
    pa_data = requests.get("http://localhost:57827/intervention_status").json()
    return PersonalAnalyticsData(**pa_data)


class UserInput(BaseModel):
    filename: str
    id: int
    time: datetime
    tsStart: datetime
    tsEnd: datetime
    keyTotal: int
    clickTotal: int
    scrollDelta: int
    movedDistance: int


class WindowsActivity(BaseModel):
    filename: str
    id: int
    time: datetime
    tsStart: datetime
    tsEnd: datetime
    window: str
    process: str


def get_base_dir() -> str:
    base_dirs_list = [
        "C:/Users/bigar/OneDrive/Documents1/PersonalAnalytics",
        "C:/Users/bigar/Documents1/PersonalAnalytics",
        f"{os.getenv('UserProfile')}\\OneDrive\\Documents\\PersonalAnalytics",
        f"{os.getenv('UserProfile')}\\Documents\\PersonalAnalytics",
    ]
    for base_dir in base_dirs_list:
        if os.path.exists(base_dir):
            return base_dir

    raise Exception("Directory for personal analytics database does not exist")


def get_tracking_data() -> Tuple[List[UserInput], List[WindowsActivity]]:
    # username = os.getenv("USERNAME")
    # if username == "bigar":
    #     base_dir = f"C:/Users/{username}/OneDrive/Documents/PersonalAnalytics"
    # else:
    #     base_dir = f"C:/Users/{username}/Documents/PersonalAnalytics"
    base_dir = get_base_dir()
    paths = [
        f"{base_dir}/{filename}"
        for filename in os.listdir(base_dir)
        if filename.endswith(".pa.dat")
    ]
    user_input_batch = []
    windows_activity_batch = []
    for path in paths:
        with sql.connect(path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, time, tsStart, tsEnd, keyTotal, clickTotal, scrollDelta, movedDistance FROM user_input"
            )
            user_input_data = cur.fetchall()
            user_input_batch.extend(
                [
                    UserInput(
                        filename=path.split("/")[-1],
                        id=d[0],
                        time=d[1],
                        tsStart=d[2],
                        tsEnd=d[3],
                        keyTotal=d[4],
                        clickTotal=d[5],
                        scrollDelta=d[6],
                        movedDistance=d[7],
                    )
                    for d in user_input_data
                ]
            )

            cur.execute(
                "SELECT id, time, tsStart, tsEnd, window, process FROM windows_activity"
            )
            windows_activity_data = cur.fetchall()
            windows_activity_batch.extend(
                [
                    WindowsActivity(
                        filename=path.split("/")[-1],
                        id=d[0],
                        time=d[1],
                        tsStart=d[2],
                        tsEnd=d[3],
                        window=d[4],
                        process=d[5],
                    )
                    for d in windows_activity_data
                ]
            )

    return user_input_batch, windows_activity_batch
