# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from decimal import Decimal

import pytest

from indico_ecm.services.costs import (CostSheet, MealRates, cost_sheet_from_legacy, event_totals, exceeds_budget,
                                       money)


@pytest.mark.parametrize(('value', 'expected'), (
    ('120', Decimal('120.00')),
    ('120,50', Decimal('120.50')),
    ('€ 1200', Decimal('1200.00')),
    (None, Decimal('0.00')),
    ('', Decimal('0.00')),
    (Decimal('3.005'), Decimal('3.01')),
))
def test_money_normalizes(value, expected):
    assert money(value) == expected


def test_per_physician_and_total():
    sheet = CostSheet(physicians=3, room=money(120), city_tax=money(5), catering=money(60), travel=money(80))
    assert sheet.per_physician == Decimal('265.00')
    assert sheet.total == Decimal('795.00')


def test_meal_rates_replace_the_lump_sum():
    sheet = CostSheet(physicians=2, room=money(100), catering=money(999), lunches=2, coffee_breaks=3,
                      dinners=1)
    priced = sheet.with_rates(MealRates(lunch=Decimal(25), coffee_break=Decimal(8), dinner=Decimal(45)))
    assert priced.catering == Decimal('119.00')
    assert priced.per_physician == Decimal('219.00')
    assert sheet.catering == Decimal('999.00')


def test_cost_sheet_from_legacy_row():
    sheet = cost_sheet_from_legacy({
        'numeroMedici': '2', 'costoCamera': '120,00', 'costoCityTax': '5', 'costoRistorativo': '60',
        'viaggio': '80', 'numeroPranzi': '2', 'numeroCoffeeBreak': '3', 'numeroCene': '1',
    })
    assert sheet.physicians == 2
    assert sheet.room == Decimal('120.00')
    assert sheet.lunches == 2
    assert sheet.total == Decimal('530.00')


def test_cost_sheet_from_an_empty_row():
    sheet = cost_sheet_from_legacy({})
    assert sheet.physicians == 1
    assert sheet.total == Decimal('0.00')


def test_cost_sheet_survives_junk_values():
    sheet = cost_sheet_from_legacy({'numeroMedici': 'due', 'numeroPranzi': 'tanti'})
    assert sheet.physicians == 1
    assert sheet.lunches == 0


def test_event_totals_multiply_by_physicians():
    sheets = [
        CostSheet(physicians=2, room=money(100), travel=money(50)),
        CostSheet(physicians=1, room=money(200)),
    ]
    totals = event_totals(sheets)
    assert totals['invitations'] == 2
    assert totals['physicians'] == 3
    assert totals['room'] == Decimal('400.00')
    assert totals['travel'] == Decimal('100.00')
    assert totals['total'] == Decimal('500.00')


def test_event_totals_of_nothing():
    totals = event_totals([])
    assert totals['physicians'] == 0
    assert totals['total'] == Decimal('0.00')


def test_budget_check_reports_the_overrun():
    sheets = [CostSheet(physicians=4, room=money(150))]
    exceeded, total, overrun = exceeds_budget(sheets, 500)
    assert exceeded
    assert total == Decimal('600.00')
    assert overrun == Decimal('100.00')


def test_budget_check_within_limit():
    sheets = [CostSheet(physicians=1, room=money(150))]
    exceeded, _total, overrun = exceeds_budget(sheets, 500)
    assert not exceeded
    assert overrun == Decimal('0.00')


def test_serialization_uses_strings_not_floats():
    data = CostSheet(physicians=1, room=money('0.10'), travel=money('0.20')).as_dict()
    assert data['per_physician'] == '0.30'
    assert isinstance(data['total'], str)
