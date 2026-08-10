"""Initial integrations schema

Revision ID: integrations
Revises:
Create Date: 2026-08-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql  # noqa: F401

from indico.core.db.sqlalchemy import UTCDateTime


# revision identifiers, used by Alembic.
revision = 'integrations'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.schema.CreateSchema('plugin_integrations'))
    op.create_table(
        'outbox',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('target', sa.String(), nullable=False),
        sa.Column('topic', sa.String(), nullable=False),
        sa.Column('subject_type', sa.String(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('state', sa.SMALLINT(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_dt', UTCDateTime, nullable=False),
        sa.Column('last_error', sa.Text(), nullable=False),
        sa.Column('external_ref', sa.String(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.Column('delivered_dt', UTCDateTime, nullable=True),
        sa.CheckConstraint('plugin_integrations.outbox.state IN (__[POSTCOMPILE_param_1])', name='ck_outbox_valid_enum_state'),
        schema='plugin_integrations',
    )
    op.create_index('ix_outbox_deliverable', 'outbox', ['state', 'next_attempt_dt'], schema='plugin_integrations')
    op.create_index('ix_outbox_event_id', 'outbox', ['event_id'], schema='plugin_integrations')
    op.create_index('ix_outbox_subject', 'outbox', ['subject_type', 'subject_id'], schema='plugin_integrations')
    op.create_index('ix_outbox_target', 'outbox', ['target'], schema='plugin_integrations')


def downgrade():
    op.drop_table('outbox', schema='plugin_integrations')
    op.execute(sa.schema.DropSchema('plugin_integrations'))
