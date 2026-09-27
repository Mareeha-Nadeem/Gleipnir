"""Extended test suite with stable, flaky, and broken tests for Gleipnir demo."""

import os
import random
import threading
import time


# ---------------------------------------------------------------------------
# STABLE tests — always pass
# ---------------------------------------------------------------------------

def test_stable_addition():
    assert 1 + 1 == 2


def test_stable_string_ops():
    assert "hello".upper() == "HELLO"


def test_stable_list_sort():
    data = [3, 1, 4, 1, 5, 9, 2, 6]
    assert sorted(data) == [1, 1, 2, 3, 4, 5, 6, 9]


def test_stable_dict_access():
    config = {"host": "localhost", "port": 8080}
    assert config["port"] == 8080


def test_stable_type_check():
    assert isinstance(42, int)
    assert isinstance("text", str)
    assert isinstance([], list)


def test_stable_exception_raised():
    try:
        int("not-a-number")
        assert False, "should have raised"
    except ValueError:
        pass


def test_stable_set_operations():
    a = {1, 2, 3, 4}
    b = {3, 4, 5, 6}
    assert a & b == {3, 4}
    assert a | b == {1, 2, 3, 4, 5, 6}


def test_stable_generator():
    total = sum(x * x for x in range(10))
    assert total == 285


# ---------------------------------------------------------------------------
# FLAKY tests — pass most of the time but occasionally fail
# ---------------------------------------------------------------------------

def test_flaky_random_threshold():
    """Fails ~15% of the time (random.random() < 0.15)."""
    assert random.random() >= 0.15


def test_flaky_random_coin():
    """Fails ~25% of the time."""
    assert random.choice([True, True, True, False])


def test_flaky_sleep_timing():
    """Sleeps briefly then checks elapsed time — occasionally off on loaded CI."""
    start = time.monotonic()
    time.sleep(0.05)
    elapsed = time.monotonic() - start
    # Generous upper bound, but a very loaded machine may still exceed 0.5 s
    assert elapsed < 0.5


def test_flaky_random_int_range():
    """Fails ~1-in-10 runs: rolls a d10 and asserts it isn't 7."""
    roll = random.randint(1, 10)
    assert roll != 7


def test_flaky_list_shuffle_order():
    """Shuffles a list; fails when first element happens to stay at 0."""
    items = list(range(10))
    random.shuffle(items)
    assert items[0] != 0  # passes ~90% of the time


def test_flaky_env_var_present():
    """Flaky if CI sometimes sets DEBUG=1 and sometimes doesn't."""
    val = os.environ.get("DEBUG", "0")
    # Passes when DEBUG is absent or 0; fails when an environment sets DEBUG=1
    assert val in ("0", ""), f"Unexpected DEBUG={val!r}"


def test_flaky_thread_race():
    """Tiny race condition: shared counter incremented by two threads without a lock."""
    counter = [0]

    def increment():
        for _ in range(500):
            tmp = counter[0]
            # intentional yield point between read and write
            counter[0] = tmp + 1

    t1 = threading.Thread(target=increment)
    t2 = threading.Thread(target=increment)
    t1.start(); t2.start()
    t1.join(); t2.join()
    # Occasionally the race makes the result slightly below 1000
    assert counter[0] == 1000


# ---------------------------------------------------------------------------
# BROKEN tests — always fail
# ---------------------------------------------------------------------------

def test_broken_wrong_math():
    """Hardcoded incorrect assertion."""
    assert 2 + 2 == 5, "math is wrong"


def test_broken_index_out_of_range():
    """Raises IndexError every time."""
    items = [1, 2, 3]
    _ = items[99]


def test_broken_attribute_error():
    """Calls a method that doesn't exist."""
    result = "hello".nonexistent_method()  # type: ignore[attr-defined]
    assert result is not None


def test_broken_assertion_false():
    assert False, "this test is intentionally always broken"
