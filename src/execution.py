# from pydantic import BaseModel
# from typing import Optional, List

# from enum import auto, StrEnum, IntEnum

# class SessionTime(IntEnum):
#     READCOMP_TIME_SECONDS = 3 * 60
#     HOMEWORK_TIME_SECONDS = 3 * 60
#     SURVEY_TIME_SECONDS = 3 * 60


# class SessionStage(StrEnum):
#     WAITING = auto()
#     READCOMP = auto()
#     HOMEWORK = auto()
#     SURVEY = auto()
#     FINISHED = auto()


# class Session(BaseModel):
#     # Main data
#     seqnum: int
#     start_link: str
#     is_passthrough: bool
#     has_feedback: bool
#     no_equipment: Optional[bool] = False
#     stage: SessionStage
#     feedbacks: List[Feedback]
