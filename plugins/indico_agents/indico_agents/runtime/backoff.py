# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Retry timing for the work queue.

Pure functions with an injectable random source, so retry behaviour is testable
and reproducible instead of being an emergent property of production.
"""

from datetime import timedelta


DEFAULT_BASE_SECONDS = 60
DEFAULT_FACTOR = 2
DEFAULT_MAX_SECONDS = 3600
DEFAULT_JITTER_RATIO = 0.1
#: How long a worker may hold a task before other workers may take it over
DEFAULT_LEASE_SECONDS = 900


def compute_delay(attempts, *, base=DEFAULT_BASE_SECONDS, factor=DEFAULT_FACTOR, max_seconds=DEFAULT_MAX_SECONDS,
                  jitter_ratio=DEFAULT_JITTER_RATIO, rand=None):
    """Seconds to wait before the next attempt.

    Exponential with a cap, plus optional jitter so that a burst of tasks
    failing at the same time (an external API going down, typically) does not
    come back in lockstep.
    """
    if attempts < 0:
        raise ValueError('attempts cannot be negative')
    delay = min(base * (factor ** max(attempts - 1, 0)), max_seconds)
    if attempts == 0:
        delay = base
    if jitter_ratio and rand is not None:
        spread = delay * jitter_ratio
        delay = delay - spread + (2 * spread * rand())
    return max(0.0, float(delay))


def next_run_after(now, attempts, **kwargs):
    """The timestamp at which a failed task becomes claimable again."""
    return now + timedelta(seconds=compute_delay(attempts, **kwargs))


def lease_expiry(now, *, seconds=DEFAULT_LEASE_SECONDS):
    """When a lease taken now expires.

    A worker that dies does not block a task forever: once the lease expires the
    row is claimable again, which is the whole point of leasing rather than
    locking.
    """
    return now + timedelta(seconds=seconds)


def should_give_up(attempts, max_attempts):
    return attempts >= max_attempts
