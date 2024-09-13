from pydantic import BaseModel
from typing import Optional
from enum import StrEnum, auto

import requests

class Role(StrEnum):
    MANAGER = auto()
    STUDENT = auto()


class User(BaseModel):
    username: str
    password: Optional[bytes] = None
    role: str


class Session(BaseModel):
    token: str
    user: User
    ip_address: str
