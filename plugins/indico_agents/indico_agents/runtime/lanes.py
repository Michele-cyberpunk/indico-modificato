# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Two queues in one table.

Work an agent does divides cleanly in two, and mixing them makes both worse.

*Visible* work is what somebody is waiting on: a registration arrived and its
data has to be checked, a checklist item fell due, credits need re-evaluating
before the office looks at the page. It finishes in seconds and there is a lot
of it, so it is claimed in large batches on a short lease.

*Research* work reaches outside the building. It takes minutes, it fails in ways
that need long backoff, and — crucially — one slow lookup must not make forty
quick tasks wait behind it. It is claimed a few at a time on a long lease.

One table, one claiming mechanism, two sets of numbers. This is `lib/dispatch.ts`
of trycompai/crm, whose lanes exist for the same reason.

Pure: no Indico imports, no database.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Lane:
    """How one lane is drained."""

    name: str
    #: Tasks a single dispatcher tick may claim
    batch: int
    #: How long a worker holds a task before it is reclaimable
    lease_seconds: int
    description: str


VISIBLE = Lane(
    name='visible',
    batch=60,
    lease_seconds=120,
    description='lavoro che qualcuno sta aspettando: finisce in secondi',
)

RESEARCH = Lane(
    name='research',
    batch=12,
    lease_seconds=1800,
    description='lavoro che esce dalla piattaforma: minuti, non secondi',
)

LANES = (VISIBLE, RESEARCH)
LANES_BY_NAME = {lane.name: lane for lane in LANES}

#: Task kinds that reach outside. Everything not named here is visible work,
#: which is the safe default: a task in the fast lane that turns out to be slow
#: loses its lease and is retried, while a quick task stuck in the slow lane is
#: simply late, and nobody notices until they do.
RESEARCH_KINDS = frozenset({
    'company_research',
    'contact_enrichment',
    'registry_verification',
})


def lane_for(kind):
    """Which lane a task kind belongs to."""
    return RESEARCH.name if kind in RESEARCH_KINDS else VISIBLE.name


def get_lane(name):
    """The lane's settings, falling back to the fast one for an unknown name.

    An unknown lane name means a task row written by an older version or by
    hand. Draining it as visible work is wrong only in the timing.
    """
    return LANES_BY_NAME.get(name, VISIBLE)
