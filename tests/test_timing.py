import pytest

from timing import TimingService


class TestTimingService:
    def test_is_not_started_when_created(self):
        svc = TimingService()
        assert svc.is_tracking_iteration == False

    def test_set_time_to_wait_cannot_be_negative(self):
        svc = TimingService()
        with pytest.raises(ValueError):
            svc.set_time(-1)

    @pytest.mark.parametrize("time", [0, 1, 2])
    def test_set_time_to_wait_accepts_non_negative_numbers(self, time: int):
        svc = TimingService()
        svc.set_time(time)
        assert True

    def test_cannot_be_started_twice(self):
        svc = TimingService()
        svc.start_iteration()
        with pytest.raises(RuntimeError):
            svc.start_iteration()

    def test_start_changes_state(self):
        svc = TimingService()
        svc.start_iteration()
        svc.is_tracking_iteration == True

    def test_start_registers_timestamp(self):
        svc = TimingService()
        svc.start_iteration()
        assert svc.current_start_time is not None

    def test_finish_raises_if_not_started(self):
        svc = TimingService()
        with pytest.raises(RuntimeError):
            svc.finish_iteration()

    def test_finish_changes_state(self):
        svc = TimingService()
        svc.start_iteration()
        svc.finish_iteration()
        assert svc.is_tracking_iteration == False

    def test_finish_resets_timestamps(self):
        svc = TimingService()
        svc.start_iteration()
        svc.finish_iteration()
        assert svc.current_start_time is None
        assert svc.current_finish_time is None

    def test_starts_with_no_iterations(self):
        svc = TimingService()
        assert len(svc.previous_iterations) == 0

    def test_finish_registers_first_iteration(self):
        svc = TimingService()
        svc.start_iteration()
        svc.finish_iteration()
        assert len(svc.previous_iterations) == 1

    @pytest.mark.parametrize(
        "size_before, expected_size_after",
        [
            [TimingService.MOVING_AVERAGE_SIZE - 1, TimingService.MOVING_AVERAGE_SIZE],
            [TimingService.MOVING_AVERAGE_SIZE, TimingService.MOVING_AVERAGE_SIZE],
        ],
    )
    def test_finish_near_moving_average_size(
        self, size_before: int, expected_size_after: int
    ):
        svc = TimingService()
        svc.previous_iterations = [1.0 for _ in range(size_before)]
        svc.start_iteration()
        svc.finish_iteration()
        assert len(svc.previous_iterations) == expected_size_after

    def test_compute_time_not_enough_samples(self):
        svc = TimingService()
        svc.set_time(2)
        svc.previous_iterations = [
            1 for _ in range(TimingService.MOVING_AVERAGE_SIZE - 1)
        ]
        assert svc.compute_time_to_wait() == 2

    def test_compute_time_exactly_enough_samples(self):
        svc = TimingService()
        svc.set_time(2)
        svc.previous_iterations = [1 for _ in range(TimingService.MOVING_AVERAGE_SIZE)]
        assert svc.compute_time_to_wait() == 1

    def test_compute_time_average(self):
        svc = TimingService()
        svc.set_time(2)
        svc.previous_iterations = [
            1 for _ in range(TimingService.MOVING_AVERAGE_SIZE // 2)
        ]
        svc.previous_iterations.extend(
            [3 for _ in range(TimingService.MOVING_AVERAGE_SIZE // 2)]
        )
        if TimingService.MOVING_AVERAGE_SIZE % 2 == 1:
            svc.previous_iterations.append(3)
        # The time to wait is the iteration time set to 2 minus the average
        # actual elapsed time, which is 2 in this case
        assert svc.compute_time_to_wait() == 0
