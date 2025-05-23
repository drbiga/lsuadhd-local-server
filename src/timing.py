import asyncio

import datetime
from enum import IntEnum

import statistics


class State(IntEnum):
    TRACKING_ITERATION = 1
    NOT_TRACKING_ITERATION = 2


class TimingService:
    DEFAULT_TIME_TO_WAIT = 30
    MOVING_AVERAGE_SIZE = 10

    def __init__(self) -> None:
        self.previous_iterations = []
        self.current_start_time = None
        self.current_finish_time = None
        self.current_elapsed_time = None
        self.state = State.NOT_TRACKING_ITERATION
        self.time_to_wait = TimingService.DEFAULT_TIME_TO_WAIT

    def set_time(self, time_to_wait: int) -> None:
        self.time_to_wait = time_to_wait

    def start_iteration(self) -> None:
        if self.state == State.TRACKING_ITERATION:
            raise RuntimeError("There is already an iteration being tracked")

        self.current_start_time = datetime.datetime.now()
        self.state = State.TRACKING_ITERATION

    def finish_iteration(self) -> None:
        if self.state == State.NOT_TRACKING_ITERATION:
            raise RuntimeError("There is not any iteration being tracked")

        self.current_finish_time = datetime.datetime.now()
        self.current_elapsed_time = (
            self.current_finish_time - self.current_start_time
        ).seconds

        if len(self.previous_iterations) < TimingService.MOVING_AVERAGE_SIZE:
            self.previous_iterations.append(self.current_elapsed_time)
        else:
            self.previous_iterations.pop(0)
            self.previous_iterations.append(self.current_elapsed_time)

        self.current_elapsed_time = None
        self.current_start_time = None
        self.current_finish_time = None
        self.state = State.NOT_TRACKING_ITERATION

    async def wait(self) -> None:
        if len(self.previous_iterations) < TimingService.MOVING_AVERAGE_SIZE:
            # Program just started and we have not collected enough samples
            time_to_wait = self.time_to_wait
        else:
            time_to_wait = self.time_to_wait - statistics.mean(self.previous_iterations)

        print(f"\nWaiting for {time_to_wait}\n")
        if time_to_wait > 0:
            await asyncio.sleep(time_to_wait)
