# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""What an agent is allowed to spend looking something up.

An agent that can call an outside source will keep calling it. Not because it is
badly written — because one more lookup always *might* settle the question, and
nothing in the loop knows the difference between diligence and a bill.

So the budget is not advice, it is a refusal. Each subject gets a small number
of outside lookups; when they are gone the tool stops answering and tells the
agent what to do instead: write up what it already has, or schedule a recheck
with a reason. Both are useful outcomes. Looping is not.

This mirrors `lib/focus.ts` of trycompai/crm, reimplemented as an explicit
object on the run context rather than ambient state: an agent that cannot see
its own budget cannot reason about it, and a budget nobody can inspect cannot be
tested.

Pure: no Indico imports, no database, no clock.
"""

from dataclasses import dataclass, field
from typing import ClassVar


#: Enough to check a claim from two directions and no more. Deliberately small:
#: the fourth lookup on one person has almost never changed the answer.
DEFAULT_LIMIT = 4


@dataclass(frozen=True)
class Refusal:
    """Why a lookup did not happen, in words meant for the agent."""

    reason: str
    spent: int
    limit: int

    ok: ClassVar[bool] = False

    def as_result(self):
        """The shape a tool returns instead of calling out."""
        return {'ok': False, 'budget_exhausted': True, 'spent': self.spent,
                'limit': self.limit, 'reason': self.reason}


@dataclass(frozen=True)
class Allowance:
    """A lookup that may proceed."""

    spent: int
    limit: int

    ok: ClassVar[bool] = True


@dataclass
class Budget:
    """The outside lookups left for one subject.

    `subject` is what the budget is *about* — a contact, a company — because the
    limit is per subject, not per run: a run that legitimately touches thirty
    contacts should not run out on the eighth.
    """

    limit: int = DEFAULT_LIMIT
    #: subject key -> lookups already spent on it
    spent: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.limit < 0:
            raise ValueError('il budget non può essere negativo')

    def spent_on(self, subject):
        return self.spent.get(str(subject), 0)

    def remaining(self, subject):
        return max(0, self.limit - self.spent_on(subject))

    def spend(self, subject, units=1):
        """Take `units` from this subject's allowance, or refuse.

        Refusing does not raise: an exhausted budget is a normal outcome that the
        agent has to act on, not an error that unwinds the run.
        """
        if units < 1:
            raise ValueError('una spesa deve essere di almeno una unità')
        key = str(subject)
        already = self.spent.get(key, 0)
        if already + units > self.limit:
            return Refusal(
                reason=(f'Budget di ricerca esaurito per questo soggetto ({already}/{self.limit}). '
                        'Scrivi ciò che hai già trovato, oppure programma una nuova verifica '
                        'indicandone il motivo. Non continuare a cercare.'),
                spent=already, limit=self.limit)
        self.spent[key] = already + units
        return Allowance(spent=self.spent[key], limit=self.limit)

    def refund(self, subject, units=1):
        """Give back an allowance a lookup did not use.

        A source that answered "not configured" cost nothing and must not count:
        otherwise an install with no external providers would exhaust its budget
        without ever leaving the building.
        """
        key = str(subject)
        self.spent[key] = max(0, self.spent.get(key, 0) - units)

    def report(self):
        """What was spent, for the run summary and the dashboard."""
        return {'limit': self.limit,
                'subjects': dict(sorted(self.spent.items())),
                'total': sum(self.spent.values())}
