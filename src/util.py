from pydantic import PlainSerializer
from typing import Annotated
from datetime import datetime

SerializableDateTime = Annotated[
    datetime,
    PlainSerializer(lambda date: date.isoformat(), return_type=str),
]
