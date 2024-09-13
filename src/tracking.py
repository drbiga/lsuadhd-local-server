from pydantic import BaseModel
from util import SerializableDateTime


class UserInput(BaseModel):
    username: str
    filename: str
    id: int
    ts_time: SerializableDateTime
    ts_start: SerializableDateTime
    ts_end: SerializableDateTime
    keys_total: int
    clicks_total: int
    scroll_delta: float
    moved_distance: float


class WindowsActivity(BaseModel):
    username: str
    filename: str
    id: int
    ts_time: SerializableDateTime
    ts_start: SerializableDateTime
    ts_end: SerializableDateTime
    window_name: str
    process_name: str
