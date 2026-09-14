import pytest

from photoalbum.geocoding.rate_limiter import RateLimiter


class FakeTime:
    def __init__(self) -> None:
        self.current = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += seconds


def test_first_request_does_not_wait():
    fake_time = FakeTime()

    limiter = RateLimiter(
        1.0,
        clock=fake_time.clock,
        sleeper=fake_time.sleep,
    )

    limiter.wait()

    assert fake_time.sleeps == []


def test_second_immediate_request_waits():
    fake_time = FakeTime()

    limiter = RateLimiter(
        1.0,
        clock=fake_time.clock,
        sleeper=fake_time.sleep,
    )

    limiter.wait()
    limiter.wait()

    assert fake_time.sleeps == [1.0]


def test_request_after_interval_does_not_wait():
    fake_time = FakeTime()

    limiter = RateLimiter(
        1.0,
        clock=fake_time.clock,
        sleeper=fake_time.sleep,
    )

    limiter.wait()

    fake_time.current += 1.5

    limiter.wait()

    assert fake_time.sleeps == []


def test_only_remaining_interval_is_waited():
    fake_time = FakeTime()

    limiter = RateLimiter(
        1.0,
        clock=fake_time.clock,
        sleeper=fake_time.sleep,
    )

    limiter.wait()

    fake_time.current += 0.4

    limiter.wait()

    assert fake_time.sleeps == pytest.approx([0.6])


def test_negative_interval_is_rejected():
    with pytest.raises(ValueError):
        RateLimiter(-1.0)

