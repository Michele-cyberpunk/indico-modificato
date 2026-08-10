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


class CRMObjectType(RichIntEnum):
    __titles__ = [None, _('Contatto'), _('Azienda'), _('Opportunità')]
    contact = 1
    company = 2
    opportunity = 3


class IndicoObjectType(RichIntEnum):
    __titles__ = [None, _('Evento'), _('Iscrizione'), _('Persona evento'), _('Contributo'), _('Sessione'),
                  _('Abstract'), _('Documento'), _('Accordo')]
    event = 1
    registration = 2
    event_person = 3
    contribution = 4
    session = 5
    abstract = 6
    receipt_file = 7
    agreement = 8


class LinkSource(RichIntEnum):
    __titles__ = [None, _('Manuale'), _('Segnale'), _('Agente'), _('Importazione')]
    manual = 1
    signal = 2
    agent = 3
    import_ = 4


class ObjectLink(db.Model):
    """The bridge between CRM records and Indico objects.

    This is the only table that knows both worlds, and it is deliberately thin:
    a type, an id on each side, the nature of the relation and where the link
    came from. Anything richer belongs to one of the two sides.

    A link created by an agent (`source=agent`) is expected to be accompanied by
    an `Evidence` row explaining it.
    """

    __tablename__ = 'object_links'
    __table_args__ = (db.Index('ix_uq_object_links', 'crm_type', 'crm_id', 'indico_type', 'indico_id', 'relation',
                               unique=True),
                      db.Index('ix_object_links_indico', 'indico_type', 'indico_id'),
                      {'schema': 'plugin_crm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    crm_type = db.Column(
        PyIntEnum(CRMObjectType),
        nullable=False
    )
    crm_id = db.Column(
        db.Integer,
        nullable=False
    )
    indico_type = db.Column(
        PyIntEnum(IndicoObjectType),
        nullable=False
    )
    indico_id = db.Column(
        db.Integer,
        nullable=False
    )
    #: participant, speaker, moderator, sponsor_of, contract_for…
    relation = db.Column(
        db.String,
        nullable=False
    )
    source = db.Column(
        PyIntEnum(LinkSource),
        nullable=False,
        default=LinkSource.manual
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )

    def __repr__(self):
        return format_repr(self, 'id', 'crm_type', 'crm_id', 'indico_type', 'indico_id', _text=self.relation)
