# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The hospitality cost sheet of an invitation.

The mail merge table of the legacy event manager carries, for every invited
physician, what the sponsor pays: room, city tax, catering, meals and travel.
Those columns were only printed on the letter; here they also add up, which is
what turns the mail merge into a sponsor budget.

**Assumption, stated because the legacy table does not say it**: `costoCamera`,
`costoCityTax`, `costoRistorativo` and `viaggio` are per-physician amounts, and
the meal counts are informative unless per-meal rates are supplied. Passing a
`MealRates` makes the calculation explicit instead: meals are then priced from
their counts and `costoRistorativo` is ignored. Whoever configures the platform
chooses which of the two is true for their contracts.

Pure, no Indico imports.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


CENTS = Decimal('0.01')


def money(value):
    """Normalize a value to two decimals, never through a float."""
    if value in (None, ''):
        return Decimal('0.00')
    if isinstance(value, Decimal):
        amount = value
    else:
        amount = Decimal(str(value).replace('€', '').replace(' ', '').replace(',', '.') or 0)
    return amount.quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MealRates:
    """Per-meal rates, when the provider prices meals rather than lump sums."""

    lunch: Decimal = Decimal(0)
    coffee_break: Decimal = Decimal(0)
    dinner: Decimal = Decimal(0)


@dataclass(frozen=True)
class CostSheet:
    physicians: int = 1
    room: Decimal = Decimal('0.00')
    city_tax: Decimal = Decimal('0.00')
    catering: Decimal = Decimal('0.00')
    travel: Decimal = Decimal('0.00')
    lunches: int = 0
    coffee_breaks: int = 0
    dinners: int = 0

    @property
    def per_physician(self):
        return money(self.room + self.city_tax + self.catering + self.travel)

    @property
    def total(self):
        return money(self.per_physician * self.physicians)

    def with_rates(self, rates: MealRates):
        """Recompute catering from the meal counts and the given rates."""
        catering = (rates.lunch * self.lunches + rates.coffee_break * self.coffee_breaks
                    + rates.dinner * self.dinners)
        return CostSheet(physicians=self.physicians, room=self.room, city_tax=self.city_tax,
                         catering=money(catering), travel=self.travel, lunches=self.lunches,
                         coffee_breaks=self.coffee_breaks, dinners=self.dinners)

    def as_dict(self):
        return {
            'physicians': self.physicians,
            'room': str(self.room),
            'city_tax': str(self.city_tax),
            'catering': str(self.catering),
            'travel': str(self.travel),
            'lunches': self.lunches,
            'coffee_breaks': self.coffee_breaks,
            'dinners': self.dinners,
            'per_physician': str(self.per_physician),
            'total': str(self.total),
        }


def cost_sheet_from_legacy(row, *, physicians=None):
    """Build a cost sheet from a legacy mail merge row."""
    def count(key):
        value = row.get(key)
        try:
            return int(float(str(value).replace(',', '.'))) if value not in (None, '') else 0
        except ValueError:
            return 0

    return CostSheet(
        physicians=physicians or max(count('numeroMedici'), 1),
        room=money(row.get('costoCamera')),
        city_tax=money(row.get('costoCityTax')),
        catering=money(row.get('costoRistorativo')),
        travel=money(row.get('viaggio')),
        lunches=count('numeroPranzi'),
        coffee_breaks=count('numeroCoffeeBreak'),
        dinners=count('numeroCene'),
    )


def event_totals(sheets):
    """Roll up every invitation of an event."""
    sheets = list(sheets)
    return {
        'invitations': len(sheets),
        'physicians': sum(sheet.physicians for sheet in sheets),
        'room': money(sum((sheet.room * sheet.physicians for sheet in sheets), Decimal(0))),
        'city_tax': money(sum((sheet.city_tax * sheet.physicians for sheet in sheets), Decimal(0))),
        'catering': money(sum((sheet.catering * sheet.physicians for sheet in sheets), Decimal(0))),
        'travel': money(sum((sheet.travel * sheet.physicians for sheet in sheets), Decimal(0))),
        'total': money(sum((sheet.total for sheet in sheets), Decimal(0))),
    }


def exceeds_budget(sheets, budget):
    """Whether the invitations cost more than the sponsor agreed to.

    Returns `(exceeded, total, overrun)` so a caller can raise a task with the
    actual numbers instead of a warning.
    """
    total = event_totals(sheets)['total']
    limit = money(budget)
    return total > limit, total, money(max(total - limit, Decimal(0)))
