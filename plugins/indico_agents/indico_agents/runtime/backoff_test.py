# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from datetime import datetime, timedelta

import pytest

from indico_agents.runtime.backoff import (compute_delay, lease_expiry, next_run_after, should_give_up)


NOW = datetime(2026, 9, 15, 10, 0)


@pytest.mark.parametrize(('attempts', 'expected'), (
    (0, 60),
    (1, 60),
    (2, 120),
    (3, 240),
    (4, 480),
))
def test_delay_grows_exponentially(attempts, expected):
    assert compute_delay(attempts, jitter_ratio=0) == expected


def test_delay_is_capped():
    assert compute_delay(20, jitter_ratio=0) == 3600
    assert compute_delay(20, max_seconds=300, jitter_ratio=0) == 300


def test_delay_never_decreases():
    delays = [compute_delay(n, jitter_ratio=0) for n in range(10)]
    assert delays == sorted(delays)


def test_jitter_stays_within_bounds():
    lowest = compute_delay(3, rand=lambda: 0.0)
    highest = compute_delay(3, rand=lambda: 1.0)
    middle = compute_delay(3, rand=lambda: 0.5)
    assert lowest == pytest.approx(216)
    assert highest == pytest.approx(264)
    assert middle == pytest.approx(240)


def test_jitter_is_skipped_without_a_random_source():
    assert compute_delay(3) == 240


def test_negative_attempts_are_rejected():
    with pytest.raises(ValueError, match='cannot be negative'):
        compute_delay(-1)


def test_next_run_after():
    assert next_run_after(NOW, 2, jitter_ratio=0) == NOW + timedelta(seconds=120)


def test_lease_expiry_default():
    assert lease_expiry(NOW) == NOW + timedelta(minutes=15)


def test_lease_expiry_custom():
    assert lease_expiry(NOW, seconds=60) == NOW + timedelta(minutes=1)


@pytest.mark.parametrize(('attempts', 'max_attempts', 'expected'), (
    (0, 5, False),
    (4, 5, False),
    (5, 5, True),
    (6, 5, True),
))
def test_should_give_up(attempts, max_attempts, expected):
    assert should_give_up(attempts, max_attempts) is expected
