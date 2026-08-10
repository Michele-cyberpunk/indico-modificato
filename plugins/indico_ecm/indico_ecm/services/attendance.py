# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Turning Indico's timetable and check-ins into the inputs of the rules engine.

Everything here is a translation layer: it reads Indico objects and produces the
pure `Interval` and `ProgramSlot` values the rules engine consumes. No decision
is taken in this module.
"""

from indico.core.db import db
from indico.util.date_time import now_utc

from indico_ecm.models.attendance import AttendanceAdjustment, AttendanceSource, SessionAttendance
from indico_ecm.services.credit_rules import Interval, ProgramSlot


#: Session block titles that are part of the timetable but are not training time
NON_TRAINING_KEYWORDS = ('pausa', 'coffee', 'lunch', 'pranzo', 'registrazione dei partecipanti', 'welcome')


def build_program(event, *, include_all_blocks=False):
    """Build the accredited program of an event from its timetable.

    Only session blocks are considered: they are the granularity at which
    presence is recorded. Breaks are kept in the program but marked as not
    counting, so they neither add nor subtract training time.
    """
    slots = []
    for block in event.session_blocks:
        if block.start_dt is None or block.end_dt is None:
            continue
        title = (block.full_title or '').casefold()
        counts = include_all_blocks or not any(keyword in title for keyword in NON_TRAINING_KEYWORDS)
        slots.append(ProgramSlot(start=block.start_dt, end=block.end_dt, session_id=block.id,
                                 counts_as_training=counts))
    return tuple(sorted(slots, key=lambda slot: (slot.start, slot.end)))


def build_intervals(registration):
    """Build the presence intervals of a registration.

    Rows still open (checked in, never checked out) are dropped rather than
    closed at "now": an open presence is an anomaly for a human to resolve, not
    something to guess at credit time.
    """
    rows = (SessionAttendance.query
            .filter_by(registration_id=registration.id)
            .filter(SessionAttendance.check_out_dt.isnot(None))
            .order_by(SessionAttendance.check_in_dt)
            .all())
    return tuple(Interval(start=row.check_in_dt, end=row.check_out_dt, session_id=row.session_block_id)
                 for row in rows)


def open_attendance(registration):
    """Presences with no exit recorded, which block a clean evaluation."""
    return (SessionAttendance.query
            .filter_by(registration_id=registration.id, check_out_dt=None)
            .order_by(SessionAttendance.check_in_dt)
            .all())


def check_in(registration, *, session_block=None, source=AttendanceSource.qr, device_ref='', user=None,
             when=None):
    """Record an entry.

    Re-scanning while a presence is already open is a no-op: the existing row is
    returned instead of opening a second one, which is what keeps duplicated
    scans from inflating attendance.
    """
    when = when or now_utc()
    existing = (SessionAttendance.query
                .filter_by(registration_id=registration.id, check_out_dt=None,
                           session_block_id=(session_block.id if session_block else None))
                .first())
    if existing is not None:
        return existing
    row = SessionAttendance(
        registration_id=registration.id,
        event_id=registration.event_id,
        session_block_id=(session_block.id if session_block else None),
        check_in_dt=when,
        source=source,
        device_ref=device_ref,
        created_by=user,
    )
    db.session.add(row)
    db.session.flush()
    return row


def check_out(registration, *, session_block=None, source=AttendanceSource.qr, device_ref='', when=None):
    """Record an exit for the currently open presence, if any."""
    when = when or now_utc()
    row = (SessionAttendance.query
           .filter_by(registration_id=registration.id, check_out_dt=None,
                      session_block_id=(session_block.id if session_block else None))
           .order_by(SessionAttendance.check_in_dt.desc())
           .first())
    if row is None:
        return None
    if when < row.check_in_dt:
        raise ValueError('check-out cannot precede check-in')
    row.check_out_dt = when
    if source is not row.source:
        row.device_ref = device_ref or row.device_ref
    db.session.flush()
    return row


def adjust(row, *, user, reason, check_in_dt=None, check_out_dt=None):
    """Correct a presence, leaving a permanent trail.

    A reason and an author are mandatory: attendance decides entitlement, so a
    correction without justification must be impossible by construction.
    """
    if not reason or not reason.strip():
        raise ValueError('an adjustment requires a written reason')
    if user is None:
        raise ValueError('an adjustment requires an authenticated user')
    previous = {'check_in_dt': row.check_in_dt.isoformat(),
                'check_out_dt': row.check_out_dt.isoformat() if row.check_out_dt else None}
    if check_in_dt is not None:
        row.check_in_dt = check_in_dt
    if check_out_dt is not None:
        row.check_out_dt = check_out_dt
    if row.check_out_dt is not None and row.check_out_dt < row.check_in_dt:
        raise ValueError('check-out cannot precede check-in')
    row.is_adjusted = True
    adjustment = AttendanceAdjustment(
        attendance_id=row.id,
        registration_id=row.registration_id,
        action='update',
        previous_values=previous,
        new_values={'check_in_dt': row.check_in_dt.isoformat(),
                    'check_out_dt': row.check_out_dt.isoformat() if row.check_out_dt else None},
        reason=reason.strip(),
        created_by=user,
    )
    db.session.add(adjustment)
    db.session.flush()
    return adjustment
