# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.db import db
from indico.core.db.sqlalchemy import UTCDateTime
from indico.util.date_time import now_utc
from indico.util.string import format_repr


class AssessmentResult(db.Model):
    """The outcome of a learning assessment for one participant.

    Indico's `surveys` module can host the questionnaire, but it has no notion
    of a correct answer or a pass mark, which ECM requires. Attempts are stored
    as separate rows: the history of attempts is part of the record.
    """

    __tablename__ = 'assessment_results'
    __table_args__ = (db.CheckConstraint('total_questions > 0', 'positive_total'),
                      db.CheckConstraint('correct_answers >= 0 AND correct_answers <= total_questions',
                                         'valid_score'),
                      db.Index('ix_assessment_results_registration', 'registration_id', 'created_dt'),
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
    #: The Indico survey the answers came from, when applicable
    survey_submission_id = db.Column(
        db.Integer,
        db.ForeignKey('event_surveys.submissions.id'),
        index=True,
        nullable=True
    )
    attempt = db.Column(
        db.Integer,
        nullable=False,
        default=1
    )
    correct_answers = db.Column(
        db.Integer,
        nullable=False
    )
    total_questions = db.Column(
        db.Integer,
        nullable=False
    )
    #: Per-question detail, kept for disputes
    answer_detail = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )

    registration = db.relationship(
        'Registration',
        lazy=True,
        backref=db.backref('ecm_assessment_results', lazy='dynamic', cascade='all, delete-orphan')
    )

    @property
    def ratio(self):
        return self.correct_answers / self.total_questions

    def __repr__(self):
        return format_repr(self, 'id', 'registration_id', 'attempt', 'correct_answers', 'total_questions')
