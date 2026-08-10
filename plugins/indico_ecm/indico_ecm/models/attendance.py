# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.db import db
from indico.core.db.sqlalchemy import PyIntEnum, UTCDateTime
from indico.util.date_time import now_utc
from indico.util.enum import RichIntEnum
from indico.util.i18n import _
from indico.util.string import format_repr


class AttendanceSource(RichIntEnum):
    __titles__ = [None, _('QR / badge'), _('App di check-in'), _('Inserimento manuale'), _('Piattaforma webinar'),
                  _('Importazione')]
    qr = 1
    checkin_app = 2
    manual = 3
    webinar = 4
    import_ = 5


class SessionAttendance(db.Model):
    """Presence of a participant in one slot of the program.

    Indico's core only stores a per-event `checked_in` boolean, which cannot
    support ECM: entitlement depends on how much of the accredited program a
    person actually attended. Each row is one entry/exit pair; several rows per
    participant and slot are normal (leaving the room and coming back).
    """

    __tablename__ = 'session_attendance'
    __table_args__ = (db.CheckConstraint('check_out_dt IS NULL OR check_out_dt >= check_in_dt', 'valid_period'),
                      db.Index('ix_session_attendance_registration', 'registration_id', 'check_in_dt'),
                      {'schema': 'plugin_ecm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    registration_id = db.Column(
        db.Integer,
        db.ForeignKey('event_registration.registrations.id'),
        index=True,
        nullable=False
    )
    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.events.id'),
        index=True,
        nullable=False
    )
    #: The timetable session block the presence refers to; NULL means the whole event
    session_block_id = db.Column(
        db.Integer,
        db.ForeignKey('events.session_blocks.id'),
        index=True,
        nullable=True
    )
    check_in_dt = db.Column(
        UTCDateTime,
        nullable=False
    )
    check_out_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    source = db.Column(
        PyIntEnum(AttendanceSource),
        nullable=False,
        default=AttendanceSource.qr
    )
    #: Identifier of the scanner, kiosk or webinar report the row came from
    device_ref = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: Set when a human corrected or created the row by hand
    is_adjusted = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )

    registration = db.relationship(
        'Registration',
        lazy=True,
        backref=db.backref('ecm_attendance', lazy='dynamic', cascade='all, delete-orphan')
    )
    created_by = db.relationship(
        'User',
        lazy=True
    )

    @property
    def is_open(self):
        """A presence with no exit recorded yet."""
        return self.check_out_dt is None

    def __repr__(self):
        return format_repr(self, 'id', 'registration_id', 'session_block_id', 'check_in_dt', 'check_out_dt')


class AttendanceAdjustment(db.Model):
    """An audit row for every manual change to attendance.

    Attendance decides entitlement, so a correction is never a silent update:
    the previous values, the author and a written reason are kept forever.
    """

    __tablename__ = 'attendance_adjustments'
    __table_args__ = {'schema': 'plugin_ecm'}

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    attendance_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_ecm.session_attendance.id'),
        index=True,
        nullable=True
    )
    registration_id = db.Column(
        db.Integer,
        db.ForeignKey('event_registration.registrations.id'),
        index=True,
        nullable=False
    )
    #: 'create', 'update', 'delete'
    action = db.Column(
        db.String,
        nullable=False
    )
    previous_values = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    new_values = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    reason = db.Column(
        db.Text,
        nullable=False
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=False
    )

    attendance = db.relationship(
        'SessionAttendance',
        lazy=True,
        backref=db.backref('adjustments', lazy='dynamic')
    )
    created_by = db.relationship(
        'User',
        lazy=True
    )

    def __repr__(self):
        return format_repr(self, 'id', 'registration_id', 'action', _text=self.reason[:30])
