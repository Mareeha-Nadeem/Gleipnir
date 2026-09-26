import random
import time


def test_random_failure_a():
    assert random.random() > 0.2


def test_random_failure_b():
    assert random.choice([True, True, True, False])


def test_timing_sensitive_failure():
    assert (time.time_ns() // 1_000_000) % 7 != 0
