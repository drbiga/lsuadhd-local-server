from __future__ import annotations

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

    seqnum: int

    personal_analytics_data: PaFeedback

    screenshot: str

class PaFeedback(BaseModel):
    isFocused: int
    numMouseClicks: int
    mouseScrollDistance: float
    mouseMoveDistance: float
    keyboardStrokes: int
