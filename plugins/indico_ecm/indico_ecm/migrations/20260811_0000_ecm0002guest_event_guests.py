"""Event guests

Revision ID: ecm0002guest
Revises: ecm0001initi
Create Date: 2026-08-11
"""

import sqlalchemy as sa
from alembic import op

from indico.core.db.sqlalchemy import UTCDateTime


# revision identifiers, used by Alembic.
revision = 'ecm0002guest'
down_revision = 'ecm0001initi'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'event_guests',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=False),
        sa.Column('pax', sa.Integer(), nullable=False),
        sa.Column('arrival', sa.Time(), nullable=True),
        sa.Column('departure', sa.Time(), nullable=True),
        sa.Column('transfer_place', sa.String(), nullable=False),
        sa.Column('own_transport', sa.Boolean(), nullable=False),
        sa.Column('lunch', sa.Boolean(), nullable=False),
        sa.Column('dinner', sa.Boolean(), nullable=False),
        sa.Column('diet_notes', sa.String(), nullable=False),
        sa.Column('notes', sa.String(), nullable=False),
        sa.Column('name_order_certain', sa.Boolean(), nullable=False),
        sa.Column('source_row', sa.String(), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.CheckConstraint('pax > 0', name='pax_positive'),
        schema='plugin_ecm',
    )
    op.create_index('ix_event_guests_event', 'event_guests', ['event_id'], schema='plugin_ecm')

    op.add_column('event_operations',
                  sa.Column('transfer_strategy', sa.String(), nullable=False, server_default='vehicle'),
                  schema='plugin_ecm')
    op.add_column('event_operations',
                  sa.Column('transfer_window', sa.Integer(), nullable=False, server_default='60'),
                  schema='plugin_ecm')
    op.add_column('event_operations',
                  sa.Column('seats_per_vehicle', sa.Integer(), nullable=False, server_default='8'),
                  schema='plugin_ecm')
    for column in ('transfer_strategy', 'transfer_window', 'seats_per_vehicle'):
        op.alter_column('event_operations', column, server_default=None, schema='plugin_ecm')


def downgrade():
    for column in ('seats_per_vehicle', 'transfer_window', 'transfer_strategy'):
        op.drop_column('event_operations', column, schema='plugin_ecm')
    op.drop_table('event_guests', schema='plugin_ecm')
