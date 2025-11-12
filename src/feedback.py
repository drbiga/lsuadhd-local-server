from __future__ import annotations
import os

from pydantic import BaseModel
from typing import Optional
from enum import StrEnum, auto

import random

from personal_analytics import get_feedback_personal_analytics
from screenshot import take_screenshot


class Feedback(BaseModel):
    """Feedback model will have two events in its lifecycle. First, it will be
    created with the available feedback data collected from students. Second, the
    output will be computed based on the inputs. We assume the data is going to be
    sent the backend in regular intervals such that at every new output computation
    event, this computation is being performed always over new data, meaning a new
    feedback is going to be computed."""

    personal_analytics_data: PaFeedback

    screenshot: str


class PaFeedback(BaseModel):
    isFocused: int
    numMouseClicks: int
    mouseScrollDistance: float
    mouseMoveDistance: float
    keyboardStrokes: int


async def collect_feedback() -> Feedback:
    pa_feedback = await get_feedback_personal_analytics()
    screenshot = take_screenshot()
    feedback = Feedback(
        personal_analytics_data=PaFeedback(
            numMouseClicks=pa_feedback.clickTotal,
            keyboardStrokes=pa_feedback.keyTotal,
            mouseMoveDistance=pa_feedback.movedDistance,
            mouseScrollDistance=pa_feedback.scrollDelta,
            isFocused=pa_feedback.isFocused,
        ),
        screenshot=screenshot,
    )
    return feedback


def clean(feedback: Feedback) -> None:
    os.remove(feedback.screenshot)
